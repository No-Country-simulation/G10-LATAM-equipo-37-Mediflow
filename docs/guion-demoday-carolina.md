# DemoDay: borrador de 5 minutos — Carolina y Diana

Actualizado 14/10/2026 tras el mensaje de María. Propuesta para acordar con Diana,
no ensayo realizado ni evidencia de producción. Proyecto listo el viernes 16/10;
fin de semana solo ajustes. María prepara README final y entregables; no subir aún
nada a la plataforma. Completar al menos un ensayo previo; F-08 pide dos.

| Tiempo | Qué mostramos | Responsable propuesto |
|---|---|---|
| 0:00–0:40 | Problema: documentos clínicos heterogéneos y revisión manual | Diana |
| 0:40–1:20 | Agente: clasificación, extracción con evidencia, reglas y revisión humana | Carolina |
| 1:20–2:00 | Rutina: GS-28 y destino operativo | Diana opera, Carolina explica |
| 2:00–2:50 | Urgencia: GS-07, prioridad y alerta n8n → Slack | Carolina opera, Diana explica |
| 2:50–3:50 | Ambigüedad: GS-06, revisión/corrección y reanudación | Carolina opera y explica |
| 3:50–4:35 | Evaluación final: modelo elegido, métricas y límites medidos | Diana |
| 4:35–5:00 | Cierre: revisión humana y alcance del prototipo | Ambas |

## Texto de apoyo

Diana: «MediFlow organiza el recorrido de documentos clínicos. El desafío es
reconocer qué documento llegó, extraer lo que realmente dice y saber cuándo
necesita intervención humana. Usamos documentos sintéticos para esta demo».

Carolina: «El agente separa clasificación, extracción, validación y enrutamiento.
Cada dato se apoya en evidencia del documento. Si falta información o existe una
ambigüedad, interviene un revisor. No reemplaza el diagnóstico ni la decisión
clínica del profesional».

Rutina: mostrar el identificador sintético, tipo y destino. Urgencia: mostrar la
prioridad, destino y recepción real de la alerta sin datos del paciente. Ambigüedad:
contrastar el campo con el documento, corregir y mostrar la nueva validación.
GS-04 queda como respaldo adicional de alto riesgo, coordinado con el video #105.

Resultados: insertar únicamente las métricas publicadas de N3-01 y su commit/modelo.
No confundir tests de software con precisión del modelo. Si la corrida no está,
decir «evaluación pendiente» y no presentar cifras preliminares como finales.

## Verificación antes del ensayo

- Confirmar versión desplegada y modelo activo con Carlos. Cadena acordada para
  demo: Groq Qwen Vision → Groq gpt-oss → Gemini Flash. DeepSeek/Mistral solo se
  comparan en costos; no anunciar una cadena como desplegada sin comprobarla.
- Probar una vez cada escenario en la URL pública con el equipo; guardar resultado,
  fecha, commit y modelo. Evitar pruebas masivas y cuidar el cupo.
- Confirmar que #35/#120 y revisión humana están integrados antes de prometerlos.
- Verificar alerta n8n → Slack en menos de un minuto con Alessandro/Sabrina y
  Carlos/Néstor; falla del webhook no debe detener el documento.
- Verificar ausencia de datos del paciente en pantalla, límite de pedidos y caída
  a reglas al agotar cupo. Si se usa fallback, identificarlo claramente.
- Coordinar con Diana horario de ensayo y quién comparte pantalla. Registrar duración,
  incidentes y ajustes en dos ensayos; todavía no se realizaron.

## Plan B

Tener abierto el video #105 de Alessandro y Sabrina, o capturas de una corrida
verificada. Identificarlas como grabación y explicar el fallo en vivo. Si a los
15 segundos no hay respuesta o se agota el cupo, pasar a esa evidencia. El video,
las capturas y su funcionamiento están pendientes de confirmación del equipo.
