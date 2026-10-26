"""El modo demo debe poder construir una respuesta valida para cada formato y perfil."""

import importlib
import sys
from pathlib import Path

import pytest

from nuevamente.contratos import Respuesta

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def demo():
    sys.path.insert(0, str(RAIZ / "app"))
    try:
        yield importlib.import_module("demo")
    finally:
        sys.path.remove(str(RAIZ / "app"))


@pytest.mark.parametrize("formato", ["Flashcards", "Tutorial", "Quiz", "TLDR", "Guion"])
@pytest.mark.parametrize("perfil", ["Principiante", "Ejecutivo"])
def test_demo_genera_respuesta_valida(demo, formato, perfil):
    valor = {"archivo_nombre": "vcn.md", "perfil": perfil, "formato": formato, "nicho": "Fintech", "nivel": "Profundo"}

    respuesta = demo._respuesta_de_ejemplo(valor, "Una VCN es una red privada.")

    assert isinstance(respuesta, Respuesta)
    assert respuesta.metadatos.formato_generado == formato
    assert respuesta.metadatos.prerrequisitos
    Respuesta.model_validate_json(respuesta.model_dump_json())


def test_recursos_de_marca_existen():
    for ruta in (
        "app/assets/favicon.png",
        "app/assets/favicon.ico",
        "app/frontend/assets/logo-nuevamente.svg",
        "app/frontend/assets/isotipo-nuevamente.svg",
        "app/frontend/assets/marca-vo.svg",
    ):
        assert (RAIZ / ruta).is_file(), ruta
    html = (RAIZ / "app/frontend/index.html").read_text(encoding="utf-8")
    assert 'class="marca-logo"' in html and 'aria-label="NuevaMente"' in html
    assert 'src="assets/isotipo-nuevamente.svg"' in html


def test_la_ui_no_depende_de_fuentes_externas():
    html = (RAIZ / "app/frontend/index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html
    assert "Google Sans" not in html
    for fuente in (
        "montserrat-latin-400-normal.woff2",
        "montserrat-latin-800-normal.woff2",
        "jetbrains-mono-latin-400-normal.woff2",
        "material-symbols-rounded-latin-400-normal.woff2",
    ):
        assert f"fonts/{fuente}" in html, fuente
        assert (RAIZ / "app/frontend/fonts" / fuente).is_file(), fuente


@pytest.mark.parametrize(
    "texto",
    ["Tu documentación técnica", "Ajústalo a tu público", "Qué hacer ahora", "Narración", "Líder técnico", "Didáctico"],
)
def test_la_ui_esta_escrita_con_tildes(texto):
    assert texto in (RAIZ / "app/frontend/index.html").read_text(encoding="utf-8")
