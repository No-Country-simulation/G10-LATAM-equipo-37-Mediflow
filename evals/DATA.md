# Ficha de datos

Regla que no se negocia: ningún documento real de ningún paciente.

## Qué es el conjunto de prueba

Documentos cuya respuesta correcta conocemos de antemano. Cada uno lleva su etiqueta: tipo, datos a extraer, prioridad, destino y si requiere auditoría. Se pasan por el agente, se compara la salida con la etiqueta y de ahí salen las métricas. Un documento no entra hasta que dos personas revisan su etiqueta.

## Cuánto y por qué

| Qué | Cantidad | Quién lo produce |
|---|---|---|
| Documentos de texto | 30 | El generador, y dos personas revisan cada etiqueta |
| Casos fuera de alcance | 7 | Escritos por el equipo, uno por cada motivo de `fuera_de_alcance` en rules.yaml, más el de la instrucción incrustada: factura de farmacia, consentimiento informado, carnet de obra social, informe en inglés, pedido de diagnóstico, receta veterinaria e ionograma con una orden escondida en el texto |
| Imágenes degradadas | 12 | Un script sobre los PDF ya generados, así que son de varios tipos. Heredan el contenido, no hay que revisarlas |
| Fotos de recetas manuscritas | 8, una por persona | Cada integrante escribe y fotografía la suya. Todas son Receta Médica, que es el único tipo que se escribe a mano |
| **Total de elementos** | **57** | |

Los siete casos fuera de alcance se miden aparte, porque responden otra pregunta: no si el agente acierta, sino si sabe cuándo no le corresponde decidir. Seis cubren un motivo cada uno de `fuera_de_alcance.motivos` en rules.yaml, con el motivo esperado anotado en la columna `motivo_fuera_de_alcance` del plan, y deben terminar en revisión humana con AMB-6. El séptimo, la instrucción incrustada en el texto, debe enrutarse por lo que el documento realmente es, ignorando la orden.

Treinta alcanza para responder la pregunta que importa en un hackathon: ¿funciona o está roto? Un fallo sobre 30 es el 3 %, y si fallan cinco se nota de inmediato. Para detectar mejoras de dos o tres puntos entre versiones de los prompts harían falta cientos, y eso no cabe en cinco semanas con ocho personas construyendo el producto a la vez.

## Reparto de los 30 documentos

El plan documento por documento, con su cuadro clínico y su etiqueta esperada, está en `evals/golden/plan_golden.csv`.

Los mismos 30 documentos se ven desde dos ángulos. Las dos tablas suman 30 cada una porque describen el mismo conjunto, no dos conjuntos distintos.

**Por tipo de documento**

| Tipo | Cantidad |
|---|---|
| Receta Médica | 6 |
| Informe de Estudio por Imágenes | 6 |
| Informe de Laboratorio | 5 |
| Orden de Solicitud de Procedimiento | 5 |
| Epicrisis | 4 |
| Certificado Médico | 4 |
| **Total** | **30** |

**Por resultado esperado**, es decir por el camino del grafo que debe seguir cada uno

| Resultado | Cantidad |
|---|---|
| Rutina, destino por tipo sin auditoría | 13 |
| Alto riesgo farmacológico, Farmacia con auditoría | 3 |
| Urgencia, Emergencia sin auditoría | 6 |
| Urgencia con ambigüedad, Emergencia con auditoría | 2 |
| Ambigüedad, Revisión Humana | 6 |
| **Total** | **30** |

No todas las combinaciones existen: un certificado médico no puede ser urgente ni un informe de imágenes llevar medicamentos de alto riesgo. El generador solo produce las que tienen sentido clínico, según la columna `tipos_documento` del banco clínico.

Las 6 ambigüedades cubren las cinco categorías: AMB-1 falta un campo obligatorio (2), AMB-2 contradicción interna (1), AMB-3 dosis fuera de rango (1), AMB-4 texto truncado (1), AMB-5 dos documentos en un archivo (1).

