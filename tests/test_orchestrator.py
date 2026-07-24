import json
import shutil
from pathlib import Path

import pytest

from core.knowledge import load_perfil, guardar_perfil, Perfil
from core.sheets_client import FakeSheetReader
from core.llm_client import FakeLLMClient
from core.pubmed_client import FakePubMedClient
from tests.fixtures.sheet_rows_sinteticas import FILAS_SINTETICAS


def test_run_perfilar_ok_escribe_perfil(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
    reader = FakeSheetReader(FILAS_SINTETICAS)
    r = orchestrator.run_perfilar(reader, out_path="knowledge/perfil_epe.yaml")
    assert r.ok
    assert (tmp_path / "knowledge" / "perfil_epe.yaml").exists()


def test_run_perfilar_fallo_usa_cache_si_existe(tmp_path, monkeypatch):
    import orchestrator
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
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
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knowledge").mkdir()
    reader = FakeSheetReader([], fail=True)
    r = orchestrator.run_perfilar(reader, out_path=str(tmp_path / "knowledge" / "perfil_epe.yaml"))
    assert not r.ok


def test_run_propose_produce_candidatos(tmp_path, monkeypatch):
    import orchestrator
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "knowledge").mkdir()
    shutil.copy(repo_root / "knowledge" / "plantilla_epe.yaml",
                tmp_path / "knowledge" / "plantilla_epe.yaml")
    monkeypatch.chdir(tmp_path)
    perfil_path = tmp_path / "perfil.yaml"
    guardar_perfil(Perfil(n_por_celda={("adultos_mayores", "riesgo_sistemico_asa"): 45},
                          distribuciones={}, generado_en="2026-07-24"), str(perfil_path))
    llm = FakeLLMClient(responses=[json.dumps({"score": 8.0, "justificacion": "ok"})])
    pubmed = FakePubMedClient({})
    r = orchestrator.run_propose("knowledge/plantilla_epe.yaml", str(perfil_path), pubmed, llm)
    assert r.ok
    assert len(r.data) >= 1


def test_orchestrator_main_uso_sin_argumentos(capsys):
    import orchestrator
    assert orchestrator.main([]) == 2
    err = capsys.readouterr().err
    assert "perfilar" in err
    assert "propose" in err
