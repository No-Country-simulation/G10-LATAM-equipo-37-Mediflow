"""Lógica del panel del auditor, separada de la página para poder probarla sin Streamlit.

La cola, la decisión y el formato de las correcciones siguen la sección 11 de docs/api-contract.md.
Este módulo no importa nada de agent/: el contenedor de la UI solo copia la carpeta ui/.

Privacidad: la extracción y las correcciones son datos clínicos. Nada de este módulo los escribe en
logs, y los mensajes de error nunca repiten el contenido que se envió.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

EJEMPLOS = Path(__file__).resolve().parent / "ejemplos" / "auditoria.json"

ACCIONES = ("aprobar", "corregir", "rechazar")  # ADR-004: rechazar es una acción, no un destino
MOTIVO_APROBAR = "Extracción verificada contra el documento original."

CATEGORIAS_AMB = {
    "AMB-1": "Campo obligatorio faltante",
    "AMB-2": "Contradicción interna",
    "AMB-3": "Dosis fuera de rango o medicamento no identificable",
    "AMB-4": "Texto truncado o parcialmente ilegible",
    "AMB-5": "Dos documentos en uno",
    "AMB-6": "Fuera del alcance del agente",
}
# Los valores son los del contrato, sin tildes; la pantalla los muestra con su nombre en español.
NOMBRES_TIPO = {
    "Receta Medica": "Receta Médica",
    "Informe de Estudio por Imagenes": "Informe de Estudio por Imágenes",
    "Informe de Laboratorio": "Informe de Laboratorio",
    "Orden de Solicitud de Procedimiento": "Orden de Solicitud de Procedimiento",
    "Epicrisis": "Epicrisis",
    "Certificado Medico": "Certificado Médico",
    "Otro": "Otro",
}
TIPOS_DOCUMENTO = list(NOMBRES_TIPO)
PRIORIDADES = ["Urgente", "Prioritario", "Rutina"]
DESTINO_URGENCIA = "Cola_Emergencia_Medica"
LEGIBILIDAD_MINIMA = 0.40  # rules.yaml, umbrales.legibilidad_minima
SCORE_AUTOMATICO = 0.85  # rules.yaml, umbrales.automatico

LISTAS = ("medicamentos", "estudios_solicitados")  # se corrigen enteras, nunca por índice
COLUMNAS_MEDICAMENTO = ("nombre", "dosis", "frecuencia", "duracion")  # alto_riesgo lo calcula el grafo
CAMPOS_ENTEROS = {"paciente.edad", "dias_reposo"}
CAMPOS_FECHA_ISO = {"paciente.fecha_nacimiento"}
CAMPOS_LARGOS = {"hallazgos", "conclusion", "motivo_ingreso", "tratamiento", "indicaciones_alta", "justificacion"}
ESCALARES = (str, int, float, bool, type(None))

ETIQUETAS = {
    "paciente.nombre": "Paciente · nombre",
    "paciente.edad": "Paciente · edad",
    "paciente.fecha_nacimiento": "Paciente · fecha de nacimiento (AAAA-MM-DD)",
    "medico_solicitante.nombre": "Médico · nombre",
    "medico_solicitante.matricula": "Médico · matrícula",
    "estudio_realizado": "Estudio realizado",
    "procedimiento_solicitado": "Procedimiento solicitado",
    "diagnostico_principal": "Diagnóstico principal",
    "diagnostico_egreso": "Diagnóstico de egreso",
    "diagnostico": "Diagnóstico",
    "cie10_sugerido": "CIE-10",
    "hallazgos": "Hallazgos",
    "conclusion": "Conclusión",
    "fecha": "Fecha",
    "fecha_ingreso": "Fecha de ingreso",
    "fecha_egreso": "Fecha de egreso",
    "motivo_ingreso": "Motivo de ingreso",
    "tratamiento": "Tratamiento",
    "indicaciones_alta": "Indicaciones al alta",
    "dias_reposo": "Días de reposo",
    "institucion": "Institución",
    "justificacion": "Justificación",
    "motivo": "Motivo",
    "medicamentos": "Medicamentos",
    "estudios_solicitados": "Estudios solicitados",
}


class ErrorApi(Exception):
    """Un fallo al hablar con la API, con un mensaje que se puede mostrar tal cual."""


# ---------------------------------------------------------------------------
# La cola: lo que llega se ordena y se limpia antes de mostrarlo
# ---------------------------------------------------------------------------


def como_dict(valor: Any) -> dict:
    return valor if isinstance(valor, dict) else {}


def _textos(valor: Any) -> list[str]:
    return [str(v) for v in valor if v is not None] if isinstance(valor, list) else []


def _texto(valor: Any) -> str | None:
    """Un valor que el panel usa como texto o como clave: texto, número como texto, o null."""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(valor)
    return None


def normalizar_item(item: Any) -> dict | None:
    """Un elemento de la cola con la forma que la página espera, aunque la extracción venga incompleta.

    Una extracción mal formada no puede romper la cola entera: lo que no tiene la forma del contrato se
    reemplaza por vacío, y un elemento sin documento_id se descarta.
    """
    if not isinstance(item, dict) or item.get("documento_id") in (None, ""):
        return None
    extraccion = dict(como_dict(item.get("extraccion")))
    for clave in ("clasificacion", "validacion", "datos_extraidos"):
        extraccion[clave] = dict(como_dict(extraccion.get(clave)))
    for clave in ("decision_enrutamiento", "decision"):
        if clave in extraccion:
            extraccion[clave] = dict(como_dict(extraccion[clave]))

    clasificacion = extraccion["clasificacion"]
    for clave in ("tipo_documento", "nivel_prioridad", "especialidad"):
        if clave in clasificacion:
            clasificacion[clave] = _texto(clasificacion[clave])
    validacion = extraccion["validacion"]
    for clave in ("campos_faltantes", "conflictos", "errores"):
        validacion[clave] = _textos(validacion.get(clave))
    for clave in ("categoria_amb", "motivo_fuera_de_alcance"):
        validacion[clave] = _texto(validacion.get(clave))
    for clave in ("decision_enrutamiento", "decision"):
        decision = extraccion.get(clave)
        if isinstance(decision, dict):
            for campo in ("destino_principal", "justificacion_enrutamiento"):
                if campo in decision:
                    decision[campo] = _texto(decision[campo])

    datos = extraccion["datos_extraidos"]
    datos["paciente"] = {"nombre": None, "edad": None, "fecha_nacimiento": None, **como_dict(datos.get("paciente"))}
    datos["medico_solicitante"] = {"nombre": None, "matricula": None, **como_dict(datos.get("medico_solicitante"))}
    medicamentos = datos.get("medicamentos")
    datos["medicamentos"] = [m for m in medicamentos if isinstance(m, dict)] if isinstance(medicamentos, list) else []
    datos["estudios_solicitados"] = _textos(datos.get("estudios_solicitados"))

    if not isinstance(extraccion.get("evidencias"), (list, dict)):
        extraccion["evidencias"] = []
    if not isinstance(extraccion.get("texto"), str):
        extraccion["texto"] = None
    return {**item, "documento_id": str(item["documento_id"]), "extraccion": extraccion}


def decision_de(extraccion: dict) -> dict:
    """La decisión de enrutamiento. Acepta el nombre de la respuesta y el del estado del grafo."""
    return como_dict(extraccion.get("decision_enrutamiento") or extraccion.get("decision"))


def score_de(extraccion: dict) -> float | None:
    valor = extraccion.get("score_confianza", extraccion.get("score"))
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def es_urgente(extraccion: dict) -> bool:
    prioridad = como_dict(extraccion.get("clasificacion")).get("nivel_prioridad")
    return decision_de(extraccion).get("destino_principal") == DESTINO_URGENCIA or prioridad == "Urgente"


def ordenar_cola(items: list[dict]) -> list[dict]:
    """Urgentes primero, después prioritarios, después el resto; dentro de cada grupo, por documento."""

    def clave(item: dict) -> tuple[int, str]:
        extraccion = como_dict(item.get("extraccion"))
        prioridad = como_dict(extraccion.get("clasificacion")).get("nivel_prioridad")
        rango = 0 if es_urgente(extraccion) else 1 if prioridad == "Prioritario" else 2
        return rango, str(item.get("documento_id", ""))

    return sorted(items, key=clave)


def nombre_tipo(tipo: str | None) -> str:
    return NOMBRES_TIPO.get(tipo, tipo) if tipo else "Sin clasificar"


def motivo_revision(extraccion: dict) -> tuple[str, str]:
    """Por qué el documento espera a una persona: un título corto y la justificación del agente."""
    validacion = como_dict(extraccion.get("validacion"))
    justificacion = str(decision_de(extraccion).get("justificacion_enrutamiento") or "")
    categoria = validacion.get("categoria_amb")
    if categoria:
        titulo = f"{categoria} · {CATEGORIAS_AMB.get(categoria, 'categoría sin descripción')}"
        motivo = validacion.get("motivo_fuera_de_alcance")
        return (f"{titulo} ({motivo})" if motivo else titulo), justificacion

    legibilidad = extraccion.get("legibilidad")
    medicamentos = como_dict(extraccion.get("datos_extraidos")).get("medicamentos") or []
    score = score_de(extraccion)
    if isinstance(legibilidad, (int, float)) and legibilidad < LEGIBILIDAD_MINIMA:
        titulo = "Ilegible"
    elif any(isinstance(m, dict) and m.get("alto_riesgo") for m in medicamentos):
        titulo = "Medicamento de alto riesgo"
    elif score is not None and score < SCORE_AUTOMATICO:
        titulo = "Confianza insuficiente para decidir solo"
    else:
        titulo = "Revisión pedida por el agente"
    return titulo, justificacion


def etiqueta_item(item: dict) -> str:
    """Una línea para elegir el documento en la cola."""
    extraccion = como_dict(item.get("extraccion"))
    tipo = nombre_tipo(como_dict(extraccion.get("clasificacion")).get("tipo_documento"))
    titulo, _ = motivo_revision(extraccion)
    marca = "URGENTE · " if es_urgente(extraccion) else ""
    return f"{marca}{item.get('documento_id', 'sin id')} · {tipo} · {titulo.split(' · ')[0]}"


def etiqueta_campo(ruta: str) -> str:
    """`medicamentos[0].dosis` -> `Medicamento 1 · dosis`; `paciente.nombre` -> `Paciente · nombre`."""
    if ruta in ETIQUETAS:
        return ETIQUETAS[ruta]
    indice = re.fullmatch(r"(\w+)\[(\d+)\]\.?(\w*)", ruta)
    if indice:
        lista, numero, campo = indice.groups()
        nombre = "Medicamento" if lista == "medicamentos" else ETIQUETAS.get(lista, lista)
        return f"{nombre} {int(numero) + 1}" + (f" · {campo}" if campo else "")
    return ruta.replace("_", " ").replace(".", " · ").capitalize()


def md(texto: Any) -> str:
    """Texto del documento listo para meter en Markdown sin que se interprete como formato."""
    texto = re.sub(r"([\\`*_\[\]<>$~|#])", r"\\\1", str(texto))
    texto = re.sub(r"(?m)^(\s*)([-+])(\s)", r"\1\\\2\3", texto)  # viñetas
    texto = re.sub(r"(?m)^(\s*)(\d+)([.)])(\s)", r"\1\2\\\3\4", texto)  # listas numeradas
    return re.sub(r"(?m)^(\s*)-(\s*-){2,}\s*$", lambda m: m.group(0).replace("-", r"\-"), texto)  # líneas ---


def aplanar(datos: dict | None, prefijo: str = "") -> dict[str, Any]:
    """`{"paciente": {"nombre": "X"}}` -> `{"paciente.nombre": "X"}`. Las listas quedan enteras."""
    planos: dict[str, Any] = {}
    for clave, valor in como_dict(datos).items():
        if clave.startswith("_") or clave.startswith("evidencia_"):
            continue  # marcas internas del grafo y evidencias en línea
        ruta = f"{prefijo}.{clave}" if prefijo else clave
        if isinstance(valor, dict):
            planos.update(aplanar(valor, ruta))
        else:
            planos[ruta] = valor
    return planos


def evidencias_por_campo(extraccion: dict) -> dict[str, str]:
    """El fragmento del documento que sustenta cada campo. Acepta lista `{campo, fragmento}` o dict."""
    evidencias = extraccion.get("evidencias") or []
    if isinstance(evidencias, dict):
        return {str(c): str(f) for c, f in evidencias.items() if f}
    if not isinstance(evidencias, list):
        return {}
    return {
        str(e["campo"]): str(e["fragmento"])
        for e in evidencias
        if isinstance(e, dict) and e.get("campo") and e.get("fragmento")
    }


def campos_del_formulario(extraccion: dict) -> tuple[list[str], list[str], dict[str, Any]]:
    """Qué campos se muestran para revisar, cuáles quedan vacíos para completar si hace falta, y qué datos
    se muestran solo para leer.

    Se muestran los que tienen valor y los obligatorios que faltan, aunque la extracción no los traiga.
    Las listas del contrato (medicamentos, estudios) van aparte, como tabla. Un valor que no es texto ni
    número, como una lista donde el contrato espera texto, no se edita: se muestra tal cual.
    """
    planos = aplanar(extraccion.get("datos_extraidos"))
    faltantes = [
        ruta for ruta in como_dict(extraccion.get("validacion")).get("campos_faltantes") or []
        if "[" not in ruta and ruta not in LISTAS
    ]
    visibles, vacios, solo_lectura = [], [], {}
    for ruta, valor in planos.items():
        if ruta in LISTAS:
            continue
        if not isinstance(valor, ESCALARES):
            solo_lectura[ruta] = valor
        elif _limpio(valor) is not None or ruta in faltantes:
            visibles.append(ruta)
        else:
            vacios.append(ruta)
    visibles += [ruta for ruta in faltantes if ruta not in planos]
    return visibles, vacios, solo_lectura


def medicamentos_de_alto_riesgo(medicamentos: Any) -> list[str]:
    """Los que el agente marcó de alto riesgo, para mostrarlo: el auditor no cambia esa marca."""
    return [
        str(m.get("nombre")) for m in medicamentos or []
        if isinstance(m, dict) and m.get("alto_riesgo") and m.get("nombre")
    ]


# ---------------------------------------------------------------------------
# Correcciones
# ---------------------------------------------------------------------------


def _limpio(valor: Any) -> Any:
    """Texto sin espacios de más; vacío y NaN (celda vacía de una tabla) cuentan como null."""
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        return valor or None
    return valor


def mostrado(valor: Any) -> str:
    """Cómo aparece un valor de la extracción en un campo de texto del panel."""
    valor = _limpio(valor)
    return "" if valor is None else str(valor)


def convertir(ruta: str, valor: Any) -> Any:
    """Lo que escribió el auditor, al tipo del contrato. Lanza ValueError con un mensaje para mostrar."""
    valor = _limpio(valor)
    if valor is None:
        return None
    if ruta in CAMPOS_ENTEROS:
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and float(valor).is_integer():
            return int(valor)
        if isinstance(valor, str) and re.fullmatch(r"\d{1,3}", valor):
            return int(valor)
        raise ValueError(f"{etiqueta_campo(ruta)}: tiene que ser un número entero, sin letras ni decimales.")
    if ruta in CAMPOS_FECHA_ISO:
        try:
            date.fromisoformat(str(valor))
        except ValueError:
            raise ValueError(f"{etiqueta_campo(ruta)}: no es una fecha válida; por ejemplo, 1994-06-14.") from None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(valor)):
            raise ValueError(f"{etiqueta_campo(ruta)}: no es una fecha válida; por ejemplo, 1994-06-14.")
    return valor


def normalizar_medicamentos(filas: Any) -> list[dict]:
    """Filas de la tabla del panel, o de la extracción, con las cuatro columnas que edita el auditor.

    Cada celda queda como texto o null, aunque la extracción traiga un número. Una fila sin nombre, dosis,
    frecuencia ni duración es la fila vacía de la tabla y se descarta.
    """
    resultado = []
    for fila in filas if isinstance(filas, list) else []:
        if not isinstance(fila, dict):
            continue
        medicamento = {col: (None if _limpio(fila.get(col)) is None else str(_limpio(fila.get(col))))
                       for col in COLUMNAS_MEDICAMENTO}
        if any(v is not None for v in medicamento.values()):
            resultado.append(medicamento)
    return resultado


def lineas(texto: str | None) -> list[str]:
    """Un área de texto con un elemento por línea, como lista."""
    return [linea.strip() for linea in (texto or "").splitlines() if linea.strip()]


def calcular_correcciones(
    extraccion: dict,
    escritos: dict[str, Any],
    clasificacion: dict[str, Any] | None = None,
    medicamentos: list[dict] | None = None,
    estudios: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Solo lo que el auditor cambió, con las rutas de la sección 11 del contrato, y los errores de formato
    de lo que cambió.

    `escritos` es lo que quedó en cada campo de texto, tal cual. Un campo se compara con lo que mostraba el
    panel, así que un campo sin tocar nunca cuenta como cambio, ni se valida. `medicamentos` y `estudios`
    en None significan que el panel no los mostró; si se mostraron y cambiaron, van enteros.
    """
    originales = aplanar(extraccion.get("datos_extraidos"))
    correcciones: dict[str, Any] = {}
    errores: list[str] = []
    for ruta, escrito in escritos.items():
        antes = mostrado(originales.get(ruta))
        if mostrado(escrito) == antes:
            continue
        try:
            nuevo = convertir(ruta, escrito)
        except ValueError as exc:
            errores.append(str(exc))
            continue
        try:
            igual = nuevo == convertir(ruta, antes)  # "068" y "68" son la misma edad
        except ValueError:
            igual = False
        if not igual:
            correcciones[ruta] = nuevo

    clasificacion_original = como_dict(extraccion.get("clasificacion"))
    for campo, nuevo in (clasificacion or {}).items():
        if nuevo is not None and nuevo != clasificacion_original.get(campo):
            correcciones[f"clasificacion.{campo}"] = nuevo

    datos = como_dict(extraccion.get("datos_extraidos"))
    if medicamentos is not None:
        nuevos = normalizar_medicamentos(medicamentos)
        if nuevos != normalizar_medicamentos(datos.get("medicamentos")):
            correcciones["medicamentos"] = nuevos
    if estudios is not None:
        nuevos_estudios = [str(e).strip() for e in estudios if e and str(e).strip()]
        if nuevos_estudios != [str(e).strip() for e in datos.get("estudios_solicitados") or [] if str(e).strip()]:
            correcciones["estudios_solicitados"] = nuevos_estudios
    return correcciones, errores


