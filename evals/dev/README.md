# Evaluaciones de Desarrollo (`evals/dev`)

Este directorio contiene las herramientas y los casos de prueba que usamos **durante el desarrollo** para validar cambios en los prompts de extracción antes de pasarlos a `main`.

## ¿Qué contiene?

- **`extraccion.json`**: 9 casos de prueba sintéticos (órdenes, epicrisis, certificados y recetas) con el resultado esperado (`esperado`). Se usan para comparar el comportamiento de dos versiones de un prompt.
- **`evaluar_extraccion.py`**: Script que corre los casos de `extraccion.json` con dos prompts (uno "antes" y uno "después") y genera un reporte de mejoras y regresiones.
- **`test_evaluar_extraccion.py`**: Tests unitarios del comparador, que aseguran que las regresiones (por ejemplo, dosis incorrectas) se detecten correctamente y que no falle con listas vacías o null.

## ¿Cómo se usa?

### 1. Correr los tests del comparador

Para verificar que el comparador funciona bien, ejecutá en la terminal:
python -m pytest evals/dev/test_evaluar_extraccion.py -q

### 2. Correr una comparación entre dos prompts

Para medir el impacto de un cambio en el prompt, ejecutá:
python evals/dev/evaluar_extraccion.py --antes prompt-antes.md --despues agent/prompts/extraer.md --salida evals/output/n113-comparacion.json

Los argumentos son:
- `--antes`: Ruta al prompt viejo (el que está en `develop` o `main`).
- `--despues`: Ruta al prompt nuevo (el que se quiere validar).
- `--salida`: Ruta donde se guarda el JSON con los resultados.

**Nota:** La corrida final ya se realizó (SHA `6b72ef9`) y el JSON está en `evals/output/n113-comparacion.json` con `valido: True` y `regresiones: {}`.

### 3. Interpretar los resultados

El archivo de salida tiene dos campos clave:
- **`valido`**: `true` si todas las llamadas al modelo se completaron sin errores.
- **`regresiones`**: Un objeto con los campos que empeoraron (si está vacío, no hay regresiones).

También incluye un detalle por caso (`resultados`) donde se ve, campo por campo, si el prompt nuevo acertó o falló.

## ¿Por qué existe esta carpeta?

Los prompts de extracción son críticos: un cambio en una regla puede mejorar la extracción de medicamentos pero romper la de certificados. Esta carpeta permite **medir el impacto de un cambio antes de fusionarlo**, con casos reproducibles y una comparación objetiva.

## Notas

- Los casos de `extraccion.json` son **sintéticos** y no contienen datos de pacientes reales.
- El script de comparación usa el modelo configurado en el entorno (por defecto, DeepSeek). No requiere credenciales en el repositorio.
- El README no reemplaza la evaluación formal (`evals/golden`), sino que es una herramienta de desarrollo para iterar rápido.