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
| 0:00–0:25 | Intro | Qué es Mediflow y qué se va a demostrar (3 escenarios, producto en vivo). |
| 0:25–1:25 | Escenario 1 · Rutina | Enviar `rutina.json`; mostrar destino Historia Clínica y sin auditoría. |
| 1:25–2:40 | Escenario 2 · Urgencia | Enviar `urgencia.json` (TEP); mostrar Cola de Emergencia y alerta. |
| 2:40–3:55 | Escenario 3 · Ambigüedad | Enviar `ambiguedad.json`; mostrar Cola de Revisión Humana y auditoría. |
| 3:55–4:30 | Cierre | Resultados de la evaluación (`plan_golden.csv`/`evals/run.py`) y próximos pasos. |

## 5. Storyboard

| Escena | Visual | Narración | Acción de producto/demo | Riesgo | Mitigación | Evidencia / documento fuente |
|---|---|---|---|---|---|---|
| 1. Intro | Logo + UI de carga | "Mediflow enruta documentos clínicos y sabe cuándo no decidir solo." | Abrir la app en vivo | — | — | `docs/plan.md` (H5) |
| 2. Rutina | UI/terminal con `rutina.json` y la respuesta | "Un certificado médico simple va directo a la historia clínica." | `POST /triage` con `rutina.json` | Sobre-escalar o revisión innecesaria | Clasificación y extracción | `evals/semilla/rutina.json`, `docs/demo.md`; ref. GS-27/GS-28 |
| 3. Urgencia | Respuesta + cola de emergencia y alerta | "Un TEP agudo llega a emergencia con alerta, sin esperar a nadie." | `POST /triage` con `urgencia.json` | Falso negativo en una urgencia vital | Regla de urgencia (también en fallback) | `evals/semilla/urgencia.json`, `docs/demo.md`; ref. GS-07 |
| 4. Ambigüedad | Respuesta + cola de revisión humana | "Ante una dosis dudosa, el agente no adivina: deriva a una persona." | `POST /triage` con `ambiguedad.json` | Decisión automática sobre dato incierto | Revisión humana con auditoría | `evals/semilla/ambiguedad.json`, `docs/demo.md`; ref. GS-06 |
| 5. Cierre | Resumen + métricas de evaluación | "Tres riesgos, tres mitigaciones, en vivo y medidos." | Mostrar el reporte de `evals/run.py` | — | — | `evals/golden/plan_golden.csv`; issue #73 |

## 6. Checklist de aceptación (issue #73)

- [ ] Integrar `docs/demo.md` y `evals/semilla/` (N1-10) en `develop`, o confirmar la rama de la demo.
- [ ] Los 3 escenarios (rutina, urgencia, ambigüedad) corren en vivo con los archivos semilla.
- [ ] Duración total entre 3 y 5 minutos.
- [ ] Decisión sobre `plan_golden.csv` registrada (apoyo para validar resultados, no fuente principal).
- [ ] **Guion aprobado en la sincronización del viernes 16.**
- [ ] Revisión correspondiente obtenida e integrada.
