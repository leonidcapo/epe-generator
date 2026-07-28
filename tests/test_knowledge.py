import pytest

from core.knowledge import load_plantilla, VocabularioError, Perfil, guardar_perfil, load_perfil
from core.knowledge import ejes_implementados_por_subpoblacion


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


def test_load_plantilla_terminos_busqueda_referencia_id_desconocido(tmp_path):
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
terminos_busqueda:
  ejes:
    eje_fantasma: "algo"
"""
    with pytest.raises(VocabularioError, match="eje_fantasma"):
        load_plantilla(_escribir(tmp_path, contenido))


def test_load_plantilla_real_carga_terminos_busqueda():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    assert p.terminos_busqueda["ejes"]["riesgo_sistemico_asa"] == "ASA physical status classification"
    assert p.terminos_busqueda["subpoblaciones"]["adultos_mayores"] == "older adults"
    assert p.terminos_busqueda["outcomes"]["grado_cooperacion"] == "patient cooperation behavior management"


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


def test_ejes_implementados_por_subpoblacion_excluye_ejes_sin_datos():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    universos = ejes_implementados_por_subpoblacion(p)
    # adultos es compatible con morbilidad_cie11_sistemas y estado_nutricional_imc en la
    # plantilla, pero ninguno tiene columna de datos real (estado: sin_datos) -> deben
    # quedar fuera del universo implementado.
    assert universos["adultos"] == frozenset({"riesgo_sistemico_asa", "procedencia_acceso"})
    assert universos["adultos_mayores"] == frozenset(
        {"riesgo_sistemico_asa", "farmacoterapia_polifarmacia", "procedencia_acceso"}
    )
    assert universos["discapacidad_intelectual"] == frozenset(
        {"discapacidad_tipo_severidad", "cooperacion_manejo_conductual"}
    )
    assert universos["asa3_alto_riesgo"] == frozenset(
        {"riesgo_sistemico_asa", "farmacoterapia_polifarmacia"}
    )
    # subpoblaciones con un solo eje compatible siguen apareciendo (universo tamaño 1);
    # es tarea de gap_finder decidir que tamaño <2 no genera candidatos multivariados.
    assert universos["adolescentes"] == frozenset({"procedencia_acceso"})
    assert universos["discapacidad_fisica"] == frozenset({"discapacidad_tipo_severidad"})
    assert universos["discapacidad_sensorial"] == frozenset({"discapacidad_tipo_severidad"})


def test_perfil_n_conjunto_default_vacio():
    perfil = Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27")
    assert perfil.n_conjunto == {}


def test_perfil_roundtrip_incluye_n_conjunto(tmp_path):
    perfil = Perfil(
        n_por_celda={("adultos", "riesgo_sistemico_asa"): 120},
        distribuciones={"sexo": {"F": 900, "M": 834}},
        generado_en="2026-07-27",
        n_conjunto={"adultos": 45, "adultos_mayores": 30},
    )
    path = str(tmp_path / "perfil_epe.yaml")
    guardar_perfil(perfil, path)
    cargado = load_perfil(path)
    assert cargado == perfil


def test_load_perfil_perfil_viejo_sin_n_conjunto_degrada_a_vacio(tmp_path):
    # Un perfil_epe.yaml cacheado ANTES de esta migración no tiene la clave n_conjunto.
    contenido = """
n_por_celda:
  - {subpoblacion: adultos, eje: riesgo_sistemico_asa, n: 10}
distribuciones: {}
generado_en: '2026-07-01'
"""
    path = tmp_path / "perfil_viejo.yaml"
    path.write_text(contenido, encoding="utf-8")
    perfil = load_perfil(str(path))
    assert perfil.n_conjunto == {}


def test_load_plantilla_outcomes_escala():
    p = load_plantilla("knowledge/plantilla_epe.yaml")
    assert p.outcomes_escala == {
        "nivel_tratamiento_requerido": "ordinal",
        "ubicacion_procedimiento": "nominal",
        "grado_cooperacion": "nominal",
    }
    assert "ubicacion_procedimiento_sop_vs_consultorio" not in p.outcomes
    assert p.outcomes["ubicacion_procedimiento"] == "categorico"
