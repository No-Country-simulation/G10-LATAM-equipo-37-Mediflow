"""Publicación en OCI Notifications (alertas y reporte diario)."""
import os


def publicar(titulo: str, cuerpo: str) -> None:
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
