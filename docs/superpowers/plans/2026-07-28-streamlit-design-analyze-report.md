# Streamlit Design/Analyze/Report Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the deployed Streamlit app (`streamlit_app.py`) with 3 new views —
Design, Analyze, Report — so the full 4-phase cycle (`propose` → `design` → `analyze` →
`report`) is usable from the cloud, not just the CLI.

**Architecture:** `orchestrator.py`'s `run_design`/`run_analyze`/`run_report` gain an
optional `candidatos_json_path` parameter so Streamlit can pass an uploaded file's
temp path directly, bypassing the CLI's `outputs/`-directory glob entirely (avoids
cross-session collision risk on a shared deployed instance). `streamlit_app.py` gains 3
new view functions following the exact upload→generate→download pattern
`vista_propose` already uses, wired together via a sidebar radio nav.

**Tech Stack:** No new dependencies — reuses existing `streamlit`, `orchestrator.py`,
`ui_render.py` functions.

## Global Constraints

- `candidatos_json_path: str | None = None` is purely additive on
  `_localizar_candidato`/`run_design`/`run_analyze`/`run_report` — when omitted, behavior
  is byte-identical to today (glob `outputs/*/candidatos.json`, take the most recent). No
  existing CLI test may change.
- When `candidatos_json_path` is passed, NOTHING under `outputs/` is read or written by
  candidate lookup — this is the whole point (session isolation on a shared deployed
  instance).
- No PHI touches any of the 3 new views — same security model as `vista_propose` today
  (uploaded files are aggregated candidate metadata / model output statistics, never
  patient rows).
- No new Streamlit secrets — the 6 keys already in `_SECRET_KEYS` cover everything
  `design`/`report` need (`DEEPSEEK_API_KEY` etc.); `analyze` needs no LLM at all.
- Same upload→generate→download pattern as `vista_propose`, no state persisted across
  sessions, nothing written to a directory shared between users.
