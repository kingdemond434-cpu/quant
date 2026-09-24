"""THE LIVE-SLEEVE COST FENCE, pinned.

WHAT THESE PIN AND WHY IT IS WORTH PINNING. On 2026-09-24 the trading box carried 355 LIVE
clocks; 13 of them could not say what they were charged and one had its family and selector
transposed. Both came from a single `sleeve_registry.freeze()` caller. The fence below is the
only thing that makes either shape loud, so the properties that matter are:

  * a LIVE row with no cost basis FAILS -- a null cost is UNMEASURED, never zero;
  * a RETIRED row with no cost basis does not, because it is not being traded;
  * a selector that names a registered family FAILS, because the canonical identity is
    `symbol|family|selector` and a transposition breaks every join the row participates in;
  * an absent registry is a verdict about the HOST and must not read as a failure of the desk;
  * a registry that parses with no LIVE row at all is UNMEASURED and must NOT pass.

The last two are the pair that fence_exit exists to keep apart, and getting them the wrong way
round is how a fence reports SUCCESS over an input that vanished.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_live_sleeve_cost as F  # noqa: E402

PRICED = {"spread_per_lot": 7.0, "commission_per_lot": 2.0,
          "contract_oz": 100.0, "quote_per_account": 1.15844}


def _row(**kw):
    ident = {"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia"}
    ident.update(kw.pop("identity", {}))
    row = {"identity": ident, "status": "LIVE", "cost_fields": dict(PRICED)}
    row.update(kw)
    return row


def _write(tmp_path: Path, rows: dict) -> Path:
    p = tmp_path / "sleeve_registry.json"
    p.write_text(json.dumps({"sleeves": rows}), "utf-8")
    return p


def _scan(tmp_path: Path, rows: dict):
    return F.scan(_write(tmp_path, rows), tmp_path / "no_such_roster.json")


def test_every_live_row_priced_is_ok(tmp_path):
    rep = _scan(tmp_path, {"XAUUSD.asia": _row()})
    assert rep["status"] == F.OK, rep
    assert rep["n_live"] == 1 and rep["n_null_cost"] == 0


@pytest.mark.parametrize("cost_fields", [
    None,
    {},
    {"spread_per_lot": 7.0},                                    # incomplete
    {**PRICED, "commission_per_lot": None},                     # an explicit null
    {**PRICED, "quote_per_account": 0.0},                       # a scale of zero prices nothing
    {**PRICED, "spread_per_lot": float("nan")},                 # non-finite
    {**PRICED, "contract_oz": "100"},                           # string sneaks past json
])
def test_a_live_row_that_cannot_say_what_it_is_charged_fails(tmp_path, cost_fields):
    """A null cost is UNMEASURED, and UNMEASURED on a row trading real money is a defect."""
    rows = {"XAUUSD.asia": _row(cost_fields=cost_fields)}
    if cost_fields is None:
        rows["XAUUSD.asia"].pop("cost_fields")
    rep = _scan(tmp_path, rows)
    if cost_fields == {**PRICED, "contract_oz": "100"}:
        # A numeric string IS usable -- float() takes it and the engine would too. Pinned so a
        # future tightening is a deliberate edit rather than an accident of parsing.
        assert rep["status"] == F.OK, rep
        return
    assert rep["status"] == F.NULL_COST, rep
    assert rep["n_null_cost"] == 1
    assert rep["null_cost"][0]["symbol"] == "XAUUSD"


def test_a_retired_row_with_no_cost_is_not_a_defect(tmp_path):
    """Only a LIVE row is one the desk is trading. Judging retired rows would make the fence
    permanently red over history nobody can change, which is how a fence gets switched off."""
    rows = {"XAUUSD.asia": _row(),
            "OLD.asia": _row(status="RETIRED", cost_fields=None)}
    rows["OLD.asia"].pop("cost_fields")
    assert _scan(tmp_path, rows)["status"] == F.OK


def test_a_selector_that_names_a_family_is_a_transposition(tmp_path):
    """`XAUUSD.multi_speed_trend.continuous@D1` froze as family=session_range_breakout,
    selector=multi_speed_trend. The canonical identity is symbol|family|selector, so the row
    can never join its own certificate."""
    rows = {
        "legit": _row(identity={"family": "multi_speed_trend", "selector": "continuous"}),
        "swapped": _row(identity={"family": "session_range_breakout",
                                  "selector": "multi_speed_trend"}),
    }
    rep = _scan(tmp_path, rows)
    assert rep["status"] == F.SWAPPED, rep
    assert rep["n_swapped"] == 1
    assert rep["swapped"][0]["key"] == "swapped"


def test_the_family_vocabulary_comes_from_the_registry_including_retired_rows(tmp_path):
    """A family retired yesterday is still a family name. Dropping retired rows from the
    vocabulary would make the swap detector weaker every time a clock retires."""
    rows = {
        "dead": _row(status="RETIRED",
                     identity={"family": "multi_speed_trend", "selector": "continuous"}),
        "swapped": _row(identity={"family": "session_range_breakout",
                                  "selector": "multi_speed_trend"}),
    }
    assert _scan(tmp_path, rows)["status"] == F.SWAPPED


def test_a_window_selector_is_never_a_transposition(tmp_path):
    """asia / london_am / afternoon / continuous are windows, not families. The detector must
    not cry wolf over the ordinary shape or it will be switched off (L1.43)."""
    rows = {f"XAUUSD.{sel}": _row(identity={"selector": sel})
            for sel in ("asia", "london_am", "afternoon", "ny_open", "continuous")}
    assert _scan(tmp_path, rows)["status"] == F.OK


def test_no_registry_is_a_verdict_about_the_host_and_exits_zero(tmp_path):
    rep = F.scan(tmp_path / "absent.json", tmp_path / "absent_roster.json")
    assert rep["status"] == F.NOT_READABLE
    assert F.main(["--registry", str(tmp_path / "absent.json"),
                   "--roster", str(tmp_path / "absent_roster.json"),
                   "--report", str(tmp_path / "rep.json")]) == 0


def test_a_registry_with_no_live_row_is_unmeasured_and_never_passes(tmp_path):
    """The false-GREEN shape fence_exit exists to end: an input that vanished must not report
    success. A registry that parses with zero LIVE rows examined NOTHING."""
    rep = _scan(tmp_path, {"OLD.asia": _row(status="RETIRED")})
    assert rep["status"] == F.UNMEASURED
    assert F.main(["--registry", str(_write(tmp_path, {"OLD.asia": _row(status="RETIRED")})),
                   "--roster", str(tmp_path / "absent_roster.json"),
                   "--report", str(tmp_path / "rep.json")]) == F.fence_exit(
        F.UNMEASURED, F._PASSING)


def test_the_fence_fails_loudly_end_to_end(tmp_path):
    """The exit code is the only thing cron, systemd and the pre-push hook read."""
    reg = _write(tmp_path, {"XAUUSD.asia": {"identity": {"symbol": "XAUUSD",
                                                         "family": "session_range_breakout",
                                                         "selector": "asia"},
                                            "status": "LIVE"}})
    rc = F.main(["--registry", str(reg), "--roster", str(tmp_path / "absent.json"),
                 "--report", str(tmp_path / "rep.json")])
    assert rc == 2
    written = json.loads((tmp_path / "rep.json").read_text("utf-8"))
    assert written["status"] == F.NULL_COST
    assert written["n_null_cost"] == 1


def test_the_fence_never_writes_to_the_registry(tmp_path):
    """It reports; it does not size, retire, disable or repair. A LIVE sleeve stays LIVE."""
    reg = _write(tmp_path, {"XAUUSD.asia": _row(cost_fields={})})
    before = reg.read_bytes()
    F.main(["--registry", str(reg), "--roster", str(tmp_path / "absent.json"),
            "--report", str(tmp_path / "rep.json")])
    assert reg.read_bytes() == before
