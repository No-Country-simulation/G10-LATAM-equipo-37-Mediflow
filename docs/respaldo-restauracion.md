# Respaldo y restauración del estado durable

Apoyo a N2-10. La utilidad está probada en local; su instalación y validación en OCI corresponden
al paquete de Sabrina. No se instaló un job en ninguna VM.

El estado completo requiere **SQLite y los objetos privados del bucket**. La base contiene
referencias SHA-256 a los payloads. Copiar solamente el archivo SQLite deja un respaldo incompleto.

## Crear y comprobar

Con las mismas variables `MEDIFLOW_CHECKPOINT_DB`, `STORAGE_BACKEND`, `ENV` y `OCI_BUCKET_*`
que usa la API, ejecutar desde la raíz del repositorio:

```bash
python -m agent.storage.respaldo crear --destino /ruta/privada/mediflow-20261009.zip
```

Para subir además el ZIP al prefijo `respaldos/` del bucket configurado:

```bash
python -m agent.storage.respaldo crear --destino /ruta/privada/mediflow-20261009.zip --subir
```

La utilidad toma el mismo bloqueo SQLite del runtime, usa la API de backup de SQLite y copia
los objetos del bucket excepto `respaldos/`. Genera un manifiesto con hashes y fecha UTC.
El directorio de salida debe estar fuera del bucket local. No sobrescribe un ZIP existente.
El archivo contiene datos operativos y debe guardarse en un directorio y bucket privados.
El hash detecta alteraciones accidentales; no es una firma ni reemplaza permisos de acceso.

## Restaurar en un entorno aislado

```bash
python -m agent.storage.respaldo restaurar --origen /ruta/privada/mediflow-20261009.zip --destino /ruta/nueva/recuperacion
```

El destino debe ser nuevo. Primero se verifican inventario, rutas y hashes; después se escribe
SQLite y `recuperacion/{bucket}/...`. Se comprueba `PRAGMA integrity_check`.
Para probar la recuperación, iniciar **una instancia aislada** con:

```text
STORAGE_BACKEND=local
MEDIFLOW_DATA_DIR=/ruta/nueva/recuperacion
MEDIFLOW_CHECKPOINT_DB=/ruta/nueva/recuperacion/checkpoints.sqlite3
OCI_BUCKET=<bucket indicado en manifest.json>
USE_LLM=false
```

Comprobar que un documento pendiente aparece en la cola, que se recupera el original y que una
decisión lo reanuda. Conservar evidencia sin contenido clínico: fecha, commit, cantidad de
objetos, integridad, ID sintético y resultado. La suite ejecuta este recorrido con datos de prueba.

## Instalación diaria propuesta para Sabrina

Preparar un timer o job del despliegue que ejecute `crear --subir` una vez por día con nombre UTC
único. Debe compartir el volumen de SQLite y el bloqueo con la API, usar los permisos del servicio
y devolver un fallo observable si no completa el upload. Verificar además permisos del bucket,
retención, espacio disponible y una restauración desde un ZIP descargado de OCI.

El job no queda activado por añadir esta utilidad. No se eligió una política de retención ni se
borraron respaldos. Para el MVP el ZIP se construye localmente y se carga completo en memoria;
evaluar streaming, tiempos de bloqueo y capacidad antes de usarlo con un volumen grande de datos.
Las escrituras que evadan el bloqueo del runtime no quedan coordinadas por esta herramienta.
