"""Pruebas de la puerta de legibilidad (>= 0.40) sobre el golden set.

Separa la decisión de producto (bloquear severas < 0.40, dejar pasar leves y
medias >= 0.40) de la calibración de banda exacta (0.70 / 0.40), que vive en
`test_legibilidad_golden.py`. Los casos pendientes de fase 4 se dejan como
xfail (no strict): si pasan, bien; si fallan, se reportan sin romper el CI.
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from agent.nodes.normalizar import normalizar

RAIZ = Path(__file__).resolve().parents[2]
PLAN = RAIZ / "evals" / "golden" / "plan_golden.csv"
DIR_DOCS = RAIZ / "evals" / "golden" / "files"
DIR_MANUSCRITAS = RAIZ / "evals" / "handwritten"

# Casos que la puerta 0.40 no resuelve todavía (fase 4).
XFAIL_PUERTA = {"GS-02", "GS-28", "M4", "M5", "M6", "M7"}


def _banda(score: float) -> str:
    if score >= 0.70:
        return "leve"
    if score >= 0.40:
        return "media"
    return "severa"


def _binario_tesseract() -> bool:
    try:
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


def _score_archivo(ruta: Path) -> float:
    import base64

    data = base64.b64encode(ruta.read_bytes()).decode("ascii")
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [data],
        "trace": [],
    })
    return out["legibilidad"]


_tesseract = pytest.mark.skipif(not _binario_tesseract(), reason="Tesseract no instalado")


def _params_puerta() -> list:
    """Params del test de puerta: los casos pendientes de fase 4 van como xfail (no strict).

    Casos que la puerta 0.40 no resuelve todavía: GS-02, GS-28, M4–M7.
    """
    params: list = []
    for cid, ruta, banda_esperada in _imagenes_existentes():
        if cid in XFAIL_PUERTA:
            params.append(
                pytest.param(
                    cid,
                    ruta,
                    banda_esperada,
                    marks=pytest.mark.xfail(
                        strict=False,
                        reason=f"Puerta 0.40 pendiente de calibración (fase 4): {cid}",
                    ),
                )
            )
        else:
            params.append(pytest.param(cid, ruta, banda_esperada))
    return params


@_tesseract
@pytest.mark.parametrize(
    "cid,ruta,banda_esperada",
    _params_puerta(),
    ids=[c[0] for c in _imagenes_existentes()],
)
def test_puerta_040_bloquea_solo_severas(cid, ruta, banda_esperada):
    """Puerta de producto: leve/media pasan (>= 0.40), severa se bloquea (< 0.40)."""
    score = _score_archivo(ruta)

    pasa_puerta = score >= 0.40
    espera_pasar = banda_esperada in ("leve", "media")
    assert pasa_puerta == espera_pasar, (
        f"{cid}: score {score} ({_banda(score)}), "
        f"esperaba {'pasar' if espera_pasar else 'bloquear'} para banda {banda_esperada}"
    )
