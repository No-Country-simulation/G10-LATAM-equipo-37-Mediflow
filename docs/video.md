# F-01: Guion y storyboard del video (issue #73)

- Issue: #73 — F-01: Guion y storyboard del video
- Responsable: Alessandro · Apoyo: Sabrina · Dependencia: N1-10
- Fechas del plan: 13/10 a 16/10 · Aprobación: sincronización del **viernes 16**
- Estado: **borrador para revisión**

## 1. Objetivo

Video de **3 a 5 minutos (objetivo: 4:30)** que muestre **Mediflow en vivo** (producto funcionando, sin mockups)
resolviendo los **3 escenarios del brief de mayor riesgo y resiliencia**.

## 2. Fuentes y documentos utilizados

Evidencia previa revisada (13/10/2026): en la rama base solo existe `README.md` (vacío). No existían `docs/video.md`,
`docs/plan.md` ni `plan_golden.csv`. El único PR relacionado es #104 (borrador de este mismo trabajo); no hay material que reutilizar.

| Fuente | Uso | Por qué / cómo |
|---|---|---|
| `docs/plan.md` (redistribución vigente del 7/10/2026) | **Fuente principal** | Es la fuente declarada en el issue #73 (fechas, responsables, dependencia N1-10). Define qué escenarios y flujos se priorizan. **No está en el repositorio**: debe incorporarse o enlazarse antes de aprobar. |
| Brief del proyecto | Fuente de los 3 escenarios | El issue pide los 3 escenarios del brief de mayor riesgo/resiliencia. |
| `plan_golden.csv` | **Descartado como fuente principal; opcional como apoyo** | El issue no lo menciona y no existe en el repo. Solo se usaría como datos de ejemplo (casos "golden") para la demo si el equipo confirma que existe; el guion no depende de él. |

## 3. Escenarios de mayor riesgo y resiliencia

> Los títulos siguientes son una **propuesta** a confirmar contra el brief y `docs/plan.md` en la sync del viernes 16.
> Si el brief define otros, se reemplazan manteniendo la estructura.

### Escenario A — Flujo crítico de punta a punta (turno/atención) con datos sensibles
- **Contexto:** un paciente solicita/gestiona una atención y el personal la procesa en el producto en vivo.
- **Riesgo principal:** error o pérdida de datos clínicos/personales en el flujo central.
- **Resiliencia/mitigación:** validaciones, control de acceso por rol y registro de auditoría.
- **Evidencia en demo:** flujo completado en vivo; registro de auditoría visible; acceso denegado a un rol no autorizado.

### Escenario B — Falla de un componente/servicio dependiente
- **Contexto:** durante la operación se cae o demora un servicio externo/interno.
- **Riesgo principal:** interrupción del servicio o pérdida de operaciones en curso.
- **Resiliencia/mitigación:** reintentos, degradación controlada y mensajes claros al usuario; sin pérdida de datos.
- **Evidencia en demo:** falla provocada en vivo, el sistema sigue operando y se recupera; logs/estado de salud.

### Escenario C — Concurrencia y consistencia (conflictos/duplicados)
- **Contexto:** dos usuarios intentan operar sobre el mismo recurso (p. ej. mismo turno) a la vez.
- **Riesgo principal:** doble reserva o estado inconsistente.
- **Resiliencia/mitigación:** control de concurrencia/idempotencia; el segundo intento recibe un rechazo claro.
- **Evidencia en demo:** dos sesiones en paralelo; solo una operación se confirma, la otra se rechaza sin corrupción.

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
| 2. Flujo crítico | Pantalla completa de la app | "Un paciente gestiona su atención." | Completar el flujo y mostrar auditoría | Pérdida/exposición de datos | Validación, roles, auditoría | Escenario A · `docs/plan.md` |
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
