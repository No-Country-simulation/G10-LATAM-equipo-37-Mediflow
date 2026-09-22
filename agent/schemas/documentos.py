"""Un esquema de extracción por tipo de documento. El LLM devuelve JSON que se valida contra estos modelos."""
from typing import Optional

from pydantic import BaseModel

from agent.schemas.contrato import Medicamento, MedicoSolicitante, Paciente


class BaseDocumento(BaseModel):
    paciente: Paciente = Paciente()
    profesional: MedicoSolicitante = MedicoSolicitante()
    fecha: Optional[str] = None
    institucion: Optional[str] = None


class RecetaMedica(BaseDocumento):
    medicamentos: list[Medicamento] = []
    diagnostico: Optional[str] = None
    cie10_sugerido: Optional[str] = None


class InformeEstudio(BaseDocumento):
    estudio_realizado: Optional[str] = None
    hallazgos: Optional[str] = None
    conclusion: Optional[str] = None
    diagnostico_principal: Optional[str] = None
    cie10_sugerido: Optional[str] = None


class OrdenProcedimiento(BaseDocumento):
    procedimiento_solicitado: Optional[str] = None
    justificacion: Optional[str] = None
    diagnostico: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    estudios_solicitados: list[str] = []


class Epicrisis(BaseDocumento):
    motivo_ingreso: Optional[str] = None
    diagnostico_egreso: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    tratamiento: Optional[str] = None
    indicaciones_alta: Optional[str] = None


class CertificadoMedico(BaseDocumento):
    motivo: Optional[str] = None
    dias_reposo: Optional[int] = None
    diagnostico: Optional[str] = None
    cie10_sugerido: Optional[str] = None


ESQUEMAS_POR_TIPO = {
    "Receta Medica": RecetaMedica,
    "Informe de Estudio por Imagenes": InformeEstudio,
    "Informe de Laboratorio": InformeEstudio,
    "Orden de Solicitud de Procedimiento": OrdenProcedimiento,
    "Epicrisis": Epicrisis,
    "Certificado Medico": CertificadoMedico,
}
