"""Archivos del ciclo de auditoría. Las escrituras repetidas son idempotentes."""

from agent.nodes.notificar import notificar
from agent.nodes.persistir import persistir, storage
from agent.storage import local, local_audit
from agent.storage.buckets import bucket_actual
from agent.storage.identificadores import validar_id


def carpeta(documento_id):
    return local.DATA_DIR / bucket_actual() / "auditoria_humana" / validar_id(documento_id)


def extraccion(state):
    return local_audit.snapshot_revision(state)


def preparar_revision(state):
    documento_id = state["documento_id"]
    local_audit.guardar_extraccion(documento_id, extraccion(state))
    if state.get("texto") and state.get("tipo_archivo") in {"TEXTO", "JSON"}:
        # Texto de entrada, nunca un reemplazo del PDF o imagen original.
        local_audit.escribir_archivo(documento_id, "original.txt", state["texto"].encode("utf-8"))
    return {"revision_version": state.get("revision_version", 1),
            "alerta_emitida": bool(state.get("decision", {}).get("notificacion_generada"))}


def cerrar_revision(state):
    documento_id = state["documento_id"]
    resolucion = dict(state["resolucion_humana"])
    resolucion["fecha"] = state["fecha_revision"]
    bucket = bucket_actual()
    if state.get("rechazado"):
        ruta = f"rechazados/{state['documento_id']}.json"
        storage.upload_json(bucket, ruta, {**extraccion(state), "status": "rechazado", "resolucion": resolucion})
        cambios = {"almacenamiento": {"bucket": bucket, "ruta_objeto": ruta, "status_backup": "exito"}}
    else:
        cambios = persistir(state)
        if cambios["almacenamiento"]["status_backup"] != "exito":
            raise OSError("No se pudo persistir la revisión")
        if state["decision"].get("notificacion_generada") and not state.get("alerta_emitida"):
            cambios.update(notificar(state))
            cambios["alerta_emitida"] = True
    repetida = not state.get("rechazado") and state["decision"].get("requiere_auditoria_humana")
    if repetida:
        numero = state["revision_version"] - 1
        local_audit.escribir_json(documento_id, f"resolucion_{numero}.json", resolucion)
        local_audit.guardar_extraccion(documento_id, extraccion(state))
    else:
        local_audit.escribir_json(documento_id, "resolucion.json", resolucion)
    return cambios
