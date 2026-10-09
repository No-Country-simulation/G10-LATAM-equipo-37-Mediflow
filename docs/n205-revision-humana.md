# N2-05: pausa y reanudación

Implementación sobre PR #3 actualizado con develop 6688cc9, siguiendo la sección 11
propuesta en PR #26. No fusionar esta rama dentro de la rama de urgencia: primero #3
a develop y luego cambiar la base de este PR a develop.

`run_triage` usa SqliteSaver y un thread_id por documento. Después de persistir y
llamar a notificar, todo caso con requiere_auditoria_humana queda en interrupt.
POST /audit/{id} reanuda el mismo checkpoint con Command(resume=...).

- Aprobar conserva extracción, lleva la cola al destino de su tipo y conserva una
  urgencia ya enrutada. Otro no tiene destino: requiere corregir tipo o rechazar.
- Corregir admite rutas del contrato y listas completas, calcula alto_riesgo,
  revalida, puntúa, detecta urgencia y enruta. No llama al modelo de nuevo.
- Si sigue necesitando revisión, guarda resolucion_N.json y una extracción nueva.
- Rechazar persiste en rechazados/ y termina, sin destino operativo nuevo.
- Resoluciones cerradas devuelven 409. revision_version es opcional por compatibilidad
  con PR #26; se recomienda que el panel la envíe para detectar decisiones obsoletas.
- Un fallo de almacenamiento mantiene la operación pendiente. Repetir la misma decisión
  continúa desde el checkpoint sin aplicar otra vez las correcciones.

## Almacenamiento y privacidad

MEDIFLOW_CHECKPOINT_DB define el archivo; por defecto data/checkpoints.sqlite3.
SQLite guarda referencias SHA-256. El contenido serializado está en
{bucket}/checkpoints/{sha}.bin, en el backend privado configurado. Restaurar requiere
la base SQLite y estos objetos; la base sola no basta. No se utiliza pickle.
La prueba de privacidad comprueba ausencia de un nombre de prueba en SQLite;
no sustituye la prueba de fuga completa de N2-10.

La cola local sigue ./data/{bucket}/auditoria_humana. La extracción del panel incluye
clasificación, datos, decisión, evidencias, validación, texto, legibilidad y versión.
Los originales PDF/imagen dependen de ruta_original de la ingesta/persistencia.
No se sustituye una imagen original por texto extraído.

## Integración pendiente de revisión

- Coordinar con #28 (Sabrina/Cristian): el modelo de decisión y POST /audit cambian
  aquí; conservar su GET /audit/{id}/original al integrar. La ruta local coincide.
- Néstor revisa grafo y reanudación; Sabrina, el endpoint. Camila, el panel y contrato.
- Notificar sigue siendo el nodo del equipo, actualmente stub: no se afirma entrega
  de email o Slack. Un transporte real debe usar clave de idempotencia por documento.
- Un mutex SQLite serializa operaciones en el MVP. No está diseñado para múltiples
  réplicas ni alto tráfico; el bloqueo puede esperar hasta 30 segundos.
- No se prueban OCI, permisos de bucket, despliegue, autenticación ni el panel en vivo.
  La cola de #28 es local; no declarar el flujo OCI completo sin esa integración.
- Casos antiguos sin checkpoint requieren reprocesar con un nuevo ID; no se inventa
  estado a partir de extracciones incompletas.

## Validación

Pruebas con SQLite y filesystem temporales, sin LLM/OCI: reinicio, aprobación,
corrección, rechazo, repetición, versión obsoleta, reentrada con historial, AMB-6,
alto riesgo recalculado, urgencia antes de pausa y recuperación de fallo al persistir.
API, validación, urgencia y enrutamiento se verifican junto con el paquete.

Referencias técnicas: https://docs.langchain.com/oss/python/langgraph/interrupts
y https://docs.langchain.com/oss/python/langgraph/persistence.
# Seguimiento del 8/10

La prueba de restauración copia SQLite con su API de backup y copia los objetos
del bucket local a otro directorio. El grafo restaurado conserva la pausa y puede
resolverla; copiar solo SQLite falla por falta de los objetos. Esta evidencia es
local, no acredita el job diario ni los permisos de OCI de N2-10.

Integración pendiente con Carlos y Cristian: PR #29 cambia la elección de bucket
por entorno. `revision.py`, `checkpoint_payload.py` y `local_audit.py` deben usar
la misma función `bucket_actual()` que acuerden para persistir y la cola. Hasta
esa integración esta rama usa OCI_BUCKET; no mezclar configuraciones con #29.
