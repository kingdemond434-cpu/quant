"""Institutional mechanism cards, aimed at the axes this desk has never certified.

WHAT THIS IS AND IS NOT. Every mechanism below is drawn from PUBLIC material -- firm strategy
descriptions, interviews, patents, regulatory filings, litigation records and institutional
reporting. Nothing here is confidential, none of it is a leaked parameter, and no card claims to
reproduce any firm's implementation. What is portable is the MECHANISM CLASS and the economic
reason it should exist; the parameterisation is this desk's to find and the evidence is this
desk's to earn through all ten gates.

WHY THE CARDS TARGET THESE INSTRUMENTS AND NOT BETTER FX CELLS. Measured 2026-09-14: 58
certificates, ALL of them H1/asia, 27 of 28 certificate symbols FX or FX-exotic and exactly one a
commodity. Meanwhile the mandate's other classes hold ZERO certificates between them while their
H1 bars sit on disk already collected:

    Indices 16 | Crypto 14 | Commodities 11 | Soft Commodity 11 | Energy 3 | Bonds 3

Fifty-eight instruments, six asset classes, no hypothesis ever minted. A better XAUUSD cell adds a
correlated bet to a book already at n_eff 5.6; a certificate on UST10Y or SUGAR opens an axis. The
binding constraint is independence, so the cards go where the desk has never looked.

AND THE ECONOMIC NOTE IS LOAD-BEARING, NOT DECORATION. `economic_prior` refuses any cell whose
mechanism_status is not NAMED -- that is the gate that keeps statistical mining out of the
certificate stock. Each card therefore carries the actual reason the effect should exist, sourced
to the public record. A card that cannot state one does not belong here and is not written.

THE THREE ARCHITECTURE IDEAS ARE DELIBERATELY ABSENT FROM THE CARDS. "Predict the predictor"
(Marshall Wace TOPS), "predict which strategy deserves the next dollar" (Citadel/Millennium) and
"let cost and capacity decide whether a forecast becomes a trade" (XTX) are not price families and
cannot be expressed as one. They belong in the CEO docket as capability proposals, and are named
in the module docstring so they are not quietly lost.

    python desks/mt5/research/institutional_cards.py            # report
    python desks/mt5/research/institutional_cards.py --apply    # write the seat's donation
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
UNIVERSE = BASE / "data" / "universe" / "universe.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SEAT = BASE / "data" / "intelligence" / "institutional"
REPORT = BASE / "reports" / "INSTITUTIONAL_CARDS.json"

#: Asset classes the desk may hunt for statistical hypotheses. Single-name EQUITIES are excluded
#: by the principal's standing order of 2026-09-06 -- they are traded on news and earnings in the
#: event lane, never mined -- and excluding them here is that law, not an oversight.
HUNTABLE = ("Indices", "Commodities", "Energy", "Soft Commodity", "Bonds", "Crypto")

#: (family, asset classes, economic note, public source). The family must be one the desk already
#: registers, or the card compiles to nothing; the note is what `economic_prior` reads.
CARDS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("turn_of_month", ("Indices",),
     "Index funds and pension mandates rebalance on a calendar, not on a view. The flow is "
     "forced, dated and public, so its price impact is a mechanism rather than a pattern -- and "
     "it lands on the INDEX, which is where the rebalancing happens, not on FX.",
     "ExodusPoint publishes index rebalance, IPO, spin-off and share-class arbitrage as explicit "
     "quantitative/event strategies targeting passive flows."),
    ("calendar_month", ("Indices", "Bonds"),
     "Month and quarter boundaries concentrate mandated flow: duration extension in bond indices "
     "at month end, equity index reconstitution at quarter end. The date is known in advance and "
     "the participant is price-insensitive.",
     "Same ExodusPoint passive-flow family; bond index duration extension is a documented "
     "month-end mechanic."),
    ("opening_range", ("Indices",),
     "An index CFD has a real cash open; FX does not. Overnight information accumulates against a "
     "closed book and is repriced in the first minutes, so the opening range carries information "
     "for indices that the same construction cannot carry for a 24-hour currency.",
     "Standard market-structure reasoning; Jane Street describes detailed market mechanics as "
     "co-equal with quantitative analysis."),
    ("multi_speed_trend", ("Commodities", "Energy", "Soft Commodity", "Bonds", "Crypto"),
     "Trend persistence is one of the most widely documented premia and is strongest where "
     "hedging pressure and inventory cycles dominate -- physical commodities and rates -- rather "
     "than in majors. Different speeds respond to different regimes, so several are carried.",
     "Man AHL and Winton built their firms on diversified multi-horizon trend; Harding has "
     "publicly warned that a crowded edge decays, which is why the uncrowded markets matter."),
    ("carry", ("Bonds", "Commodities", "Crypto"),
     "Carry is a premium for bearing a funding or storage cost that someone else wishes to avoid: "
     "term premium in rates, convenience yield and storage in commodities, perpetual funding in "
     "crypto CFDs. Each is a different economic payer, which is what makes them independent.",
     "AQR publishes carry as one of its core documented premia across asset classes."),
    ("cross_sectional", ("Indices", "Commodities", "Soft Commodity"),
     "Sixteen equity indices, eleven metals and eleven softs are genuine cross-sections that share "
     "a factor and differ idiosyncratically. Ranking within the cross-section removes the common "
     "move and isolates the relative mispricing -- the classic stat-arb construction.",
     "D.E. Shaw pioneered statistical arbitrage; Citadel assigned a team to reverse-engineer it "
     "and was trading it within six months."),
    ("pca_residual", ("Indices", "Commodities", "Crypto"),
     "Within a tight cross-section the first components ARE the risk factor. Trading the residual "
     "is trading what the factor does not explain, which is by construction closer to orthogonal "
     "to the book than another directional bet on the same factor.",
     "Residualisation against common factors is the standard institutional construction for "
     "market-neutral books."),
    ("cot_positioning", ("Commodities", "Energy", "Indices"),
     "The CFTC publishes Commitments of Traders weekly: how commercials, managed money and small "
     "traders are actually positioned. Extreme speculative positioning against commercial hedgers "
     "has a real mechanism -- someone must be unwound -- and the data is free and public.",
     "Citadel expects its teams to know how rivals are positioned; COT is the public, lawful "
     "version of that question for futures-linked instruments."),
    ("macro_conditional", ("Energy", "Soft Commodity"),
     "Physical commodities have weather and inventory as genuine causal inputs to supply: natural "
     "gas to heating and cooling degree days, softs to growing-region conditions. This is a "
     "cause-and-effect claim about a real balance, not a chart shape.",
     "Citadel has employed hydrologists and invested in turning sensor and satellite data into "
     "commodity forecasts; Bridgewater's stated method is explicit cause-and-effect modelling."),
    ("vol_transition", ("Indices", "Crypto"),
     "Volatility clusters and mean-reverts, and the transition between regimes is where risk "
     "limits force position changes on participants who did not choose the timing. Indices and "
     "crypto CFDs show the widest and most regular regime shifts in this universe.",
     "Capula specialises in rates and volatility relative value; Brevan Howard describes seeking "
     "convexity where pricing misrepresents the distribution."),
    ("regime_transition", ("Indices", "Bonds"),
     "Growth and inflation surprises move equities and bonds in opposite directions in some "
     "regimes and the same direction in others. Conditioning on the latent regime beats trying to "
     "predict the level, and the equity/bond pair is where the sign flip is sharpest.",
     "Bridgewater's published architecture is growth surprise x inflation surprise mapped to "
     "asset behaviour, codified into systematic rules."),
    ("correlation_regime", ("Indices", "Crypto"),
     "A correlation that is stable in calm and breaks in stress is a hedging assumption that "
     "fails exactly when it is needed. Detecting the break is both a risk signal and a trade, and "
     "it names the crowding the desk cannot otherwise see.",
     "Millennium and Balyasny both run centralised risk specifically to see cross-book factor and "
     "crowding exposure no single manager can."),
    ("lead_lag", ("Energy", "Soft Commodity", "Commodities"),
     "Physically linked instruments transmit information at different speeds: crude to products, "
     "energy input cost to agricultural production, base metals to industrial demand. The lag is "
     "a supply chain, which is why it is a mechanism and not a coincidence.",
     "Cross-asset lead-lag is a documented institutional research family across the multi-manager "
     "platforms."),
    ("liquidity_regime", ("Crypto", "Soft Commodity"),
     "Where spread and depth vary by an order of magnitude across the session, the cost of trading "
     "is itself predictable -- and a forecast is only tradeable where the edge survives the cost. "
     "These are the widest-spread instruments in the mandate, so the effect is largest here.",
     "XTX states that its fair-value models let it hold risk for meaningful periods rather than "
     "externalise every trade; cost and impact decide whether a forecast becomes a trade."),
    ("style_premia", ("Indices", "Commodities"),
     "Value, momentum, carry and defensive applied ACROSS a cross-section rather than to one "
     "instrument. The premia are public; the edge is in specification, neutralisation and cost, "
     "which is exactly what this desk's gauntlet measures.",
     "AQR publishes the factor set and states plainly that implementation, not the factor name, "
     "is where the remaining alpha sits."),
)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _universe_by_class() -> dict[str, list[str]]:
    """asset class -> symbols, read from the registry's own `asset_class` field."""
    uni = _read(UNIVERSE, {})
    out: dict[str, list[str]] = {}
    for sym, row in (uni or {}).items():
        cls = str((row or {}).get("asset_class") or "?")
        out.setdefault(cls, []).append(str(sym))
    return {k: sorted(v) for k, v in out.items()}