def resumen_cambios(extraccion: dict, correcciones: dict[str, Any]) -> list[dict[str, str]]:
    """Campo, antes y después, para mostrarle al auditor lo que quedó registrado."""
    originales = aplanar(extraccion.get("datos_extraidos"))
    filas = []
    for ruta, nuevo in correcciones.items():
        if ruta.startswith("clasificacion."):
            antes = como_dict(extraccion.get("clasificacion")).get(ruta.split(".", 1)[1])
            if ruta.endswith("tipo_documento"):
                etiqueta, antes, nuevo = "Tipo de documento", nombre_tipo(antes), nombre_tipo(nuevo)
            else:
                etiqueta = "Prioridad"
        else:
            antes, etiqueta = originales.get(ruta), etiqueta_campo(ruta)
        filas.append({"Campo": etiqueta, "Antes": _como_texto(antes), "Después": _como_texto(nuevo)})
    return filas


def _como_texto(valor: Any) -> str:
    if valor is None:
        return "(vacío)"
    if isinstance(valor, list):
        if all(isinstance(v, dict) for v in valor):
            texto = "; ".join(
                " ".join(str(m.get(c)) for c in COLUMNAS_MEDICAMENTO if m.get(c)) for m in valor
            )
        else:
            texto = "; ".join(str(v) for v in valor)
        return texto or "(vacío)"
    return str(valor)


