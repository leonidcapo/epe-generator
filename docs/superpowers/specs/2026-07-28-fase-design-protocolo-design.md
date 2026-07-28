# Fase `design` (Protocolo) — Diseño

**Fecha:** 2026-07-28
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

Añadir la segunda fase del ciclo de `epe-generator`, espejando `endes-generator`:
`propose` (ya implementado) → **`design`** (esta fase) → `analyze` → `report` (futuras).

`design` toma un candidato ya generado por `propose` (identificado por su `id` en
`candidatos.json`) y produce un **protocolo de investigación ex ante**: PICOT, tabla de
variables, diseño estadístico (modelo elegido según el mecanismo generador del outcome),
prosa académica en futuro (introducción, marco teórico, objetivos, hipótesis, métodos), y
una sección de limitaciones metodológicas auditada automáticamente.

## 2. Alcance

- **Solo CLI**: `python orchestrator.py design <candidato_id>`. Sin cambios en
  `streamlit_app.py` en esta entrega.
- **Salida**: `protocolo.md` + `protocolo.docx` (nueva dependencia `python-docx`).
- **Fuera de alcance**: `analyze`/`report` (fases futuras, cada una con su propio ciclo
  spec→plan→implementación).

## 3. Corrección de datos encontrada durante el diseño

El outcome `ubicacion_procedimiento_sop_vs_consultorio` estaba declarado como `binario`
(Consultorio vs. SOP), pero la cohorte real registra **3 categorías**: Consultorio, SOP,
Hospitalización. Se renombra a **`ubicacion_procedimiento`** (el sufijo `_sop_vs_consultorio`
ya no describe el dato real) y se reclasifica como `categorico`/`nominal` (sin orden natural
entre las 3 ubicaciones, confirmado por el usuario). Verificado: ningún test ni código de
producción referencia el id viejo fuera de `plantilla_epe.yaml`, así que el renombrado no
tiene efectos colaterales.

**Consecuencia**: con este cambio, la plantilla actual **no tiene ningún outcome binario**.
El código de `design` debe seguir siendo capaz de manejar un outcome binario en el futuro
(vía el árbol de decisión de la sección 5), pero no se fuerza ninguna declaración
`medida_asociacion` (OR/RP) en la plantilla hoy — eso se agrega cuando exista un outcome
binario real (YAGNI).

## 4. Metadata nueva en `knowledge/plantilla_epe.yaml`

Cada outcome gana un campo `escala` (solo aplica a `tipo: categorico`), decidido caso por
caso con el usuario, no por una regla genérica:

```yaml
outcomes:
  - {id: nivel_tratamiento_requerido, tipo: categorico, escala: ordinal}
  - {id: ubicacion_procedimiento, tipo: categorico, escala: nominal}
  - {id: grado_cooperacion, tipo: categorico, escala: nominal}
```

- `nivel_tratamiento_requerido` → **ordinal** (existe una escalada natural de complejidad
  de tratamiento) → regresión logística **ordinal**.
- `ubicacion_procedimiento` → **nominal** (3 categorías sin jerarquía clara) → regresión
  logística **multinomial**.
- `grado_cooperacion` → **nominal** (valores como Positivo/Negativo/Def.Positivo/
  Def.Negativo, sin orden claro) → regresión logística **multinomial**.

## 5. Selección de modelo (árbol de decisión, ref. memoria Rosana Ferrero)

A diferencia de `endes-generator` (que infiere `outcome_tipo` por nombre de eje hardcodeado
en código), EPE **lee `tipo`/`escala` directamente de `Plantilla.outcomes`**, ya declarados
en el YAML — más simple y sin lógica de inferencia frágil.

| `tipo` | `escala` | Modelo |
|---|---|---|
| `categorico` | `ordinal` | Regresión logística ordinal (odds proporcionales) |
| `categorico` | `nominal` | Regresión logística multinomial |
| `binario` | (futuro: `medida_asociacion: OR`\|`RP`) | Logística estándar (OR) o Poisson robusto (RP) |
| `continuo` | — | Modelo lineal (LM) |

Ningún outcome de la plantilla actual es `binario`/`continuo`; el código soporta esas ramas
para cuando se agregue un outcome de ese tipo, sin necesidad de refactorizar.

## 6. Componentes