def _certified_symbols() -> set[str]:
    s = _read(SURVIVORS, {})
    return {str(((v or {}).get("shadow_spec") or {}).get("symbol", "")).upper()
            for v in (s.get("survivors") or {}).values() if v}


def _has_bars(sym: str) -> bool:
    return (BASE / "data" / "universe" / f"{sym}_H1.parquet").exists()


def build() -> dict[str, Any]:
    """One donation row per (mechanism, asset class), naming only instruments the desk can run.

    A CARD THAT NAMES AN INSTRUMENT WITHOUT BARS IS A WISH. Symbols are filtered to those with an
    H1 parquet already on disk, so every card is immediately buildable rather than a request for
    collection -- and measured 2026-09-14 all 58 uncertified symbols in the huntable classes
    already have them.
    """
    by_class = _universe_by_class()
    certd = _certified_symbols()
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for family, classes, note, source in CARDS:
        syms: list[str] = []
        for cls in classes:
            if cls not in HUNTABLE:
                continue
            syms.extend(x for x in by_class.get(cls, [])
                        if x.upper() not in certd and _has_bars(x))
        syms = sorted(set(syms))
        if not syms:
            skipped.append({"family": family, "classes": list(classes),
                            "why": "no uncertified symbol in these classes has H1 bars on disk"})
            continue
        rows.append({
            "kind": "hypothesis",
            "family": family,
            "symbols": syms,
            # THE GATE READS THIS. `economic_prior` refuses a cell whose mechanism_status is not
            # NAMED, which is what keeps statistical mining out of the certificate stock. The note
            # is the actual reason the effect should exist, and the source is where it is public.
            "mechanism_status": "NAMED",
            "mechanism_note": note,
            "mechanism": note,
            "title": f"{family} on {'/'.join(classes)} -- an axis with no certificate",
            "source": "institutional_mechanism",
            "producer": "institutional_cards.py",
            "public_source": source,
            "asset_classes": list(classes),
            "why_this_axis": ("all 58 of the desk's certificates are H1/asia and 27 of 28 "
                              "certificate symbols are FX; these classes hold zero certificates "
                              "while their bars are already collected"),
            "first_seen": datetime.now(UTC).isoformat(timespec="seconds"),
        })
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "authority": ("PROPOSES ONLY. Every card clears the same ten gates as anything else on "
                      "the docket; naming a public mechanism grants no evidence and no capital."),
        "n_cards": len(rows),
        "n_symbols": len(sorted({s for r in rows for s in r["symbols"]})),
        "by_family": {r["family"]: len(r["symbols"]) for r in rows},
        "skipped": skipped,
        "cards": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the cards into the institutional seat for the compiler to read")
    a = ap.parse_args(argv)
    doc = build()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"institutional cards: {doc['n_cards']} card(s) over {doc['n_symbols']} uncertified "
          f"symbol(s) with bars")
    for fam, n in doc["by_family"].items():
        print(f"    {fam:22} {n:3} symbol(s)")
    for s in doc["skipped"]:
        print(f"    skipped {s['family']}: {s['why']}")
    if a.apply:
        SEAT.mkdir(parents=True, exist_ok=True)
        out = SEAT / f"discoveries_{datetime.now(UTC):%Y%m%d}.json"
        out.write_text(json.dumps(doc["cards"], indent=1), encoding="utf-8")
        print(f"  donated -> {out}")
    else:
        print("  report only; re-run with --apply to donate them to the compiler")
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
