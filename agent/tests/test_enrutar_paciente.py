"""La alerta puede omitir el nombre del paciente (ALERTA_OCULTAR_PACIENTE)."""
from agent.nodes.enrutar import enrutar

STATE = {
    "clasificacion": {"tipo_documento": "Receta"},
    "score": 0.9,
    "legibilidad": 0.9,
    "urgencia": {"detectada": True, "motivos": ["TEP agudo"]},
    "datos_extraidos": {"paciente": {"nome": "Juan Pérez"}},
}


def test_alerta_incluye_paciente_por_defecto(monkeypatch):
    monkeypatch.delenv("ALERTA_OCULTAR_PACIENTE", raising=False)
    msg = enrutar(STATE)["decision"]["notificacion_generada"]["mensaje"]
    assert "Juan Pérez" in msg


def test_alerta_omite_paciente_si_se_configura(monkeypatch):
    monkeypatch.setenv("ALERTA_OCULTAR_PACIENTE", "true")
    msg = enrutar(STATE)["decision"]["notificacion_generada"]["mensaje"]
    assert "Juan Pérez" not in msg
