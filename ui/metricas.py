"""Lógica del dashboard de métricas (N3-04), separada de Streamlit para probarla sola.

Lee dos endpoints de la API: `GET /metrics` (operación) y `GET /metrics/evaluacion` (la última corrida
oficial del conjunto de prueba). Arma las tablas, los gráficos y las tarjetas; la página `5_Metricas.py`
solo los acomoda. No importa nada de `agent/`, porque el contenedor de la interfaz solo copia `ui/`.

Cada dato que se muestra lleva su explicación: qué significa, de dónde sale y cómo leerlo. Se ve al
pasar el mouse (o al enfocarlo con el teclado), para que lo entienda cualquier persona del hospital.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import altair as alt
import httpx
import pandas as pd

TIMEOUT = 20

# Un solo color para las barras de un único conjunto (la identidad la da el eje, no el color).
AZUL = "#2a78d6"
# Rampa ordinal del mismo azul, de claro a oscuro, para las tres franjas de confianza.
RAMPA_FRANJAS = ["#86b6ef", "#3987e5", "#1c5cab"]
# El valor al final de cada barra va en tinta de texto, nunca en el color de la serie.
TEXTO = {"light": "#0b0b0b", "dark": "#f0efec"}
TEXTO_NEUTRO = "#7a7974"  # se lee en los dos fondos, si no se sabe cuál es

# Estados de las tarjetas: siempre con ícono y texto, nunca solo color.
ESTADOS = {
    "critico": {"color": "#d43c3c"},
    "alerta": {"color": "#d98a0b"},
    "ok": {"color": "#23945a"},
    "falla": {"color": "#d43c3c"},
    "info": {"color": AZUL},
}

# El único objetivo escrito en el proyecto (docs/api-contract.md, sección 4).
OBJETIVO_RECALL = 1.0

# --------------------------------------------------------------------------- nombres y significados
DESTINOS = {
    "Cola_Emergencia_Medica": "Emergencia",
    "Farmacia_Hospitalaria": "Farmacia",
    "Auditoria_Autorizaciones": "Autorizaciones",
    "Historia_Clinica_Electronica": "Historia clínica",
    "Cola_Revision_Humana": "Revisión humana",
}
SIGNIFICADO_DESTINOS = {
    "Cola_Emergencia_Medica": "Cola de la guardia médica. Entra todo lo urgente, sea del tipo que sea, y se "
                              "avisa al equipo de guardia en el momento.",
    "Farmacia_Hospitalaria": "Recetas para dispensar. Las de medicamentos de alto riesgo llegan marcadas "
                             "para que alguien las revise antes.",
    "Auditoria_Autorizaciones": "Órdenes de procedimiento que necesitan una autorización administrativa.",
    "Historia_Clinica_Electronica": "Informes de imágenes y de laboratorio, epicrisis y certificados que se "
                                    "archivan en la historia del paciente.",
    "Cola_Revision_Humana": "Lo que el agente no decide solo: ilegible, ambiguo, con confianza baja o fuera "
                            "de alcance. Lo resuelve una persona en Auditoría.",
}
TIPOS = {
    "Receta Medica": "Receta médica",
    "Informe de Estudio por Imagenes": "Informe de imágenes",
    "Informe de Laboratorio": "Informe de laboratorio",
    "Orden de Solicitud de Procedimiento": "Orden de procedimiento",
    "Epicrisis": "Epicrisis",
    "Certificado Medico": "Certificado médico",
    "Otro": "Otro (fuera de alcance)",
}
SIGNIFICADO_TIPOS = {
    "Receta Medica": "Indicación de medicamentos con dosis y frecuencia.",
    "Informe de Estudio por Imagenes": "Informe escrito de una radiografía, tomografía, ecografía o resonancia. "
                                       "El agente lee el informe, no la imagen.",
    "Informe de Laboratorio": "Resultados de análisis: sangre, orina y otros.",
    "Orden de Solicitud de Procedimiento": "Pedido de un estudio, una cirugía o un procedimiento.",
    "Epicrisis": "Resumen de una internación al dar el alta.",
    "Certificado Medico": "Constancia de reposo, aptitud o asistencia.",
    "Otro": "No es un documento clínico que MediFlow deba ordenar (por ejemplo, una factura). "
            "Va a revisión humana con el motivo.",
}
FRANJAS = {
    "automatico": "Enruta solo",
    "segunda_opinion": "Segunda opinión",
    "revision": "Revisión humana",
}
# Cómo se agrupan los fallos en el informe de evals/run.py: categoría AMB, urgencia, legibilidad o tipo.
CATEGORIAS = {
    "AMB-1": "AMB-1 · campo obligatorio faltante",
    "AMB-2": "AMB-2 · contradicción interna",
    "AMB-3": "AMB-3 · dosis fuera de rango",
    "AMB-4": "AMB-4 · truncado o poco legible",
    "AMB-5": "AMB-5 · dos documentos en uno",
    "AMB-6": "AMB-6 · fuera de alcance",
    "urgencia": "Urgencias",
    "legibilidad media": "Imagen de legibilidad media",
    "legibilidad severa": "Imagen de legibilidad severa",
    **{tipo: f"{nombre} sin ambigüedad" for tipo, nombre in TIPOS.items() if tipo != "Otro"},
}
SIGNIFICADO_CATEGORIAS = {
    "AMB-1": "Documentos a los que les falta un dato obligatorio, como el nombre del paciente o la matrícula. "
             "El agente debía detectarlo y pedir revisión.",
    "AMB-2": "Documentos que se contradicen, como una edad que no cuadra con la fecha de nacimiento.",
    "AMB-3": "Recetas con una dosis fuera de rango o un medicamento que no se puede identificar.",
    "AMB-4": "Documentos cortados o con partes que no se leen.",
    "AMB-5": "Dos documentos distintos en un mismo archivo.",
    "AMB-6": "Documentos que no le corresponden al agente (facturas, consentimientos, informes en otro "
             "idioma). Debía reconocerlo y decir por qué.",
    "urgencia": "Documentos urgentes. Cualquier fallo aquí es el más grave del panel.",
    "legibilidad media": "Fotos o escaneos con calidad media: el agente debía marcarlos para revisión.",
    "legibilidad severa": "Fotos o escaneos casi ilegibles: el agente debía pedir una nueva captura.",
    **{tipo: f"{nombre}: documentos claros, sin trampas, que igual tuvieron algún error."
       for tipo, nombre in TIPOS.items() if tipo != "Otro"},
}
CAMPOS = {
    "destino": "Destino",
    "auditoria": "Marca de auditoría",
    "urgencia": "Urgencia",
    "tipo": "Tipo de documento",
    "categoria_amb": "Categoría AMB",
    "motivo_fuera_de_alcance": "Motivo fuera de alcance",
    "error de ejecución": "Error de ejecución",
}


def significado_modelo(nombre: str) -> str:
    nombre = str(nombre)
    if nombre == "stub":
        return "Sin modelo de lenguaje: el agente decidió solo con las reglas (modo de desarrollo)."
    if nombre == "sin modelo":
        return "El documento no llegó a consultarse a un modelo, por ejemplo porque la imagen era ilegible."
    return ("Modelo de lenguaje que leyó y clasificó el documento. Si el principal falla, el adaptador pasa "
            "al de respaldo sin perder el documento.")


# --------------------------------------------------------------------------- de dónde sale cada dato
FUENTE_OPERACION = ("Resultados que guarda la API cada vez que procesa un documento "
                    "(GET /metrics, tabla triage_results).")
FUENTE_COLA = "Documentos pendientes en la página Auditoría (GET /metrics, cola de revisión humana)."
FUENTE_REGLAS = "Umbrales de rules.yaml; se editan en la página Reglas."


def fuente_evaluacion(corrida: str) -> str:
    return (f"Corrida {corrida} de evals/run.py (evals/resultados/), comparada con las respuestas correctas "
            "que el equipo etiquetó a mano (evals/golden/plan_golden.csv).")


GLOSARIO = [
    ("Documento", "Lo que llega al hospital: una receta, un informe, una orden. Puede venir como PDF, foto, "
                  "texto o JSON."),
    ("Urgencia", "Un documento con riesgo vital o un hallazgo crítico. Va a Emergencia y la guardia recibe el "
                 "aviso en el momento."),
    ("Revisión humana", "Cuando el agente no está seguro, no adivina: el documento pasa a una persona en la "
                        "página Auditoría, con el motivo."),
    ("Confianza (score)", "Un número de 0 a 1 que resume qué tan seguro está el agente: 25 % legibilidad, "
                          "30 % validación de datos, 25 % el modelo y 20 % acuerdo entre pasos."),
    ("Ambigüedad (AMB-1 a AMB-6)", "Las seis razones por las que un documento necesita una persona: falta un "
                                   "dato, se contradice, dosis fuera de rango, ilegible, dos en uno o fuera "
                                   "de alcance."),
    ("Conjunto de prueba", "45 documentos que el equipo etiquetó a mano con la respuesta correcta. Cada uno "
                           "se prueba en varias versiones (texto, PDF, foto, escaneo): son las variantes."),
    ("Recall de urgencias", "De todas las urgencias del conjunto de prueba, cuántas detectó el agente. Es la "
                            "métrica más importante: una urgencia perdida puede costar un paciente."),
]


class ErrorApi(Exception):
    """La API no respondió o respondió algo que no se puede mostrar."""


# --------------------------------------------------------------------------- API
def _pedir(api_url: str, ruta: str, cliente: httpx.Client | None = None, params: dict | None = None):
    url = api_url.rstrip("/") + ruta
    try:
        if cliente is not None:
            return cliente.get(url, params=params, timeout=TIMEOUT)
        return httpx.get(url, params=params, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise ErrorApi(f"No se pudo conectar con la API en {api_url} ({type(exc).__name__}).") from exc


def obtener_operacion(api_url: str, cliente: httpx.Client | None = None) -> dict:
    respuesta = _pedir(api_url, "/metrics", cliente)
    if respuesta.status_code != 200:
        raise ErrorApi(f"La API no devolvió las métricas ({respuesta.status_code}).")
    datos = respuesta.json()
    if not isinstance(datos, dict):
        raise ErrorApi("La API devolvió métricas con un formato inesperado.")
    return datos


def obtener_evaluacion(api_url: str, corrida: str | None = None, cliente: httpx.Client | None = None) -> dict | None:
    """La corrida pedida o la más reciente. None si todavía no hay ninguna publicada."""
    params = {"corrida": corrida} if corrida else None
    respuesta = _pedir(api_url, "/metrics/evaluacion", cliente, params)
    if respuesta.status_code == 404:
        return None
    if respuesta.status_code != 200:
        raise ErrorApi(f"La API no devolvió la evaluación ({respuesta.status_code}).")
    datos = respuesta.json()
    return datos if isinstance(datos, dict) else None


# --------------------------------------------------------------------------- formato
def _es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def porcentaje(valor: Any) -> str:
    """0.9048 -> «90 %». Sin dato -> «—»."""
    return f"{round(valor * 100)} %" if _es_numero(valor) else "—"


def decimal(valor: Any) -> str:
    """0.8123 -> «0,81», con coma decimal."""
    return f"{valor:.2f}".replace(".", ",") if _es_numero(valor) else "—"


def fecha_corta(texto: Any) -> str:
    """ISO -> «13/10 14:05». Si no se puede leer, el texto tal cual."""
    try:
        return datetime.fromisoformat(str(texto)).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return str(texto or "—")


def nombre_corrida(nombre: str) -> str:
    """«2026-10-13_deepseek» -> «13/10/2026 · deepseek»."""
    fecha, _, resto = str(nombre).partition("_")
    try:
        legible = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(nombre)
    return f"{legible} · {resto.replace('_', ' ')}" if resto else legible


def segundos(texto: Any) -> str:
    """«4.3 s» (como lo escribe run.py) -> «4,3 s»."""
    return str(texto).replace(".", ",") if texto not in (None, "") else "—"


def de_cada_10(valor: Any) -> str:
    """0.7 -> «Acierta 7 de cada 10». Para quien no lee porcentajes."""
    if not _es_numero(valor):
        return "Sin dato"
    if valor >= 1:
        return "Acierta en todos los casos"
    if valor <= 0:
        return "No acierta en ninguno"
    return f"Acierta {max(1, min(9, round(valor * 10)))} de cada 10"


def hora_local(zona: str, ahora: datetime | None = None) -> str:
    """La hora del hospital, para decir cuándo se consultaron los datos."""
    try:
        tz = ZoneInfo(zona)
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone(timedelta(hours=-3))
    return (ahora or datetime.now(timezone.utc)).astimezone(tz).strftime("%d/%m/%Y %H:%M")


def resumen_operacion(op: dict) -> str:
    """Una frase para quien no va a mirar los gráficos."""
    hoy, total = int(op.get("documentos_hoy") or 0), int(op.get("documentos_total") or 0)
    if total == 0:
        return "Todavía no se procesó ningún documento."
    urg, cola = int(op.get("urgencias_hoy") or 0), int(op.get("en_revision") or 0)
    partes = [f"Hoy llegaron <b>{hoy}</b> documento{'s' if hoy != 1 else ''}."]
    if urg:
        partes.append(f"<b>{urg}</b> {'eran urgencias' if urg != 1 else 'era una urgencia'} y la guardia "
                      "recibió el aviso en el momento.")
    else:
        partes.append("Ninguno fue urgente.")
    if cola:
        partes.append(f"<b>{cola}</b> esperan que una persona los revise en Auditoría.")
    else:
        partes.append("No hay nada esperando revisión.")
    return " ".join(partes)


def resumen_evaluacion_texto(ev: dict) -> str:
    recall = metrica(ev, "recall_urgencias")
    destino = metrica(ev, "accuracy_destino")
    partes = ["Antes de trabajar con documentos reales, MediFlow se prueba con <b>45 documentos</b> que el "
              f"equipo etiquetó a mano, en <b>{ev.get('variantes', 0)} versiones</b> (texto, PDF, foto y "
              "escaneo)."]
    if recall.get("total"):
        partes.append(f"Detectó <b>{recall.get('aciertos')} de {recall.get('total')}</b> urgencias")
        partes[-1] += (f" y mandó a la cola correcta {destino.get('aciertos')} de {destino.get('total')} "
                       "documentos legibles." if destino.get("total") else ".")
    return " ".join(partes)


def _lista(valor: Any) -> list[dict]:
    return [v for v in valor if isinstance(v, dict)] if isinstance(valor, list) else []


# --------------------------------------------------------------------------- diseño
# Paleta de la interfaz por tema. Los colores de estado van siempre con ícono y texto, nunca solos.
PALETAS = {
    "light": {"fondo": "#f4f6f9", "panel": "#ffffff", "borde": "#e3e8ef", "texto": "#101828", "suave": "#526073",
              "tenue": "#8794a6", "acento": "#2a78d6", "acento_suave": "#eaf2fc", "pista": "#e9edf3",
              "tip_fondo": "#101828", "tip_texto": "#f4f6f9", "tip_titulo": "#9cc7f5", "sombra": "rgba(16,24,40,.06)"},
    "dark": {"fondo": "#0b0f14", "panel": "#131a22", "borde": "#243040", "texto": "#eef2f6", "suave": "#a7b3c2",
             "tenue": "#7b8899", "acento": "#4c93e6", "acento_suave": "rgba(76,147,230,.14)", "pista": "#223040",
             "tip_fondo": "#eef2f6", "tip_texto": "#101828", "tip_titulo": "#1c5cab", "sombra": "rgba(0,0,0,.35)"},
}

_SVG = '<svg viewBox="0 0 16 16" width="{t}" height="{t}" aria-hidden="true" focusable="false">{c}</svg>'
ICONOS = {
    "info": _SVG.format(t=14, c='<circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.3"/>'
                              '<path d="M8 7.2v3.6M8 5.1v.1" stroke="currentColor" stroke-width="1.5" '
                              'stroke-linecap="round"/>'),
    "critico": _SVG.format(t=12, c='<path d="M8 1.8 15 14H1z" fill="currentColor"/><path d="M8 6.2v3.6M8 11.6v.1" '
                                 'stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>'),
    "alerta": _SVG.format(t=12, c='<circle cx="8" cy="8" r="6.5" fill="currentColor"/><path d="M8 4.6V8l2.2 1.6" '
                                'stroke="#fff" stroke-width="1.5" fill="none" stroke-linecap="round"/>'),
    "ok": _SVG.format(t=12, c='<circle cx="8" cy="8" r="6.5" fill="currentColor"/><path d="m5.2 8.2 1.9 1.9 3.7-4" '
                            'stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round" '
                            'stroke-linejoin="round"/>'),
    "falla": _SVG.format(t=12, c='<path d="M8 1.8 15 14H1z" fill="currentColor"/><path d="M8 6.2v3.6M8 11.6v.1" '
                               'stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>'),
}


def paleta(tema: str | None) -> dict:
    return PALETAS.get(str(tema), PALETAS["light"])


def estilos(tema: str | None) -> str:
    """La hoja de estilos de la página, con los colores del tema activo."""
    p = paleta(tema)
    variables = ";".join(f"--mf-{k.replace('_', '-')}:{v}" for k, v in p.items())
    estados = ";".join(f"--mf-{k}:{v['color']}" for k, v in ESTADOS.items())
    return f"""<style>
