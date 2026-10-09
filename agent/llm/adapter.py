"""Adaptador único de modelos con cadena de respaldo y reintentos con backoff.

Estrategia:
1. Se prueba el modelo PRIMARY.
2. Si falla con error recuperable (429, 5xx, timeout), se reintenta hasta
   REINTENTOS_POR_MODELO veces con backoff exponencial.
3. Si sigue fallando, se pasa al siguiente modelo de FALLBACKS.
4. Si todos los modelos fallan, se levanta RuntimeError con el detalle.

Devuelve el texto y el modelo que respondió, para registrarlo en la traza.
"""
import base64
import logging
import mimetypes
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PRIMARY = os.getenv("LLM_PRIMARY", "gemini/gemini-2.5-flash")
FALLBACKS = [m.strip() for m in os.getenv("LLM_FALLBACKS", "").split(",") if m.strip()]

# Configuración de reintentos.
REINTENTOS_POR_MODELO = int(os.getenv("LLM_REINTENTOS", "3"))
BACKOFF_BASE_S = float(os.getenv("LLM_BACKOFF_BASE", "2"))


@dataclass
class LLMResult:
    """Resultado de una llamada al LLM."""
    text: str
    model: str
    latency_ms: int
    intentos: int = 1  # cuántos intentos se hicieron en total (incluye reintentos)


def _to_data_url(path: str) -> str:
    """Convierte un archivo de imagen local a un data URL base64."""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _es_error_recuperable(exc: Exception) -> bool:
    """
    Determina si un error es recuperable (conviene reintentar el mismo modelo).

    Recuperables:
    - 429 (rate limit)
    - 5xx (error del servidor)
    - Timeout
    """
    nombre = type(exc).__name__.lower()
    mensaje = str(exc).lower()

    # Timeout
    if "timeout" in nombre or "timeout" in mensaje:
        return True

    # Rate limit / 429
    if "429" in mensaje or "rate" in mensaje or "ratelimit" in nombre:
        return True

    # 5xx
    for codigo in ("500", "502", "503", "504"):
        if codigo in mensaje:
            return True

    return False


def _llamar_modelo(
    model: str,
    content: list[dict],
    json_mode: bool,
    timeout: int,
) -> str:
    """Hace UNA llamada al modelo. Devuelve el texto de la respuesta."""
    import litellm  # se importa acá para que los tests sin claves no lo necesiten

    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": content}],
        timeout=timeout,
        **kwargs,
    )
    return resp.choices[0].message.content


def complete(
    prompt: str,
    images: list[str] | None = None,
    json_mode: bool = True,
    timeout: int = 60,
) -> LLMResult:
    """
    Llama al LLM con cadena de respaldo y reintentos con backoff.

    Args:
        prompt: texto del prompt.
        images: lista de rutas a imágenes (opcional).
        json_mode: si True, pide JSON al modelo.
        timeout: timeout en segundos por intento.

    Returns:
        LLMResult con texto, modelo, latencia e intentos.

    Raises:
        RuntimeError: si todos los modelos fallan tras agotar los reintentos.
    """
    # Preparar el contenido.
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in images or []:
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(path)}})

    errores = []
    t0_total = time.time()
    intentos_totales = 0

    for model in [PRIMARY, *FALLBACKS]:
        for intento in range(1, REINTENTOS_POR_MODELO + 1):
            intentos_totales += 1
            try:
                logger.debug("Intento %d/%d con %s", intento, REINTENTOS_POR_MODELO, model)
                texto = _llamar_modelo(model, content, json_mode, timeout)
                return LLMResult(
                    text=texto,
                    model=model,
                    latency_ms=int((time.time() - t0_total) * 1000),
                    intentos=intentos_totales,
                )
            except Exception as e:  # noqa: BLE001
                recuperable = _es_error_recuperable(e)
                errores.append(f"{model} (intento {intento}): {type(e).__name__}: {e}")

                if recuperable and intento < REINTENTOS_POR_MODELO:
                    espera = BACKOFF_BASE_S * (2 ** (intento - 1))  # 2, 4, 8
                    logger.warning(
                        "Error recuperable en %s (intento %d). Reintentando en %.1fs: %s",
                        model, intento, espera, e,
                    )
                    time.sleep(espera)
                    continue

                # No recuperable o último intento: pasar al siguiente modelo.
                logger.warning("Modelo %s agotado tras %d intentos. Pasando al siguiente.", model, intento)
                break

    raise RuntimeError(
        f"Todos los modelos fallaron tras {intentos_totales} intentos: "
        + " | ".join(errores)
    )


__all__ = ["complete", "LLMResult", "PRIMARY", "FALLBACKS"]