# ---------------------------------------------------------------------------
# Decisión
# ---------------------------------------------------------------------------


def validar_decision(
    accion: str, revisor: str | None, motivo: str | None, correcciones: dict, errores_formato: list[str] = ()
) -> list[str]:
    """Qué le falta a la decisión para poder enviarla. Lista vacía: está lista.

    `errores_formato` son los de `calcular_correcciones`: solo importan al corregir. Al aprobar, cualquier
    campo tocado frena el envío; al rechazar, los campos tocados no se envían.
    """
    if accion not in ACCIONES:
        return [f"Acción desconocida: {accion}."]
    errores = []
    if not (revisor or "").strip():
        errores.append("Escribe tu nombre en «Revisor», en la barra lateral: la decisión queda firmada.")
    if accion == "aprobar" and (correcciones or errores_formato):
        cambios = len(correcciones) + len(errores_formato)
        errores.append(
            f"Cambiaste {cambios} campo(s). Para guardarlos usa «Corregir»; "
            "para aprobar la extracción como está, deshaz los cambios."
        )
    if accion == "corregir":
        errores += list(errores_formato)
        if not correcciones and not errores_formato:
            errores.append("No cambiaste ningún campo. Si la extracción está bien, usa «Aprobar».")
    if accion in ("corregir", "rechazar") and not (motivo or "").strip():
        errores.append("Escribe el motivo de la decisión: queda registrado junto con ella.")
    return errores


