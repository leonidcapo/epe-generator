# Saneamiento de plantilla vs. datos reales — Diseño

**Fecha:** 2026-07-29
**Autor:** Leonid (DolphinStats) + Claude
**Estado:** Aprobado (diseño) — pendiente de plan de implementación
**Contexto:** Entrega 1 de 2. Prerrequisito del export de datos reales (Entrega 2), que no
tiene sentido construir sobre columnas que están vacías.

---

## 1. Propósito

Corregir tres inconsistencias entre lo que `plantilla_epe.yaml` **declara** y lo que la
pestaña Marco del Sheet **realmente contiene**, detectadas al preparar el export de datos
reales. Dos de las tres producen fallas silenciosas hoy.

Además, hacer que el invariante que ya está documentado en la plantilla deje de depender de
un comentario y pase a **detectarse solo en tiempo de ejecución**.

## 2. Hallazgos con evidencia

Verificados contra `knowledge/perfil_epe.yaml` (artefacto agregado, sin PHI), no contra el
Sheet en vivo.

### 2.1 `procedencia_acceso` está declarado `candidato` pero no tiene datos

La columna `"Lugar de Procedencia"` no aparece en `distribuciones` y el eje
`procedencia_acceso` no aparece en ninguna celda de `n_por_celda`.

Como el eje está declarado `estado: candidato`, `ejes_implementados_por_subpoblacion` lo
incluye en el universo conjunto de las 4 subpoblaciones etarias con las que es compatible.
Ninguna fila puede satisfacer ese universo jamás, así que quedan en cero **en silencio**:

```yaml
ninos_preescolares_escolares: 0
adolescentes: 0
adultos: 0
adultos_mayores: 0
```

Esto es exactamente la falla que el comentario invariante sobre el bloque `ejes:` advertía
que ocurriría. Es la primera vez que se manifiesta con datos reales.

**Efecto del arreglo:** `adultos_mayores` pasa a universo `{riesgo_sistemico_asa,
farmacoterapia_polifarmacia}` — 2 ejes con datos, suficiente para generar candidatos
multivariados sobre 919 pacientes. `adultos` y `ninos_preescolares_escolares` quedan con 1
solo eje (insuficiente para multivariado, pero dejan de reportar un 0 engañoso) y
`adolescentes` queda con universo vacío (no tiene ningún eje compatible con datos).

### 2.2 El outcome `ubicacion_procedimiento` no tiene datos

La columna `"Ubicación del procedimiento"` tampoco aparece en `distribuciones`.

A diferencia de los ejes, los outcomes no participan del cálculo de `n_conjunto`, así que
esto no anula ninguna subpoblación. Pero `gap_finder.generar_espacio` itera **todos** los
outcomes declarados sin filtrar, así que hoy genera candidatos cuyo outcome no tiene datos
— estudios imposibles de analizar que igual compiten por lugar en el ranking.

De los 3 outcomes declarados, solo `grado_cooperacion` tiene datos confirmados;
`nivel_tratamiento_requerido` está fuera del allow-list de `perfilador.py`, así que su
estado es desconocido hasta que se agregue (ver §3.4).

### 2.3 La categoría `Jóven` (139 pacientes) no está mapeada

`Grupo etareo` trae la categoría `Jóven` con 139 pacientes (~8% de la cohorte), que no
existe en `_MAPA_GRUPO_ETAREO_A_SUBPOBLACION`. Esos pacientes no caen en ninguna
subpoblación etaria y quedan fuera de todo candidato.

Ya está documentado como limitación conocida en `limitaciones_epe.yaml`
(`calidad_de_registro`), pero es más volumen del que esa nota sugiere.

## 3. Cambios

### 3.1 `knowledge/plantilla_epe.yaml`

- `procedencia_acceso`: `estado: candidato` → `estado: sin_datos`.
- Los outcomes ganan campo `estado` (mismo vocabulario que los ejes):
  ```yaml
  outcomes:
    - {id: nivel_tratamiento_requerido, tipo: categorico, escala: ordinal, estado: candidato}
    - {id: ubicacion_procedimiento, tipo: categorico, escala: nominal, estado: sin_datos}
    - {id: grado_cooperacion, tipo: categorico, escala: nominal, estado: candidato}
  ```
