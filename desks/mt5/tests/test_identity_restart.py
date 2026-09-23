"""A clock broken on the CURRENT schema had no restart path, and that was the readiness blocker.

`migrate_identity_venue.py` selected rows by `identity_schema != CURRENT_SCHEMA` and merely
COUNTED the IDENTITY_BROKEN ones. With 11 sleeves broken on the current schema it printed
"nothing to migrate" and exited 0, while `check_live_readiness` blocked rung 0 on exactly those
11. IDENTITY_BROKEN is terminal by design and nothing else clears it, so the desk's own path to
first live capital was closed by the one tool built to open it.

These pin the restart, and the two things that make a restart legitimate rather than a laundering
step: the evidence is ARCHIVED (never deleted) and the new window inherits NOTHING.

THE PATHS ARE MONKEYPATCHED ON THE MODULE, NOT REDIRECTED WITH `cwd`. The script resolves
`ROOT = Path(__file__).resolve().parent.parent`, so running it as a subprocess from a temporary
directory does NOT redirect it -- the first version of this file did that and archived eleven
LIVE sleeves (restored from the archive it had just written; the tool deletes nothing, which is
the only reason that was recoverable). A test that can reach production state is a test that
eventually will.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "migrate_identity_venue.py"

BROKEN_ROW = {
    "identity": {"family": "session_range_breakout", "symbol": "CADJPY", "cost_hash": "old"},
    "identity_schema": "venue-2026-08-26",
    "frozen_at": "2026-08-26T11:19:15+00:00",
    "forward_start": "2026-08-26T11:18:25+00:00",
    "status": "IDENTITY_BROKEN",
    "status_why": "cost_hash changed after the clock froze",
}
CLOCK = {"n": 7, "cum_r": -0.05, "days_active": 9, "status": "IDENTITY_BROKEN",
         "forward_start": "2026-08-26T11:18:25+00:00"}


def _load_module():
    spec = importlib.util.spec_from_file_location("migrate_identity_venue_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The module with every path pointed at a throwaway tree. Live state is unreachable."""
    module = _load_module()
    reg = tmp_path / "sleeve_registry.json"
    shadow = tmp_path / "shadow_state.json"
    archive = tmp_path / "sleeve_registry_archive.json"
    reg.write_text(json.dumps({"sleeves": {
        "CADJPY.asia": dict(BROKEN_ROW),
        "XAUUSD.asia": {"identity": {"symbol": "XAUUSD"},
                        "identity_schema": "venue-2026-08-26", "status": "ACTIVE"},
    }}))
    shadow.write_text(json.dumps({"CADJPY.asia": dict(CLOCK),
                                  "XAUUSD.asia": {"n": 8, "status": "ACTIVE"}}))
    monkeypatch.setattr(module, "REGISTRY", reg)
    monkeypatch.setattr(module, "SHADOW", shadow)
    monkeypatch.setattr(module, "ARCHIVE", archive)
    module._paths = (reg, shadow, archive)
    return module


def _run(module, *args: str) -> int:
    argv = sys.argv
    try:
        sys.argv = ["migrate_identity_venue.py", *args]
        return module.main()
    finally:
        sys.argv = argv


def _load(module) -> tuple[dict, dict, dict]:
    reg, shadow, archive = module._paths
    arch = json.loads(archive.read_text()) if archive.exists() else {"archived": []}
    return json.loads(reg.read_text()), json.loads(shadow.read_text()), arch


def test_broken_rows_are_never_reported_as_nothing_to_do(desk, capsys) -> None:
    assert _run(desk) == 0
    out = capsys.readouterr().out
    assert "nothing to migrate" not in out
    assert "--restart-broken" in out
    assert "CADJPY.asia" in out, "the report must name which clock is stuck"


def test_a_clean_registry_still_reports_nothing_to_migrate(desk, capsys) -> None:
    reg, _, _ = desk._paths
    reg.write_text(json.dumps({"sleeves": {
        "XAUUSD.asia": {"identity_schema": "venue-2026-08-26", "status": "ACTIVE"}}}))
    assert _run(desk) == 0
    assert "nothing to migrate" in capsys.readouterr().out


def test_restart_clears_both_artifacts(desk) -> None:
    assert _run(desk, "--restart-broken") == 0
    reg, shadow, _ = _load(desk)
    assert "CADJPY.asia" not in reg["sleeves"], "registry row survived the restart"
    assert "CADJPY.asia" not in shadow, (
        "the CLOCK survived: status stays IDENTITY_BROKEN and the engine's verdict branch is "
        "gated on status == ACTIVE, so the sleeve would carry a new identity and never be judged")


def test_a_healthy_sleeve_is_untouched(desk) -> None:
    _run(desk, "--restart-broken")
    reg, shadow, _ = _load(desk)
    assert reg["sleeves"]["XAUUSD.asia"]["status"] == "ACTIVE"
    assert shadow["XAUUSD.asia"]["n"] == 8


def test_evidence_is_archived_never_destroyed(desk) -> None:
    _run(desk, "--restart-broken")
    _, _, arch = _load(desk)
    entry = next(r for r in arch["archived"] if r["key"] == "CADJPY.asia")
    assert entry["row"]["status_why"] == "cost_hash changed after the clock froze"
    assert entry["clock"]["n"] == 7 and entry["clock"]["cum_r"] == -0.05, (
        "the accrued record must survive the restart or the restart is a deletion")


def test_restarts_are_counted_so_a_repeat_drifter_cannot_look_young(desk) -> None:
    _run(desk, "--restart-broken")
    reg_path, _, _ = desk._paths
    reg = json.loads(reg_path.read_text())
    reg["sleeves"]["CADJPY.asia"] = dict(BROKEN_ROW)
    reg_path.write_text(json.dumps(reg))
    _run(desk, "--restart-broken")
    _, _, arch = _load(desk)
    numbers = [r["restart_number"] for r in arch["archived"] if r["key"] == "CADJPY.asia"]
    assert numbers == [1, 2], f"restart count did not advance: {numbers}"


def test_restart_is_not_implied_by_apply(desk) -> None:
    # --apply targets PRE-SCHEMA rows. A broken current-schema clock must need the explicit flag,
    # or an automatic pass would erase drift as fast as it appeared.
    _run(desk, "--apply")
    reg, shadow, _ = _load(desk)
    assert "CADJPY.asia" in reg["sleeves"]
    assert shadow["CADJPY.asia"]["n"] == 7


def test_code_hash_ignores_decorators_but_not_the_body():
    """@register_family is SEARCH metadata (param grids, tags): registering a family must not
    stop its live clocks. The body is the strategy: touching it must."""
    import hashlib
    import inspect
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
    import sleeve_registry as reg

    def _fake_decorator(fn):
        return fn

    @_fake_decorator
    def decorated(x):
        return x + 1

    deco_src = inspect.getsource(decorated)
    assert deco_src.splitlines()[0].lstrip().startswith("@")
    stripped = "".join(deco_src.splitlines(keepends=True)[1:])
    assert reg.code_hash(decorated) == hashlib.sha256(
        stripped.encode("utf-8")).hexdigest()[:16], (
        "the decorator line must never be part of a sleeve's identity")
