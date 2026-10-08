"""Rules page: view and edit rules via GET/PUT /rules."""
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import admin_headers, api_request, show_api_error

st.title("⚙️ Reglas")

try:
    response = api_request("GET", "/rules")
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

if not response.is_success:
    show_api_error(response)
    st.stop()

current_rules = response.json()
st.subheader("Reglas actuales")
st.json(current_rules)

st.subheader("Editar reglas")
editor = st.text_input("Editor (X-Editor)", help="Quién realiza el cambio; queda en la auditoría.")
raw = st.text_area("Reglas (JSON)", value=json.dumps(current_rules, indent=2, ensure_ascii=False), height=300)

if st.button("Guardar reglas", type="primary"):
    if not editor.strip():
        st.error("Indicá quién edita (X-Editor).")
        st.stop()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        st.error(f"JSON inválido: {exc}")
        st.stop()
    try:
        put_response = api_request("PUT", "/rules", json=payload, headers=admin_headers(editor.strip()))
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    if put_response.is_success:
        st.success("Reglas guardadas.")
        body = put_response.json()
        if isinstance(body, dict) and body.get("aviso"):
            st.warning(body["aviso"])
    else:
        show_api_error(put_response)
