from unittest.mock import MagicMock, patch

from nuevamente.almacenamiento import guardar, leer


def test_guardar_sube_el_objeto_y_devuelve_la_clave():
    cliente_falso = MagicMock()
    with (
        patch("nuevamente.almacenamiento._obtener_cliente", return_value=cliente_falso),
        patch.dict("os.environ", {"OCI_NAMESPACE": "ns", "OCI_BUCKET_NAME": "bucket"}),
    ):
        resultado = guardar("contenido-001.json", b"{\"a\": 1}")

    assert resultado == "contenido-001.json"
    cliente_falso.put_object.assert_called_once_with("ns", "bucket", "contenido-001.json", b"{\"a\": 1}")


def test_leer_devuelve_los_bytes_del_objeto():
    cliente_falso = MagicMock()
    cliente_falso.get_object.return_value.data.content = b"contenido"
    with (
        patch("nuevamente.almacenamiento._obtener_cliente", return_value=cliente_falso),
        patch.dict("os.environ", {"OCI_NAMESPACE": "ns", "OCI_BUCKET_NAME": "bucket"}),
    ):
        resultado = leer("contenido-001.json")

    assert resultado == b"contenido"
    cliente_falso.get_object.assert_called_once_with("ns", "bucket", "contenido-001.json")
