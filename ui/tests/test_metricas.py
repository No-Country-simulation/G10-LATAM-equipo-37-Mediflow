"""Pruebas del dashboard (N3-04): la lógica de ui/metricas.py y la página 5_Metricas.py con el AppTest de Streamlit.

Ninguna prueba sale a la red: la API se reemplaza por un transporte simulado de httpx.
"""
import sys
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

UI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI))

import metricas as met  # noqa: E402

PAGINA = str(UI / "pages" / "5_Metricas.py")

OPERACION = {
    "hoy": "2026-10-13", "zona_horaria": "America/Argentina/Buenos_Aires",
    "documentos_total": 12, "documentos_hoy": 5, "urgencias_total": 3, "urgencias_hoy": 1,
    "en_revision": 2, "con_auditoria": 4, "tasa_revision_humana": 0.3333, "confianza_media": 0.8123,
    "por_destino": [{"nombre": "Farmacia_Hospitalaria", "cantidad": 6},
                    {"nombre": "Cola_Emergencia_Medica", "cantidad": 3}],
    "por_tipo": [{"nombre": "Receta Medica", "cantidad": 7}],
    "franjas_confianza": [{"nombre": "automatico", "desde": 0.85, "cantidad": 8},
                          {"nombre": "segunda_opinion", "desde": 0.6, "cantidad": 3},
                          {"nombre": "revision", "desde": 0.0, "cantidad": 1}],
    "modelos": [{"nombre": "deepseek/deepseek-chat", "cantidad": 11}],
    "alertas": [{"documento_id": "GS-07", "fecha": "2026-10-13T14:05:00-03:00",
                 "destino": "Cola_Emergencia_Medica", "tipo": "Informe de Estudio por Imagenes",
                 "canal": "registro_local"}],
}

EVALUACION = {
    "corrida": "2026-10-13_deepseek", "corridas": ["2026-10-13_deepseek", "2026-10-12_gemini"],
    "fecha": "2026-10-13T15:00:00", "simulado": False, "variantes": 76, "casos_con_error": 0,
    "falsas_urgencias": 2, "latencia_p50": "3.1 s", "latencia_p95": "7.9 s",
    "metricas": [{"clave": "recall_urgencias", "nombre": "Recall de urgencias", "texto": "100 % (9/9)",
                  "valor": 1.0, "aciertos": 9, "total": 9},
                 {"clave": "accuracy_destino", "nombre": "Destino", "texto": "80 % (40/50)",
                  "valor": 0.8, "aciertos": 40, "total": 50}],
    "por_tipo": [{"tipo": "Receta Medica", "variantes": 10, "destino_ok": 9, "tipo_ok": 10}],
    "fallos_por_campo": [{"nombre": "destino", "cantidad": 1}],
    "fallos_por_categoria": [{"nombre": "AMB-3", "cantidad": 1, "casos": ["GS-06"]}],
    "modelos": [{"nombre": "deepseek/deepseek-chat", "cantidad": 76}],
    "fallos": [{"id": "GS-06", "archivo": "GS-06.txt", "categoria": "AMB-3", "campos": ["destino"],
                "esperado_destino": "Cola_Revision_Humana", "obtenido_destino": "Farmacia_Hospitalaria",
                "error": ""}],
}


def transporte(operacion=OPERACION, evaluacion=EVALUACION, caida=False):
    """Una API falsa: /metrics y /metrics/evaluacion (404 si evaluacion es None)."""
    def responder(pedido: httpx.Request) -> httpx.Response:
        if caida:
            raise httpx.ConnectError("sin conexión", request=pedido)
        if pedido.url.path == "/metrics":
            return httpx.Response(200, json=operacion)
        if pedido.url.path == "/metrics/evaluacion":
            if evaluacion is None:
                return httpx.Response(404, json={"detail": "sin corridas"})
            pedida = pedido.url.params.get("corrida")
            return httpx.Response(200, json={**evaluacion, "corrida": pedida or evaluacion["corrida"]})
        return httpx.Response(404)
    return httpx.MockTransport(responder)


@pytest.fixture
def api_falsa(monkeypatch):
    """Reemplaza httpx.get por un cliente con transporte simulado; devuelve la función para configurarlo."""
    def configurar(**kwargs):
        cliente = httpx.Client(transport=transporte(**kwargs))
        monkeypatch.setattr(httpx, "get", lambda url, **kw: cliente.get(url, **kw))
    return configurar


