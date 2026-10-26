"""Modo claro por defecto y boton para activar el modo oscuro."""

import sys
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))

from componente import (  # va despues de agregar app/ al path
    TEMA_POR_DEFECTO,
    leer_cambio_de_tema,
)


def test_el_modo_principal_es_el_claro():
    assert TEMA_POR_DEFECTO == "claro"
    config = tomllib.loads((RAIZ / ".streamlit/config.toml").read_text(encoding="utf-8"))
    assert config["theme"]["base"] == "light"
    # Sin [theme.dark], Streamlit no se pasa solo a oscuro aunque el sistema lo este
    assert "dark" not in config["theme"]


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_acepta_el_cambio_de_tema_del_boton(tema):
    assert leer_cambio_de_tema({"accion": "tema", "tema": tema, "id": "tema-1"}) == tema


@pytest.mark.parametrize(
    "valor",
    [
        None,
        {},
        {"accion": "generar", "tema": "oscuro"},
        {"accion": "tema", "tema": "rosa"},
        {"accion": "tema", "tema": "</style><script>alert(1)</script>"},
        {"accion": "tema"},
        "oscuro",
    ],
)
def test_ignora_valores_que_no_son_un_cambio_de_tema_valido(valor):
    assert leer_cambio_de_tema(valor) is None


def test_la_ui_arranca_en_claro_y_tiene_el_interruptor():
    html = (RAIZ / "app/frontend/index.html").read_text(encoding="utf-8")
    assert 'id="btn-tema" role="switch" aria-checked="false"' in html
    assert "prefers-color-scheme" not in html  # el sistema ya no decide el tema
