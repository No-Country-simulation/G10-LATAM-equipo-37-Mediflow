"""N2-05: decisión humana validada, sin efectos laterales antes del interrupt."""
from copy import deepcopy
from typing import Any, Literal

from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.nodes.enrutar import enrutar
from agent.nodes.puntuar import puntuar
from agent.nodes.urgencia import detectar_urgencia
from agent.nodes.validar import validar
from agent.rules.loader import load_rules
from agent.schemas.contrato import NivelPrioridad, TipoDocumento


class DecisionHumana(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    accion: Literal["aprobar", "corregir", "rechazar"]
    revisor: str = Field(min_length=1)
    motivo: str = Field(min_length=1)
    correcciones: dict[str, Any] | None = None
    revision_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def coherencia(self):
        if self.accion == "corregir":
            if not self.correcciones:
                raise ValueError("Corregir requiere al menos un campo")
            validar_correcciones(self.correcciones)
        elif self.correcciones is not None:
            raise ValueError("Solo corregir admite correcciones")
        return self


_TEXTOS = set("estudio_realizado procedimiento_solicitado diagnostico_principal "
              "diagnostico_egreso cie10_sugerido hallazgos conclusion fecha institucion "
              "diagnostico justificacion fecha_ingreso fecha_egreso motivo_ingreso "
              "tratamiento indicaciones_alta motivo texto_libre".split())
_TEXTOS.update({"paciente.nombre", "paciente.fecha_nacimiento",
                "medico_solicitante.nombre", "medico_solicitante.matricula"})
_MED = {"nombre", "dosis", "frecuencia", "duracion"}


def validar_correcciones(cambios):
    for campo, valor in cambios.items():
        if campo in _TEXTOS:
            valido = valor is None or isinstance(valor, str)
        elif campo in {"paciente.edad", "dias_reposo"}:
            valido = valor is None or (type(valor) is int and valor >= 0)
        elif campo == "medicamentos":
            valido = isinstance(valor, list) and all(
                isinstance(m, dict) and set(m) <= _MED
                and all(v is None or isinstance(v, str) for v in m.values()) for m in valor
            )
        elif campo == "estudios_solicitados":
            valido = isinstance(valor, list) and all(isinstance(v, str) for v in valor)
        elif campo == "clasificacion.tipo_documento":
            valido = valor in {t.value for t in TipoDocumento}
        elif campo == "clasificacion.nivel_prioridad":
            valido = valor in {t.value for t in NivelPrioridad}
        elif campo == "clasificacion.especialidad":
            valido = valor is None or isinstance(valor, str)
        else:
            valido = False
        if not valido:
            raise ValueError("Campo o valor de corrección no permitido")


def necesita_revision(state):
    return bool(state.get("decision", {}).get("requiere_auditoria_humana"))


def aplicar_decision(state, entrada):
    respuesta = DecisionHumana.model_validate(entrada)
    nuevo = deepcopy(state)
    version = state.get("revision_version", 1)
    if respuesta.revision_version is not None and respuesta.revision_version != version:
        raise ValueError("La revisión cambió; vuelva a cargar la cola")
    nuevo["resolucion_humana"] = respuesta.model_dump(exclude={"revision_version"})
    nuevo["revision_version"] = version + 1
    nuevo["rechazado"] = respuesta.accion == "rechazar"
    if nuevo["rechazado"]:
        return nuevo
    if respuesta.accion == "aprobar":
        decision = nuevo["decision"]
        if decision["destino_principal"] == "Cola_Revision_Humana":
            tipo = nuevo.get("clasificacion", {}).get("tipo_documento", "Otro")
            destino = load_rules()["destinos"]["por_tipo"].get(tipo)
            if not destino or destino == "Cola_Revision_Humana":
                raise ValueError("Documento sin destino operativo: corrija el tipo o rechace")
            decision["destino_principal"] = destino
        decision["requiere_auditoria_humana"] = False
        decision["justificacion_enrutamiento"] = "Extracción aprobada por revisión humana"
        return nuevo
    for campo, valor in respuesta.correcciones.items():
        partes = campo.split(".")
        destino = nuevo.setdefault("datos_extraidos", {})
        if partes[0] == "clasificacion":
            destino = nuevo.setdefault("clasificacion", {})
            partes = partes[1:]
        for parte in partes[:-1]:
            if not isinstance(destino.get(parte), dict):
                destino[parte] = {}
            destino = destino[parte]
        destino[partes[-1]] = deepcopy(valor)
    terminos = load_rules().get("medicamentos_alto_riesgo", [])
    for med in nuevo.get("datos_extraidos", {}).get("medicamentos", []) or []:
        med["alto_riesgo"] = any(t.lower() in (med.get("nombre") or "").lower() for t in terminos)
    for nodo in (validar, puntuar, detectar_urgencia, enrutar):
        nuevo.update(nodo(nuevo))
    # Las trazas de esos nodos incluyen datos clínicos. El resumen de la revisión no los propaga.
    nuevo["trace"] = state.get("trace", []) + [{"nodo": "revision_humana", "detalle": "corregir"}]
    return nuevo


def revision_humana(state):
    respuesta = interrupt({"documento_id": state["documento_id"],
                           "revision_version": state.get("revision_version", 1)})
    return aplicar_decision(state, respuesta)
