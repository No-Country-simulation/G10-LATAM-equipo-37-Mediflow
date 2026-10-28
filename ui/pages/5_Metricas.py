"""Panel de MediFlow (N3-04): cómo está la operación hoy y qué tan bien decide el agente.

Pensado para cualquier persona del hospital, técnica o no: cada número dice qué es, de dónde sale y cómo
leerlo al pasar el mouse por encima (o al enfocarlo con el teclado); cada barra explica su categoría; cada
columna de tabla tiene ayuda.

Dos pestañas, dos fuentes:
- Operación de hoy: `GET /metrics`, con los documentos procesados que guarda la API (N1-02) y la cola
  del auditor.
- Calidad del agente: `GET /metrics/evaluacion`, la corrida oficial del conjunto de prueba
  (evals/resultados/), la misma que publica el README.

Por privacidad no muestra datos del paciente: solo identificadores, tipos, destinos, scores y horas.
"""
import os
import sys
from pathlib import Path

import streamlit as st

UI = Path(__file__).resolve().parents[1]
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))  # para importar ui/metricas.py también si la página se abre sola

import metricas as met  # noqa: E402

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Panel · MediFlow", page_icon="🏥", layout="wide")


def a_lo_ancho(funcion, *args, **kwargs):
    """`width="stretch"` en Streamlit nuevo; `use_container_width` en el piso del proyecto (1.39)."""
    try:
        return funcion(*args, width="stretch", **kwargs)
    except Exception:  # noqa: BLE001 - versiones que no aceptan width="stretch"
        return funcion(*args, use_container_width=True, **kwargs)


def tema_actual() -> str | None:
    """«light» o «dark» si esta versión de Streamlit lo informa (st.context.theme, 1.46 en adelante)."""
    try:
        return st.context.theme.type
    except Exception:  # noqa: BLE001 - versiones anteriores no lo exponen
        return None


TEMA = tema_actual()
st.markdown(met.estilos(TEMA), unsafe_allow_html=True)


def html(texto: str) -> None:
    st.markdown(texto, unsafe_allow_html=True)


def tarjeta(*args, **kwargs) -> None:
    html(met.tarjeta_html(*args, **kwargs))


def panel(nombre: str):
    """Un panel blanco con borde: el estilo lo da la clase st-key-mf_panel_* (Streamlit 1.42 en adelante)."""
    try:
        return st.container(border=True, key=f"mf_panel_{nombre}")
    except TypeError:  # versiones sin `key` en los contenedores: queda el borde de Streamlit
        return st.container(border=True)


def grafico(chart, filas: int = 0, vecino: int = 0) -> None:
    """El gráfico y, si el de al lado tiene más barras, el espacio que falta para que los paneles midan igual."""
    a_lo_ancho(st.altair_chart, chart)
    if met.relleno(filas, vecino):
        html(f'<div style="height:{met.relleno(filas, vecino)}px" aria-hidden="true"></div>')


def tabla(df, ayudas: dict[str, str]) -> None:
    configuracion = {col: st.column_config.TextColumn(col, help=ayuda) for col, ayuda in ayudas.items()}
    a_lo_ancho(st.dataframe, df, hide_index=True, column_config=configuracion)


def pie(texto: str) -> None:
    html(f'<div class="mf-pie">{texto}</div>')


# --------------------------------------------------------------------------- datos
with st.sidebar:
    if a_lo_ancho(st.button, "Actualizar datos", type="primary"):
        st.rerun()
    st.caption(f"API: `{API_URL}`")

error_api = ""
try:
    op = met.obtener_operacion(API_URL)
except met.ErrorApi as exc:
    op, error_api = None, str(exc)
try:
    ev = met.obtener_evaluacion(API_URL)
except met.ErrorApi as exc:
    ev, error_api = None, error_api or str(exc)

