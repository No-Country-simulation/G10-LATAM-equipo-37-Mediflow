# Configuración de OCI para MediFlow

Guía paso a paso para crear y configurar los buckets, políticas y credenciales de OCI que usa MediFlow.

**Referencias:**
- Plan: `docs/plan.md`, paquete N2-02
- Políticas IAM: `infra/oci/policies.txt`
- Variables de entorno: `.env.example`
- Script de VM: `infra/oci/setup-vm.sh`

---

## 1. Buckets (N2-02)

MediFlow usa **dos buckets separados** por entorno:

| Bucket | Entorno | Quién escribe | Uso |
|---|---|---|---|
| `mediflow-dev` | Desarrollo | `mediflow-devs` (humanos) | Pruebas locales y desarrollo |
| `mediflow-prod` | Producción | `mediflow-vm` (dynamic group) | VM en producción |

**Regla clave:** un dev **no puede escribir** en `mediflow-prod`. Solo la VM lo hace.

### Crear los buckets

```bash
# Ver el compartment
COMPARTMENT_ID="<COMPARTMENT_OCID>"

# Bucket dev
oci os bucket create \
  --name mediflow-dev \
  --compartment-id "$COMPARTMENT_ID" \
  --storage-tier Standard

# Bucket prod
oci os bucket create \
  --name mediflow-prod \
  --compartment-id "$COMPARTMENT_ID" \
  --storage-tier Standard
```

---

## 2. Despliegue en OCI (N2-01)

### Estado actual

**Última revisión:** 27 de octubre de 2026
**Estado:** ✅ Deploy funcionando con HTTPS y dominio propio. Cada merge a `main` despliega con GitHub Actions (`.github/workflows/deploy.yml`)
**Responsable:** Carlos Zunino
**Revisora:** Sabrina

### URLs públicas

| Servicio | URL | Estado |
| :--- | :--- | :--- |
| **UI Streamlit** | https://mediflow-equipo37.duckdns.org/ | ✅ Funcionando |
| **API** | https://mediflow-equipo37.duckdns.org/api/ | ✅ Funcionando |
| **API Docs** | https://mediflow-equipo37.duckdns.org/api/docs | ✅ Funcionando (requiere el bloque `/openapi.json` en `infra/nginx.conf`) |
| **Health Check** | https://mediflow-equipo37.duckdns.org/api/health | ✅ `{"status":"ok","service":"mediflow-api"}` |

**Redirección:** `http://mediflow-equipo37.duckdns.org/` → `301` → `https://mediflow-equipo37.duckdns.org/`

### Dominio y DNS

| Componente | Valor |
| :--- | :--- |
| **Proveedor** | DuckDNS (gratuito) |
| **Dominio** | `mediflow-equipo37.duckdns.org` |
| **IP** | IP pública de la VM (ver consola de OCI) |

### Certificado SSL

| Componente | Valor |
| :--- | :--- |
| **Emisor** | Let's Encrypt |
| **Herramienta** | Certbot 3.1.0 |
| **Válido hasta** | 10 de enero de 2027 |
| **Ubicación** | `/etc/letsencrypt/live/mediflow-equipo37.duckdns.org/` |
| **Renovación** | Manual (`sudo certbot renew`) |

### Infraestructura

#### VM

| Componente | Valor |
| :--- | :--- |
| **Shape** | VM.Standard.A1.Flex (ARM) |
| **OCPU** | 2 |
| **RAM** | 12 GB |
| **Disco** | 30 GB (raíz) + 15 GB (/var/oled) |
| **Sistema Operativo** | Oracle Linux 9.8 (aarch64) |
| **IP pública** | ver consola de OCI |
| **Usuario SSH** | `opc` |
| **Clave SSH** | la entrega el responsable de infraestructura; nunca se sube al repositorio |
| **Región** | sa-saopaulo-1 |
| **Dominio de disponibilidad** | AD-1 |

#### Red

