"""Tests de los KPIs del reporte diario (N3-05)."""

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone

from agent.llm.adapter import LLMResult
from agent.storage import triage_results
from worker import main as worker
from worker import reporte

TZ = timezone(timedelta(hours=-3))  # el día local 15/10 va de 03:00 UTC del 15 a 03:00 UTC del 16


def _insertar(db, doc_id, destino, score, creado_utc, tipo="Receta Medica", auditoria=False):
    resultado = {
        "documento_id": doc_id,
        "clasificacion": {"tipo_documento": tipo},
        "decision_enrutamiento": {"destino_principal": destino, "requiere_auditoria_humana": auditoria},
        "score_confianza": score,
    }
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO triage_results (documento_id, destino, score, resultado_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (doc_id, destino, score, json.dumps(resultado), creado_utc),
        )


def _db(tmp_path):
    db = tmp_path / "t.sqlite3"
    triage_results._conectar(db).close()  # crea la tabla con el esquema real
    return db


def test_sin_base_devuelve_ceros(tmp_path):
    kpis = reporte.kpis_del_dia(date(2026, 10, 15), TZ, tmp_path / "no_existe.sqlite3")
    assert kpis["total"] == 0
    assert kpis["confianza_media"] is None
    assert kpis["tasa_revision"] == 0.0


def test_cuenta_destinos_y_promedia(tmp_path):
    db = _db(tmp_path)
    _insertar(db, "a", "Cola_Emergencia_Medica", 0.90, "2026-10-15 12:00:00")
    _insertar(db, "b", "Cola_Revision_Humana", 0.50, "2026-10-15 13:00:00", auditoria=True)
    _insertar(db, "c", "Farmacia_Hospitalaria", 0.80, "2026-10-15 14:00:00", tipo="Receta Medica")
    _insertar(db, "d", "Historia_Clinica_Electronica", 0.60, "2026-10-15 15:00:00", tipo="Epicrisis")

    kpis = reporte.kpis_del_dia(date(2026, 10, 15), TZ, db)

    assert kpis["total"] == 4
    assert kpis["urgencias"] == 1
    assert kpis["en_revision"] == 1
    assert kpis["requieren_auditoria"] == 1
    assert kpis["tasa_revision"] == 0.25
    assert kpis["confianza_media"] == 0.7
    assert kpis["por_destino"]["Farmacia_Hospitalaria"] == 1
    assert kpis["por_tipo"]["Epicrisis"] == 1


def test_respeta_el_limite_del_dia_local(tmp_path):
    db = _db(tmp_path)
    _insertar(db, "antes", "Farmacia_Hospitalaria", 0.9, "2026-10-15 02:59:59")  # 23:59 del 14 local
    _insertar(db, "inicio", "Farmacia_Hospitalaria", 0.9, "2026-10-15 03:00:00")  # 00:00 del 15 local
    _insertar(db, "ultimo", "Farmacia_Hospitalaria", 0.9, "2026-10-16 02:59:59")  # 23:59 del 15 local
    _insertar(db, "despues", "Farmacia_Hospitalaria", 0.9, "2026-10-16 03:00:00")  # 00:00 del 16 local

    assert reporte.kpis_del_dia(date(2026, 10, 15), TZ, db)["total"] == 2


KPIS = {
    "fecha": "2026-10-15",
    "total": 4,
    "urgencias": 1,
    "en_revision": 1,
    "requieren_auditoria": 1,
    "tasa_revision": 0.25,
    "confianza_media": 0.7,
    "por_destino": {"Farmacia_Hospitalaria": 1, "Cola_Revision_Humana": 1},
    "por_tipo": {"Receta Medica": 2},
}
CINCO_LINEAS = "\n".join(
    [
        "Se procesaron 4 documentos.",
        "Hubo 1 urgencia.",
        "Un caso fue a revisión.",
        "Confianza 0.70.",
        "Sin otras novedades.",
    ]
)


def _con_llm(monkeypatch, texto=None, error=None):
    monkeypatch.setenv("USE_LLM", "true")

    def falso(prompt, **kwargs):
        if error:
            raise error
        return LLMResult(text=texto, model="groq/qwen", latency_ms=1)

    monkeypatch.setattr(reporte, "complete", falso)


def test_plantilla_tiene_cinco_lineas_y_las_cifras():
    texto = reporte.resumen_plantilla(KPIS)
    assert len(texto.splitlines()) == 5
    assert "4 documentos" in texto and "25%" in texto


