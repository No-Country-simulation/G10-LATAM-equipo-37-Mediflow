import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from agent.revision_runtime import ejecutar, reanudar
from agent.storage import local, respaldo
from agent.tests.test_revision_humana import decision, estado
from agent.tests.test_revision_humana import entorno as entorno_base  # noqa: F401


@pytest.fixture
def entorno(entorno_base):  # noqa: F811 - fixture compartida de pytest
    return entorno_base


def test_respaldo_restaura_y_reanuda(entorno, monkeypatch):
    ejecutar(estado())
    archivo = entorno / "backup.zip"
    manifiesto = respaldo.crear(archivo)
    assert "checkpoints.sqlite3" in manifiesto["archivos"]
    assert any(n.startswith("objetos/checkpoints/") for n in manifiesto["archivos"])
    nuevo = entorno / "recuperado"
    respaldo.restaurar(archivo, nuevo)
    monkeypatch.setattr(local, "DATA_DIR", nuevo)
    monkeypatch.setenv("MEDIFLOW_CHECKPOINT_DB", str(nuevo / "checkpoints.sqlite3"))
    assert reanudar("N205", decision("rechazar"))["status"] == "rechazado"
    assert (nuevo / "pruebas/rechazados/N205.json").exists()
    assert not (entorno / "pruebas/rechazados/N205.json").exists()


def test_no_sobrescribe_ni_se_incluye_a_si_mismo(entorno):
    ejecutar(estado())
    with pytest.raises(ValueError):
        respaldo.crear(entorno / "pruebas/backup.zip")
    archivo = entorno / "backup.zip"
    respaldo.crear(archivo)
    with pytest.raises(FileExistsError):
        respaldo.crear(archivo)
    with pytest.raises(FileExistsError):
        respaldo.restaurar(archivo, entorno)


@pytest.mark.parametrize("alteracion", ["contenido", "ruta"])
def test_rechaza_respaldo_alterado_antes_de_escribir(entorno, alteracion):
    ejecutar(estado())
    archivo = entorno / "backup.zip"
    respaldo.crear(archivo)
    manipulado = entorno / "alterado.zip"
    with ZipFile(archivo) as src, ZipFile(manipulado, "w", ZIP_DEFLATED) as dst:
        for nombre in src.namelist():
            contenido = src.read(nombre)
            if alteracion == "contenido" and nombre == "checkpoints.sqlite3":
                contenido = b"alterado"
            if alteracion == "ruta" and nombre == "manifest.json":
                datos = json.loads(contenido)
                datos["bucket"] = "../escape"
                contenido = json.dumps(datos).encode()
            dst.writestr(nombre, contenido)
    destino = entorno / "nuevo"
    with pytest.raises(ValueError):
        respaldo.restaurar(manipulado, destino)
    assert not destino.exists()
