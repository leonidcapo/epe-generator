from core.sheets_client import FakeSheetReader, _deduplicar_encabezados, _filas_desde_valores


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


def test_deduplicar_encabezados_columnas_vacias_y_repetidas():
    crudos = ["sexo", "Celular", "Celular", "", "", "edad"]
    resultado = _deduplicar_encabezados(crudos)
    assert resultado == ["sexo", "Celular", "Celular (2)", "_col_3", "_col_4", "edad"]
    assert len(set(resultado)) == len(resultado)  # ninguna colisión


def test_deduplicar_encabezados_preserva_orden_y_longitud():
    crudos = ["a", "b", "c"]
    assert _deduplicar_encabezados(crudos) == ["a", "b", "c"]


def test_filas_desde_valores_salta_fila_en_blanco_antes_del_encabezado():
    valores = [
        ["", "", ""],
        ["sexo", "edad", "Grupo etareo"],
        ["F", "48", "Adulto"],
        ["M", "61", "Adulto mayor"],
    ]
    assert _filas_desde_valores(valores) == [
        {"sexo": "F", "edad": "48", "Grupo etareo": "Adulto"},
        {"sexo": "M", "edad": "61", "Grupo etareo": "Adulto mayor"},
    ]


def test_filas_desde_valores_hoja_totalmente_vacia_devuelve_lista_vacia():
    assert _filas_desde_valores([]) == []
    assert _filas_desde_valores([["", ""], ["", ""]]) == []


def test_filas_desde_valores_multiples_filas_en_blanco_antes_del_encabezado():
    valores = [
        ["", "", ""],
        ["", "", ""],
        ["sexo", "edad"],
        ["F", "48"],
    ]
    assert _filas_desde_valores(valores) == [{"sexo": "F", "edad": "48"}]


def test_filas_desde_valores_sin_fila_en_blanco_funciona_igual():
    valores = [["sexo", "edad"], ["F", "48"]]
    assert _filas_desde_valores(valores) == [{"sexo": "F", "edad": "48"}]
