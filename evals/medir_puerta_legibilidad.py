"""Mide la puerta de legibilidad (óptico + OCR) sobre el golden set.

Por cada imagen imprime: nivel esperado, score óptico, confianza OCR, palabras
OCR, score combinado, si acierta la puerta 0.40 y si acierta la banda exacta.
Requiere Tesseract instalado; sin binario solo mide el óptico.

    python evals/medir_puerta_legibilidad.py
"""
import csv
import glob
import os
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"

from agent.nodes.normalizar import (  # noqa: E402
    _confianza_ocr,
    _score_de_imagen,
)


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


def _puerta_ok(nivel: str, score: float) -> bool:
    """Acierto de la puerta de producto: leve/media >= 0.40, severa < 0.40."""
    if nivel in ("leve", "media"):
        return score >= 0.40
    if nivel == "severa":
        return score < 0.40
    return False


def _ocr_de_imagen(img: Image.Image):
    """(confianza, palabras) de Tesseract o (None, 0) si no hay OCR."""
    ocr = _confianza_ocr(img)
    if ocr is None:
        return None, 0
    return ocr


def main() -> int:
    niveles = _niveles()
    total = aciertos_banda = aciertos_puerta = 0

    print(
        f"{'archivo':22} {'nivel':7} {'optico':7} {'conf_ocr':8} {'pal_ocr':7} "
        f"{'combinado':9} {'puerta0.40':9} {'banda':6}"
    )
    for patron, clave in (
        ("evals/golden/files/*.png", "_"),
        ("evals/handwritten/*.jpg", "."),
    ):
        for ruta in sorted(glob.glob(str(RAIZ / patron))):
            nombre = os.path.basename(ruta)
            cid = nombre.split(clave)[0]
            nivel = niveles.get(cid, "?")
            img = Image.open(ruta)

            optico = _score_de_imagen(img)
            conf, pal = _ocr_de_imagen(img)

            # Score combinado replicando la lógica de _score_de_pagina:
            # si hay >= 20 palabras se combina con peso 0.8, si no, solo óptico.
            from agent.nodes.normalizar import _PALABRAS_MIN_OCR, _PESO_OCR  # noqa: E402

            if pal >= _PALABRAS_MIN_OCR and conf is not None:
                combinado = round(_PESO_OCR * conf + (1.0 - _PESO_OCR) * optico, 4)
            else:
                combinado = optico

            bien_banda = _ok(nivel, combinado)
            bien_puerta = _puerta_ok(nivel, combinado)
            total += 1
            aciertos_banda += bien_banda
            aciertos_puerta += bien_puerta

            conf_s = f"{conf:.2f}" if conf is not None else "   -"
            print(
                f"{nombre:22} {nivel:7} {optico:7.2f} {conf_s:>8} {pal:7d} "
                f"{combinado:9.2f}  {'OK' if bien_puerta else 'NO':9}  "
                f"{'OK' if bien_banda else 'NO':6}"
            )

    print(f"\nBanda exacta: {aciertos_banda}/{total} en banda")
    print(f"Puerta 0.40:  {aciertos_puerta}/{total} correctas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
