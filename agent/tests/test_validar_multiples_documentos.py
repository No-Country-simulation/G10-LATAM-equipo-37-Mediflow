"""AMB-5 (dos documentos en un archivo): señal del modelo y respaldo en modo reglas."""
import pytest

from agent.nodes.validar import validar


def _estado(**extra):
    estado = {
        "datos_extraidos": {},
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "trace": [],
    }
    estado.update(extra)
    return estado


def _categoria(estado):
    return validar(estado)["validacion"]["categoria_amb"]


def test_el_modelo_informa_amb5():
    assert _categoria(_estado(ambiguedad="AMB-5")) == "AMB-5"


def test_respaldo_heuristica_si_el_modelo_no_informo():
    estado = _estado()
    estado["clasificacion"]["multiples_documentos"] = True
    assert _categoria(estado) == "AMB-5"


@pytest.mark.parametrize("valor", [False, None, "true", 1, "si"])
def test_respaldo_solo_con_true_estricto(valor):
    estado = _estado()
    estado["clasificacion"]["multiples_documentos"] = valor
    assert _categoria(estado) != "AMB-5"


def test_la_marca_vieja_en_datos_extraidos_ya_no_cuenta():
    estado = _estado()
    estado["datos_extraidos"]["_multiples_documentos"] = True
    assert _categoria(estado) != "AMB-5"


def test_el_respaldo_no_se_usa_si_el_modelo_informo_amb4():
    estado = _estado(ambiguedad="AMB-4")
    estado["clasificacion"]["multiples_documentos"] = True
    assert _categoria(estado) != "AMB-5"


def test_fuera_de_alcance_sigue_antes_que_amb5_con_el_respaldo():
    estado = _estado()
    estado["clasificacion"] = {
        "tipo_documento": "Otro",
        "motivo_fuera_de_alcance": "no_clinico",
        "multiples_documentos": True,
    }
    assert _categoria(estado) == "AMB-6"
