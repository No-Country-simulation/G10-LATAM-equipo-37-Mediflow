"""Valida campos obligatorios, consistencia y conflictos (docs/api-contract.md, sección 6).

Cambios respecto a la versión anterior de este archivo en `develop`:

1. BUG corregido: se leía `paciente.nome` (portugués). ADR-003 (23/9) decidió que el campo
   es `paciente.nombre` en todo el proyecto. OJO: `agent/nodes/extraer.py` (dueño: Carlos)
   TODAVÍA escribe `nome` en su stub actual. Este archivo ya sigue la decisión (ADR-003),
   así que hasta que Carlos actualice `extraer.py`, la detección de "paciente sin nombre"
   (AMB-1) va a marcar falso positivo en documentos reales. Avisar y coordinar el mismo PR
   o el mismo día, tal como pide la consecuencia de ADR-003.
2. `campos_obligatorios` ya NO está hardcodeado acá: se lee de `agent/rules/rules.yaml`,
   que es la fuente de verdad (así lo dice el propio rules.yaml).
3. Catálogos: se usan `evals/generator/data/medicamentos.csv` y
   `evals/generator/data/cie10.csv` (las versiones con ATC/validar_dosis y con
   fuente OPS/OMS), NO `data/raw/*.csv`, que parece una copia desactualizada.
4. `categoria_amb` ahora sigue las 6 categorías reales del contrato (sección 6), no las
   5 genéricas que habíamos supuesto antes de leer el contrato real.

TODO / decisiones pendientes de coordinar con el equipo (no bloquean el esqueleto, pero
hay que resolverlas antes de que esto sea definitivo):
  - AMB-2 (contradicción interna): solo cubre edad fuera de rango plausible. Falta la regla
    de "diagnóstico no coincide con el tipo de estudio" que menciona el contrato.
  - AMB-5 (dos documentos en un archivo): este nodo asume que llega marcado en
    `datos_extraidos["_multiples_documentos"]`, pero no sé todavía qué nodo (¿normalizar?
    ¿clasificar?) es el que realmente detecta y escribe esa marca. Confirmar con Kevin/Carlos.
  - AMB-6 (fuera de alcance): el contrato dice que "validar.py lo escribe en el estado", pero
    el motivo (uno de los 5 de `fuera_de_alcance.motivos` en rules.yaml) parece un juicio que
    hace el modelo de clasificación, no una regla determinística de este nodo. Acá simplemente
    lo repito si `clasificacion` ya trae `tipo_documento == "Otro"` y un motivo; si no viene,
    lo dejo sin asignar y qué quede como pendiente de conversación con Carlos (clasificar.py).
  - AMB-4 (texto truncado/ilegible): lo deduzco de `state["legibilidad"]` contra el umbral
    "media" de rules.yaml, pero el contrato (sección 5, regla 1) hace sonar que el enrutador
    (Néstor) también mira legibilidad para el caso "< 0,40" (ilegible directo, sin llamar
    modelo). Confirmar con Néstor que no se pisen ambas lógicas.
"""

import csv
import re
from pathlib import Path
from typing import Any

import yaml

from agent.nodes.common import step
from agent.state import TriageState

RULES_PATH = Path("agent/rules/rules.yaml")
MEDICAMENTOS_PATH = Path("evals/generator/data/medicamentos.csv")
CIE10_PATH = Path("evals/generator/data/cie10.csv")

_rules_cache: dict | None = None
_medicamentos_cache: list[dict] | None = None
_cie10_cache: list[dict] | None = None


# ---------------------------------------------------------------------------
# Carga de rules.yaml y catálogos (con caché simple en memoria de proceso)
# ---------------------------------------------------------------------------

def _cargar_rules(path: Path = RULES_PATH) -> dict:
    global _rules_cache
    if _rules_cache is None:
        with open(path, encoding="utf-8") as f:
            _rules_cache = yaml.safe_load(f)
    return _rules_cache


def _cargar_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _cargar_medicamentos(path: Path = MEDICAMENTOS_PATH) -> list[dict]:
    global _medicamentos_cache
    if _medicamentos_cache is None:
        _medicamentos_cache = _cargar_csv(path)
    return _medicamentos_cache


def _cargar_cie10(path: Path = CIE10_PATH) -> list[dict]:
    global _cie10_cache
    if _cie10_cache is None:
        _cie10_cache = _cargar_csv(path)
    return _cie10_cache


