from agents.novelty_checker import Candidato
from agents.number_guard import (
    ESTRUCTURALES_DEFAULT,
    estructurales_estudio,
    numeros_legitimos,
    p_legitimos,
    verificar_numeros,
)


def _tablas():
    return {
        "descriptivos": [{"termino": "nivel_tratamiento_requerido", "efecto": 2.34,
                          "ic_inf": 2.10, "ic_sup": 2.58, "p": None}],
        "modelo": [
            {"termino": "riesgo_sistemico_asa", "efecto": 1.87, "ic_inf": 1.20,
             "ic_sup": 2.91, "p": 0.003},
            {"termino": "_cons", "efecto": 0.5, "ic_inf": 0.3, "ic_sup": 0.8, "p": 0.01},
        ],
        "bivariado": {"farmacoterapia_polifarmacia": [
            {"termino": "1", "efecto": 3.1, "ic_inf": 2.0, "ic_sup": 4.2, "p": None},
            {"termino": "2", "efecto": 1.5, "ic_inf": 0.9, "ic_sup": 2.1, "p": None},
        ]},
    }


def test_numeros_legitimos_incluye_efecto_e_ic():
    legit = numeros_legitimos(_tablas())
    assert 1.87 in legit
    assert 1.20 in legit
    assert 2.91 in legit


def test_p_legitimos_sin_redondear():
    p_leg = p_legitimos(_tablas())
    assert 0.003 in p_leg
    assert 0.01 in p_leg


def test_estructurales_estudio_cuenta_covariables_y_bivariado():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="asa3_alto_riesgo",
                 outcome="nivel_tratamiento_requerido",
                 covariables_ajuste=("farmacoterapia_polifarmacia",), n_disponible=1350)
    variables = [
        {"nombre": "nivel_tratamiento_requerido", "rol": "outcome"},
        {"nombre": "riesgo_sistemico_asa", "rol": "exposicion_principal"},
        {"nombre": "farmacoterapia_polifarmacia", "rol": "covariable"},
    ]
    s = estructurales_estudio(c, variables, _tablas())
    assert 1.0 in s
    assert 2.0 in s


def test_estructurales_estudio_descarta_cero():
    c = Candidato(eje="riesgo_sistemico_asa", subpoblacion="adultos",
                 outcome="nivel_tratamiento_requerido", covariables_ajuste=(), n_disponible=50)
    s = estructurales_estudio(c, [], {"bivariado": {}})
    assert 0.0 not in s


def test_verificar_numeros_detecta_cifra_no_legitima():
    ilegit = verificar_numeros("El efecto fue de 9.99 con IC amplio.", legitimos={1.87})
    assert "9.99" in ilegit


def test_verificar_numeros_acepta_cifra_legitima():
    ilegit = verificar_numeros("El efecto fue de 1.87.", legitimos={1.87})
    assert ilegit == []


def test_verificar_numeros_acepta_estructural():
    ilegit = verificar_numeros("Se ajustó por 1 covariable.", legitimos=set(), estructurales={1.0})
    assert ilegit == []


def test_verificar_numeros_convencion_005_y_100():
    ilegit = verificar_numeros(
        "El umbral de significancia fue p < 0,05 sobre el 100% de los casos.",
        legitimos=set(), estructurales=ESTRUCTURALES_DEFAULT, p_leg={0.003},
    )
    assert ilegit == []


def test_verificar_numeros_p_valor_umbral_verificable():
    ilegit = verificar_numeros("p < 0,01", legitimos=set(), p_leg={0.003})
    assert ilegit == []


def test_verificar_numeros_p_valor_no_verificable():
    ilegit = verificar_numeros("p < 0,001", legitimos=set(), p_leg={0.5})
    assert "0,001" in ilegit


def test_verificar_numeros_ignora_citas():
    ilegit = verificar_numeros("Según [4], el hallazgo es consistente.", legitimos=set())
    assert ilegit == []
