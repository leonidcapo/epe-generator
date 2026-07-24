# EPE Seed Generator — Fase `propose` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `perfilar` → `propose` pipeline of the EPE Seed Generator: read the EPE
Google Sheet via a service-account credential, produce a **PHI-free aggregated profile**,
and generate ranked research-idea seeds (candidatos) from it, mirroring the architecture and
principles of `endes-generator`'s Gap Finder.

**Architecture:** Standalone Python app (own git repo, `epe-generator/`), CLI orchestrator
(`orchestrator.py`) with two commands (`perfilar`, `propose`) over a `core/` (result contract,
YAML knowledge loading, LLM client, Google Sheets client, PubMed client) + `agents/`
(perfilador, novelty_checker, gap_finder) + `ui_render.py` split, same shape as
`endes-generator`. Every external dependency (Sheets, LLM, PubMed) is injected behind a small
interface with a `Fake*` test double, so the full test suite runs with **no network, no
credentials, no PHI**.

**Tech Stack:** Python 3.12, `gspread` + `google-auth` (Sheets), `pyyaml`, `requests` (DeepSeek
+ PubMed E-utilities), `streamlit` (thin UI, out of scope for this plan — see Task 9 note),
`pytest`.

## Global Constraints

- **No PHI ever leaves `perfilador.py`.** Any column not explicitly on the allow-list is
  dropped before any aggregation happens. A blocklist test asserts DNI/name/phone/DOB never
  appear in `perfil_epe.yaml` or in any in-memory aggregate.
- **No inference of causality.** Every candidate seed is framed as an observational
  association/prevalence question. `causal_permitido: false` in `plantilla_epe.yaml` is
  enforced structurally (candidate text templates never use causal language) — see Task 8.
- **Degrade, never crash.** Missing LLM key → rank by novelty only. Missing PubMed access →
  neutral novelty (0.5) + warning. Missing/failed Sheets read → reuse last cached
  `perfil_epe.yaml` if present, else fail `perfilar` with a clear error (there is nothing to
  degrade to on the very first run).
- **This project never modifies `nucleo/` or `endes-generator/`.** All work happens inside the
  new `epe-generator/` repo (already git-initialized, first commit = design spec).
- **Suite runs offline.** `python -m pytest -q` must pass with zero network access and zero
  real credentials, using fixtures/fakes only.
- **`n_min` factibilidad** default = 30 (rule-of-thumb minimum cell size for both statistical
  usefulness and re-identification suppression), configurable via `plantilla_epe.yaml`.

---

## File Structure

```
epe-generator/
  core/
    result.py            # AgentResult (success/degraded/failure) — ported from endes-generator
    knowledge.py          # Plantilla, Perfil dataclasses + YAML load/save + VocabularioError
    sheets_client.py      # SheetReader protocol, FakeSheetReader, GspreadSheetReader
    pubmed_client.py      # PubMedClient protocol, FakePubMedClient, real E-utilities client
    llm_client.py         # FakeLLMClient, DeepSeekClient, make_client — ported from endes-generator
  agents/
    perfilador.py         # perfilar(reader, config) -> AgentResult(perfil dict), PHI blocklist
    novelty_checker.py     # Candidato dataclass, score_novedad(candidato, pubmed_client)
    gap_finder.py          # generar_espacio, filtrar_factibilidad, filtrar_novedad, rankear, seleccionar_estratificado
  knowledge/
    plantilla_epe.yaml     # ADN metodológico EPE (ejes, subpoblaciones, outcomes, compatibilidad)
  ui_render.py             # render_candidatos_md, render_candidatos_json
  orchestrator.py          # run_perfilar, run_propose, CLI dispatch (main)
  tests/
    fixtures/
      sheet_rows_sinteticas.py
    test_result.py
    test_knowledge.py
    test_sheets_client.py
    test_perfilador.py
    test_llm_client.py
    test_pubmed_client.py
    test_novelty_checker.py
    test_gap_finder.py
    test_ui_render.py
    test_orchestrator.py
  requirements.txt
  .env.example
  .gitignore
  README.md
```

---

### Task 1: Scaffold + `core/result.py`

**Files:**
- Create: `core/__init__.py` (empty)
- Create: `core/result.py`
- Create: `agents/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_result.py`
- Create: `.gitignore`
- Create: `requirements.txt`

**Interfaces:**
- Produces: `AgentResult` (dataclass) with fields `ok: bool`, `data: Any`, `warnings: list[str]`
  and classmethods `success(data, warnings=None)`, `degraded(data, warnings)`,
  `failure(warnings, data=None)`. Used by every agent function in this plan.

- [ ] **Step 1: Create directories and empty `__init__.py` files**

```bash
mkdir -p core agents tests/fixtures knowledge
touch core/__init__.py agents/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.env
knowledge/perfil_epe.yaml
outputs/
credentials/
*.json.key
.pytest_cache/
```

- [ ] **Step 3: Write `requirements.txt`**

```
pyyaml>=6.0
gspread>=6.1
google-auth>=2.29
requests>=2.31
python-dotenv>=1.0
streamlit>=1.36
pytest>=8.0
```

- [ ] **Step 4: Write the failing test `tests/test_result.py`**

```python
from core.result import AgentResult


def test_success_defaults_no_warnings():
    r = AgentResult.success({"x": 1})
    assert r.ok is True
    assert r.data == {"x": 1}
    assert r.warnings == []


def test_degraded_carries_warnings_but_ok_true():
    r = AgentResult.degraded({"x": 1}, warnings=["llm no disponible"])
    assert r.ok is True
    assert r.warnings == ["llm no disponible"]


def test_failure_ok_false():
    r = AgentResult.failure(["no se pudo leer el sheet"])
    assert r.ok is False
    assert r.data is None
    assert r.warnings == ["no se pudo leer el sheet"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_result.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.result'`

- [ ] **Step 3: Write `core/result.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Uniform return contract for every agent in this repo.

    ok       : the deterministic core always succeeds; ok=False is reserved
               for unrecoverable input errors (e.g. no Sheets access and no cache).
    data     : primary in-memory result.
    warnings : non-fatal notes (e.g. LLM degraded, PubMed unavailable).
    """

    ok: bool
    data: Any = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls, data: Any, warnings: list[str] | None = None) -> "AgentResult":
        return cls(ok=True, data=data, warnings=list(warnings or []))

    @classmethod
    def degraded(cls, data: Any, warnings: list[str]) -> "AgentResult":
        return cls(ok=True, data=data, warnings=list(warnings))

    @classmethod
    def failure(cls, warnings: list[str], data: Any = None) -> "AgentResult":
        return cls(ok=False, data=data, warnings=list(warnings))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_result.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add core/ agents/__init__.py tests/ .gitignore requirements.txt
git commit -m "feat: scaffold repo + AgentResult contract"
```

---

### Task 2: `core/knowledge.py` — `Plantilla` + `knowledge/plantilla_epe.yaml`

