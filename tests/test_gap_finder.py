import json

from agents.gap_finder import generar_espacio, filtrar_factibilidad, rankear
from agents.novelty_checker import Candidato
from core.knowledge import load_plantilla, Perfil
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def test_generar_espacio_respeta_compatibilidad():
    p = _plantilla()
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-24")
    espacio = generar_espacio(p, perfil)
    # cooperacion_manejo_conductual solo es válido para ninos/discapacidad_intelectual
    for c in espacio:
        if c.eje == "cooperacion_manejo_conductual":
            assert c.subpoblacion in {"ninos_preescolares_escolares", "discapacidad_intelectual"}


def test_generar_espacio_adjunta_n_disponible_del_perfil():
    p = _plantilla()
    perfil = Perfil(n_por_celda={("adultos_mayores", "riesgo_sistemico_asa"): 45},
                    distribuciones={}, generado_en="2026-07-24")
    espacio = generar_espacio(p, perfil)
    match = [c for c in espacio if c.eje == "riesgo_sistemico_asa" and c.subpoblacion == "adultos_mayores"]
    assert match and all(c.n_disponible == 45 for c in match)


def test_filtrar_factibilidad_descarta_bajo_n_min():
    p = _plantilla()  # n_min: 30
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos", outcome="grado_cooperacion", n_disponible=10),
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion", n_disponible=45),
    ]
    supervivientes = filtrar_factibilidad(candidatos, p)
    assert len(supervivientes) == 1
    assert supervivientes[0].subpoblacion == "adultos_mayores"


def test_rankear_ok_con_llm_disponible():
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion", n_disponible=45),
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.5, "justificacion": "relevante"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] == 8.5
    assert r.data[0]["novedad"] == 1.0


def test_rankear_degrada_sin_llm():
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion", n_disponible=45),
    ]
    llm = FakeLLMClient(fail=True)
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] is None
    assert "degradado" in r.warnings[0].lower() or "LLM" in r.warnings[0]


def test_rankear_cap_por_eje_limita_diversidad():
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion=f"pob_{i}", outcome="grado_cooperacion", n_disponible=45)
        for i in range(5)
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 9.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, top_n=5, cap_por_eje=2)
    assert len(r.data) == 5  # segunda pasada completa el resto ignorando el cap
    primeros_dos_ejes = {row["candidato"].eje for row in r.data[:2]}
    assert primeros_dos_ejes == {"riesgo_sistemico_asa"}
