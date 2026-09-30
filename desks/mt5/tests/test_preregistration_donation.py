"""The donation path pre-registers, and says so by name when it cannot.

Pre-registration is what separates a TESTED hypothesis from a FITTED one: the card is hashed
before the evidence exists, so a cell's specification can be shown to predate its result. That is
the assumption the deflated-Sharpe charge, the walk-forward split and the lockbox all rest on.

Measured 2026-09-23: 2,908 of 537,933 donated rows (0.54%) carried a `prereg_hash`, and 28 of 28
standing certificates rested on cells with no card at all. Three faults compounded, and this file
pins each one separately so none can come back alone:

  1. the `horizon` derivation read `horizon_days` (zero occurrences in the corpus) and never read
     `horizon` (616) or `hold_days` (110), so `validate` failed and `register` raised;
  2. the registration loop sat inside ONE try block, so the first raising row took every later
     row in the batch with it -- 30.9% of unregistered rows had a complete card;
  3. `except Exception: pass` hid all of it for the path's entire 19-day life.

And it pins the rule that outlives them: a donation that cannot pre-register is DONATED ANYWAY
and stamped, never dropped. Coverage rises by pre-registering more rows, never by mining fewer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import preregistration as pr  # noqa: E402

pc = pytest.importorskip("research.proposer_common")


def _cand(**over: Any) -> dict[str, Any]:
    c: dict[str, Any] = {"title": "t", "mechanism": "m", "family": "session_range_breakout",
                         "symbol": "XAUUSD", "params": {"hold_bars": 8, "side_mode": "follow"},
                         "evidence": {"screen": "s"}}
    c.update(over)
    return c


# ------------------------------------------------------------------ fault 1: the derivation
@pytest.mark.parametrize("key,value", [("hold_bars", 8), ("horizon", 5), ("hold_days", 3),
                                       ("ttl_bars", 12), ("horizon_days", 2)])
def test_horizon_is_read_from_every_key_proposers_actually_use(key: str, value: int) -> None:
    """MEASURED, not guessed. `horizon` and `hold_days` were the keys the corpus used and the
    derivation ignored; dropping either again puts 726 rows per sweep back on the floor."""
    card = pr.from_candidate(_cand(params={key: value, "side_mode": "follow"}))
    assert card["horizon"] == value
    assert pr.validate(card) == []


def test_an_undeclared_horizon_is_recorded_as_undeclared_never_invented() -> None:
    """A card may not fabricate a holding period it was never given -- that forges the exact
    guarantee pre-registration provides. It records the absence and stays registrable."""
    card = pr.from_candidate(_cand(params={"side_mode": "follow"}))
    assert card["horizon"] == pr.UNDECLARED
    assert pr.validate(card) == []


def test_an_empty_parameter_set_still_yields_a_registrable_card() -> None:
    card = pr.from_candidate(_cand(params={}))
    assert pr.validate(card) == []
    assert card["variables"] == [pr.UNDECLARED]


def test_a_candidate_with_no_universe_at_all_is_refused_by_name() -> None:
    """A hypothesis with no instrument is not testable, so it fails -- loudly, with a reason."""
    h, why = pr.register_candidate(_cand(symbol=None), source="t", path=None)
    assert h is None and why is not None and "universe" in why


def test_the_symbols_list_is_read_when_there_is_no_single_symbol(tmp_path: Path) -> None:
    h, why = pr.register_candidate(_cand(symbol=None, symbols=["EURUSD", "GBPUSD"]),
                                   source="t", path=tmp_path / "p.jsonl")
    assert why is None and h


# ------------------------------------------------- fault 2: one bad row must not kill the batch
def test_one_unregistrable_row_never_silences_the_rest_of_the_batch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr, "LEDGER", tmp_path / "p.jsonl")
    rows = [_cand(symbol=None, title=None, mechanism=None),   # cannot register
            _cand(symbol="EURUSD"), _cand(symbol="GBPUSD")]
    out = pc._preregister("unit_test", rows)
    assert out["failed"] == 1
    assert out["preregistered"] == 2, "a row behind a bad one must still be pre-registered"
    assert rows[1]["prereg_hash"] and rows[2]["prereg_hash"]


# --------------------------------------------- fault 3: a failure is named, never swallowed
def test_a_failure_is_stamped_on_the_row_and_counted_by_reason(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr, "LEDGER", tmp_path / "p.jsonl")
    bad = _cand(symbol=None, title=None, mechanism=None)
    out = pc._preregister("unit_test", [bad])
    assert bad["prereg_status"] == pr.PREREG_FAILED
    assert bad.get("prereg_failure")
    assert sum(out["reasons"].values()) == 1
    assert out["failures"] and out["failures"][0]["why"]


def test_a_row_that_cannot_preregister_is_still_donated(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NEVER SOLVE THIS BY DONATING FEWER CELLS. The measurement defect is the failure count,
    not the candidate; dropping the row would answer a blind spot by mining less."""
    monkeypatch.setattr(pr, "LEDGER", tmp_path / "p.jsonl")
    rows = [_cand(symbol=None, title=None, mechanism=None)]
    pc._preregister("unit_test", rows)
    assert len(rows) == 1


