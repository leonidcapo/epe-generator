# EPE Seed Generator — Diseño (fase de semillas)

**Fecha:** 2026-07-24
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

App agéntica **nueva e independiente** que produce **semillas de ideas de investigación
primaria** a partir del perfil agregado de la cohorte **EPE** (Servicio de Pacientes
Especiales, Depto. de Odontoestomatología, Hospital Nacional PNP "Luis N. Sáenz").

Replica el **patrón metodológico y la arquitectura** de `endes-generator` (Sistema agéntico
que genera investigaciones desde microdatos ENDES), pero:

- **Alcance v1 = solo la fase de semillas** (equivalente a `propose` / Gap Finder de ENDES).
  Las fases posteriores (protocolo, análisis, informe) quedan para versiones futuras,
  igual que ENDES escalonó A✓ / B·C·D pendientes.
- **Fuente de datos = cohorte clínica propia (EPE)**, no una encuesta pública.

### Qué NO es (límites duros)

- **No toca `nucleo`** ni **`endes-generator`**. Es un proyecto separado, en carpeta propia.
- **No alimenta el motor de nucleo.** Es una fuente de *semillas*: una semilla que el
  usuario valide la lleva él, manualmente y ya formulada, a nucleo (para la revisión de
  literatura de respaldo) si así lo decide. EPE → idea → (opcional) nucleo. Nunca EPE
  *dentro* de nucleo.
- **No hace investigación secundaria de literatura.** Genera ideas de estudios *primarios*
  observacionales sobre la cohorte EPE.

## 2. Contexto y encuadre

| | ENDES Generator | Nucleo | **EPE Seed Generator (este proyecto)** |
|---|---|---|---|
| Insumo | Microdata pública ENDES | Una idea ya formulada | Perfil agregado de cohorte EPE (propia) |
| Naturaleza | Investigación primaria (2ª de datos) | Revisión sistemática de literatura | Investigación primaria (registro clínico) |
| Salida | Estudios end-to-end | Protocolo + Informe | **Semillas de ideas rankeadas** |

La cohorte EPE es **PHI real sin anonimizar** (ver memoria `project-hospital-pnp-odonto`).
Restricción de privacidad de primer orden en este diseño: **el generador de ideas nunca
consume filas individuales**; solo un **perfil agregado** (conteos, prevalencias, n por
celda) sin identificadores.

## 3. Diferencia estructural clave frente a ENDES: factibilidad determinista por `n`

ENDES valida la *existencia* de columnas contra un catálogo por año (`disponibilidad_ENDES.yaml`)
y depende de la novedad para podar. La validación del Gap Finder (memoria
`project-nucleo-gap-finder-validation`) midió que **la combinatoria sola produce ~65% de
basura**; el pipeline que funciona es de 3 filtros (API → poda LLM → PROSPERO).

EPE tiene una ventaja: el perfil agregado da el **`n` exacto por celda**. Por eso la
**factibilidad muestral** deja de ser una incógnita y se vuelve un **filtro determinista
fuerte**, aplicado *antes* del ranking LLM. Una semilla cuya celda (subpoblación × outcome ×
exposición) no alcanza un `n` mínimo se descarta de forma determinista, no por opinión del
LLM. Esto ataca directamente la fuente principal de "basura" de la combinatoria.

Principio heredado de ENDES: **el LLM propone, el código valida.** Deterministas:
no-causalidad, dedup, factibilidad de `n`. El LLM solo rankea y justifica en prosa que el
humano revisa.

## 4. Arquitectura

Estructura que espeja `endes-generator`:

```
epe-generator/
  agents/
    perfilador.py       # Drive (o .xlsx) → perfil agregado. NUNCA emite PHI.
    gap_finder.py       # espacio combinatorio → poda (novedad + factibilidad n) → ranking LLM → diversidad
    novelty_checker.py  # saturación de literatura vía conector PubMed
  core/
    knowledge.py        # carga de plantilla_epe.yaml, perfil_epe.yaml (dataclasses)
    llm_client.py       # cliente LLM (DeepSeek/Anthropic), degrada sin API key
    result.py           # AgentResult (success/degraded/failure) — patrón ENDES
  knowledge/
    plantilla_epe.yaml         # "ADN" metodológico de EPE (ejes, subpoblaciones, outcomes, diseño)
    perfil_epe.yaml            # GENERADO por `perfilar`: agregados sin PHI (cacheado)
  orchestrator.py        # comandos: perfilar | propose
  streamlit_app.py       # UI liviana (sin estado; expediente viaja en archivos)
  tests/                 # fixtures sintéticos; corre sin red / sin PHI / sin API key
  requirements.txt
  README.md
```

### Dos comandos (v1)

| Comando | Entrada | Proceso | Salida |
|---|---|---|---|
| `perfilar` | Google Sheet EPE (Drive, en vivo) | descarga vía conector → decodifica → agrega con `openpyxl`/`pandas` → escribe agregados | `knowledge/perfil_epe.yaml` |
| `propose` | `plantilla_epe.yaml` + `perfil_epe.yaml` | combinatoria → poda novedad+factibilidad → ranking LLM → selección diversa | `candidatos.md` + `candidatos.json` |

## 5. Componentes en detalle

### 5.1 `perfilador.py`
- **Entrada:** Google Sheet "Estadística EPE 2023-2026"
  (id `<EPE_SHEET_ID — ver .env local>`), leído **en vivo vía el conector de
  Google Drive** (`download_file_content` con `exportMimeType` de xlsx → base64 → `openpyxl`).
  **Fallback documentado (no descartado):** un `.xlsx` local descargado por el usuario.
