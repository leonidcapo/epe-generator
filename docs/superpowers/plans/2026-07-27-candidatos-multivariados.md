# Candidatos Multivariados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `epe-generator`'s bivariate candidates (`eje × subpoblación → outcome`, `n`
marginal) with multivariate candidates (`eje_principal × subpoblación → outcome, ajustado por
covariables_ajuste`, `n` **conjunto** — the joint count of patients with data present
simultaneously across every covariate in the model).

**Architecture:** `perfilador.py` now needs `Plantilla` (previously data-source-only) to compute,
per subpoblación, the joint count over its full *implemented* set of compatible ejes (declared-but-
dataless ejes like `morbilidad_cie11_sistemas`/`estado_nutricional_imc` are excluded from that
universe via a new `estado: sin_datos` marker, otherwise the joint requirement could never be
satisfied and would zero out entire subpoblaciones). `gap_finder.generar_espacio` produces one
candidate per eje-as-principal-exposure per subpoblación with ≥2 implemented compatible ejes, using
the rest of that universe as adjustment covariates.

**Tech Stack:** No new dependencies. Pure Python dataclass/dict changes across the existing
`core`/`agents`/`ui_render`/`orchestrator` modules.

## Global Constraints

- **Replaces, does not coexist with, bivariate candidates.** `propose` only produces multivariate
  candidates from this point forward.
- **Covariate universe = all ejes compatible with the subpoblación per
  `compatibilidad_eje_subpoblacion`, minus any eje marked `estado: sin_datos`** (declared but with
  no backing data column in `perfilador.py`). This is not optional — using the full *declared*
  universe (including dataless ejes) would make the joint-count requirement impossible to satisfy
  for `adultos`, `adultos_mayores`, and `asa3_alto_riesgo` (all three have `morbilidad_cie11_sistemas`
  and/or `estado_nutricional_imc` in their declared compatible set).
- **One candidate per eje-as-principal-exposure.** For each subpoblación with ≥2 implemented
  compatible ejes, generate one candidate per eje in that set acting as the principal exposure; the
  rest of the set are `covariables_ajuste`.
- **Subpoblaciones with <2 implemented compatible ejes are excluded** from candidate generation
  entirely (no adjustment covariate possible → not multivariate).
- **`n_disponible` = joint count over the full covariate universe**, identical for every
  eje-as-principal variant within a subpoblación (the required simultaneous-presence set is the
  same regardless of which member is called "principal").
- **PHI safety is unchanged and must be re-verified**: the new joint-count logic operates on
  `filas_limpias` (already PHI-stripped), exactly like the existing `_n_por_celda`. No new raw data
  reaches any output.
- **Expect fewer candidates than before** — this is correct, not a regression: joint `n` is always
  `≤` any single marginal `n`.
- **`n_min` = 30** (from `knowledge/plantilla_epe.yaml`, unchanged) applies to the new joint
  `n_disponible` exactly as it applied to the old marginal one.

---

## File Structure

```
epe-generator/
  knowledge/
    plantilla_epe.yaml        # MODIFIED — 2 ejes marked estado: sin_datos
  core/
    knowledge.py                # MODIFIED — Perfil.n_conjunto, ejes_implementados_por_subpoblacion()
  agents/
    perfilador.py                # MODIFIED — perfilar(reader, plantilla), _n_conjunto()
    novelty_checker.py            # MODIFIED — Candidato.covariables_ajuste, candidato_id()
    gap_finder.py                  # MODIFIED — generar_espacio() rewrite, prompt wording
  ui_render.py                     # MODIFIED — render covariables_ajuste
  orchestrator.py                  # MODIFIED — run_perfilar() loads + passes Plantilla
  tests/
    test_knowledge.py               # MODIFIED — n_conjunto roundtrip, universo tests
    test_perfilador.py               # MODIFIED — new signature, n_conjunto assertions
    test_novelty_checker.py           # MODIFIED — Candidato shape, candidato_id
    test_gap_finder.py                 # MODIFIED — generar_espacio rewrite tests
    test_ui_render.py                   # MODIFIED — covariables in render
    test_orchestrator.py                 # MODIFIED — plantilla-aware run_perfilar
```

---

### Task 1: `core/knowledge.py` — `Perfil.n_conjunto` + `ejes_implementados_por_subpoblacion`

**Files:**
- Modify: `knowledge/plantilla_epe.yaml`
- Modify: `core/knowledge.py`
- Modify: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: nothing new (extends existing `Plantilla`/`Perfil`).
- Produces: `ejes_implementados_por_subpoblacion(p: Plantilla) -> dict[str, frozenset[str]]`
  (subpoblación id → frozenset of eje ids compatible with it AND not marked `sin_datos`). `Perfil`
  gains `n_conjunto: dict[str, int] = field(default_factory=dict)` (subpoblación id → joint count),
  with `guardar_perfil`/`load_perfil` serializing/deserializing it (missing key on load degrades to
  `{}`, for backward-compat with pre-migration cached files). Used by `agents/perfilador.py`
  (Task 2, produces the values) and `agents/gap_finder.py` (Task 4, consumes them).

