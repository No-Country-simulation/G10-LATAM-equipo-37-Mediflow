"""Acceso a OCI Object Storage. En la VM usa instance principal; en local, ~/.oci/config."""
import json
import os


def _client():
    import oci

    if os.getenv("OCI_AUTH", "config") == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return oci.object_storage.ObjectStorageClient(config={}, signer=signer)
    config = oci.config.from_file(profile_name=os.getenv("OCI_CONFIG_PROFILE", "DEFAULT"))
    return oci.object_storage.ObjectStorageClient(config)


def namespace() -> str:
    return os.getenv("OCI_NAMESPACE") or _client().get_namespace().data


def upload_bytes(bucket: str, ruta: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client().put_object(namespace(), bucket, ruta, data, content_type=content_type)


def upload_json(bucket: str, ruta: str, obj: dict) -> None:
    upload_bytes(bucket, ruta, json.dumps(obj, ensure_ascii=False, indent=2).encode(), "application/json")


def list_prefix(bucket: str, prefijo: str) -> list[str]:
    resp = _client().list_objects(namespace(), bucket, prefix=prefijo)
    return [o.name for o in resp.data.objects]


def download(bucket: str, ruta: str) -> bytes:
    return _client().get_object(namespace(), bucket, ruta).data.content
