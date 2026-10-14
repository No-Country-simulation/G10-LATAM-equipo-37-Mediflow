"""Tests para el fallback por regex de extraer.py (GS-27 y certificados)."""


from agent.nodes.extraer import _extraer_por_regex

# --- Test 1: GS-27 (certificado) → Paula Soria sin saltos de línea ---

def test_certificado_medico_toma_medico_al_pie():
    """Un certificado sin 'Medico Solicitante:' toma a quien firma al pie."""
    texto = (
        "CERTIFICADO MEDICO\n"
        "Paciente: Juan Pérez\n"
        "Edad: 45 años\n"
        "El paciente se encuentra apto para trabajar.\n"
        "\n"
        "Dra. Paula Soria\n"
        "Matrícula: MP 73624\n"
    )
    datos = _extraer_por_regex(texto, tipo_documento="Certificado Medico")
    assert datos["medico_solicitante"]["nombre"] == "Paula Soria"
    assert "Matrícula" not in (datos["medico_solicitante"]["nombre"] or "")
    assert "\n" not in (datos["medico_solicitante"]["nombre"] or "")


# --- Test 2: Informe sin línea de solicitante → sigue en None ---

def test_informe_sin_solicitante_sigue_en_none():
    """Un informe (no certificado) sin 'Medico Solicitante:' queda en None."""
    texto = (
        "INFORME DE ESTUDIO\n"
        "Paciente: María López\n"
        "Estudio: Radiografía de tórax\n"
        "CONCLUSION: Sin hallazgos patológicos.\n"
    )
    datos = _extraer_por_regex(texto, tipo_documento="Informe de Estudio")
    assert datos["medico_solicitante"]["nombre"] is None


# --- Test 3: Receta con "Firma: Ana Perez" (paciente) → None ---

def test_receta_con_firma_de_paciente_no_toma_medico():
    """Una receta con 'Firma:' de la paciente no debe tomar a la paciente como médico."""
    texto = (
        "RECETA MEDICA\n"
        "Paciente: Ana Perez\n"
        "Medicamento: Losartán 50 mg\n"
        "Firma: Ana Perez\n"
    )
    datos = _extraer_por_regex(texto, tipo_documento="Receta Medica")
    assert datos["medico_solicitante"]["nombre"] is None
