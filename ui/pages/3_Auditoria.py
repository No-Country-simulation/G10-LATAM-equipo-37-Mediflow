"""Human review queue page."""
from __future__ import annotations

import streamlit as st

from ui.lib import api_request, show_api_error, show_document_preview

st.title("🧾 Auditoría humana")
st.caption("Revisa el documento original y decide si se aprueba, corrige o rechaza.")

try:
    response = api_request("GET", "/queue/human")
    if response.is_success:
        items = response.json().get("items", [])
    else:
        show_api_error(response)
        items = []
except RuntimeError as exc:
    st.error(str(exc))
    items = []

if not items:
    st.info("No hay documentos pendientes en la cola de revisión humana.")
else:
    labels = [f"{item.get('documento_id', 'sin-id')} · {item.get('motivo', 'requiere revisión')}" for item in items]
    selected = st.selectbox("Documento pendiente", range(len(items)), format_func=lambda index: labels[index])
    item = items[selected]
    st.json(item)

    # If the item includes the original, make it available to the same preview component.
    if item.get("documento_id"):
        st.session_state["audit_document_id"] = item["documento_id"]

    st.subheader("Decisión del auditor")
    decision = st.radio("Resultado", ["aprobar", "corregir", "rechazar"], horizontal=True)
    notes = st.text_area("Motivo o corrección", placeholder="Describe la evidencia revisada...")
    if st.button("Guardar decisión", type="primary"):
        try:
            audit_response = api_request(
                "POST",
                f"/audit/{item.get('documento_id', '')}",
                json={"decision": decision, "motivo": notes},
            )
            if audit_response.is_success:
                st.success("Decisión enviada a la API.")
                st.json(audit_response.json())
            else:
                show_api_error(audit_response)
        except RuntimeError as exc:
            st.error(str(exc))

if st.session_state.get("review_file_bytes"):
    st.divider()
    st.subheader("Documento original recuperado")
    show_document_preview()
