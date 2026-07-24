import pytest

from core.llm_client import FakeLLMClient, make_client


def test_fake_llm_client_devuelve_default_sin_respuestas():
    client = FakeLLMClient()
    assert client.call("sys", "user") == "{}"
    assert client.call_count == 1


def test_fake_llm_client_cicla_respuestas():
    client = FakeLLMClient(responses=["a", "b"])
    assert [client.call("s", "u") for _ in range(3)] == ["a", "b", "a"]


def test_fake_llm_client_simula_fallo():
    client = FakeLLMClient(fail=True)
    with pytest.raises(RuntimeError):
        client.call("s", "u")


def test_make_client_sin_api_key_lanza_value_error():
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        make_client({"LLM_PROVIDER": "deepseek"})


def test_make_client_provider_desconocido_lanza_value_error():
    with pytest.raises(ValueError, match="no soportado"):
        make_client({"LLM_PROVIDER": "otro"})
