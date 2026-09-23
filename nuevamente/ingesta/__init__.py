from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def leer_documento(nombre_archivo: str, contenido: bytes) -> str:
    extension = nombre_archivo.lower().rsplit(".", 1)[-1]
    if extension == "pdf":
        return _leer_pdf(contenido)
    if extension in ("md", "txt"):
        return contenido.decode("utf-8", errors="ignore")
    raise ValueError(f"Formato no soportado: {extension}")


def _leer_pdf(contenido: bytes) -> str:
    lector = PdfReader(BytesIO(contenido))
    paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    return "\n".join(paginas).strip()
