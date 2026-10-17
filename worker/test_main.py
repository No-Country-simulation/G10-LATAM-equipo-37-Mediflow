
"""Tests del procesamiento de documentos del worker."""

from agent.storage import local as almacenamiento_local
from worker import main as worker


def preparar_worker(monkeypatch, ruta, resultado_sqlite=None):
    """Prepara dependencias simuladas para probar el worker."""
    procesados = []
    movimientos = []

    monkeypatch.setattr(worker, "listar_recibidos", lambda: [ruta])
    monkeypatch.setattr(
        worker.triage_results,
        "obtener_resultado",
        lambda documento_id: resultado_sqlite,
    )
    monkeypatch.setattr(
        worker,
        "procesar_archivo",
        lambda ruta: procesados.append(ruta),
    )
    monkeypatch.setattr(
        worker,
        "mover_archivo",
        lambda ruta, destino: movimientos.append((ruta, destino)),
    )

    return procesados, movimientos


def test_procesar_pendientes_mueve_archivo_valido(monkeypatch):
    """Procesa un archivo válido y lo mueve a procesados."""
    ruta = "recibidos/DOC-001.txt"
    procesados, movimientos = preparar_worker(monkeypatch, ruta)

    worker.procesar_pendientes()

    assert procesados == [ruta]
    assert movimientos == [(ruta, "procesados/entrada")]


def test_procesar_pendientes_mueve_documento_ya_registrado(monkeypatch):
    """Mueve un documento registrado sin procesarlo de nuevo."""
    ruta = "recibidos/DOC-002.txt"
    procesados, movimientos = preparar_worker(
        monkeypatch,
        ruta,
        resultado_sqlite={"documento_id": "DOC-002"},
    )

    worker.procesar_pendientes()

    assert procesados == []
    assert movimientos == [(ruta, "procesados/entrada")]


def test_procesar_pendientes_rechaza_error_de_ingestion(monkeypatch):
    """Mueve a rechazados un archivo que no se puede ingerir."""
    ruta = "recibidos/DOC-003.txt"
    procesados, movimientos = preparar_worker(monkeypatch, ruta)

    def archivo_invalido(ruta):
        procesados.append(ruta)
        raise worker.IngestionError("Documento inválido")

    monkeypatch.setattr(worker, "procesar_archivo", archivo_invalido)

    worker.procesar_pendientes()

    assert procesados == [ruta]
    assert movimientos == [(ruta, "rechazados")]


def test_procesar_pendientes_rechaza_tras_tres_intentos(monkeypatch):
    """Mueve a rechazados un archivo tras tres fallos."""
    ruta = "recibidos/DOC-004.txt"
    procesados, movimientos = preparar_worker(monkeypatch, ruta)

    def archivo_con_error(ruta):
        procesados.append(ruta)
        raise RuntimeError("Fallo temporal")

    monkeypatch.setattr(worker, "procesar_archivo", archivo_con_error)
    monkeypatch.setattr(worker.time, "sleep", lambda segundos: None)

    worker.procesar_pendientes()

    assert procesados == [ruta, ruta, ruta]
    assert movimientos == [(ruta, "rechazados")]


def test_mover_archivo_mueve_realmente_el_archivo(monkeypatch, tmp_path):
    """Mueve el archivo real del almacenamiento local al destino."""
    monkeypatch.setattr(worker, "storage", almacenamiento_local)
    monkeypatch.setattr(almacenamiento_local, "DATA_DIR", tmp_path)
    monkeypatch.setattr(worker, "bucket_actual", lambda: "bucket-test")

    origen = tmp_path / "bucket-test" / "recibidos" / "DOC-101.txt"
    origen.parent.mkdir(parents=True)
    origen.write_bytes(b"documento de prueba")

    worker.mover_archivo("recibidos/DOC-101.txt", "procesados/entrada")

    destino = (
        tmp_path / "bucket-test" / "procesados" / "entrada" / "DOC-101.txt"
    )
    assert destino.exists()
    assert destino.read_bytes() == b"documento de prueba"
    assert not origen.exists()


def test_mover_archivo_conserva_origen_si_falla_la_copia(
    monkeypatch, tmp_path
):
    """No elimina el original si falla la escritura en el destino."""
    monkeypatch.setattr(worker, "storage", almacenamiento_local)
    monkeypatch.setattr(almacenamiento_local, "DATA_DIR", tmp_path)
    monkeypatch.setattr(worker, "bucket_actual", lambda: "bucket-test")

    origen = tmp_path / "bucket-test" / "recibidos" / "DOC-102.txt"
    origen.parent.mkdir(parents=True)
    origen.write_bytes(b"documento de prueba")

    def fallar_escritura(*args, **kwargs):
        raise OSError("Fallo simulado al escribir")

    monkeypatch.setattr(almacenamiento_local, "upload_bytes", fallar_escritura)

    try:
        worker.mover_archivo("recibidos/DOC-102.txt", "procesados/entrada")
        raise AssertionError("Se esperaba un error de escritura")
    except OSError as exc:
        assert str(exc) == "Fallo simulado al escribir"

    assert origen.exists()
    assert origen.read_bytes() == b"documento de prueba"


def test_archivo_invalido_se_mueve_realmente_a_rechazados(
    monkeypatch, tmp_path
):
    """Mueve un documento inválido y elimina su ubicación original."""
    monkeypatch.setattr(worker, "storage", almacenamiento_local)
    monkeypatch.setattr(almacenamiento_local, "DATA_DIR", tmp_path)
    monkeypatch.setattr(worker, "bucket_actual", lambda: "bucket-test")
    monkeypatch.setattr(worker, "listar_recibidos", lambda: [
        "recibidos/DOC-103.txt"
    ])
    monkeypatch.setattr(
        worker.triage_results,
        "obtener_resultado",
        lambda documento_id: None,
    )

    def archivo_invalido(ruta):
        raise worker.IngestionError("Documento inválido")

    monkeypatch.setattr(worker, "procesar_archivo", archivo_invalido)

    origen = tmp_path / "bucket-test" / "recibidos" / "DOC-103.txt"
    origen.parent.mkdir(parents=True)
    origen.write_bytes(b"documento invalido")

    worker.procesar_pendientes()

    destino = tmp_path / "bucket-test" / "rechazados" / "DOC-103.txt"
    assert destino.exists()
    assert destino.read_bytes() == b"documento invalido"
    assert not origen.exists()
