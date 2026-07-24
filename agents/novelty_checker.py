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


def _termino(grupo: dict[str, str], id_: str) -> str:
    """Traduce un id interno a su frase de búsqueda; si falta, degrada al id crudo."""
    return grupo.get(id_, id_)


def _query(c: Candidato, terminos_busqueda: dict[str, dict[str, str]] | None = None) -> str:
    terminos_busqueda = terminos_busqueda or {}
    t_sub = _termino(terminos_busqueda.get("subpoblaciones", {}), c.subpoblacion)
    t_eje = _termino(terminos_busqueda.get("ejes", {}), c.eje)
    t_out = _termino(terminos_busqueda.get("outcomes", {}), c.outcome)
    return f"{t_sub} {t_eje} {t_out} dental"


_CAP_SATURACION = 100  # nº de artículos a partir del cual la novedad se considera ~0


def score_novedad(candidato: Candidato, pubmed_client,
                  terminos_busqueda: dict[str, dict[str, str]] | None = None,
                  ) -> tuple[float, list[str]]:
    try:
        conteo = pubmed_client.contar(_query(candidato, terminos_busqueda))
    except ConnectionError:
        return 0.5, ["PubMed no disponible: novedad neutra (0.5) asignada por defecto."]
    score = max(0.0, 1.0 - math.log10(1 + conteo) / math.log10(1 + _CAP_SATURACION))
    return round(score, 4), []
