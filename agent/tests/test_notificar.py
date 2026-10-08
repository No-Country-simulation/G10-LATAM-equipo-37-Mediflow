"""Tests para el nodo notificar."""
from unittest.mock import patch

from agent.nodes.notificar import notificar


def test_notificar_sin_urgencia_no_publica():
    """Si no hay notificacion_generada, no llama a publicar()."""
    state = {"decision": {}}
    with patch("agent.storage.notifications.publicar") as mock_publicar:
        resultado = notificar(state)
    mock_publicar.assert_not_called()
    # El trace es una lista; el último registro tiene el detalle
    assert resultado["trace"][-1]["detalle"]["enviada"] is False


def test_notificar_con_urgencia_publica():
    """Si hay notificacion_generada, llama a publicar()."""
    state = {
        "decision": {
            "notificacion_generada": {
                "canal": "Alerta_Guardia_Medica",
                "mensaje": "ALERTA URGENTE: TEP agudo para paciente sin identificar.",
            }
        }
    }
    with patch("agent.storage.notifications.publicar") as mock_publicar:
        resultado = notificar(state)
    mock_publicar.assert_called_once_with(
        titulo="Alerta_Guardia_Medica",
        cuerpo="ALERTA URGENTE: TEP agudo para paciente sin identificar.",
    )
    assert resultado["trace"][-1]["detalle"]["enviada"] is True


def test_notificar_maneja_error_de_publicacion():
    """Si publicar() falla, no rompe el flujo (solo loguea)."""
    state = {
        "decision": {
            "notificacion_generada": {
                "canal": "Alerta_Guardia_Medica",
                "mensaje": "ALERTA URGENTE: falla simulada.",
            }
        }
    }
    with patch("agent.storage.notifications.publicar", side_effect=Exception("OCI caído")):
        resultado = notificar(state)
    assert resultado["trace"][-1]["detalle"]["enviada"] is False