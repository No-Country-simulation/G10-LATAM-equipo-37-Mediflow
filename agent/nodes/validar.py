"""Valida campos obligatorios, consistencia y conflictos (docs/api-contract.md, sección 6).

Cambios respecto a la versión anterior de este archivo en `develop`:

1. BUG corregido: se leía `paciente.nome` (portugués). ADR-003 (23/9) decidió que el campo
   es `paciente.nombre` en todo el proyecto. `extraer.py` y `contrato.py` (PR #1) y
   `enrutar.py` (PR #3) adoptan `nombre` en sus propios PR. Los tres PR (#1, #3 y este)
   deben fusionarse el mismo día: si este entrara antes, todo documento real saldría
   con AMB-1 falso.
2. `campos_obligatorios` ya NO está hardcodeado acá: se lee de `agent/rules/rules.yaml`,
   que es la fuente de verdad (así lo dice el propio rules.yaml).
3. Catálogos: se usan `evals/generator/data/medicamentos.csv` y
   `evals/generator/data/cie10.csv`, verificados contra ANMAT y OPS/OMS (con ATC y
   validar_dosis). `data/raw/*.csv` es una versión anterior, con estado_verificacion
   "pendiente", y este módulo no la usa.
4. `categoria_amb` ahora sigue las 6 categorías reales del contrato (sección 6), no las
   5 genéricas que habíamos supuesto antes de leer el contrato real.

TODO / decisiones pendientes de coordinar con el equipo (no bloquean el esqueleto, pero
hay que resolverlas antes de que esto sea definitivo):
- AMB-2 (contradicción interna): cubre edad fuera de rango plausible, edad contra
    `paciente.fecha_nacimiento` (ADR-009, tolerancia de 1 año; la regla se omite si falta
    la fecha del documento o es ilegible) y un CIE-10 que no existe en el catálogo
    (AMB-2 tiene prioridad sobre AMB-3). Falta la regla de "diagnóstico no coincide con
    el tipo de estudio" que menciona el contrato.
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
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from agent.nodes.common import step
from agent.rules.loader import RULES_PATH, load_rules
from agent.state import TriageState

MEDICAMENTOS_PATH = Path("evals/generator/data/medicamentos.csv")
CIE10_PATH = Path("evals/generator/data/cie10.csv")


_medicamentos_cache: list[dict] | None = None
_cie10_cache: list[dict] | None = None


# ---------------------------------------------------------------------------
# Carga de rules.yaml y catálogos (con caché simple en memoria de proceso)
# ---------------------------------------------------------------------------

def _cargar_rules(path: Path = RULES_PATH) -> dict:
    """Con la ruta por defecto usa load_rules(), que se recarga sola cuando cambian las reglas."""
    if path == RULES_PATH:
        return load_rules()
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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

_FACTOR_MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001, "µg": 0.001, "ug": 0.001}


def _a_numero(texto: Any) -> float | None:
    """Extrae el primer número. '1.000' se lee como miles; '0,4' y '0.25' como decimales."""
    if texto is None:
        return None
    m = re.search(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+(?:[.,]\d+)?", str(texto))
    if not m:
        return None
    s = m.group(0)
    if re.fullmatch(r"[1-9]\d{0,2}(?:\.\d{3})+", s):
        s = s.replace(".", "")
    else:
        s = s.replace(",", ".")
    return float(s)


def _dosis_en_unidad_catalogo(texto: Any, unidad_catalogo: str) -> float | None:
    """Convierte la dosis del documento a la unidad del catálogo. None si no se puede."""
    valor = _a_numero(texto)
    if valor is None:
        return None
    m = re.search(r"\d\s*(mg|g|mcg|µg|ug)\b", str(texto).lower())
    if not m:
        return valor  # sin unidad: se asume la del catálogo
    if unidad_catalogo.lower() == "mg":
        return valor * _FACTOR_MG[m.group(1)]
    return valor if m.group(1) == unidad_catalogo.lower() else None

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _buscar_medicamento(nombre: str | None, catalogo: list[dict]) -> dict | None:
    """Busca por nombre genérico o sinónimo (ADR-006), sin tildes y por palabra completa.
    Ante varias coincidencias gana la más larga (p. ej. 'amoxicilina-clavulánico' sobre 'amoxicilina')."""
    if not nombre:
        return None
    objetivo = _norm(str(nombre))
    mejor, mejor_len = None, 0
    for fila in catalogo:
        candidatos = [fila.get("nombre", "")] + (fila.get("sinonimos") or "").split(";")
        for c in candidatos:
            c = _norm(c)
            if c and len(c) > mejor_len and re.search(rf"\b{re.escape(c)}\b", objetivo):
                mejor, mejor_len = fila, len(c)
    return mejor


# ---------------------------------------------------------------------------
# Validaciones individuales
# ---------------------------------------------------------------------------

def validar_campos_obligatorios(datos: dict, tipo_documento: str, rules: dict) -> list[str]:
    """AMB-1: campo obligatorio faltante, según agent/rules/rules.yaml -> campos_obligatorios."""
    obligatorios = rules.get("campos_obligatorios", {}).get(tipo_documento, [])
    faltantes = [campo for campo in obligatorios if _vacio(_get(datos, campo))]

    # El contrato (sección 3) también obliga nombre y dosis dentro de cada medicamento.
    if tipo_documento == "Receta Medica":
        for i, med in enumerate(datos.get("medicamentos") or []):
            if not isinstance(med, dict):
                continue  # el formato inválido lo reporta validar_dosis_medicamentos
            if _vacio(med.get("nombre")):
                faltantes.append(f"medicamentos[{i}].nombre")
            if _vacio(med.get("dosis")):
                faltantes.append(f"medicamentos[{i}].dosis")

    return faltantes


def _frecuencia_diaria_o_mayor(frecuencia: Any) -> bool:
    """True si el texto indica una toma diaria o más frecuente (diario, cada 24 h, c/12 h, QD...).
    Mejor esfuerzo sobre texto libre: lo semanal ('semanal', 'cada 7 días') nunca cuenta."""
    f = _norm(str(frecuencia or ""))
    if not f or re.search(r"semana|\bsem\b|7 dias", f):
        return False
    return bool(re.search(
        r"diari|\bdia\b|cada\s*\d{1,2}\s*(?:h|hs|horas)\b|c/\s*\d{1,2}\s*(?:h|hs)\b|\bqd\b|\bbid\b|\btid\b",
        f,
    ))

# Tipos de documento que pueden llevar tratamiento (receta; epicrisis con tratamiento al alta).
# En los demás, un fármaco mencionado en la conclusión no es una prescripción.
_TIPOS_CON_TRATAMIENTO = {"receta medica", "epicrisis"}


def validar_dosis_medicamentos(datos: dict, medicamentos_catalogo: list[dict], tipo_documento: str = "") -> list[str]:
    """AMB-3: dosis fuera de rango o medicamento no identificable.
    ADR-007: solo se compara si validar_dosis == 'si'; los que van por peso/protocolo
    (enoxaparina, alteplasa, heparina, insulina, potasio IV, fentanilo, morfina)
    no generan AMB-3 aunque sean de alto riesgo.
    """
    conflictos: list[str] = []
    if tipo_documento and _norm(tipo_documento) not in _TIPOS_CON_TRATAMIENTO:
        return conflictos
    for med in datos.get("medicamentos") or []:
        if not isinstance(med, dict):
            conflictos.append(f"Medicamento con formato inválido: {med!r}")
            continue
        nombre = med.get("nombre")
        if not nombre:
            continue  # ya se marcó como campo faltante
        fila = _buscar_medicamento(nombre, medicamentos_catalogo)
        if fila is None:
            conflictos.append(f"Medicamento no identificable en el catálogo: {nombre!r}")
            continue
        if (fila.get("validar_dosis") or "no").strip().lower() != "si":
            continue  # ADR-007

        unidad = fila.get("unidad") or "mg"
        dosis_valor = _dosis_en_unidad_catalogo(med.get("dosis"), unidad)
        dosis_min = _a_numero(fila.get("dosis_min_toma"))
        dosis_max = _a_numero(fila.get("dosis_max_toma"))

        # Periodicidad especial del catálogo (p. ej. metotrexato semanal). Solo se compara
        # cuando el catálogo la declara; no se generaliza a otros protocolos.
        periodicidad = _norm(str(fila.get("periodicidad_especial") or ""))
        if periodicidad == "semanal" and _frecuencia_diaria_o_mayor(med.get("frecuencia")):
            conflictos.append(
                f"Frecuencia incompatible para {nombre}: el catálogo indica toma semanal y el "
                f"documento indica {med.get('frecuencia')!r}"
            )

        if dosis_valor is None:
            conflictos.append(f"Dosis no interpretable para {nombre}: {med.get('dosis')!r}")
        elif dosis_min is not None and dosis_max is not None and not (dosis_min <= dosis_valor <= dosis_max):
            conflictos.append(
                f"Dosis fuera de rango para {nombre}: {dosis_valor} {unidad} "
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


RUTAS_FECHA_DOCUMENTO = ("fecha", "fecha_egreso", "fecha_ingreso")  # docs/api-contract.md


def _a_fecha(valor: Any) -> date | None:
    """Lee AAAA-MM-DD. None si falta o no se puede interpretar."""
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def validar_contradiccion_interna(datos: dict) -> list[str]:
    """AMB-2: contradicción interna. TODO: falta diagnóstico vs. tipo de estudio
    (ej. fractura en una ecografía abdominal).
    """
    conflictos: list[str] = []
    edad = _get(datos, "paciente.edad")
    n = None
    if edad is not None:
        n = _a_numero(edad)
        if n is None:
            conflictos.append(f"Edad no numérica: {edad!r}")
        elif not (0 <= n <= 120):
            conflictos.append(f"Edad fuera de rango plausible: {edad}")

    # Edad vs. fecha de nacimiento (GS-17): solo se compara si el contrato trae ambas fechas.
    nacimiento = _a_fecha(_get(datos, "paciente.fecha_nacimiento"))
    referencia = next(
        (f for f in (_a_fecha(_get(datos, ruta)) for ruta in RUTAS_FECHA_DOCUMENTO) if f),
        None,  # sin fecha documental válida no se compara: evita falsas contradicciones
    )
    if n is not None and nacimiento and referencia:
        calculada = referencia.year - nacimiento.year - (
            (referencia.month, referencia.day) < (nacimiento.month, nacimiento.day)
        )
        if abs(calculada - n) > 1:
            conflictos.append(
                f"Edad {edad} no coincide con fecha de nacimiento {nacimiento} "
                f"(corresponde a {calculada} años al {referencia})"
            )
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
    conflictos_cie10: list[str] | None = None,
) -> str | None:
    """Devuelve la categoría principal, o None si el documento no es ambiguo.
    Orden: se elige la más específica que aplique; el contrato exige UNA sola categoría
    principal por caso. Un CIE-10 inexistente se trata como contradicción interna (AMB-2).
    Fuera de alcance (AMB-6) va antes que múltiples documentos (AMB-5): un documento no
    clínico debe ir a revisión humana con su motivo aunque venga con varios archivos.
    """
    if clasificacion.get("tipo_documento") == "Otro":
        return "AMB-6"  # el motivo se copia aparte
    if es_multiples_documentos:
        return "AMB-5"
    if campos_faltantes:
        return "AMB-1"
    if conflictos_contradiccion or conflictos_cie10:
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
    conflictos_dosis = validar_dosis_medicamentos(datos, medicamentos_catalogo, tipo_documento)
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
        conflictos_cie10,
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
