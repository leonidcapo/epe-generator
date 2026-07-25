from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from core.auth import verificar_credenciales
from core.knowledge import load_perfil
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from orchestrator import run_propose
from ui_render import render_candidatos_json, render_candidatos_md

_SECRET_KEYS = ("LLM_PROVIDER", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL",
               "PUBMED_API_KEY", "AUTH_USER", "AUTH_PASSWORD")

_PLANTILLA = str(Path(__file__).parent / "knowledge" / "plantilla_epe.yaml")


def _puente_secrets_a_env() -> None:
    """Copia las claves de st.secrets a os.environ (idempotente, tolerante a
    ausencias). NUNCA incluye GOOGLE_SERVICE_ACCOUNT_JSON ni EPE_SHEET_ID —
    perfilar es exclusivamente local (ver docs/superpowers/specs/
    2026-07-24-streamlit-deploy-design.md, §3)."""
    try:
        disponibles = st.secrets
    except Exception:
        return  # sin secrets.toml (p.ej. corrida local con .env) — no es un error
    for k in _SECRET_KEYS:
        if k in disponibles and k not in os.environ:
            os.environ[k] = str(disponibles[k])


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
    subido = st.file_uploader("Sube perfil_epe.yaml", type=["yaml", "yml"])
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
            r = run_propose(_PLANTILLA, ruta_perfil, pubmed_client, llm_client)
        except Exception as exc:
            st.error(f"Ocurrió un error generando candidatos: {exc}")
            return
        finally:
            os.unlink(ruta_perfil)

        st.session_state["resultado"] = (r.data, r.warnings)

    if "resultado" in st.session_state:
        data, warnings = st.session_state["resultado"]
        for w in warnings:
            st.warning(w)
        st.markdown(render_candidatos_md(data, warnings))
        if data:
            c1, c2 = st.columns(2)
            c1.download_button("Descargar candidatos.md",
                               render_candidatos_md(data, warnings),
                               file_name="candidatos.md")
            c2.download_button("Descargar candidatos.json",
                               render_candidatos_json(data),
                               file_name="candidatos.json", mime="application/json")


def main() -> None:
    _puente_secrets_a_env()
    st.set_page_config(page_title="epe-generator", layout="wide")
    if not _gate_login():
        return
    vista_propose()


if __name__ == "__main__":
    main()
