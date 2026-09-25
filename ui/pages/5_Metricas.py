"""Métricas · cómo viene operando el triaje.

Los números salen de los resultados persistidos en el bucket, con la misma capa de datos que usa la
pantalla de Trazas (`agent/traza.py`). Si no hay datos, se explica qué falta en vez de mostrar un
tablero vacío con ceros, que no distingue "no hay documentos" de "no se pudo leer".
"""
import csv
import io
import os
import sys
from pathlib import Path

import httpx
import streamlit as st

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

try:
    from agent import traza
except ImportError:  # la UI puede correr sin el paquete agent: se muestra solo lo que da la API
    traza = None

API_URL = os.getenv("API_URL", "http://localhost:8000")
COLUMNAS = (
    "documento_id",
    "tipo_documento",
    "destino",
    "score",
    "prioridad",
    "urgencia",
    "requiere_auditoria",
    "modelo",
    "segunda_opinion",
    "acuerdo_segunda_opinion",
    "ms_total",
    "costo_usd",
)

st.title("Métricas")
st.caption(
    "Volumen, urgencias, tasa de revisión humana, confianza media, calibración del score y latencias "
    "de todo lo que pasó por el grafo."
)


def _pct(valor) -> str:
    return f"{valor * 100:.1f} %" if isinstance(valor, (int, float)) else "s/d"


def _segundos(ms) -> str:
    return f"{ms / 1000:.2f} s" if isinstance(ms, (int, float)) else "s/d"


def _tabla(conteo: dict, etiqueta: str, valor: str) -> list[dict]:
    """Conteo a tabla, para mostrarlo con el nombre de las columnas que ve la persona."""
    return [{etiqueta: clave, valor: cantidad} for clave, cantidad in conteo.items()]


if traza is None:
    st.warning(
        "No se pudo importar `agent.traza`. Corré la UI desde la raíz del repo "
        "(`streamlit run ui/app.py`) para calcular las métricas sobre los resultados persistidos."
    )
    st.stop()

bucket = traza.bucket_configurado()
lectura = traza.leer_resultados(bucket=bucket)

if lectura["error"] or not lectura["resultados"]:
    motivo = lectura["error"] or f"El bucket `{bucket}` está vacío."
    st.info(f"{motivo} Procesá documentos desde la pantalla de Carga y volvé a entrar.")

    # Mientras no haya histórico, se muestra lo que responde la API, para no dejar la pantalla muda
    # y para que se vea que el endpoint existe.
    with st.expander("Lo que reporta la API en /metrics"):
        try:
            st.json(httpx.get(f"{API_URL}/metrics", timeout=15).json())
        except Exception as e:  # noqa: BLE001 - la API puede no estar levantada
            st.caption(f"No se pudo consultar la API: {e}")
    st.stop()

registros = traza.a_registros(lectura["resultados"])
kpi = traza.metricas(registros)

st.caption(
    f"{kpi['documentos']} documento(s) en `{bucket}`"
    + (f" · {lectura['ilegibles']} archivo(s) ilegible(s), ignorados" if lectura["ilegibles"] else "")
)

# --------------------------------------------------------------------------- KPI

columnas = st.columns(6)
columnas[0].metric("Documentos", kpi["documentos"])
columnas[1].metric("Urgencias", f"{kpi['urgencias']} ({_pct(kpi['urgencias_pct'])})")
columnas[2].metric("Revisión humana", _pct(kpi["tasa_revision_humana"]))
columnas[3].metric("Con auditoría", kpi["con_auditoria"])
columnas[4].metric("Confianza media", kpi["confianza_media"] if kpi["confianza_media"] is not None else "s/d")
columnas[5].metric("Latencia p95", _segundos(kpi["latencia_ms"]["p95"]))

for alerta in kpi["alertas"]:
    st.warning(alerta)

# --------------------------------------------------------------------------- volumen

izquierda, derecha = st.columns(2)
with izquierda:
    st.markdown("#### Volumen por destino")
    st.bar_chart(kpi["por_destino"], horizontal=True, color="#4C78A8")
    st.dataframe(_tabla(kpi["por_destino"], "Destino", "Documentos"), width="stretch", hide_index=True)
with derecha:
    st.markdown("#### Volumen por tipo de documento")
    st.bar_chart(kpi["por_tipo"], horizontal=True, color="#F58518")
    st.dataframe(_tabla(kpi["por_tipo"], "Tipo", "Documentos"), width="stretch", hide_index=True)

# --------------------------------------------------------------------------- calibración y modelos

st.markdown("#### Calibración del score")
st.caption(
    "Tasa de revisión humana por franja de score. Con el score bien calibrado, la franja baja "
    "concentra las revisiones y la alta casi no tiene."
)
st.dataframe(kpi["calibracion"], width="stretch", hide_index=True)

columna_a, columna_b = st.columns(2)
with columna_a:
    st.markdown("#### Confianza media por tipo")
    if kpi["confianza_media_por_tipo"]:
        st.dataframe(
            _tabla(kpi["confianza_media_por_tipo"], "Tipo", "Confianza media"),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Sin documentos con score.")

with columna_b:
    st.markdown("#### Segunda opinión y respaldos")
    st.write(f"Pedidas: **{kpi['segunda_opinion']['pedidas']}**")
    st.write(
        f"Con desacuerdo: **{kpi['segunda_opinion']['desacuerdos']}** "
        f"({_pct(kpi['segunda_opinion']['tasa_desacuerdo'])})"
    )
    st.write(f"Costo acumulado: **{kpi['costo_usd'] if kpi['costo_usd'] is not None else 's/d'}** US$")
    if kpi["por_modelo"]:
        st.dataframe(_tabla(kpi["por_modelo"], "Modelo", "Documentos"), width="stretch", hide_index=True)

# --------------------------------------------------------------------------- tabla y descarga

st.markdown("#### Documentos")
st.dataframe(
    [{clave: registro[clave] for clave in COLUMNAS} for registro in registros],
    width="stretch",
    hide_index=True,
)

buffer = io.StringIO()
escritor = csv.DictWriter(buffer, fieldnames=list(COLUMNAS), extrasaction="ignore")
escritor.writeheader()
escritor.writerows(registros)
st.download_button(
    "Descargar la tabla (CSV)",
    data=buffer.getvalue(),
    file_name="mediflow-metricas.csv",
    mime="text/csv",
)
st.caption("Datos sintéticos. El CSV sale de los resultados persistidos y no incluye texto de documentos.")
