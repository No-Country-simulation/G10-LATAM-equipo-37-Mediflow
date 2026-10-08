"""Archivos del ciclo de auditoría. Las escrituras repetidas son idempotentes."""
import json
import os

from agent.nodes.notificar import notificar
from agent.nodes.persistir import persistir, storage
from agent.storage import local


def carpeta(documento_id):
    if (not documento_id or len(documento_id) > 128 or documento_id in {".", ".."}
            or any(c in documento_id for c in '/\\:\x00') or ".." in documento_id):
        raise ValueError("Identificador no permitido")
    return local.DATA_DIR / os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos") / "auditoria_humana" / documento_id


def _escribir(path, contenido):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    temporal.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(path)


def extraccion(state):
    return {"documento_id": state["documento_id"],
            "clasificacion": state.get("clasificacion"),
            "datos_extraidos": state.get("datos_extraidos", {}),
            "decision_enrutamiento": state.get("decision"),
            "score_confianza": state.get("score"),
            "validacion": state.get("validacion"), "texto": state.get("texto"),
            "legibilidad": state.get("legibilidad"),
            "evidencias": state.get("evidencias", []),
            "revision_version": state.get("revision_version", 1)}


def preparar_revision(state):
    destino = carpeta(state["documento_id"])
    _escribir(destino / "extraccion.json", extraccion(state))
    if not any(destino.glob("original*")) and state.get("texto"):
        # Es el texto de entrada; nunca se presenta como la imagen o el PDF original.
        if state.get("tipo_archivo") in {"TEXTO", "JSON"}:
            (destino / "original.txt").write_text(state["texto"], encoding="utf-8")
    return {"revision_version": state.get("revision_version", 1),
            "alerta_emitida": bool(state.get("decision", {}).get("notificacion_generada"))}


def cerrar_revision(state):
    destino = carpeta(state["documento_id"])
    resolucion = dict(state["resolucion_humana"])
    resolucion["fecha"] = state["fecha_revision"]
    bucket = os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos")
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
        _escribir(destino / f"resolucion_{numero}.json", resolucion)
        _escribir(destino / "extraccion.json", extraccion(state))
    else:
        _escribir(destino / "resolucion.json", resolucion)
    return cambios
