"""Reporte diario al gestor (N3-05).

Paso 1: KPIs del día desde SQLite. Solo conteos y porcentajes, sin datos de pacientes
(docs/privacidad.md: los reportes son agregados).
Paso 2: resumen de cinco líneas redactado por el agente, con una plantilla de respaldo.
Paso 3: copia en reportes/diario/{fecha}.json y generación a la hora configurada (REPORTE_HORA).
"""
import json
import logging
import os
import re
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent.llm.adapter import complete
from agent.storage import notifications, triage_results

logger = logging.getLogger(__name__)

LINEAS_RESUMEN = 5
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")
REPORTE_TZ = os.getenv("REPORTE_TZ", "America/Argentina/Buenos_Aires")
REPORTE_HORA = os.getenv("REPORTE_HORA", "07:00")
DESTINO_URGENCIA = "Cola_Emergencia_Medica"
DESTINO_REVISION = "Cola_Revision_Humana"


def zona_horaria(nombre: str = REPORTE_TZ) -> tzinfo:
    """Zona del reporte. Si el sistema no trae la base de zonas (Windows sin tzdata), usa UTC-3."""
    try:
        return ZoneInfo(nombre)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3))


def _ventana_utc(dia: date, tz: tzinfo) -> tuple[str, str]:
    """Inicio y fin del día local, en UTC y con el formato de created_at (CURRENT_TIMESTAMP)."""
    inicio = datetime.combine(dia, time.min, tzinfo=tz).astimezone(timezone.utc)
    fin = datetime.combine(dia + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    formato = "%Y-%m-%d %H:%M:%S"
    return inicio.strftime(formato), fin.strftime(formato)


def _filas_del_dia(dia: date, tz: tzinfo, db_path: Path | None) -> list[sqlite3.Row]:
    ruta = Path(db_path) if db_path is not None else triage_results.DB_PATH
    if not ruta.exists():
        return []
    inicio, fin = _ventana_utc(dia, tz)
    with closing(sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT destino, score, resultado_json FROM triage_results "
                "WHERE created_at >= ? AND created_at < ?",
                (inicio, fin),
            ).fetchall()
        except sqlite3.OperationalError:  # la tabla aún no existe
            return []


def kpis_del_dia(dia: date, tz: tzinfo | None = None, db_path: Path | None = None) -> dict:
    """KPIs del día local `dia`. Sin documentos, devuelve ceros y confianza_media None."""
    tz = tz or zona_horaria()
    filas = _filas_del_dia(dia, tz, db_path)

    por_destino: Counter = Counter()
    por_tipo: Counter = Counter()
    auditoria = 0
    for fila in filas:
        por_destino[fila["destino"]] += 1
        resultado = json.loads(fila["resultado_json"])
        por_tipo[(resultado.get("clasificacion") or {}).get("tipo_documento", "Otro")] += 1
        if (resultado.get("decision_enrutamiento") or {}).get("requiere_auditoria_humana"):
            auditoria += 1

    total = len(filas)
    return {
        "fecha": dia.isoformat(),
        "total": total,
        "urgencias": por_destino[DESTINO_URGENCIA],
        "en_revision": por_destino[DESTINO_REVISION],
        "requieren_auditoria": auditoria,
        "tasa_revision": round(por_destino[DESTINO_REVISION] / total, 3) if total else 0.0,
        "confianza_media": round(sum(f["score"] for f in filas) / total, 3) if total else None,
        "por_destino": dict(sorted(por_destino.items())),
        "por_tipo": dict(sorted(por_tipo.items())),
    }


def resumen_plantilla(kpis: dict) -> str:
    """Resumen de cinco líneas sin modelo. Es el respaldo cuando el LLM no responde."""
    fecha, total = kpis["fecha"], kpis["total"]
    if not total:
        lineas = [
            f"Reporte del {fecha}.",
            "No se procesaron documentos en el día.",
            "Sin urgencias.",
            "Sin casos en revisión humana.",
            "Sin novedades que informar.",
        ]
    else:
        destinos = ", ".join(f"{d} {n}" for d, n in kpis["por_destino"].items())
        lineas = [
            f"Reporte del {fecha}: documentos procesados: {total}.",
            f"Urgencias detectadas: {kpis['urgencias']}.",
            f"En revisión humana: {kpis['en_revision']} ({kpis['tasa_revision']:.0%} del total); "
            f"requieren auditoría: {kpis['requieren_auditoria']}.",
            f"Confianza media del agente: {kpis['confianza_media']:.2f}.",
            f"Destinos: {destinos}.",
        ]
    return "\n".join(lineas)


def _prompt_resumen(kpis: dict) -> str:
    return (
        "Eres el asistente de MediFlow. Redacta para el gestor hospitalario un resumen del día de "
        f"exactamente {LINEAS_RESUMEN} líneas, una frase por línea, sin viñetas ni títulos. "
        "Usa solo los datos de abajo: no inventes cifras ni agregues información que no esté.\n\n"
        f"Datos del día:\n{json.dumps(kpis, ensure_ascii=False, indent=2)}"
    )


def _cifras_permitidas(kpis: dict) -> set[float]:
    """Cifras que el resumen puede citar: las de los KPIs, sus porcentajes y las partes de la fecha."""
    permitidas: set[float] = set()

    def agregar(valor, *decimales: int) -> None:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return
        permitidas.add(round(float(valor), 6))
        for d in decimales:
            permitidas.add(round(float(round(valor, d)), 6))

    agregar(kpis.get("total"))
    agregar(kpis.get("urgencias"))
    agregar(kpis.get("en_revision"))
    agregar(kpis.get("requieren_auditoria"))
    agregar(kpis.get("confianza_media"), 1, 2, 3)
    tasa = kpis.get("tasa_revision")
    if isinstance(tasa, (int, float)):
        agregar(tasa * 100, 0, 1)
    for conteos in (kpis.get("por_destino") or {}, kpis.get("por_tipo") or {}):
        for valor in conteos.values():
            agregar(valor)
    for parte in _NUMERO.findall(str(kpis.get("fecha", ""))):
        agregar(float(parte))
    return permitidas


def cifras_validas(texto: str, kpis: dict) -> bool:
    """True si toda cifra del texto sale de los KPIs y el total de documentos aparece completo.

    Compara números enteros, no subcadenas: con total 4, "40 documentos" no vale. Un resumen con
    una cifra que no está en los KPIs (o con 0,70 frente a 0.7) se compara por valor.
    """
    cifras = [round(float(t.replace(",", ".")), 6) for t in _NUMERO.findall(texto)]
    total = kpis.get("total")
    if total is None or float(total) not in cifras:
        return False
    permitidas = _cifras_permitidas(kpis)
    return all(c in permitidas for c in cifras)


def redactar_resumen(kpis: dict) -> tuple[str, str]:
    """Devuelve (texto, origen). Origen es el modelo que lo redactó o "plantilla".

    Cae a la plantilla si USE_LLM no está activo, si el modelo falla, si su respuesta no tiene
    cinco líneas o si sus cifras no coinciden con los KPIs (ver `cifras_validas`).
    """
    if os.getenv("USE_LLM", "false").lower() not in ("true", "1", "yes"):
        return resumen_plantilla(kpis), "plantilla"
    try:
        resultado = complete(_prompt_resumen(kpis), json_mode=False, timeout=30)
    except Exception:  # noqa: BLE001 - el reporte no debe caerse por el modelo
        logger.exception("No se pudo redactar el resumen con el modelo; se usa la plantilla")
        return resumen_plantilla(kpis), "plantilla"

    lineas = [linea.strip() for linea in (resultado.text or "").splitlines() if linea.strip()]
    if len(lineas) != LINEAS_RESUMEN or not cifras_validas("\n".join(lineas), kpis):
        logger.warning("El resumen del modelo no cumple el formato; se usa la plantilla")
        return resumen_plantilla(kpis), "plantilla"
    return "\n".join(lineas), resultado.model


def ruta_reporte(dia: date) -> str:
    return f"reportes/diario/{dia.isoformat()}.json"


def armar_reporte(
    dia: date, tz: tzinfo | None = None, db_path: Path | None = None, ahora: datetime | None = None
) -> dict:
    """KPIs y resumen del día `dia`, listos para guardar."""
    kpis = kpis_del_dia(dia, tz, db_path)
    resumen, redactado_por = redactar_resumen(kpis)
    return {
        "fecha": dia.isoformat(),
        "resumen": resumen,
        "redactado_por": redactado_por,
        "kpis": kpis,
        "generado_en": (ahora or datetime.now(timezone.utc)).isoformat(),
    }


def enviar_por_correo(contenido: dict) -> bool:
    """Envía el resumen por correo. Si falla, el reporte ya está guardado y solo se registra."""
    try:
        return notifications.publicar_correo(f"MediFlow - Reporte diario {contenido['fecha']}", contenido["resumen"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo enviar el reporte por correo: %s", exc)
        return False


def generar_reporte_diario(
    ahora: datetime, storage, bucket: str, db_path: Path | None = None, hora: str | None = None
) -> str:
    """Genera el reporte del día anterior si ya pasó la hora y todavía no existe.

    `ahora` es un instante con zona. `storage` es el módulo de almacenamiento (local u OCI).
    Devuelve "temprano", "ya_existia" o "generado".
    """
    tz = zona_horaria()
    local = ahora.astimezone(tz)
    horas, minutos = (int(x) for x in (hora or REPORTE_HORA).split(":"))
    if (local.hour, local.minute) < (horas, minutos):
        return "temprano"

    dia = local.date() - timedelta(days=1)
    ruta = ruta_reporte(dia)
    if ruta in storage.list_prefix(bucket, ruta):
        return "ya_existia"

    contenido = armar_reporte(dia, tz, db_path, ahora)
    storage.upload_json(bucket, ruta, contenido)
    enviar_por_correo(contenido)
    return "generado"
