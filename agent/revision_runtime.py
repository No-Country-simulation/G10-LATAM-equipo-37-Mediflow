"""Ejecución durable N2-05. SQLite en volumen local; sin credenciales cloud."""
import hashlib
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent.nodes.revision_humana import aplicar_decision
from agent.storage import local
from agent.storage.checkpoint_payload import PayloadSerializer
from agent.storage.revision import carpeta


class RevisionNoExiste(Exception):
    pass


class RevisionConflicto(Exception):
    pass


@contextmanager
def sesion(documento_id):
    carpeta(documento_id)  # validar antes de abrir archivos
    ruta = Path(os.getenv("MEDIFLOW_CHECKPOINT_DB", str(local.DATA_DIR / "checkpoints.sqlite3")))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Un bloqueo SQLite entre procesos evita dos ejecuciones simultáneas del mismo estado.
    # MVP: serializa también otros documentos. Escalar requiere una cola/locks por documento.
    with closing(sqlite3.connect(str(ruta) + ".lock", timeout=30)) as lock:
        lock.execute("CREATE TABLE IF NOT EXISTS mutex (id INTEGER PRIMARY KEY)")
        lock.commit()
        lock.execute("BEGIN IMMEDIATE")
        try:
            with closing(sqlite3.connect(str(ruta), check_same_thread=False)) as conn:
                saver = SqliteSaver(conn, serde=PayloadSerializer())
                from agent.graph import build_graph
                yield build_graph(checkpointer=saver), {"configurable": {"thread_id": documento_id}}
        finally:
            lock.rollback()


def ejecutar(estado):
    with sesion(estado["documento_id"]) as (grafo, config):
        existente = grafo.get_state(config)
        if existente.values:
            if existente.next and "revision_humana" not in existente.next:
                return grafo.invoke(None, config)
            return dict(existente.values)
        return grafo.invoke(estado, config)


def reanudar(documento_id, decision):
    with sesion(documento_id) as (grafo, config):
        snapshot = grafo.get_state(config)
        if not snapshot.values:
            raise RevisionNoExiste("Documento sin checkpoint; requiere reprocesamiento")
        estado = dict(snapshot.values)
        if not snapshot.next:
            raise RevisionConflicto("La revisión ya terminó")
        digest = hashlib.sha256(json.dumps(decision, sort_keys=True).encode()).hexdigest()
        # Una operación que falló después del interrupt se retoma sin volver a aplicar la decisión.
        if "cerrar_revision" in snapshot.next:
            if estado.get("decision_digest") != digest:
                raise RevisionConflicto("Hay una decisión pendiente de persistir")
            resultado = grafo.invoke(None, config)
        else:
            if "revision_humana" not in snapshot.next:
                raise RevisionConflicto("El documento no está esperando una revisión")
            if estado.get("decision_digest") == digest:
                raise RevisionConflicto("Decisión repetida; actualice la cola y la versión")
            if decision.get("revision_version") not in (None, estado.get("revision_version", 1)):
                raise RevisionConflicto("La revisión cambió; vuelva a cargar la cola")
            aplicar_decision(estado, decision)  # validar antes de consumir el interrupt
            grafo.update_state(config, {"fecha_revision": datetime.now(timezone.utc).isoformat(),
                                       "decision_digest": digest})
            resultado = grafo.invoke(Command(resume=decision), config)
        resolucion = dict(resultado["resolucion_humana"])
        resolucion["fecha"] = resultado["fecha_revision"]
        return {"documento_id": documento_id, "resolucion": resolucion,
                "status": "rechazado" if resultado.get("rechazado") else
                    ("revision_humana" if resultado["decision"].get("requiere_auditoria_humana") else "procesado"),
                "decision_enrutamiento": None if resultado.get("rechazado") else resultado["decision"],
                "revision_version": resultado.get("revision_version", 1)}
