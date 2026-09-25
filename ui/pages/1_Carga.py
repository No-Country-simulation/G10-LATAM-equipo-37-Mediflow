"""Document upload and triage page."""
from __future__ import annotations

import uuid

import streamlit as st

from ui.lib import api_request, remember_document, render_result, show_api_error

st.title("📄 Carga de documento")
st.caption("El original se conserva en la sesión para que pueda ser revisado si el grafo solicita auditoría humana.")

with st.form("triage_upload"):
    uploaded = st.file_uploader(
        "Selecciona un PDF, imagen, texto o JSON",
        type=["pdf", "png", "jpg", "jpeg", "tif", "tiff", "webp", "txt", "json"],
    )
    document_id = st.text_input("ID del documento", value=f"DOC-UI-{uuid.uuid4().hex[:8].upper()}")
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
                    files={"archivo": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
                )
                if response.is_success:
                    st.session_state["last_triage_result"] = response.json()
                else:
                    show_api_error(response)
            except RuntimeError as exc:
                st.error(str(exc))

result = st.session_state.get("last_triage_result")
if result:
    st.divider()
    render_result(result)
    if result.get("status") == "revision_humana" or result.get("decision_enrutamiento", {}).get("requiere_auditoria_humana"):
        with st.expander("Abrir documento para auditoría", expanded=True):
            from ui.lib import show_document_preview

            show_document_preview()
