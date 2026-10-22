"""Mide el score optico (_score_de_imagen) sobre las imagenes del golden set.

Replica la medicion de revision de la puerta N2-08: por cada imagen imprime
archivo, nivel esperado (plan_golden.csv), score y si cae en su banda
(leve >= 0.70, media [0.40, 0.70), severa < 0.40). Solo Pillow, sin Tesseract:
no mide la combinacion con OCR (eso lo cubre test_legibilidad_golden.py en CI).

    python evals/medir_legibilidad.py
"""
import csv
import glob
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"


def _niveles() -> dict:
    niveles = {}
    with open(PLAN, encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            if fila["variante_imagen"]:
                niveles[fila["id"]] = fila["nivel_legibilidad"]
    return niveles


def _ok(nivel: str, score: float) -> bool:
    return (
        (nivel == "leve" and score >= 0.70)
        or (nivel == "media" and 0.40 <= score < 0.70)
        or (nivel == "severa" and score < 0.40)
    )


def main() -> int:
    from PIL import Image

    from agent.nodes.normalizar import _score_de_imagen

    niveles = _niveles()
    total = aciertos = 0
    for patron, clave in (
        ("evals/golden/files/*.png", "_"),
        ("evals/handwritten/*.jpg", "."),
    ):
        for ruta in sorted(glob.glob(str(RAIZ / patron))):
            nombre = os.path.basename(ruta)
            cid = nombre.split(clave)[0]
            nivel = niveles.get(cid, "?")
            score = _score_de_imagen(Image.open(ruta))
            bien = _ok(nivel, score)
            total += 1
            aciertos += bien
            print(f"{nombre:22} {nivel:7} {score:5.2f}  {'ok' if bien else 'NO'}")
    print(f"\n{aciertos}/{total} en banda")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
