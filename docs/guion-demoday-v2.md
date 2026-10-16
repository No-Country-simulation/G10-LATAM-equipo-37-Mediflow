# Guion Demo Day 1 · MediFlow (equipo 37), versión 2

Martes 27/10/2026 · 5 minutos estrictos · Diana y Carolina.
Propuesta de reparto en 7 bloques. Las partes de Carolina son un borrador para que ella las ajuste.

| Tiempo | Bloque | Quién |
|---|---|---|
| 0:00-0:35 | Problema | Diana |
| 0:35-1:10 | Solución y cómo funciona | Carolina |
| 1:10-1:50 | Demo rutina GS-28 | Diana opera, Carolina explica |
| 1:50-2:35 | Demo urgencia GS-07 y alerta | Carolina opera, Diana explica |
| 2:35-3:20 | Demo GS-06, revisión humana | Carolina |
| 3:20-3:55 | Resultados | Diana |
| 3:55-4:25 | Cómo trabajamos como equipo | Diana o Carolina |
| 4:25-5:00 | Impacto y cierre | Las dos |

## 0:00-0:35 · Problema (Diana)
"Buenas tardes, somos el equipo 37 y les presentamos MediFlow. En un hospital llegan cada día cientos de documentos, en PDF, en foto o en texto. Hoy una persona lee cada uno para saber qué es y a dónde va. Eso es lento. Y lo más grave: una urgencia puede quedar enterrada en la pila. MediFlow hace ese primer recorrido: identifica, extrae y enruta. Si tiene dudas, se lo pasa a una persona. En esta demostración usamos documentos sintéticos."

## 0:35-1:10 · Solución y cómo funciona (Carolina)
"MediFlow recibe el documento, lo clasifica, extrae los datos clave, revisa que sean consistentes y lo envía al destino correcto. Cada paso está separado: clasificación, extracción, validación y enrutamiento. Si falta información o hay una duda, interviene una persona. MediFlow no reemplaza el diagnóstico ni la decisión clínica. Lo vemos con tres casos."

## 1:10-1:50 · Demo rutina GS-28
- Diana: "Primer caso: un documento de rutina. Veamos a dónde lo manda."
- Carolina: "Lo reconoce como certificado médico y lo envía a Historia Clínica Electrónica, sin revisión humana, en segundos, y lo guarda en OCI Object Storage."

## 1:50-2:35 · Demo urgencia GS-07
- Diana: "Ahora un caso crítico: un informe con hallazgo de tromboembolismo pulmonar. El agente detecta la urgencia, lo manda directo a la cola de urgencias, sin pasar por revisión [y avisa a la guardia: solo si el #119 está desplegado]. Todo en segundos."

## 2:35-3:20 · Demo GS-06, revisión humana (Carolina)
"Tercer caso: una receta de amoxicilina con una dosis que el agente no puede dar por buena. No la deja pasar: la manda a revisión humana. Un auditor la revisa, la corrige y el flujo sigue."

## 3:20-3:55 · Resultados (Diana)
"Para medirlo armamos un conjunto de prueba: 45 documentos etiquetados a mano, evaluados en 76 variantes. [Con las cifras finales de N3-01: detectamos [__] de [__] urgencias y acertamos el destino en el [__] % de los casos.] La demo corre con modelos gratuitos."

## 3:55-4:25 · Cómo trabajamos como equipo
"Somos un equipo de [__] personas de [__] países. Trabajamos con un plan dividido en paquetes, cada uno con su responsable. Todo cambio entró por un pull request chico, revisado por el dueño de cada módulo y con pruebas automáticas. Las decisiones importantes quedaron escritas. Y construimos juntos el conjunto de prueba para medir el agente."

## 4:25-5:00 · Impacto y cierre
- Diana: "El valor de MediFlow es que ninguna urgencia queda esperando en una pila: llega a su destino en segundos. Lo rutinario avanza solo, y el personal dedica su tiempo a lo que necesita criterio humano."
- Carolina: "Y cuando el agente duda, no inventa: le pasa el caso a una persona. MediFlow no reemplaza al médico: ordena el camino para que el médico llegue antes. Gracias."

