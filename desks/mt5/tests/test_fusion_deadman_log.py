"""A LOG LINE NEVER FAILS A DEADMAN PASS, AND EACH PASS HAS ITS OWN LOG (box 2026-10-29).

MEASURED: MT5-FusionDeadman (the dry-run pass) exited 1 intermittently with
`main -> log("dry-run pass stands aside ...") -> BREACH_LOG.open("a")` raising PermissionError
[Errno 13] on logs\\fusion_deadman.log -- the dry-run and live passes fire in the same second and
appended to one file, which on Windows is a sharing violation. These pin:

  1. `log()` never raises: a refused open is retried, then the line goes to stderr;
  2. the dry-run and live passes append to different files, and neither to the old shared one;
  3. a pass whose log is unwritable still writes its stamp and returns its own verdict, and
     the stand-aside pass returns 0;
  4. the module has exactly one append, inside `log()` (the class guard for this file).
Nothing here changes or reads a rail threshold.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_fusion_deadman_dry_run as base


@pytest.fixture
def fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = base._load()
    data = tmp_path / "data"
    data.mkdir()
    for attr, name in (("STATE", "gateway_state.json"), ("LEDGER", "live_ledger.jsonl"),
                       ("INTENTS", "order_intents.jsonl"), ("PAUSED", "GATEWAY_PAUSED"),
                       ("STAMP", "fusion_deadman_state.json"),
                       ("ARMED_MARKER", "FUSION_DEADMAN_ARMED.json"),
                       ("FUSION_ACCOUNT", "FUSION_LIVE_ACCOUNT.json")):
        monkeypatch.setattr(mod, attr, data / name)
    monkeypatch.setattr(mod, "BREACH_LOG", tmp_path / "logs" / "fusion_deadman.log")
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    monkeypatch.setitem(sys.modules, "MetaTrader5", base._NoTerminal())
    return mod


def _unwritable(fd) -> None:
    """Make every pass log refuse to open: each target path is a DIRECTORY."""
    for name in ("dry", "live"):
        fd._PASS[0] = name
        fd.pass_log().mkdir(parents=True, exist_ok=True)


def test_log_never_raises_and_falls_back_to_stderr(fd, capsys) -> None:
    _unwritable(fd)
    fd._PASS[0] = "dry"
    fd.log("the line that cannot be written")          # must not raise
    err = capsys.readouterr().err
    assert "log write to fusion_deadman_dry.log failed" in err
    assert "the line that cannot be written" in err


def test_a_refused_open_is_retried_before_giving_up(fd, monkeypatch) -> None:
    real_open = Path.open
    calls = {"n": 0}

    def flaky(self, *a, **kw):
        if self.name.startswith("fusion_deadman_") and calls["n"] == 0:
            calls["n"] += 1
            raise PermissionError(13, "sharing violation")
        return real_open(self, *a, **kw)

    monkeypatch.setattr(Path, "open", flaky)
    fd._PASS[0] = "live"
    fd.log("written on the second try")
    assert calls["n"] == 1
    assert "written on the second try" in fd.pass_log().read_text("utf-8")


def test_the_dry_and_live_passes_write_separate_logs(fd) -> None:
    fd.main(dry_run=True)
    fd.log("from the dry pass")
    fd.main(dry_run=False)            # unarmed: demoted to DRY-RUN, but it is the LIVE pass
    logs = fd.BREACH_LOG.parent
    dry, live = logs / "fusion_deadman_dry.log", logs / "fusion_deadman_live.log"
    assert "from the dry pass" in dry.read_text("utf-8")
    assert "--live requested but NOT armed" in live.read_text("utf-8")
    assert "--live requested" not in dry.read_text("utf-8")
    assert not fd.BREACH_LOG.exists(), "no pass appends to the old shared file"


def test_the_stand_aside_pass_returns_zero_when_its_log_is_unwritable(fd) -> None:
    fd.ARMED_MARKER.write_text(json.dumps({"armed_by": "zuck"}), "utf-8")
    _unwritable(fd)
    assert fd.main(dry_run=True) == 0


def test_an_unwritable_log_costs_no_stamp_and_no_verdict(fd) -> None:
    _unwritable(fd)
    base._write_state(fd, equity=fd.EQUITY_FLOOR_EUR - 1.0)
    assert fd.main(dry_run=True) == 1               # the breach verdict, not a crash
    stamp = json.loads(fd.STAMP.read_text("utf-8"))
    assert stamp["breaches"] == ["EQUITY_FLOOR"] and stamp["mode"] == "DRY-RUN"


def test_the_only_append_in_the_rail_is_inside_log() -> None:
    src = base.MODULE.read_text("utf-8")
    appends = [m.start() for m in re.finditer(r'\.open\(\s*"a"|open\([^)]*,\s*"a"', src)]
    assert len(appends) == 1
    body = src[src.index("def log(msg: str)"):src.index("def _read(")]
    assert '.open("a"' in body and "except (OSError, ValueError)" in body