### 6.1 `agents/protocol_designer.py` (nuevo)

```python
@dataclass
class Protocolo:
    candidato_id: str
    picot: dict
    variables: list[dict]
    diseno: dict
    prosa: dict = field(default_factory=dict)
    limitaciones: list[str] = field(default_factory=list)
    warnings_auditoria: list[str] = field(default_factory=list)
```

- `build_picot(c: Candidato) -> dict`: `poblacion=c.subpoblacion`, `exposicion=c.eje`,
  `covariables=c.covariables_ajuste`, `comparador="categorías de referencia de las
  covariables"`, `outcome=c.outcome`, `tiempo="transversal (sin seguimiento)"`.
- `build_variables(c, p) -> list[dict]`: outcome (rol=`outcome`, tipo/escala de
  `p.outcomes`/`p.outcomes_escala`), exposición principal (rol=`exposicion_principal`),
  cada covariable de `c.covariables_ajuste` (rol=`covariable`).
- `inferir_modelo(tipo: str, escala: str | None) -> tuple[str, list[str]]`: implementa la
  tabla de la sección 5. Devuelve `(nombre_modelo, anclajes_citables)`.
- `_generar_prosa`: mismas 5 secciones que ENDES (`introduccion, marco_teorico, objetivos,
  hipotesis, metodos`), mismo `_SYSTEM_PROTOCOLO` (futuro, sin lenguaje causal), degrada a
  `[prosa pendiente: LLM no disponible]` sin crashear.
- `disenar_protocolo(candidato, plantilla, limitaciones, llm_client) -> AgentResult`.

### 6.2 `agents/bias_auditor.py` (nuevo, puerto directo de la lógica de ENDES)

Mismo mecanismo (`Limitacion`, `load_limitaciones`, `limitaciones_aplicables`,
`condicion_aplica`, escaneo de lenguaje causal en 2 niveles — regex + verificación LLM por
oración). Solo cambia el **catálogo** (`knowledge/limitaciones_epe.yaml`), específico al
contexto de EPE: registro clínico de un único hospital (no muestra probabilística
poblacional), dependencia de datos ya recolectados (Sigesapol/registro clínico, no control
del investigador sobre la captura original), ausencia de causalidad (rechaza lenguaje causal
— aplica siempre, igual que ENDES), variables limitadas al registro clínico disponible,
completitud/calidad de registro (recordar el bug de `#DIV/0!` en IMC y "Jóven" sin mapear ya
detectados en esta cohorte).

### 6.3 `ui_render.py` — `render_protocolo_md` + `render_protocolo_docx`

Mismo patrón que ENDES: Markdown legible + `.docx` vía `python-docx` (`Document`,
`add_heading`, tabla de variables, párrafos de prosa por sección, limitaciones).
`render_protocolo_docx` no re-parsea el `.md`, construye desde el mismo `Protocolo` objeto.

### 6.4 `orchestrator.py` — comando `design <id>`

Lee `candidatos.json` (busca el `.json` más reciente en `outputs/`, mismo patrón que ENDES),
localiza el candidato por `id` (`candidato_id()` ya existe en `novelty_checker.py`), llama
`disenar_protocolo`, escribe `protocolo.md` y `protocolo.docx` en el mismo directorio de
`outputs/<timestamp>/`.

## 7. Testing

Suite ampliada cubriendo: `inferir_modelo` para las 3 combinaciones reales
(ordinal/nominal/nominal) más al menos un caso hipotético binario/continuo (para no dejar
esas ramas sin probar aunque no haya outcome real de ese tipo hoy); `build_picot`/
`build_variables` con un candidato multivariado real (2+ covariables); degradación de prosa
sin LLM; auditor de sesgos con el catálogo EPE (causal-language siempre aplica; al menos una
limitación condicional específica de EPE); roundtrip de `render_protocolo_md`/
`render_protocolo_docx`; comando `design` end-to-end con un `candidatos.json` sintético.

## 8. Fuera de alcance

- Fases `analyze`/`report`.
- Integración en `streamlit_app.py`.
- Declarar `medida_asociacion` (OR/RP) para un outcome binario — no existe ninguno hoy.
- Cualquier cambio a `perfilador.py`/`gap_finder.py`/el modelo `Candidato` (ya estables).
