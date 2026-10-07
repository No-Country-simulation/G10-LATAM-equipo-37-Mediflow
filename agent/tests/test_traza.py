"""Tests de la capa de trazas y métricas.

Es lógica pura sobre JSON: no necesita Streamlit ni un backend real, así que se prueba con
resultados armados a mano y con un `./data` temporal.
"""
from __future__ import annotations

import json

import pytest

from agent import traza


def _registro(nodo: str, ms: float, ts: float, modelo: str | None = None, **detalle) -> dict:
    registro = {"nodo": nodo, "ms": ms, "ts": ts, "detalle": detalle}
    if modelo:
        registro["modelo"] = modelo
    return registro


def _payload(
    documento_id: str,
    score: float,
    destino: str = "Farmacia_Hospitalaria",
    tipo: str = "Receta Medica",
    urgencia: bool = False,
    con_traza: bool = True,
) -> dict:
    return {
        "documento_id": documento_id,
        "tipo_archivo": "TEXTO",
        "canal_origen": "web",
        "clasificacion": {"tipo_documento": tipo, "nivel_prioridad": "Urgente" if urgencia else "Rutina"},
        "datos_extraidos": {"paciente": {"nome": "Paciente Sintetico"}},
        "validacion": {"campos_faltantes": [], "conflictos": [], "errores": []},
        "score": score,
        "urgencia": {"detectada": urgencia, "alto_riesgo_farmacologico": []},
        "decision": {"destino_principal": destino, "requiere_auditoria_humana": score < 0.85},
        "modelo_utilizado": "gemini/gemini-2.5-flash",
        "trace": [_registro("normalizar", 1.0, 0.0), _registro("enrutar", 2.0, 1.0)] if con_traza else [],
    }


# --------------------------------------------------------------------------- resumen de traza


def test_resumen_traza_suma_tiempos_y_detecta_el_cambio_de_modelo():
    trace = [
        _registro("normalizar", 4.0, 100.0),
        _registro("clasificar", 900.0, 101.0, modelo="gemini/gemini-2.5-flash", tokens_entrada=800, tokens_salida=60),
        _registro("puntuar", 1.0, 102.0),
        _registro("segunda_opinion", 500.0, 103.0, modelo="groq/llama-4-scout", costo_usd=0.0004),
        _registro("puntuar", 1.0, 104.0),
    ]
    resumen = traza.resumen_traza(trace)

    assert resumen["total_ms"] == 1406.0
    assert resumen["medido"] is True
    assert resumen["nodos_repetidos"]["puntuar"] == 2
    assert resumen["segunda_opinion"] is True
    assert resumen["cambio_de_modelo"] == {
        "hubo": True,
        "de": "gemini/gemini-2.5-flash",
        "a": "groq/llama-4-scout",
    }
    assert resumen["tokens"] == {"entrada": 800, "salida": 60}
    assert resumen["costo_usd"] == 0.0004


def test_resumen_traza_estima_con_marcas_de_tiempo_cuando_no_hay_ms():
    trace = [_registro("normalizar", 0, 100.0), _registro("validar", 0, 100.25)]
    for registro in trace:
        registro.pop("ms")

    resumen = traza.resumen_traza(trace)
    assert resumen["medido"] is False
    assert resumen["nodos"][0]["ms"] == 250.0
    assert resumen["nodos"][1]["ms"] is None


def test_resumen_traza_vacio_no_rompe():
    resumen = traza.resumen_traza(None)
    assert resumen["nodos"] == []
    assert resumen["total_ms"] is None
    assert resumen["cambio_de_modelo"]["hubo"] is False


# --------------------------------------------------------------------------- tabla y métricas


def test_a_registros_arma_una_fila_por_documento():
    registro = traza.a_registros([_payload("DOC-1", 0.90, urgencia=True)])[0]

    assert registro["documento_id"] == "DOC-1"
    assert registro["destino"] == "Farmacia_Hospitalaria"
    assert registro["urgencia"] is True
    assert registro["nodos_ejecutados"] == 2
    assert registro["ms_total"] == 3.0


