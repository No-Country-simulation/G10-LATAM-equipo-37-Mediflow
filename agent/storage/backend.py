"""Backend compartido por resultados, auditoría y payloads de checkpoints."""
import os

if os.getenv("STORAGE_BACKEND", "local").lower() == "oci":
    from agent.storage import object_storage as storage
else:
    from agent.storage import local as storage

__all__ = ["storage"]
