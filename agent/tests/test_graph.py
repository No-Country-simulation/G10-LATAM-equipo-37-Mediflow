import json
from pathlib import Path

from agent.graph import run_triage

EJEMPLO = json.loads((Path(__file__).parents[2] / "docs" / "examples" / "triage_request.json").read_text())


def test_ejemplo_del_brief_va_a_emergencia():
    resultado = run_triage(
        EJEMPLO["documento_id"], EJEMPLO["tipo_archivo"], EJEMPLO["documento_texto"], EJEMPLO["canal_origen"]
    )
    assert resultado["clasificacion"]["tipo_documento"] == "Informe de Estudio por Imagenes"
    assert resultado["urgencia"]["detectada"] is True
    assert resultado["decision"]["destino_principal"] == "Cola_Emergencia_Medica"
    assert resultado["decision"]["notificacion_generada"] is not None
    assert resultado["almacenamiento"]["ruta_objeto"].startswith("procesados/urgentes/")
    assert [t["nodo"] for t in resultado["trace"]][0] == "normalizar"


def test_documento_vacio_va_a_revision_humana():
    resultado = run_triage("DOC-VACIO", "IMAGEN", "", "test")
    assert resultado["decision"]["destino_principal"] == "Cola_Revision_Humana"
    assert resultado["decision"]["requiere_auditoria_humana"] is True
