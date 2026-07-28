# Fase Design (Protocolo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `design` phase to `epe-generator`: `python orchestrator.py design <candidato_id>`
reads a candidate from `candidatos.json` (produced by `propose`) and generates a research
protocol (PICOT, variables, statistical model selection, LLM-written prose in future tense,
audited limitations) as `protocolo.md` + `protocolo.docx`.

**Architecture:** Mirrors `endes-generator`'s `protocol_designer.py`/`bias_auditor.py` pattern,
adapted to EPE's multivariate `Candidato` shape (`eje` = principal exposure, `covariables_ajuste`
= adjustment set) and to EPE's own outcome-type/scale declarations already in
`plantilla_epe.yaml`, rather than inferring model choice from hardcoded eje-name checks like
ENDES does.

**Tech Stack:** `python-docx` (new dependency, already used by `endes-generator` for the same
purpose). No other new dependencies.

## Global Constraints

- CLI only in this phase — no changes to `streamlit_app.py`.
- Model selection per outcome uses `Plantilla.outcomes` (`tipo`) + a NEW `Plantilla.outcomes_escala`
  (only present for `categorico` outcomes): `categorico`+`ordinal` → regresión logística ordinal;
  `categorico`+`nominal` → regresión logística multinomial; `continuo` → lineal; `binario` →
  logística binaria (no outcome of this type exists today, but the branch must exist and be
  tested for when one is added later).
- The outcome id `ubicacion_procedimiento_sop_vs_consultorio` is RENAMED to
  `ubicacion_procedimiento` in `knowledge/plantilla_epe.yaml` (verified: no test or other
  production file references the old id, so this is a contained rename).
- Prosa generation must degrade to `"[prosa pendiente: LLM no disponible]"` per section without
  crashing when the LLM client is `None` or raises — same "degrade, never crash" principle as
  every other LLM-touching code path in this project.
- No inference of causality: the LLM system prompt for prosa forbids causal language (same
  wording/spirit as the rest of the project), and the bias auditor's causal-language scan
  (`agents/bias_auditor.py`) applies unconditionally (`aplica_siempre: true`) to every protocol.
- PHI safety is unaffected by this plan — `design` operates only on already-PHI-free
  `Candidato`/`Perfil`-derived data (via `candidatos.json`), never touches `agents/perfilador.py`
  or raw Sheet data.

---

## File Structure

```
epe-generator/
  core/
    knowledge.py                 # MODIFIED — Plantilla.outcomes_escala
  knowledge/
    plantilla_epe.yaml            # MODIFIED — rename outcome id, add escala per outcome
    limitaciones_epe.yaml          # NEW — EPE-specific bias/limitation catalog
  agents/
    protocol_designer.py            # NEW — Protocolo, build_picot/variables, inferir_modelo, disenar_protocolo
    bias_auditor.py                  # NEW — Limitacion, load_limitaciones, auditar, causal-language scan
  ui_render.py                       # MODIFIED — render_protocolo_md, render_protocolo_docx
  orchestrator.py                    # MODIFIED — run_design, _cmd_design, "design <id>" CLI command
  requirements.txt                    # MODIFIED — add python-docx
  tests/
    test_knowledge.py                 # MODIFIED — outcomes_escala tests
    test_protocol_designer.py           # NEW
    test_bias_auditor.py                 # NEW
    test_ui_render.py                     # MODIFIED — protocol rendering tests
    test_orchestrator.py                   # MODIFIED — run_design/_cmd_design tests
```

---

### Task 1: `knowledge/plantilla_epe.yaml` rename + `Plantilla.outcomes_escala`

**Files:**
- Modify: `knowledge/plantilla_epe.yaml`
- Modify: `core/knowledge.py`
- Modify: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: nothing new (extends existing `Plantilla`).
- Produces: `Plantilla` gains `outcomes_escala: dict[str, str]` (outcome id → `"ordinal"`\|`"nominal"`,
  only present for `categorico` outcomes that declare it). Used by `agents/protocol_designer.py`
  (Task 2).

- [ ] **Step 1: Rename the outcome id and add `escala` in `knowledge/plantilla_epe.yaml`**

Change the `outcomes:` block from:
```yaml
outcomes:
  - {id: nivel_tratamiento_requerido, tipo: categorico}
  - {id: ubicacion_procedimiento_sop_vs_consultorio, tipo: binario}
  - {id: grado_cooperacion, tipo: categorico}
```
to:
```yaml
outcomes:
  - {id: nivel_tratamiento_requerido, tipo: categorico, escala: ordinal}
  - {id: ubicacion_procedimiento, tipo: categorico, escala: nominal}
  - {id: grado_cooperacion, tipo: categorico, escala: nominal}
```

In the `terminos_busqueda.outcomes:` block, change:
```yaml
    ubicacion_procedimiento_sop_vs_consultorio: "operating room versus outpatient dental treatment"
```
to:
```yaml
    ubicacion_procedimiento: "dental procedure location (outpatient, operating room, or hospitalization)"
```

- [ ] **Step 2: Write the failing test — add to `tests/test_knowledge.py`**

```python
def test_load_plantilla_outcomes_escala():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    assert p.outcomes_escala == {
        "nivel_tratamiento_requerido": "ordinal",
        "ubicacion_procedimiento": "nominal",
        "grado_cooperacion": "nominal",
    }
    assert "ubicacion_procedimiento_sop_vs_consultorio" not in p.outcomes
    assert p.outcomes["ubicacion_procedimiento"] == "categorico"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge.py::test_load_plantilla_outcomes_escala -v`
Expected: FAIL with `AttributeError: 'Plantilla' object has no attribute 'outcomes_escala'`

