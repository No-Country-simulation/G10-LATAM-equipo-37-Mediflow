# Contrato de MediFlow

Versión 1.1 · Incorpora la regla A de urgencia (ADR-002), el campo del paciente como `nombre` en todo el proyecto (ADR-003), los valores críticos de laboratorio como cuarta fuente de urgencia, el alto riesgo solo en recetas, la categoría AMB-6 de fuera de alcance, la distinción entre medicamentos que se validan por rango y los que se dosifican por protocolo (ADR-007), la fecha de nacimiento del paciente (ADR-009) y la revisión humana: la cola, la decisión del auditor y cómo se escriben las correcciones (sección 11).

Fuente: `agent/schemas/contrato.py`, `agent/schemas/documentos.py` y `agent/rules/rules.yaml` del esqueleto, más el ejemplo de entrada y salida del brief. Los nombres de campo siguen al brief, con una excepción decidida por el equipo y registrada en el ADR-003: `paciente.nombre` en lugar de `nome`, para que todo el contrato esté en un solo idioma.

---

## 1. Entrada

### 1.1 JSON (texto ya extraído o documento JSON)

```json
{
  "documento_id": "DOC-CLIN-2026-8942",
  "tipo_archivo": "TEXTO",
  "documento_texto": "HOSPITAL SANTA LUCIA - INFORME DE ESTUDIO RADIOLOGICO. Paciente: ...",
  "canal_origen": "Guardia_Emergencias"
}
```

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `documento_id` | string | sí | Único. Si se repite, la API responde el resultado anterior (idempotencia), no procesa dos veces |
| `tipo_archivo` | `TEXTO`, `JSON`, `PDF`, `IMAGEN` | sí | |
| `documento_texto` | string | sí para `TEXTO` y `JSON` | Vacío o solo espacios: error 422 |
| `canal_origen` | string | no | Libre. Ejemplos: `Guardia_Emergencias`, `Consultorio_Externo`, `Farmacia`, `web`, `bucket` |

### 1.2 Archivo (PDF o imagen)

`POST /triage/upload` multipart con `documento_id`, `canal_origen` y `archivo`. Formatos: `pdf`, `txt`, `json`, `png`, `jpg`, `jpeg`, `tiff`, `webp`. Tamaño máximo 20 MB y 50 páginas por PDF, configurables con `MEDIFLOW_MAX_UPLOAD_BYTES` y `MEDIFLOW_MAX_PDF_PAGES`.

La ingesta detecta el formato por la firma del archivo, no por la extensión ni por el tipo que declara el cliente: si no coinciden, el archivo se rechaza. Cualquier entrada inválida, sea por formato, tamaño, archivo vacío o codificación, responde 422 con un mensaje controlado que nunca devuelve contenido clínico ni rutas internas.

El archivo original se guarda en `recibidos/{documento_id}.{ext}` antes de llamar a cualquier modelo.

---

## 2. Salida

Idéntica al ejemplo del brief, más cuatro campos propios al final.

| Campo | Contenido |
|---|---|
| `status` | `procesado`, `revision_humana`, `rechazado`, `pendiente` |
| `documento_id` | El recibido |
| `clasificacion` | `tipo_documento`, `especialidad`, `nivel_prioridad`, `score_confianza_clasificacion` (0 a 1) |
| `datos_extraidos` | `paciente {nombre, edad, fecha_nacimiento}`, `medico_solicitante {nombre, matricula}`, `estudio_realizado`, `diagnostico_principal`, `cie10_sugerido`, `medicamentos []`, `estudios_solicitados []` |
| `decision_enrutamiento` | `destino_principal`, `requiere_auditoria_humana`, `justificacion_enrutamiento`, `notificacion_generada {canal, mensaje}` o null |
| `almacenamiento_oci` | `bucket`, `ruta_objeto`, `status_backup` (`exito`, `pendiente`, `error`) |
| `score_confianza` | Propio. Score compuesto de 0 a 1 |
| `modelo_utilizado` | Propio. Qué modelo respondió, para la traza y para medir respaldos |
| `evidencias` | Propio. Por cada campo extraído, el fragmento del documento que lo sustenta, o null |
| `trace` | Propio. Un registro por nodo del grafo: nombre, tiempo, detalle, modelo |

