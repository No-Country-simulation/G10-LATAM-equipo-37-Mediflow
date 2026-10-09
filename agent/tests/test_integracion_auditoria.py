"""Regresiones de integración: backend, bucket, original y versión del panel.

El backend remoto se simula en memoria: estas pruebas no certifican IAM ni OCI real.
"""
import importlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import agent.graph as graph
import api.main as api
from agent.revision_runtime import ejecutar, reanudar
from agent.storage import checkpoint_payload, local, local_audit, revision
from agent.tests.test_revision_humana import decision, estado
from ui.auditoria import armar_decision, normalizar_item


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "DATA_DIR", tmp_path)
    monkeypatch.setenv("MEDIFLOW_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite3"))
    monkeypatch.delenv("OCI_BUCKET", raising=False)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("OCI_BUCKET_PROD", "pruebas-produccion")
    for nombre in ("normalizar", "clasificar", "extraer"):
        monkeypatch.setattr(graph, nombre, lambda s: {})
    return tmp_path


class StorageMemoria:
    def __init__(self):
        self.objetos = {}

    def upload_bytes(self, bucket, ruta, contenido, **kwargs):
        self.objetos[bucket, ruta] = contenido

    def upload_json(self, bucket, ruta, contenido):
        self.upload_bytes(bucket, ruta, json.dumps(contenido).encode())

    def download(self, bucket, ruta):
        return self.objetos[bucket, ruta]

    def list_prefix(self, bucket, prefijo):
        return sorted(r for b, r in self.objetos if b == bucket and r.startswith(prefijo))


@pytest.mark.parametrize("remoto", [False, True])
def test_ciclo_api_panel_historial_mismo_backend(entorno, monkeypatch, remoto):
    almacenamiento = StorageMemoria() if remoto else local
    # persistir puede haber sido recargado por la suite existente: parchear el módulo
    # de la función conservada por graph, además del import actual.
    monkeypatch.setitem(graph.persistir.__globals__, "storage", almacenamiento)
    for modulo in (local_audit, checkpoint_payload, revision, api):
        monkeypatch.setattr(modulo, "storage", almacenamiento)
    s = estado("INTEGRACION")
    s["tipo_archivo"] = "PDF"
    s["ruta_original"] = "recibidos/INTEGRACION/original"
    original = b"%PDF-1.4\noriginal sintetico de prueba"
    almacenamiento.upload_bytes("pruebas-produccion", s["ruta_original"], original)
    ejecutar(s)
    client = TestClient(api.app)
    item = normalizar_item(client.get("/queue/human").json()["items"][0])
    extraccion = item["extraccion"]
    assert extraccion["clasificacion"]["tipo_documento"] == "Receta Medica"
    assert extraccion["revision_version"] == 1
    assert client.get("/audit/INTEGRACION/original").content == original
    entrada = armar_decision("corregir", "Auditor", "Corrección parcial",
                             {"paciente.edad": 40}, revision_version=extraccion["revision_version"])
    assert client.post("/audit/INTEGRACION", json=entrada).json()["status"] == "revision_humana"
    assert client.post("/audit/INTEGRACION", json=entrada).status_code == 409
    nueva = client.get("/queue/human").json()["items"][0]["extraccion"]
    assert nueva["revision_version"] == 2
    respuesta = client.post("/audit/INTEGRACION", json=decision("rechazar", revision_version=2))
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "rechazado"
    assert client.get("/queue/human").json() == {"items": []}
    rutas = almacenamiento.list_prefix("pruebas-produccion", "auditoria_humana/")
    assert "auditoria_humana/INTEGRACION/resolucion_1.json" in rutas
    assert "auditoria_humana/INTEGRACION/resolucion.json" in rutas
    assert almacenamiento.list_prefix("pruebas-produccion", "checkpoints/")
    if remoto:
        assert not (entorno / "pruebas-produccion").exists()


def test_fallo_copia_original_no_publica_exito_y_reintento_recupera(entorno):
    s = estado("FALLO-ORIGINAL")
    s["tipo_archivo"] = "PDF"
    s["ruta_original"] = "recibidos/pendiente.pdf"
    with pytest.raises(OSError):
        ejecutar(s)
    local.upload_bytes("pruebas-produccion", s["ruta_original"], b"%PDF-1.4 prueba")
    assert ejecutar(s)["__interrupt__"]
    assert reanudar(s["documento_id"], decision("rechazar"))["status"] == "rechazado"


def test_upload_conserva_bytes_y_no_sustituye_original_de_checkpoint(entorno, monkeypatch):
    from agent.ingestion import IngestedDocument
    monkeypatch.setattr(api, "ingest_document", lambda *a, **kw: IngestedDocument("PDF", "", legibilidad=0))
    client = TestClient(api.app)
    original = b"%PDF-1.4\nDocumento original de prueba"
    r = client.post("/triage/upload", data={"documento_id": "UPLOAD"},
                    files={"archivo": ("prueba.pdf", original, "application/pdf")})
    assert r.status_code == 200
    assert client.get("/audit/UPLOAD/original").content == original
    r = client.post("/triage/upload", data={"documento_id": "UPLOAD"},
                    files={"archivo": ("otro.pdf", b"%PDF-1.4 diferente", "application/pdf")})
    assert r.status_code == 200
    assert client.get("/audit/UPLOAD/original").content == original


@pytest.mark.parametrize("documento_id", ["../escape", "a:b", "a\\b", "x\x00y"])
def test_api_rechaza_identificador_inseguro(entorno, documento_id):
    r = TestClient(api.app).post("/triage", json={"documento_id": documento_id, "tipo_archivo": "TEXTO",
                                                 "documento_texto": "prueba", "canal_origen": "web"})
    assert r.status_code == 422


def test_oci_listado_paginado(monkeypatch):
    modulo = importlib.import_module("agent.storage.object_storage")
    llamadas = []

    def listado(ns, bucket, **kwargs):
        llamadas.append(kwargs)
        pagina = (SimpleNamespace(objects=[SimpleNamespace(name="auditoria_humana/A/extraccion.json")],
                                  next_start_with="siguiente") if "start" not in kwargs else
                  SimpleNamespace(objects=[SimpleNamespace(name="auditoria_humana/B/extraccion.json")],
                                  next_start_with=None))
        return SimpleNamespace(data=pagina)

    monkeypatch.setattr(modulo, "_client", lambda: SimpleNamespace(list_objects=listado))
    monkeypatch.setattr(modulo, "namespace", lambda: "ns")
    assert len(modulo.list_prefix("bucket", "auditoria_humana/")) == 2
    assert llamadas[1]["start"] == "siguiente"


def test_api_fallo_persistencia_es_503_sin_datos_privados(entorno, monkeypatch):
    def falla(*args, **kwargs):
        raise OSError("NombrePacientePrivado ruta/privada")
    monkeypatch.setattr(api, "run_triage", falla)
    r = TestClient(api.app).post("/triage", json={"documento_id": "FALLO", "tipo_archivo": "TEXTO",
                                                 "documento_texto": "prueba", "canal_origen": "web"})
    assert r.status_code == 503
    assert "NombrePacientePrivado" not in r.text
