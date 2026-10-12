# MediFlow · Plan de ejecución (versión 1.0, 22 de septiembre de 2026)

Un solo plan: paquetes de trabajo con dueño, entregable y criterio de terminado, desde el 22 de septiembre hasta el DemoDay. Reemplaza los cronogramas anteriores. El tablero de GitHub es el seguimiento diario; este documento es el plan base.

## Cómo se lee

1. Busca tu nombre. Cada paquete con tu nombre es tuyo hasta que cumple su columna **Listo cuando**, que es lo que revisa el PR.
2. **Entregable** dice qué archivos o artefactos produces; **Listo cuando** dice cómo sabemos que terminó.
3. Orden del README: Base y Nivel 1 hasta el 5/10, Nivel 2 hasta el 12/10, Nivel 3 solo con los dos anteriores cerrados. ★ marca la cadena crítica.
4. Cada nodo del grafo escribe solo sus claves del estado (sección Contratos). Nadie espera a nadie para empezar.
5. Una tarea, una rama, un PR chico, CI en verde, una aprobación del dueño del módulo y squash merge. Hasta el sprint 3 todo corre en Codespaces con almacenamiento local; el despliegue en OCI se hace una vez, en el sprint 3.

## Hitos

| Hito | Fecha | Nombre | Qué se demuestra |
|---|---|---|---|
| H1 | miércoles 30/9 | Listos para construir | Decisiones cerradas, main protegida, Codespaces funcionando para los ocho, conjunto de prueba de 30 documentos y 8 recetas revisado dos veces |
| H2 | lunes 5/10 | Nivel 1 completo (cierre del sprint 2) | Texto, PDF e imagen entran por la API y por la interfaz; validación, urgencia y score funcionan; los tres escenarios del brief corren de punta a punta en el entorno de desarrollo; primera evaluación publicada en el README |
| H3 | lunes 12/10 | Nivel 2 completo (cierre del sprint 3) | Todo desplegado en OCI con URL pública; panel del auditor, reglas editables, lectura de manuscritas con puerta de legibilidad, alertas a correo y Slack. Último día para empezar algo nuevo |
| H4 | lunes 19/10 | Congelamiento (cierre del sprint 4) | Cero errores graves, evaluación final con calibración en el README, nivel 3 solo lo que entró. Desde aquí solo arreglos |
| H5 | domingo 25/10 | Cierre del desarrollo | Video en YouTube, README final, Tareas 1 a 4 entregadas en la plataforma, presentación ensayada |
| DD | martes 27/10 | DemoDay, eliminatoria | Presentación en vivo desde la URL pública en OCI |
| F | jueves 29/10 | Final |  |

Definición de terminado para todo paquete: código en `main` por PR aprobado por el dueño del módulo con CI en verde; un test cubre el criterio Listo cuando; funciona de punta a punta en Codespaces y, desde el sprint 3, en la URL pública de OCI; README o `docs/` actualizados si cambia algo visible; issue cerrado con el enlace al PR.

## Equipo y propiedad de módulos

| Persona | Rol | Módulos que posee y cuyos PR revisa |
|---|---|---|
| Néstor Gribaudo | LLM Engineer | `agent/graph.py`, `agent/state.py`, `puntuar.py`, `enrutar.py`, `segunda_opinion.py`, `notificar.py`, `normalizar.py` (PDF, imagen, legibilidad); página de trazas; el diagrama del grafo en el README |
| Carlos Zunino | AI Engineer | `clasificar.py`, `extraer.py`, `agent/llm/`, `agent/prompts/`, `persistir.py`; la cuenta de OCI: VM, buckets, despliegue y alertas; revisión de los archivos de datos |
| Cristian Ojeda | AI Engineer | `validar.py`, `urgencia.py`, `agent/rules/`; endpoints de revisión humana (`/queue/human`, `/audit`); reporte al gestor |
| Carolina Chambique | AI Engineer | Revisión humana dentro del grafo (pausa y reanudación); corrección de fallas por categoría; tablero de GitHub; presentación del DemoDay |
| Kevin Lemos | AI Engineer | Sus módulos se reasignaron el 5 de octubre; ver «Redistribución del 5 de octubre» |
| Diana Gaitan | Datos y pruebas | Casos borde de la ingesta (archivos y resultados esperados); documentos del conjunto de prueba; apoyo en la presentación del DemoDay |
| Sabrina Valentim Guimaraes | Backend Developer | `api/` (cola de triaje, `/health`), `worker/`, SQLite y respaldos; bloque en portugués |
| Alessandro Cappelli | Full Stack Developer | `ui/` (carga, cola, reglas); configuración del repositorio; demo y video; alertas con n8n |
| Maria Camila Gonzalez Nuñez | Data Scientist | `evals/` (conjunto de prueba, generador, harness, evaluación); panel del auditor y dashboard (`3_Auditoria.py`, `5_Metricas.py`, `GET /metrics`); resultados en el README; decisiones de datos |

### Ya entregado en el sprint 1

- Clasificación y extracción con evidencia por campo, probadas con GS-06 (Carlos)
- Integración con OCI Object Storage: `persistir.py` sube al bucket; `docs/oci-setup.md`; 35 tests (Carlos)
- Kit de datos (plan del conjunto de prueba, banco clínico, medicamentos, CIE-10 y `rules.yaml`), README y template del repositorio (Camila)
- Repositorio del equipo en la organización de GitHub y Codespaces verificado sobre el repositorio (Néstor)

