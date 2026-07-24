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
        return ws.get_all_records()