**Files:**
- Create: `knowledge/plantilla_epe.yaml`
- Create: `core/knowledge.py`
- Create: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `VocabularioError(ValueError)`; `Plantilla` dataclass with fields `ejes:
  dict[str,str]`, `subpoblaciones: dict[str,str]`, `outcomes: dict[str,str]`,
  `compatibilidad: dict[str, frozenset[str]]` (eje -> subpoblaciones válidas),
  `causal_permitido: bool`, `n_min: int`; function `load_plantilla(path: str) -> Plantilla`.
  Used by `agents/gap_finder.py` (Task 8) and `agents/novelty_checker.py` (Task 7).

- [ ] **Step 1: Write `knowledge/plantilla_epe.yaml`**

```yaml
# plantilla_epe.yaml
# ADN metodológico de la cohorte EPE (Servicio de Pacientes Especiales,
# Depto. de Odontoestomatología, Hospital Nacional PNP "Luis N. Sáenz").
# Define el espacio combinatorio que agents/gap_finder.py explora para proponer
# semillas de ideas de investigación primaria (observacional, sin inferencia causal).

diseno:
  tipo: observacional_analitico_registro_clinico
  inferencia_causal_permitida: false
  n_min: 30   # tamaño mínimo de celda: factibilidad estadística + supresión anti-reidentificación

ejes:
  - {id: riesgo_sistemico_asa, estado: candidato}
  - {id: discapacidad_tipo_severidad, estado: candidato}
  - {id: morbilidad_cie11_sistemas, estado: candidato}
  - {id: farmacoterapia_polifarmacia, estado: candidato}
  - {id: cooperacion_manejo_conductual, estado: candidato}
  - {id: procedencia_acceso, estado: candidato}
  - {id: estado_nutricional_imc, estado: candidato}

subpoblaciones:
  - {id: ninos_preescolares_escolares, estado: candidato}
  - {id: adolescentes, estado: candidato}
  - {id: adultos, estado: candidato}
  - {id: adultos_mayores, estado: candidato}
  - {id: discapacidad_intelectual, estado: candidato}
  - {id: discapacidad_fisica, estado: candidato}
  - {id: discapacidad_sensorial, estado: candidato}
  - {id: asa3_alto_riesgo, estado: candidato}

outcomes:
  - {id: nivel_tratamiento_requerido, tipo: categorico}
  - {id: ubicacion_procedimiento_sop_vs_consultorio, tipo: binario}
  - {id: grado_cooperacion, tipo: categorico}

# Qué subpoblaciones tienen sentido clínico para cada eje. gap_finder.py descarta
# cualquier tupla eje×subpoblación que no aparezca aquí.
compatibilidad_eje_subpoblacion:
  - {eje: riesgo_sistemico_asa, subpoblaciones_validas: [adultos, adultos_mayores, asa3_alto_riesgo]}
  - {eje: discapacidad_tipo_severidad, subpoblaciones_validas: [discapacidad_intelectual, discapacidad_fisica, discapacidad_sensorial]}
  - {eje: morbilidad_cie11_sistemas, subpoblaciones_validas: [adultos, adultos_mayores, asa3_alto_riesgo]}
  - {eje: farmacoterapia_polifarmacia, subpoblaciones_validas: [adultos_mayores, asa3_alto_riesgo]}
  - {eje: cooperacion_manejo_conductual, subpoblaciones_validas: [ninos_preescolares_escolares, discapacidad_intelectual]}
  - {eje: procedencia_acceso, subpoblaciones_validas: [ninos_preescolares_escolares, adolescentes, adultos, adultos_mayores]}
  - {eje: estado_nutricional_imc, subpoblaciones_validas: [adultos, adultos_mayores]}
```

- [ ] **Step 2: Write the failing test `tests/test_knowledge.py`**

```python
import pytest

from core.knowledge import load_plantilla, VocabularioError


def _escribir(tmp_path, contenido):
    path = tmp_path / "plantilla.yaml"
    path.write_text(contenido, encoding="utf-8")
    return str(path)


def test_load_plantilla_real_epe():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    assert p.causal_permitido is False
    assert p.n_min == 30
    assert "riesgo_sistemico_asa" in p.ejes
    assert "adultos" in p.subpoblaciones
    assert "nivel_tratamiento_requerido" in p.outcomes
    assert p.compatibilidad["riesgo_sistemico_asa"] == frozenset(
        {"adultos", "adultos_mayores", "asa3_alto_riesgo"}
    )


def test_load_plantilla_compatibilidad_referencia_eje_desconocido(tmp_path):
    contenido = """
diseno:
  inferencia_causal_permitida: false
  n_min: 30
ejes:
  - {id: eje_a, estado: candidato}
subpoblaciones:
  - {id: pob_a, estado: candidato}
outcomes:
  - {id: out_a, tipo: binario}
compatibilidad_eje_subpoblacion:
  - {eje: eje_fantasma, subpoblaciones_validas: [pob_a]}
"""
    with pytest.raises(VocabularioError, match="eje_fantasma"):
        load_plantilla(_escribir(tmp_path, contenido))


def test_load_plantilla_compatibilidad_referencia_subpoblacion_desconocida(tmp_path):
    contenido = """
diseno:
  inferencia_causal_permitida: false
  n_min: 30
ejes:
  - {id: eje_a, estado: candidato}
subpoblaciones:
  - {id: pob_a, estado: candidato}
outcomes:
  - {id: out_a, tipo: binario}
compatibilidad_eje_subpoblacion:
  - {eje: eje_a, subpoblaciones_validas: [pob_fantasma]}
"""
    with pytest.raises(VocabularioError, match="pob_fantasma"):
        load_plantilla(_escribir(tmp_path, contenido))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.knowledge'`

- [ ] **Step 4: Write `core/knowledge.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

import yaml


class VocabularioError(ValueError):
    """Raised when plantilla_epe.yaml references an id that isn't declared."""


@dataclass
class Plantilla:
    ejes: dict[str, str]                      # id -> estado
    subpoblaciones: dict[str, str]            # id -> estado
    outcomes: dict[str, str]                  # id -> tipo
    compatibilidad: dict[str, frozenset[str]]  # eje -> subpoblaciones validas
    causal_permitido: bool
    n_min: int


def load_plantilla(path: str) -> Plantilla:
    with open(path, encoding="utf-8") as fh:
        d = yaml.safe_load(fh)

    ejes = {e["id"]: e["estado"] for e in d["ejes"]}
    subpoblaciones = {p["id"]: p["estado"] for p in d["subpoblaciones"]}
    outcomes = {o["id"]: o["tipo"] for o in d["outcomes"]}

    compat = {}
    for c in d.get("compatibilidad_eje_subpoblacion", []):
        if c["eje"] not in ejes:
            raise VocabularioError(f"compatibilidad_eje_subpoblacion referencia eje desconocido: {c['eje']}")
        desconocidas = sorted(set(c["subpoblaciones_validas"]) - set(subpoblaciones))
        if desconocidas:
            raise VocabularioError(
                f"compatibilidad_eje_subpoblacion[{c['eje']}] referencia subpoblaciones "
                f"desconocidas: {desconocidas}"
            )
        compat[c["eje"]] = frozenset(c["subpoblaciones_validas"])

    return Plantilla(
        ejes=ejes,
        subpoblaciones=subpoblaciones,
        outcomes=outcomes,
        compatibilidad=compat,
        causal_permitido=bool(d["diseno"]["inferencia_causal_permitida"]),
        n_min=int(d["diseno"]["n_min"]),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add core/knowledge.py knowledge/plantilla_epe.yaml tests/test_knowledge.py
git commit -m "feat: Plantilla loader + plantilla_epe.yaml (espacio combinatorio EPE)"
```

