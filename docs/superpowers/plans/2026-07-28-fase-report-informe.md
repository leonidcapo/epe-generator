# Fase Report (Informe Final) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the final `report` phase to `epe-generator`: `python orchestrator.py report
<candidato_id> <ruta_resultados_xlsx>` ingests the `resultados.xlsx` the statistician
produced by running `analisis.do` (from `analyze`), and generates `articulo.md` — the
complete final report (protocol sections reused + deterministic Results + audited LLM
Discussion/Conclusions/Recommendations/Summary).

**Architecture:** `agents/executor.py` parses `resultados.xlsx` into typed tables (ported
from `endes-generator`, generic enough to work for any of the 4 Stata model commands
`analyze` can emit, since they all share the same `putexcel ... matrix(r(table))`
convention). `agents/writer.py` reuses `disenar_protocolo` (unchanged, from the `design`
phase) to regenerate the ex-ante sections without persisting a new artifact, builds the
deterministic Results section directly from the parsed tables, and generates the 4 ex-post
sections via LLM — each individually checked against `agents/number_guard.py` (new,
reimplemented anti-hallucination number check) and the whole article re-audited by the
existing `agents/bias_auditor.py`.

**Tech Stack:** New dependency `openpyxl` (reading `.xlsx`, already used by
`endes-generator` for the same purpose).

## Global Constraints

- No corpus of previous studies / no numbered citations — EPE has nothing equivalent to
  `endes-generator`'s 13-study `estudios_previos.json`. The Discussion prompt asks for
  general contrast with the literature, no `[n]` citation instruction, no "Referencias"
  section in the output.
- `report` reuses `disenar_protocolo` (already in `agents/protocol_designer.py`, unchanged)
  to regenerate the ex-ante sections (introducción/marco_teorico/objetivos/hipotesis/
  metodos) — no new persisted `protocolo.json` artifact, matching the same
  recompute-don't-persist pattern already used by `analyze`.
- Known, accepted limitation: the reused ex-ante prosa was written in future tense (as a
  protocol); it is NOT converted to past tense for the final report. This mirrors
  `endes-generator`'s own unresolved limitation and is out of scope here (no
  `tense_corrector`-equivalent is built).
- `agents/number_guard.py`'s EPE-specific `ESTRUCTURALES_DEFAULT = frozenset({0.05,
  100.0})` only — no ENDES-specific year ranges or age-limit exemptions (they don't apply
  to EPE and must not be fabricated without a real source).
- `agents/executor.py`'s parser is generic over Stata command — it reads whatever rows/
  columns exist by label (`b`/`ll`/`ul`/`pvalue`), not tied to a specific model type, since
  all 4 commands `analyze` can emit (`ologit`/`mlogit`/`logistic`/`regress`/`mean`) share
  the same `putexcel A1 = matrix(r(table)), names` convention.
- No `.xlsx` sheet is silently accepted with missing required rows — `parsear_resultados`
  fails loud naming exactly what's missing for `descriptivos`/`modelo` (mandatory sheets);
  malformed `bivariado_*` sheets are individually skipped with a warning, never blocking
  the rest.
- Output is `articulo.md` only — no `.docx` for this phase (decided in the spec: the
  formal ex-ante deliverable already has `.docx` via `design`; the final report can add it
  later if requested).
- Out of scope: executing Stata, a multi-phase "expediente" (`estudio.json`), Streamlit
  integration.

---

## File Structure

```
epe-generator/
  agents/
    number_guard.py             # NEW — numeros_legitimos, p_legitimos, estructurales_estudio, verificar_numeros
    executor.py                  # NEW — parsear_resultados(xlsx_path) -> AgentResult
    writer.py                     # NEW — redactar_resultados, redactar_articulo, Articulo
  ui_render.py                    # MODIFIED — render_articulo_md
  orchestrator.py                  # MODIFIED — run_report/_cmd_report, "report <id> <xlsx>" CLI
  requirements.txt                  # MODIFIED — add openpyxl
  README.md                          # MODIFIED — add report command, close out pending-phases line
  tests/
    test_number_guard.py               # NEW
    test_executor.py                    # NEW
    test_writer.py                       # NEW
    test_ui_render.py                     # MODIFIED — render_articulo_md tests
    test_orchestrator.py                   # MODIFIED — run_report/_cmd_report tests
```

---

### Task 1: `agents/number_guard.py`

**Files:**
- Create: `agents/number_guard.py`
- Create: `tests/test_number_guard.py`

**Interfaces:**
- Consumes: nothing new (pure functions over plain `dict`/`str`/`set` types).
- Produces: `ESTRUCTURALES_DEFAULT: frozenset[float]`; `numeros_legitimos(tablas: dict) ->
  set[float]`; `p_legitimos(tablas: dict) -> set[float]`; `estructurales_estudio(candidato:
  Candidato, protocolo_variables: list[dict], tablas: dict) -> set[float]`;
  `verificar_numeros(texto: str, legitimos: set[float], estructurales: set[float] =
  frozenset(), p_leg: set[float] = frozenset()) -> list[str]`. Used by `agents/writer.py`
  (Task 3). `tablas` is the same `dict` shape `agents/executor.py::parsear_resultados`
  (Task 2) produces: `{"descriptivos": list[dict], "modelo": list[dict], "bivariado":
  dict[str, list[dict]]}`, where each `dict` in a list has keys `termino`/`efecto`/
  `ic_inf`/`ic_sup`/`p` (any may be `None`).

- [ ] **Step 1: Write the failing tests — create `tests/test_number_guard.py`**

```python
from agents.novelty_checker import Candidato
from agents.number_guard import (
    ESTRUCTURALES_DEFAULT,
    estructurales_estudio,
    numeros_legitimos,
    p_legitimos,
    verificar_numeros,
)


