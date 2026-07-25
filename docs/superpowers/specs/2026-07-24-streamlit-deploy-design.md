# Deploy en Streamlit Community Cloud — Diseño

**Fecha:** 2026-07-24
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

Añadir una UI web mínima (`streamlit_app.py`) a `epe-generator` y deployarla en Streamlit
Community Cloud, para poder correr la fase `propose` (la única implementada en v1) desde el
navegador, sin depender de la terminal. Espeja el patrón de `endes-generator/streamlit_app.py`
(login por secrets, sin estado en el servidor, sube/descarga archivos).

## 2. Alcance

`epe-generator` v1 solo tiene la fase `propose` (`perfilar` produce el insumo). La UI, por lo
tanto, es **una sola vista**, no el sidebar multi-fase de `endes-generator`.

## 3. Decisión de arquitectura: PHI nunca sube a la nube

`perfilar` necesita `GOOGLE_SERVICE_ACCOUNT_JSON`, una credencial con acceso de lectura al
Sheet EPE (PHI real). Subir esa credencial a los secrets de Streamlit Cloud pondría la llave
de acceso a datos de pacientes en un servicio de terceros.

**Decisión (aprobada por el usuario): `perfilar` queda exclusivamente local.** Mismo patrón
que la fase `analyze` de `endes-generator` (necesita microdatos + Stata local). La nube solo
corre `propose`:

```
LOCAL (tu máquina)                          NUBE (Streamlit Community Cloud)
─────────────────                           ────────────────────────────────
python orchestrator.py perfilar    →   subes perfil_epe.yaml   →   propose (candidatos)
(usa GOOGLE_SERVICE_ACCOUNT_JSON,
 toca el Sheet EPE con PHI)
```

`GOOGLE_SERVICE_ACCOUNT_JSON` **nunca** se sube a los secrets de Streamlit Cloud.

## 4. Login

Reusa el patrón de `endes-generator`/`nucleo`: usuario/contraseña vía `AUTH_USER`/
`AUTH_PASSWORD` en secrets, comparación timing-safe.

## 5. Componentes

### 5.1 `core/auth.py` (nuevo)
Copia literal del patrón de `endes-generator/core/auth.py`:

```python
from __future__ import annotations

import hmac


def verificar_credenciales(usuario_in: str, pass_in: str,
                           usuario_real: str, pass_real: str) -> bool:
    """Compara credenciales en tiempo constante. Config vacía (sin usuario/pass
    real) => siempre False, para no dejar la app abierta por secrets ausentes."""
    if not usuario_real or not pass_real:
        return False
    u_ok = hmac.compare_digest(usuario_in or "", usuario_real)
    p_ok = hmac.compare_digest(pass_in or "", pass_real)
    return u_ok and p_ok
```

### 5.2 `streamlit_app.py` (nuevo)

- `_SECRET_KEYS = ("LLM_PROVIDER", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "PUBMED_API_KEY",
  "AUTH_USER", "AUTH_PASSWORD")` — nunca `GOOGLE_SERVICE_ACCOUNT_JSON`/`EPE_SHEET_ID`.
- `_puente_secrets_a_env()`: copia `st.secrets` → `os.environ`, idempotente, tolerante a
  ausencias (mismo patrón que endes-generator).
- `_cliente_llm_o_none()` / `_cliente_pubmed()`: envuelven `make_client`/`make_pubmed_client`
  de `core/`, degradando con `st.warning` igual que el CLI degrada con `print(aviso:...)`.
- `_gate_login()`: formulario usuario/contraseña, `st.session_state["auth_ok"]`.
- **Vista única `vista_propose()`**:
  1. Texto explicando el flujo local→nube (ver §3) y un enlace/instrucción para correr
     `python orchestrator.py perfilar` localmente.
  2. `st.file_uploader("Sube perfil_epe.yaml", type="yaml")`.
  3. Botón "Generar candidatos": escribe el archivo subido a un `NamedTemporaryFile`, llama
     `load_perfil(ruta_temporal)` → `run_propose("knowledge/plantilla_epe.yaml", ruta_perfil,
     pubmed_client, llm_client)` (la `plantilla_epe.yaml` viaja en el repo, no hace falta
     subirla).
  4. Renderiza `render_candidatos_md(...)` con `st.markdown`, muestra `st.warning` por cada
     aviso de degradación.
  5. Dos `st.download_button`: `candidatos.md` y `candidatos.json`
     (`render_candidatos_json`).
- `main()`: `st.set_page_config(page_title="epe-generator", layout="wide")` → `_gate_login()`
  → `vista_propose()`.

**Sin cambios** en `orchestrator.py`, `core/`, `agents/` — la app es una capa nueva sobre el
motor ya probado (validado end-to-end en la sesión anterior). `run_propose` ya acepta una
ruta a `perfil_epe.yaml`; el `NamedTemporaryFile` es solo para adaptar el `UploadedFile` de
Streamlit a esa firma existente.

## 6. Testing

- Tests para `core/auth.py::verificar_credenciales` (mismos casos que endes-generator:
  credenciales correctas, incorrectas, config vacía → False, comparación no filtra timing
  — no se puede testear timing directamente, pero sí la lógica).
- `streamlit_app.py` en sí no se testea unitariamente (UI, mismo criterio que
  `endes-generator`) — se verifica manualmente corriendo `streamlit run streamlit_app.py`
  localmente antes de deployar.

## 7. Deploy

1. En [share.streamlit.io](https://share.streamlit.io), conectar el repo
   `github.com/leonidcapo/epe-generator` y apuntar a `streamlit_app.py`.
2. En **Secrets**, pegar `LLM_PROVIDER`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`,
   `PUBMED_API_KEY`, `AUTH_USER`, `AUTH_PASSWORD` (generar credenciales nuevas para
   `AUTH_USER`/`AUTH_PASSWORD`, no reusar las de nucleo).
3. La app queda tras login. Flujo: correr `perfilar` local → subir `perfil_epe.yaml` →
   `propose` → descargar `candidatos.md`/`.json`.
4. Actualizar `README.md` con esta sección de deploy (mismo formato que
   `endes-generator/README.md`).

## 8. Fuera de alcance
- Cualquier fase más allá de `propose` (no existen todavía).
- Subir `perfilar` a la nube (decisión explícita, §3).
- Persistencia de estado en el servidor (la app es stateless, como endes-generator).
