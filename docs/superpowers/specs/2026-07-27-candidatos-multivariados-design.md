# Candidatos multivariados — Diseño

**Fecha:** 2026-07-27
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

Hoy `propose` genera candidatos **bivariados**: `eje × subpoblación → outcome`, con `n_disponible`
= el `n` **marginal** de ese único eje en esa subpoblación. Este diseño los reemplaza por
candidatos **multivariados**: `eje_principal × subpoblación → outcome, ajustado por
covariables_ajuste`, donde `covariables_ajuste` son los demás ejes compatibles con esa
subpoblación según `plantilla_epe.yaml`, y `n_disponible` pasa a ser el **`n` conjunto** — cuántos
pacientes tienen dato simultáneo en *todas* las variables del modelo, no en cada una por separado.

## 2. El problema que resuelve

El `n` marginal de un eje individual sobreestima la factibilidad real de un modelo ajustado: un
paciente puede tener dato en `riesgo_sistemico_asa` pero no en `farmacoterapia_polifarmacia`, y el
`n` conjunto de ambas siempre es `≤` al menor de los dos marginales. Generar candidatos con `n`
marginal cuando la pregunta de investigación es multivariada es, en el mejor caso, optimista, y en
el peor, engañoso sobre la potencia estadística real disponible.

## 3. Decisiones de diseño (aprobadas)

- **Reemplaza, no coexiste con, los candidatos bivariados actuales.** `propose` solo produce
  candidatos multivariados de ahora en adelante.
- **Universo de covariables = todos los ejes compatibles con la subpoblación** (según
  `compatibilidad_eje_subpoblacion` en `plantilla_epe.yaml`), no un subconjunto elegido por el LLM
  ni por el usuario.
- **Un candidato por cada eje-como-exposición-principal.** Para cada subpoblación con ≥2 ejes
  compatibles, se genera un candidato por cada eje de ese conjunto actuando como **exposición
  principal**; el resto del conjunto son **covariables de ajuste**. Replica el formato estándar de
  un paper epidemiológico (razón de prevalencia ajustada).
- **Subpoblaciones con solo 1 eje compatible se excluyen** de la generación — no hay covariable de
  ajuste posible, así que no calificaría como modelo multivariado.
- **`n_disponible` = `n` conjunto sobre el universo completo de covariables** (exposición principal
  + todas las de ajuste), no un `n` distinto por cada elección de exposición principal. Esto es
  válido porque el conjunto de variables que deben coexistir en el paciente es el mismo
  (exposición + ajuste = universo completo) sin importar cuál de ellas se declare "principal" —
  usar el `n` del universo completo como cota es correcto y consistente entre las variantes.
- **Consecuencia esperada y aceptada:** al exigir `n` conjunto en vez de marginal, es probable que
  salgan **menos candidatos que antes** — algunas celdas que hoy pasan `n_min=30` en bivariado no
  lo pasarán en conjunto. Es el comportamiento correcto del filtro de factibilidad, no un defecto.
- **Novedad de PubMed se mantiene simple**: sigue basada en `(subpoblación, eje_principal,
  outcome)`, no en cada combinación de covariables — la pregunta de novedad de literatura es sobre
  la hipótesis principal, no sobre el modelo de ajuste completo.

## 4. Cambios de arquitectura

### 4.1 `agents/perfilador.py` — ahora necesita conocer `Plantilla`

`perfilar(reader, plantilla)` cambia de firma (antes: `perfilar(reader)`). Necesita
`plantilla.compatibilidad` para saber, por cada subpoblación, cuál es su universo completo de ejes
compatibles.

Nueva lógica: para cada subpoblación declarada en `compatibilidad_eje_subpoblacion` con ≥2 ejes
compatibles, cuenta cuántas filas (pacientes) de esa subpoblación tienen
`_ejes_aplicables(fila) ⊇ universo_completo_de_esa_subpoblación` — es decir, dato presente
simultáneamente en **todos** los ejes de su universo, no solo en uno.

Esto reusa `_subpoblaciones(fila)` y `_ejes_aplicables(fila)` ya existentes; solo cambia el
predicado de conteo (intersección de todo el conjunto, no membresía en un solo eje).

**Garantía de privacidad sin cambios**: esta lógica opera sobre `filas_limpias` (post allow-list),
igual que `_n_por_celda` hoy — ningún dato nuevo ni PHI entra al cálculo.

### 4.2 `core/knowledge.py` — `Perfil` gana `n_conjunto`

