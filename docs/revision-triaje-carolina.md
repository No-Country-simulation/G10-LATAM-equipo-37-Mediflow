# Revisión de Carolina · MediFlow · 24/09/2026

Revisión sobre develop 27a68ea que incorpora los cuatro adjuntos de María y agrega regresiones de Carolina.

## Cambios
- Incluye los nodos y tests originales de María: regla A, detección de laboratorio y correcciones de auditoría.
- Carolina: campos faltantes, errores y categoría de ambigüedad requieren revisión aunque el score sea alto. Si hay urgencia, mantiene Emergencia y marca auditoría.
- La notificación usa exclusivamente paciente.nombre, conforme a la decisión del equipo.
- Filtra negaciones directas de hallazgos y palabras de urgencia (sin evidencia de, sin signos de, sin datos de, no hay, no presenta, no se observa, no se detecta). No suprime «no se descarta» ni una segunda mención afirmativa ni la urgencia del modelo.

## Evidencia
- Tests de María contra develop: 16 pasan, 11 fallan.
- Tests de María con sus nodos: 27 pasan.
- Propuesta con 27 regresiones nuevas y tests existentes agent/tests + api/tests: 70 pasan.
- Ruff completo: sin errores tras ordenar imports preexistentes en graph.py, test_ingestion.py y api/main.py.
- Codacy MCP no disponible en la sesión; análisis pendiente del servicio de CI.
- Pruebas locales sin LLM ni llamadas OCI; no constituyen evaluación clínica ni validación del modelo real.

## Pendientes y límites
- La base develop 27a68ea aún contiene nome en extracción, validación y esquema. Deben alinearse a nombre en la integración del equipo; este PR cambia el consumidor de alertas, no esos módulos.
- Negación: pendiente de revisión colectiva; heurística acotada, no resuelve listas coordinadas, temporalidad ni contexto clínico general; requiere evaluación adicional antes de uso real.
- El parser de laboratorio de María compara números sin validar unidades ni contexto de rangos de referencia. No se modificó en esta propuesta.
- La validación existente todavía es provisional: enrutar respeta los problemas que recibe, pero no garantiza que validar detecte todos.
- No implementa N2-05 (pausa/reanudación humana).

## Reproducción

    python -m pytest -q
    python -m ruff check .

Ejecutar con USE_LLM=false y STORAGE_BACKEND=local en el entorno del proyecto.

## AMB-6: contrato propuesto entre nodos

El productor de validación debe entregar `validacion.categoria_amb = "AMB-6"` y `validacion.motivo_fuera_de_alcance` con una clave de `rules.yaml` (`no_clinico`, `tipo_no_soportado`, `paciente_no_humano`, `idioma_no_soportado`, `pide_diagnostico`) o una descripción textual. El enrutamiento conserva la descripción en la justificación y la traza. Si falta motivo lo indica explícitamente, sin inventarlo.

AMB-6 tiene precedencia sobre el destino por tipo, ilegibilidad y la marca de urgencia: revisión humana, auditoría obligatoria y sin alerta de guardia. Es un límite del sistema, no un defecto del documento. Las otras ambigüedades mantienen la política de urgencia primero.

Los tests inyectan estados de validación: verifican el enrutamiento, no detección automática de facturas, idioma o pacientes no humanos. El nodo productor aún debe implementar esa detección y acordar el campo propuesto.
