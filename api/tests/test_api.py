import json
from pathlib import Path

from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app

client = TestClient(app)
EJEMPLO = json.loads((Path(__file__).parents[2] / "docs" / "examples" / "triage_request.json").read_text())


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_triage_ejemplo():
    r = client.post("/triage", json=EJEMPLO)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["documento_id"] == EJEMPLO["documento_id"]
    assert cuerpo["decision_enrutamiento"]["destino_principal"] == "Cola_Emergencia_Medica"
    assert set(cuerpo) >= {"status", "clasificacion", "datos_extraidos", "decision_enrutamiento", "almacenamiento_oci"}


def test_upload_rechaza_documento_id_con_ruta(monkeypatch):
    def no_debe_guardar(*args, **kwargs):
        raise AssertionError("No debe guardar un identificador inválido")

    monkeypatch.setattr(api_main.upload_storage, "upload_bytes", no_debe_guardar)

    respuesta = client.post(
        "/triage/upload",
        data={"documento_id": "../TEST-03"},
        files={"archivo": ("receta.txt", b"Receta de prueba", "text/plain")},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == "documento_id no válido"


def test_upload_no_ejecuta_triage_si_falla_el_almacenamiento(monkeypatch):
    def fallo_almacenamiento(*args, **kwargs):
        raise OSError("Fallo simulado")

    def triage_no_debe_ejecutarse(*args, **kwargs):
        raise AssertionError("La triage no debe ejecutarse si falla el almacenamiento")

    monkeypatch.setattr(api_main.upload_storage, "upload_bytes", fallo_almacenamiento)
    monkeypatch.setattr(api_main, "run_triage", triage_no_debe_ejecutarse)

    respuesta = client.post(
        "/triage/upload",
        data={"documento_id": "TEST-503"},
        files={"archivo": ("receta.txt", b"Receta de prueba", "text/plain")},
    )

    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == "No se pudo guardar el archivo original"


def test_upload_guarda_original_antes_de_executar_triage(monkeypatch):
    chamadas = []

    def guardar_original(bucket, ruta, data, content_type):
        chamadas.append({
            "bucket": bucket,
            "ruta": ruta,
            "data": data,
            "content_type": content_type,
        })

    def simular_triage(*args, **kwargs):
        assert len(chamadas) == 1
        assert chamadas[0]["ruta"] == "recibidos/TEST-04.txt"
        assert chamadas[0]["data"] == b"Receta de prueba"

        return {
            "documento_id": "TEST-04",
            "decision": {
                "destino_principal": "Cola_Revision_Humana",
                "requiere_auditoria_humana": True,
                "justificacion_enrutamiento": "Prueba de almacenamiento",
            },
            "almacenamiento": {
                "bucket": "test-bucket",
                "ruta_objeto": "recibidos/TEST-04.txt",
                "status_backup": "exito",
            },
        }

    monkeypatch.setattr(
        api_main.upload_storage, "upload_bytes", guardar_original
    )
    monkeypatch.setattr(api_main, "run_triage", simular_triage)

    respuesta = client.post(
        "/triage/upload",
        data={"documento_id": "TEST-04", "canal_origen": "web"},
        files={
            "archivo": (
                "receta.txt",
                b"Receta de prueba",
                "text/plain",
            )
        },
    )

    assert len(chamadas) == 1
    assert chamadas[0]["content_type"] == "text/plain"
    assert respuesta.status_code == 200