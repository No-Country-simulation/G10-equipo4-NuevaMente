"""Almacenamiento de documentos y resultados en Supabase Storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuevamente.config import requerir_configuracion

if TYPE_CHECKING:
    from supabase import Client

_cliente: Client | None = None


def _obtener_cliente() -> Client:
    global _cliente  # cliente unico perezoso, se crea al primer uso
    if _cliente is None:
        # Import perezoso: la app y las pruebas cargan sin necesitar credenciales ni red
        from supabase import create_client

        _cliente = create_client(requerir_configuracion("SUPABASE_URL"), requerir_configuracion("SUPABASE_KEY"))
    return _cliente


def _obtener_bucket() -> str:
    return requerir_configuracion("SUPABASE_BUCKET")


def guardar(clave: str, contenido: bytes, content_type: str = "application/json") -> str:
    cliente = _obtener_cliente()
    bucket = _obtener_bucket()
    cliente.storage.from_(bucket).upload(
        path=clave,
        file=contenido,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return clave


def leer(clave: str) -> bytes:
    cliente = _obtener_cliente()
    bucket = _obtener_bucket()
    return cliente.storage.from_(bucket).download(clave)
