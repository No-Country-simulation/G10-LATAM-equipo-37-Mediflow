# Generador del conjunto de prueba

El `.txt` que escribe cada persona en `evals/golden/files/` es la fuente de verdad. Estos dos
scripts producen a partir de él las demás versiones, para que todas digan exactamente lo mismo y
compartan la etiqueta esperada de `plan_golden.csv`.

## Antes de correrlos

Cada persona genera las variantes de sus propios documentos, después de subir su `.txt`. Hacen
falta tres librerías:

```bash
pip install reportlab pymupdf pillow
```

Y se corren con `--solo` y tus IDs, por ejemplo:

```bash
python evals/generator/generate.py --solo GS-03 GS-11
python evals/generator/degradar.py --solo GS-11
```

**Si ya habías generado variantes con una versión anterior de estos scripts, rehazlas con
`--forzar`.** La versión anterior agregaba al PDF un membrete y una marca de "paciente ficticio", y
usaba Augraphy por defecto, que en algunas imágenes producía páginas de libro y tachones.

## `generate.py`

Produce el PDF y el JSON de entrada de cada caso que los pida en el plan.

```bash
python evals/generator/generate.py               # todo lo que falte
python evals/generator/generate.py --solo GS-07  # un caso
python evals/generator/generate.py --forzar      # rehace los que ya existen
```

El PDF dice exactamente lo que dice el `.txt`, ni una palabra más ni una menos: el membrete, el
título y la firma los escribe cada persona en su texto, y el generador solo les da formato de
documento impreso. Nunca agrega datos ni marcas de "documento de prueba".

## `degradar.py`

Produce las variantes de imagen: `GS-NN_foto.png`, que simula la foto de un teléfono, y
`GS-NN_escaneado.png`, que simula el escáner de admisiones. El nivel sale de la columna
`nivel_legibilidad` del plan.

```bash
python evals/generator/degradar.py               # todo lo que falte
python evals/generator/degradar.py --solo GS-12
```

Usa una tubería propia con Pillow, que es la calibrada. Augraphy queda como opción explícita,
`--con-augraphy`, y no se recomienda: su configuración por defecto mete efectos que no existen en una
foto real, como páginas de libro, el documento repetido o tachones, y eso cambia la etiqueta esperada.

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
