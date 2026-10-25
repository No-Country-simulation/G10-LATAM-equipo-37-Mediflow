# Resultados oficiales de la evaluación

Aquí se publican las corridas de `evals/run.py` que cuentan: las que cita el README y las que muestra el dashboard (página **Métricas**, pestaña *Evaluación del agente*).

`evals/output/` sigue siendo la carpeta de trabajo de cada quien y no se versiona. Cuando una corrida es la oficial, se copia aquí.

## Una carpeta por corrida

```
evals/resultados/
└── AAAA-MM-DD_modelo/        p. ej. 2026-10-13_deepseek
    ├── report.md             el informe tal como lo escribe run.py
    └── resultados.json       el detalle por variante; es lo que lee el dashboard
```

- El nombre empieza por la fecha de la corrida, para que el dashboard muestre primero la más reciente.
- Después del guion bajo va el modelo principal (`deepseek`, `gemini`...).
- No se editan los archivos a mano: si algo está mal, se vuelve a correr.

## Cómo se genera

```bash
USE_LLM=true STORAGE_BACKEND=local python evals/run.py
mkdir -p evals/resultados/2026-10-13_deepseek
cp evals/output/report.md evals/output/resultados.json evals/resultados/2026-10-13_deepseek/
```

Las claves del modelo van en `.env` y nunca se suben. En el PR se anota el commit de `develop` con el que se corrió.

## Qué lee el dashboard

`GET /metrics/evaluacion` busca aquí las carpetas que tienen `resultados.json`, toma la más reciente (o la que se pida con `?corrida=`) y la cruza con `evals/golden/plan_golden.csv` para agrupar por tipo y por categoría. La imagen de la API copia esta carpeta y el plan (ver `api/Dockerfile`), así que una corrida nueva aparece en el dashboard con el siguiente despliegue.
