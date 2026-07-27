import json
import shutil
from pathlib import Path

import pytest

from core.knowledge import load_perfil, guardar_perfil, Perfil
from core.sheets_client import FakeSheetReader
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient
from tests.fixtures.sheet_rows_sinteticas import FILAS_SINTETICAS


def _copiar_plantilla(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "knowledge").mkdir(exist_ok=True)
    shutil.copy(repo_root / "knowledge" / "plantilla_epe.yaml",
                tmp_path / "knowledge" / "plantilla_epe.yaml")


def test_run_perfilar_ok_escribe_perfil(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = orchestrator.run_perfilar(reader, out_path="knowledge/perfil_epe.yaml")
    assert r.ok
    assert (tmp_path / "knowledge" / "perfil_epe.yaml").exists()


def test_run_perfilar_fallo_usa_cache_si_existe(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    cache_path = tmp_path / "knowledge" / "perfil_epe.yaml"
    guardar_perfil(Perfil(n_por_celda={("adultos", "riesgo_sistemico_asa"): 99},
                          distribuciones={}, generado_en="2026-07-01"), str(cache_path))
    reader = FakeSheetReader([], fail=True)
    r = orchestrator.run_perfilar(reader, out_path=str(cache_path))
    assert r.ok
    assert "cacheado" in r.warnings[0].lower()
    assert load_perfil(str(cache_path)).n(("adultos", "riesgo_sistemico_asa")) == 99


def test_run_perfilar_fallo_sin_cache_falla(tmp_path, monkeypatch):
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    reader = FakeSheetReader([], fail=True)
    r = orchestrator.run_perfilar(reader, out_path=str(tmp_path / "knowledge" / "perfil_epe.yaml"))
    assert not r.ok


def test_run_perfilar_fallo_cache_con_warnings_vacio_no_crashea(tmp_path, monkeypatch):
    from core.result import AgentResult
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    cache_path = tmp_path / "knowledge" / "perfil_epe.yaml"
    guardar_perfil(Perfil(n_por_celda={("adultos", "riesgo_sistemico_asa"): 99},
                          distribuciones={}, generado_en="2026-07-01"), str(cache_path))
    monkeypatch.setattr(
        orchestrator, "perfilar",
        lambda reader, plantilla: AgentResult.failure([]),
    )
    r = orchestrator.run_perfilar(FakeSheetReader([], fail=True), out_path=str(cache_path))
    assert r.ok
    assert "motivo desconocido" in r.warnings[0]


def test_run_perfilar_fallo_sin_cache_warnings_vacio_no_crashea(tmp_path, monkeypatch):
    from core.result import AgentResult
    import orchestrator
    _copiar_plantilla(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        orchestrator, "perfilar",
        lambda reader, plantilla: AgentResult.failure([]),
    )
    r = orchestrator.run_perfilar(
        FakeSheetReader([], fail=True),
        out_path=str(tmp_path / "knowledge" / "perfil_epe.yaml"),
    )
    assert not r.ok
    assert "motivo desconocido" in r.warnings[0]


def test_run_propose_produce_candidatos(tmp_path, monkeypatch):
    import orchestrator
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "knowledge").mkdir()
    shutil.copy(repo_root / "knowledge" / "plantilla_epe.yaml",
                tmp_path / "knowledge" / "plantilla_epe.yaml")
    monkeypatch.chdir(tmp_path)
    perfil_path = tmp_path / "perfil.yaml"
    guardar_perfil(Perfil(n_por_celda={}, distribuciones={}, generado_en="2026-07-27",
                          n_conjunto={"discapacidad_intelectual": 40}), str(perfil_path))
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = orchestrator.run_propose("knowledge/plantilla_epe.yaml", str(perfil_path), pubmed, llm)
    assert r.ok
    assert len(r.data) >= 1
    assert all(row["candidato"].n_disponible >= 30 for row in r.data)


def test_orchestrator_main_uso_sin_argumentos(capsys):
    import orchestrator
    assert orchestrator.main([]) == 2
    err = capsys.readouterr().err
    assert "perfilar" in err
    assert "propose" in err


def test_cmd_propose_con_fallo_no_escribe_y_retorna_1(tmp_path, monkeypatch, capsys):
    from core.result import AgentResult
    import orchestrator
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "perfil_epe.yaml").write_text("generado_en: '2026-07-24'\n",
                                                             encoding="utf-8")
    monkeypatch.setattr(
        orchestrator, "run_propose",
        lambda *a, **k: AgentResult.failure(["motivo de prueba"]),
    )
    codigo = orchestrator.main(["propose"])
    assert codigo == 1
    salida = capsys.readouterr()
    assert "motivo de prueba" in salida.err
    assert not (tmp_path / "outputs").exists()


def test_cmd_propose_sin_perfil_no_crashea_y_retorna_1(tmp_path, monkeypatch, capsys):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    codigo = orchestrator.main(["propose"])
    assert codigo == 1
    err = capsys.readouterr().err
    assert "perfilar" in err
