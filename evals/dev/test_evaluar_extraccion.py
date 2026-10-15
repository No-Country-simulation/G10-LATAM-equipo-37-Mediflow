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
