from __future__ import annotations

import os

import oci

_cliente: oci.object_storage.ObjectStorageClient | None = None


def _obtener_cliente() -> oci.object_storage.ObjectStorageClient:
    global _cliente
    if _cliente is None:
        try:
            config = oci.config.from_file()
            _cliente = oci.object_storage.ObjectStorageClient(config)
        except oci.exceptions.ConfigFileNotFound:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            _cliente = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
    return _cliente


def guardar(clave: str, contenido: bytes) -> str:
    cliente = _obtener_cliente()
    namespace = os.environ["OCI_NAMESPACE"]
    bucket = os.environ["OCI_BUCKET_NAME"]
    cliente.put_object(namespace, bucket, clave, contenido)
    return clave


def leer(clave: str) -> bytes:
    cliente = _obtener_cliente()
    namespace = os.environ["OCI_NAMESPACE"]
    bucket = os.environ["OCI_BUCKET_NAME"]
    respuesta = cliente.get_object(namespace, bucket, clave)
    return respuesta.data.content
