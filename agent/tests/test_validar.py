"""
agent/tests/test_validar.py

Cubre las 6 categorías reales de docs/api-contract.md sección 6 (no las 5 que
habíamos supuesto antes de leer el contrato). Usa fixtures en memoria para
rules.yaml y los catálogos, así no depende de rutas de archivo durante el test
(mismo patrón que B-05: "test sin credenciales").
"""

import pytest

from agent.nodes.validar import (
    asignar_categoria_amb,
    evaluar_legibilidad,
    validar,
    validar_campos_obligatorios,
    validar_cie10,
    validar_contradiccion_interna,
    validar_dosis_medicamentos,
)


# ---------------------------------------------------------------------------
# Fixtures: versión mínima de rules.yaml y los catálogos reales
# ---------------------------------------------------------------------------

@pytest.fixture
def rules() -> dict:
    return {
        "umbrales": {"automatico": 0.85, "segunda_opinion": 0.60, "legibilidad_minima": 0.40},
        "legibilidad": {"leve": 0.70, "media": 0.40},
        "campos_obligatorios": {
            "Receta Medica": [
                "paciente.nombre",
                "medico_solicitante.nombre",
                "medico_solicitante.matricula",
                "medicamentos",
            ],
            "Informe de Laboratorio": ["paciente.nombre", "estudio_realizado"],
            "Otro": [],
        },
    }


@pytest.fixture
def medicamentos_catalogo() -> list[dict]:
    # Tomado tal cual de evals/generator/data/medicamentos.csv
    return [
        {
            "nombre": "amoxicilina",
            "sinonimos": "amoxicilina trihidrato",
            "validar_dosis": "si",
            "dosis_min_toma": "250",
            "dosis_max_toma": "1000",
            "unidad": "mg",
        },
        {
            "nombre": "morfina",
            "sinonimos": "",
            "validar_dosis": "no",  # se dosifica por protocolo (ADR-007)
            "dosis_min_toma": "",
            "dosis_max_toma": "",
            "unidad": "mg",
        },
        {
            "nombre": "ácido fólico",
            "sinonimos": "folato; vitamina B9",
            "validar_dosis": "si",
            "dosis_min_toma": "0,4",  # coma decimal real del CSV
            "dosis_max_toma": "15",
            "unidad": "mg",
        },
    ]


@pytest.fixture
def cie10_catalogo() -> list[dict]:
    # Tomado de evals/generator/data/cie10.csv
    return [
        {"codigo": "I26.9", "descripcion": "Embolia pulmonar sin mención de corazón pulmonar agudo"},
        {"codigo": "A41.9", "descripcion": "Septicemia, no especificada"},
    ]


@pytest.fixture(autouse=True)
def _parchar_catalogos(monkeypatch, rules, medicamentos_catalogo, cie10_catalogo):
    monkeypatch.setattr("agent.nodes.validar._cargar_rules", lambda path=None: rules)
    monkeypatch.setattr(
        "agent.nodes.validar._cargar_medicamentos", lambda path=None: medicamentos_catalogo
    )
    monkeypatch.setattr("agent.nodes.validar._cargar_cie10", lambda path=None: cie10_catalogo)


# ---------------------------------------------------------------------------
# Funciones individuales
# ---------------------------------------------------------------------------

def test_campos_obligatorios_receta_sin_paciente(rules):
    datos = {
        "medico_solicitante": {"nombre": "Dr. Pérez", "matricula": "12345"},
        "medicamentos": [{"nombre": "amoxicilina", "dosis": "500 mg"}],
    }
    faltantes = validar_campos_obligatorios(datos, "Receta Medica", rules)
    assert "paciente.nombre" in faltantes


def test_dosis_dentro_de_rango(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "amoxicilina", "dosis": "500 mg"}]}
    assert validar_dosis_medicamentos(datos, medicamentos_catalogo) == []


def test_dosis_fuera_de_rango(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "amoxicilina", "dosis": "5000 mg"}]}
    conflictos = validar_dosis_medicamentos(datos, medicamentos_catalogo)
    assert len(conflictos) == 1
    assert "fuera de rango" in conflictos[0]


def test_dosis_con_coma_decimal(medicamentos_catalogo):
    """ADR-006/ADR-007: el CSV real usa coma decimal ('0,4')."""
    datos = {"medicamentos": [{"nombre": "ácido fólico", "dosis": "1 mg"}]}
    assert validar_dosis_medicamentos(datos, medicamentos_catalogo) == []


