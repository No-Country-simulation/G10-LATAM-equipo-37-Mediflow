"""Los catálogos de validar.py se encuentran sin importar desde qué carpeta se ejecuta."""
from pathlib import Path

from agent.nodes import validar


def test_rutas_de_catalogos_son_absolutas_y_existen():
    for ruta in (validar.MEDICAMENTOS_PATH, validar.CIE10_PATH):
        assert ruta.is_absolute()
        assert ruta.exists()


def test_cargar_catalogos_desde_otro_directorio(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(validar, "_medicamentos_cache", None)
    monkeypatch.setattr(validar, "_cie10_cache", None)
    assert len(validar._cargar_medicamentos()) > 0
    assert len(validar._cargar_cie10()) > 0
