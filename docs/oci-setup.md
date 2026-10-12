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

**Fecha:** 12 de octubre de 2026
**Estado:** ✅ Deploy funcionando con HTTPS y dominio propio
**Responsable:** Carlos Zunino
**Revisora:** Sabrina

### URLs públicas

| Servicio | URL | Estado |
| :--- | :--- | :--- |
| **UI Streamlit** | https://mediflow-equipo37.duckdns.org/ | ✅ Funcionando |
| **API** | https://mediflow-equipo37.duckdns.org/api/ | ✅ Funcionando |
| **API Docs** | https://mediflow-equipo37.duckdns.org/api/docs | ✅ Funcionando |
| **Health Check** | https://mediflow-equipo37.duckdns.org/api/health | ✅ `{"status":"ok","service":"mediflow-api"}` |

**Redirección:** `http://mediflow-equipo37.duckdns.org/` → `301` → `https://mediflow-equipo37.duckdns.org/`

### Dominio y DNS

| Componente | Valor |
| :--- | :--- |
| **Proveedor** | DuckDNS (gratuito) |
| **Dominio** | `mediflow-equipo37.duckdns.org` |
| **IP** | `144.22.215.79` |

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
| **IP pública** | 144.22.215.79 |
| **Usuario SSH** | `opc` |
| **Clave SSH** | `~/.ssh/mediflow-vm-1.key` |
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
ssh -i "$env:USERPROFILE\.ssh\mediflow-vm-1.key" opc@144.22.215.79
```

### Cómo deployar

#### Stack `infra` (con nginx + HTTPS)

**Nota:** `podman-compose` falla con Python 3.9. Los contenedores se levantan manualmente.

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

**Nota:** Para el DemoDay (27/10/2026) no hace falta renovar. El certificado vence el 10/01/2027.

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

### Pendientes

#### Seguridad de endpoints

- **PUT /rules:** ✅ Ya implementado en `develop` (PR #81). Valida el token: 503 si falta `RULES_ADMIN_TOKEN`, 401 si no coincide, 422 si falta `X-Editor`. La VM corre una versión vieja; hay que redesplegar `develop`.
- **POST /audit/{id}:** No valida token. Es módulo de Cristian; queda así por ahora y se coordina con Camila después de H3.
- **Acción:** Redesplegar `develop` en la VM para que `PUT /rules` funcione con validación de token.

#### ADB (Autonomous Database)

- **Estado:** No implementado en el MVP.
- **Nota:** El `docs/api-contract.md` dice que el MVP usa SQLite. ADB es para Sprint 3.
- **Wallet:** La carpeta `wallet/` está vacía (no se necesita para el MVP).

#### podman-compose

- **Estado:** Roto (falla con Python 3.9).
- **Workaround:** Los contenedores se levantan manualmente con `podman run`.
- **Fix:** Instalar Python 3.11+ en la VM.

### Historial de cambios

| Fecha | Cambio |
| :--- | :--- |
| 9 oct 2026 | Deploy inicial en VM ARM. 3 contenedores corriendo (api, ui, worker). |
| 12 oct 2026 | Deploy con HTTPS y dominio (DuckDNS + Let's Encrypt + nginx). 4 contenedores en stack `infra`. Bloque `/openapi.json` para Swagger. |