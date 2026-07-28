from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from core.auth import verificar_credenciales
from core.knowledge import load_perfil
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from orchestrator import run_analyze, run_design, run_propose, run_report
from ui_render import (render_articulo_md, render_candidatos_json, render_candidatos_md,
                       render_protocolo_docx, render_protocolo_md)

_SECRET_KEYS = ("LLM_PROVIDER", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL",
               "PUBMED_API_KEY", "AUTH_USER", "AUTH_PASSWORD")

_PLANTILLA = str(Path(__file__).parent / "knowledge" / "plantilla_epe.yaml")
_LIMITACIONES = str(Path(__file__).parent / "knowledge" / "limitaciones_epe.yaml")


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


def _cliente_llm_o_none():
    try:
        return make_client(os.environ)
    except ValueError as exc:
        st.warning(f"LLM no disponible: {exc} — modo degradado (ranking por novedad).")
        return None


def _parsear_candidatos_subido(subido) -> list[dict] | None:
    try:
        items = json.loads(subido.getvalue().decode("utf-8"))
    except Exception as exc:
        st.error(f"No se pudo leer candidatos.json: {exc}")
        return None
    if not isinstance(items, list) or not all("id" in it for it in items):
        st.error("El archivo no tiene el formato esperado de candidatos.json.")
        return None
    return items


def _selector_candidato(items: list[dict]) -> str:
    etiquetas = {
        f"{it['eje']} × {it['subpoblacion']} → {it['outcome']} ({it['id']})": it["id"]
        for it in items
    }
    etiqueta = st.selectbox("Candidato", list(etiquetas.keys()))
    return etiquetas[etiqueta]


def _guardar_temp_json(items: list[dict]) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                     encoding="utf-8") as tmp:
        json.dump(items, tmp)
        return tmp.name


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


def vista_design() -> None:
    st.header("Design — protocolo de investigación")
    subido = st.file_uploader("Sube candidatos.json", type=["json"], key="design_candidatos")
    if not subido:
        return
    items = _parsear_candidatos_subido(subido)
    if items is None:
        return
    if not items:
        st.warning("El archivo no tiene candidatos.")
        return
    candidato_id = _selector_candidato(items)
    if st.button("Generar protocolo"):
        ruta_candidatos = _guardar_temp_json(items)
        try:
            r = run_design(candidato_id, _PLANTILLA, _LIMITACIONES,
                           candidatos_json_path=ruta_candidatos)
        except Exception as exc:
            st.error(f"Ocurrió un error generando el protocolo: {exc}")
            return
        finally:
            os.unlink(ruta_candidatos)
        st.session_state["resultado_design"] = r

    if "resultado_design" in st.session_state:
        r = st.session_state["resultado_design"]
        for w in r.warnings:
            st.warning(w)
        if r.ok:
            protocolo = r.data
            st.markdown(render_protocolo_md(protocolo))
            c1, c2 = st.columns(2)
            c1.download_button("Descargar protocolo.md", render_protocolo_md(protocolo),
                               file_name="protocolo.md")
            c2.download_button(
                "Descargar protocolo.docx", render_protocolo_docx(protocolo),
                file_name="protocolo.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            st.error("No se pudo generar el protocolo.")


def vista_analyze() -> None:
    st.header("Analyze — sintaxis Stata")
    subido = st.file_uploader("Sube candidatos.json", type=["json"], key="analyze_candidatos")
    if not subido:
        return
    items = _parsear_candidatos_subido(subido)
    if items is None:
        return
    if not items:
        st.warning("El archivo no tiene candidatos.")
        return
    candidato_id = _selector_candidato(items)
    if st.button("Generar análisis"):
        ruta_candidatos = _guardar_temp_json(items)
        try:
            r = run_analyze(candidato_id, _PLANTILLA, candidatos_json_path=ruta_candidatos)
        except Exception as exc:
            st.error(f"Ocurrió un error generando el análisis: {exc}")
            return
        finally:
            os.unlink(ruta_candidatos)
        st.session_state["resultado_analyze"] = r

    if "resultado_analyze" in st.session_state:
        r = st.session_state["resultado_analyze"]
        for w in r.warnings:
            st.warning(w)
        if r.ok:
            st.code(r.data, language="stata")
            st.download_button("Descargar analisis.do", r.data, file_name="analisis.do")
        else:
            st.error("No se pudo generar el análisis.")


def vista_report() -> None:
    st.header("Report — informe final")
    subido_candidatos = st.file_uploader("Sube candidatos.json", type=["json"],
                                         key="report_candidatos")
    subido_xlsx = st.file_uploader("Sube resultados.xlsx", type=["xlsx"], key="report_xlsx")
    if not subido_candidatos or not subido_xlsx:
        return
    items = _parsear_candidatos_subido(subido_candidatos)
    if items is None:
        return
    if not items:
        st.warning("El archivo no tiene candidatos.")
        return
    candidato_id = _selector_candidato(items)
    if st.button("Generar informe"):
        ruta_candidatos = _guardar_temp_json(items)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_xlsx:
            tmp_xlsx.write(subido_xlsx.getvalue())
            ruta_xlsx = tmp_xlsx.name
        try:
            r = run_report(candidato_id, ruta_xlsx, _PLANTILLA, _LIMITACIONES,
                           candidatos_json_path=ruta_candidatos)
        except Exception as exc:
            st.error(f"Ocurrió un error generando el informe: {exc}")
            return
        finally:
            os.unlink(ruta_candidatos)
            os.unlink(ruta_xlsx)
        st.session_state["resultado_report"] = r

    if "resultado_report" in st.session_state:
        r = st.session_state["resultado_report"]
        for w in r.warnings:
            st.warning(w)
        if r.ok:
            articulo = r.data
            st.markdown(render_articulo_md(articulo))
            st.download_button("Descargar articulo.md", render_articulo_md(articulo),
                               file_name="articulo.md")
        else:
            st.error("No se pudo generar el informe.")


def main() -> None:
    _puente_secrets_a_env()
    st.set_page_config(page_title="epe-generator", layout="wide")
    if not _gate_login():
        return
    vista = st.sidebar.radio("Fase", ["Propose", "Design", "Analyze", "Report"])
    if vista == "Propose":
        vista_propose()
    elif vista == "Design":
        vista_design()
    elif vista == "Analyze":
        vista_analyze()
    else:
        vista_report()


if __name__ == "__main__":
    main()
