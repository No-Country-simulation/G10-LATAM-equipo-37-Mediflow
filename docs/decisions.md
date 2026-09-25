# Registro de decisiones

Una entrada por decisión, el mismo día. Formato: contexto, decisión, alternativas descartadas, consecuencias.

## ADR-001 · Orquestación con LangGraph, interfaz en Streamlit, modelo principal Gemini con respaldo
- Fecha: 16 de septiembre de 2026
- Decisión: consolidada por el equipo en el sprint 1 (LangGraph, Pydantic, FastAPI, Streamlit; Gemini por su capa gratuita, un solo respaldo al inicio).

## ADR-002 · Regla de urgencia por tipo de documento: opción A
- Fecha: 22 de septiembre de 2026
- Contexto: las listas automáticas de `rules.yaml` (hallazgos críticos, palabras de urgencia, valores críticos de laboratorio) disparan con que la palabra aparezca, sin leer el contexto.
- Decisión: las listas se aplican solo a informes de estudio por imágenes, informes de laboratorio y órdenes de procedimiento (`deteccion_automatica_urgencia.aplica_a`). En recetas, epicrisis y certificados la urgencia la decide el modelo con justificación. El alto riesgo farmacológico se detecta solo en recetas y va a Farmacia con auditoría.
- Alternativa descartada: opción B, listas en todos los tipos. Manda a Emergencia epicrisis de alta y recetas de mantenimiento que solo mencionan un diagnóstico tratado o una instrucción de alarma.
- Consecuencias: las etiquetas de GS-01, GS-04, GS-24 y GS-25 quedan en su destino normal; `urgencia.py` lee la lista de tipos; volver a la B es agregar tres líneas a esa lista.

## ADR-003 · El campo del paciente se llama `nombre` en todo el proyecto
- Fecha: 23 de septiembre de 2026
- Contexto: el ejemplo de respuesta del brief escribe `paciente.nome` y `medico_solicitante.nombre`. Se consultó a la instructora si era un error de tipeo y no hubo respuesta. Mientras tanto, el repositorio quedó con las dos formas mezcladas: `extraer.py` escribía `nombre` y `enrutar.py` leía `nome`, así que las alertas de urgencia salían con "paciente sin identificar".
- Decisión: se usa `nombre` en todo el proyecto, igual que el campo del médico. El contrato queda en un solo idioma y sin excepciones que alguien pueda olvidar. La prueba `test_la_notificacion_nombra_al_paciente` detecta cualquier regresión.
- Alternativas descartadas: (a) usar `nome` como el ejemplo del brief, que obliga a recordar una excepción en cada archivo y ya produjo un error; (b) un alias de Pydantic que acepte las dos formas y serialice `nome`, correcto pero agrega un concepto más para ocho personas.
- Riesgo asumido: si la evaluación compara la salida campo por campo contra el ejemplo del brief, aparecería esa diferencia. Se asume porque el brief lo presenta como ejemplo de respuesta, no como esquema obligatorio, y porque el campo solo existe en la salida: la entrada es `documento_texto`, así que ningún JSON externo se rompe.
- Reversión: si la instructora confirma que debe ser `nome`, se cambia con una búsqueda y reemplazo en `contrato.py`, `documentos.py`, `extraer.py`, `validar.py`, `enrutar.py`, `prompts/extraer.md`, `rules.yaml`, `docs/api-contract.md` y las etiquetas del conjunto de prueba, en un solo PR.

## ADR-004 · `Rechazado` no es un destino del agente
- Fecha: 22 de septiembre de 2026
- Decisión: el enum `DestinoEnrutamiento` conserva los cinco destinos del brief. Rechazar es una de las tres acciones del auditor sobre un caso de la Cola de Revisión Humana (aprobar, corregir, rechazar); `persistir.py` guarda el resultado en `rechazados/`.

## ADR-005 · Datos 100 % sintéticos
- Fecha: 22 de septiembre de 2026
- Decisión: ningún documento real de ningún paciente. Conjunto de prueba escrito por el equipo: 30 documentos, 12 imágenes degradadas y 8 fotos de recetas manuscritas. Consulta de validación enviada a la instructora.

