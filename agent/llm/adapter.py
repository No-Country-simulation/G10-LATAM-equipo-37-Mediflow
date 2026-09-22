"""Adaptador único de modelos con cadena de respaldo.

Principal → respaldo 1 → respaldo 2. Cambia de modelo ante 429, 5xx, timeout o cualquier error.
Devuelve el texto y el modelo que respondió, para registrarlo en la traza.
"""
import base64
import mimetypes
import os
import time
from dataclasses import dataclass

PRIMARY = os.getenv("LLM_PRIMARY", "gemini/gemini-2.5-flash")
FALLBACKS = [m.strip() for m in os.getenv("LLM_FALLBACKS", "").split(",") if m.strip()]


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int


def _to_data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def complete(prompt: str, images: list[str] | None = None, json_mode: bool = True, timeout: int = 60) -> LLMResult:
    import litellm  # se importa aquí para que los tests sin claves no lo necesiten

    errores = []
    for model in [PRIMARY, *FALLBACKS]:
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
            )
        except Exception as e:  # noqa: BLE001 - cualquier fallo pasa al siguiente modelo
            errores.append(f"{model}: {type(e).__name__}: {e}")
    raise RuntimeError("Todos los modelos fallaron: " + " | ".join(errores))
