from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidato:
    eje: str
    subpoblacion: str
    outcome: str
    n_disponible: int


def candidato_id(c: Candidato) -> str:
    return f"{c.eje}_{c.subpoblacion}_{c.outcome}"


def _query(c: Candidato) -> str:
    return f"{c.subpoblacion} {c.eje} {c.outcome} dental"


_CAP_SATURACION = 100  # nº de artículos a partir del cual la novedad se considera ~0


def score_novedad(candidato: Candidato, pubmed_client) -> tuple[float, list[str]]:
    try:
        conteo = pubmed_client.contar(_query(candidato))
    except ConnectionError:
        return 0.5, ["PubMed no disponible: novedad neutra (0.5) asignada por defecto."]
    score = max(0.0, 1.0 - math.log10(1 + conteo) / math.log10(1 + _CAP_SATURACION))
    return round(score, 4), []
