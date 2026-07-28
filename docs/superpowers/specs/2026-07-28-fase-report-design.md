# Fase `report` (Informe Final) — Diseño

**Fecha:** 2026-07-28
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

Cerrar el ciclo de 4 fases de `epe-generator`, espejando `endes-generator`: `propose` →
`design` → `analyze` → **`report`** (esta fase). `report` ingiere `resultados.xlsx` (que
el estadístico produjo corriendo el `analisis.do` de la fase `analyze`), y produce
**`articulo.md`**: el informe final completo (ex post), con la sección de Resultados
generada de forma 100% determinista desde las tablas reales (imposible inventar una cifra
por construcción), y Discusión/Conclusiones/Recomendaciones/Resumen redactadas por LLM en
pasado, auditadas contra lenguaje causal y contra cifras no verificables.

## 2. Alcance

- **Solo CLI**: `python orchestrator.py report <candidato_id> <ruta_resultados_xlsx>`. Sin
  cambios en `streamlit_app.py`.
- **Sin "expediente"**: como ya se decidió en `analyze`, no existe un `estudio.json` que
  trackee el estado multi-fase — la ruta a `resultados.xlsx` se pasa explícitamente como
  argumento del CLI.
- **Salida**: solo `articulo.md` (texto plano). Sin `.docx` en esta entrega — a diferencia
  de `design`, que sí generó `.docx` porque el protocolo es el entregable ex ante formal;
  el informe final puede añadir `.docx` en una iteración futura si se pide.
- **Fuera de alcance**: corpus de estudios previos / citas Vancouver a un corpus fijo
  (EPE no tiene un equivalente al `estudios_previos.json` de 13 estudios que indexa
  ENDES — la Discusión contrasta con la literatura de forma general, sin citas numeradas
  a un corpus mantenido), corrección determinista de tiempos verbales, ejecutar Stata,
  integración en `streamlit_app.py`.

## 3. Decisión: reuso de las secciones ex ante de `design`

El informe final es el **artículo completo**: reconstruye el protocolo (introducción,
marco teórico, objetivos, hipótesis, métodos — mismas 5 secciones de `design`) llamando de
nuevo a `disenar_protocolo(candidato, plantilla, limitaciones, llm_client)`, exactamente
igual que `analyze` ya recalcula `build_estructura` sin depender de que `design` se haya
corrido antes ni de un `protocolo.json` persistido. `report` añade las secciones ex post
(Resultados, Discusión, Conclusiones, Recomendaciones, Resumen) a continuación.

**Limitación conocida y aceptada:** la prosa reusada de `disenar_protocolo` se redactó en
tiempo **futuro** (como corresponde a un protocolo ex ante); el informe final la reutiliza
tal cual, sin convertirla a pasado. `endes-generator` tiene la misma limitación (nunca
implementó conversión de tiempos verbales entre protocolo e informe) y no se resuelve
aquí — `nucleo` sí tiene un `utils/tense_corrector.py` para este problema, pero es una
herramienta de otro proyecto que no se reimporta ni se reimplementa en esta entrega
(fuera de alcance explícito).

## 4. Decisión: sin corpus de estudios previos

A diferencia de `endes-generator` (cuya Discusión cita `[n]` contra un corpus fijo de 13
estudios indexados en `knowledge/estudios_previos.json`), `report` en EPE **no** construye
ni mantiene un corpus de literatura previa. El prompt de la sección Discusión pide
contraste general con la literatura (sin instrucción de citar `[n]` a una lista numerada).
No hay `estudios_relevantes`/`ensamblar_referencias`/sección "Referencias" en el
`articulo.md` de EPE.

## 5. Componentes

### 5.1 `agents/number_guard.py` (nuevo, reimplementado — no importa de `endes-generator`)

Puerto directo del mecanismo anti-invención numérica: extrae el conjunto de cifras
legítimas de las tablas parseadas (`efecto`/`ic_inf`/`ic_sup` redondeados a 2 decimales;
`p` sin redondear, validado por umbral/igualdad tipada) y escanea la prosa LLM en busca de
números que no pertenezcan a ese conjunto ni a un conjunto de "estructurales" (conteos
verificables del propio estudio — nº de covariables, nº de términos bivariados) ni a
convenciones del discurso estadístico (`0.05` de significancia, `100` como total
porcentual). Citas Vancouver `[n]` se excluyen del escaneo por completo (no aplica aquí al
no haber citas, pero se mantiene el mecanismo por si el usuario decide añadir citas más
adelante).

**Diferencia deliberada con `endes-generator`:** el conjunto de "estructurales por
defecto" de EPE **no** incluye rangos de años (2015-2025) ni límites etarios específicos
de los grupos poblacionales ENDES — esos hechos no aplican a la cohorte EPE y no deben
inventarse sin una fuente real. `ESTRUCTURALES_DEFAULT_EPE = frozenset({0.05, 100.0})`
únicamente.

Funciones: `numeros_legitimos(tablas: dict) -> set[float]`, `p_legitimos(tablas: dict) ->
set[float]`, `estructurales_estudio(candidato, protocolo_variables, tablas) -> set[float]`,
`verificar_numeros(texto: str, legitimos: set[float], estructurales: set[float] =
frozenset(), p_leg: set[float] = frozenset()) -> list[str]`.

