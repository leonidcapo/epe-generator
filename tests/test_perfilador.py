from agents.perfilador import perfilar, PHI_COLUMNS_EXCLUIDAS
from core.knowledge import load_plantilla
from core.sheets_client import FakeSheetReader
from tests.fixtures.sheet_rows_sinteticas import FILAS_SINTETICAS


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def test_perfilar_excluye_columnas_phi():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = perfilar(reader, _plantilla())
    assert r.ok
    perfil = r.data
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda) + str(perfil.n_conjunto)
    for col in PHI_COLUMNS_EXCLUIDAS:
        assert col not in texto_completo
    # ningún valor de DNI/nombre/celular sobrevive en ninguna distribución
    assert "09900807" not in texto_completo
    assert "REÁTEGUI" not in texto_completo
    # el DNI usado para deduplicar tampoco debe sobrevivir
    assert "11111111" not in texto_completo


def test_perfilar_agrega_distribucion_por_variable():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.distribuciones["sexo"] == {"F": 4, "M": 3}
    assert perfil.distribuciones["Riesgo sistémico"] == {"ASA2": 2, "ASA3": 3, "ASA1": 2}


def test_perfilar_calcula_n_por_celda_subpoblacion_eje():
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n(("adultos_mayores", "riesgo_sistemico_asa")) == 2
    # 3: filas 1 y 4 (Adulto) + fila 8 (Adulto, DNI único tras dedupe)
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 3


def test_perfilar_n_por_celda_discapacidad_intelectual_x_tipo_severidad():
    # Filas con Tipo de discapacidad == "Intelectual": fila 1 (Adulto) y fila 6 (Adolescente).
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n(("discapacidad_intelectual", "discapacidad_tipo_severidad")) == 2


def test_perfilar_n_por_celda_farmacoterapia_excluye_ninguna():
    # "Ninguna" es un sentinel de "no aplica" (filas 3 y 5), no debe contar como
    # farmacoterapia presente. Solo filas 4 (Torres, Antihipertensivos) y 6 (Ramos,
    # Anticonvulsivantes) tienen medicación real.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    # Fila 3 (Fausta Ángeles, Adulto mayor, "Ninguna") no debe contar.
    assert perfil.n(("adultos_mayores", "farmacoterapia_polifarmacia")) == 0
    # Fila 5 (Mateo Silva, ninos_preescolares_escolares, "Ninguna") no debe contar.
    assert perfil.n(("ninos_preescolares_escolares", "farmacoterapia_polifarmacia")) == 0
    # Fila 4 (Milagros Torres, "Antihipertensivos") sí cuenta: adultos, discapacidad_fisica,
    # asa3_alto_riesgo.
    assert perfil.n(("adultos", "farmacoterapia_polifarmacia")) == 1
    assert perfil.n(("discapacidad_fisica", "farmacoterapia_polifarmacia")) == 1
    assert perfil.n(("asa3_alto_riesgo", "farmacoterapia_polifarmacia")) == 1
    # Fila 6 (Valeria Ramos, "Anticonvulsivantes") sí cuenta: adolescentes,
    # discapacidad_intelectual.
    assert perfil.n(("adolescentes", "farmacoterapia_polifarmacia")) == 1
    assert perfil.n(("discapacidad_intelectual", "farmacoterapia_polifarmacia")) == 1
    # Total de la celda del eje en todo el perfil: exactamente 5 (3 de fila 4 + 2 de fila 6).
    total = sum(
        n for (sp, eje), n in perfil.n_por_celda.items()
        if eje == "farmacoterapia_polifarmacia"
    )
    assert total == 5


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
    perfil = perfilar(reader, _plantilla()).data
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
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) >= 1
    assert perfil.n(("asa3_alto_riesgo", "riesgo_sistemico_asa")) >= 1
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 3
    assert perfil.n(("asa3_alto_riesgo", "riesgo_sistemico_asa")) == 3


def test_perfilar_descarta_columna_desconocida_no_blocklisteada():
    filas = [dict(f) for f in FILAS_SINTETICAS]
    for f in filas:
        f["Direccion"] = "AV FICTICIA 123"
    reader = FakeSheetReader(filas)
    r = perfilar(reader, _plantilla())
    assert r.ok
    perfil = r.data
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda)
    assert "AV FICTICIA" not in texto_completo
    assert "Direccion" not in texto_completo


def test_perfilar_conexion_fallida_produce_failure():
    reader = FakeSheetReader([], fail=True)
    r = perfilar(reader, _plantilla())
    assert not r.ok
    assert "simulado" in r.warnings[0]


def test_perfilar_sheet_vacio_produce_perfil_vacio_sin_crashear():
    reader = FakeSheetReader([])
    r = perfilar(reader, _plantilla())
    assert r.ok
    assert r.data.n_por_celda == {}


