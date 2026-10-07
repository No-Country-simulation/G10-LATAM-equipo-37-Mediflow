"""Grafo de decisión de MediFlow.

normalizar → (legible?) → clasificar → extraer → validar → puntuar → detectar_urgencia
  → urgencia: enrutar (+ notificar)
  → score alto y sin conflictos: enrutar
  → score medio: segunda_opinion → puntuar de nuevo → enrutar
  → score bajo: enrutar (revisión humana)
enrutar → persistir → notificar → FIN

El auditor tiene tres salidas y no son equivalentes: aprobar o corregir devuelve el documento al
enrutamiento por tipo; rechazar termina en rechazados/ y nunca continúa hacia un destino operativo.

**Trazas.** Cada nodo se registra envuelto en `_con_tiempo`, así que su registro de traza lleva la
duración real medida con `perf_counter` además del detalle y el modelo. `run_triage` agrega el
resumen ya calculado (`traza_resumen`) para que la API y la UI lo muestren sin recalcular nada.
"""
import logging
import time
from collections.abc import Callable

from langgraph.graph import END, StateGraph

from agent.nodes.clasificar import clasificar
from agent.nodes.enrutar import enrutar
from agent.nodes.extraer import extraer
from agent.nodes.normalizar import normalizar
from agent.nodes.notificar import notificar
from agent.nodes.persistir import persistir
from agent.nodes.puntuar import puntuar
from agent.nodes.segunda_opinion import segunda_opinion
from agent.nodes.urgencia import detectar_urgencia
from agent.nodes.validar import validar
from agent.rules.loader import load_rules
from agent.state import TriageState
from agent.traza import resumen_traza

logger = logging.getLogger(__name__)

# Los nodos del grafo, en el orden en que se construyen. Se expone para que los tests verifiquen que
# el grafo sigue teniendo los diez nodos que documenta docs/architecture.md.
NODOS: tuple[tuple[str, Callable], ...] = (
    ("normalizar", normalizar),
    ("clasificar", clasificar),
    ("extraer", extraer),
    ("validar", validar),
    ("puntuar", puntuar),
    ("detectar_urgencia", detectar_urgencia),
    ("segunda_opinion", segunda_opinion),
    ("enrutar", enrutar),
    ("persistir", persistir),
    ("notificar", notificar),
)


def _con_tiempo(nombre: str, nodo: Callable) -> Callable:
    """Envuelve un nodo para medir cuánto tarda y dejarlo en su registro de traza.

    Se mide acá y no dentro de cada nodo por dos razones: hay un solo lugar que mantener y el nodo no
    necesita saber que lo están cronometrando. El registro que completa es el último que el nodo
    agregó, que es el que deja `common.step` al final de la lista.
    """

    def _envuelto(state: TriageState) -> dict:
        inicio = time.perf_counter()
        salida = nodo(state)
        ms = round((time.perf_counter() - inicio) * 1000, 1)
        traza = salida.get("trace") if isinstance(salida, dict) else None
        if isinstance(traza, list) and traza:
            traza[-1]["ms"] = ms
        else:
            logger.debug("El nodo %s no devolvió traza: no se pudo registrar su duración.", nombre)
        return salida

    _envuelto.__name__ = f"{nombre}_cronometrado"
    return _envuelto



def _tras_normalizar(state: TriageState) -> str:
    minimo = load_rules()["umbrales"]["legibilidad_minima"]
    return "clasificar" if state.get("legibilidad", 0.0) >= minimo else "enrutar"


def _tras_urgencia(state: TriageState) -> str:
    umbrales = load_rules()["umbrales"]
    if state.get("urgencia", {}).get("detectada"):
        return "enrutar"
    if state.get("segunda_opinion"):          # ya se pidió una vez, no se repite
        return "enrutar"
    score = state.get("score", 0.0)
    conflictos = state.get("validacion", {}).get("conflictos")
    if score >= umbrales["automatico"] and not conflictos:
        return "enrutar"
    if score >= umbrales["segunda_opinion"]:
        return "segunda_opinion"
    return "enrutar"


def build_graph():
    g = StateGraph(TriageState)
    for nombre, nodo in NODOS:
        g.add_node(nombre, _con_tiempo(nombre, nodo))

    g.set_entry_point("normalizar")
    g.add_conditional_edges("normalizar", _tras_normalizar, {"clasificar": "clasificar", "enrutar": "enrutar"})
    g.add_edge("clasificar", "extraer")
    g.add_edge("extraer", "validar")
    g.add_edge("validar", "puntuar")
    g.add_edge("puntuar", "detectar_urgencia")
    g.add_conditional_edges(
        "detectar_urgencia", _tras_urgencia, {"enrutar": "enrutar", "segunda_opinion": "segunda_opinion"}
    )
    g.add_edge("segunda_opinion", "puntuar")
    g.add_edge("enrutar", "persistir")
    g.add_edge("persistir", "notificar")
    g.add_edge("notificar", END)
    return g.compile()


def run_triage(
    documento_id: str,
    tipo_archivo: str,
    texto: str | None,
    canal_origen: str | None,
    *,
    imagenes: list[str] | None = None,
    legibilidad: float | None = None,
    ruta_original: str | None = None,
) -> dict:
    """Corre el grafo. `imagenes` y `legibilidad` los llena la ingesta cuando el documento entra
    por archivo; si no vienen, los resuelve `normalizar`."""
    grafo = build_graph()
    estado_inicial: TriageState = {
        "documento_id": documento_id,
        "tipo_archivo": tipo_archivo,
        "texto": texto or "",
        "canal_origen": canal_origen or "",
        "trace": [],
    }
    if imagenes:
        estado_inicial["imagenes"] = imagenes
    if legibilidad is not None:
        estado_inicial["legibilidad"] = legibilidad
    if ruta_original:
        estado_inicial["ruta_original"] = ruta_original

    resultado = grafo.invoke(estado_inicial)
    # Cada nodo ya dejó su duración medida: acá se resume una sola vez para que la API y la UI no
    # tengan que recorrer la traza ni recalcular nada.
    resultado["traza_resumen"] = resumen_traza(resultado.get("trace"))
    return resultado
