"""
MediFlow · Esquemas de extracción por tipo documental
Hackathon ONE G10 · Oracle Next Education & Alura

Este archivo tiene DOS responsabilidades:

1. Definir modelos Pydantic específicos por tipo documental. El LLM
   devuelve JSON que se valida contra estos modelos.

2. Declarar qué campos son obligatorios por tipo (para detectar AMB-1).

Fuente de verdad: agent/rules/rules.yaml y docs/api-contract.md.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from agent.schemas.contrato import (
    Medicamento,
    MedicoSolicitante,
    Paciente,
)

# =============================================================================
# MODELOS BASE POR TIPO DOCUMENTAL
# =============================================================================


class BaseDocumento(BaseModel):
    """
    Campos comunes a todos los tipos documentales.

    NOTA: usamos `default_factory` en lugar de instanciar directamente.
    En Pydantic v2, `paciente: Paciente = Paciente()` crea una instancia
    COMPARTIDA entre todos los objetos, provocando bugs sutiles.
    """
    paciente: Paciente = Field(default_factory=Paciente)
    medico_solicitante: MedicoSolicitante = Field(default_factory=MedicoSolicitante)
    fecha: Optional[str] = None
    institucion: Optional[str] = None


class RecetaMedica(BaseDocumento):
    """Receta médica (sección 3 del api-contract)."""
    medicamentos: list[Medicamento] = Field(default_factory=list)
    diagnostico: Optional[str] = None
    cie10_sugerido: Optional[str] = None


class InformeEstudio(BaseDocumento):
    """Informe de estudio por imágenes (sección 3 del api-contract)."""
    estudio_realizado: Optional[str] = None
    hallazgos: Optional[str] = None
    conclusion: Optional[str] = None
    diagnostico_principal: Optional[str] = None
    cie10_sugerido: Optional[str] = None


class InformeLaboratorio(BaseDocumento):
    """
    Informe de laboratorio. Separado de InformeEstudio por si EQU-01
    decide diferenciarlos (decisión 2 del api-contract).
    """
    estudio_realizado: Optional[str] = None
    hallazgos: Optional[str] = None
    conclusion: Optional[str] = None
    diagnostico_principal: Optional[str] = None
    cie10_sugerido: Optional[str] = None


class OrdenProcedimiento(BaseDocumento):
    """Orden de solicitud de procedimiento (sección 3 del api-contract)."""
    procedimiento_solicitado: Optional[str] = None
    justificacion: Optional[str] = None
    diagnostico: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    estudios_solicitados: list[str] = Field(default_factory=list)


class Epicrisis(BaseDocumento):
    """Epicrisis / informe de alta (sección 3 del api-contract)."""
    motivo_ingreso: Optional[str] = None
    diagnostico_egreso: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    tratamiento: Optional[str] = None
    indicaciones_alta: Optional[str] = None


class CertificadoMedico(BaseDocumento):
    """Certificado médico (sección 3 del api-contract)."""
    motivo: Optional[str] = None
    dias_reposo: Optional[int] = None
    diagnostico: Optional[str] = None
    cie10_sugerido: Optional[str] = None


class OtroDocumento(BaseDocumento):
    """
    Documento que no encaja en ningún otro tipo.
    Siempre va a revisión humana, pero igual extraemos lo que se pueda
    para ayudar al auditor.
    """
    texto_libre: Optional[str] = None


# =============================================================================
# MAPEO TIPO → MODELO
# =============================================================================

ESQUEMAS_POR_TIPO: dict[str, type[BaseDocumento]] = {
    "Receta Medica": RecetaMedica,
    "Informe de Estudio por Imagenes": InformeEstudio,
    "Informe de Laboratorio": InformeLaboratorio,
    "Orden de Solicitud de Procedimiento": OrdenProcedimiento,
    "Epicrisis": Epicrisis,
    "Certificado Medico": CertificadoMedico,
    "Otro": OtroDocumento,
}


def obtener_esquema(tipo: str) -> type[BaseDocumento]:
    """
    Devuelve la clase Pydantic correspondiente a un tipo documental.

    Si el tipo no se reconoce, devuelve `OtroDocumento`.

    Ejemplo:
        >>> obtener_esquema("Receta Medica")
        <class 'agent.schemas.documentos.RecetaMedica'>
    """
    return ESQUEMAS_POR_TIPO.get(tipo, OtroDocumento)


# =============================================================================
# CAMPOS OBLIGATORIOS POR TIPO (para detectar AMB-1)
# =============================================================================

CAMPOS_OBLIGATORIOS: dict[str, list[str]] = {
    "Receta Medica": [
        "paciente.nome",
        "medico_solicitante.nombre",
        "medico_solicitante.matricula",
        "medicamentos",
    ],
    "Informe de Estudio por Imagenes": [
        "paciente.nome",
        "estudio_realizado",
        "conclusion",
    ],
    "Informe de Laboratorio": [
        "paciente.nome",
        "estudio_realizado",
    ],
    "Orden de Solicitud de Procedimiento": [
        "paciente.nome",
        "medico_solicitante.nombre",
        "medico_solicitante.matricula",
        "procedimiento_solicitado",
    ],
    "Epicrisis": [
        "paciente.nome",
        "diagnostico_egreso",
    ],
    "Certificado Medico": [
        "paciente.nome",
        "medico_solicitante.nombre",
        "medico_solicitante.matricula",
        "fecha",
    ],
    "Otro": [],
}


# =============================================================================
# DESTINOS POR TIPO (sin urgencia ni ambigüedad)
# =============================================================================

DESTINOS_POR_TIPO: dict[str, str] = {
    "Receta Medica": "Farmacia_Hospitalaria",
    "Informe de Estudio por Imagenes": "Historia_Clinica_Electronica",
    "Informe de Laboratorio": "Historia_Clinica_Electronica",
    "Orden de Solicitud de Procedimiento": "Auditoria_Autorizaciones",
    "Epicrisis": "Historia_Clinica_Electronica",
    "Certificado Medico": "Historia_Clinica_Electronica",
    "Otro": "Cola_Revision_Humana",
}


# =============================================================================
# HELPERS
# =============================================================================


def obtener_campos_obligatorios(tipo: str) -> list[str]:
    """Devuelve los campos obligatorios para un tipo documental."""
    return CAMPOS_OBLIGATORIOS.get(tipo, [])


def obtener_destino_por_tipo(tipo: str) -> str:
    """Devuelve el destino por defecto para un tipo documental."""
    return DESTINOS_POR_TIPO.get(tipo, "Cola_Revision_Humana")


def campo_esta_presente(datos_extraidos: dict, campo: str) -> bool:
    """
    Verifica si un campo (con notación de punto) tiene valor no nulo.
    Soporta rutas anidadas: 'paciente.nome' navega el dict.
    Las listas vacías cuentan como ausentes.
    """
    partes = campo.split(".")
    valor: Optional[object] = datos_extraidos

    for parte in partes:
        if not isinstance(valor, dict):
            return False
        valor = valor.get(parte)
        if valor is None:
            return False

    if isinstance(valor, list) and len(valor) == 0:
        return False

    return True


def detectar_campos_faltantes(tipo: str, datos_extraidos: dict) -> list[str]:
    """
    Devuelve los campos obligatorios que faltan o son nulos.
    Si la lista NO está vacía, el caso es AMB-1 y va a revisión humana.
    """
    obligatorios = obtener_campos_obligatorios(tipo)
    return [c for c in obligatorios if not campo_esta_presente(datos_extraidos, c)]


__all__ = [
    # Modelos
    "BaseDocumento",
    "RecetaMedica",
    "InformeEstudio",
    "InformeLaboratorio",
    "OrdenProcedimiento",
    "Epicrisis",
    "CertificadoMedico",
    "OtroDocumento",
    # Mapeo
    "ESQUEMAS_POR_TIPO",
    "obtener_esquema",
    # Reglas
    "CAMPOS_OBLIGATORIOS",
    "DESTINOS_POR_TIPO",
    "obtener_campos_obligatorios",
    "obtener_destino_por_tipo",
    "campo_esta_presente",
    "detectar_campos_faltantes",
]