---

### Task 3: `core/knowledge.py` — `Perfil` (perfil agregado) + load/save

**Files:**
- Modify: `core/knowledge.py`
- Modify: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Perfil` dataclass with fields `n_por_celda: dict[tuple[str, str], int]` (keyed by
  `(subpoblacion, eje)`), `distribuciones: dict[str, dict[str, int]]` (variable ->
  {categoria: conteo}), `generado_en: str` (ISO date); functions `guardar_perfil(perfil:
  Perfil, path: str) -> None` and `load_perfil(path: str) -> Perfil`. Used by
  `agents/perfilador.py` (Task 5, produces it) and `agents/gap_finder.py` (Task 8, consumes
  `n_por_celda` for factibilidad).

- [ ] **Step 1: Add failing tests to `tests/test_knowledge.py`**

```python
from core.knowledge import Perfil, guardar_perfil, load_perfil


def test_perfil_roundtrip(tmp_path):
    perfil = Perfil(
        n_por_celda={("adultos", "riesgo_sistemico_asa"): 120, ("adultos_mayores", "riesgo_sistemico_asa"): 45},
        distribuciones={"sexo": {"F": 900, "M": 834}},
        generado_en="2026-07-24",
    )
    path = str(tmp_path / "perfil_epe.yaml")
    guardar_perfil(perfil, path)
    cargado = load_perfil(path)
    assert cargado == perfil


def test_perfil_n_por_celda_ausente_devuelve_cero():
    perfil = Perfil(n_por_celda={("adultos", "riesgo_sistemico_asa"): 10},
                    distribuciones={}, generado_en="2026-07-24")
    assert perfil.n(("adolescentes", "riesgo_sistemico_asa")) == 0
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: FAIL with `ImportError: cannot import name 'Perfil'`

- [ ] **Step 3: Add `Perfil` + `guardar_perfil` + `load_perfil` to `core/knowledge.py`**

```python
@dataclass
class Perfil:
    n_por_celda: dict[tuple[str, str], int]   # (subpoblacion, eje) -> n
    distribuciones: dict[str, dict[str, int]]  # variable -> {categoria: conteo}
    generado_en: str

    def n(self, celda: tuple[str, str]) -> int:
        return self.n_por_celda.get(celda, 0)


def guardar_perfil(perfil: Perfil, path: str) -> None:
    serializable = {
        "n_por_celda": [
            {"subpoblacion": sp, "eje": eje, "n": n}
            for (sp, eje), n in perfil.n_por_celda.items()
        ],
        "distribuciones": perfil.distribuciones,
        "generado_en": perfil.generado_en,
    }
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(serializable, fh, allow_unicode=True, sort_keys=False)


def load_perfil(path: str) -> Perfil:
    with open(path, encoding="utf-8") as fh:
        d = yaml.safe_load(fh)
    n_por_celda = {
        (row["subpoblacion"], row["eje"]): row["n"] for row in d["n_por_celda"]
    }
    return Perfil(
        n_por_celda=n_por_celda,
        distribuciones=d["distribuciones"],
        generado_en=d["generado_en"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add core/knowledge.py tests/test_knowledge.py
git commit -m "feat: Perfil (perfil agregado EPE) con roundtrip YAML"
```

---

### Task 4: `core/sheets_client.py` — lector de Google Sheets inyectable

**Files:**
- Create: `core/sheets_client.py`
- Create: `tests/test_sheets_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SheetReader` protocol with method `leer_filas() -> list[dict[str, Any]]`;
  `FakeSheetReader(filas: list[dict])` test double; `GspreadSheetReader(credentials_path: str,
  sheet_id: str, worksheet_name: str)` real implementation (network, not unit-tested). Used by
  `agents/perfilador.py` (Task 5).

- [ ] **Step 1: Write the failing test `tests/test_sheets_client.py`**

```python
from core.sheets_client import FakeSheetReader


def test_fake_sheet_reader_devuelve_filas_inyectadas():
    filas = [{"sexo": "F", "edad": "48"}, {"sexo": "M", "edad": "61"}]
    reader = FakeSheetReader(filas)
    assert reader.leer_filas() == filas


def test_fake_sheet_reader_puede_simular_fallo():
    reader = FakeSheetReader([], fail=True)
    try:
        reader.leer_filas()
        assert False, "debía lanzar"
    except ConnectionError as exc:
        assert "simulado" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sheets_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.sheets_client'`

- [ ] **Step 3: Write `core/sheets_client.py`**

```python
from __future__ import annotations

from typing import Any, Protocol


class SheetReader(Protocol):
    def leer_filas(self) -> list[dict[str, Any]]: ...


class FakeSheetReader:
    """Deterministic stub. No network. Set fail=True to simulate a connection error."""

    def __init__(self, filas: list[dict[str, Any]], fail: bool = False):
        self._filas = filas
        self._fail = fail

    def leer_filas(self) -> list[dict[str, Any]]:
        if self._fail:
            raise ConnectionError("fallo simulado de conexión a Google Sheets")
        return list(self._filas)


class GspreadSheetReader:
    """Lee una pestaña de un Google Sheet vía cuenta de servicio (gspread).

    Requiere GOOGLE_SERVICE_ACCOUNT_JSON (ruta al JSON de credenciales) en el entorno,
    y que esa cuenta de servicio tenga acceso de lectura al Sheet (compartido explícitamente
    por el dueño). No se testea con red real — ver README para el setup manual.
    """

    def __init__(self, credentials_path: str, sheet_id: str, worksheet_name: str):
        self._credentials_path = credentials_path
        self._sheet_id = sheet_id
        self._worksheet_name = worksheet_name

    def leer_filas(self) -> list[dict[str, Any]]:
        import gspread  # imported lazily so tests never need the package installed to run

        gc = gspread.service_account(filename=self._credentials_path)
        sh = gc.open_by_key(self._sheet_id)
        ws = sh.worksheet(self._worksheet_name)
        return ws.get_all_records()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sheets_client.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add core/sheets_client.py tests/test_sheets_client.py
git commit -m "feat: SheetReader inyectable (Fake + Gspread real)"
```

---

### Task 5: `agents/perfilador.py` — perfil agregado sin PHI

**Files:**
- Create: `agents/perfilador.py`
- Create: `tests/fixtures/sheet_rows_sinteticas.py`
- Create: `tests/test_perfilador.py`

