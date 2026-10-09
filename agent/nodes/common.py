"""Utilidades compartidas por los nodos."""
import os
import time
from typing import Any

from agent.privacidad import registro_seguro, seudonimizar
from agent.state import TriageState


def step(state: TriageState, nodo: str, detalle: dict[str, Any] | None = None, modelo: str | None = None) -> list:
    """Devuelve la traza con un registro nuevo agregado. Cada nodo la retorna en su dict de salida."""
    registro = {"nodo": nodo, "ts": time.time(), "detalle": detalle or {}}
    if modelo:
        registro["modelo"] = modelo
    paciente = (state.get("datos_extraidos") or {}).get("paciente") or {}
    nombre = paciente.get("nombre")
    if isinstance(nombre, str) and nombre and os.getenv("MEDIFLOW_CLAVE_SEUDONIMO"):
        registro["paciente_ref"] = seudonimizar(nombre)
    # También limpiar detalles históricos al retomar un checkpoint anterior.
    anteriores = [registro_seguro(r)
                  for r in state.get("trace", []) if isinstance(r, dict)]
    return [*anteriores, registro_seguro(registro)]
