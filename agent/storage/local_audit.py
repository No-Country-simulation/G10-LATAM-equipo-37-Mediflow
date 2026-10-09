"""Cola de auditoría sobre el mismo backend y bucket que el grafo.

Se conserva el nombre del módulo y el parámetro base para los consumidores locales.
Sin base explícita, STORAGE_BACKEND y bucket_actual gobiernan todas las operaciones.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent.storage import local
from agent.storage.backend import storage
from agent.storage.buckets import bucket_actual
from agent.storage.identificadores import validar_id

BUCKET = bucket_actual()
DATA_DIR = local.DATA_DIR / BUCKET / "auditoria_humana"
_DEFAULT_DATA_DIR = DATA_DIR
ACCIONES_VALIDAS = {"aprobar", "corregir", "rechazar"}


class ErrorAuditoria(Exception):
    """Error base de auditoría."""


class DocumentoNoEncontrado(ErrorAuditoria):
    """El documento no está en la cola."""


class AccionInvalida(ErrorAuditoria):
    """La acción no está permitida."""


class ResolucionYaExiste(ErrorAuditoria):
    """El documento ya fue resuelto."""


class OriginalNoDisponible(ErrorAuditoria):
    """No hay original guardado."""


def _base(base=None):
    if base is not None:
        return Path(base)
    return DATA_DIR if DATA_DIR != _DEFAULT_DATA_DIR else None


def _clave(documento_id, archivo):
    return f"auditoria_humana/{validar_id(documento_id)}/{archivo}"


def _dir_documento(documento_id, base=None):
    raiz = _base(base)
    if raiz is None:
        raiz = local.DATA_DIR / bucket_actual() / "auditoria_humana"
    return raiz / validar_id(documento_id)


def leer_archivo(documento_id, archivo, base=None):
    if _base(base) is not None:
        return (_dir_documento(documento_id, base) / archivo).read_bytes()
    return storage.download(bucket_actual(), _clave(documento_id, archivo))


def escribir_archivo(documento_id, archivo, contenido, base=None):
    if _base(base) is not None or storage is local:
        destino = _dir_documento(documento_id, base) / archivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + f".{uuid4().hex}.tmp")
        temporal.write_bytes(contenido)
        temporal.replace(destino)
    else:
        storage.upload_bytes(bucket_actual(), _clave(documento_id, archivo), contenido)


def escribir_json(documento_id, archivo, contenido, base=None):
    escribir_archivo(documento_id, archivo,
                     json.dumps(contenido, ensure_ascii=False, indent=2).encode("utf-8"), base)


def _archivos(base=None):
    raiz = _base(base)
    if raiz is not None:
        return {p.relative_to(raiz).as_posix() for p in raiz.glob("*/*") if p.is_file()}
    prefijo = "auditoria_humana/"
    return {p.removeprefix(prefijo) for p in storage.list_prefix(bucket_actual(), prefijo)}


def snapshot_revision(state):
    return {"documento_id": state["documento_id"],
            "clasificacion": state.get("clasificacion"),
            "datos_extraidos": state.get("datos_extraidos", {}),
            "decision_enrutamiento": state.get("decision"),
            "score_confianza": state.get("score"),
            "validacion": state.get("validacion"), "texto": state.get("texto"),
            "legibilidad": state.get("legibilidad"),
            "evidencias": state.get("evidencias", []),
            "revision_version": state.get("revision_version", 1)}


def guardar_extraccion(documento_id: str, extraccion: dict[str, Any], base=None):
    escribir_json(documento_id, "extraccion.json", extraccion, base)


def listar_cola_humana(base=None):
    archivos = _archivos(base)
    pendientes = []
    for ruta in sorted(archivos):
        partes = ruta.split("/")
        if len(partes) != 2 or partes[1] != "extraccion.json":
            continue
        documento_id = partes[0]
        if f"{documento_id}/resolucion.json" not in archivos:
            extraccion = json.loads(leer_archivo(documento_id, "extraccion.json", base))
            pendientes.append({"documento_id": documento_id, "extraccion": extraccion})
    return pendientes


def guardar_resolucion(documento_id, accion, revisor, motivo, correcciones=None, base=None):
    """Compatibilidad para consumidores sin grafo; la API usa reanudar()."""
    if accion not in ACCIONES_VALIDAS:
        raise AccionInvalida("Acción inválida")
    validar_id(documento_id)
    archivos = _archivos(base)
    if f"{documento_id}/extraccion.json" not in archivos:
        raise DocumentoNoEncontrado("Documento no encontrado en la cola de revisión")
    if f"{documento_id}/resolucion.json" in archivos:
        raise ResolucionYaExiste("El documento ya tiene una resolución registrada")
    resolucion = {"revisor": revisor, "fecha": datetime.now(timezone.utc).isoformat(),
                  "accion": accion, "motivo": motivo, "correcciones": correcciones or {}}
    escribir_json(documento_id, "resolucion.json", resolucion, base)
    return resolucion


def _tipo_de_contenido(contenido):
    if contenido.startswith(b"%PDF"):
        return "application/pdf"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    try:
        contenido.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    return "text/plain; charset=utf-8"


def obtener_original(documento_id, base=None):
    try:
        validar_id(documento_id)
    except ValueError as exc:
        raise DocumentoNoEncontrado("Identificador no permitido") from exc
    archivos = _archivos(base)
    if f"{documento_id}/extraccion.json" not in archivos:
        raise DocumentoNoEncontrado("Documento no encontrado en la cola de revisión")
    nombres = ("original", "original.txt", "original.pdf", "original.png",
               "original.jpg", "original.jpeg", "original.json")
    for nombre in nombres:
        if f"{documento_id}/{nombre}" in archivos:
            contenido = leer_archivo(documento_id, nombre, base)
            return contenido, _tipo_de_contenido(contenido)
    raise OriginalNoDisponible("El documento no tiene original guardado")
