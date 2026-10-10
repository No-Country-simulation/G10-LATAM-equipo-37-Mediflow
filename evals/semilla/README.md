# Datos semilla (N1-10, issue #53)

Tres solicitudes con el contrato de entrada de `POST /triage` (ver `docs/api-contract.md`
y `docs/examples/triage_request.json`). Guion de ejecución en [`docs/demo.md`](../../docs/demo.md).

| Archivo | Escenario | Resultado esperado |
|---|---|---|
| `rutina.json` | Rutina (certificado médico) | `Historia_Clinica_Electronica`, sin auditoría |
| `urgencia.json` | Urgencia (TEP agudo) | `Cola_Emergencia_Medica`, alerta generada |
| `ambiguedad.json` | Ambigüedad (dosis dudosa) | `Cola_Revision_Humana`, auditoría humana |
