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
