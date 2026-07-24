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
