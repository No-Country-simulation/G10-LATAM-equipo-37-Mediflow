"""SQLite guarda referencias; el estado completo vive en el almacenamiento privado.

El respaldo/restauración debe conservar SQLite Y estos objetos. No usar pickle.
"""
import hashlib
import os
from threading import Lock

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agent.nodes.persistir import storage


class PayloadSerializer:
    def __init__(self):
        self.serde = JsonPlusSerializer()
        self.bucket = os.getenv("OCI_BUCKET", "mediflow-documentos-clinicos")
        self.lock = Lock()

    def dumps_typed(self, obj):
        tipo, contenido = self.serde.dumps_typed(obj)
        clave = hashlib.sha256(contenido).hexdigest()
        with self.lock:
            storage.upload_bytes(self.bucket, f"checkpoints/{clave}.bin", contenido)
        return "referencia:" + tipo, clave.encode("ascii")

    def loads_typed(self, dato):
        tipo, clave = dato
        if not tipo.startswith("referencia:"):
            raise ValueError("Checkpoint sin referencia privada")
        digest = clave.decode("ascii")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Referencia de checkpoint inválida")
        contenido = storage.download(self.bucket, f"checkpoints/{digest}.bin")
        if hashlib.sha256(contenido).hexdigest() != digest:
            raise ValueError("Checkpoint alterado")
        return self.serde.loads_typed((tipo.removeprefix("referencia:"), contenido))