:root{{{variables};{estados}}}
.stApp{{background:var(--mf-fondo)}}
[data-testid="stHeader"]{{background:transparent}}
[data-testid="stToolbar"],[data-testid="stAppDeployButton"]{{display:none}}
[data-testid="stMainBlockContainer"]{{padding-top:2.2rem;max-width:1320px}}
.mf-top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:6px}}
.mf-eyebrow{{font-size:.72rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--mf-acento)}}
.mf-h1{{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;color:var(--mf-texto);margin:2px 0 4px;line-height:1.2}}
.mf-sub{{color:var(--mf-suave);font-size:.95rem;margin:0;max-width:720px;line-height:1.5}}
.mf-estado-api{{display:inline-flex;align-items:center;gap:8px;font-size:.82rem;color:var(--mf-suave);
  background:var(--mf-panel);border:1px solid var(--mf-borde);border-radius:999px;padding:6px 12px}}
.mf-punto{{width:8px;height:8px;border-radius:50%;background:var(--mf-ok);box-shadow:0 0 0 3px rgba(35,148,90,.18)}}
.mf-punto.mf-caida{{background:var(--mf-critico);box-shadow:0 0 0 3px rgba(212,60,60,.18)}}
.stTabs [role="tablist"]{{gap:28px;border-bottom:1px solid var(--mf-borde)}}
.stTabs [role="tab"]{{padding:10px 2px;color:var(--mf-suave)!important}}
.stTabs [role="tab"] p{{font-weight:500;color:inherit!important}}
.stTabs [role="tab"][aria-selected="true"]{{color:var(--mf-texto)!important}}
.stTabs [role="tab"][aria-selected="true"] p{{font-weight:600}}
.stTabs .react-aria-SelectionIndicator,.stTabs [data-baseweb="tab-highlight"]{{
  background-color:var(--mf-acento)!important}}
