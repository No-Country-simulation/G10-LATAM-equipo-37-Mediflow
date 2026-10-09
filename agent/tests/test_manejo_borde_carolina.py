"""Regresiones de los dos fallos informados por Diana, sin duplicar su suite."""
import pytest
from fastapi.testclient import TestClient

from agent.nodes.clasificar import _normalizar_respuesta, clasificar
from agent.nodes.documentos_multiples import detectar_documentos_multiples
from agent.nodes.enrutar import enrutar
from agent.nodes.validar import validar
from api.main import app


@pytest.mark.parametrize("tipo", ["TEXTO", "JSON"])
@pytest.mark.parametrize("texto", ["", "   ", "\t\n", None])
def test_entrada_vacia_422_sin_ejecutar_grafo(monkeypatch, tipo, texto):
    import api.main as modulo
    def no_ejecutar(*args, **kwargs):
        pytest.fail("Una entrada vacía no debe ejecutar el agente")
    monkeypatch.setattr(modulo, "run_triage", no_ejecutar)
    r = TestClient(app).post("/triage", json={"documento_id": "CB", "tipo_archivo": tipo,
                                               "documento_texto": texto})
    assert r.status_code == 422


@pytest.mark.parametrize("texto,esperado", [
    ("RECETA MÉDICA\nPaciente: Ana\nCERTIFICADO MÉDICO\nPaciente: Ana", True),
    ("RECETA MÉDICA\nPaciente: Ana\nRECETA MÉDICA\nPaciente: Luis", True),
    ("RECETA MÉDICA\nPaciente: Ana\nRECETA MÉDICA\nPaciente: Ana", False),
    ("RECETA MÉDICA\nSe adjunta certificado médico para el trabajo.", False),
    ("INFORME DE LABORATORIO\nSe solicita receta médica.", False),
])
def test_encabezados_independientes(texto, esperado):
    assert detectar_documentos_multiples(texto) is esperado


def test_fallback_produce_amb5_y_revision():
    s = {"texto": "RECETA MÉDICA\nPaciente: Ana\nCERTIFICADO MÉDICO\nPaciente: Ana",
         "datos_extraidos": {}, "legibilidad": 1.0, "score": 0.99, "trace": []}
    s.update(clasificar(s))
    s.update(validar(s))
    assert s["validacion"]["categoria_amb"] == "AMB-5"
    assert enrutar(s)["decision"]["destino_principal"] == "Cola_Revision_Humana"


@pytest.mark.parametrize("valor,esperado", [
    (True, True), (False, False), ("false", False), ("true", False), (None, False)])
def test_senal_llm_es_booleano_estricto(valor, esperado):
    assert _normalizar_respuesta({"multiples_documentos": valor})["multiples_documentos"] is esperado
