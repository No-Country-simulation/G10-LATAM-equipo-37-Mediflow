"""Pruebas de la página de carga: el ID que escribe la persona no se pierde al enviar el formulario.

Ninguna prueba sale a la red: sin archivo seleccionado la página no llama a la API.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGINA = str(Path(__file__).resolve().parents[1] / "pages" / "1_Carga.py")


def _campo_id(at: AppTest):
    return next(t for t in at.text_input if t.label == "ID del documento")


def _enviar(at: AppTest) -> None:
    next(b for b in at.button if b.label == "Procesar documento").click()
    at.run()


def test_el_id_por_defecto_tiene_el_formato_esperado():
    at = AppTest.from_file(PAGINA).run()
    assert not at.exception
    assert _campo_id(at).value.startswith("DOC-UI-")


def test_el_id_escrito_se_conserva_al_enviar():
    at = AppTest.from_file(PAGINA).run()
    _campo_id(at).set_value("ENSAYO-GS07-CO")
    _enviar(at)  # sin archivo: la página avisa y no llama a la API
    assert not at.exception
    assert _campo_id(at).value == "ENSAYO-GS07-CO"
