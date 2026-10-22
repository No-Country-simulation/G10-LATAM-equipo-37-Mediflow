# MediFlow Agent Workflow Configuration (`AGENTS.md`)

## 🛠️ Entorno de Proveedores

- **Proveedor Principal:** OpenRouter (modelos gratuitos recomendados):
  - `meta-llama/llama-3.2-3b-instruct:free` — triaje/clasificación (rápido, buen razonamiento)
  - `mistralai/mistral-7b-instruct:free` — extracción de datos (JSON estructurado fuerte)
  - `google/gemma-2-9b-it:free` — alternativa multilingüe
- **Monitoreo:** Arize Phoenix local (OpenInference) escuchando trazas instrumentadas de LiteLLM.
  - UI: `http://localhost:6006` (auto-iniciado en `ENV=dev`)
  - Datos persistidos en `./phoenix_data/`
- **Validación:** Pruebas automatizadas mediante CLI de `promptfoo` (`promptfooconfig.yaml`).

## 📋 Acciones del Agente de Desarrollo

Al modificar prompts o flujos lógicos en las carpetas del backend (`agent/prompts/`, `agent/nodes/`, `agent/graph.py`):

1. **Validar entorno local**
   ```bash
   # Verificar que la clave está cargada
   cat .env | grep OPENROUTER_API_KEY
   # Debe mostrar: OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxx
   ```

2. **Ejecutar validación con Promptfoo**
   ```bash
   # Instalar promptfoo (una vez)
   npm install -g promptfoo
   
   # Ejecutar evaluación completa
   promptfoo eval -c promptfooconfig.yaml
   
   # Ver reporte HTML
   promptfoo view
   ```
   - Verificar que no fallen aserciones críticas (tag `critical`)
   - Revisar comparación cross-model (tag `cross_model`)

3. **Verificar trazas en Phoenix**
   ```bash
   # Iniciar API (Phoenix auto-inicia en puerto 6006)
   uvicorn api.main:app --reload
   
   # Procesar un documento de prueba
   curl -X POST http://localhost:8000/triage \
     -H "Content-Type: application/json" \
     -d '{"documento_id":"test-001","tipo_archivo":"TEXTO","documento_texto":"Paciente con dolor toracico...","canal_origen":"test"}'
   
   # Abrir UI de Phoenix
   open http://localhost:6006
   ```
   - Confirmar que aparecen spans de `clasificar` y `extraer`
   - Verificar tokens, latencia, costo estimado

4. **Ejecutar tests unitarios**
   ```bash
   pytest agent/tests/ -v -k "clasificar or extraer"
   ```

5. **Lint y typecheck**
   ```bash
   ruff check .
   # mypy si está configurado
   ```

## 🔧 Configuración de Variables de Entorno

Crear `.env` en la raíz del proyecto (basado en `.env.example`):

```bash
# OpenRouter (obtener clave en https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxx

# Modelo primario (triage) y fallbacks (extracción, alternativo)
LLM_PRIMARY=openrouter/meta-llama/llama-3.2-3b-instruct:free
LLM_FALLBACKS=openrouter/mistralai/mistral-7b-instruct:free,openrouter/google/gemma-2-9b-it:free

# Phoenix (observabilidad)
PHOENIX_ENABLED=true
PHOENIX_PORT=6006
PHOENIX_WORKING_DIR=./phoenix_data

# Headers opcionales OpenRouter (ranking/atribución)
OPENROUTER_REFERER=https://github.com/MediFlow
OPENROUTER_TITLE=MediFlow App
```

## 🏗️ Arquitectura de LLM Nodes

```
┌─────────────────────────────────────────────────────────────┐
│                    LiteLLM Adapter                            │
│  (agent/llm/adapter.py — fallback chain + backoff + cost)    │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  clasificar   │           │   extraer     │
│  (triage)     │           │ (extraction)  │
│  Model:       │           │  Model:       │
│  Llama-3.2-3B │           │  Mistral-7B   │
│  Temp: 0.1    │           │  Temp: 0.0    │
└───────┬───────┘           └───────┬───────┘
        │                           │
        ▼                           ▼
   JSON output                  JSON output
   (priority,                   (structured
    type, confidence)             clinical data)
```

### Chain de Fallback (configurable via `.env`)

1. **PRIMARY**: `openrouter/meta-llama/llama-3.2-3b-instruct:free`
2. **FALLBACK 1**: `openrouter/mistralai/mistral-7b-instruct:free`
3. **FALLBACK 2**: `openrouter/google/gemma-2-9b-it:free`

