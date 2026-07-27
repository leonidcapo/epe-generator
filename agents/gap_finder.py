from __future__ import annotations

import json

from agents.novelty_checker import Candidato, score_novedad
from core.knowledge import Perfil, Plantilla, ejes_implementados_por_subpoblacion
from core.result import AgentResult

_SYSTEM_RANKING = (
    "Eres un epidemiólogo/odontólogo que evalúa huecos de investigación observacional "
    "sobre una cohorte clínica de pacientes especiales (sin inferencia causal). Cada "
    "propuesta es un modelo MULTIVARIADO: una exposición principal ajustada por "
    'covariables. Responde SOLO JSON {"score": <0-10>, "justificacion": "<3-4 líneas, '
    'sin lenguaje causal>"}.'
)


def generar_espacio(p: Plantilla, perfil: Perfil) -> list[Candidato]:
    espacio: list[Candidato] = []
    universos = ejes_implementados_por_subpoblacion(p)
    for subpoblacion, ejes_validos in universos.items():
        if len(ejes_validos) < 2:
            continue
        n_conjunto = perfil.n_conjunto.get(subpoblacion, 0)
        for eje_principal in sorted(ejes_validos):
            covariables = tuple(sorted(ejes_validos - {eje_principal}))
            for outcome in p.outcomes:
                espacio.append(Candidato(
                    eje=eje_principal, subpoblacion=subpoblacion, outcome=outcome,
                    covariables_ajuste=covariables, n_disponible=n_conjunto,
                ))
    return espacio


def filtrar_factibilidad(candidatos: list[Candidato], p: Plantilla) -> list[Candidato]:
    return [c for c in candidatos if c.n_disponible >= p.n_min]


def _prompt_candidato(c: Candidato) -> str:
    ajuste = ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)"
    return (
        f"Exposición principal: {c.eje}\nSubpoblación: {c.subpoblacion}\n"
        f"Outcome propuesto: {c.outcome}\nCovariables de ajuste: {ajuste}\n"
        f"n disponible (conjunto, todas las variables presentes simultáneamente): "
        f"{c.n_disponible}\n"
        "Evalúa plausibilidad clínica, relevancia y publicabilidad de un estudio "
        "observacional multivariado (asociación ajustada) sobre esta combinación."
    )


def _top_diverso(filas: list[dict], top_n: int, cap_por_eje: int) -> list[dict]:
    seleccion: list[dict] = []
    conteo: dict[str, int] = {}
    for f in filas:
        if len(seleccion) >= top_n:
            break
        eje = f["candidato"].eje
        if conteo.get(eje, 0) < cap_por_eje:
            seleccion.append(f)
            conteo[eje] = conteo.get(eje, 0) + 1
    if len(seleccion) < top_n:
        ya = {id(f) for f in seleccion}
        for f in filas:
            if len(seleccion) >= top_n:
                break
            if id(f) not in ya:
                seleccion.append(f)
    return seleccion


def rankear(candidatos: list[Candidato], pubmed_client, llm_client,
           terminos_busqueda: dict[str, dict[str, str]] | None = None,
           top_n: int = 5, cap_por_eje: int = 2) -> AgentResult:
    warnings: list[str] = []
    filas = []
    llm_degradado = False
    for c in candidatos:
        novedad, novedad_warnings = score_novedad(c, pubmed_client, terminos_busqueda)
        warnings.extend(novedad_warnings)
        if llm_degradado:
            filas.append({"candidato": c, "score_llm": None, "justificacion": "", "novedad": novedad})
            continue
        try:
            raw = llm_client.call(_SYSTEM_RANKING, _prompt_candidato(c))
            parsed = json.loads(raw)
            filas.append({
                "candidato": c, "score_llm": float(parsed["score"]),
                "justificacion": parsed["justificacion"], "novedad": novedad,
            })
        except Exception as exc:  # LLM/parse failure -> degrade for the rest, never crash
            llm_degradado = True
            warnings.append(f"Ranking LLM degradado ({type(exc).__name__}): "
                            f"resto ordenado por novedad.")
            filas.append({"candidato": c, "score_llm": None, "justificacion": "", "novedad": novedad})

    if llm_degradado:
        filas.sort(key=lambda f: f["novedad"], reverse=True)
    else:
        filas.sort(key=lambda f: f["score_llm"], reverse=True)

    return AgentResult.degraded(_top_diverso(filas, top_n, cap_por_eje), warnings) if warnings \
        else AgentResult.success(_top_diverso(filas, top_n, cap_por_eje))
