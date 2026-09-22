"""
MediFlow · Contrato de entrada y salida
Hackathon ONE G10 · Oracle Next Education & Alura

Sigue el ejemplo del brief; los nombres de campo no se cambian.
Cualquier cambio se hace en este archivo y en docs/api-contract.md en el mismo PR.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# ENUMS · valores controlados del contrato
# =============================================================================


class TipoArchivo(str, Enum):
    """Formato del documento de entrada."""
    TEXTO = "TEXTO"
    JSON = "JSON"
    PDF = "PDF"
    IMAGEN = "IMAGEN"


class TipoDocumento(str, Enum):
    """Los 6 tipos documentales soportados más el comodín 'Otro'."""
    RECETA_MEDICA = "Receta Medica"
    INFORME_IMAGENES = "Informe de Estudio por Imagenes"
    INFORME_LABORATORIO = "Informe de Laboratorio"
    ORDEN_PROCEDIMIENTO = "Orden de Solicitud de Procedimiento"
    EPICRISIS = "Epicrisis"
    CERTIFICADO_MEDICO = "Certificado Medico"
    OTRO = "Otro"


class NivelPrioridad(str, Enum):
    """Nivel de prioridad clínica."""
    URGENTE = "Urgente"
    PRIORITARIO = "Prioritario"
    RUTINA = "Rutina"


class DestinoEnrutamiento(str, Enum):
    """Los 5 destinos operativos del agente."""
    COLA_EMERGENCIA_MEDICA = "Cola_Emergencia_Medica"
    FARMACIA_HOSPITALARIA = "Farmacia_Hospitalaria"
    AUDITORIA_AUTORIZACIONES = "Auditoria_Autorizaciones"
    HISTORIA_CLINICA_ELECTRONICA = "Historia_Clinica_Electronica"
    COLA_REVISION_HUMANA = "Cola_Revision_Humana"


class EstadoProcesamiento(str, Enum):
    """Estado del procesamiento del documento."""
    PROCESADO = "procesado"
    REVISION_HUMANA = "revision_humana"
    RECHAZADO = "rechazado"
    PENDIENTE = "pendiente"


class CategoriaAmbiguedad(str, Enum):
    """Las 5 categorías de ambigüedad (sección 6 del api-contract)."""
    AMB_1 = "AMB-1"  # Campo obligatorio faltante
    AMB_2 = "AMB-2"  # Contradicción interna
    AMB_3 = "AMB-3"  # Dosis fuera de rango o medicamento no identificable
    AMB_4 = "AMB-4"  # Texto truncado o parcialmente ilegible
    AMB_5 = "AMB-5"  # Dos documentos en uno


class StatusBackup(str, Enum):
    """Estado del respaldo en OCI Object Storage."""
    EXITO = "exito"
    PENDIENTE = "pendiente"
    ERROR = "error"


# =============================================================================
# ENTRADA
# =============================================================================


class TriageRequest(BaseModel):
    """Solicitud de triaje (sección 1.1 del api-contract)."""
    documento_id: str
    tipo_archivo: Literal["PDF", "IMAGEN", "TEXTO", "JSON"] = "TEXTO"
    documento_texto: Optional[str] = None
    canal_origen: Optional[str] = None


# =============================================================================
# DATOS EXTRAÍDOS
# =============================================================================


class Paciente(BaseModel):
    """Datos del paciente. El brief usa `nome`; se respeta el contrato."""
    nome: Optional[str] = None
    edad: Optional[int] = Field(default=None, ge=0, le=130)


class MedicoSolicitante(BaseModel):
    """Datos del profesional solicitante o firmante."""
    nombre: Optional[str] = None
    matricula: Optional[str] = None


class Medicamento(BaseModel):
    """
    Medicamento extraído de una receta.
    IMPORTANTE: `nombre` es Optional porque puede ser ilegible (AMB-3).
    """
    nombre: Optional[str] = None
    dosis: Optional[str] = None
    frecuencia: Optional[str] = None
    duracion: Optional[str] = None
    alto_riesgo: bool = False


class DatosExtraidos(BaseModel):
    """
    Datos clínicos y administrativos extraídos.
    Un dato que no está en el documento es null. NUNCA se inventa.
    """
    paciente: Paciente = Field(default_factory=Paciente)
    medico_solicitante: MedicoSolicitante = Field(default_factory=MedicoSolicitante)
    estudio_realizado: Optional[str] = None
    procedimiento_solicitado: Optional[str] = None
    diagnostico_principal: Optional[str] = None
    diagnostico_egreso: Optional[str] = None
    cie10_sugerido: Optional[str] = None
    hallazgos: Optional[str] = None
    conclusion: Optional[str] = None
    medicamentos: list[Medicamento] = Field(default_factory=list)
    estudios_solicitados: list[str] = Field(default_factory=list)


# =============================================================================
# CLASIFICACIÓN Y ENRUTAMIENTO
# =============================================================================


class Clasificacion(BaseModel):
    """
    Resultado de la clasificación documental.
    Ampliado con `TipoDocumento` y `NivelPrioridad` (enums) en lugar de str/Literal.
    """
    tipo_documento: TipoDocumento
    especialidad: Optional[str] = None
    nivel_prioridad: NivelPrioridad = NivelPrioridad.RUTINA
    score_confianza_clasificacion: float = Field(ge=0, le=1)


class NotificacionGenerada(BaseModel):
    """Notificación generada por el agente (urgencia o alto riesgo)."""
    canal: str
    mensaje: str


class DecisionEnrutamiento(BaseModel):
    """Decisión de enrutamiento del agente."""
    destino_principal: DestinoEnrutamiento
    requiere_auditoria_humana: bool
    justificacion_enrutamiento: str
    notificacion_generada: Optional[NotificacionGenerada] = None


class AlmacenamientoOci(BaseModel):
    """Resultado del respaldo en OCI Object Storage."""
    bucket: str
    ruta_objeto: str
    status_backup: StatusBackup


# =============================================================================
# EVIDENCIAS Y TRAZA (campos propios del equipo)
# =============================================================================


class Evidencia(BaseModel):
    """
    Evidencia de extracción. Campo propio del equipo (sección 2 del contrato).
    Por cada campo extraído, el fragmento del documento que lo sustenta.
    """
    campo: str
    fragmento: Optional[str] = None
    valor_extraido: Optional[object] = None


class RegistroTraza(BaseModel):
    """Registro de traza por nodo del grafo."""
    nodo: str
    tiempo_ms: int = Field(ge=0)
    detalle: Optional[str] = None
    modelo: Optional[str] = None


# =============================================================================
# SALIDA
# =============================================================================


class TriageResponse(BaseModel):
    """
    Respuesta del agente de triaje.
    Idéntica al brief, más 4 campos propios del equipo:
    score_confianza, modelo_utilizado, evidencias y trace.
    """
    status: EstadoProcesamiento
    documento_id: str
    clasificacion: Clasificacion
    datos_extraidos: DatosExtraidos
    decision_enrutamiento: DecisionEnrutamiento
    almacenamiento_oci: AlmacenamientoOci
    # Campos propios del equipo:
    score_confianza: float = Field(ge=0, le=1)
    modelo_utilizado: Optional[str] = None
    evidencias: list[Evidencia] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)


__all__ = [
    # Enums
    "TipoArchivo",
    "TipoDocumento",
    "NivelPrioridad",
    "DestinoEnrutamiento",
    "EstadoProcesamiento",
    "CategoriaAmbiguedad",
    "StatusBackup",
    # Entrada
    "TriageRequest",
    # Extracción
    "Paciente",
    "MedicoSolicitante",
    "Medicamento",
    "DatosExtraidos",
    # Clasificación / enrutamiento
    "Clasificacion",
    "NotificacionGenerada",
    "DecisionEnrutamiento",
    "AlmacenamientoOci",
    # Evidencias / traza
    "Evidencia",
    "RegistroTraza",
    # Salida
    "TriageResponse",
]