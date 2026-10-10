from unittest.mock import MagicMock, patch

from nuevamente.almacenamiento import guardar, leer


def test_guardar_sube_el_objeto_y_devuelve_la_clave():
    cliente_falso = MagicMock()

    with patch(
        "nuevamente.almacenamiento._obtener_cliente",
        return_value=cliente_falso,
    ), patch.dict(
        "os.environ",
        {"SUPABASE_BUCKET": "documentos"},
    ):
        resultado = guardar("contenido-001.json", b'{"a": 1}')

    assert resultado == "contenido-001.json"

    cliente_falso.storage.from_.assert_called_once_with("documentos")

    cliente_falso.storage.from_.return_value.upload.assert_called_once_with(
        path="contenido-001.json",
        file=b'{"a": 1}',
        file_options={
            "content-type": "application/json",
            "upsert": "true",
        },
    )


def test_leer_devuelve_los_bytes_del_objeto():
    cliente_falso = MagicMock()

    cliente_falso.storage.from_.return_value.download.return_value = b"contenido"

    with patch(
        "nuevamente.almacenamiento._obtener_cliente",
        return_value=cliente_falso,
    ), patch.dict(
        "os.environ",
        {"SUPABASE_BUCKET": "documentos"},
    ):
        resultado = leer("contenido-001.json")

    assert resultado == b"contenido"

    cliente_falso.storage.from_.assert_called_once_with("documentos")

    cliente_falso.storage.from_.return_value.download.assert_called_once_with(
        "contenido-001.json"
    )