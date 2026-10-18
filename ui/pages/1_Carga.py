"""Document upload and triage page."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import api_request, remember_document, render_result, show_api_error

st.title("📄 Carga de documento")
st.caption("El original se conserva en la sesión para que pueda ser revisado si el grafo solicita auditoría humana.")



def _id_nuevo() -> str:
    return f"DOC-UI-{uuid.uuid4().hex[:8].upper()}"


# El ID por defecto se genera una vez por sesión. Si cambiara en cada ejecución, Streamlit trataría el campo
# como uno nuevo al enviar el formulario y descartaría el ID que la persona escribió.
if st.session_state.pop("carga_id_rotar", False) or "carga_id" not in st.session_state:
    st.session_state["carga_id"] = _id_nuevo()

with st.form("triage_upload"):
    uploaded = st.file_uploader(
        "Selecciona un PDF, imagen, texto o JSON",
        type=["pdf", "png", "jpg", "jpeg", "tif", "tiff", "webp", "txt", "json"],
    )
    document_id = st.text_input("ID del documento", key="carga_id")
    channel = st.text_input("Canal de origen", value="streamlit")
    submitted = st.form_submit_button("Procesar documento", type="primary")

if submitted:
    if uploaded is None:
        st.error("Selecciona un archivo antes de procesar.")
    elif not document_id.strip():
        st.error("El ID del documento es obligatorio.")
    else:
        remember_document(uploaded)
        with st.spinner("Ejecutando ingesta y grafo de triaje..."):
            try:
                response = api_request(
                    "POST",
                    "/triage/upload",
                    data={"documento_id": document_id.strip(), "canal_origen": channel.strip() or "streamlit"},
                    files={
                        "archivo": (
                            uploaded.name,
                            uploaded.getvalue(),
                            uploaded.type or "application/octet-stream",
                        )
                    },
                )
                if response.is_success:
                    st.session_state["last_triage_result"] = response.json()
                    st.session_state["carga_id_rotar"] = True  # el siguiente documento lleva un ID nuevo
                    st.rerun()  # el resultado se pinta desde la sesión; el formulario vuelve con el ID nuevo
                else:
                    show_api_error(response)
            except RuntimeError as exc:
                st.error(str(exc))

result = st.session_state.get("last_triage_result")
if result:
    st.divider()
    render_result(result)
    decision = result.get("decision_enrutamiento", {})
    if result.get("status") == "revision_humana" or decision.get("requiere_auditoria_humana"):
        with st.expander("Abrir documento para auditoría", expanded=True):
            from lib import show_document_preview

            show_document_preview()
