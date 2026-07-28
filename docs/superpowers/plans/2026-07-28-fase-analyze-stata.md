# Fase Analyze (Sintaxis Stata) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `analyze` phase to `epe-generator`: `python orchestrator.py analyze <candidato_id>`
reads a candidate from the most recent `candidatos.json` and generates `analisis.do` — a
deterministic (no LLM) Stata syntax file the statistician runs manually on their own
exported dataset.

**Architecture:** A new pure function `agents/statistician.py::generar_do(candidato,
plantilla) -> str` reuses `agents/protocol_designer.py::build_estructura` to recompute the
same model selection `design` would produce — no new persisted artifact, no dependency on
`design` having run first. `orchestrator.py` gains `analyze <id>`, sharing a small
candidate-lookup helper extracted from the existing `design` command (`run_design`) to
avoid duplicating that logic.

**Tech Stack:** No new dependencies — pure string generation, same stdlib/yaml/dataclass
patterns already used throughout the project.

## Global Constraints

- `epe-generator` never touches real patient rows in this phase — `analyze` produces only
  the `.do` text. The statistician exports their own `datos.dta` using column names that
  match the plantilla's eje/outcome ids exactly (already valid Stata identifiers:
  snake_case, no special characters).
- No `svy:` prefix on any Stata command — EPE has no complex survey design (no
  peso/estrato/PSU); it is a single-hospital clinical registry, not a probability survey.
- Model → Stata command mapping (exhaustive, matches `agents/protocol_designer.py`'s
  `inferir_modelo` output exactly): `logistica_ordinal`→`ologit`, `logistica_multinomial`→
  `mlogit`, `logistica_binaria`→`logistic`, `lineal`→`regress`.
- The subpoblación filter is NOT translated into executable Stata — no rule for it exists
  anywhere in the codebase today (only as a clinical concept). The `.do` includes a
  comment placeholder only: `* filtrar a subpoblacion: {subpoblacion} (definir criterio
  real con el estadistico)`.
- No citation anchors are fabricated — `build_estructura`'s `diseno['anclajes']` is
  already empty from the `design` phase; `analyze` does not add any.
- 3 blocks per `.do`: header (comments), descriptivos + bivariado, modelo — each
  ends in `putexcel set resultados.xlsx, sheet(<nombre_fijo>) ...` /
  `putexcel A1 = matrix(r(table)), names`, mirroring `endes-generator`'s fixed-sheet
  contract (`descriptivos`, `bivariado_<covariable>`, `modelo`).
- Out of scope: `report` phase, executing Stata automatically, exporting `datos.dta`,
  a multi-phase "expediente" (`estudio.json`), Streamlit integration.

---

## File Structure

```
epe-generator/
  agents/
    statistician.py             # NEW — generar_do(candidato, plantilla) -> str
  orchestrator.py                # MODIFIED — extract _localizar_candidato, add run_analyze/_cmd_analyze, "analyze <id>" CLI
  tests/
    test_statistician.py          # NEW
    test_orchestrator.py           # MODIFIED — run_analyze/_cmd_analyze tests
```

---

### Task 1: `agents/statistician.py`

**Files:**
- Create: `agents/statistician.py`
- Create: `tests/test_statistician.py`

**Interfaces:**
- Consumes: `Candidato` from `agents/novelty_checker.py` (`eje`, `subpoblacion`, `outcome`,
  `covariables_ajuste`); `candidato_id(c)` from the same module; `build_estructura(c, p)`
  from `agents/protocol_designer.py` (already returns `diseno['modelo']` — one of the 4
  exhaustive model names); `Plantilla` from `core/knowledge.py`.
- Produces: `generar_do(candidato: Candidato, plantilla: Plantilla) -> str`. Used by
  `orchestrator.py` (Task 2).

- [ ] **Step 1: Write the failing tests — create `tests/test_statistician.py`**

