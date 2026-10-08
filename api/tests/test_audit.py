"""
api/tests/test_audit.py

Prueba los endpoints reales sobre HTTP con TestClient, monkeypatcheando el
directorio base de agent.storage.local_audit para no tocar ./data/ real.
Sigue el mismo patrón que api/tests/test_api.py (TestClient(app)).
"""

from fastapi.testclient import TestClient

import agent.graph as graph
from agent.revision_runtime import ejecutar
from agent.storage import local, local_audit
from agent.storage.revision import carpeta
from api.main import app

client = TestClient(app)


def preparar_checkpoint(tmp_path, monkeypatch, documento_id):
    """La API N2-05 requiere un grafo pausado, no solo un JSON de muestra."""
    monkeypatch.setattr(local, "DATA_DIR", tmp_path)
    monkeypatch.setenv("OCI_BUCKET", "pruebas")
    monkeypatch.setenv("MEDIFLOW_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite3"))
    monkeypatch.setattr(local_audit, "DATA_DIR", carpeta(documento_id).parent)
    for nombre in ("normalizar", "clasificar", "extraer"):
        monkeypatch.setattr(graph, nombre, lambda s: {})
    ejecutar({"documento_id": documento_id, "tipo_archivo": "TEXTO", "texto": "Ejemplo",
              "legibilidad": 1.0, "trace": [],
              "clasificacion": {"tipo_documento": "Receta Medica", "score_confianza_clasificacion": 0.5},
              "datos_extraidos": {"paciente": {"nombre": "Ana"}, "medicamentos": []}})


def test_cola_vacia_al_inicio(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    r = client.get("/queue/human")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_documento_aparece_en_cola(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)

    r = client.get("/queue/human")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["documento_id"] == "DOC-001"


def test_auditar_aprobar_devuelve_200_y_registra_resolucion(tmp_path, monkeypatch):
    preparar_checkpoint(tmp_path, monkeypatch, "DOC-001")

    r = client.post(
        "/audit/DOC-001",
        json={"accion": "aprobar", "revisor": "Carolina", "motivo": "Datos correctos"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["documento_id"] == "DOC-001"
    assert cuerpo["resolucion"]["accion"] == "aprobar"
    assert cuerpo["resolucion"]["revisor"] == "Carolina"
    assert "fecha" in cuerpo["resolucion"]


def test_auditar_documento_inexistente_da_404(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    r = client.post(
        "/audit/NO-EXISTE",
        json={"accion": "aprobar", "revisor": "Carolina", "motivo": "x"},
    )
    assert r.status_code == 404


def test_auditar_accion_invalida_da_422(tmp_path, monkeypatch):
    """FastAPI/Pydantic rechaza el body antes de llegar a la lógica, por el
    Literal["aprobar", "corregir", "rechazar"] del schema."""
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.post(
        "/audit/DOC-001",
        json={"accion": "aprobar_mal", "revisor": "Carolina", "motivo": "x"},
    )
    assert r.status_code == 422


def test_auditar_dos_veces_el_mismo_documento_da_409(tmp_path, monkeypatch):
    preparar_checkpoint(tmp_path, monkeypatch, "DOC-001")
    client.post("/audit/DOC-001", json={"accion": "aprobar", "revisor": "Carolina", "motivo": "ok"})

    r = client.post("/audit/DOC-001", json={"accion": "rechazar", "revisor": "Carolina", "motivo": "otra vez"})
    assert r.status_code == 409


def test_auditar_corregir_con_correcciones(tmp_path, monkeypatch):
    preparar_checkpoint(tmp_path, monkeypatch, "DOC-002")

    r = client.post(
        "/audit/DOC-002",
        json={
            "accion": "corregir",
            "revisor": "Carolina",
            "motivo": "Falta matricula",
            "correcciones": {"medico_solicitante.matricula": "12345"},
        },
    )
    assert r.status_code == 200
    assert r.json()["resolucion"]["correcciones"] == {"medico_solicitante.matricula": "12345"}


def test_documento_resuelto_desaparece_de_la_cola(tmp_path, monkeypatch):
    preparar_checkpoint(tmp_path, monkeypatch, "DOC-001")
    client.post("/audit/DOC-001", json={"accion": "aprobar", "revisor": "Carolina", "motivo": "ok"})

    r = client.get("/queue/human")
    assert r.json() == {"items": []}
