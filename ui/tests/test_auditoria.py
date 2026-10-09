"""Pruebas del panel del auditor: la lógica de ui/auditoria.py y la página, con el AppTest de Streamlit.

Ninguna prueba sale a la red: la API se reemplaza por funciones de prueba o por un transporte simulado.
"""
import copy
import json
import sys
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

UI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI))

import auditoria as aud  # noqa: E402

PAGINA = str(UI / "pages" / "3_Auditoria.py")
EJEMPLOS = {i["documento_id"]: i for i in aud.cargar_ejemplos()}


def ejemplo(documento_id: str) -> dict:
    return copy.deepcopy(EJEMPLOS[documento_id]["extraccion"])


def item(documento_id: str, extraccion: dict) -> dict:
    return aud.normalizar_item({"documento_id": documento_id, "extraccion": extraccion})


def sin_tocar(extraccion: dict, **cambios) -> dict:
    """Lo que devuelven los campos de texto del formulario: lo que mostraban, más lo que se cambió."""
    planos = aud.aplanar(extraccion["datos_extraidos"])
    escritos = {ruta: aud.mostrado(v) for ruta, v in planos.items() if ruta not in aud.LISTAS}
    escritos.update(cambios)
    return escritos


def tabla(extraccion: dict) -> list[dict]:
    """Lo que devuelve la tabla de medicamentos sin tocarla: texto, con celdas vacías, y la fila para agregar."""
    filas = [{c: m[c] or "" for c in aud.COLUMNAS_MEDICAMENTO} for m in
             aud.normalizar_medicamentos(extraccion["datos_extraidos"]["medicamentos"])]
    return [*filas, {c: "" for c in aud.COLUMNAS_MEDICAMENTO}]


# ---------------------------------------------------------------------------
# Ejemplos y lectura de la cola
# ---------------------------------------------------------------------------


def test_los_ejemplos_tienen_la_forma_de_la_cola():
    assert list(EJEMPLOS) == ["GS-06", "GS-14", "GS-26", "M8"]
    for documento_id, elemento in EJEMPLOS.items():
        extraccion = elemento["extraccion"]
        assert extraccion["documento_id"] == documento_id
        assert extraccion["decision_enrutamiento"]["requiere_auditoria_humana"] is True
        assert extraccion["clasificacion"]["tipo_documento"] in aud.TIPOS_DOCUMENTO
        assert extraccion["validacion"]["categoria_amb"] in (None, *aud.CATEGORIAS_AMB)
        assert elemento["original_ruta"] is None or elemento["original_ruta"].exists()


def test_la_cola_pone_primero_las_urgencias():
    cola = aud.ordenar_cola(list(EJEMPLOS.values()))
    assert [i["documento_id"] for i in cola] == ["GS-14", "GS-06", "GS-26", "M8"]
    assert aud.etiqueta_item(cola[0]) == "URGENTE · GS-14 · Informe de Laboratorio · AMB-1"
    assert aud.etiqueta_item(cola[1]) == "GS-06 · Receta Médica · AMB-3"


@pytest.mark.parametrize(
    "documento_id, titulo",
    [
        ("GS-06", "AMB-3 · Dosis fuera de rango o medicamento no identificable"),
        ("GS-26", "AMB-4 · Texto truncado o parcialmente ilegible"),
        ("M8", "Ilegible"),
    ],
)
def test_el_motivo_de_la_revision_queda_a_la_vista(documento_id, titulo):
    extraccion = ejemplo(documento_id)
    justificacion = extraccion["decision_enrutamiento"]["justificacion_enrutamiento"]
    assert aud.motivo_revision(extraccion) == (titulo, justificacion)


def test_fuera_de_alcance_muestra_el_motivo():
    extraccion = {"validacion": {"categoria_amb": "AMB-6", "motivo_fuera_de_alcance": "idioma_no_soportado"}}
    assert aud.motivo_revision(extraccion)[0] == "AMB-6 · Fuera del alcance del agente (idioma_no_soportado)"