zona = str((op or {}).get("zona_horaria") or "America/Argentina/Buenos_Aires")
consulta = met.hora_local(zona)
estado_api = f"API en línea · datos de las {consulta[-5:]}" if not error_api else "Sin conexión con la API"

# --------------------------------------------------------------------------- encabezado
html(met.encabezado_html(
    "Panel de operación",
    "Qué pasa hoy con los documentos del hospital y qué tan bien decide el agente. Pasa el mouse sobre "
    "cualquier número, barra o columna para ver qué significa y de dónde sale.",
    api_ok=not error_api, detalle_api=estado_api))

with st.expander("Cómo leer este panel"):
    columnas = st.columns(2, gap="large")
    for i, (termino, explicacion) in enumerate(met.GLOSARIO):
        with columnas[i % 2]:
            st.markdown(f"**{termino}**  \n{explicacion}")
    st.caption("Privacidad: el panel no muestra datos de pacientes, solo identificadores de documento, tipos, "
               "destinos, scores y horas.")

pestana_operacion, pestana_evaluacion = st.tabs(["Operación de hoy", "Calidad del agente"])

# --------------------------------------------------------------------------- operación
with pestana_operacion:
    if op is None:
        html(met.vacio_html("No se pudo leer la operación",
                            f"{error_api} Revisa que la API esté encendida y toca «Actualizar datos»."))
    else:
        total = int(op.get("documentos_total") or 0)
        urg_hoy = int(op.get("urgencias_hoy") or 0)
        cola = int(op.get("en_revision") or 0)
        alto, medio = met.umbrales(op.get("franjas_confianza"))
        html(met.resumen_html("Resumen de hoy", met.resumen_operacion(op)))

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            tarjeta("Documentos hoy", str(op.get("documentos_hoy", 0)), f"{total} desde el inicio",
                    que_es="Documentos clínicos que MediFlow leyó, clasificó y mandó a una cola hoy.",
                    como_leer="«Hoy» se cuenta en la hora del hospital, no en la del servidor.",
                    fuente=met.FUENTE_OPERACION)
        with c2:
            tarjeta("Urgencias hoy", str(urg_hoy), f"{op.get('urgencias_total', 0)} desde el inicio",
                    que_es="Documentos con riesgo vital o un hallazgo crítico. Fueron a Emergencia y la "
                           "guardia recibió el aviso en el momento.",
                    como_leer="Cada urgencia aparece abajo, en «Últimas urgencias avisadas».",
                    fuente=met.FUENTE_OPERACION,
                    estado="critico" if urg_hoy else "ok",
                    texto_estado="Guardia avisada" if urg_hoy else "Sin urgencias")
        with c3:
            tarjeta("Esperan revisión", str(cola), "en la cola del auditor",
                    que_es="Documentos que el agente no decidió solo y esperan a una persona en Auditoría.",
                    como_leer="Si este número crece, hace falta más gente revisando. Incluye pendientes de "
                              "días anteriores.",
                    fuente=met.FUENTE_COLA,
                    estado="alerta" if cola else "ok",
                    texto_estado="Pendientes" if cola else "Al día")
        with c4:
            tarjeta("Revisión humana", met.porcentaje(op.get("tasa_revision_humana")),
                    f"{op.get('con_auditoria', 0)} de {total} documentos",
                    que_es="Parte de los documentos que pasaron por una persona: ambiguos, con medicamentos "
                           "de alto riesgo o con confianza media o baja.",
                    como_leer="Más bajo significa más trabajo automático, pero nunca a costa de la seguridad: "
                              "ante la duda, el agente pregunta.",
                    fuente=met.FUENTE_OPERACION, progreso=op.get("tasa_revision_humana"))
        with c5:
            tarjeta("Confianza media", met.decimal(op.get("confianza_media")), "escala de 0 a 1",
                    que_es="Qué tan seguro estuvo el agente, en promedio. Combina legibilidad (25 %), "
                           "validación de datos (30 %), el modelo (25 %) y acuerdo entre pasos (20 %).",
                    como_leer=f"Con {alto} o más el documento se enruta solo; debajo de {medio} va a una persona.",
                    fuente=met.FUENTE_OPERACION, progreso=op.get("confianza_media"), derecha=True)

        if total == 0:
            html(met.vacio_html("Todavía no hay documentos procesados",
                                "Sube uno desde Carga y vuelve a esta página."))
        else:
            destinos = met.tabla_conteo(op.get("por_destino"), met.DESTINOS, met.SIGNIFICADO_DESTINOS,
                                        met.FUENTE_OPERACION)
            tipos = met.tabla_conteo(op.get("por_tipo"), met.TIPOS, met.SIGNIFICADO_TIPOS, met.FUENTE_OPERACION)
            franjas = met.tabla_franjas(op.get("franjas_confianza"))
            modelos_op = met.tabla_conteo(op.get("modelos"), {}, fuente=met.FUENTE_OPERACION,
                                          significado=met.significado_modelo)

            izquierda, derecha = st.columns(2, gap="medium")
            with izquierda, panel("destinos"):
                html(met.seccion_html(
                    "Adónde fue cada documento", "Cola del hospital que eligió el agente",
                    que_es="Cada documento termina en una cola. La decide el agente según el tipo, la urgencia "
                           "y la confianza; lo urgente siempre va a Emergencia.",
                    como_leer="Pasa el mouse por cada barra para ver qué recibe esa cola.",
                    fuente=met.FUENTE_OPERACION))
                grafico(met.barras(destinos, "Documentos", tema=TEMA, categoria="Destino"), len(destinos), len(tipos))
            with derecha, panel("tipos"):
                html(met.seccion_html(
                    "Qué tipo de documento llegó", "Clase de documento que reconoció el agente",
                    que_es="Recetas, informes, órdenes, epicrisis y certificados. «Otro» es lo que no le "
                           "corresponde ordenar, como una factura.",
                    fuente=met.FUENTE_OPERACION))
                grafico(met.barras(tipos, "Documentos", tema=TEMA, categoria="Tipo"), len(tipos), len(destinos))

            with panel("alertas"):
                html(met.seccion_html(
                    "Últimas urgencias avisadas", "Las 10 más recientes, con el aviso a la guardia médica",
                    que_es="Documentos urgentes que fueron a Emergencia. Cada uno avisó a la guardia en el "
                           "momento en que se procesó.",
                    como_leer="El mensaje del aviso no se muestra porque puede nombrar al paciente.",
                    fuente=met.FUENTE_OPERACION))
                alertas = met.tabla_alertas(op.get("alertas"))
                if alertas.empty:
                    pie("Sin urgencias por ahora.")
                else:
                    tabla(alertas, met.AYUDA_ALERTAS)

            izquierda, derecha = st.columns(2, gap="medium")
            with izquierda, panel("confianza"):
                html(met.seccion_html(
                    "Qué tan seguro estuvo el agente", f"Franjas del score: ≥ {alto} · {medio} a {alto} · < {medio}",
                    que_es="Cuántos documentos cayeron en cada franja del score de confianza.",
                    como_leer=f"Con {alto} o más se enruta solo; entre {medio} y {alto} pide segunda opinión o "
                              f"marca auditoría; debajo de {medio} va a revisión humana.",
                    fuente=met.FUENTE_OPERACION + " Umbrales: " + met.FUENTE_REGLAS))
                grafico(met.barras_franjas(franjas, tema=TEMA), len(franjas), len(modelos_op))
            with derecha, panel("modelos"):
                html(met.seccion_html(
                    "Qué modelo respondió", "Modelo de lenguaje que leyó cada documento",
                    que_es="Si el modelo principal falla, el adaptador pasa al de respaldo y el documento no se "
                           "pierde. Aquí se ve cuántas veces respondió cada uno.",
                    fuente=met.FUENTE_OPERACION))
                grafico(met.barras(modelos_op, "Documentos", tema=TEMA, categoria="Modelo"), len(modelos_op),
                        len(franjas))

        pie(f"Datos consultados el {consulta}, hora del hospital ({zona}). Sin datos de pacientes.")

