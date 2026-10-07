"""Persiste el resultado en Object Storage por estado y registra el historial.

El backend se elige con la variable de entorno STORAGE_BACKEND:
- local (por defecto): escribe en ./data/ con el mismo layout del bucket.
- oci: escribe en OCI Object Storage (requiere credenciales).

Cuando el documento requiere auditoría humana (`requiere_auditoria_humana = true`),
además escribe:
- `auditoria_humana/{id}/extraccion.json` con validacion, texto y legibilidad.
- `auditoria_humana/{id}/original` con el documento original.
"""
import logging
import os

from agent.nodes.common import step
from agent.state import TriageState

logger = logging.getLogger(__name__)

# Elegir el backend según STORAGE_BACKEND.
_STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

if _STORAGE_BACKEND == "oci":
    from agent.storage import object_storage as storage
else:
    from agent.storage import local as storage


_CARPETAS = {
    "Cola_Emergencia_Medica": "procesados/urgentes",
    "Farmacia_Hospitalaria": "procesados/farmacia",
    "Auditoria_Autorizaciones": "procesados/autorizaciones",
    "Historia_Clinica_Electronica": "procesados/historia_clinica",
    "Cola_Revision_Humana": "auditoria_humana",
}


def _persistir_auditoria(state: TriageState, bucket: str) -> None:
    """
    Escribe los archivos de auditoría humana si el documento lo requiere.

    Solo se llama cuando `requiere_auditoria_humana = true`. Escribe:
    - `auditoria_humana/{id}/extraccion.json` con validacion, texto y legibilidad.
    - `auditoria_humana/{id}/original` con el documento original (si existe ruta_original).
    """
    documento_id = state.get("documento_id")
    if not documento_id:
        return

    # 1. Escribir extraccion.json
    extraccion = {
        "documento_id": documento_id,
        "validacion": state.get("validacion"),
        "texto": state.get("texto"),
        "legibilidad": state.get("legibilidad"),
    }
    ruta_extraccion = f"auditoria_humana/{documento_id}/extraccion.json"
    storage.upload_json(bucket, ruta_extraccion, extraccion)
    logger.info("Persistido extraccion.json en %s", ruta_extraccion)

    # 2. Copiar el original al lado (si existe ruta_original)
    ruta_original = state.get("ruta_original")
    if ruta_original:
        try:
            contenido = storage.download(bucket, ruta_original)
            ruta_destino = f"auditoria_humana/{documento_id}/original"
            storage.upload_bytes(bucket, ruta_destino, contenido)
            logger.info("Copiado original a %s", ruta_destino)
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo copiar el original a auditoria_humana: %s", e)


def persistir(state: TriageState) -> dict:
    """
    Persiste el resultado en el backend configurado (local u OCI).

    Determina la carpeta según el destino, construye el JSON de respuesta y
    lo sube. Si el upload falla, marca status_backup='error' y registra el
    motivo en la traza. Nunca reporta 'exito' si el objeto no quedó escrito.

    Si el documento requiere auditoría humana, además escribe los archivos
    de auditoría (extraccion.json + original).
    """
    destino = state.get("decision", {}).get("destino_principal", "Cola_Revision_Humana")
    carpeta = _CARPETAS.get(destino, "auditoria_humana")
    ruta = f"{carpeta}/{state['documento_id']}.json"
    # Elegir bucket según ENV (dev/prod).
    # OCI_BUCKET (legacy) tiene prioridad si está definido.
    entorno = os.getenv("ENV", "dev").lower()
    bucket_por_entorno = f"OCI_BUCKET_{entorno.upper()}"
    bucket = os.getenv("OCI_BUCKET") or os.getenv(bucket_por_entorno, "mediflow-dev")

    payload = {
        "documento_id": state.get("documento_id"),
        "tipo_archivo": state.get("tipo_archivo"),
        "canal_origen": state.get("canal_origen"),
        "clasificacion": state.get("clasificacion"),
        "datos_extraidos": state.get("datos_extraidos"),
        "validacion": state.get("validacion"),
        "score": state.get("score"),
        "urgencia": state.get("urgencia"),
        "decision": state.get("decision"),
        "modelo_utilizado": state.get("modelo_utilizado"),
    }

    try:
        storage.upload_json(bucket, ruta, payload)
        almacenamiento = {
            "bucket": bucket,
            "ruta_objeto": ruta,
            "status_backup": "exito",
        }
        logger.info(
            "Persistido en %s: %s/%s", _STORAGE_BACKEND, bucket, ruta
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Fallo al persistir en %s (%s): %s", _STORAGE_BACKEND, ruta, e)
        almacenamiento = {
            "bucket": bucket,
            "ruta_objeto": ruta,
            "status_backup": "error",
        }

    # Si requiere auditoría humana, escribir los archivos de auditoría.
    if state.get("decision", {}).get("requiere_auditoria_humana"):
        try:
            _persistir_auditoria(state, bucket)
        except Exception as e:  # noqa: BLE001
            logger.warning("Fallo al persistir los archivos de auditoría: %s", e)

    return {
        "almacenamiento": almacenamiento,
        "trace": step(state, "persistir", almacenamiento),
    }