def _tablas():
    return {
        "descriptivos": [{"termino": "nivel_tratamiento_requerido", "efecto": 2.34,
                          "ic_inf": 2.10, "ic_sup": 2.58, "p": None}],
        "modelo": [
            {"termino": "riesgo_sistemico_asa", "efecto": 1.87, "ic_inf": 1.20,
             "ic_sup": 2.91, "p": 0.003},
            {"termino": "_cons", "efecto": 0.5, "ic_inf": 0.3, "ic_sup": 0.8, "p": 0.01},
        ],
        "bivariado": {"farmacoterapia_polifarmacia": [
            {"termino": "1", "efecto": 3.1, "ic_inf": 2.0, "ic_sup": 4.2, "p": None},
            {"termino": "2", "efecto": 1.5, "ic_inf": 0.9, "ic_sup": 2.1, "p": None},
        ]},
    }


def test_numeros_legitimos_incluye_efecto_e_ic():
    legit = numeros_legitimos(_tablas())
    assert 1.87 in legit
    assert 1.20 in legit
    assert 2.91 in legit


def test_p_legitimos_sin_redondear():
    p_leg = p_legitimos(_tablas())
    assert 0.003 in p_leg
    assert 0.01 in p_leg


def test_estructurales_estudio_cuenta_covariables_y_bivariado():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                 outcome="nivel_tratamiento_requerido",
                 covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)
    variables = [
        {"nombre": "nivel_tratamiento_requerido", "rol": "outcome"},
        {"nombre": "riesgo_sistemico_asa", "rol": "exposicion_principal"},
        {"nombre": "farmacoterapia_polifarmacia", "rol": "covariable"},
    ]
    s = estructurales_estudio(c, variables, _tablas())
    assert 1.0 in s
    assert 2.0 in s


def test_estructurales_estudio_descarta_cero():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos",
                 outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=50)
    s = estructurales_estudio(c, [], {"bivariado": {}})
    assert 0.0 not in s


def test_verificar_numeros_detecta_cifra_no_legitima():
    ilegit = verificar_numeros("El efecto fue de 9.99 con IC amplio.", legitimos={1.87})
    assert "9.99" in ilegit


def test_verificar_numeros_acepta_cifra_legitima():
    ilegit = verificar_numeros("El efecto fue de 1.87.", legitimos={1.87})
    assert ilegit == []


def test_verificar_numeros_acepta_estructural():
    ilegit = verificar_numeros("Se ajustó por 1 covariable.", legitimos=set(), estructurales={1.0})
    assert ilegit == []


def test_verificar_numeros_convencion_005_y_100():
    ilegit = verificar_numeros(
        "El umbral de significancia fue p < 0,05 sobre el 100% de los casos.",
        legitimos=set(), estructurales=ESTRUCTURALES_DEFAULT, p_leg={0.003},
    )
    assert ilegit == []


def test_verificar_numeros_p_valor_umbral_verificable():
    ilegit = verificar_numeros("p < 0,01", legitimos=set(), p_leg={0.003})
    assert ilegit == []


def test_verificar_numeros_p_valor_no_verificable():
    ilegit = verificar_numeros("p < 0,001", legitimos=set(), p_leg={0.5})
    assert "0,001" in ilegit


def test_verificar_numeros_ignora_citas():
    ilegit = verificar_numeros("Según [4], el hallazgo es consistente.", legitimos=set())
    assert ilegit == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_number_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.number_guard'`

- [ ] **Step 3: Implement `agents/number_guard.py`**

