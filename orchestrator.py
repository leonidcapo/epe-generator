from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from agents.gap_finder import filtrar_factibilidad, generar_espacio, rankear
from agents.perfilador import perfilar
from core.knowledge import guardar_perfil, load_perfil, load_plantilla
from core.llm_client import make_client
from core.pubmed_client import make_pubmed_client
from core.result import AgentResult
from core.sheets_client import GspreadSheetReader, SheetReader
from ui_render import render_candidatos_json, render_candidatos_md


def run_perfilar(reader: SheetReader, plantilla_path: str = "knowledge/plantilla_epe.yaml",
                 out_path: str = "knowledge/perfil_epe.yaml") -> AgentResult:
    plantilla = load_plantilla(plantilla_path)
    r = perfilar(reader, plantilla)
    if r.ok:
        guardar_perfil(r.data, out_path)
        return r
    # perfilar falló (p.ej. sin conexión): degrada al último perfil cacheado si existe.
    motivo = r.warnings[0] if r.warnings else "motivo desconocido"
    if Path(out_path).exists():
        cacheado = load_perfil(out_path)
        return AgentResult.degraded(
            cacheado,
            [f"No se pudo leer el Sheet en vivo ({motivo}); "
             f"usando perfil cacheado del {cacheado.generado_en}."],
        )
    return AgentResult.failure(
        [f"No se pudo leer el Sheet y no hay perfil cacheado en {out_path}: {motivo}"]
    )


def run_propose(plantilla_path: str, perfil_path: str, pubmed_client, llm_client,
               top_n: int = 5, max_candidatos: int = 40) -> AgentResult:
    p = load_plantilla(plantilla_path)
    perfil = load_perfil(perfil_path)
    espacio = generar_espacio(p, perfil)
    factibles = filtrar_factibilidad(espacio, p)[:max_candidatos]
    resultado = rankear(factibles, pubmed_client, llm_client, p.terminos_busqueda, top_n=top_n)
    if not perfil.n_conjunto and perfil.n_por_celda:
        aviso = (
            "El perfil cargado es anterior a la migración multivariada (no tiene "
            "n_conjunto): todos los candidatos quedarán en n=0. Re-ejecuta 'perfilar' "
            "para regenerarlo."
        )
        return AgentResult(
            ok=resultado.ok,
            data=resultado.data,
            warnings=[aviso, *resultado.warnings],
        )
    return resultado


def _make_llm_client_or_none():
    try:
        return make_client(os.environ)
    except ValueError as exc:
        print(f"  aviso: {exc} — modo degradado (sin LLM)")
        return None


def _cmd_perfilar() -> int:
    credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("EPE_SHEET_ID")
    worksheet = os.environ.get("EPE_WORKSHEET_NAME", "Marco")
    if not credentials or not sheet_id:
        print("Faltan GOOGLE_SERVICE_ACCOUNT_JSON y/o EPE_SHEET_ID en el entorno (.env).",
              file=sys.stderr)
        return 1
    reader = GspreadSheetReader(credentials, sheet_id, worksheet)
    r = run_perfilar(reader)
    for w in r.warnings:
        print(f"  aviso: {w}")
    if not r.ok:
        return 1
    print("Escrito: knowledge/perfil_epe.yaml")
    return 0


def _cmd_propose() -> int:
    perfil_path = Path("knowledge/perfil_epe.yaml")
    if not perfil_path.exists():
        print(
            "No existe knowledge/perfil_epe.yaml; corre 'python orchestrator.py perfilar' primero.",
            file=sys.stderr,
        )
        return 1
    llm = _make_llm_client_or_none()
    if llm is None:
        from core.llm_client import FakeLLMClient
        llm = FakeLLMClient(default='{"score": 0, "justificacion": ""}')
    pubmed = make_pubmed_client(os.environ)
    result = run_propose("knowledge/plantilla_epe.yaml", "knowledge/perfil_epe.yaml", pubmed, llm)
    if not result.ok:
        for w in result.warnings:
            print(f"  aviso: {w}", file=sys.stderr)
        return 1
    md = render_candidatos_md(result.data, result.warnings)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out = Path("outputs") / run_id / "candidatos.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    (out.parent / "candidatos.json").write_text(
        render_candidatos_json(result.data), encoding="utf-8")
    print(f"Escrito: {out}")
    for w in result.warnings:
        print(f"  aviso: {w}")
    return 0


def main(argv: list[str]) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if argv and argv[0] == "perfilar":
        return _cmd_perfilar()
    if argv and argv[0] == "propose":
        return _cmd_propose()
    print("uso: python orchestrator.py perfilar | propose", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
