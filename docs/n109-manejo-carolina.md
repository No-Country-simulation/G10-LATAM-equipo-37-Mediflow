# N1-09: manejo de los fallos reportados por Diana

POST /triage rechaza texto vacío o compuesto solo por espacios antes de invocar
el grafo (422), para TEXTO y JSON. La ingesta por archivo conserva su tratamiento.

Clasificación ahora produce multiples_documentos, que validación consume para
AMB-5. Conserva la marca anterior _multiples_documentos por compatibilidad.
La respuesta del LLM solo acepta true booleano. El fallback detecta encabezados
explícitos de documentos distintos, o títulos repetidos con pacientes distintos.

Límite: es una heurística conservadora, no segmentación universal. Una mención
en prosa o repetir el encabezado con el mismo paciente no basta. Dos documentos
del mismo tipo/paciente o sin encabezados requieren la señal del modelo y
evaluación con los casos de Diana. No se afirma precisión sin esa corrida.

Diana mantiene fixtures, tabla y test_casos_borde.py. Esta rama añade regresiones
dirigidas en test_manejo_borde_carolina.py para los dos defectos de implementación.
Revisar con Diana, Carlos (clasificador) y Cristian (validación).
