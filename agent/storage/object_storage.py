"""Acceso a OCI Object Storage. Plan B: Fallback local forzado para la VM."""
import json
import os

# Directorio local para guardar los archivos en la VM
LOCAL_STORAGE_DIR = "/app/data/storage_fallback"

def _client():
    # Forzamos a que no use OCI para evitar el error 401 de Instance Principal
    return None

def namespace() -> str:
    return "local"

def upload_bytes(bucket: str, ruta: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    filepath = os.path.join(LOCAL_STORAGE_DIR, bucket, ruta)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"FALLBACK: Guardado localmente en {filepath}")

def upload_json(bucket: str, ruta: str, obj: dict) -> None:
    upload_bytes(bucket, ruta, json.dumps(obj, ensure_ascii=False, indent=2).encode(), "application/json")

def list_prefix(bucket: str, prefijo: str) -> list[str]:
    resultados = []
    prefix_dir = os.path.join(LOCAL_STORAGE_DIR, bucket)
    if os.path.exists(prefix_dir):
        for root, _dirs, files in os.walk(prefix_dir):
            for file in files:
                ruta = os.path.join(root, file).replace(prefix_dir + "/", "")
                if ruta.startswith(prefijo):
                    resultados.append(ruta)
    return resultados

def download(bucket: str, ruta: str) -> bytes:
    filepath = os.path.join(LOCAL_STORAGE_DIR, bucket, ruta)
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return f.read()
    raise FileNotFoundError(f"No se encontró el archivo {ruta} en {bucket}")

def borrar(bucket: str, ruta: str) -> None:
    filepath = os.path.join(LOCAL_STORAGE_DIR, bucket, ruta)
    if os.path.exists(filepath):
        os.remove(filepath)