def test_medicamento_por_protocolo_no_genera_amb3(medicamentos_catalogo):
    """ADR-007: morfina (validar_dosis = no) nunca genera conflicto de dosis,
    aunque la dosis parezca alta."""
    datos = {"medicamentos": [{"nombre": "morfina", "dosis": "500 mg"}]}
    assert validar_dosis_medicamentos(datos, medicamentos_catalogo) == []


def test_medicamento_no_identificable(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "medicamento inventado xyz", "dosis": "10 mg"}]}
    conflictos = validar_dosis_medicamentos(datos, medicamentos_catalogo)
    assert len(conflictos) == 1
    assert "no identificable" in conflictos[0]


def test_cie10_codigo_valido(cie10_catalogo):
    assert validar_cie10({"cie10_sugerido": "I26.9"}, cie10_catalogo) == []


def test_cie10_codigo_inexistente(cie10_catalogo):
    """ADR-008: K35.2 no existe en la lista OPS/OMS (K35.0 es el correcto)."""
    conflictos = validar_cie10({"cie10_sugerido": "K35.2"}, cie10_catalogo)
    assert len(conflictos) == 1


def test_contradiccion_edad_implausible():
    conflictos = validar_contradiccion_interna({"paciente": {"edad": 200}})
    assert len(conflictos) == 1


def test_legibilidad_banda_media_da_amb4(rules):
    assert evaluar_legibilidad(0.55, rules) is True


def test_legibilidad_leve_no_da_amb4(rules):
    assert evaluar_legibilidad(0.85, rules) is False


# ---------------------------------------------------------------------------
# Una prueba por cada una de las 6 categorías AMB reales
# ---------------------------------------------------------------------------

def test_amb_1_campo_obligatorio_faltante():
    categoria = asignar_categoria_amb(
        campos_faltantes=["paciente.nombre"],
        conflictos_dosis=[],
        conflictos_contradiccion=[],
        es_ilegible_medio=False,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Receta Medica"},
    )
    assert categoria == "AMB-1"


def test_amb_2_contradiccion_interna():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=[],
        conflictos_contradiccion=["Edad fuera de rango plausible: 200"],
        es_ilegible_medio=False,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Epicrisis"},
    )
    assert categoria == "AMB-2"


def test_amb_3_dosis_fuera_de_rango_o_no_identificable():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=["Dosis fuera de rango para amoxicilina: 5000 mg"],
        conflictos_contradiccion=[],
        es_ilegible_medio=False,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Receta Medica"},
    )
    assert categoria == "AMB-3"


def test_amb_4_texto_parcialmente_ilegible():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=[],
        conflictos_contradiccion=[],
        es_ilegible_medio=True,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Informe de Laboratorio"},
    )
    assert categoria == "AMB-4"


def test_amb_5_dos_documentos_en_un_archivo():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=[],
        conflictos_contradiccion=[],
        es_ilegible_medio=False,
        es_multiples_documentos=True,
        clasificacion={"tipo_documento": "Receta Medica"},
    )
    assert categoria == "AMB-5"


def test_amb_6_fuera_de_alcance():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=[],
        conflictos_contradiccion=[],
        es_ilegible_medio=False,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Otro"},
    )
    assert categoria == "AMB-6"


def test_documento_sin_ambiguedad_no_asigna_categoria():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=[],
        conflictos_contradiccion=[],
        es_ilegible_medio=False,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Receta Medica"},
    )
    assert categoria is None


# ---------------------------------------------------------------------------
# Prueba de integración del nodo completo (validar())
# ---------------------------------------------------------------------------

def test_validar_receta_completa_y_valida():
    state = {
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "datos_extraidos": {
            "paciente": {"nombre": "Ana Gómez", "edad": 45},
            "medico_solicitante": {"nombre": "Dr. Pérez", "matricula": "12345"},
            "medicamentos": [{"nombre": "amoxicilina", "dosis": "500 mg"}],
        },
        "legibilidad": 0.90,
        "trace": [],
    }
    resultado = validar(state)
    v = resultado["validacion"]
    assert v["campos_faltantes"] == []
    assert v["conflictos"] == []
    assert "categoria_amb" not in v
    assert resultado["trace"][-1]["nodo"] == "validar"


def test_validar_receta_sin_paciente_da_amb1():
    state = {
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "datos_extraidos": {
            "medico_solicitante": {"nombre": "Dr. Pérez", "matricula": "12345"},
            "medicamentos": [{"nombre": "amoxicilina", "dosis": "500 mg"}],
        },
        "legibilidad": 0.90,
        "trace": [],
    }
    resultado = validar(state)
    assert resultado["validacion"]["categoria_amb"] == "AMB-1"
    assert "paciente.nombre" in resultado["validacion"]["campos_faltantes"]
