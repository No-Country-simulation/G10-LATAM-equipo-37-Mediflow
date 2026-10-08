"""Publica la alerta en OCI Notifications cuando hay urgencia o alto riesgo."""
import logging

from agent.nodes.common import step
from agent.state import TriageState

logger = logging.getLogger(__name__)


def notificar(state: TriageState) -> dict:
    """
    Publica la alerta en OCI Notifications si hay urgencia.

    Si no hay notificación generada (no hay urgencia), no hace nada.
    Si falla la publicación, no rompe el flujo (solo loguea el error).
    """
    notificacion = state.get("decision", {}).get("notificacion_generada")

    if not notificacion:
        return {"trace": step(state, "notificar", {"enviada": False})}

    # Publicar en OCI Notifications (con manejo de errores)
    enviada = False
    try:
        from agent.storage.notifications import publicar

        publicar(
            titulo=notificacion.get("canal", "Alerta MediFlow"),
            cuerpo=notificacion.get("mensaje", ""),
        )
        enviada = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo publicar la alerta: %s", exc)

    return {"trace": step(state, "notificar", {"enviada": enviada})}