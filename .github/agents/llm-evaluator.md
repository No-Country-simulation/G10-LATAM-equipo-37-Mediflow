# LLM Evaluator Agent

## Description
Agente evaluador automático para MediFlow. Ejecuta evaluaciones de triaje clínico usando Promptfoo cuando se detecta la etiqueta "evals" en un PR.

## Configuration
- **Model**: meta-llama/llama-3.2-3b-instruct:free (gratuito, adecuado para clasificación médica)
- **Fallback**: openrouter/mistralai/mistral-7b-instruct:free
- **Trigger**: PRs con label "evals"
- **Action**: Ejecuta `promptfoo eval -c promptfooconfig.yaml`

## Prompt Template
```
Sos un agente de triaje clínico. Analizá el siguiente texto y clasificá la prioridad (ALTA, MEDIA, BAJA): {{historial}}
```

## Test Cases
El archivo `promptfooconfig.yaml` incluye 6 casos de prueba cubriendo:
- Infarto agudo de miocardio (ALTA)
- Faringitis leve / certificado médico (BAJA)
- Neumonía lobar (ALTA)
- Control HTA estable (BAJA)
- Gastroenteritis con deshidratación en pediatría (ALTA)
- Dermatitis de contacto leve (BAJA)

## CI Integration
El workflow `.github/workflows/ci.yml` ya incluye un job `evals` que:
1. Se ejecuta en PRs con label "evals"
2. Corre `python evals/run.py` (wrapper para promptfoo)
3. Reporta resultados en GitHub Checks

## Evaluación de Calidad
- **Accuracy objetivo**: >90% en clasificación de prioridad
- **Latencia**: <5s por evaluación
- **Costo**: $0.00 (modelos gratuitos)
