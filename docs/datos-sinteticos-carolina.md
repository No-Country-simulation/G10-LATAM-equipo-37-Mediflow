# Procedencia de los documentos de Carolina

GS-03, GS-11, GS-19, GS-27 y FA-05 son datos sintéticos de evaluación: pacientes, profesionales, matrículas, historias clínicas e institución inventados. No representan atenciones reales ni tienen validez asistencial. Esta declaración queda fuera del contenido evaluado para evitar pistas de clasificación.

El 6/10/2026 se retiraron las marcas de prueba de los cinco TXT y se regeneraron las variantes con generate.py y degradar.py de develop 9a67dcc. No se modificaron datos clínicos, fechas, dosis, diagnósticos ni etiquetas esperadas. La instrucción adversarial de FA-05 se conserva como dato de evaluación.

Se invocaron las funciones del generador sobre rutas explícitas porque RAIZ en esos scripts resuelve a evals/. Para GS-27 se creó un PDF intermedio temporal con el mismo generador, evitando la fuente de respaldo Linux en Windows. Ese PDF no se incorpora al conjunto. Se aplicó Pillow con semilla 37, GS-11 media y GS-27 leve, sin cambiar los parámetros de degradación. No se modifican los scripts compartidos.

Verificación: el texto extraído de los PDF coincide con el TXT normalizando espacios; una página por PDF. Las imágenes se generan de esos mismos contenidos y requieren revisión humana. No se ejecutó un modelo ni se midió precisión OCR. M3 y su etiqueta permanecen intactos; esta actualización cubre los cinco documentos solicitados.
