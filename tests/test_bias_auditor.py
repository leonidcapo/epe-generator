from agents.bias_auditor import auditar, escanear_causal, limitaciones_aplicables, load_limitaciones
from core.llm_client import FakeLLMClient


def _limitaciones():
    return load_limitaciones("knowledge/limitaciones_epe.yaml")


def _ctx(covariables):
    return {
        "subpoblacion": "adultos",
        "eje": "riesgo_sistemico_asa",
        "outcome": "grado_cooperacion",
        "outcome_tipo": "categorico",
        "modelo": "logistica_multinomial",
        "covariables": covariables,
    }


def test_load_limitaciones_epe():
    lims = _limitaciones()
    ids = {l.id for l in lims}
    assert "ausencia_causalidad" in ids
    assert "cohorte_hospital_unico" in ids
    assert "dependencia_registro_clinico" in ids
    assert "variables_limitadas_al_registro" in ids
    assert "calidad_de_registro" in ids
    assert "covariables_no_exhaustivas" in ids


def test_limitaciones_aplica_siempre_causalidad_y_representatividad():
    lims = _limitaciones()
    aplicables = limitaciones_aplicables(_ctx([]), lims)
    ids = {l.id for l in aplicables}
    assert "ausencia_causalidad" in ids
    assert "cohorte_hospital_unico" in ids
    # covariables_no_exhaustivas NO debe aplicar sin covariables (aplica_si lo condiciona)
    assert "covariables_no_exhaustivas" not in ids


def test_limitaciones_covariables_no_exhaustivas_aplica_con_covariables():
    lims = _limitaciones()
    aplicables = limitaciones_aplicables(_ctx(["farmacoterapia_polifarmacia"]), lims)
    ids = {l.id for l in aplicables}
    assert "covariables_no_exhaustivas" in ids


def test_escanear_causal_detecta_lenguaje_causal():
    texto = "El riesgo sistémico causa un aumento en el nivel de tratamiento requerido."
    assert "causa" in escanear_causal(texto)


def test_escanear_causal_ignora_negaciones():
    texto = "No fue posible establecer causa alguna entre las variables."
    assert escanear_causal(texto) == []


def test_auditar_marca_lenguaje_causal_sin_llm():
    lims = _limitaciones()
    textos, warnings = auditar(
        _ctx([]), "El riesgo sistémico causa el nivel de tratamiento.", lims, llm_client=None
    )
    assert any("Lenguaje causal" in w for w in warnings)


def test_auditar_confusion_residual_pocas_covariables():
    lims = _limitaciones()
    textos, warnings = auditar(
        _ctx(["farmacoterapia_polifarmacia"]), "Texto sin lenguaje causal.", lims, llm_client=None
    )
    assert any("confusión residual" in w for w in warnings)


def test_auditar_sin_confusion_residual_con_varias_covariables():
    lims = _limitaciones()
    textos, warnings = auditar(
        _ctx(["farmacoterapia_polifarmacia", "procedencia_acceso"]),
        "Texto sin lenguaje causal.", lims, llm_client=None,
    )
    assert not any("confusión residual" in w for w in warnings)


def test_auditar_devuelve_textos_de_todas_las_limitaciones_aplicables():
    lims = _limitaciones()
    textos, warnings = auditar(_ctx([]), "Texto sin lenguaje causal.", lims, llm_client=None)
    assert len(textos) >= 5  # las 5 aplica_siempre: true del catálogo


def test_auditar_llm_confirma_causal():
    lims = _limitaciones()
    llm = FakeLLMClient(responses=["SI"])
    textos, warnings = auditar(_ctx([]), "El riesgo sistémico causa el nivel de tratamiento.", lims, llm_client=llm)
    assert any("Lenguaje causal" in w for w in warnings)


def test_auditar_llm_descarta_falso_positivo():
    lims = _limitaciones()
    llm = FakeLLMClient(responses=["NO"])
    textos, warnings = auditar(_ctx([]), "El riesgo sistémico causa el nivel de tratamiento.", lims, llm_client=llm)
    assert not any("Lenguaje causal" in w for w in warnings)