def test_perfilar_descarta_fila_sin_dni():
    # Fila 7 (sin DNI) es un registro incompleto: no debe contar en ninguna celda ni
    # distribución. Su valor sentinel "Indeterminado" (Grado de cooperación) no debe
    # aparecer en ningún lado.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    texto_completo = str(perfil.distribuciones) + str(perfil.n_por_celda)
    assert "Indeterminado" not in texto_completo
    assert perfil.distribuciones["Grado de cooperación"] == {"Positivo": 6, "Negativo": 1}


def test_perfilar_deduplica_dni_repetido_se_queda_con_la_primera_fila():
    # Filas 8 y 9 comparten DNI "11111111" pero tienen "Grado de cooperación"
    # distinto (Positivo vs Negativo) y sexo distinto (M vs F). Solo la fila 8
    # (primera aparición) debe sobrevivir.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    # Si la fila 9 (Negativo) se hubiera colado, este total sería 2 en vez de 1.
    assert perfil.distribuciones["Grado de cooperación"]["Negativo"] == 1
    # Si la fila 9 (sexo F) se hubiera colado, "F" sería 5 y "M" 2.
    assert perfil.distribuciones["sexo"] == {"F": 4, "M": 3}


def test_perfilar_estado_nutricional_imc_nunca_aparece():
    # Marco no tiene "Categorías IMC": este eje debe estar estructuralmente ausente
    # de n_por_celda, no solo en cero para los datos de este fixture.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    ejes_presentes = {eje for (_, eje) in perfil.n_por_celda}
    assert "estado_nutricional_imc" not in ejes_presentes


def test_perfilar_n_conjunto_ninos_preescolares_escolares():
    # Universo implementado de ninos_preescolares_escolares: {cooperacion_manejo_conductual,
    # procedencia_acceso}. Solo la fila 5 (Mateo Silva, Niño escolar) pertenece a esta
    # subpoblación, y tiene AMBOS ejes presentes (Grado de cooperación="Negativo" truthy,
    # Lugar de Procedencia="Lima") -> cuenta.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["ninos_preescolares_escolares"] == 1


def test_perfilar_n_conjunto_adultos():
    # Universo implementado de adultos: {riesgo_sistemico_asa, procedencia_acceso}.
    # Fila 1 (Reátegui): no tiene Lugar de Procedencia -> no cuenta.
    # Fila 4 (Torres Vega): tiene ambos -> cuenta.
    # Fila 8 (Duplicado primero): no tiene Lugar de Procedencia -> no cuenta.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["adultos"] == 1


def test_perfilar_n_conjunto_adultos_mayores_insuficiente():
    # Universo implementado de adultos_mayores: {riesgo_sistemico_asa,
    # farmacoterapia_polifarmacia, procedencia_acceso}. Ninguna de las filas 2 (Orrego,
    # sin farmacoterapia/procedencia) ni 3 (Ángeles, Farmacoterapia="Ninguna" -> excluida
    # del eje) tiene los TRES ejes simultáneamente -> el n conjunto es 0, aunque el n
    # marginal de riesgo_sistemico_asa para esta subpoblación sea 2.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["adultos_mayores"] == 0
    assert perfil.n(("adultos_mayores", "riesgo_sistemico_asa")) == 2  # marginal, para contraste


def test_perfilar_n_conjunto_discapacidad_intelectual():
    # Universo implementado: {discapacidad_tipo_severidad, cooperacion_manejo_conductual}.
    # Fila 1 (Reátegui, Intelectual, Grado="Positivo") y fila 6 (Ramos, Intelectual,
    # Grado="Positivo") tienen ambos ejes -> cuenta 2.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["discapacidad_intelectual"] == 2


def test_perfilar_n_conjunto_asa3_alto_riesgo():
    # Universo implementado: {riesgo_sistemico_asa, farmacoterapia_polifarmacia}.
    # Fila 2 (Orrego, ASA3, sin farmacoterapia) y fila 3 (Ángeles, ASA3,
    # Farmacoterapia="Ninguna") no califican. Fila 4 (Torres Vega, ASA3,
    # Farmacoterapia="Antihipertensivos") sí -> cuenta 1.
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert perfil.n_conjunto["asa3_alto_riesgo"] == 1


def test_perfilar_n_conjunto_dni_nunca_aparece():
    # El DNI "11111111" usado internamente para deduplicar no debe sobrevivir en
    # n_conjunto tampoco (mismo principio que el resto del perfil).
    reader = FakeSheetReader(FILAS_SINTETICAS)
    perfil = perfilar(reader, _plantilla()).data
    assert "11111111" not in str(perfil.n_conjunto)
