from core.result import AgentResult


def test_success_defaults_no_warnings():
    r = AgentResult.success({"x": 1})
    assert r.ok is True
    assert r.data == {"x": 1}
    assert r.warnings == []


def test_degraded_carries_warnings_but_ok_true():
    r = AgentResult.degraded({"x": 1}, warnings=["llm no disponible"])
    assert r.ok is True
    assert r.warnings == ["llm no disponible"]


def test_failure_ok_false():
    r = AgentResult.failure(["no se pudo leer el sheet"])
    assert r.ok is False
    assert r.data is None
    assert r.warnings == ["no se pudo leer el sheet"]