# ---------------------------------------------------------------------------
# Helpers de acceso a datos anidados y parsing numérico (columnas con coma decimal)
# ---------------------------------------------------------------------------

def _get(datos: dict, ruta: str) -> Any:
    """Lee un campo posiblemente anidado con notación 'a.b' (ej. paciente.nombre)."""
    valor: Any = datos
    for parte in ruta.split("."):
        if not isinstance(valor, dict):
            return None
        valor = valor.get(parte)
    return valor


def _vacio(valor: Any) -> bool:
    return valor is None or valor == "" or valor == [] or valor == {}


def _a_numero(texto: Any) -> float | None:
    """Convierte '0,4' o '5' o '1000 mg' (extrae el primer número) a float."""
    if texto is None:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", str(texto))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _buscar_medicamento(nombre: str | None, catalogo: list[dict]) -> dict | None:
    """Busca el medicamento por nombre genérico o por sinónimo (ADR-006: en el documento
    clínico aparece el nombre/sinónimo, no el código ATC)."""
    if not nombre:
        return None
    objetivo = nombre.strip().lower()
    for fila in catalogo:
        candidatos = [fila.get("nombre", "")] + [
            s.strip() for s in fila.get("sinonimos", "").split(";") if s.strip()
        ]
        for candidato in candidatos:
            candidato_low = candidato.lower()
            if candidato_low and (candidato_low in objetivo or objetivo in candidato_low):
                return fila
    return None


# ---------------------------------------------------------------------------
# Validaciones individuales
# ---------------------------------------------------------------------------

def validar_campos_obligatorios(datos: dict, tipo_documento: str, rules: dict) -> list[str]:
    """AMB-1: campo obligatorio faltante, según agent/rules/rules.yaml -> campos_obligatorios."""
    obligatorios = rules.get("campos_obligatorios", {}).get(tipo_documento, [])
    faltantes = [campo for campo in obligatorios if _vacio(_get(datos, campo))]

    # Extensión sobre lo que dice rules.yaml: el contrato (sección 3) también obliga
    # nombre* y dosis* DENTRO de cada medicamento de una receta, no solo la lista en sí.
    if tipo_documento == "Receta Medica":
        for i, med in enumerate(datos.get("medicamentos") or []):
            if _vacio(med.get("nombre")):
                faltantes.append(f"medicamentos[{i}].nombre")
            if _vacio(med.get("dosis")):
                faltantes.append(f"medicamentos[{i}].dosis")

    return faltantes


def validar_dosis_medicamentos(datos: dict, medicamentos_catalogo: list[dict]) -> list[str]:
    """AMB-3: dosis fuera de rango o medicamento no identificable.
    ADR-007: solo se compara si el medicamento tiene validar_dosis == 'si'; los que van
    por peso/protocolo (enoxaparina, alteplasa, heparina, insulina, potasio IV, fentanilo,
    morfina) no generan AMB-3 aunque sean de alto riesgo.
    """
    conflictos: list[str] = []
    for med in datos.get("medicamentos") or []:
        nombre = med.get("nombre")
        if not nombre:
            continue  # ya se marcó como campo faltante arriba
        fila = _buscar_medicamento(nombre, medicamentos_catalogo)
        if fila is None:
            conflictos.append(f"Medicamento no identificable en el catálogo: {nombre!r}")
            continue
        if (fila.get("validar_dosis") or "no").strip().lower() != "si":
            continue  # se dosifica por protocolo/peso (ADR-007): no genera AMB-3

        dosis_valor = _a_numero(med.get("dosis"))
        dosis_min = _a_numero(fila.get("dosis_min_toma"))
        dosis_max = _a_numero(fila.get("dosis_max_toma"))

        if dosis_valor is None:
            conflictos.append(f"Dosis no interpretable para {nombre}: {med.get('dosis')!r}")
        elif dosis_min is not None and dosis_max is not None and not (dosis_min <= dosis_valor <= dosis_max):
            conflictos.append(
                f"Dosis fuera de rango para {nombre}: {dosis_valor} {fila.get('unidad', '')} "
                f"(rango válido {dosis_min}-{dosis_max})"
            )
    return conflictos


def validar_cie10(datos: dict, cie10_catalogo: list[dict]) -> list[str]:
    """Verifica que el código CIE-10 sugerido exista en la lista tabular OPS/OMS (ADR-008)."""
    codigo = datos.get("cie10_sugerido")
    if not codigo:
        return []
    for fila in cie10_catalogo:
        if fila.get("codigo") == codigo:
            return []
    return [f"Código CIE-10 no encontrado en la lista OPS/OMS: {codigo}"]