## Contratos de integración

El grafo comparte un solo estado (`TriageState` en `agent/state.py`). Cada nodo escribe únicamente sus claves. Una clave nueva se agrega a `agent/state.py` por PR del dueño del grafo y se anota en `docs/api-contract.md` el mismo día. Todo nodo agrega un registro a `trace` con `nodo`, `ts`, `modelo` y `detalle`.

| Nodo | Dueño | Lee | Escribe |
|---|---|---|---|
| normalizar | Néstor | `tipo_archivo`, archivo o `texto` | `texto`, `imagenes` (páginas renderizadas), `legibilidad` (0 a 1), `ruta_original` |
| clasificar | Carlos | `texto`, `imagenes` | `clasificacion`: `tipo_documento`, `especialidad`, `nivel_prioridad`, `score_confianza_clasificacion`; `modelo_utilizado` |
| extraer | Carlos | `texto`, `imagenes`, `clasificacion.tipo_documento` | `datos_extraidos` con los campos del contrato del brief y `evidencias` por campo |
| validar | Cristian | `datos_extraidos`, `clasificacion`, `medicamentos.csv`, `cie10.csv` | `validacion`: `campos_faltantes`, `conflictos`, `errores`, `categoria_amb` (AMB-1 a AMB-6) y `motivo_fuera_de_alcance` cuando es AMB-6 |
| detectar_urgencia | Cristian | `texto`, `clasificacion`, `datos_extraidos`, `rules.yaml` | `urgencia`: `detectada`, `motivos`, `alto_riesgo_farmacologico` |
| puntuar | Néstor | `legibilidad`, `validacion`, `clasificacion`, `segunda_opinion` | `score` (0 a 1) y sus cuatro componentes en la traza |
| segunda_opinion | Néstor | `texto`, `imagenes`, `datos_extraidos` | `segunda_opinion`: `acuerdo`, `campos_en_desacuerdo`, `modelo` |
| enrutar | Néstor | todo lo anterior y `rules.yaml` | `decision`: `destino_principal`, `requiere_auditoria_humana`, `justificacion_enrutamiento`, `notificacion_generada` |
| revision_humana | Carolina | `decision` y el estado completo, en pausa | reanuda con la decisión del auditor: aprobar o corregir vuelve a `enrutar`; rechazar termina en `rechazados/` |
| persistir | Carlos | `decision` y el resultado completo | `almacenamiento`: `bucket`, `ruta_objeto`, `status_backup`; copia en SQLite |
| notificar | Néstor | `decision.notificacion_generada` | publica en OCI Notifications; registra en `trace` |

### Endpoints

| Endpoint | Qué hace | Paquete | Dueño |
|---|---|---|---|
| `POST /triage` | JSON del brief; devuelve el JSON de salida del brief | Existe | Carlos |
| `POST /triage/upload` | PDF, imagen o txt; guarda en `recibidos/` y corre el grafo | N1-01 | Sabrina |
| `GET /triage` y `GET /triage/{id}` | Cola de triaje y resultado de un documento, desde SQLite | N1-02 | Sabrina |
| `GET /queue/human` y `POST /audit/{id}` | Cola de revisión y decisión del auditor: aprobar, corregir, rechazar | N2-04 | Cristian |
| `GET /rules` y `PUT /rules` | Reglas vigentes; edición con validación del YAML y recarga | N2-07 | Alessandro |
| `GET /metrics` | KPIs para el dashboard y el reporte | N3-04 | Camila |
| `GET /health` | Verificación del despliegue | Existe | Sabrina |

### Configuración

| Variable | Uso |
|---|---|
| `STORAGE_BACKEND` | `local` (por defecto en desarrollo, escribe en `./data/` con el mismo layout del bucket) o `oci` (desde el despliegue del sprint 3) |
| `ENV` | `dev` o `prod`: elige el bucket con `bucket_actual()` en `agent/storage/buckets.py` |
| `OCI_BUCKET_DEV`, `OCI_BUCKET_PROD` | `mediflow-dev`, con carpeta por persona, y `mediflow-prod`, que solo usa la VM. Reemplazan a `OCI_BUCKET` |
| `RULES_ADMIN_TOKEN` | Clave para editar reglas con `PUT /rules`. Solo en el `.env`, nunca en el repo; sin ella la edición responde 503 |
| `USE_LLM` | `false` en los tests del CI (respuestas simuladas); `true` en `evals/run.py` y en producción |
| `LLM_PRIMARY`, `LLM_FALLBACKS` | Modelo principal y cadena de respaldo, con la clave de cada desarrollador como secreto de Codespaces |

Layout del bucket y de `./data/` en local: `recibidos/`  ·  `procesados/urgentes|farmacia|autorizaciones|historia_clinica/`  ·  `auditoria_humana/{id}/original`, `extraccion.json`, `resolucion.json`  ·  `rechazados/`  ·  `reportes/diario/`

Evaluación: `plan_golden.csv` define, por documento, tipo, resultado esperado, destino, auditoría, categoría AMB y nivel de legibilidad. `evals/run.py` compara contra eso y contra los campos extraídos. Nadie ajusta prompts mirando el conjunto de prueba.

## Paquetes de trabajo