def test_metricas_calcula_kpi_y_calibracion():
    registros = traza.a_registros(
        [
            _payload("DOC-1", 0.90),
            _payload("DOC-2", 0.70, destino="Cola_Revision_Humana", urgencia=True),
            _payload("DOC-3", 0.30, destino="Cola_Revision_Humana", con_traza=False),
        ]
    )
    kpi = traza.metricas(registros)

    assert kpi["documentos"] == 3
    assert kpi["urgencias"] == 1
    assert kpi["tasa_revision_humana"] == pytest.approx(0.667, abs=0.001)
    assert kpi["confianza_media"] == pytest.approx(0.633, abs=0.001)
    assert kpi["por_destino"]["Cola_Revision_Humana"] == 2
    assert [franja["documentos"] for franja in kpi["calibracion"]] == [1, 1, 1]
    assert kpi["calibracion"][2]["tasa"] == 0.0
    assert kpi["latencia_ms"]["media"] == 3.0
    # DOC-3 no tiene traza: tiene que aparecer como alerta y no como un error.
    assert any("sin traza guardada" in alerta for alerta in kpi["alertas"])


def test_metricas_avisa_cuando_el_score_contradice_el_destino():
    registros = traza.a_registros(
        [
            _payload("DOC-1", 0.20),  # score bajo y sin revisión
            _payload("DOC-2", 0.95, destino="Cola_Revision_Humana"),  # score alto y en revisión
        ]
    )
    kpi = traza.metricas(registros)

    assert any("no terminaron en revisión humana" in alerta for alerta in kpi["alertas"])
    assert any("sobre el umbral automático" in alerta for alerta in kpi["alertas"])


def test_metricas_sin_datos_devuelve_ceros():
    kpi = traza.metricas([])
    assert kpi["documentos"] == 0
    assert kpi["confianza_media"] is None
    assert kpi["tasa_revision_humana"] is None
    assert kpi["latencia_ms"]["p95"] is None
    assert kpi["alertas"] == []


def test_percentiles_interpolados():
    assert traza._percentil([100.0, 200.0, 300.0], 0.50) == 200.0
    assert traza._percentil([100.0, 200.0, 300.0], 0.95) == 290.0
    assert traza._percentil([], 0.5) is None


# --------------------------------------------------------------------------- lectura del bucket


def _escribir(base, ruta: str, contenido: str) -> None:
    destino = base / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")


def test_leer_resultados_del_disco(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIFLOW_DATA_DIR", str(tmp_path))
    _escribir(tmp_path, "bucket-test/procesados/farmacia/DOC-1.json", json.dumps(_payload("DOC-1", 0.9)))
    _escribir(tmp_path, "bucket-test/auditoria_humana/DOC-2.json", json.dumps(_payload("DOC-2", 0.5)))
    _escribir(tmp_path, "bucket-test/procesados/farmacia/roto.json", "{no es json")
    # recibidos/ no es un resultado: el original todavía no pasó por el grafo.
    _escribir(tmp_path, "bucket-test/recibidos/DOC-3.json", json.dumps(_payload("DOC-3", 0.9)))

    lectura = traza.leer_resultados(bucket="bucket-test")

    assert lectura["archivos"] == 3
    assert lectura["ilegibles"] == 1
    assert lectura["error"] is None
    assert {r["documento_id"] for r in lectura["resultados"]} == {"DOC-1", "DOC-2"}
    assert all(r["ruta_objeto"] for r in lectura["resultados"])


def test_leer_resultados_sin_carpeta_explica_el_motivo(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIFLOW_DATA_DIR", str(tmp_path / "no-existe"))

    lectura = traza.leer_resultados(bucket="bucket-test")

    assert lectura["resultados"] == []
    assert "No hay resultados" in lectura["error"]


def test_cargar_json_acepta_texto_y_bytes():
    assert traza.cargar_json('{"documento_id": "DOC-1"}')["documento_id"] == "DOC-1"
    assert traza.cargar_json(b'{"documento_id": "DOC-1"}')["documento_id"] == "DOC-1"

    with pytest.raises(ValueError, match="no es JSON válido"):
        traza.cargar_json("{roto")
    with pytest.raises(ValueError, match="objeto JSON"):
        traza.cargar_json("[1, 2, 3]")


def test_umbrales_salen_de_rules_yaml():
    umbral = traza.umbrales()

    assert set(umbral) == {"revision", "automatico"}
    assert 0 < umbral["revision"] < umbral["automatico"] <= 1