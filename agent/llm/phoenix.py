"""Inicialización de Arize Phoenix / OpenInference para MediFlow.

Este módulo configura la instrumentación automática de trazas para llamadas a LLM
a través de LiteLLM (que usa la API compatible con OpenAI de OpenRouter).

Uso:
    from agent.llm.phoenix import init_phoenix, shutdown_phoenix
    
    # En api/main.py y worker/main.py al inicio:
    init_phoenix()
    # ... app lifecycle ...
    shutdown_phoenix()

Variables de entorno:
    PHOENIX_ENABLED=true|false (default: false - opt-in explícito)
    PHOENIX_PORT=6006 (default)
    PHOENIX_HOST=127.0.0.1 (default loopback, NO 0.0.0.0)
    PHOENIX_WORKING_DIR=./phoenix_data (default)
"""
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Estado global para evitar inicialización múltiple
_phoenix_initialized = False
_phoenix_app = None


def _phoenix_enabled() -> bool:
    """Verifica si Phoenix debe activarse (opt-in explícito)."""
    forced = os.getenv("PHOENIX_ENABLED", "").lower()
    if forced in ("true", "1", "yes"):
        return True
    if forced in ("false", "0", "no", ""):
        return False
    return False


def _is_dev_environment() -> bool:
    """Determina si estamos en entorno de desarrollo (solo para logging)."""
    env = os.getenv("ENV", "prod").lower()
    return env in ("dev", "development", "local")


def init_phoenix(
    host: str | None = None,
    port: int | None = None,
    working_dir: str | None = None,
) -> bool:
    """
    Inicializa el servidor Phoenix e instrumentación OpenInference.
    
    Args:
        host: Host donde escuchar (default: PHOENIX_HOST o 127.0.0.1 loopback)
        port: Puerto (default: PHOENIX_PORT o 6006)
        working_dir: Directorio de datos (default: PHOENIX_WORKING_DIR o ./phoenix_data)
    
    Returns:
        True si se inicializó correctamente, False si ya estaba inicializado
        o si está desactivado.
    """
    global _phoenix_initialized, _phoenix_app

    if _phoenix_initialized:
        logger.debug("Phoenix ya inicializado, omitiendo.")
        return False

    if not _phoenix_enabled():
        logger.info("Phoenix desactivado (opt-in: PHOENIX_ENABLED no es 'true').")
        return False

    try:
        import phoenix as px
        from openinference.instrumentation.litellm import LiteLLMInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor
    except ImportError as e:
        logger.warning(
            "Dependencias de Phoenix no instaladas: %s. "
            "Ejecuta: pip install arize-phoenix "
            "openinference-instrumentation-litellm "
            "openinference-instrumentation-openai",
            e,
        )
        return False

    # Default a loopback (127.0.0.1) para seguridad - NO 0.0.0.0
    host = host or os.getenv("PHOENIX_HOST", "127.0.0.1")
    port = port or int(os.getenv("PHOENIX_PORT", "6006"))
    working_dir = working_dir or os.getenv("PHOENIX_WORKING_DIR", "./phoenix_data")

    # Crear directorio de trabajo si no existe
    os.makedirs(working_dir, exist_ok=True)

    try:
        # Iniciar la app de Phoenix (servidor web en background)
        logger.info("Iniciando Phoenix en http://%s:%d ...", host, port)
        _phoenix_app = px.launch_app(
            host=host,
            port=port,
            working_dir=working_dir,
        )

        # Instrumentar LiteLLM (lo que usa nuestro adapter)
        LiteLLMInstrumentor().instrument()
        logger.info("Instrumentación LiteLLM activada.")

        # También instrumentar OpenAI por compatibilidad (OpenRouter usa API compatible)
        OpenAIInstrumentor().instrument()
        logger.info("Instrumentación OpenAI activada.")

        _phoenix_initialized = True
        logger.info("Phoenix listo en http://%s:%d", host, port)
        return True

    except Exception as e:  # noqa: BLE001
        logger.error("Error inicializando Phoenix: %s", e)
        return False


def shutdown_phoenix() -> None:
    """Cierra el servidor Phoenix si está corriendo."""
    global _phoenix_initialized, _phoenix_app

    if _phoenix_app is not None:
        try:
            # Phoenix no tiene un método público de shutdown limpio en todas las versiones
            # El proceso se termina cuando el proceso principal termina
            logger.info("Cerrando Phoenix...")
            _phoenix_app = None
            _phoenix_initialized = False
        except Exception as e:  # noqa: BLE001
            logger.warning("Error cerrando Phoenix: %s", e)


@contextmanager
def phoenix_session(
    host: str | None = None,
    port: int | None = None,
    working_dir: str | None = None,
):
    """
    Context manager para inicializar y cerrar Phoenix automáticamente.
    
    Uso:
        with phoenix_session():
            # código que genera trazas
            run_triage(...)
    """
    initialized = init_phoenix(host, port, working_dir)
    try:
        yield initialized
    finally:
        if initialized:
            shutdown_phoenix()


def is_phoenix_running() -> bool:
    """Verifica si Phoenix está inicializado y corriendo."""
    return _phoenix_initialized and _phoenix_app is not None


def get_phoenix_url() -> str | None:
    """Devuelve la URL del servidor Phoenix si está corriendo."""
    if is_phoenix_running():
        host = os.getenv("PHOENIX_HOST", "127.0.0.1")
        port = os.getenv("PHOENIX_PORT", "6006")
        return f"http://{host}:{port}"
    return None


__all__ = [
    "init_phoenix",
    "shutdown_phoenix",
    "phoenix_session",
    "is_phoenix_running",
    "get_phoenix_url",
]