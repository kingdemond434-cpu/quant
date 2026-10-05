"""THE MONEY-PATH FLOOR HAD NO MEMORY AND SCORED SILENCE AS FINE (audit 2026-09-05).

    python -m pytest tests/scripts/test_check_mt5_coverage_floor.py -q

Two findings, verified against the tree:

  (a) `desks/mt5/data/coverage_high_water.json` was never committed and a missing file was read
      as `{}`, so every fresh CI runner compared the measurement against ZERO and passed. A
      ratchet whose memory lives on a disposable host is not a ratchet.
  (c) a money-path module missing from the report printed `absent` and CONTINUED -- the opposite
      of "the capital-moving code needs the strongest proof".

MEASURED AT SEALING. The gateway was expected to be absent (MetaTrader5 cannot be imported on
Linux). It is not: coverage.py lists every file under a `--cov` source directory whether or not
it was imported, so `gateway.py` is in the report at 0.60% -- ten prelude lines up to the
`import MetaTrader5` that raises, 0 of 438 branches. The allowlist was written for its absence,
the report covered it, and the ratchet retired the excuse at the seal exactly as the rule says.
The excuse mechanism is still exercised here (with the allowlist monkeypatched) because the
next money-path file that genuinely cannot be measured will need it to work.

WHAT MUST NOT REGRESS:

  1. a missing or corrupt baseline is a FAILURE that names the file and the command that creates it
  2. `--init` seals the baseline from the report -- once; a second `--init` is refused
  3. a fall past the tolerance fails by name and the mark does NOT drop
  4. a rise raises the mark, stamps `measured_at`, and leaves `sealed_at` alone
  5. an absent module fails unless its absence is declared in UNMEASURABLE_HERE with a reason
  6. an allowlisted module that DOES appear is floored, its allowlist entry retired, and reported
  7. the committed baseline is real: present, sealed, and consistent with the allowlist
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import scripts.check_mt5_coverage_floor as F

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = "desks/mt5/mt5desk/gateway.py"
ENGINE = "desks/mt5/mt5desk/engine.py"
REASON = "MetaTrader5 not importable on Linux; portable decision core pending split"
SEALED_AT = "2026-09-05T00:00:00+00:00"


def _report(pcts: dict[str, float | None] | None = None, *, branch: bool = True) -> dict[str, Any]:
    """A coverage.py JSON report shaped like the real one. Every money-path file is present at
    70% -- the gateway at 0.6%, which is what a Linux runner actually measures -- unless
    overridden; `None` removes a file, which is what a deleted test file, a rename, or a run
    dying before import looks like in the real report."""
    want: dict[str, float | None] = dict.fromkeys(F.MONEY_PATH, 70.0)
    want[GATEWAY] = 0.6
    want.update(pcts or {})
    return {
        "meta": {"version": "7.16.0", "timestamp": "2026-09-05T00:00:00", "branch_coverage": branch,
                 "show_contexts": False},
        "files": {rel: {"summary": {"percent_covered": pct, "num_statements": 100}}
                  for rel, pct in want.items() if pct is not None},
        "totals": {"percent_covered": 70.0},
    }


def _sealed(pcts: dict[str, float] | None = None, **extra: Any) -> dict[str, Any]:
    """A baseline as `--init` writes it over a report that covers every file."""
    hw = dict.fromkeys(F.MONEY_PATH, 0.7)
    hw[GATEWAY] = 0.006
    hw.update(pcts or {})
    doc: dict[str, Any] = {
        "sealed_at": SEALED_AT,
        "measured_at": SEALED_AT,
        "report": "mt5cov.json",
        "report_sha256": "0" * 64,
        "high_water": hw,
        "unmeasurable_here": {},
        "allowlist_retired": {},
    }
    doc.update(extra)
    return doc


def _excused(**extra: Any) -> dict[str, Any]:
    """A baseline sealed while the gateway was absent and excused -- the shape the audit
    expected the runner to produce."""
    doc = _sealed(unmeasurable_here={GATEWAY: REASON}, **extra)
    del doc["high_water"][GATEWAY]
    return doc


def _run(tmp_path: Path, capsys: pytest.CaptureFixture[str], report: dict[str, Any],
         baseline: dict[str, Any] | str | None, *, init: bool = False,
         ) -> tuple[int, str, dict[str, Any] | None]:
    """Drive main() against an isolated report and baseline.

    Returns (exit code, stdout, the baseline on disk afterwards or None). `baseline` may be a
    dict (written as JSON), a raw string (written verbatim, for corruption), or None (absent).
    """
    rpath = tmp_path / "mt5cov.json"
    rpath.write_text(json.dumps(report), "utf-8")
    bpath = tmp_path / "data" / "coverage_high_water.json"
    if isinstance(baseline, dict):
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(json.dumps(baseline), "utf-8")
    elif isinstance(baseline, str):
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(baseline, "utf-8")
    argv = ["--report", str(rpath), "--baseline", str(bpath)] + (["--init"] if init else [])
    code = F.main(argv)
    out = capsys.readouterr().out
    return code, out, _on_disk(bpath)


def _on_disk(bpath: Path) -> dict[str, Any] | None:
    """The baseline after the run: None when absent, or still the junk it was seeded with."""
    if not bpath.exists():
        return None
    try:
        doc = json.loads(bpath.read_text("utf-8"))
    except ValueError:
        return {"_unparseable": bpath.read_text("utf-8")}
    return doc if isinstance(doc, dict) else {"_not_a_record": doc}


@pytest.fixture
def gateway_excused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The allowlist as it was written before the seal measured the gateway."""
    monkeypatch.setattr(F, "UNMEASURABLE_HERE", {GATEWAY: REASON})