```python
from agents.novelty_checker import Candidato, candidato_id
from agents.statistician import generar_do
from core.knowledge import Plantilla, load_plantilla


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def _plantilla_sintetica(outcome_tipo: str, outcome_escala: str | None = None) -> Plantilla:
    """La plantilla real de hoy no declara ningun outcome binario/continuo (ver
    docs/superpowers/specs/2026-07-28-fase-design-protocolo-design.md §3) — se construye
    una Plantilla minima para probar esas dos ramas del mapeo modelo->comando."""
    return Plantilla(
        ejes={"exposicion_x": "candidato"},
        subpoblaciones={"poblacion_y": "candidato"},
        outcomes={"outcome_z": outcome_tipo},
        outcomes_escala={"outcome_z": outcome_escala} if outcome_escala else {},
        compatibilidad={"exposicion_x": frozenset({"poblacion_y"})},
        causal_permitido=False,
        n_min=30,
        terminos_busqueda={},
    )


def test_generar_do_ordinal_incluye_encabezado_y_bloques():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                 outcome="nivel_tratamiento_requerido",
                 covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)
    texto = generar_do(c, _plantilla())
    assert candidato_id(c) in texto
    assert 'use "datos.dta", clear' in texto
    assert "* filtrar a subpoblacion: asa3_alto_riesgo" in texto
    assert "sheet(descriptivos)" in texto
    assert "sheet(bivariado_riesgo_sistemico_asa)" in texto
    assert "sheet(bivariado_farmacoterapia_polifarmacia)" in texto
    assert "sheet(modelo)" in texto
    assert "ologit nivel_tratamiento_requerido riesgo_sistemico_asa farmacoterapia_polifarmacia" in texto
    assert "svy" not in texto.lower()


def test_generar_do_nominal_usa_mlogit():
    c = Candidato(eje="cooperacion_manejo_conductual", subpoblacion="discapacidad_intelectual",
                 outcome="grado_cooperacion", covariables_ajuste=("discapacidad_tipo_severidad",),
                 n_disponible=131)
    texto = generar_do(c, _plantilla())
    assert "mlogit grado_cooperacion cooperacion_manejo_conductual discapacidad_tipo_severidad" in texto


def test_generar_do_sin_covariables_no_deja_espacio_colgante():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos",
                 outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=200)
    texto = generar_do(c, _plantilla())
    assert "* covariables de ajuste: (ninguna)" in texto
    assert "ologit nivel_tratamiento_requerido riesgo_sistemico_asa" in texto
    assert "ologit nivel_tratamiento_requerido riesgo_sistemico_asa \n" not in texto


def test_generar_do_binario_usa_logistic():
    p = _plantilla_sintetica("binario")
    c = Candidato(eje="exposicion_x", subpoblacion="poblacion_y", outcome="outcome_z",
                 covariables_ajuste=(), n_disponible=50)
    texto = generar_do(c, p)
    assert "logistic outcome_z exposicion_x" in texto


def test_generar_do_continuo_usa_regress():
    p = _plantilla_sintetica("continuo")
    c = Candidato(eje="exposicion_x", subpoblacion="poblacion_y", outcome="outcome_z",
                 covariables_ajuste=(), n_disponible=50)
    texto = generar_do(c, p)
    assert "regress outcome_z exposicion_x" in texto
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_statistician.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.statistician'`

- [ ] **Step 3: Implement `agents/statistician.py`**

