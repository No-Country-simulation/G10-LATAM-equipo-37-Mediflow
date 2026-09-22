"""Extrae los datos estructurados según el esquema del tipo de documento.

Nodo AI-02 (Carlos Zunino). Reemplaza el stub de regex por una llamada al
LLM con el prompt de `agent/prompts/extraer.md`. Si el LLM falla, cae al
fallback de regex para el ejemplo del brief.

Para activar el LLM en tu entorno local:
    $env:USE_LLM = "true"   # PowerShell
    export USE_LLM=true      # Bash
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from agent.llm import adapter
from agent.nodes.common import step
from agent.state import TriageState

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extraer.md"


# --- Fallback por regex ---

def _buscar(patron: str, texto: str) -> str | None:
    m = re.search(patron, texto, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extraer_por_regex(texto: str) -> dict:
    """Fallback: extracción con expresiones regulares."""
    paciente = _buscar(r"Paciente:\s*([^,\.\n]+)", texto)
    edad = _buscar(r"(\d{1,3})\s*a[nñ]os", texto)
    medico = _buscar(
        r"M[eé]dic[oa] Solicitante:\s*(.+?)(?:\s+MP|\s+Matr|\n|$)", texto
    )
    matricula = _buscar(r"(?:MP|Matr[ií]cula)\s*:?\s*(\d+)", texto)
    estudio = _buscar(r"Estudio:\s*([^\.\n]+)", texto)
    conclusion = _buscar(r"CONCLUSION:\s*([^\.\n]+)", texto)

    return {
        "paciente": {"nome": paciente, "edad": int(edad) if edad else None},
        "medico_solicitante": {"nombre": medico, "matricula": matricula},
        "estudio_realizado": estudio,
        "diagnostico_principal": conclusion,
        "cie10_sugerido": None,
        "medicamentos": [],
        "estudios_solicitados": [],
    }


# --- LLM ---

def _parsear_json(texto: str) -> dict:
    """Parsea JSON tolerando bloques markdown ```json ... ```."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[1] if "\n" in limpio else limpio
        if limpio.endswith("```"):
            limpio = limpio[:-3]
        limpio = limpio.strip()
    return json.loads(limpio)

def _limpiar_evidencias(obj):
    """Remueve recursivamente las claves que empiezan con 'evidencia_'."""
    if isinstance(obj, dict):
        return {
            k: _limpiar_evidencias(v)
            for k, v in obj.items()
            if not k.startswith("evidencia_")
        }
    if isinstance(obj, list):
        return [_limpiar_evidencias(item) for item in obj]
    return obj

def _normalizar_medicamento(med, medicamentos_alto_riesgo: set[str]) -> dict:
    """
    Normaliza un medicamento al formato del contrato:
    nombre, dosis, frecuencia, duracion, alto_riesgo.

    Acepta:
    - dict con campo 'nombre'
    - string (nombre suelto)
    """
    # Si viene como string, convertir a dict.
    if isinstance(med, str):
        med = {"nombre": med}
    if not isinstance(med, dict):
        return {
            "nombre": None,
            "dosis": None,
            "frecuencia": None,
            "duracion": None,
            "alto_riesgo": False,
        }

    nombre = (med.get("nombre") or "").strip() or None
    alto_riesgo = False
    if nombre:
        nombre_lower = nombre.lower()
        alto_riesgo = any(
            termino.lower() in nombre_lower
            for termino in medicamentos_alto_riesgo
        )
    return {
        "nombre": nombre,
        "dosis": med.get("dosis"),
        "frecuencia": med.get("frecuencia"),
        "duracion": med.get("duracion"),
        "alto_riesgo": alto_riesgo,
    }