Reglas de la salida:

- Un dato que no está en el documento es `null`. Nunca se inventa, nunca se completa con conocimiento externo.
- `status_backup` solo dice `exito` si el objeto quedó escrito en el bucket. Un fallo de almacenamiento nunca reporta éxito.
- Si todos los modelos fallan, `status` es `pendiente`, el documento queda en `recibidos/` y el worker reintenta. No se pierde.

Significado de `status`:

| status | Cuándo |
|---|---|
| `procesado` | Enrutado a un destino operativo, con o sin marca de auditoría |
| `revision_humana` | Destino `Cola_Revision_Humana` |
| `rechazado` | Entrada inválida o formato no soportado (también responde 4xx) |
| `pendiente` | No se pudo procesar por fallo del proveedor; se reintenta |

---

## 3. Tipos de documento y campos por tipo

Seis tipos clínicos más `Otro`, que es el valor que toma cualquier documento fuera de alcance. El asterisco marca campo obligatorio: si falta, el caso es ambiguo por "campo obligatorio faltante" y va a revisión humana.

| Tipo | Campos |
|---|---|
| `Receta Medica` | paciente.nombre*, paciente.edad, medico.nombre*, medico.matricula*, fecha, institucion, medicamentos[]* (nombre*, dosis*, frecuencia, duracion, alto_riesgo), diagnostico, cie10_sugerido |
| `Informe de Estudio por Imagenes` | paciente.nombre*, paciente.edad, medico.nombre, medico.matricula, estudio_realizado*, hallazgos, conclusion*, diagnostico_principal, cie10_sugerido |
| `Informe de Laboratorio` | paciente.nombre*, paciente.edad, medico.nombre, medico.matricula, estudio_realizado*, hallazgos (valores y rangos), conclusion, diagnostico_principal, cie10_sugerido |
| `Orden de Solicitud de Procedimiento` | paciente.nombre*, paciente.edad, medico.nombre*, medico.matricula*, procedimiento_solicitado*, justificacion, diagnostico, cie10_sugerido, estudios_solicitados[] |
| `Epicrisis` | paciente.nombre*, paciente.edad, medico.nombre, medico.matricula, fecha_ingreso, fecha_egreso, motivo_ingreso, diagnostico_egreso*, cie10_sugerido, tratamiento, indicaciones_alta |
| `Certificado Medico` | paciente.nombre*, medico.nombre*, medico.matricula*, fecha*, motivo, dias_reposo, diagnostico (opcional, suele omitirse), cie10_sugerido |
| `Otro` | Cualquier documento que no encaje. Siempre va a revisión humana |

**`paciente.fecha_nacimiento`** es opcional en los seis tipos. Va en formato ISO, `AAAA-MM-DD`, sea
como sea que la escriba el documento, y es `null` si el documento no la trae. **Nunca se calcula a
partir de la edad**: eso sería inventar un dato, y además taparía justo la contradicción que el
campo existe para detectar. Si el documento trae edad y fecha de nacimiento, `validar.py` calcula la
edad a la fecha del documento, o a la de procesamiento si el documento no tiene fecha, y si difiere
de la declarada en más de un año marca AMB-2. Si falta cualquiera de las dos, no se compara.

**`cie10_sugerido`** se valida por el código contra `evals/generator/data/cie10.csv`. La descripción
puede variar según la edición de la clasificación, por ejemplo "Septicemia" o "Sepsis" para A41.9, y
no genera conflicto: lo que se compara es el código.

`especialidad` es texto libre sugerido por el modelo (por ejemplo `Radiologia / Neumonologia`). No se valida contra una lista en el MVP.

---

## 4. Prioridad, urgencia y alto riesgo

| `nivel_prioridad` | Definición |
|---|---|
| `Urgente` | Riesgo vital o hallazgo crítico. Va a Emergencia sin importar el tipo de documento |
| `Prioritario` | Resultado anormal que requiere seguimiento pronto, sin riesgo vital inmediato (por ejemplo "ampliar estudios", "control en 48 horas") |
| `Rutina` | Todo lo demás |