| Componente | Valor |
| :--- | :--- |
| **VCN** | vcn-mediflow (10.0.0.0/16) |
| **Subred** | subnet-mediflow-public (10.0.0.0/24) |
| **Internet Gateway** | igw-mediflow |
| **Route Table** | Default Route Table for vcn-mediflow |

#### Puertos abiertos

| Puerto | Protocolo | Origen | Descripción |
| :--- | :--- | :--- | :--- |
| 22 | TCP | 0.0.0.0/0 | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP (redirige a HTTPS) |
| 443 | TCP | 0.0.0.0/0 | HTTPS |

**Nota:** Los puertos 8000 y 8501 ya no están expuestos directamente. Todo pasa por nginx (80/443).

### Cómo conectarse a la VM

```bash
ssh -i <ruta-de-la-clave> opc@<IP_DE_LA_VM>
```

### Cómo deployar

#### Despliegue automático

El camino normal es hacer merge a `main` por PR. El workflow `deploy.yml` se conecta por SSH, hace `git reset` a `origin/main`, reconstruye con `docker compose -f infra/docker-compose.yml`, verifica `/api/health` y, si algo falla, vuelve al commit anterior. El paso SSH tiene un límite de 30 minutos (`command_timeout`), porque la reconstrucción completa tarda más de 10.

#### Despliegue manual (respaldo)

Solo si el workflow no está disponible. Los contenedores se pueden levantar a mano con `podman run`:

```bash
# 1. Construir las imágenes
cd /opt/mediflow
sudo podman build -t localhost/infra_api:latest -f api/Dockerfile .
sudo podman build -t localhost/infra_ui:latest -f ui/Dockerfile .
sudo podman build -t localhost/infra_worker:latest -f worker/Dockerfile .

# 2. Crear la red (si no existe)
sudo podman network create infra_default 2>/dev/null

# 3. Levantar API
sudo podman run -d --name infra_api_1 \
  --network infra_default \
  --network-alias api \
  --env-file /opt/mediflow/.env \
  -v /opt/mediflow/wallet:/app/wallet:ro \
  localhost/infra_api:latest

# 4. Levantar UI
sudo podman run -d --name infra_ui_1 \
  --network infra_default \
  --network-alias ui \
  --env-file /opt/mediflow/.env \
  -e API_URL=http://api:8000 \
  localhost/infra_ui:latest

# 5. Levantar worker
sudo podman run -d --name infra_worker_1 \
  --network infra_default \
  --env-file /opt/mediflow/.env \
  -v /opt/mediflow/wallet:/app/wallet:ro \
  localhost/infra_worker:latest

# 6. Levantar nginx
sudo podman run -d --name infra_nginx_1 \
  --network infra_default \
  -p 80:80 -p 443:443 \
  -v /opt/mediflow/infra/nginx.conf:/etc/nginx/conf.d/default.conf:ro \
  -v /etc/letsencrypt:/etc/letsencrypt:ro \
  -v /var/www/certbot:/var/www/certbot:ro \
  docker.io/library/nginx:stable
```

#### Ver los logs

```bash
sudo podman logs infra_nginx_1 --tail 50
sudo podman logs infra_api_1 --tail 50
sudo podman logs infra_ui_1 --tail 50
sudo podman logs infra_worker_1 --tail 50
```

#### Ver el estado de los contenedores

```bash
sudo podman ps
```

### Configuración de nginx

**Archivo:** `/opt/mediflow/infra/nginx.conf`

```nginx
# Redirigir HTTP a HTTPS (excepto el desafío de Certbot)
server {
    listen 80;
    server_name mediflow-equipo37.duckdns.org;
    client_max_body_size 25m;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# Servidor HTTPS
server {
    listen 443 ssl;
    server_name mediflow-equipo37.duckdns.org;
    client_max_body_size 25m;

    ssl_certificate     /etc/letsencrypt/live/mediflow-equipo37.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mediflow-equipo37.duckdns.org/privkey.pem;

    location = /openapi.json {
        proxy_pass http://api:8000/openapi.json;
        proxy_set_header Host $host;
    }

    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_read_timeout 180s;
    }

    location / {
        proxy_pass http://ui:8501/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 180s;
    }
}
```

