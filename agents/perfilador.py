from __future__ import annotations

from collections import Counter
from datetime import date

from core.knowledge import Perfil
from core.result import AgentResult
from core.sheets_client import SheetReader

# Bloqueadas de forma explícita y permanente: ningún cambio aguas abajo debe poder
# hacer que estas columnas (o sus valores) lleguen a perfil_epe.yaml.
PHI_COLUMNS_EXCLUIDAS = frozenset({
    "Insertar N° de DNI", "Apellidos y Nombres", "N° de HC", "Celular",
    "Fecha de Nacimiento", "Cuidador",
})

# Variable de agregación -> id de subpoblación cuando el valor corresponde a esa categoría.
_MAPA_GRUPO_ETAREO_A_SUBPOBLACION = {
    "Adulto": "adultos",
    "Adulto mayor": "adultos_mayores",
}

_VARIABLES_AGREGABLES = (
    "sexo", "Grupo etareo", "Riesgo sistémico", "Tipo de discapacidad",
    "Severidad de la discapacidad", "Grado de cooperación",
    "Ubicación del procedimiento", "Categorías IMC",
)


def _fila_sin_phi(fila: dict) -> dict:
    return {k: v for k, v in fila.items() if k not in PHI_COLUMNS_EXCLUIDAS}


def _n_por_celda(filas_limpias: list[dict]) -> dict[tuple[str, str], int]:
    conteo: Counter[tuple[str, str]] = Counter()
    for fila in filas_limpias:
        subpoblacion = _MAPA_GRUPO_ETAREO_A_SUBPOBLACION.get(fila.get("Grupo etareo"))
        if subpoblacion is None:
            continue
        if fila.get("Riesgo sistémico"):
            conteo[(subpoblacion, "riesgo_sistemico_asa")] += 1
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
