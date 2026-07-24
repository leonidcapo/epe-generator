from core.sheets_client import FakeSheetReader


def test_fake_sheet_reader_devuelve_filas_inyectadas():
    filas = [{"sexo": "F", "edad": "48"}, {"sexo": "M", "edad": "61"}]
    reader = FakeSheetReader(filas)
    assert reader.leer_filas() == filas


def test_fake_sheet_reader_puede_simular_fallo():
    reader = FakeSheetReader([], fail=True)
    try:
        reader.leer_filas()
        assert False, "debía lanzar"
    except ConnectionError as exc:
        assert "simulado" in str(exc)
