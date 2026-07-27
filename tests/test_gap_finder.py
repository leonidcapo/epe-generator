import json

from agents.gap_finder import generar_espacio, filtrar_factibilidad, rankear
from agents.novelty_checker import Candidato
from core.knowledge import load_plantilla, Perfil
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient


def _plantilla():
    return load_plantilla("knowledge/plantilla_epe.yaml")


def test_generar_espacio_excluye_subpoblaciones_con_menos_de_2_ejes():
    p = _plantilla()
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27", n_conjunto={})
    espacio = generar_espacio(p, perfil)
    subpoblaciones_presentes = {c.subpoblacion for c in espacio}
    # adolescentes, discapacidad_fisica, discapacidad_sensorial solo tienen 1 eje
    # implementado compatible -> no generan candidatos multivariados.
    assert "adolescentes" not in subpoblaciones_presentes
    assert "discapacidad_fisica" not in subpoblaciones_presentes
    assert "discapacidad_sensorial" not in subpoblaciones_presentes


def test_generar_espacio_un_candidato_por_eje_como_principal():
    p = _plantilla()
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27",
                    n_conjunto={"discapacidad_intelectual": 40})
    espacio = generar_espacio(p, perfil)
    cands_di = [c for c in espacio if c.subpoblacion == "discapacidad_intelectual"]
    ejes_principales = {c.eje for c in cands_di}
    # 2 ejes compatibles implementados (discapacidad_tipo_severidad,
    # cooperacion_manejo_conductual) -> cada uno aparece una vez como principal.
    assert ejes_principales == {"discapacidad_tipo_severidad", "cooperacion_manejo_conductual"}
    for c in cands_di:
        if c.eje == "discapacidad_tipo_severidad":
            assert c.covariables_ajuste == ("cooperacion_manejo_conductual",)
        else:
            assert c.covariables_ajuste == ("discapacidad_tipo_severidad",)
        assert c.n_disponible == 40


def test_generar_espacio_usa_n_conjunto_no_marginal():
    p = _plantilla()
    perfil = Perfil(n_por_celda={("adultos_mayores", "riesgo_sistemico_asa"): 900},  # marginal alto
                    distribuciones={}, generado_en="2026-07-27",
                    n_conjunto={"adultos_mayores": 5})  # conjunto bajo
    espacio = generar_espacio(p, perfil)
    cands = [c for c in espacio if c.subpoblacion == "adultos_mayores" and c.eje == "riesgo_sistemico_asa"]
    assert cands
    assert all(c.n_disponible == 5 for c in cands)  # no 900 — usa el conjunto, no el marginal


def test_filtrar_factibilidad_descarta_bajo_n_min():
    p = _plantilla()  # n_min: 30
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos", outcome="grado_cooperacion",
                 covariables_ajuste=("procedencia_acceso",), n_disponible=10),
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"), n_disponible=45),
    ]
    supervivientes = filtrar_factibilidad(candidatos, p)
    assert len(supervivientes) == 1
    assert supervivientes[0].subpoblacion == "adultos_mayores"


def test_rankear_ok_con_llm_disponible():
    p = _plantilla()
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"), n_disponible=45),
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.5, "justificacion": "relevante"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, p.terminos_busqueda, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] == 8.5
    assert r.data[0]["novedad"] == 1.0


def test_rankear_degrada_sin_llm():
    p = _plantilla()
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores", outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"), n_disponible=45),
    ]
    llm = FakeLLMClient(fail=True)
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, p.terminos_busqueda, top_n=5, cap_por_eje=2)
    assert r.ok
    assert r.data[0]["score_llm"] is None
    assert "degradado" in r.warnings[0].lower() or "LLM" in r.warnings[0]


def test_rankear_cap_por_eje_limita_diversidad():
    p = _plantilla()
    candidatos = [
        Candidato(eje="riesgo_sistemico_asa", subpoblacion=f"pob_{i}", outcome="grado_cooperacion",
                 covariables_ajuste=(), n_disponible=45)
        for i in range(5)
    ]
    llm = FakeLLMClient(responses=[json.dumps({"score": 9.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = rankear(candidatos, pubmed, llm, p.terminos_busqueda, top_n=5, cap_por_eje=2)
    assert len(r.data) == 5  # segunda pasada completa el resto ignorando el cap
    primeros_dos_ejes = {row["candidato"].eje for row in r.data[:2]}
    assert primeros_dos_ejes == {"riesgo_sistemico_asa"}
