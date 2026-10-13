# Análisis de la primera evaluación · 13/10/2026

Corrida oficial de `evals/run.py`:
- **Qué se evaluó:** las 76 variantes de los 45 documentos del conjunto de prueba.
- **Modelo principal:** DeepSeek (`deepseek/deepseek-chat`).
- **Código:** commit `b3ff577` de develop, con #103, #98 y #10 ya fusionados.
- **Archivos:** `report.md` y `resultados.json` son la salida del harness sin editar. Este análisis se escribió después, a partir de ellos.

## Resumen

| Métrica | Corrida completa | Solo texto, PDF y JSON |
|---|---|---|
| Recall de urgencias | 94 % (16/17) | **100 % (16/16)** |
| Accuracy de clasificación | 83 % (52/63) | 96 % (52/54) |
| Accuracy de destino | 62 % (39/63) | 67 % (36/54) |
| Acierto de la marca de auditoría | 60 % (38/63) | 63 % (34/54) |
| Casos fuera de alcance resueltos | 0 % (0/12) | 0 % (0/10) |
| Puerta de legibilidad (media y severa) | 46 % (6/13) | no aplica |
| Casos correctos en todo | 41 % (31/76) | 46 % (25/54) |
| Falsas urgencias | 10 | 10 |
| Tasa de revisión humana | 45 % (34/76) | |
| Latencia p50 / p95 | 3,9 s / 5,2 s | |
| Errores de ejecución | 0 | |

La columna de la derecha deja afuera las 22 imágenes, porque en esta corrida no se llegaron a evaluar (punto 1).

**Margen de error.** Con 54 variantes de texto, un acierto del 67 % tiene un margen de unos ±13 puntos con un 95 % de confianza: 1,96 × √(0,67 × 0,33 ÷ 54) ≈ 0,13. Sirve para encontrar qué está roto, no para comparar modelos que difieran en pocos puntos.

## Qué explica los números

### 1. Las imágenes no se evaluaron

Las 22 imágenes terminaron igual:
- sin tipo y sin score;
- en Revisión humana;
- en menos de 5 segundos.

Es la señal de que el OCR no devolvió texto. En ese caso la legibilidad provisional de `normalizar.py` queda en 0,30, por debajo del mínimo de 0,40, y el agente decide «ilegible» sin llamar al modelo. Con tesseract instalado, el OCR lee el escaneo de GS-07 sin problema (más de 1.500 caracteres). Todo indica que faltaba tesseract en la máquina de la corrida. La imagen de la API sí lo instala.

Consecuencias:
- **La única urgencia que falta es una imagen:** GS-07 escaneado.
- **No miden el agente:** la puerta de legibilidad (46 %), la categoría «legibilidad media» y los fallos de las fotos manuscritas M1 a M6.
- **Hace falta un modelo multimodal en la cadena:** DeepSeek no recibe imágenes, así que la corrida siguiente necesita un modelo de respaldo que sí las lea.

### 2. Las falsas urgencias vienen de la regla A, que todavía no está en develop

`agent/nodes/urgencia.py` en develop sigue siendo la versión inicial. Aplica los hallazgos críticos y las palabras clave a todos los tipos de documento. La regla A (ADR-002) los limita a informes de estudio, informes de laboratorio y órdenes, y está en el PR de N1-06, que no está fusionado.

8 de las 10 falsas urgencias caen en tipos donde la regla A no admite las listas automáticas:
- **Recetas:** GS-01 y GS-04. GS-04 es el caso trampa: la enoxaparina al alta menciona el TEP del episodio.
- **Epicrisis:** GS-23, GS-24 (texto y PDF) y GS-25.
- **Fuera de alcance:** FA-02 (texto y PDF).

Las otras dos son GS-21 (orden) y FA-04 (informe en inglés que el agente tomó por un informe de imágenes).

Estas urgencias explican 10 de los 18 errores de destino en texto. Entre ellos, 4 de las 5 epicrisis; la quinta, GS-26, es del punto 4.

### 3. Fuera de alcance: el agente reconoce el caso, pero no se marca la auditoría

En 8 de las 10 variantes de texto fuera de alcance, el agente clasifica el documento como «Otro» y asigna AMB-6 con el motivo correcto (`no_clinico`, `pide_diagnostico`, `paciente_no_humano`, `tipo_no_soportado`).

Seis de esas ocho van a Revisión humana, como corresponde, y aun así fallan: `enrutar.py` no marca `requiere_auditoria_humana` en el camino «destino por tipo», que es por donde pasa el tipo «Otro». Son FA-01 (texto y PDF), FA-03, FA-06 y FA-07 (texto y PDF), y fallan solo por esa marca.

