# Saneamiento de plantilla vs. datos reales + `.do` autodescriptivo — Diseño

**Fecha:** 2026-07-29
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación

---

## 1. Propósito

Dos cosas, en una sola entrega:

1. **Saneamiento**: corregir las inconsistencias entre lo que `plantilla_epe.yaml` *declara* y
   lo que la pestaña Marco del Sheet *realmente contiene*. Varias producen fallas silenciosas
   hoy, y dejan ~29% de la cohorte fuera de todo análisis.
2. **`.do` autodescriptivo**: que `analisis.do` diga exactamente qué columnas descargar del
   Sheet y emita el filtro de subpoblación como sintaxis Stata real, en vez del comentario
   placeholder actual.

**Decisión de alcance explícita:** se evaluó que `epe-generator` exportara automáticamente los
datos reales anonimizados, y **se descartó**. El export ahorraría poco del trabajo que
realmente cuesta (recodificar, tratar faltantes, elegir categorías de referencia — todo eso
sigue siendo del estadístico en Stata), expandiría de forma permanente la superficie de PHI —
hoy `perfilador.py` nunca emite filas individuales, garantía estructural fácil de auditar — y
con dos columnas vacías (§2.1, §2.2) aplicaría a un subconjunto menor de candidatos del que
parecía. El usuario sigue descargando los datos manualmente; el `.do` se encarga de que esa
descarga sea inequívoca.

## 2. Hallazgos con evidencia

Verificados contra `knowledge/perfil_epe.yaml` (artefacto agregado, sin PHI), no contra el
Sheet en vivo.

### 2.1 `procedencia_acceso` declarado `candidato` pero sin datos

`"Lugar de Procedencia"` no aparece en `distribuciones`, y el eje no aparece en ninguna celda
de `n_por_celda`. Como está declarado `candidato`, `ejes_implementados_por_subpoblacion` lo
mete en el universo conjunto de las 4 subpoblaciones etarias; ninguna fila puede satisfacerlo
jamás, así que quedan en cero **en silencio**:

```yaml
ninos_preescolares_escolares: 0   adultos: 0
adolescentes: 0                   adultos_mayores: 0
```

Es exactamente la falla que el comentario invariante del bloque `ejes:` advertía. Primera vez
que se manifiesta con datos reales.

**Efecto del arreglo:** `adultos_mayores` pasa a universo `{riesgo_sistemico_asa,
farmacoterapia_polifarmacia}` — 2 ejes con datos, genera candidatos sobre 919 pacientes.
`adultos` y `ninos_preescolares_escolares` quedan con 1 eje (insuficiente para multivariado,
pero dejan de reportar un 0 engañoso); `adolescentes` queda con universo vacío.

### 2.2 El outcome `ubicacion_procedimiento` no tiene datos

`"Ubicación del procedimiento"` tampoco aparece en `distribuciones`. Los outcomes no
participan de `n_conjunto`, así que no anula subpoblaciones — pero
`gap_finder.generar_espacio` itera **todos** los outcomes sin filtrar, generando candidatos
imposibles de analizar que compiten por lugar en el ranking.

### 2.3 Categorías sin mapear: 638 pacientes (~37% de la cohorte)

| Columna | Categoría | n | Estado hoy |
|---|---|---|---|
| `Grupo etareo` | `Jóven` | 139 | sin mapear |
| `Tipo de discapacidad` | `Comportamiento` | 337 | sin mapear |
| `Tipo de discapacidad` | `Compuesto` | 162 | sin mapear |

`_MAPA_GRUPO_ETAREO_A_SUBPOBLACION` y `_MAPA_DISCAPACIDAD_A_SUBPOBLACION` solo cubren parte
de las categorías reales. Esos 638 pacientes no caen en ninguna subpoblación y quedan fuera
de todo candidato.

### 2.4 Colisión eje/outcome sobre la misma columna

`cooperacion_manejo_conductual` (eje) y `grado_cooperacion` (outcome) mapean ambos a
`"Grado de cooperación"`. `generar_espacio` puede producir un candidato con ese eje **y** ese
outcome — un modelo degenerado que regresa una variable contra sí misma. Hoy nada lo impide.

## 3. Decisiones tomadas

- **`Compuesto` = "2 o más discapacidades, cualesquiera sean"** (dato del usuario). El registro
  **no guarda cuáles**, así que la pertenencia múltiple queda descartada: asignar esos 162
  pacientes a intelectual + física + sensorial contaría a cada uno en las tres, inflando
  `discapacidad_sensorial` (hoy 42) con casos que no le corresponden, y ese error se
  propagaría al `n` de los candidatos y al análisis. Se trata como **subpoblación propia**
  `discapacidad_multiple`. Efecto colateral deseable: las otras tres quedan definidas como
  "discapacidad única de ese tipo", mutuamente excluyentes.
- **`compatibilidad` declara sentido clínico; `estado` declara realidad del dato.** Mantener
  esa separación es lo que permite que una subpoblación quede correctamente declarada con sus
  ejes compatibles aunque hoy no tengan datos, y que la plantilla siga siendo correcta cuando
  esas columnas aparezcan.