- `streamlit_app.py` has no automated tests today (UI/Streamlit-runtime code is out of
  scope for this project's "pure logic" test convention — see `CLAUDE.md`) — this plan
  does not add any either, consistent with `vista_propose`'s own precedent. Task 2 ends
  with a manual verification checklist instead of `pytest` steps.

---

## File Structure

```
epe-generator/
  orchestrator.py    # MODIFIED — _localizar_candidato/run_design/run_analyze/run_report gain candidatos_json_path
  streamlit_app.py     # MODIFIED — vista_design, vista_analyze, vista_report + sidebar nav
  tests/
    test_orchestrator.py  # MODIFIED — candidatos_json_path tests
```

---

### Task 1: `orchestrator.py` — `candidatos_json_path` parameter

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_localizar_candidato(candidato_id_buscado: str, candidatos_json_path: str |
  None = None) -> tuple[Candidato | None, list[str]]`; `run_design(candidato_id_buscado,
  plantilla_path=..., limitaciones_path=..., candidatos_json_path: str | None = None) ->
  AgentResult`; `run_analyze(candidato_id_buscado, plantilla_path=..., candidatos_json_path:
  str | None = None) -> AgentResult`; `run_report(candidato_id_buscado,
  resultados_xlsx_path, plantilla_path=..., limitaciones_path=..., candidatos_json_path:
  str | None = None) -> AgentResult`. Used by `streamlit_app.py` (Task 2).

- [ ] **Step 1: Write the failing tests — append to `tests/test_orchestrator.py`**

```python
def test_localizar_candidato_con_ruta_explicita_no_toca_outputs(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    candidatos_path = tmp_path / "mi_candidatos.json"
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": [],
        "n_disponible": 100, "novedad": 1.0, "score_llm": 8.0,
    }
    candidatos_path.write_text(json.dumps([candidato_data]), encoding="utf-8")
    candidato, errores = orchestrator._localizar_candidato("abc", str(candidatos_path))
    assert candidato is not None
    assert errores == []
    assert not (tmp_path / "outputs").exists()


def test_localizar_candidato_ruta_explicita_no_encontrado(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    candidatos_path = tmp_path / "mi_candidatos.json"
    candidatos_path.write_text(json.dumps([]), encoding="utf-8")
    candidato, errores = orchestrator._localizar_candidato("no_existe", str(candidatos_path))
    assert candidato is None
    assert errores


def test_localizar_candidato_ruta_explicita_archivo_faltante(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    candidato, errores = orchestrator._localizar_candidato(
        "abc", str(tmp_path / "no_existe.json"))
    assert candidato is None
    assert errores


def test_run_design_con_candidatos_json_path_explicito(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidatos_path = tmp_path / "mi_candidatos.json"
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": [],
        "n_disponible": 100, "novedad": 1.0, "score_llm": 8.0,
    }
    candidatos_path.write_text(json.dumps([candidato_data]), encoding="utf-8")
    r = orchestrator.run_design("abc", candidatos_json_path=str(candidatos_path))
    assert r.ok
    assert not (tmp_path / "outputs").exists()


def test_run_analyze_con_candidatos_json_path_explicito(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidatos_path = tmp_path / "mi_candidatos.json"
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": [],
        "n_disponible": 100, "novedad": 1.0, "score_llm": 8.0,
    }
    candidatos_path.write_text(json.dumps([candidato_data]), encoding="utf-8")
    r = orchestrator.run_analyze("abc", candidatos_json_path=str(candidatos_path))
    assert r.ok
    assert not (tmp_path / "outputs").exists()


def test_run_report_con_candidatos_json_path_explicito(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidatos_path = tmp_path / "mi_candidatos.json"
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": [],
        "n_disponible": 100, "novedad": 1.0, "score_llm": 8.0,
    }
    candidatos_path.write_text(json.dumps([candidato_data]), encoding="utf-8")
    xlsx_path = _resultados_xlsx_valido(tmp_path)
    r = orchestrator.run_report("abc", xlsx_path, candidatos_json_path=str(candidatos_path))
    assert r.ok
    assert not (tmp_path / "outputs").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v -k candidatos_json_path`
Expected: FAIL with `TypeError: _localizar_candidato() got an unexpected keyword argument`
(or positional-arg-count errors for `run_design`/`run_analyze`/`run_report`)

- [ ] **Step 3: Implement in `orchestrator.py`**

Replace the existing `_localizar_candidato`:

```python
def _localizar_candidato(candidato_id_buscado: str) -> tuple[Candidato | None, list[str]]:
    jsons = sorted(Path("outputs").glob("*/candidatos.json"), key=lambda p: p.stat().st_mtime)
    if not jsons:
        return None, ["No hay candidatos.json; corre 'propose' primero."]
    data = json.loads(jsons[-1].read_text(encoding="utf-8"))
    item = next((it for it in data if it["id"] == candidato_id_buscado), None)
    if item is None:
        return None, [f"Candidato '{candidato_id_buscado}' no encontrado en {jsons[-1]}."]
    return _candidato_desde_json(item), []
```

with:

```python
def _localizar_candidato(candidato_id_buscado: str,
                         candidatos_json_path: str | None = None) -> tuple[Candidato | None, list[str]]:
    if candidatos_json_path is not None:
        ruta = Path(candidatos_json_path)
        if not ruta.exists():
            return None, [f"No existe el archivo de candidatos: {candidatos_json_path}"]
    else:
        jsons = sorted(Path("outputs").glob("*/candidatos.json"), key=lambda p: p.stat().st_mtime)
        if not jsons:
            return None, ["No hay candidatos.json; corre 'propose' primero."]
        ruta = jsons[-1]
    data = json.loads(ruta.read_text(encoding="utf-8"))
    item = next((it for it in data if it["id"] == candidato_id_buscado), None)
    if item is None:
        return None, [f"Candidato '{candidato_id_buscado}' no encontrado en {ruta}."]
    return _candidato_desde_json(item), []
```

Replace `run_design`:

```python
def run_design(candidato_id_buscado: str, plantilla_path: str = "knowledge/plantilla_epe.yaml",
              limitaciones_path: str = "knowledge/limitaciones_epe.yaml") -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado)
```

with:

```python
def run_design(candidato_id_buscado: str, plantilla_path: str = "knowledge/plantilla_epe.yaml",
              limitaciones_path: str = "knowledge/limitaciones_epe.yaml",
              candidatos_json_path: str | None = None) -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado, candidatos_json_path)
```

(the rest of `run_design`'s body is unchanged).

Replace `run_analyze`:

```python
def run_analyze(candidato_id_buscado: str,
                plantilla_path: str = "knowledge/plantilla_epe.yaml") -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado)
```

with:

```python
def run_analyze(candidato_id_buscado: str,
                plantilla_path: str = "knowledge/plantilla_epe.yaml",
                candidatos_json_path: str | None = None) -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado, candidatos_json_path)
```

(the rest of `run_analyze`'s body is unchanged).

Replace `run_report`:

```python
def run_report(candidato_id_buscado: str, resultados_xlsx_path: str,
               plantilla_path: str = "knowledge/plantilla_epe.yaml",
               limitaciones_path: str = "knowledge/limitaciones_epe.yaml") -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado)
```

with:

```python
def run_report(candidato_id_buscado: str, resultados_xlsx_path: str,
               plantilla_path: str = "knowledge/plantilla_epe.yaml",
               limitaciones_path: str = "knowledge/limitaciones_epe.yaml",
               candidatos_json_path: str | None = None) -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado, candidatos_json_path)
```

(the rest of `run_report`'s body is unchanged).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests, including the 6 new ones, AND every pre-existing
`test_run_design_*`/`test_run_analyze_*`/`test_run_report_*`/`test_localizar_candidato_*`
test still passes unchanged — confirms the new parameter is purely additive)

- [ ] **Step 5: Run the FULL suite**

Run: `python -m pytest -q`
Expected: PASS, all files green (baseline before this task: 167 passed; expect 173 after
this task's 6 new tests).

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: candidatos_json_path opcional en run_design/run_analyze/run_report (aisla sesiones Streamlit de outputs/)"
```

