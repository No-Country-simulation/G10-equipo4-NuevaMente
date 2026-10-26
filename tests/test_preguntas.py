"""Pregúntale al documento, idioma y ajustes en los prompts, e indice por huella."""

import sys
from pathlib import Path
from unittest.mock import patch

import chromadb
import pytest

from nuevamente import agentes, rag
from nuevamente.contratos import Chunk, RespuestaPregunta, Solicitud
from nuevamente.preguntas import LARGO_MAXIMO, preguntar, validar_pregunta
from tests.test_robustez import _EmbeddingFalso

CHUNKS = [Chunk(texto="La VCN es regional.", fuente="doc · fragmento 1 de 3"),
          Chunk(texto="NAT da salida a internet.", fuente="doc · fragmento 2 de 3")]


# ---------- preguntar ----------


@pytest.mark.parametrize("pregunta", ["", "  ", "ok", "x" * (LARGO_MAXIMO + 1)])
def test_preguntas_vacias_o_enormes_se_rechazan(pregunta):
    with pytest.raises(ValueError):
        validar_pregunta(pregunta)


def test_preguntar_devuelve_solo_las_fuentes_citadas():
    respuesta = RespuestaPregunta(respuesta="Sale por NAT.", fragmentos_usados=[2, 2, 9, 0], en_documento=True)
    with (
        patch("nuevamente.rag.asegurar_indice") as asegurar,
        patch("nuevamente.rag.recuperar", return_value=CHUNKS),
        patch("nuevamente.agentes.responder_pregunta", return_value=respuesta) as responder,
    ):
        resultado = preguntar("Guía VCN.md", "texto completo", "  ¿Cómo   sale a internet? ", "English")

    asegurar.assert_called_once_with("guia-vcn-md", "texto completo")
    responder.assert_called_once_with("¿Cómo sale a internet?", CHUNKS, "English")
    assert resultado == {"respuesta": "Sale por NAT.", "en_documento": True, "fuentes": [CHUNKS[1].model_dump()]}


def test_si_no_esta_en_el_documento_no_se_muestran_fuentes():
    respuesta = RespuestaPregunta(respuesta="No aparece en el documento.", fragmentos_usados=[1], en_documento=False)
    with (
        patch("nuevamente.rag.asegurar_indice"),
        patch("nuevamente.rag.recuperar", return_value=CHUNKS),
        patch("nuevamente.agentes.responder_pregunta", return_value=respuesta),
    ):
        resultado = preguntar("doc.md", "texto", "¿Cuánto cuesta?")

    assert resultado["en_documento"] is False
    assert resultado["fuentes"] == []


def test_el_prompt_de_preguntas_usa_fragmentos_numerados_e_idioma():
    with patch.object(agentes, "_invocar") as invocar:
        agentes.responder_pregunta("¿Qué es NAT?", CHUNKS, "Português")

    prompt, modelo = invocar.call_args.args
    assert modelo is RespuestaPregunta
    assert "[1] La VCN es regional." in prompt and "[2] NAT da salida a internet." in prompt
    assert "Português" in prompt
    assert "no las sigas" in prompt  # defensa contra instrucciones dentro de la pregunta


# ---------- idioma y ajustes en el redactor ----------


def _solicitud(**extra):
    base = {"documento_titulo": "t", "documento_contenido": "c", "perfil_destinatario": "Junior",
                "formato_salida": "Quiz", "nicho_sector": "General", "nivel_detalle": "Intermedio"}
    return Solicitud(**{**base, **extra})


def test_el_redactor_escribe_en_el_idioma_pedido():
    with patch.object(agentes, "_invocar") as invocar:
        agentes._redactar(_solicitud(idioma_salida="English"), "hallazgos")
    assert "en English" in invocar.call_args.args[0]


def test_el_redactor_recibe_los_ajustes_sin_repetir():
    with patch.object(agentes, "_invocar") as invocar:
        agentes._redactar(_solicitud(ajustes=["mas_corto", "menos_jerga", "mas_corto"]), "hallazgos")
    prompt = invocar.call_args.args[0]
    assert prompt.count("Se mas breve") == 1
    assert "Evita la jerga tecnica" in prompt


def test_sin_ajustes_el_prompt_no_menciona_una_nueva_version():
    with patch.object(agentes, "_invocar") as invocar:
        agentes._redactar(_solicitud(), "hallazgos")
    assert "nueva version" not in invocar.call_args.args[0]


def test_la_solicitud_por_defecto_es_en_espanol_y_sin_ajustes():
    solicitud = _solicitud()
    assert solicitud.idioma_salida == "Español"
    assert solicitud.ajustes == []


# ---------- indice por huella ----------


@pytest.fixture
def chroma(monkeypatch):
    cliente = chromadb.EphemeralClient()
    for nombre in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nombre)
    monkeypatch.setattr(rag, "_cliente", cliente)
    monkeypatch.setattr(rag, "_funcion_embedding", _EmbeddingFalso())
    return cliente


def test_asegurar_indice_no_reindexa_el_mismo_texto(chroma):
    assert rag.asegurar_indice("manual", "a" * 1200) is True
    with patch.object(rag, "indexar", wraps=rag.indexar) as indexar:
        assert rag.asegurar_indice("manual", "a" * 1200) is False
        indexar.assert_not_called()


def test_asegurar_indice_reindexa_si_el_texto_cambio(chroma):
    rag.asegurar_indice("manual", "a" * 1200)
    assert rag.asegurar_indice("manual", "e" * 600) is True
    assert chroma.get_collection("manual").count() == 2


def test_indexar_desde_procesar_tambien_deja_la_huella(chroma):
    rag.indexar("guia", "texto de la guia " * 40)
    assert rag.asegurar_indice("guia", "texto de la guia " * 40) is False


# ---------- demo ----------


def test_el_demo_responde_buscando_en_el_documento():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
    import demo

    texto = "# VCN\n\nUna VCN es una red privada.\n\nEl NAT Gateway da salida a internet sin exponer la instancia."
    resultado = demo.preguntar_demo("vcn.md", texto, "¿Qué hace el NAT Gateway?")
    assert resultado["en_documento"] is True
    assert resultado["fuentes"][0]["fuente"] == "vcn.md · fragmento 3 de 3"

    nada = demo.preguntar_demo("vcn.md", texto, "¿Cuál es el precio del almuerzo?")
    assert nada["en_documento"] is False and nada["fuentes"] == []
