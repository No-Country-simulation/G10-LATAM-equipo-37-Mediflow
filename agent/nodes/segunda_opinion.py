"""Con score medio, un segundo modelo extrae y se compara con el primero. Una sola vez."""
from agent.nodes.common import step
from agent.state import TriageState


def segunda_opinion(state: TriageState) -> dict:
    # TODO sprint 3: llamar al respaldo 1 con el mismo prompt y comparar campo por campo.
    resultado = {"acuerdo": True, "campos_en_desacuerdo": [], "modelo": "stub"}
    return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", resultado, modelo="stub")}