def test_alto_riesgo_sin_ambiguedad_tambien_explica_por_que_espera():
    extraccion = {
        "datos_extraidos": {"medicamentos": [{"nombre": "Warfarina", "dosis": "5 mg", "alto_riesgo": True}]},
        "decision_enrutamiento": {"destino_principal": "Farmacia_Hospitalaria", "justificacion_enrutamiento": "x"},
    }
    assert aud.motivo_revision(extraccion) == ("Medicamento de alto riesgo", "x")
    assert aud.medicamentos_de_alto_riesgo(extraccion["datos_extraidos"]["medicamentos"]) == ["Warfarina"]


def test_acepta_los_nombres_del_estado_del_grafo():
    extraccion = {"decision": {"destino_principal": "Cola_Emergencia_Medica"}, "score": 0.7}
    assert aud.es_urgente(extraccion)
    assert aud.score_de(extraccion) == 0.7


def test_una_extraccion_mal_formada_no_rompe_la_cola():
    raro = aud.normalizar_item({
        "documento_id": 7,
        "extraccion": {
            "clasificacion": ["no", "es", "un", "dict"],
            "validacion": {"campos_faltantes": [None, "paciente.nombre"], "conflictos": "texto", "errores": None},
            "datos_extraidos": {"paciente": None, "medicamentos": 3, "estudios_solicitados": "TAC"},
            "evidencias": 3,
            "texto": 5,
        },
    })
    assert raro["documento_id"] == "7"
    extraccion = raro["extraccion"]
    assert extraccion["clasificacion"] == {}
    assert extraccion["validacion"]["campos_faltantes"] == ["paciente.nombre"]
    assert extraccion["validacion"]["conflictos"] == []
    assert extraccion["datos_extraidos"]["paciente"] == {"nombre": None, "edad": None, "fecha_nacimiento": None}
    assert extraccion["datos_extraidos"]["medicamentos"] == []
    assert extraccion["evidencias"] == [] and extraccion["texto"] is None
    assert aud.normalizar_item({"extraccion": {}}) is None
    assert aud.normalizar_item({"documento_id": "X", "extraccion": "texto"})["extraccion"]["clasificacion"] == {}


def test_un_tipo_o_una_categoria_que_no_son_texto_no_rompen_la_cola():
    raro = aud.normalizar_item({"documento_id": "X", "extraccion": {
        "clasificacion": {"tipo_documento": ["Receta Medica"], "nivel_prioridad": {"x": 1}},
        "validacion": {"categoria_amb": ["AMB-1"], "motivo_fuera_de_alcance": 3},
        "decision_enrutamiento": {"destino_principal": ["Cola_Revision_Humana"]},
    }})
    extraccion = raro["extraccion"]
    assert extraccion["clasificacion"] == {"tipo_documento": None, "nivel_prioridad": None}
    assert extraccion["validacion"]["categoria_amb"] is None
    assert extraccion["decision_enrutamiento"]["destino_principal"] is None
    assert aud.etiqueta_item(raro) == "X · Sin clasificar · Revisión pedida por el agente"


def test_el_formulario_muestra_lo_extraido_y_lo_que_falta():
    visibles, vacios, solo_lectura = aud.campos_del_formulario(ejemplo("GS-14"))
    assert visibles[0] == "paciente.nombre"  # falta, y se muestra para completarlo
    assert "medico_solicitante.matricula" in visibles
    assert set(vacios) == {"paciente.edad", "paciente.fecha_nacimiento"}
    assert "medicamentos" not in visibles + vacios and solo_lectura == {}


def test_un_obligatorio_que_la_extraccion_no_trae_tambien_se_muestra():
    extraccion = {
        "datos_extraidos": {"paciente": {"nombre": "Ana"}},
        "validacion": {"campos_faltantes": ["fecha", "medicamentos[0].dosis"]},
    }
    assert aud.campos_del_formulario(extraccion) == (["paciente.nombre", "fecha"], [], {})


def test_un_valor_que_no_es_texto_se_muestra_sin_editar():
    extraccion = {"datos_extraidos": {"hallazgos": ["leucocitosis", "lactato alto"], "dias_reposo": 3}}
    visibles, _, solo_lectura = aud.campos_del_formulario(extraccion)
    assert visibles == ["dias_reposo"]
    assert solo_lectura == {"hallazgos": ["leucocitosis", "lactato alto"]}