# ------------------------------------------------- 1. no memory is a failure, not a zero

def test_a_missing_baseline_fails_and_names_the_file_and_the_command(tmp_path: Path,
                                                                    capsys: Any) -> None:
    """THE MEASURED DEFECT. `hw = {}` on a fresh runner meant "previous" was zero for every file
    and the gate was green on any number at all."""
    code, out, after = _run(tmp_path, capsys, _report(), None)
    assert code != 0
    assert "coverage_high_water.json" in out
    assert "--init" in out, "the message must name the one command that creates the baseline"
    assert after is None, "a failing run must not manufacture the baseline it says is missing"


@pytest.mark.parametrize("junk", ["", "not json", "[]", '{"no_high_water": 1}'])
def test_a_corrupt_baseline_fails_rather_than_reading_as_empty(tmp_path: Path, capsys: Any,
                                                              junk: str) -> None:
    code, out, _ = _run(tmp_path, capsys, _report(), junk)
    assert code != 0
    assert "UNREADABLE" in out


# ------------------------------------------------- 2. sealing is a deliberate, one-time act

def test_init_seals_the_measured_values_with_provenance(tmp_path: Path, capsys: Any) -> None:
    code, out, after = _run(tmp_path, capsys, _report({ENGINE: 81.25}), None, init=True)
    assert code == 0, out
    assert after is not None
    assert after["high_water"][ENGINE] == 0.8125
    assert after["high_water"][GATEWAY] == 0.006
    assert set(after["high_water"]) == set(F.MONEY_PATH)
    assert after["unmeasurable_here"] == {}
    for key in ("sealed_at", "measured_at", "report", "report_sha256", "report_meta",
                "suite_command", "money_path_files"):
        assert after.get(key), f"baseline sealed without `{key}`"
    assert after["sealed_at"] == after["measured_at"]
    assert len(after["report_sha256"]) == 64
    assert after["suite_command"] == F.SUITE_COMMAND
    assert "--cov-branch" in after["suite_command"]


def test_init_records_an_excused_absence_with_its_reason(tmp_path: Path, capsys: Any,
                                                        gateway_excused: None) -> None:
    code, out, after = _run(tmp_path, capsys, _report({GATEWAY: None}), None, init=True)
    assert code == 0, out
    assert after is not None
    assert GATEWAY not in after["high_water"]
    assert after["unmeasurable_here"] == {GATEWAY: REASON}
    assert after["allowlist_retired"] == {}


def test_init_retires_an_excuse_the_report_did_not_need(tmp_path: Path, capsys: Any,
                                                        gateway_excused: None) -> None:
    """What actually happened on 2026-09-05: the excuse was written for an absence and the
    report covered the file, so the seal floors it and keeps the reason as history."""
    code, out, after = _run(tmp_path, capsys, _report(), None, init=True)
    assert code == 0, out
    assert after is not None
    assert after["high_water"][GATEWAY] == 0.006
    assert after["unmeasurable_here"] == {}
    assert after["allowlist_retired"][GATEWAY]["was_excused_as"] == REASON
    assert after["allowlist_retired"][GATEWAY]["pct"] == 0.006


def test_init_refuses_to_overwrite_an_existing_baseline(tmp_path: Path, capsys: Any) -> None:
    """Re-sealing would be the one code path that can lower a mark. There must not be one."""
    code, out, after = _run(tmp_path, capsys, _report({ENGINE: 10.0}),
                            _sealed({ENGINE: 0.9}), init=True)
    assert code != 0
    assert "REFUSING" in out
    assert after is not None and after["high_water"][ENGINE] == 0.9


def test_init_refuses_a_report_missing_an_unexcused_module(tmp_path: Path, capsys: Any) -> None:
    """A baseline sealed over a partial population is a permanent error."""
    code, out, after = _run(tmp_path, capsys, _report({ENGINE: None}), None, init=True)
    assert code != 0
    assert ENGINE in out
    assert after is None


