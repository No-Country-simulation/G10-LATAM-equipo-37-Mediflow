"""Rules page."""
import streamlit as st

from ui.lib import api_request, show_api_error

st.title("⚙️ Reglas")
try:
    response = api_request("GET", "/rules")
    if response.is_success:
        st.json(response.json())
    else:
        show_api_error(response)
except RuntimeError as exc:
    st.error(str(exc))

st.caption("La edición queda deshabilitada hasta que la API implemente la persistencia de reglas.")
