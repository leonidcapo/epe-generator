from agents.perfilador import perfilar, PHI_COLUMNS_EXCLUIDAS
from core.sheets_client import FakeSheetReader
from tests.fixtures.sheet_rows_sinteticas import FILAS_SINTETICAS


def test_perfilar_excluye_columnas_phi():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = perfilar(reader)
    assert r.ok
    perfil = r.data
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda)
    for col in PHI_COLUMNS_EXCLUIDAS:
        assert col not in texto_completo
    # ningún valor de DNI/nombre/celular sobrevive en ninguna distribución
    assert "09900807" not in texto_completo
    assert "REÁTEGUI" not in texto_completo


def test_perfilar_agrega_distribucion_por_variable():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    assert perfil.distribuciones["sexo"] == {"F": 2, "M": 1}
    assert perfil.distribuciones["Riesgo sistémico"] == {"ASA2": 1, "ASA3": 2}


def test_perfilar_calcula_n_por_celda_subpoblacion_eje():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    # 2 filas son "Adulto mayor" -> n de la celda (adultos_mayores, riesgo_sistemico_asa) = 2
    assert perfil.n(("adultos_mayores", "riesgo_sistemico_asa")) == 2
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 1


def test_perfilar_conexion_fallida_produce_failure():
    reader = FakeSheetReader([], fail=True)
    r = perfilar(reader)
    assert not r.ok
    assert "simulado" in r.warnings[0]


def test_perfilar_sheet_vacio_produce_perfil_vacio_sin_crashear():
    reader = FakeSheetReader([])
    r = perfilar(reader)
    assert r.ok
    assert r.data.n_por_celda == {}
