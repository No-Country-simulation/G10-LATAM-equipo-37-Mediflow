# Generador del conjunto de prueba

El `.txt` que escribe cada persona en `evals/golden/files/` es la fuente de verdad. Estos dos
scripts producen a partir de él las demás versiones, para que todas digan exactamente lo mismo y
compartan la etiqueta esperada de `plan_golden.csv`.

## `generate.py`

Produce el PDF y el JSON de entrada de cada caso que los pida en el plan.

```bash
python evals/generator/generate.py               # todo lo que falte
python evals/generator/generate.py --solo GS-07  # un caso
python evals/generator/generate.py --forzar      # rehace los que ya existen
```

El PDF imita un documento impreso: membrete, bloque del paciente, cuerpo y pie de firma. No es
decoración, es lo que obliga al modelo a vérselas con encabezados y sellos en vez de texto plano.

## `degradar.py`

Produce las variantes de imagen: `GS-NN_foto.png`, que simula la foto de un teléfono, y
`GS-NN_escaneado.png`, que simula el escáner de admisiones. El nivel sale de la columna
`nivel_legibilidad` del plan.

```bash
python evals/generator/degradar.py               # todo lo que falte
python evals/generator/degradar.py --solo GS-12
python evals/generator/degradar.py --sin-augraphy
```

Usa Augraphy si está instalado y, si no, una tubería propia con Pillow. Las dos respetan los tres
niveles, así que el conjunto se regenera en cualquier máquina.

### Cómo están calibrados los niveles

No se ajustaron a ojo. Se midió con OCR cuánto texto sobrevive a cada nivel, contra los umbrales de
`rules.yaml`:

| Nivel | Texto que sobrevive | Qué debe pasar |
|---|---|---|
| leve | 100 % | legibilidad 0,70 o más: se procesa normal |
| media | alrededor del 75 % | entre 0,40 y 0,70: se extrae lo posible y va a revisión con AMB-4 |
| severa | 0 a 1 % | por debajo de 0,40: revisión humana, solicitar nueva captura |

Lo que más castiga al OCR no es el desenfoque sino la pérdida de resolución, así que el parámetro
de escala es el que manda. Si se cambian esos números, hay que volver a medir con OCR, no mirar la
imagen y decidir.

La degradación usa una semilla fija (`--semilla`), así que regenerar el conjunto produce las mismas
imágenes.

## Tablas de referencia

`data/` guarda el banco clínico, los medicamentos y los códigos CIE-10. Se consultan al escribir
los documentos y el agente las usa para validar, pero no se evalúan: no son parte del conjunto de
prueba.
