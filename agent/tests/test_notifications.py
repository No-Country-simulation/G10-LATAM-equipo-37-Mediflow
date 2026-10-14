from unittest.mock import Mock, patch

from agent.storage.notifications import publicar


def test_publicar_usa_n8n_y_envia_el_payload(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/mediflow-alert")
    respuesta = Mock()

    with patch("httpx.post", return_value=respuesta) as post:
        publicar("Alerta_Guardia_Medica", "Urgencia de prueba")

    post.assert_called_once_with(
        "http://n8n:5678/webhook/mediflow-alert",
        json={"titulo": "Alerta_Guardia_Medica", "cuerpo": "Urgencia de prueba"},
        timeout=10,
    )
    respuesta.raise_for_status.assert_called_once_with()
