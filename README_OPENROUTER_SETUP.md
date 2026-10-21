# OpenRouter + Promptfoo + Phoenix Setup

Quick start guide for the OpenRouter integration PR (#150).

## Quick Steps

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key:
# OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxx
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt -r requirements-dev.txt
npm install -g promptfoo
```

### 3. Run Critical Tests (Promptfoo)
```bash
promptfoo eval -c promptfooconfig.yaml --tags critical
```

### 4. Start API with Phoenix (Observability)
```bash
ENV=dev uvicorn api.main:app --reload
```
Phoenix UI available at: **http://localhost:6006**

### 5. Test End-to-End
```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"documento_id":"test-001","tipo_archivo":"TEXTO","documento_texto":"Paciente con dolor toracico opresivo de 2 horas de evolucion","canal_origen":"test"}'
```

### 6. Verify in Phoenix UI
Open http://localhost:6006 → Check traces for `clasificar` and `extraer` spans with tokens, latency, cost.

## Models Used (Free Tier)
| Task | Model | Temp |
|------|-------|------|
| Triage | `meta-llama/llama-3.2-3b-instruct:free` | 0.1 |
| Extraction | `mistralai/mistral-7b-instruct:free` | 0.0 |
| Fallback | `google/gemma-2-9b-it:free` | 0.0 |

## Key Files
- `.env.example` — Configuration template
- `agent/llm/adapter.py` — LLM adapter with fallback chain
- `agent/llm/phoenix.py` — Phoenix initialization
- `promptfooconfig.yaml` — Test suites
- `AGENTS.md` — Full workflow documentation