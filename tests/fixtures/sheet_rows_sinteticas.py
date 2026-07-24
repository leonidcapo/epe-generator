"""Filas sintéticas con la MISMA forma de columnas que la pestaña 'Datos' real del
Sheet EPE (ver memoria project-hospital-pnp-odonto), incluyendo columnas PHI a
propósito para que test_perfilador.py verifique que perfilador.py las descarta."""

FILAS_SINTETICAS = [
    {
        "Insertar N° de DNI": "09900807", "Apellidos y Nombres": "REÁTEGUI RUÍZ, JANET",
        "N° de HC": "00478220", "Celular": "999999999", "Fecha de Nacimiento": "1975-01-01",
        "sexo": "F", "edad": "48", "Grupo etareo": "Adulto", "Riesgo sistémico": "ASA2",
        "Tipo de discapacidad": "Intelectual", "Severidad de la discapacidad": "Moderado",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Normal",
    },
    {
        "Insertar N° de DNI": "06771050", "Apellidos y Nombres": "ORREGO CALLE, FERNANDO",
        "N° de HC": "00255163", "Celular": "988888888", "Fecha de Nacimiento": "1962-05-05",
        "sexo": "M", "edad": "61", "Grupo etareo": "Adulto mayor", "Riesgo sistémico": "ASA3",
        "Tipo de discapacidad": "Sensorial", "Severidad de la discapacidad": "Leve",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Sobrepeso",
    },
    {
        "Insertar N° de DNI": "06254207", "Apellidos y Nombres": "ANGELES PÉREZ, FAUSTA",
        "N° de HC": "00059849", "Celular": "977777777", "Fecha de Nacimiento": "1953-02-02",
        "sexo": "F", "edad": "71", "Grupo etareo": "Adulto mayor", "Riesgo sistémico": "ASA3",
        "Tipo de discapacidad": "No aplica", "Severidad de la discapacidad": "No aplica",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Normal",
    },
]
