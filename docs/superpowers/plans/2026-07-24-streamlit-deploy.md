# Streamlit Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Streamlit web UI (`streamlit_app.py`) to `epe-generator` that runs the
existing `propose` pipeline from a browser, gated by login, deployable to Streamlit Community
Cloud.

**Architecture:** A single-view Streamlit app sits on top of the already-tested `orchestrator.py`
engine with zero changes to `core/`/`agents/`. `perfilar` (which needs PHI-adjacent Google
credentials) stays local-only; the user uploads the `perfil_epe.yaml` it produces, and the app
runs `run_propose(...)` against it.

**Tech Stack:** Streamlit (`streamlit>=1.36`, already in `requirements.txt`), `hmac` (stdlib,
timing-safe credential comparison), `tempfile` (stdlib).

## Global Constraints

- `GOOGLE_SERVICE_ACCOUNT_JSON` and `EPE_SHEET_ID` must NEVER be read from or copied to
  `st.secrets`/`os.environ` inside `streamlit_app.py` — `perfilar` is exclusively local, per
  the design decision in `docs/superpowers/specs/2026-07-24-streamlit-deploy-design.md` §3.
- Only these six keys may be bridged from `st.secrets` to `os.environ`: `LLM_PROVIDER`,
  `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `PUBMED_API_KEY`, `AUTH_USER`, `AUTH_PASSWORD`.
- Empty/missing `AUTH_USER`/`AUTH_PASSWORD` must make login always fail (never leave the app
  open because secrets are unset).
- No changes to `orchestrator.py`, `core/knowledge.py`, `core/llm_client.py`,
  `core/pubmed_client.py`, `agents/gap_finder.py`, `ui_render.py` — the UI is a new layer only.
- The app is stateless on the server: no writes to disk outside a single temp file per
  "Generar candidatos" click, which is not persisted or reused across requests.

---

## File Structure

```
epe-generator/
  core/
    auth.py          # NEW — verificar_credenciales(usuario_in, pass_in, usuario_real, pass_real) -> bool
  tests/
    test_auth.py      # NEW — unit tests for verificar_credenciales
  streamlit_app.py     # NEW — the UI itself (not unit-tested, per spec §6; verified by manual run)
  README.md            # MODIFIED — add deploy section
```

---

### Task 1: `core/auth.py` — timing-safe credential check

**Files:**
- Create: `core/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces: `verificar_credenciales(usuario_in: str, pass_in: str, usuario_real: str, pass_real: str) -> bool`. Used by `streamlit_app.py` (Task 2) as the login gate's check.

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth.py`:

```python
from core.auth import verificar_credenciales


def test_verificar_credenciales_correctas():
    assert verificar_credenciales("leo", "s3cret", "leo", "s3cret") is True


def test_verificar_credenciales_usuario_incorrecto():
    assert verificar_credenciales("otro", "s3cret", "leo", "s3cret") is False


def test_verificar_credenciales_password_incorrecta():
    assert verificar_credenciales("leo", "mala", "leo", "s3cret") is False


def test_verificar_credenciales_ambas_incorrectas():
    assert verificar_credenciales("otro", "mala", "leo", "s3cret") is False


def test_verificar_credenciales_config_vacia_usuario_real_ausente():
    assert verificar_credenciales("leo", "s3cret", "", "s3cret") is False


def test_verificar_credenciales_config_vacia_password_real_ausente():
    assert verificar_credenciales("leo", "s3cret", "leo", "") is False


def test_verificar_credenciales_config_totalmente_vacia():
    assert verificar_credenciales("", "", "", "") is False


def test_verificar_credenciales_entradas_vacias_contra_config_real():
    assert verificar_credenciales("", "", "leo", "s3cret") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.auth'`

- [ ] **Step 3: Write `core/auth.py`**

