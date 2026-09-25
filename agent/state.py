"""Estado compartido entre los nodos del grafo.

Es el contrato interno del grafo: cada nodo lee lo que necesita y devuelve solo las claves que
cambia. Las claves declaradas acá son las que algún nodo escribe; si un nodo devuelve una clave que
no está en esta lista, se pierde silenciosamente, así que conviene mantenerla completa.

Entre paréntesis, quién escribe cada clave.
"""
from typing import Any, Optional, TypedDict


class TriageState(TypedDict, total=False):
    documento_id: str
    tipo_archivo: str               # PDF | IMAGEN | TEXTO | JSON
    canal_origen: str
    ruta_original: str              # objeto en recibidos/
    texto: str                      # texto recibido o extraído
    imagenes: list[str]             # páginas renderizadas (base64) o rutas, si aplica
    legibilidad: float              # 0 a 1
    clasificacion: dict[str, Any]   # clasificar: tipo, especialidad, prioridad, confianza
    datos_extraidos: dict[str, Any] # extraer: datos del documento según el esquema del tipo
    evidencias: list[dict[str, Any]]  # extraer: fragmento del documento que sustenta cada campo
    hallazgo_critico: dict[str, Any]  # extraer: hallazgo de riesgo vital detectado por el modelo
    ambiguedad: dict[str, Any]      # extraer: categoría de ambigüedad detectada por el modelo
    validacion: dict[str, Any]      # validar: errores, conflictos, campos_faltantes
    score: float                    # puntuar: score compuesto de confianza
    urgencia: dict[str, Any]        # urgencia: detectada, motivos, alto_riesgo_farmacologico
    segunda_opinion: dict[str, Any] # segunda_opinion: acuerdo, campos en desacuerdo, modelo
    decision: dict[str, Any]        # enrutar: destino, auditoría, justificación, notificación
    almacenamiento: dict[str, Any]  # persistir: bucket, ruta del objeto, estado del respaldo
    modelo_utilizado: str           # clasificar / extraer: el que respondió la primera extracción
    trace: list[dict[str, Any]]     # un registro por nodo, con tiempo, modelo y detalle
    traza_resumen: dict[str, Any]   # run_triage: resumen de la traza para la API y la UI
    error: Optional[str]
