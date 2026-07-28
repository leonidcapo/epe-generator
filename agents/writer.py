from __future__ import annotations

from dataclasses import dataclass, field

from agents.bias_auditor import auditar
from agents.novelty_checker import Candidato
from agents.number_guard import (
    ESTRUCTURALES_DEFAULT,
    estructurales_estudio,
    numeros_legitimos,
    p_legitimos,
    verificar_numeros,
)
from agents.protocol_designer import disenar_protocolo
from agents.statistician import mapeo_hojas_bivariado
from core.knowledge import Plantilla
from core.result import AgentResult

_PREFIJO_BIVARIADO = "bivariado_"


def _num(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def redactar_resultados(tablas: dict, candidato: Candidato) -> str:
    lineas = ["## Resultados", ""]
    for t in tablas.get("modelo", []):
        if t["termino"] == "_cons":
            continue
        p_txt = f"; p = {_num(t['p'], 3)}" if t.get("p") is not None else ""
        lineas.append(
            f"- {t['termino']}: efecto = {_num(t['efecto'])} "
            f"(IC95%: {_num(t['ic_inf'])}–{_num(t['ic_sup'])}{p_txt})."
        )
    bivariado = tablas.get("bivariado") or {}
    if bivariado:
        predictores = [candidato.eje, *candidato.covariables_ajuste]
        hoja_a_pred = {
            hoja[len(_PREFIJO_BIVARIADO):]: pred
            for pred, hoja in mapeo_hojas_bivariado(predictores).items()
        }
        lineas += ["", "### Análisis bivariado", ""]
        for hoja_key, terminos in bivariado.items():
            pred_real = hoja_a_pred.get(hoja_key, hoja_key)  # degrada al key crudo si no coincide
            for t in terminos:
                lineas.append(
                    f"- {pred_real} = {t['termino']}: valor = {_num(t['efecto'])} "
                    f"(IC95%: {_num(t['ic_inf'])}–{_num(t['ic_sup'])})."
                )
    return "\n".join(lineas)


_SECCIONES_POST = ["discusion", "conclusiones", "recomendaciones", "resumen"]
_PENDIENTE_LLM = "[pendiente: LLM no disponible]"
_PENDIENTE_CIFRA = "[sección pendiente: cifra no verificable]"

_SYSTEM_WRITER = (
    "Eres un investigador que redacta el INFORME FINAL (ex post) de un estudio "
    "observacional transversal con datos de un registro clínico (EPE, Servicio de "
    "Pacientes Especiales, Depto. de Odontoestomatología). Escribe en español académico, "
    "impersonal y en TIEMPO PASADO. PROHIBIDO el lenguaje causal (asociación, no causa) y "
    "PROHIBIDO citar cifras que no estén en los resultados provistos."
)


@dataclass
class Articulo:
    candidato_id: str
    resultados: str
    prosa_ante: dict = field(default_factory=dict)
    prosa_post: dict = field(default_factory=dict)
    limitaciones: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _prompt_seccion(seccion: str, candidato: Candidato, resultados: str) -> str:
    return (
        f"Sección: {seccion}\nEje (exposición principal): {candidato.eje}\n"
        f"Subpoblación: {candidato.subpoblacion}\nOutcome: {candidato.outcome}\n"
        f"Resultados (única fuente de cifras):\n{resultados}\n\n"
        f"Redacta '{seccion}' en pasado, sin lenguaje causal, sin cifras nuevas."
    )


def redactar_articulo(candidato: Candidato, plantilla: Plantilla, tablas: dict,
                      limitaciones, llm_client) -> AgentResult:
    protocolo_result = disenar_protocolo(candidato, plantilla, limitaciones, llm_client)
    protocolo = protocolo_result.data
    resultados = redactar_resultados(tablas, candidato)

    legitimos = numeros_legitimos(tablas)
    p_leg = p_legitimos(tablas)
    estructurales = ESTRUCTURALES_DEFAULT | estructurales_estudio(
        candidato, protocolo.variables, tablas)

    prosa_post: dict = {}
    warnings: list = list(protocolo_result.warnings)
    for sec in _SECCIONES_POST:
        if llm_client is None:
            prosa_post[sec] = _PENDIENTE_LLM
            continue
        try:
            texto = llm_client.call(
                _SYSTEM_WRITER, _prompt_seccion(sec, candidato, resultados)).strip()
        except Exception as exc:  # LLM caído -> degradar esta y las demas
            for s in _SECCIONES_POST:
                prosa_post.setdefault(s, _PENDIENTE_LLM)
            warnings.append(f"Prosa LLM no disponible ({type(exc).__name__}).")
            break
        ilegit = verificar_numeros(texto, legitimos, estructurales, p_leg=p_leg)
        if ilegit:
            prosa_post[sec] = _PENDIENTE_CIFRA
            warnings.append(f"Sección '{sec}': cifras no verificables {ilegit}.")
        else:
            prosa_post[sec] = texto
    if llm_client is None:
        warnings.append("LLM no disponible: secciones de prosa pendientes.")

    ctx = {
        "subpoblacion": candidato.subpoblacion,
        "eje": candidato.eje,
        "outcome": candidato.outcome,
        "outcome_tipo": protocolo.diseno["outcome_tipo"],
        "modelo": protocolo.diseno["modelo"],
        "covariables": list(candidato.covariables_ajuste),
    }
    texto_completo = "\n".join(
        v for v in list(protocolo.prosa.values()) + list(prosa_post.values())
        if not v.startswith("[")
    )
    limit_textos, audit_warnings = auditar(ctx, texto_completo, limitaciones, llm_client)
    warnings += audit_warnings

    art = Articulo(candidato_id=protocolo.candidato_id, resultados=resultados,
                   prosa_ante=protocolo.prosa, prosa_post=prosa_post,
                   limitaciones=limit_textos, warnings=warnings)
    if any(v.startswith("[") for v in prosa_post.values()):
        return AgentResult.degraded(art, warnings=warnings)
    return AgentResult.success(art, warnings=warnings)
