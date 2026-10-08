"""Adaptador único de modelos con cadena de respaldo y reintentos con backoff.

Estrategia:
1. Se prueba el modelo PRIMARY.
2. Si falla con error recuperable (429, 5xx, timeout), se reintenta hasta
   REINTENTOS_POR_MODELO veces con backoff exponencial.
3. Si sigue fallando, se pasa al siguiente modelo de FALLBACKS.
4. Si todos los modelos fallan, se levanta RuntimeError con el detalle.

Devuelve el texto, el modelo que respondió y el uso (tokens/costo), para registrarlo en la traza.

Dos usos y un solo camino de llamada:
- `complete(prompt)` recorre la cadena en orden. Es lo que usan `clasificar` y `extraer`.
- `complete(prompt, modelo=...)` pone ese modelo primero y deja el resto de respaldo. Es lo que usa
  `segunda_opinion`, que necesita la respuesta de OTRO modelo: preguntarle dos veces al mismo no
  es una segunda opinión, es la misma opinión repetida.

`modelos_disponibles()` expone la cadena configurada para que los nodos no la repitan.
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
    # Uso y costo son informativos: no todos los proveedores devuelven `usage` y no todos los
    # modelos tienen tarifa conocida. La traza los muestra cuando están y los ignora cuando no.
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    costo_usd: float | None = None


def modelos_disponibles() -> list[str]:
    """La cadena configurada, en el orden normal de intento (principal primero)."""
    return [PRIMARY, *FALLBACKS]


def _cadena(modelo: str | None = None) -> list[str]:
    """Orden de intentos. Con `modelo`, ese va primero y el resto sigue de respaldo."""
    cadena = [PRIMARY, *FALLBACKS]
    if not modelo:
        return cadena
    return [modelo, *(m for m in cadena if m != modelo)]


def _uso(resp) -> dict:
    """Tokens y costo de una respuesta. Nunca rompe la llamada: si no se pueden leer, van en None."""
    uso = getattr(resp, "usage", None)
    datos: dict = {
        "tokens_entrada": getattr(uso, "prompt_tokens", None),
        "tokens_salida": getattr(uso, "completion_tokens", None),
        "costo_usd": None,
    }
    try:
        import litellm

        datos["costo_usd"] = litellm.completion_cost(completion_response=resp)
    except Exception as e:  # noqa: BLE001 - el costo es informativo y no puede bloquear la llamada
        logger.debug("No se pudo calcular el costo del modelo: %s", e)
    return datos


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
):
    """Hace UNA llamada al modelo. Devuelve la respuesta cruda."""
    import litellm  # se importa acá para que los tests sin claves no lo necesiten

    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    return litellm.completion(
        model=model,
        messages=[{"role": "user", "content": content}],
        timeout=timeout,
        **kwargs,
    )


def complete(
    prompt: str,
    images: list[str] | None = None,
    json_mode: bool = True,
    timeout: int = 60,
    modelo: str | None = None,
) -> LLMResult:
    """
    Llama al LLM con cadena de respaldo y reintentos con backoff.

    `modelo` no agrega ni quita nada de la cadena: solo le cambia el orden, poniéndolo primero. El
    resto sigue disponible como respaldo, así que pedir un modelo puntual nunca es menos resiliente
    que la llamada normal.

    Args:
        prompt: texto del prompt.
        images: lista de rutas a imágenes (opcional).
        json_mode: si True, pide JSON al modelo.
        timeout: timeout en segundos por intento.
        modelo: si se especifica, se prueba primero (y el resto queda de respaldo).

    Returns:
        LLMResult con texto, modelo, latencia, intentos y uso.

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

    for model in _cadena(modelo):
        for intento in range(1, REINTENTOS_POR_MODELO + 1):
            intentos_totales += 1
            try:
                logger.debug("Intento %d/%d con %s", intento, REINTENTOS_POR_MODELO, model)
                resp = _llamar_modelo(model, content, json_mode, timeout)
                return LLMResult(
                    text=resp.choices[0].message.content,
                    model=model,
                    latency_ms=int((time.time() - t0_total) * 1000),
                    intentos=intentos_totales,
                    **_uso(resp),
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


__all__ = ["complete", "LLMResult", "PRIMARY", "FALLBACKS", "modelos_disponibles"]