def test_evidencias_en_lista_o_en_diccionario():
    assert aud.evidencias_por_campo({"evidencias": [{"campo": "cie10_sugerido", "fragmento": "CIE-10: J03.9"}]}) == {
        "cie10_sugerido": "CIE-10: J03.9"
    }
    assert aud.evidencias_por_campo({"evidencias": {"paciente.nombre": "Paciente: Ana", "fecha": None}}) == {
        "paciente.nombre": "Paciente: Ana"
    }
    assert aud.evidencias_por_campo({"evidencias": [3, {"campo": "x"}]}) == {}


def test_etiquetas_y_nombres_para_la_pantalla():
    assert aud.etiqueta_campo("paciente.nombre") == "Paciente · nombre"
    assert aud.etiqueta_campo("medicamentos[0].dosis") == "Medicamento 1 · dosis"
    assert aud.etiqueta_campo("campo_nuevo") == "Campo nuevo"
    assert aud.nombre_tipo("Certificado Medico") == "Certificado Médico"
    assert aud.nombre_tipo(None) == "Sin clasificar"


def test_el_texto_del_documento_no_se_interpreta_como_markdown():
    assert aud.md("*5* $ [x] <b>") == r"\*5\* \$ \[x\] \<b\>"
    assert aud.md("- Lactato: 3,8") == r"\- Lactato: 3,8"
    assert aud.md("1. Amoxicilina") == r"1\. Amoxicilina"
    assert aud.md("2) Ibuprofeno") == r"2\) Ibuprofeno"
    assert aud.md("---") == r"\-\-\-"


# ---------------------------------------------------------------------------
# Correcciones
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ruta, escrito, esperado",
    [
        ("paciente.edad", " 32 ", 32),
        ("paciente.edad", "", None),
        ("paciente.nombre", "  Ana  ", "Ana"),
        ("paciente.fecha_nacimiento", "1994-06-14", "1994-06-14"),
    ],
)
def test_convertir_al_tipo_del_contrato(ruta, escrito, esperado):
    assert aud.convertir(ruta, escrito) == esperado


@pytest.mark.parametrize(
    "ruta, escrito",
    [
        ("paciente.edad", "32 años"),
        ("paciente.edad", "3.5"),
        ("paciente.fecha_nacimiento", "14/06/1994"),
        ("paciente.fecha_nacimiento", "2026-13-45"),
        ("paciente.fecha_nacimiento", "19940614"),
    ],
)
def test_convertir_rechaza_lo_que_no_cumple(ruta, escrito):
    with pytest.raises(ValueError):
        aud.convertir(ruta, escrito)


def test_sin_cambios_no_hay_correcciones():
    extraccion = ejemplo("GS-06")
    clasificacion = {"tipo_documento": "Receta Medica", "nivel_prioridad": "Rutina"}
    resultado = aud.calcular_correcciones(extraccion, sin_tocar(extraccion), clasificacion, tabla(extraccion), [])
    assert resultado == ({}, [])


def test_un_valor_raro_sin_tocar_no_cuenta_como_cambio_ni_frena_la_decision():
    extraccion = item("X", {"datos_extraidos": {
        "paciente": {"nombre": "Ana", "edad": "68 años", "fecha_nacimiento": "14/06/1994"},
        "medico_solicitante": {"nombre": "Dra. Vera", "matricula": 131795},
        "dias_reposo": 3.0,
    }})["extraccion"]
    correcciones, errores = aud.calcular_correcciones(extraccion, sin_tocar(extraccion))
    assert (correcciones, errores) == ({}, [])
    assert aud.validar_decision("aprobar", "Camila", "", correcciones, errores) == []
    assert aud.validar_decision("rechazar", "Camila", "Ilegible", correcciones, errores) == []


def test_un_formato_invalido_solo_frena_al_corregir():
    extraccion = ejemplo("GS-06")
    correcciones, errores = aud.calcular_correcciones(extraccion, sin_tocar(extraccion, **{"paciente.edad": "abc"}))
    assert correcciones == {} and len(errores) == 1
    assert aud.validar_decision("corregir", "Camila", "Dato", correcciones, errores) == errores
    assert "Cambiaste 1 campo(s)" in aud.validar_decision("aprobar", "Camila", "", correcciones, errores)[0]
    assert aud.validar_decision("rechazar", "Camila", "Ilegible", correcciones, errores) == []