- [ ] **Step 1: Mark the two dataless ejes in `knowledge/plantilla_epe.yaml`**

Change these two lines (leave everything else in the file untouched):

```yaml
  - {id: morbilidad_cie11_sistemas, estado: sin_datos}
```

```yaml
  - {id: estado_nutricional_imc, estado: sin_datos}
```

(Both were previously `estado: candidato`.)

- [ ] **Step 2: Write the failing tests — add to `tests/test_knowledge.py`**

Add this import at the top (alongside the existing ones):

```python
from core.knowledge import ejes_implementados_por_subpoblacion
```

Append these tests:

```python
def test_ejes_implementados_por_subpoblacion_excluye_ejes_sin_datos():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    universos = ejes_implementados_por_subpoblacion(p)
    # adultos es compatible con morbilidad_cie11_sistemas y estado_nutricional_imc en la
    # plantilla, pero ninguno tiene columna de datos real (estado: sin_datos) -> deben
    # quedar fuera del universo implementado.
    assert universos["adultos"] == frozenset({"riesgo_sistemico_asa", "procedencia_acceso"})
    assert universos["adultos_mayores"] == frozenset(
        {"riesgo_sistemico_asa", "farmacoterapia_polifarmacia", "procedencia_acceso"}
    )
    assert universos["discapacidad_intelectual"] == frozenset(
        {"discapacidad_tipo_severidad", "cooperacion_manejo_conductual"}
    )
    assert universos["asa3_alto_riesgo"] == frozenset(
        {"riesgo_sistemico_asa", "farmacoterapia_polifarmacia"}
    )
    # subpoblaciones con un solo eje compatible siguen apareciendo (universo tamaño 1);
    # es tarea de gap_finder decidir que tamaño <2 no genera candidatos multivariados.
    assert universos["adolescentes"] == frozenset({"procedencia_acceso"})
    assert universos["discapacidad_fisica"] == frozenset({"discapacidad_tipo_severidad"})
    assert universos["discapacidad_sensorial"] == frozenset({"discapacidad_tipo_severidad"})


def test_perfil_n_conjunto_default_vacio():
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27")
    assert perfil.n_conjunto == {}


def test_perfil_roundtrip_incluye_n_conjunto(tmp_path):
    perfil = Perfil(
        n_por_celda={("adultos", "riesgo_sistemico_asa"): 120},
        distribuciones={"sexo": {"F": 900, "M": 834}},
        generado_en="2026-07-27",
        n_conjunto={"adultos": 45, "adultos_mayores": 30},
    )
    path = str(tmp_path / "perfil_epe.yaml")
    guardar_perfil(perfil, path)
    cargado = load_perfil(path)
    assert cargado == perfil


def test_load_perfil_perfil_viejo_sin_n_conjunto_degrada_a_vacio(tmp_path):
    # Un perfil_epe.yaml cacheado ANTES de esta migración no tiene la clave n_conjunto.
    contenido = """
n_por_celda:
  - {subpoblacion: adultos, eje: riesgo_sistemico_asa, n: 10}
distribuciones: {}
generado_en: '2026-07-01'
"""
    path = tmp_path / "perfil_viejo.yaml"
    path.write_text(contenido, encoding="utf-8")
    perfil = load_perfil(str(path))
    assert perfil.n_conjunto == {}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: FAIL — `ImportError: cannot import name 'ejes_implementados_por_subpoblacion'` and/or
`TypeError: Perfil.__init__() got an unexpected keyword argument 'n_conjunto'`

- [ ] **Step 4: Implement in `core/knowledge.py`**

Change the import line at the top from `from dataclasses import dataclass` to:

```python
from dataclasses import dataclass, field
```

Add `n_conjunto` to the `Perfil` dataclass (it currently has `n_por_celda`, `distribuciones`,
`generado_en`, and the `.n()` method — add the new field right after `generado_en`):

```python
    n_conjunto: dict[str, int] = field(default_factory=dict)  # subpoblacion -> n conjunto
```

Add this function after `load_plantilla` (before the `Perfil` dataclass):

```python
def ejes_implementados_por_subpoblacion(p: Plantilla) -> dict[str, frozenset[str]]:
    """Para cada subpoblación declarada, el universo de ejes compatibles que además tienen
    datos reales calculados por perfilador (estado != 'sin_datos' en la plantilla). Ejes
    declarados compatibles pero sin columna de datos (p.ej. morbilidad_cie11_sistemas,
    estado_nutricional_imc) quedan fuera del universo — de lo contrario el n conjunto
    exigiría un eje que ninguna fila puede satisfacer jamás, anulando subpoblaciones
    enteras (adultos, adultos_mayores, asa3_alto_riesgo tienen alguno de estos dos ejes
    en su set compatible declarado)."""
    resultado: dict[str, frozenset[str]] = {sp: frozenset() for sp in p.subpoblaciones}
    for eje, subpoblaciones_validas in p.compatibilidad.items():
        if p.ejes.get(eje) == "sin_datos":
            continue
        for sp in subpoblaciones_validas:
            resultado[sp] = resultado[sp] | {eje}
    return resultado
