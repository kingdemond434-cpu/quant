"""On a Fusion Zero account the cost is a published constant, and the desk was arguing about 4%.

THE MEASUREMENT. Over the 161 symbols whose stored spread can be verified against their own bars,
COMMISSION IS A MEDIAN 96% OF THE RAW-REGIME ROUND TRIP. Fusion Zero charges USD 2.25 per lot per
side -- contractual, identical for every symbol, and it does not widen under stress. The spread is
the residual, and the desk's stored spreads are wrong in BOTH directions:

    OVER   BlockInc 500x its own bars, USDRUB 34.8x, GBPCHF 23.6x, NZDJPY 9.8x, +2
    UNDER  six symbols billed ZERO against bars that quote a positive spread every hour

The over-charged six sit outside even the 3x their own `stress_costs` gate tested, so nothing on
them can pass the gauntlet -- a Rule 2 breach, not caution.

WHAT THESE TESTS PIN, and the refusals matter more than the arithmetic:

    ZERO IS NOT THE DEFAULT. `run_edges_macro_fusion_sweep` defined these regimes and said in its
    own words that ZERO is "a BOUND, not because any account fills at it". Defaulting to it would
    make every backtest better in the one direction the desk's guards exist to prevent. RAW is the
    default; ZERO is computed and published beside it.

    THE REGIMES ARE MIRRORED, NOT INVENTED. A test asserts this module's table equals the sweep's,
    so the two cannot drift into describing two different accounts.

    THE COMMISSION SHARE IS MEASURED ONLY WHERE THE SPREAD IS VERIFIED. `Costs.from_symbol` floors
    the spread term at 0.05, so a symbol with a zero or broken spread reports commission as ~99%
    of its cost BY CONSTRUCTION. Pooling those would turn an artifact of the floor into a headline
    about the account.

    THE FLAG LINE IS THE GAUNTLET'S 3x, NOT A NUMBER CHOSEN HERE. At a 1.2x line the audit
    reported 28 rows of which 22 were two estimators disagreeing -- the lesson `check_time_joins`
    learned at 75. Between 1.2x and 3x a row is counted as WIDE and not flagged.

    IT REWRITES NO REGISTRY. `median_spread_pts` is a money-path field; rewriting it re-judges
    every certificate priced against it and rebases the forward clocks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.portfolio import fusion_cost as fc  # noqa: E402


def _desk(tmp: Path, symbols: dict[str, dict], hours: dict[str, float | None]) -> Path:
    data = tmp / "desks" / "mt5" / "data"
    (data / "universe").mkdir(parents=True, exist_ok=True)
    (data / "universe" / "universe.json").write_text(
        json.dumps({"symbols": symbols}), encoding="utf-8")
    surf = {"symbols": {s: {"hours": {
        str(h): ({"status": "MEASURED", "p50": v} if v is not None else {"status": "UNMEASURED"})
        for h in range(24)}} for s, v in hours.items()}}
    (data / "cost_surface.json").write_text(json.dumps(surf), encoding="utf-8")
    return tmp


def _meta(spread: float | None, *, source: str = "", tick: float = 1e-5,
          contract: float = 1e5, tick_value: float = 1.0) -> dict:
    m: dict = {"tick_size": tick, "contract_size": contract, "tick_value": tick_value}
    if spread is not None:
        m["median_spread_pts"] = spread
    if source:
        m["_provenance"] = {"median_spread_pts": {"source": source}}
    return m


# --------------------------------------------------------------------- the account contract ---
def test_the_commission_is_fusions_published_per_side_figure():
    """Cited at engine.py:39 and used as validate_fusion.FUSION_COMMISSION. Changing it here
    would silently re-price the whole book against an account the desk does not hold."""
    assert fc.COMMISSION_PER_LOT_PER_SIDE == 2.25
    assert fc.COMMISSION_PER_LOT_PER_SIDE * 2 == 4.50


def test_the_regimes_mirror_the_desks_own_table():
    """Two tables describing one account is how they end up describing two."""
    sweep = _ROOT / "desks" / "mt5" / "research" / "run_edges_macro_fusion_sweep.py"
    src = sweep.read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.startswith("COST_REGIMES"))
    assert eval(line.split("=", 1)[1].strip()) == fc.COST_REGIMES


def test_zero_is_a_bound_and_never_the_default():
    """`run_edges_macro_fusion_sweep`: ZERO is "kept because it is a BOUND, not because any
    account fills at it". Defaulting to it makes every backtest better in the one direction the
    guards exist to prevent."""
    assert fc.DEFAULT_REGIME == "RAW"
    assert fc.COST_REGIMES[fc.DEFAULT_REGIME] > 0.0
    assert fc.COST_REGIMES["ZERO"] == 0.0


def test_zero_regime_still_charges_the_commission():
    """"Commission-only" is not "free". universe.py measured EURUSD at 17.21 per round trip."""
    rt = fc.round_trip_per_lot(_meta(12.0))
    assert rt["ZERO"] > 0.0
    assert rt["ZERO"] > fc.COMMISSION_PER_LOT_PER_SIDE * 2
    assert rt["RAW"] > rt["ZERO"]
    assert rt["WIDE"] > rt["RAW"]


def test_the_zero_regime_is_not_actually_a_zero_spread_bound():
    """`Costs.from_symbol` ends `max(spread * mult, SPREAD_FLOOR)`, so at mult=0.0 the spread does
    not vanish -- it floors. The "optimistic bound" therefore still carries a residual, which is
    arguably the RIGHT behaviour on a raw account and is certainly not what the name says. Pinned
    here so nobody computes a bound they think is tighter than it is."""
    rt = fc.round_trip_per_lot(_meta(12.0))
    commission_only = fc.COMMISSION_PER_LOT_PER_SIDE * 2
    assert rt["ZERO"] == pytest.approx(commission_only + fc.ENGINE_SPREAD_FLOOR)
    assert fc.ENGINE_SPREAD_FLOOR > 0.0


def test_commission_dominates_on_a_raw_account():
    """The finding: the spread argument is about the last few percent."""
    rt = fc.round_trip_per_lot(_meta(12.0))
    assert rt["ZERO"] / rt["RAW"] > 0.5


# ------------------------------------------------------------------------ the sanity gate -----
def test_a_charge_far_above_its_own_bars_is_impossible(tmp_path):
    """A bar stamp samples the widest instant of its hour, so the bar median is already the WIDE
    reading. GBPCHF is charged 165 against bars of 7."""
    root = _desk(tmp_path, {"X": _meta(165.0, source="realized_fills")}, {"X": 7.0})
    doc = fc.audit(root)
    assert doc["by_verdict"][fc.IMPOSSIBLE] == 1
    row = doc["over_charged"][0]
    assert row["charged_over_bars"] > 20
    assert "nothing on this symbol can pass" in row["why"]


def test_a_modest_disagreement_is_wide_and_not_a_defect(tmp_path):
    """At a 1.2x line the real audit reported 28 rows of which 22 were ordinary disagreement."""
    root = _desk(tmp_path, {"X": _meta(4.0)}, {"X": 3.0})
    doc = fc.audit(root)
    assert doc["by_verdict"][fc.WIDE] == 1 and doc["by_verdict"][fc.IMPOSSIBLE] == 0
    assert "not a defect" in doc["wide_of_bars"][0]["why"]


def test_the_flag_line_is_the_gauntlets_stress_multiple():
    """3.0 is `stress_costs`'s own. A charge inside it is covered by a gate that already ran."""
    assert fc.IMPLAUSIBLE_ABOVE_BAR == 3.0
    assert fc.NOTEWORTHY_ABOVE_BAR < fc.IMPLAUSIBLE_ABOVE_BAR


