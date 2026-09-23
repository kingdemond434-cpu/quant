"""The units fence must FIND the defect it was built for, not merely fail to find one.

A detector whose only observed behaviour is silence has not been validated. This desk has paid
for that lesson twice -- the L1.66 prototype scored 0/3 on hand-verified positives and reported
a clean sweep, and the gauntlet ran for months without once being shown to pass a known-good
alpha. So the load-bearing test here is the POSITIVE CONTROL: a gateway that prices every
sleeve from gold's constants, which is exactly what this repo shipped until 2026-08-20, must
come back CONSTANT-ON-SIZING-PATH.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_fence():
    spec = importlib.util.spec_from_file_location(
        "check_risk_units", ROOT / "scripts" / "check_risk_units.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


CRU = _load_fence()


#: The sizing path exactly as it stood before the fix: gold's contract size and a frozen
#: EUR/USD rate, applied to whatever symbol the sleeve happened to name.
DEFECTIVE_GATEWAY = '''
DIST_USD = 19.1
CONTRACT_OZ = 100
FX_EUR = 0.92


def realised_q(equity, dist_usd=None):
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    lot = max(_lot_steps(Q_OPT * equity / (d * CONTRACT_OZ * FX_EUR)), 0.01)
    return float(lot * d * CONTRACT_OZ * FX_EUR / equity) if equity > 0 else 0.0


def auto_lot(equity, dist_usd=None):
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    lot = _lot_steps(Q_OPT * equity / (d * CONTRACT_OZ * FX_EUR))
    return float(min(max(lot, 0.01), 5.0))


def promoted_lot(equity, live_n, dist_usd=None):
    ramp = 0.25 if live_n < 50 else (0.5 if live_n < 200 else 1.0)
    lot = auto_lot(equity, dist_usd) * ramp
    return float(min(max(lot, 0.01), 5.0))
'''

#: The same functions with the constants only in the DOCSTRING, where they are the record of
#: what went wrong. A text scan would flag this; an AST walk of executable statements must not.
HISTORY_IN_DOCSTRING = '''
CONTRACT_OZ = 100
FX_EUR = 0.92
GOLD_SYMBOL = "XAUUSD"


def realised_q(equity, dist_usd=None, symbol=GOLD_SYMBOL, info=None):
    """This read `dist * CONTRACT_OZ * FX_EUR` for every sleeve and was wrong by 939x."""
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    return float(_lot_steps(Q_OPT * equity / (d * _eur_per_price_unit(symbol, info))))


def auto_lot(equity, dist_usd=None, symbol=GOLD_SYMBOL, info=None):
    """CONTRACT_OZ * FX_EUR is named here deliberately, as history."""
    d = float(dist_usd) if dist_usd and dist_usd > 0 else DIST_USD
    return float(_lot_steps(Q_OPT * equity / (d * _eur_per_price_unit(symbol, info))))


def promoted_lot(equity, live_n, dist_usd=None, symbol=GOLD_SYMBOL, info=None):
    """FX_EUR was the frozen rate."""
    return auto_lot(equity, dist_usd, symbol, info) * 0.5
'''


@pytest.fixture
def gateway_src(tmp_path, monkeypatch):
    """Point the fence at a synthetic gateway.

    A TUPLE, NOT A PATH, since the gateway was split into `gateway.py` + `decision_core.py`. The
    fence audits the UNION of both halves' function tables -- a sizing function now lives in
    whichever file the split put it in -- so `CRU.GATEWAY` became a tuple and this fixture kept
    handing it a bare Path. Every test in this file then died on `TypeError: 'PosixPath' object is
    not iterable`, which is a fixture that was never updated with the code, not a fence that
    broke: the fence itself is correct and has been correct since the split.
    """
    def _set(src: str):
        p = tmp_path / "gateway.py"
        p.write_text(src, encoding="utf-8")
        monkeypatch.setattr(CRU, "GATEWAY", (p,))
        return p
    return _set


# ------------------------------------------------------------ positive control

def test_the_fence_catches_the_defect_it_was_built_for(gateway_src):
    """THE POSITIVE CONTROL. Without this the fence's OK verdict means nothing."""
    gateway_src(DEFECTIVE_GATEWAY)
    constants, omissions, calls = CRU.audit_sizing_path()
    assert calls > 0, "no sizing call sites found -- the fence scanned nothing"
    names = " ".join(constants)
    assert "auto_lot" in names and "realised_q" in names
    assert "CONTRACT_OZ" in names and "FX_EUR" in names
    # the delegating call inside promoted_lot omits the symbol
    assert any("auto_lot" in o for o in omissions)


