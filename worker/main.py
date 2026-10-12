"""Worker de MediFlow.

Revisa recibidos/ cada 30 segundos, procesa documentos con el grafo,
registra los resultados en SQLite y aplica reintentos ante fallos temporales.
"""
import logging
import os
import time

from agent.graph import run_triage
from agent.ingestion import IngestionError, ingest_document
from agent.storage import triage_results

from agent.storage.buckets import bucket_actual

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("worker")

INTERVALO = int(os.getenv("WORKER_INTERVALO_SEG", "30"))

_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

if _BACKEND == "oci":
    from agent.storage import object_storage as storage
elif _BACKEND == "local":
    from agent.storage import local as storage
else:
    raise ValueError(
        f"STORAGE_BACKEND no válido: {_BACKEND!r}. Usa 'local' u 'oci'."
    )


def listar_recibidos() -> list[str]:
    """Devuelve las rutas de los archivos que están en recibidos/."""
    return storage.list_prefix(bucket_actual(), "recibidos/")


def preparar_resultado_sqlite(resultado: dict) -> dict:
    """Adapta la salida del grafo al formato que espera SQLite."""
    decision = resultado["decision"]

    return {
        "documento_id": resultado["documento_id"],
        "clasificacion": resultado.get("clasificacion") or {
            "tipo_documento": "Otro",
            "nivel_prioridad": "Rutina",
            "score_confianza_clasificacion": 0.0,
        },
        "datos_extraidos": resultado.get("datos_extraidos") or {},
        "decision_enrutamiento": decision,
        "almacenamiento_oci": resultado["almacenamiento"],
        "score_confianza": resultado.get("score", 0.0),
        "modelo_utilizado": resultado.get("modelo_utilizado"),
        "trace": resultado.get("trace", []),
    }


def procesar_archivo(ruta: str) -> None:
    """Procesa un archivo recibido y registra su resultado en SQLite."""
    bucket = bucket_actual()
    contenido = storage.download(bucket, ruta)
    nombre = ruta.rsplit("/", 1)[-1]

    documento_id = nombre.rsplit(".", 1)[0]

    documento = ingest_document(
        contenido,
        filename=nombre,
    )

    resultado = run_triage(
        documento_id,
        documento.tipo_archivo,
        documento.texto,
        "worker",
        imagenes=documento.imagenes,
        legibilidad=documento.legibilidad,
        ruta_original=ruta,
    )

    almacenamiento = resultado.get("almacenamiento") or {}
    if almacenamiento.get("status_backup") != "exito":
        raise RuntimeError(
            f"No se confirmó la persistencia del documento {documento_id}"
        )

    resultado_sqlite = preparar_resultado_sqlite(resultado)
    triage_results.guardar_resultado(resultado_sqlite)

    log.info("Documento procesado y registrado en SQLite: %s", documento_id)


def procesar_pendientes() -> None:
    """Procesa los archivos recibidos, con reintentos ante fallos temporales."""
    archivos = listar_recibidos()

    if not archivos:
        log.info("No hay archivos en recibidos/")
        return

    log.info("Archivos encontrados en recibidos/: %d", len(archivos))

    for ruta in archivos:
        nombre = ruta.rsplit("/", 1)[-1]
        documento_id = nombre.rsplit(".", 1)[0]

        if triage_results.obtener_resultado(documento_id) is not None:
            log.info("Documento ya registrado en SQLite; se omite: %s", documento_id)
            continue

        for intento in range(1, 4):
            try:
                procesar_archivo(ruta)
                break
            except IngestionError as exc:
                log.error("Archivo no válido: %s. Motivo: %s", ruta, exc)
                break
            except Exception:
                log.exception(
                    "Fallo al procesar %s (intento %d de 3)",
                    ruta,
                    intento,
                )

                if intento < 3:
                    espera = 2 ** intento
                    log.info("Nuevo intento en %d segundos", espera)
                    time.sleep(espera)
                else:
                    log.error(
                        "Se agotaron los intentos para %s; "
                        "se conservará para el siguiente ciclo",
                        ruta,
                    )


def reporte_diario() -> None:
    # Sprint 3: implementación del reporte diario.
    log.info("Reporte diario pendiente de implementación")


if __name__ == "__main__":
    log.info("Worker iniciado; intervalo=%s segundos", INTERVALO)

    while True:
        try:
            procesar_pendientes()
        except Exception:
            log.exception("Fallo al revisar recibidos/")

        time.sleep(INTERVALO)