Urgencia se detecta por cuatro fuentes independientes y basta con una. **Regla A (ADR-002):** las fuentes 1, 2 y 4 son listas automáticas de `rules.yaml` y se aplican solo a los tipos de `deteccion_automatica_urgencia.aplica_a`, que son informes de estudio por imágenes, informes de laboratorio y órdenes de procedimiento. En recetas, epicrisis y certificados solo cuenta la fuente 3, porque en esos documentos las frases de alarma suelen ser instrucciones de alta o diagnósticos ya tratados.

1. Hallazgo crítico en la lista de `rules.yaml`: tromboembolismo pulmonar, infarto agudo de miocardio, accidente cerebrovascular, sepsis, neumotórax a tensión, hemorragia activa, hiperpotasemia severa. La lista crece con el golden set.
2. Palabra clave: urgente, inmediato, crítico, emergencia.
3. Juicio del modelo: `nivel_prioridad = Urgente` con justificación. Es la única fuente que aplica a todos los tipos.
4. Valor crítico de laboratorio (`valores_criticos_laboratorio` en `rules.yaml`), aunque el texto no diga urgente.

Un falso positivo de urgencia cuesta minutos de un médico. Un falso negativo cuesta un paciente. Por eso el objetivo de recall de urgencias en el golden set es 100 %.

Alto riesgo farmacológico, solo en recetas: los grupos A PINCH de la OMS, con la lista en `medicamentos_alto_riesgo` de `rules.yaml` y el rango de dosis de cada uno en `medicamentos.csv`. Una receta con alguno va a `Farmacia_Hospitalaria` con `requiere_auditoria_humana = true`; nunca a Emergencia, porque no hay una urgencia clínica.

---

## 5. Destinos

| Destino | Cuándo |
|---|---|
| `Cola_Emergencia_Medica` | Urgencia detectada, cualquier tipo. Genera `notificacion_generada` con canal `Alerta_Guardia_Medica` |
| `Farmacia_Hospitalaria` | Receta Medica |
| `Auditoria_Autorizaciones` | Orden de Solicitud de Procedimiento |
| `Historia_Clinica_Electronica` | Informe de Estudio (imágenes o laboratorio), Epicrisis, Certificado Medico |
| `Cola_Revision_Humana` | Ambigüedad, ilegibilidad, score bajo, tipo `Otro` |

Orden de decisión, de arriba hacia abajo, gana la primera que aplica:

1. Ilegible (legibilidad menor a 0,40): `Cola_Revision_Humana`, motivo "ilegible, solicitar nueva captura".
2. Urgencia: `Cola_Emergencia_Medica`. Si además hay ambigüedad o score bajo, `requiere_auditoria_humana = true`. La urgencia nunca se pierde por una ambigüedad.
3. Ambigüedad (cualquier categoría de la sección 6) o score menor a 0,60: `Cola_Revision_Humana`.
4. Destino por tipo. Si el score está entre 0,60 y 0,85 o hay alto riesgo farmacológico, `requiere_auditoria_humana = true`.

Umbrales iniciales, se calibran con el golden set en el sprint 3: automático 0,85, revisión 0,60, legibilidad mínima 0,40.

---

## 6. Categorías de ambigüedad

Cada caso ambiguo lleva exactamente una categoría principal en `justificacion_enrutamiento` y en la etiqueta del golden set. El informe de errores se lee por categoría.

| Código | Categoría | Ejemplo |
|---|---|---|
| `AMB-1` | Campo obligatorio faltante | Receta sin nombre de paciente; orden sin matrícula |
| `AMB-2` | Contradicción interna | Edad 52 con fecha de nacimiento de 1998; diagnóstico de fractura en una ecografía abdominal |
| `AMB-3` | Dosis fuera de rango o medicamento no identificable | "Amoxicilina 5000 mg cada 2 horas"; nombre de fármaco ilegible |
| `AMB-4` | Texto truncado o parcialmente ilegible | Documento cortado a la mitad; página con manchas que tapan la conclusión |
| `AMB-5` | Dos documentos en uno | Una receta y un certificado en el mismo archivo |
| `AMB-6` | Fuera del alcance del agente | Factura de farmacia; consentimiento informado; receta veterinaria; informe en inglés; pedido de interpretar una radiografía |

