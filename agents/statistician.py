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
    for pred in [exposicion, *covariables]:
        lines.append(f"mean {outcome}, over({pred})")
        lines.append(f"putexcel set resultados.xlsx, sheet(bivariado_{pred}) modify")
        lines.append("putexcel A1 = matrix(r(table)), names")
    lines += [
        "",
        "* Modelo",
        f"{comando} {outcome} {predictores}",
        "putexcel set resultados.xlsx, sheet(modelo) modify",
        "putexcel A1 = matrix(r(table)), names",
    ]
    return "\n".join(lines) + "\n"