def validar_contradiccion_interna(datos: dict) -> list[str]:
    """AMB-2: contradicción interna. TODO: solo cubre edad implausible por ahora;
    falta la regla de diagnóstico vs. tipo de estudio (ej. fractura en una ecografía
    abdominal) que menciona el contrato como ejemplo.
    """
    conflictos: list[str] = []
    edad = _get(datos, "paciente.edad")
    if edad is not None:
        try:
            if not (0 <= int(edad) <= 120):
                conflictos.append(f"Edad fuera de rango plausible: {edad}")
        except (TypeError, ValueError):
            conflictos.append(f"Edad no numérica: {edad!r}")
    return conflictos


def evaluar_legibilidad(legibilidad: float | None, rules: dict) -> bool:
    """AMB-4: True si la legibilidad cae en la banda 'media' (revisión con AMB-4,
    según rules.yaml). Por debajo de legibilidad_minima el contrato dice que el
    enrutador decide directo sin llamar al modelo -> ese caso no es responsabilidad
    de este nodo, se deja pasar.
    """
    if legibilidad is None:
        return False
    umbral_media = rules.get("legibilidad", {}).get("media", 0.40)
    umbral_leve = rules.get("legibilidad", {}).get("leve", 0.70)
    return umbral_media <= legibilidad < umbral_leve


# ---------------------------------------------------------------------------
# Categorización AMB — una sola categoría principal por caso (contrato, sección 6)
# ---------------------------------------------------------------------------

def asignar_categoria_amb(
    campos_faltantes: list[str],
    conflictos_dosis: list[str],
    conflictos_contradiccion: list[str],
    es_ilegible_medio: bool,
    es_multiples_documentos: bool,
    clasificacion: dict,
) -> str | None:
    """Devuelve la categoría principal, o None si el documento no es ambiguo.
    Orden: se elige la más específica que aplique; el contrato exige UNA sola categoría
    principal por caso.
    """
    if es_multiples_documentos:
        return "AMB-5"
    if clasificacion.get("tipo_documento") == "Otro":
        return "AMB-6"  # el motivo se copia aparte, ver TODO en el docstring del módulo
    if campos_faltantes:
        return "AMB-1"
    if conflictos_contradiccion:
        return "AMB-2"
    if conflictos_dosis:
        return "AMB-3"
    if es_ilegible_medio:
        return "AMB-4"
    return None


# ---------------------------------------------------------------------------
# Entrada del nodo
# ---------------------------------------------------------------------------

def validar(state: TriageState) -> dict:
    datos = state.get("datos_extraidos", {}) or {}
    clasificacion = state.get("clasificacion", {}) or {}
    tipo_documento = clasificacion.get("tipo_documento", "")
    legibilidad = state.get("legibilidad")

    rules = _cargar_rules()
    medicamentos_catalogo = _cargar_medicamentos()
    cie10_catalogo = _cargar_cie10()

    campos_faltantes = validar_campos_obligatorios(datos, tipo_documento, rules)
    conflictos_dosis = validar_dosis_medicamentos(datos, medicamentos_catalogo)
    conflictos_cie10 = validar_cie10(datos, cie10_catalogo)
    conflictos_contradiccion = validar_contradiccion_interna(datos)
    es_ilegible_medio = evaluar_legibilidad(legibilidad, rules)
    es_multiples_documentos = bool(datos.get("_multiples_documentos"))  # TODO: confirmar origen real de esta marca

    categoria = asignar_categoria_amb(
        campos_faltantes,
        conflictos_dosis,
        conflictos_contradiccion,
        es_ilegible_medio,
        es_multiples_documentos,
        clasificacion,
    )

    validacion: dict[str, Any] = {
        "campos_faltantes": campos_faltantes,
        "conflictos": [*conflictos_dosis, *conflictos_contradiccion, *conflictos_cie10],
        "errores": [],
    }
    if categoria:
        validacion["categoria_amb"] = categoria
    if categoria == "AMB-6":
        # Ver TODO: de dónde sale este motivo. Por ahora lo repetimos si clasificar.py
        # ya lo dejó en el estado; si no está, queda sin motivo (pendiente).
        motivo = clasificacion.get("motivo_fuera_de_alcance")
        if motivo:
            validacion["motivo_fuera_de_alcance"] = motivo

    return {"validacion": validacion, "trace": step(state, "validar", validacion)}
