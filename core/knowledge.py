from __future__ import annotations

from dataclasses import dataclass

import yaml


class VocabularioError(ValueError):
    """Raised when plantilla_epe.yaml references an id that isn't declared."""


@dataclass
class Plantilla:
    ejes: dict[str, str]                      # id -> estado
    subpoblaciones: dict[str, str]            # id -> estado
    outcomes: dict[str, str]                  # id -> tipo
    compatibilidad: dict[str, frozenset[str]]  # eje -> subpoblaciones validas
    causal_permitido: bool
    n_min: int


def load_plantilla(path: str) -> Plantilla:
    with open(path, encoding="utf-8") as fh:
        d = yaml.safe_load(fh)

    ejes = {e["id"]: e["estado"] for e in d["ejes"]}
    subpoblaciones = {p["id"]: p["estado"] for p in d["subpoblaciones"]}
    outcomes = {o["id"]: o["tipo"] for o in d["outcomes"]}

    compat = {}
    for c in d.get("compatibilidad_eje_subpoblacion", []):
        if c["eje"] not in ejes:
            raise VocabularioError(f"compatibilidad_eje_subpoblacion referencia eje desconocido: {c['eje']}")
        desconocidas = sorted(set(c["subpoblaciones_validas"]) - set(subpoblaciones))
        if desconocidas:
            raise VocabularioError(
                f"compatibilidad_eje_subpoblacion[{c['eje']}] referencia subpoblaciones "
                f"desconocidas: {desconocidas}"
            )
        compat[c["eje"]] = frozenset(c["subpoblaciones_validas"])

    return Plantilla(
        ejes=ejes,
        subpoblaciones=subpoblaciones,
        outcomes=outcomes,
        compatibilidad=compat,
        causal_permitido=bool(d["diseno"]["inferencia_causal_permitida"]),
        n_min=int(d["diseno"]["n_min"]),
    )