## Formatos

Los 30 existen como texto plano. Algunos además se materializan en otro formato, con la misma etiqueta, porque el generador produce las cuatro versiones del mismo contenido.

| Formato | Archivos |
|---|---|
| Texto plano | 30 |
| JSON | 6 |
| PDF con capa de texto | 10 |
| PDF escaneado, degradado de los anteriores | 6 |
| Foto de documento impreso, degradada | 6 |
| Foto de receta manuscrita | 8 |

## Legibilidad

Solo aplica a las 20 imágenes, las 12 degradadas más las 8 manuscritas. Tres niveles, cada uno con un comportamiento esperado distinto, que es lo que permite ajustar los umbrales de 0,40 y 0,70.

| Nivel | Score esperado | Qué debe hacer el sistema | Degradadas | Manuscritas |
|---|---|---|---|---|
| Leve | 0,70 o más | Procesar con normalidad | 4 | 3 |
| Media | Entre 0,40 y 0,70 | Extraer lo legible, resto en `null`, revisión con AMB-4 | 4 | 3 |
| Severa | Menos de 0,40 | Rechazar y pedir nueva captura | 4 | 2 |

Las degradadas se producen con Augraphy sobre el PDF limpio: ruido, inclinación, sombra, desenfoque y baja resolución según el nivel. Heredan el contenido verdadero, así que no hay que etiquetar de nuevo; lo que cambia con el nivel es la decisión esperada: leve mantiene la del documento limpio, media va a revisión con AMB-4 y severa pide nueva captura. Las manuscritas las escribe el equipo, una receta ficticia por persona con paciente inventado y un medicamento real, fotografiada con el celular; dos se toman mal a propósito.

## Fuentes externas

Etiquetan campos, no decisiones de enrutamiento. Todas CC BY 4.0, casos clínicos en español anotados por especialistas.

| Fuente | Enlace | Qué campo permite medir |
|---|---|---|
| CodiEsp | https://zenodo.org/records/3625747 | `cie10_sugerido` |
| MEDDOCAN | https://github.com/PlanTL-GOB-ES/SPACCC_MEDDOCAN | `paciente.nombre`, `medico_solicitante.nombre`, `matricula` |
| PharmaCoNER | https://zenodo.org/records/4270158 | `medicamentos[].nombre` |

Ninguna trae tipo de documento, prioridad, destino, ni dosis, frecuencia o duración. Para esos campos la única verdad posible son los documentos que generamos y las recetas que escribimos a mano.

## Tablas de referencia

No son casos de prueba: el agente las consulta mientras procesa cada documento.

| Tabla | Origen | Estado |
|---|---|---|
| Catálogo CIE-10 | CIE-10 de la OMS en español: `evals/generator/data/cie10.csv`. Fuente oficial: lista tabular del Volumen 1 de la OPS/OMS, Publicación Científica 554, en https://ais.paho.org/classifications/chapters/pdf/volume1.pdf | Verificado el 25/9 contra la lista tabular: 22 códigos, 7 descripciones corregidas y 1 código inválido reemplazado (K35.2 por K35.0) |
| Tabla de medicamentos | `evals/generator/data/medicamentos.csv`, 22 medicamentos identificados por código ATC y DCI de la OMS, válidos en toda Latinoamérica | Alto riesgo según los grupos A PINCH de la OMS. Rangos verificados contra los prospectos de ANMAT el 25/9: 15 verificados y 7 marcados como dosificados por protocolo |

## Separación de conjuntos

| Carpeta | Regla |
|---|---|
| `agent/prompts/examples/` | Ejemplos incrustados en el prompt. Nunca se evalúan |
| `evals/dev/` | Para iterar prompts y reglas |
| `evals/golden/` | De aquí salen los números publicados |

Salen del mismo generador con semillas distintas, así que son disjuntos por construcción.
