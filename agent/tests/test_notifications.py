"""Tests de publicar(): prioridad y respaldo entre canales."""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from agent.storage.notifications import publicar

N8N = "http://n8n:5678/webhook/mediflow-alert"
DISCORD = "https://discord.test/hook"


@pytest.fixture(autouse=True)
def _sin_canales(monkeypatch):
    for var in ("N8N_WEBHOOK_URL", "DISCORD_WEBHOOK_URL", "ONS_TOPIC_OCID"):
        monkeypatch.delenv(var, raising=False)


def test_publicar_usa_n8n_y_envia_el_payload(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", N8N)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD)
    respuesta = Mock()
    with patch("httpx.post", return_value=respuesta) as post:
        publicar("Alerta_Guardia_Medica", "Urgencia de prueba")
    post.assert_called_once_with(
        N8N, json={"titulo": "Alerta_Guardia_Medica", "cuerpo": "Urgencia de prueba"}, timeout=10
    )
    respuesta.raise_for_status.assert_called_once_with()


def test_publicar_si_n8n_falla_cae_a_discord(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", N8N)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD)
    with patch("agent.storage.notifications._publicar_oci") as oci, patch(
        "httpx.post", side_effect=[RuntimeError("n8n caído"), Mock()]
    ) as post:
        publicar("T", "C")
    assert [c.args[0] for c in post.call_args_list] == [N8N, DISCORD]
    oci.assert_not_called()


def test_publicar_si_n8n_y_discord_fallan_cae_a_oci(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", N8N)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD)
    monkeypatch.setenv("ONS_TOPIC_OCID", "ocid1.test")
    with patch("agent.storage.notifications._publicar_oci") as oci, patch(
        "httpx.post", side_effect=RuntimeError("caído")
    ):
        publicar("T", "C")
    oci.assert_called_once_with("ocid1.test", "T", "C")


def test_publicar_relanza_si_fallan_todos_los_canales(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", N8N)
    monkeypatch.setenv("ONS_TOPIC_OCID", "ocid1.test")
    with patch("agent.storage.notifications._publicar_oci", side_effect=RuntimeError("oci caído")), patch(
        "httpx.post", side_effect=RuntimeError("n8n caído")
    ):
        with pytest.raises(RuntimeError, match="oci caído"):
            publicar("T", "C")


def test_publicar_sin_canales_no_falla():
    publicar("T", "C")


def test_workflow_escapa_texto_especial_de_slack():
    ruta = Path(__file__).resolve().parents[2] / "infra" / "n8n" / "alerta-slack.json"
    nodos = json.loads(ruta.read_text())["nodes"]
    cuerpo = next(n for n in nodos if n["name"] == "Publicar en Slack")["parameters"]["jsonBody"]
    assert "&amp;" in cuerpo and "&lt;" in cuerpo and "&gt;" in cuerpo