def _normalizar_datos(datos: dict) -> dict:
    """
    Asegura que el dict tenga todas las claves del contrato, limpia las
    evidencias anidadas y normaliza los medicamentos (calcula alto_riesgo).
    """
    from agent.rules.loader import load_rules

    datos = _limpiar_evidencias(datos)
    reglas = load_rules()
    terminos_alto_riesgo = set(reglas.get("medicamentos_alto_riesgo", []))

    medicamentos_raw = datos.get("medicamentos") or []
    medicamentos = [
        _normalizar_medicamento(m, terminos_alto_riesgo) for m in medicamentos_raw
    ]

    return {
        "paciente": datos.get("paciente") or {"nome": None, "edad": None},
        "medico_solicitante": datos.get("medico_solicitante")
        or {"nombre": None, "matricula": None},
        "estudio_realizado": datos.get("estudio_realizado"),
        "procedimiento_solicitado": datos.get("procedimiento_solicitado"),
        "diagnostico_principal": datos.get("diagnostico_principal"),
        "diagnostico_egreso": datos.get("diagnostico_egreso"),
        "cie10_sugerido": datos.get("cie10_sugerido"),
        "hallazgos": datos.get("hallazgos"),
        "conclusion": datos.get("conclusion"),
        "medicamentos": medicamentos,
        "estudios_solicitados": datos.get("estudios_solicitados") or [],
    }


def _extraer_evidencias(payload: dict) -> list[dict]:
    """
    Extrae los campos evidencia_* del payload del LLM y los convierte
    al formato del contrato: {campo, fragmento, valor_extraido}.

    El LLM devuelve los datos con un campo adicional por cada campo extraído:
        "paciente": {
            "nome": "Carlos Eduardo Mendes",
            "evidencia_nome": "Paciente: Carlos Eduardo Mendes, 52 anos."
        }

    Esta función recorre el payload y arma la lista de evidencias.
    """
    evidencias = []
    datos = payload.get("datos_extraidos", payload)

    def _recorrer(prefijo: str, obj: dict) -> None:
        for clave, valor in obj.items():
            if clave.startswith("evidencia_"):
                continue  # las evidencias se procesan junto al campo que sustentan
            campo_completo = f"{prefijo}.{clave}" if prefijo else clave
            clave_evidencia = f"evidencia_{clave}"
            if isinstance(valor, dict):
                _recorrer(campo_completo, valor)
            else:
                fragmento = obj.get(clave_evidencia)
                if fragmento:
                    evidencias.append({
                        "campo": campo_completo,
                        "fragmento": fragmento,
                        "valor_extraido": valor,
                    })

    _recorrer("", datos)
    return evidencias


def _construir_prompt(texto: str, tipo_documento: str) -> str:
    """
    Carga el prompt y sustituye las variables {{tipo_documento}} y {{documento}}.
    """
    plantilla = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        plantilla.replace("{{tipo_documento}}", tipo_documento)
        .replace("{{documento}}", texto)
    )


def extraer(state: TriageState) -> dict:
    """Extrae datos del documento. Usa LLM si USE_LLM=true, sino regex."""
    texto = state.get("texto", "")
    tipo_documento = state.get("clasificacion", {}).get("tipo_documento", "Otro")

    # Inicializar variables antes de cualquier camino.
    evidencias: list[dict] = []    

    # Camino rápido: sin LLM.
    if not USE_LLM:
        datos = _extraer_por_regex(texto)
        return {
            "datos_extraidos": datos,
            "evidencias": [],
            "modelo_utilizado": "stub",
            "trace": step(state, "extraer", {"campos": list(datos)}, modelo="stub"),
        }

    # Camino con LLM.
    modelo = "stub"
    hallazgo_critico = None
    ambiguedad = None

    try:
        if not PROMPT_PATH.exists():
            logger.warning("No existe prompts/extraer.md, usando regex.")
            datos = _extraer_por_regex(texto)
            evidencias = []
        else:
            prompt = _construir_prompt(texto, tipo_documento)
            resultado_llm = adapter.complete(prompt, json_mode=False, timeout=30)
            payload = _parsear_json(resultado_llm.text)
            datos_raw = payload.get("datos_extraidos", payload)
            datos = _normalizar_datos(datos_raw)
            evidencias = _extraer_evidencias(payload)
            hallazgo_critico = payload.get("hallazgo_critico_detectado")
            ambiguedad = payload.get("ambiguedad_detectada")
            modelo = resultado_llm.model
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM falló en extraer (%s), usando regex.", e)
        datos = _extraer_por_regex(texto)
        evidencias = []

    salida: dict = {
        "datos_extraidos": datos,
        "evidencias": evidencias,
        "modelo_utilizado": modelo,
        "trace": step(state, "extraer", {"campos": list(datos)}, modelo=modelo),
    }

    if hallazgo_critico:
        salida["hallazgo_critico"] = hallazgo_critico
    if ambiguedad:
        salida["ambiguedad"] = ambiguedad

    return salida