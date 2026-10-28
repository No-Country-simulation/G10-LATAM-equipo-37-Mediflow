"""Casos borde de la ingesta y del grafo (N1-09).

Cada caso tiene su archivo en agent/tests/casos_borde/ y su resultado esperado en
agent/tests/casos_borde/casos_borde.csv. La regla común: la API responde 200 o 422 con un
mensaje controlado, nunca 500, y cada documento que entra al grafo termina en un destino definido.

Corren sin modelo (USE_LLM=false). Los PDF de 50 y 51 páginas se generan en el test para no
guardar archivos pesados en el repositorio.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.graph import run_triage
from api.main import app

CASOS = Path(__file__).parent / "casos_borde"
REVISION = "Cola_Revision_Humana"

# raise_server_exceptions=False: si algo revienta, el test ve un 500 en lugar de una excepción.
client = TestClient(app, raise_server_exceptions=False)

_MIME = {
    ".txt": "text/plain",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _subir(nombre: str, contenido: bytes, documento_id: str):
    tipo = _MIME.get(Path(nombre).suffix.lower(), "application/octet-stream")
    return client.post(
        "/triage/upload",
        data={"documento_id": documento_id, "canal_origen": "test"},
        files={"archivo": (nombre, contenido, tipo)},
    )


def _pdf_de(paginas: int) -> bytes:
    pymupdf = pytest.importorskip("pymupdf", reason="PyMuPDF no instalado")
    documento = pymupdf.open()
    for numero in range(1, paginas + 1):
        pagina = documento.new_page()
        pagina.insert_text((72, 72), f"Hospital General San Martin - Historia clinica, hoja {numero}")
    return documento.tobytes()


# --------------------------------------------------------------------------- entradas inválidas: 422
@pytest.mark.parametrize(
    ("caso", "archivo", "mensaje"),
    [
        ("CB-01", "vacio.txt", "vacío"),
        ("CB-03", "json_texto_vacio.json", "documento_texto"),
        ("CB-05", "pdf_disfrazado.png", "extensión"),
        ("CB-06", "nota_evolucion.docx", "no soportado"),
        ("CB-07", "latin1.txt", "UTF-8"),
        ("CB-08", "pdf_danado.pdf", "no se puede leer"),
        ("CB-09", "imagen_danada.jpg", "no se puede leer"),
    ],
)
def test_entrada_invalida_responde_422_controlado(caso, archivo, mensaje):
    respuesta = _subir(archivo, (CASOS / archivo).read_bytes(), caso)
    assert respuesta.status_code == 422, respuesta.text
    assert mensaje in respuesta.json()["detail"]


def test_cb04_triage_con_texto_solo_espacios_responde_422():
    # docs/api-contract.md: documento_texto vacío o solo espacios -> 422.
    cuerpo = {"documento_id": "CB-04", "tipo_archivo": "TEXTO", "canal_origen": "test", "documento_texto": "   "}
    respuesta = client.post("/triage", json=cuerpo)
    assert respuesta.status_code == 422, respuesta.text


def test_cb10_pdf_de_51_paginas_se_rechaza():
    respuesta = _subir("largo.pdf", _pdf_de(51), "CB-10")
    assert respuesta.status_code == 422, respuesta.text
    assert "50 páginas" in respuesta.json()["detail"]


# --------------------------------------------------------------------------- entradas que pasan
def test_cb02_texto_solo_espacios_va_a_revision_humana():
    respuesta = _subir("solo_espacios.txt", (CASOS / "solo_espacios.txt").read_bytes(), "CB-02")
    assert respuesta.status_code == 200, respuesta.text
    decision = respuesta.json()["decision_enrutamiento"]
    assert decision["destino_principal"] == REVISION
    assert decision["requiere_auditoria_humana"] is True


def test_cb11_pdf_de_50_paginas_se_acepta_y_tiene_destino():
    respuesta = _subir("limite.pdf", _pdf_de(50), "CB-11")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["decision_enrutamiento"]["destino_principal"]


# --------------------------------------------------------------------------- ambigüedad en el grafo
def test_cb12_dos_documentos_en_un_archivo_es_amb5():
    texto = (CASOS / "dos_documentos.txt").read_text(encoding="utf-8")
    resultado = run_triage("CB-12", "TEXTO", texto, "test")
    assert resultado["validacion"].get("categoria_amb") == "AMB-5"
    assert resultado["decision"]["destino_principal"] == REVISION
    assert resultado["decision"]["requiere_auditoria_humana"] is True


def test_cb13_json_sin_paciente_es_amb1():
    datos = json.loads((CASOS / "json_sin_paciente.json").read_text(encoding="utf-8"))
    resultado = run_triage(datos["documento_id"], "JSON", datos["documento_texto"], datos["canal_origen"])
    assert resultado["validacion"].get("categoria_amb") == "AMB-1"
    assert resultado["decision"]["destino_principal"] == REVISION
    assert resultado["decision"]["requiere_auditoria_humana"] is True


# --------------------------------------------------------------------------- ninguno tumba la API
@pytest.mark.parametrize(
    "archivo",
    sorted(p.name for p in CASOS.iterdir() if p.suffix.lower() in _MIME),
)
def test_ningun_archivo_tumba_la_api(archivo):
    respuesta = _subir(archivo, (CASOS / archivo).read_bytes(), f"CB-{archivo}")
    assert respuesta.status_code in (200, 422), f"{archivo}: {respuesta.status_code} {respuesta.text[:200]}"