**Interfaces:**
- Consumes: `SheetReader` (Task 4), `Perfil` (Task 3), `Plantilla.ejes`/`.subpoblaciones` ids
  (Task 2, only the id strings — perfilador does not import `Plantilla` itself, it just needs
  to produce cells keyed by matching ids).
- Produces: `PHI_COLUMNS_EXCLUIDAS: frozenset[str]` (module-level constant); function
  `perfilar(reader: SheetReader) -> AgentResult` returning `AgentResult.success(Perfil)` /
  `AgentResult.failure([...])` on connection error. Used by `orchestrator.py` (Task 9).

- [ ] **Step 1: Write synthetic fixture `tests/fixtures/sheet_rows_sinteticas.py`**

```python
"""Filas sintéticas con la MISMA forma de columnas que la pestaña 'Datos' real del
Sheet EPE (ver memoria project-hospital-pnp-odonto), incluyendo columnas PHI a
propósito para que test_perfilador.py verifique que perfilador.py las descarta."""

FILAS_SINTETICAS = [
    {
        "Insertar N° de DNI": "09900807", "Apellidos y Nombres": "REÁTEGUI RUÍZ, JANET",
        "N° de HC": "00478220", "Celular": "999999999", "Fecha de Nacimiento": "1975-01-01",
        "sexo": "F", "edad": "48", "Grupo etareo": "Adulto", "Riesgo sistémico": "ASA2",
        "Tipo de discapacidad": "Intelectual", "Severidad de la discapacidad": "Moderado",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Normal",
    },
    {
        "Insertar N° de DNI": "06771050", "Apellidos y Nombres": "ORREGO CALLE, FERNANDO",
        "N° de HC": "00255163", "Celular": "988888888", "Fecha de Nacimiento": "1962-05-05",
        "sexo": "M", "edad": "61", "Grupo etareo": "Adulto mayor", "Riesgo sistémico": "ASA3",
        "Tipo de discapacidad": "Sensorial", "Severidad de la discapacidad": "Leve",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Sobrepeso",
    },
    {
        "Insertar N° de DNI": "06254207", "Apellidos y Nombres": "ANGELES PÉREZ, FAUSTA",
        "N° de HC": "00059849", "Celular": "977777777", "Fecha de Nacimiento": "1953-02-02",
        "sexo": "F", "edad": "71", "Grupo etareo": "Adulto mayor", "Riesgo sistémico": "ASA3",
        "Tipo de discapacidad": "No aplica", "Severidad de la discapacidad": "No aplica",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Normal",
    },
]
```

- [ ] **Step 2: Write the failing test `tests/test_perfilador.py`**

```python
from agents.perfilador import perfilar, PHI_COLUMNS_EXCLUIDAS
from core.sheets_client import FakeSheetReader
from tests.fixtures.sheet_rows_sinteticas import FILAS_SINTETICAS


def test_perfilar_excluye_columnas_phi():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = perfilar(reader)
    assert r.ok
    perfil = r.data
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda)
    for col in PHI_COLUMNS_EXCLUIDAS:
        assert col not in texto_completo
    # ningún valor de DNI/nombre/celular sobrevive en ninguna distribución
    assert "09900807" not in texto_completo
    assert "REÁTEGUI" not in texto_completo


def test_perfilar_agrega_distribucion_por_variable():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    assert perfil.distribuciones["sexo"] == {"F": 2, "M": 1}
    assert perfil.distribuciones["Riesgo sistémico"] == {"ASA2": 1, "ASA3": 2}


def test_perfilar_calcula_n_por_celda_subpoblacion_eje():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    # 2 filas son "Adulto mayor" -> n de la celda (adultos_mayores, riesgo_sistemico_asa) = 2
    assert perfil.n(("adultos_mayores", "riesgo_sistemico_asa")) == 2
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 1


def test_perfilar_conexion_fallida_produce_failure():
    reader = FakeSheetReader([], fail=True)
    r = perfilar(reader)
    assert not r.ok
    assert "simulado" in r.warnings[0]


def test_perfilar_sheet_vacio_produce_perfil_vacio_sin_crashear():
    reader = FakeSheetReader([])
    r = perfilar(reader)
    assert r.ok
    assert r.data.n_por_celda == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_perfilador.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.perfilador'`

- [ ] **Step 4: Write `agents/perfilador.py`**

```python
from __future__ import annotations

from collections import Counter
from datetime import date

from core.knowledge import Perfil
from core.result import AgentResult
from core.sheets_client import SheetReader

# Bloqueadas de forma explícita y permanente: ningún cambio aguas abajo debe poder
# hacer que estas columnas (o sus valores) lleguen a perfil_epe.yaml.
PHI_COLUMNS_EXCLUIDAS = frozenset({
    "Insertar N° de DNI", "Apellidos y Nombres", "N° de HC", "Celular",
    "Fecha de Nacimiento", "Cuidador",
})

# Variable de agregación -> id de subpoblación cuando el valor corresponde a esa categoría.
_MAPA_GRUPO_ETAREO_A_SUBPOBLACION = {
    "Adulto": "adultos",
    "Adulto mayor": "adultos_mayores",
}

_VARIABLES_AGREGABLES = (
    "sexo", "Grupo etareo", "Riesgo sistémico", "Tipo de discapacidad",
    "Severidad de la discapacidad", "Grado de cooperación",
    "Ubicación del procedimiento", "Categorías IMC",
)


def _fila_sin_phi(fila: dict) -> dict:
    return {k: v for k, v in fila.items() if k not in PHI_COLUMNS_EXCLUIDAS}


def _n_por_celda(filas_limpias: list[dict]) -> dict[tuple[str, str], int]:
    conteo: Counter[tuple[str, str]] = Counter()
    for fila in filas_limpias:
        subpoblacion = _MAPA_GRUPO_ETAREO_A_SUBPOBLACION.get(fila.get("Grupo etareo"))
        if subpoblacion is None:
            continue
        if fila.get("Riesgo sistémico"):
            conteo[(subpoblacion, "riesgo_sistemico_asa")] += 1
    return dict(conteo)


def perfilar(reader: SheetReader) -> AgentResult:
    try:
        filas = reader.leer_filas()
    except ConnectionError as exc:
        return AgentResult.failure([str(exc)])

    filas_limpias = [_fila_sin_phi(f) for f in filas]

    distribuciones: dict[str, dict[str, int]] = {}
    for var in _VARIABLES_AGREGABLES:
        conteo = Counter(f[var] for f in filas_limpias if f.get(var))
        if conteo:
            distribuciones[var] = dict(conteo)

    perfil = Perfil(
        n_por_celda=_n_por_celda(filas_limpias),
        distribuciones=distribuciones,
        generado_en=date.today().isoformat(),
    )
    return AgentResult.success(perfil)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_perfilador.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add agents/perfilador.py tests/fixtures/ tests/test_perfilador.py
git commit -m "feat: perfilador agrega EPE sin PHI (n por celda + distribuciones)"
```

---

### Task 6: `core/llm_client.py` — cliente LLM inyectable (degrada sin API key)

