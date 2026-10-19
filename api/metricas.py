"""Métricas del dashboard (N3-04).

Dos fuentes, dos preguntas:

- Operación: qué está pasando con los documentos reales. Sale de `triage_results` (SQLite, N1-02) y
  de la cola de revisión humana. Responde `GET /metrics`.
- Evaluación: qué tan bien decide el agente. Sale de la última corrida oficial del conjunto de
  prueba, guardada en `evals/resultados/<corrida>/resultados.json`, más la etiqueta de cada caso en
  `evals/golden/plan_golden.csv`. Responde `GET /metrics/evaluacion`.

Las funciones de cálculo son puras: reciben filas y devuelven diccionarios, así se prueban sin
base de datos ni archivos. Por privacidad, nada de lo que devuelven trae datos del paciente: ni
nombres, ni texto del documento, ni el mensaje de la alerta. Solo identificadores, destinos,
tipos, scores y horas.
"""
from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RAIZ = Path(__file__).resolve().parent.parent
DIR_EVALUACIONES = Path(os.getenv("MEDIFLOW_EVAL_DIR", RAIZ / "evals" / "resultados"))
PLAN_GOLDEN = Path(os.getenv("MEDIFLOW_PLAN_GOLDEN", RAIZ / "evals" / "golden" / "plan_golden.csv"))


def _zona(nombre: str):
    """La zona del hospital. La imagen python:slim no trae la base de zonas horarias: en ese caso se usa
    UTC-3 fijo, que es la hora de Argentina todo el año (no tiene horario de verano)."""
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone(timedelta(hours=-3), nombre)


# "Hoy" es el día del hospital, no el del servidor: la VM corre en UTC.
ZONA = _zona(os.getenv("MEDIFLOW_TZ", "America/Argentina/Buenos_Aires"))

DESTINOS = [
    "Cola_Emergencia_Medica",
    "Farmacia_Hospitalaria",
    "Auditoria_Autorizaciones",
    "Historia_Clinica_Electronica",
    "Cola_Revision_Humana",
]
TIPOS = [
    "Receta Medica",
    "Informe de Estudio por Imagenes",
    "Informe de Laboratorio",
    "Orden de Solicitud de Procedimiento",
    "Epicrisis",
    "Certificado Medico",
    "Otro",
]
URGENCIA = "Cola_Emergencia_Medica"
REVISION = "Cola_Revision_Humana"
MAX_ALERTAS = 10


# --------------------------------------------------------------------------- operación
def _fecha_local(created_at: str | None) -> datetime | None:
    """`created_at` de SQLite viene en UTC y sin zona («2026-10-13 14:05:09»)."""
    if not created_at:
        return None
    try:
        crudo = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if crudo.tzinfo is None:
        crudo = crudo.replace(tzinfo=timezone.utc)
    return crudo.astimezone(ZONA)


def _dict(valor: Any) -> dict:
    return valor if isinstance(valor, dict) else {}