- **Salida:** `perfil_epe.yaml` con **solo agregados**: por cada variable de interés,
  conteos y prevalencias; y `n` por celda para las combinaciones subpoblación × variable
  que el Gap Finder necesita para el filtro de factibilidad.
- **Garantía de privacidad:** ninguna fila individual, ningún identificador (DNI, nombre,
  celular, fecha de nacimiento) se escribe ni se pasa aguas abajo. El libro es **vivo**
  (el usuario lo edita) → `perfilar` siempre re-lee; nunca asume un snapshot viejo.

### 5.2 `plantilla_epe.yaml` — el "ADN" que define el espacio de ideas
- **Ejes temáticos** (derivados de las variables EPE): riesgo sistémico / ASA · tipo y
  severidad de discapacidad · morbilidad por sistema CIE-11 · polifarmacia / farmacoterapia ·
  cooperación y manejo conductual · procedencia / acceso · estado nutricional (IMC).
- **Subpoblaciones:** grupo etario · tipo de discapacidad · categoría ASA.
- **Outcomes plausibles:** nivel de tratamiento requerido · ubicación del procedimiento
  (consultorio vs SOP — conecta con el proyecto `predictor-quirofano-epe`) · grado de
  cooperación.
- **Diseño de estudio:** observacional analítico de registro clínico (prevalencias /
  asociaciones, RP Poisson cuando el outcome es binario). **Sin inferencia causal** — el
  código rechaza toda semilla con formulación causal (igual que ENDES).
- **Compatibilidad:** qué subpoblaciones/outcomes son válidos por eje (evita combinaciones
  sin sentido clínico), espejando `compatibilidad` de la plantilla ENDES.

### 5.3 `gap_finder.py` (mirror del de ENDES)
1. `generar_espacio(plantilla)`: producto eje × subpoblación × outcome filtrado por
   `compatibilidad`.
2. **Poda determinista:**
   - **Factibilidad:** descarta celdas con `n < n_min` según `perfil_epe.yaml`.
   - **Novedad:** `novelty_checker` (ver 5.4); descarta las de saturación de literatura
     por encima de un umbral.
3. `rankear(...)`: por cada superviviente, el LLM devuelve `{"score": 0-10, "justificacion":
   "..."}`. **Degrada sin crashear**: sin API key / fallo de parseo → ordena por novedad y
   marca `score_llm=None` (patrón `AgentResult.degraded`).
4. Selección **diversa** con tope por eje (evita que el top se llene de un solo eje).

### 5.4 `novelty_checker.py` — saturación de literatura vía PubMed
- Para cada semilla (subpoblación × outcome × exposición), construye una query y consulta
  el **conector PubMed** (`search_articles` / `get_article_metadata`).
- Estima **saturación**: muchos resultados directamente on-topic → poca novedad (score
  bajo); vacío o escasez → alta novedad. La heurística exacta (conteo, filtros, ventana de
  años) se afina en implementación.
- **Degrada:** si PubMed no está disponible, emite advertencia y asigna novedad neutra en
  vez de fallar (principio "degrada, no muere").

### 5.5 Salida — cada semilla trae
`eje` · `subpoblación` · `outcome` propuesto · `exposición`/covariables candidatas ·
**`n` disponible** (del perfil) · diseño sugerido · `score_novedad` (saturación PubMed) ·
`score_llm` + `justificacion`. Formato doble: `candidatos.md` (legible) + `candidatos.json`
(máquina, para un futuro `design`).

## 6. Manejo de datos y privacidad (resumen)
- El **único** punto que toca PHI es `perfilar`, y su salida ya es agregada.
- `propose`, `gap_finder`, `novelty_checker` operan **solo** sobre `perfil_epe.yaml` +
  literatura pública (PubMed). Nunca ven PHI.
- Los agregados (`perfil_epe.yaml`) **no** deben permitir reidentificación: celdas con `n`
  muy pequeño se marcan/suprimen (regla de `n_min` sirve doble propósito: factibilidad +
  privacidad).
- Nada de PHI a git.

## 7. Degradación (heredada de ENDES)
Sin API key del LLM → `propose` rankea por novedad. Sin PubMed → novedad neutra. Sin acceso
al Drive → usa `.xlsx` local si existe, si no, error claro en `perfilar` (no en `propose`).

## 8. Testing
Suite `pytest` con **fixtures sintéticos** (perfil EPE ficticio, respuestas PubMed/LLM
mockeadas): corre **sin red, sin PHI, sin API keys**. Cubre lógica pura: `generar_espacio`,
poda por factibilidad, poda por novedad, degradación del ranking, selección diversa,
no-causalidad, y que `perfilar` nunca emita campos identificadores.

## 9. Fuera de alcance (v1)
- Fases `design` / `analyze` / `report` (protocolo, datos, informe).
- Escritura de vuelta al Drive.
- Cualquier integración con nucleo o endes-generator.
- Descarga automática de datos por parte del sistema (la lectura del Drive es explícita en
  `perfilar`).

## 10. Decisiones abiertas para el plan de implementación
- Heurística exacta de saturación PubMed (umbral, ventana de años, campos de query).
- Valor de `n_min` (factibilidad + supresión por privacidad).
- Lista concreta de variables EPE que entran al perfil y a la `plantilla_epe.yaml`
  (se derivan de las 42 columnas del Marco + DxSistémicos/CIE-11 ya mapeados).
- Proveedor LLM por defecto (DeepSeek vs Anthropic) y si se reusa el `.env` de otros proyectos.
