# Evaluación de MediFlow · 13/10/2026 10:53

| Métrica | Valor |
|---|---|
| Accuracy de clasificación | 83% (52/63) |
| Accuracy de destino | 62% (39/63) |
| Acierto de la marca de auditoría | 60% (38/63) |
| **Recall de urgencias** | 94% (16/17) |
| Casos fuera de alcance resueltos | 0% (0/12) |
| Puerta de legibilidad (imágenes media y severa) | 46% (6/13) |
| Tasa de revisión humana | 45% (34/76) |
| Latencia p50 | 3.9 s |
| Latencia p95 | 5.2 s |
| Casos correctos en todo | 41% (31/76) |

Variantes evaluadas: 63 legibles y 13 degradadas. Falsas urgencias: 10. Errores de ejecución: 0.

Las métricas de clasificación y destino se calculan sobre los documentos legibles. Las imágenes media y severa se miden aparte, en la puerta de legibilidad: de ellas no se espera el destino del documento original sino que el agente reconozca que no puede leerlas.

## Fallos

| Caso | Qué falló | Esperado | Obtenido |
|---|---|---|---|
| GS-01 | destino | Farmacia_Hospitalaria | Cola_Emergencia_Medica |
| GS-01 | urgencia | False | True |
| GS-01 (leve) | destino | Farmacia_Hospitalaria | Cola_Revision_Humana |
| GS-01 (leve) | auditoria | False | True |
| GS-01 (leve) | tipo | Receta Medica |  |
| GS-02 (media) | tipo | Receta Medica |  |
| GS-02 (media) | categoria_amb | AMB-4 |  |
| GS-04 | destino | Farmacia_Hospitalaria | Cola_Emergencia_Medica |
| GS-04 | auditoria | True | False |
| GS-04 | urgencia | False | True |
| GS-05 | destino | Farmacia_Hospitalaria | Cola_Revision_Humana |
| GS-07 (leve) | destino | Cola_Emergencia_Medica | Cola_Revision_Humana |
| GS-07 (leve) | auditoria | False | True |
| GS-07 (leve) | urgencia | True | False |
| GS-07 (leve) | tipo | Informe de Estudio por Imagenes |  |
| GS-10 | auditoria | True | False |
| GS-10 | categoria_amb | AMB-4 |  |
| GS-10 | auditoria | True | False |
| GS-10 | categoria_amb | AMB-4 |  |
| GS-11 (media) | tipo | Informe de Estudio por Imagenes |  |
| GS-11 (media) | categoria_amb | AMB-4 |  |
| GS-12 | destino | Historia_Clinica_Electronica | Cola_Revision_Humana |
| GS-12 | auditoria | False | True |
| GS-12 | destino | Historia_Clinica_Electronica | Cola_Revision_Humana |
| GS-12 | auditoria | False | True |
| GS-14 | auditoria | True | False |
| GS-14 | auditoria | True | False |
| GS-20 (leve) | destino | Auditoria_Autorizaciones | Cola_Revision_Humana |
| GS-20 (leve) | auditoria | False | True |
| GS-20 (leve) | tipo | Orden de Solicitud de Procedimiento |  |
| GS-21 | destino | Auditoria_Autorizaciones | Cola_Emergencia_Medica |
| GS-21 | urgencia | False | True |
| GS-22 | destino | Cola_Revision_Humana | Auditoria_Autorizaciones |
| GS-23 | destino | Historia_Clinica_Electronica | Cola_Emergencia_Medica |
| GS-23 | urgencia | False | True |
| GS-23 (media) | tipo | Epicrisis |  |
| GS-23 (media) | categoria_amb | AMB-4 |  |
| GS-24 | destino | Historia_Clinica_Electronica | Cola_Emergencia_Medica |
| GS-24 | urgencia | False | True |
| GS-24 | destino | Historia_Clinica_Electronica | Cola_Emergencia_Medica |
| GS-24 | urgencia | False | True |
| GS-25 | destino | Historia_Clinica_Electronica | Cola_Emergencia_Medica |
| GS-25 | urgencia | False | True |
| GS-26 | destino | Cola_Revision_Humana | Historia_Clinica_Electronica |
| GS-26 | auditoria | True | False |
| GS-26 | categoria_amb | AMB-4 | AMB-1 |
| GS-27 | auditoria | False | True |
| GS-27 (leve) | destino | Historia_Clinica_Electronica | Cola_Revision_Humana |
| GS-27 (leve) | auditoria | False | True |
| GS-27 (leve) | tipo | Certificado Medico |  |
| GS-28 (media) | tipo | Certificado Medico |  |
| GS-28 (media) | categoria_amb | AMB-4 |  |
| GS-29 | destino | Cola_Revision_Humana | Historia_Clinica_Electronica |
| GS-29 | auditoria | True | False |
| GS-30 | destino | Cola_Revision_Humana | Historia_Clinica_Electronica |
| GS-30 | categoria_amb | AMB-5 |  |
| FA-01 | auditoria | True | False |
| FA-01 | auditoria | True | False |
| FA-02 | destino | Cola_Revision_Humana | Cola_Emergencia_Medica |
| FA-02 | auditoria | True | False |
| FA-02 | urgencia | False | True |
| FA-02 | destino | Cola_Revision_Humana | Cola_Emergencia_Medica |
| FA-02 | auditoria | True | False |
| FA-02 | urgencia | False | True |
| FA-03 | auditoria | True | False |
| FA-03 (leve) | tipo | Otro |  |
| FA-03 (leve) | categoria_amb | AMB-6 |  |
| FA-03 (leve) | motivo_fuera_de_alcance | no_clinico |  |
| FA-04 | destino | Cola_Revision_Humana | Cola_Emergencia_Medica |
| FA-04 | auditoria | True | False |
| FA-04 | urgencia | False | True |
| FA-04 | tipo | Otro | Informe de Estudio por Imagenes |
| FA-04 | categoria_amb | AMB-6 |  |
| FA-04 | motivo_fuera_de_alcance | idioma_no_soportado |  |
| FA-04 | destino | Cola_Revision_Humana | Historia_Clinica_Electronica |
| FA-04 | auditoria | True | False |
| FA-04 | tipo | Otro | Informe de Estudio por Imagenes |
| FA-04 | categoria_amb | AMB-6 |  |
| FA-04 | motivo_fuera_de_alcance | idioma_no_soportado |  |
| FA-06 | auditoria | True | False |
| FA-06 (leve) | tipo | Otro |  |
| FA-06 (leve) | categoria_amb | AMB-6 |  |
| FA-06 (leve) | motivo_fuera_de_alcance | pide_diagnostico |  |
| FA-07 | auditoria | True | False |
| FA-07 | auditoria | True | False |
| M1 (leve) | destino | Farmacia_Hospitalaria | Cola_Revision_Humana |
| M1 (leve) | auditoria | False | True |
| M1 (leve) | tipo | Receta Medica |  |
| M2 (leve) | destino | Farmacia_Hospitalaria | Cola_Revision_Humana |
| M2 (leve) | tipo | Receta Medica |  |
| M3 (leve) | tipo | Receta Medica |  |
| M3 (leve) | categoria_amb | AMB-3 |  |
| M4 (media) | tipo | Receta Medica |  |
| M4 (media) | categoria_amb | AMB-4 |  |
| M5 (media) | tipo | Receta Medica |  |
| M5 (media) | categoria_amb | AMB-4 |  |
| M6 (media) | tipo | Receta Medica |  |
| M6 (media) | categoria_amb | AMB-4 |  |

## Fallos por categoría

| Categoría | Casos |
|---|---|
| AMB-1 | GS-14, GS-14, GS-22, GS-29 |
| AMB-3 | M3 (leve) |
| AMB-4 | GS-10, GS-10, GS-26 |
| AMB-5 | GS-30 |
| AMB-6 | FA-01, FA-01, FA-02, FA-02, FA-03, FA-03 (leve), FA-04, FA-04, FA-06, FA-06 (leve), FA-07, FA-07 |
| Certificado Medico | GS-27, GS-27 (leve) |
| Epicrisis | GS-23, GS-24, GS-24, GS-25 |
| Informe de Estudio por Imagenes | GS-12, GS-12 |
| Orden de Solicitud de Procedimiento | GS-20 (leve), GS-21 |
| Receta Medica | GS-01, GS-01 (leve), GS-04, GS-05, M1 (leve), M2 (leve) |
| legibilidad media | GS-02 (media), GS-11 (media), GS-23 (media), GS-28 (media), M4 (media), M5 (media), M6 (media) |
| urgencia | GS-07 (leve) |