```

In `guardar_perfil`, add `n_conjunto` to the serialized dict:

```python
def guardar_perfil(perfil: Perfil, path: str) -> None:
    serializable = {
        "n_por_celda": [
            {"subpoblacion": sp, "eje": eje, "n": n}
            for (sp, eje), n in perfil.n_por_celda.items()
        ],
        "distribuciones": perfil.distribuciones,
        "generado_en": perfil.generado_en,
        "n_conjunto": perfil.n_conjunto,
    }
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(serializable, fh, allow_unicode=True, sort_keys=False)
```

In `load_perfil`, read it back with a degrading default:

```python
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
        n_conjunto=d.get("n_conjunto", {}),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: PASS (all tests in the file, including the 4 new ones)

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: some failures are OK here — this task deliberately changes `Perfil`'s shape and
`plantilla_epe.yaml`'s content, which later tasks fix. Confirm specifically that
`tests/test_knowledge.py` itself is 100% green; other files' failures are expected until their
respective tasks land.

- [ ] **Step 7: Commit**

```bash
git add knowledge/plantilla_epe.yaml core/knowledge.py tests/test_knowledge.py
git commit -m "feat: Perfil.n_conjunto + ejes_implementados_por_subpoblacion (universo real)"
```

---

### Task 2: `agents/perfilador.py` — `perfilar(reader, plantilla)` computes `n_conjunto`

**Files:**
- Modify: `agents/perfilador.py`
- Modify: `tests/test_perfilador.py`

**Interfaces:**
- Consumes: `Perfil.n_conjunto`, `ejes_implementados_por_subpoblacion(p: Plantilla) ->
  dict[str, frozenset[str]]` (Task 1). `Plantilla` type from `core.knowledge`.
- Produces: `perfilar(reader: SheetReader, plantilla: Plantilla) -> AgentResult` — **breaking
  signature change** (previously `perfilar(reader)`). Used by `orchestrator.py` (Task 6).

- [ ] **Step 1: Write the failing tests — modify `tests/test_perfilador.py`**

Add this import at the top:

```python
from core.knowledge import load_plantilla
```

Add this helper right after the imports:

```python
def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")
```

Update **every** existing call of the form `perfilar(reader)` in this file to `perfilar(reader,
_plantilla())`. There are 11 call sites — in
`test_perfilar_excluye_columnas_phi`, `test_perfilar_agrega_distribucion_por_variable`,
`test_perfilar_calcula_n_por_celda_subpoblacion_eje`,
`test_perfilar_n_por_celda_discapacidad_intelectual_x_tipo_severidad`,
`test_perfilar_n_por_celda_farmacoterapia_excluye_ninguna`,
`test_perfilar_cubre_al_menos_5_de_6_ejes_en_scope`,
`test_perfilar_fila_cuenta_en_dos_subpoblaciones_simultaneamente`,
`test_perfilar_descarta_columna_desconocida_no_blocklisteada`,
`test_perfilar_conexion_fallida_produce_failure`,
`test_perfilar_sheet_vacio_produce_perfil_vacio_sin_crashear`,
`test_perfilar_descarta_fila_sin_dni`, `test_perfilar_deduplica_dni_repetido_se_queda_con_la_primera_fila`,
`test_perfilar_estado_nutricional_imc_nunca_aparece`. Each becomes e.g.:

```python
def test_perfilar_conexion_fallida_produce_failure():
    reader = FakeSheetReader([], fail=True)
    r = perfilar(reader, _plantilla())
    assert not r.ok
    assert "simulado" in r.warnings[0]
```

(Same pattern for all of them — just add `, _plantilla()` as the second argument to every
`perfilar(reader)` call.)

