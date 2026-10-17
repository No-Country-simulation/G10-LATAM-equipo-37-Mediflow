# Guion Demo Day 1 · MediFlow (equipo 37), versión 2

Martes 27/10/2026 · 5 minutos estrictos: contenido de 4:40 + 20 s de margen.
Propuesta de reparto en 8 bloques. El reparto es provisional: quién presenta cada bloque se define en la reunión del equipo. Las partes de Carolina son un borrador para que ella las ajuste.

| Tiempo | Bloque | Quién |
|---|---|---|
| 0:00-0:30 | Problema | Por definir |
| 0:30-1:05 | Solución y cómo funciona | Carolina |
| 1:05-1:45 | Demo rutina GS-28 | Por definir |
| 1:45-2:25 | Demo urgencia GS-07 y alerta | Por definir |
| 2:25-3:05 | Demo GS-06, revisión humana | Por definir |
| 3:05-3:35 | Resultados | Por definir |
| 3:35-4:05 | Cómo trabajamos como equipo | Por definir |
| 4:05-4:40 | Impacto y cierre | Por definir |
| 4:40-5:00 | Margen | — |

## 0:00-0:30 · Problema
"Buenas tardes, somos el equipo 37 y les presentamos MediFlow. En un hospital llegan cada día documentos en PDF, en foto o en texto. Hoy una persona lee cada uno para saber qué es y a dónde va. Eso es lento. Y lo más grave: una urgencia puede quedar enterrada en la pila. MediFlow hace ese primer recorrido: identifica, extrae y enruta. Si tiene dudas, se lo pasa a una persona. En esta demostración usamos documentos sintéticos."

## 0:30-1:05 · Solución y cómo funciona (texto propuesto por Carolina)
"MediFlow clasifica el documento, extrae los datos y aplica reglas para proponer un destino. Si detecta información incompleta o una ambigüedad, lo deriva a revisión humana. Cada decisión queda registrada. No realiza diagnósticos ni sustituye la decisión clínica. Lo vemos con tres casos."

## 1:05-1:45 · Demo rutina GS-28
[Usar GS-28.txt, la versión en texto. En la prueba del 17/10 la foto fue a revisión humana (el OCR leyó solo 6 caracteres, #97). Mostrar la foto solo si el #97 se corrige y se prueba en el ensayo.]

"Primer caso: un documento de rutina. Veamos a dónde lo manda."
"Lo reconoce como certificado médico y lo envía a Historia Clínica Electrónica, sin revisión humana, y lo guarda en OCI Object Storage."

## 1:45-2:25 · Demo urgencia GS-07
"Ahora un caso crítico: un informe con hallazgo de tromboembolismo pulmonar. El agente detecta la urgencia y lo manda directo a la cola de urgencias, sin pasar por revisión. [Y avisa a la guardia: decirlo solo si el flujo de alertas (n8n a Slack) está desplegado y verificado.]"

## 2:25-3:05 · Demo GS-06, revisión humana
"Tercer caso: una receta de amoxicilina que el agente no puede dar por buena con los datos que tiene. No la deja pasar: la manda a revisión humana y deja registrado el motivo."
[Decir solo lo que muestre la pantalla. No decir "dosis fuera de rango" hasta confirmar la traza de GS-06. Con AMB-1 la pantalla dirá "dosis faltante".]
[La corrección y la continuación del flujo se muestran solo si la función de corrección está integrada, desplegada y probada en vivo.]

## 3:05-3:35 · Resultados
"Para medirlo armamos un conjunto de prueba: 45 documentos etiquetados a mano, evaluados en 76 variantes. [Con las cifras finales de N3-01: detectamos [__] de [__] urgencias y acertamos el destino en el [__] % de los casos.] La demo corre con modelos gratuitos."
[No usar la medición de N1-13: era del prompt anterior y hay que reevaluar el nuevo. No decir tiempos por caso hasta medirlos con Groq.]

## 3:35-4:05 · Cómo trabajamos como equipo
"Somos un equipo de 8 personas de [__] países. Trabajamos con un plan dividido en paquetes, cada uno con su responsable. Los cambios entran por pull request, con revisión y pruebas automáticas. Las decisiones importantes quedaron escritas. Y construimos juntos el conjunto de prueba para medir el agente."

## 4:05-4:40 · Impacto y cierre
- "El valor de MediFlow es que buscamos reducir la espera de los documentos urgentes. Lo rutinario avanza solo, y el personal dedica su tiempo a lo que necesita criterio humano."
- "Y cuando el agente duda, no inventa: le pasa el caso a una persona. MediFlow no reemplaza al médico: ordena el camino para que el médico llegue antes. Gracias."
