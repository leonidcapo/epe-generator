# Fix: mismatch de prefijo en traducción de nombres bivariado (writer vs executor)

## Bug confirmado por trazado directo (antes de tocar código)

1. `agents/statistician.py::mapeo_hojas_bivariado(predictores)` devuelve un dict
   `predictor_real -> nombre_hoja_excel` donde el valor SIEMPRE incluye el prefijo
   `bivariado_` (truncado a 31 caracteres en total, prefijo incluido). Confirmado:
   `mapeo_hojas_bivariado(['riesgo_sistemico_asa','farmacoterapia_polifarmacia'])
   ['farmacoterapia_polifarmacia'] == 'bivariado_farmacoterapia_polifa'`.

2. `agents/executor.py::parsear_resultados` (línea ~10: `_PREFIJO_BIVARIADO =
   "bivariado_"`; línea ~91: `pred = hoja[len(_PREFIJO_BIVARIADO):]`) descubre las
   hojas bivariado por el prefijo y guarda `data["bivariado"]` **con las claves SIN
   el prefijo** (p.ej. `"farmacoterapia_polifa"`, no `"bivariado_farmacoterapia_polifa"`).

3. `agents/writer.py::redactar_resultados` (antes del fix, línea 37) construía:
   `hoja_a_pred = {hoja: pred for pred, hoja in mapeo_hojas_bivariado(predictores).items()}`
   — las CLAVES de este dict son los nombres de hoja **con prefijo** (paso 1). Luego
   hacía `hoja_a_pred.get(hoja_key, hoja_key)` donde `hoja_key` viene de
   `tablas["bivariado"]`, que por el paso 2 está **sin prefijo**. El lookup por lo
   tanto SIEMPRE fallaba (claves con prefijo vs. claves de búsqueda sin prefijo), y
   caía silenciosamente al nombre crudo truncado/recortado — es decir, la traducción
   era código muerto que nunca corregía un nombre truncado en producción. Para
   nombres no truncados solo "funcionaba por casualidad" porque el fragmento
   recortado coincidía con el nombre real, no porque el lookup tuviera éxito.

Confirmado leyendo `agents/executor.py` (definición de `_PREFIJO_BIVARIADO` y
derivación de `pred` desde `hoja`) y `agents/writer.py::redactar_resultados`.

## Fix aplicado

`agents/writer.py`:
- Se agregó la constante de módulo `_PREFIJO_BIVARIADO = "bivariado_"` (duplica el
  literal de `executor.py`/`statistician.py` intencionalmente; centralizarlo queda
  fuera de alcance de este fix).
- `hoja_a_pred` ahora se construye recortando el prefijo de los valores de
  `mapeo_hojas_bivariado(...)` antes de usarlos como claves, para que coincidan con
  las claves reales (sin prefijo) que produce `executor.py`:

```python
hoja_a_pred = {
    hoja[len(_PREFIJO_BIVARIADO):]: pred
    for pred, hoja in mapeo_hojas_bivariado(predictores).items()
}
```

## Tests

- `tests/test_writer.py::test_redactar_resultados_traduce_hoja_bivariado_a_covariable_real`:
  corregido para construir `tablas["bivariado"]` con la clave SIN el prefijo
  (`hoja_farmaco_stripped`), igual que lo hace el executor real, en vez de la clave
  con prefijo que usaba antes (por lo cual el test pasaba pese al bug).
  - Nota: la aserción `assert hoja_farmaco_stripped not in texto` sugerida original-
    mente no es satisfacible incluso con el fix correcto, porque
    `"farmacoterapia_polifa"` (fragmento truncado) es un substring literal de
    `"farmacoterapia_polifarmacia"` (nombre real ya traducido correctamente). Se
    ajustó a `assert f"{hoja_farmaco_stripped} =" not in texto`, que sí verifica lo
    que se pretendía (que el fragmento truncado no aparezca como token de predictor
    en la prosa) sin ser un falso negativo.
- Se agregó `tests/test_writer.py::test_redactar_resultados_traduce_correctamente_via_executor_real`:
  prueba de integración real que escribe un `.xlsx` con el nombre de hoja EXACTO que
  generaría `statistician.py` (vía `mapeo_hojas_bivariado`), lo parsea con el
  `parsear_resultados` real de `agents/executor.py` (no un dict armado a mano), y
  confirma que `redactar_resultados` muestra el nombre real de la covariable.
- Se agregó el import de `openpyxl` y `parsear_resultados` al inicio de
  `tests/test_writer.py`.

## README

Se corrigió `README.md` (sección "Ciclo completo (v1)"): decía "el ciclo de cuatro
fases está implementado" pero listaba 5 pasos incluyendo `perfilar`, que es un
prerrequisito, no una de las 4 fases numeradas. Se reescribió para aclarar que
`perfilar` es prerrequisito y que el ciclo de 4 fases propiamente dicho es
`propose → design → analyze → report`.

## Resultado de tests

```
$ python -m pytest tests/test_writer.py -v
...
tests/test_writer.py::test_redactar_resultados_excluye_cons PASSED       [ 12%]
tests/test_writer.py::test_redactar_resultados_traduce_hoja_bivariado_a_covariable_real PASSED [ 25%]
tests/test_writer.py::test_redactar_resultados_traduce_correctamente_via_executor_real PASSED [ 37%]
tests/test_writer.py::test_redactar_articulo_degrada_sin_llm PASSED      [ 50%]
tests/test_writer.py::test_redactar_articulo_con_llm_disponible PASSED   [ 62%]
tests/test_writer.py::test_redactar_articulo_marca_cifra_inventada PASSED [ 75%]
tests/test_writer.py::test_redactar_articulo_detecta_lenguaje_causal PASSED [ 87%]
tests/test_writer.py::test_redactar_articulo_candidato_id_coincide_con_protocolo PASSED [100%]

8 passed in 8.07s
```

```
$ python -m pytest -q
........................................................................ [ 43%]
........................................................................ [ 86%]
.......................                                                  [100%]
167 passed, 2 warnings in 21.25s
```

Baseline era 166 tests; se corrigió 1 test existente y se agregó 1 nuevo, dando
167 — coincide con lo esperado. Sin regresiones, sin cuelgues. Las 2 warnings son
preexistentes (`openpyxl` avisando de nombres de hoja >31 caracteres, comportamiento
intencional del truncado que motivó esta feature).