def test_a_line_only_report_is_refused_for_a_branch_floor(tmp_path: Path, capsys: Any) -> None:
    """Line coverage is never below branch coverage; sealing or checking a branch floor from a
    line report inflates every number in it."""
    code, out, _ = _run(tmp_path, capsys, _report(branch=False), None, init=True)
    assert code != 0 and "--cov-branch" in out
    code, out, _ = _run(tmp_path, capsys, _report(branch=False), _sealed())
    assert code != 0 and "--cov-branch" in out


# ------------------------------------------------- 3 & 4. the ratchet: falls fail, rises stick

def test_a_fall_past_tolerance_fails_by_name_and_the_mark_holds(tmp_path: Path,
                                                               capsys: Any) -> None:
    code, out, after = _run(tmp_path, capsys, _report({ENGINE: 60.0}), _sealed({ENGINE: 0.9}))
    assert code != 0
    assert "FAIL" in out and ENGINE in out and "REGRESSION" in out
    assert after is not None
    assert after["high_water"][ENGINE] == 0.9, "a regression must never write itself in as the mark"


def test_a_fall_inside_tolerance_is_not_a_regression(tmp_path: Path, capsys: Any) -> None:
    """Coverage moves a little with ordering and optional skips; a floor that fires on noise
    gets deleted, which is worse than a floor two points low."""
    code, out, after = _run(tmp_path, capsys, _report({ENGINE: 89.0}), _sealed({ENGINE: 0.9}))
    assert code == 0, out
    assert after is not None and after["high_water"][ENGINE] == 0.9


def test_a_rise_raises_the_mark_and_keeps_the_seal_date(tmp_path: Path, capsys: Any) -> None:
    code, out, after = _run(tmp_path, capsys, _report({ENGINE: 95.5}), _sealed({ENGINE: 0.9}))
    assert code == 0, out
    assert after is not None
    assert after["high_water"][ENGINE] == 0.955
    assert after["measured_at"] != SEALED_AT, "a raise must be dated"
    assert after["sealed_at"] == SEALED_AT, (
        "the seal date is when the ratchet was armed; a raise does not move it")
    assert after["report_sha256"] != "0" * 64, "the record must name the report that earned it"
    assert "raised" in out


def test_a_flat_run_writes_nothing(tmp_path: Path, capsys: Any) -> None:
    """Running the gate must not look like improving coverage (GAP #85's shape)."""
    code, _out, after = _run(tmp_path, capsys, _report(), _sealed())
    assert code == 0
    assert after is not None and after["measured_at"] == SEALED_AT


def test_evaluate_never_returns_a_lower_mark() -> None:
    """Unit bar on the pure core: whatever the report says, the marks only go up."""
    base = _sealed({ENGINE: 0.9})
    now = F.measure(_report({ENGINE: 5.0}))
    v = F.evaluate(now, base)
    assert v["high_water"][ENGINE] == 0.9
    assert v["failures"]


# ------------------------------------------------- 5. absent is a failure unless declared

def test_an_absent_unexcused_module_fails_by_name(tmp_path: Path, capsys: Any) -> None:
    """Finding (c). `absent` was a line of output; it is the case the floor exists to catch."""
    code, out, _ = _run(tmp_path, capsys, _report({ENGINE: None}), _sealed())
    assert code != 0
    assert f"FAIL: {ENGINE}" in out
    assert "ABSENT" in out


def test_the_gateway_going_absent_now_fails_because_it_has_been_measured(
        tmp_path: Path, capsys: Any) -> None:
    """The report covers the gateway today at 0.6%. A future run in which it vanishes -- the
    --cov path changed, the file moved -- is a hole where the order-placing file was."""
    code, out, _ = _run(tmp_path, capsys, _report({GATEWAY: None}), _sealed())
    assert code != 0
    assert f"FAIL: {GATEWAY}" in out and "measured before" in out


def test_an_excused_absence_passes_with_its_reason(tmp_path: Path, capsys: Any,
                                                   gateway_excused: None) -> None:
    """The honest interim for a file the host cannot import: the reason travels with the
    verdict so absent-and-known and absent-and-broken never render alike."""
    code, out, _ = _run(tmp_path, capsys, _report({GATEWAY: None}), _excused())
    assert code == 0, out
    assert GATEWAY in out and "excused" in out and REASON in out


# ------------------------------------------------- 6. the allowlist is itself ratcheted

