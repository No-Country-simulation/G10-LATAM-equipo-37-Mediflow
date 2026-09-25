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

## `golden_v0.jsonl`

Un caso por línea, generado a partir de `plan_golden.csv` y de `files/`. Lo lee `evals/run.py`:

```json
{"documento_id": "GS-06", "tipo_archivo": "TEXTO", "archivo": "evals/golden/files/GS-06.txt",
 "esperado": {"tipo_documento": "Receta Medica", "resultado": "ambiguedad", "destino_principal": "Cola_Revision_Humana",
              "requiere_auditoria_humana": true, "categoria_amb": "AMB-3", "nivel_prioridad": "Rutina"},
 "revisado_por": ["CO", "CC"]}
```

Regla: nadie ajusta prompts mirando estos archivos. Para eso está `evals/dev/`.
