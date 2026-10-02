"""Triage queue page."""
import streamlit as st

from ui.lib import api_request, show_api_error

st.title("📥 Cola de triaje")
try:
    response = api_request("GET", "/queue/human")
    if response.is_success:
        items = response.json().get("items", [])
        if items:
            st.dataframe(items, use_container_width=True)
        else:
            st.info("La cola de revisión humana está vacía.")
    else:
        show_api_error(response)
except RuntimeError as exc:
    st.error(str(exc))
