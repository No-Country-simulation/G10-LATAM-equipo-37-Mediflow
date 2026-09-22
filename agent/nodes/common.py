"""Utilidades compartidas por los nodos."""
import time
from typing import Any

from agent.state import TriageState


def step(state: TriageState, nodo: str, detalle: dict[str, Any] | None = None, modelo: str | None = None) -> list:
    """Devuelve la traza con un registro nuevo agregado. Cada nodo la retorna en su dict de salida."""
    registro = {"nodo": nodo, "ts": time.time(), "detalle": detalle or {}}
    if modelo:
        registro["modelo"] = modelo
    return [*state.get("trace", []), registro]