# --------------------------------------------------------------------------- evaluación
with pestana_evaluacion:
    if ev is not None and len(ev.get("corridas") or []) > 1:
        corridas = list(ev["corridas"])
        _, derecha = st.columns([3, 1])
        with derecha:
            elegida = st.selectbox("Corrida de evaluación", corridas,
                                   index=corridas.index(ev.get("corrida", corridas[0])),
                                   format_func=met.nombre_corrida,
                                   help="Cada corrida es una prueba completa del agente sobre el conjunto de "
                                        "prueba. La primera es la más reciente.")
        if elegida != ev.get("corrida"):
            ev = met.obtener_evaluacion(API_URL, elegida) or ev

    if ev is None:
        if error_api:
            html(met.vacio_html("No se pudo leer la evaluación",
                                f"{error_api} Revisa que la API esté encendida y toca «Actualizar datos»."))
        else:
            html(met.vacio_html("Todavía no hay una evaluación publicada",
                                "Cuando se suba una corrida oficial a evals/resultados/, aparece aquí con sus "
                                "métricas."))
    else:
        corrida = str(ev.get("corrida", ""))
        fuente = met.fuente_evaluacion(corrida)
        html(met.resumen_html(f"Evaluación del {met.nombre_corrida(corrida)}", met.resumen_evaluacion_texto(ev)))
        if ev.get("simulado"):
            st.warning("Esta corrida es simulada: el harness no llamó al modelo y los números no miden nada.")

        recall = met.metrica(ev, "recall_urgencias")
        valor_recall = recall.get("valor")
        cumple = isinstance(valor_recall, (int, float)) and valor_recall >= met.OBJETIVO_RECALL
        perdidas = (recall.get("total") or 0) - (recall.get("aciertos") or 0)
        hero, resto = st.columns([1, 3], gap="medium")
        with hero:
            tarjeta("Urgencias detectadas", met.porcentaje(valor_recall),
                    f"{recall.get('aciertos', '—')} de {recall.get('total', '—')} urgencias · "
                    f"{ev.get('falsas_urgencias', 0)} falsas alarmas",
                    que_es="De todas las urgencias del conjunto de prueba, cuántas mandó el agente a Emergencia "
                           "(recall de urgencias). Es la métrica que más pesa.",
                    como_leer="El objetivo del proyecto es 100 %: una urgencia perdida puede costar un paciente. "
                              "Una falsa alarma solo cuesta minutos de un médico.",
                    fuente=fuente + " Objetivo: docs/api-contract.md, sección 4.",
                    estado="ok" if cumple else "falla",
                    texto_estado="Objetivo 100 % cumplido" if cumple
                    else f"{perdidas} urgencia{'s' if perdidas != 1 else ''} sin detectar",
                    progreso=valor_recall, grande=True)
        with resto:
            claves = [
                ("accuracy_clasificacion", "Tipo correcto",
                 "Si el agente reconoció bien qué documento era (receta, informe, orden...).",
                 "Sobre los documentos legibles: texto, PDF y fotos de buena calidad."),
                ("accuracy_destino", "Cola correcta",
                 "Si el documento fue a la cola que corresponde: Emergencia, Farmacia, Autorizaciones, "
                 "Historia clínica o Revisión humana.",
                 "Sobre los documentos legibles."),
                ("accuracy_auditoria", "Marca de revisión",
                 "Si el agente marcó para revisión humana los documentos que lo necesitaban, y solo esos.",
                 "Un error aquí puede ser pedir revisión de más o de menos."),
                ("fuera_de_alcance", "Fuera de alcance",
                 "Si el agente dijo «esto no me corresponde» ante facturas, consentimientos o informes en otro "
                 "idioma (AMB-6), con el motivo.",
                 "Sobre los casos fuera de alcance del conjunto de prueba."),
                ("puerta_legibilidad", "Imágenes ilegibles",
                 "Si ante fotos o escaneos de calidad media o mala el agente reconoció que no podía leerlos bien "
                 "en vez de inventar.",
                 "Sobre las imágenes de legibilidad media y severa."),
                ("casos_perfectos", "Correcto en todo",
                 "Versiones de documentos en las que el agente no se equivocó en ningún campo.",
                 "Es la vara más exigente del panel: un solo campo mal y el caso no cuenta."),
            ]
            filas = [st.columns(3), st.columns(3)]
            for i, (clave, titulo, que_es, sobre) in enumerate(claves):
                m = met.metrica(ev, clave)
                with filas[i // 3][i % 3]:
                    tarjeta(titulo, met.porcentaje(m.get("valor")),
                            f"{met.de_cada_10(m.get('valor'))} · {m.get('aciertos', '—')} de {m.get('total', '—')}",
                            que_es=que_es, como_leer=sobre, fuente=fuente, progreso=m.get("valor"),
                            derecha=i % 3 == 2)

        por_tipo = met.tabla_por_tipo(ev.get("por_tipo"), corrida)
        categorias = met.tabla_conteo(ev.get("fallos_por_categoria"), met.CATEGORIAS,
                                      met.SIGNIFICADO_CATEGORIAS, fuente)
        izquierda, derecha = st.columns(2, gap="medium")
        with izquierda, panel("por_tipo"):
            html(met.seccion_html(
                "Acierto por tipo de documento", "Parte que fue a la cola correcta, solo versiones legibles",
                que_es="Para cada tipo de documento, en qué parte de sus versiones el agente eligió la cola "
                       "correcta.",
                como_leer="Una barra corta señala el tipo de documento que más hay que mejorar.",
                fuente=fuente))
            if por_tipo.empty:
                pie("Sin datos.")
            else:
                grafico(met.barras(por_tipo, "Acierto", formato=".0%", dominio=(0, 1), etiqueta_col="acierto",
                                   texto_col="detalle", tema=TEMA, categoria="Tipo"),
                        len(por_tipo), len(categorias))
        with derecha, panel("fallos"):
            html(met.seccion_html(
                "Dónde se equivoca", "Versiones con algún error, por grupo",
                que_es="Los errores agrupados como el informe de evals/run.py: por categoría de ambigüedad, "
                       "urgencia, legibilidad o tipo de documento.",
                como_leer="Es la lista de lo que hay que mejorar. Pasa el mouse por cada barra para ver los casos.",
                fuente=fuente))
            if categorias.empty:
                pie("Ningún fallo en esta corrida.")
            else:
                grafico(met.barras(categorias, "Versiones con fallo", tema=TEMA, categoria="Grupo"),
                        len(categorias), len(por_tipo))

        fallos = met.tabla_fallos(ev.get("fallos"))
        if not fallos.empty:
            with st.expander(f"Ver los {len(fallos)} fallos, caso por caso"):
                tabla(fallos, met.AYUDA_FALLOS)

        modelos = met.tabla_conteo(ev.get("modelos"), {})
        texto_pie = (f"Tiempo por documento: la mitad tarda menos de {met.segundos(ev.get('latencia_p50'))} y el "
                     f"95 % menos de {met.segundos(ev.get('latencia_p95'))}.")
        if not modelos.empty:
            texto_pie += " Modelos: " + ", ".join(f"{r.etiqueta} ({r.cantidad})" for r in modelos.itertuples()) + "."
        pie(texto_pie + f" Corrida {met.nombre_corrida(corrida)}, {ev.get('variantes', 0)} variantes, "
                        f"{met.fecha_corta(ev.get('fecha'))}. El detalle completo está en evals/resultados/ "
                        "y en el README.")
