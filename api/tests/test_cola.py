
"""Pruebas de la cola de triaje y sus resultados."""
import pytest
from fastapi.testclient import TestClient

from agent.storage import triage_results
from api.main import app


@pytest.fixture
def cliente_y_db_temporal(tmp_path, monkeypatch):
    """Usa una base SQLite temporal para no modificar datos reales."""
    monkeypatch.setattr(
        triage_results,
        "DB_PATH",
        tmp_path / "triage_test.sqlite3",
    )
    return TestClient(app)


def resultado_ejemplo():
    """Crea un resultado mínimo para las pruebas."""
    return {
        "documento_id": "DOC-TEST-001",
        "decision_enrutamiento": {
            "destino_principal": "Cola_Revision_Humana"
        },
        "score_confianza": 0.82,
        "datos_extraidos": {},
    }


def test_listar_triage(cliente_y_db_temporal):
    triage_results.guardar_resultado(resultado_ejemplo())

    respuesta = cliente_y_db_temporal.get("/triage")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos["items"]) == 1
    assert datos["items"][0]["documento_id"] == "DOC-TEST-001"
    assert datos["items"][0]["destino"] == "Cola_Revision_Humana"
    assert datos["items"][0]["score"] == 0.82


def test_obtener_triage_por_id(cliente_y_db_temporal):
    triage_results.guardar_resultado(resultado_ejemplo())

    respuesta = cliente_y_db_temporal.get("/triage/DOC-TEST-001")

    assert respuesta.status_code == 200
    assert respuesta.json()["documento_id"] == "DOC-TEST-001"
    assert respuesta.json()["score_confianza"] == 0.82


def test_triage_no_encontrado(cliente_y_db_temporal):
    respuesta = cliente_y_db_temporal.get("/triage/DOC-INEXISTENTE")

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "Documento no encontrado"



def test_post_triage_guarda_resultado(cliente_y_db_temporal, monkeypatch):
    """Comprueba que POST /triage persiste el resultado."""
    from api import main
    from agent.schemas.contrato import TriageResponse

    resultado_simulado = {
        "documento_id": "DOC-POST-001",
        "decision_enrutamiento": {
            "destino_principal": "Cola_Revision_Humana"
        },
        "score_confianza": 0.91,
    }

    respuesta_valida = TriageResponse.model_validate({
        "status": "revision_humana",
        "documento_id": "DOC-POST-001",
        "clasificacion": {
            "tipo_documento": "Receta Medica",
            "nivel_prioridad": "Rutina",
            "score_confianza_clasificacion": 0.91,
        },
        "datos_extraidos": {},
        "decision_enrutamiento": {
            "destino_principal": "Cola_Revision_Humana",
            "requiere_auditoria_humana": True,
            "justificacion_enrutamiento": "Resultado simulado para pruebas",
        },
        "almacenamiento_oci": {
            "bucket": "test",
            "ruta_objeto": "test/DOC-POST-001",
            "status_backup": "pendiente",
        },
        "score_confianza": 0.91,
    })

    monkeypatch.setattr(
        main,
        "run_triage",
        lambda *args, **kwargs: resultado_simulado,
    )
    monkeypatch.setattr(
        main,
        "_a_respuesta",
        lambda resultado: respuesta_valida,
    )

    respuesta = cliente_y_db_temporal.post(
        "/triage",
        json={
            "documento_id": "DOC-POST-001",
            "tipo_archivo": "TEXTO",
            "documento_texto": "Documento de prueba",
            "canal_origen": "test",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["documento_id"] == "DOC-POST-001"

    guardado = triage_results.obtener_resultado("DOC-POST-001")
    assert guardado is not None
    assert guardado["documento_id"] == "DOC-POST-001"
    assert guardado["score_confianza"] == 0.91