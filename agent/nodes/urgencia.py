"""Detecta urgencia y alto riesgo farmacológico.

Cuatro fuentes independientes, basta con que una dispare:

1. Hallazgo crítico de la lista de `rules.yaml`.
2. Palabra de urgencia de la lista de `rules.yaml`.
3. Valor crítico de laboratorio, aunque el texto no diga que es urgente.
4. Juicio del modelo: `nivel_prioridad = Urgente`.

Regla A (ADR-002): las fuentes 1, 2 y 3 son listas automáticas y solo se aplican a los tipos de
`deteccion_automatica_urgencia.aplica_a`, que son informes de estudio, informes de laboratorio y
órdenes. En recetas, epicrisis y certificados decide el modelo, porque ahí las frases de alarma
suelen ser instrucciones de alta o diagnósticos ya tratados: una epicrisis de alta tras un
tromboembolismo no es una urgencia activa.

El alto riesgo farmacológico se detecta solo en recetas y no es una urgencia: manda el documento a
Farmacia Hospitalaria con auditoría, nunca a Emergencia.
"""
import re

from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState

TIPO_RECETA = "Receta Medica"


def _mencion_afirmativa(texto: str, termino: str) -> bool:
    """Filtra solo negaciones directas; no resuelve contexto clínico general.

    No suprime incertidumbre ("no se descarta") ni menciones afirmativas posteriores.
    """
    for m in re.finditer(rf"(?<!\w){re.escape(termino.lower())}(?!\w)", texto):
        prefijo = texto[max(0, m.start() - 80):m.start()]
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
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):  # separador de miles
        texto = texto.replace(".", "")
    return float(texto.replace(",", ".")) if re.fullmatch(r"\d+(\.\d+)?", texto.replace(",", ".")) else None


def _valores_criticos(texto: str, reglas: dict) -> list[str]:
    """Busca cada analito y el primer número que lo acompaña."""
    motivos = []
    for regla in reglas.get("valores_criticos_laboratorio", []):
        analito = str(regla.get("analito", "")).lower()
        operador = str(regla.get("operador", ""))
        if not analito:
            continue
        if operador == "texto":
            esperado = str(regla.get("valor", "")).lower()
            # ".{0,40}?" y no "\\W": entre el analito y el valor puede haber letras, como en
            # "troponina I elevada".
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
                break  # una mención por analito alcanza
    return motivos


def _aplica_deteccion_automatica(tipo: str, reglas: dict) -> bool:
    configurado = reglas.get("deteccion_automatica_urgencia", {}).get("aplica_a")
    if not configurado:  # sin la clave, se comporta como antes: aplica a todos los tipos
        return True
    return tipo in configurado


def _alto_riesgo(state: TriageState, tipo: str, reglas: dict) -> list[str]:
    """Solo en recetas. Compara por inclusión: 'Insulina glargina 100 UI' contiene 'insulina'."""
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


def detectar_urgencia(state: TriageState) -> dict:
    reglas = load_rules()
    texto = state.get("texto", "").lower()
    tipo = state.get("clasificacion", {}).get("tipo_documento", "Otro")
    automatica = _aplica_deteccion_automatica(tipo, reglas)
    motivos = []

    if automatica:
        for hallazgo in reglas.get("hallazgos_criticos", []):
            if _mencion_afirmativa(texto, hallazgo):
                motivos.append(f"hallazgo critico: {hallazgo}")
        for palabra in reglas.get("palabras_urgencia", []):
            if _mencion_afirmativa(texto, palabra):
                motivos.append(f"palabra clave: {palabra}")
        motivos.extend(_valores_criticos(texto, reglas))

    if state.get("clasificacion", {}).get("nivel_prioridad") == "Urgente":
        motivos.append("prioridad del modelo: Urgente")

    urgencia = {
        "detectada": bool(motivos),
        "motivos": motivos,
        "alto_riesgo_farmacologico": _alto_riesgo(state, tipo, reglas),
        # Queda en la traza para poder explicar por qué un documento no disparó las listas.
        "deteccion_automatica_aplicada": automatica,
    }
    return {"urgencia": urgencia, "trace": step(state, "detectar_urgencia", urgencia)}
