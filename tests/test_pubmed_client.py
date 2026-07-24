import pytest

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
