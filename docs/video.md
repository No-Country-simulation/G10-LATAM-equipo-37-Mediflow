# F-01: Guion y storyboard del video (issue #73)

- Issue: #73 — F-01: Guion y storyboard del video
- Responsable: Alessandro · Apoyo: Sabrina · Dependencia: N1-10
- Fechas del plan: 13/10 a 16/10 · Aprobación: sincronización del **viernes 16**
- Estado: **borrador para revisión**

## 1. Objetivo

Video de **3 a 5 minutos (objetivo: 4:30)** que muestre **Mediflow en vivo** (producto funcionando, sin mockups)
resolviendo los **3 escenarios del brief de mayor riesgo y resiliencia**.

## 2. Fuentes y documentos utilizados

Verificado el 13/10/2026 contra la rama `develop` y la rama `copilot/n1-10-tres-escenarios-reproducibles` (N1-10, issue #53).
No existía `docs/video.md` ni otro guion previo; el único PR relacionado es #104 (este trabajo).

| Fuente | Rol | Qué se toma de ella |
|---|---|---|
| `docs/plan.md` (v1.0, redistribución vigente) | **Fuente principal** | Paquete F-01 (fechas 13/10–16/10, dependencia N1-10, criterio de aceptación), hito H5 (video en YouTube) y definición de los tres escenarios del brief: rutina, urgencia y ambigüedad (N1-10). |
| `docs/demo.md` y `evals/semilla/` (`rutina.json`, `urgencia.json`, `ambiguedad.json`, `README.md`) | **Fuente de la demo en vivo** (entregable de N1-10) | Comandos, solicitudes `POST /triage` y tabla de resultado esperado de cada escenario. **Hoy solo existen en la rama `copilot/n1-10-tres-escenarios-reproducibles`, no en `develop`**: F-01 depende de que se integren. |
| `evals/golden/plan_golden.csv` | **Usado como apoyo (no como fuente principal)** | Fuente de verdad del conjunto de prueba: sirve para citar casos equivalentes y su resultado esperado (ver tabla de casos). El guion se basa en `docs/plan.md`; el CSV valida que lo narrado coincide con el resultado esperado. |
| `docs/api-contract.md`, `docs/examples/triage_request.json` | Apoyo | Contrato de `POST /triage` mostrado en pantalla. |
| `docs/guardarrailes.md`, `docs/privacidad.md`, `docs/alcance-y-limites.md` | Apoyo | Mensajes sobre límites del agente y auditoría humana. |

## 3. Los tres escenarios (rutina, urgencia, ambigüedad)

Resultado esperado según `docs/demo.md`.

| Escenario | Archivo de demo | Destino esperado | Auditoría | Casos equivalentes en `plan_golden.csv` |
|---|---|---|---|---|
| 1. Rutina | `evals/semilla/rutina.json` | `Historia_Clinica_Electronica` | No | GS-27, GS-28 (certificado médico), GS-15 |
| 2. Urgencia | `evals/semilla/urgencia.json` | `Cola_Emergencia_Medica` + alerta | No | GS-07 (TEP, el caso del brief), GS-13, GS-18 |
| 3. Ambigüedad | `evals/semilla/ambiguedad.json` | `Cola_Revision_Humana` | Sí | GS-06 (dosis fuera de rango), GS-14, GS-22 |

### Escenario 1 — Rutina (certificado médico)
- **Contexto:** documento clínico simple y completo que llega por `POST /triage`.
- **Riesgo principal:** sobre-escalar (falsa urgencia, saturar emergencias) o dejarlo sin extraer y mandarlo a revisión innecesariamente.
- **Resiliencia/mitigación:** clasificación y extracción; enruta a la historia clínica sin intervención humana.
- **Evidencia en demo:** `rutina.json` → destino `Historia_Clinica_Electronica`, auditoría "No", objeto en `procesados/historia_clinica/`.

### Escenario 2 — Urgencia (TEP agudo)
- **Contexto:** informe con tromboembolismo pulmonar agudo (caso del brief, GS-07).
- **Riesgo principal:** un falso negativo retrasa la atención de una urgencia vital.
- **Resiliencia/mitigación:** regla de urgencia que se mantiene aun sin clave de modelo (fallback por reglas, según `docs/demo.md`); envío a emergencia y alerta.
- **Evidencia en demo:** `urgencia.json` → `Cola_Emergencia_Medica`, alerta generada, objeto en `procesados/urgentes/`.

### Escenario 3 — Ambigüedad (dosis dudosa)
- **Contexto:** receta con dosis dudosa o fuera de rango (GS-06).
- **Riesgo principal:** que el agente decida solo sobre un dato incierto y cause un daño al paciente.
- **Resiliencia/mitigación:** el agente no adivina: deriva a la cola de revisión humana con auditoría.
- **Evidencia en demo:** `ambiguedad.json` → `Cola_Revision_Humana`, auditoría "Sí", objeto en `auditoria_humana/`.

## 4. Guion por tiempos

| Tiempo | Bloque | Contenido |
|---|---|---|
| 0:00–0:20 | Intro | Qué es Mediflow y qué se va a demostrar. |
| 0:20–1:30 | Escenario A | Demo en vivo del flujo crítico y auditoría. |
| 1:30–2:45 | Escenario B | Provocar falla, mostrar recuperación. |
| 2:45–4:00 | Escenario C | Dos sesiones en paralelo, conflicto resuelto. |
| 4:00–4:30 | Cierre | Resumen de riesgos mitigados y próximos pasos. |

## 5. Storyboard

| Escena | Visual | Narración | Acción de producto/demo | Riesgo | Mitigación | Evidencia / fuente |
|---|---|---|---|---|---|---|
| 1. Intro | Logo + pantalla de inicio | "Mediflow: gestión de atención con resiliencia." | Abrir app en vivo | — | — | Brief |
| 2. Flujo crítico | Pantalla completa de la app | "Un paciente gestiona su atención." | Completar el flujo y mostrar auditoría | Pérdida/exposición de datos | Validación, roles, auditoría | Escenario 1 · `evals/semilla/rutina.json` |
| 3. Falla | App + panel de logs/estado | "Si un servicio falla, el sistema no se cae." | Provocar la falla y recuperar | Caída del servicio | Reintentos, degradación controlada | Escenario B · `docs/plan.md` |
| 4. Concurrencia | Pantalla dividida, 2 sesiones | "Dos usuarios, un solo turno." | Operar a la vez sobre el mismo recurso | Doble reserva | Control de concurrencia | Escenario C · `docs/plan.md` |
| 5. Cierre | Resumen en pantalla | "Tres riesgos, tres mitigaciones, en vivo." | — | — | — | Issue #73 |

## 6. Checklist de aceptación (issue #73)

- [ ] PR/evidencia previa vinculada (ninguna previa encontrada; ver sección 2).
- [ ] Los 3 escenarios del brief confirmados contra `docs/plan.md`/brief.
- [ ] Duración total entre 3 y 5 minutos.
- [ ] Producto en vivo en todas las escenas de demo.
- [ ] Decisión sobre `plan_golden.csv` registrada.
- [ ] **Guion aprobado en la sincronización del viernes 16.**
- [ ] Revisión correspondiente obtenida e integrada.
