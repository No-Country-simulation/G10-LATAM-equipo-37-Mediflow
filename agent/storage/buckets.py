"""Selección del bucket de OCI según el entorno.

Este módulo es el ÚNICO lugar que decide el bucket.
Lo usan:
- agent/nodes/persistir.py (para escribir)
- agent/storage/local_audit.py (para leer la cola de revisión)

Reglas:
- OCI_BUCKET (legacy) tiene prioridad si está definido.
- Si no, se usa OCI_BUCKET_<ENV> (ej: OCI_BUCKET_DEV, OCI_BUCKET_PROD).
- Default: mediflow-dev.
"""
import os


def bucket_actual() -> str:
    """
    Devuelve el bucket de OCI según ENV.

    Ejemplos:
        ENV=dev, OCI_BUCKET_DEV=mediflow-dev   → "mediflow-dev"
        ENV=prod, OCI_BUCKET_PROD=mediflow-prod → "mediflow-prod"
        OCI_BUCKET=mediflow-legacy             → "mediflow-legacy" (legacy gana)
        (sin variables)                        → "mediflow-dev"
    """
    entorno = os.getenv("ENV", "dev").lower()
    bucket_por_entorno = f"OCI_BUCKET_{entorno.upper()}"
    return os.getenv("OCI_BUCKET") or os.getenv(bucket_por_entorno, "mediflow-dev")