from unittest.mock import MagicMock, patch

import pytest
import requests

from core.pubmed_client import FakePubMedClient, make_pubmed_client, PubMedClient


def test_fake_pubmed_client_devuelve_conteo_por_query():
    client = FakePubMedClient({"asa dental risk": 12})
    assert client.contar("asa dental risk") == 12


def test_fake_pubmed_client_query_no_registrada_devuelve_cero():
    client = FakePubMedClient({})
    assert client.contar("query desconocida") == 0


def test_fake_pubmed_client_simula_fallo():
    client = FakePubMedClient({}, fail=True)
    with pytest.raises(ConnectionError):
        client.contar("cualquier query")


def test_make_pubmed_client_sin_api_key_no_lanza():
    client = make_pubmed_client({})
    assert isinstance(client, PubMedClient)
    assert client._api_key is None


def test_pubmed_client_envuelve_error_de_conexion_como_builtin():
    with patch("core.pubmed_client._requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("boom")
        client = PubMedClient()
        with pytest.raises(ConnectionError) as excinfo:
            client.contar("query cualquiera")
        # No debe ser la excepción de requests (que no hereda del builtin).
        assert not isinstance(excinfo.value, requests.exceptions.RequestException)


def test_pubmed_client_envuelve_json_malformado_como_builtin():
    with patch("core.pubmed_client._requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"esearchresult": {}}  # falta "count"
        mock_get.return_value = mock_resp
        client = PubMedClient()
        with pytest.raises(ConnectionError) as excinfo:
            client.contar("query cualquiera")
        assert not isinstance(excinfo.value, requests.exceptions.RequestException)
