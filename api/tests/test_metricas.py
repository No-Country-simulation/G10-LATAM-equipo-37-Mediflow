"""Pruebas de las métricas del dashboard (N3-04): GET /metrics y GET /metrics/evaluacion."""
import json
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent.storage import local_audit, triage_results
from api import metricas
from api.main import app

UMBRALES = {"automatico": 0.85, "segunda_opinion": 0.60}


def fila(documento_id, destino, score=0.9, tipo="Receta Medica", auditoria=False, alerta=None,
         modelo="gemini/gemini-2.5-flash", created_at="2026-10-13 15:00:00"):
    return {
        "documento_id": documento_id,
        "created_at": created_at,
        "resultado": {
            "documento_id": documento_id,
            "clasificacion": {"tipo_documento": tipo},
            "decision_enrutamiento": {
                "destino_principal": destino,
                "requiere_auditoria_humana": auditoria,
                "notificacion_generada": alerta,
            },
            "score_confianza": score,
            "modelo_utilizado": modelo,
        },
    }


# --------------------------------------------------------------------------- operación
def test_sin_documentos_todo_en_cero():
    m = metricas.metricas_operacion([], en_revision=0, umbrales=UMBRALES, hoy=date(2026, 10, 13))
    assert m["documentos_total"] == 0 and m["documentos_hoy"] == 0
    assert m["tasa_revision_humana"] is None and m["confianza_media"] is None
    assert [d["nombre"] for d in m["por_destino"]] == metricas.DESTINOS
    assert all(d["cantidad"] == 0 for d in m["por_destino"])
    assert m["alertas"] == [] and m["modelos"] == []


def test_cuenta_destinos_urgencias_auditoria_y_confianza():
    alerta = {"canal": "Alerta_Guardia_Medica", "mensaje": "ALERTA URGENTE para Laura Gómez"}
    filas = [
        fila("A", "Cola_Emergencia_Medica", 0.92, "Informe de Laboratorio", alerta=alerta),
        fila("B", "Farmacia_Hospitalaria", 0.70, auditoria=True),
        fila("C", "Cola_Revision_Humana", 0.40, "Otro", auditoria=True, modelo="deepseek/deepseek-chat"),
    ]
    m = metricas.metricas_operacion(filas, en_revision=2, umbrales=UMBRALES, hoy=date(2026, 10, 13))
    assert m["documentos_total"] == 3 and m["documentos_hoy"] == 3
    assert m["urgencias_total"] == 1 and m["urgencias_hoy"] == 1
    assert m["en_revision"] == 2 and m["con_auditoria"] == 2
    assert m["tasa_revision_humana"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["confianza_media"] == pytest.approx((0.92 + 0.70 + 0.40) / 3, abs=1e-4)
    franjas = {f["nombre"]: f["cantidad"] for f in m["franjas_confianza"]}
    assert franjas == {"automatico": 1, "segunda_opinion": 1, "revision": 1}
    assert {d["nombre"]: d["cantidad"] for d in m["por_tipo"]}["Otro"] == 1
    assert {d["nombre"]: d["cantidad"] for d in m["modelos"]} == {"gemini/gemini-2.5-flash": 2,
                                                                  "deepseek/deepseek-chat": 1}


def test_las_alertas_no_traen_el_mensaje_ni_datos_del_paciente():
    alerta = {"canal": "Alerta_Guardia_Medica", "mensaje": "ALERTA URGENTE para Laura Gómez"}
    m = metricas.metricas_operacion([fila("A", "Cola_Emergencia_Medica", alerta=alerta)], 0, UMBRALES,
                                    hoy=date(2026, 10, 13))
    assert m["alertas"][0]["canal"] == "Alerta_Guardia_Medica"
    assert "Laura" not in json.dumps(m, ensure_ascii=False)
    assert "mensaje" not in m["alertas"][0]


def test_hoy_es_el_dia_del_hospital_no_el_de_utc():
    # 02:30 UTC del 14/10 son las 23:30 del 13/10 en Buenos Aires.
    tarde = fila("A", "Historia_Clinica_Electronica", created_at="2026-10-14 02:30:00")
    m = metricas.metricas_operacion([tarde], 0, UMBRALES, hoy=date(2026, 10, 13))
    assert m["documentos_hoy"] == 1
    m = metricas.metricas_operacion([tarde], 0, UMBRALES, hoy=date(2026, 10, 14))
    assert m["documentos_hoy"] == 0


def test_los_umbrales_vienen_de_las_reglas():
    filas = [fila("A", "Farmacia_Hospitalaria", 0.80)]
    m = metricas.metricas_operacion(filas, 0, {"automatico": 0.75, "segunda_opinion": 0.5}, hoy=date(2026, 10, 13))
    assert {f["nombre"]: f["cantidad"] for f in m["franjas_confianza"]}["automatico"] == 1
    assert m["franjas_confianza"][0]["desde"] == 0.75


def test_tolera_filas_raras_sin_caerse():
    filas = [
        {"documento_id": "X", "created_at": "no es fecha", "resultado": None},
        fila("Y", "Destino_Nuevo", score="0.9"),
        fila("Z", "Farmacia_Hospitalaria", score=True, modelo=None),
    ]
    m = metricas.metricas_operacion(filas, 0, UMBRALES, hoy=date(2026, 10, 13))
    assert m["documentos_total"] == 3
    assert m["confianza_media"] is None  # ningún score válido
    assert {d["nombre"]: d["cantidad"] for d in m["por_destino"]}["Destino_Nuevo"] == 1
    assert "sin modelo" in {d["nombre"] for d in m["modelos"]}


def test_alertas_mas_recientes_primero_y_con_tope():
    alerta = {"canal": "Alerta_Guardia_Medica"}
    filas = [fila(f"D{i:02d}", "Cola_Emergencia_Medica", alerta=alerta, created_at=f"2026-10-13 12:{i:02d}:00")
             for i in range(15)]
    m = metricas.metricas_operacion(filas, 0, UMBRALES, hoy=date(2026, 10, 13))
    assert len(m["alertas"]) == metricas.MAX_ALERTAS
    assert m["alertas"][0]["documento_id"] == "D14"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(triage_results, "DB_PATH", tmp_path / "triage.sqlite3")
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path / "auditoria_humana")
    monkeypatch.setattr(metricas, "DIR_EVALUACIONES", tmp_path / "resultados")
    monkeypatch.setattr(metricas, "PLAN_GOLDEN", tmp_path / "plan_golden.csv")
    return TestClient(app)


