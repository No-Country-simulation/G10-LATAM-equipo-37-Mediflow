"""Selección del bucket de OCI según el entorno.

Este módulo es el ÚNICO lugar que decide el bucket.
Lo usan:
- agent/nodes/persistir.py (para escribir)
- agent/storage/local_audit.py (para leer la cola de revisión)

Reglas:
- Se usa OCI_BUCKET_<ENV> (ej: OCI_BUCKET_DEV, OCI_BUCKET_PROD).
- Si ENV no es "dev" ni "prod", lanza ValueError.
"""
import os

_ENTORNOS_VALIDOS = {"dev", "prod"}


def bucket_actual() -> str:
    """
    Devuelve el bucket de OCI según ENV.

    Ejemplos:
        ENV=dev, OCI_BUCKET_DEV=mediflow-dev   → "mediflow-dev"
        ENV=prod, OCI_BUCKET_PROD=mediflow-prod → "mediflow-prod"
        ENV=otro                                → ValueError
    """
    entorno = os.getenv("ENV", "dev").lower()
    if entorno not in _ENTORNOS_VALIDOS:
        raise ValueError(
            f"ENV='{entorno}' no es válido. Valores permitidos: {sorted(_ENTORNOS_VALIDOS)}"
        )
    bucket_por_entorno = f"OCI_BUCKET_{entorno.upper()}"
    default = f"mediflow-{entorno}"
    return os.getenv(bucket_por_entorno, default)