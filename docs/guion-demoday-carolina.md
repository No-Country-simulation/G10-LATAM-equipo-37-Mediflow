# DemoDay: borrador de guion de 5 minutos

Carolina con Diana. Preparado el 9/10/2026. Presentación preliminar; el criterio de F-08 se cumple
con dos ensayos cronometrados de la demo integrada, aún pendientes para el 22–26/10.

| Tiempo | Diapositiva / acción | Responsable propuesto |
|---|---|---|
| 0:00–0:35 | Presentación de MediFlow | Carolina |
| 0:35–1:15 | Problema documental | Carolina |
| 1:15–1:55 | Intervención del auditor | Carolina |
| 1:55–2:30 | Demo: documento de rutina | Diana opera; Carolina explica |
| 2:30–3:10 | Demo: urgencia y revisión si corresponde | Diana opera; Carolina explica |
| 3:10–4:10 | Demo: ambigüedad, corrección y reanudación | Diana opera; Carolina explica |
| 4:10–5:00 | Validación, límites y siguiente paso | Carolina |

## Texto de apoyo

**Inicio.** Hola, soy Carolina y presento MediFlow con el equipo 37. Trabajamos sobre el recorrido
de un documento clínico: leerlo, extraer la información y encaminarlo al destino correspondiente.
Cuando falta información o aparece una ambigüedad, el auditor puede intervenir. Hoy mostramos
ese recorrido con documentos sintéticos.

**Problema.** Una receta puede omitir un dato, contener una ambigüedad o llegar como una imagen
que no se puede leer. El sistema necesita reconocer esa incertidumbre. MediFlow separa la
extracción, la validación y el enrutamiento para que el caso quede disponible para revisión
cuando no hay evidencia suficiente.

**Revisión.** El grafo conserva el estado antes de esperar al auditor. El panel permite comparar
el original con la extracción. Aprobar continúa el recorrido. Corregir vuelve a validar los datos.
Rechazar registra el motivo y cierra el caso. Si queda otro problema, el documento vuelve a la
cola con una nueva versión y conserva el historial.

**Demo.** Primero mostramos un documento de rutina y su destino. Después, un caso urgente:
verificamos la prioridad y si también necesita revisión. Finalmente abrimos un caso ambiguo,
contrastamos un campo con el original y enviamos la corrección. Mostramos el resultado y
actualizamos la cola. Si persiste una ambigüedad, explicamos por qué vuelve a revisión.

**Cierre.** La integración cuenta con pruebas de reanudación, control de versiones e historial,
y de restauración local del estado. La medición con modelos reales y la validación en OCI
siguen pendientes. El siguiente paso es completar esas verificaciones y ensayar el recorrido
con el equipo. La demostración no constituye una validación para uso con pacientes reales.

## Preparación de la demo

- Usar un commit integrado y aceptado por el equipo. Registrar el commit y la configuración.
- Elegir con Diana tres casos sintéticos revisados; no improvisar correcciones clínicas.
- Usar IDs nuevos por ensayo: un ID existente recupera su checkpoint en vez de crear otro caso.
- Comprobar API, panel, original y destinos antes de presentar. El archivo
  `ui/pages/3_Auditoria.py` puede ejecutarse con `streamlit run` para verificar el panel.
- La API se inicia con `uvicorn api.main:app`. Configurar las variables del entorno de prueba
  y el volumen de SQLite. `USE_LLM=false` permite pruebas deterministas, pero no mide el modelo.
- Mostrar notificaciones externas solamente si el despliegue ya está verificado.
- Como contingencia, el panel tiene modo demostración. Indicar que ese modo no envía decisiones
  a la API ni prueba la reanudación real. No presentarlo como sustituto de la demo integrada.

## Registro de ensayos pendiente

| Ensayo | Fecha / commit | Duración total | Incidencias | Resultado |
|---|---|---|---|---|
| 1 | Pendiente | Pendiente | Pendiente | No realizado |
| 2 | Pendiente | Pendiente | Pendiente | No realizado |

Actualizar la diapositiva de validación después de la evaluación real. No sustituir métricas
de exactitud por el número de pruebas de software.