# --------------------------------------------------------------------------- formato
def test_formatos():
    assert met.porcentaje(0.9048) == "90 %"
    assert met.porcentaje(None) == "—" and met.porcentaje(True) == "—"
    assert met.decimal(0.8123) == "0,81"
    assert met.fecha_corta("2026-10-13T14:05:00-03:00") == "13/10 14:05"
    assert met.fecha_corta("no es fecha") == "no es fecha"
    assert met.nombre_corrida("2026-10-13_deepseek") == "13/10/2026 · deepseek"
    assert met.nombre_corrida("sin-fecha") == "sin-fecha"


# --------------------------------------------------------------------------- tablas
def test_tabla_conteo_usa_nombres_legibles_y_tolera_basura():
    df = met.tabla_conteo([{"nombre": "Cola_Emergencia_Medica", "cantidad": 3}, "basura", {"nombre": "X"}],
                          met.DESTINOS)
    assert list(df["cantidad"]) == [3, 0]
    assert df["etiqueta"][0] == met.DESTINOS["Cola_Emergencia_Medica"]
    assert met.tabla_conteo(None, {}).empty


def test_franjas_toman_los_umbrales_de_la_api():
    filas = [{"nombre": "automatico", "desde": 0.9, "cantidad": 3},
             {"nombre": "segunda_opinion", "desde": 0.7, "cantidad": 1},
             {"nombre": "revision", "desde": 0.0, "cantidad": 0}]
    assert met.umbrales(filas) == ("0,90", "0,70")
    df = met.tabla_franjas(filas)
    assert list(df["rango"]) == ["≥ 0,90", "0,70 a 0,90", "< 0,70"]
    assert list(df["parte"]) == [0.75, 0.25, 0.0]


def test_alertas_no_muestran_mensaje():
    df = met.tabla_alertas([{**OPERACION["alertas"][0], "mensaje": "Paciente Juan Pérez"}])
    assert list(df.columns) == ["Hora", "Documento", "Tipo", "Destino", "Aviso"]
    assert set(met.AYUDA_ALERTAS) == set(df.columns)
    assert "Juan" not in df.to_string()


def test_por_tipo_y_fallos():
    df = met.tabla_por_tipo(EVALUACION["por_tipo"])
    assert df["acierto"][0] == 0.9 and df["detalle"][0] == "9/10"
    fallos = met.tabla_fallos(EVALUACION["fallos"])
    assert fallos["Qué falló"][0] == "Destino"
    assert set(met.AYUDA_FALLOS) == set(fallos.columns)
    assert met.metrica(EVALUACION, "recall_urgencias")["aciertos"] == 9
    assert met.metrica(EVALUACION, "no_existe") == {}


def test_lectura_en_lenguaje_simple():
    assert met.de_cada_10(0.7) == "Acierta 7 de cada 10"
    assert met.de_cada_10(0.98) == "Acierta 9 de cada 10"  # nunca redondea a «todos» si hubo un error
    assert met.de_cada_10(0.02) == "Acierta 1 de cada 10"
    assert met.de_cada_10(1.0) == "Acierta en todos los casos" and met.de_cada_10(None) == "Sin dato"
    texto = met.resumen_operacion(OPERACION)
    assert "<b>5</b> documentos" in texto and "<b>1</b> era una urgencia" in texto and "<b>2</b> esperan" in texto
    assert met.resumen_operacion({"documentos_total": 0}) == "Todavía no se procesó ningún documento."
    assert "Detectó <b>9 de 9</b> urgencias" in met.resumen_evaluacion_texto(EVALUACION)


def test_tarjeta_explica_y_escapa():
    tarjeta = met.tarjeta_html("Urgencias <hoy>", "3", "en total", que_es="Qué <b>es</b>", fuente="La API",
                               como_leer="Así", estado="critico", texto_estado="Guardia avisada")
    assert "Urgencias &lt;hoy&gt;" in tarjeta and "Qué &lt;b&gt;es&lt;/b&gt;" in tarjeta
    assert "<b>De dónde sale</b>La API" in tarjeta and "<b>Cómo leerlo</b>Así" in tarjeta
    assert 'tabindex="0"' in tarjeta and 'role="tooltip"' in tarjeta  # también con teclado
    assert "Guardia avisada" in tarjeta and met.ESTADOS["critico"]["color"] in tarjeta
    assert "<svg" in tarjeta  # el estado lleva ícono además del color
    con_barra = met.tarjeta_html("X", "70 %", que_es="q", fuente="f", progreso=0.7)
    assert 'width:70.0%' in con_barra and "mf-progreso" not in tarjeta


