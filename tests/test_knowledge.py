import pytest

from core.knowledge import load_plantilla, VocabularioError


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
