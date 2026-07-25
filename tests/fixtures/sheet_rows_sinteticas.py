"""Filas sintéticas con la MISMA forma de columnas que la pestaña 'Marco' real del
Sheet EPE (sampling frame, 1 fila = 1 paciente), incluyendo columnas PHI a propósito
para que test_perfilador.py verifique que perfilador.py las descarta.

Filas 1-6: casos clínicos base (análogos a los anteriores de "Datos", sin
"Categorías IMC" -que Marco no tiene- y con "Lugar de Procedencia" en vez de
"Procedencia/ Referido de Provincia").
Fila 7: DNI en blanco -> registro incompleto, debe descartarse por completo.
Filas 8 y 9: mismo DNI ("11111111") -> solo la fila 8 (primera aparición) debe
contarse; la fila 9 se descarta como duplicado accidental.
"""

FILAS_SINTETICAS = [
    {
        "N° de DNI": "09900807", "Apellidos y Nombres": "REÁTEGUI RUÍZ, JANET",
        "Celular 1": "999999999", "Celular 2": "", "Fecha de nacimiento": "1975-01-01",
        "sexo": "F", "edad atencion": "48", "Grupo etareo": "Adulto",
        "Riesgo sistémico": "ASA2", "Tipo de discapacidad": "Intelectual",
        "Severidad de la discapacidad": "Moderado", "Grado de cooperación": "Positivo",
        "Ubicación del procedimiento": "C",
    },
    {
        "N° de DNI": "06771050", "Apellidos y Nombres": "ORREGO CALLE, FERNANDO",
        "Celular 1": "988888888", "Celular 2": "", "Fecha de nacimiento": "1962-05-05",
        "sexo": "M", "edad atencion": "61", "Grupo etareo": "Adulto mayor",
        "Riesgo sistémico": "ASA3", "Tipo de discapacidad": "Sensorial",
        "Severidad de la discapacidad": "Leve", "Grado de cooperación": "Positivo",
        "Ubicación del procedimiento": "C",
    },
    {
        "N° de DNI": "06254207", "Apellidos y Nombres": "ANGELES PÉREZ, FAUSTA",
        "Celular 1": "977777777", "Celular 2": "", "Fecha de nacimiento": "1953-02-02",
        "sexo": "F", "edad atencion": "71", "Grupo etareo": "Adulto mayor",
        "Riesgo sistémico": "ASA3", "Tipo de discapacidad": "No aplica",
        "Severidad de la discapacidad": "No aplica", "Grado de cooperación": "Positivo",
        "Ubicación del procedimiento": "C",
        "Farmacoterapia": "Ninguna", "Lugar de Procedencia": "Lima",
    },
    {
        "N° de DNI": "07112233", "Apellidos y Nombres": "TORRES VEGA, MILAGROS",
        "Celular 1": "966666666", "Celular 2": "", "Fecha de nacimiento": "1980-03-03",
        "sexo": "F", "edad atencion": "44", "Grupo etareo": "Adulto",
        "Riesgo sistémico": "ASA3", "Tipo de discapacidad": "Física",
        "Severidad de la discapacidad": "Moderado", "Grado de cooperación": "Positivo",
        "Ubicación del procedimiento": "C",
        "Farmacoterapia": "Antihipertensivos", "Lugar de Procedencia": "Provincia",
    },
    {
        "N° de DNI": "08223344", "Apellidos y Nombres": "SILVA LOPEZ, MATEO",
        "Celular 1": "955555555", "Celular 2": "", "Fecha de nacimiento": "2018-06-06",
        "sexo": "M", "edad atencion": "6", "Grupo etareo": "Niño escolar",
        "Riesgo sistémico": "ASA1", "Tipo de discapacidad": "No aplica",
        "Severidad de la discapacidad": "No aplica", "Grado de cooperación": "Negativo",
        "Ubicación del procedimiento": "C",
        "Farmacoterapia": "Ninguna", "Lugar de Procedencia": "Lima",
    },
    {
        "N° de DNI": "09334455", "Apellidos y Nombres": "RAMOS DIAZ, VALERIA",
        "Celular 1": "944444444", "Celular 2": "", "Fecha de nacimiento": "2010-07-07",
        "sexo": "F", "edad atencion": "14", "Grupo etareo": "Adolescente",
        "Riesgo sistémico": "ASA1", "Tipo de discapacidad": "Intelectual",
        "Severidad de la discapacidad": "Leve", "Grado de cooperación": "Positivo",
        "Ubicación del procedimiento": "C",
        "Farmacoterapia": "Anticonvulsivantes", "Lugar de Procedencia": "Provincia",
    },
    {
        # Fila 7: sin DNI -> registro incompleto, debe descartarse por completo.
        "N° de DNI": "", "Apellidos y Nombres": "SIN DNI, REGISTRO",
        "Celular 1": "", "Celular 2": "", "Fecha de nacimiento": "",
        "sexo": "M", "edad atencion": "70", "Grupo etareo": "Adulto mayor",
        "Riesgo sistémico": "ASA1", "Tipo de discapacidad": "No aplica",
        "Severidad de la discapacidad": "No aplica", "Grado de cooperación": "Indeterminado",
        "Ubicación del procedimiento": "C",
    },
    {
        # Fila 8: primera aparición del DNI "11111111" -> debe contarse.
        "N° de DNI": "11111111", "Apellidos y Nombres": "DUPLICADO, PRIMERO",
        "Celular 1": "933333333", "Celular 2": "", "Fecha de nacimiento": "1990-01-01",
        "sexo": "M", "edad atencion": "35", "Grupo etareo": "Adulto",
        "Riesgo sistémico": "ASA2", "Tipo de discapacidad": "No aplica",
        "Severidad de la discapacidad": "No aplica", "Grado de cooperación": "Positivo",
        "Ubicación del procedimiento": "C",
    },
    {
        # Fila 9: mismo DNI que la fila 8 -> duplicado, debe descartarse.
        "N° de DNI": "11111111", "Apellidos y Nombres": "DUPLICADO, SEGUNDO",
        "Celular 1": "922222222", "Celular 2": "", "Fecha de nacimiento": "1990-01-01",
        "sexo": "F", "edad atencion": "35", "Grupo etareo": "Adulto",
        "Riesgo sistémico": "ASA3", "Tipo de discapacidad": "No aplica",
        "Severidad de la discapacidad": "No aplica", "Grado de cooperación": "Negativo",
        "Ubicación del procedimiento": "C",
    },
]
