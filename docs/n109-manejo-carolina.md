# N1-09: respaldo heurístico de AMB-5

Este PR se limita al clasificador en modo reglas (incluida la caída por fallo del
proveedor). Escribe `clasificacion["multiples_documentos"]` como booleano usando
encabezados documentales explícitos. El clasificador LLM no pide ni produce otra
señal de ambigüedad: la principal es `state["ambiguedad"]`, desde extracción.

El consumidor y sus prioridades están en #120 de Cristian: respaldo solo si el
modelo no informó AMB-4 ni AMB-5; AMB-6 conserva prioridad. Fusionar #120 antes de
este PR y verificar la integración. Este PR no modifica validar.py.

La heurística detecta encabezados de tipos distintos o títulos repetidos con
pacientes distintos. Repetir el encabezado del mismo paciente o mencionar otro
tipo en prosa no basta. Dos documentos del mismo tipo/paciente o sin encabezados
requieren la señal del modelo. No se afirma precisión sin evaluación real.

El rechazo de entrada vacía y la auditoría humana quedan en #86. Diana mantiene
los fixtures y la evaluación de casos borde. Esta separación evita incluir aquí
cambios de API y evita duplicar la decisión del modelo en clasificar y extraer.