.stTabs [data-baseweb="tab-border"]{{display:none}}
[data-testid="stBaseButton-primary"]{{background:var(--mf-acento)!important;border-color:var(--mf-acento)!important;
  color:#fff!important;border-radius:10px}}
[data-testid="stBaseButton-primary"]:hover{{filter:brightness(1.08)}}
[data-testid="stExpander"]{{margin:14px 0 6px}}
[class*="st-key-mf_panel"]{{background:var(--mf-panel);border:1px solid var(--mf-borde)!important;
  border-radius:14px!important;box-shadow:0 1px 2px var(--mf-sombra);padding:20px 22px 14px!important}}
[data-testid="stExpander"] details{{background:var(--mf-panel);border:1px solid var(--mf-borde);border-radius:12px}}
.mf-resumen{{display:flex;gap:14px;align-items:flex-start;background:var(--mf-panel);border:1px solid var(--mf-borde);
  border-radius:14px;padding:16px 20px;margin:18px 0 16px;box-shadow:0 1px 2px var(--mf-sombra);
  color:var(--mf-texto);font-size:1rem;line-height:1.6}}
.mf-resumen-marca{{flex:none;width:4px;align-self:stretch;border-radius:4px;background:var(--mf-acento)}}
.mf-resumen-etiqueta{{font-size:.7rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:var(--mf-tenue);margin-bottom:2px}}
.mf-card{{position:relative;background:var(--mf-panel);border:1px solid var(--mf-borde);border-radius:14px;
  padding:16px 18px 14px;box-shadow:0 1px 2px var(--mf-sombra);min-height:156px;margin-bottom:14px;
  cursor:help;outline:none;transition:border-color .15s,box-shadow .15s}}
.mf-card:hover,.mf-card:focus{{border-color:var(--mf-acento);box-shadow:0 0 0 3px var(--mf-acento-suave)}}
.mf-card.mf-grande{{min-height:208px}}
.mf-etiqueta{{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:.78rem;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--mf-suave)}}
.mf-etiqueta svg{{color:var(--mf-tenue);flex:none}}
.mf-valor{{font-size:2rem;font-weight:650;letter-spacing:-.02em;color:var(--mf-texto);margin:10px 0 2px;
  font-variant-numeric:tabular-nums;line-height:1.1}}
.mf-grande .mf-valor{{font-size:2.9rem}}
.mf-detalle{{font-size:.84rem;color:var(--mf-suave);line-height:1.45}}
.mf-progreso{{height:6px;border-radius:6px;background:var(--mf-pista);margin:12px 0 2px;position:relative;
  overflow:hidden}}
.mf-progreso span{{position:absolute;inset:0 auto 0 0;border-radius:6px;background:var(--mf-acento)}}
.mf-chip{{display:inline-flex;align-items:center;gap:6px;margin-top:10px;font-size:.76rem;font-weight:600;
  padding:3px 9px;border-radius:999px;color:var(--mf-c);background:color-mix(in srgb,var(--mf-c) 12%,transparent)}}
.mf-chip-texto{{color:var(--mf-texto)}}
.mf-tip{{display:none;position:absolute;z-index:1000;top:calc(100% + 8px);left:0;width:330px;max-width:82vw;
  background:var(--mf-tip-fondo);color:var(--mf-tip-texto);border-radius:12px;padding:14px 16px;font-size:.84rem;
  line-height:1.5;box-shadow:0 12px 32px rgba(0,0,0,.28);cursor:default;text-transform:none;letter-spacing:0;
  font-weight:400}}
.mf-tip.mf-derecha{{left:auto;right:0}}
.mf-card:hover .mf-tip,.mf-card:focus .mf-tip,.mf-ayuda:hover .mf-tip,.mf-ayuda:focus .mf-tip{{display:block}}
.mf-tip b{{color:var(--mf-tip-titulo);display:block;margin-top:8px;font-size:.7rem;letter-spacing:.08em;
  text-transform:uppercase;font-weight:600}}
.mf-tip b:first-child{{margin-top:0}}
.mf-seccion{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}}
.mf-seccion-titulo{{font-size:1.02rem;font-weight:600;color:var(--mf-texto);margin:0}}
.mf-seccion-sub{{font-size:.84rem;color:var(--mf-suave);margin:2px 0 0}}
.mf-ayuda{{position:relative;color:var(--mf-tenue);cursor:help;outline:none;padding:2px}}
.mf-ayuda .mf-tip{{left:auto;right:0}}
.mf-pie{{font-size:.8rem;color:var(--mf-tenue);margin-top:4px;line-height:1.5}}
.mf-vacio{{background:var(--mf-panel);border:1px dashed var(--mf-borde);border-radius:14px;padding:28px;
  text-align:center;color:var(--mf-suave)}}
