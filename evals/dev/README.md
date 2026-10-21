# Evaluaciones de Desarrollo (`evals/dev`)

Este directorio contiene las herramientas y los casos de prueba que usamos **durante el desarrollo** para validar cambios en los prompts de extracción antes de pasarlos a `main`.

## ¿Qué contiene?

- **`extraccion.json`**: 10 casos de prueba sintéticos (órdenes, epicrisis, certificados y recetas) con el resultado esperado (`esperado`). Se usan para comparar el comportamiento de dos versiones de un prompt.
- **`evaluar_extraccion.py`**: Script que corre los casos de `extraccion.json` con dos prompts (uno "antes" y uno "después") y genera un reporte de mejoras y regresiones.
- **`test_evaluar_extraccion.py`**: Tests unitarios del comparador, que aseguran que las regresiones (por ejemplo, dosis incorrectas) se detecten correctamente y que no falle con listas vacías o null.

## ¿Cómo se usa?

### 1. Correr los tests del comparador

Para verificar que el comparador funciona bien, ejecutá en la terminal:
python -m pytest evals/dev/test_evaluar_extraccion.py -q

### 2. Correr una comparación entre dos prompts

Para medir el impacto de un cambio en el prompt, ejecutá:
python evals/dev/evaluar_extraccion.py --antes prompt-antes.md --despues agent/prompts/extraer.md --salida evals/output/n113-comparacion-nueva.json

Los argumentos son:
- `--antes`: Ruta al prompt viejo (el que está en `develop` o `main`).
- `--despues`: Ruta al prompt nuevo (el que se quiere validar).
- `--salida`: Ruta donde se guarda el JSON con los resultados.

**Evidencia disponible:**
- Corrida histórica: `evals/output/n113-comparacion.json`, 9 casos con `deepseek/deepseek-chat`, reportada sobre `6b72ef9`.
- Corrida más reciente: `evals/output/n113-comparacion-final.json`, 10 casos (20 llamadas) con `deepseek/deepseek-flash`, `valido: true` y `regresiones: []`. Incluye DEV-RECETA-04 y conserva la dosis sintética de `5000 mg`.
- Carlos identifica el prompt candidato como `5597536` en Discord. El JSON no incorpora hashes de los prompts: queda pendiente identificar y conservar el archivo o SHA exacto del baseline para reproducir la comparación.

Usar el mismo modelo en ambos lados y comprobar el modelo efectivo en cada resultado. Las dos corridas usan modelos distintos; no deben atribuirse sus diferencias únicamente al cambio de prompt. El ejecutor no sobrescribe archivos existentes: usar una salida nueva y conservar los reportes anteriores.

### 3. Interpretar los resultados

El archivo de salida tiene dos campos clave:
- **`valido`**: `true` si todas las llamadas al modelo se completaron sin errores.
- **`regresiones`**: Una lista con los identificadores de casos que tienen al menos un campo que empeoró (si está vacía, no hay regresiones).

También incluye un detalle por caso (`resultados`) donde se ve, campo por campo, si el prompt nuevo acertó o falló.

## ¿Por qué existe esta carpeta?

Los prompts de extracción son críticos: un cambio en una regla puede mejorar la extracción de medicamentos pero romper la de certificados. Esta carpeta permite **medir el impacto de un cambio antes de fusionarlo**, con casos reproducibles y una comparación objetiva.

## Notas

- Los casos de `extraccion.json` son **sintéticos** y no contienen datos de pacientes reales.
- El script de comparación usa el modelo configurado en el entorno (por defecto, DeepSeek). No requiere credenciales en el repositorio.
- El README no reemplaza la evaluación formal (`evals/golden`), sino que es una herramienta de desarrollo para iterar rápido.

## Alcance de la verificación

La comparación llama al adaptador de extracción; no ejecuta el flujo completo de validación y enrutamiento. Ni los tests locales ni la ausencia de regresiones en estos diez casos cierran por sí solos N1-13. Falta validar el flujo completo y la evaluación acordada con el equipo, conservando los controles de campos realmente ausentes. Esta evidencia de DeepSeek no acredita el rendimiento de la cadena gratuita desplegada.