def test_la_misma_edad_escrita_de_otra_forma_no_es_un_cambio():
    extraccion = ejemplo("GS-06")
    assert aud.calcular_correcciones(extraccion, sin_tocar(extraccion, **{"paciente.edad": "032"})) == ({}, [])


def test_corregir_la_dosis_manda_la_lista_entera_sin_alto_riesgo():
    extraccion = ejemplo("GS-06")
    filas = tabla(extraccion)
    filas[0]["dosis"] = "500 mg"
    correcciones, _ = aud.calcular_correcciones(extraccion, sin_tocar(extraccion), None, filas)
    assert correcciones == {
        "medicamentos": [{"nombre": "Amoxicilina", "dosis": "500 mg", "frecuencia": "cada 8 horas", "duracion": None}]
    }


def test_medicamentos_con_numeros_se_comparan_como_texto():
    datos = {"medicamentos": [{"nombre": "Ibuprofeno", "dosis": 400}]}
    extraccion = item("X", {"datos_extraidos": datos})["extraccion"]
    filas = [{"nombre": "Ibuprofeno", "dosis": "400", "frecuencia": "", "duracion": ""}]
    assert aud.calcular_correcciones(extraccion, {}, None, filas) == ({}, [])


def test_completar_un_campo_y_cambiar_la_prioridad():
    extraccion = ejemplo("GS-14")
    escritos = sin_tocar(extraccion, **{"paciente.nombre": "Rodríguez, Ana María"})
    clasificacion = {"tipo_documento": "Informe de Laboratorio", "nivel_prioridad": "Prioritario"}
    correcciones, _ = aud.calcular_correcciones(extraccion, escritos, clasificacion)
    assert correcciones == {"paciente.nombre": "Rodríguez, Ana María", "clasificacion.nivel_prioridad": "Prioritario"}


def test_borrar_un_dato_lo_deja_en_null():
    extraccion = ejemplo("GS-06")
    assert aud.calcular_correcciones(extraccion, sin_tocar(extraccion, cie10_sugerido="   ")) == (
        {"cie10_sugerido": None}, []
    )


def test_estudios_cambiados_van_enteros():
    extraccion = item("X", {"datos_extraidos": {"estudios_solicitados": ["Hemograma"]}})["extraccion"]
    correcciones, _ = aud.calcular_correcciones(extraccion, {}, None, None, ["Hemograma", "Urea"])
    assert correcciones == {"estudios_solicitados": ["Hemograma", "Urea"]}


def test_el_resumen_muestra_antes_y_despues():
    filas = aud.resumen_cambios(
        ejemplo("GS-14"), {"paciente.nombre": "Ana", "clasificacion.tipo_documento": "Certificado Medico"}
    )
    assert filas == [
        {"Campo": "Paciente · nombre", "Antes": "(vacío)", "Después": "Ana"},
        {"Campo": "Tipo de documento", "Antes": "Informe de Laboratorio", "Después": "Certificado Médico"},
    ]


# ---------------------------------------------------------------------------
# Decisión
# ---------------------------------------------------------------------------


def test_aprobar_con_cambios_pide_usar_corregir():
    errores = aud.validar_decision("aprobar", "Camila", "", {"paciente.nombre": "Ana"})
    assert len(errores) == 1 and "«Corregir»" in errores[0]


def test_corregir_sin_cambios_pide_usar_aprobar():
    errores = aud.validar_decision("corregir", "Camila", "motivo", {})
    assert len(errores) == 1 and "«Aprobar»" in errores[0]


def test_sin_revisor_ni_motivo_no_se_envia():
    assert len(aud.validar_decision("rechazar", "  ", "", {})) == 2


def test_aprobar_sin_motivo_deja_el_motivo_de_siempre():
    decision = aud.armar_decision("aprobar", " Camila ", "", {})
    assert decision == {"accion": "aprobar", "revisor": "Camila", "motivo": aud.MOTIVO_APROBAR, "correcciones": None}


