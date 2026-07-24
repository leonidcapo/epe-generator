import pytest

from core.knowledge import load_plantilla, VocabularioError, Perfil, guardar_perfil, load_perfil


def _escribir(tmp_path, contenido):
    path = tmp_path / "plantilla.yaml"
    path.write_text(contenido, encoding="utf-8")
    return str(path)


def test_load_plantilla_real_epe():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    assert p.causal_permitido is False
    assert p.n_min == 30
    assert "riesgo_sistemico_asa" in p.ejes
    assert "adultos" in p.subpoblaciones
    assert "nivel_tratamiento_requerido" in p.outcomes
    assert p.compatibilidad["riesgo_sistemico_asa"] == frozenset(
        {"adultos", "adultos_mayores", "asa3_alto_riesgo"}
    )


def test_load_plantilla_compatibilidad_referencia_eje_desconocido(tmp_path):
    contenido = """
diseno:
  inferencia_causal_permitida: false
  n_min: 30
ejes:
  - {id: eje_a, estado: candidato}
subpoblaciones:
  - {id: pob_a, estado: candidato}
outcomes:
  - {id: out_a, tipo: binario}
compatibilidad_eje_subpoblacion:
  - {eje: eje_fantasma, subpoblaciones_validas: [pob_a]}
"""
    with pytest.raises(VocabularioError, match="eje_fantasma"):
        load_plantilla(_escribir(tmp_path, contenido))


def test_load_plantilla_compatibilidad_referencia_subpoblacion_desconocida(tmp_path):
    contenido = """
diseno:
  inferencia_causal_permitida: false
  n_min: 30
ejes:
  - {id: eje_a, estado: candidato}
subpoblaciones:
  - {id: pob_a, estado: candidato}
outcomes:
  - {id: out_a, tipo: binario}
compatibilidad_eje_subpoblacion:
  - {eje: eje_a, subpoblaciones_validas: [pob_fantasma]}
"""
    with pytest.raises(VocabularioError, match="pob_fantasma"):
        load_plantilla(_escribir(tmp_path, contenido))


def test_perfil_roundtrip(tmp_path):
    perfil = Perfil(
        n_por_celda={("adultos", "riesgo_sistemico_asa"): 120, ("adultos_mayores", "riesgo_sistemico_asa"): 45},
        distribuciones={"sexo": {"F": 900, "M": 834}},
        generado_en="2026-07-24",
    )
    path = str(tmp_path / "perfil_epe.yaml")
    guardar_perfil(perfil, path)
    cargado = load_perfil(path)
    assert cargado == perfil


def test_perfil_n_por_celda_ausente_devuelve_cero():
    perfil = Perfil(n_por_celda={("adultos", "riesgo_sistemico_asa"): 10},
                    distribuciones={}, generado_en="2026-07-24")
    assert perfil.n(("adolescentes", "riesgo_sistemico_asa")) == 0
    assert perfil.n(("adultos", "riesgo_sistemico_asa")) == 10
