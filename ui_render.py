from __future__ import annotations

import json

from agents.novelty_checker import candidato_id


def render_candidatos_md(filas: list[dict], warnings: list[str]) -> str:
    lines = ["# Candidatos de semilla EPE", ""]
    if warnings:
        lines += ["> ⚠️ " + w for w in warnings] + [""]
    if not filas:
        lines.append("_No se generaron candidatos._")
        return "\n".join(lines)
    for i, row in enumerate(filas, 1):
        c = row["candidato"]
        score = row["score_llm"]
        score_txt = f"{score:.1f}" if score is not None else "s/valorar (LLM degradado)"
        ajuste_txt = ", ".join(c.covariables_ajuste) if c.covariables_ajuste else "(ninguna)"
        lines += [
            f"## {i}. {c.eje} × {c.subpoblacion} → {c.outcome}",
            "",
            f"**Pregunta tentativa (observacional, multivariado ajustado):** ¿Cuál es la "
            f"asociación de {c.eje} con {c.outcome} en {c.subpoblacion} de la cohorte EPE, "
            f"ajustando por {ajuste_txt}?",
            "",
            f"- Covariables de ajuste: {ajuste_txt}",
            f"- n disponible (conjunto): {c.n_disponible}",
            f"- **Score LLM:** {score_txt}",
            f"- **Score de novedad (0=saturado,1=vacío en literatura):** {row['novedad']:.2f}",
        ]
        just = row["justificacion"].strip()
        if just:
            lines += ["", f"**Justificación:** {just}"]
        lines.append("")
    return "\n".join(lines)


def render_candidatos_json(filas: list[dict]) -> str:
    items = []
    for row in filas:
        c = row["candidato"]
        items.append({
            "id": candidato_id(c),
            "eje": c.eje,
            "subpoblacion": c.subpoblacion,
            "outcome": c.outcome,
            "covariables_ajuste": list(c.covariables_ajuste),
            "n_disponible": c.n_disponible,
            "novedad": row["novedad"],
            "score_llm": row["score_llm"],
        })
    return json.dumps(items, ensure_ascii=False, indent=2)
