"""Rules page."""
import streamlit as st

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import api_request, show_api_error

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
