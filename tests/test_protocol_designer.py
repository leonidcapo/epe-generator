import pytest

from agents.protocol_designer import (
    build_estructura,
    build_picot,
    build_variables,
    disenar_protocolo,
    inferir_modelo,
)
from agents.novelty_checker import Candidato, candidato_id
from core.knowledge import load_plantilla
from core.llm_client import FakeLLMClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def _candidato():
    return Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                     outcome="nivel_tratamiento_requerido",
                     covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)


def test_inferir_modelo_categorico_ordinal():
    modelo, anclajes = inferir_modelo("categorico", "ordinal")
    assert modelo == "logistica_ordinal"


def test_inferir_modelo_categorico_nominal():
    modelo, anclajes = inferir_modelo("categorico", "nominal")
    assert modelo == "logistica_multinomial"


def test_inferir_modelo_continuo():
    modelo, anclajes = inferir_modelo("continuo", None)
    assert modelo == "lineal"


def test_inferir_modelo_binario():
    modelo, anclajes = inferir_modelo("binario", None)
    assert modelo == "logistica_binaria"


def test_inferir_modelo_categorico_sin_escala_declarada_lanza_error():
    with pytest.raises(ValueError, match="escala"):
        inferir_modelo("categorico", None)


def test_inferir_modelo_tipo_desconocido_lanza_error():
    with pytest.raises(ValueError, match="tipo"):
        inferir_modelo("inventado", None)


def test_build_picot():
    c = _candidato()
    picot = build_picot(c)
    assert picot["poblacion"] == "asa3_alto_riesgo"
    assert picot["exposicion"] == "riesgo_sistemico_asa"
    assert picot["covariables_ajuste"] == "farmacoterapia_polifarmacia"
    assert picot["outcome"] == "nivel_tratamiento_requerido"
    assert picot["tiempo"] == "transversal (sin seguimiento)"


def test_build_picot_sin_covariables():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                 outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=1350)
    picot = build_picot(c)
    assert picot["covariables_ajuste"] == "(ninguna)"


def test_build_variables():
    c = _candidato()
    p = _plantilla()
    variables = build_variables(c, p)
    assert variables[0] == {"nombre": "nivel_tratamiento_requerido", "rol": "outcome",
                            "tipo": "categorico", "escala": "ordinal"}
    assert {"nombre": "riesgo_sistemico_asa", "rol": "exposicion_principal", "tipo": "categorica"} in variables
    assert {"nombre": "farmacoterapia_polifarmacia", "rol": "covariable", "tipo": "categorica"} in variables
    assert len(variables) == 3


def test_build_estructura_usa_modelo_correcto_para_ordinal():
    c = _candidato()
    p = _plantilla()
    estructura = build_estructura(c, p)
    assert estructura["diseno"]["modelo"] == "logistica_ordinal"
    assert estructura["diseno"]["outcome_tipo"] == "categorico"
    assert estructura["diseno"]["outcome_escala"] == "ordinal"


def test_build_estructura_nominal_para_grado_cooperacion():
    c = Candidato(eje="cooperacion_manejo_conductual", subpoblacion="discapacidad_intelectual",
                 outcome="grado_cooperacion", covariables_ajuste=("discapacidad_tipo_severidad",),
                 n_disponible=131)
    p = _plantilla()
    estructura = build_estructura(c, p)
    assert estructura["diseno"]["modelo"] == "logistica_multinomial"


def test_disenar_protocolo_degrada_sin_llm():
    c = _candidato()
    p = _plantilla()
    r = disenar_protocolo(c, p, [], None)
    assert r.ok
    assert r.data.prosa["introduccion"] == "[prosa pendiente: LLM no disponible]"
    assert any("Prosa no disponible" in w for w in r.warnings)
    assert r.data.candidato_id == candidato_id(c)


def test_disenar_protocolo_con_llm_disponible():
    c = _candidato()
    p = _plantilla()
    llm = FakeLLMClient(responses=["Texto de sección en futuro."])
    r = disenar_protocolo(c, p, [], llm)
    assert r.ok
    assert r.data.prosa["introduccion"] == "Texto de sección en futuro."
    assert r.data.prosa["metodos"] == "Texto de sección en futuro."
    assert r.warnings == []
