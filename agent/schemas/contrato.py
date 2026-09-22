"""Contrato de entrada y salida. Sigue el ejemplo del brief; los nombres de campo no se cambian."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TriageRequest(BaseModel):
    documento_id: str
    tipo_archivo: Literal["PDF", "IMAGEN", "TEXTO", "JSON"] = "TEXTO"
    documento_texto: Optional[str] = None
    canal_origen: Optional[str] = None


class Paciente(BaseModel):
    nome: Optional[str] = None          # el brief usa "nome"; se respeta el contrato
    edad: Optional[int] = None


class MedicoSolicitante(BaseModel):
    nombre: Optional[str] = None
    matricula: Optional[str] = None


class Medicamento(BaseModel):
    nombre: str
    dosis: Optional[str] = None
    frecuencia: Optional[str] = None
    duracion: Optional[str] = None
    alto_riesgo: bool = False


class Clasificacion(BaseModel):
    tipo_documento: str
    especialidad: Optional[str] = None
    nivel_prioridad: Literal["Rutina", "Prioritario", "Urgente"] = "Rutina"
    score_confianza_clasificacion: float = Field(ge=0, le=1)


class DatosExtraidos(BaseModel):
    paciente: Paciente = Paciente()
    medico_solicitante: MedicoSolicitante = MedicoSolicitante()
    estudio_realizado: Optional[str] = None
    diagnostico_principal: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    medicamentos: list[Medicamento] = []
    estudios_solicitados: list[str] = []


class NotificacionGenerada(BaseModel):
    canal: str
    mensaje: str


class DecisionEnrutamiento(BaseModel):
    destino_principal: str
    requiere_auditoria_humana: bool
    justificacion_enrutamiento: str
    notificacion_generada: Optional[NotificacionGenerada] = None


class AlmacenamientoOci(BaseModel):
    bucket: str
    ruta_objeto: str
    status_backup: Literal["exito", "pendiente", "error"]


class TriageResponse(BaseModel):
    status: Literal["procesado", "revision_humana", "rechazado", "pendiente"]
    documento_id: str
    clasificacion: Clasificacion
    datos_extraidos: DatosExtraidos
    decision_enrutamiento: DecisionEnrutamiento
    almacenamiento_oci: AlmacenamientoOci
    score_confianza: float = Field(ge=0, le=1)
    modelo_utilizado: Optional[str] = None
    trace: list[dict] = []
