import json

from agents.novelty_checker import Candidato
from ui_render import render_candidatos_md, render_candidatos_json


def _fila():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="grado_cooperacion",
                 covariables_ajuste=("farmacoterapia_polifarmacia", "procedencia_acceso"),
                 n_disponible=45)
    return {"candidato": c, "score_llm": 8.5, "justificacion": "relevante", "novedad": 0.9}


def test_render_candidatos_md_incluye_datos_clave():
    md = render_candidatos_md([_fila()], warnings=["aviso x"])
    assert "riesgo_sistemico_asa" in md
    assert "adultos_mayores" in md
    assert "n disponible (conjunto): 45" in md
    assert "farmacoterapia_polifarmacia" in md
    assert "procedencia_acceso" in md
    assert "aviso x" in md


def test_render_candidatos_md_sin_covariables_muestra_ninguna():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos_mayores",
                 outcome="grado_cooperacion", covariables_ajuste=(), n_disponible=45)
    fila = {"candidato": c, "score_llm": None, "justificacion": "", "novedad": 0.5}
    md = render_candidatos_md([fila], warnings=[])
    assert "(ninguna)" in md


def test_render_candidatos_md_vacio():
    md = render_candidatos_md([], warnings=[])
    assert "No se generaron candidatos" in md


def test_render_candidatos_json_roundtrip_campos():
    data = json.loads(render_candidatos_json([_fila()]))
    assert data[0]["eje"] == "riesgo_sistemico_asa"
    assert data[0]["n_disponible"] == 45
    assert data[0]["score_llm"] == 8.5
    assert data[0]["covariables_ajuste"] == ["farmacoterapia_polifarmacia", "procedencia_acceso"]
