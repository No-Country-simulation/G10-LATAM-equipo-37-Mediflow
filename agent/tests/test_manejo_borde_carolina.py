"""Heurística de respaldo AMB-5; validación e integración pertenecen a #120."""
import pytest

from agent.nodes.clasificar import _clasificar_por_reglas, _normalizar_respuesta
from agent.nodes.documentos_multiples import detectar_documentos_multiples


@pytest.mark.parametrize("texto,esperado", [
    ("RECETA MÉDICA\nPaciente: Ana\nCERTIFICADO MÉDICO\nPaciente: Ana", True),
    ("RECETA MÉDICA\nPaciente: Ana\nRECETA MÉDICA\nPaciente: Luis", True),
    ("RECETA MÉDICA\nPaciente: Ana\nRECETA MÉDICA\nPaciente: Ana", False),
    ("RECETA MÉDICA\nSe adjunta certificado médico para el trabajo.", False),
    ("INFORME DE LABORATORIO\nSe solicita receta médica.", False),
])
def test_encabezados_independientes(texto, esperado):
    assert detectar_documentos_multiples(texto) is esperado



def test_fallback_marca_documentos_multiples():
    texto = "RECETA MÉDICA\nPaciente: Ana\nCERTIFICADO MÉDICO\nPaciente: Ana"
    assert _clasificar_por_reglas(texto)["multiples_documentos"] is True


def test_clasificador_llm_no_produce_segunda_senal_amb5():
    assert "multiples_documentos" not in _normalizar_respuesta({"multiples_documentos": True})
