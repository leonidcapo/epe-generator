# Final Review Fix Report — epe-generator

**Commit date:** 2026-07-28  
**Branch:** `streamlit-design-analyze-report`  
**Status:** All fixes applied and tested.

---

## Fix 1: `_puente_secrets_a_env` crash on local runs without `secrets.toml`

### Issue
`streamlit_app.py` line 25–36 had the `for` loop **outside** the `try/except` block. Since `st.secrets` is lazy-loading, accessing `disponibles = st.secrets` never raises. The actual parsing (and `StreamlitSecretNotFoundError` when no `secrets.toml` exists) only happens when code queries the object — e.g., `k in disponibles` triggers `__contains__` → `_parse()` → raises.

Result: Local runs without `secrets.toml` (the normal dev setup, explicitly called out as supported in the docstring) crashed immediately on page load with an uncaught exception.

### Fix
Moved the `for k in _SECRET_KEYS:` loop from line 34 to inside the `try` block (line 28), so the entire secrets-access sequence (lazy parse included) is covered by exception handling.

**File:** `streamlit_app.py` lines 25–36

```python
def _puente_secrets_a_env() -> None:
    """Copia las claves de st.secrets a os.environ (idempotente, tolerante a
    ausencias). NUNCA incluye GOOGLE_SERVICE_ACCOUNT_JSON ni EPE_SHEET_ID —
    perfilar es exclusivamente local (ver docs/superpowers/specs/
    2026-07-24-streamlit-deploy-design.md, §3)."""
    try:
        disponibles = st.secrets
        for k in _SECRET_KEYS:
            if k in disponibles and k not in os.environ:
                os.environ[k] = str(disponibles[k])
    except Exception:
        return  # sin secrets.toml (p.ej. corrida local con .env) — no es un error
```

### Regression Test
Created `tests/test_streamlit_app.py` with two tests:

1. **`test_puente_secrets_a_env_no_crashea_sin_secrets_toml`**: Mocks `st.secrets` to raise an exception on query (simulating no `secrets.toml`). Asserts that `_puente_secrets_a_env()` returns without propagating the exception.

2. **`test_puente_secrets_a_env_copies_available_secrets_to_environ`**: Mocks `st.secrets` with available values and verifies they're copied to `os.environ`.

Both tests pass.

---

## Fix 2: README.md outdated deployment description

### Issue
Line 40 of `README.md` stated: "La UI (`streamlit_app.py`) corre solo la fase `propose` en la nube."

This was false — the UI now runs all four phases: `propose`, `design`, `analyze`, and `report`. Only `perfilar` remains local-only (because it needs the Google Sheet credentials with PHI, which never leave the local machine).

### Fix
Updated the "Deploy en Streamlit Community Cloud" section (lines 38–62) to:

- Line 40–41: Changed to "La UI (`streamlit_app.py`) corre **todas las cuatro fases** (`propose`, `design`, `analyze`, `report`) en la nube."
- Line 59–60: Updated the deployment flow example to show: "perfilar local → Propose (generate candidatos) → Design (protocol) → Analyze (Stata syntax) → Report (final article with results) → download artifacts."
- Kept the explanation that `perfilar` is **exclusively local** (because of PHI/Google credentials).

**File:** `README.md` lines 38–62

---

## Test Results

### New tests in `test_streamlit_app.py`
```
$ python -m pytest tests/test_streamlit_app.py -v
tests/test_streamlit_app.py::test_puente_secrets_a_env_no_crashea_sin_secrets_toml PASSED
tests/test_streamlit_app.py::test_puente_secrets_a_env_copies_available_secrets_to_environ PASSED
2 passed in 13.63s
```

### Full test suite
```
$ python -m pytest -q
175 passed, 2 warnings in 16.70s
```

**Baseline (before fixes):** 173 tests  
**After fixes:** 175 tests  
**Delta:** +2 (both new regression tests for Fix 1)

---

## Files Changed

| File | Change |
|------|--------|
| `streamlit_app.py` | Fixed: moved `for` loop inside `try` block in `_puente_secrets_a_env()` (lines 25–36) |
| `README.md` | Updated: deployment section to reflect all 4 phases now run in cloud (lines 38–62) |
| `tests/test_streamlit_app.py` | Created: new file with 2 regression tests for secrets-handling |

---

## Commit

All changes committed in a single commit:

```
fix: revision final - bug en puente de secrets (crash sin secrets.toml local) + README streamlit 4 fases
```

Includes:
- Bugfix in `streamlit_app.py` for the lazy-loading secrets crash
- Updated `README.md` deployment docs
- New regression test file `tests/test_streamlit_app.py`
