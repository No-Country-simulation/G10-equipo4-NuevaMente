from __future__ import annotations

import chromadb

from nuevamente.contratos import Chunk

_cliente = chromadb.PersistentClient(path="chroma_db")

TAMANO_CHUNK = 500
SOLAPAMIENTO = 50


def _dividir_en_chunks(texto: str, tamano: int = TAMANO_CHUNK, solapamiento: int = SOLAPAMIENTO) -> list[str]:
    chunks = []
    inicio = 0
    while inicio < len(texto):
        chunks.append(texto[inicio:inicio + tamano])
        inicio += tamano - solapamiento
    return [c for c in chunks if c.strip()]


def indexar(doc_id: str, texto: str) -> int:
    coleccion = _cliente.get_or_create_collection(doc_id)
    fragmentos = _dividir_en_chunks(texto)
    coleccion.upsert(
        ids=[f"{doc_id}-{i}" for i in range(len(fragmentos))],
        documents=fragmentos,
    )
    return len(fragmentos)


def recuperar(doc_id: str, consulta: str, k: int = 5) -> list[Chunk]:
    coleccion = _cliente.get_or_create_collection(doc_id)
    resultado = coleccion.query(query_texts=[consulta], n_results=k)
    documentos = resultado["documents"][0] if resultado["documents"] else []
    return [Chunk(texto=doc, fuente=doc_id) for doc in documentos]
