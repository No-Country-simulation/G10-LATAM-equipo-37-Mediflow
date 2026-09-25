"""Harness de evaluación de MediFlow.

Corre el conjunto de prueba contra el agente y compara lo que salió con la etiqueta esperada de
`evals/golden/plan_golden.csv`. Produce `evals/output/report.md` y `evals/output/resultados.json`.

    python evals/run.py                      # todo lo que tenga archivo escrito
    python evals/run.py --limite 5           # una corrida corta
    python evals/run.py --solo GS-06 FA-05   # casos puntuales
    python evals/run.py --simulado           # sin llamar al modelo, para probar el harness

Un elemento sin archivo escrito no cuenta como error: aparece en la lista de pendientes. Así el
harness sirve desde el primer documento y no hay que esperar a tener los 45.

Las métricas que publica el README salen de aquí. La que manda es el recall de urgencias: un falso
positivo cuesta minutos de un profesional, un falso negativo puede costar un paciente.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"
DIR_DOCS = RAIZ / "evals" / "golden" / "files"
DIR_MANUSCRITAS = RAIZ / "evals" / "handwritten"
SALIDA = RAIZ / "evals" / "output"

EXTENSIONES = {"TEXTO": ".txt", "JSON": ".json", "PDF": ".pdf", "IMAGEN": ".png"}


# --------------------------------------------------------------------------- el plan
@dataclass
class Caso:
    id: str
    tipo_documento: str
    resultado: str
    categoria_amb: str
    motivo_fuera_de_alcance: str
    destino: str
    auditoria: bool
    prioridad: str
    nivel_legibilidad: str
    revisiones: int
    # (ruta, tipo de archivo, clase). La clase es "base" para texto, JSON y PDF nativo, e "imagen"
    # para las variantes degradadas y las recetas manuscritas.
    variantes: list[tuple[Path, str, str]] = field(default_factory=list)

    @property
    def es_urgencia(self) -> bool:
        return self.resultado in ("urgencia", "urgencia_ambiguedad")

    @property
    def es_fuera_de_alcance(self) -> bool:
        return self.categoria_amb == "AMB-6"


def expectativa(caso: Caso, clase: str) -> dict:
    """Qué se espera de cada variante.

    La etiqueta de la fila describe el documento legible. Una imagen degradada del mismo documento
    no espera lo mismo: los umbrales de `rules.yaml` mandan por encima del contenido.

      leve    se comporta como el documento legible
      media   se extrae lo posible y va a revisión humana con AMB-4, salvo que sea urgencia, que
              va a Emergencia y además queda marcada para auditoría
      severa  por debajo de 0,40 no se clasifica: revisión humana, solicitar nueva captura
    """
    esperado = {"tipo": caso.tipo_documento, "destino": caso.destino, "auditoria": caso.auditoria,
                "urgencia": caso.es_urgencia, "categoria_amb": caso.categoria_amb,
                "motivo_fuera_de_alcance": caso.motivo_fuera_de_alcance,
                "comparar_tipo": True}
    if clase != "imagen" or caso.nivel_legibilidad in ("", "leve"):
        return esperado
    if caso.nivel_legibilidad == "media":
        esperado["auditoria"] = True
        if not caso.es_urgencia:
            esperado["destino"] = "Cola_Revision_Humana"
            esperado["categoria_amb"] = "AMB-4"
        return esperado
    # severa: el grafo va de normalizar a enrutar sin clasificar, así que el tipo no se compara
    esperado.update({"destino": "Cola_Revision_Humana", "auditoria": True, "urgencia": False,
                     "categoria_amb": "", "motivo_fuera_de_alcance": "", "comparar_tipo": False})
    return esperado


def _variantes_de(fila: dict) -> list[tuple[Path, str, str]]:
    """Todas las versiones existentes del elemento. Cada una se evalúa por separado, porque una
    imagen degradada no espera el mismo resultado que el documento legible."""
    cid = fila["id"]
    if cid.startswith("M"):  # recetas manuscritas: solo la foto
        for ext in (".jpg", ".jpeg", ".png"):
            p = DIR_MANUSCRITAS / f"{cid}{ext}"
            if p.exists():
                return [(p, "IMAGEN", "imagen")]
        return []

    candidatos = [(DIR_DOCS / f"{cid}.txt", "TEXTO", "base")]
    if fila["formato_json"] == "si":
        candidatos.append((DIR_DOCS / f"{cid}.json", "JSON", "base"))
    if fila["formato_pdf"] == "si":
        candidatos.append((DIR_DOCS / f"{cid}.pdf", "PDF", "base"))
    if fila["variante_imagen"] == "foto":
        candidatos.append((DIR_DOCS / f"{cid}_foto.png", "IMAGEN", "imagen"))
    if fila["variante_imagen"] == "pdf_escaneado":
        candidatos.append((DIR_DOCS / f"{cid}_escaneado.png", "IMAGEN", "imagen"))
    return [(ruta, tipo, clase) for ruta, tipo, clase in candidatos if ruta.exists()]


def cargar_plan() -> list[Caso]:
    casos = []
    with open(PLAN, encoding="utf-8-sig") as fh:
        for fila in csv.DictReader(fh):
            casos.append(Caso(
                id=fila["id"],
                tipo_documento=fila["tipo_documento"],
                resultado=fila["resultado_esperado"],
                categoria_amb=fila["categoria_ambiguedad"],
                motivo_fuera_de_alcance=fila.get("motivo_fuera_de_alcance", ""),
                destino=fila["destino_esperado"],
                auditoria=fila["requiere_auditoria"] == "si",
                prioridad=fila["nivel_prioridad"],
                nivel_legibilidad=fila["nivel_legibilidad"],
                revisiones=sum(1 for c in ("revision_1", "revision_2") if fila.get(c, "").strip()),
                variantes=_variantes_de(fila),
            ))
    return casos


# --------------------------------------------------------------------------- ejecución
def ejecutar(caso: Caso, ruta: Path, tipo: str, clase: str, simulado: bool) -> tuple[dict, float]:
    """Devuelve el estado final del grafo y el tiempo en segundos."""
    if simulado:
        # Devuelve lo que se espera de esta variante: prueba el harness, nunca mide nada.
        e = expectativa(caso, clase)
        return {
            "clasificacion": {"tipo_documento": e["tipo"], "nivel_prioridad": caso.prioridad},
            "urgencia": {"detectada": e["urgencia"]},
            "validacion": {"categoria_amb": e["categoria_amb"],
                           "motivo_fuera_de_alcance": e["motivo_fuera_de_alcance"]},
            "decision": {"destino_principal": e["destino"], "requiere_auditoria_humana": e["auditoria"]},
            "score": 0.9,
        }, 0.0

    from agent.graph import run_triage  # se importa aquí para que --simulado no necesite langgraph

    inicio = time.perf_counter()
    if tipo in ("PDF", "IMAGEN"):
        from agent.ingestion import ingest_document

        doc = ingest_document(ruta.read_bytes(), filename=ruta.name)
        estado = run_triage(caso.id, doc.tipo_archivo, doc.texto, "evaluacion",
                            imagenes=doc.imagenes, legibilidad=doc.legibilidad)
    else:
        estado = run_triage(caso.id, tipo, ruta.read_text(encoding="utf-8"), "evaluacion")
    return estado, time.perf_counter() - inicio


# --------------------------------------------------------------------------- comparación
@dataclass
class Resultado:
    caso: Caso
    clase: str
    archivo: str
    segundos: float
    obtenido: dict
    aciertos: dict[str, bool] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and all(self.aciertos.values())

    @property
    def etiqueta(self) -> str:
        if self.clase != "imagen":
            return self.caso.id
        return f"{self.caso.id} ({self.caso.nivel_legibilidad or 'imagen'})"


def comparar(caso: Caso, clase: str, archivo: str, estado: dict, segundos: float) -> Resultado:
    clasificacion = estado.get("clasificacion") or {}
    decision = estado.get("decision") or {}
    validacion = estado.get("validacion") or {}
    urgencia = estado.get("urgencia") or {}
    obtenido = {
        "tipo_documento": clasificacion.get("tipo_documento", ""),
        "destino_principal": decision.get("destino_principal", ""),
        "requiere_auditoria_humana": bool(decision.get("requiere_auditoria_humana")),
        "urgencia_detectada": bool(urgencia.get("detectada")),
        "categoria_amb": validacion.get("categoria_amb", "") or "",
        "motivo_fuera_de_alcance": validacion.get("motivo_fuera_de_alcance", "") or "",
        "score": estado.get("score"),
    }
    e = expectativa(caso, clase)
    aciertos = {
        "destino": obtenido["destino_principal"] == e["destino"],
        "auditoria": obtenido["requiere_auditoria_humana"] == e["auditoria"],
        "urgencia": obtenido["urgencia_detectada"] == e["urgencia"],
    }
    if e["comparar_tipo"]:
        aciertos["tipo"] = obtenido["tipo_documento"] == e["tipo"]
    if e["categoria_amb"]:
        aciertos["categoria_amb"] = obtenido["categoria_amb"] == e["categoria_amb"]
    if e["motivo_fuera_de_alcance"]:
        aciertos["motivo_fuera_de_alcance"] = obtenido["motivo_fuera_de_alcance"] == e["motivo_fuera_de_alcance"]
    return Resultado(caso=caso, clase=clase, archivo=archivo, segundos=segundos, obtenido=obtenido,
                     aciertos=aciertos)


# --------------------------------------------------------------------------- métricas
def _porcentaje(parte: int, total: int) -> str:
    return f"{parte / total:.0%} ({parte}/{total})" if total else "sin datos"


def metricas(resultados: list[Resultado]) -> dict:
    hechos = [r for r in resultados if not r.error]
    legibles = [r for r in hechos if r.clase != "imagen" or r.caso.nivel_legibilidad in ("", "leve")]
    degradadas = [r for r in hechos if r.clase == "imagen" and r.caso.nivel_legibilidad in ("media", "severa")]
    urgencias = [r for r in legibles if r.caso.es_urgencia]
    fuera = [r for r in hechos if r.caso.es_fuera_de_alcance]
    tiempos = sorted(r.segundos for r in hechos) or [0.0]
    revision = [r for r in hechos if r.obtenido["destino_principal"] == "Cola_Revision_Humana"]
    return {
        "casos_evaluados": len(hechos),
        "casos_con_error": sum(1 for r in resultados if r.error),
        "accuracy_clasificacion": _porcentaje(sum(r.aciertos.get("tipo", True) for r in legibles), len(legibles)),
        "accuracy_destino": _porcentaje(sum(r.aciertos["destino"] for r in legibles), len(legibles)),
        "accuracy_auditoria": _porcentaje(sum(r.aciertos["auditoria"] for r in legibles), len(legibles)),
        "puerta_legibilidad": _porcentaje(sum(r.ok for r in degradadas), len(degradadas)),
        "recall_urgencias": _porcentaje(sum(r.obtenido["urgencia_detectada"] for r in urgencias), len(urgencias)),
        "falsas_urgencias": sum(1 for r in legibles if r.obtenido["urgencia_detectada"] and not r.caso.es_urgencia),
        "variantes_evaluadas": f"{len(legibles)} legibles y {len(degradadas)} degradadas",
        "fuera_de_alcance": _porcentaje(sum(r.ok for r in fuera), len(fuera)),
        "tasa_revision_humana": _porcentaje(len(revision), len(hechos)),
        "latencia_p50": f"{statistics.median(tiempos):.1f} s",
        "latencia_p95": f"{tiempos[int(len(tiempos) * 0.95) - 1]:.1f} s" if len(tiempos) > 1 else "sin datos",
        "casos_perfectos": _porcentaje(sum(r.ok for r in hechos), len(hechos)),
    }


def informe(resultados: list[Resultado], pendientes: list[Caso], sin_revisar: list[Caso], m: dict,
            simulado: bool) -> str:
    L = [f"# Evaluación de MediFlow · {datetime.now():%d/%m/%Y %H:%M}", ""]
    if simulado:
        L += ["> Corrida **simulada**: el harness no llamó al modelo. Los números no miden nada, solo "
              "comprueban que el harness funciona.", ""]
    L += ["| Métrica | Valor |", "|---|---|"]
    for clave, etiqueta in [
        ("accuracy_clasificacion", "Accuracy de clasificación"),
        ("accuracy_destino", "Accuracy de destino"),
        ("accuracy_auditoria", "Acierto de la marca de auditoría"),
        ("recall_urgencias", "**Recall de urgencias**"),
        ("fuera_de_alcance", "Casos fuera de alcance resueltos"),
        ("puerta_legibilidad", "Puerta de legibilidad (imágenes media y severa)"),
        ("tasa_revision_humana", "Tasa de revisión humana"),
        ("latencia_p50", "Latencia p50"),
        ("latencia_p95", "Latencia p95"),
        ("casos_perfectos", "Casos correctos en todo"),
    ]:
        L.append(f"| {etiqueta} | {m[clave]} |")
    L += ["", f"Variantes evaluadas: {m['variantes_evaluadas']}. Falsas urgencias: {m['falsas_urgencias']}. "
          f"Errores de ejecución: {m['casos_con_error']}.", "",
          "Las métricas de clasificación y destino se calculan sobre los documentos legibles. Las imágenes "
          "media y severa se miden aparte, en la puerta de legibilidad: de ellas no se espera el destino del "
          "documento original sino que el agente reconozca que no puede leerlas.", ""]

    fallos = [r for r in resultados if not r.ok]
    if fallos:
        L += ["## Fallos", "", "| Caso | Qué falló | Esperado | Obtenido |", "|---|---|---|---|"]
        for r in fallos:
            if r.error:
                L.append(f"| {r.etiqueta} | error de ejecución | | {r.error[:70]} |")
                continue
            for campo, ok in r.aciertos.items():
                if not ok:
                    esperado = expectativa(r.caso, r.clase)[campo]
                    obtenido = {"tipo": r.obtenido["tipo_documento"], "destino": r.obtenido["destino_principal"],
                                "auditoria": r.obtenido["requiere_auditoria_humana"],
                                "urgencia": r.obtenido["urgencia_detectada"],
                                "categoria_amb": r.obtenido["categoria_amb"],
                                "motivo_fuera_de_alcance": r.obtenido["motivo_fuera_de_alcance"]}[campo]
                    L.append(f"| {r.etiqueta} | {campo} | {esperado} | {obtenido} |")
        L.append("")

    # las fallas por categoría son lo que se ataca en el paquete N1-13
    por_categoria: dict[str, list[str]] = {}
    for r in fallos:
        if r.clase == "imagen" and r.caso.nivel_legibilidad in ("media", "severa"):
            clave = f"legibilidad {r.caso.nivel_legibilidad}"
        else:
            clave = r.caso.categoria_amb or ("urgencia" if r.caso.es_urgencia else r.caso.tipo_documento)
        por_categoria.setdefault(clave, []).append(r.etiqueta)
    if por_categoria:
        L += ["## Fallos por categoría", "", "| Categoría | Casos |", "|---|---|"]
        L += [f"| {k} | {', '.join(v)} |" for k, v in sorted(por_categoria.items())] + [""]

    if pendientes:
        L += [f"## Pendientes de escribir ({len(pendientes)})", "",
              "No cuentan como error: todavía no tienen archivo.", "",
              ", ".join(c.id for c in pendientes), ""]
    if sin_revisar:
        L += [f"## Escritos pero sin doble revisión ({len(sin_revisar)})", "",
              "Un elemento no cuenta para las métricas oficiales hasta tener dos revisiones.", "",
              ", ".join(c.id for c in sin_revisar), ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- principal
def main() -> int:
    p = argparse.ArgumentParser(description="Corre el conjunto de prueba contra el agente.")
    p.add_argument("--solo", nargs="+", metavar="ID", help="evalúa solo estos casos")
    p.add_argument("--limite", type=int, help="evalúa como mucho N casos")
    p.add_argument("--simulado", action="store_true", help="no llama al modelo: prueba el harness")
    args = p.parse_args()

    if not args.simulado and os.getenv("USE_LLM", "").lower() not in ("1", "true", "si"):
        print("Aviso: USE_LLM no está activo. Para medir de verdad, USE_LLM=true python evals/run.py")

    casos = cargar_plan()
    if args.solo:
        pedidos = {c.upper() for c in args.solo}
        casos = [c for c in casos if c.id.upper() in pedidos]
    pendientes = [c for c in casos if not c.variantes]
    listos = [c for c in casos if c.variantes]
    sin_revisar = [c for c in listos if c.revisiones < 2]
    if args.limite:
        listos = listos[:args.limite]

    tareas = [(caso, ruta, tipo, clase) for caso in listos for ruta, tipo, clase in caso.variantes]
    print(f"{len(listos)} elementos con archivo ({len(tareas)} variantes), {len(pendientes)} pendientes")
    resultados = []
    for i, (caso, ruta, tipo, clase) in enumerate(tareas, 1):
        print(f"  [{i}/{len(tareas)}] {ruta.name}", end=" ", flush=True)
        try:
            estado, segundos = ejecutar(caso, ruta, tipo, clase, args.simulado)
            r = comparar(caso, clase, ruta.name, estado, segundos)
        except Exception as exc:  # noqa: BLE001 - una variante rota no detiene la corrida
            r = Resultado(caso=caso, clase=clase, archivo=ruta.name, segundos=0.0, obtenido={},
                          error=f"{type(exc).__name__}: {exc}")
        resultados.append(r)
        print("ok" if r.ok else ("ERROR" if r.error else "falla"))

    m = metricas(resultados)
    SALIDA.mkdir(parents=True, exist_ok=True)
    texto = informe(resultados, pendientes, sin_revisar, m, args.simulado)
    (SALIDA / "report.md").write_text(texto, encoding="utf-8")
    json.dump(
        {"fecha": datetime.now().isoformat(timespec="seconds"), "simulado": args.simulado, "metricas": m,
         "variantes": [{"id": r.caso.id, "archivo": r.archivo, "clase": r.clase, "ok": r.ok,
                        "error": r.error, "aciertos": r.aciertos, "obtenido": r.obtenido,
                        "segundos": round(r.segundos, 3)} for r in resultados]},
        open(SALIDA / "resultados.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("\n" + "\n".join(texto.splitlines()[:16]))
    print(f"\nInforme completo en {SALIDA / 'report.md'}")
    return 0 if all(r.ok for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
