"""Tests de agent/schemas/documentos.py (Carlos, AI-02)."""


from agent.schemas.contrato import TipoDocumento
from agent.schemas.documentos import (
    ESQUEMAS_POR_TIPO,
    OtroDocumento,
    RecetaMedica,
    campo_esta_presente,
    detectar_campos_faltantes,
    obtener_campos_obligatorios,
    obtener_destino_por_tipo,
    obtener_esquema,
)


def test_todos_los_tipos_tienen_esquema():
    """Cada valor del enum TipoDocumento debe tener un esquema asociado."""
    for tipo in TipoDocumento:
        assert tipo.value in ESQUEMAS_POR_TIPO, (
            f"Falta el esquema para '{tipo.value}'"
        )


def test_todos_los_tipos_tienen_destino():
    """Cada tipo debe tener un destino por defecto."""
    from agent.schemas.documentos import DESTINOS_POR_TIPO

    for tipo in TipoDocumento:
        assert tipo.value in DESTINOS_POR_TIPO, (
            f"Falta el destino para '{tipo.value}'"
        )


def test_obtener_esquema_desconocido_devuelve_otro():
    """Un tipo desconocido devuelve OtroDocumento, no rompe."""
    assert obtener_esquema("Tipo Que No Existe") is OtroDocumento


def test_receta_medica_tiene_medicamentos_vacios():
    """La receta se instancia sin medicamentos por defecto."""
    receta = RecetaMedica()
    assert receta.medicamentos == []


def test_instancias_no_comparten_paciente():
    """
    Dos recetas distintas NO deben compartir la misma instancia de Paciente.
    Esto verifica que usamos default_factory y no un default mutable.
    """
    r1 = RecetaMedica()
    r2 = RecetaMedica()
    r1.paciente.nome = "Juan"
    assert r2.paciente.nome is None  # No se contagia


def test_campos_obligatorios_receta():
    """Una receta tiene 4 campos obligatorios."""
    campos = obtener_campos_obligatorios("Receta Medica")
    assert "paciente.nome" in campos
    assert "medicamentos" in campos
    assert len(campos) == 4


def test_detectar_campos_faltantes_informe():
    """Detecta correctamente los campos obligatorios ausentes."""
    datos = {
        "paciente": {"nome": None, "edad": 52},
        "estudio_realizado": "TAC de tórax",
        "conclusion": None,
    }
    faltantes = detectar_campos_faltantes(
        "Informe de Estudio por Imagenes", datos
    )
    assert "paciente.nome" in faltantes
    assert "conclusion" in faltantes
    assert "estudio_realizado" not in faltantes


def test_campo_lista_vacia_cuenta_como_ausente():
    """Una lista vacía se considera campo ausente (AMB-1)."""
    datos = {"medicamentos": []}
    assert not campo_esta_presente(datos, "medicamentos")


def test_destino_por_tipo():
    """El destino por tipo se resuelve correctamente."""
    assert (
        obtener_destino_por_tipo("Receta Medica")
        == "Farmacia_Hospitalaria"
    )
    assert (
        obtener_destino_por_tipo("Otro")
        == "Cola_Revision_Humana"
    )