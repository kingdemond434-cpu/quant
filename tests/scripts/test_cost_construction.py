"""`Costs.from_symbol` is the only correct constructor, and 24 call sites still build by hand.

THE TWO TRAPS, both documented in this repo before this census existed, and both still live:

  QUOTE_PER_ACCOUNT. `engine.Costs.from_symbol`: "On a EUR account, CADJPY prices in yen: one yen
  of price is worth 0.005418 EUR, so a 7.00 EUR round-turn commission is 0.01292 yen of price --
  and the engine was charging 7.00/100000 = 0.00007. 184x too little, ON THE JPY CROSSES WHERE
  THIS DESK'S SURVIVING EDGES ACTUALLY LIVE, in the direction that manufactures survivors." It
  defaults to 1.0 so adding it changed no existing call site silently -- the right default, and
  also the reason the sites still carry the bug.

  PER-SIDE VERSUS ROUND-TURN. `orthogonal_sweep.py:761`: "commission_per_lot=3.50, a ROUND-TURN
  figure in a PER-SIDE field ($7.00 charged)". Fusion Zero's contract is 2.25 per side.

THEY PUSH IN OPPOSITE DIRECTIONS and a site can carry both, so they are counted separately and
never netted.

THE PRECISION TESTS ARE THE POINT, AGAIN. The first pass reported 8 sites on a clock. Reading
them found three real ones and five false positives of two distinct kinds -- and one of those was
`shadow_forward.frozen_costs`, the LIVE FORWARD LEDGER, which builds via `Costs(**mapping)` and
explicitly requires `quote_per_account` in a `required` set. Reporting the forward path as
mispriced when it is correct is worse than reporting nothing at all.

    UNPACKED KWARGS cannot be read statically, so the verdict is UNKNOWN and a person opens it.
    LITERAL FIXTURES are not priced instruments: `check_backtest_realism` builds
    `Costs(spread_per_lot=16.0, ...)` beside `Costs(spread_per_lot=160.0, commission_per_lot=
    22.5, ...)` to assert cost scales with notional. The 22.5 is deliberately ten times.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import check_cost_construction as cc  # noqa: E402


def _mod(tmp_path: Path, body: str, name: str = "m.py") -> Path:
    p = tmp_path / "desks" / "mt5" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _scan(tmp_path: Path, body: str, live: set[str] | None = None):
    return cc.scan_module(_mod(tmp_path, body), tmp_path, live or set())


def test_the_per_side_contract_matches_the_cost_model():
    """Two constants describing one account is how they end up describing two."""
    from libs.portfolio import fusion_cost as fc
    assert cc.COMMISSION_PER_SIDE == fc.COMMISSION_PER_LOT_PER_SIDE


def test_from_symbol_is_correct(tmp_path):
    sites = _scan(tmp_path, "c = Costs.from_symbol(meta, mult=2.0)\n")
    assert [s.verdict for s in sites] == [cc.CORRECT]


def test_a_hand_rolled_call_without_quote_per_account_is_flagged(tmp_path):
    sites = _scan(tmp_path, 'c = Costs(spread_per_lot=s, commission_per_lot=2.25, '
                            'contract_oz=meta["contract_size"])\n')
    assert [s.verdict for s in sites] == [cc.NO_QPA]
    assert "184x too little" in sites[0].why


def test_a_round_turn_figure_in_a_per_side_field_is_flagged(tmp_path):
    sites = _scan(tmp_path, 'c = Costs(spread_per_lot=s, commission_per_lot=3.50, '
                            'contract_oz=meta["contract_size"], quote_per_account=q)\n')
    assert [s.verdict for s in sites] == [cc.ROUND_TURN]
    assert "7.00 a round trip" in sites[0].why


def test_both_traps_at_once_is_its_own_verdict(tmp_path):
    """Netting them would report a site undercharging 184x and overcharging 1.56x as fine."""
    sites = _scan(tmp_path, 'c = Costs(spread_per_lot=s, commission_per_lot=3.50, '
                            'contract_oz=meta["contract_size"])\n')
    assert [s.verdict for s in sites] == [cc.BOTH]
    assert "184x" in sites[0].why and "round trip" in sites[0].why


def test_unpacked_kwargs_are_unknown_and_never_flagged(tmp_path):
    """`shadow_forward.frozen_costs` builds this way and IS correct. A false positive on the live
    forward ledger is worse than no census."""
    sites = _scan(tmp_path, 'c = Costs(**{n: float(fields[n]) for n in required})\n')
    assert [s.verdict for s in sites] == [cc.UNKNOWN]
    assert "Open it rather than trusting" in sites[0].why


def test_a_literal_fixture_is_not_a_priced_instrument(tmp_path):
    sites = _scan(tmp_path, "small = Costs(spread_per_lot=16.0, commission_per_lot=2.25, "
                            "contract_oz=100.0)\n")
    assert [s.verdict for s in sites] == [cc.FIXTURE]


def test_a_costs_derived_from_another_inherits_its_conversions(tmp_path):
    sites = _scan(tmp_path, "c2 = Costs(costs.spread_per_lot * 2, commission_per_lot=2.25)\n")
    assert [s.verdict for s in sites] == [cc.DERIVED]


def test_the_live_flag_comes_from_a_real_scheduler(tmp_path):
    sites = _scan(tmp_path, 'c = Costs(spread_per_lot=s, commission_per_lot=2.25, '
                            'contract_oz=meta["contract_size"])\n', live={"m"})
    assert sites[0].live is True


def test_the_real_repo_has_no_broken_site_on_a_clock():
    """THE NUMBER THAT IS A WORK-LIST. A trap in a script no clock reaches costs nothing until
    someone runs it; one on a scheduled path is charging wrong money now. Three were fixed --
    exit_study, run_hunt12 and full_pipeline -- and this fails if a fourth appears."""
    doc = cc.census(_ROOT)
    assert doc["n_sites"] > 50, "the scan found almost nothing, so it is probably broken"
    assert doc["n_broken_on_a_clock"] == 0, (
        f"{doc['n_broken_on_a_clock']} cost sites on a schedule are missing a unit conversion: "
        f"{[s['module'] for s in doc['broken_on_a_clock']]}")


def test_the_three_fixed_sites_now_use_from_symbol():
    """They carried both traps AND the gold override the engine calls near-spread-free.

    CHECKED IN THE AST, NOT THE TEXT. Each of these files still EXPLAINS the old constants in a
    comment -- deliberately, because a fix nobody can read is a fix that gets undone -- so a
    substring search over the source would fail on the very prose that documents the repair.
    """
    import ast as _ast

    for rel in ("desks/mt5/research/exit_study.py", "desks/mt5/run_hunt12.py",
                "desks/mt5/scripts/full_pipeline.py"):
        src = (_ROOT / Path(*rel.split("/"))).read_text(encoding="utf-8")
        tree = _ast.parse(src)
        assert "Costs.from_symbol" in src, rel
        # The census is the judge, not a ban on the name: a Costs DERIVED from another inherits
        # its conversions and is fine. What must be gone is any verdict that says a conversion
        # was dropped.
        bad = [x for x in cc.scan_module(_ROOT / Path(*rel.split("/")), _ROOT, set())
               if x.verdict in (cc.NO_QPA, cc.ROUND_TURN, cc.BOTH, cc.STRESSED_COMMISSION)]
        assert not bad, f"{rel} line {bad[0].line}: {bad[0].verdict}"
        # The gold override and the round-turn commission are gone from the CODE.
        literals = {n.value for n in _ast.walk(tree)
                    if isinstance(n, _ast.Constant) and isinstance(n.value, float)}
        assert 0.48 not in literals, f"{rel} still carries the gold spread override"
        assert 3.50 not in literals, f"{rel} still carries a round-turn commission"


def test_commission_is_never_scaled_by_a_stress_multiplier():
    """Commission is contractual and does not widen -- `Costs.stressed` scales the spread only.
    `full_pipeline.costs_for` multiplied it, so a 2x stress quietly billed $14.00 a round trip."""
    src = (_ROOT / "desks" / "mt5" / "scripts" / "full_pipeline.py").read_text(encoding="utf-8")
    assert "commission_per_lot=3.50 * mult" not in src
    assert "mult=mult" in src, "the multiplier must still reach the SPREAD"


def test_the_census_edits_no_source():
    """It enumerates and stops. Rewriting 24 money-path call sites blind, to chase a trap that
    only bites non-account-currency quotes, is how one bug becomes twenty-four."""
    src = (_ROOT / "scripts" / "check_cost_construction.py").read_text(encoding="utf-8")
    for forbidden in ("subprocess", "def fix", "def repair", "os.rename", "unlink("):
        assert forbidden not in src, f"the census reached for {forbidden}"
    # It writes exactly one path, and it is a report.
    assert src.count("write_text(") == 1
    assert cc.OUT_REL.startswith("desks/mt5/reports/")


def test_a_stress_that_widens_a_contractual_commission_is_flagged(tmp_path):
    """Commission does not widen. `Costs.stressed` scales the spread alone, and the positional
    three-field rebuild this replaces ALSO dropped quote_per_account -- the trap engine.py:71
    records. run_hunt12 did both at once, on a clock."""
    sites = _scan(tmp_path, "r2 = Costs(costs.spread_per_lot * 2, costs.commission_per_lot * 2, "
                            "costs.contract_oz)\n")
    assert [s.verdict for s in sites] == [cc.STRESSED_COMMISSION]
    assert "Costs.stressed" in sites[0].why


def test_a_plain_derived_costs_is_not_flagged(tmp_path):
    sites = _scan(tmp_path, "c2 = Costs(spread_per_lot=costs.spread_per_lot * 3, "
                            "commission_per_lot=2.25, contract_oz=costs.contract_oz)\n")
    assert [s.verdict for s in sites] == [cc.DERIVED]


def test_run_hunt12_stresses_through_the_engines_own_constructor():
    src = (_ROOT / "desks" / "mt5" / "run_hunt12.py").read_text(encoding="utf-8")
    assert "costs.stressed(2.0)" in src
