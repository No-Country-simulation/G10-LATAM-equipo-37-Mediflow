"""Pruebas de la ingesta y de la legibilidad, sin documentos clínicos reales y sin llamar al modelo.
Las que dependen de PyMuPDF o Pillow se saltan solas si la librería no está instalada, así el CI
sigue en verde mientras se agregan las dependencias.
"""
import base64
import io
import json

import pytest
from agent.ingestion import IngestionError, ingest_document
from agent.nodes.normalizar import normalizar


# --------------------------------------------------------------------------- texto y JSON
def test_ingesta_texto_utf8():
    doc = ingest_document(b"Paciente: ejemplo", filename="informe.txt", content_type="text/plain")
    assert doc.tipo_archivo == "TEXTO"
    assert doc.texto == "Paciente: ejemplo"
    assert doc.legibilidad == 1.0
    assert doc.imagenes == []


def test_ingesta_json_toma_documento_texto():
    crudo = json.dumps({"documento_id": "GS-01", "documento_texto": "Receta: amoxicilina 500 mg"}).encode()
    doc = ingest_document(crudo, filename="GS-01.json", content_type="application/json")
    assert doc.tipo_archivo == "JSON"
    assert doc.texto == "Receta: amoxicilina 500 mg"


def test_rechaza_json_sin_documento_texto():
    with pytest.raises(IngestionError, match="documento_texto"):
        ingest_document(json.dumps({"otra_cosa": 1}).encode(), filename="x.json", content_type="application/json")


def test_rechaza_extension_que_no_coincide_con_firma():
    with pytest.raises(IngestionError, match="extensión"):
        ingest_document(b"%PDF-1.7\n", filename="documento.png", content_type="application/pdf")


def test_rechaza_archivo_vacio():
    with pytest.raises(IngestionError, match="vacío"):
        ingest_document(b"", filename="documento.txt", content_type="text/plain")


def test_texto_vacio_pide_revision():
    doc = ingest_document(b"   ", filename="documento.txt", content_type="text/plain")
    assert doc.requiere_revision is True
    assert doc.legibilidad == 0.0


# --------------------------------------------------------------------------- imagen
def _png_de_prueba(color=(255, 255, 255), tamanio=(60, 40)) -> bytes:
    Image = pytest.importorskip("PIL.Image", reason="Pillow no instalado")
    buffer = io.BytesIO()
    Image.new("RGB", tamanio, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_imagen_conserva_la_pagina_y_deja_la_legibilidad_al_grafo():
    doc = ingest_document(_png_de_prueba(), filename="receta.png", content_type="image/png")
    assert doc.tipo_archivo == "IMAGEN"
    assert doc.legibilidad is None, "la legibilidad de una imagen la calcula normalizar (N2-08)"
    assert len(doc.imagenes) == 1, "el modelo multimodal tiene que ver la página"
    assert base64.b64decode(doc.imagenes[0]).startswith(b"\x89PNG")


# --------------------------------------------------------------------------- PDF
def test_pdf_con_capa_de_texto_no_renderiza_paginas():
    fitz_mod = pytest.importorskip("fitz", reason="PyMuPDF no instalado")
    documento = fitz_mod.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), "Informe de laboratorio: potasio 6,8 mEq/L")
    data = documento.tobytes()
    documento.close()

    doc = ingest_document(data, filename="lab.pdf", content_type="application/pdf")
    assert "potasio" in doc.texto
    assert doc.legibilidad == 1.0
    assert doc.imagenes == []


def test_pdf_escaneado_renderiza_y_deja_la_legibilidad_al_grafo():
    fitz_mod = pytest.importorskip("fitz", reason="PyMuPDF no instalado")
    pytest.importorskip("PIL.Image", reason="Pillow no instalado")
    documento = fitz_mod.open()
    documento.new_page()  # página en blanco: sin capa de texto, como un escaneo
    data = documento.tobytes()
    documento.close()

    doc = ingest_document(data, filename="escaneo.pdf", content_type="application/pdf")
    assert doc.legibilidad is None
    assert len(doc.imagenes) == 1


# --------------------------------------------------------------------------- legibilidad del grafo
def test_normalizar_respeta_la_legibilidad_que_ya_viene():
    salida = normalizar({"texto": "hola", "tipo_archivo": "TEXTO", "legibilidad": 1.0, "trace": []})
    assert salida["legibilidad"] == 1.0
    assert salida["trace"][-1]["detalle"]["legibilidad_provisional"] is False


def test_normalizar_marca_ilegible_la_imagen_sin_texto():
    salida = normalizar({"texto": "", "tipo_archivo": "IMAGEN", "imagenes": ["x"], "trace": []})
    assert salida["legibilidad"] < 0.40, "debajo de legibilidad_minima: va a revisión humana"
    assert salida["trace"][-1]["detalle"]["legibilidad_provisional"] is True


def test_normalizar_da_mejor_legibilidad_cuando_hay_texto_suficiente():
    salida = normalizar({"texto": "a" * 250, "tipo_archivo": "IMAGEN", "imagenes": ["x"], "trace": []})
    assert salida["legibilidad"] >= 0.70