- [ ] **Step 4: Implement in `core/knowledge.py`**

Add `outcomes_escala` to the `Plantilla` dataclass, right after `outcomes`:

```python
    outcomes_escala: dict[str, str]           # outcome id -> "ordinal"|"nominal" (solo categoricos que lo declaran)
```

In `load_plantilla`, right after the line `outcomes = {o["id"]: o["tipo"] for o in d["outcomes"]}`,
add:

```python
    outcomes_escala = {o["id"]: o["escala"] for o in d["outcomes"] if "escala" in o}
```

And add `outcomes_escala=outcomes_escala,` to the `Plantilla(...)` constructor call at the end
of the function (right after `outcomes=outcomes,`).

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: some failures are OK here — Task 5 (orchestrator) and later tasks still reference
the old outcome id indirectly through real-data-shaped tests that don't exist yet. Confirm
specifically that `tests/test_knowledge.py`, `tests/test_gap_finder.py`,
`tests/test_novelty_checker.py`, and `tests/test_perfilador.py` are unaffected (they don't
reference the renamed outcome id at all, per the pre-implementation grep). If any of those
four files show new failures, stop and investigate before committing.

- [ ] **Step 7: Commit**

```bash
git add knowledge/plantilla_epe.yaml core/knowledge.py tests/test_knowledge.py
git commit -m "feat: Plantilla.outcomes_escala + renombra ubicacion_procedimiento (3 categorias, no binario)"
```

---

### Task 2: `agents/protocol_designer.py`

**Files:**
- Create: `agents/protocol_designer.py`
- Create: `tests/test_protocol_designer.py`

**Interfaces:**
- Consumes: `Candidato(eje, subpoblacion, outcome, covariables_ajuste, n_disponible)` and
  `candidato_id(c)` from `agents/novelty_checker.py`; `Plantilla.outcomes`/`.outcomes_escala`
  (Task 1); `AgentResult` from `core/result.py`; `agents.bias_auditor.auditar` (Task 3, but this
  task's tests pass an empty `limitaciones=[]` list so it does NOT need Task 3 to exist yet —
  `auditar` is called with a plain empty list, and `limitaciones_aplicables([], ...)` style logic
  must tolerate an empty catalog; see Step 4 note).
- Produces: `Protocolo` dataclass (`candidato_id`, `picot`, `variables`, `diseno`, `prosa`,
  `limitaciones`, `warnings_auditoria`); `build_picot(c) -> dict`; `build_variables(c, p) -> list[dict]`;
  `inferir_modelo(tipo: str, escala: str | None) -> tuple[str, list[str]]`; `build_estructura(c, p) -> dict`;
  `disenar_protocolo(candidato, plantilla, limitaciones, llm_client) -> AgentResult`. Used by
  `orchestrator.py` (Task 5) and `ui_render.py` (Task 4, via the `Protocolo` shape).

**Important — this task has a forward dependency on Task 3's module, not its content:** the
brief calls `from agents.bias_auditor import auditar` inside `protocol_designer.py`. Since Task 3
hasn't run yet at this point in the plan, you must ALSO create a minimal placeholder
`agents/bias_auditor.py` in THIS task with just enough to make imports work and tests pass — Task 3
will REPLACE it with the full implementation. Create this minimal version:

```python
def auditar(ctx: dict, prosa_texto: str, limitaciones: list, llm_client=None) -> tuple[list[str], list[str]]:
    """Placeholder minimal — Task 3 reemplaza esta implementación completa."""
    return [], []
```

- [ ] **Step 1: Write the failing tests — create `tests/test_protocol_designer.py`**

```python
import pytest

from agents.protocol_designer import (
    build_estructura,
    build_picot,
    build_variables,
    disenar_protocolo,
    inferir_modelo,
)
from agents.novelty_checker import Candidato, candidato_id
from core.knowledge import load_plantilla
from core.llm_client import FakeLLMClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def _candidato():
    return Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                     outcome="nivel_tratamiento_requerido",
                     covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)


def test_inferir_modelo_categorico_ordinal():
    modelo, anclajes = inferir_modelo("categorico", "ordinal")
    assert modelo == "logistica_ordinal"


def test_inferir_modelo_categorico_nominal():
    modelo, anclajes = inferir_modelo("categorico", "nominal")
    assert modelo == "logistica_multinomial"


def test_inferir_modelo_continuo():
    modelo, anclajes = inferir_modelo("continuo", None)
    assert modelo == "lineal"


def test_inferir_modelo_binario():
    modelo, anclajes = inferir_modelo("binario", None)
    assert modelo == "logistica_binaria"


def test_inferir_modelo_categorico_sin_escala_declarada_lanza_error():
    with pytest.raises(ValueError, match="escala"):
        inferir_modelo("categorico", None)


def test_inferir_modelo_tipo_desconocido_lanza_error():
    with pytest.raises(ValueError, match="tipo"):
        inferir_modelo("inventado", None)


def test_build_picot():
    c = _candidato()
    picot = build_picot(c)
    assert picot["poblacion"] == "asa3_alto_riesgo"
    assert picot["exposicion"] == "riesgo_sistemico_asa"
    assert picot["covariables_ajuste"] == "farmacoterapia_polifarmacia"
    assert picot["outcome"] == "nivel_tratamiento_requerido"
    assert picot["tiempo"] == "transversal (sin seguimiento)"


def test_build_picot_sin_covariables():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                 outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=1350)
    picot = build_picot(c)
    assert picot["covariables_ajuste"] == "(ninguna)"


def test_build_variables():
    c = _candidato()
    p = _plantilla()
    variables = build_variables(c, p)
    assert variables[0] == {"nombre": "nivel_tratamiento_requerido", "rol": "outcome",
                            "tipo": "categorico", "escala": "ordinal"}
    assert {"nombre": "riesgo_sistemico_asa", "rol": "exposicion_principal", "tipo": "categorica"} in variables
    assert {"nombre": "farmacoterapia_polifarmacia", "rol": "covariable", "tipo": "categorica"} in variables
    assert len(variables) == 3


def test_build_estructura_usa_modelo_correcto_para_ordinal():
    c = _candidato()
    p = _plantilla()
    estructura = build_estructura(c, p)
    assert estructura["diseno"]["modelo"] == "logistica_ordinal"
    assert estructura["diseno"]["outcome_tipo"] == "categorico"
    assert estructura["diseno"]["outcome_escala"] == "ordinal"


def test_build_estructura_nominal_para_grado_cooperacion():
    c = Candidato(eje="cooperacion_manejo_conductual", subpoblacion="discapacidad_intelectual",
                 outcome="grado_cooperacion", covariables_ajuste=("discapacidad_tipo_severidad",),
                 n_disponible=131)
    p = _plantilla()
    estructura = build_estructura(c, p)
    assert estructura["diseno"]["modelo"] == "logistica_multinomial"


def test_disenar_protocolo_degrada_sin_llm():
    c = _candidato()
    p = _plantilla()
    r = disenar_protocolo(c, p, [], None)
    assert r.ok
    assert r.data.prosa["introduccion"] == "[prosa pendiente: LLM no disponible]"
    assert any("Prosa no disponible" in w for w in r.warnings)
    assert r.data.candidato_id == candidato_id(c)


def test_disenar_protocolo_con_llm_disponible():
    c = _candidato()
    p = _plantilla()
    llm = FakeLLMClient(responses=["Texto de sección en futuro."])
    r = disenar_protocolo(c, p, [], llm)
    assert r.ok
    assert r.data.prosa["introduccion"] == "Texto de sección en futuro."
    assert r.data.prosa["metodos"] == "Texto de sección en futuro."
    assert r.warnings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_designer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.protocol_designer'`

