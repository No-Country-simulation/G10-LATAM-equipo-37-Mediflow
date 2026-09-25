"""Clasifica el tipo de documento, la especialidad y la prioridad.

Nodo AI-02 (Carlos Zunino). Usa el prompt existente en
`agent/prompts/clasificar.md` que devuelve:

    {
      "tipo_documento": "...",
      "especialidad": "..." o null,
      "nivel_prioridad": "Rutina | Prioritario | Urgente",
      "idioma": "es | pt | en",
      "legible": true | false,
      "confianza": 0.0 a 1.0,
      "justificacion": "..."
    }

Si el LLM falla o USE_LLM=false, cae al fallback de reglas.

Para activar el LLM:
    $env:USE_LLM = "true"   # PowerShell
    export USE_LLM=true      # Bash
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from agent.llm import adapter
from agent.nodes.common import step
from agent.schemas.contrato import NivelPrioridad, TipoDocumento
from agent.state import TriageState

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "clasificar.md"


# --- Fallback por reglas ---

_PISTAS = [
    ("receta", "Receta Medica"),
    ("epicrisis", "Epicrisis"),
    ("informe de alta", "Epicrisis"),
    ("certificado", "Certificado Medico"),
    ("orden", "Orden de Solicitud de Procedimiento"),
    ("solicitud de procedimiento", "Orden de Solicitud de Procedimiento"),
    ("laboratorio", "Informe de Laboratorio"),
    ("informe", "Informe de Estudio por Imagenes"),
    ("tomografia", "Informe de Estudio por Imagenes"),
]


def _clasificar_por_reglas(texto: str) -> dict:
    """Fallback: clasificación por substring, sin LLM."""
    tipo = TipoDocumento.OTRO.value
    for pista, candidato in _PISTAS:
        if pista in texto.lower():
            tipo = candidato
            break
    confianza = 0.9 if tipo != TipoDocumento.OTRO.value else 0.3
    return {
        "tipo_documento": tipo,
        "especialidad": None,
        "nivel_prioridad": NivelPrioridad.RUTINA.value,
        "score_confianza_clasificacion": confianza,
        "idioma": "es",
        "legible": bool(texto.strip()),
        "justificacion": "Clasificación por reglas (fallback).",
    }


# --- Helpers de LLM ---

def _parsear_json(texto: str) -> dict:
    """Parsea JSON tolerando bloques markdown ```json ... ```."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[1] if "\n" in limpio else limpio
        if limpio.endswith("```"):
            limpio = limpio[:-3]
        limpio = limpio.strip()
    return json.loads(limpio)


def _lista_tipos_documento() -> str:
    """Devuelve la lista de tipos válidos, separada por comas, para el prompt."""
    return ", ".join(f'"{t.value}"' for t in TipoDocumento)


def _construir_prompt(texto: str) -> str:
    """Carga el prompt y sustituye las variables."""
    plantilla = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        plantilla.replace("{{tipos_documento}}", _lista_tipos_documento())
        .replace("{{documento}}", texto)
    )


def _normalizar_respuesta(datos: dict) -> dict:
    """
    Mapea la respuesta del LLM (con campos del prompt) al formato que espera
    el estado del grafo (con campos del contrato).
    """
    # tipo_documento: validar contra el enum.
    tipo_raw = datos.get("tipo_documento", "Otro")
    try:
        tipo = TipoDocumento(tipo_raw).value
    except ValueError:
        logger.warning("Tipo documental inválido '%s', usando Otro.", tipo_raw)
        tipo = TipoDocumento.OTRO.value

    # nivel_prioridad: validar contra el enum.
    prioridad_raw = datos.get("nivel_prioridad", "Rutina")
    try:
        prioridad = NivelPrioridad(prioridad_raw).value
    except ValueError:
        logger.warning("Prioridad inválida '%s', usando Rutina.", prioridad_raw)
        prioridad = NivelPrioridad.RUTINA.value

    # confianza → score_confianza_clasificacion.
    try:
        confianza = float(datos.get("confianza", 0.5))
    except (TypeError, ValueError):
        confianza = 0.5
    confianza = max(0.0, min(1.0, confianza))

    return {
        "tipo_documento": tipo,
        "especialidad": datos.get("especialidad"),
        "nivel_prioridad": prioridad,
        "score_confianza_clasificacion": confianza,
        # Campos extra que el prompt devuelve y son útiles para el resto del flujo.
        "idioma": datos.get("idioma", "es"),
        "legible": bool(datos.get("legible", True)),
        "justificacion": datos.get("justificacion"),
    }


# --- Nodo principal ---

def clasificar(state: TriageState) -> dict:
    """Clasifica el documento. Usa LLM si USE_LLM=true, sino reglas."""
    texto = state.get("texto", "")

    # Camino rápido: sin LLM.
    if not USE_LLM:
        clasificacion = _clasificar_por_reglas(texto)
        return {
            "clasificacion": clasificacion,
            "modelo_utilizado": "stub",
            "trace": step(state, "clasificar", clasificacion, modelo="stub"),
        }

    # Camino con LLM.
    modelo = "stub"
    try:
        if not PROMPT_PATH.exists():
            logger.warning("No existe prompts/clasificar.md, usando reglas.")
            clasificacion = _clasificar_por_reglas(texto)
        else:
            prompt = _construir_prompt(texto)
            resultado_llm = adapter.complete(prompt, json_mode=False, timeout=15)
            clasificacion = _normalizar_respuesta(_parsear_json(resultado_llm.text))
            modelo = resultado_llm.model
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM falló en clasificar (%s), usando reglas.", e)
        clasificacion = _clasificar_por_reglas(texto)

    return {
        "clasificacion": clasificacion,
        "modelo_utilizado": modelo,
        "trace": step(state, "clasificar", clasificacion, modelo=modelo),
    }