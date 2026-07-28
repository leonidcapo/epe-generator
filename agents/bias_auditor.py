from __future__ import annotations

import re
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Limitacion:
    id: str
    categoria: str
    descripcion: str
    aplica_siempre: bool
    aplica_si: str | None
    accion_agente: str | None


def load_limitaciones(path: str) -> list[Limitacion]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    lims = []
    for d in raw:
        lims.append(Limitacion(
            id=d["id"],
            categoria=d.get("categoria", ""),
            descripcion=d.get("descripcion", "").strip(),
            aplica_siempre=bool(d.get("aplica_siempre", False)),
            aplica_si=d.get("aplica_si"),
            accion_agente=d.get("accion_agente"),
        ))
    return lims


def condicion_aplica(aplica_si: str, ctx: dict) -> bool:
    if aplica_si == "modelo_tiene_covariables_de_ajuste":
        return len(ctx.get("covariables", [])) >= 1
    return False


def limitaciones_aplicables(ctx: dict, limitaciones: list[Limitacion]) -> list[Limitacion]:
    aplicables = []
    for lim in limitaciones:
        if lim.aplica_siempre:
            aplicables.append(lim)
        elif lim.aplica_si is not None and condicion_aplica(lim.aplica_si, ctx):
            aplicables.append(lim)
    return aplicables


_MARCADORES_CAUSALES = [
    "causa", "provoca", "efecto de", "produce", "genera un aumento",
    "debido a", "conlleva a", "da lugar a",
]
_NEGACIONES_CAUSALES = [
    "no fue posible establecer", "no es posible establecer",
    "no se puede establecer", "no permite establecer",
    "sin poder establecer", "no establece",
    "investigar las causas", "explorar las causas", "estudiar las causas",
    "determinar las causas", "identificar las causas", "esclarecer las causas",
]
_SEPARADOR_ORACIONES = re.compile(r"(?<=[.!?])\s+")


_SYSTEM_VERIFICADOR_CAUSAL = (
    "Eres un auditor metodológico. Se te da UNA oración de un protocolo de "
    "investigación transversal (no experimental). Responde ÚNICAMENTE 'SI' si "
    "la oración afirma o implica una relación de causa-efecto entre variables "
    "del estudio, o ÚNICAMENTE 'NO' si es un disclaimer de no-causalidad, una "
    "recomendación de investigación futura, una explicación metodológica sin "
    "afirmar causalidad del hallazgo, u otro uso no-causal. Una sola palabra."
)
_RESPUESTA_NO = re.compile(r"^NO[.!]?$")


def _verificar_causal_llm(oracion: str, llm_client) -> bool:
    try:
        r = llm_client.call(_SYSTEM_VERIFICADOR_CAUSAL, oracion).strip().upper()
    except Exception:
        return True
    if _RESPUESTA_NO.match(r):
        return False
    return True


def _candidatos_causales(texto: str) -> list[tuple[str, str]]:
    candidatos: list[tuple[str, str]] = []
    for oracion in _SEPARADOR_ORACIONES.split(texto):
        low = oracion.lower()
        if any(neg in low for neg in _NEGACIONES_CAUSALES):
            continue
        for m in _MARCADORES_CAUSALES:
            if m in low:
                candidatos.append((oracion, m))
    return candidatos


def escanear_causal(texto: str) -> list[str]:
    encontrados: list[str] = []
    for _, m in _candidatos_causales(texto):
        if m not in encontrados:
            encontrados.append(m)
    return encontrados


def auditar(ctx: dict, prosa_texto: str, limitaciones: list[Limitacion],
            llm_client=None) -> tuple[list[str], list[str]]:
    aplicables = limitaciones_aplicables(ctx, limitaciones)
    textos = [lim.descripcion for lim in aplicables]
    warnings: list[str] = []
    for lim in aplicables:
        a = lim.accion_agente
        if a == "rechazar_lenguaje_causal_en_redaccion":
            candidatos = _candidatos_causales(prosa_texto)
            if llm_client is None:
                marcadores = []
                for _, m in candidatos:
                    if m not in marcadores:
                        marcadores.append(m)
            else:
                veredicto_por_oracion: dict[str, bool] = {}
                for oracion, _ in candidatos:
                    if oracion not in veredicto_por_oracion:
                        veredicto_por_oracion[oracion] = _verificar_causal_llm(oracion, llm_client)
                marcadores = []
                for oracion, m in candidatos:
                    if veredicto_por_oracion[oracion] and m not in marcadores:
                        marcadores.append(m)
            for frase in marcadores:
                warnings.append(f"Lenguaje causal detectado en la prosa: '{frase}'.")
        elif a == "advertir_confusion_residual_si_pocas_covariables":
            if len(ctx.get("covariables", [])) <= 1:
                warnings.append("Pocas covariables de ajuste: posible confusión residual no controlada.")
    return textos, warnings
