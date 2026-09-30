"""Detecta urgencia (4 fuentes, Regla A / ADR-002) y alto riesgo farmacológico.

Cambios respecto a la versión anterior de este archivo en `develop`:

1. BUG corregido (Regla A / ADR-002): el stub anterior aplicaba hallazgos_criticos y
   palabras_urgencia a TODOS los tipos de documento. rules.yaml (deteccion_automatica_
   urgencia.aplica_a) dice que estas fuentes automáticas solo aplican a Informe de Estudio
   por Imagenes, Informe de Laboratorio y Orden de Solicitud de Procedimiento. En receta,
   epicrisis y certificado, frases como "de urgencia" suelen ser instrucciones de alta o
   diagnósticos ya tratados, no una urgencia real (son justo los casos GS-01, GS-04, GS-24,
   GS-25 del golden set, que NO deben disparar urgencia).
2. BUG corregido: la comprobación de alto riesgo estaba invertida. El stub anterior hacía
   `nombre in medicamentos_alto_riesgo`, que exige una coincidencia EXACTA de todo el
   nombre contra la lista. rules.yaml es explícito: "la coincidencia es por inclusión:
   'insulina' detecta 'insulina glargina'" -> tiene que ser al revés,
   `any(palabra in nombre for palabra in medicamentos_alto_riesgo)`.
3. BUG corregido: el stub anterior no restringía el alto riesgo a recetas. El contrato dice
   "alto riesgo farmacológico, solo en recetas". Ahora se chequea tipo_documento antes.
4. NUEVO: se agrega la fuente 4 (valores críticos de laboratorio), que faltaba por completo.
   Como extraer.py todavía no produce datos de laboratorio estructurados (sigue siendo un
   stub, ver TODO en ese archivo), esta fuente busca los valores directamente en el texto
   crudo con una expresión regular por analito, igual que ya se hace con hallazgos_criticos.
   Cuando extraer.py entregue valores estructurados (analito, valor, unidad), esta función
   debería preferir esos datos sobre el regex, que es un mejor esfuerzo mientras tanto.

TODO / pendiente de coordinar con el equipo:
  - Confirmar con Carlos (dueño de extraer.py) cuándo va a existir un campo estructurado
    de resultados de laboratorio en datos_extraidos, para dejar de depender del regex.
  - El operador "texto" (troponina: elevada) usa una detección simple de presencia de
    palabras cercanas en el texto; no distingue "troponina no elevada" de "troponina
    elevada". Falta una regla de negación si aparecen casos así en el golden set.
"""

import re

from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState


def _valor_critico_detectado(texto: str, regla: dict) -> bool:
    """Busca el analito en el texto y compara contra el umbral de rules.yaml.
    El operador 'texto' (ej. troponina: elevada) se detecta por presencia de la
    palabra clave, no por comparación numérica.
    """
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

    # Regla A (ADR-002): las fuentes automáticas (1, 2 y 4) solo aplican a estos tipos.
    aplica_deteccion_automatica = tipo_documento in reglas["deteccion_automatica_urgencia"]["aplica_a"]

    if aplica_deteccion_automatica:
        # Fuente 1: hallazgos críticos
        for hallazgo in reglas["hallazgos_criticos"]:
            if hallazgo.lower() in texto:
                motivos.append(f"hallazgo critico: {hallazgo}")

        # Fuente 2: palabras clave de urgencia
        for palabra in reglas["palabras_urgencia"]:
            if palabra.lower() in texto:
                motivos.append(f"palabra clave: {palabra}")

        # Fuente 4: valores críticos de laboratorio (best-effort por regex, ver TODO arriba)
        for regla_valor in reglas.get("valores_criticos_laboratorio", []):
            if _valor_critico_detectado(texto, regla_valor):
                motivos.append(
                    f"valor critico de laboratorio: {regla_valor['analito']} "
                    f"{regla_valor['operador']} {regla_valor['valor']} {regla_valor.get('unidad', '')}".strip()
                )

    # Fuente 3: juicio del modelo. Es la ÚNICA que aplica a todos los tipos, según la Regla A.
    if state.get("clasificacion", {}).get("nivel_prioridad") == "Urgente":
        motivos.append("prioridad del modelo: Urgente")

    # Alto riesgo farmacológico: solo en recetas (contrato, sección 4 / ADR-002).
    alto_riesgo: list[str] = []
    if tipo_documento == "Receta Medica":
        lista_alto_riesgo = reglas["medicamentos_alto_riesgo"]
        for medicamento in state.get("datos_extraidos", {}).get("medicamentos", []) or []:
            nombre = (medicamento.get("nombre") or "").lower()
            if not nombre:
                continue
            coincide_por_lista = any(clave in nombre for clave in lista_alto_riesgo)
            if medicamento.get("alto_riesgo") or coincide_por_lista:
                alto_riesgo.append(medicamento.get("nombre"))

    urgencia = {
        "detectada": bool(motivos),
        "motivos": motivos,
        "alto_riesgo_farmacologico": alto_riesgo,
    }
    return {"urgencia": urgencia, "trace": step(state, "detectar_urgencia", urgencia)}
