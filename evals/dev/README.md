# N1-13: extracción y falsas AMB-1

La evaluación publicada el 13/10 identifica campos faltantes falsos en órdenes,
epicrisis y certificados. El prompt no pedía procedimiento_solicitado ni
diagnostico_egreso aunque rules.yaml los exige. Se agregan esos campos con evidencia
y se aclara quién es el médico emisor de un certificado, sin inventar nombres.

Los seis documentos de extraccion.json son sintéticos y nuevos, separados del golden.
Incluyen controles negativos: diagnóstico ausente, firma ilegible y procedimiento vacío.
No se cambian los requisitos de validación para ocultar faltantes reales.

## Comparación pendiente con modelo real

Guardar el prompt anterior de develop en un archivo UTF-8 y ejecutar desde el repo:

```powershell
python evals/dev/evaluar_extraccion.py --antes prompt-antes.md --despues agent/prompts/extraer.md --salida evals/output/n113-comparacion.json
```

Configurar previamente el mismo proveedor, modelo y credencial para ambos prompts.
Son 12 llamadas externas. El comparador llama directamente al adaptador: un fallo de
proveedor invalida la comparación y nunca se reemplaza por resultados del stub.
Registra aciertos por campo, modelo y consumo. Una regresión o error devuelve código 1.
La ausencia de regresiones no basta para cerrar N1-13: debe comprobarse mejora de la
categoría atacada y repetir la evaluación completa con el equipo para las demás categorías.

Los tests locales solo comprueban el comparador; no prueban mejora del modelo.
AMB-4/AMB-5 se coordinan con #112 de Cristian y el enrutamiento con Néstor (#20).