.mf-vacio strong{{display:block;color:var(--mf-texto);font-size:1.02rem;margin-bottom:4px}}
@media (max-width:640px){{.mf-h1{{font-size:1.5rem}}.mf-grande .mf-valor{{font-size:2.3rem}}}}
</style>"""


def _explicacion(que_es: str, fuente: str, como_leer: str = "") -> str:
    e = html.escape
    texto = f"<b>Qué es</b>{e(que_es)}"
    if como_leer:
        texto += f"<b>Cómo leerlo</b>{e(como_leer)}"
    return texto + f"<b>De dónde sale</b>{e(fuente)}"


def encabezado_html(titulo: str, subtitulo: str, api_ok: bool, detalle_api: str) -> str:
    e = html.escape
    punto = "mf-punto" if api_ok else "mf-punto mf-caida"
    return (f'<div class="mf-top"><div><div class="mf-eyebrow">MediFlow · Triaje documental clínico</div>'
            f'<div class="mf-h1">{e(titulo)}</div><div class="mf-sub">{e(subtitulo)}</div></div>'
            f'<div class="mf-estado-api" role="status"><span class="{punto}"></span>{e(detalle_api)}</div></div>')


def resumen_html(etiqueta: str, texto: str) -> str:
    """`texto` ya viene armado por resumen_operacion / resumen_evaluacion_texto (solo <b> con números)."""
    return (f'<div class="mf-resumen"><span class="mf-resumen-marca"></span><div>'
            f'<div class="mf-resumen-etiqueta">{html.escape(etiqueta)}</div>{texto}</div></div>')


def seccion_html(titulo: str, subtitulo: str, *, que_es: str, fuente: str, como_leer: str = "") -> str:
    e = html.escape
    return (f'<div class="mf-seccion"><div><div class="mf-seccion-titulo">{e(titulo)}</div>'
            f'<div class="mf-seccion-sub">{e(subtitulo)}</div></div>'
            f'<span class="mf-ayuda" tabindex="0" aria-label="Qué significa: {e(titulo)}">{ICONOS["info"]}'
            f'<span class="mf-tip" role="tooltip">{_explicacion(que_es, fuente, como_leer)}</span></span></div>')


def vacio_html(titulo: str, texto: str) -> str:
    return f'<div class="mf-vacio"><strong>{html.escape(titulo)}</strong>{html.escape(texto)}</div>'


def tarjeta_html(titulo: str, valor: str, detalle: str = "", *, que_es: str, fuente: str,
                 como_leer: str = "", estado: str | None = None, texto_estado: str = "",
                 derecha: bool = False, progreso: float | None = None, grande: bool = False) -> str:
    """Tarjeta de un número. Al pasar el mouse (o con Tab) explica qué es, de dónde sale y cómo leerlo."""
    e = html.escape
    chip = ""
    if texto_estado:
        color = ESTADOS.get(estado or "info", ESTADOS["info"])["color"]
        chip = (f'<div class="mf-chip" style="--mf-c:{color}">{ICONOS.get(estado or "", "")}'
                f'<span class="mf-chip-texto">{e(texto_estado)}</span></div>')
    barra = ""
    if _es_numero(progreso):
        ancho = max(0.0, min(1.0, float(progreso))) * 100
        barra = f'<div class="mf-progreso" aria-hidden="true"><span style="width:{ancho:.1f}%"></span></div>'
    clases = "mf-card mf-grande" if grande else "mf-card"
    return (
        f'<div class="{clases}" tabindex="0" role="group" aria-label="{e(titulo)}: {e(valor)}">'
        f'<div class="mf-etiqueta"><span>{e(titulo)}</span>{ICONOS["info"]}</div>'
        f'<div class="mf-valor">{e(valor)}</div>{barra}'
        f'<div class="mf-detalle">{e(detalle)}</div>{chip}'
        f'<div class="mf-tip{" mf-derecha" if derecha else ""}" role="tooltip">'
        f'{_explicacion(que_es, fuente, como_leer)}</div>'
        "</div>"
    )


# --------------------------------------------------------------------------- tablas
def tabla_conteo(filas: Any, nombres: dict[str, str], significados: dict[str, str] | None = None,
                 fuente: str = "", significado=None) -> pd.DataFrame:
    """[{"nombre", "cantidad"}] -> DataFrame con etiqueta legible, parte del total, qué significa y de dónde
    sale, en el orden recibido. `significado` es una función para lo que no está en el diccionario."""
    datos = []
    for f in _lista(filas):
        clave = str(f.get("nombre"))
        texto = (significados or {}).get(clave) or (significado(clave) if significado else "")
        casos = f.get("casos")
        datos.append({"etiqueta": nombres.get(clave, clave), "cantidad": int(f.get("cantidad") or 0),
                      "significado": texto, "fuente": fuente,
                      "casos": ", ".join(map(str, casos[:12])) + (" …" if len(casos) > 12 else "")
                      if isinstance(casos, list) else ""})
    df = pd.DataFrame(datos, columns=["etiqueta", "cantidad", "significado", "fuente", "casos"])
    total = df["cantidad"].sum()
    df["parte"] = df["cantidad"] / total if total else 0.0
    return df


def umbrales(filas: Any) -> tuple[str, str]:
    """Los dos cortes del score que vienen con las franjas: («0,85», «0,60»)."""
    desde = {str(f.get("nombre")): f.get("desde") for f in _lista(filas)}
    return decimal(desde.get("automatico", 0.85)), decimal(desde.get("segunda_opinion", 0.60))


def tabla_franjas(filas: Any) -> pd.DataFrame:
    alto, medio = umbrales(filas)
    rangos = {"automatico": f"≥ {alto}", "segunda_opinion": f"{medio} a {alto}", "revision": f"< {medio}"}
    significados = {
        "automatico": "El agente está seguro y enruta el documento solo.",
        "segunda_opinion": "Confianza media: se consulta otra vez al modelo o se marca para auditoría.",
        "revision": "Confianza baja: el documento va a una persona.",
    }
    datos = []
    for f in _lista(filas):
        nombre = str(f.get("nombre"))
        datos.append({"etiqueta": FRANJAS.get(nombre, nombre), "rango": rangos.get(nombre, "—"),
                      "cantidad": int(f.get("cantidad") or 0), "significado": significados.get(nombre, ""),
                      "fuente": FUENTE_OPERACION + " Umbrales: " + FUENTE_REGLAS})
    total = sum(d["cantidad"] for d in datos)
    for d in datos:
        d["parte"] = d["cantidad"] / total if total else 0.0
    return pd.DataFrame(datos, columns=["etiqueta", "rango", "cantidad", "parte", "significado", "fuente"])


def tabla_alertas(filas: Any) -> pd.DataFrame:
    datos = [{
        "Hora": fecha_corta(f.get("fecha")),
        "Documento": str(f.get("documento_id") or ""),
        "Tipo": TIPOS.get(str(f.get("tipo")), str(f.get("tipo") or "—")),
        "Destino": DESTINOS.get(str(f.get("destino")), str(f.get("destino") or "—")),
        "Aviso": str(f.get("canal") or "—").replace("_", " "),
    } for f in _lista(filas)]
    return pd.DataFrame(datos, columns=["Hora", "Documento", "Tipo", "Destino", "Aviso"])


AYUDA_ALERTAS = {
    "Hora": "Cuándo se procesó el documento, en la hora del hospital.",
    "Documento": "Identificador del documento. No es un dato del paciente.",
    "Tipo": "Qué clase de documento era, según el agente.",
    "Destino": "La cola a la que fue. Las urgencias siempre van a Emergencia.",
    "Aviso": "Por dónde se avisó a la guardia médica.",
}


def tabla_por_tipo(filas: Any, corrida: str = "") -> pd.DataFrame:
    datos = []
    for f in _lista(filas):
        total = int(f.get("variantes") or 0)
        ok = int(f.get("destino_ok") or 0)
        tipo = str(f.get("tipo"))
        datos.append({"etiqueta": TIPOS.get(tipo, tipo), "acierto": ok / total if total else 0.0,
                      "detalle": f"{ok}/{total}", "significado": SIGNIFICADO_TIPOS.get(tipo, ""),
                      "lectura": f"{ok} de {total} versiones legibles fueron a la cola correcta.",
                      "fuente": fuente_evaluacion(corrida)})
    return pd.DataFrame(datos, columns=["etiqueta", "acierto", "detalle", "significado", "lectura", "fuente"])


def tabla_fallos(filas: Any) -> pd.DataFrame:
    datos = [{
        "Caso": str(f.get("id") or ""),
        "Archivo": str(f.get("archivo") or ""),
        "Categoría": CATEGORIAS.get(str(f.get("categoria")), str(f.get("categoria") or "")),
        "Qué falló": ", ".join(CAMPOS.get(c, c) for c in f.get("campos") or []),
        "Destino esperado": DESTINOS.get(str(f.get("esperado_destino")), str(f.get("esperado_destino") or "—")),
        "Destino obtenido": DESTINOS.get(str(f.get("obtenido_destino")), str(f.get("obtenido_destino") or "—")),
    } for f in _lista(filas)]
    return pd.DataFrame(datos, columns=["Caso", "Archivo", "Categoría", "Qué falló", "Destino esperado",
                                        "Destino obtenido"])


AYUDA_FALLOS = {
    "Caso": "Documento del conjunto de prueba (GS = caso clínico, FA = fuera de alcance o intento de engaño).",
    "Archivo": "La versión que se probó: texto, PDF, foto o escaneo.",
    "Categoría": "El grupo del fallo, como en el informe de evals/run.py.",
    "Qué falló": "Los campos en los que la respuesta del agente no coincidió con la etiqueta del equipo.",
    "Destino esperado": "La cola correcta, según la etiqueta del equipo.",
    "Destino obtenido": "La cola a la que lo mandó el agente.",
}


def metrica(evaluacion: dict, clave: str) -> dict:
    for m in _lista(evaluacion.get("metricas")):
        if m.get("clave") == clave:
            return m
    return {}


# --------------------------------------------------------------------------- gráficos
ALTO_FILA = 34  # píxeles por barra


def relleno(filas: int, otras: int) -> int:
    """Píxeles que le faltan a un gráfico de `filas` barras para medir lo mismo que el de al lado."""
    return max(0, max(60, ALTO_FILA * otras) - max(60, ALTO_FILA * filas))


def color_texto(tema: str | None) -> str:
    return TEXTO.get(str(tema), TEXTO_NEUTRO)


def _terminar(grafico, tema: str | None):
    """Fondo transparente para que el gráfico se apoye en su panel; ejes y grilla en tinta suave."""
    p = paleta(tema)
    color_eje = p["suave"] if tema in PALETAS else TEXTO_NEUTRO
    return (grafico.properties(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=color_eje, gridColor=p["borde"] if tema in PALETAS else "#8080803a",
                            labelFontSize=12, labelPadding=10))


def _tooltip(df: pd.DataFrame, categoria: str, valor_col: str, titulo_valor: str, formato: str) -> list:
    """Lo que se ve al pasar el mouse por una barra: el dato, su parte del total, qué significa y de dónde sale."""
    campos = [alt.Tooltip("etiqueta:N", title=categoria),
              alt.Tooltip(f"{valor_col}:Q", title=titulo_valor, format=formato)]
    extras = [("detalle", "Aciertos", "N"), ("rango", "Score", "N"), ("parte", "Parte del total", "Q"),
              ("lectura", "Cómo leerlo", "N"), ("casos", "Casos", "N"),
              ("significado", "Qué significa", "N"), ("fuente", "De dónde sale", "N")]
    for col, titulo, tipo in extras:
        if col in df.columns and col != valor_col and df[col].astype(str).str.len().gt(0).any():
            campos.append(alt.Tooltip(f"{col}:{tipo}", title=titulo, **({"format": ".0%"} if col == "parte" else {})))
    return campos


def barras(df: pd.DataFrame, titulo_valor: str, formato: str = "d", dominio: tuple | None = None,
           etiqueta_col: str = "cantidad", texto_col: str | None = None, tema: str | None = None,
           categoria: str = " ") -> alt.Chart:
    """Barras horizontales de un solo conjunto: el orden del DataFrame se respeta, el valor va al final
    de la barra y la grilla queda al fondo."""
    alto = max(60, ALTO_FILA * len(df))
    orden = list(df["etiqueta"])
    escala = alt.Scale(domain=list(dominio)) if dominio else alt.Undefined
    base = alt.Chart(df).encode(
        y=alt.Y("etiqueta:N", sort=orden, title=None, axis=alt.Axis(labelLimit=220, ticks=False, domain=False)),
        x=alt.X(f"{etiqueta_col}:Q", title=None, scale=escala,
                axis=alt.Axis(format=formato, grid=True, tickCount=4, domain=False, ticks=False, labels=False)),
        tooltip=_tooltip(df, categoria, etiqueta_col, titulo_valor, formato),
    )
    marcas = base.mark_bar(color=AZUL, cornerRadiusEnd=4, height=16)
    texto = base.mark_text(align="left", dx=6, fontSize=12, color=color_texto(tema)).encode(
        text=alt.Text(f"{texto_col or etiqueta_col}:{'N' if texto_col else 'Q'}",
                      **({} if texto_col else {"format": formato}))
    )
    return _terminar((marcas + texto).properties(height=alto), tema)


def barras_franjas(df: pd.DataFrame, tema: str | None = None) -> alt.Chart:
    """Las tres franjas del score, de la más confiable a la que va a revisión, en la rampa de un azul."""
    alto = max(60, ALTO_FILA * len(df))
    orden = list(df["etiqueta"])
    base = alt.Chart(df).encode(
        y=alt.Y("etiqueta:N", sort=orden, title=None, axis=alt.Axis(labelLimit=220, ticks=False, domain=False)),
        x=alt.X("cantidad:Q", title=None, axis=alt.Axis(grid=True, tickCount=4, domain=False, ticks=False,
                                                         labels=False)),
        tooltip=_tooltip(df, "Franja", "cantidad", "Documentos", "d"),
    )
    marcas = base.mark_bar(cornerRadiusEnd=4, height=16).encode(
        color=alt.Color("etiqueta:N", scale=alt.Scale(domain=orden, range=RAMPA_FRANJAS[:len(orden)]),
                        legend=None)
    )
    texto = base.mark_text(align="left", dx=6, fontSize=12, color=color_texto(tema)).encode(
        text=alt.Text("cantidad:Q"))
    return _terminar((marcas + texto).properties(height=alto), tema)
