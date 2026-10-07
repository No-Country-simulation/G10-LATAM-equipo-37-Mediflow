# Recetas manuscritas

Una por persona, M1 a M8, según el reparto de `evals/golden/plan_golden.csv`. Cada quien escribe a
mano una receta con un paciente inventado, la fotografía con el teléfono y la guarda como `M1.jpg`
… `M8.jpg`.

## La etiqueta de cada receta

Al lado de cada foto va su etiqueta en un archivo propio, `M1.json` … `M8.json`, con lo que
realmente dice la receta. Un archivo por receta, nunca uno compartido: así ningún PR choca con otro.

```json
{"id": "M5", "paciente": "Lucía Verón", "edad": 34, "medicamento": "Nitrofurantoína",
 "dosis": "100 mg", "frecuencia": "cada 6 horas", "duracion": "5 días",
 "resultado_esperado": "ambiguedad"}
```

Si un dato no está en la receta, como la duración de una insulina basal, va `null`, sin comillas.
El `resultado_esperado` es el de la fila de esa receta en el plan.

## Niveles de legibilidad

| Recetas | Nivel | Cómo se ve la foto |
|---|---|---|
| M1, M2 y M3 | leve | Buena luz, de frente, letra clara: se lee sin esfuerzo |
| M4, M5 y M6 | media | Letra apurada, foto algo inclinada o con sombra: se lee, pero cuesta |
| M7 y M8 | severa | Letra muy apurada, poca luz, foto movida o cortada: a una persona le cuesta leerla, pero sigue siendo una receta |

## Tres reglas

1. **Escrita a mano de verdad y fotografiada.** Nada de imágenes generadas con IA ni de texto
   impreso imitando letra: lo que se prueba es si el agente lee manuscrita real.
2. **Datos inventados que parezcan reales.** Ninguna palabra como "ficticio", "simulado" o
   "prueba" en nombres, matrículas, membretes o sellos: un documento real no la trae y el agente
   podría usarla como pista.
3. **El nivel lo fija el plan.** Una foto más legible o menos legible que su nivel cambia el
   resultado esperado y la prueba deja de medir lo que tiene que medir.
