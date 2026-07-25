from __future__ import annotations

from typing import Any, Protocol


class SheetReader(Protocol):
    def leer_filas(self) -> list[dict[str, Any]]: ...


class FakeSheetReader:
    """Deterministic stub. No network. Set fail=True to simulate a connection error."""

    def __init__(self, filas: list[dict[str, Any]], fail: bool = False):
        self._filas = filas
        self._fail = fail

    def leer_filas(self) -> list[dict[str, Any]]:
        if self._fail:
            raise ConnectionError("fallo simulado de conexión a Google Sheets")
        return list(self._filas)


class GspreadSheetReader:
    """Lee una pestaña de un Google Sheet vía cuenta de servicio (gspread).

    Requiere GOOGLE_SERVICE_ACCOUNT_JSON (ruta al JSON de credenciales) en el entorno,
    y que esa cuenta de servicio tenga acceso de lectura al Sheet (compartido explícitamente
    por el dueño). No se testea con red real — ver README para el setup manual.
    """

    def __init__(self, credentials_path: str, sheet_id: str, worksheet_name: str):
        self._credentials_path = credentials_path
        self._sheet_id = sheet_id
        self._worksheet_name = worksheet_name

    def leer_filas(self) -> list[dict[str, Any]]:
        import gspread  # imported lazily so tests never need the package installed to run

        gc = gspread.service_account(filename=self._credentials_path)
        sh = gc.open_by_key(self._sheet_id)
        ws = sh.worksheet(self._worksheet_name)
        # get_all_records() exige encabezados únicos y no vacíos; el Sheet real trae
        # columnas duplicadas/sin nombre (p.ej. "Celular" repetida, columnas finales
        # vacías) y a veces una fila completamente en blanco antes del encabezado
        # real, así que armamos los dicts a mano en vez de delegar en gspread.
        return _filas_desde_valores(ws.get_all_values())


def _deduplicar_encabezados(encabezados: list[str]) -> list[str]:
    """Da un nombre único a cada columna: las vacías se numeran como '_col_N',
    las repetidas reciben un sufijo ' (2)', ' (3)', etc. — así ninguna fila de
    datos se pierde ni se sobrescribe al construir el dict por columna."""
    vistos: dict[str, int] = {}
    resultado = []
    for i, h in enumerate(encabezados):
        nombre = h.strip() if h.strip() else f"_col_{i}"
        vistos[nombre] = vistos.get(nombre, 0) + 1
        resultado.append(nombre if vistos[nombre] == 1 else f"{nombre} ({vistos[nombre]})")
    return resultado


def _filas_desde_valores(valores: list[list[str]]) -> list[dict[str, Any]]:
    """Convierte la matriz cruda de celdas (gspread `get_all_values()`) en dicts por
    fila. Detecta el encabezado como la primera fila no completamente en blanco —
    algunos Sheets EPE traen una o más filas vacías antes del encabezado real — y
    deduplica nombres de columna repetidos/vacíos antes de construir cada dict."""
    idx_encabezado = next(
        (i for i, fila in enumerate(valores) if any(c.strip() for c in fila)), None
    )
    if idx_encabezado is None:
        return []
    encabezados = _deduplicar_encabezados(valores[idx_encabezado])
    return [dict(zip(encabezados, fila)) for fila in valores[idx_encabezado + 1:]]