**Files:**
- Create: `core/llm_client.py`
- Create: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `FakeLLMClient(responses=None, default="{}", fail=False)` with `.call(system, user)
  -> str`; `DeepSeekClient(api_key, model="deepseek-chat", ...)` real client; `make_client(env:
  dict)` factory reading `LLM_PROVIDER`/`DEEPSEEK_API_KEY`, raising `ValueError` if
  misconfigured. Used by `agents/gap_finder.py` (Task 8) and `orchestrator.py` (Task 9).

- [ ] **Step 1: Write the failing test `tests/test_llm_client.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.llm_client'`

- [ ] **Step 3: Write `core/llm_client.py`**

```python
from __future__ import annotations

import threading

import requests as _requests


class FakeLLMClient:
    """Deterministic stub. No network. Set fail=True to simulate an API error."""

    def __init__(self, responses: list[str] | None = None, default: str = "{}", fail: bool = False):
        self._responses = list(responses or [])
        self._default = default
        self._fail = fail
        self._idx = 0
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def call(self, system: str, user: str) -> str:
        with self._lock:
            self.calls.append((system, user))
            if self._fail:
                raise RuntimeError("LLM simulated failure")
            if not self._responses:
                return self._default
            resp = self._responses[self._idx % len(self._responses)]
            self._idx += 1
            return resp


class DeepSeekClient:
    """Cliente para la API de DeepSeek (Chat Completions, compatible con OpenAI)."""

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com", max_tokens: int = 2048,
                 temperature: float = 0.4):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._max_tokens = max_tokens
        self._temperature = temperature

    def call(self, system: str, user: str) -> str:
        resp = _requests.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": self._model,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def make_client(env: dict):
    provider = env.get("LLM_PROVIDER", "deepseek").lower()
    if provider == "deepseek":
        api_key = env.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("Falta DEEPSEEK_API_KEY en el entorno (.env)")
        return DeepSeekClient(api_key=api_key)
    raise ValueError(f"LLM_PROVIDER no soportado: {provider} (usa deepseek)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add core/llm_client.py tests/test_llm_client.py
git commit -m "feat: LLM client inyectable (Fake + DeepSeek real, degrada sin API key)"
```

---

### Task 7: `core/pubmed_client.py` — cliente PubMed inyectable

**Files:**
- Create: `core/pubmed_client.py`
- Create: `tests/test_pubmed_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `FakePubMedClient(conteos: dict[str, int], fail=False)` with `.contar(query: str)
  -> int`; `PubMedClient(api_key: str | None)` real client using NCBI E-utilities
  (`esearch.fcgi`, returns `count` from the JSON response); `make_pubmed_client(env: dict)`
  factory (never raises — PubMed key is optional per NCBI, degrades to unauthenticated rate
  limit). Used by `agents/novelty_checker.py` (Task 8).

- [ ] **Step 1: Write the failing test `tests/test_pubmed_client.py`**

```python
import pytest

from core.pubmed_client import FakePubMedClient, make_pubmed_client, PubMedClient


def test_fake_pubmed_client_devuelve_conteo_por_query():
    client = FakePubMedClient({"asa dental risk": 12})
    assert client.contar("asa dental risk") == 12


def test_fake_pubmed_client_query_no_registrada_devuelve_cero():
    client = FakePubMedClient({})
    assert client.contar("query desconocida") == 0


def test_fake_pubmed_client_simula_fallo():
    client = FakePubMedClient({}, fail=True)
    with pytest.raises(ConnectionError):
        client.contar("cualquier query")


def test_make_pubmed_client_sin_api_key_no_lanza():
    client = make_pubmed_client({})
    assert isinstance(client, PubMedClient)
    assert client._api_key is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pubmed_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.pubmed_client'`

- [ ] **Step 3: Write `core/pubmed_client.py`**

```python
from __future__ import annotations

import requests as _requests

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


class FakePubMedClient:
    """Deterministic stub. No network. Set fail=True to simulate an API error."""

    def __init__(self, conteos: dict[str, int], fail: bool = False):
        self._conteos = dict(conteos)
        self._fail = fail

    def contar(self, query: str) -> int:
        if self._fail:
            raise ConnectionError("fallo simulado de conexión a PubMed")
        return self._conteos.get(query, 0)


class PubMedClient:
    """Cliente para NCBI E-utilities (esearch). api_key es opcional (NCBI da un límite
    de tasa menor sin ella, pero funciona)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def contar(self, query: str) -> int:
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 0}
        if self._api_key:
            params["api_key"] = self._api_key
        resp = _requests.get(_ESEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        return int(resp.json()["esearchresult"]["count"])


def make_pubmed_client(env: dict) -> PubMedClient:
    return PubMedClient(api_key=env.get("PUBMED_API_KEY"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pubmed_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add core/pubmed_client.py tests/test_pubmed_client.py
git commit -m "feat: PubMed client inyectable (Fake + E-utilities real)"
```

---

### Task 8: `agents/novelty_checker.py` + `agents/gap_finder.py`

**Files:**
- Create: `agents/novelty_checker.py`
- Create: `tests/test_novelty_checker.py`
- Create: `agents/gap_finder.py`
- Create: `tests/test_gap_finder.py`

**Interfaces:**
- Consumes: `Plantilla`, `Perfil` (Task 2/3), `PubMedClient` protocol (Task 7, `FakePubMedClient`
  for tests), `FakeLLMClient`/`make_client` (Task 6).
- Produces: `Candidato` (frozen dataclass: `eje: str`, `subpoblacion: str`, `outcome: str`,
  `n_disponible: int`); `candidato_id(c: Candidato) -> str`; `score_novedad(candidato:
  Candidato, pubmed_client) -> tuple[float, list[str]]` (score 0=saturado..1=vacío, warnings);
  `generar_espacio(plantilla: Plantilla, perfil: Perfil) -> list[Candidato]`;
  `filtrar_factibilidad(candidatos, plantilla) -> list[Candidato]`; `rankear(candidatos,
  pubmed_client, llm_client, top_n=5, cap_por_eje=2) -> AgentResult`. Used by
  `orchestrator.py` (Task 9).

- [ ] **Step 1: Write the failing test `tests/test_novelty_checker.py`**

```python
from agents.novelty_checker import Candidato, candidato_id, score_novedad
from core.pubmed_client import FakePubMedClient

_C = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
              outcome="nivel_tratamiento_requerido", n_disponible=45)


def test_candidato_id_es_slug_estable():
    assert candidato_id(_C) == "riesgo_sistemico_asa_adultos_mayores_nivel_tratamiento_requerido"


def test_score_novedad_alto_cuando_pubmed_vacio():
    client = FakePubMedClient({})
    score, warnings = score_novedad(_C, client)
    assert score == 1.0
    assert warnings == []


def test_score_novedad_bajo_cuando_pubmed_saturado():
    query = (f"{_C.subpoblacion} {_C.eje} {_C.outcome} dental")
    client = FakePubMedClient({query: 500})
    score, warnings = score_novedad(_C, client)
    assert score < 0.2
    assert warnings == []


def test_score_novedad_degrada_a_neutro_si_pubmed_falla():
    client = FakePubMedClient({}, fail=True)
    score, warnings = score_novedad(_C, client)
    assert score == 0.5
    assert "PubMed" in warnings[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_novelty_checker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.novelty_checker'`

