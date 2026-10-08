"""Carga, validación y guardado de reglas.

Lee agent/rules/rules.yaml. Si existe un archivo de override (lo que escribe PUT /rules), manda el override.
La caché se invalida sola cuando cambia la fecha de modificación de cualquiera de los dos archivos, así que la
API y el worker ven el cambio sin reiniciar.
"""
import os
from pathlib import Path
from typing import Any

import yaml

RULES_PATH = Path(__file__).with_name("rules.yaml")
OVERRIDE_PATH = Path(
    os.getenv("RULES_OVERRIDE_PATH", Path(__file__).resolve().parents[2] / "data" / "rules.override.yaml")
)

CLAVES_OBLIGATORIAS = ("version", "umbrales", "legibilidad", "tipos_documento", "campos_obligatorios")
LISTAS_DE_TEXTO = ("hallazgos_criticos", "palabras_urgencia", "palabras_prioritario", "medicamentos_alto_riesgo")

_cache: dict[str, Any] = {"marca": None, "reglas": None}


class ReglasInvalidas(ValueError):
    """Las reglas no pasan la validación; .errores trae la lista legible."""

    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


def _ruta_activa() -> Path:
    return OVERRIDE_PATH if OVERRIDE_PATH.exists() else RULES_PATH


def _marca() -> tuple:
    return tuple(p.stat().st_mtime_ns if p.exists() else None for p in (RULES_PATH, OVERRIDE_PATH))


def load_rules() -> dict:
    marca = _marca()
    if _cache["reglas"] is None or _cache["marca"] != marca:
        with open(_ruta_activa(), encoding="utf-8") as f:
            _cache["reglas"] = yaml.safe_load(f)
        _cache["marca"] = marca
    return _cache["reglas"]


def _es_numero(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _lista_texto(valor: Any) -> bool:
    return isinstance(valor, list) and all(isinstance(v, str) and v.strip() for v in valor)


def validar_reglas(reglas: Any) -> list[str]:
    """Devuelve la lista de errores; vacía si las reglas son válidas."""
    if not isinstance(reglas, dict):
        return ["las reglas deben ser un objeto"]
    errores: list[str] = []
    for clave in CLAVES_OBLIGATORIAS:
        if clave not in reglas:
            errores.append(f"falta la clave '{clave}'")
    if errores:
        return errores

    u = reglas["umbrales"]
    if not isinstance(u, dict):
        errores.append("umbrales debe ser un objeto")
    else:
        for k in ("automatico", "segunda_opinion", "legibilidad_minima"):
            if not _es_numero(u.get(k)) or not 0 <= u[k] <= 1:
                errores.append(f"umbrales.{k} debe ser un número entre 0 y 1")
        if not errores and not u["automatico"] > u["segunda_opinion"] > u["legibilidad_minima"]:
            errores.append("se exige umbrales.automatico > segunda_opinion > legibilidad_minima")

    lg = reglas["legibilidad"]
    if not isinstance(lg, dict):
        errores.append("legibilidad debe ser un objeto")
    else:
        for k in ("leve", "media"):
            if not _es_numero(lg.get(k)) or not 0 <= lg[k] <= 1:
                errores.append(f"legibilidad.{k} debe ser un número entre 0 y 1")
        if _es_numero(lg.get("leve")) and _es_numero(lg.get("media")) and not lg["leve"] > lg["media"]:
            errores.append("se exige legibilidad.leve > legibilidad.media")

    tipos = reglas["tipos_documento"]
    if not _lista_texto(tipos) or not tipos:
        errores.append("tipos_documento debe ser una lista de textos no vacíos")
        tipos = []

    co = reglas["campos_obligatorios"]
    if not isinstance(co, dict):
        errores.append("campos_obligatorios debe ser un objeto")
    else:
        for tipo, campos in co.items():
            if tipo not in tipos:
                errores.append(f"campos_obligatorios: '{tipo}' no está en tipos_documento")
            if not _lista_texto(campos):
                errores.append(f"campos_obligatorios.{tipo} debe ser una lista de textos")

    for clave in LISTAS_DE_TEXTO:
        if clave in reglas and not _lista_texto(reglas[clave]):
            errores.append(f"{clave} debe ser una lista de textos no vacíos")

    aplica = (reglas.get("deteccion_automatica_urgencia") or {}).get("aplica_a")
    if aplica is not None:
        if not _lista_texto(aplica):
            errores.append("deteccion_automatica_urgencia.aplica_a debe ser una lista de textos")
        else:
            errores += [f"aplica_a: '{t}' no está en tipos_documento" for t in aplica if t not in tipos]

    for i, v in enumerate(reglas.get("valores_criticos_laboratorio") or []):
        if not isinstance(v, dict) or not isinstance(v.get("analito"), str) or "valor" not in v:
            errores.append(f"valores_criticos_laboratorio[{i}] necesita analito y valor")
        elif v.get("operador") not in (">=", "<=", ">", "<", "texto"):
            errores.append(f"valores_criticos_laboratorio[{i}].operador no es válido")

    fa = reglas.get("fuera_de_alcance")
    if fa is not None and (not isinstance(fa, dict) or not fa.get("categoria")):
        errores.append("fuera_de_alcance necesita 'categoria'")
    return errores


def guardar_reglas(reglas: dict) -> None:
    """Valida y escribe el override de forma atómica. Lanza ReglasInvalidas si algo no cuadra."""
    errores = validar_reglas(reglas)
    if errores:
        raise ReglasInvalidas(errores)
    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OVERRIDE_PATH.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(reglas, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(OVERRIDE_PATH)
    _cache["marca"] = None
