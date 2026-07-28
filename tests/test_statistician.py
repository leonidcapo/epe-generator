from agents.novelty_checker import Candidato, candidato_id
from agents.statistician import generar_do
from core.knowledge import Plantilla, load_plantilla


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def _plantilla_sintetica(outcome_tipo: str, outcome_escala: str | None = None) -> Plantilla:
    """La plantilla real de hoy no declara ningun outcome binario/continuo (ver
    docs/superpowers/specs/2026-07-28-fase-design-protocolo-design.md §3) — se construye
    una Plantilla minima para probar esas dos ramas del mapeo modelo->comando."""
    return Plantilla(
        ejes={"exposicion_x": "candidato"},
        subpoblaciones={"poblacion_y": "candidato"},
        outcomes={"outcome_z": outcome_tipo},
        outcomes_escala={"outcome_z": outcome_escala} if outcome_escala else {},
        compatibilidad={"exposicion_x": frozenset({"poblacion_y"})},
        causal_permitido=False,
        n_min=30,
        terminos_busqueda={},
    )


def test_generar_do_ordinal_incluye_encabezado_y_bloques():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                 outcome="nivel_tratamiento_requerido",
                 covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)
    texto = generar_do(c, _plantilla())
    assert candidato_id(c) in texto
    assert 'use "datos.dta", clear' in texto
    assert "* filtrar a subpoblacion: asa3_alto_riesgo" in texto
    assert "sheet(descriptivos)" in texto
    assert "sheet(bivariado_riesgo_sistemico_asa)" in texto
    assert "sheet(bivariado_farmacoterapia_polifarmacia)" in texto
    assert "sheet(modelo)" in texto
    assert "ologit nivel_tratamiento_requerido riesgo_sistemico_asa farmacoterapia_polifarmacia" in texto
    assert "svy" not in texto.lower()


def test_generar_do_nominal_usa_mlogit():
    c = Candidato(eje="cooperacion_manejo_conductual", subpoblacion="discapacidad_intelectual",
                 outcome="grado_cooperacion", covariables_ajuste=("discapacidad_tipo_severidad",),
                 n_disponible=131)
    texto = generar_do(c, _plantilla())
    assert "mlogit grado_cooperacion cooperacion_manejo_conductual discapacidad_tipo_severidad" in texto


def test_generar_do_sin_covariables_no_deja_espacio_colgante():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos",
                 outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=200)
    texto = generar_do(c, _plantilla())
    assert "* covariables de ajuste: (ninguna)" in texto
    assert "ologit nivel_tratamiento_requerido riesgo_sistemico_asa" in texto
    assert "ologit nivel_tratamiento_requerido riesgo_sistemico_asa \n" not in texto


def test_generar_do_binario_usa_logistic():
    p = _plantilla_sintetica("binario")
    c = Candidato(eje="exposicion_x", subpoblacion="poblacion_y", outcome="outcome_z",
                 covariables_ajuste=(), n_disponible=50)
    texto = generar_do(c, p)
    assert "logistic outcome_z exposicion_x" in texto


def test_generar_do_continuo_usa_regress():
    p = _plantilla_sintetica("continuo")
    c = Candidato(eje="exposicion_x", subpoblacion="poblacion_y", outcome="outcome_z",
                 covariables_ajuste=(), n_disponible=50)
    texto = generar_do(c, p)
    assert "regress outcome_z exposicion_x" in texto