def armar_decision(accion: str, revisor: str, motivo: str | None, correcciones: dict) -> dict:
    """El cuerpo de POST /audit/{documento_id}."""
    motivo = (motivo or "").strip() or (MOTIVO_APROBAR if accion == "aprobar" else "")
    return {
        "accion": accion,
        "revisor": revisor.strip(),
        "motivo": motivo,
        "correcciones": correcciones if accion == "corregir" else None,
    }


# ---------------------------------------------------------------------------
# API y ejemplos
# ---------------------------------------------------------------------------


def _pedir(metodo: str, api_url: str, ruta: str, cliente: httpx.Client | None = None, **kwargs: Any) -> httpx.Response:
    url = f"{api_url.rstrip('/')}{ruta}"
    try:
        if cliente is not None:
            return cliente.request(metodo, url, **kwargs)
        with httpx.Client(timeout=30.0) as propio:
            return propio.request(metodo, url, **kwargs)
    except httpx.HTTPError as exc:
        raise ErrorApi(f"No se pudo conectar con la API en {api_url} ({type(exc).__name__}).") from exc


def _json(respuesta: httpx.Response) -> Any:
    try:
        return respuesta.json()
    except ValueError:
        return None


def _detalle(respuesta: httpx.Response) -> str:
    """El motivo del error, sin repetir lo que se envió: un 422 de FastAPI trae el cuerpo en `input`."""
    datos = _json(respuesta)
    detalle = datos.get("detail") if isinstance(datos, dict) else None
    if isinstance(detalle, list):
        return "; ".join(
            ".".join(str(p) for p in e.get("loc", []) if p != "body") + f": {e.get('msg', '')}"
            for e in detalle
            if isinstance(e, dict)
        )
    return str(detalle or respuesta.reason_phrase)


