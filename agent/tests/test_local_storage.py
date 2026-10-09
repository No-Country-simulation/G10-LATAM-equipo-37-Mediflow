"""Tests del almacenamiento local y del backend configurable.

Verifica que con STORAGE_BACKEND=local:
- Nada llega a OCI.
- Los archivos se escriben en una carpeta temporal (no en ./data/).
- La suite pasa sin credenciales.
"""
import json
import os

import pytest

# Aseguramos que los tests corran con backend local.
os.environ["STORAGE_BACKEND"] = "local"

from agent.storage import local  # noqa: E402


@pytest.fixture(autouse=True)
def usar_data_temporal(tmp_path, monkeypatch):
    """Parchea local.DATA_DIR para que use una carpeta temporal.

    Esto evita que los tests borren o modifiquen ./data/ del proyecto.
    """
    monkeypatch.setattr(local, "DATA_DIR", tmp_path)
    yield


def test_namespace_devuelve_valor():
    """namespace() devuelve un valor (placeholder en local)."""
    ns = local.namespace()
    assert ns is not None
    assert isinstance(ns, str)
    assert len(ns) > 0


def test_upload_y_download_json():
    """Subir y bajar un JSON funciona."""
    bucket = "mediflow-test"
    ruta = "recibidos/test.json"
    data = {"documento_id": "TEST-001", "score": 0.95}

    local.upload_json(bucket, ruta, data)
    contenido = local.download(bucket, ruta)
    resultado = json.loads(contenido)

    assert resultado == data


def test_upload_crea_carpetas():
    """upload_json crea las carpetas intermedias si no existen."""
    bucket = "mediflow-test"
    ruta = "procesados/urgentes/DOC-001.json"
    data = {"documento_id": "DOC-001"}

    local.upload_json(bucket, ruta, data)
    archivo = local.DATA_DIR / bucket / ruta

    assert archivo.exists()
    assert archivo.is_file()


def test_list_prefix():
    """list_prefix devuelve los archivos que empiezan con el prefijo."""
    bucket = "mediflow-test"

    local.upload_json(bucket, "recibidos/A.json", {"id": "A"})
    local.upload_json(bucket, "recibidos/B.json", {"id": "B"})
    local.upload_json(bucket, "procesados/C.json", {"id": "C"})

    recibidos = local.list_prefix(bucket, "recibidos/")
    procesados = local.list_prefix(bucket, "procesados/")

    assert sorted(recibidos) == ["recibidos/A.json", "recibidos/B.json"]
    assert procesados == ["procesados/C.json"]


def test_list_prefix_bucket_inexistente():
    """list_prefix en un bucket que no existe devuelve lista vacía."""
    resultado = local.list_prefix("bucket-que-no-existe", "cualquier/")
    assert resultado == []


def test_download_archivo_inexistente():
    """download de un archivo que no existe lanza FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        local.download("mediflow-test", "no-existe.json")


def test_borrar():
    """borrar elimina el archivo."""
    bucket = "mediflow-test"
    ruta = "recibidos/borrar.json"

    local.upload_json(bucket, ruta, {"id": "BORRAR"})
    assert local.download(bucket, ruta) is not None

    local.borrar(bucket, ruta)
    with pytest.raises(FileNotFoundError):
        local.download(bucket, ruta)


def test_persistir_escribe_en_local():
    """persistir() escribe el JSON en la carpeta temporal cuando el backend es local."""
    from agent.nodes.persistir import persistir

    state = {
        "documento_id": "TEST-LOCAL-001",
        "tipo_archivo": "TEXTO",
        "canal_origen": "test",
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "datos_extraidos": {"paciente": {"nombre": "Test"}},
        "decision": {"destino_principal": "Farmacia_Hospitalaria"},
        "score": 0.95,
        "modelo_utilizado": "stub",
    }

    resultado = persistir(state)

    assert resultado["almacenamiento"]["status_backup"] == "exito"
    ruta = resultado["almacenamiento"]["ruta_objeto"]
    assert ruta == "procesados/farmacia/TEST-LOCAL-001.json"

    # Verificar que el archivo existe en la carpeta temporal (no en ./data/)
    archivo = local.DATA_DIR / resultado["almacenamiento"]["bucket"] / ruta
    assert archivo.exists()

    # Verificar el contenido
    contenido = json.loads(archivo.read_text(encoding="utf-8"))
    assert contenido["documento_id"] == "TEST-LOCAL-001"
    assert contenido["clasificacion"]["tipo_documento"] == "Receta Medica"


def test_persistir_no_toca_oci(monkeypatch):
    """Con STORAGE_BACKEND=local, persistir NO importa object_storage."""
    import sys
    # Limpiar módulos ya importados
    for mod in list(sys.modules.keys()):
        if "object_storage" in mod or "persistir" in mod:
            del sys.modules[mod]

    # Forzar backend local
    monkeypatch.setenv("STORAGE_BACKEND", "local")

    # Importar persistir después de setear la variable
    import importlib  # noqa: E402

    import agent.nodes.persistir as mod  # noqa: E402

    importlib.reload(mod)

    # Verificar que _STORAGE_BACKEND es local
    assert mod._STORAGE_BACKEND == "local"

    # Verificar que el módulo de storage es local, no object_storage
    assert mod.storage.__name__ == "agent.storage.local"