La comparación numérica solo corre cuando `medicamentos.csv` tiene `validar_dosis = si`. Siete
medicamentos se dosifican por peso, por coagulograma o por protocolo (enoxaparina, insulina,
alteplasa, cloruro de potasio, fentanilo, heparina y morfina) y no tienen rango por toma: no
generan AMB-3, pero siguen siendo de alto riesgo y su receta va a Farmacia con auditoría.

### Cómo viaja el motivo de AMB-6

AMB-6 no dice qué le falta al documento sino por qué el agente no decide sobre él, así que necesita
un motivo. `validar.py` lo escribe en el estado y `enrutar.py` lo repite en la justificación, sin
volver a calcularlo.

```json
"validacion": {
  "campos_faltantes": [],
  "conflictos": [],
  "errores": [],
  "categoria_amb": "AMB-6",
  "motivo_fuera_de_alcance": "no_clinico"
}
```

`motivo_fuera_de_alcance` toma una de las cinco claves de `fuera_de_alcance.motivos` en
`rules.yaml`: `no_clinico`, `tipo_no_soportado`, `paciente_no_humano`, `idioma_no_soportado` o
`pide_diagnostico`. Es `null` en cualquier otra categoría. El texto que ve la persona sale de esa
misma tabla del YAML, así que se cambia sin tocar código.

---

## 7. Los cuatro escenarios del golden set

Definiciones para etiquetar. Cada caso pertenece a uno solo.

| Escenario | Qué contiene el documento | Etiqueta esperada |
|---|---|---|
| Rutina | Completo, legible, sin hallazgo crítico, sin campo obligatorio faltante | Destino por tipo, `requiere_auditoria_humana = false`, `status = procesado`, prioridad `Rutina` o `Prioritario` |
| Urgencia | Hallazgo crítico o palabra clave de urgencia, datos completos | `Cola_Emergencia_Medica`, `requiere_auditoria_humana = false`, notificación generada, prioridad `Urgente` |
| Ambigüedad | Una categoría AMB-1 a AMB-6, sin hallazgo crítico | `Cola_Revision_Humana`, `requiere_auditoria_humana = true`, `status = revision_humana`, categoría en la justificación |
| Urgencia con ambigüedad | Hallazgo crítico más una categoría AMB | `Cola_Emergencia_Medica`, `requiere_auditoria_humana = true`, notificación generada, categoría en la justificación |

Escenario extra para la demo, dentro de Rutina: receta con medicamento de alto riesgo, etiqueta `Farmacia_Hospitalaria` con `requiere_auditoria_humana = true`.

El conjunto vive en `evals/golden/plan_golden.csv`: 45 elementos, 30 documentos de los seis tipos, 7 casos fuera de alcance, 8 recetas manuscritas y 12 imágenes degradadas derivadas de los documentos. El reparto por escenario y por persona está en esa tabla, con una fila por elemento.

---

## 8. Formato de la etiqueta en el golden set

El conjunto de prueba vive en `evals/golden/plan_golden.csv`: una fila por elemento, con la etiqueta esperada y las columnas de su revisión. `evals/run.py` lee esa tabla, busca en `evals/golden/files/` todas las variantes que existan de cada elemento (texto, JSON, PDF e imagen degradada) y evalúa cada una por separado.

La etiqueta de la fila describe el documento legible. De una imagen degradada se espera otra cosa, porque manda el umbral de legibilidad: en nivel medio, revisión humana con AMB-4; en nivel severo, revisión humana sin comparar el tipo, porque el grafo no llega a clasificar. Está explicado en `evals/golden/README.md`.

## 9. Almacenamiento