---

### Task 2: `streamlit_app.py` — vistas Design, Analyze, Report

**Files:**
- Modify: `streamlit_app.py`

**Interfaces:**
- Consumes: `run_design`, `run_analyze`, `run_report` (Task 1, with
  `candidatos_json_path`); `render_protocolo_md`, `render_protocolo_docx`,
  `render_articulo_md` from `ui_render.py` (all already exist, unchanged).
- Produces: `vista_design() -> None`, `vista_analyze() -> None`, `vista_report() -> None`,
  wired into `main()` via a sidebar radio. No automated tests (see Global Constraints) —
  this task ends with a manual verification checklist instead of `pytest` steps.

- [ ] **Step 1: Add new imports and constants to `streamlit_app.py`**

At the top of the file, change:

```python
from core.auth import verificar_credenciales
from core.knowledge import load_perfil
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from orchestrator import run_propose
from ui_render import render_candidatos_json, render_candidatos_md
```

to:

```python
import json

from core.auth import verificar_credenciales
from core.knowledge import load_perfil
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from orchestrator import run_analyze, run_design, run_propose, run_report
from ui_render import (render_articulo_md, render_candidatos_json, render_candidatos_md,
                       render_protocolo_docx, render_protocolo_md)
```

Right after the existing `_PLANTILLA = str(Path(__file__).parent / "knowledge" /
"plantilla_epe.yaml")` line, add:

```python
_LIMITACIONES = str(Path(__file__).parent / "knowledge" / "limitaciones_epe.yaml")
```

- [ ] **Step 2: Add shared helper functions**

Right after the existing `_cliente_llm_o_none` function (before `_gate_login`), add:

```python
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
```

- [ ] **Step 3: Add `vista_design`**

Right after `vista_propose` (before `main`), add:

```python
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
```

- [ ] **Step 4: Add `vista_analyze`**

Right after `vista_design`, add:

```python
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
```

- [ ] **Step 5: Add `vista_report`**

Right after `vista_analyze`, add:

```python
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
```

- [ ] **Step 6: Wire the sidebar navigation into `main()`**

Replace:

```python
def main() -> None:
    _puente_secrets_a_env()
    st.set_page_config(page_title="epe-generator", layout="wide")
    if not _gate_login():
        return
    vista_propose()
```

with:

```python
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
```

- [ ] **Step 7: Manual verification**

Run: `streamlit run streamlit_app.py` (needs a local `.env` with `AUTH_USER`/
`AUTH_PASSWORD` at minimum — `DEEPSEEK_API_KEY` optional, to also verify the degraded-LLM
path).

Checklist:
1. Log in. Confirm the sidebar shows 4 options: Propose, Design, Analyze, Report.
2. **Propose** (regression check — must still work exactly as before): upload a
   `perfil_epe.yaml` (from a real `python orchestrator.py perfilar` run, or reuse an
   existing one), generate candidates, confirm `candidatos.md`/`candidatos.json` downloads
   work.
3. **Design**: upload the `candidatos.json` just downloaded from step 2 (or any real one).
   Confirm the selectbox lists candidates with readable labels. Pick one, click "Generar
   protocolo". Confirm the protocol renders on screen and both `protocolo.md` and
   `protocolo.docx` download buttons work and produce valid files. If no `DEEPSEEK_API_KEY`
   is configured, confirm the degraded-LLM warning appears (via `r.warnings`) and the
   protocol still renders with `[prosa pendiente: LLM no disponible]` placeholders instead
   of crashing.
4. **Analyze**: upload the same `candidatos.json`, pick a candidate, click "Generar
   análisis". Confirm `analisis.do` renders as a code block and downloads correctly — no
   LLM warning should ever appear here (analyze is LLM-free).
5. **Report**: upload the same `candidatos.json` PLUS a real or synthetic
   `resultados.xlsx` (can reuse one of the test fixtures' shape: sheets `descriptivos`,
   `modelo`, optionally `bivariado_*`, rows `b`/`ll`/`ul`). Pick a candidate, click "Generar
   informe". Confirm `articulo.md` renders and downloads.
6. Confirm switching between sidebar tabs preserves each tab's last generated result (via
   `st.session_state`) without needing to regenerate — e.g. go Design → Analyze → back to
   Design, confirm the protocol is still shown without re-clicking "Generar protocolo".
7. Confirm no `outputs/` directory appears in the project root after any of steps 3-5 (this
   proves `candidatos_json_path` is correctly bypassing the CLI's filesystem convention).

- [ ] **Step 8: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: vistas Design/Analyze/Report en streamlit_app.py (ciclo completo en la nube)"
```
