# Extensión Streamlit — design / analyze / report — Diseño

**Fecha:** 2026-07-28
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

`streamlit_app.py` hoy solo expone la fase `propose` en la nube (`design`/`analyze`/
`report` son CLI-only desde que se implementaron — no por una restricción de PHI, sino
porque no estaban en alcance en ese momento). Esta entrega agrega las 3 fases restantes a
la app desplegada, cerrando el ciclo completo de 4 fases en Streamlit Community Cloud.

## 2. Alcance

- Agrega 3 vistas nuevas a `streamlit_app.py`: Design, Analyze, Report — junto a la vista
  `Propose` ya existente.
- Navegación: `st.sidebar.radio` con las 4 opciones, cada una su propia función de vista
  (mismo patrón que `vista_propose` ya usa — nada de routing/URL, todo en un solo archivo).
- Mismo patrón subir→generar→descargar que `propose` para las 3 vistas nuevas: sin estado
  compartido en el servidor entre sesiones, todo vive en `st.session_state` de la sesión
  actual o se descarga inmediatamente.
- **Sin restricción de PHI**: ninguna de las 3 fases nuevas toca el Sheet ni datos de
  pacientes — igual que `propose`, operan sobre `candidatos.json` (ya agregado y sin PHI) y
  archivos que el usuario sube (`resultados.xlsx` para `report`, que solo contiene
  estadísticas agregadas del modelo, nunca filas de pacientes).
- Sin secrets nuevos: las 6 claves ya whitelisteadas en `_SECRET_KEYS`
  (`LLM_PROVIDER`/`DEEPSEEK_API_KEY`/`DEEPSEEK_MODEL`/`PUBMED_API_KEY`/`AUTH_USER`/
  `AUTH_PASSWORD`) alcanzan — `design`/`report` reusan `DEEPSEEK_API_KEY` vía el mismo
  `_cliente_llm_o_none()`; `analyze` no necesita LLM en absoluto.

## 3. Decisión: aislar la búsqueda de candidato de `outputs/`

`run_design`/`run_analyze`/`run_report` (en `orchestrator.py`) hoy localizan el candidato
leyendo el `candidatos.json` **más reciente** bajo `outputs/*/` — un contrato pensado para
el CLI (cada corrida de `propose` escribe ahí, y las corridas siguientes de `design`/
`analyze`/`report` lo recogen). Si Streamlit reusara ese mismo contrato (escribiendo el
archivo subido a un `outputs/<tmp>/` antes de llamar a `run_design`, etc.), dos usuarios
simultáneos en una instancia compartida de Streamlit Community Cloud podrían pisarse: la
búsqueda siempre toma el archivo más reciente sin importar qué sesión lo escribió.

**Decisión:** `_localizar_candidato`, `run_design`, `run_analyze`, `run_report` ganan un
parámetro opcional `candidatos_json_path: str | None = None`:
- Si se pasa, se lee esa ruta **directamente** (sin tocar `outputs/` en absoluto) — así usa
  Streamlit, escribiendo el archivo subido a un `tempfile` propio de la sesión, fuera de
  cualquier directorio compartido.
- Si se omite (`None`), el comportamiento es **exactamente el actual**: buscar el
  `candidatos.json` más reciente en `outputs/*/`. El CLI (`orchestrator.py design <id>`,
  etc.) sigue funcionando sin cambios — no pasa este parámetro.

Cambio 100% aditivo en `orchestrator.py`: ningún test ni comportamiento existente cambia.

## 4. Vistas nuevas

Cada vista sigue el patrón exacto de `vista_propose`: `st.file_uploader` → validar →
botón → guardar resultado en `st.session_state` → renderizar + `st.download_button`(s).

### 4.1 Vista Design

1. `st.file_uploader("Sube candidatos.json", type=["json"])`.
2. Parsear el JSON subido (lista de dicts con `id`/`eje`/`subpoblacion`/`outcome`/
   `covariables_ajuste`/`n_disponible`/`novedad`/`score_llm` — el mismo formato que
   `render_candidatos_json` ya produce). Si el JSON no es válido o no tiene esa forma,
   `st.error` y no continuar.
3. `st.selectbox` con una etiqueta legible por candidato (ej. `"{eje} × {subpoblacion} →
   {outcome} ({id})"`), value = el `id`.
4. Botón "Generar protocolo": escribe el JSON subido a un archivo temporal propio de la
   sesión, llama `run_design(id_elegido, candidatos_json_path=ruta_temporal)` con el
   mismo `_cliente_llm_o_none()` ya usado en `propose` (si es `None`, `disenar_protocolo`
   ya degrada solo — no hace falta el `FakeLLMClient` de respaldo que usa `propose`, ya que
   `design` no depende de que el LLM funcione para producir un resultado usable).
5. Resultado en `st.session_state`: renderiza `render_protocolo_md` en pantalla, ofrece
   `st.download_button` para `protocolo.md` y otro para `protocolo.docx`
   (`render_protocolo_docx`).

### 4.2 Vista Analyze

1. Mismo `file_uploader` de `candidatos.json` + mismo selector de candidato.
2. Botón "Generar análisis": `run_analyze(id_elegido, candidatos_json_path=ruta_temporal)`
   — sin LLM, sin cliente PubMed, 100% determinista.
3. Renderiza el `.do` en un bloque de código (`st.code(..., language="stata")` si
   Streamlit lo soporta, o texto plano) + `st.download_button` para `analisis.do`.

### 4.3 Vista Report

1. Dos `file_uploader`: `candidatos.json` + `resultados.xlsx` (`type=["xlsx"]`).
2. Mismo selector de candidato (parseado del `candidatos.json` subido).
3. Botón "Generar informe": ambos archivos subidos se escriben a rutas temporales de la
   sesión; `run_report(id_elegido, ruta_resultados_temporal,
   candidatos_json_path=ruta_candidatos_temporal)` con el mismo `_cliente_llm_o_none()`.
4. Renderiza `render_articulo_md` en pantalla + `st.download_button` para `articulo.md`.
   Sin `.docx` (el informe final solo tiene `.md`, decisión ya tomada en el spec de
   `report`).

## 5. Testing

- `orchestrator.py`: tests nuevos/actualizados confirmando que
  `run_design`/`run_analyze`/`run_report` con `candidatos_json_path` explícito leen esa
  ruta y NO tocan `outputs/` en absoluto (ej. correr sin que exista ningún
  `outputs/*/candidatos.json` y confirmar que igual funciona); y que omitiendo el
  parámetro el comportamiento CLI existente (glob sobre `outputs/`) sigue intacto —
  ningún test de `test_run_design_*`/`test_run_analyze_*`/`test_run_report_*` existente
  debe cambiar.
- `streamlit_app.py` no tiene tests unitarios hoy (es UI de Streamlit, fuera del patrón
  "lógica pura testeable" del proyecto — mismo criterio que ya se aplicó a `vista_propose`,
  que tampoco tiene tests dedicados). Verificación manual con `streamlit run
  streamlit_app.py` local antes de desplegar.

## 6. Fuera de alcance

- Persistencia de estado entre fases dentro de una misma sesión (ej. pasar directo de
  `propose` a `design` sin re-subir el JSON) — cada vista es independiente, subir/generar/
  descargar, igual que `propose` hoy.
- Cambios al modelo de autenticación o a las claves whitelisteadas en `_SECRET_KEYS`.
- Cualquier cambio a `perfilar` — sigue exclusivamente local, sin cambios.
- Rediseño visual/UX de la app — se reusa el patrón visual existente sin alterarlo.
