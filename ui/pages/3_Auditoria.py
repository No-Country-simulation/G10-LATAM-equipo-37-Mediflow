"""Panel del auditor: el documento y lo que extrajo el agente, lado a lado; el motivo de la revisión a la
vista, y aprobar, corregir o rechazar con un clic.

Habla con la API de revisión humana (docs/api-contract.md, sección 11). El modo demostración carga cuatro
casos del conjunto de prueba, con datos sintéticos, y no envía nada a la API.
"""
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

UI = Path(__file__).resolve().parents[1]
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))  # para importar ui/auditoria.py también si la página se abre sola

import auditoria as aud  # noqa: E402

API_URL = os.getenv("API_URL", "http://localhost:8000")
IMAGENES = ("image/png", "image/jpeg", "image/webp", "image/gif")
VERBOS = {"aprobar": "aprobado", "corregir": "corregido", "rechazar": "rechazado"}

st.set_page_config(page_title="Auditoría · MediFlow", page_icon="🩺", layout="wide")
estado = st.session_state
estado.setdefault("resueltos", [])
estado.setdefault("demo_resueltos", [])
estado.setdefault("resueltos_ids", [])  # (modo, documento) que resolvió esta sesión, para no confundirlos


def mostrar_resultado(ultimo: dict) -> None:
    """La última decisión: qué se hizo, qué cambió y, si la API lo devuelve, adónde fue el documento."""
    st.success(f"**{aud.md(ultimo['documento_id'])}** {VERBOS[ultimo['accion']]} por {aud.md(ultimo['revisor'])}.")
    destino = aud.como_dict(ultimo["respuesta"].get("decision_enrutamiento")).get("destino_principal")
    if destino:
        st.info(f"El agente lo reencaminó a **{aud.md(destino)}**.")
    if ultimo["cambios"]:
        st.dataframe(pd.DataFrame(ultimo["cambios"]), hide_index=True)
    titulo = "Lo que se enviaría a la API" if ultimo["demo"] else "Lo que quedó registrado"
    with st.expander(titulo):
        if ultimo["demo"]:
            st.caption("En modo demostración no se envía nada. Este es el cuerpo de la decisión:")
            st.json({"POST": f"/audit/{ultimo['documento_id']}", "cuerpo": ultimo["decision"]})
        else:
            st.json(ultimo["respuesta"])


def mostrar_historial() -> None:
    if estado.resueltos:
        with st.expander(f"Resueltos en esta sesión ({len(estado.resueltos)})"):
            st.dataframe(pd.DataFrame(estado.resueltos), hide_index=True)


