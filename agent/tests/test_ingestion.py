"""Pruebas de validación de entrada sin usar documentos clínicos reales."""
import pytest

from agent.ingestion import IngestionError, ingest_document


def test_ingesta_texto_utf8():
    result = ingest_document(b"Paciente: ejemplo", filename="informe.txt", content_type="text/plain")
    assert result.tipo_archivo == "TEXTO"
    assert result.texto == "Paciente: ejemplo"
    assert result.legibilidad == 1.0


def test_rechaza_extension_que_no_coincide_con_firma():
    with pytest.raises(IngestionError, match="extensión"):
        ingest_document(b"%PDF-1.7\n", filename="documento.png", content_type="application/pdf")


def test_rechaza_archivo_vacio():
    with pytest.raises(IngestionError, match="vacío"):
        ingest_document(b"", filename="documento.txt", content_type="text/plain")
