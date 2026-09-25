"""Pruebas del enrutamiento. Fijan las reglas del diagrama del README, no la implementación.

Cada prueba arma el estado a mano, así que no llama al modelo y corre en el CI con USE_LLM=false.
"""
from agent.nodes.enrutar import enrutar
from agent.rules.loader import load_rules

REGLAS = load_rules()
UMBRALES = REGLAS["umbrales"]
DESTINOS = REGLAS["destinos"]


def _estado(**cambios):
    base = {
        "documento_id": "TEST",
        "legibilidad": 1.0,
        "score": 0.95,
        "clasificacion": {"tipo_documento": "Informe de Laboratorio"},
        "validacion": {"conflictos": []},
        "urgencia": {"detectada": False},
        "datos_extraidos": {"paciente": {"nombre": "Ana Pérez"}},
        "trace": [],
    }
    base.update(cambios)
    return base


def _decision(**cambios):
    return enrutar(_estado(**cambios))["decision"]


# --------------------------------------------------------------------------- urgencia
def test_urgencia_limpia_va_a_emergencia_sin_auditoria():
    d = _decision(urgencia={"detectada": True, "motivos": ["tromboembolismo pulmonar"]})
    assert d["destino_principal"] == DESTINOS["urgencia"]
    assert d["requiere_auditoria_humana"] is False
    assert d["notificacion_generada"] is not None


def test_urgencia_con_ambiguedad_va_a_emergencia_y_ademas_se_audita():
    """Se atiende primero y se revisa después: la alerta sale igual, pero queda marcada."""
    d = _decision(
        urgencia={"detectada": True, "motivos": ["hiperpotasemia severa"]},
        validacion={"conflictos": ["edad no coincide con la fecha de nacimiento"]},
        score=0.90,
    )
    assert d["destino_principal"] == DESTINOS["urgencia"]
    assert d["requiere_auditoria_humana"] is True
    assert d["notificacion_generada"] is not None


def test_urgencia_con_score_bajo_se_audita():
    d = _decision(urgencia={"detectada": True, "motivos": ["sepsis"]}, score=0.40)
    assert d["destino_principal"] == DESTINOS["urgencia"]
    assert d["requiere_auditoria_humana"] is True


def test_la_notificacion_nombra_al_paciente():
    """El campo es `nombre` en todo el proyecto: si alguien escribe `nome`, esta prueba lo detecta."""
    d = _decision(
        urgencia={"detectada": True, "motivos": ["infarto agudo de miocardio"]},
        datos_extraidos={"paciente": {"nombre": "Ana Pérez"}},
    )
    assert "Ana Pérez" in d["notificacion_generada"]["mensaje"]


def test_la_notificacion_avisa_cuando_no_hay_nombre():
    d = _decision(
        urgencia={"detectada": True, "motivos": ["sepsis"]},
        datos_extraidos={"paciente": {}},
    )
    assert "paciente sin identificar" in d["notificacion_generada"]["mensaje"]


# --------------------------------------------------------------------------- revisión humana
def test_tipo_desconocido_va_a_revision_y_siempre_con_auditoria():
    """Un documento en la cola de revisión nunca puede declararse automático."""
    d = _decision(clasificacion={"tipo_documento": "Otro"}, score=0.99)
    assert d["destino_principal"] == DESTINOS["revision"]
    assert d["requiere_auditoria_humana"] is True
    assert "revisión humana" in d["justificacion_enrutamiento"]


def test_fuera_de_alcance_va_a_revision_con_auditoria():
    """FA-01 a FA-04 y FA-06: el agente deriva en vez de forzar el documento a un tipo que no es."""
    d = _decision(
        clasificacion={"tipo_documento": "Otro"},
        validacion={"conflictos": [], "categoria_amb": "AMB-6"},
        score=0.95,
    )
    assert d["destino_principal"] == DESTINOS["revision"]
    assert d["requiere_auditoria_humana"] is True
    assert d["notificacion_generada"] is None


def test_documento_ilegible_va_a_revision():
    d = _decision(legibilidad=0.1)
    assert d["destino_principal"] == DESTINOS["revision"]
    assert d["requiere_auditoria_humana"] is True


def test_conflictos_sin_urgencia_van_a_revision():
    d = _decision(validacion={"conflictos": ["dosis fuera de rango"]})
    assert d["destino_principal"] == DESTINOS["revision"]
    assert d["requiere_auditoria_humana"] is True


def test_score_bajo_va_a_revision():
    d = _decision(score=0.30)
    assert d["destino_principal"] == DESTINOS["revision"]
    assert d["requiere_auditoria_humana"] is True


# --------------------------------------------------------------------------- caminos normales
def test_documento_de_rutina_se_enruta_solo():
    d = _decision()
    assert d["destino_principal"] == DESTINOS["por_tipo"]["Informe de Laboratorio"]
    assert d["requiere_auditoria_humana"] is False
    assert d["notificacion_generada"] is None


def test_receta_de_alto_riesgo_va_a_farmacia_con_auditoria_y_sin_alerta():
    d = _decision(
        clasificacion={"tipo_documento": "Receta Medica"},
        urgencia={"detectada": False, "alto_riesgo_farmacologico": ["warfarina"]},
    )
    assert d["destino_principal"] == DESTINOS["por_tipo"]["Receta Medica"]
    assert d["requiere_auditoria_humana"] is True
    assert d["notificacion_generada"] is None, "el alto riesgo no genera alerta de guardia"


def test_score_entre_umbrales_se_enruta_pero_se_audita():
    medio = (UMBRALES["segunda_opinion"] + UMBRALES["automatico"]) / 2
    d = _decision(score=medio)
    assert d["destino_principal"] == DESTINOS["por_tipo"]["Informe de Laboratorio"]
    assert d["requiere_auditoria_humana"] is True