### 5.2 `agents/executor.py` (nuevo, reimplementado)

`parsear_resultados(xlsx_path: str) -> AgentResult`: lee `resultados.xlsx` con
`openpyxl`. Hojas obligatorias: `descriptivos`, `modelo` (según lo que `analyze` ya
genera vía `putexcel`); hojas `bivariado_<covariable>` descubiertas por prefijo, opcionales
(si faltan o vienen mal formadas, se omiten con aviso, sin bloquear el resto). Filas
requeridas por hoja: `b`, `ll`, `ul` (más `pvalue` si existe, opcional). Hoja
faltante, fila requerida faltante, o celda no numérica donde se espera un número →
`AgentResult.failure` nombrando exactamente qué falta — **nunca** resultados parciales
silenciosos. Mismo parser genérico de fila/columna que `endes-generator` (no depende del
comando Stata específico — funciona igual para `mean`/`ologit`/`mlogit`/`logistic`/
`regress`, ya que todos escriben con la misma convención `putexcel A1 =
matrix(r(table)), names`).

### 5.3 `agents/writer.py` (nuevo)

- **`redactar_resultados(tablas: dict) -> str`** — determinista, cero LLM: itera los
  términos de la tabla `modelo` (excluye `_cons`) y emite una línea por término con
  efecto + IC95% (+ p si existe); si hay bivariado, añade una subsección "Análisis
  bivariado" con las proporciones/medias por categoría.
- **`redactar_articulo(candidato, plantilla, tablas, limitaciones, llm_client) ->
  AgentResult`**: llama `disenar_protocolo` para obtener el protocolo (picot, variables,
  diseño, prosa ex ante, limitaciones); llama `redactar_resultados(tablas)` para la
  sección determinista; genera Discusión/Conclusiones/Recomendaciones/Resumen sección por
  sección vía LLM (prompt en pasado, sin lenguaje causal, sin instrucción de citar un
  corpus), auditando cada sección con `number_guard.verificar_numeros` (cifra no
  verificable → sección marcada `[sección pendiente: cifra no verificable]`, con aviso) y
  el texto completo con `agents.bias_auditor.auditar` (reusa el mismo motor de `design`,
  igual catálogo `limitaciones_epe.yaml`). Degrada a `[pendiente: LLM no disponible]` por
  sección si `llm_client` es `None` o falla, sin crashear — mismo patrón de
  `disenar_protocolo`.
- Dataclass `Articulo(candidato_id: str, resultados: str, prosa_ante: dict, prosa_post:
  dict, limitaciones: list[str], warnings: list[str])` — separa explícitamente la prosa
  reusada de `design` (`prosa_ante`, en futuro) de la nueva prosa ex post
  (`prosa_post`, en pasado), para que el renderer pueda etiquetarlas sin ambigüedad y para
  que la limitación de tiempos verbales (§3) quede documentada en el propio dato, no solo
  en un comentario.

### 5.4 `ui_render.py` — `render_articulo_md`

`render_articulo_md(articulo: Articulo) -> str`: título, secciones ex ante (PICOT +
introducción/marco/objetivos/hipótesis/métodos — mismo contenido y orden que
`render_protocolo_md`), luego Resultados (determinista), luego
Discusión/Conclusiones/Recomendaciones/Resumen, luego Limitaciones, luego avisos de
auditoría si los hay. Sin sección "Referencias" (§4).

### 5.5 `orchestrator.py` — comando `report <id> <ruta_xlsx>`

Localiza el candidato con el `_localizar_candidato` ya compartido (de `analyze`), carga
`plantilla_epe.yaml` + `limitaciones_epe.yaml`, parsea `resultados.xlsx` con
`agents.executor.parsear_resultados` (si falla, el comando falla con el mismo mensaje),
llama `redactar_articulo`, escribe `articulo.md` en un nuevo `outputs/<run_id>/`.

## 6. Testing

- `number_guard`: cifras legítimas/ilegítimas, p-valores (igualdad/umbral), estructurales
  EPE (0.05/100, conteos reales del estudio) — sin los casos ENDES-específicos (años,
  límites etarios).
- `executor`: fixtures `resultados.xlsx` sintéticas (`openpyxl`) — parseo feliz, hoja
  faltante, fila requerida faltante, celda no numérica, bivariado mal formado (se omite
  con aviso sin bloquear).
- `writer`: `redactar_resultados` determinista (tablas → prosa de resultados exacta);
  `redactar_articulo` con `FakeLLMClient` (éxito, degradación sin LLM, cifra inventada
  detectada y marcada pendiente, lenguaje causal detectado).
- `orchestrator.run_report`/`_cmd_report`: end-to-end con `candidatos.json` sintético +
  `resultados.xlsx` sintético.
- Suite completa sin Stata, sin red, sin API keys.

## 7. Fuera de alcance

- Corpus de estudios previos / citas Vancouver numeradas.
- `.docx` para el informe final.
- Corrección determinista de tiempos verbales (prosa ex ante queda en futuro, limitación
  documentada — §3).
- Ejecutar Stata automáticamente.
- Un "expediente" de estudio multi-fase (`estudio.json`).
- Integración en `streamlit_app.py`.