def test_solo_corregir_lleva_correcciones():
    assert aud.armar_decision("rechazar", "Camila", "Ilegible", {"paciente.nombre": "Ana"})["correcciones"] is None
    assert aud.armar_decision("corregir", "Camila", "Dato", {"paciente.nombre": "Ana"})["correcciones"] == {
        "paciente.nombre": "Ana"
    }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def cliente(manejador) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_obtener_cola_devuelve_los_elementos_limpios():
    def manejador(peticion):
        assert (peticion.method, peticion.url.path) == ("GET", "/queue/human")
        return httpx.Response(200, json={"items": [{"documento_id": "GS-06", "extraccion": {}}, {"sin": "id"}]})

    cola = aud.obtener_cola("http://api/", cliente(manejador))
    assert [i["documento_id"] for i in cola] == ["GS-06"]
    assert cola[0]["extraccion"]["validacion"]["campos_faltantes"] == []


def test_enviar_decision_devuelve_lo_que_registra_la_api():
    decision = aud.armar_decision("aprobar", "Camila", "", {})

    def manejador(peticion):
        assert (peticion.method, peticion.url.path) == ("POST", "/audit/GS-06")
        return httpx.Response(200, json={"documento_id": "GS-06", "resolucion": json.loads(peticion.content)})

    assert aud.enviar_decision("http://api", "GS-06", decision, cliente(manejador))["resolucion"] == decision


def test_el_id_va_codificado_en_la_ruta():
    rutas = []

    def manejador(peticion):
        rutas.append(peticion.url.raw_path.decode())
        return httpx.Response(200, json={})

    aud.enviar_decision("http://api", "DOC#7/a", {}, cliente(manejador))
    assert rutas == ["/audit/DOC%237%2Fa"]


@pytest.mark.parametrize("codigo, texto", [(404, "ya no está en la cola"), (409, "ya tiene una decisión registrada")])
def test_enviar_decision_explica_404_y_409(codigo, texto):
    respuesta = cliente(lambda peticion: httpx.Response(codigo, json={"detail": "x"}))
    with pytest.raises(aud.ErrorApi, match=texto):
        aud.enviar_decision("http://api", "GS-06", {}, respuesta)


def test_un_422_no_repite_el_contenido_enviado():
    detalle = [{"loc": ["body", "accion"], "msg": "Input should be 'aprobar'", "input": "Paciente Ana Pérez"}]
    respuesta = cliente(lambda peticion: httpx.Response(422, json={"detail": detalle}))
    with pytest.raises(aud.ErrorApi) as error:
        aud.enviar_decision("http://api", "GS-06", {}, respuesta)
    assert "accion: Input should be 'aprobar'" in str(error.value)
    assert "Ana Pérez" not in str(error.value)


def test_sin_conexion_da_un_mensaje_claro():
    def manejador(peticion):
        raise httpx.ConnectError("sin red")

    with pytest.raises(aud.ErrorApi, match="No se pudo conectar con la API en http://api"):
        aud.obtener_cola("http://api", cliente(manejador))


def test_el_original_es_opcional():
    sin_original = cliente(lambda peticion: httpx.Response(404, json={"detail": "Not Found"}))
    assert aud.obtener_original("http://api", "GS-06", sin_original) is None
    con_original = cliente(lambda peticion: httpx.Response(200, content=b"png", headers={"content-type": "image/png"}))
    assert aud.obtener_original("http://api", "M8", con_original) == (b"png", "image/png")


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch):
    """La página sin API: obtener_cola falla como cuando nadie escucha, y no hay originales."""

    def sin_api(api_url):
        raise aud.ErrorApi(f"No se pudo conectar con la API en {api_url} (ConnectError).")

    monkeypatch.setenv("API_URL", "http://api-de-prueba")
    monkeypatch.setattr(aud, "obtener_cola", sin_api)
    monkeypatch.setattr(aud, "obtener_original", lambda api_url, documento_id: None)
    return AppTest.from_file(PAGINA, default_timeout=30)


