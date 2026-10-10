from __future__ import annotations

import os

from supabase import create_client, Client


_cliente: Client | None = None



def _obtener_cliente() -> Client:
    global _cliente

    if _cliente is None:
        import streamlit as st

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url:
            url = st.secrets.get("SUPABASE_URL")

        if not key:
            key = st.secrets.get("SUPABASE_KEY")

        if not url or not key:
            raise RuntimeError(
                "Faltan las credenciales SUPABASE_URL o SUPABASE_KEY."
            )

        _cliente = create_client(url, key)

    return _cliente


def _obtener_bucket() -> str:
    bucket = os.environ.get("SUPABASE_BUCKET")

    if not bucket:
        try:
            import streamlit as st
            bucket = st.secrets.get("SUPABASE_BUCKET")
        except Exception:
            bucket = None

    if not bucket:
        raise RuntimeError(
            "Falta configurar la variable SUPABASE_BUCKET."
        )

    return bucket

def guardar(
    clave: str,
    contenido: bytes,
    content_type: str = "application/json",
) -> str:
    cliente = _obtener_cliente()
    bucket = _obtener_bucket()

    cliente.storage.from_(bucket).upload(
        path=clave,
        file=contenido,
        file_options={
            "content-type": content_type,
            "upsert": "true",
        },
    )

    return clave

def leer(clave: str) -> bytes:
    cliente = _obtener_cliente()
    bucket = _obtener_bucket()

    respuesta = cliente.storage.from_(bucket).download(clave)

    return respuesta