```python
from __future__ import annotations

import time

from agents.novelty_checker import Candidato, candidato_id
from agents.protocol_designer import build_estructura
from core.knowledge import Plantilla

_COMANDO_POR_MODELO = {
    "logistica_ordinal": "ologit",
    "logistica_multinomial": "mlogit",
    "logistica_binaria": "logistic",
    "lineal": "regress",
}


def generar_do(candidato: Candidato, plantilla: Plantilla) -> str:
    """Sintaxis Stata determinista (sin LLM, sin red, sin tocar datos reales) para que
    el estadistico la corra sobre su propio datos.dta exportado. Sin svy: — EPE es un
    registro clinico de un solo hospital, no una encuesta con diseno muestral complejo."""
    estructura = build_estructura(candidato, plantilla)
    modelo = estructura["diseno"]["modelo"]
    comando = _COMANDO_POR_MODELO[modelo]
    outcome = candidato.outcome
    exposicion = candidato.eje
    covariables = list(candidato.covariables_ajuste)
    predictores = " ".join([exposicion, *covariables])
    ajuste_txt = ", ".join(covariables) if covariables else "(ninguna)"

    lines = [
        f"* Analisis EPE — candidato={candidato_id(candidato)}",
        f"* generado: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"* eje (exposicion principal): {exposicion}",
        f"* subpoblacion: {candidato.subpoblacion}",
        f"* outcome: {outcome} (modelo: {modelo})",
        f"* covariables de ajuste: {ajuste_txt}",
        f"* filtrar a subpoblacion: {candidato.subpoblacion} (definir criterio real "
        "con el estadistico)",
        "",
        'use "datos.dta", clear',
        "",
        "* Descriptivos",
        f"mean {outcome} {predictores}",
        "putexcel set resultados.xlsx, sheet(descriptivos) replace",
        "putexcel A1 = matrix(r(table)), names",
        "",
        "* Bivariado (outcome por categoria de cada predictor)",
    ]
    for pred in [exposicion, *covariables]:
        lines.append(f"mean {outcome}, over({pred})")
        lines.append(f"putexcel set resultados.xlsx, sheet(bivariado_{pred}) modify")
        lines.append("putexcel A1 = matrix(r(table)), names")
    lines += [
        "",
        "* Modelo",
        f"{comando} {outcome} {predictores}",
        "putexcel set resultados.xlsx, sheet(modelo) modify",
        "putexcel A1 = matrix(r(table)), names",
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_statistician.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything (baseline before this task: 124 passed) — this task only adds
new files, no existing behavior touched.

- [ ] **Step 6: Commit**

```bash
git add agents/statistician.py tests/test_statistician.py
git commit -m "feat: agents/statistician.py (genera analisis.do, sin svy, sin LLM)"
```

---

### Task 2: `orchestrator.py` — comando `analyze <id>`

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `generar_do(candidato, plantilla)` (Task 1); existing `load_plantilla`,
  `AgentResult`, `Candidato`.
- Produces: `run_analyze(candidato_id_buscado: str, plantilla_path: str =
  "knowledge/plantilla_epe.yaml") -> AgentResult`; `_cmd_analyze(candidato_id_arg: str) ->
  int`; `main`'s CLI dispatch gains the `analyze <id>` subcommand. Internally extracts a
  shared `_localizar_candidato(candidato_id_buscado: str) -> tuple[Candidato | None,
  list[str]]` helper used by BOTH `run_design` (refactored, same external behavior) and
  the new `run_analyze` — avoids duplicating the "find most-recent candidatos.json, match
  by id" logic that currently lives only inside `run_design`.

- [ ] **Step 1: Write the failing tests — append to `tests/test_orchestrator.py`**

```python
def test_run_analyze_encuentra_candidato_y_genera_do(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidato_data = {
        "id": "riesgo_sistemico_asa_asa3_alto_riesgo_nivel_tratamiento_requerido_adj_farmacoterapia_polifarmacia",
        "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": ["farmacoterapia_polifarmacia"],
        "n_disponible": 1350, "novedad": 1.0, "score_llm": 8.0,
    }
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([candidato_data]), encoding="utf-8")
    r = orchestrator.run_analyze(candidato_data["id"])
    assert r.ok
    assert "ologit nivel_tratamiento_requerido" in r.data


def test_run_analyze_candidato_no_encontrado(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([]), encoding="utf-8")
    r = orchestrator.run_analyze("no_existe")
    assert not r.ok


def test_run_analyze_sin_candidatos_json_falla(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = orchestrator.run_analyze("cualquiera")
    assert not r.ok


def test_cmd_analyze_escribe_do(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": ["farmacoterapia_polifarmacia"],
        "n_disponible": 1350, "novedad": 1.0, "score_llm": 8.0,
    }
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([candidato_data]), encoding="utf-8")
    exit_code = orchestrator.main(["analyze", "abc"])
    assert exit_code == 0
    archivos = list((tmp_path / "outputs").glob("*/analisis.do"))
    assert len(archivos) == 1
```

Note: unlike the `design` tests, these do NOT need `_copiar_limitaciones(tmp_path)` —
`analyze` never calls `agents/bias_auditor.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `AttributeError: module 'orchestrator' has no attribute 'run_analyze'`

- [ ] **Step 3: Implement in `orchestrator.py`**

Add this import at the top (alongside the existing ones):

```python
from agents.statistician import generar_do
```

