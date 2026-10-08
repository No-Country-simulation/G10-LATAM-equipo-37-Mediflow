"""N2-05: SQLite real, reinicio, API, rechazo y reentrada sin LLM/OCI."""
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import agent.graph as graph
from agent.nodes.revision_humana import DecisionHumana, aplicar_decision
from agent.revision_runtime import RevisionConflicto, ejecutar, reanudar, sesion
from agent.storage import local
from agent.storage.revision import carpeta
from api.main import app


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "DATA_DIR", tmp_path)
    monkeypatch.setenv("MEDIFLOW_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite3"))
    monkeypatch.setenv("OCI_BUCKET", "pruebas")
    # Solo OCR/LLM son simulados. Validación, puntuación, urgencia y almacenamiento son reales.
    for nombre in ("normalizar", "clasificar", "extraer"):
        monkeypatch.setattr(graph, nombre, lambda s: {})
    return tmp_path


def estado(doc="N205", urgente=False):
    return {"documento_id": doc, "tipo_archivo": "TEXTO", "texto": "Documento de prueba",
            "legibilidad": 1.0, "trace": [],
            "clasificacion": {"tipo_documento": "Receta Medica", "score_confianza_clasificacion": 0.99,
                              "nivel_prioridad": "Urgente" if urgente else "Rutina"},
            "datos_extraidos": {"paciente": {"nombre": None},
                                "medico_solicitante": {"nombre": "Profesional", "matricula": "123"},
                                "medicamentos": [{"nombre": "Amoxicilina", "dosis": "500 mg",
                                                  "frecuencia": "cada 8 horas"}]}}


def test_sqlite_no_guarda_datos_clinicos(entorno):
    s = estado()
    s["datos_extraidos"]["paciente"]["nombre"] = "NombreReservadoN205"
    s["datos_extraidos"]["medico_solicitante"]["matricula"] = None
    ejecutar(s)
    assert b"NombreReservadoN205" not in (entorno / "checkpoints.sqlite3").read_bytes()
    assert list((entorno / "pruebas/checkpoints").glob("*.bin"))


def decision(accion="aprobar", **extra):
    return {"accion": accion, "revisor": "Auditor de pruebas", "motivo": "Verificado", **extra}


def test_pausa_y_reinicio_sqlite(entorno):
    inicial = ejecutar(estado())
    assert inicial["__interrupt__"]
    with sesion("N205") as (g, config):
        assert g.get_state(config).next == ("revision_humana",)
    respuesta = reanudar("N205", decision())  # otra conexión y otro grafo
    assert respuesta["decision_enrutamiento"]["destino_principal"] == "Farmacia_Hospitalaria"
    assert (carpeta("N205") / "resolucion.json").exists()
    with pytest.raises(RevisionConflicto):
        reanudar("N205", decision())


def test_rechazo_no_continua(entorno):
    ejecutar(estado())
    respuesta = reanudar("N205", decision("rechazar"))
    assert respuesta["status"] == "rechazado"
    assert respuesta["decision_enrutamiento"] is None
    assert (entorno / "pruebas/rechazados/N205.json").exists()
    assert not (entorno / "pruebas/procesados/farmacia/N205.json").exists()


def test_corregir_revalida_y_resuelve(entorno):
    ejecutar(estado())
    r = reanudar("N205", decision("corregir", correcciones={"paciente.nombre": "Ana"}))
    assert r["status"] == "procesado"
    guardado = json.loads((entorno / "pruebas/procesados/farmacia/N205.json").read_text())
    assert guardado["datos_extraidos"]["paciente"]["nombre"] == "Ana"
    assert not guardado["validacion"].get("categoria_amb")


def test_corregir_incompleto_vuelve_a_cola_con_historia(entorno):
    ejecutar(estado())
    entrada = decision("corregir", correcciones={"paciente.edad": 40}, revision_version=1)
    r = reanudar("N205", entrada)
    assert r["status"] == "revision_humana"
    assert (carpeta("N205") / "resolucion_1.json").exists()
    assert not (carpeta("N205") / "resolucion.json").exists()
    assert json.loads((carpeta("N205") / "extraccion.json").read_text())["revision_version"] == 2
    with pytest.raises(RevisionConflicto):
        reanudar("N205", entrada)
    reanudar("N205", decision("rechazar", revision_version=2))


