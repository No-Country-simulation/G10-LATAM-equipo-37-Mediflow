# Demo: tres escenarios reproducibles (N1-10, issue #53)

## Contexto y objetivo
Correr en Codespaces los tres escenarios del brief (rutina, urgencia, ambigüedad) con datos
semilla de `evals/semilla/`, usando la misma API `POST /triage` que la demo final.

## Prerrequisitos
- Codespace (o máquina) con Python 3.12.
- Clave de API del proveedor de modelos en `.env` (`GEMINI_API_KEY`). Sin clave, el agente usa
  clasificación por reglas (fallback): la urgencia se detecta igual, pero rutina y ambigüedad
  no producen el resultado esperado de la tabla (ver "Sin clave de modelo").

## Instalación
```bash
cp .env.example .env            # completar GEMINI_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Pruebas
```bash
make test                       # ruff + pytest -q
```

## Ejecución de los escenarios
Terminal 1:
```bash
set -a; source .env; set +a
uvicorn api.main:app --port 8000
```
Terminal 2:
```bash
for e in rutina urgencia ambiguedad; do
  echo "== $e"
  curl -s -X POST http://localhost:8000/triage -H "Content-Type: application/json" \
    -d @evals/semilla/$e.json | python -m json.tool
done
```
Para ver solo lo esencial, reemplazar `python -m json.tool` por
`python -c "import sys,json; r=json.load(sys.stdin); print(r['decision_enrutamiento']['destino_principal'], r['decision_enrutamiento']['requiere_auditoria_humana'], r['almacenamiento_oci']['ruta_objeto'])"`.

## Resultado esperado
| Escenario | Archivo | Destino | Auditoría humana | Objeto |
|---|---|---|---|---|
| Rutina | `rutina.json` | `Historia_Clinica_Electronica` | No | `procesados/historia_clinica/` |
| Urgencia | `urgencia.json` | `Cola_Emergencia_Medica` + alerta | No | `procesados/urgentes/` |
| Ambigüedad | `ambiguedad.json` | `Cola_Revision_Humana` | Sí | `auditoria_humana/` |

### Sin clave de modelo
Observado con el fallback por reglas: urgencia coincide con lo esperado; rutina y ambigüedad
no (rutina cae en `Cola_Revision_Humana` por falta de extracción; ambigüedad en
`Farmacia_Hospitalaria` con auditoría). Usar la clave para validar los tres.

## Evidencia de ejecución (plantilla)
- Fecha:
- Ejecutó:
- Commit:
- `make test`: 

| Escenario | Destino obtenido | Auditoría | Objeto | ¿Coincide? |
|---|---|---|---|---|
| Rutina | | | | |
| Urgencia | | | | |
| Ambigüedad | | | | |
