from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

EXTENSIONES_SOPORTADAS = ("pdf", "md", "txt")
TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB: mismo limite que valida la UI antes de enviar


def leer_documento(nombre_archivo: str, contenido: bytes) -> str:
    extension = nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""
    if extension not in EXTENSIONES_SOPORTADAS:
        raise ValueError(f"Formato no soportado: '{extension or nombre_archivo}'. Sube un archivo PDF, MD o TXT.")
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ValueError("El archivo supera el tamaño máximo de 10 MB.")
    if extension == "pdf":
        return _leer_pdf(contenido)
    return _decodificar_texto(contenido)


def _decodificar_texto(contenido: bytes) -> str:
    # utf-8-sig quita el BOM que agregan editores como el Bloc de notas de Windows;
    # cp1252 cubre los .txt guardados en "ANSI" (tildes y enes de Windows en espanol)
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="ignore")


def _leer_pdf(contenido: bytes) -> str:
    try:
        lector = PdfReader(BytesIO(contenido))
        if lector.is_encrypted and lector.decrypt("") == 0:
            raise ValueError("El PDF está protegido con contraseña. Sube una versión sin protección.")
        paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    except PyPdfError as exc:
        raise ValueError("No se pudo abrir el PDF: el archivo parece dañado o no es un PDF válido.") from exc
    return "\n".join(paginas).strip()
