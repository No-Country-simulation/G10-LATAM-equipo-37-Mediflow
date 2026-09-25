"""Lectura de trazas y métricas de triaje.

Está separado de Streamlit a propósito: la página de Trazas y la de Métricas leen de acá, la API
puede devolver lo mismo en `/metrics` sin reimplementarlo y los tests verifican los números sin
abrir una interfaz.

Cuatro capas, cada una probable por separado:

1. `resumen_traza(trace)`: qué pasó dentro de una corrida (nodos, tiempos, modelos, costo).
2. `leer_resultados()`: qué documentos hay en el bucket, con el mismo backend que usa `persistir`.
3. `a_registros(...)`: una tabla, una fila por documento.
4. `metricas(...)`: los KPI y las alertas de calibración.

Ninguna función levanta excepción por datos faltantes o archivos a medio escribir: devuelve lo que
se pudo leer y lo informa. Un panel de métricas no puede tumbar la API ni la UI.
"""
from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Carpetas del bucket donde `persistir` deja resultados. El orden define el orden de la tabla.
CARPETAS = ("procesados/", "auditoria_humana/", "rechazados/")

# Umbrales por defecto, por si rules.yaml no está disponible.
UMBRAL_REVISION = 0.60
UMBRAL_AUTOMATICO = 0.85


def _storage(nombre_backend: str | None = None):
    """Backend de almacenamiento: el mismo que usa `persistir`, elegido por STORAGE_BACKEND."""
    nombre = (nombre_backend or os.getenv("STORAGE_BACKEND", "local")).lower()
    if nombre == "oci":
        from agent.storage import object_storage as storage
    else:
        from agent.storage import local as storage
    return storage


def bucket_configurado() -> str:
    """Bucket de resultados. Mismo valor por defecto que `persistir`."""
    return os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos")


def umbrales() -> dict[str, float]:
    """Umbrales de decisión. Si rules.yaml está disponible mandan esos; si no, los del contrato."""
    try:
        from agent.rules.loader import load_rules

        reglas = load_rules().get("umbrales") or {}
        return {
            "revision": float(reglas.get("segunda_opinion", UMBRAL_REVISION)),
            "automatico": float(reglas.get("automatico", UMBRAL_AUTOMATICO)),
        }
    except Exception as e:  # noqa: BLE001 - sin reglas se muestran los valores por defecto
        logger.debug("No se pudieron leer los umbrales de rules.yaml: %s", e)
        return {"revision": UMBRAL_REVISION, "automatico": UMBRAL_AUTOMATICO}


# --------------------------------------------------------------------------- traza de una corrida


