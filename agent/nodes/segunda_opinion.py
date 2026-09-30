"""Segunda opinión: cuando el score cae en la franja media, otro modelo repite la extracción.

**Cuándo corre.** `graph._tras_urgencia` deriva acá solo si no hay urgencia, el score no llegó al
umbral automático y todavía no se pidió una segunda opinión. El nodo lo verifica por su cuenta: una
sola vez, siempre.

**Cómo se compara, y por qué así.**

1. Mismo prompt y mismo esquema, **otro modelo**. Preguntarle dos veces al mismo modelo no agrega
   información, agrega confianza falsa. El modelo se elige de la cadena configurada salteando el que
   ya respondió (`state["modelo_utilizado"]`) y se puede fijar con `LLM_SEGUNDA_OPINION`.
2. La comparación es simétrica: los dos resultados se aplanan con la misma función, campo por campo.
   El nodo no depende de cómo normalice cada versión de `extraer`, así que funciona igual con el
   extractor por regex y con el extractor por LLM.
3. `acuerdo` es False solo cuando los dos modelos dan un valor **presente y distinto** para el mismo
   campo. Esa contradicción es la que manda el caso a revisión humana.
4. Que un modelo complete un campo y el otro lo deje nulo **no** es desacuerdo: es diferencia de
   cobertura, y se informa aparte en `campos_solo_en_un_modelo`. Contarlo como desacuerdo subiría la
   tasa de revisión humana por campos opcionales, sin ninguna contradicción real que resolver.
5. El nodo nunca deja el grafo sin respuesta y nunca lo rompe: si el modelo de respaldo falla, la
   segunda opinión queda como no disponible, el score se recalcula igual (el componente de acuerdo
   queda neutro) y el documento sigue su camino con marca de auditoría. Un modelo caído no puede
   perder un documento clínico.

La decisión de qué hacer con el desacuerdo no vive acá: el nodo informa y `puntuar` + `enrutar`
deciden, que es donde están las reglas.

**Limitación conocida y registrada.** `state["imagenes"]` trae páginas renderizadas en base64, y el
adaptador espera rutas de archivo, así que hoy la segunda opinión trabaja sobre el texto (en un
documento escaneado, sobre el OCR). Queda anotado en la traza como `con_imagenes: false`.
"""
from __future__ import annotations

import json
import logging
import os
import unicodedata
from pathlib import Path
from typing import Any

from agent.llm import adapter
from agent.nodes.common import step
from agent.schemas.documentos import ESQUEMAS_POR_TIPO
from agent.state import TriageState

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")

# Modelo preferido para la segunda opinión. Vacío: se elige solo, salteando el que ya respondió.
MODELO_PREFERIDO = os.getenv("LLM_SEGUNDA_OPINION", "").strip()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extraer.md"

# Campos que se comparan. Son los datos del documento que después usan el score y el enrutamiento.
_CAMPOS = (
    "paciente.nome",
    "paciente.edad",
    "medico_solicitante.nombre",
    "medico_solicitante.matricula",
    "estudio_realizado",
    "hallazgos",
    "conclusion",
    "diagnostico_principal",
    "cie10_sugerido",
    "procedimiento_solicitado",
    "estudios_solicitados",
    "diagnostico_egreso",
    "motivo",
    "fecha",
)

# Cada campo puede venir con dos nombres: el contrato del brief usa `nome` y `medico_solicitante`,
# los esquemas por tipo usan `nombre` y `profesional`. Se aceptan los dos para que la comparación no
# dependa de esa diferencia.
_ALIAS: dict[str, tuple[str, ...]] = {
    "paciente.nome": ("paciente.nome", "paciente.nombre"),
    "paciente.edad": ("paciente.edad",),
    "medico_solicitante.nombre": ("medico_solicitante.nombre", "profesional.nombre"),
    "medico_solicitante.matricula": ("medico_solicitante.matricula", "profesional.matricula"),
    "estudio_realizado": ("estudio_realizado",),
    "hallazgos": ("hallazgos",),
    "conclusion": ("conclusion",),
    "diagnostico_principal": ("diagnostico_principal",),
    "cie10_sugerido": ("cie10_sugerido",),
    "procedimiento_solicitado": ("procedimiento_solicitado",),
    "estudios_solicitados": ("estudios_solicitados",),
    "diagnostico_egreso": ("diagnostico_egreso",),
    "motivo": ("motivo",),
    "fecha": ("fecha",),
}

_ESQUEMA_MINIMO = {
    "paciente": {"nome": "string o null", "edad": "entero o null"},
    "medico_solicitante": {"nombre": "string o null", "matricula": "string o null"},
    "diagnostico_principal": "string o null",
    "cie10_sugerido": "string o null",
    "medicamentos": [],
}

# --------------------------------------------------------------------------- comparación de campos