def con_cola(monkeypatch, cola: list[dict]) -> list[dict]:
    monkeypatch.setattr(aud, "obtener_cola", lambda api_url: [i for i in map(aud.normalizar_item, cola) if i])
    return cola


def boton(app: AppTest, etiqueta: str):
    return next(b for b in app.button if b.label == etiqueta)


def abrir_demostracion(app: AppTest, revisor: str = "Camila") -> AppTest:
    app.run()
    app.text_input(key="revisor").set_value(revisor)
    app.toggle(key="demo").set_value(True).run()
    assert not app.exception
    return app


def test_sin_api_avisa_y_sugiere_la_demostracion(app):
    app.run()
    assert not app.exception
    assert app.error[0].value == "No se pudo conectar con la API en http://api-de-prueba (ConnectError)."


def test_la_demostracion_abre_la_urgencia_primero(app):
    abrir_demostracion(app)
    assert app.selectbox(key="seleccion:demo").value == "GS-14"
    assert app.error[0].value.startswith("**Urgente.**")
    assert "AMB-1 · Campo obligatorio faltante" in app.warning[0].value


def test_corregir_un_campo_resuelve_y_pasa_al_siguiente(app):
    abrir_demostracion(app)
    app.text_input(key="demo:GS-14:campo:paciente.nombre").set_value("Rodríguez, Ana María")
    app.text_area(key="demo:GS-14:decision:motivo").set_value("Nombre de la orden de laboratorio")
    boton(app, "Corregir").click().run()
    assert not app.exception
    assert app.success[0].value == "**GS-14** corregido por Camila."
    assert app.session_state["ultimo"]["decision"]["correcciones"] == {"paciente.nombre": "Rodríguez, Ana María"}
    assert app.selectbox(key="seleccion:demo").value == "GS-06"  # la receta, con su tabla de medicamentos


def test_aprobar_con_cambios_no_envia_nada(app):
    abrir_demostracion(app)
    app.text_input(key="demo:GS-14:campo:paciente.nombre").set_value("Ana")
    boton(app, "Aprobar").click().run()
    assert any("«Corregir»" in e.value for e in app.error)
    assert app.selectbox(key="seleccion:demo").value == "GS-14"  # sigue en la cola


def test_sin_revisor_la_decision_no_se_firma(app):
    abrir_demostracion(app, revisor="")
    boton(app, "Aprobar").click().run()
    assert any("«Revisor»" in e.value for e in app.error)


def test_rechazar_pide_el_motivo_y_despues_resuelve(app):
    abrir_demostracion(app)
    app.selectbox(key="seleccion:demo").set_value("M8").run()
    assert app.get("image") or app.get("imgs")  # la foto de la receta, al lado
    boton(app, "Rechazar").click().run()
    assert any("Escribe el motivo" in e.value for e in app.error)
    app.text_area(key="demo:M8:decision:motivo").set_value("Ilegible: pedir una foto nueva a Farmacia")
    boton(app, "Rechazar").click().run()
    assert app.success[0].value == "**M8** rechazado por Camila."
    assert "M8" not in app.selectbox(key="seleccion:demo").options


def test_un_certificado_con_motivo_no_choca_con_el_motivo_de_la_decision(app, monkeypatch):
    certificado = {
        "clasificacion": {"tipo_documento": "Certificado Medico", "nivel_prioridad": "Rutina"},
        "datos_extraidos": {"paciente": {"nombre": "Ana"}, "motivo": "Lumbalgia", "dias_reposo": 3, "fecha": None},
        "validacion": {"campos_faltantes": ["fecha"]},
        "decision_enrutamiento": {"destino_principal": "Cola_Revision_Humana", "justificacion_enrutamiento": "AMB-1"},
    }
    con_cola(monkeypatch, [{"documento_id": "CERT-1", "extraccion": certificado}])
    app.run()
    assert not app.exception
    assert app.text_input(key="api:CERT-1:campo:motivo").value == "Lumbalgia"
    assert app.text_area(key="api:CERT-1:decision:motivo").value == ""


