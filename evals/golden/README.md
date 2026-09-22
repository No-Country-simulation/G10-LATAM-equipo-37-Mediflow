# Golden set

Un archivo JSONL por versión (`golden_v0.jsonl`). Cada línea:

```json
{
  "documento_id": "SYN-0001",
  "tipo_archivo": "TEXTO",
  "idioma": "es",
  "fuente": "generador",
  "documento_texto": "...",
  "archivo": "evals/golden/files/SYN-0001.pdf",
  "esperado": {
    "tipo_documento": "Receta Medica",
    "nivel_prioridad": "Rutina",
    "destino_principal": "Farmacia_Hospitalaria",
    "requiere_auditoria_humana": false,
    "datos_extraidos": {"paciente": {"nome": "...", "edad": 44}, "medicamentos": []}
  },
  "revisado_por": ["persona1", "persona2"]
}
```

Sin doble revisión no entra al golden set.
