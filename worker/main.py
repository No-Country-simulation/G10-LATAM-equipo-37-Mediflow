"""Worker de MediFlow.

1. Cada 30 segundos lista recibidos/ en el bucket y procesa lo nuevo con el grafo.
2. Reintentos con backoff cuando el proveedor de modelos falla; el documento queda en cola "pendiente".
3. A las 07:00 genera el reporte diario para el gestor.
"""
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

INTERVALO = int(os.getenv("WORKER_INTERVALO_SEG", "30"))


def procesar_pendientes() -> None:
    # TODO sprint 2: list_prefix(bucket, "recibidos/"), descargar, run_triage, mover a la carpeta destino.
    log.info("revisando recibidos/ (pendiente de implementar)")


def reporte_diario() -> None:
    # TODO sprint 3: KPIs desde ADB, narrativa con el LLM, envío por OCI Notifications, guardar en reportes/.
    log.info("reporte diario (pendiente de implementar)")


if __name__ == "__main__":
    log.info("worker iniciado")
    while True:
        try:
            procesar_pendientes()
        except Exception as e:  # noqa: BLE001
            log.exception("fallo en el ciclo: %s", e)
        time.sleep(INTERVALO)