def test_lo_escrito_en_la_demostracion_no_pasa_al_documento_real(app, monkeypatch):
    real = {"documento_id": "GS-14", "extraccion": ejemplo("GS-14")}
    con_cola(monkeypatch, [real])
    abrir_demostracion(app)
    app.text_input(key="demo:GS-14:campo:paciente.nombre").set_value("Nombre de prueba")
    boton(app, "Corregir").click().run()  # falta el motivo: no se envía
    app.toggle(key="demo").set_value(False).run()
    assert not app.exception
    assert app.text_input(key="api:GS-14:campo:paciente.nombre").value == ""


def test_si_otra_sesion_lo_resuelve_avisa_que_la_decision_no_se_guardo(app, monkeypatch):
    cola = con_cola(monkeypatch, [{"documento_id": d, "extraccion": ejemplo(d)} for d in ("GS-06", "GS-26")])
    app.run()
    app.selectbox(key="seleccion:api").set_value("GS-26").run()
    cola.pop()  # se resolvió GS-26 desde otra sesión mientras esta lo tenía abierto
    boton(app, "Actualizar la cola").click().run()
    assert not app.exception
    assert app.warning[0].value.startswith("**GS-26** salió de la cola mientras lo revisabas")
    assert app.selectbox(key="seleccion:api").value == "GS-06"


def test_salir_de_la_demostracion_no_confunde_los_documentos(app, monkeypatch):
    con_cola(monkeypatch, [])
    abrir_demostracion(app)
    app.selectbox(key="seleccion:demo").set_value("GS-26").run()
    app.toggle(key="demo").set_value(False).run()
    assert not app.exception
    assert not app.warning  # GS-26 era un ejemplo: no "salió de la cola"
    assert app.success[0].value == "No hay documentos esperando revisión."


def test_una_urgencia_fuera_de_emergencia_se_marca(app, monkeypatch):
    extraccion = ejemplo("GS-14")
    extraccion["decision_enrutamiento"]["destino_principal"] = "Historia_Clinica_Electronica"
    con_cola(monkeypatch, [{"documento_id": "GS-14", "extraccion": extraccion}])
    app.run()
    assert app.error[0].value.startswith("**Prioridad urgente, pero el destino es Historia\\_Clinica\\_Electronica.**")


def test_una_extraccion_rara_se_muestra_sin_romper(app, monkeypatch):
    raro = {
        "clasificacion": None,
        "validacion": {"campos_faltantes": [None], "conflictos": [3]},
        "datos_extraidos": {"paciente": None, "medicamentos": {"x": 1}, "hallazgos": ["a", "b"],
                            "medico_solicitante": {"matricula": 131795}},
        "evidencias": "nada",
        "texto": 42,
    }
    con_cola(monkeypatch, [{"documento_id": 99, "extraccion": raro}, {"documento_id": "Y", "extraccion": "texto"}])
    enviados = []
    monkeypatch.setattr(aud, "enviar_decision", lambda url, doc, decision: enviados.append((doc, decision)) or {})
    app.run()
    assert not app.exception
    app.text_input(key="revisor").set_value("Camila").run()
    boton(app, "Aprobar").click().run()  # nada tocado: el número de matrícula no cuenta como cambio
    assert not app.exception
    assert not app.error
    assert enviados[0][0] == "99" and enviados[0][1]["correcciones"] is None


def test_una_orden_corrige_sus_estudios(app, monkeypatch):
    orden = {
        "clasificacion": {"tipo_documento": "Orden de Solicitud de Procedimiento", "nivel_prioridad": "Rutina"},
        "datos_extraidos": {"paciente": {"nombre": "Ana"}, "estudios_solicitados": ["Hemograma"]},
        "decision_enrutamiento": {"destino_principal": "Cola_Revision_Humana"},
    }
    con_cola(monkeypatch, [{"documento_id": "ORD-1", "extraccion": orden}])
    enviados = []
    monkeypatch.setattr(aud, "enviar_decision", lambda url, doc, decision: enviados.append(decision) or {})
    app.run()
    app.text_input(key="revisor").set_value("Camila")
    app.text_area(key="api:ORD-1:campo:estudios_solicitados").set_value("Hemograma\nUrea")
    app.text_area(key="api:ORD-1:decision:motivo").set_value("Falta la urea en la extracción")
    boton(app, "Corregir").click().run()
    assert enviados[0]["correcciones"] == {"estudios_solicitados": ["Hemograma", "Urea"]}


