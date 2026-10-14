# PR — N2-08: Puerta de legibilidad (Refs #62)

**Rama:** `feat/n2-08-puerta-legibilidad` → `develop`
**Issue:** #62 · **Asignado:** Néstor · **Apoyo:** Carlos, Camila
**Squad revisor:** @mediflow-one-g10/agente (CODEOWNERS de `/agent/`)

## Qué hace

Reemplaza la medida provisional de legibilidad (conteo de caracteres del OCR) por un
**score óptico real (0 a 1)** calculado sobre la imagen con tres métricas determinísticas
(Pillow, sin modelo ni red):

- **Resolución** — área efectiva de la página respecto a 1200x900.
- **Contraste** — desviación estándar de la luminancia.
- **Nitidez** — varianza del Laplaciano (detecta desenfoque / foto movida).

Fórmula: `score = resolucion * (0.75 * contraste + 0.25 * nitidez)`.
El modelo es multiplicativo: una imagen diminuta o sin contraste no puede pasar aunque el
resto acompañe. Calibración: nítida 1600x1200 → ~1.0; media 800x600 → ~0.44;
borrosa/oscura o en blanco → < 0.40.

El score alimenta la puerta ya existente en `graph.py` (`_tras_normalizar`), que deriva a
`enrutar` cuando `legibilidad < legibilidad_minima` (0.40). **No se toca el grafo ni la API.**

## Por qué sin autoevaluación del modelo

El alcance de #62 la menciona, pero queda como **fase 2** a propósito: requiere claves y red
(rompe el CI), es no determinística (no se fija en tests estables) y suma costo/latencia en
un nodo que corre en todos los documentos. Las 3 métricas ya cubren el criterio de aceptación.

## Archivos modificados / agregados

| Archivo | Cambio |
|---|---|
| `agent/nodes/normalizar.py` | Score óptico real; corrige bug de nitidez (Sobel inexistente en Pillow) y cálculo O(n²); decodifica la imagen una sola vez; actualiza el TODO (N2-08, issue #62). |
| `agent/tests/test_legibilidad.py` | **Nuevo.** 8 tests: bandas leve/media/severa, rango [0,1], legibilidad precargada intacta, integración `normalizar` con imagen borrosa. |
| `PR_DESCRIPTION.md` | Este documento. |

## Contrato respetado (sin cambios)

- Solo calcula cuando `legibilidad is None` (imagen / PDF escaneado). Texto digital conserva
  el valor de la ingesta; `legibilidad` precargada no se recalcula.
- `_tras_normalizar` (`graph.py`) sigue leyendo `legibilidad` y `legibilidad_minima` (0.40).
- Fallback de texto (`_score_from_text`) solo cuando la imagen no se puede decodificar.

## Validación

- [x] `pytest agent/tests/test_legibilidad.py` en verde (8 passed)
- [x] `pytest agent/tests` sin roturas (126 passed: ingesta, grafo, reglas, validar, auditoría, storage)
- [x] `ruff check agent/nodes/normalizar.py agent/tests/test_legibilidad.py` limpio (All checks passed)

## Alcance del criterio de aceptación (#62)

> "Imágenes severas → revisión (ilegible), leves pasan, y M1 a M8 dan su resultado esperado."

- **Parcial en este PR:** score y tests listos; la verificación M1–M8 depende de las 8 fotos.
  En `develop` solo existen M1, M2, M6 y M7. **Faltan M3, M4, M5 y M8** (niveles media y
  severa, las que calibran el umbral 0.40).
- Los tests usan imágenes sintéticas para no bloquearse con el set incompleto.

## Notas para el revisor

- No modifica `graph.py`, `state.py`, `rules.yaml`, `ingestion.py` ni el contrato de la API.
- La autoevaluación del modelo queda explícitamente fuera de alcance (fase 2).