def test_get_metrics_lee_triage_results_y_la_cola(cliente, tmp_path):
    respuesta = {
        "documento_id": "DOC-1",
        "decision_enrutamiento": {"destino_principal": "Cola_Emergencia_Medica", "requiere_auditoria_humana": False,
                                  "notificacion_generada": {"canal": "Alerta_Guardia_Medica", "mensaje": "x"}},
        "clasificacion": {"tipo_documento": "Informe de Laboratorio"},
        "score_confianza": 0.91,
        "modelo_utilizado": "gemini/gemini-2.5-flash",
    }
    triage_results.guardar_resultado(respuesta)
    local_audit.guardar_extraccion("DOC-2", {"documento_id": "DOC-2"}, base=tmp_path / "auditoria_humana")

    datos = cliente.get("/metrics").json()
    assert datos["documentos_total"] == 1
    assert datos["urgencias_total"] == 1
    assert datos["en_revision"] == 1
    assert datos["alertas"][0]["documento_id"] == "DOC-1"
    # las claves que ya leía la página anterior siguen ahí
    for clave in ("documentos_hoy", "urgencias_hoy", "en_revision", "confianza_media"):
        assert clave in datos


# --------------------------------------------------------------------------- evaluación
def test_parsear_porcentaje():
    assert metricas.parsear_porcentaje("90% (57/63)") == {"valor": 0.9048, "aciertos": 57, "total": 63}
    assert metricas.parsear_porcentaje("sin datos") is None
    assert metricas.parsear_porcentaje(None) is None
    assert metricas.parsear_porcentaje("0% (0/0)")["valor"] is None


PLAN = (
    "id,tipo_documento,resultado_esperado,categoria_ambiguedad,destino_esperado,nivel_legibilidad\n"
    "GS-01,Receta Medica,rutina,,Farmacia_Hospitalaria,leve\n"
    "GS-06,Receta Medica,ambiguedad,AMB-3,Cola_Revision_Humana,\n"
    "GS-12,Informe de Estudio por Imagenes,rutina,,Historia_Clinica_Electronica,severa\n"
    "GS-07,Informe de Estudio por Imagenes,urgencia,,Cola_Emergencia_Medica,leve\n"
)


def corrida(variantes, fecha="2026-10-13T12:00:00"):
    return {"fecha": fecha, "simulado": False,
            "metricas": {"recall_urgencias": "100% (1/1)", "accuracy_destino": "67% (2/3)", "falsas_urgencias": 1,
                         "casos_con_error": 0, "latencia_p50": "3.1 s", "latencia_p95": "8.0 s"},
            "variantes": variantes}


def variante(id_, archivo, clase="base", ok=True, aciertos=None, destino="", modelo="", error=""):
    return {"id": id_, "archivo": archivo, "clase": clase, "ok": ok, "error": error,
            "aciertos": aciertos if aciertos is not None else {"destino": ok, "auditoria": True,
                                                                  "urgencia": True, "tipo": True},
            "obtenido": {"destino_principal": destino, "modelo": modelo}, "segundos": 1.0}


