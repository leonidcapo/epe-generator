from __future__ import annotations

import re

from agents.novelty_checker import Candidato

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
# Citas Vancouver de texto: [4], [1, 6]. Sus digitos son numeros de referencia,
# no cifras de datos -- se excluyen del escaneo por completo (no hay citas en
# EPE hoy, pero el mecanismo se mantiene por si se agregan mas adelante).
_CITA = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
# Contexto p-valor: "p = 0,539", "p< 0,001", "p ≤ 0,05". Los p-valores exigen
# validacion tipada (igualdad a 3 decimales o umbral), no el redondeo a 2
# decimales de la pasada general.
_P_CTX = re.compile(r"\bp\s*(=|<=|<|≤)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
# Convenciones del discurso estadistico (no son datos): 0.05 = umbral de
# significancia convencional, 100 = total porcentual. NO se exentan 0.01/0.001:
# esas formas viajan como "p < 0,001" y las valida la pasada p-tipada. A
# diferencia de endes-generator, NO se incluyen rangos de anios ni limites
# etarios: no aplican a la cohorte EPE y no deben inventarse sin fuente real.
ESTRUCTURALES_DEFAULT = frozenset({0.05, 100.0})


def _iter_terminos(tablas: dict):
    for v in tablas.values():
        if isinstance(v, dict):            # bivariado: predictor -> list[dict]
            for lst in v.values():
                yield from lst
        else:                              # descriptivos/modelo: list[dict]
            yield from v


def numeros_legitimos(tablas: dict) -> set[float]:
    vals: set[float] = set()
    for t in _iter_terminos(tablas):
        for k in ("efecto", "ic_inf", "ic_sup"):
            v = t.get(k)
            if isinstance(v, (int, float)):
                vals.add(round(float(v), 2))
    return vals


def p_legitimos(tablas: dict) -> set[float]:
    """Valores p crudos de las tablas (sin redondear: la comparacion por umbral
    'p < x' necesita el valor exacto)."""
    vals: set[float] = set()
    for t in _iter_terminos(tablas):
        v = t.get("p")
        if isinstance(v, (int, float)):
            vals.add(float(v))
    return vals


def estructurales_estudio(candidato: Candidato, protocolo_variables: list[dict],
                          tablas: dict) -> set[float]:
    """Conteos estructurales verificables del estudio (nº de covariables de
    ajuste, nº de terminos bivariados por predictor), para que el guard no
    marque un conteo real como cifra inventada. Solo hechos derivables del
    propio estudio; no debilita el guard frente a cifras estadisticas
    inventadas."""
    s: set[float] = set()
    n_cov = sum(1 for v in protocolo_variables if v.get("rol") == "covariable")
    s.add(float(n_cov))
    for terminos in (tablas.get("bivariado") or {}).values():
        s.add(float(len(terminos)))
    s.discard(0.0)  # 0 no es un conteo informativo; evita exentar un "0" espurio
    return s


def verificar_numeros(texto: str, legitimos: set[float],
                      estructurales: set[float] = frozenset(),
                      p_leg: set[float] = frozenset()) -> list[str]:
    texto = _CITA.sub("[cita]", texto)
    ilegit: list[str] = []

    def _validar_p(m: re.Match) -> str:
        op, tok = m.group(1), m.group(2)
        x = float(tok.replace(",", "."))
        if op == "=":
            ok = any(round(v, 3) == round(x, 3) for v in p_leg)
        elif op == "<":
            ok = any(v < x for v in p_leg)
        else:  # "≤" | "<="
            ok = any(v <= x for v in p_leg)
        if not ok:
            ilegit.append(tok)
        return "[p]"  # el span sale del texto: la pasada general no lo re-escanea

    texto = _P_CTX.sub(_validar_p, texto)

    for m in _NUM.finditer(texto):
        tok = m.group()
        x = float(tok.replace(",", "."))
        if round(x, 2) in legitimos:
            continue
        if x in estructurales:
            continue
        ilegit.append(tok)
    return ilegit
