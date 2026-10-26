"""El script real y la demo deben renderizar su componente sin excepciones."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("archivo", ["app/main.py", "app/demo.py"])
def test_arranque_streamlit(archivo):
    app = AppTest.from_file(Path(__file__).resolve().parent.parent / archivo).run(timeout=20)
    assert not app.exception
    assert len(app.get("component_instance")) == 1
