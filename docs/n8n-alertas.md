# Alertas urgentes por n8n y Slack

El agente publica las alertas con `publicar()` (`agent/storage/notifications.py`), que prueba los canales en orden de prioridad y pasa al siguiente si uno falla:

1. **n8n** (`N8N_WEBHOOK_URL`, por defecto `http://n8n:5678/webhook/mediflow-alert`). El workflow `infra/n8n/alerta-slack.json` publica `titulo` y `cuerpo` en Slack.
2. **Discord** (`DISCORD_WEBHOOK_URL`).
3. **OCI Notifications** (`ONS_TOPIC_OCID`).

Si n8n no responde, la alerta sale por Discord y, si este también falla, por OCI. Solo si fallan todos los canales configurados el nodo `notificar` registra `enviada: False`.

## Configuración

1. Copia `.env.example` a `.env` si aún no existe.
2. Crea un Slack Incoming Webhook para el canal de guardia y guarda su URL solo en `.env` como `SLACK_WEBHOOK_URL`. No la agregues al workflow ni al repositorio.
3. Conserva `N8N_WEBHOOK_URL=http://n8n:5678/webhook/mediflow-alert` cuando uses Docker Compose. El editor de n8n solo se publica en `127.0.0.1:5678`; para abrirlo en la VM usa `ssh -L 5678:127.0.0.1:5678 opc@<IP_VM>`.
4. Levanta la infraestructura desde la raíz del repositorio (`--env-file` es necesario para que Compose lea `SLACK_WEBHOOK_URL` y `GENERIC_TIMEZONE`):

   ```bash
   docker compose --env-file .env -f infra/docker-compose.yml up -d --build
   ```

El entrypoint del contenedor n8n importa **y publica** el workflow (`import:workflow` + `publish:workflow`) en cada arranque. Sin la publicación el webhook de producción responde 404. No hace falta activarlo desde el editor.

El volumen `n8n-data` conserva el workflow y la clave de cifrado de n8n. No lo borres al actualizar el servicio.

### Variables de entorno de n8n

- El contenedor **no** recibe el `.env` completo: solo `SLACK_WEBHOOK_URL` y la configuración propia de n8n. Así las claves de los modelos y las credenciales de la base no quedan al alcance de los workflows ni del editor.
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` es necesario porque el workflow lee `$env.SLACK_WEBHOOK_URL`; al ser la única variable sensible del contenedor, la exposición queda limitada a ella. Aun así, solo personas de confianza deben acceder al editor.
- Zona horaria: se configura con `GENERIC_TIMEZONE` en `.env` (se aplica también a `TZ`). Por defecto `America/Argentina/Buenos_Aires`; cámbiala si el equipo de guardia usa otra.
- Versión de la imagen: fijada en `infra/docker-compose.yml` (`N8N_VERSION`, por defecto `2.43.6`). El entrypoint depende de `publish:workflow` (n8n 2.x); actualiza la versión a propósito y vuelve a verificar el flujo.

### Despliegue manual con Podman

En la VM que usa Podman, agrega n8n a la red existente para que la API resuelva el alias `n8n`. Pasa solo `SLACK_WEBHOOK_URL` (no `--env-file`); exporta antes la variable en tu shell (`export SLACK_WEBHOOK_URL=...`) para que `-e SLACK_WEBHOOK_URL` la tome sin escribirla en el historial:

```bash
sudo podman volume create n8n-data
sudo -E podman run -d --name infra_n8n_1 \
  --network infra_default --network-alias n8n \
  -p 127.0.0.1:5678:5678 \
  -e SLACK_WEBHOOK_URL \
  -e N8N_HOST=localhost -e N8N_PORT=5678 -e N8N_PROTOCOL=http \
  -e N8N_EDITOR_BASE_URL=http://localhost:5678/ \
  -e N8N_SECURE_COOKIE=false -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e GENERIC_TIMEZONE=America/Argentina/Buenos_Aires \
  -e TZ=America/Argentina/Buenos_Aires \
  -v n8n-data:/home/node/.n8n \
  -v /opt/mediflow/infra/n8n/alerta-slack.json:/home/node/workflow.json:ro,Z \
  docker.n8n.io/n8nio/n8n:2.43.6
sudo podman exec infra_n8n_1 n8n import:workflow --input=/home/node/workflow.json
sudo podman exec infra_n8n_1 n8n publish:workflow --id=mediflow-alert-slack
sudo podman restart infra_n8n_1
```

Reinicia el contenedor tras publicar: n8n registra el webhook de producción al arrancar. El `.env` de la VM debe contener `N8N_WEBHOOK_URL=http://n8n:5678/webhook/mediflow-alert`. Los contenedores API y n8n deben compartir `infra_default`.

## Privacidad (PII)

El mensaje de alerta incluye el nombre del paciente. Con datos reales, esto envía datos personales de salud a un servicio externo (Slack): **solo es aceptable con datos sintéticos**. Para omitirlo define `ALERTA_OCULTAR_PACIENTE=true` en el `.env` de la API; el mensaje dirá “paciente (nombre omitido)”.

## Escape de texto para Slack

El workflow escapa `&`, `<` y `>` en título y cuerpo (`&amp;`, `&lt;`, `&gt;`) antes de enviar a Slack, de modo que `<!channel>`, `<!here>` o enlaces `<...>` presentes en el documento se muestran como texto y no generan menciones ni enlaces.

## Verificación

Prueba rápida del webhook, con n8n activo y `SLACK_WEBHOOK_URL` configurada:

```bash
curl -fsS -X POST http://localhost:5678/webhook/mediflow-alert \
  -H 'Content-Type: application/json' \
  -d '{"titulo":"Alerta_Guardia_Medica","cuerpo":"Urgencia de prueba N3-08 <!channel> & co"}'
```

Comprueba que Slack muestra el texto literal `<!channel> & co` sin mencionar al canal.

### Checklist de verificación de punta a punta tras el despliegue (GS-07, sintético)

Usa solo el documento sintético GS-07 contra la URL pública (`https://<DOMINIO_PUBLICO>`).

- [ ] `docker compose ps` (o `podman ps`) muestra `n8n` en ejecución y `docker compose exec n8n env | grep -c API_KEY` devuelve `0` (no recibe el `.env`).
- [ ] El webhook de producción responde 200 (no 404): el curl de arriba funciona.
- [ ] Envía GS-07 a la API pública (`POST https://<DOMINIO_PUBLICO>/...`, ver `docs/api-contract.md`) con `N8N_WEBHOOK_URL` configurada.
- [ ] La respuesta trae `notificacion_generada` y el trace del nodo `notificar` indica `enviada: true`.
- [ ] El mensaje llega al canal de Slack de guardia, con la hora en la zona horaria configurada.
- [ ] Con `ALERTA_OCULTAR_PACIENTE=true` el mensaje no incluye el nombre del paciente.
- [ ] Detén n8n (`docker compose stop n8n`), repite el envío y confirma que la alerta sale por Discord u OCI (respaldo); vuelve a iniciar n8n.
- [ ] No se usaron datos reales de pacientes en ningún paso.
