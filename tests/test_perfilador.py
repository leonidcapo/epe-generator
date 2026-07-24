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
    assert perfil.distribuciones["sexo"] == {"F": 4, "M": 2}
    assert perfil.distribuciones["Riesgo sistémico"] == {"ASA2": 1, "ASA3": 3, "ASA1": 2}


def test_perfilar_calcula_n_por_celda_subpoblacion_eje():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    # 2 filas son "Adulto mayor" -> n de la celda (adultos_mayores, riesgo_sistemico_asa) = 2
    assert perfil.n(("adultos_mayores", "riesgo_sistemico_asa")) == 2
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 2


def test_perfilar_n_por_celda_discapacidad_intelectual_x_tipo_severidad():
    # Filas con Tipo de discapacidad == "Intelectual": fila 1 (Adulto) y fila 6 (Adolescente).
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    assert perfil.n(("discapacidad_intelectual", "discapacidad_tipo_severidad")) == 2


def test_perfilar_cubre_al_menos_5_de_6_ejes_en_scope():
    ejes_en_scope = [
        "riesgo_sistemico_asa",
        "discapacidad_tipo_severidad",
        "cooperacion_manejo_conductual",
        "estado_nutricional_imc",
        "farmacoterapia_polifarmacia",
        "procedencia_acceso",
    ]
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    cubiertos = 0
    for eje_id in ejes_en_scope:
        total = sum(n for (sp, eje), n in perfil.n_por_celda.items() if eje == eje_id)
        if total > 0:
            cubiertos += 1
    assert cubiertos >= 5


def test_perfilar_fila_cuenta_en_dos_subpoblaciones_simultaneamente():
    # Fila 4 (Milagros Torres) es "Adulto" + Riesgo sistémico "ASA3":
    # debe contar tanto en adultos como en asa3_alto_riesgo, para el mismo eje.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader).data
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) >= 1
    assert perfil.n(("asa3_alto_riesgo", "riesgo_sistemico_asa")) >= 1
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 2
    assert perfil.n(("asa3_alto_riesgo", "riesgo_sistemico_asa")) == 3


def test_perfilar_descarta_columna_desconocida_no_blocklisteada():
    filas = [dict(f) for f in FILAS_SINTETICAS]
    for f in filas:
        f["Direccion"] = "AV FICTICIA 123"
    reader = FakeSheetReader(filas)
    r = perfilar(reader)
    assert r.ok
    perfil = r.data
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda)
    assert "AV FICTICIA" not in texto_completo
    assert "Direccion" not in texto_completo


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
