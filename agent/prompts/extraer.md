Extrae los datos del siguiente documento clínico de tipo "{{tipo_documento}}". Devuelve SOLO un JSON que cumpla este esquema:

{{esquema_json}}

Reglas:
- Copia los valores tal como aparecen; no completes con conocimiento externo.
- Para cada campo agrega "evidencia": el fragmento exacto del documento que lo sustenta, o null.
- Si un campo no está en el documento, déjalo en null. No inventes.
- cie10_sugerido: código CIE-10 más probable para el diagnóstico principal, o null.
- Marca alto_riesgo en medicamentos anticoagulantes, opioides, insulina y quimioterápicos.

Documento:
{{documento}}
