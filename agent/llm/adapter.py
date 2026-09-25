"""Adaptador único de modelos con cadena de respaldo.

Principal → respaldo 1 → respaldo 2. Cambia de modelo ante 429, 5xx, timeout o cualquier error.
Devuelve el texto y el modelo que respondió, para registrarlo en la traza.

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


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
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
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def complete(
    prompt: str,
    images: list[str] | None = None,
    json_mode: bool = True,
    timeout: int = 60,
    modelo: str | None = None,
) -> LLMResult:
    """Llama al modelo y devuelve el texto junto con el modelo que respondió y el uso.

    `modelo` no agrega ni quita nada de la cadena: solo le cambia el orden, poniéndolo primero. El
    resto sigue disponible como respaldo, así que pedir un modelo puntual nunca es menos resiliente
    que la llamada normal.
    """
    import litellm  # se importa aquí para que los tests sin claves no lo necesiten

    errores = []
    for model in _cadena(modelo):
        t0 = time.time()
        try:
            content: list[dict] = [{"type": "text", "text": prompt}]
            for path in images or []:
                content.append({"type": "image_url", "image_url": {"url": _to_data_url(path)}})
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            resp = litellm.completion(
                model=model, messages=[{"role": "user", "content": content}], timeout=timeout, **kwargs
            )
            return LLMResult(
                text=resp.choices[0].message.content,
                model=model,
                latency_ms=int((time.time() - t0) * 1000),
                **_uso(resp),
            )
        except Exception as e:  # noqa: BLE001 - cualquier fallo pasa al siguiente modelo
            errores.append(f"{model}: {type(e).__name__}: {e}")
    raise RuntimeError("Todos los modelos fallaron: " + " | ".join(errores))