Un bucket privado con prefijos por estado: `mediflow-dev` en desarrollo, con una carpeta por persona, y el de producción, que solo acepta escrituras desde la VM. Hasta el despliegue del sprint 3 el mismo layout se escribe en `./data/` con `STORAGE_BACKEND=local`. Sin Autonomous AI Database en el MVP: la cola de revisión y el estado de la API viven en SQLite en un volumen de la VM, y el JSON en el bucket es la fuente de verdad.

```
recibidos/{documento_id}.{ext}                  original, antes de procesar
procesados/urgentes/{documento_id}.json
procesados/farmacia/{documento_id}.json
procesados/autorizaciones/{documento_id}.json
procesados/historia_clinica/{documento_id}.json
auditoria_humana/{documento_id}/original.{ext}
auditoria_humana/{documento_id}/extraccion.json
auditoria_humana/{documento_id}/resolucion.json   decisión del auditor: revisor, fecha, motivo, correcciones
rechazados/{documento_id}.json
```

---

## 10. Decisiones cerradas

Las preguntas que abrió este contrato ya están resueltas y registradas en `docs/decisions.md`, cada
una con su motivo y la alternativa descartada: los seis tipos y sus campos obligatorios, el informe
de laboratorio como tipo propio, las seis categorías de ambigüedad, la regla de que la urgencia
nunca se pierde por una ambigüedad, los umbrales 0,85 / 0,60 / 0,40, y SQLite en la VM con el bucket
como fuente de verdad.

Sigue vigente una regla de trabajo: cualquier cambio de nombre de campo se hace en `contrato.py` y
en este documento en el mismo PR, y el test `test_ejemplo_del_brief` tiene que seguir pasando.

---

## 11. Revisión humana

Un documento espera a una persona cuando sale del grafo con `requiere_auditoria_humana = true`: en
`Cola_Revision_Humana`, en `Cola_Emergencia_Medica` con ambigüedad, o en el destino de su tipo con alto
riesgo farmacológico o con un score entre 0,60 y 0,85. La urgencia ya se avisó al entrar: la revisión no
la frena. La API de la cola es N2-04, el panel del auditor es N2-06 (`ui/pages/3_Auditoria.py`) y la
reanudación del grafo con la decisión es N2-05.

### 11.1 Qué espera en la cola

`persistir.py` escribe `auditoria_humana/{documento_id}/extraccion.json` para todo documento con
`requiere_auditoria_humana = true`, además de la copia por destino de la sección 9, y copia el
original al lado, en `original.{ext}`. En local, la carpeta es la de `agent/storage/local.py`:
`./data/{bucket}/auditoria_humana/`.

En la rama de integración, persistencia, API, checkpoints y resoluciones usan el mismo
backend (`STORAGE_BACKEND`) y `bucket_actual()`. La cola incluye también documentos urgentes
que requieren auditoría. El original de una carga se conserva en `recibidos/` y se copia
junto a la extracción. La integración todavía requiere revisión antes de pasar a `develop`.

`extraccion.json` es la salida de la sección 2, con los mismos nombres de campo, más tres que el panel
necesita:

| Campo | Contenido |
|---|---|
| `validacion` | El bloque de la sección 6 |
| `texto` | El texto que leyó el agente, o null si no llegó a leerlo, como en una imagen ilegible |
| `legibilidad` | De 0 a 1, o null en un documento de texto |
| `revision_version` | Versión de revisión, comienza en 1 y aumenta tras cada decisión |

Las rutas de campo son relativas a `datos_extraidos` y van con punto: `paciente.nombre`,
`medico_solicitante.matricula`. Son las mismas en `validacion.campos_faltantes`, en
`evidencias[].campo` y en las correcciones. Solo `campos_faltantes` señala un medicamento por su
índice, como `medicamentos[0].dosis`; las correcciones nunca usan índices (11.3).

### 11.2 Endpoints

