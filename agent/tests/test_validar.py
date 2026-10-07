"""
agent/tests/test_validar.py

Cubre las 6 categorías reales de docs/api-contract.md sección 6 (no las 5 que
habíamos supuesto antes de leer el contrato). Usa fixtures en memoria para
rules.yaml y los catálogos, así no depende de rutas de archivo durante el test
(mismo patrón que B-05: "test sin credenciales").
"""
import csv
from pathlib import Path

import pytest

from agent.nodes.validar import (
    _buscar_medicamento,
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
        {"codigo": "J03.9", "descripcion": "Amigdalitis aguda, no especificada"},
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
def test_dosis_en_gramos_se_convierte(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "amoxicilina", "dosis": "1 g"}]}
    assert validar_dosis_medicamentos(datos, medicamentos_catalogo) == []


def test_dosis_con_separador_de_miles(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "amoxicilina", "dosis": "1.000 mg"}]}
    assert validar_dosis_medicamentos(datos, medicamentos_catalogo) == []


def test_medicamento_sin_tildes(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "acido folico", "dosis": "1 mg"}]}
    assert validar_dosis_medicamentos(datos, medicamentos_catalogo) == []


def test_medicamento_parcial_no_coincide(medicamentos_catalogo):
    datos = {"medicamentos": [{"nombre": "ácido", "dosis": "1 mg"}]}
    assert "no identificable" in validar_dosis_medicamentos(datos, medicamentos_catalogo)[0]


def test_medicamento_no_dict_no_tumba_el_nodo(medicamentos_catalogo):
    datos = {"medicamentos": ["amoxicilina 500"]}
    assert len(validar_dosis_medicamentos(datos, medicamentos_catalogo)) == 1


def test_edad_con_texto():
    assert validar_contradiccion_interna({"paciente": {"edad": "45 años"}}) == []


PLAN_GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden" / "plan_golden.csv"


def _estado_gs06() -> dict:
    """Salida esperada del extractor para GS-06 (plan_golden.csv, fila GS-06).
    TODO: reemplazar por el archivo real cuando llegue a develop."""
    return {
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "datos_extraidos": {
            "paciente": {"nombre": "Paciente de Prueba", "edad": 8},
            "medico_solicitante": {"nombre": "Dr. Prueba", "matricula": "12345"},
            "medicamentos": [{"nombre": "Amoxicilina", "dosis": "5000 mg cada 8 horas"}],
            "cie10_sugerido": "J03.9",
        },
        "legibilidad": 0.90,
        "trace": [],
    }


def test_gs06_sale_con_amb3():
    v = validar(_estado_gs06())["validacion"]
    assert v["categoria_amb"] == "AMB-3"
    assert v["campos_faltantes"] == []
    assert any("fuera de rango" in c for c in v["conflictos"])


def test_gs06_coincide_con_plan_golden():
    """Si alguien cambia la etiqueta de GS-06 en el plan, este test avisa."""
    with open(PLAN_GOLDEN, encoding="utf-8") as f:
        fila = next(r for r in csv.DictReader(f) if "GS-06" in r.values())
    assert "AMB-3" in fila.values()


def test_validar_amb5_dos_documentos_en_un_archivo():
    state = _estado_gs06()
    state["datos_extraidos"]["medicamentos"] = [{"nombre": "amoxicilina", "dosis": "500 mg"}]
    state["datos_extraidos"]["_multiples_documentos"] = True
    assert validar(state)["validacion"]["categoria_amb"] == "AMB-5"


def test_validar_amb6_fuera_de_alcance_con_motivo():
    state = {
        "clasificacion": {"tipo_documento": "Otro", "motivo_fuera_de_alcance": "no clínico"},
        "datos_extraidos": {},
        "legibilidad": 0.90,
        "trace": [],
    }
    v = validar(state)["validacion"]
    assert v["categoria_amb"] == "AMB-6"
    assert v["motivo_fuera_de_alcance"] == "no clínico"


def test_validar_amb6_sin_motivo_no_inventa_uno():
    state = {
        "clasificacion": {"tipo_documento": "Otro"},
        "datos_extraidos": {},
        "legibilidad": 0.90,
        "trace": [],
    }
    v = validar(state)["validacion"]
    assert v["categoria_amb"] == "AMB-6"
    assert "motivo_fuera_de_alcance" not in v



