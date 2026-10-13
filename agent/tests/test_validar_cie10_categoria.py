"""El CIE-10 se valida por categoría de 3 caracteres (ADR-013).

El catálogo sigue la CIE-10 de la OMS: `R91` e `I10` no tienen subcódigos. Si el modelo devuelve la
forma de la CIE-10-CM (`R91.1`), para el triaje cuenta la categoría.
"""
import pytest

from agent.nodes.validar import validar, validar_cie10

CATALOGO = [
    {"codigo": "I26.9", "descripcion": "Embolia pulmonar"},
    {"codigo": "K35.0", "descripcion": "Apendicitis aguda con peritonitis generalizada"},
    {"codigo": "R91", "descripcion": "Hallazgos anormales en imagen del pulmón"},
    {"codigo": "I10", "descripcion": "Hipertensión esencial"},
    {"codigo": "Z34.9", "descripcion": "Supervisión de embarazo normal"},
]


@pytest.mark.parametrize(
    "codigo",
    ["R91", "R91.1", "R91.8", "r91.1", " R91.1 ", "I10", "I26.9", "I26", "Z34.9"],
)
def test_codigo_con_categoria_en_el_catalogo_es_valido(codigo):
    assert validar_cie10({"cie10_sugerido": codigo}, CATALOGO) == []


@pytest.mark.parametrize("codigo", ["Z99", "X00.1", "texto libre", "R9", "R911", "R91.1.2", "91"])
def test_codigo_sin_categoria_en_el_catalogo_se_marca(codigo):
    conflictos = validar_cie10({"cie10_sugerido": codigo}, CATALOGO)
    assert len(conflictos) == 1 and "no encontrado" in conflictos[0]


@pytest.mark.parametrize("datos", [{}, {"cie10_sugerido": None}, {"cie10_sugerido": ""}])
def test_sin_codigo_no_hay_conflicto(datos):
    assert validar_cie10(datos, CATALOGO) == []


def test_limitacion_subcodigo_inventado_en_categoria_real_pasa():
    """Límite conocido: I26.7 no está en el catálogo pero su categoría I26 sí, así que pasa."""
    assert validar_cie10({"cie10_sugerido": "I26.7"}, CATALOGO) == []


def test_limitacion_k35_2_pasa_por_la_categoria_k35():
    """ADR-008 lo trataba como inexistente; con ADR-013 pasa por la categoría K35."""
    assert validar_cie10({"cie10_sugerido": "K35.2"}, CATALOGO) == []


def test_validar_conserva_el_codigo_tal_como_lo_devolvio_el_modelo(monkeypatch):
    monkeypatch.setattr("agent.nodes.validar._cargar_cie10", lambda path=None: CATALOGO)
    datos = {"cie10_sugerido": "R91.1"}
    estado = {
        "datos_extraidos": datos,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
        "legibilidad": 1.0,
    }
    salida = validar(estado)
    assert datos["cie10_sugerido"] == "R91.1"
    assert "datos_extraidos" not in salida
    assert not any("CIE-10" in c for c in salida["validacion"]["conflictos"])


def test_codigo_inexistente_en_validar_da_conflicto_cie10(monkeypatch):
    monkeypatch.setattr("agent.nodes.validar._cargar_cie10", lambda path=None: CATALOGO)
    estado = {
        "datos_extraidos": {"cie10_sugerido": "Z99"},
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
        "legibilidad": 1.0,
    }
    conflictos = validar(estado)["validacion"]["conflictos"]
    assert any("CIE-10" in c and "Z99" in c for c in conflictos)
