from agents.novelty_checker import Candidato, _query, candidato_id, score_novedad
from core.knowledge import load_plantilla
from core.pubmed_client import FakePubMedClient

_C = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
              outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=45)

_TERMINOS = {
    "ejes": {"riesgo_sistemico_asa": "ASA physical status classification"},
    "subpoblaciones": {"adultos_mayores": "older adults"},
    "outcomes": {"nivel_tratamiento_requerido": "dental treatment complexity"},
}


def test_candidato_id_sin_covariables_mantiene_formato_anterior():
    assert candidato_id(_C) == "riesgo_sistemico_asa_adultos_mayores_nivel_tratamiento_requerido"


def test_candidato_id_incluye_covariables_de_ajuste():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="nivel_tratamiento_requerido",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"),
                 n_disponible=45)
    assert candidato_id(c) == (
        "riesgo_sistemico_asa_adultos_mayores_nivel_tratamiento_requerido"
        "_adj_farmacoterapia_polifarmacia_procedencia_acceso"
    )


def test_score_novedad_alto_cuando_pubmed_vacio():
    client = FakePubMedClient({})
    score, warnings = score_novedad(_C, client, _TERMINOS)
    assert score == 1.0
    assert warnings == []


def test_score_novedad_bajo_cuando_pubmed_saturado():
    query = _query(_C, _TERMINOS)
    client = FakePubMedClient({query: 500})
    score, warnings = score_novedad(_C, client, _TERMINOS)
    assert score < 0.2
    assert warnings == []


def test_score_novedad_degrada_a_neutro_si_pubmed_falla():
    client = FakePubMedClient({}, fail=True)
    score, warnings = score_novedad(_C, client, _TERMINOS)
    assert score == 0.5
    assert "PubMed" in warnings[0]


def test_query_usa_terminos_traducidos_de_la_plantilla_real():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                  outcome="grado_cooperacion", covariables_ajuste=(), n_disponible=45)
    query = _query(c, p.terminos_busqueda)
    assert "ASA physical status classification" in query
    assert "older adults" in query
    assert "patient cooperation behavior management" in query
    # no debe contener los slugs crudos con guion bajo
    assert "riesgo_sistemico_asa" not in query
    assert "adultos_mayores" not in query
    assert "grado_cooperacion" not in query


def test_query_degrada_a_id_crudo_si_falta_termino():
    c = Candidato(eje="eje_sin_termino", subpoblacion="adultos_mayores",
                  outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=45)
    query = _query(c, _TERMINOS)
    assert "eje_sin_termino" in query
    assert "older adults" in query
    assert "dental treatment complexity" in query
