"""Almacenamiento local. Escribe en ./data/ con el mismo layout del bucket.

Se usa cuando STORAGE_BACKEND=local (por defecto en desarrollo). No requiere
credenciales de OCI ni conexión a internet.

Layout: ./data/{bucket}/{ruta}
Ejemplo: ./data/mediflow-documentos-clinicos/procesados/urgentes/GS-07.json
"""
import json
import os
from pathlib import Path

# Raíz del proyecto (dos niveles arriba de agent/storage/local.py)
RAIZ = Path(__file__).resolve().parent.parent.parent

# Carpeta base del almacenamiento local
DATA_DIR = RAIZ / "data"


def _ruta_absoluta(bucket: str, ruta: str) -> Path:
    """Devuelve la ruta absoluta del archivo dentro de ./data/."""
    return DATA_DIR / bucket / ruta


def namespace() -> str:
    """En local no hay namespace real. Devolvemos un placeholder."""
    return os.getenv("OCI_NAMESPACE", "local-namespace")


def upload_bytes(bucket: str, ruta: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Escribe bytes en ./data/{bucket}/{ruta}. Crea las carpetas si no existen."""
    destino = _ruta_absoluta(bucket, ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)


def upload_json(bucket: str, ruta: str, obj: dict) -> None:
    """Escribe un JSON en ./data/{bucket}/{ruta}."""
    contenido = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    upload_bytes(bucket, ruta, contenido, "application/json")


def list_prefix(bucket: str, prefijo: str) -> list[str]:
    """Lista los archivos en ./data/{bucket}/ que empiezan con el prefijo.

    Devuelve las rutas relativas al bucket (como hace OCI).
    """
    base = DATA_DIR / bucket
    if not base.exists():
        return []
    resultado = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        # Ruta relativa al bucket, con separador '/'
        relativa = path.relative_to(base).as_posix()
        if relativa.startswith(prefijo):
            resultado.append(relativa)
    return sorted(resultado)


def download(bucket: str, ruta: str) -> bytes:
    """Lee el contenido de ./data/{bucket}/{ruta}."""
    origen = _ruta_absoluta(bucket, ruta)
    if not origen.exists():
        raise FileNotFoundError(f"No existe el archivo local: {origen}")
    return origen.read_bytes()


def borrar(bucket: str, ruta: str) -> None:
    """Borra un archivo local (útil para tests y limpieza)."""
    destino = _ruta_absoluta(bucket, ruta)
    if destino.exists():
        destino.unlink()


__all__ = [
    "namespace",
    "upload_bytes",
    "upload_json",
    "list_prefix",
    "download",
    "borrar",
]