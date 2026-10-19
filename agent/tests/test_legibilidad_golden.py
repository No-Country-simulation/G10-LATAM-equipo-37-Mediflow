"""Pruebas de la puerta de legibilidad con imágenes reales del golden set.

Complementan a `test_legibilidad.py` (sintéticas, deterministas): usan las fotos y
escaneos de `evals/golden/files` y `evals/handwritten`, que es lo que habría
detectado la brecha entre óptico y real. Requieren Tesseract instalado; en el CI se
instala vía apt, en local sin binario se saltan.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from agent.nodes.normalizar import normalizar

RAIZ = Path(__file__).resolve().parents[2]
PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"
DIR_DOCS = RAIZ / "evals" / "golden" / "files"
DIR_MANUSCRITAS = RAIZ / "evals" / "handwritten"

# (id, archivo, banda esperada): los casos que detectaron la brecha.
CASOS = [
    ("GS-01", DIR_DOCS / "GS-01_foto.png", "leve"),
    ("GS-20", DIR_DOCS / "GS-20_escaneado.png", "leve"),
    ("GS-28", DIR_DOCS / "GS-28_foto.png", "media"),
    ("M7", DIR_MANUSCRITAS / "M7.jpg", "severa"),
]


def _banda(score: float) -> str:
    if score >= 0.70:
        return "leve"
    if score >= 0.40:
        return "media"
    return "severa"


def _binario_tesseract() -> bool:
    try:
        import shutil

        import pytesseract

        pytesseract.get_tesseract_version()
        return shutil.which("tesseract") is not None
    except Exception:  # noqa: BLE001 - sin binario se salta
        return False


def _etiquetas_plan() -> dict[str, str]:
    """Banda esperada por id según la columna nivel_legibilidad del plan."""
    etiquetas: dict[str, str] = {}
    with open(PLAN, encoding="utf-8-sig") as fh:
        for fila in csv.DictReader(fh):
            if fila["variante_imagen"] in ("foto", "pdf_escaneado", "foto_manuscrita") and fila[
                "nivel_legibilidad"
            ]:
                etiquetas[fila["id"]] = fila["nivel_legibilidad"]
    return etiquetas


def _imagenes_existentes() -> list[tuple[str, Path, str]]:
    etiquetas = _etiquetas_plan()
    candidatos = []
    for ruta in sorted(DIR_DOCS.glob("*_foto.png")) + sorted(DIR_DOCS.glob("*_escaneado.png")):
        cid = ruta.name.rsplit("_", 1)[0]
        if cid in etiquetas:
            candidatos.append((cid, ruta, etiquetas[cid]))
    for ruta in sorted(DIR_MANUSCRITAS.glob("M*.jpg")):
        cid = ruta.stem
        if cid in etiquetas:
            candidatos.append((cid, ruta, etiquetas[cid]))
    return candidatos


def _score_archivo(ruta: Path) -> tuple[float, dict]:
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [_b64_archivo(ruta)],
        "trace": [],
    })
    return out["legibilidad"], out["trace"][-1]["detalle"]


def _b64_archivo(ruta: Path) -> str:
    import base64

    return base64.b64encode(ruta.read_bytes()).decode("ascii")


_tesseract = pytest.mark.skipif(not _binario_tesseract(), reason="Tesseract no instalado")


@_tesseract
@pytest.mark.parametrize("cid,ruta,banda", _imagenes_existentes(), ids=[c[0] for c in _imagenes_existentes()])
def test_imagen_golden_cae_en_su_banda(cid, ruta, banda):
    """Cada imagen real del golden set cae en la banda de su etiqueta."""
    score, _ = _score_archivo(ruta)
    assert _banda(score) == banda, f"{cid}: score {score}, esperado {banda}"


@_tesseract
@pytest.mark.parametrize(
    "cid,ruta,banda",
    [c for c in CASOS if c[1].exists()],
    ids=[c[0] for c in CASOS if c[1].exists()],
)
@pytest.mark.xfail(strict=True, reason="Calibración con OCR pendiente (fase 4)")
def test_casos_que_detectaron_la_brecha(cid, ruta, banda):
    """GS-01, GS-20, GS-28 y M7: los que evidenciaron que el óptico no alcanzaba."""
    score, detalle = _score_archivo(ruta)
    assert _banda(score) == banda, f"{cid}: score {score} (ocr={detalle['confianza_ocr']})"