- [ ] **Step 3: Write `agents/novelty_checker.py`**

```python
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidato:
    eje: str
    subpoblacion: str
    outcome: str
    n_disponible: int


def candidato_id(c: Candidato) -> str:
    return f"{c.eje}_{c.subpoblacion}_{c.outcome}"


def _query(c: Candidato) -> str:
    return f"{c.subpoblacion} {c.eje} {c.outcome} dental"


_CAP_SATURACION = 100  # nº de artículos a partir del cual la novedad se considera ~0


def score_novedad(candidato: Candidato, pubmed_client) -> tuple[float, list[str]]:
    try:
        conteo = pubmed_client.contar(_query(candidato))
    except ConnectionError:
        return 0.5, ["PubMed no disponible: novedad neutra (0.5) asignada por defecto."]
    score = max(0.0, 1.0 - math.log10(1 + conteo) / math.log10(1 + _CAP_SATURACION))
    return round(score, 4), []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_novelty_checker.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Write the failing test `tests/test_gap_finder.py`**

```python
import json

from agents.gap_finder import generar_espacio, filtrar_factibilidad, rankear
from agents.novelty_checker import Candidato
from core.knowledge import load_plantilla, Perfil
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def test_generar_espacio_respeta_compatibilidad():
    p = _plantilla()
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-24")
    espacio = generar_espacio(p, perfil)
    # cooperacion_manejo_conductual solo es válido para ninos/discapacidad_intelectual
    for c in espacio:
        if c.eje == "cooperacion_manejo_conductual":
            assert c.subpoblacion in {"ninos_preescolares_escolares", "discapacidad_intelectual"}


def test_generar_espacio_adjunta_n_disponible_del_perfil():
    p = _plantilla()
    perfil = Perfil(n_por_celda={("adultos_mayores", "riesgo_sistemico_asa"): 45},
                    distribuciones={}, generado_en="2026-07-24")
    espacio = generar_espacio(p, perfil)
    match = [c for c in espacio if c.eje == "riesgo_sistemico_asa" and c.subpoblacion == "adultos_mayores"]
    assert match and all(c.n_disponible == 45 for c in match)


def test_filtrar_factibilidad_descarta_bajo_n_min():
    p = _plantilla()  # n_min: 30
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos", outcome="grado_cooperacion", n_disponible=10),
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion", n_disponible=45),
    ]
    supervivientes = filtrar_factibilidad(candidatos, p)
    assert len(supervivientes) == 1
    assert supervivientes[0].subpoblacion == "adultos_mayores"


def test_rankear_ok_con_llm_disponible():
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion", n_disponible=45),
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.5, "justificacion": "relevante"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] == 8.5
    assert r.data[0]["novedad"] == 1.0


def test_rankear_degrada_sin_llm():
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion", n_disponible=45),
    ]
    llm = FakeLLMClient(fail=True)
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] is None
    assert "degradado" in r.warnings[0].lower() or "LLM" in r.warnings[0]


def test_rankear_cap_por_eje_limita_diversidad():
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion=f"pob_{i}", outcome="grado_cooperacion", n_disponible=45)
        for i in range(5)
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 9.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, top_n=5, cap_por_eje=2)
    assert len(r.data) == 5  # segunda pasada completa el resto ignorando el cap
    primeros_dos_ejes = {row["candidato"].eje for row in r.data[:2]}
    assert primeros_dos_ejes == {"riesgo_sistemico_asa"}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_gap_finder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.gap_finder'`

- [ ] **Step 7: Write `agents/gap_finder.py`**

```python
from __future__ import annotations

import json
from itertools import product

from agents.novelty_checker import Candidato, score_novedad
from core.knowledge import Perfil, Plantilla
from core.result import AgentResult

_SYSTEM_RANKING = (
    "Eres un epidemiólogo/odontólogo que evalúa huecos de investigación observacional "
    "sobre una cohorte clínica de pacientes especiales (sin inferencia causal). Responde "
    'SOLO JSON {"score": <0-10>, "justificacion": "<3-4 líneas, sin lenguaje causal>"}.'
)


def generar_espacio(p: Plantilla, perfil: Perfil) -> list[Candidato]:
    espacio: list[Candidato] = []
    for eje, subpoblacion, outcome in product(p.ejes, p.subpoblaciones, p.outcomes):
        validas = p.compatibilidad.get(eje, frozenset())
        if subpoblacion not in validas:
            continue
        espacio.append(Candidato(
            eje=eje, subpoblacion=subpoblacion, outcome=outcome,
            n_disponible=perfil.n((subpoblacion, eje)),
        ))
    return espacio


def filtrar_factibilidad(candidatos: list[Candidato], p: Plantilla) -> list[Candidato]:
    return [c for c in candidatos if c.n_disponible >= p.n_min]


def _prompt_candidato(c: Candidato) -> str:
    return (
        f"Eje temático: {c.eje}\nSubpoblación: {c.subpoblacion}\nOutcome propuesto: {c.outcome}\n"
        f"n disponible en la cohorte: {c.n_disponible}\n"
        "Evalúa plausibilidad clínica, relevancia y publicabilidad de un estudio "
        "observacional (prevalencia/asociación) sobre esta combinación."
    )


def _top_diverso(filas: list[dict], top_n: int, cap_por_eje: int) -> list[dict]:
    seleccion: list[dict] = []
    conteo: dict[str, int] = {}
    for f in filas:
        if len(seleccion) >= top_n:
            break
        eje = f["candidato"].eje
        if conteo.get(eje, 0) < cap_por_eje:
            seleccion.append(f)
            conteo[eje] = conteo.get(eje, 0) + 1
    if len(seleccion) < top_n:
        ya = {id(f) for f in seleccion}
        for f in filas:
            if len(seleccion) >= top_n:
                break
            if id(f) not in ya:
                seleccion.append(f)
    return seleccion


def rankear(candidatos: list[Candidato], pubmed_client, llm_client,
           top_n: int = 5, cap_por_eje: int = 2) -> AgentResult:
    warnings: list[str] = []
    filas = []
    llm_degradado = False
    for c in candidatos:
        novedad, novedad_warnings = score_novedad(c, pubmed_client)
        warnings.extend(novedad_warnings)
        if llm_degradado:
            filas.append({"candidato": c, "score_llm": None, "justificacion": "", "novedad": novedad})
            continue
        try:
            raw = llm_client.call(_SYSTEM_RANKING, _prompt_candidato(c))
            parsed = json.loads(raw)
            filas.append({
                "candidato": c, "score_llm": float(parsed["score"]),
                "justificacion": parsed["justificacion"], "novedad": novedad,
            })
        except Exception as exc:  # LLM/parse failure -> degrade for the rest, never crash
            llm_degradado = True
            warnings.append(f"Ranking LLM degradado ({type(exc).__name__}): "
                            f"resto ordenado por novedad.")
            filas.append({"candidato": c, "score_llm": None, "justificacion": "", "novedad": novedad})

    if llm_degradado:
        filas.sort(key=lambda f: f["novedad"], reverse=True)
    else:
        filas.sort(key=lambda f: f["score_llm"], reverse=True)

    return AgentResult.degraded(_top_diverso(filas, top_n, cap_por_eje), warnings) if warnings \
        else AgentResult.success(_top_diverso(filas, top_n, cap_por_eje))
```

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest tests/test_gap_finder.py tests/test_novelty_checker.py -v`
Expected: PASS (10 passed)

- [ ] **Step 9: Commit**

```bash
git add agents/novelty_checker.py agents/gap_finder.py tests/test_novelty_checker.py tests/test_gap_finder.py
git commit -m "feat: Gap Finder EPE (factibilidad por n + novedad PubMed + ranking LLM degradable)"
```

---

### Task 9: `ui_render.py` + `orchestrator.py` (CLI: `perfilar`, `propose`)

**Files:**
- Create: `ui_render.py`
- Create: `tests/test_ui_render.py`
- Create: `orchestrator.py`
- Create: `tests/test_orchestrator.py`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–8.
- Produces: `render_candidatos_md(filas, warnings) -> str`; `render_candidatos_json(filas) ->
  str`; `run_perfilar(sheets_reader) -> AgentResult`; `run_propose(plantilla_path: str,
  perfil_path: str, pubmed_client, llm_client, top_n=5, max_candidatos=40) -> AgentResult`;
  `main(argv: list[str]) -> int` CLI dispatch (`perfilar`, `propose`).

- [ ] **Step 1: Write the failing test `tests/test_ui_render.py`**

```python
import json

