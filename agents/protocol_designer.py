from __future__ import annotations

from dataclasses import dataclass, field

from agents.bias_auditor import auditar
from agents.novelty_checker import Candidato, candidato_id
from core.knowledge import Plantilla
from core.result import AgentResult


@dataclass
class Protocolo:
    candidato_id: str
    picot: dict
    variables: list[dict]
    diseno: dict
    prosa: dict = field(default_factory=dict)
    limitaciones: list[str] = field(default_factory=list)
    warnings_auditoria: list[str] = field(default_factory=list)


def inferir_modelo(tipo: str, escala: str | None) -> tuple[str, list[str]]:
    """Selección de modelo según el árbol de decisión (tipo de variable respuesta +
    mecanismo generador de datos, no una regla genérica) — ver
    docs/superpowers/specs/2026-07-28-fase-design-protocolo-design.md §5. anclajes
    citables se dejan vacíos hasta que el usuario aporte referencias reales; no se
    inventan citas."""
    if tipo == "continuo":
        return "lineal", []
    if tipo == "binario":
        return "logistica_binaria", []
    if tipo == "categorico":
        if escala == "ordinal":
            return "logistica_ordinal", []
        if escala == "nominal":
            return "logistica_multinomial", []
        raise ValueError(
            f"outcome categorico requiere 'escala' declarada (ordinal|nominal) en la plantilla"
        )
    raise ValueError(f"tipo de outcome desconocido: {tipo}")


def build_picot(c: Candidato) -> dict:
    return {
        "poblacion": c.subpoblacion,
        "exposicion": c.eje,
        "covariables_ajuste": ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)",
        "comparador": "categorías de referencia de las covariables",
        "outcome": c.outcome,
        "tiempo": "transversal (sin seguimiento)",
    }


def build_variables(c: Candidato, p: Plantilla) -> list[dict]:
    tipo = p.outcomes[c.outcome]
    escala = p.outcomes_escala.get(c.outcome)
    variables = [{"nombre": c.outcome, "rol": "outcome", "tipo": tipo, "escala": escala}]
    variables.append({"nombre": c.eje, "rol": "exposicion_principal", "tipo": "categorica"})
    for cov in c.covariables_ajuste:
        variables.append({"nombre": cov, "rol": "covariable", "tipo": "categorica"})
    return variables


def build_estructura(c: Candidato, p: Plantilla) -> dict:
    tipo = p.outcomes[c.outcome]
    escala = p.outcomes_escala.get(c.outcome)
    modelo, anclajes = inferir_modelo(tipo, escala)
    return {
        "picot": build_picot(c),
        "variables": build_variables(c, p),
        "diseno": {
            "tipo": "transversal_analitico",
            "modelo": modelo,
            "anclajes": anclajes,
            "outcome_tipo": tipo,
            "outcome_escala": escala,
        },
    }


_SECCIONES = ["introduccion", "marco_teorico", "objetivos", "hipotesis", "metodos"]

_SYSTEM_PROTOCOLO = (
    "Eres un metodólogo que redacta un PROTOCOLO de investigación (ex ante) para un "
    "estudio observacional analítico con datos de un registro clínico (EPE, Servicio de "
    "Pacientes Especiales, Depto. de Odontoestomatología). Escribe en español académico, "
    "impersonal y en TIEMPO FUTURO (el estudio 'determinará', 'analizará'). PROHIBIDO el "
    "lenguaje causal: es un estudio de asociación, no de causa-efecto. Responde solo el "
    "texto de la sección."
)

_PENDIENTE = "[prosa pendiente: LLM no disponible]"


def _prompt_seccion(seccion: str, c: Candidato, estructura: dict) -> str:
    ajuste = ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)"
    return (
        f"Sección: {seccion}\nExposición principal: {c.eje}\nSubpoblación: {c.subpoblacion}\n"
        f"Outcome: {c.outcome}\nCovariables de ajuste: {ajuste}\n"
        f"Modelo estadístico: {estructura['diseno']['modelo']}\n"
        f"Redacta la sección '{seccion}' del protocolo (3-5 oraciones), en futuro, sin "
        "lenguaje causal."
    )


def _generar_prosa(c: Candidato, estructura: dict, llm_client) -> tuple[dict, list[str]]:
    try:
        prosa = {}
        for sec in _SECCIONES:
            prosa[sec] = llm_client.call(_SYSTEM_PROTOCOLO, _prompt_seccion(sec, c, estructura)).strip()
        return prosa, []
    except Exception as exc:  # incl. llm_client is None -> AttributeError
        prosa = {sec: _PENDIENTE for sec in _SECCIONES}
        return prosa, [f"Prosa no disponible ({type(exc).__name__}): secciones marcadas como pendientes."]


def disenar_protocolo(candidato: Candidato, plantilla: Plantilla, limitaciones, llm_client) -> AgentResult:
    estructura = build_estructura(candidato, plantilla)
    ctx = {
        "subpoblacion": candidato.subpoblacion,
        "eje": candidato.eje,
        "outcome": candidato.outcome,
        "outcome_tipo": estructura["diseno"]["outcome_tipo"],
        "modelo": estructura["diseno"]["modelo"],
        "covariables": list(candidato.covariables_ajuste),
    }
    prosa, prosa_warnings = _generar_prosa(candidato, estructura, llm_client)
    prosa_texto = "\n".join(prosa.values())
    limit_textos, audit_warnings = auditar(ctx, prosa_texto, limitaciones, llm_client)
    protocolo = Protocolo(
        candidato_id=candidato_id(candidato),
        picot=estructura["picot"],
        variables=estructura["variables"],
        diseno=estructura["diseno"],
        prosa=prosa,
        limitaciones=limit_textos,
        warnings_auditoria=audit_warnings,
    )
    warnings = list(prosa_warnings)
    if warnings:
        return AgentResult.degraded(protocolo, warnings=warnings)
    return AgentResult.success(protocolo)