Also extend `test_perfilar_excluye_columnas_phi` to include `n_conjunto` in the PHI-leak check
(append this line to `texto_completo`'s construction):

```python
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda) + str(perfil.n_conjunto)
```

Append these new tests (hand-verified against `tests/fixtures/sheet_rows_sinteticas.py`'s 9 rows —
see the derivation table below):

```python
def test_perfilar_n_conjunto_ninos_preescolares_escolares():
    # Universo implementado de ninos_preescolares_escolares: {cooperacion_manejo_conductual,
    # procedencia_acceso}. Solo la fila 5 (Mateo Silva, Niño escolar) pertenece a esta
    # subpoblación, y tiene AMBOS ejes presentes (Grado de cooperación="Negativo" truthy,
    # Lugar de Procedencia="Lima") -> cuenta.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["ninos_preescolares_escolares"] == 1


def test_perfilar_n_conjunto_adultos():
    # Universo implementado de adultos: {riesgo_sistemico_asa, procedencia_acceso}.
    # Fila 1 (Reátegui): no tiene Lugar de Procedencia -> no cuenta.
    # Fila 4 (Torres Vega): tiene ambos -> cuenta.
    # Fila 8 (Duplicado primero): no tiene Lugar de Procedencia -> no cuenta.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["adultos"] == 1


def test_perfilar_n_conjunto_adultos_mayores_insuficiente():
    # Universo implementado de adultos_mayores: {riesgo_sistemico_asa,
    # farmacoterapia_polifarmacia, procedencia_acceso}. Ninguna de las filas 2 (Orrego,
    # sin farmacoterapia/procedencia) ni 3 (Ángeles, Farmacoterapia="Ninguna" -> excluida
    # del eje) tiene los TRES ejes simultáneamente -> el n conjunto es 0, aunque el n
    # marginal de riesgo_sistemico_asa para esta subpoblación sea 2.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["adultos_mayores"] == 0
    assert perfil.n(("adultos_mayores", "riesgo_sistemico_asa")) == 2  # marginal, para contraste


def test_perfilar_n_conjunto_discapacidad_intelectual():
    # Universo implementado: {discapacidad_tipo_severidad, cooperacion_manejo_conductual}.
    # Fila 1 (Reátegui, Intelectual, Grado="Positivo") y fila 6 (Ramos, Intelectual,
    # Grado="Positivo") tienen ambos ejes -> cuenta 2.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["discapacidad_intelectual"] == 2


def test_perfilar_n_conjunto_asa3_alto_riesgo():
    # Universo implementado: {riesgo_sistemico_asa, farmacoterapia_polifarmacia}.
    # Fila 2 (Orrego, ASA3, sin farmacoterapia) y fila 3 (Ángeles, ASA3,
    # Farmacoterapia="Ninguna") no califican. Fila 4 (Torres Vega, ASA3,
    # Farmacoterapia="Antihipertensivos") sí -> cuenta 1.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["asa3_alto_riesgo"] == 1


def test_perfilar_n_conjunto_dni_nunca_aparece():
    # El DNI "11111111" usado internamente para deduplicar no debe sobrevivir en
    # n_conjunto tampoco (mismo principio que el resto del perfil).
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert "11111111" not in str(perfil.n_conjunto)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_perfilador.py -v`
Expected: FAIL — `TypeError: perfilar() missing 1 required positional argument: 'plantilla'`

- [ ] **Step 3: Implement in `agents/perfilador.py`**

Change the import line:

```python
from core.knowledge import Perfil, Plantilla, ejes_implementados_por_subpoblacion
```

Add this function right before `def perfilar(...)`:

```python
def _n_conjunto(filas_limpias: list[dict], plantilla: Plantilla) -> dict[str, int]:
    """Para cada subpoblación, cuenta pacientes con dato presente SIMULTÁNEAMENTE en todo
    su universo de ejes implementados (ver ejes_implementados_por_subpoblacion) — el n
    conjunto que necesita un modelo multivariado, no el n marginal de un solo eje.
    Universos vacíos o de un solo eje se computan igual (0 o su n marginal); es tarea de
    gap_finder decidir que <2 no genera candidatos multivariados."""
    universos = ejes_implementados_por_subpoblacion(plantilla)
    conteo: dict[str, int] = {sp: 0 for sp in universos}
    for fila in filas_limpias:
        ejes_fila = _ejes_aplicables(fila)
        for sp in _subpoblaciones(fila):
            universo = universos.get(sp)
            if universo and universo <= ejes_fila:
                conteo[sp] += 1
    return conteo
```

Change the `perfilar` function signature and body:

```python
def perfilar(reader: SheetReader, plantilla: Plantilla) -> AgentResult:
    try:
        filas = reader.leer_filas()
    except ConnectionError as exc:
        return AgentResult.failure([str(exc)])

    filas_unicas = _filas_con_dni_unico(filas)
    filas_limpias = [_fila_sin_phi(f) for f in filas_unicas]

    distribuciones: dict[str, dict[str, int]] = {}
    for var in _VARIABLES_AGREGABLES:
        conteo = Counter(f[var] for f in filas_limpias if f.get(var))
        if conteo:
            distribuciones[var] = dict(conteo)

    perfil = Perfil(
        n_por_celda=_n_por_celda(filas_limpias),
        distribuciones=distribuciones,
        generado_en=date.today().isoformat(),
        n_conjunto=_n_conjunto(filas_limpias, plantilla),
    )
    return AgentResult.success(perfil)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_perfilador.py -v`
Expected: PASS (all tests, including the 6 new `n_conjunto` ones)

- [ ] **Step 5: Commit**

```bash
git add agents/perfilador.py tests/test_perfilador.py
git commit -m "feat: perfilar(reader, plantilla) calcula n conjunto por subpoblación"
```

---

### Task 3: `agents/novelty_checker.py` — `Candidato.covariables_ajuste`

**Files:**
- Modify: `agents/novelty_checker.py`
- Modify: `tests/test_novelty_checker.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Candidato` frozen dataclass gains `covariables_ajuste: tuple[str, ...]` as a required
  field (inserted between `outcome` and `n_disponible`, so the full field order is `eje,
  subpoblacion, outcome, covariables_ajuste, n_disponible`). `candidato_id(c)` now appends
  `_adj_{covariables joined by '_'}` when `covariables_ajuste` is non-empty, unchanged format
  otherwise. `_query`/`score_novedad` behavior is **unchanged** (still ignore
  `covariables_ajuste` entirely, per the design decision that novelty is about the primary
  hypothesis only). Used by `agents/gap_finder.py` (Task 4) and `ui_render.py` (Task 5).

- [ ] **Step 1: Write the failing tests — modify `tests/test_novelty_checker.py`**

Change the module-level `_C` constant (add `covariables_ajuste=()`):

```python
_C = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
              outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=45)
```

Update `test_candidato_id_es_slug_estable` — replace it with:

```python
def test_candidato_id_sin_covariables_mantiene_formato_anterior():
    assert candidato_id(_C) == "riesgo_sistemico_asa_adultos_mayores_nivel_tratamiento_requerido"


def test_candidato_id_incluye_covariables_de_ajuste():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="nivel_tratamiento_requerido",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"),
                 n_disponible=45)
    assert candidato_id(c) == (
        "riesgo_sistemico_asa_adultos_mayores_nivel_tratamiento_requerido"
        "_adj_farmacoterapia_polifarmacia_procedencia_acceso"
    )
```

In `test_query_usa_terminos_traducidos_de_la_plantilla_real`, add `covariables_ajuste=()` to the
`Candidato(...)` call:

```python
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                  outcome="grado_cooperacion", covariables_ajuste=(), n_disponible=45)
```

In `test_query_degrada_a_id_crudo_si_falta_termino`, add `covariables_ajuste=()` to its
`Candidato(...)` call:

```python
    c = Candidato(eje="eje_sin_termino", subpoblacion="adultos_mayores",
                  outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=45)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_novelty_checker.py -v`
Expected: FAIL — `TypeError: Candidato.__init__() missing 1 required positional argument:
'covariables_ajuste'`

- [ ] **Step 3: Implement in `agents/novelty_checker.py`**

Change the `Candidato` dataclass:

```python
@dataclass(frozen=True)
class Candidato:
    eje: str
    subpoblacion: str
    outcome: str
    covariables_ajuste: tuple[str, ...]
    n_disponible: int
```

Change `candidato_id`:

```python
def candidato_id(c: Candidato) -> str:
    base = f"{c.eje}_{c.subpoblacion}_{c.outcome}"
    if not c.covariables_ajuste:
        return base
    return f"{base}_adj_{'_'.join(c.covariables_ajuste)}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_novelty_checker.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add agents/novelty_checker.py tests/test_novelty_checker.py
git commit -m "feat: Candidato.covariables_ajuste (modelo multivariado, no bivariado)"
```

---

### Task 4: `agents/gap_finder.py` — `generar_espacio` produce candidatos multivariados

**Files:**
- Modify: `agents/gap_finder.py`
- Modify: `tests/test_gap_finder.py`

**Interfaces:**
- Consumes: `Candidato(eje, subpoblacion, outcome, covariables_ajuste, n_disponible)` (Task 3),
  `ejes_implementados_por_subpoblacion(p) -> dict[str, frozenset[str]]` and `Perfil.n_conjunto`
  (Task 1).
- Produces: `generar_espacio(p: Plantilla, perfil: Perfil) -> list[Candidato]` — **behavior
  change** (was bivariate, now multivariate; same signature). `filtrar_factibilidad`,
  `_top_diverso`, `rankear` signatures unchanged. Used by `orchestrator.run_propose` (unchanged
  call site — no changes needed in Task 6 for this specific function).

- [ ] **Step 1: Write the failing tests — replace `tests/test_gap_finder.py` in full**

```python
import json

from agents.gap_finder import generar_espacio, filtrar_factibilidad, rankear
from agents.novelty_checker import Candidato
from core.knowledge import load_plantilla, Perfil
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def test_generar_espacio_excluye_subpoblaciones_con_menos_de_2_ejes():
    p = _plantilla()
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27", n_conjunto={})
    espacio = generar_espacio(p, perfil)
    subpoblaciones_presentes = {c.subpoblacion for c in espacio}
    # adolescentes, discapacidad_fisica, discapacidad_sensorial solo tienen 1 eje
    # implementado compatible -> no generan candidatos multivariados.
    assert "adolescentes" not in subpoblaciones_presentes
    assert "discapacidad_fisica" not in subpoblaciones_presentes
    assert "discapacidad_sensorial" not in subpoblaciones_presentes


def test_generar_espacio_un_candidato_por_eje_como_principal():
    p = _plantilla()
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27",
                    n_conjunto={"discapacidad_intelectual": 40})
    espacio = generar_espacio(p, perfil)
    cands_di = [c for c in espacio if c.subpoblacion == "discapacidad_intelectual"]
    ejes_principales = {c.eje for c in cands_di}
    # 2 ejes compatibles implementados (discapacidad_tipo_severidad,
    # cooperacion_manejo_conductual) -> cada uno aparece una vez como principal.
    assert ejes_principales == {"discapacidad_tipo_severidad", "cooperacion_manejo_conductual"}
    for c in cands_di:
        if c.eje == "discapacidad_tipo_severidad":
            assert c.covariables_ajuste == ("cooperacion_manejo_conductual",)
        else:
            assert c.covariables_ajuste == ("discapacidad_tipo_severidad",)
        assert c.n_disponible == 40


def test_generar_espacio_usa_n_conjunto_no_marginal():
    p = _plantilla()
    perfil = Perfil(n_por_celda={("adultos_mayores", "riesgo_sistemico_asa"): 900},  # marginal alto
                    distribuciones={}, generado_en="2026-07-27",
                    n_conjunto={"adultos_mayores": 5})  # conjunto bajo
    espacio = generar_espacio(p, perfil)
    cands = [c for c in espacio if c.subpoblacion == "adultos_mayores" and c.eje == "riesgo_sistemico_asa"]
    assert cands
    assert all(c.n_disponible == 5 for c in cands)  # no 900 — usa el conjunto, no el marginal


def test_filtrar_factibilidad_descarta_bajo_n_min():
    p = _plantilla()  # n_min: 30
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos", outcome="grado_cooperacion",
                 covariables_ajuste=("procedencia_acceso",), n_disponible=10),
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"), n_disponible=45),
    ]
    supervivientes = filtrar_factibilidad(candidatos, p)
    assert len(supervivientes) == 1
    assert supervivientes[0].subpoblacion == "adultos_mayores"


def test_rankear_ok_con_llm_disponible():
    p = _plantilla()
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"), n_disponible=45),
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.5, "justificacion": "relevante"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, p.terminos_busqueda, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] == 8.5
    assert r.data[0]["novedad"] == 1.0


def test_rankear_degrada_sin_llm():
    p = _plantilla()
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"), n_disponible=45),
    ]
    llm = FakeLLMClient(fail=True)
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, p.terminos_busqueda, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] is None
    assert "degradado" in r.warnings[0].lower() or "LLM" in r.warnings[0]


def test_rankear_cap_por_eje_limita_diversidad():
    p = _plantilla()
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion=f"pob_{i}", outcome="grado_cooperacion",
                 covariables_ajuste=(), n_disponible=45)
        for i in range(5)
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 9.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, p.terminos_busqueda, top_n=5, cap_por_eje=2)
    assert len(r.data) == 5  # segunda pasada completa el resto ignorando el cap
    primeros_dos_ejes = {row["candidato"].eje for row in r.data[:2]}
    assert primeros_dos_ejes == {"riesgo_sistemico_asa"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_gap_finder.py -v`
Expected: FAIL — `TypeError: Candidato.__init__() missing 1 required positional argument:
'covariables_ajuste'` (from the still-old `generar_espacio`) and/or old-signature errors

- [ ] **Step 3: Implement in `agents/gap_finder.py`**

Replace the file's imports and `_SYSTEM_RANKING`/`generar_espacio`/`_prompt_candidato`:

```python
from __future__ import annotations

import json

from agents.novelty_checker import Candidato, score_novedad
from core.knowledge import Perfil, Plantilla, ejes_implementados_por_subpoblacion
from core.result import AgentResult

_SYSTEM_RANKING = (
    "Eres un epidemiólogo/odontólogo que evalúa huecos de investigación observacional "
    "sobre una cohorte clínica de pacientes especiales (sin inferencia causal). Cada "
    "propuesta es un modelo MULTIVARIADO: una exposición principal ajustada por "
    'covariables. Responde SOLO JSON {"score": <0-10>, "justificacion": "<3-4 líneas, '
    'sin lenguaje causal>"}.'
)


def generar_espacio(p: Plantilla, perfil: Perfil) -> list[Candidato]:
    espacio: list[Candidato] = []
    universos = ejes_implementados_por_subpoblacion(p)
    for subpoblacion, ejes_validos in universos.items():
        if len(ejes_validos) < 2:
            continue
        n_conjunto = perfil.n_conjunto.get(subpoblacion, 0)
        for eje_principal in sorted(ejes_validos):
            covariables = tuple(sorted(ejes_validos - {eje_principal}))
            for outcome in p.outcomes:
                espacio.append(Candidato(
                    eje=eje_principal, subpoblacion=subpoblacion, outcome=outcome,
                    covariables_ajuste=covariables, n_disponible=n_conjunto,
                ))
    return espacio


def filtrar_factibilidad(candidatos: list[Candidato], p: Plantilla) -> list[Candidato]:
    return [c for c in candidatos if c.n_disponible >= p.n_min]


def _prompt_candidato(c: Candidato) -> str:
    ajuste = ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)"
    return (
        f"Exposición principal: {c.eje}\nSubpoblación: {c.subpoblacion}\n"
        f"Outcome propuesto: {c.outcome}\nCovariables de ajuste: {ajuste}\n"
        f"n disponible (conjunto, todas las variables presentes simultáneamente): "
        f"{c.n_disponible}\n"
        "Evalúa plausibilidad clínica, relevancia y publicabilidad de un estudio "
        "observacional multivariado (asociación ajustada) sobre esta combinación."
    )
```

Leave `_top_diverso` and `rankear` exactly as they are (they operate on `Candidato` generically via
`.eje`, which still exists unchanged).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_gap_finder.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add agents/gap_finder.py tests/test_gap_finder.py
git commit -m "feat: generar_espacio produce candidatos multivariados (eje principal + ajuste)"
```

---

### Task 5: `ui_render.py` — mostrar `covariables_ajuste`

**Files:**
- Modify: `ui_render.py`
- Modify: `tests/test_ui_render.py`

**Interfaces:**
- Consumes: `Candidato.covariables_ajuste` (Task 3).
- Produces: `render_candidatos_md`/`render_candidatos_json` — same signatures, new content
  (covariables listed in both). Used by `orchestrator.py` and `streamlit_app.py` (no signature
  changes needed in either caller).

- [ ] **Step 1: Write the failing tests — replace `tests/test_ui_render.py` in full**

```python
import json

from agents.novelty_checker import Candidato
from ui_render import render_candidatos_md, render_candidatos_json


def _fila():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"),
                 n_disponible=45)
    return {"candidato": c, "score_llm": 8.5, "justificacion": "relevante", "novedad": 0.9}


