from agents.novelty_checker import Candidato, candidato_id, score_novedad
from core.pubmed_client import FakePubMedClient

_C = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
              outcome="nivel_tratamiento_requerido", n_disponible=45)


def test_candidato_id_es_slug_estable():
    assert candidato_id(_C) == "riesgo_sistemico_asa_adultos_mayores_nivel_tratamiento_requerido"


def test_score_novedad_alto_cuando_pubmed_vacio():
    client = FakePubMedClient({})
    score, warnings = score_novedad(_C, client)
    assert score == 1.0
    assert warnings == []


def test_score_novedad_bajo_cuando_pubmed_saturado():
    query = (f"{_C.subpoblacion} {_C.eje} {_C.outcome} dental")
    client = FakePubMedClient({query: 500})
    score, warnings = score_novedad(_C, client)
    assert score < 0.2
    assert warnings == []


def test_score_novedad_degrada_a_neutro_si_pubmed_falla():
    client = FakePubMedClient({}, fail=True)
    score, warnings = score_novedad(_C, client)
    assert score == 0.5
    assert "PubMed" in warnings[0]
