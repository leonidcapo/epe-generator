from __future__ import annotations

from collections import Counter
from datetime import date

from core.knowledge import Perfil
from core.result import AgentResult
from core.sheets_client import SheetReader

# Histórico/documental: estas eran las columnas bloqueadas explícitamente antes de
# pasar a un allow-list. Ya no gobiernan el filtrado (ver _COLUMNAS_PERMITIDAS /
# _fila_sin_phi más abajo), pero se conservan como referencia de qué es PHI en el
# Sheet EPE.
PHI_COLUMNS_EXCLUIDAS = frozenset({
    "Insertar N° de DNI", "Apellidos y Nombres", "N° de HC", "Celular",
    "Fecha de Nacimiento", "Cuidador",
})

# Grupo etareo -> subpoblación(es) a las que pertenece la fila (1:1 en este caso).
_MAPA_GRUPO_ETAREO_A_SUBPOBLACION = {
    "Niño preescolar": "ninos_preescolares_escolares",
    "Niño escolar": "ninos_preescolares_escolares",
    "Adolescente": "adolescentes",
    "Adulto": "adultos",
    "Adulto mayor": "adultos_mayores",
}

# Tipo de discapacidad -> subpoblación de discapacidad correspondiente.
_MAPA_DISCAPACIDAD_A_SUBPOBLACION = {
    "Intelectual": "discapacidad_intelectual",
    "Física": "discapacidad_fisica",
    "Sensorial": "discapacidad_sensorial",
}

_VARIABLES_AGREGABLES = (
    "sexo", "Grupo etareo", "Riesgo sistémico", "Tipo de discapacidad",
    "Severidad de la discapacidad", "Grado de cooperación",
    "Ubicación del procedimiento", "Categorías IMC",
    # Columnas nuevas, requeridas para los ejes farmacoterapia_polifarmacia y
    # procedencia_acceso; también se exponen como distribución.
    "Farmacoterapia", "Procedencia/ Referido de Provincia",
)


# Allow-list estructural: ninguna columna que no esté aquí llega a filas_limpias,
# sin importar de dónde venga o si es PHI o no. Cualquier columna futura desconocida
# se descarta por default (defense-in-depth real, no incidental).
_COLUMNAS_PERMITIDAS = frozenset(_VARIABLES_AGREGABLES) | {"Grupo etareo", "Riesgo sistémico"}


def _fila_sin_phi(fila: dict) -> dict:
    return {k: v for k, v in fila.items() if k in _COLUMNAS_PERMITIDAS}


def _subpoblaciones(fila: dict) -> set[str]:
    subpoblaciones: set[str] = set()
    sp_etareo = _MAPA_GRUPO_ETAREO_A_SUBPOBLACION.get(fila.get("Grupo etareo"))
    if sp_etareo is not None:
        subpoblaciones.add(sp_etareo)
    sp_discapacidad = _MAPA_DISCAPACIDAD_A_SUBPOBLACION.get(fila.get("Tipo de discapacidad"))
    if sp_discapacidad is not None:
        subpoblaciones.add(sp_discapacidad)
    if fila.get("Riesgo sistémico") == "ASA3":
        subpoblaciones.add("asa3_alto_riesgo")
    return subpoblaciones


def _ejes_aplicables(fila: dict) -> set[str]:
    ejes: set[str] = set()
    if fila.get("Riesgo sistémico"):
        ejes.add("riesgo_sistemico_asa")
    tipo_discapacidad = fila.get("Tipo de discapacidad")
    if tipo_discapacidad and tipo_discapacidad != "No aplica":
        ejes.add("discapacidad_tipo_severidad")
    if fila.get("Grado de cooperación"):
        ejes.add("cooperacion_manejo_conductual")
    if fila.get("Categorías IMC"):
        ejes.add("estado_nutricional_imc")
    if fila.get("Farmacoterapia"):
        ejes.add("farmacoterapia_polifarmacia")
    if fila.get("Procedencia/ Referido de Provincia"):
        ejes.add("procedencia_acceso")
    return ejes


def _n_por_celda(filas_limpias: list[dict]) -> dict[tuple[str, str], int]:
    conteo: Counter[tuple[str, str]] = Counter()
    for fila in filas_limpias:
        subpoblaciones = _subpoblaciones(fila)
        ejes = _ejes_aplicables(fila)
        for subpoblacion in subpoblaciones:
            for eje in ejes:
                conteo[(subpoblacion, eje)] += 1
    return dict(conteo)


def perfilar(reader: SheetReader) -> AgentResult:
    try:
        filas = reader.leer_filas()
    except ConnectionError as exc:
        return AgentResult.failure([str(exc)])

    filas_limpias = [_fila_sin_phi(f) for f in filas]

    distribuciones: dict[str, dict[str, int]] = {}
    for var in _VARIABLES_AGREGABLES:
        conteo = Counter(f[var] for f in filas_limpias if f.get(var))
        if conteo:
            distribuciones[var] = dict(conteo)

    perfil = Perfil(
        n_por_celda=_n_por_celda(filas_limpias),
        distribuciones=distribuciones,
        generado_en=date.today().isoformat(),
    )
    return AgentResult.success(perfil)