Replace the existing `run_design` function (currently inlines the candidate-lookup logic)
with a refactored version that extracts the shared helper. Find this block:

```python
def run_design(candidato_id_buscado: str, plantilla_path: str = "knowledge/plantilla_epe.yaml",
              limitaciones_path: str = "knowledge/limitaciones_epe.yaml") -> AgentResult:
    jsons = sorted(Path("outputs").glob("*/candidatos.json"), key=lambda p: p.stat().st_mtime)
    if not jsons:
        return AgentResult.failure(["No hay candidatos.json; corre 'propose' primero."])
    data = json.loads(jsons[-1].read_text(encoding="utf-8"))
    item = next((it for it in data if it["id"] == candidato_id_buscado), None)
    if item is None:
        return AgentResult.failure([f"Candidato '{candidato_id_buscado}' no encontrado en {jsons[-1]}."])
    candidato = _candidato_desde_json(item)
    plantilla = load_plantilla(plantilla_path)
    limitaciones = load_limitaciones(limitaciones_path)
    llm = _make_llm_client_or_none()
    return disenar_protocolo(candidato, plantilla, limitaciones, llm)
```

Replace it with (add the new `_localizar_candidato` helper right above, keep
`_candidato_desde_json` unchanged since `_localizar_candidato` still calls it):

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


def run_design(candidato_id_buscado: str, plantilla_path: str = "knowledge/plantilla_epe.yaml",
              limitaciones_path: str = "knowledge/limitaciones_epe.yaml") -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado)
    if candidato is None:
        return AgentResult.failure(errores)
    plantilla = load_plantilla(plantilla_path)
    limitaciones = load_limitaciones(limitaciones_path)
    llm = _make_llm_client_or_none()
    return disenar_protocolo(candidato, plantilla, limitaciones, llm)


def run_analyze(candidato_id_buscado: str,
                plantilla_path: str = "knowledge/plantilla_epe.yaml") -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado)
    if candidato is None:
        return AgentResult.failure(errores)
    plantilla = load_plantilla(plantilla_path)
    return AgentResult.success(generar_do(candidato, plantilla))
```

Add `_cmd_analyze` right after `_cmd_design`:

```python
def _cmd_analyze(candidato_id_arg: str) -> int:
    r = run_analyze(candidato_id_arg)
    if not r.ok:
        for w in r.warnings:
            print(f"  aviso: {w}", file=sys.stderr)
        return 1
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path("outputs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "analisis.do").write_text(r.data, encoding="utf-8")
    print(f"Escrito: {out_dir / 'analisis.do'}")
    for w in r.warnings:
        print(f"  aviso: {w}")
    return 0
```

In `main()`, add the new subcommand dispatch (before the final usage-string fallback) and
update the usage string. Replace:

```python
    if len(argv) >= 2 and argv[0] == "design":
        return _cmd_design(argv[1])
    print("uso: python orchestrator.py perfilar | propose | design <id>", file=sys.stderr)
    return 2
```

with:

```python
    if len(argv) >= 2 and argv[0] == "design":
        return _cmd_design(argv[1])
    if len(argv) >= 2 and argv[0] == "analyze":
        return _cmd_analyze(argv[1])
    print("uso: python orchestrator.py perfilar | propose | design <id> | analyze <id>",
          file=sys.stderr)
    return 2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests, including the 4 new ones, AND the existing `test_run_design_*`
tests still pass unchanged — confirms the `_localizar_candidato` refactor preserved
`run_design`'s external behavior)

- [ ] **Step 5: Run the FULL suite**

Run: `python -m pytest -q`
Expected: PASS, all files green (baseline before this task: 129 passed = 124 + 5 from
Task 1; expect ~133 after this task's 4 new tests).

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: comando 'analyze <id>' (analisis.do) + extrae _localizar_candidato compartido"
```

---

## Post-plan manual step (not automatable, not part of the test suite)

After Task 2 is merged, the human (Leonid) should run `python orchestrator.py analyze
<id>` with a real candidate id from a real `candidatos.json`, and review the generated
`analisis.do` with the actual statistician who will run it — in particular confirming the
subpoblación-filter comment is understood as a placeholder requiring manual completion,
not executable syntax.
