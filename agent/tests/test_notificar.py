from unittest.mock import patch

from agent.nodes.notificar import notificar


def test_notificar_publica_alerta_generada():
    state = {
        "decision": {
            "notificacion_generada": {
                "canal": "Alerta_Guardia_Medica",
                "mensaje": "ALERTA URGENTE: evento de prueba.",
            }
        }
    }

    with patch("agent.storage.notifications.publicar") as publicar:
        resultado = notificar(state)

    publicar.assert_called_once_with(
        titulo="Alerta_Guardia_Medica",
        cuerpo="ALERTA URGENTE: evento de prueba.",
    )
    assert resultado["trace"][-1]["detalle"]["enviada"] is True


def test_notificar_sin_alerta_no_publica():
    with patch("agent.storage.notifications.publicar") as publicar:
        resultado = notificar({"decision": {}})

    publicar.assert_not_called()
    assert resultado["trace"][-1]["detalle"]["enviada"] is False


def test_notificar_no_interrumpe_el_flujo_si_falla_publicar():
    state = {
        "decision": {
            "notificacion_generada": {
                "canal": "Alerta_Guardia_Medica",
                "mensaje": "Alerta de prueba.",
            }
        }
    }
    with patch("agent.storage.notifications.publicar", side_effect=RuntimeError("webhook caído")):
        resultado = notificar(state)

    assert resultado["trace"][-1]["detalle"]["enviada"] is False
