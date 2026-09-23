import pytest
from unittest.mock import MagicMock, patch

from nuevamente.ingesta import leer_documento


def test_leer_txt():
    resultado = leer_documento("nota.txt", b"contenido de prueba")
    assert resultado == "contenido de prueba"


def test_leer_md():
    resultado = leer_documento("nota.md", "# Titulo".encode("utf-8"))
    assert resultado == "# Titulo"


def test_formato_no_soportado_falla():
    with pytest.raises(ValueError):
        leer_documento("imagen.png", b"binario")


def test_leer_pdf_extrae_texto_de_cada_pagina():
    pagina_1 = MagicMock()
    pagina_1.extract_text.return_value = "Pagina uno"
    pagina_2 = MagicMock()
    pagina_2.extract_text.return_value = "Pagina dos"

    with patch("nuevamente.ingesta.PdfReader") as mock_reader:
        mock_reader.return_value.pages = [pagina_1, pagina_2]
        resultado = leer_documento("doc.pdf", b"contenido-pdf-falso")

    assert resultado == "Pagina uno\nPagina dos"
