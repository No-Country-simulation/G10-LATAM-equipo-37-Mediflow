# Configuración de OCI para MediFlow

Guía paso a paso para crear y configurar los buckets, políticas y credenciales de OCI que usa MediFlow.

**Referencias:**
- Plan: `docs/plan.md`, paquete N2-02
- Políticas IAM: `infra/oci/policies.txt`
- Variables de entorno: `.env.example`
- Script de VM: `infra/oci/setup-vm.sh`

## 1. Buckets

MediFlow usa **dos buckets separados** por entorno:

| Bucket | Entorno | Quién escribe | Uso |
|---|---|---|---|
| `mediflow-dev` | Desarrollo | `mediflow-devs` (humanos) | Pruebas locales y desarrollo |
| `mediflow-prod` | Producción | `mediflow-vm` (dynamic group) | VM en producción |

**Regla clave:** un dev **no puede escribir** en `mediflow-prod`. Solo la VM lo hace.

### Crear los buckets

```bash
# Ver el compartment
COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaklh5si4fxiesxrqwnb3j62yxdui2zx6svwahioi4wo3jrkwm6qcq"

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