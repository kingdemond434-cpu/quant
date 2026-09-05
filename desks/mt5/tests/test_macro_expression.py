"""EXPRESSION -- an impact estimate on an untradeable currency must not dead-end.

The principal's case: a South American country changes something about its bean exports. The
impact is about BRL. BRL is not in the Fusion universe. A pipeline that stops there silently
throws away every commodity-driven signal it will ever produce, and nothing in the logs says so.

These pin the three properties that stop that happening, and one that stops the fix becoming its
own problem:

  1. the impact reaches instruments the desk can actually trade, through MEASURED exposure
  2. the propagation is measured, not tabled -- a source fence fails if anyone ever writes a
     commodity-to-currency mapping into this package
  3. a genuine dead end is NAMED as a blind spot rather than returning an empty list
  4. there is no "boost the opposite side" rule anywhere -- that is the allocator's joint solve
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.expression import (  # noqa: E402
    DRIVER_CLASSES,
    Exposure,
    express,
    learn_aliases,
    lexical_drivers,
    load_aliases,
    load_universe,
    measure_exposures,
    symbol_currencies,
    symbols_in_classes,
    tradeable_currencies,
)
from macro.factors import FactorBasis, MultiplicityLedger, factor_basis  # noqa: E402
from macro.prices import FakePriceReader  # noqa: E402
from macro.schema import Status  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_the_desk_really_can_express_a_soft_commodity_event() -> None:
    """Checked against the universe file rather than assumed."""
    uni = load_universe()
    assert len(uni) > 200
    softs = symbols_in_classes(uni, ("Soft Commodity",))
    assert {"SOYBEAN", "CORN", "WHEAT", "SUGAR", "COTTON"} <= set(softs)
    exotics = symbols_in_classes(uni, ("Forex Exotics",))
    assert len(exotics) > 40, "exotic crosses are real expressions, not a rounding error"
    assert "XCUUSD" in symbols_in_classes(uni, ("Commodities",)), "copper is quoted"


def test_which_economies_are_actually_unreachable_measured_not_assumed() -> None:
    """MEASURED, and it corrects the assumption this module was briefed on.

    BRL is NOT unreachable: USDBRL is quoted, so a Brazilian story has a direct expression.
    ARS, CLP, COP, PEN, TWD, PHP and MYR genuinely are unreachable, so the untradeable-economy
    path is real -- just narrower than one would guess. Pinned because the size of the gap is
    what decides how much the driver route is worth.
    """
    uni = load_universe()
    tradeable = tradeable_currencies(uni)
    assert len(tradeable) == 27
    assert "BRL" in tradeable, "USDBRL is quoted -- the briefing's example is directly tradeable"
    assert {"ARS", "CLP", "COP", "PEN", "TWD", "PHP", "MYR"} & tradeable == set()


def test_a_symbol_that_merely_looks_like_a_pair_does_not_invent_a_currency() -> None:
    """COFARA is robusta/arabica coffee, not COF against ARA. Shape-only parsing invented a
    currency here and would have sent the expression step hunting exposures nobody implied."""
    uni = load_universe()
    assert symbol_currencies("COFARA", uni.get("COFARA")) == ("USD",)
    assert symbol_currencies("EURPLN", uni.get("EURPLN")) == ("EUR", "PLN")
    assert "ARA" not in tradeable_currencies(uni)


def test_reading_a_headline_resolves_the_instrument_it_is_talking_about() -> None:
    """LEXICAL, not causal: that the word 'soybean' refers to SOYBEAN is a naming fact."""
    uni = load_universe()
    al = load_aliases(uni)
    assert lexical_drivers("Brazil raises export tax on soybean shipments", al) == ["SOYBEAN"]
    assert "XTIUSD" in lexical_drivers("OPEC cuts crude output", al)
    assert "XCUUSD" in lexical_drivers("Copper smelter strike extends", al)


def test_a_south_american_soybean_story_reaches_tradeable_instruments_by_measured_exposure(
) -> None:
    """THE PRINCIPAL'S CASE, end to end, using an economy the desk genuinely cannot trade (ARS).

    No table anywhere says which country exports beans. The desk measured which tradeable
    instruments move with SOYBEAN, and the event rides those betas."""
    uni = load_universe()
    # A MEASURED exposure: AUDUSD has an admitted beta on SOYBEAN. Nothing anywhere asserts
    # WHY -- the number is the claim.
    exposures = [
        Exposure("AUDUSD", "SOYBEAN", 0.42, 0.05, 0.28, 0.56, 900, 120, True, Status.MEASURED),
        Exposure("EURUSD", "SOYBEAN", 0.01, 0.05, -0.13, 0.15, 900, 120, False,
                 Status.RECORDED_ONLY),
    ]
    basis = FactorBasis((), {}, {}, 0, Status.UNMEASURED, "not needed for the driver route")
    forecasts, blind = express(
        factor_deltas={}, basis=basis, drivers_named=["SOYBEAN"],
        driver_moves={"SOYBEAN": -1.5}, exposures=exposures, universe=uni,
        economies=["ARS"])

    got = {f.symbol: f for f in forecasts}
    assert "SOYBEAN" in got, "the soft itself is the most direct expression"
    assert "AUDUSD" in got, "and the currency carried by a MEASURED beta"
    assert "EURUSD" not in got, "an unadmitted beta carries nothing"
    assert got["AUDUSD"].expected_move_sigma < 0, "beta positive, driver down"
    assert got["AUDUSD"].path[0] == "driver" and "SOYBEAN" in got["AUDUSD"].path

    ars = [b for b in blind if b.get("economy") == "ARS"]
    assert ars, "an untradeable economy must be recorded, reached or not"
    assert "measured driver/factor exposure" in ars[0]["resolved_via"]


def test_a_genuine_dead_end_is_NAMED_rather_than_silently_empty() -> None:
    uni = load_universe()
    basis = FactorBasis((), {}, {}, 0, Status.UNMEASURED, "")
    forecasts, blind = express(
        factor_deltas={}, basis=basis, drivers_named=[], driver_moves=None,
        exposures=[], universe=uni, economies=["ARS"])
    assert forecasts == []
    assert blind, "an inexpressible event must produce a named blind spot"
    reasons = " ".join(b["note"] for b in blind)
    assert "INEXPRESSIBLE" in reasons or "no admitted" in reasons
    assert "acquisition" in reasons.lower() or "no capital authority" in reasons


def test_the_factor_route_also_reaches_instruments() -> None:
    uni = load_universe()
    basis = FactorBasis(("XAUUSD", "XAGUSD"),
                        {"F1[+XAUUSD,+XAGUSD]": {"XAUUSD": 0.7, "XAGUSD": 0.7}},
                        {"F1[+XAUUSD,+XAGUSD]": 0.6}, 1000, Status.MEASURED, "")
    forecasts, _ = express(factor_deltas={"F1[+XAUUSD,+XAGUSD]": 1.2}, basis=basis,
                           drivers_named=[], driver_moves=None, exposures=[], universe=uni)
    syms = {f.symbol for f in forecasts}
    assert {"XAUUSD", "XAGUSD"} <= syms
    assert all(f.expected_move_sigma > 0 for f in forecasts)
    assert all(f.path[0] == "factor" for f in forecasts)


def test_exposures_are_measured_with_a_multiplicity_charge_that_never_shrinks(
        tmp_path: Path) -> None:
    """Exploring a 251 x 30 grid is paid for in the width of every interval it produces."""
    n = 400
    span = 3600.0
    import math
    drv = [(T0 + timedelta(seconds=span * i), 100.0 * math.exp(0.01 * math.sin(i / 3.0)))
           for i in range(n)]
    # A target that genuinely tracks the driver, and one that is pure noise against it.
    linked = [(t, 50.0 * math.exp(0.008 * math.sin(i / 3.0)))
              for i, (t, _) in enumerate(drv)]
    noise = [(t, 20.0 * math.exp(0.004 * math.cos(i / 7.0) + 0.002 * math.sin(i / 11.0)))
             for i, (t, _) in enumerate(drv)]
    reader = FakePriceReader({"SOYBEAN": drv, "AUDUSD": linked, "USDJPY": noise},
                             dict.fromkeys(("SOYBEAN", "AUDUSD", "USDJPY"), span))
    led = MultiplicityLedger(tmp_path / "m.json")
    out = measure_exposures(reader, targets=["AUDUSD", "USDJPY"], drivers=["SOYBEAN"],
                            ledger=led, min_n=200)
    by = {e.symbol: e for e in out}
    assert by["AUDUSD"].admitted is True
    assert by["AUDUSD"].beta > 0
    assert by["AUDUSD"].cells_charged >= 2

    charged_first = led.total
    led.save()
    again = MultiplicityLedger(tmp_path / "m.json")
    measure_exposures(reader, targets=["AUDUSD"], drivers=["SOYBEAN"], ledger=again, min_n=200)
    again.save()
    assert MultiplicityLedger(tmp_path / "m.json").total >= charged_first, \
        "the charge may never shrink"


def test_thin_data_refuses_rather_than_reporting_a_beta(tmp_path: Path) -> None:
    reader = FakePriceReader(
        {"SOYBEAN": [(T0 + timedelta(hours=i), 100.0 + i) for i in range(20)],
         "AUDUSD": [(T0 + timedelta(hours=i), 50.0 + i * 0.4) for i in range(20)]},
        {"SOYBEAN": 3600.0, "AUDUSD": 3600.0})
    out = measure_exposures(reader, targets=["AUDUSD"], drivers=["SOYBEAN"],
                            ledger=MultiplicityLedger(tmp_path / "m.json"), min_n=250)
    assert out and out[0].status == Status.UNMEASURED and out[0].admitted is False


def test_the_alias_vocabulary_grows_from_evidence() -> None:
    """A commodity, company or policy term nobody listed becomes readable once the market has
    repeatedly shown what it refers to. Still vocabulary -- it asserts no direction."""
    obs = [(f"quixote bean harvest report number {i} released", {"SOYBEAN": 2.0, "CORN": 0.1})
           for i in range(25)]
    learned = learn_aliases(obs, min_instances=20, concentration=0.6)
    assert "quixote" in learned.get("SOYBEAN", [])
    assert "quixote" not in learned.get("CORN", [])


def test_a_factor_basis_is_discovered_not_declared() -> None:
    """The factors themselves must not be hardcoded, or an event that moves a fourth thing has
    nowhere to land."""
    import math
    n = 400
    common = [math.sin(i / 5.0) for i in range(n)]
    panel = {
        "A": [0.01 * c + 0.001 * math.cos(i / 3.0) for i, c in enumerate(common)],
        "B": [0.01 * c + 0.001 * math.cos(i / 7.0) for i, c in enumerate(common)],
        "C": [0.01 * c + 0.001 * math.sin(i / 11.0) for i, c in enumerate(common)],
        "D": [-0.01 * c + 0.001 * math.cos(i / 13.0) for i, c in enumerate(common)],
        "E": [0.002 * math.cos(i / 17.0) for i in range(n)],
    }
    basis = factor_basis(panel, k=2)
    assert basis.status == Status.MEASURED
    # Named after the measurement, never after a story.
    assert all(fid.startswith("F") and "[" in fid for fid in basis.loadings)
    top = next(iter(basis.loadings))
    assert basis.explained[top] > 0.4


def _code_only(path: Path) -> str:
    """The file's CODE, with every comment and string literal removed.

    The distinction `scripts/check_mt5_purity.py` makes and for the same reason: prose ABOUT a
    thing is not the thing. This package's docstrings discuss soybeans, Brazil and gold at
    length -- that is the reasoning, and burning it to satisfy a fence would be the wrong trade.
    What must not exist is a LITERAL mapping in the code.
    """
    import io
    import tokenize

    out: list[str] = []
    with open(path, "rb") as fh:
        try:
            for tok in tokenize.tokenize(io.BytesIO(fh.read()).readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                out.append(tok.string)
        except tokenize.TokenError:
            return path.read_text("utf-8")
    return " ".join(out)


def test_no_commodity_to_currency_table_may_be_written_into_this_package() -> None:
    """SOURCE-LEVEL FENCE, and the most important test in this file.

    A hardcoded propagation table can only ever encode what was known the day it was written --
    exactly what the principal ruled out. The whole macro package's CODE is scanned, not just
    this module, because such a table could be smuggled in anywhere.
    """
    banned = ("SOYBEAN_CURRENCIES", "COMMODITY_CURRENCY", "COMMODITY_TO_CURRENCY",
              "EXPORT_BASKET", "TERMS_OF_TRADE_TABLE", "DRIVER_CURRENCY_MAP",
              "CURRENCY_EXPOSURE_TABLE", "EVENT_IMPACT_TABLE", "EVENT_DIRECTION")
    for path in sorted((_DESK / "macro").glob("*.py")):
        code = _code_only(path)
        for token in banned:
            assert token not in code, f"a hardcoded propagation table appeared in {path.name}"

    # And no currency code that is not USD may appear as a bare identifier or literal in the
    # expression module's code -- the currencies it handles all arrive as data.
    code = _code_only(_DESK / "macro" / "expression.py")
    for ccy in ("BRL", "ARS", "AUD", "JPY", "CLP"):
        assert ccy not in code, f"{ccy} is named in expression.py's code rather than measured"


def test_there_is_no_boost_the_opposite_side_rule_anywhere() -> None:
    """It must fall out of the allocator's joint solve. An event that impairs one exposure often
    impairs its naive opposite too, and hardcoding a paired response would fight the optimiser."""
    for path in sorted((_DESK / "macro").glob("*.py")):
        code = _code_only(path).lower()
        for token in ("opposite_side", "boost_opposite", "invert_exposure",
                      "paired_opposite", "hedge_pair", "offsetting_leg"):
            assert token not in code, f"a paired-opposite rule appeared in {path.name}"


def test_driver_classes_exclude_fx_because_fx_is_the_target_side() -> None:
    assert "Forex" not in DRIVER_CLASSES and "Forex Exotics" not in DRIVER_CLASSES
    assert "Soft Commodity" in DRIVER_CLASSES