Dueño lleva el paquete; apoyo es a quien se le pide ayuda primero. ★: cadena crítica. Ítem: casilla del checklist Prioridades de entrega del README que cubre el paquete.

### Base: lo que habilita a los ocho para trabajar en paralelo

| ID | Paquete | Dueño | Apoyo | Entregable | Listo cuando | Depende de | Fechas | Ítem |
|---|---|---|---|---|---|---|---|---|
| B-01 | **Decisiones de datos registradas**. Regla A de urgencia (las listas de palabras solo en informes y órdenes), el nombre del campo del paciente según responda la instructora, y `Rechazado` fuera del enum de destinos | Camila |  | Tres entradas en `docs/decisions.md`; `rules.yaml` con la regla A y el campo confirmado | Las tres decisiones tienen fecha, motivo y alternativa descartada, y el contrato usa el nombre confirmado |  | 22/9 a 25/9 |  |
| B-02 | **Acuerdos de trabajo registrados**. Flujo con Codespaces, rama por issue, PR con una aprobación, congelamiento el 19/10 | Alessandro |  | Sección Cómo contribuir del README y entrada en `docs/decisions.md` | Un integrante nuevo puede seguir el flujo leyendo solo el README |  | 22/9 a 24/9 |  |
| B-03 | **Proteger main**. Regla sobre `main`: PR con una aprobación y CI en verde, solo squash merge, borrado automático de ramas | Alessandro | — | Configuración del repositorio en GitHub | Un push directo a `main` es rechazado y un PR sin aprobación no se puede fusionar |  | 22/9 a 23/9 |  |
| B-04 | **Codespaces listo para todos**. `.devcontainer/devcontainer.json` con Python 3.12, dependencias, puertos 8000 y 8501, storage local por defecto | Néstor |  | `.devcontainer/` en el repo y `make dev` funcionando | En un Codespace recién creado, `make dev` levanta api, interfaz y worker sin pasos manuales |  | 22/9 a 24/9 |  |
| B-05 | **Almacenamiento local**. `persistir.py` elige el backend con `STORAGE_BACKEND`; `local` escribe en `./data/` con el layout del bucket. Hasta el despliegue del sprint 3, todo el equipo trabaja con `local` | Carlos | — | `agent/storage/local.py`, cambio en `persistir.py`, test sin credenciales | Con `STORAGE_BACKEND=local` nada llega a OCI y la suite completa pasa sin claves |  | 22/9 a 25/9 |  |
| B-06 | **Tablero de GitHub con este plan**. Un issue por paquete con dueño, etiqueta de nivel e hito; columnas Por hacer, En curso, En revisión y Hecho | Carolina | Cristian | GitHub Projects del repo | Cada paquete de este documento tiene su issue y cada persona ve los suyos filtrando por asignado |  | 22/9 a 24/9 |  |
| B-07 | **Repo alineado con el kit de datos**. `rules.yaml` con las decisiones, los cuatro CSV en su carpeta, `DATA.md`, CIE-10 con texto oficial | Camila | Carlos | PR con `rules.yaml`, `banco_clinico.csv`, `medicamentos.csv`, `cie10.csv`, `plan_golden.csv`, `evals/DATA.md` | El loader lee el YAML sin cambios de código y los tests siguen en verde | B-01 | 24/9 a 26/9 |  |
| B-08 | **Dosis verificadas en ANMAT**. Rangos de los 22 medicamentos contra el Vademécum Nacional, primero los 11 de alto riesgo | Camila | Carolina | `medicamentos.csv` con `producto_consultado`, `fecha_consulta` y `estado_verificacion` | Las 22 filas en estado verificado |  | 22/9 a 26/9 |  |
| B-09 | **Conjunto de prueba escrito y revisado** ★. Cada persona escribe 3 o 4 documentos según `plan_golden.csv` y fotografía una receta manuscrita; revisión cruzada, una por documento desde el 6/10; Carlos revisa los archivos de datos. Incluye los siete casos fuera de alcance, FA-01 a FA-07. Se escribe el `.txt`; el PDF, el JSON y las imágenes los generan los scripts de `generator/` | Camila | Carlos | Archivos en `evals/golden/files/`, fotos M1 a M8 en `evals/handwritten/`, `plan_golden.csv` con `revision_1` | Los 45 elementos tienen etiqueta y su revisión anotada |  | 23/9 a 30/9 | 1.6 |
| B-10 | **PDF e imágenes degradadas**. PDF con ReportLab para los 30 documentos y 12 imágenes degradadas con Pillow, 4 por nivel de legibilidad | Camila | — | `evals/generator/degradar.py` y las 12 imágenes en `evals/golden/files/` | Cada imagen tiene su nivel (leve, media, severa) anotado en `plan_golden.csv` | B-09 | 29/9 a 1/10 | 2.4 |
| B-11 | **Harness de evaluación con el modelo real** ★. `evals/run.py` corre el conjunto de prueba con `USE_LLM=true` y compara contra `plan_golden.csv` | Camila | Carlos | `evals/run.py`, `evals/output/report.md` | Una corrida produce accuracy de clasificación y de destino, recall de urgencias, tasa de revisión humana, latencia p50 y p95, y precisión por campo |  | 25/9 a 2/10 |  |

### Nivel 1: obligatorio, checklist de evaluación del brief

