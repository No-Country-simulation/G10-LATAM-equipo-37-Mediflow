# Contratos

Los esquemas JSON se generan desde los modelos Pydantic para que nunca se desincronicen:

```bash
python -c "import json; from agent.schemas.contrato import TriageRequest, TriageResponse; \
print(json.dumps(TriageRequest.model_json_schema(), indent=2, ensure_ascii=False))" > docs/contracts/triage_request.schema.json
python -c "import json; from agent.schemas.contrato import TriageRequest, TriageResponse; \
print(json.dumps(TriageResponse.model_json_schema(), indent=2, ensure_ascii=False))" > docs/contracts/triage_response.schema.json
```