- Reintentos por modelo: `LLM_REINTENTOS=3` (backoff exponencial 2s, 4s, 8s)
- Errores recuperables: 429 (rate limit), 5xx, timeout
- Costo estimado: $0.00 (modelos :free)

## 🧪 Promptfoo Test Suite (`promptfooconfig.yaml`)

### Categorías de Tests

| Tag | Descripción | Modelos |
|-----|-------------|---------|
| `critical` | Casos que DEBEN clasificar como Urgente (infarto, TEP, ACV, sepsis) | Llama-3.2-3B |
| `urgent` | Prioritario (apendicitis, neumonía, cetoacidosis) | Llama-3.2-3B |
| `routine` | Rutina (control HTA, recetas, dermatología) | Llama-3.2-3B |
| `out_of_scope` | No clínico, pide diagnóstico | Llama-3.2-3B |
| `extraction` | Extracción estructurada por tipo de documento | Mistral-7B |
| `edge_case` | Ilegible, múltiples documentos (AMB-5) | Mistral-7B |
| `cross_model` | Mismo test en los 3 modelos free | Los 3 |

### Ejecutar subset de tests

```bash
# Solo tests críticos
promptfoo eval -c promptfooconfig.yaml --tags critical

# Solo extracción
promptfoo eval -c promptfooconfig.yaml --tags extraction

# Comparar modelos
promptfoo eval -c promptfooconfig.yaml --tags cross_model
```

## 🔍 Phoenix / OpenInference

### Qué se instrumenta automáticamente

- ✅ Llamadas a `litellm.completion()` (vía `LiteLLMInstrumentor`)
- ✅ Llamadas compatibles OpenAI (vía `OpenAIInstrumentor`)
- ✅ Tokens entrada/salida, latencia, costo estimado
- ✅ Metadata: modelo, nodo (clasificar/extraer), prompt hash

### Acceder a la UI

```bash
# En terminal separada mientras corre la API/worker
# Phoenix corre en background, no bloquea
open http://localhost:6006
```

### Estructura de trazas

Cada ejecución del grafo genera una traza con spans:

```
triage_run (root)
├── normalizar
├── clasificar (LLM call → Llama-3.2-3B)
│   ├── input: prompt + documento
│   ├── output: JSON clasificación
│   └── metadata: tokens, latency, cost
├── extraer (LLM call → Mistral-7B)
│   ├── input: prompt + documento + tipo
│   ├── output: JSON extracción + evidencias
│   └── metadata: tokens, latency, cost
├── validar
├── puntuar
├── detectar_urgencia
├── enrutar
├── persistir
└── notificar
```

## 🚀 Comandos Rápidos (Makefile)

```bash
# Instalar dependencias
make install-dev

# Ejecutar API + Phoenix
make run-api

# Ejecutar Worker + Phoenix
make run-worker

# Evaluar prompts
make eval-prompts

# Ver reporte promptfoo
make view-eval

# Tests
make test

# Lint
make lint
```

### Agregar a `Makefile`

```makefile
.PHONY: run-api run-worker eval-prompts view-eval

run-api:
	ENV=dev uvicorn api.main:app --reload --port 8000

run-worker:
	ENV=dev python -m worker.main

eval-prompts:
	promptfoo eval -c promptfooconfig.yaml

view-eval:
	promptfoo view

install-dev:
	pip install -r requirements-dev.txt
	npm install -g promptfoo
```

## ⚠️ Limitaciones Modelos Free

| Limitación | Impacto | Mitigación |
|------------|---------|------------|
| Rate limit estricto | 429 errors frecuentes | Backoff exponencial en adapter (2s, 4s, 8s) |
| Sin JSON mode garantizado | Parsing puede fallar | Fallback regex en `clasificar.py` y `extraer.py` |
| Contexto limitado (32k-128k) | Documentos largos truncados | Pre-procesamiento en `normalizar` |
| Calidad variable | Falsos negativos en triaje | Tests `critical` obligatorios en CI |

## 📝 Checklist Pre-Commit

- [ ] `OPENROUTER_API_KEY` configurada en `.env` local
- [ ] `promptfoo eval` pasa todos los tests `critical`
- [ ] Phoenix UI muestra trazas completas sin errores
- [ ] `pytest agent/tests/test_clasificar.py agent/tests/test_extraer.py` pasa
- [ ] `ruff check .` sin errores
- [ ] Cambios en prompts documentados en PR description

## 🔗 Referencias

- OpenRouter Models: https://openrouter.ai/models
- Promptfoo Docs: https://www.promptfoo.dev/docs/
- Arize Phoenix: https://phoenix.arize.com/
- OpenInference: https://github.com/Arize-ai/openinference
- LiteLLM OpenRouter: https://docs.litellm.ai/docs/providers/openrouter