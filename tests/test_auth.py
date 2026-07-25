from core.auth import verificar_credenciales


def test_verificar_credenciales_correctas():
    assert verificar_credenciales("leo", "s3cret", "leo", "s3cret") is True


def test_verificar_credenciales_usuario_incorrecto():
    assert verificar_credenciales("otro", "s3cret", "leo", "s3cret") is False


def test_verificar_credenciales_password_incorrecta():
    assert verificar_credenciales("leo", "mala", "leo", "s3cret") is False


def test_verificar_credenciales_ambas_incorrectas():
    assert verificar_credenciales("otro", "mala", "leo", "s3cret") is False


def test_verificar_credenciales_config_vacia_usuario_real_ausente():
    assert verificar_credenciales("leo", "s3cret", "", "s3cret") is False


def test_verificar_credenciales_config_vacia_password_real_ausente():
    assert verificar_credenciales("leo", "s3cret", "leo", "") is False


def test_verificar_credenciales_config_totalmente_vacia():
    assert verificar_credenciales("", "", "", "") is False


def test_verificar_credenciales_entradas_vacias_contra_config_real():
    assert verificar_credenciales("", "", "leo", "s3cret") is False
