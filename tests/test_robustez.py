"""Pruebas de las correcciones de robustez: configuracion, ingesta, nombres de coleccion,
re-indexado en ChromaDB y respaldo de Ollama a Gemini."""

from types import SimpleNamespace
from unittest.mock import patch

import chromadb
import pytest
from chromadb.api.types import EmbeddingFunction

from nuevamente import agentes, rag
from nuevamente.config import (
    ConfiguracionIncompletaError,
    leer_configuracion,
    requerir_configuracion,
)
from nuevamente.contratos import _generar_doc_id
from nuevamente.errores import describir_error
from nuevamente.ingesta import TAMANO_MAXIMO_BYTES, leer_documento

# ---------- Configuracion ----------


def test_config_lee_variables_de_entorno(monkeypatch):
    monkeypatch.setenv("NUEVAMENTE_PRUEBA", "  valor  ")
    assert leer_configuracion("NUEVAMENTE_PRUEBA") == "valor"


def test_config_sin_secrets_devuelve_el_defecto(monkeypatch):
    # Sin .env ni secrets.toml, st.secrets lanza FileNotFoundError: no debe propagarse
    monkeypatch.delenv("NUEVAMENTE_NO_EXISTE", raising=False)
    assert leer_configuracion("NUEVAMENTE_NO_EXISTE", "defecto") == "defecto"


def test_config_obligatoria_faltante_lanza_error_claro(monkeypatch):
    monkeypatch.delenv("NUEVAMENTE_NO_EXISTE", raising=False)
    with pytest.raises(ConfiguracionIncompletaError, match="NUEVAMENTE_NO_EXISTE"):
        requerir_configuracion("NUEVAMENTE_NO_EXISTE")


def test_config_faltante_se_explica_sin_jerga():
    resultado = describir_error(ConfiguracionIncompletaError("OLLAMA_BASE_URL"))

    assert resultado["titulo"] == "Configuración incompleta"
    assert resultado["reintentable"] is False
    assert "OLLAMA_BASE_URL" not in resultado["mensaje"]
    assert "OLLAMA_BASE_URL" in resultado["detalle"]


# ---------- Ingesta ----------


def test_txt_con_bom_no_deja_caracteres_raros():
    assert leer_documento("nota.txt", "﻿Hola".encode()) == "Hola"


def test_txt_guardado_en_ansi_conserva_tildes():
    assert leer_documento("nota.txt", "Configuración de la región".encode("cp1252")) == "Configuración de la región"


def test_archivo_sin_extension_falla_con_mensaje_claro():
    with pytest.raises(ValueError, match="PDF, MD o TXT"):
        leer_documento("README", b"texto")


def test_archivo_demasiado_grande_falla():
    with pytest.raises(ValueError, match="10 MB"):
        leer_documento("grande.txt", b"a" * (TAMANO_MAXIMO_BYTES + 1))


def test_pdf_danado_da_un_error_entendible():
    with pytest.raises(ValueError, match="PDF"):
        leer_documento("roto.pdf", b"esto no es un pdf")

    resultado = describir_error(_capturar(lambda: leer_documento("roto.pdf", b"%PDF-1.4 basura")))
    assert resultado["reintentable"] is False


def _capturar(funcion):
    try:
        funcion()
    except ValueError as exc:
        return exc
    raise AssertionError("se esperaba ValueError")


# ---------- Nombres de coleccion en ChromaDB ----------


@pytest.mark.parametrize(
    "titulo",
    ["a.md", "x", "ñ.txt", "Guía de configuración.pdf", "---.txt", "a" * 59 + "-b.pdf", "!!!"],
)
def test_doc_id_siempre_es_un_nombre_de_coleccion_valido(titulo):
    doc_id = _generar_doc_id(titulo)

    assert 3 <= len(doc_id) <= 63
    assert doc_id[0].isalnum()
    assert doc_id[-1].isalnum()
    chromadb.EphemeralClient().get_or_create_collection(doc_id)  # no lanza