def _score(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if 0 <= valor <= 1 else None


def _contar(valores: list[str], orden: list[str]) -> list[dict]:
    """Conteo en el orden fijo del contrato; lo que no está en el contrato va al final."""
    conteo = Counter(v for v in valores if v)
    filas = [{"nombre": n, "cantidad": conteo.pop(n, 0)} for n in orden]
    filas += [{"nombre": n, "cantidad": c} for n, c in sorted(conteo.items())]
    return filas


def _franja(score: float, umbrales: dict) -> str:
    automatico = float(umbrales.get("automatico", 0.85))
    segunda = float(umbrales.get("segunda_opinion", 0.60))
    if score >= automatico:
        return "automatico"
    if score >= segunda:
        return "segunda_opinion"
    return "revision"


def metricas_operacion(filas: list[dict], en_revision: int, umbrales: dict, hoy: date | None = None) -> dict:
    """Resume los resultados guardados en `triage_results`.

    `filas` son las de `triage_results.listar_completos()`: documento_id, created_at y el resultado
    completo (la salida de la sección 2 del contrato). `en_revision` es el largo de la cola humana.
    """
    hoy = hoy or datetime.now(ZONA).date()
    registros = []
    for fila in filas:
        resultado = _dict(fila.get("resultado"))
        decision = _dict(resultado.get("decision_enrutamiento"))
        clasificacion = _dict(resultado.get("clasificacion"))
        fecha = _fecha_local(fila.get("created_at"))
        registros.append({
            "documento_id": str(fila.get("documento_id") or resultado.get("documento_id") or ""),
            "fecha": fecha,
            "destino": str(decision.get("destino_principal") or ""),
            "auditoria": bool(decision.get("requiere_auditoria_humana")),
            "alerta": _dict(decision.get("notificacion_generada")),
            "tipo": str(clasificacion.get("tipo_documento") or ""),
            "score": _score(resultado.get("score_confianza")),
            "modelo": str(resultado.get("modelo_utilizado") or ""),
        })

    de_hoy = [r for r in registros if r["fecha"] and r["fecha"].date() == hoy]
    scores = [r["score"] for r in registros if r["score"] is not None]
    franjas = Counter(_franja(s, umbrales) for s in scores)
    alertas = sorted(
        (r for r in registros if r["alerta"]),
        key=lambda r: r["fecha"] or datetime.min.replace(tzinfo=ZONA),
        reverse=True,
    )[:MAX_ALERTAS]
    total = len(registros)

    return {
        "hoy": hoy.isoformat(),
        "zona_horaria": str(ZONA),
        "documentos_total": total,
        "documentos_hoy": len(de_hoy),
        "urgencias_total": sum(1 for r in registros if r["destino"] == URGENCIA),
        "urgencias_hoy": sum(1 for r in de_hoy if r["destino"] == URGENCIA),
        "en_revision": en_revision,
        "con_auditoria": sum(1 for r in registros if r["auditoria"]),
        "tasa_revision_humana": round(sum(1 for r in registros if r["auditoria"]) / total, 4) if total else None,
        "confianza_media": round(sum(scores) / len(scores), 4) if scores else None,
        "por_destino": _contar([r["destino"] for r in registros], DESTINOS),
        "por_tipo": _contar([r["tipo"] for r in registros], TIPOS),
        "franjas_confianza": [
            {"nombre": "automatico", "desde": float(umbrales.get("automatico", 0.85)),
             "cantidad": franjas["automatico"]},
            {"nombre": "segunda_opinion", "desde": float(umbrales.get("segunda_opinion", 0.60)),
             "cantidad": franjas["segunda_opinion"]},
            {"nombre": "revision", "desde": 0.0, "cantidad": franjas["revision"]},
        ],
        "modelos": [
            {"nombre": n, "cantidad": c}
            for n, c in Counter(r["modelo"] or "sin modelo" for r in registros).most_common()
        ],
        # Sin el mensaje de la alerta: puede nombrar al paciente.
        "alertas": [
            {
                "documento_id": r["documento_id"],
                "fecha": r["fecha"].isoformat() if r["fecha"] else None,
                "destino": r["destino"],
                "tipo": r["tipo"],
                "canal": str(r["alerta"].get("canal") or ""),
            }
            for r in alertas
        ],
    }


# --------------------------------------------------------------------------- evaluación
_PORCENTAJE = re.compile(r"(\d+)%\s*\((\d+)/(\d+)\)")
METRICAS_EVALUACION = [
    ("recall_urgencias", "Recall de urgencias"),
    ("accuracy_clasificacion", "Clasificación"),
    ("accuracy_destino", "Destino"),
    ("accuracy_auditoria", "Marca de auditoría"),
    ("fuera_de_alcance", "Fuera de alcance"),
    ("puerta_legibilidad", "Puerta de legibilidad"),
    ("tasa_revision_humana", "Tasa de revisión humana"),
    ("casos_perfectos", "Casos correctos en todo"),
]


def parsear_porcentaje(texto: Any) -> dict | None:
    """«90% (57/63)» -> {"valor": 0.9048, "aciertos": 57, "total": 63}. Lo demás, None."""
    m = _PORCENTAJE.search(str(texto or ""))
    if not m:
        return None
    aciertos, total = int(m.group(2)), int(m.group(3))
    return {"valor": round(aciertos / total, 4) if total else None, "aciertos": aciertos, "total": total}


def cargar_plan(ruta: Path | None = None) -> dict[str, dict]:
    ruta = Path(ruta or PLAN_GOLDEN)
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8-sig") as fh:
        return {fila["id"]: fila for fila in csv.DictReader(fh)}


def listar_corridas(directorio: Path | None = None) -> list[str]:
    """Corridas oficiales, la más reciente primero. Cada una es una carpeta con resultados.json."""
    directorio = Path(directorio or DIR_EVALUACIONES)
    if not directorio.exists():
        return []
    return sorted((d.name for d in directorio.iterdir() if (d / "resultados.json").is_file()), reverse=True)


def cargar_corrida(nombre: str | None = None, directorio: Path | None = None) -> tuple[str, dict] | None:
    directorio = Path(directorio or DIR_EVALUACIONES)
    corridas = listar_corridas(directorio)
    if not corridas:
        return None
    if nombre is None:
        nombre = corridas[0]
    if nombre not in corridas:  # también impide salir de la carpeta con «..»
        return None
    with open(directorio / nombre / "resultados.json", encoding="utf-8") as fh:
        return nombre, json.load(fh)


def _categoria_de_fallo(variante: dict, caso: dict) -> str:
    """La misma agrupación que el informe de `evals/run.py` (sección «Fallos por categoría»)."""
    nivel = caso.get("nivel_legibilidad", "")
    if variante.get("clase") == "imagen" and nivel in ("media", "severa"):
        return f"legibilidad {nivel}"
    if caso.get("categoria_ambiguedad"):
        return caso["categoria_ambiguedad"]
    if caso.get("resultado_esperado") in ("urgencia", "urgencia_ambiguedad"):
        return "urgencia"
    return caso.get("tipo_documento") or "sin etiqueta"


def resumen_evaluacion(nombre: str, datos: dict, plan: dict[str, dict], corridas: list[str]) -> dict:
    variantes = [v for v in datos.get("variantes", []) if isinstance(v, dict)]
    metricas = _dict(datos.get("metricas"))

    # Clasificación y destino por tipo de documento esperado, solo sobre lo legible (como run.py).
    por_tipo: dict[str, dict] = {}
    fallos_por_campo: Counter = Counter()
    fallos_por_categoria: dict[str, list[str]] = {}
    fallos = []
    modelos: Counter = Counter()
    for v in variantes:
        caso = plan.get(v.get("id", ""), {})
        aciertos = _dict(v.get("aciertos"))
        obtenido = _dict(v.get("obtenido"))
        if obtenido.get("modelo"):
            modelos[obtenido["modelo"]] += 1
        legible = v.get("clase") != "imagen" or caso.get("nivel_legibilidad", "") in ("", "leve")
        tipo = caso.get("tipo_documento") or "sin etiqueta"
        if legible and not v.get("error"):
            fila = por_tipo.setdefault(tipo, {"tipo": tipo, "variantes": 0, "destino_ok": 0, "tipo_ok": 0})
            fila["variantes"] += 1
            fila["destino_ok"] += int(bool(aciertos.get("destino")))
            fila["tipo_ok"] += int(bool(aciertos.get("tipo", True)))
        if v.get("ok"):
            continue
        etiqueta = v.get("id", "")
        if v.get("clase") == "imagen" and caso.get("nivel_legibilidad"):
            etiqueta += f" ({caso['nivel_legibilidad']})"
        fallos_por_categoria.setdefault(_categoria_de_fallo(v, caso), []).append(etiqueta)
        campos = [c for c, ok in aciertos.items() if not ok] or (["error de ejecución"] if v.get("error") else [])
        fallos_por_campo.update(campos)
        fallos.append({
            "id": v.get("id", ""),
            "archivo": v.get("archivo", ""),
            "categoria": _categoria_de_fallo(v, caso),
            "campos": campos,
            "esperado_destino": caso.get("destino_esperado", ""),
            "obtenido_destino": obtenido.get("destino_principal", ""),
            "error": str(v.get("error") or "")[:120],
        })

    orden_tipos = {t: i for i, t in enumerate(TIPOS)}
    return {
        "corrida": nombre,
        "corridas": corridas,
        "fecha": datos.get("fecha"),
        "simulado": bool(datos.get("simulado")),
        "variantes": len(variantes),
        "casos_con_error": metricas.get("casos_con_error", 0),
        "falsas_urgencias": metricas.get("falsas_urgencias", 0),
        "latencia_p50": metricas.get("latencia_p50"),
        "latencia_p95": metricas.get("latencia_p95"),
        "metricas": [
            {"clave": clave, "nombre": nombre_metrica, "texto": metricas.get(clave),
             **(parsear_porcentaje(metricas.get(clave)) or {})}
            for clave, nombre_metrica in METRICAS_EVALUACION
        ],
        "por_tipo": sorted(por_tipo.values(), key=lambda f: orden_tipos.get(f["tipo"], len(TIPOS))),
        "fallos_por_campo": [{"nombre": n, "cantidad": c} for n, c in fallos_por_campo.most_common()],
        "fallos_por_categoria": [
            {"nombre": n, "cantidad": len(casos), "casos": casos}
            for n, casos in sorted(fallos_por_categoria.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ],
        "modelos": [{"nombre": n, "cantidad": c} for n, c in modelos.most_common()],
        "fallos": fallos,
    }
