import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import hashlib
import json
import logging
import re
import time
import unicodedata

import streamlit as st
from componente import OPCIONES, configurar_pagina, manejar_cambio_de_tema, render_ui
from flujo import ejecutar_accion, iniciar_estado

from nuevamente.contratos import procesar
from nuevamente.preguntas import preguntar

logger = logging.getLogger(__name__)

TIPOS_MIME = {"pdf": "application/pdf", "txt": "text/plain", "md": "text/markdown"}
MENSAJES_ESPERA = {
    "generar": "Generando contenido...",
    "ruta": "Preparando tu ruta de estudio (3 materiales)...",
    "comparar": "Generando las dos versiones para comparar...",
    "preguntar": "Buscando la respuesta en el documento...",
}


def _nombre_seguro(nombre_archivo: str, contenido: bytes) -> str:
    """Nombre valido para Supabase Storage. El prefijo con la huella del contenido evita que
    dos archivos distintos con el mismo nombre se sobrescriban entre si."""
    ascii_ = unicodedata.normalize("NFKD", nombre_archivo).encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^a-zA-Z0-9._-]", "-", ascii_).strip("-.") or "documento"
    return f"{hashlib.sha256(contenido).hexdigest()[:12]}-{limpio}"


def _guardar_original(nombre_archivo: str, contenido: bytes) -> None:
    """Guarda el documento subido en Supabase. Es opcional: si falla, la generacion sigue."""
    try:
        from nuevamente.almacenamiento import guardar

        extension = nombre_archivo.lower().rsplit(".", 1)[-1]
        guardar(
            f"subidos_usuario/{_nombre_seguro(nombre_archivo, contenido)}",
            contenido,
            TIPOS_MIME.get(extension, "application/octet-stream"),
        )
    except Exception:  # el almacenamiento nunca debe impedir generar
        logger.warning("No se pudo guardar el documento original en Supabase", exc_info=True)


def _registrar_valoracion(datos: dict) -> None:
    """Guarda el 👍/👎 (sin datos personales) para saber que generaciones sirven."""
    logger.info("Valoracion recibida: %s", datos)
    from nuevamente.almacenamiento import guardar

    clave = f"valoraciones/{time.strftime('%Y%m%d-%H%M%S')}-{datos['id_material']}.json"
    guardar(clave, json.dumps(datos, ensure_ascii=False).encode("utf-8"))


configurar_pagina()
iniciar_estado(st.session_state)

valor = render_ui(
    opciones=OPCIONES,
    resultado=st.session_state.resultado,
    error=st.session_state.error,
    historial=st.session_state.historial,
    conversaciones=st.session_state.conversaciones,
    valoraciones=st.session_state.valoraciones,
)

manejar_cambio_de_tema(valor)

accion = valor.get("accion") if isinstance(valor, dict) else None
with st.spinner(MENSAJES_ESPERA.get(accion, "Procesando...")):
    hubo_cambios = ejecutar_accion(
        valor,
        st.session_state,
        procesar=procesar,
        preguntar=preguntar,
        guardar_original=_guardar_original,
        registrar_valoracion=_registrar_valoracion,
    )
if hubo_cambios:
    st.rerun()