def _ruta_documento(documento_id: str) -> str:
    return quote(str(documento_id), safe="")  # un "#" o un "/" en el id no pueden cortar la ruta


def obtener_cola(api_url: str, cliente: httpx.Client | None = None) -> list[dict]:
    """GET /queue/human: los documentos que esperan una decisión, ya limpios."""
    respuesta = _pedir("GET", api_url, "/queue/human", cliente)
    datos = _json(respuesta)
    if respuesta.status_code != 200 or not isinstance(datos, dict):
        raise ErrorApi(f"La API no devolvió la cola ({respuesta.status_code}): {_detalle(respuesta)}")
    items = datos.get("items") if isinstance(datos.get("items"), list) else []
    return [i for i in map(normalizar_item, items) if i]


def enviar_decision(api_url: str, documento_id: str, decision: dict, cliente: httpx.Client | None = None) -> dict:
    """POST /audit/{documento_id}. Devuelve la respuesta de la API: `documento_id`, `resolucion` y, cuando
    el grafo se reanude, `decision_enrutamiento` con el destino nuevo."""
    respuesta = _pedir("POST", api_url, f"/audit/{_ruta_documento(documento_id)}", cliente, json=decision)
    if respuesta.status_code == 200:
        datos = _json(respuesta)
        return datos if isinstance(datos, dict) else {"documento_id": documento_id}
    if respuesta.status_code == 404:
        raise ErrorApi(f"{documento_id} ya no está en la cola de revisión. Actualiza la cola.")
    if respuesta.status_code == 409:
        raise ErrorApi(f"{documento_id} ya tiene una decisión registrada: se resolvió antes desde otra sesión.")
    raise ErrorApi(f"La API rechazó la decisión ({respuesta.status_code}): {_detalle(respuesta)}")


def obtener_original(api_url: str, documento_id: str, cliente: httpx.Client | None = None) -> tuple[bytes, str] | None:
    """GET /audit/{documento_id}/original: el archivo y su tipo, o None si la API todavía no lo ofrece."""
    try:
        respuesta = _pedir("GET", api_url, f"/audit/{_ruta_documento(documento_id)}/original", cliente)
    except ErrorApi:
        return None
    if respuesta.status_code != 200 or not respuesta.content:
        return None
    tipo = respuesta.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    return respuesta.content, tipo


def cargar_ejemplos(ruta: Path = EJEMPLOS) -> list[dict]:
    """Los casos del modo demostración, con la misma forma que GET /queue/human."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    items = []
    for item in map(normalizar_item, datos.get("items", [])):
        if item:
            original = item.get("original")
            item["original_ruta"] = ruta.parent / original if original else None
            items.append(item)
    return items


def tipo_de_archivo(ruta: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }.get(ruta.suffix.lower(), "application/octet-stream")
