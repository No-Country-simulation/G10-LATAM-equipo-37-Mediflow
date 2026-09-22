"""Persiste el resultado en Object Storage por estado y registra el historial."""
import os

from agent.nodes.common import step
from agent.state import TriageState

_CARPETAS = {
    "Cola_Emergencia_Medica": "procesados/urgentes",
    "Farmacia_Hospitalaria": "procesados/farmacia",
    "Auditoria_Autorizaciones": "procesados/autorizaciones",
    "Historia_Clinica_Electronica": "procesados/historia_clinica",
    "Cola_Revision_Humana": "auditoria_humana",
}


def persistir(state: TriageState) -> dict:
    destino = state.get("decision", {}).get("destino_principal", "Cola_Revision_Humana")
    carpeta = _CARPETAS.get(destino, "auditoria_humana")
    ruta = f"{carpeta}/{state['documento_id']}.json"
    bucket = os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos")

    # TODO sprint 2: agent.storage.object_storage.upload_json(bucket, ruta, resultado) y
    # agent.storage.db.guardar_resultado(...). Mientras tanto, status "pendiente".
    almacenamiento = {"bucket": bucket, "ruta_objeto": ruta, "status_backup": "pendiente"}
    return {"almacenamiento": almacenamiento, "trace": step(state, "persistir", almacenamiento)}
