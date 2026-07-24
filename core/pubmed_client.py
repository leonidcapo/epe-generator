from __future__ import annotations

import requests as _requests

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


class FakePubMedClient:
    """Deterministic stub. No network. Set fail=True to simulate an API error."""

    def __init__(self, conteos: dict[str, int], fail: bool = False):
        self._conteos = dict(conteos)
        self._fail = fail

    def contar(self, query: str) -> int:
        if self._fail:
            raise ConnectionError("fallo simulado de conexión a PubMed")
        return self._conteos.get(query, 0)


class PubMedClient:
    """Cliente para NCBI E-utilities (esearch). api_key es opcional (NCBI da un límite
    de tasa menor sin ella, pero funciona)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def contar(self, query: str) -> int:
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 0}
        if self._api_key:
            params["api_key"] = self._api_key
        try:
            resp = _requests.get(_ESEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            return int(resp.json()["esearchresult"]["count"])
        except (_requests.exceptions.RequestException, KeyError, ValueError) as exc:
            raise ConnectionError(f"fallo al consultar PubMed: {exc}") from exc


def make_pubmed_client(env: dict) -> PubMedClient:
    return PubMedClient(api_key=env.get("PUBMED_API_KEY"))
