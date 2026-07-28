"""Regression tests for streamlit_app.py, specifically the st.secrets boundary."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test (outside streamlit run, but we use mocks)
import sys
from pathlib import Path

# Add parent directory to path so we can import streamlit_app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_puente_secrets_a_env_no_crashea_sin_secrets_toml(monkeypatch):
    """Regression: _puente_secrets_a_env must not crash when st.secrets cannot be
    loaded (e.g., no secrets.toml in the environment).

    Bug (commit 2026-07-28): The for loop was OUTSIDE the try/except block.
    st.secrets is lazy-loading: `disponibles = st.secrets` never raises. The
    parsing (and StreamlitSecretNotFoundError) only happens later, when code
    queries it (e.g., `k in disponibles` triggers __contains__ -> _parse()).
    Thus the for loop, being outside the try, crashed the app on local runs
    without a secrets.toml, contradicting the function's own docstring.

    Fix: move the for loop INSIDE the try block.
    """
    # Mock streamlit to simulate the no-secrets.toml scenario
    mock_st = MagicMock()

    # Create a mock secrets object that raises StreamlitSecretNotFoundError
    # when queried (e.g., when __contains__ is called).
    class MockSecretsNoFile:
        def __contains__(self, key):
            # Simulate lazy-parse failure: StreamlitSecretNotFoundError on query
            raise Exception("StreamlitSecretNotFoundError: No secrets.toml found")

    mock_st.secrets = MockSecretsNoFile()

    # Patch the streamlit import in streamlit_app module
    with patch("streamlit_app.st", mock_st):
        import streamlit_app

        # This should NOT raise — the exception should be caught and logged silently.
        # With the old buggy code, this would crash with StreamlitSecretNotFoundError.
        try:
            streamlit_app._puente_secrets_a_env()
        except Exception as e:
            pytest.fail(
                f"_puente_secrets_a_env() raised {type(e).__name__}: {e}. "
                "Should catch exceptions from st.secrets and return silently."
            )


def test_puente_secrets_a_env_copies_available_secrets_to_environ(monkeypatch):
    """_puente_secrets_a_env should copy available secrets from st.secrets to os.environ."""
    # Clean up os.environ for this test
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    # Mock streamlit with available secrets
    mock_st = MagicMock()
    mock_secrets = {
        "LLM_PROVIDER": "deepseek",
        "DEEPSEEK_API_KEY": "test-key-123",
        "PUBMED_API_KEY": "pubmed-key",
    }

    # Create a dict-like mock that supports __contains__ and item access
    class MockSecretsAvailable:
        def __contains__(self, key):
            return key in mock_secrets

        def __getitem__(self, key):
            return mock_secrets[key]

    mock_st.secrets = MockSecretsAvailable()

    with patch("streamlit_app.st", mock_st):
        import streamlit_app

        streamlit_app._puente_secrets_a_env()

        # Verify that available secrets were copied to os.environ
        assert os.environ.get("LLM_PROVIDER") == "deepseek"
        assert os.environ.get("DEEPSEEK_API_KEY") == "test-key-123"
        assert os.environ.get("PUBMED_API_KEY") == "pubmed-key"