def mostrar_original(item: dict, extraccion: dict, demo: bool) -> None:
    """El original, si hay, y el texto que leyó el agente."""
    original = None
    if demo and item.get("original_ruta"):
        ruta = item["original_ruta"]
        original = (ruta.read_bytes(), aud.tipo_de_archivo(ruta))
    elif not demo:
        original = aud.obtener_original(API_URL, item["documento_id"])

    if original:
        datos, tipo = original
        mostrada = False
        if tipo in IMAGENES:
            try:
                st.image(datos, caption="Original")
                mostrada = True
            except Exception:  # una imagen dañada no puede tirar la página: queda la descarga
                st.warning("No se pudo mostrar la imagen original. Descárgala para verla.")
        if not mostrada:
            st.download_button(
                "Descargar el original", datos, mime=tipo,
                file_name=f"{item['documento_id']}{mimetypes.guess_extension(tipo) or ''}",
                key=f"{prefijo}:{item['documento_id']}:original",
            )

    texto = extraccion.get("texto")
    if texto:
        if original:
            st.caption("Texto que leyó el agente")
        lineas = sum(max(1, -(-len(linea) // 70)) for linea in texto.splitlines())  # contando las que se parten
        with st.container(height=min(900, 48 + 27 * lineas), border=True):
            st.text(texto)
    elif not original:
        st.info("La extracción no trae el texto del documento y la API todavía no entrega el original.")


def campo(ruta: str, valor, falta: bool, evidencia: str | None, clave: str) -> str:
    etiqueta = aud.etiqueta_campo(ruta) + (" :red[· el agente no lo encontró]" if falta else "")
    texto = aud.mostrado(valor)
    if ruta.split(".")[-1] in aud.CAMPOS_LARGOS or len(texto) > 90:
        escrito = st.text_area(etiqueta, value=texto, key=clave, height=110)
    else:
        escrito = st.text_input(etiqueta, value=texto, key=clave)
    if evidencia:
        st.caption(f"En el documento: «{aud.md(evidencia)}»")
    return escrito


def tabla_medicamentos(medicamentos, evidencia: str | None, clave: str) -> list[dict]:
    filas = pd.DataFrame(aud.normalizar_medicamentos(medicamentos), columns=list(aud.COLUMNAS_MEDICAMENTO))
    filas = filas.astype(object).where(filas.notna(), "")  # celdas de texto, vacías en lugar de "None"
    st.markdown("**Medicamentos**")
    editadas = st.data_editor(
        filas,
        key=clave,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "nombre": st.column_config.TextColumn("Nombre"),
            "dosis": st.column_config.TextColumn("Dosis"),
            "frecuencia": st.column_config.TextColumn("Frecuencia"),
            "duracion": st.column_config.TextColumn("Duración"),
        },
    )
    riesgo = aud.medicamentos_de_alto_riesgo(medicamentos)
    if riesgo:
        st.caption(f"Alto riesgo según el agente: {aud.md(', '.join(riesgo))}. El grafo lo vuelve a calcular.")
    if evidencia:
        st.caption(f"En el documento: «{aud.md(evidencia)}»")
    return editadas.to_dict("records")


def area_estudios(estudios: list[str], clave: str) -> list[str]:
    escrito = st.text_area("Estudios solicitados, uno por línea", value="\n".join(estudios), key=clave)
    return aud.lineas(escrito)


def indice(opciones: list[str], valor) -> int | None:
    return opciones.index(valor) if valor in opciones else None


def formulario(documento_id: str, extraccion: dict) -> dict:
    """Los campos para revisar y los tres botones. Devuelve lo que escribió el auditor y el botón que tocó."""
    clasificacion = extraccion["clasificacion"]
    datos = extraccion["datos_extraidos"]
    faltantes = set(extraccion["validacion"]["campos_faltantes"])
    evidencias = aud.evidencias_por_campo(extraccion)
    planos = aud.aplanar(datos)
    visibles, vacios, solo_lectura = aud.campos_del_formulario(extraccion)
    tipo_original = clasificacion.get("tipo_documento")
    sin_tipo = tipo_original in (None, "", "Otro")

    def clave(nombre: str) -> str:
        return f"{prefijo}:{documento_id}:{nombre}"  # el modo va en la clave: GS-14 de prueba no es el real

    # Sin enter_to_submit, un Enter en cualquier campo equivaldría a tocar «Aprobar» (Streamlit 1.39 o más).
    with st.form(clave("formulario"), enter_to_submit=False):
        c1, c2 = st.columns(2)
        tipo = c1.selectbox(
            "Tipo de documento", aud.TIPOS_DOCUMENTO, index=indice(aud.TIPOS_DOCUMENTO, tipo_original),
            format_func=aud.nombre_tipo, key=clave("clasificacion:tipo"), placeholder="Sin clasificar",
        )
        prioridad = c2.selectbox(
            "Prioridad", aud.PRIORIDADES, index=indice(aud.PRIORIDADES, clasificacion.get("nivel_prioridad")),
            key=clave("clasificacion:prioridad"), placeholder="Sin clasificar",
        )
        escritos = {
            ruta: campo(ruta, planos.get(ruta), ruta in faltantes, evidencias.get(ruta), clave(f"campo:{ruta}"))
            for ruta in visibles
        }

        medicamentos = estudios = None
        if datos["medicamentos"] or tipo_original == "Receta Medica":
            medicamentos = tabla_medicamentos(datos["medicamentos"], evidencias.get("medicamentos"),
                                              clave("campo:medicamentos"))
        if datos["estudios_solicitados"] or tipo_original == "Orden de Solicitud de Procedimiento":
            estudios = area_estudios(datos["estudios_solicitados"], clave("campo:estudios_solicitados"))
        if sin_tipo and medicamentos is None and estudios is None:
            with st.expander("Agregar medicamentos o estudios"):
                medicamentos = tabla_medicamentos([], None, clave("campo:medicamentos"))
                estudios = area_estudios([], clave("campo:estudios_solicitados"))

        if vacios:
            with st.expander(f"Campos vacíos ({len(vacios)})"):
                for ruta in vacios:
                    escritos[ruta] = campo(ruta, None, False, None, clave(f"campo:{ruta}"))
        if solo_lectura:
            with st.expander("Otros datos extraídos, solo para leer"):
                st.json(solo_lectura)

        motivo = st.text_area(
            "Motivo de la decisión",
            key=clave("decision:motivo"),
            placeholder="Obligatorio para corregir o rechazar. Si apruebas y lo dejas vacío, queda: "
            f"«{aud.MOTIVO_APROBAR}»",
        )
        b1, b2, b3 = st.columns(3)
        aprobar = b1.form_submit_button("Aprobar")
        corregir = b2.form_submit_button("Corregir")
        rechazar = b3.form_submit_button("Rechazar")
        st.caption(
            "Aprobar: el documento sigue con la extracción tal cual. Corregir: sigue con tus cambios. "
            "Rechazar: no sigue; queda registrado con tu motivo."
        )

    accion = "aprobar" if aprobar else "corregir" if corregir else "rechazar" if rechazar else None
    return {
        "accion": accion,
        "escritos": escritos,
        "clasificacion": {"tipo_documento": tipo, "nivel_prioridad": prioridad},
        "medicamentos": medicamentos,
        "estudios": estudios,
        "motivo": motivo,
    }


def resolver(documento_id: str, extraccion: dict, enviado: dict, demo: bool) -> list[str]:
    """Valida, envía y deja el resultado para mostrarlo. Devuelve los errores para el auditor, si los hay."""
    correcciones, errores_formato = aud.calcular_correcciones(
        extraccion, enviado["escritos"], enviado["clasificacion"], enviado["medicamentos"], enviado["estudios"]
    )
    errores = aud.validar_decision(enviado["accion"], estado.revisor, enviado["motivo"], correcciones, errores_formato)
    if errores:
        return errores

    decision = aud.armar_decision(enviado["accion"], estado.revisor, enviado["motivo"], correcciones)
    if demo:
        respuesta = {
            "documento_id": documento_id,
            "resolucion": {**decision, "fecha": datetime.now(timezone.utc).isoformat()},
        }
        estado.demo_resueltos.append(documento_id)
    else:
        try:
            respuesta = aud.enviar_decision(API_URL, documento_id, decision)
        except aud.ErrorApi as exc:
            return [str(exc)]

    destino = aud.como_dict(respuesta.get("decision_enrutamiento")).get("destino_principal")
    estado.ultimo = {
        "documento_id": documento_id,
        "accion": decision["accion"],
        "revisor": decision["revisor"],
        "cambios": aud.resumen_cambios(extraccion, decision["correcciones"] or {}),
        "decision": decision,
        "respuesta": respuesta,
        "demo": demo,
    }
    estado.resueltos_ids.append((prefijo, documento_id))
    # Si el documento vuelve a la cola para otra ronda, su formulario empieza limpio, no con lo de esta.
    for vieja in [k for k in estado.keys() if str(k).startswith(f"{prefijo}:{documento_id}:")]:
        del estado[vieja]
    estado.resueltos.append({
        "Documento": documento_id,
        "Decisión": decision["accion"],
        "Revisor": decision["revisor"],
        "Hora": datetime.now().strftime("%H:%M"),
        "Destino nuevo": destino or "—",
        "Modo": "demostración" if demo else "API",
    })
    return []


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------

with st.sidebar:
    # Streamlit borra los widgets al pasar a otra página: el nombre y el modo se guardan aparte.
    st.text_input(
        "Revisor", value=estado.get("_revisor", ""), key="revisor", placeholder="Tu nombre y apellido",
        help="Queda registrado con cada decisión, junto con la fecha y el motivo.",
    )
    demo = st.toggle(
        "Modo demostración", value=estado.get("_demo", False), key="demo",
        help="Cuatro casos del conjunto de prueba, con datos sintéticos. No envía nada a la API.",
    )
    st.button("Actualizar la cola")
estado._revisor = estado.revisor
estado._demo = demo
prefijo = "demo" if demo else "api"

st.title("Auditoría humana")
st.caption(
    "Documentos que el agente no puede decidir solo. Compara el original con lo que extrajo el agente y decide: "
    "aprobar, corregir o rechazar."
)

if estado.get("modo") != prefijo:  # la última decisión era del otro modo
    estado.pop("ultimo", None)
    estado.modo = prefijo

if estado.get("ultimo"):
    mostrar_resultado(estado.ultimo)

if demo:
    st.info(
        "**Modo demostración.** Casos del conjunto de prueba, con datos sintéticos. Las decisiones se muestran "
        "pero no se envían a la API."
    )
    items = [i for i in aud.cargar_ejemplos() if i["documento_id"] not in estado.demo_resueltos]
else:
    try:
        items = aud.obtener_cola(API_URL)
    except aud.ErrorApi as exc:
        st.error(str(exc))
        st.caption("Para ver el panel sin la API, activa el modo demostración en la barra lateral.")
        mostrar_historial()
        st.stop()

items = aud.ordenar_cola(items)
por_id = {i["documento_id"]: i for i in items}
ids = list(por_id)
clave_seleccion = f"seleccion:{prefijo}"
anterior = estado.get(f"elegido:{prefijo}")
if anterior and anterior not in por_id and (prefijo, anterior) not in estado.resueltos_ids:
    st.warning(
        f"**{aud.md(anterior)}** salió de la cola mientras lo revisabas: se resolvió desde otra sesión. Si "
        "estabas por decidir, tu decisión no se guardó."
    )
    estado.pop(f"elegido:{prefijo}")

if not items:
    st.success("No hay documentos esperando revisión.")
    if not demo:
        st.caption("Para ver cómo funciona el panel, activa el modo demostración en la barra lateral.")
    elif st.button("Volver a cargar los ejemplos"):
        estado.demo_resueltos.clear()
        estado.resueltos_ids = [r for r in estado.resueltos_ids if r[0] != "demo"]
        estado.pop("ultimo", None)
        st.rerun()
    mostrar_historial()
    st.stop()

# Si el documento elegido ya no está, se elige el primero de la cola, que es el más urgente. Se asigna antes de
# dibujar el selector para que el navegador muestre el documento nuevo y no el recién resuelto.
if estado.get(clave_seleccion) not in por_id:
    estado[clave_seleccion] = ids[0]
urgentes = sum(aud.es_urgente(i["extraccion"]) for i in items)
st.caption(f"Cola de revisión: {len(items)} documento(s), {urgentes} urgente(s). Primero lo urgente.")
documento_id = st.selectbox(
    "Documento", ids, format_func=lambda d: aud.etiqueta_item(por_id[d]), key=clave_seleccion,
    label_visibility="collapsed",
)
estado[f"elegido:{prefijo}"] = documento_id
item = por_id[documento_id]
extraccion = item["extraccion"]
decision_actual = aud.decision_de(extraccion)
validacion = extraccion["validacion"]

if aud.es_urgente(extraccion):
    destino = decision_actual.get("destino_principal")
    aviso = aud.como_dict(decision_actual.get("notificacion_generada"))
    canal = f" y se avisó por {aud.md(aviso['canal'])}" if aviso.get("canal") else ""
    if destino == aud.DESTINO_URGENCIA:
        st.error(
            f"**Urgente.** Ya está en {destino}{canal}. Esta revisión no frena la urgencia: sirve para que los "
            "datos queden bien."
        )
    else:
        st.error(
            f"**Prioridad urgente, pero el destino es {aud.md(destino or 'ninguno')}.** Una urgencia va siempre "
            f"a {aud.DESTINO_URGENCIA}: revisa la prioridad."
        )

titulo, justificacion = aud.motivo_revision(extraccion)
detalle = [aud.md(justificacion)] if justificacion else []
faltan = [aud.etiqueta_campo(c) for c in validacion["campos_faltantes"]]
if faltan:
    detalle.append("Falta: " + ", ".join(faltan) + ".")
detalle += [f"Conflicto: {aud.md(c)}" for c in validacion["conflictos"]]
detalle += [f"Error: {aud.md(e)}" for e in validacion["errores"]]
st.warning(f"**{aud.md(titulo)}**\n\n" + "\n".join(f"- {d}" for d in detalle))

izquierda, derecha = st.columns(2, gap="large")
with izquierda:
    st.subheader("Documento")
    mostrar_original(item, extraccion, demo)

with derecha:
    st.subheader("Lo que extrajo el agente")
    score = aud.score_de(extraccion)
    st.markdown(
        f"**Destino actual:** {aud.md(decision_actual.get('destino_principal') or '—')} · "
        f"**Confianza:** {f'{round(score * 100)} %' if score is not None else '—'} · "
        f"**Canal:** {aud.md(extraccion.get('canal_origen') or '—')}"
    )
    enviado = formulario(documento_id, extraccion)
    if enviado["accion"]:
        errores = resolver(documento_id, extraccion, enviado, demo)
        if errores:
            for error in errores:
                st.error(error)
        else:
            st.rerun()

mostrar_historial()
