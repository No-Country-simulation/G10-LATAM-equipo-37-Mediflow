"""validar lee la ambigüedad que informa `extraer` en el estado (AMB-4 y AMB-5).

Son las dos categorías que no salen de los datos extraídos: texto cortado y dos documentos
en un archivo solo se aprecian leyendo el documento, así que las informa el modelo.
"""
import pytest

from agent.nodes.validar import categoria_ambiguedad_del_modelo, validar


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("AMB-4", "AMB-4"),
        ("amb-5", "AMB-5"),
        ("AMB-5: dos documentos en un mismo archivo", "AMB-5"),
        ("AMB_4", "AMB-4"),
        ("AMB-1", None),  # las decide validar con reglas
        ("AMB-3", None),
        ("AMB-6", None),  # la decide la clasificación
        ("texto confuso", None),
        ("", None),
        (None, None),
        (5, None),
    ],
)
def test_categoria_ambiguedad_del_modelo(valor, esperado):
    assert categoria_ambiguedad_del_modelo(valor) == esperado


def _estado(ambiguedad=None, tipo_documento="Receta Medica"):
    estado = {
        "datos_extraidos": {},
        "clasificacion": {"tipo_documento": tipo_documento},
        "legibilidad": 1.0,
    }
    if ambiguedad is not None:
        estado["ambiguedad"] = ambiguedad
    return estado


def test_sin_ambiguedad_en_el_estado_no_cambia_nada():
    sin = validar(_estado())["validacion"].get("categoria_amb")
    con_vacio = validar(_estado(""))["validacion"].get("categoria_amb")
    assert sin == con_vacio


def test_amb5_del_modelo_se_asigna():
    assert validar(_estado("AMB-5"))["validacion"]["categoria_amb"] == "AMB-5"


def test_amb4_del_modelo_se_asigna_si_no_hay_nada_mas_especifico():
    base = validar(_estado())["validacion"].get("categoria_amb")
    resultado = validar(_estado("AMB-4"))["validacion"]["categoria_amb"]
    # Si los datos ya dan una categoría más específica (p. ej. AMB-1 por campos faltantes), gana esa.
    assert resultado == (base or "AMB-4")


def test_documento_fuera_de_alcance_sigue_siendo_amb6():
    assert validar(_estado("AMB-5", tipo_documento="Otro"))["validacion"]["categoria_amb"] == "AMB-6"


def test_categoria_que_no_es_del_modelo_se_ignora():
    sin = validar(_estado())["validacion"].get("categoria_amb")
    assert validar(_estado("AMB-3"))["validacion"].get("categoria_amb") == sin
