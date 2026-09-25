# Contrato de MediFlow

Versión 1.0 · 22 de septiembre de 2026 · Incorpora la regla A de urgencia (ADR-002), los valores críticos de laboratorio como cuarta fuente de urgencia y el alto riesgo solo en recetas. El nombre del campo del paciente queda como estaba hasta que la instructora responda.

Fuente del borrador: `agent/schemas/contrato.py`, `agent/schemas/documentos.py` y `agent/rules/rules.yaml` del esqueleto, más el ejemplo de entrada y salida del brief. Los nombres de campo siguen al brief, con una excepción acordada por el equipo: `paciente.nombre` en lugar de `nome`, para que todo el contrato esté en español.

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

`POST /triage/upload` multipart con `documento_id`, `canal_origen` y `archivo`. Formatos: `pdf`, `png`, `jpg`, `jpeg`, `txt`. Tamaño máximo 25 MB. Formato no soportado: error 415. Tamaño excedido: error 413.

El archivo original se guarda en `recibidos/{documento_id}.{ext}` antes de llamar a cualquier modelo.

---

## 2. Salida

Idéntica al ejemplo del brief, más cuatro campos propios al final.

| Campo | Contenido |
|---|---|
| `status` | `procesado`, `revision_humana`, `rechazado`, `pendiente` |
| `documento_id` | El recibido |
| `clasificacion` | `tipo_documento`, `especialidad`, `nivel_prioridad`, `score_confianza_clasificacion` (0 a 1) |
| `datos_extraidos` | `paciente {nombre, edad}`, `medico_solicitante {nombre, matricula}`, `estudio_realizado`, `diagnostico_principal`, `cie10_sugerido`, `medicamentos []`, `estudios_solicitados []` |
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

Seis valores posibles para `tipo_documento`. El asterisco marca campo obligatorio: si falta, el caso es ambiguo por "campo obligatorio faltante" y va a revisión humana.

| Tipo | Campos |
|---|---|
| `Receta Medica` | paciente.nombre*, paciente.edad, medico.nombre*, medico.matricula*, fecha, institucion, medicamentos[]* (nombre*, dosis*, frecuencia, duracion, alto_riesgo), diagnostico, cie10_sugerido |
| `Informe de Estudio por Imagenes` | paciente.nombre*, paciente.edad, medico.nombre, medico.matricula, estudio_realizado*, hallazgos, conclusion*, diagnostico_principal, cie10_sugerido |
| `Informe de Laboratorio` | paciente.nombre*, paciente.edad, medico.nombre, medico.matricula, estudio_realizado*, hallazgos (valores y rangos), conclusion, diagnostico_principal, cie10_sugerido |
| `Orden de Solicitud de Procedimiento` | paciente.nombre*, paciente.edad, medico.nombre*, medico.matricula*, procedimiento_solicitado*, justificacion, diagnostico, cie10_sugerido, estudios_solicitados[] |
| `Epicrisis` | paciente.nombre*, paciente.edad, medico.nombre, medico.matricula, fecha_ingreso, fecha_egreso, motivo_ingreso, diagnostico_egreso*, cie10_sugerido, tratamiento, indicaciones_alta |
| `Certificado Medico` | paciente.nombre*, medico.nombre*, medico.matricula*, fecha*, motivo, dias_reposo, diagnostico (opcional, suele omitirse), cie10_sugerido |
| `Otro` | Cualquier documento que no encaje. Siempre va a revisión humana |

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

Reparto de v0, 40 casos en español: 20 rutina (4 por tipo, incluida una receta de alto riesgo), 8 urgencia (3 informes de imágenes, 2 epicrisis, 2 órdenes, 1 laboratorio), 8 ambigüedad (mínimo uno por categoría AMB), 4 urgencia con ambigüedad.

---

## 8. Formato de la etiqueta en el golden set

Una línea JSONL por caso en `evals/golden/golden_v0.jsonl`:

```json
{
  "documento_id": "SYN-0007",
  "tipo_archivo": "TEXTO",
  "idioma": "es",
  "escenario": "urgencia_ambiguedad",
  "categoria_ambiguedad": "AMB-1",
  "fuente": "generador",
  "documento_texto": "...",
  "esperado": {
    "tipo_documento": "Informe de Estudio por Imagenes",
    "nivel_prioridad": "Urgente",
    "destino_principal": "Cola_Emergencia_Medica",
    "requiere_auditoria_humana": true,
    "datos_extraidos": {
      "paciente": {"nombre": null, "edad": 64},
      "medico_solicitante": {"nombre": "Dr. Julián Restrepo", "matricula": "88213"},
      "estudio_realizado": "Angiotomografía de tórax",
      "diagnostico_principal": "Tromboembolismo pulmonar agudo",
      "cie10_sugerido": "I26.9",
      "medicamentos": [],
      "estudios_solicitados": []
    }
  },
  "revisado_por": []
}
```

`escenario` toma `rutina`, `urgencia`, `ambiguedad`, `urgencia_ambiguedad`. `categoria_ambiguedad` es null salvo en los dos últimos. Sin dos nombres en `revisado_por`, el caso no cuenta para las métricas.

---

## 9. Almacenamiento

Un solo bucket privado, `mediflow-documentos-clinicos`, con prefijos por estado. Sin Autonomous AI Database en el MVP: la cola de revisión y el estado de la API viven en SQLite en un volumen de la VM, y el JSON en el bucket es la fuente de verdad.

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

## 10. Decisiones que EQU-01 debe cerrar hoy

1. ¿Se aceptan los seis tipos y los campos obligatorios de la sección 3?
2. ¿`Informe de Laboratorio` es un tipo aparte o se funde con `Informe de Estudio por Imagenes` como "Informe de Estudio"?
3. ¿Se aceptan las cinco categorías de ambigüedad y la regla "la urgencia nunca se pierde por una ambigüedad"?
4. ¿Umbrales iniciales 0,85 / 0,60 / 0,40?
5. ¿SQLite en la VM para cola y estado, con el bucket como fuente de verdad?
6. Cualquier cambio de nombre de campo se hace en `contrato.py` y en este documento en el mismo PR. El test `test_ejemplo_del_brief` sigue pasando o el PR no se mergea.