def test_cie10_inexistente_da_amb2():
    """Un código CIE-10 que no existe en la lista OPS/OMS va a revisión como AMB-2."""
    state = _estado_gs06()
    state["datos_extraidos"]["medicamentos"] = [{"nombre": "amoxicilina", "dosis": "500 mg"}]
    state["datos_extraidos"]["cie10_sugerido"] = "K35.2"
    v = validar(state)["validacion"]
    assert v["categoria_amb"] == "AMB-2"
    assert any("CIE-10" in c for c in v["conflictos"])


def test_cie10_valido_no_genera_categoria():
    state = _estado_gs06()
    state["datos_extraidos"]["medicamentos"] = [{"nombre": "amoxicilina", "dosis": "500 mg"}]
    v = validar(state)["validacion"]
    assert "categoria_amb" not in v


def test_asignar_categoria_cie10_solo():
    categoria = asignar_categoria_amb(
        campos_faltantes=[],
        conflictos_dosis=[],
        conflictos_contradiccion=[],
        es_ilegible_medio=False,
        es_multiples_documentos=False,
        clasificacion={"tipo_documento": "Receta Medica"},
        conflictos_cie10=["Código CIE-10 no encontrado en la lista OPS/OMS: K35.2"],
    )
    assert categoria == "AMB-2"


# --- Búsqueda de medicamentos: la coincidencia más larga gana ---------------

_CATALOGO_REAL = Path(__file__).resolve().parents[2] / "evals" / "generator" / "data" / "medicamentos.csv"


