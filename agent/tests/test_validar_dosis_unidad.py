"""La dosis se lee de la cantidad que lleva su unidad, no del primer número del texto.

Caso real: GS-05 (metotrexato «3 comprimidos (15 mg)» una vez por semana). Leer el 3 daba
3 mg, fuera del rango 7,5 a 30 mg del catálogo, y la receta salía con AMB-3 de más.
"""
import pytest

from agent.nodes.validar import _dosis_en_unidad_catalogo, validar_dosis_medicamentos

METOTREXATO = {
    "nombre": "metotrexato",
    "sinonimos": "metotrexate; methotrexate; MTX",
    "validar_dosis": "si",
    "dosis_min_toma": "7,5",
    "dosis_max_toma": "30",
    "unidad": "mg",
    "periodicidad_especial": "semanal",
}


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("3 comprimidos (15 mg)", 15.0),
        ("15 mg", 15.0),
        ("2 comprimidos de 5 mg", 5.0),  # se conserva la regla: la primera cantidad con unidad
        ("1.000 mg", 1000.0),
        ("0,25 mg", 0.25),
        ("2 g", 2000.0),
        ("400 mcg", 0.4),
        ("500", 500.0),  # sin unidad: primer número, unidad del catálogo
        ("1 comprimido", 1.0),
    ],
)
def test_dosis_se_lee_de_la_cantidad_con_unidad(texto, esperado):
    assert _dosis_en_unidad_catalogo(texto, "mg") == pytest.approx(esperado)


def test_dosis_sin_numero_es_none():
    assert _dosis_en_unidad_catalogo("según indicación", "mg") is None
    assert _dosis_en_unidad_catalogo(None, "mg") is None


def test_catalogo_en_otra_unidad_solo_acepta_la_misma_unidad():
    assert _dosis_en_unidad_catalogo("400 mcg", "mcg") == pytest.approx(400.0)
    assert _dosis_en_unidad_catalogo("0,4 mg", "mcg") is None


def test_gs05_metotrexato_15_mg_semanal_no_es_ambiguo():
    datos = {
        "medicamentos": [
            {"nombre": "Metotrexato", "dosis": "3 comprimidos (15 mg)", "frecuencia": "una vez por semana"}
        ]
    }
    assert validar_dosis_medicamentos(datos, [METOTREXATO], "Receta Medica") == []


def test_dosis_realmente_baja_sigue_marcandose():
    datos = {"medicamentos": [{"nombre": "Metotrexato", "dosis": "2,5 mg", "frecuencia": "una vez por semana"}]}
    conflictos = validar_dosis_medicamentos(datos, [METOTREXATO], "Receta Medica")
    assert len(conflictos) == 1 and "fuera de rango" in conflictos[0]


def test_frecuencia_diaria_de_metotrexato_sigue_marcandose():
    medicamento = {"nombre": "Metotrexato", "dosis": "3 comprimidos (15 mg)", "frecuencia": "una vez al día"}
    datos = {"medicamentos": [medicamento]}
    conflictos = validar_dosis_medicamentos(datos, [METOTREXATO], "Receta Medica")
    assert any("Frecuencia incompatible" in c for c in conflictos)
