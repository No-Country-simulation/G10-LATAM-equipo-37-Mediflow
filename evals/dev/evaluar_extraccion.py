"""Compara dos prompts con casos nuevos; exige respuestas del modelo, sin fallback stub."""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def normalizar(valor, *, nombre_medico=False):
    if valor is None:
        return None
    texto = unicodedata.normalize("NFC", str(valor)).strip().rstrip(".").casefold()
    if nombre_medico:
        texto = re.sub(r"^(?:doctora|doctor|dra|dr)\.?\s+", "", texto)
    return texto


def comparar(esperado, datos):
    resultados = {}
    for campo, valor in esperado.items():
        actual = datos
        for parte in campo.split("."):
            if isinstance(actual, list) and parte.isdigit():
                actual = actual[int(parte)] if int(parte) < len(actual) else None
            elif isinstance(actual, dict):
                actual = actual.get(parte)
            else:
                actual = None
                break

        # Para listas de diccionarios (como medicamentos), comparar campo por campo
        if isinstance(valor, list) and valor and isinstance(valor[0], dict):
            if not isinstance(actual, list) or len(actual) != len(valor):
                # Si la lista no existe o tiene distinto tamaño, todos los subcampos fallan
                for i, esperado_item in enumerate(valor):
                    for k, in esperado_item.keys():
                        nombre_campo = f"{campo}.{i}.{k}"
                        resultados[nombre_campo] = False
                continue
            
            # Si la lista coincide en tamaño, comparar item por item y campo por campo
            for i, (esperado_item, actual_item) in enumerate(zip(valor, actual, strict=True)):
                for k, v in esperado_item.items():
                    nombre_campo = f"{campo}.{i}.{k}"
                    if isinstance(actual_item, dict):
                        actual_v = actual_item.get(k)
                    else:
                        actual_v = None
                    resultados[nombre_campo] = normalizar(actual_v) == normalizar(v)
        else:
            es_medico = campo == "medico_solicitante.nombre"
            resultados[campo] = (
                normalizar(actual, nombre_medico=es_medico) == normalizar(valor, nombre_medico=es_medico)
            )
    return resultados


def main():
    from agent.llm import adapter
    from agent.nodes.extraer import _parsear_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--antes", type=Path, required=True)
    parser.add_argument("--despues", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if args.salida.exists():
        parser.error("La salida ya existe; use una ruta nueva")
    casos = json.loads(Path(__file__).with_name("extraccion.json").read_text(encoding="utf-8"))
    resultados = []
    for caso in casos:
        registro = {"id": caso["id"], "tipo": caso["tipo"]}
        for nombre, ruta in (("antes", args.antes), ("despues", args.despues)):
            prompt = ruta.read_text(encoding="utf-8").replace("{{tipo_documento}}", caso["tipo"])
            prompt = prompt.replace("{{documento}}", caso["texto"])
            try:
                respuesta = adapter.complete(prompt, json_mode=False, timeout=30)
                payload = _parsear_json(respuesta.text)
                campos = comparar(caso["esperado"], payload.get("datos_extraidos", payload))
                registro[nombre] = {"campos": campos, "modelo": respuesta.model,
                    "consumo": respuesta.consumo("extraer"), "error": False,
                    "respuesta": payload}
            except Exception as exc:
                # No guardar mensajes del proveedor que puedan contener secretos.
                registro[nombre] = {"error": True, "clase_error": type(exc).__name__}
        resultados.append(registro)
    valido = all(not r[n]["error"] for r in resultados for n in ("antes", "despues"))
    regresiones = [r["id"] for r in resultados if not r["antes"]["error"]
                   and not r["despues"]["error"] and any(
                       bien and not r["despues"]["campos"][c] for c, bien in r["antes"]["campos"].items())]
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps({"valido": valido, "regresiones": regresiones,
                                      "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if valido and not regresiones else 1


if __name__ == "__main__":
    raise SystemExit(main())