- **`jovenes` espeja `adultos`** — queda con 1 eje real, así que se declara pero todavía no
  genera candidatos. Es lo esperado, no un error.

## 4. Cambios

### 4.1 `knowledge/plantilla_epe.yaml`

- `procedencia_acceso`: `estado: candidato` → `estado: sin_datos`.
- Los outcomes ganan `estado` (mismo vocabulario que los ejes):
  ```yaml
  outcomes:
    - {id: nivel_tratamiento_requerido, tipo: categorico, escala: ordinal, estado: candidato}
    - {id: ubicacion_procedimiento, tipo: categorico, escala: nominal, estado: sin_datos}
    - {id: grado_cooperacion, tipo: categorico, escala: nominal, estado: candidato}
  ```
- Subpoblaciones nuevas: `jovenes`, `discapacidad_comportamiento`, `discapacidad_multiple`
  (todas `estado: candidato`).
- `compatibilidad_eje_subpoblacion`:
  - `jovenes` se agrega a los mismos ejes que `adultos` (`riesgo_sistemico_asa`,
    `morbilidad_cie11_sistemas`, `procedencia_acceso`, `estado_nutricional_imc`).
  - `discapacidad_comportamiento` y `discapacidad_multiple` se agregan a
    `discapacidad_tipo_severidad` y `cooperacion_manejo_conductual` — 2 ejes con datos cada
    una, así que **ambas generan candidatos multivariados** (337 y 162 pacientes).
- **Bloque nuevo `columnas_datos`** — id → columna(s) real(es) del Sheet. Fuente única
  consumida por `perfilador`, `gap_finder` y `statistician`; admite lista cuando un eje
  necesita más de una columna:
  ```yaml
  columnas_datos:
    riesgo_sistemico_asa: "Riesgo sistémico"
    discapacidad_tipo_severidad: ["Tipo de discapacidad", "Severidad de la discapacidad"]
    farmacoterapia_polifarmacia: "Farmacoterapia"
    cooperacion_manejo_conductual: "Grado de cooperación"
    procedencia_acceso: "Lugar de Procedencia"
    nivel_tratamiento_requerido: "nivel_tto"
    ubicacion_procedimiento: "Ubicación del procedimiento"
    grado_cooperacion: "Grado de cooperación"
  ```
- **Bloque nuevo `filtro_subpoblacion`** — criterio que define cada subpoblación, declarativo:
  ```yaml
  filtro_subpoblacion:
    ninos_preescolares_escolares: {columna: "Grupo etareo", valores: ["Niño preescolar", "Niño escolar"]}
    adolescentes:                 {columna: "Grupo etareo", valores: ["Adolescente"]}
    jovenes:                      {columna: "Grupo etareo", valores: ["Jóven"]}
    adultos:                      {columna: "Grupo etareo", valores: ["Adulto"]}
    adultos_mayores:              {columna: "Grupo etareo", valores: ["Adulto mayor"]}
    discapacidad_intelectual:     {columna: "Tipo de discapacidad", valores: ["Intelectual"]}
    discapacidad_fisica:          {columna: "Tipo de discapacidad", valores: ["Física"]}
    discapacidad_sensorial:       {columna: "Tipo de discapacidad", valores: ["Sensorial"]}
    discapacidad_comportamiento:  {columna: "Tipo de discapacidad", valores: ["Comportamiento"]}
    discapacidad_multiple:        {columna: "Tipo de discapacidad", valores: ["Compuesto"]}
    asa3_alto_riesgo:             {columna: "Riesgo sistémico", valores: ["ASA3"]}
  ```
- Se extiende el comentario invariante para cubrir también outcomes.

### 4.2 `core/knowledge.py`

- `Plantilla` gana `outcomes_estado: dict[str, str]` (default `"candidato"` si el campo falta),
  `columnas_datos: dict[str, tuple[str, ...]]` (un string suelto se normaliza a tupla de 1) y
  `filtro_subpoblacion: dict[str, dict]`.
- Validación de vocabulario: todo id referenciado en `columnas_datos` y `filtro_subpoblacion`
  debe estar declarado como eje/outcome/subpoblación, y toda subpoblación declarada debe tener
  filtro. Error explícito (`VocabularioError`) si no.

### 4.3 `agents/perfilador.py`

- `_subpoblaciones(fila, plantilla)` pasa a leer `filtro_subpoblacion` y **reemplaza** los dos
  mapas hardcodeados (`_MAPA_GRUPO_ETAREO_A_SUBPOBLACION`,
  `_MAPA_DISCAPACIDAD_A_SUBPOBLACION`). Con eso, las 3 categorías del §2.3 quedan cubiertas por
  construcción, no por parches sueltos. Los llamadores (`_n_por_celda`, `_n_conjunto`) se
  actualizan.
