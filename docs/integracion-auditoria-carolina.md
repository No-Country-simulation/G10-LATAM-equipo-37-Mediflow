# Integración de auditoría humana

Rama: `integration/carolina-auditoria-completa`. Preparada el 8–9 de octubre de 2026.
Es una propuesta de integración para revisión, no un despliegue ni el cierre de los paquetes.

## Cambios que reúne

Se integraron las ramas de #3 (triaje), #30 (revisión durable), #35 (casos borde),
#85 (privacidad), #29 (buckets), #28 (API de auditoría) y #26 (panel), sobre `develop`.
Se conservaron los commits de sus autores. Las ramas originales no se modificaron.

Al combinarlas se corrigieron estos problemas:

- Persistencia, API, resoluciones y payloads de checkpoints usaban buckets o backends distintos.
  Ahora comparten `STORAGE_BACKEND` y `bucket_actual()`.
- La extracción persistida para auditoría omitía campos que necesitaba el panel.
- La carga de archivos no conservaba el original. Se guarda con una clave por contenido y se
  copia junto a la extracción. Reintentar un ID no sustituye el original de su checkpoint.
- El panel no enviaba la versión de revisión. Ahora la API detecta una decisión desactualizada.
- Una copia fallida del original podía reportar persistencia exitosa. El grafo durable se detiene
  y permite reintentar antes de consumir la revisión.
- El listado de OCI no recorría las páginas. Ahora continúa hasta completar el prefijo.
- Se recuperó la sanitización de logs de clasificación tras resolver el conflicto entre ramas.
- Se cierran explícitamente las conexiones SQLite para liberar los archivos también en Windows.

El CI corre en PR a `develop`, con LLM desactivado y almacenamiento local. Esta parte coincide
con el objetivo de #22; no sustituye la revisión de ese PR. El job de evaluación real conserva
la activación por etiqueta `evals` y usa la CLI vigente.

## Evidencia

Python 3.12, `USE_LLM=false`, `STORAGE_BACKEND=local`: 316 pruebas aprobadas.
`python -m ruff check .`: sin errores. La suite cubre API, agentes y helpers del panel.

Las nuevas regresiones verifican cola, original, corrección parcial, versión desactualizada,
rechazo e historial con almacenamiento local y remoto simulado. También prueban paginación,
identificadores inválidos, reintento tras fallo de copia y conservación exacta de los bytes
de una carga. El respaldo se restaura en un directorio nuevo y reanuda un caso pendiente.

El almacenamiento remoto en memoria comprueba el contrato, **no** IAM, cifrado, conectividad,
notificaciones o despliegue en OCI. Las pruebas sin modelo no miden exactitud clínica.

## Revisión e integración del equipo

Revisar en especial el grafo con Néstor, la API con Cristian, el almacenamiento con Carlos,
el respaldo con Sabrina y la interacción del panel con Camila. Esta lista es coordinación
propuesta, no solicitudes de revisión enviadas automáticamente.

Para evitar incorporar dos veces los mismos cambios, el equipo debe elegir entre integrar esta
rama conjunta o aplicar sus correcciones después de los PR originales. No fusionar ambas rutas
a ciegas. No se cerraron los issues ni se fusionó `develop` automáticamente.

Antes de desplegar: persistir SQLite y su archivo de bloqueo en un volumen compartido por los
procesos del runtime. Todos los escritores deben usar el mismo bloqueo. El MVP serializa los
documentos con SQLite; no resuelve procesamiento distribuido en varias VM. La API del prototipo
todavía requiere la revisión de controles de acceso del despliegue.

## Pendientes de Carolina que dependen de otra evidencia

| Paquete | Estado y siguiente paso |
|---|---|
| N2-05 / #33 | Implementado e integrado para revisión. Falta aceptación e integración del equipo. |
| N1-09 / #34 | Manejo de nodos integrado. Diana valida sus fixtures y criterios de casos borde. |
| N2-10 / #64 | Privacidad y utilidad de respaldo con restauración local. Sabrina valida el job y la restauración en OCI. |
| N1-13 / #56 | Espera la corrida real y lista de fallas de N1-11. No se ajustó el golden ni se inventó una mejora. |
| B-06 / #41 | Los 50 issues existen. Falta vincularlos a Projects; la credencial CLI carece de `read:project`. |
| M3 / #10 | Falta una nueva fotografía manuscrita consistente con el etiquetado solicitado. No se alteró el JSON para contradecir la imagen. |
| B-08 / #43 | Sigue pendiente la validación de fuentes de medicamentos con Camila. |
| N3-06 / #70 | Programado después de cerrar niveles 1 y 2. No se habilitó exportación automática de datos clínicos a tests. |
| F-08 / #80 | Borrador de presentación y guion preparados. Faltan demo integrada y dos ensayos reales con Diana. |

## N1-13: cómo producir una comparación válida

1. Tomar la lista de fallas publicada por Camila, con commit, modelo, configuración y resultados.
2. Seleccionar categorías AMB concretas y describir la hipótesis de cada cambio.
3. Crear documentos sintéticos nuevos en `evals/dev/`, separados del golden.
4. Correr antes y después con los mismos casos y configuración; conservar fallos y aciertos.
5. Publicar el cambio por categoría y tipo documental, e investigar regresiones en otras categorías.
6. Repetir la evaluación independiente del golden sin usarlo para ajustar prompts.

Las 316 pruebas de software no sustituyen esta comparación.