def guardar_corrida(directorio, nombre, datos):
    carpeta = directorio / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "resultados.json").write_text(json.dumps(datos), encoding="utf-8")


def test_resumen_por_tipo_categoria_y_fallos():
    plan = {f["id"]: f for f in __import__("csv").DictReader(PLAN.splitlines())}
    variantes = [
        variante("GS-01", "GS-01.txt", destino="Farmacia_Hospitalaria", modelo="deepseek/deepseek-chat"),
        variante("GS-01", "GS-01_foto.png", clase="imagen", modelo="gemini/gemini-2.5-flash"),
        variante("GS-06", "GS-06.txt", ok=False, destino="Farmacia_Hospitalaria",
                 aciertos={"destino": False, "categoria_amb": False, "auditoria": True, "urgencia": True}),
        variante("GS-12", "GS-12_escaneado.png", clase="imagen", ok=False, destino="Farmacia_Hospitalaria",
                 aciertos={"destino": False, "auditoria": False, "urgencia": True}),
        variante("GS-07", "GS-07.txt", ok=False, error="RuntimeError: todos los modelos fallaron", aciertos={}),
    ]
    r = metricas.resumen_evaluacion("2026-10-13_deepseek", corrida(variantes), plan, ["2026-10-13_deepseek"])
    por_tipo = {f["tipo"]: f for f in r["por_tipo"]}
    # la imagen severa no cuenta en el acierto por tipo, y el error de ejecución tampoco
    assert por_tipo["Receta Medica"] == {"tipo": "Receta Medica", "variantes": 3, "destino_ok": 2, "tipo_ok": 3}
    assert "Informe de Estudio por Imagenes" not in por_tipo
    categorias = {c["nombre"]: c["casos"] for c in r["fallos_por_categoria"]}
    assert categorias == {"AMB-3": ["GS-06"], "legibilidad severa": ["GS-12 (severa)"], "urgencia": ["GS-07"]}
    campos = {c["nombre"]: c["cantidad"] for c in r["fallos_por_campo"]}
    assert campos["destino"] == 2 and campos["error de ejecución"] == 1
    assert {m["nombre"]: m["cantidad"] for m in r["modelos"]} == {"deepseek/deepseek-chat": 1,
                                                                  "gemini/gemini-2.5-flash": 1}
    recall = next(m for m in r["metricas"] if m["clave"] == "recall_urgencias")
    assert recall["valor"] == 1.0 and recall["aciertos"] == 1
    assert r["falsas_urgencias"] == 1 and r["latencia_p95"] == "8.0 s"


def test_get_evaluacion_sin_corridas_es_404(cliente):
    assert cliente.get("/metrics/evaluacion").status_code == 404


def test_get_evaluacion_la_mas_reciente_o_la_pedida(cliente, tmp_path):
    (tmp_path / "plan_golden.csv").write_text(PLAN, encoding="utf-8")
    guardar_corrida(tmp_path / "resultados", "2026-10-13_deepseek", corrida([variante("GS-01", "GS-01.txt")]))
    guardar_corrida(tmp_path / "resultados", "2026-10-14_gemini", corrida([variante("GS-01", "GS-01.txt")] * 2))
    (tmp_path / "resultados" / "README.md").write_text("no es una corrida", encoding="utf-8")

    datos = cliente.get("/metrics/evaluacion").json()
    assert datos["corrida"] == "2026-10-14_gemini"
    assert datos["corridas"] == ["2026-10-14_gemini", "2026-10-13_deepseek"]
    assert datos["variantes"] == 2

    pedida = cliente.get("/metrics/evaluacion", params={"corrida": "2026-10-13_deepseek"}).json()
    assert pedida["variantes"] == 1


def test_get_evaluacion_no_sale_de_la_carpeta(cliente, tmp_path):
    guardar_corrida(tmp_path / "resultados", "2026-10-13_deepseek", corrida([]))
    guardar_corrida(tmp_path, "secreto", corrida([]))
    assert cliente.get("/metrics/evaluacion", params={"corrida": "../secreto"}).status_code == 404
    assert cliente.get("/metrics/evaluacion", params={"corrida": "no-existe"}).status_code == 404


def test_sin_base_de_zonas_horarias_usa_utc_menos_3(monkeypatch):
    """La imagen python:slim no trae tzdata: la API tiene que arrancar igual, con la hora de Argentina."""
    def sin_tzdata(nombre):
        raise metricas.ZoneInfoNotFoundError(nombre)
    monkeypatch.setattr(metricas, "ZoneInfo", sin_tzdata)
    zona = metricas._zona("America/Argentina/Buenos_Aires")
    assert str(zona) == "America/Argentina/Buenos_Aires"
    assert datetime(2026, 1, 15, 12, tzinfo=zona).utcoffset() == timedelta(hours=-3)
