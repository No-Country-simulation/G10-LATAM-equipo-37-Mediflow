"""Respaldo consistente de SQLite y objetos privados; restauración local aislada.

Ejecutar como módulo. No restaura sobre datos existentes ni incluye secretos.
El ZIP contiene datos operativos: conservarlo en almacenamiento privado.
"""
import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from agent.storage import local
from agent.storage.backend import storage
from agent.storage.buckets import bucket_actual


def _ruta_segura(nombre):
    ruta = PurePosixPath(nombre)
    if ruta.is_absolute() or not ruta.parts or any(p in {".", ".."} for p in ruta.parts):
        raise ValueError("Ruta de respaldo inválida")
    if "\\" in nombre or ":" in nombre or any(ord(c) < 32 for c in nombre):
        raise ValueError("Ruta de respaldo inválida")
    return ruta


def crear(destino: Path, subir=False):
    """Bloquea escritores del runtime mientras captura DB y objetos del bucket."""
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError("El respaldo ya existe")
    db = Path(os.getenv("MEDIFLOW_CHECKPOINT_DB", str(local.DATA_DIR / "checkpoints.sqlite3")))
    if not db.is_file():
        raise FileNotFoundError("No existe la base de checkpoints")
    bucket = bucket_actual()
    _ruta_segura(bucket)
    # Evita respaldarse a sí mismo cuando el backend es local.
    if destino.resolve().is_relative_to((local.DATA_DIR / bucket).resolve()):
        raise ValueError("El respaldo debe guardarse fuera del bucket local")
    destino.parent.mkdir(parents=True, exist_ok=True)
    manifiesto = {"version": 1, "bucket": bucket, "fecha": datetime.now(timezone.utc).isoformat(), "archivos": {}}
    with TemporaryDirectory(dir=destino.parent) as temporal:
        raiz = Path(temporal)
        with closing(sqlite3.connect(str(db) + ".lock", timeout=30)) as lock:
            lock.execute("CREATE TABLE IF NOT EXISTS mutex (id INTEGER PRIMARY KEY)")
            lock.commit()
            lock.execute("BEGIN IMMEDIATE")
            try:
                with (closing(sqlite3.connect(db)) as origen,
                      closing(sqlite3.connect(raiz / "checkpoints.sqlite3")) as copia):
                    origen.backup(copia)
                with ZipFile(raiz / "respaldo.zip", "w", ZIP_DEFLATED) as archivo:
                    def agregar(nombre, contenido):
                        archivo.writestr(nombre, contenido)
                        manifiesto["archivos"][nombre] = hashlib.sha256(contenido).hexdigest()

                    agregar("checkpoints.sqlite3", (raiz / "checkpoints.sqlite3").read_bytes())
                    for clave in storage.list_prefix(bucket, ""):
                        if clave.startswith("respaldos/"):
                            continue
                        _ruta_segura(clave)
                        agregar(f"objetos/{clave}", storage.download(bucket, clave))
                    archivo.writestr("manifest.json", json.dumps(manifiesto, ensure_ascii=False))
            finally:
                lock.rollback()
        # Publicar solo el archivo completamente construido.
        with destino.open("xb") as salida:
            salida.write((raiz / "respaldo.zip").read_bytes())
    if subir:
        storage.upload_bytes(bucket, f"respaldos/{destino.name}", destino.read_bytes(), content_type="application/zip")
    return manifiesto


def restaurar(origen: Path, destino: Path):
    """Valida todo antes de escribir; restaura en un directorio nuevo."""
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError("La restauración exige un directorio nuevo")
    with ZipFile(origen) as archivo:
        manifiesto = json.loads(archivo.read("manifest.json"))
        bucket = manifiesto["bucket"]
        if manifiesto.get("version") != 1 or len(_ruta_segura(bucket).parts) != 1:
            raise ValueError("Formato de respaldo inválido")
        entradas = manifiesto["archivos"]
        if "checkpoints.sqlite3" not in entradas:
            raise ValueError("Falta SQLite")
        if set(archivo.namelist()) != set(entradas) | {"manifest.json"}:
            raise ValueError("El inventario del respaldo no coincide")
        for nombre, digest in entradas.items():
            _ruta_segura(nombre)
            if nombre != "checkpoints.sqlite3" and not nombre.startswith("objetos/"):
                raise ValueError("Entrada no permitida")
            if hashlib.sha256(archivo.read(nombre)).hexdigest() != digest:
                raise ValueError("El respaldo está alterado")
        destino.mkdir(parents=True, exist_ok=False)
        for nombre in entradas:
            ruta = (destino / nombre if nombre == "checkpoints.sqlite3" else
                    destino / bucket / nombre.removeprefix("objetos/"))
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(archivo.read(nombre))
    with closing(sqlite3.connect(destino / "checkpoints.sqlite3")) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite no supera la validación de integridad")
    return manifiesto


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    acciones = parser.add_subparsers(dest="accion", required=True)
    crear_parser = acciones.add_parser("crear")
    crear_parser.add_argument("--destino", type=Path, required=True)
    crear_parser.add_argument("--subir", action="store_true",
                              help="Sube al prefijo privado respaldos/ del bucket actual")
    restaurar_parser = acciones.add_parser("restaurar")
    restaurar_parser.add_argument("--origen", type=Path, required=True)
    restaurar_parser.add_argument("--destino", type=Path, required=True)
    args = parser.parse_args()
    if args.accion == "crear":
        resultado = crear(args.destino, args.subir)
    else:
        resultado = restaurar(args.origen, args.destino)
    print(json.dumps({"status": "ok", "archivos": len(resultado["archivos"]), "fecha": resultado["fecha"]}))


if __name__ == "__main__":
    main()