def _cargar_catalogo_real():
    with open(_CATALOGO_REAL, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_prefiere_la_coincidencia_mas_larga():
    cat = _cargar_catalogo_real()
    assert _buscar_medicamento("amoxicilina-clavulánico 875 mg", cat)["id"] == "MED-04"


def test_amoxicilina_sola_sigue_siendo_med_03():
    cat = _cargar_catalogo_real()
    assert _buscar_medicamento("amoxicilina 500 mg", cat)["id"] == "MED-03"


def test_dosis_en_el_limite_del_rango_es_valida():
    """Bordes inclusivos del catálogo verificado. GS-24: 875 mg es el máximo
    de amoxicilina-clavulánico (MED-04) y 1 g = 1000 mg es el mínimo de ceftriaxona (MED-06)."""
    cat = _cargar_catalogo_real()
    datos = {"medicamentos": [
        {"nombre": "amoxicilina-clavulánico", "dosis": "875 mg"},
        {"nombre": "ceftriaxona", "dosis": "1 g"},
    ]}
    assert validar_dosis_medicamentos(datos, cat) == []


def test_dosis_apenas_fuera_del_limite_es_conflicto():
    """Un miligramo por encima del máximo de MED-04 (875 mg) debe marcarse."""
    cat = _cargar_catalogo_real()
    datos = {"medicamentos": [{"nombre": "amoxicilina-clavulánico", "dosis": "876 mg"}]}
    conflictos = validar_dosis_medicamentos(datos, cat)
    assert len(conflictos) == 1
    assert "fuera de rango" in conflictos[0]


def test_edad_contradice_fecha_de_nacimiento_gs17():
    from agent.nodes.validar import validar_contradiccion_interna

    datos = {"paciente": {"edad": 38, "fecha_nacimiento": "1961-03-15"}, "fecha": "2026-09-23"}
    assert any("fecha de nacimiento" in c for c in validar_contradiccion_interna(datos))


def test_edad_coherente_con_fecha_de_nacimiento_no_genera_conflicto():
    from agent.nodes.validar import validar_contradiccion_interna

    datos = {"paciente": {"edad": 65, "fecha_nacimiento": "1961-03-15"}, "fecha": "2026-09-23"}
    assert validar_contradiccion_interna(datos) == []


def test_sin_fecha_de_nacimiento_no_se_compara():
    from agent.nodes.validar import validar_contradiccion_interna

    datos = {"paciente": {"edad": 38}, "fecha": "2026-09-23"}
    assert validar_contradiccion_interna(datos) == []


def test_fuera_de_alcance_con_multiples_documentos_conserva_amb6_y_motivo():
    from agent.nodes.validar import validar

    for motivo in ("paciente_no_humano", "no_clinico"):
        state = {
            "datos_extraidos": {"_multiples_documentos": True},
            "clasificacion": {"tipo_documento": "Otro", "motivo_fuera_de_alcance": motivo},
            "trace": [],
        }
        validacion = validar(state)["validacion"]
        assert validacion["categoria_amb"] == "AMB-6"
        assert validacion["motivo_fuera_de_alcance"] == motivo


def test_multiples_documentos_en_tipo_clinico_sigue_siendo_amb5():
    from agent.nodes.validar import validar

    state = {
        "datos_extraidos": {"_multiples_documentos": True},
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "trace": [],
    }
    assert validar(state)["validacion"]["categoria_amb"] == "AMB-5"


def test_gs17_sin_fecha_del_documento_no_compara_edad():
    # Sin fecha documental válida no hay referencia confiable: no se inventa una
    # contradicción contra la fecha de hoy.
    from agent.nodes.validar import validar_contradiccion_interna

    datos = {"paciente": {"edad": 38, "fecha_nacimiento": "1961-03-15"}}
    assert validar_contradiccion_interna(datos) == []


def test_gs17_fecha_del_documento_ilegible_no_compara_edad():
    # Formato DD/MM/AAAA no se interpreta: se omite la regla en vez de usar hoy.
    from agent.nodes.validar import validar_contradiccion_interna

    datos = {
        "paciente": {"edad": 59, "fecha_nacimiento": "1961-03-15"},
        "fecha": "23/09/2020",
    }
    assert validar_contradiccion_interna(datos) == []


_CATALOGO_PERIODICIDAD = [
    {
        "nombre": "metotrexato", "sinonimos": "mtx", "validar_dosis": "si", "unidad": "mg",
        "dosis_min_toma": "7,5", "dosis_max_toma": "30", "periodicidad_especial": "semanal",
    },
    {
        "nombre": "amoxicilina", "sinonimos": "", "validar_dosis": "si", "unidad": "mg",
        "dosis_min_toma": "250", "dosis_max_toma": "1000", "periodicidad_especial": "",
    },
]


def test_metotrexato_diario_genera_conflicto_por_periodicidad_semanal():
    from agent.nodes.validar import validar_dosis_medicamentos

    for frecuencia in ("diario", "cada 24 horas", "1 vez al día"):
        datos = {"medicamentos": [{"nombre": "Metotrexato", "dosis": "15 mg", "frecuencia": frecuencia}]}
        conflictos = validar_dosis_medicamentos(datos, _CATALOGO_PERIODICIDAD)
        assert any("Frecuencia incompatible" in c for c in conflictos), frecuencia


def test_metotrexato_semanal_no_genera_conflicto():
    from agent.nodes.validar import validar_dosis_medicamentos

    for frecuencia in ("semanal", "1 vez por semana", "cada 7 días"):
        datos = {"medicamentos": [{"nombre": "Metotrexato", "dosis": "15 mg", "frecuencia": frecuencia}]}
        assert validar_dosis_medicamentos(datos, _CATALOGO_PERIODICIDAD) == [], frecuencia


def test_medicamento_sin_periodicidad_especial_puede_ser_diario():
    from agent.nodes.validar import validar_dosis_medicamentos

    datos = {"medicamentos": [{"nombre": "Amoxicilina", "dosis": "500 mg", "frecuencia": "diario"}]}
    assert validar_dosis_medicamentos(datos, _CATALOGO_PERIODICIDAD) == []

def test_informe_de_laboratorio_no_valida_farmacos_del_texto():
    from agent.nodes.validar import validar_dosis_medicamentos

    datos = {"medicamentos": [{"nombre": "hierro oral", "dosis": None, "frecuencia": None}]}
    assert validar_dosis_medicamentos(datos, _CATALOGO_PERIODICIDAD, "Informe de Laboratorio") == []


def test_receta_sigue_marcando_medicamento_desconocido():
    from agent.nodes.validar import validar_dosis_medicamentos

    datos = {"medicamentos": [{"nombre": "hierro oral", "dosis": None, "frecuencia": None}]}
    assert validar_dosis_medicamentos(datos, _CATALOGO_PERIODICIDAD, "Receta Medica") != []