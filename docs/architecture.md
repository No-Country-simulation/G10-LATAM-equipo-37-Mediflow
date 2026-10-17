# Arquitectura

## Componentes

| Componente | Tecnología |
|---|---|
| LLM multimodal | Gemini (principal), Groq Llama 4 Scout y Mistral Small (respaldos), adaptador único con cambio automático |
| Orquestación | LangGraph |
| API | FastAPI |
| UI | Streamlit |
| Documentos | OCI Object Storage (Always Free) |
| Historial y reglas | Autonomous AI Database 26ai (Always Free), APEX para el dashboard |
| Alertas y reportes | OCI Notifications, OCI Email Delivery |
| Cómputo | VM Ampere A1 (Always Free), Docker Compose |
| Secretos | OCI Vault, instance principal |

## Grafo de decisión

```mermaid
flowchart TD
    A["Ingesta: PDF, imagen, texto o JSON"] --> B["Normalizar: detectar formato, extraer texto o renderizar páginas"]
    B --> C{"Legible?"}
    C -- "No" --> H["Cola de Revisión Humana"]
    C -- "Sí" --> D["Clasificar: tipo, especialidad, prioridad"]
    D --> E["Extraer con esquema Pydantic por tipo"]
    E --> F["Validar: obligatorios, CIE-10, dosis, matrícula, consistencia"]
    F --> G["Score de confianza compuesto"]
    G --> U{"Urgencia o alto riesgo?"}
    U -- "Sí" --> Q1["Cola de Emergencia Médica y alerta"]
    U -- "No" --> T{"Score alto y sin conflictos?"}
    T -- "Sí" --> R{"Tipo de documento"}
    T -- "No" --> S{"Score medio?"}
    S -- "Sí" --> V["Segunda opinión con otro modelo, una sola vez"]
    V --> W{"Acuerdo?"}
    W -- "Sí" --> R
    W -- "No" --> H
    S -- "No" --> H
    R -- "Receta" --> Q2["Farmacia Hospitalaria"]
    R -- "Orden de procedimiento" --> Q3["Auditoría de Autorizaciones"]
    R -- "Informe, epicrisis o certificado" --> Q4["Historia Clínica Electrónica"]
    H --> X["Auditor aprueba, corrige o rechaza"]
    X --> R
    Q1 --> P["Persistir en Object Storage y ADB, responder JSON"]
    Q2 --> P
    Q3 --> P
    Q4 --> P
    H --> P
```

## Layout de Object Storage

```
mediflow-documentos-clinicos/
  recibidos/{documento_id}.{pdf|png|jpg|txt|json}
  procesados/urgentes/{documento_id}.json
  procesados/farmacia/{documento_id}.json
  procesados/autorizaciones/{documento_id}.json
  procesados/historia_clinica/{documento_id}.json
  auditoria_humana/{documento_id}/original.{ext}
  auditoria_humana/{documento_id}/extraccion.json
  rechazados/{documento_id}.json
  reportes/diario/{fecha}.json
```