def test_an_allowlisted_module_that_appears_is_floored_and_its_entry_retired(
        tmp_path: Path, capsys: Any, gateway_excused: None) -> None:
    code, out, after = _run(tmp_path, capsys, _report({GATEWAY: 42.0}), _excused())
    assert code == 0, out
    assert "ALLOWLIST RATCHETED" in out and GATEWAY in out
    assert after is not None
    assert after["high_water"][GATEWAY] == 0.42
    assert after["allowlist_retired"][GATEWAY]["pct"] == 0.42
    assert after["allowlist_retired"][GATEWAY]["was_excused_as"] == REASON
    assert after["allowlist_retired"][GATEWAY]["measured_at"]


def test_once_retired_the_absence_is_no_longer_excused(tmp_path: Path, capsys: Any,
                                                       gateway_excused: None) -> None:
    """The ratchet's second half: the constant in the script cannot un-measure a file."""
    base = _sealed({GATEWAY: 0.42},
                   allowlist_retired={GATEWAY: {"measured_at": "2026-09-06T00:00:00+00:00",
                                                "pct": 0.42, "was_excused_as": REASON}})
    code, out, _ = _run(tmp_path, capsys, _report({GATEWAY: None}), base)
    assert code != 0
    assert f"FAIL: {GATEWAY}" in out
    assert "not excused" in out and "measured before" in out


def test_a_stale_allowlist_entry_is_reported_every_run(tmp_path: Path, capsys: Any,
                                                       gateway_excused: None) -> None:
    base = _sealed({GATEWAY: 0.42},
                   allowlist_retired={GATEWAY: {"measured_at": "2026-09-06T00:00:00+00:00",
                                                "pct": 0.42, "was_excused_as": REASON}})
    code, out, _ = _run(tmp_path, capsys, _report({GATEWAY: 45.0}), base)
    assert code == 0, out
    assert "STALE ALLOWLIST ENTRY" in out and GATEWAY in out


# ------------------------------------------------- 7. the committed baseline is real

def test_the_committed_baseline_exists_and_is_sealed() -> None:
    """Finding (a), asserted on the real file so deleting it reddens the quality job too."""
    assert F.HIGH_WATER.exists(), (
        f"{F.HIGH_WATER.relative_to(ROOT)} is not committed -- the money-path ratchet has no "
        f"memory. Produce it with:\n  {F.SUITE_COMMAND}\n  {F.INIT_COMMAND}")
    doc = F.read_baseline(F.HIGH_WATER)
    assert doc.get("sealed_at") and doc.get("measured_at") and doc.get("report_sha256")
    assert doc["high_water"], "a sealed baseline with no marks is an absent one"
    for rel, pct in doc["high_water"].items():
        assert 0.0 <= float(pct) <= 1.0, f"{rel}: {pct} is not a fraction"
    for rel in F.MONEY_PATH:
        assert rel in doc["high_water"] or rel in doc.get("unmeasurable_here", {}), (
            f"{rel} is in MONEY_PATH but the baseline neither measures nor excuses it")
    for rel in doc.get("unmeasurable_here", {}):
        assert rel in F.UNMEASURABLE_HERE, f"the baseline excuses {rel} but the script does not"


def test_the_allowlist_carries_no_entry_the_ratchet_has_retired() -> None:
    """The ratchet removes an entry by measuring it; this fence makes leaving the dead constant
    behind a red test rather than a line of output nobody reads."""
    doc = F.read_baseline(F.HIGH_WATER)
    stale = sorted(set(doc.get("allowlist_retired", {})) & set(F.UNMEASURABLE_HERE))
    assert not stale, (
        f"{stale} appeared in the coverage report and were floored; delete their "
        "UNMEASURABLE_HERE entries -- the ratchet has retired them")
    measured_but_listed = sorted(set(doc["high_water"]) & set(F.UNMEASURABLE_HERE))
    assert not measured_but_listed, (
        f"{measured_but_listed} carry a high-water mark and an excuse at once")


def test_the_gateway_interim_is_on_record_one_way_or_the_other() -> None:
    """The order-placing file is either measured and floored, or excused with the mandated
    reason -- never silently neither. Today it is measured (0.6%, the import prelude), and the
    reason the excuse was written for is kept beside that number."""
    assert GATEWAY in F.MONEY_PATH, "excusing or retiring a file is not dropping it from the path"
    doc = F.read_baseline(F.HIGH_WATER)
    if GATEWAY in doc["high_water"]:
        assert doc["allowlist_retired"][GATEWAY]["was_excused_as"] == REASON
    else:
        assert F.UNMEASURABLE_HERE.get(GATEWAY) == REASON
        assert doc["unmeasurable_here"].get(GATEWAY) == REASON


def test_the_money_path_is_the_universe_the_desk_trades() -> None:
    banned = [f for f in F.MONEY_PATH if "binance" in f]
    assert not banned, f"MONEY_PATH names retired crypto adapters {banned} (LAWS §1)"
