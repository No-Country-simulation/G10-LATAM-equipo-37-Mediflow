# Conjunto de prueba (golden set)

`evals/run.py` compara contra este plan. `plan_golden.csv` es la lista de los 45 elementos con su etiqueta esperada: tipo, resultado, destino, auditoría, categoría AMB, nivel de legibilidad, formato y las columnas `revision_1` y `revision_2`. Un elemento no cuenta hasta que tiene las dos revisiones.

## Archivos en `files/`, uno por elemento y formato

| Formato | Nombre | Ejemplo |
|---|---|---|
| Texto | `GS-NN.txt` | `GS-06.txt` |
| Entrada JSON (columna `formato_json = si`) | `GS-NN.json` | `GS-01.json` |
| PDF nativo (columna `formato_pdf = si`) | `GS-NN.pdf` | `GS-07.pdf` |
| Imagen degradada, variante `foto` | `GS-NN_foto.png` | `GS-12_foto.png` |
| Imagen degradada, variante `pdf_escaneado` | `GS-NN_escaneado.png` | `GS-16_escaneado.png` |

El nivel de legibilidad de cada imagen (leve, media, severa) está en `plan_golden.csv`, no en el nombre del archivo.

## Cómo lo lee `evals/run.py`

El harness no necesita un archivo intermedio: lee `plan_golden.csv`, busca en `files/` todas las
variantes que existan de cada elemento y evalúa cada una por separado. Un elemento sin archivo
escrito no cuenta como error, aparece como pendiente.

Regla: nadie ajusta prompts mirando estos archivos. Para eso está `evals/dev/`.

## La etiqueta de la fila describe el documento legible

Cada fila lleva la respuesta correcta del documento tal como se escribió. Una imagen degradada del
mismo documento **no espera lo mismo**: manda el umbral de legibilidad, no el contenido. `run.py`
evalúa cada variante por separado y deriva lo que espera de la imagen:

| Nivel | Qué se espera de la imagen |
|---|---|
| leve | lo mismo que el documento legible: la imagen se lee bien |
| media | revisión humana con AMB-4 y marca de auditoría. Si el documento es una urgencia, va a Emergencia y además queda marcado |
| severa | revisión humana con marca de auditoría, sin comparar el tipo: por debajo de 0,40 el grafo no llega a clasificar |

Por eso, por ejemplo, GS-12 dice Historia Clínica Electrónica en su fila y su imagen severa debe
terminar en la Cola de Revisión Humana. Las dos cosas son correctas y se miden por separado: las
métricas de clasificación y destino salen de los documentos legibles, y las imágenes media y severa
alimentan la métrica de la puerta de legibilidad.
