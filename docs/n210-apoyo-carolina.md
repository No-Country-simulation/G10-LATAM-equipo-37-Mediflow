# N2-10: apoyo de Carolina a privacidad

Seudonimización HMAC-SHA256 con clave externa y minimización de trazas por lista
permitida. El texto libre (justificaciones, conflictos detallados, evidencias y
rutas) permanece solo en el estado operativo y en los archivos privados que
necesita el auditor. Las trazas guardan enums, scores, banderas y cantidades;
no duplican los detalles clínicos. No se modifican las decisiones del agente.

MEDIFLOW_CLAVE_SEUDONIMO habilita una referencia estable de paciente en la traza.
Sin clave no se genera referencia ni se utiliza una clave por defecto. La clave
se configura fuera del repo. Cambiarla cambia las referencias. Seudonimizar no
equivale a anonimizar: el acceso a las trazas también necesita control.

Los logs de clasificar, extraer, persistir y adapter conservan la clase del error,
sin copiar el mensaje de la excepción ni las rutas del documento. Los modelos
mostrados en las trazas se limitan a los configurados en LLM_PRIMARY/FALLBACKS y stub.

Pruebas: nombres, DNI e historia clínica centinela en detalle libre, trazas
históricas, rutas y errores no aparecen en la traza/log generado. El estado
operativo no cambia. La misma identidad produce la misma referencia y otra
clave produce otra referencia.

Límites y coordinación con Sabrina:

- Este PR es apoyo al paquete #64; no lo cierra. Falta el job diario, la prueba
  de restauración en OCI y la verificación de permisos/controles del despliegue.
- #30 contiene la prueba de restauración local de SQLite y objetos privados.
- No se ejecutó el golden completo con proveedor real ni se certifica fuga cero
  de los 45 casos. Faltan documentos/revisiones y la corrida de Camila.
- Las trazas históricas se limpian al pasar por step; no migra archivos antiguos.
- Logs de servidores HTTP, bibliotecas externas y herramientas de observabilidad
  requieren revisión separada. No activar logging de prompts/respuestas.
- Néstor debe revisar el resumen por nodo para N3-02: los motivos clínicos ya no
  se copian a la vista general de trazas; el auditor mantiene el detalle completo.
- Integrar los cambios de clasificar con #35 y persistir con #29 sin perder sus
  campos ni su selección de bucket. Son modificaciones a bloques distintos.

No se cambian los estados de docs/privacidad.md a "Hecho" sin evidencia completa.