def test_the_real_gateway_is_clean_now(gateway_src):
    """The repo's own gateway, after the fix. If this fails the defect is back."""
    constants, omissions, calls = CRU.audit_sizing_path()
    assert calls >= 5, f"only {calls} sizing call sites found -- did the loop change?"
    assert constants == [], f"constants back on the sizing path: {constants}"
    assert omissions == [], f"call sites defaulting to gold: {omissions}"


def test_history_in_a_docstring_is_not_a_defect(gateway_src):
    """These docstrings quote the old formula ON PURPOSE. A fence that punished the record of
    what went wrong would be edited to delete the record."""
    gateway_src(HISTORY_IN_DOCSTRING)
    constants, _, _ = CRU.audit_sizing_path()
    assert constants == [], f"flagged documented history as live code: {constants}"


def test_a_renamed_or_deleted_sizing_function_is_a_defect(gateway_src):
    """A gate that cannot find its subject must not report health (L1.49)."""
    gateway_src("def something_else(equity):\n    return 0.01\n")
    constants, _, _ = CRU.audit_sizing_path()
    assert len(constants) == len(CRU.SIZING_FUNCTIONS)
    assert all("NOT FOUND" in c for c in constants)


def test_an_unparseable_gateway_fails_rather_than_passes(gateway_src):
    gateway_src("def auto_lot(:\n")
    constants, _, calls = CRU.audit_sizing_path()
    assert constants and "unparseable" in constants[0]
    assert calls == 0


# ------------------------------------------------------------ the measurement

def test_the_divergence_is_measured_from_the_venue_not_asserted():
    rows, skipped = CRU.measure_divergence()
    assert rows, "no symbol could be priced -- the universe snapshot is missing or empty"
    by_sym = {r["symbol"]: r for r in rows}
    # The spread that made one constant impossible: five orders of magnitude.
    assert by_sym["EURUSD"]["eur_per_price_unit"] > 10_000
    assert by_sym["BTCUSD"]["eur_per_price_unit"] < 1.0
    for r in rows:
        # published rounded to 4dp, so the tolerance is the rounding and not a fudge
        assert r["error_multiple"] == pytest.approx(
            r["eur_per_price_unit"] / CRU.LEGACY_EUR_PER_PRICE_UNIT, abs=1e-4)
    assert isinstance(skipped, list)


def test_an_unpriceable_symbol_is_counted_not_dropped(tmp_path, monkeypatch):
    """L1.60: a denominator that loses members in silence is a coverage claim we cannot cash."""
    u = tmp_path / "universe.json"
    u.write_text(json.dumps({
        "GOOD": {"tick_size": 0.01, "tick_value": 0.86, "last": "2026-08-14 23:00:00+00:00"},
        "NOTICK": {"tick_size": 0, "tick_value": 0, "last": ""},
    }), encoding="utf-8")
    monkeypatch.setattr(CRU, "UNIVERSE", u)
    rows, skipped = CRU.measure_divergence()
    assert len(rows) == 1 and len(skipped) == 1
    assert "NOTICK" in skipped[0]


def test_an_unreadable_universe_is_unmeasured_not_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(CRU, "UNIVERSE", tmp_path / "nope.json")
    rows, skipped = CRU.measure_divergence()
    assert rows == []
    assert skipped and "unreadable" in skipped[0]


def test_zero_priced_symbols_can_never_exit_zero(tmp_path, monkeypatch):
    """UNMEASURED must never read as OK (L1.28a), and a pass over an empty set is refused
    at the exit site (L1.57)."""
    monkeypatch.setattr(CRU, "UNIVERSE", tmp_path / "nope.json")
    monkeypatch.setattr(CRU, "OUT", tmp_path / "out.json")
    assert CRU.main() != 0
    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["status"] == "UNMEASURED"
    assert payload["symbols_priced"] == 0


def test_a_stale_snapshot_is_its_own_status(tmp_path, monkeypatch):
    """tick_value carries an FX rate, so a stale universe is the frozen constant again."""
    u = tmp_path / "universe.json"
    u.write_text(json.dumps({
        "OLD": {"tick_size": 0.01, "tick_value": 0.86, "last": "2020-01-01 00:00:00+00:00"},
    }), encoding="utf-8")
    monkeypatch.setattr(CRU, "UNIVERSE", u)
    monkeypatch.setattr(CRU, "OUT", tmp_path / "out.json")
    assert CRU.main() != 0
    payload = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert payload["status"] == "SNAPSHOT-STALE"
    assert payload["snapshot_age_days"] > CRU.SNAPSHOT_MAX_AGE_DAYS


def test_the_live_run_writes_its_artifact():
    assert CRU.main() == 0
    payload = json.loads(CRU.OUT.read_text(encoding="utf-8"))
    assert payload["status"] == "OK"
    assert payload["law"] == "L1.67"
    assert payload["symbols_priced"] > 0
    assert payload["sizing_call_sites"] > 0
