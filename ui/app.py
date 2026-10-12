"""MediFlow Streamlit application entry point."""
import streamlit as st

st.set_page_config(page_title="MediFlow", page_icon="🏥", layout="wide")

st.title("MediFlow")
st.subheader("Triaje documental clínico")
st.markdown(
    "Carga documentos clínicos, consulta su resultado de enrutamiento y revisa manualmente "
    "los casos ambiguos sin perder el archivo original."
)

st.info("Usa el menú lateral para cargar documentos, consultar la cola de auditoría y revisar métricas.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Formatos soportados", "PDF · imagen · texto · JSON")
with col2:
    st.metric("Revisión humana", "AMB-1 a AMB-6")
with col3:
    st.metric("Procesamiento", "API + grafo MediFlow")

st.caption("MediFlow realiza triaje documental; no interpreta imágenes médicas ni emite diagnósticos.")