from agents.novelty_checker import Candidato
from ui_render import render_candidatos_md, render_candidatos_json


def _fila():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="grado_cooperacion", n_disponible=45)
    return {"candidato": c, "score_llm": 8.5, "justificacion": "relevante", "novedad": 0.9}


def test_render_candidatos_md_incluye_datos_clave():
    md = render_candidatos_md([_fila()], warnings=["aviso x"])
    assert "riesgo_sistemico_asa" in md
    assert "adultos_mayores" in md
    assert "n disponible: 45" in md
    assert "aviso x" in md


def test_render_candidatos_md_vacio():
    md = render_candidatos_md([], warnings=[])
    assert "No se generaron candidatos" in md


def test_render_candidatos_json_roundtrip_campos():
    data = json.loads(render_candidatos_json([_fila()]))
    assert data[0]["eje"] == "riesgo_sistemico_asa"
    assert data[0]["n_disponible"] == 45
    assert data[0]["score_llm"] == 8.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ui_render'`

- [ ] **Step 3: Write `ui_render.py`**

```python
from __future__ import annotations

import json

from agents.novelty_checker import candidato_id


def render_candidatos_md(filas: list[dict], warnings: list[str]) -> str:
    lines = ["# Candidatos de semilla EPE", ""]
    if warnings:
        lines += ["> ⚠️ " + w for w in warnings] + [""]
    if not filas:
        lines.append("_No se generaron candidatos._")
        return "\n".join(lines)
    for i, row in enumerate(filas, 1):
        c = row["candidato"]
        score = row["score_llm"]
        score_txt = f"{score:.1f}" if score is not None else "s/valorar (LLM degradado)"
        lines += [
            f"## {i}. {c.eje} × {c.subpoblacion} → {c.outcome}",
            "",
            f"**Pregunta tentativa (observacional, asociación/prevalencia):** ¿Cuál es la "
            f"prevalencia/asociación de {c.eje} con {c.outcome} en {c.subpoblacion} de la "
            f"cohorte EPE?",
            "",
            f"- **n disponible:** {c.n_disponible}",
            f"- **Score LLM:** {score_txt}",
            f"- **Score de novedad (0=saturado,1=vacío en literatura):** {row['novedad']:.2f}",
        ]
        just = row["justificacion"].strip()
        if just:
            lines += ["", f"**Justificación:** {just}"]
        lines.append("")
    return "\n".join(lines)


def render_candidatos_json(filas: list[dict]) -> str:
    items = []
    for row in filas:
        c = row["candidato"]
        items.append({
            "id": candidato_id(c),
            "eje": c.eje,
            "subpoblacion": c.subpoblacion,
            "outcome": c.outcome,
            "n_disponible": c.n_disponible,
            "novedad": row["novedad"],
            "score_llm": row["score_llm"],
        })
    return json.dumps(items, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write the failing test `tests/test_orchestrator.py`**

```python
import json

import pytest

from core.knowledge import load_perfil, guardar_perfil, Perfil
from core.sheets_client import FakeSheetReader
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient
from tests.fixtures.sheet_rows_sinteticas import FILAS_SINTETICAS


