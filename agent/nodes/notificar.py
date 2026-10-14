"""Publica la alerta generada cuando hay urgencia o alto riesgo."""
import logging

from agent.nodes.common import step
from agent.state import TriageState

logger = logging.getLogger(__name__)


def notificar(state: TriageState) -> dict:
    notificacion = state.get("decision", {}).get("notificacion_generada")
    enviada = False
    if notificacion:
        try:
            from agent.storage.notifications import publicar

            publicar(
                titulo=notificacion.get("canal", "Alerta MediFlow"),
                cuerpo=notificacion.get("mensaje", ""),
            )
            enviada = True
        except Exception as exc:
            logger.warning("No se pudo publicar la alerta: %s", exc)
    return {"trace": step(state, "notificar", {"enviada": enviada})}
