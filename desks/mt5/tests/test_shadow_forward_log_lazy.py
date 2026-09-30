"""shadow_forward must not hold a log handle open from import time (ResourceWarning in CI)."""
from __future__ import annotations

import gc
import importlib
import io
import sys
import warnings
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))


def test_import_opens_no_file_handle() -> None:
    import shadow_forward

    for name, value in vars(shadow_forward).items():
        assert not isinstance(value, io.IOBase), f"module-level open handle: {name}"
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        importlib.reload(shadow_forward)
        gc.collect()


def test_slog_appends_and_closes(tmp_path: Path, monkeypatch) -> None:
    import shadow_forward

    target = tmp_path / "logs" / "shadow.log"
    monkeypatch.setattr(shadow_forward, "LOG_PATH", target)
    shadow_forward.slog("one", 2)
    shadow_forward.slog("three")
    assert target.read_text("utf-8") == "one 2\nthree\n"


def test_slog_survives_an_unwritable_log(tmp_path: Path, monkeypatch, capsys) -> None:
    import shadow_forward

    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(shadow_forward, "LOG_PATH", blocker / "shadow.log")
    shadow_forward.slog("still printed")
    captured = capsys.readouterr()
    assert "still printed" in captured.out
    assert "shadow.log write failed" in captured.err