### Renovación del certificado SSL

El certificado dura 90 días. Para renovarlo manualmente:

```bash
sudo certbot renew
```

**Nota:** el certificado vence el 10/01/2027. Renovarlo antes de esa fecha.

### Archivos de configuración

#### `.env` (en `/opt/mediflow/.env`)

Variables configuradas para la VM:

```bash
ENV=dev
OCI_REGION=sa-saopaulo-1
OCI_NAMESPACE=<OCI_NAMESPACE>
OCI_BUCKET_DEV=mediflow-dev
OCI_BUCKET_PROD=mediflow-prod
OCI_COMPARTMENT=<COMPARTMENT_OCID>
OCI_AUTH=instance_principal
ONS_TOPIC_OCID=<ONS_TOPIC_OCID>
STORAGE_BACKEND=oci
RULES_ADMIN_TOKEN=<TOKEN>
```

### Estado al cierre del hackathon

- **PUT /rules:** valida token. Responde 503 si falta `RULES_ADMIN_TOKEN`, 401 si el token no coincide y 422 si falta `X-Editor`.
- **POST /audit/{id}:** no valida token. Queda para la siguiente versión.
- **Autonomous Database:** fuera del MVP. El estado del grafo y la cola de revisión usan SQLite en el volumen `mediflow-data`. La carpeta `wallet/` no se usa.

### Alertas (N2-09 y N3-08)

- **Canal activo: n8n → Slack.** El contenedor `n8n` recibe el webhook en `N8N_WEBHOOK_URL` y publica en el canal de Slack de la guardia. Verificado de punta a punta en la URL pública el 24/10/2026. Detalle en `docs/n8n-alertas.md`.
- **Respaldos:** si n8n no responde, la alerta cae a Discord (`DISCORD_WEBHOOK_URL`) y después a OCI Notifications por correo (`ONS_TOPIC_OCID`). Se usa un solo canal por alerta.
- **Privacidad:** con `ALERTA_OCULTAR_PACIENTE=true`, la alerta no incluye el nombre del paciente.
- `api` y `worker` cargan `/opt/mediflow/.env`, así que las dos leen las mismas variables de alertas.

### Historial de cambios

| Fecha | Cambio |
| :--- | :--- |
| 9 oct 2026 | Deploy inicial en VM ARM. 3 contenedores corriendo (api, ui, worker). |
| 12 oct 2026 | Deploy con HTTPS y dominio (DuckDNS + Let's Encrypt + nginx). 4 contenedores en stack `infra`. Bloque `/openapi.json` para Swagger. |
| 16 oct 2026 | Alertas en tiempo real con n8n → Slack (#83 y #128). |
| 18 y 19 oct 2026 | Deploy automático con `docker compose`, rollback y aviso a Discord. |
| 23 oct 2026 | `command_timeout` de 30 minutos en el paso SSH (#154). |
| 27 oct 2026 | Revisión de cierre: se quitan la IP, la ruta de la clave, el OCID del topic y el correo personal; alertas actualizadas a n8n → Slack. |

## 8. Alertas en tiempo real (N2-09)

### Topic de OCI Notifications

- **Nombre:** `mediflow-alertas`
- **OCID:** en `ONS_TOPIC_OCID` del `.env` de la VM (no se publica)
- **Variable de entorno:** `ONS_TOPIC_OCID`

### Suscripciones

| Protocolo | Endpoint | Estado | Notas |
|---|---|---|---|
| EMAIL | correo del responsable de guardia | ✅ ACTIVE | Respaldo de último nivel |
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
N8N_WEBHOOK_URL=http://n8n:5678/webhook/mediflow-alert   # canal activo (n8n → Slack)
DISCORD_WEBHOOK_URL=         # URL del webhook de Discord
ONS_TOPIC_OCID=              # OCID del topic de OCI Notifications
