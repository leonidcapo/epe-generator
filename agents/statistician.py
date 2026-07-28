from __future__ import annotations

import time

from agents.novelty_checker import Candidato, candidato_id
from agents.protocol_designer import build_estructura
from core.knowledge import Plantilla

_COMANDO_POR_MODELO = {
    "logistica_ordinal": "ologit",
    "logistica_multinomial": "mlogit",
    "logistica_binaria": "logistic",
    "lineal": "regress",
}

_MAX_HOJA = 31


def mapeo_hojas_bivariado(predictores: list[str]) -> dict[str, str]:
    """Nombre de hoja Excel/Stata (<=31 caracteres, limite duro OOXML) para cada
    predictor del bloque bivariado, en el mismo orden que se escriben en el .do.
    Determinista: report vuelve a llamar esta funcion con los mismos predictores
    (en el mismo orden) para recuperar que covariable real corresponde a cada
    hoja, en vez de intentar deshacer un truncamiento (imposible en general)."""
    usados: set[str] = set()
    mapeo: dict[str, str] = {}
    for pred in predictores:
        base = f"bivariado_{pred}"[:_MAX_HOJA]
        if base not in usados:
            usados.add(base)
            mapeo[pred] = base
            continue
        for i in range(2, 100):
            sufijo = f"_{i}"
            candidato_hoja = f"bivariado_{pred}"[:_MAX_HOJA - len(sufijo)] + sufijo
            if candidato_hoja not in usados:
                usados.add(candidato_hoja)
                mapeo[pred] = candidato_hoja
                break
        else:
            raise RuntimeError(f"no se pudo generar un nombre de hoja unico para '{pred}'")
    return mapeo


def generar_do(candidato: Candidato, plantilla: Plantilla) -> str:
    """Sintaxis Stata determinista (sin LLM, sin red, sin tocar datos reales) para que
    el estadistico la corra sobre su propio datos.dta exportado. Sin svy: — EPE es un
    registro clinico de un solo hospital, no una encuesta con diseno muestral complejo."""
    estructura = build_estructura(candidato, plantilla)
    modelo = estructura["diseno"]["modelo"]
    comando = _COMANDO_POR_MODELO[modelo]
    outcome = candidato.outcome
    exposicion = candidato.eje
    covariables = list(candidato.covariables_ajuste)
    predictores = " ".join([exposicion, *covariables])
    ajuste_txt = ", ".join(covariables) if covariables else "(ninguna)"

    lines = [
        f"* Analisis EPE — candidato={candidato_id(candidato)}",
        f"* generado: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"* eje (exposicion principal): {exposicion}",
        f"* subpoblacion: {candidato.subpoblacion}",
        f"* outcome: {outcome} (modelo: {modelo})",
        f"* covariables de ajuste: {ajuste_txt}",
        f"* filtrar a subpoblacion: {candidato.subpoblacion} (definir criterio real "
        "con el estadistico)",
    ]

    # Preparar mapeo de hojas bivariadas (truncadas a 31 caracteres si necesario)
    predictores_bivariado = [exposicion, *covariables]
    hojas_bivariado = mapeo_hojas_bivariado(predictores_bivariado)
    truncadas = {p: h for p, h in hojas_bivariado.items() if h != f"bivariado_{p}"}
    if truncadas:
        lines.append("* Nombres de hoja truncados a 31 caracteres (limite OOXML):")
        for p, h in truncadas.items():
            lines.append(f"*   {h} -> {p}")

    lines += [
        "",
        'use "datos.dta", clear',
        "",
        "* Descriptivos",
        f"mean {outcome} {predictores}",
        "putexcel set resultados.xlsx, sheet(descriptivos) replace",
        "putexcel A1 = matrix(r(table)), names",
        "",
        "* Bivariado (outcome por categoria de cada predictor)",
    ]
    for pred in predictores_bivariado:
        lines.append(f"mean {outcome}, over({pred})")
        lines.append(f"putexcel set resultados.xlsx, sheet({hojas_bivariado[pred]}) modify")
        lines.append("putexcel A1 = matrix(r(table)), names")
    lines += [
        "",
        "* Modelo",
        f"{comando} {outcome} {predictores}",
        "putexcel set resultados.xlsx, sheet(modelo) modify",
        "putexcel A1 = matrix(r(table)), names",
    ]
    return "\n".join(lines) + "\n"
