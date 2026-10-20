from evals.dev.evaluar_extraccion import comparar


def test_detecta_campo_omitido_y_dato_inventado():
    assert comparar({"diagnostico_egreso": "gastroenteritis"}, {}) == {"diagnostico_egreso": False}
    assert comparar({"medico_solicitante.nombre": None}, {
        "medico_solicitante": {"nombre": "Inventado"}
    }) == {"medico_solicitante.nombre": False}


def test_compara_anidados_y_toleras_formato_sin_perder_contenido():
    assert comparar({"paciente.nombre": "Lucía Prado"}, {
        "paciente": {"nombre": " LUCÍA PRADO. "}
    }) == {"paciente.nombre": True}


def test_nombre_medico_tolera_tratamiento_sin_aceptar_otro_nombre():
    for titulo in ("Dr.", "Dra.", "Doctor", "Doctora"):
        assert comparar({"medico_solicitante.nombre": "Ines Cabrera"}, {
            "medico_solicitante": {"nombre": f"{titulo} Ines Cabrera"}
        }) == {"medico_solicitante.nombre": True}
    assert comparar({"medico_solicitante.nombre": "Dra. Ines Cabrera"}, {
        "medico_solicitante": {"nombre": "Ines Cabrera"}
    }) == {"medico_solicitante.nombre": True}
    assert comparar({"medico_solicitante.nombre": "Ines Cabrera"}, {
        "medico_solicitante": {"nombre": "Dra. Ines Perez"}
    }) == {"medico_solicitante.nombre": False}


def test_tratamiento_no_se_elimina_en_campos_clinicos():
    assert comparar({"diagnostico_egreso": "Doctor pendiente"}, {
        "diagnostico_egreso": "pendiente"
    }) == {"diagnostico_egreso": False}

def test_comparar_detecta_regresion_de_dosis():
    """Reproduce el caso reportado por Carolina: la dosis es incorrecta pero el nombre está bien."""
    esperado = {"medicamentos": [{"nombre": "Amoxicilina", "dosis": "500 mg"}]}
    # El modelo devuelve el nombre bien pero la dosis mal
    datos = {"medicamentos": [{"nombre": "Amoxicilina", "dosis": "5000 mg"}]}
    
    resultados = comparar(esperado, datos)
    
    # El comparador debe generar resultados individuales por campo
    assert resultados["medicamentos.0.nombre"] is True
    assert resultados["medicamentos.0.dosis"] is False