def _canonico(valor: Any) -> str:
    """Forma comparable de un valor: sin tildes, sin mayúsculas, sin espacios de más.

    Devuelve "" para lo que no aporta a la comparación (None, diccionario vacío, lista vacía).
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(int(valor)) if float(valor).is_integer() else str(round(float(valor), 2))
    if isinstance(valor, dict):
        return ""
    if isinstance(valor, (list, tuple)):
        partes = [_canonico(item) for item in valor]
        return "|".join(sorted(p for p in partes if p))

    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split()).strip(" .,;:-–—")


def _leer(datos: dict, rutas: tuple[str, ...]) -> Any:
    """Primer valor presente entre los nombres alternativos de un campo. Soporta rutas anidadas."""
    for ruta in rutas:
        valor: Any = datos
        for parte in ruta.split("."):
            if not isinstance(valor, dict):
                valor = None
                break
            valor = valor.get(parte)
        if valor not in (None, "", [], {}):
            return valor
    return None


def _nombres_medicamentos(datos: dict) -> list[str]:
    """Nombres de medicamentos en forma comparable. Acepta dicts y strings sueltos."""
    nombres = []
    for med in datos.get("medicamentos") or []:
        nombre = _canonico(med.get("nombre")) if isinstance(med, dict) else _canonico(med)
        if nombre:
            nombres.append(nombre)
    return sorted(set(nombres))


def _aplanar(datos: dict) -> dict[str, str]:
    """Deja una extracción en la misma forma que la otra: campo comparable → valor comparable.

    Los campos vacíos no se incluyen: así un dato ausente no se compara contra nada.
    """
    plano: dict[str, str] = {}
    for campo in _CAMPOS:
        canonico = _canonico(_leer(datos, _ALIAS[campo]))
        if canonico:
            plano[campo] = canonico

    medicamentos = _nombres_medicamentos(datos)
    if medicamentos:
        plano["medicamentos"] = "|".join(medicamentos)
    return plano


def _comparar(primero: dict[str, str], segundo: dict[str, str]) -> dict[str, Any]:
    """Compara dos extracciones aplanadas y devuelve el veredicto campo por campo.

    `acuerdo` es False solo cuando los dos modelos dan un valor presente y distinto para el mismo
    campo. Cuando uno completa y el otro no, el campo se informa como `solo_en_un_modelo`.
    """
    en_desacuerdo: list[str] = []
    solo_en_uno: list[str] = []

    for campo in sorted(set(primero) | set(segundo)):
        valor_primero, valor_segundo = primero.get(campo), segundo.get(campo)
        if valor_primero and valor_segundo:
            if valor_primero != valor_segundo:
                en_desacuerdo.append(campo)
        elif valor_primero or valor_segundo:
            solo_en_uno.append(campo)

    return {
        "acuerdo": not en_desacuerdo,
        "campos_en_desacuerdo": en_desacuerdo,
        "campos_solo_en_un_modelo": solo_en_uno,
    }


# --------------------------------------------------------------------------- llamada al modelo


def _parsear_json(texto: str) -> dict:
    """Parsea JSON tolerando bloques markdown ```json ... ```, como el resto de los nodos."""
    limpio = (texto or "").strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[1] if "\n" in limpio else limpio
        if limpio.endswith("```"):
            limpio = limpio[:-3]
        limpio = limpio.strip()
    datos = json.loads(limpio)
    if not isinstance(datos, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON")
    return datos


def _esquema_json(tipo_documento: str) -> str:
    """Esquema del tipo, para llenar {{esquema_json}} del prompt. Sin esquema propio, uno mínimo."""
    modelo = ESQUEMAS_POR_TIPO.get(tipo_documento)
    esquema = modelo.model_json_schema() if modelo is not None else _ESQUEMA_MINIMO
    return json.dumps(esquema, ensure_ascii=False, indent=2)


def _construir_prompt(texto: str, tipo_documento: str) -> str:
    """Mismo prompt que la primera extracción: sin eso no se comparan modelos, se comparan prompts."""
    plantilla = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        plantilla.replace("{{tipo_documento}}", tipo_documento)
        .replace("{{esquema_json}}", _esquema_json(tipo_documento))
        .replace("{{documento}}", texto)
    )


def _rutas_de_imagenes(state: TriageState) -> list[str]:
    """Solo rutas reales: la ingesta entrega páginas en base64 y el adaptador espera archivos."""
    return [p for p in (state.get("imagenes") or []) if isinstance(p, str) and os.path.isfile(p)]


def _elegir_modelo(modelo_primario: str | None) -> str | None:
    """Otro modelo de la cadena. Si no hay ninguno distinto, no hay segunda opinión posible."""
    candidatos = [m for m in adapter.modelos_disponibles() if m != modelo_primario]
    if MODELO_PREFERIDO and MODELO_PREFERIDO in candidatos:
        return MODELO_PREFERIDO
    return candidatos[0] if candidatos else None


def _motivo_para_no_llamar(state: TriageState) -> str | None:
    """Por qué no se puede pedir la segunda opinión. None cuando sí se puede."""
    if not USE_LLM:
        return "USE_LLM está desactivado: no se pidió segunda opinión."
    if not PROMPT_PATH.exists():
        return f"No está el prompt de extracción ({PROMPT_PATH.name})."
    if not (state.get("texto") or "").strip() and not _rutas_de_imagenes(state):
        return "No hay texto ni imágenes para volver a extraer."
    return None


# --------------------------------------------------------------------------- nodo


def segunda_opinion(state: TriageState) -> dict:
    """Repite la extracción con otro modelo y la compara campo por campo. Una sola vez."""
    if state.get("segunda_opinion"):
        # El grafo ya evita la segunda vuelta; esto la evita también si el nodo se llama suelto.
        return {}

    modelo_primario = state.get("modelo_utilizado") or adapter.PRIMARY
    resultado: dict[str, Any] = {
        "disponible": False,
        "acuerdo": None,
        "campos_en_desacuerdo": [],
        "campos_solo_en_un_modelo": [],
        "campos_comparados": 0,
        "modelo": None,
        "modelo_primario": modelo_primario,
        "motivo": "",
    }

    motivo = _motivo_para_no_llamar(state)
    modelo = None if motivo else _elegir_modelo(modelo_primario)
    if motivo is None and modelo is None:
        motivo = "No hay otro modelo configurado en la cadena: no es posible una segunda opinión."
    if motivo:
        resultado["motivo"] = motivo
        return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", resultado)}

    imagenes = _rutas_de_imagenes(state)
    tipo_documento = state.get("clasificacion", {}).get("tipo_documento", "Otro")
    resultado["con_imagenes"] = bool(imagenes)

    try:
        prompt = _construir_prompt(state.get("texto") or "", tipo_documento)
        respuesta = adapter.complete(prompt, images=imagenes, json_mode=False, timeout=45, modelo=modelo)
    except Exception as e:  # noqa: BLE001 - un respaldo caído no puede perder el documento
        logger.warning("Segunda opinión no disponible con %s: %s", modelo, e)
        resultado["motivo"] = f"El modelo de respaldo no respondió: {type(e).__name__}"
        return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", resultado)}

    # El adaptador puede haber caído a otro respaldo de la cadena: se registra el que respondió.
    modelo = respuesta.model
    resultado.update(
        {
            "modelo": modelo,
            "latencia_ms": respuesta.latency_ms,
            "tokens_entrada": respuesta.tokens_entrada,
            "tokens_salida": respuesta.tokens_salida,
            "costo_usd": respuesta.costo_usd,
        }
    )

    try:
        payload = _parsear_json(respuesta.text)
    except (ValueError, TypeError) as e:
        logger.warning("Segunda opinión con JSON inválido de %s: %s", modelo, e)
        resultado["motivo"] = "El modelo de respaldo no devolvió un JSON válido."
        return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", resultado, modelo=modelo)}

    datos_segundo = payload.get("datos_extraidos", payload)
    if not isinstance(datos_segundo, dict):
        resultado["motivo"] = "El modelo de respaldo devolvió datos_extraidos con un formato inesperado."
        return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", resultado, modelo=modelo)}

    plano_primero = _aplanar(state.get("datos_extraidos") or {})
    plano_segundo = _aplanar(datos_segundo)
    if not plano_segundo:
        resultado["motivo"] = "El modelo de respaldo no devolvió ningún campo comparable."
        return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", resultado, modelo=modelo)}

    comparacion = _comparar(plano_primero, plano_segundo)
    resultado.update(comparacion)
    resultado.update(
        {
            "disponible": True,
            "datos": datos_segundo,
            "campos_comparados": len(set(plano_primero) | set(plano_segundo)),
            "campos_primero": sorted(plano_primero),
            "campos_segundo": sorted(plano_segundo),
            "motivo": (
                "Los modelos discrepan en " + ", ".join(comparacion["campos_en_desacuerdo"]) + "."
                if not comparacion["acuerdo"]
                else "Los dos modelos coinciden en los campos comparables."
            ),
        }
    )

    # La traza guarda el veredicto y no la extracción completa: el texto de la segunda extracción ya
    # viaja en `segunda_opinion.datos`, y la traza se lee, se persiste y se muestra en la UI.
    detalle = {k: v for k, v in resultado.items() if k != "datos"}
    return {"segunda_opinion": resultado, "trace": step(state, "segunda_opinion", detalle, modelo=modelo)}


__all__ = ["segunda_opinion"]
