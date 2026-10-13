# Guion y storyboard del video (F-01)

Paquete **F-01** de `docs/plan.md` (redistribución vigente del 7/10/2026). Issue #73.

| Campo | Valor |
|---|---|
| Responsable / apoyo | Alessandro / Sabrina |
| Fechas | 13/10 a 16/10 |
| Depende de | N1-10 (tres escenarios reproducibles); N1-06 (regla A) fusionado y desplegado en la VM |
| Duración objetivo | 4:00 (rango permitido: 3 a 5 minutos) |
| Criterio de aceptación | Guion aprobado en la sincronización del viernes 16/10 |
| Pasos siguientes | F-03 ensayo con persona externa (17/10), F-04 grabación (21/10) |

Regla de producción: todo se muestra **en vivo desde la URL pública en OCI**, nunca desde localhost. Presenta el producto Alessandro; los resultados de la evaluación los presenta Sabrina (F-04).

## Los tres escenarios elegidos

Son los de mayor riesgo y resiliencia entre los escenarios de demostración del README (sección «Escenarios de demostración»). La rutina se muestra solo como contraste de 20 s al inicio.

| # | Escenario | Qué demuestra | Documento (de `evals/golden/plan_golden.csv`) | Resultado esperado |
|---|---|---|---|---|
| 1 | **Urgencia** | Riesgo vital detectado y alertado | `GS-07` (informe de tomografía con tromboembolismo pulmonar agudo; `evals/golden/files/GS-07.txt` y `GS-07_escaneado.png`); caso del brief en `docs/examples/triage_request.json` | `Cola_Emergencia_Medica`, prioridad `Urgente`, alerta a Slack vía n8n, objeto en `procesados/urgentes/` |
| 2 | **Ambigüedad y resiliencia** | El sistema no adivina: duda, deriva a una persona y tolera entradas malas | `M4` (receta manuscrita con dosis dudosa, AMB-4, legibilidad media; `evals/handwritten/M4.jpg`). Respaldo: `M7` (ilegible, severa) y `GS-06` (AMB-3, texto) | `M4`: `Cola_Revision_Humana`, `requiere_auditoria_humana: true`; el auditor corrige y se reencamina a Farmacia, o rechaza y queda en `rechazados/`. `M7`: `Cola_Revision_Humana` con motivo «solicitar nueva captura» |
| 3 | **Alto riesgo** | El medicamento peligroso se audita, no se confunde con una urgencia | `GS-04` (receta con enoxaparina, en `medicamentos_alto_riesgo`; `evals/golden/files/GS-04.txt`). Alternativas: `GS-03`, `GS-05` | `Farmacia_Hospitalaria` con `requiere_auditoria_humana: true`; no va a Emergencia (regla A de N1-06, que debe ignorar la frase «Consultar de urgencia ante sangrado») |

Contraste de apertura (rutina): `GS-27` (certificado médico; `evals/golden/files/GS-27.txt` y `GS-27_foto.png`) → `Historia_Clinica_Electronica`, sin auditoría. No usar `GS-25` para la rutina: sin N1-06 sale como falsa urgencia.

## Rutina / apertura alternativa

Como contraste de apertura para la rutina, también puede usarse `GS-28` (`evals/golden/files/GS-28.txt` y `GS-28_foto.png`), que corresponde a un certificado médico y va a `Historia_Clinica_Electronica`, sin auditoría.

## Storyboard y guion

