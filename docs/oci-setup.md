## 8. Alertas en tiempo real (N2-09)

### Topic de OCI Notifications

- **Nombre:** `mediflow-alertas`
- **OCID:** `ocid1.onstopic.oc1.sa-saopaulo-1.amaaaaaaof3op2aa77wg5xnuyc4cxw2wqahukas2shrzamxyg2jhdrlenx2q`
- **Variable de entorno:** `ONS_TOPIC_OCID`

### Suscripciones

| Protocolo | Endpoint | Estado | Notas |
|---|---|---|---|
| EMAIL | `zunino.cau@gmail.com` | ✅ ACTIVE | Recibe alertas de urgencia |
| CUSTOM_HTTPS | Discord webhook | ⚠️ PENDING | OCI no valida webhooks de Discord |

### Cómo funciona

El nodo `notificar` lee `notificacion_generada` del state y llama a `publicar()`. Esta función elige el canal según las variables de entorno:

| Prioridad | Variable | Destino |
|---|---|---|
| 1 | `N8N_WEBHOOK_URL` | n8n (Nivel 3, N3-08) |
| 2 | `DISCORD_WEBHOOK_URL` | Discord/Slack directo |
| 3 | `ONS_TOPIC_OCID` | OCI Notifications (correo) |

### Variables de entorno

```bash
# Alertas (N2-09): prioridad N8N > DISCORD > OCI
# N8N_WEBHOOK_URL=           # (Nivel 3, N3-08)
DISCORD_WEBHOOK_URL=         # URL del webhook de Discord
ONS_TOPIC_OCID=              # OCID del topic de OCI Notifications