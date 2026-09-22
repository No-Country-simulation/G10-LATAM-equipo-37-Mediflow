"""Harness de evaluación: corre el golden set por el grafo y calcula las métricas."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from agent.graph import run_triage


def evaluar(golden: Path) -> dict:
    total = Counter()
    latencias = []
    for linea in golden.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        caso = json.loads(linea)
        t0 = time.time()
        r = run_triage(caso["documento_id"], caso["tipo_archivo"], caso.get("documento_texto"), "evals")
        latencias.append(time.time() - t0)
        esperado = caso["esperado"]
        total["n"] += 1
        total["tipo_ok"] += r["clasificacion"]["tipo_documento"] == esperado.get("tipo_documento")
        if "destino_principal" in esperado:
            total["destino_ok"] += r["decision"]["destino_principal"] == esperado["destino_principal"]
        if esperado.get("nivel_prioridad") == "Urgente":
            total["urgencias"] += 1
            total["urgencias_detectadas"] += r["urgencia"]["detectada"]
        total["revision_humana"] += r["decision"]["destino_principal"] == "Cola_Revision_Humana"
    n = max(1, total["n"])
    latencias.sort()
    return {
        "n": total["n"],
        "accuracy_clasificacion": round(total["tipo_ok"] / n, 3),
        "accuracy_destino": round(total["destino_ok"] / n, 3),
        "recall_urgencias": round(total["urgencias_detectadas"] / max(1, total["urgencias"]), 3),
        "tasa_revision_humana": round(total["revision_humana"] / n, 3),
        "latencia_p50_s": round(latencias[len(latencias) // 2], 2) if latencias else None,
        "latencia_p95_s": round(latencias[int(len(latencias) * 0.95)], 2) if latencias else None,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--golden", default="evals/golden/golden_v0.jsonl")
    p.add_argument("--report", default="evals/output/report.md")
    args = p.parse_args()
    golden = Path(args.golden)
    if not golden.exists():
        print(f"No existe {golden}. Genera el golden set primero.")
        return
    m = evaluar(golden)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    filas = "\n".join(f"| {k} | {v} |" for k, v in m.items())
    Path(args.report).write_text(f"# Evaluación\n\n| Métrica | Valor |\n|---|---|\n{filas}\n", encoding="utf-8")
    print(json.dumps(m, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
