"""
agent/tests/test_local_audit.py

Cubre el "Listo cuando" de N2-04: aprobar, corregir o rechazar queda registrado
con quién (revisor), cuándo (fecha) y por qué (motivo). Usa un directorio temporal
(pytest tmp_path) en vez de tocar ./data/ real.
"""

import json

import pytest

from agent.storage.local_audit import (
    AccionInvalida,
    DocumentoNoEncontrado,
    ResolucionYaExiste,
    guardar_extraccion,
    guardar_resolucion,
    listar_cola_humana,
)


def test_cola_vacia_al_inicio(tmp_path):
    assert listar_cola_humana(base=tmp_path) == []


def test_documento_aparece_en_cola_tras_extraccion(tmp_path):
    guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    cola = listar_cola_humana(base=tmp_path)
    assert len(cola) == 1
    assert cola[0]["documento_id"] == "DOC-001"
    assert cola[0]["extraccion"]["tipo_documento"] == "Receta Medica"


def test_guardar_resolucion_aprobar_registra_quien_cuando_y_porque(tmp_path):
    guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    resolucion = guardar_resolucion(
        "DOC-001", "aprobar", revisor="Carolina", motivo="Datos correctos", base=tmp_path
    )
    assert resolucion["revisor"] == "Carolina"
    assert resolucion["accion"] == "aprobar"
    assert resolucion["motivo"] == "Datos correctos"
    assert "fecha" in resolucion


def test_documento_desaparece_de_cola_tras_resolucion(tmp_path):
    guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    guardar_resolucion("DOC-001", "aprobar", revisor="Carolina", motivo="ok", base=tmp_path)
    assert listar_cola_humana(base=tmp_path) == []


def test_accion_invalida_se_rechaza(tmp_path):
    guardar_extraccion("DOC-002", {"tipo_documento": "Epicrisis"}, base=tmp_path)
    with pytest.raises(AccionInvalida):
        guardar_resolucion("DOC-002", "aprobar_mal", revisor="X", motivo="Y", base=tmp_path)


def test_documento_no_encontrado(tmp_path):
    with pytest.raises(DocumentoNoEncontrado):
        guardar_resolucion("DOC-INEXISTENTE", "aprobar", revisor="X", motivo="Y", base=tmp_path)


def test_no_permite_doble_resolucion(tmp_path):
    guardar_extraccion("DOC-002", {"tipo_documento": "Epicrisis"}, base=tmp_path)
    guardar_resolucion("DOC-002", "corregir", revisor="Carolina", motivo="Falta matricula", base=tmp_path)
    with pytest.raises(ResolucionYaExiste):
        guardar_resolucion("DOC-002", "rechazar", revisor="Carolina", motivo="otra vez", base=tmp_path)


def test_correcciones_se_persisten(tmp_path):
    guardar_extraccion("DOC-002", {"tipo_documento": "Epicrisis"}, base=tmp_path)
    guardar_resolucion(
        "DOC-002",
        "corregir",
        revisor="Carolina",
        motivo="Falta matricula",
        correcciones={"medico_solicitante.matricula": "12345"},
        base=tmp_path,
    )
    resolucion = json.loads((tmp_path / "DOC-002" / "resolucion.json").read_text(encoding="utf-8"))
    assert resolucion["correcciones"] == {"medico_solicitante.matricula": "12345"}


def test_rechazar_es_una_accion_valida_no_un_destino(tmp_path):
    """ADR-004: Rechazado no es un destino del agente, es una acción del auditor."""
    guardar_extraccion("DOC-003", {"tipo_documento": "Otro"}, base=tmp_path)
    resolucion = guardar_resolucion(
        "DOC-003", "rechazar", revisor="Carolina", motivo="Fuera de alcance", base=tmp_path
    )
    assert resolucion["accion"] == "rechazar"


def test_cola_ignora_carpetas_sin_extraccion(tmp_path):
    (tmp_path / "DOC-004").mkdir(parents=True)  # carpeta vacía, sin extraccion.json
    assert listar_cola_humana(base=tmp_path) == []

def test_data_dir_por_defecto_sigue_el_layout_de_local():
    from agent.storage import local, local_audit

    assert local_audit.DATA_DIR == local.DATA_DIR / local_audit.BUCKET / "auditoria_humana"


def test_la_cola_lee_lo_que_escribe_local(tmp_path, monkeypatch):
    from agent.storage import local

    monkeypatch.setattr(local, "DATA_DIR", tmp_path)
    local.upload_json("bucket-x", "auditoria_humana/DOC-9/extraccion.json", {"tipo_documento": "Receta Medica"})
    cola = listar_cola_humana(base=tmp_path / "bucket-x" / "auditoria_humana")
    assert [c["documento_id"] for c in cola] == ["DOC-9"]