from unittest.mock import MagicMock, patch

from nuevamente.contratos import Chunk
from nuevamente.rag import _dividir_en_chunks, indexar, recuperar


def test_dividir_en_chunks_respeta_tamano():
    texto = "a" * 1200
    chunks = _dividir_en_chunks(texto, tamano=500, solapamiento=50)
    assert all(len(c) <= 500 for c in chunks)
    assert len(chunks) >= 3


def test_dividir_en_chunks_texto_corto_da_un_solo_chunk():
    chunks = _dividir_en_chunks("texto corto", tamano=500, solapamiento=50)
    assert chunks == ["texto corto"]


def test_indexar_agrega_chunks_a_la_coleccion():
    coleccion_falsa = MagicMock()
    with patch("nuevamente.rag._cliente") as cliente_falso:
        cliente_falso.get_or_create_collection.return_value = coleccion_falsa
        total = indexar("doc1", "a" * 1200)

    assert total >= 3
    coleccion_falsa.upsert.assert_called_once()


def test_recuperar_devuelve_chunks():
    coleccion_falsa = MagicMock()
    coleccion_falsa.query.return_value = {"documents": [["fragmento uno", "fragmento dos"]]}
    with patch("nuevamente.rag._cliente") as cliente_falso:
        cliente_falso.get_or_create_collection.return_value = coleccion_falsa
        resultados = recuperar("doc1", "consulta", k=2)

    assert resultados == [
        Chunk(texto="fragmento uno", fuente="doc1"),
        Chunk(texto="fragmento dos", fuente="doc1"),
    ]