def test_doc_id_conserva_las_letras_con_tilde():
    assert _generar_doc_id("Guía de configuración.pdf") == "guia-de-configuracion-pdf"


def test_doc_id_de_titulos_normales_no_cambia():
    assert _generar_doc_id("Intro a VCN en OCI") == "intro-a-vcn-en-oci"


# ---------- Re-indexado ----------


class _EmbeddingFalso(EmbeddingFunction):
    """Embedding determinista y sin red: cuenta letras."""

    def __init__(self) -> None:
        pass

    def __call__(self, input):  # "input": nombre exigido por la interfaz de ChromaDB
        return [[float(texto.count(letra)) + 0.01 for letra in "aeiouxyz"] for texto in input]

    @staticmethod
    def name() -> str:
        return "embedding_falso"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(_config):
        return _EmbeddingFalso()


@pytest.fixture
def chroma_en_memoria(monkeypatch):
    cliente = chromadb.EphemeralClient()
    for nombre in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nombre)
    monkeypatch.setattr(rag, "_cliente", cliente)
    monkeypatch.setattr(rag, "_funcion_embedding", _EmbeddingFalso())
    return cliente


def test_reindexar_un_documento_mas_corto_borra_los_fragmentos_viejos(chroma_en_memoria):
    assert rag.indexar("manual", "x" * 3000) == 7
    assert rag.indexar("manual", "y" * 600) == 2

    coleccion = chroma_en_memoria.get_collection("manual")
    assert coleccion.count() == 2
    textos = rag.recuperar("manual", "y", k=5)
    assert all("x" not in chunk.texto for chunk in textos)
    assert {c.fuente for c in textos} == {"manual · fragmento 1 de 2", "manual · fragmento 2 de 2"}


def test_recuperar_con_chroma_real_devuelve_fuentes(chroma_en_memoria):
    rag.indexar("guia", "aeiou " * 300)

    chunks = rag.recuperar("guia", "aeiou", k=3)

    assert 1 <= len(chunks) <= 3
    assert all(chunk.fuente.startswith("guia · fragmento ") for chunk in chunks)


def test_indexar_texto_vacio_falla(chroma_en_memoria):
    with pytest.raises(ValueError):
        rag.indexar("vacio", "   ")


# ---------- Agentes ----------


def test_texto_de_respuesta_acepta_str_y_bloques():
    assert agentes._texto_de_respuesta(SimpleNamespace(content="hola")) == "hola"
    bloques = [{"type": "text", "text": "uno "}, {"type": "thinking", "thinking": "x"}, "dos"]
    assert agentes._texto_de_respuesta(SimpleNamespace(content=bloques)) == "uno dos"


def test_si_ollama_falla_sin_gemini_configurado_se_ve_el_error_de_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")

    def invocar_que_falla(_llm, _prompt, **_kwargs):
        raise ConnectionError("Ollama no responde")

    with (
        patch.object(agentes, "_obtener_llm_primario", return_value=object()),
        patch.object(agentes, "_obtener_llm_fallback", side_effect=ConfiguracionIncompletaError("GEMINI_API_KEY")),
        patch.object(agentes, "invocar_con_espera", side_effect=invocar_que_falla),
        pytest.raises(ConnectionError, match="Ollama no responde"),
    ):
        agentes._invocar("prompt")


def test_si_ollama_falla_se_reintenta_con_gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVEEDOR", "ollama")
    primario, respaldo = object(), object()

    def invocar(llm, _prompt, **_kwargs):
        if llm is primario:
            raise ConnectionError("Ollama no responde")
        return "respuesta de gemini"

    with (
        patch.object(agentes, "_obtener_llm_primario", return_value=primario),
        patch.object(agentes, "_obtener_llm_fallback", return_value=respaldo),
        patch.object(agentes, "invocar_con_espera", side_effect=invocar),
    ):
        assert agentes._invocar("prompt") == "respuesta de gemini"


def test_falta_la_api_key_de_gemini_es_configuracion_incompleta(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfiguracionIncompletaError):
        agentes._construir_llm("gemini")