def test_cada_barra_dice_que_significa_y_de_donde_sale():
    df = met.tabla_conteo(OPERACION["por_destino"], met.DESTINOS, met.SIGNIFICADO_DESTINOS, met.FUENTE_OPERACION)
    assert df["significado"].str.len().gt(0).all() and (df["fuente"] == met.FUENTE_OPERACION).all()
    assert list(df["parte"].round(2)) == [0.67, 0.33]
    titulos = [t["title"] for t in met.barras(df, "Documentos", categoria="Destino").to_dict()["layer"][0]
               ["encoding"]["tooltip"]]
    assert titulos == ["Destino", "Documentos", "Parte del total", "Qué significa", "De dónde sale"]
    assert all(c in met.SIGNIFICADO_CATEGORIAS for c in met.CATEGORIAS)
    assert all(t in met.SIGNIFICADO_TIPOS for t in met.TIPOS)
    assert all(d in met.SIGNIFICADO_DESTINOS for d in met.DESTINOS)
    casos = met.tabla_conteo(EVALUACION["fallos_por_categoria"], met.CATEGORIAS, met.SIGNIFICADO_CATEGORIAS)
    assert casos["casos"][0] == "GS-06"


def test_paneles_vecinos_miden_igual():
    assert met.relleno(5, 7) == 2 * met.ALTO_FILA and met.relleno(7, 5) == 0 and met.relleno(1, 1) == 0


def test_estilos_por_tema():
    claro, oscuro = met.estilos("light"), met.estilos("dark")
    assert met.PALETAS["light"]["panel"] in claro and met.PALETAS["dark"]["panel"] in oscuro
    assert met.estilos(None) == claro  # sin tema conocido, el claro (el de Streamlit por defecto)


# --------------------------------------------------------------------------- gráficos
@pytest.mark.parametrize("tema,color", [("light", "#0b0b0b"), ("dark", "#f0efec"), (None, "#7a7974")])
def test_texto_de_las_barras_sigue_el_tema(tema, color):
    grafico = met.barras(met.tabla_conteo(OPERACION["por_destino"], met.DESTINOS), "Documentos", tema=tema)
    capas = grafico.to_dict()["layer"]
    assert capas[0]["mark"]["color"] == met.AZUL
    assert capas[1]["mark"]["color"] == color


def test_franjas_en_la_rampa_ordinal():
    grafico = met.barras_franjas(met.tabla_franjas(OPERACION["franjas_confianza"]), tema="light")
    escala = grafico.to_dict()["layer"][0]["encoding"]["color"]["scale"]
    assert escala["range"] == met.RAMPA_FRANJAS


# --------------------------------------------------------------------------- API
def test_obtener_operacion_y_evaluacion():
    cliente = httpx.Client(transport=transporte())
    assert met.obtener_operacion("http://api", cliente)["documentos_total"] == 12
    assert met.obtener_evaluacion("http://api", "2026-10-12_gemini", cliente)["corrida"] == "2026-10-12_gemini"


def test_evaluacion_sin_corridas_es_none_y_api_caida_es_error():
    assert met.obtener_evaluacion("http://api", cliente=httpx.Client(transport=transporte(evaluacion=None))) is None
    with pytest.raises(met.ErrorApi):
        met.obtener_operacion("http://api", httpx.Client(transport=transporte(caida=True)))


# --------------------------------------------------------------------------- página
def correr_pagina() -> AppTest:
    app = AppTest.from_file(PAGINA, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    return app


def html_de(app: AppTest) -> str:
    return " ".join(m.value for m in app.markdown)


def test_pagina_con_datos(api_falsa):
    api_falsa()
    app = correr_pagina()
    pagina = html_de(app)
    assert "Documentos hoy" in pagina and 'mf-valor">5<' in pagina
    assert "Urgencias detectadas" in pagina and 'mf-valor">100 %<' in pagina
    assert "Objetivo 100 % cumplido" in pagina and "7,9 s" in pagina
    assert "API en línea" in pagina and "Resumen de hoy" in pagina
    assert "Hoy llegaron <b>5</b> documentos" in pagina
    assert pagina.count('role="group"') == 12  # 5 de operación + 7 de evaluación, todas con explicación
    assert pagina.count("De dónde sale") == 19  # las 12 tarjetas y los 7 paneles
    assert len(app.selectbox) == 1  # hay dos corridas: aparece el selector


def test_pagina_sin_corridas_ni_documentos(api_falsa):
    api_falsa(operacion={**OPERACION, "documentos_total": 0, "documentos_hoy": 0}, evaluacion=None)
    app = correr_pagina()
    pagina = html_de(app)
    assert "Todavía no hay documentos procesados" in pagina and "Todavía no hay una evaluación" in pagina
    assert "Todavía no se procesó ningún documento." in pagina


def test_pagina_con_api_caida(api_falsa):
    api_falsa(caida=True)
    app = correr_pagina()
    pagina = html_de(app)
    assert "Sin conexión con la API" in pagina
    assert "No se pudo leer la operación" in pagina and "No se pudo leer la evaluación" in pagina