def test_render_candidatos_md_incluye_datos_clave():
    md = render_candidatos_md([_fila()], warnings=["aviso x"])
    assert "riesgo_sistemico_asa" in md
    assert "adultos_mayores" in md
    assert "n disponible (conjunto): 45" in md
    assert "farmacoterapia_polifarmacia" in md
    assert "procedencia_acceso" in md
    assert "aviso x" in md


def test_render_candidatos_md_sin_covariables_muestra_ninguna():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="grado_cooperacion", covariables_ajuste=(), n_disponible=45)
    fila = {"candidato": c, "score_llm": None, "justificacion": "", "novedad": 0.5}
    md = render_candidatos_md([fila], warnings=[])
    assert "(ninguna)" in md


def test_render_candidatos_md_vacio():
    md = render_candidatos_md([], warnings=[])
    assert "No se generaron candidatos" in md


def test_render_candidatos_json_roundtrip_campos():
    data = json.loads(render_candidatos_json([_fila()]))
    assert data[0]["eje"] == "riesgo_sistemico_asa"
    assert data[0]["n_disponible"] == 45
    assert data[0]["score_llm"] == 8.5
    assert data[0]["covariables_ajuste"] == ["farmacoterapia_polifarmacia", "procedencia_acceso"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: FAIL — `TypeError: Candidato.__init__() missing 1 required positional argument:
'covariables_ajuste'` (already fixed by Task 3) and/or assertion failures on the new content
(`"n disponible (conjunto)"`, `covariables_ajuste` key) not yet rendered

- [ ] **Step 3: Implement in `ui_render.py`**

Replace `render_candidatos_md` and `render_candidatos_json`:

```python
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
        ajuste_txt = ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)"
        lines += [
            f"## {i}. {c.eje} × {c.subpoblacion} → {c.outcome}",
            "",
            f"**Pregunta tentativa (observacional, multivariado ajustado):** ¿Cuál es la "
            f"asociación de {c.eje} con {c.outcome} en {c.subpoblacion} de la cohorte EPE, "
            f"ajustando por {ajuste_txt}?",
            "",
            f"- Covariables de ajuste: {ajuste_txt}",
            f"- n disponible (conjunto): {c.n_disponible}",
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
            "covariables_ajuste": list(c.covariables_ajuste),
            "n_disponible": c.n_disponible,
            "novedad": row["novedad"],
            "score_llm": row["score_llm"],
        })
    return json.dumps(items, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ui_render.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add ui_render.py tests/test_ui_render.py
git commit -m "feat: render_candidatos_md/json muestran covariables_ajuste"
```

---

### Task 6: `orchestrator.py` — `run_perfilar` carga y pasa `Plantilla`

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `perfilar(reader, plantilla)` (Task 2), `load_plantilla` (already imported).
- Produces: `run_perfilar(reader: SheetReader, plantilla_path: str =
  "knowledge/plantilla_epe.yaml", out_path: str = "knowledge/perfil_epe.yaml") -> AgentResult` —
  new optional `plantilla_path` parameter inserted before the existing `out_path` one.
  `_cmd_perfilar()`'s call site (`run_perfilar(reader)`) needs no change since both new/changed
  parameters have defaults.

- [ ] **Step 1: Write the failing tests — modify `tests/test_orchestrator.py`**

Add this helper near the top of the file (after the imports):

```python
def _copiar_plantilla(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "knowledge").mkdir(exist_ok=True)
    shutil.copy(repo_root / "knowledge" / "plantilla_epe.yaml",
                tmp_path / "knowledge" / "plantilla_epe.yaml")
```

Update every test that calls `orchestrator.run_perfilar(...)` directly, or monkeypatches
`orchestrator.perfilar`, to also ensure a real `plantilla_epe.yaml` exists at
`tmp_path/knowledge/plantilla_epe.yaml` BEFORE `monkeypatch.chdir(tmp_path)` — because
`run_perfilar` now calls `load_plantilla(plantilla_path)` unconditionally, even when `perfilar`
itself is mocked. Rewrite these 5 tests exactly as follows:

```python
def test_run_perfilar_ok_escribe_perfil(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = orchestrator.run_perfilar(reader, out_path="knowledge/perfil_epe.yaml")
    assert r.ok
    assert (tmp_path / "knowledge" / "perfil_epe.yaml").exists()


def test_run_perfilar_fallo_usa_cache_si_existe(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
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
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    reader = FakeSheetReader([], fail=True)
    r = orchestrator.run_perfilar(reader, out_path=str(tmp_path / "knowledge" / "perfil_epe.yaml"))
    assert not r.ok


def test_run_perfilar_fallo_cache_con_warnings_vacio_no_crashea(tmp_path, monkeypatch):
    from core.result import AgentResult
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    cache_path = tmp_path / "knowledge" / "perfil_epe.yaml"
    guardar_perfil(Perfil(n_por_celda={("adultos", "riesgo_sistemico_asa"): 99},
                          distribuciones={}, generado_en="2026-07-01"), str(cache_path))
    monkeypatch.setattr(
        orchestrator, "perfilar",
        lambda reader, plantilla: AgentResult.failure([]),
    )
    r = orchestrator.run_perfilar(FakeSheetReader([], fail=True), out_path=str(cache_path))
    assert r.ok
    assert "motivo desconocido" in r.warnings[0]


def test_run_perfilar_fallo_sin_cache_warnings_vacio_no_crashea(tmp_path, monkeypatch):
    from core.result import AgentResult
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        orchestrator, "perfilar",
        lambda reader, plantilla: AgentResult.failure([]),
    )
    r = orchestrator.run_perfilar(
        FakeSheetReader([], fail=True),
        out_path=str(tmp_path / "knowledge" / "perfil_epe.yaml"),
    )
    assert not r.ok
    assert "motivo desconocido" in r.warnings[0]
```

Update `test_run_propose_produce_candidatos` — its `Perfil(...)` currently only sets
`n_por_celda`, which `generar_espacio` no longer reads for factibilidad. Replace it with:

```python
def test_run_propose_produce_candidatos(tmp_path, monkeypatch):
    import orchestrator
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "knowledge").mkdir()
    shutil.copy(repo_root / "knowledge" / "plantilla_epe.yaml",
                tmp_path / "knowledge" / "plantilla_epe.yaml")
    monkeypatch.chdir(tmp_path)
    perfil_path = tmp_path / "perfil.yaml"
    guardar_perfil(Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27",
                          n_conjunto={"discapacidad_intelectual": 40}), str(perfil_path))
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = orchestrator.run_propose("knowledge/plantilla_epe.yaml", str(perfil_path), pubmed, llm)
    assert r.ok
    assert len(r.data) >= 1
    assert all(row["candidato"].n_disponible >= 30 for row in r.data)
```

The remaining tests in this file (`test_orchestrator_main_uso_sin_argumentos`,
`test_cmd_propose_con_fallo_no_escribe_y_retorna_1`, `test_cmd_propose_sin_perfil_no_crashea_y_retorna_1`)
are untouched by this task — they exercise `_cmd_propose`/`main`, not `run_perfilar`, and don't
construct `Perfil` in a way affected by `n_conjunto`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `TypeError: perfilar() missing 1 required positional argument: 'plantilla'` (from
`run_perfilar` still calling the old 1-arg `perfilar`), and/or `FileNotFoundError` for
`knowledge/plantilla_epe.yaml` in tests not yet copying it, and/or `len(r.data) == 0` in the
`test_run_propose_produce_candidatos` case (old `Perfil` had no matching `n_conjunto`)

- [ ] **Step 3: Implement in `orchestrator.py`**

Change `run_perfilar`:

```python
def run_perfilar(reader: SheetReader, plantilla_path: str = "knowledge/plantilla_epe.yaml",
                 out_path: str = "knowledge/perfil_epe.yaml") -> AgentResult:
    plantilla = load_plantilla(plantilla_path)
    r = perfilar(reader, plantilla)
    if r.ok:
        guardar_perfil(r.data, out_path)
        return r
    # perfilar falló (p.ej. sin conexión): degrada al último perfil cacheado si existe.
    motivo = r.warnings[0] if r.warnings else "motivo desconocido"
    if Path(out_path).exists():
        cacheado = load_perfil(out_path)
        return AgentResult.degraded(
            cacheado,
            [f"No se pudo leer el Sheet en vivo ({motivo}); "
             f"usando perfil cacheado del {cacheado.generado_en}."],
        )
    return AgentResult.failure(
        [f"No se pudo leer el Sheet y no hay perfil cacheado en {out_path}: {motivo}"]
    )
```

(`_cmd_perfilar` needs no change — it already calls `run_perfilar(reader)` with no explicit
`plantilla_path`/`out_path`, so the new default applies automatically.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the FULL suite**

Run: `python -m pytest -q`
Expected: PASS, all files green. Report the total count (baseline before this plan was 75).

- [ ] **Step 6: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: run_perfilar carga Plantilla y la pasa a perfilar (candidatos multivariados)"
```

---

## Post-plan manual step (not automatable, not part of the test suite)

After Task 6 is merged, the human (Leonid) must:
1. Run `python orchestrator.py perfilar` against the real `Marco` sheet to produce a fresh
   `knowledge/perfil_epe.yaml` with real `n_conjunto` values.
2. Run `python orchestrator.py propose` (or the Streamlit app) and review the resulting
   multivariate candidates — confirm the expected drop in candidate count vs. the old bivariate
   output is reasonable, and that the LLM's justifications correctly reference the adjustment
   covariates.
