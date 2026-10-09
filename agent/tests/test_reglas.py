import copy

import pytest

from agent.rules import loader


@pytest.mark.parametrize("clave,valor", [
    ("deteccion_automatica_urgencia", "x"),
    ("deteccion_automatica_urgencia", ["a"]),
    ("deteccion_automatica_urgencia", 5),
    ("valores_criticos_laboratorio", 5),
    ("valores_criticos_laboratorio", "texto"),
    ("valores_criticos_laboratorio", {"a": 1}),
    ("valores_criticos_laboratorio", ["x", 3]),
])
def test_validar_tipos_raros_devuelve_errores(clave, valor):
    reglas = copy.deepcopy(loader.load_rules())
    reglas[clave] = valor
    assert loader.validar_reglas(reglas)


def _reglas_con_cambio():
    reglas = copy.deepcopy(loader.load_rules())
    reglas["tipos_documento"] = reglas["tipos_documento"] + ["tipo_nuevo"]
    return reglas


def test_guardar_escribe_override_y_auditoria(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "OVERRIDE_PATH", tmp_path / "rules.override.yaml")
    monkeypatch.setattr(loader, "AUDIT_PATH", tmp_path / "rules.audit.jsonl")

    cambios = loader.guardar_reglas(_reglas_con_cambio(), "test")

    assert cambios
    assert loader.OVERRIDE_PATH.exists()
    assert len(loader.AUDIT_PATH.read_text(encoding="utf-8").splitlines()) == 1


def test_si_falla_la_auditoria_no_queda_el_override(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "OVERRIDE_PATH", tmp_path / "rules.override.yaml")
    monkeypatch.setattr(loader, "AUDIT_PATH", tmp_path / "rules.audit.jsonl")

    def falla(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(loader, "_registrar", falla)
    with pytest.raises(OSError):
        loader.guardar_reglas(_reglas_con_cambio(), "test")
    assert not loader.OVERRIDE_PATH.exists()


def test_validar_no_depende_de_listas_de_texto(monkeypatch):
    # Con LISTAS_DE_TEXTO vacío, du y valores_criticos deben validarse igual
    monkeypatch.setattr(loader, "LISTAS_DE_TEXTO", ())
    reglas = copy.deepcopy(loader.load_rules())
    assert loader.validar_reglas(reglas) == []
    reglas["deteccion_automatica_urgencia"] = "x"
    assert loader.validar_reglas(reglas)