Nuevo campo: `n_conjunto: dict[str, int]`, keyed por id de subpoblación → conteo de pacientes con
dato simultáneo en el universo completo de ejes compatibles con esa subpoblación.
`guardar_perfil`/`load_perfil` se extienden para serializar/deserializar este campo (dict simple
str→int, no requiere el truco de tuplas-a-lista-de-dicts que usa `n_por_celda`).

### 4.3 `agents/novelty_checker.py` — `Candidato` gana `covariables_ajuste`

```python
@dataclass(frozen=True)
class Candidato:
    eje: str                          # exposición principal
    subpoblacion: str
    outcome: str
    covariables_ajuste: tuple[str, ...]  # resto del universo compatible, ordenado determinísticamente
    n_disponible: int                 # n CONJUNTO (universo completo), no marginal
```

`candidato_id` incluye las covariables para mantener unicidad (dos candidatos con mismo
eje/subpoblación/outcome pero distinto universo de ajuste no deberían colisionar — aunque en la
práctica el universo es siempre el mismo para una subpoblación dada, así que esto es defensivo).

`_query` (construcción de query PubMed) **no cambia de comportamiento** — sigue usando solo
`eje`/`subpoblacion`/`outcome`, ignorando `covariables_ajuste`, por la decisión de la sección 3.

### 4.4 `agents/gap_finder.py` — `generar_espacio` reescrito

```python
def generar_espacio(p: Plantilla, perfil: Perfil) -> list[Candidato]:
    espacio = []
    for subpoblacion, ejes_validos in _ejes_compatibles_por_subpoblacion(p).items():
        if len(ejes_validos) < 2:
            continue  # sin covariable de ajuste posible, no es multivariado
        n_conjunto = perfil.n_conjunto.get(subpoblacion, 0)
        for eje_principal in sorted(ejes_validos):
            covariables = tuple(sorted(ejes_validos - {eje_principal}))
            for outcome in p.outcomes:
                espacio.append(Candidato(
                    eje=eje_principal, subpoblacion=subpoblacion, outcome=outcome,
                    covariables_ajuste=covariables, n_disponible=n_conjunto,
                ))
    return espacio
```

`_ejes_compatibles_por_subpoblacion` es una función nueva que invierte
`plantilla.compatibilidad` (hoy mapea eje→subpoblaciones válidas) a subpoblación→ejes válidos.

`filtrar_factibilidad` no cambia de lógica (sigue comparando `n_disponible >= p.n_min`); el
significado de `n_disponible` sí cambió (ahora es conjunto).

### 4.5 Prompt del LLM y renderizado

`_SYSTEM_RANKING` y `_prompt_candidato` (en `gap_finder.py`) se actualizan para mencionar
explícitamente que es un modelo **multivariado ajustado por covariables**, listando
`covariables_ajuste` en el prompt.

`ui_render.render_candidatos_md`/`render_candidatos_json` se extienden para mostrar
`covariables_ajuste` (lista legible en Markdown, array en JSON).

### 4.6 `orchestrator.py`

`run_perfilar` y `_cmd_perfilar` pasan a cargar la `Plantilla` (ya se hace en `run_propose`, se
replica aquí) y pasarla a `perfilar(reader, plantilla)`.

## 5. Testing

Actualización exhaustiva de fixtures y tests en `tests/test_perfilador.py` (nuevo cálculo de `n_conjunto`
con casos donde un paciente tiene dato parcial vs. completo del universo), `tests/test_knowledge.py`
(roundtrip de `Perfil.n_conjunto`), `tests/test_novelty_checker.py`/`tests/test_gap_finder.py`
(nueva forma de `Candidato`, exclusión de subpoblaciones con <2 ejes compatibles, un candidato por
cada eje-como-principal), `tests/test_ui_render.py` (covariables en el render),
`tests/test_orchestrator.py` (nueva firma de `perfilar`/`run_perfilar`).

## 6. Fuera de alcance

- No se valida (ni se intenta estimar) colinealidad entre covariables — eso es responsabilidad del
  estadístico al diseñar el modelo real, no de esta fase de generación de semillas.
- No se generan modelos con subconjuntos parciales de covariables (p. ej. "ajustado solo por A y
  B, no por C") — el universo de ajuste es siempre completo, por decisión de la sección 3.
- No cambia la garantía anti-PHI ni el flujo `perfilar` (local) / `propose` (nube) ya establecido.
