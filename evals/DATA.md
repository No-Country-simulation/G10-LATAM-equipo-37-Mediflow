# Ficha de datos

Regla: ningún documento real de ningún paciente. Todo sintético o de corpus públicos con licencia.

| Fuente | Tipo | Cantidad | Idiomas | Licencia | Uso |
|---|---|---|---|---|---|
| Generador propio (`evals/generator/`) | Sintético | pendiente | es, pt, en | MIT (este repo) | Golden set y demo |
| Recetas manuscritas del equipo (`evals/handwritten/`) | Sintético, fotos propias | pendiente | es, pt | MIT (este repo) | Escenario ambiguo, visión, legibilidad |
| CodiEsp, https://doi.org/10.5281/zenodo.3837305 | Casos clínicos anotados con CIE-10 | pendiente | es | Ver Zenodo, citar | Clasificación y CIE-10 |
| MEDDOCAN, https://github.com/PlanTL-GOB-ES/SPACCC_MEDDOCAN | Casos clínicos sintéticos con PHI ficticia | pendiente | es | Ver repositorio, citar | Extracción de paciente y PII |

Cómo reproducir el golden set: `python evals/generator/generate.py --n 12 --salida evals/golden/`.