## ADR-006 · La tabla de medicamentos se identifica por ATC y DCI, no por el código nacional
- Fecha: 25 de septiembre de 2026
- Contexto: no existe un código de medicamento común a toda Latinoamérica. Cada agencia tiene el suyo: certificado de ANMAT en Argentina, CUM del INVIMA en Colombia, registro sanitario de COFEPRIS en México, de ANVISA en Brasil y del ISP en Chile. Los rangos de dosis se verificaron contra el Vademécum Nacional de ANMAT.
- Decisión: la clave de cada medicamento es el código ATC más la Denominación Común Internacional, los dos de la OMS, que identifican el principio activo y valen igual en cualquier país. El producto nacional consultado queda como prueba del dato en `producto_consultado`, no como identidad del medicamento. La columna `sinonimos` recoge variantes regionales del principio activo y formas de sal, no marcas comerciales: las marcas cambian por país y, como la comparación es por inclusión, una marca corta produce falsos positivos.
- Alternativa descartada: usar el certificado de ANMAT como clave, que ata el agente a Argentina.
- Consecuencia: `atc_alternativo` existe porque el código depende de la vía o de la indicación en tres casos: cloruro de potasio oral A12BA01 e intravenoso B05XA01, metotrexato inmunosupresor L04AX03 y oncológico L01BA01, y fentanilo analgésico N02AB03 y anestésico N01AH01.

## ADR-007 · No todos los medicamentos se validan por rango numérico
- Fecha: 25 de septiembre de 2026
- Contexto: al verificar los 22 medicamentos contra los prospectos de ANMAT, 20 salieron "parcial". El motivo no fue un error de la tabla: siete de ellos no tienen una dosis fija por toma porque se dosifican por peso, por coagulograma o por protocolo. Enoxaparina en tratamiento es 1 mg/kg, alteplasa 0,9 mg/kg, heparina se ajusta por coagulograma, la insulina se titula por glucemia, el potasio intravenoso va por peso y velocidad de infusión, y fentanilo y morfina son individualizados.
- Decisión: la columna `validar_dosis` dice si ese medicamento se compara contra un rango. En los siete que van por protocolo vale `no`, y `nota_dosis` explica por qué. Siguen marcados como de alto riesgo, así que la receta sigue yendo a Farmacia Hospitalaria con auditoría humana: cambia el motivo, no el destino.
- Alternativa descartada: inventar un rango para esos siete. Habría marcado AMB-3 en recetas correctas y, peor, habría dado por válida una dosis peligrosa que cayera dentro del rango inventado.
- Consecuencia: `validar.py` comprueba el rango solo cuando `validar_dosis` es `si`. Ninguno de los casos del conjunto de prueba con AMB-3 usa un medicamento de los siete, así que las etiquetas no cambian.

## ADR-008 · Los códigos CIE-10 se toman de la lista tabular de la OPS, no de adaptaciones nacionales
- Fecha: 25 de septiembre de 2026
- Contexto: hay varias versiones de la CIE-10 y no coinciden. La CIE-10-ES española y la CIE-10-CM estadounidense agregan códigos y cambian redacciones respecto de la clasificación de la OMS. Al verificar los 22 códigos contra la lista tabular del Volumen 1 de la OPS aparecieron ocho diferencias.
- Decisión: la fuente es la lista tabular del Volumen 1 de la OPS/OMS, Publicación Científica 554, que es la CIE-10 de la OMS en español y la que usan los países de la región. Cada fila de `cie10.csv` lleva la fuente y la fecha de consulta.
- Hallazgo que motivó el cambio: `K35.2` no existe en esa clasificación. El código de apendicitis aguda con peritonitis generalizada es `K35.0`; `K35.2` aparece solo en revisiones posteriores y en la CIE-10-CM. Se corrigió en `cie10.csv`, en el cuadro CC-08 del banco clínico y en los casos GS-10 y FA-02 del conjunto de prueba.
- Otras siete correcciones de redacción: `I26.9` corazón pulmonar agudo y no cor pulmonale, `I21.9` infarto agudo del miocardio, `A41.9` septicemia y no sepsis en esta edición, `J93.0` neumotórax espontáneo a presión y no a tensión, `Z34.9` sin coma, `K21.0` enfermedad del reflujo y no por reflujo, y `E11.9` con la subdivisión de cuarto carácter completa.
- Consecuencia: `validar.py` compara el código y la descripción contra esta tabla, así que un documento que traiga `K35.2` ahora se marca como código inexistente, que es lo correcto.