def _numero(valor: Any) -> float | None:
    """Convierte a número lo que se pueda; None para todo lo demás (textos, listas, vacíos)."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _ms_del_registro(registro: dict, siguiente: dict | None) -> float | None:
    """Duración del nodo.

    La mide el grafo al envolver cada nodo con `graph._con_tiempo`. Si un registro viejo no la trae,
    se usa la diferencia con la marca de tiempo siguiente, que acota al nodo siguiente y no a este:
    sirve para ver el orden de magnitud, no para comparar nodos entre sí.
    """
    propio = _numero(registro.get("ms"))
    if propio is not None:
        return round(propio, 1)
    if siguiente is None:
        return None
    ts, ts_siguiente = _numero(registro.get("ts")), _numero(siguiente.get("ts"))
    if ts is None or ts_siguiente is None:
        return None
    return round((ts_siguiente - ts) * 1000, 1)


def resumen_traza(trace: list[dict] | None) -> dict[str, Any]:
    """Resume una traza: nodos con su duración, modelos usados y costo acumulado."""
    registros = [r for r in (trace or []) if isinstance(r, dict)]
    nodos: list[dict[str, Any]] = []
    modelos: list[str] = []
    repetidos: dict[str, int] = {}
    tokens_entrada = tokens_salida = 0
    costo: float | None = None
    todos_medidos = bool(registros)

    for indice, registro in enumerate(registros):
        siguiente = registros[indice + 1] if indice + 1 < len(registros) else None
        nombre = registro.get("nodo") or "nodo"
        repetidos[nombre] = repetidos.get(nombre, 0) + 1

        modelo = registro.get("modelo")
        if isinstance(modelo, str) and modelo and modelo not in modelos:
            modelos.append(modelo)

        detalle = registro.get("detalle") if isinstance(registro.get("detalle"), dict) else {}
        tokens_entrada += int(_numero(detalle.get("tokens_entrada")) or 0)
        tokens_salida += int(_numero(detalle.get("tokens_salida")) or 0)
        costo_detalle = _numero(detalle.get("costo_usd"))
        if costo_detalle is not None:
            costo = (costo or 0.0) + costo_detalle

        ms = _ms_del_registro(registro, siguiente)
        todos_medidos = todos_medidos and ms is not None
        nodos.append({"nodo": nombre, "modelo": modelo, "ms": ms, "ts": registro.get("ts"), "detalle": detalle})

    duraciones = [n["ms"] for n in nodos if n["ms"] is not None]
    return {
        "nodos": nodos,
        "nodos_ejecutados": [n["nodo"] for n in nodos],
        "nodos_repetidos": repetidos,
        "total_ms": round(sum(duraciones), 1) if duraciones else None,
        "medido": todos_medidos,
        "modelos": modelos,
        "cambio_de_modelo": {
            "hubo": len(modelos) > 1,
            "de": modelos[0] if modelos else None,
            "a": modelos[-1] if modelos else None,
        },
        "tokens": {"entrada": tokens_entrada, "salida": tokens_salida},
        "costo_usd": round(costo, 6) if costo is not None else None,
        "segunda_opinion": "segunda_opinion" in repetidos,
    }


# --------------------------------------------------------------------------- resultados persistidos


def _raiz_datos() -> Path:
    """Raíz del almacenamiento local: `./data`, el mismo layout que usa el bucket.

    Se puede mover con MEDIFLOW_DATA_DIR para la UI en contenedor, donde el repo se monta en /app.
    """
    por_defecto = Path(__file__).resolve().parent.parent / "data"
    return Path(os.getenv("MEDIFLOW_DATA_DIR", str(por_defecto)))


def _leer_del_disco(bucket: str, prefijos: tuple[str, ...]) -> dict[str, Any]:
    """Lee los resultados escritos en `./data/{bucket}/`, sin pasar por el módulo de storage.

    Es el mismo layout que documenta `docs/architecture.md`. Existe como respaldo mientras
    `agent/storage/local.py` no esté en la rama: así la pantalla de Trazas funciona igual y, cuando
    el backend local llegue, `leer_resultados` lo usa a él y este camino queda de red de seguridad.
    """
    base = _raiz_datos() / bucket
    resultado: dict[str, Any] = {"resultados": [], "archivos": 0, "ilegibles": 0, "error": None}
    if not base.exists():
        resultado["error"] = f"No hay resultados persistidos en {base}."
        return resultado

    for path in sorted(base.rglob("*.json")):
        relativa = path.relative_to(base).as_posix()
        if not relativa.startswith(prefijos):
            continue
        resultado["archivos"] += 1
        try:
            datos = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 - un archivo roto no invalida los demás
            logger.debug("Resultado ilegible %s: %s", relativa, e)
            resultado["ilegibles"] += 1
            continue
        if isinstance(datos, dict):
            datos.setdefault("ruta_objeto", relativa)
            resultado["resultados"].append(datos)
        else:
            resultado["ilegibles"] += 1
    return resultado


def leer_resultados(
    bucket: str | None = None,
    backend: str | None = None,
    prefijos: tuple[str, ...] = CARPETAS,
) -> dict[str, Any]:
    """Lee los resultados persistidos del bucket.

    Devuelve `{"resultados", "archivos", "ilegibles", "error"}`. Nunca levanta: si el backend no
    está disponible (OCI sin credenciales, por ejemplo) lo informa en `error` y devuelve la lista
    vacía, para que la pantalla pueda explicar qué falta en vez de romperse.
    """
    bucket = bucket or bucket_configurado()

    try:
        almacenamiento = _storage(backend)
    except ImportError as e:
        logger.info("Backend de almacenamiento no disponible (%s): se lee del disco.", e)
        return _leer_del_disco(bucket, prefijos)

    resultado: dict[str, Any] = {"resultados": [], "archivos": 0, "ilegibles": 0, "error": None}
    try:
        rutas: list[str] = []
        for prefijo in prefijos:
            rutas.extend(almacenamiento.list_prefix(bucket, prefijo))
    except Exception as e:  # noqa: BLE001 - sin backend no hay datos, pero tampoco una excepción
        logger.warning("No se pudo listar el bucket %s (%s): se intenta del disco.", bucket, e)
        return _leer_del_disco(bucket, prefijos)

    resultado["archivos"] = len(rutas)
    for ruta in sorted(set(rutas)):
        if not ruta.endswith(".json"):
            continue
        try:
            contenido = almacenamiento.download(bucket, ruta)
            datos = json.loads(contenido.decode("utf-8") if isinstance(contenido, bytes) else contenido)
        except Exception as e:  # noqa: BLE001 - un archivo roto no invalida los demás
            logger.debug("Resultado ilegible %s: %s", ruta, e)
            resultado["ilegibles"] += 1
            continue
        if isinstance(datos, dict):
            datos.setdefault("ruta_objeto", ruta)
            resultado["resultados"].append(datos)
        else:
            resultado["ilegibles"] += 1
    return resultado


def cargar_json(contenido: str | bytes) -> dict[str, Any]:
    """Parsea un resultado pegado o subido a mano. Levanta ValueError con un mensaje para la UI."""
    texto = contenido.decode("utf-8") if isinstance(contenido, bytes) else contenido
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"El contenido no es JSON válido: {e.msg} (línea {e.lineno})") from e
    if not isinstance(datos, dict):
        raise ValueError("Se esperaba un objeto JSON con el resultado de un triaje")
    return datos


# --------------------------------------------------------------------------- tabla y métricas


def a_registros(resultados: list[dict]) -> list[dict[str, Any]]:
    """Una fila por documento, con los campos que usan las tablas y los gráficos."""
    registros = []
    for resultado in resultados:
        decision = resultado.get("decision") or {}
        clasificacion = resultado.get("clasificacion") or {}
        urgencia = resultado.get("urgencia") or {}
        segunda = resultado.get("segunda_opinion") or {}
        traza = resumen_traza(resultado.get("trace"))
        registros.append(
            {
                "documento_id": resultado.get("documento_id"),
                "tipo_documento": clasificacion.get("tipo_documento") or "Otro",
                "prioridad": clasificacion.get("nivel_prioridad"),
                "destino": decision.get("destino_principal") or "desconocido",
                "requiere_auditoria": bool(decision.get("requiere_auditoria_humana")),
                "urgencia": bool(urgencia.get("detectada")),
                "alto_riesgo": bool(urgencia.get("alto_riesgo_farmacologico")),
                "score": _numero(resultado.get("score")),
                "modelo": resultado.get("modelo_utilizado"),
                "segunda_opinion": bool(segunda.get("disponible")),
                "acuerdo_segunda_opinion": segunda.get("acuerdo"),
                "modelo_segunda_opinion": segunda.get("modelo"),
                "ms_total": traza["total_ms"],
                "costo_usd": traza["costo_usd"],
                "nodos_ejecutados": len(traza["nodos"]),
                "tipo_archivo": resultado.get("tipo_archivo"),
                "canal_origen": resultado.get("canal_origen"),
                "ruta_objeto": resultado.get("ruta_objeto"),
            }
        )
    return registros


def _percentil(valores: list[float], proporcion: float) -> float | None:
    """Percentil por interpolación lineal. Sin numpy ni pandas: no hacen falta para esto."""
    if not valores:
        return None
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return round(ordenados[0], 1)
    posicion = (len(ordenados) - 1) * proporcion
    inferior, superior = math.floor(posicion), math.ceil(posicion)
    if inferior == superior:
        return round(ordenados[inferior], 1)
    peso = posicion - inferior
    return round(ordenados[inferior] * (1 - peso) + ordenados[superior] * peso, 1)


def _conteo(registros: list[dict], campo: str) -> dict[str, int]:
    """Cuenta documentos por valor de un campo, de mayor a menor."""
    conteo: dict[str, int] = {}
    for registro in registros:
        clave = str(registro.get(campo) or "desconocido")
        conteo[clave] = conteo.get(clave, 0) + 1
    return dict(sorted(conteo.items(), key=lambda item: -item[1]))


def _confianza_media_por_tipo(registros: list[dict]) -> dict[str, float]:
    """Confianza media por tipo documental, solo con los documentos que tienen score."""
    medias: dict[str, float] = {}
    for tipo in _conteo(registros, "tipo_documento"):
        scores = [r["score"] for r in registros if r["tipo_documento"] == tipo and r["score"] is not None]
        if scores:
            medias[tipo] = round(sum(scores) / len(scores), 3)
    return medias


def _calibracion(registros: list[dict], umbral_revision: float, umbral_automatico: float) -> list[dict]:
    """Tasa de revisión humana por franja de score.

    Es el control de que el score diga algo: si en la franja alta aparecen documentos que terminaron
    en revisión, o el score está mal calibrado o hay una regla tapando el problema.
    """
    franjas = (
        (f"0,00 - {umbral_revision:.2f}", 0.0, umbral_revision),
        (f"{umbral_revision:.2f} - {umbral_automatico:.2f}", umbral_revision, umbral_automatico),
        (f"{umbral_automatico:.2f} - 1,00", umbral_automatico, 1.01),
    )
    calibracion = []
    for etiqueta, desde, hasta in franjas:
        en_franja = [r for r in registros if r["score"] is not None and desde <= r["score"] < hasta]
        revisados = [r for r in en_franja if r["destino"] == "Cola_Revision_Humana"]
        calibracion.append(
            {
                "rango": etiqueta,
                "documentos": len(en_franja),
                "revision_humana": len(revisados),
                "tasa": round(len(revisados) / len(en_franja), 3) if en_franja else None,
            }
        )
    return calibracion


def metricas(registros: list[dict], umbrales_decisores: dict[str, float] | None = None) -> dict[str, Any]:
    """KPI de operación a partir de los registros. Sin datos devuelve contadores en cero."""
    umbral = umbrales_decisores or umbrales()
    total = len(registros)
    scores = [r["score"] for r in registros if r["score"] is not None]
    latencias = [r["ms_total"] for r in registros if r["ms_total"] is not None]
    costos = [r["costo_usd"] for r in registros if r["costo_usd"] is not None]
    en_revision = [r for r in registros if r["destino"] == "Cola_Revision_Humana"]
    urgencias = [r for r in registros if r["urgencia"]]
    segunda = [r for r in registros if r["segunda_opinion"]]
    desacuerdos = [r for r in segunda if r["acuerdo_segunda_opinion"] is False]

    return {
        "documentos": total,
        "por_tipo": _conteo(registros, "tipo_documento"),
        "por_destino": _conteo(registros, "destino"),
        "por_modelo": _conteo(registros, "modelo"),
        "por_canal": _conteo(registros, "canal_origen"),
        "urgencias": len(urgencias),
        "urgencias_pct": round(len(urgencias) / total, 3) if total else None,
        "con_auditoria": sum(1 for r in registros if r["requiere_auditoria"]),
        "tasa_revision_humana": round(len(en_revision) / total, 3) if total else None,
        "confianza_media": round(sum(scores) / len(scores), 3) if scores else None,
        "confianza_media_por_tipo": _confianza_media_por_tipo(registros),
        "calibracion": _calibracion(registros, umbral["revision"], umbral["automatico"]),
        "segunda_opinion": {
            "pedidas": len(segunda),
            "desacuerdos": len(desacuerdos),
            "tasa_desacuerdo": round(len(desacuerdos) / len(segunda), 3) if segunda else None,
        },
        "latencia_ms": {
            "media": round(sum(latencias) / len(latencias), 1) if latencias else None,
            "p50": _percentil(latencias, 0.50),
            "p95": _percentil(latencias, 0.95),
        },
        "costo_usd": round(sum(costos), 6) if costos else None,
        "costo_medio_usd": round(sum(costos) / len(costos), 6) if costos else None,
        "alertas": _alertas(registros, umbral),
    }


def _alertas(registros: list[dict], umbral: dict[str, float]) -> list[str]:
    """Inconsistencias que un tablero de triaje no puede dejar pasar sin decir nada."""
    alertas: list[str] = []

    sin_revisar = [
        r for r in registros if (r["score"] or 0.0) < umbral["revision"] and r["destino"] != "Cola_Revision_Humana"
    ]
    if sin_revisar:
        alertas.append(
            f"{len(sin_revisar)} documento(s) con score bajo el umbral de revisión no terminaron en revisión humana."
        )

    en_revision_alto = [
        r for r in registros if (r["score"] or 0.0) >= umbral["automatico"] and r["destino"] == "Cola_Revision_Humana"
    ]
    if en_revision_alto:
        alertas.append(
            f"{len(en_revision_alto)} documento(s) con score sobre el umbral automático terminaron en revisión humana."
        )

    sin_score = [r for r in registros if r["score"] is None]
    if sin_score:
        alertas.append(f"{len(sin_score)} documento(s) sin score: revisá si el grafo llegó hasta puntuar.")

    sin_traza = [r for r in registros if not r["nodos_ejecutados"]]
    if sin_traza:
        alertas.append(
            f"{len(sin_traza)} documento(s) sin traza guardada: se persiste desde `persistir`, "
            "revisá resultados anteriores a este cambio."
        )
    return alertas


__all__ = [
    "CARPETAS",
    "a_registros",
    "bucket_configurado",
    "cargar_json",
    "leer_resultados",
    "metricas",
    "resumen_traza",
    "umbrales",
]
