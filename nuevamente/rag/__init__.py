from __future__ import annotations

import math

import chromadb
from chromadb.utils import embedding_functions

from nuevamente.contratos import Chunk

_cliente = chromadb.PersistentClient(path="chroma_db")
_funcion_embedding = embedding_functions.DefaultEmbeddingFunction()

TAMANO_CHUNK = 500
SOLAPAMIENTO = 50
LAMBDA_MMR = 0.5  # 1.0 = solo relevancia, 0.0 = solo diversidad
FACTOR_CANDIDATOS = 4  # cuantos candidatos traer por cada resultado final, antes de filtrar por diversidad


def _coleccion(doc_id: str):
    # Se fija explicitamente la funcion de embeddings (la misma que Chroma usaria por
    # defecto) para poder reutilizarla y calcular el embedding de la consulta nosotros
    # mismos, algo que la API de coleccion.query() no expone.
    return _cliente.get_or_create_collection(doc_id, embedding_function=_funcion_embedding)


def _dividir_en_chunks(texto: str, tamano: int = TAMANO_CHUNK, solapamiento: int = SOLAPAMIENTO) -> list[str]:
    chunks = []
    inicio = 0
    while inicio < len(texto):
        chunks.append(texto[inicio:inicio + tamano])
        inicio += tamano - solapamiento
    return [c for c in chunks if c.strip()]


def indexar(doc_id: str, texto: str) -> int:
    coleccion = _coleccion(doc_id)
    fragmentos = _dividir_en_chunks(texto)
    total = len(fragmentos)
    coleccion.upsert(
        ids=[f"{doc_id}-{i}" for i in range(total)],
        documents=fragmentos,
        metadatas=[{"posicion": i, "total_fragmentos": total} for i in range(total)],
    )
    return total


def _producto_punto(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norma(vector: list[float]) -> float:
    return math.sqrt(_producto_punto(vector, vector)) or 1e-10


def _similitud_coseno(a: list[float], b: list[float]) -> float:
    return _producto_punto(a, b) / (_norma(a) * _norma(b))


def _seleccionar_por_mmr(
    embedding_consulta: list[float],
    embeddings_candidatos: list[list[float]],
    k: int,
    lambda_mmr: float = LAMBDA_MMR,
) -> list[int]:
    """Maximal Marginal Relevance: en cada paso elige el candidato mas relevante
    a la consulta, pero penalizando a los que se parecen mucho a lo ya elegido.
    Asi los fragmentos que vuelven no son solo los mas parecidos entre si."""
    pendientes = list(range(len(embeddings_candidatos)))
    similitud_con_consulta = [_similitud_coseno(embedding_consulta, emb) for emb in embeddings_candidatos]
    seleccionados: list[int] = []

    while pendientes and len(seleccionados) < k:
        if not seleccionados:
            elegido = max(pendientes, key=lambda i: similitud_con_consulta[i])
        else:
            def puntaje(i: int) -> float:
                diversidad = max(
                    _similitud_coseno(embeddings_candidatos[i], embeddings_candidatos[j]) for j in seleccionados
                )
                return lambda_mmr * similitud_con_consulta[i] - (1 - lambda_mmr) * diversidad

            elegido = max(pendientes, key=puntaje)
        seleccionados.append(elegido)
        pendientes.remove(elegido)

    return seleccionados


def recuperar(doc_id: str, consulta: str, k: int = 5) -> list[Chunk]:
    coleccion = _coleccion(doc_id)
    candidatos_deseados = max(k * FACTOR_CANDIDATOS, k)

    resultado = coleccion.query(
        query_texts=[consulta],
        n_results=candidatos_deseados,
        include=["documents", "embeddings", "metadatas"],
    )
    documentos = (resultado.get("documents") or [[]])[0]
    if not documentos:
        return []
    embeddings = (resultado.get("embeddings") or [None])[0]
    metadatos = (resultado.get("metadatas") or [None])[0]

    if embeddings is not None and len(embeddings) > 0:
        embedding_consulta = _funcion_embedding([consulta])[0]
        indices = _seleccionar_por_mmr(embedding_consulta, embeddings, min(k, len(documentos)))
    else:
        # Sin embeddings disponibles (por ejemplo, un mock en pruebas): se conserva
        # el orden que ya entrega Chroma por similitud, sin aplicar diversidad MMR.
        indices = list(range(min(k, len(documentos))))

    chunks = []
    for indice in indices:
        if metadatos:
            posicion = metadatos[indice].get("posicion", indice)
            total = metadatos[indice].get("total_fragmentos", len(documentos))
        else:
            posicion, total = indice, len(documentos)
        chunks.append(Chunk(texto=documentos[indice], fuente=f"{doc_id} · fragmento {posicion + 1} de {total}"))
    return chunks