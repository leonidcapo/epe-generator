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
        "Farmacoterapia": "Ninguna", "Procedencia/ Referido de Provincia": "No",
    },
    {
        "Insertar N° de DNI": "07112233", "Apellidos y Nombres": "TORRES VEGA, MILAGROS",
        "N° de HC": "00312455", "Celular": "966666666", "Fecha de Nacimiento": "1980-03-03",
        "sexo": "F", "edad": "44", "Grupo etareo": "Adulto", "Riesgo sistémico": "ASA3",
        "Tipo de discapacidad": "Física", "Severidad de la discapacidad": "Moderado",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Sobrepeso",
        "Farmacoterapia": "Antihipertensivos", "Procedencia/ Referido de Provincia": "Sí",
    },
    {
        "Insertar N° de DNI": "08223344", "Apellidos y Nombres": "SILVA LOPEZ, MATEO",
        "N° de HC": "00312999", "Celular": "955555555", "Fecha de Nacimiento": "2018-06-06",
        "sexo": "M", "edad": "6", "Grupo etareo": "Niño escolar", "Riesgo sistémico": "ASA1",
        "Tipo de discapacidad": "No aplica", "Severidad de la discapacidad": "No aplica",
        "Grado de cooperación": "Negativo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Normal",
        "Farmacoterapia": "Ninguna", "Procedencia/ Referido de Provincia": "No",
    },
    {
        "Insertar N° de DNI": "09334455", "Apellidos y Nombres": "RAMOS DIAZ, VALERIA",
        "N° de HC": "00313111", "Celular": "944444444", "Fecha de Nacimiento": "2010-07-07",
        "sexo": "F", "edad": "14", "Grupo etareo": "Adolescente", "Riesgo sistémico": "ASA1",
        "Tipo de discapacidad": "Intelectual", "Severidad de la discapacidad": "Leve",
        "Grado de cooperación": "Positivo", "Ubicación del procedimiento": "C",
        "Categorías IMC": "Bajo peso",
        "Farmacoterapia": "Anticonvulsivantes", "Procedencia/ Referido de Provincia": "Sí",
    },
]