```python
from __future__ import annotations

import re

from agents.novelty_checker import Candidato

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
# Citas Vancouver de texto: [4], [1, 6]. Sus digitos son numeros de referencia,
# no cifras de datos -- se excluyen del escaneo por completo (no hay citas en
# EPE hoy, pero el mecanismo se mantiene por si se agregan mas adelante).
_CITA = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
# Contexto p-valor: "p = 0,539", "p< 0,001", "p ≤ 0,05". Los p-valores exigen
# validacion tipada (igualdad a 3 decimales o umbral), no el redondeo a 2
# decimales de la pasada general.
_P_CTX = re.compile(r"\bp\s*(=|<=|<|≤)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
# Convenciones del discurso estadistico (no son datos): 0.05 = umbral de
# significancia convencional, 100 = total porcentual. NO se exentan 0.01/0.001:
# esas formas viajan como "p < 0,001" y las valida la pasada p-tipada. A
# diferencia de endes-generator, NO se incluyen rangos de anios ni limites
# etarios: no aplican a la cohorte EPE y no deben inventarse sin fuente real.
ESTRUCTURALES_DEFAULT = frozenset({0.05, 100.0})


def _iter_terminos(tablas: dict):
    for v in tablas.values():
        if isinstance(v, dict):            # bivariado: predictor -> list[dict]
            for lst in v.values():
                yield from lst
        else:                              # descriptivos/modelo: list[dict]
            yield from v


def numeros_legitimos(tablas: dict) -> set[float]:
    vals: set[float] = set()
    for t in _iter_terminos(tablas):
        for k in ("efecto", "ic_inf", "ic_sup"):
            v = t.get(k)
            if isinstance(v, (int, float)):
                vals.add(round(float(v), 2))
    return vals


def p_legitimos(tablas: dict) -> set[float]:
    """Valores p crudos de las tablas (sin redondear: la comparacion por umbral
    'p < x' necesita el valor exacto)."""
    vals: set[float] = set()
    for t in _iter_terminos(tablas):
        v = t.get("p")
        if isinstance(v, (int, float)):
            vals.add(float(v))
    return vals


def estructurales_estudio(candidato: Candidato, protocolo_variables: list[dict],
                          tablas: dict) -> set[float]:
    """Conteos estructurales verificables del estudio (nº de covariables de
    ajuste, nº de terminos bivariados por predictor), para que el guard no
    marque un conteo real como cifra inventada. Solo hechos derivables del
    propio estudio; no debilita el guard frente a cifras estadisticas
    inventadas."""
    s: set[float] = set()
    n_cov = sum(1 for v in protocolo_variables if v.get("rol") == "covariable")
    s.add(float(n_cov))
    for terminos in (tablas.get("bivariado") or {}).values():
        s.add(float(len(terminos)))
    s.discard(0.0)  # 0 no es un conteo informativo; evita exentar un "0" espurio
    return s


def verificar_numeros(texto: str, legitimos: set[float],
                      estructurales: set[float] = frozenset(),
                      p_leg: set[float] = frozenset()) -> list[str]:
    texto = _CITA.sub("[cita]", texto)
    ilegit: list[str] = []

    def _validar_p(m: re.Match) -> str:
        op, tok = m.group(1), m.group(2)
        x = float(tok.replace(",", "."))
        if op == "=":
            ok = any(round(v, 3) == round(x, 3) for v in p_leg)
        elif op == "<":
            ok = any(v < x for v in p_leg)
        else:  # "≤" | "<="
            ok = any(v <= x for v in p_leg)
        if not ok:
            ilegit.append(tok)
        return "[p]"  # el span sale del texto: la pasada general no lo re-escanea

    texto = _P_CTX.sub(_validar_p, texto)

    for m in _NUM.finditer(texto):
        tok = m.group()
        x = float(tok.replace(",", "."))
        if round(x, 2) in legitimos:
            continue
        if x in estructurales:
            continue
        ilegit.append(tok)
    return ilegit
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_number_guard.py -v`
Expected: PASS (all 10 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything (baseline before this task: 133 passed) — new file only, no
existing behavior touched.

- [ ] **Step 6: Commit**

```bash
git add agents/number_guard.py tests/test_number_guard.py
git commit -m "feat: agents/number_guard.py (anti-invencion numerica para el informe final)"
```

---

### Task 2: `agents/executor.py`

**Files:**
- Create: `agents/executor.py`
- Create: `tests/test_executor.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `AgentResult` from `core/result.py`; `openpyxl` (new dependency).
- Produces: `parsear_resultados(xlsx_path: str) -> AgentResult`, where `.data` (on success)
  is `{"descriptivos": list[dict], "modelo": list[dict], "bivariado": dict[str,
  list[dict]]}` — each `dict` has keys `termino: str`, `efecto: float`, `ic_inf: float`,
  `ic_sup: float`, `p: float | None`. Used by `agents/writer.py` (Task 3).

- [ ] **Step 1: Add `openpyxl` to `requirements.txt`**

Add this line (anywhere in the file, e.g. after `python-docx>=1.1`):

```
openpyxl>=3.1
```

- [ ] **Step 2: Install the new dependency**

Run: `pip install "openpyxl>=3.1"`
Expected: installs successfully.

- [ ] **Step 3: Write the failing tests — create `tests/test_executor.py`**

```python
import openpyxl

from agents.executor import parsear_resultados


def _libro_valido(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "descriptivos"
    ws.append([None, "nivel_tratamiento_requerido"])
    ws.append(["b", 2.34])
    ws.append(["ll", 2.10])
    ws.append(["ul", 2.58])

    ws2 = wb.create_sheet("modelo")
    # Fila de ecuacion repetida (nombre del outcome en ambas columnas) + fila 2
    # con los terminos reales -- simula la salida real de un comando eclass
    # (ologit/mlogit/logistic/regress) via `putexcel ... matrix(r(table))`.
    ws2.append([None, "nivel_tratamiento_requerido", "nivel_tratamiento_requerido"])
    ws2.append([None, "riesgo_sistemico_asa", "_cons"])
    ws2.append(["b", 1.87, 0.5])
    ws2.append(["ll", 1.20, 0.3])
    ws2.append(["ul", 2.91, 0.8])
    ws2.append(["pvalue", 0.003, 0.01])

    ws3 = wb.create_sheet("bivariado_farmacoterapia_polifarmacia")
    ws3.append([None, "1", "2"])
    ws3.append(["b", 3.1, 1.5])
    ws3.append(["ll", 2.0, 0.9])
    ws3.append(["ul", 4.2, 2.1])

    path = tmp_path / "resultados.xlsx"
    wb.save(path)
    return path


def test_parsear_resultados_feliz(tmp_path):
    path = _libro_valido(tmp_path)
    r = parsear_resultados(str(path))
    assert r.ok
    assert r.data["descriptivos"][0]["efecto"] == 2.34
    terminos_modelo = {t["termino"]: t for t in r.data["modelo"]}
    assert terminos_modelo["riesgo_sistemico_asa"]["efecto"] == 1.87
    assert terminos_modelo["riesgo_sistemico_asa"]["p"] == 0.003
    assert r.data["bivariado"]["farmacoterapia_polifarmacia"][0]["efecto"] == 3.1


def test_parsear_resultados_hoja_faltante(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "descriptivos"
    ws.append([None, "x"])
    ws.append(["b", 1.0])
    ws.append(["ll", 0.5])
    ws.append(["ul", 1.5])
    path = tmp_path / "resultados.xlsx"
    wb.save(path)
    r = parsear_resultados(str(path))
    assert not r.ok
    assert "modelo" in r.warnings[0]


def test_parsear_resultados_fila_requerida_faltante(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "descriptivos"
    ws.append([None, "x"])
    ws.append(["b", 1.0])
    ws.append(["ll", 0.5])
    # falta "ul"
    ws2 = wb.create_sheet("modelo")
    ws2.append([None, "x"])
    ws2.append(["b", 1.0])
    ws2.append(["ll", 0.5])
    ws2.append(["ul", 1.5])
    path = tmp_path / "resultados.xlsx"
    wb.save(path)
    r = parsear_resultados(str(path))
    assert not r.ok
    assert "descriptivos" in r.warnings[0]
    assert "'ul'" in r.warnings[0]


def test_parsear_resultados_celda_no_numerica(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "descriptivos"
    ws.append([None, "x"])
    ws.append(["b", "no_numero"])
    ws.append(["ll", 0.5])
    ws.append(["ul", 1.5])
    ws2 = wb.create_sheet("modelo")
    ws2.append([None, "x"])
    ws2.append(["b", 1.0])
    ws2.append(["ll", 0.5])
    ws2.append(["ul", 1.5])
    path = tmp_path / "resultados.xlsx"
    wb.save(path)
    r = parsear_resultados(str(path))
    assert not r.ok
    assert "celda no numérica" in r.warnings[0]


def test_parsear_resultados_bivariado_mal_formado_se_omite(tmp_path):
    path = _libro_valido(tmp_path)
    wb = openpyxl.load_workbook(path)
    ws_malo = wb.create_sheet("bivariado_otro")
    ws_malo.append([None, "1"])
    ws_malo.append(["b", 1.0])
    # falta ll/ul
    wb.save(path)
    r = parsear_resultados(str(path))
    assert r.ok
    assert "otro" not in r.data["bivariado"]
    assert any("bivariado_otro" in w for w in r.warnings)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_executor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.executor'`

- [ ] **Step 5: Implement `agents/executor.py`**

```python
from __future__ import annotations

import re

import openpyxl

from core.result import AgentResult

_HOJAS_OBLIGATORIAS = ["descriptivos", "modelo"]
_PREFIJO_BIVARIADO = "bivariado_"
_FILAS_REQUERIDAS = ["b", "ll", "ul"]

# Termino de interaccion de Stata de `mean ..., over()`: `c.{outcome}@{codigo}[bn].{pred}`.
# Solo interesa el codigo de categoria (el `bn` es la marca de nivel base de Stata).
_TERMINO_STATA = re.compile(r"@(\d+)(?:bn)?\.")


def _limpiar_termino(cn: str) -> str:
    """Convierte el nombre crudo de la matriz de Stata en una etiqueta legible.
    `c.higiene_oral@1bn.area` -> `1`. Los terminos del modelo (nombres de
    variable, `_cons`) no matchean el patron y se devuelven intactos."""
    m = _TERMINO_STATA.search(cn)
    return m.group(1) if m else cn


def _leer_hoja(ws) -> tuple[list[str], dict[str, dict[str, object]]]:
    # `putexcel ... = matrix(r(table)), names` escribe una fila extra de
    # ecuacion (nombre del outcome, repetido en cada columna) para estimadores
    # con ecuacion (ologit/mlogit/logistic/regress) -- pero no para `mean`. Si
    # la fila 1 es un solo valor repetido en mas de una columna, es esa fila
    # de ecuacion -- los terminos reales estan en la fila 2.
    fila1 = [c.value for c in ws[1][1:] if c.value is not None]
    header_row = 1
    col_names = fila1
    if len(fila1) > 1 and len(set(fila1)) == 1:
        fila2 = [c.value for c in ws[2][1:] if c.value is not None]
        if len(fila2) > 1 and len(set(fila2)) > 1:
            col_names = fila2
            header_row = 2
    filas: dict[str, dict[str, object]] = {}
    for row in ws.iter_rows(min_row=header_row + 1):
        label = row[0].value
        if label is None:
            continue
        filas[str(label)] = {cn: row[i + 1].value for i, cn in enumerate(col_names)}
    return col_names, filas


def _tabla_terminos(col_names, filas) -> list[dict]:
    terminos = []
    for cn in col_names:
        termino = _limpiar_termino(cn)
        try:
            item = {
                "termino": termino,
                "efecto": float(filas["b"][cn]),
                "ic_inf": float(filas["ll"][cn]),
                "ic_sup": float(filas["ul"][cn]),
                "p": float(filas["pvalue"][cn]) if "pvalue" in filas else None,
            }
        except (TypeError, ValueError):
            if termino == "_cons":
                continue
            raise
        terminos.append(item)
    return terminos


def parsear_resultados(xlsx_path: str) -> AgentResult:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    faltan = [h for h in _HOJAS_OBLIGATORIAS if h not in wb.sheetnames]
    if faltan:
        return AgentResult.failure([f"resultados.xlsx: falta(n) hoja(s): {faltan}"])
    data: dict[str, list[dict]] = {}
    warnings: list[str] = []
    for hoja in _HOJAS_OBLIGATORIAS:
        col_names, filas = _leer_hoja(wb[hoja])
        for req in _FILAS_REQUERIDAS:
            if req not in filas:
                return AgentResult.failure(
                    [f"resultados.xlsx[{hoja}]: falta la fila requerida '{req}'"])
        try:
            data[hoja] = _tabla_terminos(col_names, filas)
        except (TypeError, ValueError):
            return AgentResult.failure(
                [f"resultados.xlsx[{hoja}]: celda no numérica donde se esperaba un número"])
    bivariado: dict[str, list[dict]] = {}
    for hoja in wb.sheetnames:
        if not hoja.startswith(_PREFIJO_BIVARIADO):
            continue
        pred = hoja[len(_PREFIJO_BIVARIADO):]
        col_names, filas = _leer_hoja(wb[hoja])
        if not all(req in filas for req in _FILAS_REQUERIDAS):
            warnings.append(f"resultados.xlsx[{hoja}]: bivariado mal formado, se omite")
            continue
        try:
            bivariado[pred] = _tabla_terminos(col_names, filas)
        except (TypeError, ValueError):
            warnings.append(f"resultados.xlsx[{hoja}]: celda no numérica en bivariado, se omite")
    data["bivariado"] = bivariado
    return AgentResult.success(data, warnings=warnings)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_executor.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything (baseline before this task: 143 passed = 133 + 10 from
Task 1).

- [ ] **Step 8: Commit**

```bash
git add agents/executor.py tests/test_executor.py requirements.txt
git commit -m "feat: agents/executor.py (parsea resultados.xlsx generico por comando Stata)"
```

---

### Task 3: `agents/writer.py`

**Files:**
- Create: `agents/writer.py`
- Create: `tests/test_writer.py`

**Interfaces:**
- Consumes: `Candidato` from `agents/novelty_checker.py`; `Plantilla` from
  `core/knowledge.py`; `disenar_protocolo(candidato, plantilla, limitaciones, llm_client)
  -> AgentResult` from `agents/protocol_designer.py` (unchanged, returns a `Protocolo` with
  `.candidato_id`, `.variables`, `.diseno` (dict with `outcome_tipo`/`modelo` keys),
  `.prosa` (dict with the 5 ex-ante section keys)); `auditar(ctx, prosa_texto,
  limitaciones, llm_client) -> tuple[list[str], list[str]]` from `agents/bias_auditor.py`
  (unchanged); `numeros_legitimos`/`p_legitimos`/`estructurales_estudio`/
  `verificar_numeros`/`ESTRUCTURALES_DEFAULT` from `agents/number_guard.py` (Task 1);
  `AgentResult` from `core/result.py`.
- Produces: `Articulo` dataclass (`candidato_id: str`, `resultados: str`, `prosa_ante:
  dict`, `prosa_post: dict`, `limitaciones: list[str]`, `warnings: list[str]`);
  `redactar_resultados(tablas: dict) -> str`; `redactar_articulo(candidato: Candidato,
  plantilla: Plantilla, tablas: dict, limitaciones, llm_client) -> AgentResult`. Used by
  `orchestrator.py` (Task 5) and `ui_render.py` (Task 4, via the `Articulo` shape).

- [ ] **Step 1: Write the failing tests — create `tests/test_writer.py`**

```python
from agents.bias_auditor import load_limitaciones
from agents.novelty_checker import Candidato
from agents.writer import redactar_articulo, redactar_resultados
from core.knowledge import load_plantilla
from core.llm_client import FakeLLMClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def _candidato():
    return Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                     outcome="nivel_tratamiento_requerido",
                     covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)


def _tablas():
    return {
        "descriptivos": [{"termino": "nivel_tratamiento_requerido", "efecto": 2.34,
                          "ic_inf": 2.10, "ic_sup": 2.58, "p": None}],
        "modelo": [
            {"termino": "riesgo_sistemico_asa", "efecto": 1.87, "ic_inf": 1.20,
             "ic_sup": 2.91, "p": 0.003},
            {"termino": "_cons", "efecto": 0.5, "ic_inf": 0.3, "ic_sup": 0.8, "p": 0.01},
        ],
        "bivariado": {},
    }


def test_redactar_resultados_excluye_cons():
    texto = redactar_resultados(_tablas())
    assert "riesgo_sistemico_asa" in texto
    assert "1,87" in texto
    assert "_cons" not in texto


def test_redactar_articulo_degrada_sin_llm():
    r = redactar_articulo(_candidato(), _plantilla(), _tablas(), [], None)
    assert r.ok
    assert r.data.prosa_post["discusion"] == "[pendiente: LLM no disponible]"
    assert r.data.prosa_ante["introduccion"] == "[prosa pendiente: LLM no disponible]"


def test_redactar_articulo_con_llm_disponible():
    llm = FakeLLMClient(responses=["Texto redactado en pasado."])
    r = redactar_articulo(_candidato(), _plantilla(), _tablas(), [], llm)
    assert r.ok
    assert r.data.prosa_post["discusion"] == "Texto redactado en pasado."


def test_redactar_articulo_marca_cifra_inventada():
    llm = FakeLLMClient(responses=["El efecto fue de 9.99 con IC muy amplio."])
    r = redactar_articulo(_candidato(), _plantilla(), _tablas(), [], llm)
    assert r.data.prosa_post["discusion"] == "[sección pendiente: cifra no verificable]"
    assert any("cifras no verificables" in w for w in r.warnings)


def test_redactar_articulo_detecta_lenguaje_causal():
    lims = load_limitaciones("knowledge/limitaciones_epe.yaml")
    llm = FakeLLMClient(responses=["El riesgo sistemico causo el nivel de tratamiento."])
    r = redactar_articulo(_candidato(), _plantilla(), _tablas(), lims, llm)
    assert any("Lenguaje causal" in w for w in r.warnings)


def test_redactar_articulo_candidato_id_coincide_con_protocolo():
    from agents.novelty_checker import candidato_id
    c = _candidato()
    llm = FakeLLMClient(responses=["Texto en pasado."])
    r = redactar_articulo(c, _plantilla(), _tablas(), [], llm)
    assert r.data.candidato_id == candidato_id(c)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.writer'`

- [ ] **Step 3: Implement `agents/writer.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from agents.bias_auditor import auditar
from agents.novelty_checker import Candidato
from agents.number_guard import (
    ESTRUCTURALES_DEFAULT,
    estructurales_estudio,
    numeros_legitimos,
    p_legitimos,
    verificar_numeros,
)
from agents.protocol_designer import disenar_protocolo
from core.knowledge import Plantilla
from core.result import AgentResult


def _num(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def redactar_resultados(tablas: dict) -> str:
    lineas = ["## Resultados", ""]
    for t in tablas.get("modelo", []):
        if t["termino"] == "_cons":
            continue
        p_txt = f"; p = {_num(t['p'], 3)}" if t.get("p") is not None else ""
        lineas.append(
            f"- {t['termino']}: efecto = {_num(t['efecto'])} "
            f"(IC95%: {_num(t['ic_inf'])}–{_num(t['ic_sup'])}{p_txt})."
        )
    bivariado = tablas.get("bivariado") or {}
    if bivariado:
        lineas += ["", "### Análisis bivariado", ""]
        for pred, terminos in bivariado.items():
            for t in terminos:
                lineas.append(
                    f"- {pred} = {t['termino']}: valor = {_num(t['efecto'])} "
                    f"(IC95%: {_num(t['ic_inf'])}–{_num(t['ic_sup'])})."
                )
    return "\n".join(lineas)


_SECCIONES_POST = ["discusion", "conclusiones", "recomendaciones", "resumen"]
_PENDIENTE_LLM = "[pendiente: LLM no disponible]"
_PENDIENTE_CIFRA = "[sección pendiente: cifra no verificable]"

_SYSTEM_WRITER = (
    "Eres un investigador que redacta el INFORME FINAL (ex post) de un estudio "
    "observacional transversal con datos de un registro clínico (EPE, Servicio de "
    "Pacientes Especiales, Depto. de Odontoestomatología). Escribe en español académico, "
    "impersonal y en TIEMPO PASADO. PROHIBIDO el lenguaje causal (asociación, no causa) y "
    "PROHIBIDO citar cifras que no estén en los resultados provistos."
)


@dataclass
class Articulo:
    candidato_id: str
    resultados: str
    prosa_ante: dict = field(default_factory=dict)
    prosa_post: dict = field(default_factory=dict)
    limitaciones: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _prompt_seccion(seccion: str, candidato: Candidato, resultados: str) -> str:
    return (
        f"Sección: {seccion}\nEje (exposición principal): {candidato.eje}\n"
        f"Subpoblación: {candidato.subpoblacion}\nOutcome: {candidato.outcome}\n"
        f"Resultados (única fuente de cifras):\n{resultados}\n\n"
        f"Redacta '{seccion}' en pasado, sin lenguaje causal, sin cifras nuevas."
    )


def redactar_articulo(candidato: Candidato, plantilla: Plantilla, tablas: dict,
                      limitaciones, llm_client) -> AgentResult:
    protocolo_result = disenar_protocolo(candidato, plantilla, limitaciones, llm_client)
    protocolo = protocolo_result.data
    resultados = redactar_resultados(tablas)

    legitimos = numeros_legitimos(tablas)
    p_leg = p_legitimos(tablas)
    estructurales = ESTRUCTURALES_DEFAULT | estructurales_estudio(
        candidato, protocolo.variables, tablas)

    prosa_post: dict = {}
    warnings: list = list(protocolo_result.warnings)
    for sec in _SECCIONES_POST:
        if llm_client is None:
            prosa_post[sec] = _PENDIENTE_LLM
            continue
        try:
            texto = llm_client.call(
                _SYSTEM_WRITER, _prompt_seccion(sec, candidato, resultados)).strip()
        except Exception as exc:  # LLM caído -> degradar esta y las demas
            for s in _SECCIONES_POST:
                prosa_post.setdefault(s, _PENDIENTE_LLM)
            warnings.append(f"Prosa LLM no disponible ({type(exc).__name__}).")
            break
        ilegit = verificar_numeros(texto, legitimos, estructurales, p_leg=p_leg)
        if ilegit:
            prosa_post[sec] = _PENDIENTE_CIFRA
            warnings.append(f"Sección '{sec}': cifras no verificables {ilegit}.")
        else:
            prosa_post[sec] = texto
    if llm_client is None:
        warnings.append("LLM no disponible: secciones de prosa pendientes.")

    ctx = {
        "subpoblacion": candidato.subpoblacion,
        "eje": candidato.eje,
        "outcome": candidato.outcome,
        "outcome_tipo": protocolo.diseno["outcome_tipo"],
        "modelo": protocolo.diseno["modelo"],
        "covariables": list(candidato.covariables_ajuste),
    }
    texto_completo = "\n".join(
        v for v in list(protocolo.prosa.values()) + list(prosa_post.values())
        if not v.startswith("[")
    )
    limit_textos, audit_warnings = auditar(ctx, texto_completo, limitaciones, llm_client)
    warnings += audit_warnings

    art = Articulo(candidato_id=protocolo.candidato_id, resultados=resultados,
                   prosa_ante=protocolo.prosa, prosa_post=prosa_post,
                   limitaciones=limit_textos, warnings=warnings)
    if any(v.startswith("[") for v in prosa_post.values()):
        return AgentResult.degraded(art, warnings=warnings)
    return AgentResult.success(art, warnings=warnings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_writer.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything (baseline before this task: 148 passed = 143 + 5 from
Task 2).

- [ ] **Step 6: Commit**

```bash
git add agents/writer.py tests/test_writer.py
git commit -m "feat: agents/writer.py (resultados deterministas + prosa ex post auditada)"
```

---

### Task 4: `ui_render.py` — `render_articulo_md`

**Files:**
- Modify: `ui_render.py`
- Modify: `tests/test_ui_render.py`

**Interfaces:**
- Consumes: `Articulo` dataclass (Task 3).
- Produces: `render_articulo_md(articulo: Articulo) -> str`. Used by `orchestrator.py`
  (Task 5).

- [ ] **Step 1: Write the failing tests — append to `tests/test_ui_render.py`**

Add this import at the top of the file (alongside the existing ones):

```python
from agents.writer import Articulo
```

Append:

```python
def _articulo():
    return Articulo(
        candidato_id="riesgo_sistemico_asa_asa3_alto_riesgo_nivel_tratamiento_requerido_adj_farmacoterapia_polifarmacia",
        resultados="## Resultados\n\n- riesgo_sistemico_asa: efecto = 1,87 (IC95%: 1,20–2,91; p = 0,003).",
        prosa_ante={
            "introduccion": "Texto de introducción.", "marco_teorico": "Texto de marco.",
            "objetivos": "Texto de objetivos.", "hipotesis": "Texto de hipótesis.",
            "metodos": "Texto de métodos.",
        },
        prosa_post={
            "discusion": "Texto de discusión.", "conclusiones": "Texto de conclusiones.",
            "recomendaciones": "Texto de recomendaciones.", "resumen": "Texto de resumen.",
        },
        limitaciones=["Limitación 1."],
        warnings=["Aviso de prueba."],
    )


def test_render_articulo_md_incluye_secciones_ex_ante_y_ex_post():
    md = render_articulo_md(_articulo())
    assert "Texto de introducción." in md
    assert "Texto de discusión." in md
    assert "riesgo_sistemico_asa: efecto = 1,87" in md
    assert "Limitación 1." in md
    assert "Aviso de prueba." in md


def test_render_articulo_md_sin_seccion_referencias():
    md = render_articulo_md(_articulo())
    assert "Referencias" not in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_articulo_md' from 'ui_render'`

- [ ] **Step 3: Implement in `ui_render.py`**

Append this constant and function to the end of the file:

```python
_ARTICULO_SECCIONES_POST = {
    "discusion": "Discusión", "conclusiones": "Conclusiones",
    "recomendaciones": "Recomendaciones", "resumen": "Resumen",
}


def render_articulo_md(articulo) -> str:
    a = articulo
    lines = [f"# Informe final — {a.candidato_id}", ""]
    for sec, titulo in _PROTO_SECCIONES.items():
        lines += [f"## {titulo}", "", a.prosa_ante.get(sec, ""), ""]
    lines += [a.resultados, ""]
    for sec, titulo in _ARTICULO_SECCIONES_POST.items():
        lines += [f"## {titulo}", "", a.prosa_post.get(sec, ""), ""]
    if a.limitaciones:
        lines += ["## Limitaciones", ""] + [f"- {t}" for t in a.limitaciones] + [""]
    if a.warnings:
        lines += ["## Avisos de auditoría", ""] + [f"> ⚠️ {w}" for w in a.warnings]
    return "\n".join(lines)
```

Note: this reuses the module-level `_PROTO_SECCIONES` dict already defined earlier in
`ui_render.py` for `render_protocolo_md` — do not redefine it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS on everything (baseline before this task: 149 passed = 148 + 1 from
Task 3 — Task 3 added 6 tests, recount: 133+10+5+6=154; this task adds 2 more, expect 156).

- [ ] **Step 6: Commit**

```bash
git add ui_render.py tests/test_ui_render.py
git commit -m "feat: render_articulo_md (informe completo: ex ante + resultados + ex post)"
```

---

### Task 5: `orchestrator.py` — comando `report <id> <resultados.xlsx>` + README

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `parsear_resultados` (Task 2); `redactar_articulo` (Task 3);
  `render_articulo_md` (Task 4); existing `_localizar_candidato`, `load_plantilla`,
  `load_limitaciones`, `AgentResult`, `_make_llm_client_or_none`.
- Produces: `run_report(candidato_id_buscado: str, resultados_xlsx_path: str,
  plantilla_path: str = "knowledge/plantilla_epe.yaml", limitaciones_path: str =
  "knowledge/limitaciones_epe.yaml") -> AgentResult`; `_cmd_report(candidato_id_arg: str,
  resultados_xlsx_arg: str) -> int`; `main`'s CLI dispatch gains the `report <id> <xlsx>`
  subcommand.

- [ ] **Step 1: Write the failing tests — append to `tests/test_orchestrator.py`**

Add this import at the top of the file (alongside the existing `import json` etc.):

```python
import openpyxl
```

Add this helper near `_copiar_plantilla`/`_copiar_limitaciones`:

```python
def _resultados_xlsx_valido(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "descriptivos"
    ws.append([None, "nivel_tratamiento_requerido"])
    ws.append(["b", 2.34])
    ws.append(["ll", 2.10])
    ws.append(["ul", 2.58])
    ws2 = wb.create_sheet("modelo")
    ws2.append([None, "riesgo_sistemico_asa"])
    ws2.append(["b", 1.87])
    ws2.append(["ll", 1.20])
    ws2.append(["ul", 2.91])
    path = tmp_path / "resultados.xlsx"
    wb.save(path)
    return str(path)
```

Append these tests:

```python
def test_run_report_encuentra_candidato_y_genera_articulo(tmp_path, monkeypatch):
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
    xlsx_path = _resultados_xlsx_valido(tmp_path)
    r = orchestrator.run_report(candidato_data["id"], xlsx_path)
    assert r.ok
    assert "riesgo_sistemico_asa" in r.data.resultados


def test_run_report_candidato_no_encontrado(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
    monkeypatch.chdir(tmp_path)
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([]), encoding="utf-8")
    xlsx_path = _resultados_xlsx_valido(tmp_path)
    r = orchestrator.run_report("no_existe", xlsx_path)
    assert not r.ok


def test_run_report_xlsx_invalido_falla(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    _copiar_limitaciones(tmp_path)
    monkeypatch.chdir(tmp_path)
    candidato_data = {
        "id": "abc", "eje": "riesgo_sistemico_asa", "subpoblacion": "asa3_alto_riesgo",
        "outcome": "nivel_tratamiento_requerido", "covariables_ajuste": [],
        "n_disponible": 100, "novedad": 1.0, "score_llm": 8.0,
    }
    out_dir = tmp_path / "outputs" / "20260728-000000"
    out_dir.mkdir(parents=True)
    (out_dir / "candidatos.json").write_text(json.dumps([candidato_data]), encoding="utf-8")
    wb = openpyxl.Workbook()
    wb.active.title = "descriptivos"
    xlsx_path = tmp_path / "resultados_incompleto.xlsx"
    wb.save(xlsx_path)
    r = orchestrator.run_report("abc", str(xlsx_path))
    assert not r.ok


def test_cmd_report_escribe_articulo(tmp_path, monkeypatch):
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
    xlsx_path = _resultados_xlsx_valido(tmp_path)
    exit_code = orchestrator.main(["report", "abc", xlsx_path])
    assert exit_code == 0
    archivos = list((tmp_path / "outputs").glob("*/articulo.md"))
    assert len(archivos) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `AttributeError: module 'orchestrator' has no attribute 'run_report'`

- [ ] **Step 3: Implement in `orchestrator.py`**

Add these imports at the top (alongside the existing ones):

```python
from agents.executor import parsear_resultados
from agents.writer import redactar_articulo
```

Add `render_articulo_md` to the existing `from ui_render import ...` line, so it reads:

```python
from ui_render import (render_articulo_md, render_candidatos_json, render_candidatos_md,
                       render_protocolo_docx, render_protocolo_md)
```

Add `run_report` right after `run_analyze`:

```python
def run_report(candidato_id_buscado: str, resultados_xlsx_path: str,
               plantilla_path: str = "knowledge/plantilla_epe.yaml",
               limitaciones_path: str = "knowledge/limitaciones_epe.yaml") -> AgentResult:
    candidato, errores = _localizar_candidato(candidato_id_buscado)
    if candidato is None:
        return AgentResult.failure(errores)
    resultado_parse = parsear_resultados(resultados_xlsx_path)
    if not resultado_parse.ok:
        return resultado_parse
    plantilla = load_plantilla(plantilla_path)
    limitaciones = load_limitaciones(limitaciones_path)
    llm = _make_llm_client_or_none()
    articulo_result = redactar_articulo(candidato, plantilla, resultado_parse.data,
                                        limitaciones, llm)
    return AgentResult(
        ok=articulo_result.ok,
        data=articulo_result.data,
        warnings=[*resultado_parse.warnings, *articulo_result.warnings],
    )
```

Add `_cmd_report` right after `_cmd_analyze`:

```python
def _cmd_report(candidato_id_arg: str, resultados_xlsx_arg: str) -> int:
    r = run_report(candidato_id_arg, resultados_xlsx_arg)
    if not r.ok:
        for w in r.warnings:
            print(f"  aviso: {w}", file=sys.stderr)
        return 1
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path("outputs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "articulo.md").write_text(render_articulo_md(r.data), encoding="utf-8")
    print(f"Escrito: {out_dir / 'articulo.md'}")
    for w in r.warnings:
        print(f"  aviso: {w}")
    return 0
```

In `main()`, add the new subcommand dispatch (before the final usage-string fallback) and
update the usage string. Replace:

```python
    if len(argv) >= 2 and argv[0] == "analyze":
        return _cmd_analyze(argv[1])
    print("uso: python orchestrator.py perfilar | propose | design <id> | analyze <id>",
          file=sys.stderr)
    return 2
```

with:

```python
    if len(argv) >= 2 and argv[0] == "analyze":
        return _cmd_analyze(argv[1])
    if len(argv) >= 3 and argv[0] == "report":
        return _cmd_report(argv[1], argv[2])
    print("uso: python orchestrator.py perfilar | propose | design <id> | analyze <id> | "
          "report <id> <resultados.xlsx>", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Update `README.md`**

Read the current `README.md`. Add `python orchestrator.py report <candidato_id>
<ruta_resultados_xlsx>` to the command list, right after the `analyze` line, in the same
style as the existing entries (mirror the `analyze` line's comment style: report reads
`resultados.xlsx` — produced by the statistician running `analisis.do` — and writes
`outputs/<run_id>/articulo.md`, the complete final report). Update the pending-phases line
so no phase remains listed as pending (the 4-phase cycle `propose → design → analyze →
report` is now complete).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests, including the 4 new ones, AND all pre-existing
`test_run_design_*`/`test_run_analyze_*` tests still pass unchanged)

- [ ] **Step 6: Run the FULL suite**

Run: `python -m pytest -q`
Expected: PASS, all files green. Report the total count.

- [ ] **Step 7: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py README.md
git commit -m "feat: comando 'report <id> <xlsx>' (articulo.md) + cierra README del ciclo 4 fases"
```
