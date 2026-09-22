"""Extrae los datos estructurados según el esquema del tipo de documento."""
import re

from agent.nodes.common import step
from agent.state import TriageState


def _buscar(patron: str, texto: str) -> str | None:
    m = re.search(patron, texto, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None


def extraer(state: TriageState) -> dict:
    texto = state.get("texto", "")
    # Stub con expresiones regulares para el ejemplo del brief.
    # TODO sprint 2: agent.llm.adapter.complete con agent/prompts/extraer.md y validar con ESQUEMAS_POR_TIPO.
    paciente = _buscar(r"Paciente:\s*([^,\.\n]+)", texto)
    edad = _buscar(r"(\d{1,3})\s*a[nñ]os", texto)
    medico = _buscar(r"M[eé]dic[oa] Solicitante:\s*([^\.\n]+?)(?:\s+MP|\s+Matr|\.|\n)", texto)
    matricula = _buscar(r"(?:MP|Matr[ií]cula)\s*:?\s*(\d+)", texto)
    estudio = _buscar(r"Estudio:\s*([^\.\n]+)", texto)
    conclusion = _buscar(r"CONCLUSION:\s*([^\.\n]+)", texto)

    datos = {
        "paciente": {"nome": paciente, "edad": int(edad) if edad else None},
        "medico_solicitante": {"nombre": medico, "matricula": matricula},
        "estudio_realizado": estudio,
        "diagnostico_principal": conclusion,
        "cie10_sugerido": None,
        "medicamentos": [],
        "estudios_solicitados": [],
    }
    return {"datos_extraidos": datos, "trace": step(state, "extraer", {"campos": list(datos)}, modelo="stub")}
