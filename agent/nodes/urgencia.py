"""Detecta urgencia y alto riesgo farmacológico.

Regla A (ADR-002): las fuentes automáticas (hallazgos críticos, palabras de urgencia y
valores críticos de laboratorio) solo aplican a los tipos listados en
`deteccion_automatica_urgencia.aplica_a`. En recetas, epicrisis y certificados la urgencia
la decide el modelo (`nivel_prioridad = Urgente`), porque las frases de alarma suelen ser
instrucciones de alta o diagnósticos ya tratados, no una urgencia activa.

El alto riesgo farmacológico es una señal de revisión humana, no de emergencia: solo aplica a
recetas y se compara por inclusión (`"insulina"` detecta `"insulina glargina"`).
"""

import re

from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState

TIPO_RECETA = "Receta Medica"


def _mencion_afirmativa(texto: str, termino: str) -> bool:
    """Filtra negaciones directas para evitar falsos positivos en instrucciones/seguimientos."""
    for m in re.finditer(rf"(?<!\w){re.escape(termino.lower())}(?!\w)", texto):
        prefijo = texto[max(0, m.start() - 80) : m.start()]
        negada = re.search(
            r"\b(?:sin(?:\s+(?:evidencia|signos|datos)\s+de)?|"
            r"no\s+(?:hay|presenta|se\s+observa|se\s+detecta))\s*$",
            prefijo,
        )
        if not negada:
            return True
    return False


def _a_numero(crudo: str) -> float | None:
    """Acepta 6,8 y 15.000, que es como se escriben los números en los documentos en español."""
    texto = crudo.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        texto = texto.replace(".", "")
    return float(texto.replace(",", ".")) if re.fullmatch(r"\d+(\.\d+)?", texto.replace(",", ".")) else None


def _valores_criticos(texto: str, reglas: dict) -> list[str]:
    """Busca cada analito y el primer número/valor que lo acompaña."""
    motivos = []
    for regla in reglas.get("valores_criticos_laboratorio", []):
        analito = str(regla.get("analito", "")).lower()
        operador = str(regla.get("operador", ""))
        if not analito:
            continue
        if operador == "texto":
            esperado = str(regla.get("valor", "")).lower()
            if re.search(rf"{re.escape(analito)}.{{0,40}}?{re.escape(esperado)}", texto):
                motivos.append(f"valor critico de laboratorio: {analito} {esperado}")
            continue
        for encontrado in re.finditer(rf"{re.escape(analito)}[^0-9<>\n]{{0,30}}(\d[\d.,]*)", texto):
            valor = _a_numero(encontrado.group(1))
            if valor is None:
                continue
            limite = float(regla.get("valor", 0))
            if (operador == ">=" and valor >= limite) or (operador == "<=" and valor <= limite):
                unidad = regla.get("unidad", "")
                motivos.append(f"valor critico de laboratorio: {analito} {encontrado.group(1)} {unidad}".strip())
                break
    return motivos


def _aplica_deteccion_automatica(tipo: str, reglas: dict) -> bool:
    configurado = reglas.get("deteccion_automatica_urgencia", {}).get("aplica_a")
    if not configurado:
        return True
    return tipo in configurado


def _alto_riesgo(state: TriageState, tipo: str, reglas: dict) -> list[str]:
    """Solo en recetas. Compara por inclusión: 'insulina glargina' contiene 'insulina'."""
    if tipo != TIPO_RECETA:
        return []
    terminos = [t.lower() for t in reglas.get("medicamentos_alto_riesgo", [])]
    encontrados = []
    for medicamento in state.get("datos_extraidos", {}).get("medicamentos", []) or []:
        nombre = (medicamento.get("nombre") or "").strip()
        if not nombre:
            continue
        if medicamento.get("alto_riesgo") or any(t in nombre.lower() for t in terminos):
            encontrados.append(nombre)
    return encontrados


def _valor_critico_detectado(texto: str, regla: dict) -> bool:
    """Detecta analitos críticos por comparación con el umbral dado."""
    analito = regla["analito"]
    operador = regla["operador"]

    if operador == "texto":
        valor_esperado = str(regla["valor"]).lower()
        return analito in texto and valor_esperado in texto

    match = re.search(rf"{re.escape(analito)}\D{{0,15}}?(\d+(?:[.,]\d+)?)", texto, flags=re.IGNORECASE)
    if not match:
        return False
    try:
        valor_extraido = float(match.group(1).replace(",", "."))
    except ValueError:
        return False

    umbral = float(regla["valor"])
    if operador == ">=":
        return valor_extraido >= umbral
    if operador == "<=":
        return valor_extraido <= umbral
    return False


def detectar_urgencia(state: TriageState) -> dict:
    reglas = load_rules()
    texto = state.get("texto", "").lower()
    tipo_documento = state.get("clasificacion", {}).get("tipo_documento", "")
    motivos: list[str] = []

    automatica = _aplica_deteccion_automatica(tipo_documento, reglas)
    if automatica:
        for hallazgo in reglas.get("hallazgos_criticos", []):
            if hallazgo.lower() in texto:
                motivos.append(f"hallazgo critico: {hallazgo}")
        for palabra in reglas.get("palabras_urgencia", []):
            if palabra.lower() in texto:
                motivos.append(f"palabra clave: {palabra}")
        for regla_valor in reglas.get("valores_criticos_laboratorio", []):
            if _valor_critico_detectado(texto, regla_valor):
                motivos.append(
                    f"valor critico de laboratorio: {regla_valor['analito']} "
                    f"{regla_valor['operador']} {regla_valor['valor']} {regla_valor.get('unidad', '')}".strip()
                )

    if state.get("clasificacion", {}).get("nivel_prioridad") == "Urgente":
        motivos.append("prioridad del modelo: Urgente")

    urgencia = {
        "detectada": bool(motivos),
        "motivos": motivos,
        "alto_riesgo_farmacologico": _alto_riesgo(state, tipo_documento, reglas),
        "deteccion_automatica_aplicada": automatica,
    }
    return {"urgencia": urgencia, "trace": step(state, "detectar_urgencia", urgencia)}