| ID | Paquete | Dueño | Apoyo | Entregable | Listo cuando | Depende de | Fechas | Ítem |
|---|---|---|---|---|---|---|---|---|
| N1-01 | **Ingesta de PDF e imagen**. `normalizar.py` extrae texto con PyMuPDF o renderiza páginas; `POST /triage/upload` guarda en `recibidos/` y pasa las imágenes al modelo | Néstor | Sabrina | `agent/nodes/normalizar.py`, `POST /triage/upload`, `agent/tests/test_normalizar.py` | Un PDF nativo, un PDF escaneado y una foto de receta impresa producen el JSON del contrato |  | 22/9 a 2/10 | 1.1 |
| N1-02 | **Cola de triaje en la API**. Resultados guardados en SQLite y expuestos por la API | Sabrina | Alessandro | `GET /triage`, `GET /triage/{id}`, tabla `triage_results`, `api/tests/test_cola.py` | Cada documento procesado se consulta por id y aparece en la lista con destino y score |  | 22/9 a 30/9 | 1.1 |
| N1-03 | **Carga y cola de triaje en la interfaz**. Páginas Carga y Cola de triaje en Streamlit conectadas a la API | Alessandro | Sabrina | `ui/pages/1_Carga.py`, `ui/pages/2_Cola_de_triaje.py` | Desde la interfaz se sube un documento y aparece en la cola con destino y score | N1-02 | 24/9 a 2/10 | 1.1 |
| N1-04 | **Adaptador de modelos con respaldo**. Modelo principal más cadena de respaldo, reintentos con backoff ante 429 y 5xx, modelo usado en la traza | Carlos | Camila | `agent/llm/adapter.py`, `agent/tests/test_adapter.py` | Con un proveedor simulado que falla, la traza muestra el cambio al respaldo y el documento no se pierde |  | 25/9 a 1/10 | 1.2 |
| N1-05 | **Validación con categorías AMB** ★. Campos obligatorios por tipo, dosis contra `medicamentos.csv`, CIE-10 contra `cie10.csv`, matrícula, edad contra fecha, diagnóstico contra estudio; asigna `categoria_amb` | Cristian | Carolina | `agent/nodes/validar.py`, `agent/tests/test_validar.py` | GS-06 sale con AMB-3, hay un test por categoría AMB-1 a AMB-6 y cualquier conflicto manda a revisión humana | B-07 | 22/9 a 1/10 | 1.4 |
| N1-06 | **Urgencia y alto riesgo**. Regla A: hallazgos críticos y palabras de urgencia solo en informes y órdenes; valores críticos de laboratorio; prioridad del modelo en todos los tipos; alto riesgo solo en recetas, hacia Farmacia con auditoría | Cristian | Néstor | `agent/nodes/urgencia.py`, `agent/tests/test_urgencia.py` | El caso TEP del brief va a Emergencia con notificación; GS-03, GS-04 y GS-05 van a Farmacia con auditoría; GS-01, GS-04, GS-24 y GS-25 no disparan urgencia por sus frases de alarma | B-01 | 24/9 a 2/10 | 1.4 |
| N1-07 | **Score compuesto y enrutamiento por franjas** ★. `score = 0,25 legibilidad + 0,30 validación + 0,25 modelo + 0,20 acuerdo`, umbrales desde `rules.yaml` | Néstor | Cristian | `agent/nodes/puntuar.py`, `agent/nodes/enrutar.py`, `agent/tests/test_enrutar.py` | Mayor o igual a 0,85 enruta solo; entre 0,60 y 0,85 pide segunda opinión o marca auditoría; menor a 0,60 va a revisión; la traza muestra los cuatro componentes | N1-05, N1-01 | 29/9 a 5/10 | 1.4 |
| N1-08 | **Worker de recibidos/**. Proceso que lee `recibidos/` cada 30 segundos, corre el grafo y mueve el resultado; reintentos con backoff. En desarrollo lee `./data/recibidos/`; en OCI, el bucket | Sabrina | — | `worker/main.py` y su servicio en `docker-compose.dev.yml` | Un archivo dejado en `recibidos/` termina en su carpeta de destino con registro en SQLite | B-05 | 29/9 a 5/10 | 1.5 |
| N1-09 | **Casos borde**. Documento vacío, archivo equivocado, PDF largo, dos documentos en un archivo (AMB-5), JSON sin paciente (AMB-1) | Diana | Carolina | `agent/tests/test_casos_borde.py` y el manejo en los nodos | Cada caso tiene un test y un destino definido; ninguno tumba la API | N1-05 | 6/10 a 10/10 | 1.4 |
| N1-10 | **Tres escenarios reproducibles**. Rutina, urgencia y ambigüedad con datos semilla y un guion corto | Alessandro | Camila | `docs/demo.md` y `evals/semilla/` | Cualquiera del equipo corre los tres escenarios en Codespaces siguiendo el guion | N1-03, N1-05, N1-06 | 1/10 a 5/10 | 1.6 |
| N1-11 | **Primera evaluación publicada** ★. Tabla de métricas en el README y análisis de fallas por categoría AMB y por tipo de documento | Camila | Carlos | Sección Evaluación del README, `evals/output/report.md`, lista de fallas | El README muestra los números de la primera corrida completa y cada falla tiene categoría | B-09, B-11 | 2/10 a 5/10 | 1.7 |
| N1-12 | **README y diagrama al día**. El diagrama del grafo refleja la regla A y el contrato; lo mantiene el dueño del grafo | Néstor | Camila | README, `docs/architecture.md`, `docs/api-contract.md` | Diagrama, `graph.py` y `rules.yaml` coinciden nodo por nodo | B-01 | 25/9 a 5/10 | 1.7 |
| N1-13 | **Corrección de fallas por categoría** ★. Ajustar prompts y reglas según las fallas de N1-11, validando con documentos nuevos de `evals/dev/` que no son del conjunto de prueba | Carolina | Cristian | PR de prompts y de reglas con la corrida antes y después | Las categorías atacadas mejoran en la corrida siguiente y ninguna otra empeora | N1-11 | 6/10 a 12/10 | 1.3 |

### Nivel 2: diferenciales que propone el brief

| ID | Paquete | Dueño | Apoyo | Entregable | Listo cuando | Depende de | Fechas | Ítem |
|---|---|---|---|---|---|---|---|---|
| N2-01 | **Despliegue completo en OCI** ★. VM Ampere A1, Docker Compose, Nginx con TLS, dominio; cada merge a `main` despliega; `STORAGE_BACKEND=oci` en la VM | Carlos | Sabrina | `infra/` en uso, `.github/workflows/deploy.yml` activo, URL en el README | Un merge a `main` se ve en la URL pública en menos de 10 minutos y `GET /health` responde | B-03 | 6/10 a 9/10 | 2.2 |
| N2-02 | **Buckets de OCI: desarrollo y producción**. `mediflow-dev` con carpeta por persona y credenciales de desarrollo; el bucket de producción solo acepta la VM | Carlos | — | Buckets, políticas IAM en `infra/oci/policies.txt`, `docs/oci-setup.md` | Las credenciales de desarrollo no pueden escribir en el bucket de producción |  | 6/10 a 8/10 | 2.2 |
| N2-03 | **Guardia de despliegue y aviso**. El deploy solo corre para commits que vienen de un PR aprobado; avisa en Discord; vuelta atrás ensayada | Carlos | Alessandro | `.github/workflows/deploy.yml` con la guardia y el webhook | Un commit sin PR no se despliega, cada despliegue avisa en el canal y se vuelve a la versión anterior en menos de 10 minutos | N2-01 | 9/10 a 12/10 | 2.2 |
| N2-04 | **API de revisión humana**. Cola de revisión y decisión del auditor guardada en SQLite y en `auditoria_humana/{id}/resolucion.json` | Cristian | Sabrina | `GET /queue/human`, `POST /audit/{id}`, `api/tests/test_audit.py` | Aprobar, corregir o rechazar por API queda registrado con quién, cuándo y por qué | N1-02 | 2/10 a 7/10 | 2.1 |
| N2-05 | **Pausa y reanudación del grafo**. Checkpointer de SQLite; el grafo se detiene en revisión humana y se reanuda con la decisión del auditor | Carolina | Néstor | `agent/graph.py` con interrupt, `agent/tests/test_revision_humana.py` | Aprobar o corregir reanuda hacia el destino correcto; rechazar guarda en `rechazados/` | N2-04, N1-07 | 6/10 a 12/10 | 2.1 |
| N2-06 | **Panel del auditor**. Documento y JSON lado a lado, motivo AMB visible, botones aprobar, corregir y rechazar | Camila | Carlos | `ui/pages/3_Auditoria.py` | Un caso ambiguo se resuelve con un clic y el documento se reencamina | N2-04 | 6/10 a 12/10 | 2.1 |
| N2-07 | **Reglas editables sin código**. Página Reglas y `PUT /rules` con validación del YAML y recarga sin reiniciar | Alessandro | Cristian | `ui/pages/4_Reglas.py`, `PUT /rules`, `api/tests/test_rules.py` | Cambiar un umbral en la interfaz cambia la decisión del documento siguiente | B-07 | 6/10 a 10/10 | 2.3 |
| N2-08 | **Puerta de legibilidad y recetas manuscritas**. Score de legibilidad por resolución, contraste, nitidez y autoevaluación del modelo; umbrales 0,40 y 0,70 | Néstor | Carlos y Camila | `normalizar.py` con legibilidad, `agent/tests/test_legibilidad.py` | Las imágenes severas van a revisión con motivo ilegible, las leves pasan, y M1 a M8 dan su resultado esperado | N1-01, B-10 | 6/10 a 12/10 | 2.4 |
| N2-09 | **Alertas en tiempo real**. Topic de OCI Notifications con suscripción por correo y webhook a Slack; `notificar.py` publica | Carlos | Néstor | `agent/storage/notifications.py`, `notificar.py`, topic y suscripciones | Una urgencia llega a correo y a Slack en menos de un minuto | N1-06, N2-01 | 8/10 a 11/10 | 2.5 |
| N2-10 | **Respaldo y privacidad**. Respaldo diario de SQLite al bucket; checklist de privacidad: sin datos de pacientes en logs, bucket privado | Sabrina | Carolina | Job de respaldo en la VM y `docs/privacidad.md` | Un respaldo se restaura en prueba y los logs no contienen nombres de pacientes | N2-01 | 9/10 a 12/10 | 2.2 |

### Nivel 3: nuestros plus, en orden de prioridad, solo con los niveles 1 y 2 cerrados

| ID | Paquete | Dueño | Apoyo | Entregable | Listo cuando | Depende de | Fechas | Ítem |
|---|---|---|---|---|---|---|---|---|
| N3-01 | **Calibración del score y evaluación final**. Accuracy por rango de score, ajuste de umbrales, evaluación final con márgenes de error | Carlos | Camila | Gráfico de calibración, umbrales en `docs/decisions.md`, README con métricas finales | El README muestra las métricas finales con su intervalo y el gráfico de calibración | N1-13 | 13/10 a 19/10 | 3.5 |
| N3-02 | **Trazas y resiliencia en vivo**. Página Trazas nodo por nodo; escena para apagar el modelo principal en vivo y ver el cambio al respaldo | Néstor | — | `ui/pages/6_Trazas.py` y la escena en `docs/demo.md` | Cada nodo muestra tiempo, modelo y justificación; la escena se ensayó una vez | N1-07, N1-04 | 13/10 a 16/10 | 3.6 |
| N3-03 | **Segunda opinión entre modelos**. En la franja media del score, el respaldo extrae de nuevo y se compara campo por campo | Néstor | Cristian | `agent/nodes/segunda_opinion.py` real, `agent/tests/test_segunda_opinion.py` | Un caso de score medio muestra acuerdo o desacuerdo en la traza; el desacuerdo manda a revisión | N1-07 | 13/10 a 17/10 | 3.7 |
| N3-04 | **Dashboard en vivo**. Volumen por tipo y destino, urgencias, tasa de revisión, confianza media, alertas recientes | Camila | Carlos | `ui/pages/5_Metricas.py`, `GET /metrics` | La página muestra las métricas de la última corrida y las alertas del día | N2-09 | 13/10 a 17/10 | 3.1 |
| N3-05 | **Reporte diario al gestor**. Job a las 07:00: KPIs desde SQLite, resumen de cinco líneas redactado por el agente, correo, copia en `reportes/` | Cristian | Sabrina | `worker/reporte.py` | El reporte del día llega por correo y queda en `reportes/diario/` | N1-08 | 14/10 a 18/10 | 3.4 |
| N3-06 | **Correcciones del auditor como tests**. Cada corrección del panel se guarda como caso de regresión en `evals/` | Carolina | Camila | `evals/regresion/` y su corrida en el CI | Una corrección en el panel genera un caso nuevo que corre en el CI | N2-05, N2-06 | 14/10 a 17/10 | 3.8 |
| N3-07 | **Bloque en portugués**. Seis documentos en portugués en el conjunto de prueba, medidos aparte | Sabrina | Alessandro | Seis casos en `evals/golden/` con etiqueta `idioma: pt` | El README publica la accuracy en portugués junto a la de español | N1-11 | 13/10 a 18/10 | 3.3 |
| N3-08 | **Workflow en n8n para las alertas**. n8n auto-hospedado en la VM que recibe la alerta y la publica en Slack | Alessandro | Sabrina | Servicio n8n en `infra/docker-compose.yml` y el workflow exportado | Una urgencia llega a Slack pasando por n8n | N2-09 | 15/10 a 18/10 | 3.2 |

### Cierre: video, documentación y DemoDay

| ID | Paquete | Dueño | Apoyo | Entregable | Listo cuando | Depende de | Fechas | Ítem |
|---|---|---|---|---|---|---|---|---|
| F-01 | **Guion y storyboard del video**. Los tres escenarios del brief más alto riesgo y resiliencia; 3 a 5 minutos, producto en vivo | Alessandro | Sabrina | `docs/video.md` | Guion aprobado en la sincronización del viernes 16 | N1-10 | 13/10 a 16/10 |  |
| F-02 | **Cacería de errores y pulido**. Cada dueño corrige su módulo; nada se demuestra desde localhost | Néstor | Todos | Issues de error cerrados | Cero errores graves abiertos en la URL pública |  | 13/10 a 19/10 |  |
| F-03 | **Ensayo general con alguien externo**. Una persona ajena al equipo usa la demo siguiendo el guion | Alessandro | Todos | Lista de ajustes en el tablero | Lista de ajustes anotada y priorizada | F-01 | 17/10 a 17/10 |  |
| F-04 | **Grabación del video**. Dos tomas; Alessandro presenta el producto y Sabrina los resultados de la evaluación | Alessandro | Sabrina | Dos tomas completas | Una toma aprobada por el equipo | F-03 | 21/10 a 21/10 |  |
| F-05 | **Edición y subida a YouTube**. Corte final y publicación | Néstor | Alessandro | Enlace de YouTube | Enlace publicado en la Tarea 2 de la plataforma | F-04 | 22/10 a 22/10 |  |
| F-06 | **README final**. Resultados finales, diagrama definitivo, cómo ejecutarlo, equipo | Camila | Néstor | README | Todo enlace del README abre y los números coinciden con `evals/output/` | N3-01 | 20/10 a 23/10 |  |
| F-07 | **Tareas 1 a 4 en la plataforma**. Documentación, video, herramientas y enlaces, probados en una ventana de incógnito | Cristian | Sabrina | Las cuatro tareas en la plataforma | Todos los enlaces abren sin sesión | F-05, F-06 | 23/10 a 23/10 |  |
| F-08 | **Presentación del DemoDay**. Presentación corta y dos ensayos cronometrados | Carolina | Diana | Presentación y guion de 5 minutos | Dos ensayos dentro del tiempo con la demo en vivo | F-04 | 22/10 a 26/10 |  |

## Semana 1, del 22 al 28 de septiembre

| Persona | Empieza hoy | Sigue esta semana | Escribe (23 al 28/9) | Revisa (28 al 30/9) |
|---|---|---|---|---|
| Néstor | B-04 Codespaces listo para todos | N1-12 README y diagrama al día (desde el 25/9) | GS-05, GS-13, GS-21, GS-29 y la receta M5 (media) | FA-05, FA-06, GS-03, GS-04, GS-11, GS-12, GS-19, GS-20, GS-27, GS-28 |
| Carlos | B-05 Almacenamiento local | N1-04 Adaptador de modelos con respaldo (desde el 25/9) | GS-01, GS-09, GS-17, GS-25 y la receta M1 (leve) | FA-01, FA-02, GS-07, GS-08, GS-15, GS-16, GS-23, GS-24 |
| Cristian | N1-05 Validación con categorías AMB | N1-06 Urgencia y alto riesgo (desde el 24/9) | GS-02, GS-10, GS-18, GS-26 y la receta M2 (leve) | FA-02, FA-03, GS-01, GS-08, GS-09, GS-16, GS-17, GS-24, GS-25 |
| Carolina | B-06 Tablero de GitHub con este plan |  | GS-03, GS-11, GS-19, GS-27 y la receta M3 (leve) | FA-03, FA-04, GS-01, GS-02, GS-09, GS-10, GS-17, GS-18, GS-25, GS-26 |
| Kevin | N1-01 Ingesta de PDF e imagen |  | GS-04, GS-12, GS-20, GS-28 y la receta M4 (media) | FA-04, FA-05, GS-02, GS-03, GS-10, GS-11, GS-18, GS-19, GS-26, GS-27 |
| Sabrina | N1-02 Cola de triaje en la API |  | GS-06, GS-14, GS-22, GS-30 y la receta M6 (media) | FA-06, FA-07, GS-04, GS-05, GS-12, GS-13, GS-20, GS-21, GS-28, GS-29 |
| Alessandro | B-02 Acuerdos de trabajo registrados; B-03 Proteger main | N1-03 Carga y cola de triaje en la interfaz (desde el 24/9) | GS-07, GS-15, GS-23 y la receta M7 (severa) | FA-07, GS-05, GS-06, GS-13, GS-14, GS-21, GS-22, GS-29, GS-30 |
| Camila | B-01 Decisiones de datos registradas; B-08 Dosis verificadas en ANMAT | B-07 Repo alineado con el kit de datos (desde el 24/9); B-09 Conjunto de prueba escrito y revisado (desde el 23/9); B-11 Harness de evaluación con el modelo real (desde el 25/9) | GS-08, GS-16, GS-24 y la receta M8 (severa) | FA-01, GS-06, GS-07, GS-14, GS-15, GS-22, GS-23, GS-30 |

## Reparto del conjunto de prueba (B-11)

La fuente de verdad del reparto es `evals/golden/plan_golden.csv`; esta tabla es una copia para leer, regenerada el 6 de octubre.

| ID | Tipo | Resultado esperado | Legibilidad | Escribe | Revisa |
|---|---|---|---|---|---|
| GS-01 | Receta Medica | rutina | leve | Carlos | Carolina |
| GS-02 | Receta Medica | rutina | media | Cristian | Camila |
| GS-03 | Receta Medica | alto_riesgo |  | Carolina | Diana |
| GS-04 | Receta Medica | alto_riesgo |  | Diana | Néstor |
| GS-05 | Receta Medica | alto_riesgo |  | Néstor | Sabrina |
| GS-06 | Receta Medica | ambiguedad |  | Sabrina | Camila |
| GS-07 | Informe de Estudio por Imagenes | urgencia | leve | Alessandro | Camila |
| GS-08 | Informe de Estudio por Imagenes | urgencia |  | Camila | Carlos |
| GS-09 | Informe de Estudio por Imagenes | urgencia |  | Carlos | Carolina |
| GS-10 | Informe de Estudio por Imagenes | urgencia_ambiguedad |  | Cristian | Camila |
| GS-11 | Informe de Estudio por Imagenes | rutina | media | Carolina | Diana |
| GS-12 | Informe de Estudio por Imagenes | rutina | severa | Diana | Néstor |
| GS-13 | Informe de Laboratorio | urgencia |  | Néstor | Sabrina |
| GS-14 | Informe de Laboratorio | urgencia_ambiguedad |  | Sabrina | Camila |
| GS-15 | Informe de Laboratorio | rutina |  | Alessandro | Camila |
| GS-16 | Informe de Laboratorio | rutina | severa | Camila | Carlos |
| GS-17 | Informe de Laboratorio | ambiguedad |  | Carlos | Cristian |
| GS-18 | Orden de Solicitud de Procedimiento | urgencia |  | Cristian | Camila |
| GS-19 | Orden de Solicitud de Procedimiento | urgencia |  | Carolina | Diana |
| GS-20 | Orden de Solicitud de Procedimiento | rutina | leve | Carolina | Néstor |
| GS-21 | Orden de Solicitud de Procedimiento | rutina | severa | Néstor | Sabrina |
| GS-22 | Orden de Solicitud de Procedimiento | ambiguedad |  | Sabrina | Camila |
| GS-23 | Epicrisis | rutina | media | Alessandro | Camila |
| GS-24 | Epicrisis | rutina | severa | Camila | Carlos |
| GS-25 | Epicrisis | rutina |  | Carlos | Diana |
| GS-26 | Epicrisis | ambiguedad |  | Cristian | Diana y Carlos |
| GS-27 | Certificado Medico | rutina | leve | Carolina | Diana |
| GS-28 | Certificado Medico | rutina | media | Diana | Alessandro |
| GS-29 | Certificado Medico | ambiguedad |  | Néstor | Diana |
| GS-30 | Certificado Medico | ambiguedad |  | Sabrina | Diana y Camila |
| FA-01 | Otro | fuera_alcance |  | Alessandro | Camila |
| FA-02 | Otro | fuera_alcance |  | Camila | Carlos |
| FA-03 | Otro | fuera_alcance | leve | Carlos | Carolina |
| FA-04 | Otro | fuera_alcance |  | Cristian | Camila |
| FA-05 | Informe de Laboratorio | urgencia |  | Carolina | Diana |
| FA-06 | Otro | fuera_alcance | leve | Diana | Néstor |
| FA-07 | Otro | fuera_alcance |  | Néstor | Sabrina |
| M1 | Receta Medica | rutina | leve | Carlos | Cristian |
| M2 | Receta Medica | alto_riesgo | leve | Cristian | Camila |
| M3 | Receta Medica | ambiguedad | leve | Carolina | Sabrina |
| M4 | Receta Medica | ambiguedad | media | Diana | Alessandro |
| M5 | Receta Medica | ambiguedad | media | Néstor | Camila |
| M6 | Receta Medica | ambiguedad | media | Sabrina | Carlos |
| M7 | Receta Medica | ilegible | severa | Alessandro | Cristian |
| M8 | Receta Medica | ilegible | severa | Diana | Camila |

## Redistribución del 5 de octubre

Kevin no registró actividad en el repositorio ni respondió en el canal. Para no frenar al equipo, sus
tareas se reasignaron así. Si vuelve, lo sumamos donde haga falta.

| Qué | Antes | Ahora |
|---|---|---|
| GS-04, GS-12, GS-28, FA-06 y la receta M4 | Kevin | Diana |
| GS-20 | Kevin | Carolina |
| Revisiones de GS-02, GS-03, GS-10, GS-11, GS-18, GS-19, FA-04 y FA-05 | Kevin | Diana |
| Revisión de GS-26 | Kevin | Carlos |
| Revisión de M1 | Kevin | Cristian |
| Revisión de M8 | Kevin | Camila |
| Revisión de GS-28, que ahora escribe Diana | Diana | Alessandro |
| B-10, generador de PDF e imágenes | Kevin | Camila, ya entregado |
| N1-01, ingesta de PDF e imagen | Kevin, con Néstor | Néstor, con Sabrina en `POST /triage/upload` |
| N1-09, casos borde | Kevin, con Carolina | Diana arma los casos y sus resultados esperados; Carolina, el manejo en los nodos |
| N2-03, guardia de despliegue | Kevin, con Carlos | Carlos, con Alessandro |
| N2-08, puerta de legibilidad | Kevin, con Néstor | Néstor, con Carlos y Camila |
| N3-08, alertas con n8n | Kevin, con Alessandro | Alessandro, con Sabrina, después de cerrar los niveles 1 y 2 |
| F-08, presentación del DemoDay | Carolina, con Kevin | Carolina, con Diana |

Los apoyos que Kevin tenía en B-03, B-05, N1-08, N2-02 y N3-02 no se reasignaron: esos paquetes
siguen con su dueño.

Con el reparto del 5 de octubre, cada persona revisaba 11 documentos y Diana 13. Desde el 6 hay una sola
revisión por documento: ver la sección siguiente.

## Revisión única, desde el 6 de octubre

Por tiempo, cada documento del conjunto lleva una sola revisión, de alguien distinto de quien lo
escribió (ADR-012). Si un documento ya estaba revisado, por el revisor 1, el revisor 2 o la
coordinación del conjunto, esa revisión cuenta y esa persona queda como revisora. Las revisiones
pendientes de quien no había revisado se cancelan, y las segundas revisiones ya completas se
conservan: GS-26, de Diana y Carlos, y GS-30, de Diana y Camila.

Cuando la evaluación marca un fallo, antes de contarlo como error del agente se vuelve a mirar la
etiqueta. Si estaba mal, se corrige y no cuenta como error.

El estado de cada documento, quién lo revisa y si ya está aprobado vive en `evals/golden/plan_golden.csv`:
es la única fuente, y la coordinación del conjunto es la única que la edita.

## Reglas de trabajo

1. Toma tu issue y ponlo En curso. Rama desde el issue: `area/numero-tema`.
2. Codespace sobre tu rama, nunca sobre `main`. Clave de Gemini como secreto de Codespaces.
3. Commits chicos. PR temprano, como borrador si hace falta, con `Closes #numero` y cómo probarlo.
4. CI en verde y aprobación del dueño del módulo. Squash merge. Borra tu Codespace al terminar.
5. Desde el sprint 3, cada merge a `main` despliega en OCI. Desde el 19/10 solo arreglos. Nadie prueba contra el bucket de producción.
6. Estado diario en Discord en tres líneas. Un bloqueo de más de un día se dice el mismo día.

Decisiones: una propuesta va en un hilo con 48 horas para objetar; todo queda en `docs/decisions.md` el mismo día.
