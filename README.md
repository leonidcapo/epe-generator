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
python orchestrator.py perfilar                    # Sheet EPE (vivo) -> knowledge/perfil_epe.yaml (sin PHI)
python orchestrator.py propose                     # perfil + plantilla -> outputs/<timestamp>/candidatos.{md,json}
python orchestrator.py design <candidato_id>       # candidatos.json + LLM → outputs/<run_id>/protocolo.md + protocolo.docx
python orchestrator.py analyze <candidato_id>      # candidatos.json -> outputs/<run_id>/analisis.do (sintaxis Stata determinística)
python orchestrator.py report <candidato_id> <ruta_resultados_xlsx>  # resultados.xlsx (del estadístico) → outputs/<run_id>/articulo.md (informe final)
```

## Deploy en Streamlit Community Cloud

La UI (`streamlit_app.py`) corre solo la fase `propose` en la nube. `perfilar` (necesita la
credencial de Google con acceso al Sheet EPE, que contiene PHI real) queda **exclusivamente
local** — su credencial nunca sube a los secrets de Streamlit Cloud.

1. Corre `python orchestrator.py perfilar` en tu máquina para producir
   `knowledge/perfil_epe.yaml`.
2. En [share.streamlit.io](https://share.streamlit.io), conecta el repo y apunta a
   `streamlit_app.py`. **Atención:** el tier gratuito de Streamlit Community Cloud requiere
   que el repo de GitHub sea **público**. Antes de conectarlo, verifica que nada en el árbol
   lleve credenciales o identificadores: sin `.env`, sin `credentials/`, sin un `EPE_SHEET_ID`
   real, sin `knowledge/perfil_epe.yaml`. `.env`, `credentials/`, `knowledge/perfil_epe.yaml`
   y `.streamlit/secrets.toml` ya están en `.gitignore`, así que un clon limpio del repo no
   los lleva — pero de todas formas confirma con `git ls-files` antes de hacer público el repo.
3. En **Secrets**, pega `LLM_PROVIDER`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`,
   `PUBMED_API_KEY`, `AUTH_USER`, `AUTH_PASSWORD` (genera credenciales de login nuevas,
   no reuses las de otros proyectos, y usa una contraseña **larga y aleatoria**: la app
   desplegada tiene una URL pública y el formulario de login no tiene límite de intentos,
   así que un atacante puede probar credenciales sin restricción). **Nunca** pegues
   `GOOGLE_SERVICE_ACCOUNT_JSON` ni `EPE_SHEET_ID` ahí.
4. La app queda tras login. Flujo: `perfilar` local → subes `perfil_epe.yaml` en la app →
   `propose` → descargas `candidatos.md`/`.json`.

La app es sin estado: no persiste nada en el servidor entre subidas.

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

## Ciclo completo (v1)

El ciclo de cuatro fases (`propose` → `design` → `analyze` → `report`) está implementado,
precedido por el prerrequisito `perfilar`:

0. **`perfilar`** (prerrequisito): Lee el Sheet EPE (vivo, con PHI) y produce el perfil agregado.
1. **`propose`**: Genera semillas de ideas (candidatos) desde el perfil.
2. **`design`**: Diseña el protocolo ex ante con validación metodológica (auditoría de sesgos, lenguaje causal).
3. **`analyze`**: Genera sintaxis Stata determinística para análisis.
4. **`report`**: Lee el archivo de resultados y genera el informe final (`articulo.md`).

Una semilla que el usuario valide se lleva manualmente, ya formulada, a `nucleo` si quiere respaldo
de revisión de literatura — este sistema nunca alimenta el motor de `nucleo` directamente.
