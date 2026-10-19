"""Minimización de trazas: valores controlados y referencia HMAC opcional.

No modifica el documento operativo ni el que necesita leer el auditor.
"""
import hashlib
import hmac
import math
import os
import re
import unicodedata

from agent.schemas.contrato import DestinoEnrutamiento, NivelPrioridad, TipoArchivo, TipoDocumento


def seudonimizar(valor: str | None) -> str | None:
    if not valor:
        return valor
    clave = os.environ.get("MEDIFLOW_CLAVE_SEUDONIMO", "")
    if not clave:
        raise ValueError("Falta MEDIFLOW_CLAVE_SEUDONIMO")
    normalizado = re.sub(r"[\s.\-]", "", unicodedata.normalize("NFKC", valor)).upper()
    return "P-" + hmac.new(clave.encode(), normalizado.encode(), hashlib.sha256).hexdigest()[:24]


_ENUMS = {
    "tipo_documento": {v.value for v in TipoDocumento},
    "tipo_archivo": {v.value for v in TipoArchivo},
    "nivel_prioridad": {v.value for v in NivelPrioridad},
    "destino_principal": {v.value for v in DestinoEnrutamiento},
    "categoria_amb": {f"AMB-{i}" for i in range(1, 7)},
    "status_backup": {"exito", "error"},
    "idioma": {"es", "en", "pt"},
}
_SCORES = {"score", "legibilidad", "validacion", "modelo", "acuerdo", "score_confianza_clasificacion"}
_FLAGS = {"detectada", "alto_riesgo", "requiere_auditoria_humana", "notificacion_generada",
          "legible", "legibilidad_provisional", "enviada", "multiples_documentos"}


def detalle_seguro(detalle) -> dict:
    """Lista permitida: nunca copiar texto libre, rutas, evidencias ni excepciones.

    Los diagnósticos/motivos completos siguen en el estado operativo privado.
    Campos desconocidos se omiten, incluso si contienen números.
    """
    if not isinstance(detalle, dict):
        return {}
    limpio = {}
    for clave, valor in detalle.items():
        if clave in _ENUMS and isinstance(valor, str) and valor in _ENUMS[clave]:
            limpio[clave] = valor
        elif clave in _SCORES and type(valor) in (int, float) and math.isfinite(valor) and 0 <= valor <= 1:
            limpio[clave] = valor
        elif clave in _FLAGS and type(valor) is bool:
            limpio[clave] = valor
        elif clave in {"imagenes", "caracteres"} and type(valor) is int and 0 <= valor <= 10**9:
            limpio[clave] = valor
        elif clave in {"campos", "campos_faltantes", "conflictos"} and isinstance(valor, list):
            limpio[clave + "_cantidad"] = len(valor)
        elif clave in {"campos_cantidad", "campos_faltantes_cantidad", "conflictos_cantidad"}:
            if type(valor) is int and valor >= 0:
                limpio[clave] = valor
    return limpio


def registro_seguro(registro: dict) -> dict:
    nodos = {"normalizar", "clasificar", "extraer", "validar", "puntuar", "enrutar",
             "detectar_urgencia", "urgencia", "persistir", "notificar", "segunda_opinion",
             "revision_humana", "preparar_revision", "cerrar_revision"}
    limpio = {"nodo": registro.get("nodo") if registro.get("nodo") in nodos else "desconocido",
              "detalle": detalle_seguro(registro.get("detalle"))}
    if type(registro.get("ts")) in (int, float) and math.isfinite(registro["ts"]):
        limpio["ts"] = registro["ts"]
    modelos = {"stub", os.getenv("LLM_PRIMARY", "gemini/gemini-2.5-flash")}
    modelos.update(m.strip() for m in os.getenv("LLM_FALLBACKS", "").split(",") if m.strip())
    if isinstance(registro.get("modelo"), str) and registro["modelo"] in modelos:
        limpio["modelo"] = registro["modelo"]
    ref = registro.get("paciente_ref")
    if isinstance(ref, str) and re.fullmatch(r"P-[0-9a-f]{24}", ref):
        limpio["paciente_ref"] = ref
    return limpio