Las demás variantes fuera de alcance fallan por:
- **FA-02 (texto y PDF):** también es «Otro» con AMB-6, pero la falsa urgencia lo mandó a Emergencia (punto 2).
- **FA-04 (texto y PDF):** el informe en inglés se tomó como un informe de imágenes.
- **FA-03 y FA-06:** las fotos (punto 1).

El intento de engaño, **FA-05**, salió bien. El agente ignoró la instrucción incrustada y mandó el potasio crítico a Emergencia.

### 4. AMB-1 de más y ambigüedad que no llega a revisión

- **AMB-1 de más:** `validar.py` marcó AMB-1 (falta un campo obligatorio) en 13 variantes que no tienen ningún campo faltante: órdenes, epicrisis y certificados. No cambia el destino por sí solo, pero baja el score. Por eso GS-27 pide auditoría con score 0,78.
- **Ambigüedad que no llega a revisión:** el contrato manda a Revisión humana cualquier documento con ambigüedad (sección 5, paso 3), pero `enrutar.py` solo mira `validacion.conflictos`. Por eso GS-22, GS-26 y GS-29 siguen a su destino por tipo aunque el agente les marcó AMB-1.
- **Lo mismo en una urgencia:** el contrato pide marcar auditoría si una urgencia además es ambigua. `enrutar.py` solo la marca con score bajo, y por eso falla GS-14.
- **Ambigüedad no detectada:** en GS-10 (AMB-4) y en GS-30 (AMB-5), el agente no encontró la ambigüedad esperada.

## Fallos por categoría

Agrupados como el informe de `run.py`: la categoría AMB esperada, la urgencia, el nivel de legibilidad o, si no hay ninguna, el tipo.

| Categoría | Variantes con fallo | Causa principal |
|---|---|---|
| AMB-6 · fuera de alcance | 12 | Marca de auditoría (6), urgencia (2), informe en inglés (2), fotos sin OCR (2) |
| Legibilidad media | 7 | Imágenes sin OCR: no se evaluaron |
| Receta médica | 6 | Falsas urgencias (GS-01, GS-04), dosis marcada como AMB-3 (GS-05), fotos sin OCR (3) |
| AMB-1 · campo faltante | 4 | La ambigüedad no lleva a revisión (GS-22, GS-29), falta la marca de auditoría en una urgencia ambigua (GS-14, dos variantes) |
| Epicrisis | 4 | Falsas urgencias por la regla A |
| AMB-4 · truncado o poco legible | 3 | No se detectó: GS-10 (dos variantes) y GS-26, que salió como AMB-1 |
| Informe de estudio por imágenes | 2 | AMB-2 de más en GS-12 (texto y PDF) |
| Orden de procedimiento | 2 | Falsa urgencia (GS-21), foto sin OCR (GS-20) |
| Certificado médico | 2 | AMB-1 de más con auditoría (GS-27), foto sin OCR |
| AMB-3 · dosis fuera de rango | 1 | Foto sin OCR (M3) |
| AMB-5 · dos documentos en uno | 1 | No se detectó (GS-30) |
| Urgencia | 1 | Foto sin OCR (GS-07 escaneado) |

## Destino por tipo de documento (texto, PDF y JSON)

| Tipo | Destino correcto |
|---|---|
| Informe de laboratorio | 10 de 10 |
| Informe de estudio por imágenes | 9 de 11 |
| Orden de procedimiento | 6 de 8 |
| Otro (fuera de alcance) | 6 de 10 |
| Receta médica | 3 de 6 |
| Certificado médico | 2 de 4 |
| Epicrisis | 0 de 5 |

## Qué sigue

| Qué | Dónde | Paquete |
|---|---|---|
| Fusionar la regla A de urgencia | `agent/nodes/urgencia.py` | N1-06 |
| Marcar la auditoría en todo lo que va a Revisión humana y mandar ahí la ambigüedad | `agent/nodes/enrutar.py` | N1-07 |
| Afinar AMB-1, AMB-4 y AMB-5 | `agent/nodes/validar.py` y prompts | N1-05 y N1-13 |
| Puerta de legibilidad con score real | `agent/nodes/normalizar.py` | N2-08 |
| Repetir la corrida con tesseract instalado y un modelo multimodal en la cadena de respaldo | `evals/run.py` | N3-01 |

La próxima corrida se publica en su propia carpeta de `evals/resultados/`. Esta queda como línea de base para medir esos cambios.
