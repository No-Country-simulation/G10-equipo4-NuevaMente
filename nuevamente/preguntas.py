"""Pregúntale al documento: respuestas libres basadas solo en el documento subido, con sus fuentes."""

from __future__ import annotations

LARGO_MINIMO = 3
LARGO_MAXIMO = 500
FRAGMENTOS_POR_PREGUNTA = 4


def validar_pregunta(pregunta: str) -> str:
    limpia = " ".join(str(pregunta or "").split())
    if len(limpia) < LARGO_MINIMO:
        raise ValueError("Escribe una pregunta un poco más larga.")
    if len(limpia) > LARGO_MAXIMO:
        raise ValueError(f"La pregunta es muy larga: el máximo es {LARGO_MAXIMO} caracteres.")
    return limpia


def preguntar(documento_titulo: str, documento_contenido: str, pregunta: str, idioma: str = "Español") -> dict:
    """Devuelve {respuesta, en_documento, fuentes} para mostrar en la UI.

    Las fuentes son solo los fragmentos que el modelo dijo usar (los numeros invalidos se ignoran).
    """
    from nuevamente.agentes import responder_pregunta
    from nuevamente.contratos import _generar_doc_id
    from nuevamente.rag import asegurar_indice, recuperar

    pregunta = validar_pregunta(pregunta)
    doc_id = _generar_doc_id(documento_titulo)
    asegurar_indice(doc_id, documento_contenido)
    chunks = recuperar(doc_id, pregunta, k=FRAGMENTOS_POR_PREGUNTA)
    if not chunks:
        return {"respuesta": "No encontré texto en el documento para responder.", "en_documento": False, "fuentes": []}

    resultado = responder_pregunta(pregunta, chunks, idioma)
    usados = list(dict.fromkeys(i for i in resultado.fragmentos_usados if 1 <= i <= len(chunks)))
    fuentes = [chunks[i - 1].model_dump() for i in usados] if resultado.en_documento else []
    return {"respuesta": resultado.respuesta, "en_documento": resultado.en_documento, "fuentes": fuentes}
