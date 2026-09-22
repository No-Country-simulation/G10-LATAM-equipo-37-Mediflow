"""Publica la alerta en OCI Notifications cuando hay urgencia o alto riesgo."""
from agent.nodes.common import step
from agent.state import TriageState


def notificar(state: TriageState) -> dict:
    notificacion = state.get("decision", {}).get("notificacion_generada")
    # TODO sprint 3: agent.storage.notifications.publicar(topic_ocid, titulo, cuerpo)
    return {"trace": step(state, "notificar", {"enviada": bool(notificacion)})}