- `_VARIABLES_AGREGABLES` (y por lo tanto `_COLUMNAS_PERMITIDAS`) gana `"nivel_tto"`. Esto
  además **verifica** si esa columna tiene datos: si los tiene, aparecerá en `distribuciones`.
- **Aviso en runtime (el arreglo estructural):** al terminar, para cada eje con
  `estado != sin_datos` que no produjo ninguna celda, y cada outcome con `estado != sin_datos`
  cuya columna no produjo distribución, emitir un warning nombrándolo y sugiriendo marcarlo
  `sin_datos`. `perfilar` devuelve `AgentResult.degraded` con esos avisos. Convierte el
  invariante de un comentario que hay que acordarse de leer, en algo que el sistema detecta
  solo la próxima vez que una columna se vacíe o se renombre.

### 4.4 `agents/gap_finder.py`

- `generar_espacio` omite outcomes con `estado == "sin_datos"`.
- `generar_espacio` omite candidatos donde la columna del outcome coincide con la del eje o la
  de alguna covariable (§2.4) — evita el modelo degenerado.

### 4.5 `agents/statistician.py` — `.do` autodescriptivo

- Función `abreviar(columnas: list[str]) -> dict[str, str]`: determinista — quita tildes,
  minúsculas, no-alfanumérico → `_`, colapsa repetidos, trunca a 32, resuelve colisiones con
  sufijo numérico. Mismo patrón que `mapeo_hojas_bivariado`, que ya resolvió este problema.
- Encabezado nuevo del `.do`: lista las columnas exactas a descargar de Marco y el nombre de
  variable que el `.do` espera para cada una, para que el renombrado al importar sea
  inequívoco:
  ```stata
  * Columnas a descargar de la pestaña "Marco" del Sheet EPE, y el nombre
  * que este .do espera (renómbralas así al importar):
  *   "Riesgo sistémico"  -> riesgo_sistemico
  *   "Farmacoterapia"    -> farmacoterapia
  *   "nivel_tto"         -> nivel_tto
  ```
- El comentario placeholder `* filtrar a subpoblacion: ... (definir criterio real con el
  estadistico)` **desaparece**, reemplazado por sintaxis ejecutable derivada de
  `filtro_subpoblacion` (`==` para un valor, `inlist()` para varios):
  ```stata
  keep if riesgo_sistemico == "ASA3"
  ```
- El resto del `.do` (descriptivos, bivariado, modelo, `putexcel`) usa los nombres abreviados.

## 5. Testing

- Parseo de `outcomes_estado` (incluido el default), `columnas_datos` (string y lista) y
  `filtro_subpoblacion`; `VocabularioError` ante ids desconocidos o subpoblación sin filtro.
- `_subpoblaciones` con filas sintéticas: cubre `Jóven`, `Comportamiento`, `Compuesto`,
  pertenencia simultánea (etaria + discapacidad + ASA3) y categorías desconocidas (no explota).
- `generar_espacio`: omite outcomes `sin_datos`; omite la colisión eje/outcome; sigue generando
  los válidos.
- Aviso de eje/outcome declarado-sin-datos: se dispara con filas donde un eje compatible no
  produce celdas, y **no** se dispara cuando todos producen datos (evita el falso positivo).
- `abreviar`: nombres con tildes/espacios, truncado a 32, colisiones con sufijo, y que un
  nombre ya corto y limpio (`nivel_tto`) quede intacto.
- `generar_do`: encabezado con el mapeo columna→variable, `keep if` correcto para filtro de un
  valor y de varios, y ausencia del comentario placeholder viejo.
- Suite existente verde: varios tests leen la plantilla real, hay que verificar que ninguno
  asumía el número de subpoblaciones o de outcomes.

## 6. Verificación manual (post-merge, local)

Re-correr `python orchestrator.py perfilar` contra el Sheet real y confirmar:
1. `adultos_mayores` pasa de `n_conjunto: 0` a > 0.
2. `nivel_tto` aparece en `distribuciones` — confirma que la columna existe y tiene datos. Si
   **no** aparece, el nuevo aviso lo dirá y habrá que marcar `nivel_tratamiento_requerido`
   como `sin_datos`.
3. Aparecen `jovenes`, `discapacidad_comportamiento` (~337) y `discapacidad_multiple` (~162).

Luego `propose` + `analyze` sobre un candidato de `discapacidad_comportamiento`, y revisar que
el `.do` traiga el `keep if` correcto y la lista de columnas a descargar.

## 7. Fuera de alcance

- **Export automático de datos reales** — descartado explícitamente (§1).
- Refactorizar `_ejes_aplicables` para que lea `columnas_datos` (tiene lógica de presencia con
  excepciones — `"No aplica"`, `"Ninguna"` — que no es un mapeo puro; funciona hoy y se deja
  como está).
- Conseguir datos para `"Lugar de Procedencia"` y `"Ubicación del procedimiento"` — depende del
  registro clínico, no del código.
- Que el registro capture qué discapacidades componen `Compuesto` — habilitaría un análisis más
  fino, pero es un cambio en la captura de datos.
