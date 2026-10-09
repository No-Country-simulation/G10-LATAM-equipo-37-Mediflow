# Demo: tres escenarios reproducibles (N1-10, issue #53)

## Contexto y objetivo
Ejecutar tres escenarios semilla (rutina, urgencia, ambigüedad) de forma reproducible
en Codespaces. Datos en `evals/semilla/`.

> Estado actual: al momento de escribir esto el repositorio solo contiene el README;
> no hay aplicación, dependencias, pruebas ni esquema de entrada. Los seeds usan un
> esquema provisional (ver `evals/semilla/README.md`). Cuando exista el código
> (dependencias N1-03, N1-05, N1-06), reemplazar los comandos marcados como *(pendiente)*
> y alinear los campos de los JSON.

## Prerrequisitos
- Codespace del repositorio con Python 3.10+.

## Instalación
```bash
git clone https://github.com/No-Country-simulation/G10-LATAM-equipo-37-Mediflow
cd G10-LATAM-equipo-37-Mediflow
# (pendiente) pip install -r requirements.txt
```

## Pruebas
```bash
# (pendiente) pytest -q
# Verificación vigente: los seeds son JSON válidos y completos
for f in rutina urgencia ambiguedad; do
  python -c "import json,sys; d=json.load(open('evals/semilla/$f.json')); assert d['id']=='$f' and 'resultado_esperado' in d; print('OK', d['id'])"
done
```

## Ejecución de escenarios
```bash
# Hoy: mostrar el escenario y su resultado esperado
python -m json.tool evals/semilla/rutina.json
python -m json.tool evals/semilla/urgencia.json
python -m json.tool evals/semilla/ambiguedad.json
# (pendiente) ejecutar con el flujo real, p. ej.: <comando> --input evals/semilla/<escenario>.json
```

## Resultado esperado
| Escenario | Resultado esperado |
|---|---|
| Rutina | Prioridad rutina; sin aclaración |
| Urgencia | Prioridad urgencia; sin aclaración |
| Ambigüedad | Prioridad indeterminada; solicita aclaración |

## Evidencia de ejecución (plantilla)
- Fecha: 
- Ejecutó: 
- Commit: 

| Escenario | Comando | Resultado obtenido | ¿Coincide? |
|---|---|---|---|
| Rutina | | | |
| Urgencia | | | |
| Ambigüedad | | | |