| Método y ruta | Qué hace | Respuestas |
|---|---|---|
| `GET /queue/human` | Lista los documentos que tienen `extraccion.json` y todavía no tienen `resolucion.json` | 200 con `{"items": [{"documento_id", "extraccion"}]}` |
| `POST /audit/{documento_id}` | Reanuda el checkpoint y persiste la decisión | 200 con `documento_id`, `resolucion`, `status`, `decision_enrutamiento` y `revision_version`; 404 sin checkpoint; 409 por versión desactualizada o decisión repetida; 422 por decisión inválida; 503 por fallo de persistencia |
| `GET /audit/{documento_id}/original` | Devuelve el original con su tipo de contenido, para verlo al lado de la extracción. Mientras no exista, el panel muestra `texto` | 200 con el archivo; 404 si no hay |

El `documento_id` va codificado en la ruta (`DOC#7` es `DOC%237`). El panel ordena la cola: primero las
urgencias, después lo prioritario, después el resto.

### 11.3 La decisión

```json
{
  "accion": "corregir",
  "revisor": "Camila",
  "motivo": "Confirmado con el médico: 500 mg cada 8 horas",
  "correcciones": {
    "medicamentos": [
      {"nombre": "Amoxicilina", "dosis": "500 mg", "frecuencia": "cada 8 horas", "duracion": null}
    ]
  }
}
```

| Campo | Regla |
|---|---|
| `accion` | `aprobar`, `corregir` o `rechazar`. Rechazar es una acción del auditor, no un destino (ADR-004) |
| `revisor` | Quién decide. Obligatorio y no vacío |
| `motivo` | Por qué. Obligatorio y no vacío; al aprobar sin escribir nada, el panel manda "Extracción verificada contra el documento original." |
| `correcciones` | Solo con `corregir`, y solo los campos que cambiaron, con su valor nuevo. Con las otras dos acciones va `null` |

La API rechaza con 422 un `revisor` o un `motivo` vacíos, y `correcciones` con una acción que no sea
`corregir`. Las acciones sin correcciones conservan `null`. El panel envía `revision_version`
con la versión de la extracción mostrada. Una versión desactualizada devuelve 409 y exige recargar la cola.

Cómo se escriben las correcciones:

- Un campo suelto, con su ruta: `"paciente.nombre": "Rodríguez, Ana María"`. Un valor `null` borra el
  dato.
- Una lista va entera: si cambia un medicamento, va `medicamentos` con la lista completa. Nunca por
  índice.
- La clasificación, con el prefijo `clasificacion.`: `"clasificacion.tipo_documento": "Receta Medica"`,
  `"clasificacion.nivel_prioridad": "Urgente"`.
- Un medicamento corregido no lleva `alto_riesgo`: esa marca la calcula siempre el grafo con
  `rules.yaml`, y el auditor no la cambia.

`resolucion.json` guarda el cuerpo de la decisión más `fecha`, en UTC: quién, cuándo, qué y por qué.

### 11.4 Después de la decisión

| Acción | Qué hace el grafo al reanudarse |
|---|---|
| `aprobar` | Sigue con la extracción tal cual: lo que estaba en revisión va al destino de su tipo, y lo que ya tenía destino, como una urgencia, se queda ahí |
| `corregir` | Aplica las correcciones, calcula `alto_riesgo` con `rules.yaml`, vuelve a validar y enruta con la sección 5 |
| `rechazar` | Guarda el documento en `rechazados/` con el motivo y no sigue |

Si después de corregir el documento vuelve a necesitar revisión, la reanudación renombra la decisión
anterior a `resolucion_1.json` (después `resolucion_2.json`, y así) y escribe una `extraccion.json`
nueva: el documento vuelve a la cola con su historia.

La respuesta del `POST` incluye el destino nuevo cuando continúa el procesamiento. Si el documento
vuelve a revisión, `status` es `revision_humana`; si se rechaza, `decision_enrutamiento` es `null`.
Los documentos creados antes de habilitar checkpoints necesitan reprocesamiento controlado.
Un fallo después de la decisión se reintenta con el mismo cuerpo para evitar aplicarla dos veces.

### 11.5 Privacidad

La extracción, el texto y las correcciones son datos clínicos: viven en el bucket privado y no se
escriben en registros ni en la traza. El panel muestra el documento completo, porque el auditor lo
necesita, y sus mensajes de error no repiten lo enviado.