- [ ] **Step 3: Create the placeholder `agents/bias_auditor.py`**

```python
def auditar(ctx: dict, prosa_texto: str, limitaciones: list, llm_client=None) -> tuple[list[str], list[str]]:
    """Placeholder minimal — Task 3 reemplaza esta implementación completa."""
    return [], []
```

- [ ] **Step 4: Implement `agents/protocol_designer.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from agents.bias_auditor import auditar
from agents.novelty_checker import Candidato, candidato_id
from core.knowledge import Plantilla
from core.result import AgentResult


@dataclass
class Protocolo:
    candidato_id: str
    picot: dict
    variables: list[dict]
    diseno: dict
    prosa: dict = field(default_factory=dict)
    limitaciones: list[str] = field(default_factory=list)
    warnings_auditoria: list[str] = field(default_factory=list)


def inferir_modelo(tipo: str, escala: str | None) -> tuple[str, list[str]]:
    """Selección de modelo según el árbol de decisión (tipo de variable respuesta +
    mecanismo generador de datos, no una regla genérica) — ver
    docs/superpowers/specs/2026-07-28-fase-design-protocolo-design.md §5. anclajes
    citables se dejan vacíos hasta que el usuario aporte referencias reales; no se
    inventan citas."""
    if tipo == "continuo":
        return "lineal", []
    if tipo == "binario":
        return "logistica_binaria", []
    if tipo == "categorico":
        if escala == "ordinal":
            return "logistica_ordinal", []
        if escala == "nominal":
            return "logistica_multinomial", []
        raise ValueError(
            f"outcome categorico requiere 'escala' declarada (ordinal|nominal) en la plantilla"
        )
    raise ValueError(f"tipo de outcome desconocido: {tipo}")


def build_picot(c: Candidato) -> dict:
    return {
        "poblacion": c.subpoblacion,
        "exposicion": c.eje,
        "covariables_ajuste": ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)",
        "comparador": "categorías de referencia de las covariables",
        "outcome": c.outcome,
        "tiempo": "transversal (sin seguimiento)",
    }


def build_variables(c: Candidato, p: Plantilla) -> list[dict]:
    tipo = p.outcomes[c.outcome]
    escala = p.outcomes_escala.get(c.outcome)
    variables = [{"nombre": c.outcome, "rol": "outcome", "tipo": tipo, "escala": escala}]
    variables.append({"nombre": c.eje, "rol": "exposicion_principal", "tipo": "categorica"})
    for cov in c.covariables_ajuste:
        variables.append({"nombre": cov, "rol": "covariable", "tipo": "categorica"})
    return variables


def build_estructura(c: Candidato, p: Plantilla) -> dict:
    tipo = p.outcomes[c.outcome]
    escala = p.outcomes_escala.get(c.outcome)
    modelo, anclajes = inferir_modelo(tipo, escala)
    return {
        "picot": build_picot(c),
        "variables": build_variables(c, p),
        "diseno": {
            "tipo": "transversal_analitico",
            "modelo": modelo,
            "anclajes": anclajes,
            "outcome_tipo": tipo,
            "outcome_escala": escala,
        },
    }


_SECCIONES = ["introduccion", "marco_teorico", "objetivos", "hipotesis", "metodos"]

_SYSTEM_PROTOCOLO = (
    "Eres un metodólogo que redacta un PROTOCOLO de investigación (ex ante) para un "
    "estudio observacional analítico con datos de un registro clínico (EPE, Servicio de "
    "Pacientes Especiales, Depto. de Odontoestomatología). Escribe en español académico, "
    "impersonal y en TIEMPO FUTURO (el estudio 'determinará', 'analizará'). PROHIBIDO el "
    "lenguaje causal: es un estudio de asociación, no de causa-efecto. Responde solo el "
    "texto de la sección."
)

_PENDIENTE = "[prosa pendiente: LLM no disponible]"


def _prompt_seccion(seccion: str, c: Candidato, estructura: dict) -> str:
    ajuste = ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)"
    return (
        f"Sección: {seccion}\nExposición principal: {c.eje}\nSubpoblación: {c.subpoblacion}\n"
        f"Outcome: {c.outcome}\nCovariables de ajuste: {ajuste}\n"
        f"Modelo estadístico: {estructura['diseno']['modelo']}\n"
        f"Redacta la sección '{seccion}' del protocolo (3-5 oraciones), en futuro, sin "
        "lenguaje causal."
    )


def _generar_prosa(c: Candidato, estructura: dict, llm_client) -> tuple[dict, list[str]]:
    try:
        prosa = {}
        for sec in _SECCIONES:
            prosa[sec] = llm_client.call(_SYSTEM_PROTOCOLO, _prompt_seccion(sec, c, estructura)).strip()
        return prosa, []
    except Exception as exc:  # incl. llm_client is None -> AttributeError
        prosa = {sec: _PENDIENTE for sec in _SECCIONES}
        return prosa, [f"Prosa no disponible ({type(exc).__name__}): secciones marcadas como pendientes."]


def disenar_protocolo(candidato: Candidato, plantilla: Plantilla, limitaciones, llm_client) -> AgentResult:
    estructura = build_estructura(candidato, plantilla)
    ctx = {
        "subpoblacion": candidato.subpoblacion,
        "eje": candidato.eje,
        "outcome": candidato.outcome,
        "outcome_tipo": estructura["diseno"]["outcome_tipo"],
        "modelo": estructura["diseno"]["modelo"],
        "covariables": list(candidato.covariables_ajuste),
    }
    prosa, prosa_warnings = _generar_prosa(candidato, estructura, llm_client)
    prosa_texto = "\n".join(prosa.values())
    limit_textos, audit_warnings = auditar(ctx, prosa_texto, limitaciones, llm_client)
    protocolo = Protocolo(
        candidato_id=candidato_id(candidato),
        picot=estructura["picot"],
        variables=estructura["variables"],
        diseno=estructura["diseno"],
        prosa=prosa,
        limitaciones=limit_textos,
        warnings_auditoria=audit_warnings,
    )
    warnings = list(prosa_warnings)
    if warnings:
        return AgentResult.degraded(protocolo, warnings=warnings)
    return AgentResult.success(protocolo)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_designer.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything except possibly nothing — this task only adds new files plus the
placeholder `bias_auditor.py`, and doesn't modify any existing file's behavior. All prior tests
(90 as of the last plan) plus this task's new ones should be green.

- [ ] **Step 7: Commit**

```bash
git add agents/protocol_designer.py agents/bias_auditor.py tests/test_protocol_designer.py
git commit -m "feat: agents/protocol_designer.py (PICOT, variables, modelo, prosa en futuro)"
```

---

### Task 3: `agents/bias_auditor.py` (reemplaza el placeholder) + `knowledge/limitaciones_epe.yaml`

**Files:**
- Create: `knowledge/limitaciones_epe.yaml`
- Modify: `agents/bias_auditor.py` (replace placeholder from Task 2 with full implementation)
- Create: `tests/test_bias_auditor.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Limitacion` frozen dataclass (`id`, `categoria`, `descripcion`, `aplica_siempre`,
  `aplica_si`, `accion_agente`); `load_limitaciones(path: str) -> list[Limitacion]`;
  `condicion_aplica(aplica_si: str, ctx: dict) -> bool`; `limitaciones_aplicables(ctx, limitaciones) -> list[Limitacion]`;
  `escanear_causal(texto: str) -> list[str]`; `auditar(ctx: dict, prosa_texto: str, limitaciones: list[Limitacion], llm_client=None) -> tuple[list[str], list[str]]`
  (SAME signature as the Task 2 placeholder — this task only replaces the body, no caller changes
  needed in `agents/protocol_designer.py`). Used by `orchestrator.py` (Task 5, loads the catalog).

- [ ] **Step 1: Write `knowledge/limitaciones_epe.yaml`**

```yaml
# limitaciones_epe.yaml
# Checklist ejecutable de sesgos/limitaciones metodológicas conocidas para la cohorte EPE
# (registro clínico del Servicio de Pacientes Especiales, no una encuesta poblacional). El
# agente Bias Auditor recorre esta lista y marca cuáles aplican al protocolo generado.

