"""Valida campos obligatorios, consistencia y conflictos."""
from agent.nodes.common import step
from agent.state import TriageState


def validar(state: TriageState) -> dict:
    datos = state.get("datos_extraidos", {})
    faltantes, conflictos = [], []

    if not datos.get("paciente", {}).get("nome"):
        faltantes.append("paciente.nome")
    if not datos.get("medico_solicitante", {}).get("matricula"):
        faltantes.append("medico_solicitante.matricula")

    # TODO sprint 2: validar CIE-10 contra la tabla, dosis contra rangos, edad contra fecha de nacimiento,
    # diagnóstico contra estudio.

    validacion = {"campos_faltantes": faltantes, "conflictos": conflictos, "errores": []}
    return {"validacion": validacion, "trace": step(state, "validar", validacion)}
