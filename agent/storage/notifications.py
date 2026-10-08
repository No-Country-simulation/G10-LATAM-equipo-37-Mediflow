"""Publicación de alertas: webhook directo (Discord/n8n) o OCI Notifications (topic).

Prioridad de publicación:
1. N8N_WEBHOOK_URL → publica en n8n (Nivel 3, N3-08).
2. DISCORD_WEBHOOK_URL → publica directo en Discord/Slack.
3. ONS_TOPIC_OCID → publica en OCI Notifications (correo).

Esta función es el único lugar que decide cómo publicar.
"""
import logging
import os

logger = logging.getLogger(__name__)


def publicar(titulo: str, cuerpo: str) -> None:
    """Publica una alerta usando el primer método configurado."""
    n8n = os.getenv("N8N_WEBHOOK_URL")
    if n8n:
        _publicar_webhook(n8n, titulo, cuerpo, formato="n8n")
        return

    discord = os.getenv("DISCORD_WEBHOOK_URL")
    if discord:
        _publicar_webhook(discord, titulo, cuerpo, formato="discord")
        return

    topic = os.getenv("ONS_TOPIC_OCID")
    if topic:
        _publicar_oci(topic, titulo, cuerpo)
        return

    logger.warning("No hay N8N_WEBHOOK_URL, DISCORD_WEBHOOK_URL ni ONS_TOPIC_OCID configurados.")


def _publicar_webhook(url: str, titulo: str, cuerpo: str, formato: str) -> None:
    """Publica en un webhook HTTP (Discord, Slack, n8n)."""
    import httpx

    if formato == "n8n":
        # n8n espera un JSON genérico con título y cuerpo
        payload = {"titulo": titulo, "cuerpo": cuerpo}
    else:
        # Discord/Slack esperan {content: ...}
        payload = {"content": f"**{titulo}**\n{cuerpo}"}

    respuesta = httpx.post(url, json=payload, timeout=10)
    respuesta.raise_for_status()


def _publicar_oci(topic: str, titulo: str, cuerpo: str) -> None:
    """Publica en OCI Notifications (topic)."""
    import oci

    if os.getenv("OCI_AUTH", "config") == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.ons.NotificationDataPlaneClient(config={}, signer=signer)
    else:
        client = oci.ons.NotificationDataPlaneClient(oci.config.from_file())
    client.publish_message(topic, oci.ons.models.MessageDetails(title=titulo, body=cuerpo))