def test_run_perfilar_ok_escribe_perfil(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = orchestrator.run_perfilar(reader, out_path="knowledge/perfil_epe.yaml")
    assert r.ok
    assert (tmp_path / "knowledge" / "perfil_epe.yaml").exists()


def test_run_perfilar_fallo_usa_cache_si_existe(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
    cache_path = tmp_path / "knowledge" / "perfil_epe.yaml"
    guardar_perfil(Perfil(n_por_celda={("adultos", "riesgo_sistemico_asa"): 99},
                          distribuciones={}, generado_en="2026-07-01"), str(cache_path))
    reader = FakeSheetReader([], fail=True)
    r = orchestrator.run_perfilar(reader, out_path=str(cache_path))
    assert r.ok
    assert "cacheado" in r.warnings[0].lower()
    assert load_perfil(str(cache_path)).n(("adultos", "riesgo_sistemico_asa")) == 99


def test_run_perfilar_fallo_sin_cache_falla(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
    reader = FakeSheetReader([], fail=True)
    r = orchestrator.run_perfilar(reader, out_path=str(tmp_path / "knowledge" / "perfil_epe.yaml"))
    assert not r.ok


def test_run_propose_produce_candidatos(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    perfil_path = tmp_path / "perfil.yaml"
    guardar_perfil(Perfil(n_por_celda={("adultos_mayores", "riesgo_sistemico_asa"): 45},
                          distribuciones={}, generado_en="2026-07-24"), str(perfil_path))
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = orchestrator.run_propose("knowledge/plantilla_epe.yaml", str(perfil_path), pubmed, llm)
    assert r.ok
    assert len(r.data) >= 1


def test_orchestrator_main_uso_sin_argumentos(capsys):
    import orchestrator
    assert orchestrator.main([]) == 2
    assert "perfilar" in capsys.readouterr().err
    assert "propose" in capsys.readouterr().err
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator'`

- [ ] **Step 7: Write `orchestrator.py`**

```python
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from agents.gap_finder import filtrar_factibilidad, generar_espacio, rankear
from agents.perfilador import perfilar
from core.knowledge import guardar_perfil, load_perfil, load_plantilla
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from core.result import AgentResult
from core.sheets_client import GspreadSheetReader, SheetReader
from ui_render import render_candidatos_json, render_candidatos_md


def run_perfilar(reader: SheetReader, out_path: str = "knowledge/perfil_epe.yaml") -> AgentResult:
    r = perfilar(reader)
    if r.ok:
        guardar_perfil(r.data, out_path)
        return r
    # perfilar falló (p.ej. sin conexión): degrada al último perfil cacheado si existe.
    if Path(out_path).exists():
        cacheado = load_perfil(out_path)
        return AgentResult.degraded(
            cacheado,
            [f"No se pudo leer el Sheet en vivo ({r.warnings[0]}); "
             f"usando perfil cacheado del {cacheado.generado_en}."],
        )
    return AgentResult.failure(
        [f"No se pudo leer el Sheet y no hay perfil cacheado en {out_path}: {r.warnings[0]}"]
    )


def run_propose(plantilla_path: str, perfil_path: str, pubmed_client, llm_client,
               top_n: int = 5, max_candidatos: int = 40) -> AgentResult:
    p = load_plantilla(plantilla_path)
    perfil = load_perfil(perfil_path)
    espacio = generar_espacio(p, perfil)
    factibles = filtrar_factibilidad(espacio, p)[:max_candidatos]
    return rankear(factibles, pubmed_client, llm_client, top_n=top_n)


def _make_llm_client_or_none():
    try:
        return make_client(os.environ)
    except ValueError as exc:
        print(f"  aviso: {exc} — modo degradado (sin LLM)")
        return None


def _cmd_perfilar() -> int:
    credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("EPE_SHEET_ID")
    worksheet = os.environ.get("EPE_WORKSHEET_NAME", "Datos")
    if not credentials or not sheet_id:
        print("Faltan GOOGLE_SERVICE_ACCOUNT_JSON y/o EPE_SHEET_ID en el entorno (.env).",
              file=sys.stderr)
        return 1
    reader = GspreadSheetReader(credentials, sheet_id, worksheet)
    r = run_perfilar(reader)
    for w in r.warnings:
        print(f"  aviso: {w}")
    if not r.ok:
        return 1
    print("Escrito: knowledge/perfil_epe.yaml")
    return 0


def _cmd_propose() -> int:
    llm = _make_llm_client_or_none()
    if llm is None:
        from core.llm_client import FakeLLMClient
        llm = FakeLLMClient(default='{"score": 0, "justificacion": ""}')
    pubmed = make_pubmed_client(os.environ)
    result = run_propose("knowledge/plantilla_epe.yaml", "knowledge/perfil_epe.yaml", pubmed, llm)
    md = render_candidatos_md(result.data, result.warnings)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out = Path("outputs") / run_id / "candidatos.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    (out.parent / "candidatos.json").write_text(
        render_candidatos_json(result.data), encoding="utf-8")
    print(f"Escrito: {out}")
    for w in result.warnings:
        print(f"  aviso: {w}")
    return 0


def main(argv: list[str]) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if argv and argv[0] == "perfilar":
        return _cmd_perfilar()
    if argv and argv[0] == "propose":
        return _cmd_propose()
    print("uso: python orchestrator.py perfilar | propose", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest -q`
Expected: PASS (all tests in the suite green)

- [ ] **Step 9: Write `.env.example`**

```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
PUBMED_API_KEY=
GOOGLE_SERVICE_ACCOUNT_JSON=./credentials/epe-generator-sa.json
EPE_SHEET_ID=<EPE_SHEET_ID — ver .env local>
EPE_WORKSHEET_NAME=Datos
```

- [ ] **Step 10: Write `README.md`**

```markdown
# epe-generator

Sistema agéntico que genera **semillas de ideas de investigación primaria** a partir del
perfil agregado (sin PHI) de la cohorte EPE (Servicio de Pacientes Especiales, Depto. de
Odontoestomatología, Hospital Nacional PNP "Luis N. Sáenz"). Espeja el patrón `propose` /
Gap Finder de `endes-generator`. Sistema **independiente**: no depende de `nucleo` ni de
`endes-generator`.

## Ciclo (v1 — solo fase de semillas)

```
perfilar  →  propose
   A            B
Sheet EPE   candidatos.md + candidatos.json
```

## Setup de credenciales de Google (cuenta de servicio)

1. En Google Cloud Console, crea un proyecto (o reusa uno) y habilita la **Google Sheets API**.
2. Crea una **cuenta de servicio**, genera una clave JSON y guárdala fuera de git (p. ej.
   `credentials/epe-generator-sa.json` — ya está en `.gitignore`).
3. Comparte el Google Sheet **"Estadística EPE 2023-2026"** con el email de la cuenta de
   servicio (permiso de lectura basta).
4. Copia `.env.example` a `.env` y completa `GOOGLE_SERVICE_ACCOUNT_JSON`, `EPE_SHEET_ID`,
   `EPE_WORKSHEET_NAME`.

## Comandos

```bash
pip install -r requirements.txt
python orchestrator.py perfilar   # Sheet EPE (vivo) -> knowledge/perfil_epe.yaml (sin PHI)
python orchestrator.py propose    # perfil + plantilla -> outputs/<timestamp>/candidatos.{md,json}
```

## Privacidad

`perfilador.py` es el único punto que toca datos con PHI, y su salida (`perfil_epe.yaml`) es
estrictamente agregada: conteos y `n` por celda, nunca filas individuales ni identificadores
(DNI, nombre, celular, fecha de nacimiento — ver `PHI_COLUMNS_EXCLUIDAS`). Celdas con `n` por
debajo de `n_min` (30, en `knowledge/plantilla_epe.yaml`) se descartan también por factibilidad
estadística, lo que de paso suprime celdas pequeñas con riesgo de reidentificación.

## Tests

```bash
python -m pytest -q
```

Corre **sin red, sin credenciales de Google y sin API keys** (fixtures sintéticos en
`tests/fixtures/`).

## Fuera de alcance (v1)

Fases `design`/`analyze`/`report` (protocolo, datos, informe) quedan pendientes, igual que
`endes-generator` las escalonó. Una semilla que el usuario valide se lleva manualmente, ya
formulada, a `nucleo` si quiere respaldo de revisión de literatura — este sistema nunca
alimenta el motor de `nucleo` directamente.
```

- [ ] **Step 11: Commit**

```bash
git add ui_render.py orchestrator.py tests/test_ui_render.py tests/test_orchestrator.py .env.example README.md
git commit -m "feat: orchestrator CLI (perfilar/propose) + ui_render + README + setup credenciales"
```

---

## Post-plan manual step (not automatable, not part of the test suite)

After Task 9 is merged, the human (Leonid) must:
1. Create the GCP service account and share the EPE Sheet with it (README Task 9, Step 10).
2. Run `python orchestrator.py perfilar` once against the real Sheet to produce the first real
   `knowledge/perfil_epe.yaml`.
3. Run `python orchestrator.py propose` to get the first real batch of candidatos, and review
   them for clinical sense before treating any as a seed to carry into `nucleo`.
