# MediFlow · Propuesta de proyecto en una página

Para aprobación del equipo · Hackathon ONE G10 · 15 de septiembre al 14 de octubre · Todo en OCI Always Free

**Qué construimos.** Un agente que recibe documentos clínicos (PDF, imagen, texto o JSON), los clasifica, extrae los datos en JSON, calcula un score de confianza, detecta urgencias y los enruta al destino correcto. Lo ambiguo o ilegible va a un auditor humano. Documentos en OCI Object Storage, historial en Autonomous AI Database, todo dentro de Always Free.

**Lo obligatorio (checklist del brief).** Ingesta de texto, PDF e imagen · clasificación con LLM multimodal · extracción JSON validada con Pydantic · grafo de decisión en LangGraph con casos ambiguos y urgentes · Object Storage segregado por estado · demo de 3 escenarios (rutina, urgencia, ambiguo) · README con el diagrama del grafo.

**Los 5 diferenciales que nombra el brief (los hacemos todos).** Reglas de triaje editables sin código · despliegue en VM de OCI con URL pública · visión multimodal para escaneos y recetas manuscritas · panel de auditoría Human-in-the-Loop en Streamlit · alertas en tiempo real por OCI Notifications.

**Nuestro plus.** Obligatorios: reporte diario y semanal al gestor redactado por el agente · evaluación con números y calibración del score · trazabilidad, ver pensar al agente · privacidad por diseño con datos 100 % sintéticos · resiliencia con dos modelos de respaldo, demostrada en vivo en el video. Si el sprint 3 va en tiempo: multilingüe español, portugués e inglés (esfuerzo bajo: el modelo ya entiende los tres idiomas, se agregan ejemplos en cada idioma al golden set y una instrucción al prompt, el JSON de salida no cambia) · segunda opinión entre modelos · aprendizaje desde las correcciones del auditor.

**Si Gemini se cae: dos modelos de respaldo por tipo de entrada.** Cambio automático ante error 429, 5xx o timeout. Cada resultado registra qué modelo lo procesó. El golden set se corre con los tres para conocer la precisión de cada uno. Los tres proveedores tienen capa gratuita sin tarjeta. El documento nunca se pierde: ya está en `recibidos/` antes de llamar a cualquier modelo.

| Entrada | Principal | Respaldo 1 | Respaldo 2 | Si todo falla |
|---|---|---|---|---|
| Texto o JSON | Gemini Flash | Groq, Llama 4 Scout | Mistral Small | Cola "pendiente", reintento cada 5 minutos |
| PDF con capa de texto | PyMuPDF extrae el texto, sigue la fila de arriba | igual | igual | igual |
| PDF escaneado o imagen | Gemini Flash con visión | Mistral Small con visión | Groq, Llama 4 Scout con visión | OCR local con Tesseract más modelo de texto; si la confianza es baja, revisión humana |
| Ilegible (borrosa, oscura, cortada) | Mejora de imagen (contraste, enderezar, ampliar) y un reintento con el principal | Un intento con el respaldo 1 sobre la imagen mejorada | ninguno | Revisión humana con motivo "solicitar nueva captura" |

Nota: el modelo de visión de Groq está en preview y el plan gratuito de Mistral pide aceptar el uso de datos para entrenamiento. Con datos sintéticos no hay problema; con datos reales no se usarían.

**De dónde salen los datos.** Nunca documentos reales, ni propios. Un generador con LLM produce los 5 tipos de documento en español, portugués e inglés, y de cada uno salen texto, JSON, PDF digital e imagen escaneada con ruido (Augraphy). Recetas manuscritas ficticias escritas y fotografiadas por nosotros mismos. Corpus públicos con licencia: CodiEsp (1.000 casos clínicos en español con CIE-10) y MEDDOCAN (1.000 casos con datos personales ficticios). Las fuentes se citan en el README.

**Todo gratis.** LangGraph y Streamlit son open source, n8n se auto-hospeda si se usa, Slack y GitHub en plan gratuito, Gemini, Groq y Mistral en capa gratuita, y toda la infraestructura en OCI Always Free. No entra nada que cueste: ni OpenAI, ni Anthropic, ni OCI Generative AI, ni WhatsApp Business.

**Cronograma.**

| Sprint | Fechas | Resultado |
|---|---|---|
| 1 Fundaciones | 15 a 20 sep | Cuenta OCI, bucket, VM con URL pública, base de datos, repo y CI, contrato JSON, golden set v0 |
| 2 La base | 21 a 27 sep | Texto, PDF e imagen entran y sale el JSON del brief en la carpeta correcta del bucket. 3 escenarios reproducibles |
| 3 Diferenciales | 28 sep a 4 oct | Panel HITL, reglas editables, alertas, respaldos de modelos, reporte diario. Congelamiento de funcionalidades |
| 4 Endurecimiento | 5 a 11 oct | Evaluación final, casos borde, checklist de privacidad, ensayo general |
| Cierre | 12 a 14 oct | Video y entrega de las 4 tareas |

**Cómo trabajamos.** Una cuenta OCI compartida por todo el equipo · un repo en GitHub con revisión por PR y despliegue automático a la VM · demo interna cada viernes y actualización de las Tareas 1 a 4 en la plataforma · nada de código por chat, nada desplegado a mano.

**Preguntas para decidir juntos.**
1. ¿El grafo de decisión lo hacemos en LangGraph o en n8n? ¿Alguien ya trabajó con alguno de los dos?
2. ¿La interfaz en Streamlit o en Next.js? ¿Qué nos da más en cuatro semanas?
3. ¿Gemini como modelo principal con Groq y Mistral de respaldo, o proponen otra combinación gratuita?
4. ¿Estamos de acuerdo con el alcance: lo obligatorio, los 5 diferenciales y los 5 plus? ¿Qué agregarían o quitarían?
5. ¿Multilingüe, segunda opinión y aprendizaje desde la auditoría solo si el sprint 3 cierra en fecha, o alguno debería ser obligatorio?
6. ¿Datos 100 % sintéticos y corpus públicos, sin ningún documento real? ¿Alguien conoce otra fuente con licencia?
7. ¿Qué falta en esta página que ustedes harían distinto?

Con estas respuestas cerramos el proyecto, y el siguiente paso es repartir roles y tareas.
