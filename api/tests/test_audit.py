"""
api/tests/test_audit.py

Prueba los endpoints reales sobre HTTP con TestClient, monkeypatcheando el
directorio base de agent.storage.local_audit para no tocar ./data/ real.
Sigue el mismo patrón que api/tests/test_api.py (TestClient(app)).
"""

import json

from fastapi.testclient import TestClient

from agent.storage import local_audit
from api.main import app

client = TestClient(app)


def test_cola_vacia_al_inicio(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    r = client.get("/queue/human")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_documento_aparece_en_cola(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)

    r = client.get("/queue/human")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["documento_id"] == "DOC-001"


def test_auditar_aprobar_devuelve_200_y_registra_resolucion(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)

    r = client.post(
        "/audit/DOC-001",
        json={"accion": "aprobar", "revisor": "Carolina", "motivo": "Datos correctos"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["documento_id"] == "DOC-001"
    assert cuerpo["resolucion"]["accion"] == "aprobar"
    assert cuerpo["resolucion"]["revisor"] == "Carolina"
    assert "fecha" in cuerpo["resolucion"]


def test_auditar_documento_inexistente_da_404(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    r = client.post(
        "/audit/NO-EXISTE",
        json={"accion": "aprobar", "revisor": "Carolina", "motivo": "x"},
    )
    assert r.status_code == 404


def test_auditar_accion_invalida_da_422(tmp_path, monkeypatch):
    """FastAPI/Pydantic rechaza el body antes de llegar a la lógica, por el
    Literal["aprobar", "corregir", "rechazar"] del schema."""
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.post(
        "/audit/DOC-001",
        json={"accion": "aprobar_mal", "revisor": "Carolina", "motivo": "x"},
    )
    assert r.status_code == 422


def test_auditar_dos_veces_el_mismo_documento_da_409(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    client.post("/audit/DOC-001", json={"accion": "aprobar", "revisor": "Carolina", "motivo": "ok"})

    r = client.post("/audit/DOC-001", json={"accion": "rechazar", "revisor": "Carolina", "motivo": "otra vez"})
    assert r.status_code == 409


def test_auditar_corregir_con_correcciones(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-002", {"tipo_documento": "Epicrisis"}, base=tmp_path)

    r = client.post(
        "/audit/DOC-002",
        json={
            "accion": "corregir",
            "revisor": "Carolina",
            "motivo": "Falta matricula",
            "correcciones": {"medico_solicitante.matricula": "12345"},
        },
    )
    assert r.status_code == 200
    assert r.json()["resolucion"]["correcciones"] == {"medico_solicitante.matricula": "12345"}


def test_documento_resuelto_desaparece_de_la_cola(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-001", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    client.post("/audit/DOC-001", json={"accion": "aprobar", "revisor": "Carolina", "motivo": "ok"})

    r = client.get("/queue/human")
    assert r.json() == {"items": []}

def test_auditar_rechaza_revisor_vacio(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-010", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.post("/audit/DOC-010", json={"accion": "aprobar", "revisor": "", "motivo": "ok"})
    assert r.status_code == 422
    assert not (tmp_path / "DOC-010" / "resolucion.json").exists()


def test_auditar_rechaza_motivo_solo_espacios(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-011", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.post("/audit/DOC-011", json={"accion": "aprobar", "revisor": "Ana", "motivo": "   "})
    assert r.status_code == 422
    assert not (tmp_path / "DOC-011" / "resolucion.json").exists()


def test_auditar_rechaza_correcciones_si_la_accion_no_es_corregir(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-012", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.post(
        "/audit/DOC-012",
        json={"accion": "aprobar", "revisor": "Ana", "motivo": "ok", "correcciones": {"paciente.nombre": "X"}},
    )
    assert r.status_code == 422
    assert not (tmp_path / "DOC-012" / "resolucion.json").exists()


def test_auditar_corregir_acepta_correcciones(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-013", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.post(
        "/audit/DOC-013",
        json={
            "accion": "corregir",
            "revisor": "Ana",
            "motivo": "falta matrícula",
            "correcciones": {"matricula": "123"},
        },
    )
    assert r.status_code == 200
    assert r.json()["resolucion"]["correcciones"] == {"matricula": "123"}

def test_original_devuelve_el_pdf_con_su_tipo(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-020", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    (tmp_path / "DOC-020" / "original").write_bytes(b"%PDF-1.4 contenido")
    r = client.get("/audit/DOC-020/original")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-1.4 contenido"


def test_original_texto_plano_por_defecto(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-021", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    (tmp_path / "DOC-021" / "original.txt").write_text("Receta de prueba", encoding="utf-8")
    r = client.get("/audit/DOC-021/original")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")


def test_original_inexistente_devuelve_404(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    r = client.get("/audit/DOC-NO-EXISTE/original")
    assert r.status_code == 404


def test_original_no_guardado_devuelve_404(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    local_audit.guardar_extraccion("DOC-022", {"tipo_documento": "Receta Medica"}, base=tmp_path)
    r = client.get("/audit/DOC-022/original")
    assert r.status_code == 404

def test_auditar_sin_correcciones_guarda_null(tmp_path, monkeypatch):
    monkeypatch.setattr(local_audit, "DATA_DIR", tmp_path)
    for doc_id, accion, correcciones in [
        ("DOC-020", "aprobar", None),
        ("DOC-021", "aprobar", {}),
        ("DOC-022", "rechazar", None),
    ]:
        local_audit.guardar_extraccion(doc_id, {"tipo_documento": "Receta Medica"}, base=tmp_path)
        r = client.post(
            f"/audit/{doc_id}",
            json={"accion": accion, "revisor": "Ana", "motivo": "ok", "correcciones": correcciones},
        )
        assert r.status_code == 200
        assert r.json()["resolucion"]["correcciones"] is None
        guardada = json.loads((tmp_path / doc_id / "resolucion.json").read_text(encoding="utf-8"))
        assert guardada["correcciones"] is None
