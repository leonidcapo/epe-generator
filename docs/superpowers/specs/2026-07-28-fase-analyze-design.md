# Fase `analyze` (Sintaxis Stata) — Diseño

**Fecha:** 2026-07-28
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

Añadir la tercera fase del ciclo de `epe-generator`, espejando `endes-generator`:
`propose` → `design` (completas) → **`analyze`** (esta fase) → `report` (futura, fuera de
alcance).

`analyze` toma un candidato ya generado por `propose` (identificado por su `id` en
`candidatos.json`) y produce **`analisis.do`**: la sintaxis Stata determinista (sin LLM)
que el estadístico corre manualmente sobre su propio dataset para obtener los resultados
del estudio.

## 2. Restricción de PHI (decisión central de esta fase)

A diferencia de `endes-generator` (cuyos microdatos ENDES son públicos y su fase C exporta
un `datos.dta` fila-por-fila), en `epe-generator` **ningún módulo salvo
`agents/perfilador.py` puede tocar filas reales de pacientes**, y `perfilador.py` hoy solo
produce un perfil agregado (conteos), nunca un dataset fila-por-fila. Esta fase **no**
añade ninguna capacidad de exportar datos reales.

**Decisión:** `analyze` genera únicamente el texto del `.do` (sintaxis Stata). El
estadístico exporta su propio `datos.dta` directamente desde el Sheet (o su fuente),
usando exactamente los nombres de columna que aparecen como ids en `plantilla_epe.yaml`
(ejes/outcomes ya son identificadores válidos de Stata — snake_case, sin caracteres
especiales). `epe-generator` sigue sin tocar PHI en ningún punto de esta fase.

## 3. Alcance

- **Solo CLI**: `python orchestrator.py analyze <candidato_id>`. Sin cambios en
  `streamlit_app.py`.
- **Salida**: `analisis.do` (texto plano, sin biblioteca nueva).
- **Fuera de alcance**: fase `report` (executor/writer, number-guard, comparación con
  estudios previos), ejecutar Stata automáticamente (subprocess/batch), exportar
  `datos.dta`, un "expediente" de estudio (`estudio.json`) que trackee el estado
  multi-fase — cada fase de `epe-generator` sigue escribiendo a su propio
  `outputs/<timestamp>/`, como `propose` y `design` ya hacen.

## 4. Fuente de las variables/modelo (decisión)

`analyze` **no depende de que `design` se haya corrido antes** ni de un artefacto
`protocolo.json` nuevo. En su lugar, recalcula el mismo resultado que `design` produciría
llamando directamente a las funciones puras ya existentes en `agents/protocol_designer.py`:
`build_estructura(candidato, plantilla) -> dict` (que internamente llama a
`build_variables`/`inferir_modelo`). Esto es determinista — mismas entradas, misma salida
— así que no hay riesgo de que `analyze` y `design` diverjan sobre qué modelo corresponde
al outcome.

Flujo: localizar el candidato por `id` en el `candidatos.json` más reciente bajo
`outputs/` (mismo patrón de búsqueda que `design`, incluyendo mismo mensaje de error si no
hay `candidatos.json` o si el id no aparece) → reconstruir `Candidato` → llamar
`build_estructura` → generar el `.do` → escribirlo en `outputs/<run_id>/analisis.do`.

## 5. Mapeo de modelo → comando Stata

Sin `svy:` (EPE no tiene diseño muestral complejo — no hay peso/estrato/PSU, es un
registro clínico de un solo hospital, no una encuesta con muestreo complejo):

| `diseno['modelo']` (de `protocol_designer.py`) | Comando Stata |
|---|---|
| `logistica_ordinal` | `ologit` |
| `logistica_multinomial` | `mlogit` |
| `logistica_binaria` | `logistic` |
| `lineal` | `regress` |

Ningún modelo usa anclajes citables inventados — `build_estructura`'s `diseno['anclajes']`
ya viene vacío desde la fase `design` (decisión previa: no fabricar citas sin referencia
real) y `analyze` no le agrega ninguna.

## 6. Estructura del `.do` (3 bloques)

Nuevo módulo `agents/statistician.py` (nombre espeja el de `endes-generator`), función pura
sin LLM: `generar_do(candidato: Candidato, plantilla: Plantilla) -> str`.

1. **Encabezado** (comentarios `*`): candidato_id, fecha de generación, eje (exposición
   principal), subpoblación, outcome, covariables de ajuste, modelo elegido. Incluye un
   comentario placeholder — **no** sintaxis ejecutable, porque el criterio real de cada
   subpoblación no está codificado en ningún archivo hoy, solo como concepto clínico:
   ```stata
   * filtrar a subpoblación: asa3_alto_riesgo (definir criterio real con el estadístico)
   ```
2. **Descriptivos + bivariado**: `summarize`/`tabulate` de outcome y cada covariable
   (descriptivos), y outcome × cada covariable categórica (bivariado) — sin `svy:`. Cada
   bloque exporta a una hoja fija de `resultados.xlsx` vía `putexcel` (mismo patrón de
   contrato de vuelta que `endes-generator`: hojas de nombre fijo, ej. `descriptivos`,
   `bivariado_<covariable>`, `modelo`).
3. **Modelo**: el comando de la tabla §5 con `outcome exposicion_principal covariables`,
   exportado a su propia hoja `modelo` vía `putexcel`.

`use "datos.dta", clear` al inicio, asumiendo que el estadístico ya exportó el archivo con
los nombres de columna correctos (mismos ids que en la plantilla).

## 7. Integración en `orchestrator.py`

Nuevo comando `analyze <id>`, mismo patrón que `design <id>`: busca el `candidatos.json`
más reciente, localiza el candidato, llama `generar_do`, escribe
`outputs/<run_id>/analisis.do`. Reutiliza la función de búsqueda de candidato ya existente
(`_candidato_desde_json`/lookup por id, actualmente privada a `run_design` — se extrae a
una función compartida si evita duplicación real, sin sobre-diseñar una abstracción para
un único caso de uso adicional).

## 8. Testing

- Generación del `.do`: texto determinista → asserts de bloques clave (encabezado con
  candidato_id, comando de modelo correcto por cada uno de los 4 tipos, bloques
  descriptivos/bivariado presentes, nombres de hoja `putexcel` correctos, comentario de
  filtro de subpoblación presente).
- `orchestrator.analyze <id>` end-to-end con un `candidatos.json` sintético (mismo patrón
  que los tests existentes de `run_design`/`_cmd_design`).
- Suite completa sin Stata, sin red, sin API keys (no hay LLM en esta fase — es 100%
  determinista).

## 9. Fuera de alcance

- Fase `report` (executor/writer, number-guard, comparación con estudios previos vía
  `novelty_checker`).
- Ejecutar Stata automáticamente.
- Exportar `datos.dta` o cualquier dato real — decisión central de la §2.
- Codificar el criterio real de cada subpoblación en la plantilla (queda como comentario
  placeholder; formalizarlo es una mejora futura explícita, no parte de esta fase).
- Un "expediente" de estudio multi-fase (`estudio.json`) — cada fase sigue escribiendo su
  propio `outputs/<timestamp>/` independiente.
- Integración en `streamlit_app.py`.