def test_plantilla_sin_documentos():
    texto = reporte.resumen_plantilla({**KPIS, "total": 0, "por_destino": {}})
    assert len(texto.splitlines()) == 5
    assert "No se procesaron documentos" in texto


def test_sin_use_llm_no_llama_al_modelo(monkeypatch):
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.setattr(reporte, "complete", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe llamar")))
    assert reporte.redactar_resumen(KPIS)[1] == "plantilla"


def test_usa_el_resumen_del_modelo_si_cumple_el_formato(monkeypatch):
    _con_llm(monkeypatch, texto=CINCO_LINEAS)
    assert reporte.redactar_resumen(KPIS) == (CINCO_LINEAS, "groq/qwen")


def test_cae_a_la_plantilla_si_el_modelo_falla(monkeypatch):
    _con_llm(monkeypatch, error=RuntimeError("429"))
    assert reporte.redactar_resumen(KPIS) == (reporte.resumen_plantilla(KPIS), "plantilla")


def test_cae_a_la_plantilla_si_no_son_cinco_lineas(monkeypatch):
    _con_llm(monkeypatch, texto="Se procesaron 4 documentos.\nTodo bien.")
    assert reporte.redactar_resumen(KPIS)[1] == "plantilla"


def test_cae_a_la_plantilla_si_no_menciona_el_total(monkeypatch):
    _con_llm(monkeypatch, texto="a\nb\nc\nd\ne")
    assert reporte.redactar_resumen(KPIS)[1] == "plantilla"


class AlmacenFalso:
    """Imita el módulo de almacenamiento (local u OCI) con un diccionario."""

    def __init__(self):
        self.archivos = {}

    def list_prefix(self, bucket, prefijo):
        return [r for (b, r) in self.archivos if b == bucket and r.startswith(prefijo)]

    def upload_json(self, bucket, ruta, obj):
        self.archivos[(bucket, ruta)] = obj


UTC = timezone.utc


def test_antes_de_la_hora_no_genera(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_LLM", "false")
    almacen = AlmacenFalso()
    ahora = datetime(2026, 10, 16, 9, 59, tzinfo=UTC)  # 06:59 en UTC-3
    assert reporte.generar_reporte_diario(ahora, almacen, "b", tmp_path / "x.sqlite3", "07:00") == "temprano"
    assert almacen.archivos == {}


def test_genera_el_reporte_del_dia_anterior(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_LLM", "false")
    almacen = AlmacenFalso()
    ahora = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)  # 07:00 en UTC-3
    assert reporte.generar_reporte_diario(ahora, almacen, "b", tmp_path / "x.sqlite3", "07:00") == "generado"
    guardado = almacen.archivos[("b", "reportes/diario/2026-10-15.json")]
    assert guardado["fecha"] == "2026-10-15"
    assert guardado["redactado_por"] == "plantilla"
    assert len(guardado["resumen"].splitlines()) == 5


def test_no_repite_un_reporte_que_ya_existe(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_LLM", "false")
    almacen = AlmacenFalso()
    ahora = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    reporte.generar_reporte_diario(ahora, almacen, "b", tmp_path / "x.sqlite3", "07:00")
    assert reporte.generar_reporte_diario(ahora, almacen, "b", tmp_path / "x.sqlite3", "07:00") == "ya_existia"
    assert len(almacen.archivos) == 1


def _reiniciar_worker():
    worker._estado_reporte.update(dia=None, intentos=0, listo=False)


def test_worker_marca_el_dia_como_listo_y_no_repite(monkeypatch):
    _reiniciar_worker()
    llamadas = []
    monkeypatch.setattr(worker.reporte, "generar_reporte_diario", lambda *a, **k: llamadas.append(1) or "generado")
    worker.reporte_diario()
    worker.reporte_diario()
    assert len(llamadas) == 1


def test_worker_no_marca_listo_si_aun_es_temprano(monkeypatch):
    _reiniciar_worker()
    llamadas = []
    monkeypatch.setattr(worker.reporte, "generar_reporte_diario", lambda *a, **k: llamadas.append(1) or "temprano")
    worker.reporte_diario()
    worker.reporte_diario()
    assert len(llamadas) == 2


def test_worker_deja_de_reintentar_tras_tres_fallos(monkeypatch):
    _reiniciar_worker()
    llamadas = []

    def falla(*a, **k):
        llamadas.append(1)
        raise RuntimeError("storage caído")

    monkeypatch.setattr(worker.reporte, "generar_reporte_diario", falla)
    for _ in range(5):
        try:
            worker.reporte_diario()
        except RuntimeError:
            pass
    assert len(llamadas) == worker.MAX_INTENTOS_REPORTE
