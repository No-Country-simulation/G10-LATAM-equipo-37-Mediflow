"""Persiste el resultado en Object Storage por estado y registra el historial.

El backend se elige con la variable de entorno STORAGE_BACKEND:
- local (por defecto): escribe en ./data/ con el mismo layout del bucket.
- oci: escribe en OCI Object Storage (requiere credenciales).
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


def persistir(state: TriageState) -> dict:
    """
    Persiste el resultado en el backend configurado (local u OCI).

    Determina la carpeta según el destino, construye el JSON de respuesta y
    lo sube. Si el upload falla, marca status_backup='error' y registra el
    motivo en la traza. Nunca reporta 'exito' si el objeto no quedó escrito.
    """
    destino = state.get("decision", {}).get("destino_principal", "Cola_Revision_Humana")
    carpeta = _CARPETAS.get(destino, "auditoria_humana")
    ruta = f"{carpeta}/{state['documento_id']}.json"
    bucket = os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos")

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

    return {
        "almacenamiento": almacenamiento,
        "trace": step(state, "persistir", almacenamiento),
    }