def test_exactly_at_three_times_is_still_covered(tmp_path):
    root = _desk(tmp_path, {"X": _meta(9.0)}, {"X": 3.0})
    assert fc.audit(root)["by_verdict"][fc.IMPOSSIBLE] == 0
    root2 = _desk(tmp_path / "b", {"X": _meta(9.3)}, {"X": 3.0})
    assert fc.audit(root2)["by_verdict"][fc.IMPOSSIBLE] == 1


def test_zero_charged_against_positive_bars_is_under_charged(tmp_path):
    """Fusion Zero IS commission-only on some instruments, so 0.0 is real there -- but not on one
    whose bars quote a positive spread every hour."""
    root = _desk(tmp_path, {"X": _meta(0.0)}, {"X": 5.0})
    doc = fc.audit(root)
    assert doc["by_verdict"][fc.ZERO_BUT_BARS] == 1
    assert "Under-charged" in doc["under_charged"][0]["why"]


def test_a_symbol_with_no_bars_is_unverifiable_not_a_pass(tmp_path):
    root = _desk(tmp_path, {"X": _meta(99.0)}, {"X": None})
    doc = fc.audit(root)
    assert doc["by_verdict"][fc.UNVERIFIABLE] == 1
    assert "Unverifiable is not a pass" in doc["symbols"][0]["why"]


