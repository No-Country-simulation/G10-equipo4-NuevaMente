import pytest


@pytest.fixture(autouse=True)
def _cache_aislada(tmp_path, monkeypatch):
    """Cada prueba usa su propia cache: ninguna toca .cache_generacion ni contamina a otra."""
    monkeypatch.setenv("NUEVAMENTE_CACHE_DIR", str(tmp_path / "cache"))