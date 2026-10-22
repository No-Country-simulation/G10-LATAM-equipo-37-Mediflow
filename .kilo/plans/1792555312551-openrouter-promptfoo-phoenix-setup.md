# OpenRouter + Promptfoo + Arize Phoenix Setup Plan

## Goal
Configure OpenRouter as the LLM provider for both Promptfoo (eval) and Arize Phoenix/OpenInference (observability) in the MediFlow backend, using free OpenRouter models.

## Context
- Current LLM stack: LiteLLM abstraction → Gemini (primary) + Groq/Mistral (fallbacks)
- No existing Promptfoo or Phoenix configuration
- Two LLM nodes: `clasificar` (triage) and `extraer` (extraction)
- Environment config in `.env.example`

## Model Selection (Free Tier)
Based on OpenRouter free models suitable for clinical tasks:

| Node | Recommended Free Model | Rationale |
|------|------------------------|-----------|
| **clasificar** (triage) | `meta-llama/llama-3.2-3b-instruct:free` | Good reasoning, 128k context, fast |
| **extraer** (extraction) | `mistralai/mistral-7b-instruct:free` | Strong structured output, JSON mode support |

Alternative: `google/gemma-2-9b-it:free` for either (strong multilingual).

## Implementation Tasks

### 1. Update Environment Configuration
**File:** `.env.example`
- Add `OPENROUTER_API_KEY=` placeholder
- Update `LLM_PRIMARY` to use OpenRouter model format (e.g., `openrouter/meta-llama/llama-3.2-3b-instruct:free`)
- Update `LLM_FALLBACKS` with additional free models

### 2. Update LLM Adapter for OpenRouter
**File:** `agent/llm/adapter.py`
- LiteLLM already supports OpenRouter via `openrouter/` prefix
- Verify `base_url` and headers work correctly
- Add optional `extra_headers` for OpenRouter ranking (HTTP-Referer, X-Title)

### 3. Create Promptfoo Configuration
**File:** `promptfooconfig.yaml` (new)
- Define providers for both free models
- Use `${OPENROUTER_API_KEY}` variable interpolation
- Create test cases for triage classification (ALTA/MEDIA/BAJA → maps to Urgente/Prioritario/Rutina)
- Create test cases for extraction (structured JSON validation)

### 4. Add Arize Phoenix / OpenInference Integration
**Files:** 
- `requirements.txt` → add `arize-phoenix`, `openinference-instrumentation-openai`
- `agent/llm/phoenix.py` (new) → initialization module
- Update `api/main.py` and `worker/main.py` to initialize Phoenix on startup
- Instrument the OpenAI-compatible client used via LiteLLM

### 5. Create AGENTS.md
**File:** `AGENTS.md` (new)
- Document provider setup (OpenRouter free models)
- Document Phoenix local monitoring
- Document Promptfoo validation workflow
- Development agent actions checklist

### 6. Validation
- Run `promptfoo eval` with test cases
- Verify traces appear in Phoenix UI (localhost:6006)
- Test fallback chain with multiple free models

## Open Questions / Decisions Needed

1. **Phoenix deployment**: Run Phoenix as separate service (docker-compose) or in-process? → Recommend in-process for dev, separate container for CI.
2. **Promptfoo test data**: Use existing test fixtures from `agent/tests/` or create new synthetic cases?
3. **Model routing**: Should triage and extraction use different models, or same model for simplicity?

## Risk Mitigation
- Free models have rate limits → configure generous backoff in adapter
- Free models may not support JSON mode reliably → keep regex fallback
- Phoenix in-process may add latency → make initialization lazy/optional

## Rollout Order
1. `.env.example` + adapter update (core infra)
2. Promptfoo config + test cases (validation)
3. Phoenix integration (observability)
4. AGENTS.md (documentation)
5. CI integration (optional, later)