def test_the_donation_contract_publishes_its_preregistration_counts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr, "LEDGER", tmp_path / "p.jsonl")
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pc, "_record_in_registry", lambda *a, **k: None)
    now = "2026-09-24T00:00:00+00:00"
    rows = [dict(_cand(symbol="EURUSD"), available_time=now, ingested_time=now,
                 source_version="v1", event_time=now)]
    path = pc.donate("unit_test", rows, tests_run=1)
    assert path is not None
    doc = json.loads(Path(path).read_text("utf-8"))
    assert doc["counts"]["preregistered"] == 1
    assert doc["counts"]["prereg_failed"] == 0
    assert doc["discoveries"][0]["prereg_hash"]


# ------------------------------------------------------------------------- the permanent fence
def test_the_fence_fails_on_an_uncovered_row_donated_after_the_cutover(tmp_path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_preregistration", _ROOT / "scripts" / "check_preregistration.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    seat = tmp_path / "seat"
    seat.mkdir()
    (seat / "discoveries_20991231_0000.json").write_text(json.dumps({
        "source": "seat", "generated_at": "2099-12-31T00:00:00+00:00",
        "discoveries": [{"symbol": "EURUSD"}]}), "utf-8")
    breached = mod.scan_donations((tmp_path,))
    assert breached["post_cutover_rows"] == 1
    assert breached["post_cutover_uncovered"] == 1
    assert breached["post_cutover_offenders"]

    (seat / "discoveries_20991231_0000.json").write_text(json.dumps({
        "source": "seat", "generated_at": "2099-12-31T00:00:00+00:00",
        "discoveries": [{"symbol": "EURUSD", "prereg_hash": "abc123"}]}), "utf-8")
    clean = mod.scan_donations((tmp_path,))
    assert clean["post_cutover_uncovered"] == 0
    assert clean["coverage"] == 1.0


def test_an_absent_donation_corpus_reads_unmeasured_never_a_clean_pass(tmp_path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_preregistration", _ROOT / "scripts" / "check_preregistration.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    empty = mod.scan_donations((tmp_path / "nothing",))
    assert empty["rows"] == 0 and empty["coverage"] is None


def test_the_census_never_backfills_a_card() -> None:
    """A card written after the evidence was seen is a forgery. The census MEASURES the gap and
    marks it; it must never close one, so it does not import the writer at all."""
    src = (_ROOT / "scripts" / "check_preregistration.py").read_text("utf-8")
    assert "register_candidate" not in src
    assert "RETROSPECTIVELY_UNPREREGISTERED" in src


def test_the_coverage_ratchet_reads_the_census_and_is_registered() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_ratchets", _ROOT / "scripts" / "check_ratchets.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "prereg_coverage" in mod._METRICS
    assert mod._prereg_coverage({"donations": {"coverage": 0.42}}) == pytest.approx(0.42)
    assert mod._prereg_coverage({"donations": {}}) is None
    assert mod._prereg_coverage(None) is None


def test_the_donation_path_carries_no_bare_except() -> None:
    """A bare except on a registration path is how this stayed invisible for its whole life.

    MEASURED ON THE AST, never on the line text: the prose above `_preregister` quotes the very
    `except Exception: pass` it replaced, and a grep-shaped fence would read that comment as the
    defect. A fence that cannot tell code from the commentary describing it fails on a correct
    tree, and a fence that fails on a correct tree gets deleted."""
    import ast
    src = (_DESK / "research" / "proposer_common.py").read_text("utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_preregister")
    caught = []
    for node in ast.walk(fn):
        if isinstance(node, ast.ExceptHandler):
            assert node.type is not None, "a bare `except:` on the registration path"
            caught.extend(n.id for n in ast.walk(node.type) if isinstance(n, ast.Name))
    assert caught, "the registration path must still catch its named failures"
    assert "Exception" not in caught and "BaseException" not in caught