| Tiempo | Plano / pantalla en vivo | Narración (voz de Alessandro salvo indicación) | Evidencia a la vista |
|---|---|---|---|
| 0:00–0:20 | Título y diagrama del flujo (`docs/flujo-del-dato.png`) | «Cada día llegan miles de documentos clínicos y alguien los clasifica a mano. MediFlow lee, clasifica, puntúa la confianza y enruta, y cuando no está seguro, lo dice.» | Diagrama del flujo |
| 0:20–0:40 | UI de carga: se sube `GS-27` (rutina) y llega a Historia Clínica | «Un caso rutinario pasa solo: sin auditoría, a su destino.» | Cola de triaje, destino y score |
| 0:40–1:50 | **Escenario 1.** Subir `GS-07`; seguir el procesamiento en la página de trazas; abrir la alerta en Slack | «Una tomografía con tromboembolismo pulmonar agudo. El sistema lo reconoce como hallazgo crítico, va a Emergencia y la alerta llega a Slack en segundos.» Mostrar la evidencia por campo (frase del informe que justifica el hallazgo) | `status`, `Cola_Emergencia_Medica`, `evidencias`, mensaje de Slack, objeto en `procesados/urgentes/` |
| 1:50–3:00 | **Escenario 2.** Subir la foto `M4.jpg`; mostrar score bajo y el motivo; entrar al panel del auditor; corregir la dosis y reencaminar. Plano corto: `M7.jpg` (ilegible) enviada a Revisión Humana con el motivo «solicitar nueva captura» | «Esta receta manuscrita tiene una dosis dudosa. El sistema no adivina: baja el score, la envía a Revisión Humana y explica por qué. El auditor corrige y el documento sigue a Farmacia. Si la foto es ilegible, tampoco la adivina: la deriva a Revisión Humana y pide una nueva captura.» Si falla el modelo principal, mostrar en la traza el modelo de respaldo usado | Score y componentes en la traza, `modelo_utilizado`, acción del auditor, motivo «solicitar nueva captura» en `Cola_Revision_Humana` |
| 3:00–3:30 | **Escenario 3.** Subir `GS-04` (enoxaparina) | «Un anticoagulante es de alto riesgo, pero no es una urgencia clínica: va a Farmacia Hospitalaria con auditoría obligatoria, no a Emergencia.» | `Farmacia_Hospitalaria`, `requiere_auditoria_humana: true`, medicamento marcado |
| 3:30–3:50 | Panel de métricas / resultados de `evals/output/` (voz de Sabrina) | «Medimos sobre un conjunto de 45 elementos, sin ajustar prompts mirando el conjunto de prueba: aciertos de clasificación, destino y auditoría.» | Números que coinciden con el README final (F-06) |
| 3:50–4:00 | Cierre con URL pública y equipo | «MediFlow: automatiza lo rutinario, escala lo urgente y pide ayuda cuando duda.» | URL pública, nombres del equipo |

## Material reutilizado y por completar

Reutilizado (no se rehace):

- Escenarios y resultados esperados: README, «Escenarios de demostración», y `docs/api-contract.md` §7.
- Datos: `evals/golden/plan_golden.csv`, `evals/golden/files/`, `evals/handwritten/`, `docs/examples/triage_request.json` y `docs/examples/triage_response.json`.
- Guion corto de los tres escenarios reproducibles: `docs/demo.md` y `evals/semilla/` (N1-10). **No existen aún en el repositorio**; este guion los referencia como dependencia y se ajustará a ellos cuando se incorporen.

Se completa aquí: selección de casos, tiempos, narración, planos y evidencia visible por escena.

## Pendientes antes de grabar

- [ ] Confirmar que N1-06 (hoy en #3 / #86) esté fusionado y desplegado en la VM: el Escenario 3 (`GS-04`) depende de la regla A.
- [ ] Confirmar con Camila que `GS-07`, `M4`, `M7` y `GS-04` dan los resultados esperados en la URL pública de OCI.
- [ ] Alertas a Slack vía n8n funcionando (N2-09, N3-08); si no estuvieran, mostrar la alerta por correo.
- [ ] Preparar el caso de modelo de respaldo (`LLM_FALLBACKS`) para mostrarlo en la traza.
- [ ] Conciliar el tamaño del conjunto de prueba: `plan_golden.csv` tiene 45 elementos (coincide con este guion), pero el README menciona 56 casos. Revisar con Camila en F-06 antes de grabar.
- [ ] Cronometrar: el total debe quedar entre 3:00 y 5:00.

## Cómo validar este guion

1. Verificar que cada ID citado exista en `evals/golden/plan_golden.csv` y que su destino y auditoría coincidan con la tabla de escenarios.
2. Abrir los archivos citados en `evals/golden/files/` y `evals/handwritten/`.
3. Cronometrar leyendo la narración en voz alta con la demo en vivo (F-03).
4. Aprobar en la sincronización del viernes 16/10.
