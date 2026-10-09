# Despliegue en OCI (N2-01)

## Estado actual

**Fecha:** 9 de octubre de 2026
**Estado:** ✅ Deploy funcionando (HTTP, sin dominio)
**Responsable:** Carlos Zunino

## URLs públicas

| Servicio | URL | Estado |
| :--- | :--- | :--- |
| **API** | http://144.22.215.79:8000 | ✅ Funcionando |
| **API Docs** | http://144.22.215.79:8000/docs | ✅ Funcionando |
| **UI Streamlit** | http://144.22.215.79:8501 | ✅ Funcionando |
| **Health Check** | http://144.22.215.79:8000/health | ✅ `{"status":"ok"}` |

## Infraestructura

### VM

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

### Red

| Componente | Valor |
| :--- | :--- |
| **VCN** | vcn-mediflow (10.0.0.0/16) |
| **Subred** | subnet-mediflow-public (10.0.0.0/24) |
| **Internet Gateway** | igw-mediflow |
| **Route Table** | Default Route Table for vcn-mediflow |

### Puertos abiertos

| Puerto | Protocolo | Origen | Descripción |
| :--- | :--- | :--- | :--- |
| 22 | TCP | 0.0.0.0/0 | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP |
| 443 | TCP | 0.0.0.0/0 | HTTPS |
| 8000 | TCP | 0.0.0.0/0 | API FastAPI |
| 8501 | TCP | 0.0.0.0/0 | UI Streamlit |

## Cómo conectarse a la VM

```bash
ssh -i "$env:USERPROFILE\.ssh\mediflow-vm-1.key" opc@144.22.215.79