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
    terminos_busqueda: dict[str, dict[str, str]]  # "ejes"/"subpoblaciones"/"outcomes" -> id -> frase


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

    vocab_por_grupo = {"ejes": ejes, "subpoblaciones": subpoblaciones, "outcomes": outcomes}
    terminos_busqueda: dict[str, dict[str, str]] = {}
    for grupo, mapa in d.get("terminos_busqueda", {}).items():
        vocab = vocab_por_grupo.get(grupo)
        if vocab is None:
            raise VocabularioError(f"terminos_busqueda referencia grupo desconocido: {grupo}")
        desconocidos = sorted(set(mapa) - set(vocab))
        if desconocidos:
            raise VocabularioError(
                f"terminos_busqueda[{grupo}] referencia ids desconocidos: {desconocidos}"
            )
        terminos_busqueda[grupo] = dict(mapa)

    return Plantilla(
        ejes=ejes,
        subpoblaciones=subpoblaciones,
        outcomes=outcomes,
        compatibilidad=compat,
        causal_permitido=bool(d["diseno"]["inferencia_causal_permitida"]),
        n_min=int(d["diseno"]["n_min"]),
        terminos_busqueda=terminos_busqueda,
    )


@dataclass
class Perfil:
    n_por_celda: dict[tuple[str, str], int]   # (subpoblacion, eje) -> n
    distribuciones: dict[str, dict[str, int]]  # variable -> {categoria: conteo}
    generado_en: str

    def n(self, celda: tuple[str, str]) -> int:
        return self.n_por_celda.get(celda, 0)


def guardar_perfil(perfil: Perfil, path: str) -> None:
    serializable = {
        "n_por_celda": [
            {"subpoblacion": sp, "eje": eje, "n": n}
            for (sp, eje), n in perfil.n_por_celda.items()
        ],
        "distribuciones": perfil.distribuciones,
        "generado_en": perfil.generado_en,
    }
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(serializable, fh, allow_unicode=True, sort_keys=False)


def load_perfil(path: str) -> Perfil:
    with open(path, encoding="utf-8") as fh:
        d = yaml.safe_load(fh)
    n_por_celda = {
        (row["subpoblacion"], row["eje"]): row["n"] for row in d["n_por_celda"]
    }
    return Perfil(
        n_por_celda=n_por_celda,
        distribuciones=d["distribuciones"],
        generado_en=d["generado_en"],
    )
