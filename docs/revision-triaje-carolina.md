# Revisión de Carolina · MediFlow · 24/09/2026

Revisión sobre develop 27a68ea que incorpora los cuatro adjuntos de María y agrega regresiones de Carolina.

## Cambios
- Incluye los nodos y tests originales de María: regla A, detección de laboratorio y correcciones de auditoría.
- Carolina: campos faltantes, errores y categoría de ambigüedad requieren revisión aunque el score sea alto. Si hay urgencia, mantiene Emergencia y marca auditoría.
- La notificación acepta paciente.nombre y paciente.nome durante la transición. No migra esquemas, extracción ni contrato público.
- Filtra negaciones directas de hallazgos y palabras de urgencia (sin evidencia de, sin signos de, sin datos de, no hay, no presenta, no se observa, no se detecta). No suprime «no se descarta» ni una segunda mención afirmativa ni la urgencia del modelo.

## Evidencia
- Tests de María contra develop: 16 pasan, 11 fallan.
- Tests de María con sus nodos: 27 pasan.
- Propuesta con 14 regresiones nuevas y tests existentes agent/tests + api/tests: 57 pasan.
- Ruff completo: sin errores tras ordenar imports preexistentes en graph.py, test_ingestion.py y api/main.py.
- Codacy MCP no disponible en la sesión; análisis pendiente del servicio de CI.
- Pruebas locales sin LLM ni llamadas OCI; no constituyen evaluación clínica ni validación del modelo real.

## Pendientes y límites
- Acordar con el equipo la migración integral nome/nombre. El fallback solo evita perder el nombre en la alerta.
- Negación: heurística acotada, no resuelve listas coordinadas, temporalidad ni contexto clínico general; requiere evaluación adicional antes de uso real.
- El parser de laboratorio de María compara números sin validar unidades ni contexto de rangos de referencia. No se modificó en esta propuesta.
- La validación existente todavía es provisional: enrutar respeta los problemas que recibe, pero no garantiza que validar detecte todos.
- No implementa N2-05 (pausa/reanudación humana).

## Reproducción

    python -m pytest -q
    python -m ruff check .

Ejecutar con USE_LLM=false y STORAGE_BACKEND=local en el entorno del proyecto.