- id: ausencia_causalidad
  categoria: diseno_del_estudio
  descripcion: >
    Al ser un estudio observacional transversal, solo permite identificar
    asociaciones estadísticas en un momento dado, no relaciones causa-efecto.
  aplica_siempre: true
  accion_agente: rechazar_lenguaje_causal_en_redaccion

- id: cohorte_hospital_unico
  categoria: representatividad
  descripcion: >
    La cohorte proviene de un único hospital (Hospital Nacional PNP "Luis N.
    Sáenz"), no de una muestra probabilística poblacional; los resultados no
    son generalizables a otras poblaciones o servicios sin verificación externa.
  aplica_siempre: true

- id: dependencia_registro_clinico
  categoria: dependencia_datos_secundarios
  descripcion: >
    Los datos provienen de un registro clínico administrativo (Sigesapol/EPE),
    no recolectados con fines de investigación; el investigador no controla la
    captura original ni puede corregir errores de registro retrospectivamente.
  aplica_siempre: true

- id: variables_limitadas_al_registro
  categoria: dependencia_datos_secundarios
  descripcion: >
    El registro clínico no incluye todas las variables potencialmente
    relevantes según la literatura; algunos ejes declarados en la plantilla
    metodológica (p. ej. morbilidad por sistema CIE-11, estado nutricional)
    no cuentan aún con columna de datos disponible.
  aplica_siempre: true

- id: calidad_de_registro
  categoria: sesgo_medicion
  descripcion: >
    Algunas variables del registro presentan valores inconsistentes o
    incompletos (p. ej. errores de fórmula heredados en variables numéricas,
    categorías de grupo etario no mapeadas), lo que puede introducir sesgo de
    clasificación si no se depuran antes del análisis.
  aplica_siempre: true

- id: covariables_no_exhaustivas
  categoria: confusion_residual
  descripcion: >
    El ajuste multivariado incluye solo las covariables disponibles y
    compatibles con la subpoblación en la plantilla metodológica; puede
    existir confusión residual por variables no medidas en el registro.
  aplica_si: modelo_tiene_covariables_de_ajuste
  accion_agente: advertir_confusion_residual_si_pocas_covariables
```

- [ ] **Step 2: Write the failing tests — create `tests/test_bias_auditor.py`**

```python
from agents.bias_auditor import auditar, escanear_causal, limitaciones_aplicables, load_limitaciones


def _limitaciones():
    return load_limitaciones("knowledge/limitaciones_epe.yaml")


def _ctx(covariables):
    return {
        "subpoblacion": "adultos",
        "eje": "riesgo_sistemico_asa",
        "outcome": "grado_cooperacion",
        "outcome_tipo": "categorico",
        "modelo": "logistica_multinomial",
        "covariables": covariables,
    }


def test_load_limitaciones_epe():
    lims = _limitaciones()
    ids = {l.id for l in lims}
    assert "ausencia_causalidad" in ids
    assert "cohorte_hospital_unico" in ids
    assert "dependencia_registro_clinico" in ids
    assert "variables_limitadas_al_registro" in ids
    assert "calidad_de_registro" in ids
    assert "covariables_no_exhaustivas" in ids


def test_limitaciones_aplica_siempre_causalidad_y_representatividad():
    lims = _limitaciones()
    aplicables = limitaciones_aplicables(_ctx([]), lims)
    ids = {l.id for l in aplicables}
    assert "ausencia_causalidad" in ids
    assert "cohorte_hospital_unico" in ids
    # covariables_no_exhaustivas NO debe aplicar sin covariables (aplica_si lo condiciona)
    assert "covariables_no_exhaustivas" not in ids


def test_limitaciones_covariables_no_exhaustivas_aplica_con_covariables():
    lims = _limitaciones()
    aplicables = limitaciones_aplicables(_ctx(["farmacoterapia_polifarmacia"]), lims)
    ids = {l.id for l in aplicables}
    assert "covariables_no_exhaustivas" in ids


def test_escanear_causal_detecta_lenguaje_causal():
    texto = "El riesgo sistémico causa un aumento en el nivel de tratamiento requerido."
    assert "causa" in escanear_causal(texto)


def test_escanear_causal_ignora_negaciones():
    texto = "No fue posible establecer causa alguna entre las variables."
    assert escanear_causal(texto) == []


def test_auditar_marca_lenguaje_causal_sin_llm():
    lims = _limitaciones()
    textos, warnings = auditar(
        _ctx([]), "El riesgo sistémico causa el nivel de tratamiento.", lims, llm_client=None
    )
    assert any("Lenguaje causal" in w for w in warnings)


def test_auditar_confusion_residual_pocas_covariables():
    lims = _limitaciones()
    textos, warnings = auditar(
        _ctx(["farmacoterapia_polifarmacia"]), "Texto sin lenguaje causal.", lims, llm_client=None
    )
    assert any("confusión residual" in w for w in warnings)


def test_auditar_sin_confusion_residual_con_varias_covariables():
    lims = _limitaciones()
    textos, warnings = auditar(
        _ctx(["farmacoterapia_polifarmacia", "procedencia_acceso"]),
        "Texto sin lenguaje causal.", lims, llm_client=None,
    )
    assert not any("confusión residual" in w for w in warnings)


def test_auditar_devuelve_textos_de_todas_las_limitaciones_aplicables():
    lims = _limitaciones()
    textos, warnings = auditar(_ctx([]), "Texto sin lenguaje causal.", lims, llm_client=None)
    assert len(textos) >= 5  # las 5 aplica_siempre: true del catálogo
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_bias_auditor.py -v`
Expected: FAIL — the placeholder `auditar` from Task 2 returns `([], [])` unconditionally, so
every assertion expecting non-empty `textos`/`warnings` fails, and `load_limitaciones`/
`escanear_causal`/`limitaciones_aplicables` don't exist yet (`ImportError`).

- [ ] **Step 4: Replace `agents/bias_auditor.py` with the full implementation**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Limitacion:
    id: str
    categoria: str
    descripcion: str
    aplica_siempre: bool
    aplica_si: str | None
    accion_agente: str | None


def load_limitaciones(path: str) -> list[Limitacion]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    lims = []
    for d in raw:
        lims.append(Limitacion(
            id=d["id"],
            categoria=d.get("categoria", ""),
            descripcion=d.get("descripcion", "").strip(),
            aplica_siempre=bool(d.get("aplica_siempre", False)),
            aplica_si=d.get("aplica_si"),
            accion_agente=d.get("accion_agente"),
        ))
    return lims


def condicion_aplica(aplica_si: str, ctx: dict) -> bool:
    if aplica_si == "modelo_tiene_covariables_de_ajuste":
        return len(ctx.get("covariables", [])) >= 1
    return False


def limitaciones_aplicables(ctx: dict, limitaciones: list[Limitacion]) -> list[Limitacion]:
    aplicables = []
    for lim in limitaciones:
        if lim.aplica_siempre:
            aplicables.append(lim)
        elif lim.aplica_si is not None and condicion_aplica(lim.aplica_si, ctx):
            aplicables.append(lim)
    return aplicables


_MARCADORES_CAUSALES = [
    "causa", "provoca", "efecto de", "produce", "genera un aumento",
    "debido a", "conlleva a", "da lugar a",
]
_NEGACIONES_CAUSALES = [
    "no fue posible establecer", "no es posible establecer",
    "no se puede establecer", "no permite establecer",
    "sin poder establecer", "no establece",
    "investigar las causas", "explorar las causas", "estudiar las causas",
    "determinar las causas", "identificar las causas", "esclarecer las causas",
]
_SEPARADOR_ORACIONES = re.compile(r"(?<=[.!?])\s+")


_SYSTEM_VERIFICADOR_CAUSAL = (
    "Eres un auditor metodológico. Se te da UNA oración de un protocolo de "
    "investigación transversal (no experimental). Responde ÚNICAMENTE 'SI' si "
    "la oración afirma o implica una relación de causa-efecto entre variables "
    "del estudio, o ÚNICAMENTE 'NO' si es un disclaimer de no-causalidad, una "
    "recomendación de investigación futura, una explicación metodológica sin "
    "afirmar causalidad del hallazgo, u otro uso no-causal. Una sola palabra."
)
_RESPUESTA_NO = re.compile(r"^NO[.!]?$")


def _verificar_causal_llm(oracion: str, llm_client) -> bool:
    try:
        r = llm_client.call(_SYSTEM_VERIFICADOR_CAUSAL, oracion).strip().upper()
    except Exception:
        return True
    if _RESPUESTA_NO.match(r):
        return False
    return True


def _candidatos_causales(texto: str) -> list[tuple[str, str]]:
    candidatos: list[tuple[str, str]] = []
    for oracion in _SEPARADOR_ORACIONES.split(texto):
        low = oracion.lower()
        if any(neg in low for neg in _NEGACIONES_CAUSALES):
            continue
        for m in _MARCADORES_CAUSALES:
            if m in low:
                candidatos.append((oracion, m))
    return candidatos


def escanear_causal(texto: str) -> list[str]:
    encontrados: list[str] = []
    for _, m in _candidatos_causales(texto):
        if m not in encontrados:
            encontrados.append(m)
    return encontrados


def auditar(ctx: dict, prosa_texto: str, limitaciones: list[Limitacion],
            llm_client=None) -> tuple[list[str], list[str]]:
    aplicables = limitaciones_aplicables(ctx, limitaciones)
    textos = [lim.descripcion for lim in aplicables]
    warnings: list[str] = []
    for lim in aplicables:
        a = lim.accion_agente
        if a == "rechazar_lenguaje_causal_en_redaccion":
            candidatos = _candidatos_causales(prosa_texto)
            if llm_client is None:
                marcadores = []
                for _, m in candidatos:
                    if m not in marcadores:
                        marcadores.append(m)
            else:
                veredicto_por_oracion: dict[str, bool] = {}
                for oracion, _ in candidatos:
                    if oracion not in veredicto_por_oracion:
                        veredicto_por_oracion[oracion] = _verificar_causal_llm(oracion, llm_client)
                marcadores = []
                for oracion, m in candidatos:
                    if veredicto_por_oracion[oracion] and m not in marcadores:
                        marcadores.append(m)
            for frase in marcadores:
                warnings.append(f"Lenguaje causal detectado en la prosa: '{frase}'.")
        elif a == "advertir_confusion_residual_si_pocas_covariables":
            if len(ctx.get("covariables", [])) <= 1:
                warnings.append("Pocas covariables de ajuste: posible confusión residual no controlada.")
    return textos, warnings
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_bias_auditor.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — `tests/test_protocol_designer.py`'s tests call `disenar_protocolo(..., [], ...)`
with an EMPTY limitaciones list, so replacing the placeholder `auditar` doesn't change their
behavior (`limitaciones_aplicables(ctx, [])` returns `[]` regardless of implementation). Confirm
this explicitly by re-running `tests/test_protocol_designer.py` too.

- [ ] **Step 7: Commit**

```bash
git add knowledge/limitaciones_epe.yaml agents/bias_auditor.py tests/test_bias_auditor.py
git commit -m "feat: bias_auditor completo + catalogo de limitaciones EPE (registro clinico)"
```

---

### Task 4: `ui_render.py` — `render_protocolo_md` + `render_protocolo_docx`

**Files:**
- Modify: `ui_render.py`
- Modify: `requirements.txt`
- Modify: `tests/test_ui_render.py`

**Interfaces:**
- Consumes: `Protocolo` dataclass (Task 2).
- Produces: `render_protocolo_md(protocolo: Protocolo) -> str`;
  `render_protocolo_docx(protocolo: Protocolo) -> bytes`. Used by `orchestrator.py` (Task 5).

- [ ] **Step 1: Add `python-docx` to `requirements.txt`**

Add this line (anywhere in the file, e.g. after `streamlit>=1.36`):

```
python-docx>=1.1
```

- [ ] **Step 2: Install the new dependency**

Run: `pip install python-docx>=1.1`
Expected: installs successfully (no conflicts with existing pinned versions).

- [ ] **Step 3: Write the failing tests — append to `tests/test_ui_render.py`**

Add these imports at the top of the file (alongside the existing ones):

```python
from agents.protocol_designer import Protocolo
from ui_render import render_protocolo_docx, render_protocolo_md
```

Append:

```python
def _protocolo():
    return Protocolo(
        candidato_id="riesgo_sistemico_asa_asa3_alto_riesgo_nivel_tratamiento_requerido_adj_farmacoterapia_polifarmacia",
        picot={
            "poblacion": "asa3_alto_riesgo", "exposicion": "riesgo_sistemico_asa",
            "covariables_ajuste": "farmacoterapia_polifarmacia",
            "comparador": "categorías de referencia de las covariables",
            "outcome": "nivel_tratamiento_requerido", "tiempo": "transversal (sin seguimiento)",
        },
        variables=[
            {"nombre": "nivel_tratamiento_requerido", "rol": "outcome", "tipo": "categorico", "escala": "ordinal"},
            {"nombre": "riesgo_sistemico_asa", "rol": "exposicion_principal", "tipo": "categorica"},
            {"nombre": "farmacoterapia_polifarmacia", "rol": "covariable", "tipo": "categorica"},
        ],
        diseno={
            "tipo": "transversal_analitico", "modelo": "logistica_ordinal", "anclajes": [],
            "outcome_tipo": "categorico", "outcome_escala": "ordinal",
        },
        prosa={
            "introduccion": "Texto de introducción.", "marco_teorico": "Texto de marco.",
            "objetivos": "Texto de objetivos.", "hipotesis": "Texto de hipótesis.",
            "metodos": "Texto de métodos.",
        },
        limitaciones=["Al ser un estudio observacional transversal, solo permite asociaciones."],
        warnings_auditoria=[],
    )


def test_render_protocolo_md_incluye_secciones_clave():
    md = render_protocolo_md(_protocolo())
    assert "riesgo_sistemico_asa" in md
    assert "logistica_ordinal" in md
    assert "Texto de introducción." in md
    assert "Limitaciones" in md
    assert "Al ser un estudio observacional transversal" in md


def test_render_protocolo_md_sin_anclajes_no_los_menciona():
    md = render_protocolo_md(_protocolo())
    assert "anclajes" not in md.lower()


def test_render_protocolo_docx_produce_bytes_validos():
    data = render_protocolo_docx(_protocolo())
    assert isinstance(data, bytes)
    assert len(data) > 0
    assert data[:2] == b"PK"  # .docx es un archivo zip
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_protocolo_md' from 'ui_render'`

- [ ] **Step 5: Implement in `ui_render.py`**

Add this import at the top of the file (alongside the existing `import json` and
`from agents.novelty_checker import candidato_id`):

```python
import io

from docx import Document
```

Append these two functions and one module-level constant to the end of the file:

```python
_PROTO_SECCIONES = {
    "introduccion": "Introducción", "marco_teorico": "Marco Teórico",
    "objetivos": "Objetivos", "hipotesis": "Hipótesis", "metodos": "Métodos",
}


def render_protocolo_md(protocolo) -> str:
    p = protocolo
    lines = [f"# Protocolo — {p.candidato_id}", "", "## PICOT", ""]
    for k, v in p.picot.items():
        lines.append(f"- **{k}:** {v}")
    lines += ["", "## Variables", "", "| nombre | rol | tipo | escala |", "|---|---|---|---|"]
    for v in p.variables:
        lines.append(f"| {v['nombre']} | {v['rol']} | {v['tipo']} | {v.get('escala') or ''} |")
    lines += ["", "## Diseño", "", f"- **tipo:** {p.diseno['tipo']}", f"- **modelo:** {p.diseno['modelo']}"]
    if p.diseno.get("anclajes"):
        lines.append(f"- **anclajes:** {', '.join(p.diseno['anclajes'])}")
    for sec, titulo in _PROTO_SECCIONES.items():
        lines += ["", f"## {titulo}", "", p.prosa.get(sec, "")]
    lines += ["", "## Limitaciones", ""]
    for lim in p.limitaciones:
        lines.append(f"- {lim}")
    if p.warnings_auditoria:
        lines += ["", "> ⚠️ Auditoría:"] + [f"> - {w}" for w in p.warnings_auditoria]
    return "\n".join(lines)


def render_protocolo_docx(protocolo) -> bytes:
    """Word estructurado del protocolo, desde los mismos datos que render_protocolo_md
    (no re-parsea el .md). Devuelve bytes (en memoria)."""
    p = protocolo
    doc = Document()
    doc.add_heading(f"Protocolo — {p.candidato_id}", level=0)

    doc.add_heading("PICOT", level=1)
    for k, v in p.picot.items():
        doc.add_paragraph(f"{k}: {v}", style="List Bullet")

    doc.add_heading("Variables", level=1)
    tabla = doc.add_table(rows=1, cols=4)
    hdr = tabla.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "nombre", "rol", "tipo", "escala"
    for v in p.variables:
        celdas = tabla.add_row().cells
        celdas[0].text = str(v["nombre"])
        celdas[1].text = str(v["rol"])
        celdas[2].text = str(v["tipo"])
        celdas[3].text = str(v.get("escala") or "")

    doc.add_heading("Diseño", level=1)
    doc.add_paragraph(f"tipo: {p.diseno['tipo']}", style="List Bullet")
    doc.add_paragraph(f"modelo: {p.diseno['modelo']}", style="List Bullet")
    if p.diseno.get("anclajes"):
        doc.add_paragraph(f"anclajes: {', '.join(p.diseno['anclajes'])}", style="List Bullet")

    for sec, titulo in _PROTO_SECCIONES.items():
        doc.add_heading(titulo, level=1)
        doc.add_paragraph(p.prosa.get(sec, ""))

    doc.add_heading("Limitaciones", level=1)
    for lim in p.limitaciones:
        doc.add_paragraph(lim, style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: PASS (all tests)

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything (this task only adds new functions + a new import; existing
`render_candidatos_md`/`render_candidatos_json` are untouched).

- [ ] **Step 8: Commit**

```bash
git add ui_render.py requirements.txt tests/test_ui_render.py
git commit -m "feat: render_protocolo_md/docx (python-docx)"
```

---

### Task 5: `orchestrator.py` — comando `design <id>`

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `disenar_protocolo` (Task 2), `load_limitaciones` (Task 3), `render_protocolo_md`/
  `render_protocolo_docx` (Task 4), `Candidato` (existing), `load_plantilla` (existing).
- Produces: `run_design(candidato_id_buscado: str, plantilla_path: str = "knowledge/plantilla_epe.yaml", limitaciones_path: str = "knowledge/limitaciones_epe.yaml") -> AgentResult`;
  `_cmd_design(candidato_id_arg: str) -> int`; `main`'s CLI dispatch gains the `design <id>`
  subcommand.

- [ ] **Step 1: Write the failing tests — append to `tests/test_orchestrator.py`**

Add this helper near the existing `_copiar_plantilla` helper:

```python
def _copiar_limitaciones(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "knowledge").mkdir(exist_ok=True)
    shutil.copy(repo_root / "knowledge" / "limitaciones_epe.yaml",
                tmp_path / "knowledge" / "limitaciones_epe.yaml")
```

Append these tests:

```python
def test_run_design_encuentra_candidato_y_genera_protocolo(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
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
    r = orchestrator.run_design(candidato_data["id"])
    assert r.ok
    assert r.data.candidato_id == candidato_data["id"]


def test_run_design_candidato_no_encontrado(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
    monkeypatch.chdir(tmp_path)
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([]), encoding="utf-8")
    r = orchestrator.run_design("no_existe")
    assert not r.ok


def test_run_design_sin_candidatos_json_falla(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = orchestrator.run_design("cualquiera")
    assert not r.ok


def test_cmd_design_escribe_md_y_docx(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": ["farmacoterapia_polifarmacia"],
        "n_disponible": 1350, "novedad": 1.0, "score_llm": 8.0,
    }
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([candidato_data]), encoding="utf-8")
    exit_code = orchestrator.main(["design", "abc"])
    assert exit_code == 0
    archivos_md = list((tmp_path / "outputs").glob("*/protocolo.md"))
    archivos_docx = list((tmp_path / "outputs").glob("*/protocolo.docx"))
    assert len(archivos_md) == 1
    assert len(archivos_docx) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `AttributeError: module 'orchestrator' has no attribute 'run_design'`

- [ ] **Step 3: Implement in `orchestrator.py`**

Add these imports at the top (alongside the existing ones):

```python
import json

from agents.bias_auditor import load_limitaciones
from agents.protocol_designer import disenar_protocolo
from agents.novelty_checker import Candidato
from ui_render import render_candidatos_json, render_candidatos_md, render_protocolo_docx, render_protocolo_md
```

Add these functions (e.g. right after `run_propose`, before `_make_llm_client_or_none`):

```python
def _candidato_desde_json(item: dict) -> Candidato:
    return Candidato(
        eje=item["eje"], subpoblacion=item["subpoblacion"], outcome=item["outcome"],
        covariables_ajuste=tuple(item["covariables_ajuste"]), n_disponible=item["n_disponible"],
    )


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

Add `_cmd_design` right after `_cmd_propose`:

```python
def _cmd_design(candidato_id_arg: str) -> int:
    r = run_design(candidato_id_arg)
    if not r.ok:
        for w in r.warnings:
            print(f"  aviso: {w}", file=sys.stderr)
        return 1
    protocolo = r.data
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path("outputs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "protocolo.md").write_text(render_protocolo_md(protocolo), encoding="utf-8")
    (out_dir / "protocolo.docx").write_bytes(render_protocolo_docx(protocolo))
    print(f"Escrito: {out_dir / 'protocolo.md'}")
    print(f"Escrito: {out_dir / 'protocolo.docx'}")
    for w in r.warnings:
        print(f"  aviso: {w}")
    return 0
```

In `main()`, add the new subcommand dispatch (before the final `print("uso: ...")` fallback) and
update the usage string:

```python
    if len(argv) >= 2 and argv[0] == "design":
        return _cmd_design(argv[1])
    print("uso: python orchestrator.py perfilar | propose | design <id>", file=sys.stderr)
    return 2
```

(This replaces the existing two lines `print("uso: python orchestrator.py perfilar | propose", file=sys.stderr)` and `return 2` — the new `design` dispatch goes right before them.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests, including the 4 new ones)

- [ ] **Step 5: Run the FULL suite**

Run: `python -m pytest -q`
Expected: PASS, all files green. Report the total count.

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: comando 'design <id>' (protocolo.md + protocolo.docx)"
```

---

## Post-plan manual step (not automatable, not part of the test suite)

After Task 5 is merged, the human (Leonid) must:
1. Run `python orchestrator.py propose` (or reuse an existing `outputs/*/candidatos.json`) to
   get a real candidate id.
2. Run `python orchestrator.py design <id>` with a real candidate id from that file, and review
   the generated `protocolo.md`/`protocolo.docx` — confirm the model choice (ordinal/multinomial)
   matches the outcome, and that the prose reads correctly in future tense with no causal language.
3. Decide whether to add real citation anchors (`anclajes`) for the ordinal/multinomial logistic
   models — `inferir_modelo` currently returns an empty list for both, since no specific
   methodological references were provided for this plan.