```python
from __future__ import annotations

import hmac


def verificar_credenciales(usuario_in: str, pass_in: str,
                           usuario_real: str, pass_real: str) -> bool:
    """Compara credenciales en tiempo constante. Config vacía (sin usuario/pass
    real) => siempre False, para no dejar la app abierta por secrets ausentes."""
    if not usuario_real or not pass_real:
        return False
    u_ok = hmac.compare_digest(usuario_in or "", usuario_real)
    p_ok = hmac.compare_digest(pass_in or "", pass_real)
    return u_ok and p_ok
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: PASS (63 prior + 8 new = 71 passed)

- [ ] **Step 6: Commit**

```bash
git add core/auth.py tests/test_auth.py
git commit -m "feat: timing-safe login credential check (core/auth.py)"
```

---

### Task 2: `streamlit_app.py` — single-view UI over `propose`

**Files:**
- Create: `streamlit_app.py`

**Interfaces:**
- Consumes:
  - `core.auth.verificar_credenciales(usuario_in, pass_in, usuario_real, pass_real) -> bool` (Task 1)
  - `core.llm_client.make_client(env: dict)` — raises `ValueError` if misconfigured
  - `core.pubmed_client.make_pubmed_client(env: dict) -> PubMedClient` — never raises
  - `core.knowledge.load_perfil(path: str) -> Perfil`
  - `orchestrator.run_propose(plantilla_path: str, perfil_path: str, pubmed_client, llm_client, top_n: int = 5, max_candidatos: int = 40) -> AgentResult` — `AgentResult` has `.ok: bool`, `.data: list[dict]`, `.warnings: list[str]`
  - `ui_render.render_candidatos_md(filas: list[dict], warnings: list[str]) -> str`
  - `ui_render.render_candidatos_json(filas: list[dict]) -> str`
- Produces: nothing consumed by later tasks — this is the final UI layer.

This task has no automated test (per spec §6 — Streamlit UI is verified manually, matching
`endes-generator`'s convention). The verification step below is a manual run.

- [ ] **Step 1: Write `streamlit_app.py`**

```python
from __future__ import annotations

import os
import tempfile

import streamlit as st

from core.auth import verificar_credenciales
from core.knowledge import load_perfil
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from orchestrator import run_propose
from ui_render import render_candidatos_json, render_candidatos_md

_SECRET_KEYS = ("LLM_PROVIDER", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL",
               "PUBMED_API_KEY", "AUTH_USER", "AUTH_PASSWORD")


def _puente_secrets_a_env() -> None:
    """Copia las claves de st.secrets a os.environ (idempotente, tolerante a
    ausencias). NUNCA incluye GOOGLE_SERVICE_ACCOUNT_JSON ni EPE_SHEET_ID —
    perfilar es exclusivamente local (ver docs/superpowers/specs/
    2026-07-24-streamlit-deploy-design.md, §3)."""
    for k in _SECRET_KEYS:
        if k in st.secrets and k not in os.environ:
            os.environ[k] = str(st.secrets[k])


def _cliente_llm_o_none():
    try:
        return make_client(os.environ)
    except ValueError as exc:
        st.warning(f"LLM no disponible: {exc} — modo degradado (ranking por novedad).")
        return None


def _gate_login() -> bool:
    if st.session_state.get("auth_ok"):
        return True
    st.title("epe-generator")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if verificar_credenciales(u, p, os.environ.get("AUTH_USER", ""),
                                      os.environ.get("AUTH_PASSWORD", "")):
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("Credenciales inválidas.")
    return False


def vista_propose() -> None:
    st.header("Propose — semillas de investigación EPE")
    st.info(
        "`perfilar` corre exclusivamente en tu máquina (necesita la credencial de "
        "Google con acceso al Sheet EPE, que nunca sube a la nube):\n\n"
        "1. Corre `python orchestrator.py perfilar` localmente.\n"
        "2. Sube aquí el `knowledge/perfil_epe.yaml` que produce.\n"
        "3. Genera candidatos y descarga el resultado."
    )
    subido = st.file_uploader("Sube perfil_epe.yaml", type="yaml")
    if not subido:
        return
    if st.button("Generar candidatos"):
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".yaml", delete=False) as tmp:
            tmp.write(subido.getvalue())
            ruta_perfil = tmp.name
        try:
            load_perfil(ruta_perfil)  # valida que el YAML subido sea un perfil legible
        except Exception as exc:
            st.error(f"No se pudo leer el perfil subido: {exc}")
            os.unlink(ruta_perfil)
            return

        llm_client = _cliente_llm_o_none()
        if llm_client is None:
            from core.llm_client import FakeLLMClient
            llm_client = FakeLLMClient(default='{"score": 0, "justificacion": ""}')
        pubmed_client = make_pubmed_client(os.environ)

        try:
            r = run_propose("knowledge/plantilla_epe.yaml", ruta_perfil,
                            pubmed_client, llm_client)
        finally:
            os.unlink(ruta_perfil)

        for w in r.warnings:
            st.warning(w)
        st.markdown(render_candidatos_md(r.data, r.warnings))
        if r.data:
            c1, c2 = st.columns(2)
            c1.download_button("Descargar candidatos.md",
                               render_candidatos_md(r.data, r.warnings),
                               file_name="candidatos.md")
            c2.download_button("Descargar candidatos.json",
                               render_candidatos_json(r.data),
                               file_name="candidatos.json", mime="application/json")