def test_un_campo_llamado_estudios_no_choca_con_la_lista_de_estudios(app, monkeypatch):
    otro = {"clasificacion": {"tipo_documento": "Otro"}, "datos_extraidos": {"estudios": "Rx de tórax"}}
    con_cola(monkeypatch, [{"documento_id": "OTRO-1", "extraccion": otro}])
    app.run()
    assert not app.exception
    assert app.text_input(key="api:OTRO-1:campo:estudios").value == "Rx de tórax"


def test_si_el_documento_vuelve_a_la_cola_el_formulario_empieza_limpio(app, monkeypatch):
    con_cola(monkeypatch, [{"documento_id": "GS-26", "extraccion": ejemplo("GS-26")}])  # sigue en la cola
    monkeypatch.setattr(aud, "enviar_decision", lambda url, doc, decision: {"documento_id": doc})
    app.run()
    app.text_input(key="revisor").set_value("Camila")
    app.text_area(key="api:GS-26:decision:motivo").set_value("Primera ronda")
    boton(app, "Aprobar").click().run()
    assert app.success[0].value == "**GS-26** aprobado por Camila."
    assert app.text_area(key="api:GS-26:decision:motivo").value == ""


def test_un_pdf_original_se_ofrece_para_descargar(app, monkeypatch):
    con_cola(monkeypatch, [{"documento_id": "GS-26", "extraccion": ejemplo("GS-26")}])
    monkeypatch.setattr(aud, "obtener_original", lambda api_url, documento_id: (b"%PDF-1.4", "application/pdf"))
    app.run()
    assert not app.exception
    assert len(app.get("download_button")) == 1


def test_un_original_dañado_no_rompe_la_pagina(app, monkeypatch):
    con_cola(monkeypatch, [{"documento_id": "GS-06", "extraccion": ejemplo("GS-06")}])
    monkeypatch.setattr(aud, "obtener_original", lambda api_url, documento_id: (b"no es una imagen", "image/png"))
    app.run()
    assert not app.exception
    assert any("No se pudo mostrar la imagen" in w.value for w in app.warning)


def test_con_la_api_envia_la_decision_y_muestra_el_destino_nuevo(app, monkeypatch):
    enviados = []

    def enviar(api_url, documento_id, decision):
        enviados.append((documento_id, decision))
        destino = {"destino_principal": "Historia_Clinica_Electronica"}
        return {"documento_id": documento_id, "resolucion": decision, "decision_enrutamiento": destino}

    cola = [{"documento_id": "GS-26", "extraccion": ejemplo("GS-26")}]
    monkeypatch.setattr(aud, "obtener_cola", lambda api_url: [] if enviados else list(map(aud.normalizar_item, cola)))
    monkeypatch.setattr(aud, "enviar_decision", enviar)
    app.run()
    app.text_input(key="revisor").set_value("Camila").run()
    boton(app, "Aprobar").click().run()
    assert not app.exception
    assert enviados == [
        ("GS-26", {"accion": "aprobar", "revisor": "Camila", "motivo": aud.MOTIVO_APROBAR, "correcciones": None})
    ]
    assert app.info[0].value == "El agente lo reencaminó a **Historia\\_Clinica\\_Electronica**."
    assert "No hay documentos esperando revisión." in [s.value for s in app.success]


def test_con_la_api_un_409_se_muestra_y_no_se_pierde_el_documento(app, monkeypatch):
    con_cola(monkeypatch, [{"documento_id": "GS-26", "extraccion": ejemplo("GS-26")}])

    def ya_resuelto(api_url, documento_id, decision):
        raise aud.ErrorApi(f"{documento_id} ya tiene una decisión registrada: se resolvió antes desde otra sesión.")

    monkeypatch.setattr(aud, "enviar_decision", ya_resuelto)
    app.run()
    app.text_input(key="revisor").set_value("Camila").run()
    boton(app, "Aprobar").click().run()
    assert not app.exception
    assert app.error[0].value.startswith("GS-26 ya tiene una decisión registrada")
    assert not app.success