# --------------------------------------------------------------------------- the headline -----
def test_the_commission_share_excludes_symbols_whose_spread_is_broken(tmp_path):
    """`Costs.from_symbol` floors the spread at 0.05, so a zero-spread symbol reports commission
    as ~99% of cost BY CONSTRUCTION. Pooling those turns a floor artifact into a headline."""
    root = _desk(tmp_path,
                 {"OKAY": _meta(12.0), "BROKEN": _meta(0.0)},
                 {"OKAY": 12.0, "BROKEN": 5.0})
    doc = fc.audit(root)
    assert doc["commission_share_measured_on"] == 1, "the broken symbol entered the headline"
    assert doc["by_verdict"][fc.ZERO_BUT_BARS] == 1


def test_the_audit_rewrites_no_registry():
    """median_spread_pts is a money-path field: rewriting it re-judges every certificate priced
    against it and rebases the forward clocks."""
    src = (_ROOT / "libs" / "portfolio" / "fusion_cost.py").read_text(encoding="utf-8")
    for forbidden in ("universe.json\", \"w", "subprocess", "def apply", "def repair"):
        assert forbidden not in src, f"fusion_cost reached for {forbidden}"
    assert src.count("write_text(") == 1
    assert fc.OUT_REL.startswith("desks/mt5/reports/")


def test_the_arithmetic_is_the_engines_and_not_reimplemented():
    """`Costs.from_symbol` handles two unit traps this desk has already paid for -- points to
    price units, and commission via `quote_per_account`, whose absence undercharged the JPY
    crosses by 184x."""
    src = (_ROOT / "libs" / "portfolio" / "fusion_cost.py").read_text(encoding="utf-8")
    assert "Costs.from_symbol" in src
    assert "tick_size" not in src.split('"""', 2)[2], "the module re-derives price units itself"


def test_a_jpy_cross_converts_commission_through_tick_value():
    """The 184x undercharge: on a non-account-currency quote, commission is not price units."""
    jpy = fc.round_trip_per_lot(_meta(15.0, tick=0.001, contract=1e5, tick_value=0.54))
    same = fc.round_trip_per_lot(_meta(15.0, tick=0.001, contract=1e5, tick_value=1.0))
    assert jpy["ZERO"] != same["ZERO"], "tick_value did not enter the commission conversion"


@pytest.mark.parametrize("regime", sorted(fc.COST_REGIMES))
def test_every_regime_is_computable_for_every_shape(regime):
    for meta in (_meta(12.0), _meta(0.0), _meta(None), _meta(500.0, tick=0.001)):
        assert fc.round_trip_per_lot(meta)[regime] >= 0.0
