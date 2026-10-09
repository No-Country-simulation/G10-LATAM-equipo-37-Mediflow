"""Estado compartido entre los nodos del grafo."""
from typing import Any, Optional, TypedDict


class TriageState(TypedDict, total=False):
    documento_id: str
    tipo_archivo: str               # PDF | IMAGEN | TEXTO | JSON
    canal_origen: str
    ruta_original: str              # objeto en recibidos/
    texto: str                      # texto recibido o extraído
    imagenes: list[str]             # páginas renderizadas, si aplica
    legibilidad: float              # 0 a 1
    clasificacion: dict[str, Any]
    datos_extraidos: dict[str, Any]
    validacion: dict[str, Any]      # errores, conflictos, campos_faltantes
    score: float
    urgencia: dict[str, Any]        # detectada, motivo, fuente
    segunda_opinion: dict[str, Any]
    decision: dict[str, Any]
    almacenamiento: dict[str, Any]
    modelo_utilizado: str
    trace: list[dict[str, Any]]     # un registro por nodo
    error: Optional[str]
    evidencias: list[dict[str, Any]]
    hallazgo_critico: Optional[str]
    ambiguedad: Optional[str]