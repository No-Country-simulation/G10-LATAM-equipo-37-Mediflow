"""Publicación de alertas por n8n o por OCI Notifications."""
import os


def publicar(titulo: str, cuerpo: str) -> None:
    webhook_n8n = os.getenv("N8N_WEBHOOK_URL")
    if webhook_n8n:
        import httpx

        respuesta = httpx.post(
            webhook_n8n,
            json={"titulo": titulo, "cuerpo": cuerpo},
            timeout=10,
        )
        respuesta.raise_for_status()
        return

    import oci

    topic = os.getenv("ONS_TOPIC_OCID")
    if not topic:
        return
    if os.getenv("OCI_AUTH", "config") == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.ons.NotificationDataPlaneClient(config={}, signer=signer)
    else:
        client = oci.ons.NotificationDataPlaneClient(oci.config.from_file())
    client.publish_message(topic, oci.ons.models.MessageDetails(title=titulo, body=cuerpo))
