"""Almacenamiento LOCAL de la cola de revisión humana y las resoluciones del auditor.

Sigue el layout de docs/api-contract.md sección 9:
    auditoria_humana/{documento_id}/original.{ext}
    auditoria_humana/{documento_id}/extraccion.json
    auditoria_humana/{documento_id}/resolucion.json   -> revisor, fecha, motivo, correcciones

POR QUÉ EXISTE ESTE ARCHIVO (leer antes de tocarlo):
El plan original preveía `agent/storage/local.py` (paquete B-05) para el modo
STORAGE_BACKEND=local que pide el contrato ("hasta el despliegue del sprint 3, todo
el equipo trabaja con local"). Ese archivo no existe todavía en el repo. Lo que sí
existe es `agent/storage/object_storage.py` (habla con OCI real, necesita
credenciales) y `agent/storage/db.py` (habla con Oracle ADB, necesita wallet y
credenciales, y sus funciones son solo un TODO sin implementar).

Sin ninguno de los dos utilizable en desarrollo sin credenciales reales, esta capa
mínima implementa el almacenamiento local directo sobre el filesystem (./data/),
específica para la cola de auditoría, para que N2-04 sea funcional y testeable HOY.

TODO / coordinar con el equipo:
  - Cuando exista agent/storage/local.py real (B-05, dueño Carlos) o se complete
    agent/storage/db.py, este módulo debería delegar ahí en lugar de tocar el
    filesystem directamente, sin cambiar la interfaz pública (listar_cola_humana,
    guardar_resolucion, guardar_extraccion) para no romper a quien ya la use
    (la API, y en el futuro agent/nodes/revision_humana.py de Carolina).
  - `guardar_extraccion` no es parte estricta de N2-04, pero se necesita para que
    haya algo que listar en la cola durante el desarrollo/testing. El nodo real que
    debería llamarla es el que enruta a Cola_Revision_Humana (enrutar.py, Néstor) o
    persistir.py (Carlos) -- confirmar quién la invoca en producción.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.storage import local as _local

# Misma carpeta que agent/storage/local.py: ./data/{bucket}/auditoria_humana/
# El bucket tiene el mismo valor por defecto que en persistir.py.
BUCKET = os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos")
DATA_DIR = _local.DATA_DIR / BUCKET / "auditoria_humana"

ACCIONES_VALIDAS = {"aprobar", "corregir", "rechazar"}  # ADR-004: rechazar es acción, no destino


class ErrorAuditoria(Exception):
    """Error base de este módulo."""


class DocumentoNoEncontrado(ErrorAuditoria):
    """El documento no está en la cola de revisión humana."""


class AccionInvalida(ErrorAuditoria):
    """La acción no es aprobar, corregir o rechazar (ADR-004)."""


class ResolucionYaExiste(ErrorAuditoria):
    """El documento ya tiene una resolución registrada (evita doble auditoría)."""


class OriginalNoDisponible(ErrorAuditoria):
    """El documento está en la cola, pero no tiene el original guardado."""
def _dir_documento(documento_id: str, base: Path = DATA_DIR) -> Path:
    return base / documento_id


def guardar_extraccion(documento_id: str, extraccion: dict[str, Any], base: Path = DATA_DIR) -> None:
    """Escribe extraccion.json para que el documento entre a la cola de revisión."""
    d = _dir_documento(documento_id, base)
    d.mkdir(parents=True, exist_ok=True)
    (d / "extraccion.json").write_text(
        json.dumps(extraccion, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def listar_cola_humana(base: Path = DATA_DIR) -> list[dict[str, Any]]:
    """Documentos con extraccion.json pero sin resolucion.json todavía (pendientes)."""
    if not base.exists():
        return []
    pendientes = []
    for carpeta in sorted(base.iterdir()):
        if not carpeta.is_dir():
            continue
        extraccion_path = carpeta / "extraccion.json"
        resolucion_path = carpeta / "resolucion.json"
        if extraccion_path.exists() and not resolucion_path.exists():
            extraccion = json.loads(extraccion_path.read_text(encoding="utf-8"))
            pendientes.append({"documento_id": carpeta.name, "extraccion": extraccion})
    return pendientes


def guardar_resolucion(
    documento_id: str,
    accion: str,
    revisor: str,
    motivo: str,
    correcciones: dict[str, Any] | None = None,
    base: Path = DATA_DIR,
) -> dict[str, Any]:
    """Guarda la decisión del auditor. 'Listo cuando' de N2-04: queda registrado
    quién (revisor), cuándo (fecha) y por qué (motivo).
    """
    if accion not in ACCIONES_VALIDAS:
        raise AccionInvalida(f"Acción inválida: {accion!r}. Debe ser una de {sorted(ACCIONES_VALIDAS)}")

    d = _dir_documento(documento_id, base)
    extraccion_path = d / "extraccion.json"
    if not extraccion_path.exists():
        raise DocumentoNoEncontrado(f"Documento no encontrado en la cola de revisión: {documento_id}")

    resolucion_path = d / "resolucion.json"
    if resolucion_path.exists():
        raise ResolucionYaExiste(f"El documento {documento_id} ya tiene una resolución registrada")

    resolucion = {
        "revisor": revisor,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "accion": accion,
        "motivo": motivo,
        "correcciones": correcciones if accion == "corregir" else None,
    }
    resolucion_path.write_text(json.dumps(resolucion, ensure_ascii=False, indent=2), encoding="utf-8")
    return resolucion


def _tipo_de_contenido(contenido: bytes) -> str:
    """Deduce el tipo por los primeros bytes: persistir.py guarda el original sin extensión."""
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


def obtener_original(documento_id: str, base: Path = DATA_DIR) -> tuple[bytes, str]:
    """Devuelve (bytes, tipo) del documento original, para verlo junto a la extracción."""
    if documento_id in ("", ".", "..") or "/" in documento_id or "\\" in documento_id:
        raise DocumentoNoEncontrado(f"Documento no encontrado en la cola de revisión: {documento_id}")
    d = _dir_documento(documento_id, base)
    if not (d / "extraccion.json").exists():
        raise DocumentoNoEncontrado(f"Documento no encontrado en la cola de revisión: {documento_id}")
    candidatos = sorted(d.glob("original*"))  # "original" (persistir.py) u "original.{ext}" (contrato)
    if not candidatos:
        raise OriginalNoDisponible(f"El documento {documento_id} no tiene original guardado")
    contenido = candidatos[0].read_bytes()
    return contenido, _tipo_de_contenido(contenido)