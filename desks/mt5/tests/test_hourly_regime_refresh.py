import importlib.util
from pathlib import Path
from unittest.mock import Mock


def load():
    path = Path(__file__).resolve().parents[1] / "research/hourly_cycle.py"
    spec = importlib.util.spec_from_file_location("hourly_regime_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mirror_cannot_recompute_native_regime(monkeypatch):
    module = load()
    monkeypatch.setattr(module.sys, "platform", "linux")
    runner = Mock()
    monkeypatch.setattr(module, "_producer", runner)
    assert module.refresh_regime()["status"] == "SKIPPED"
    runner.assert_not_called()


def test_native_refresh_uses_bounded_existing_producer(monkeypatch):
    module = load()
    monkeypatch.setattr(module.sys, "platform", "win32")
    runner = Mock(return_value={"exit_code": 1})
    monkeypatch.setattr(module, "_producer", runner)
    assert module.refresh_regime() == {"exit_code": 1}
    runner.assert_called_once_with("regime_monitor", "research/regime_monitor.py")