def main() -> None:
    _puente_secrets_a_env()
    st.set_page_config(page_title="epe-generator", layout="wide")
    if not _gate_login():
        return
    vista_propose()


if __name__ == "__main__":
    main()
```

Note: `load_perfil` only accepts a path, not bytes, so the uploaded content is written to one
temp file that's reused for both the validation read and the `run_propose` call, then deleted.

- [ ] **Step 2: Manual verification — run the app locally**

Run: `streamlit run streamlit_app.py`

Expected: browser opens to a login form titled "epe-generator". This step requires a local
`.env` with `AUTH_USER`/`AUTH_PASSWORD` set (reuse the ones already in `epe-generator/.env`
from the earlier real-data validation session) — Streamlit does not read `.env` automatically,
so also add a `.streamlit/secrets.toml` for local testing:

```bash
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'EOF'
LLM_PROVIDER = "deepseek"
DEEPSEEK_API_KEY = "PASTE_FROM_.env"
DEEPSEEK_MODEL = "deepseek-v4-flash"
PUBMED_API_KEY = "PASTE_FROM_.env"
AUTH_USER = "leo"
AUTH_PASSWORD = "pick-a-local-test-password"
EOF
```

`.streamlit/secrets.toml` must already be covered by `.gitignore`'s `.env` pattern? — No, it
is a different filename. Add it explicitly:

```bash
echo ".streamlit/secrets.toml" >> .gitignore
```

- [ ] **Step 3: Manual verification — log in and run propose**

In the browser: enter the `AUTH_USER`/`AUTH_PASSWORD` from `.streamlit/secrets.toml`, submit.
Expected: login succeeds, "Propose" view appears with the file uploader.

Upload the real `knowledge/perfil_epe.yaml` produced in the earlier validation session (it
still exists on disk from the `perfilar` run — confirm with `ls knowledge/perfil_epe.yaml`).
Click "Generar candidatos".

Expected: candidates render as markdown (same content shape as `outputs/*/candidatos.md` from
the CLI run), with working download buttons for both `.md` and `.json`.

- [ ] **Step 4: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: PASS (71 passed, unchanged from Task 1 — `streamlit_app.py` has no automated tests)

- [ ] **Step 5: Commit**

```bash
git add streamlit_app.py .gitignore
git commit -m "feat: Streamlit UI for propose phase (perfilar stays local)"
```

---

### Task 3: README — deploy instructions

**Files:**
- Modify: `README.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add a deploy section to `README.md`**

Insert this new section immediately after the existing `## Comandos` section (before
`## Privacidad`):

```markdown
## Deploy en Streamlit Community Cloud

La UI (`streamlit_app.py`) corre solo la fase `propose` en la nube. `perfilar` (necesita la
credencial de Google con acceso al Sheet EPE, que contiene PHI real) queda **exclusivamente
local** — su credencial nunca sube a los secrets de Streamlit Cloud.

1. Corre `python orchestrator.py perfilar` en tu máquina para producir
   `knowledge/perfil_epe.yaml`.
2. En [share.streamlit.io](https://share.streamlit.io), conecta el repo y apunta a
   `streamlit_app.py`.
3. En **Secrets**, pega `LLM_PROVIDER`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`,
   `PUBMED_API_KEY`, `AUTH_USER`, `AUTH_PASSWORD` (genera credenciales de login nuevas,
   no reuses las de otros proyectos). **Nunca** pegues `GOOGLE_SERVICE_ACCOUNT_JSON` ni
   `EPE_SHEET_ID` ahí.
4. La app queda tras login. Flujo: `perfilar` local → subes `perfil_epe.yaml` en la app →
   `propose` → descargas `candidatos.md`/`.json`.

La app es sin estado: no persiste nada en el servidor entre subidas.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: deploy instructions for Streamlit Community Cloud"
```

---

## Post-plan manual step (not automatable, not part of the test suite)

After Task 3 is merged, the human (Leonid) must:
1. Go to [share.streamlit.io](https://share.streamlit.io) and connect the
   `github.com/leonidcapo/epe-generator` repo, pointing to `streamlit_app.py`.
2. Generate new `AUTH_USER`/`AUTH_PASSWORD` credentials (don't reuse nucleo's) and paste all
   six secrets into the Streamlit Cloud app's Secrets panel.
3. Run `perfilar` locally, upload the resulting `perfil_epe.yaml` to the deployed app, and
   confirm `propose` produces the same shape of output as the local CLI run did.