- Nueva subpoblación `{id: jovenes, estado: candidato}`.
- `compatibilidad_eje_subpoblacion`: `jovenes` se agrega a los mismos ejes que `adultos`
  (`riesgo_sistemico_asa`, `morbilidad_cie11_sistemas`, `procedencia_acceso`,
  `estado_nutricional_imc`).

  **Nota de diseño:** la compatibilidad declara **sentido clínico**, independiente de si
  hoy hay datos; el campo `estado` declara **realidad del dato**. Mantener esa separación
  es lo que permite que la plantilla siga siendo correcta cuando una columna aparezca.
  Consecuencia inmediata: `jovenes` queda con 1 eje real (`riesgo_sistemico_asa`), así que
  todavía no genera candidatos multivariados — pero queda correctamente declarada.
- Se extiende el comentario invariante para cubrir también outcomes.

### 3.2 `core/knowledge.py`

- `Plantilla` gana `outcomes_estado: dict[str, str]`, parseado del campo `estado` de cada
  outcome. Si un outcome no lo declara, default `"candidato"` (retrocompatible).

### 3.3 `agents/gap_finder.py`

- `generar_espacio` omite los outcomes cuyo `estado` sea `"sin_datos"` — deja de generar
  candidatos inanalizables.

### 3.4 `agents/perfilador.py`

- `_MAPA_GRUPO_ETAREO_A_SUBPOBLACION`: agregar `"Jóven": "jovenes"`.
- `_VARIABLES_AGREGABLES` (y por lo tanto `_COLUMNAS_PERMITIDAS`): agregar `"nivel_tto"`,
  la columna real del outcome `nivel_tratamiento_requerido`. Esto además **verifica** si
  esa columna tiene datos: si los tiene, aparecerá en `distribuciones` al re-correr
  `perfilar`.
- **Aviso en tiempo de ejecución (el arreglo estructural):** al terminar de perfilar, para
  cada eje con `estado != sin_datos` que no produjo ninguna celda en `n_por_celda`, y para
  cada outcome con `estado != sin_datos` cuya columna no produjo distribución, emitir un
  warning nombrándolo y sugiriendo marcarlo `sin_datos`. `perfilar` devuelve
  `AgentResult.degraded` con esos avisos.

  Esto convierte el invariante de un comentario que hay que recordar leer, en algo que el
  sistema detecta y reporta solo la próxima vez que una columna se vacíe o se renombre.

## 4. Testing

- Parseo de `outcomes_estado` (incluido el default cuando el campo falta).
- `generar_espacio` omite outcomes `sin_datos` y sigue generando los `candidato`.
- Mapeo de `"Jóven"` → `jovenes` en `_subpoblaciones`.
- El aviso de eje-declarado-sin-datos se dispara con filas sintéticas donde un eje
  compatible no produce ninguna celda, y **no** se dispara cuando todos los ejes declarados
  producen datos (evita el falso positivo).
- Toda la suite existente sigue verde (los cambios de plantilla tocan datos que varios
  tests leen — hay que verificar que ninguno asumía las 8 subpoblaciones actuales ni el
  conteo de outcomes).

## 5. Verificación manual (post-merge, local)

Re-correr `python orchestrator.py perfilar` contra el Sheet real y confirmar:
1. `adultos_mayores` pasa de `n_conjunto: 0` a un valor > 0.
2. `nivel_tto` aparece en `distribuciones` — confirma que la columna existe y tiene datos.
   Si **no** aparece, el nuevo aviso lo dirá explícitamente y habrá que marcar
   `nivel_tratamiento_requerido` como `sin_datos`.
3. `jovenes` aparece en `n_conjunto` (con 0, por tener 1 solo eje real — lo esperado).

## 6. Fuera de alcance

- El export de datos reales, la abreviación de columnas y el codebook — todo eso es la
  Entrega 2, que ya está diseñada y depende de que esta entrega cierre.
- Refactorizar `_ejes_aplicables` para que lea el mapa `id → columna` en vez de tener la
  relación hardcodeada (funciona hoy; se evalúa en la Entrega 2).
- Conseguir datos para `"Lugar de Procedencia"` y `"Ubicación del procedimiento"` — no
  depende del código sino del registro clínico.
