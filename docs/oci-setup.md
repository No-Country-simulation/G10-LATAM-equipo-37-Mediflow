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
COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaklh5si4fxiesxrqwnb3j62yxdui2zx6swahioi4wo3jrkwm6qcq"

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


---

## 2. Despliegue en OCI (N2-01)

### Estado actual

**Fecha:** 9 de octubre de 2026
**Estado:** ✅ Deploy funcionando (HTTP, sin dominio)
**Responsable:** Carlos Zunino

### URLs públicas

| Servicio | URL | Estado |
| :--- | :--- | :--- |
| **API** | http://144.22.215.79:8000 | ✅ Funcionando |
| **API Docs** | http://144.22.215.79:8000/docs | ✅ Funcionando |
| **UI Streamlit** | http://144.22.215.79:8501 | ✅ Funcionando |
| **Health Check** | http://144.22.215.79:8000/health | ✅ `{"status":"ok"}` |

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
| 80 | TCP | 0.0.0.0/0 | HTTP |
| 443 | TCP | 0.0.0.0/0 | HTTPS |
| 8000 | TCP | 0.0.0.0/0 | API FastAPI |
| 8501 | TCP | 0.0.0.0/0 | UI Streamlit |

### Cómo conectarse a la VM

```bash
ssh -i "$env:USERPROFILE\.ssh\mediflow-vm-1.key" opc@144.22.215.79

```

### Cómo deployar

#### Primera vez

```bash
# En la VM, como usuario opc
cd /opt/mediflow
sudo podman-compose -f docker-compose.dev.yml up -d --build
```

#### Actualizar el código

```bash
# En la VM
cd /opt/mediflow
git pull origin develop
sudo podman-compose -f docker-compose.dev.yml up -d --build
```

#### Ver los logs

```bash
sudo podman logs mediflow_api_1 --tail 50
sudo podman logs mediflow_ui_1 --tail 50
sudo podman logs mediflow_worker_1 --tail 50
```

#### Ver el estado de los contenedores

```bash
sudo podman ps
```

### Archivos de configuración

#### `.env` (en `/opt/mediflow/.env`)

Variables configuradas para la VM:

```bash
ENV=dev
OCI_REGION=sa-saopaulo-1
OCI_NAMESPACE=grhx3cql3ypi
OCI_BUCKET=mediflow-dev
OCI_COMPARTMENT=ocid1.compartment.oc1..aaaaaaaaklh5si4fxiesxrqwnb3j62yxdui2zx6swahioi4wo3jrkwm6qcq
OCI_AUTH=instance_principal
ONS_TOPIC_OCID=ocid1.onstopic.oc1.sa-saopaulo-1.amaaaaaaof3op2aa77wg5xnuyc4cxw2wqahukas2shrzamxyg2jhdrlenx2q
STORAGE_BACKEND=oci
```

### Pendientes

#### ADB (Autonomous Database)

- **Estado:** No implementado en el MVP.
- **Nota:** El `docs/api-contract.md` dice que el MVP usa SQLite. ADB es para Sprint 3.
- **Wallet:** La carpeta `wallet/` está vacía (no se necesita para el MVP).

#### HTTPS / Dominio

- **Estado:** No implementado.
- **Actual:** HTTP en la IP pública (`http://144.22.215.79:8501`).
- **Pendiente:** Configurar DuckDNS + Let's Encrypt + nginx.

#### Nginx

- **Estado:** No usado actualmente.
- **Nota:** El `docker-compose.dev.yml` no incluye nginx (solo api, ui, worker).
- **Pendiente:** Usar `infra/docker-compose.yml` (con nginx) cuando tengamos dominio + TLS.

### Historial de cambios

| Fecha | Cambio |
| :--- | :--- |
| 9 oct 2026 | Deploy inicial en VM ARM. 3 contenedores corriendo (api, ui, worker). |