def test_urgencia_notificada_antes_de_pausa(entorno):
    r = ejecutar(estado(urgente=True))
    assert r["decision"]["destino_principal"] == "Cola_Emergencia_Medica"
    assert any(t["nodo"] == "notificar" for t in r["trace"])
    aprobado = reanudar("N205", decision())
    assert aprobado["decision_enrutamiento"]["destino_principal"] == "Cola_Emergencia_Medica"


def test_alto_riesgo_recalculado(entorno):
    ejecutar(estado())
    r = reanudar("N205", decision("corregir", correcciones={"paciente.nombre": "Ana", "medicamentos": [
        {"nombre": "Insulina glargina", "dosis": "10 UI", "frecuencia": "cada 24 horas"}]}))
    assert r["decision_enrutamiento"]["destino_principal"] == "Farmacia_Hospitalaria"
    assert r["decision_enrutamiento"]["requiere_auditoria_humana"]
    data = json.loads((carpeta("N205") / "extraccion.json").read_text())
    assert data["datos_extraidos"]["medicamentos"][0]["alto_riesgo"]


@pytest.mark.parametrize("cambios", [{"paciente.nome": "Ana"}, {"score": 1},
    {"medicamentos[0].dosis": "500 mg"}, {"medicamentos": [{"alto_riesgo": False}]},
    {"paciente.edad": "cuarenta"}, {"clasificacion.tipo_documento": "Inventado"}])
def test_correcciones_invalidas_no_consumen_revision(entorno, cambios):
    ejecutar(estado())
    with pytest.raises((ValueError, ValidationError)):
        reanudar("N205", decision("corregir", correcciones=cambios))
    assert reanudar("N205", decision("rechazar"))["status"] == "rechazado"


@pytest.mark.parametrize("campos", [{"revisor": " "}, {"motivo": " "},
    {"accion": "aprobar", "correcciones": {}}, {"accion": "corregir"}])
def test_contrato_decision(campos):
    with pytest.raises(ValidationError):
        DecisionHumana.model_validate({**decision(), **campos})


def test_no_muta_original(entorno):
    s = ejecutar(estado())
    original = deepcopy(s)
    aplicar_decision(s, decision("corregir", correcciones={"paciente.nombre": "Ana"}))
    assert s == original


def test_api_reanuda_y_rechaza_duplicado(entorno):
    ejecutar(estado())
    with TestClient(app) as client:
        r = client.post("/audit/N205", json=decision())
        assert r.status_code == 200, r.text
        assert r.json()["decision_enrutamiento"]["destino_principal"] == "Farmacia_Hospitalaria"
        assert client.post("/audit/N205", json=decision()).status_code == 409
        assert client.post("/audit/inexistente", json=decision()).status_code == 404


def test_fallo_persistencia_se_recupera_sin_reaplicar(entorno, monkeypatch):
    import agent.storage.revision as archivos
    ejecutar(estado())
    real = archivos.persistir
    monkeypatch.setattr(archivos, "persistir", lambda s: {"almacenamiento": {"status_backup": "error"}})
    entrada = decision("corregir", correcciones={"paciente.nombre": "Ana"})
    with pytest.raises(OSError):
        reanudar("N205", entrada)
    assert not (carpeta("N205") / "resolucion.json").exists()
    monkeypatch.setattr(archivos, "persistir", real)
    assert reanudar("N205", entrada)["status"] == "procesado"


def test_version_antigua_no_aplica(entorno):
    ejecutar(estado())
    reanudar("N205", decision("corregir", correcciones={"paciente.edad": 40}))
    with pytest.raises(RevisionConflicto):
        reanudar("N205", decision("rechazar", revision_version=1))


def test_nueva_urgencia_invoca_notificacion(entorno, monkeypatch):
    import agent.storage.revision as archivos
    llamadas = []
    monkeypatch.setattr(archivos, "notificar", lambda s: llamadas.append(s["documento_id"]) or {})
    ejecutar(estado())
    r = reanudar("N205", decision("corregir", correcciones={"clasificacion.nivel_prioridad": "Urgente"}))
    assert r["decision_enrutamiento"]["destino_principal"] == "Cola_Emergencia_Medica"
    assert llamadas == ["N205"]


def test_amb6_no_fuerza_destino_al_aprobar(entorno):
    s = estado()
    s["clasificacion"]["tipo_documento"] = "Otro"
    ejecutar(s)
    with pytest.raises(ValueError):
        reanudar("N205", decision())
    assert reanudar("N205", decision("rechazar"))["status"] == "rechazado"
