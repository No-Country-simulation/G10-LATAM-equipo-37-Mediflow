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

## Respaldo de la cola incorporada por #94 (13/10)

La utilidad `python -m agent.storage.respaldo crear --destino respaldo.zip` incluye
`triage_results.sqlite3` cuando existe en la ruta configurada por `MEDIFLOW_TRIAGE_DB`,
además de checkpoints y objetos. Usa la API de backup SQLite, registra hashes y
comprueba integridad de ambas bases al restaurar. Sigue aceptando respaldos v1.

Para un punto de recuperación coherente entre ambas bases, detener la recepción en
API y worker y esperar a que terminen los trabajos antes de ejecutar el respaldo.
El mutex del runtime no cubre la escritura posterior de la cola: con tráfico activo
las copias SQLite son válidas individualmente, pero no constituyen una transacción
atómica entre ambas bases y los objetos. El job de Sabrina debe respetar esta ventana.
Si todavía no existe la base de resultados, no se crea una base vacía para respaldarla.
En el despliegue que ya usa la cola, verificar que el manifiesto la incluya.

Restaurar siempre en un directorio nuevo y configurar MEDIFLOW_CHECKPOINT_DB,
MEDIFLOW_TRIAGE_DB y la raíz de objetos hacia los archivos restaurados antes de arrancar.
La prueba local verifica que la fila de cola se recupera idéntica; OCI sigue pendiente.
