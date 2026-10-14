# Alertas urgentes por n8n y Slack

El agente envía las alertas generadas al webhook interno `http://n8n:5678/webhook/mediflow-alert`. El workflow exportado en `infra/n8n/alerta-slack.json` publica `titulo` y `cuerpo` en Slack. Si `N8N_WEBHOOK_URL` no está configurada, se conserva la publicación existente por OCI Notifications.

## Configuración

1. Copia `.env.example` a `.env` si aún no existe.
2. Crea un Slack Incoming Webhook para el canal de guardia y guarda su URL solo en `.env` como `SLACK_WEBHOOK_URL`. No la agregues al workflow ni al repositorio.
3. En `.env`, conserva `N8N_WEBHOOK_URL=http://n8n:5678/webhook/mediflow-alert` cuando uses Docker Compose. El servicio n8n solo publica el editor en `127.0.0.1:5678`; para abrirlo en la VM, usa `ssh -L 5678:127.0.0.1:5678 opc@<IP_VM>`.
4. Levanta la infraestructura desde la raíz del repositorio:

   ```bash
   docker compose -f infra/docker-compose.yml up -d --build
   ```

5. Importa el workflow montado en el contenedor y actívalo desde el editor:

   ```bash
   docker compose -f infra/docker-compose.yml exec n8n \
     n8n import:workflow --input=/home/node/workflow.json
   ```

El volumen `n8n-data` conserva el workflow y la clave de cifrado de n8n. No borres este volumen al actualizar el servicio. Las expresiones del workflow leen `SLACK_WEBHOOK_URL` del entorno del contenedor.

El acceso al editor queda limitado al loopback de la VM. Como el workflow puede leer variables de entorno, solo deben acceder al editor personas de confianza.

### Despliegue manual con Podman

En la VM que usa Podman, agrega n8n a la red existente para que API pueda resolver el alias `n8n`:

```bash
sudo podman volume create n8n-data
sudo podman run -d --name infra_n8n_1 \
  --network infra_default --network-alias n8n \
  -p 127.0.0.1:5678:5678 \
  --env-file /opt/mediflow/.env \
  -e N8N_HOST=localhost -e N8N_PORT=5678 -e N8N_PROTOCOL=http \
  -e N8N_EDITOR_BASE_URL=http://localhost:5678/ \
  -e N8N_SECURE_COOKIE=false -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e GENERIC_TIMEZONE=America/Argentina/Buenos_Aires \
  -e TZ=America/Argentina/Buenos_Aires \
  -v n8n-data:/home/node/.n8n \
  -v /opt/mediflow/infra/n8n/alerta-slack.json:/home/node/workflow.json:ro,Z \
  docker.n8n.io/n8nio/n8n:latest
sudo podman exec infra_n8n_1 n8n import:workflow --input=/home/node/workflow.json
```

El `.env` de la VM debe contener `N8N_WEBHOOK_URL=http://n8n:5678/webhook/mediflow-alert` y el `SLACK_WEBHOOK_URL` de Slack. Los contenedores API y n8n deben compartir `infra_default`.

## Verificación

Con n8n activo y `SLACK_WEBHOOK_URL` configurada, ejecuta desde la raíz:

```bash
curl -fsS -X POST http://localhost:5678/webhook/mediflow-alert \
  -H 'Content-Type: application/json' \
  -d '{"titulo":"Alerta_Guardia_Medica","cuerpo":"Urgencia de prueba N3-08"}'
```
Comprueba que el canal de Slack recibió “Urgencia de prueba N3-08”. El agente usa ese mismo endpoint cuando una urgencia genera `notificacion_generada`; la prueba automatizada de `agent/tests/test_notificar.py` confirma que ese nodo publica y tolera fallos del webhook.
Usa únicamente datos sintéticos para probar y limita el acceso al canal de Slack: no envíes datos reales de pacientes a servicios externos.
