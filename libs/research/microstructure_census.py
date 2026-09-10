"""WHICH MICROSTRUCTURE CONSTRUCTIONS THIS DESK CAN ACTUALLY COMPUTE, and what blocks each one.

A microstructure score is worthless without the venue attached, because most of the vocabulary --
queue position, order-flow imbalance, microprice, iceberg inference, absorption, book convexity --
is defined ON A LIMIT ORDER BOOK, and whether the desk has one is a measured fact rather than an
engineering choice. This module publishes that fact per construction, so "our microstructure is
about 7/10" becomes a list with names on it.

THE MEASUREMENT THAT DECIDES HALF OF THIS FILE, and it is already in the repo:

    desks/mt5/data/tape/depth_probe.json, written 2026-08-17 by `mt5desk.tape.probe_depth`
    22 symbols probed, 22 subscribed, levels: 0 on every one, verdict NO_DEPTH
    "symbols_with_real_depth": []

Fusion publishes no depth of market. Not thin depth, not top-of-book only -- zero levels, on FX
majors, on gold, on silver, on both crypto CFDs. So every construction below whose input is
RESTING DEPTH is not "not built yet"; it is UNBUILDABLE_ON_VENUE, and the probe is the citation.
Building it anyway on a book synthesised from bid/ask -- one level per side at the quoted size --
would produce a model OF THE SYNTHESIS: imbalance would be a restatement of which side the broker
last moved, and queue position would be a constant. The probe's own note says this and it is kept.

WHAT THE VENUE DOES GIVE, and it is more than it sounds. `copy_ticks_from(COPY_TICKS_ALL)` returns
real quote revisions with millisecond stamps -- bid, ask, last, volume, and flags saying which
changed. Everything that depends on the ORDER and TIMING of quote revisions rather than on resting
size is therefore fully available: effective spread at a latency, realised spread, post-trade mid
drift (adverse selection), quote intensity and burstiness, staleness, the true intrabar path, and
the realised/bipower split of variation into diffusion and jump. That is the bulk of the value in
practice, because it is the half that changes what an order does.

THE FOUR VERDICTS, and the distinction between them is the entire point:

    LIVE                 the construction runs on a clock and leaves an artifact
    STARVED              the code exists and the venue supports it -- nothing runs it, or its
                         input never reaches the box that would read it. FIXABLE HERE, TODAY.
    UNBUILDABLE_ON_VENUE the data does not exist at this broker and no amount of work creates it
    NEEDS_EXTERNAL_FEED  buildable, but the input is another venue's tape and must be acquired

Collapsing STARVED into UNBUILDABLE is how a desk stops working on the half it could fix; the
reverse is how it spends a quarter building a model of a synthesis. Both errors are expensive and
they point in opposite directions, so the census refuses to average them into a score.

NOTHING HERE COMPUTES A MICROSTRUCTURE STATISTIC. It reads the repo and reports what could be
computed. The constructions themselves live in `mt5desk/microstructure.py` (tick-only),
`mt5desk/markout.py` (intent versus fill), `libs/research/orderbook_state.py` and
`libs/research/book_microstructure.py` (depth, venue-neutral, currently unfed).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: The probe that decides every depth verdict. Written by `mt5desk.tape.probe_depth` ON THE BOX,
#: because only a machine with a live MetaTrader terminal can call `MarketBookGet`.
DEPTH_PROBE_REL = "desks/mt5/data/tape/depth_probe.json"

#: Where the census lands.
OUT_REL = "desks/mt5/reports/MICROSTRUCTURE.json"

LIVE = "LIVE"
STARVED = "STARVED"
UNBUILDABLE = "UNBUILDABLE_ON_VENUE"
EXTERNAL = "NEEDS_EXTERNAL_FEED"
VERDICTS = (LIVE, STARVED, UNBUILDABLE, EXTERNAL)

#: Inputs a construction can require. Each maps to a probe in `_have`.
TICKS = "tick_tape"                  # ts, bid, ask, last, volume, flags -- from COPY_TICKS_ALL
DEPTH = "resting_depth"              # more than one level per side. MEASURED ABSENT at Fusion.
FILLS = "own_fills"                  # the desk's own deals joined to the intents that asked
FUTURES = "external_futures_tape"    # CME/COMEX prints, for the lead-lag leg
BROKERS = "second_broker_quotes"     # a second venue's quote stream, for venue choice


@dataclass(frozen=True)
class Construction:
    """One named microstructure quantity, its input, and where it is computed."""

    key: str
    title: str
    needs: tuple[str, ...]
    module: str
    #: What a decision does with it. A construction nothing acts on is a report, and is labelled
    #: as one -- `changes` is the sentence that has to be true for the work to be worth doing.
    changes: str
    #: Artifact whose existence proves it ran, relative to the repo root. "" = no artifact yet.
    artifact: str = ""


#: THE CONSTRUCTIONS, grouped by what they need. Order within a group is by how much a decision
#: would change if the number existed, most first.
CONSTRUCTIONS: tuple[Construction, ...] = (
    # ---- tick tape only: no book required, and this is where the value actually is -----------
    Construction(
        "effective_spread_at_latency", "what a market order costs at the latency it really has",
        (TICKS,), "mt5desk/microstructure.py:effective_spread_pts",
        "the affordability gate: a cell whose edge is smaller than its executable cost is not "
        "admitted. The bar surface charges the spread STAMPED on the bar, which is not the "
        "spread at the instant the desk would have traded",
        "desks/mt5/data/cost_surface_tick.json"),
    Construction(
        "post_fill_mid_drift", "how far the mid moves against a fill in the seconds after it",
        (TICKS,), "mt5desk/microstructure.py:mid_move_pts",
        "separates a spread that is a FEE from a spread that is a WARNING. A wide quote the mid "
        "immediately runs through was not expensive liquidity, it was a signal to wait",
        ""),
    Construction(
        "realised_spread", "what the liquidity provider keeps once the mid has moved",
        (TICKS,), "mt5desk/microstructure.py:realised_spread_pts",
        "prices the desk's own toxicity to its broker, which is what a dealing desk widens on",
        ""),
    Construction(
        "intrabar_path", "whether the high came before the low, inside each bar",
        (TICKS,), "mt5desk/microstructure.py:intrabar_path",
        "decides which of a stop and a target was hit on the bars where BOTH were touched -- the "
        "bars that decide the backtest. Every result on this desk currently assumes an order",
        ""),
    Construction(
        "realised_vs_bipower", "how much of a bar's travel was diffusion and how much was a jump",
        (TICKS,), "mt5desk/microstructure.py:realized_variation",
        "a stop sized off total variation survives a smooth drift and is taken out by one release "
        "print; the split says which regime the sizing is being asked to survive",
        ""),
    Construction(
        "quote_intensity_burstiness", "whether quote updates arrived evenly or in bursts",
        (TICKS,), "mt5desk/microstructure.py:burstiness",
        "a breakout into a burst is a different trade from the same breakout into a drip, and "
        "tick_volume cannot tell them apart",
        ""),
    Construction(
        "stale_quote_fraction", "how much of the session the feed was not moving at all",
        (TICKS,), "mt5desk/microstructure.py:stale_fraction",
        "an hour that looks tradeable on bars and is a frozen quote in fact",
        ""),
    Construction(
        "latency_slippage_curve", "expected slip as a function of decision-to-fill delay",
        (TICKS,), "recorders/tape_features.py",
        "the execution twin's prior. A desk with few fills has almost no data to fit on and "
        "millions of ticks, and this curve needs no fill at all",
        "desks/mt5/data/tape/slippage_surface.json"),
    Construction(
        "order_flow_imbalance_proxy", "the sign asymmetry of quote revisions (NOT true flow)",
        (TICKS,), "mt5desk/microstructure.py:order_flow_imbalance",
        "feeds the `orderflow_imbalance` family. Carries a `basis` field saying it used revision "
        "signs and not aggressor side, because a retail CFD tape has neither",
        ""),

    # ---- the desk's own fills ---------------------------------------------------------------
    Construction(
        "entry_slippage", "what was asked for versus what was got, signed and in R",
        (FILLS,), "mt5desk/markout.py:compute",
        "the only honest measure of execution. A 0.10R average slip is 63% of the gold book's "
        "measured +0.159R edge",
        "desks/mt5/reports/markout.json"),
    Construction(
        "fill_markout_curve", "the mid's path after each of the desk's own fills, at a ladder",
        (TICKS, FILLS), "libs/research/fill_markout.py",
        "toxicity per sleeve, per hour, per order type: which of the desk's own orders are being "
        "adversely selected, and therefore which should be limit rather than market, or later",
        ""),
    Construction(
        "fill_probability", "how often a resting order at a given offset actually trades",
        (FILLS,), "mt5desk/fill_surface.py",
        "makes limit entry a costed choice rather than a hope. Falls back to 'half the spread, "
        "wide' until 30 fills exist",
        ""),

    # ---- resting depth: MEASURED ABSENT at this venue ----------------------------------------
    Construction(
        "queue_position", "where in the queue a resting order sits, and its depletion",
        (DEPTH,), "libs/research/orderbook_state.py",
        "would decide passive fill timing -- if a queue existed to sit in",
        ""),
    Construction(
        "order_flow_imbalance_true", "resting size asymmetry across levels",
        (DEPTH,), "libs/research/book_microstructure.py:features",
        "the real version of the proxy above",
        ""),
    Construction(
        "microprice", "the size-weighted mid, Cont-Kyle-Stoikov",
        (DEPTH,), "libs/research/book_microstructure.py:features",
        "where the next mid is likelier to go. Degrades to the plain mid with no sizes, and the "
        "code says `mid_fallback` rather than inventing one",
        ""),
    Construction(
        "depth_curve_convexity", "how fast liquidity thins away from the touch",
        (DEPTH,), "libs/research/orderbook_state.py:_side_slope",
        "how far a given size walks the book",
        ""),
    Construction(
        "absorption_vs_fragile_display", "whether displayed size is real or vanishes when hit",
        (DEPTH,), "libs/research/orderbook_state.py:withdrawal_asymmetry",
        "constitution section 222. The probe's note names this one as not buildable here",
        ""),
    Construction(
        "iceberg_inference", "hidden size revealed by repeated fills at one level",
        (DEPTH, TICKS), "libs/research/book_microstructure.py",
        "needs fills joined to a resting level, and there are no levels",
        ""),
    Construction(
        "cancel_replenish_hazard", "how quickly pulled depth comes back",
        (DEPTH,), "libs/research/orderbook_state.py",
        "needs order-level adds and cancels; two identical snapshots are consistent with no "
        "activity and with a thousand adds matched by a thousand cancels",
        ""),

    # ---- other venues ------------------------------------------------------------------------
    Construction(
        "futures_cfd_lead_lag", "whether COMEX gold prints move before the XAUUSD CFD quote",
        (FUTURES,), "libs/research/information_flow.py",
        "the highest-value external feed for this book: gold is the desk's largest sleeve and its "
        "price is made on a venue the desk can see but does not trade",
        ""),
    Construction(
        "venue_quote_comparison", "which broker quotes tighter, when",
        (BROKERS,), "libs/data/venue_http.py",
        "venue choice, and a second opinion on whether a wide quote was the market or the dealer",
        ""),
)


@dataclass
class Reading:
    construction: Construction
    verdict: str
    blocker: str
    fixable_here: bool
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        c = self.construction
        return {"key": c.key, "title": c.title, "needs": list(c.needs), "module": c.module,
                "changes": c.changes, "artifact": c.artifact, "verdict": self.verdict,
                "blocker": self.blocker, "fixable_here": self.fixable_here,
                "evidence": self.evidence}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _ignored(root: Path, rel: str) -> bool:
    """Would git carry this path if it existed? Decided by `git check-ignore`, never by guessing."""
    import subprocess
    try:
        r = subprocess.run(["git", "check-ignore", "-q", "--", rel],
                           cwd=root, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return True                       # unknown is treated as ignored: it proves nothing
    return r.returncode == 0


def artifact_state(root: Path, rel: str) -> dict[str, Any]:
    """Present, or absent -- and on a TWO-MACHINE desk those are three states, not two.

    THE DISTINCTION THIS EXISTS FOR. The trading box produces most microstructure artifacts,
    because only a machine with a live MetaTrader terminal has a tape. A research checkout
    therefore sees an absent file whether the box has never produced it or has produced it
    perfectly and simply not shared it -- and those demand opposite work.

    Git settles it. `desks/mt5/data/` is one of `libs.ops.release.STATE_PREFIXES`, so the box
    COMMITS AND PUSHES what it writes there. An absent path under that prefix that is NOT
    gitignored has therefore never been produced ON ANY MACHINE: had the box ever written it, the
    next adopt-and-push would have carried it here. An absent path that IS gitignored says
    nothing at all, and this reports UNKNOWN_BOX_LOCAL rather than inventing a verdict.
    """
    if not rel:
        return {"state": "NONE", "path": "", "why": "the construction declares no artifact"}
    p = root / Path(*rel.split("/"))
    if p.exists():
        return {"state": "PRESENT", "path": rel, "bytes": p.stat().st_size,
                "why": "the artifact is here"}
    if _ignored(root, rel):
        return {"state": "UNKNOWN_BOX_LOCAL", "path": rel,
                "why": ("gitignored, so its absence here is not evidence: the box may hold it. "
                        "Read it on the box or publish a fold of it")}
    return {"state": "NEVER_PRODUCED", "path": rel,
            "why": ("absent, not gitignored, under a STATE_PREFIX the box commits and pushes -- "
                    "so had any machine ever written it, the next adopt would have carried it "
                    "here. This is not a sharing gap, it is a producer that has never run")}


def depth_verdict(root: Path) -> dict[str, Any]:
    """What the venue publishes as resting depth, from the probe rather than from belief.

    NO PROBE IS NOT NO DEPTH. An absent probe means nobody has asked the terminal, which is a
    different state from having asked and been told zero -- and only the second one justifies
    abandoning a whole class of constructions. So an absent probe reads UNMEASURED and every
    depth construction reads STARVED (run the probe) rather than UNBUILDABLE.
    """
    doc = _read(root / Path(*DEPTH_PROBE_REL.split("/")))
    if not doc:
        return {"state": "UNMEASURED", "n_symbols": 0, "with_depth": [],
                "why": "no depth probe has been run; nobody has asked the terminal"}
    symbols = doc.get("symbols") or {}
    with_depth = list(doc.get("symbols_with_real_depth") or [])
    return {
        "state": "HAS_DEPTH" if with_depth else "NO_DEPTH",
        "n_symbols": len(symbols),
        "with_depth": with_depth,
        "probed_at": doc.get("at", ""),
        "why": (f"{len(symbols)} symbols probed, {len(with_depth)} publish more than one level "
                "per side. A book synthesised from bid/ask would model the synthesis"),
    }


def _have(root: Path) -> dict[str, dict[str, Any]]:
    """One probe per input class. Each returns present/absent WITH the path that decided it."""
    ticks = root / "desks" / "mt5" / "data" / "tape" / "ticks"
    tick_syms = sorted(p.name for p in ticks.iterdir()) if ticks.is_dir() else []

    deals = root / "desks" / "mt5" / "data" / "deals.jsonl"
    intents = root / "desks" / "mt5" / "data" / "intents.jsonl"

    depth = depth_verdict(root)
    return {
        TICKS: {"present": bool(tick_syms), "n_symbols": len(tick_syms),
                "path": "desks/mt5/data/tape/ticks/",
                "why": ("recorded ON THE BOX by the hourly `record_tape` leg; this tree is a "
                        "research checkout and does not carry the parquet")},
        DEPTH: {"present": depth["state"] == "HAS_DEPTH",
                "unmeasured": depth["state"] == "UNMEASURED",
                "path": DEPTH_PROBE_REL, **depth},
        FILLS: {"present": deals.exists() and intents.exists(),
                "path": "desks/mt5/data/{intents,deals}.jsonl",
                "why": ("an intent with no matching deal is an UNFILLED bracket, never a "
                        "zero-slip fill")},
        FUTURES: {"present": False, "path": "(none)",
                  "why": "no futures tape is acquired; this is a purchase, not a wiring task"},
        BROKERS: {"present": False, "path": "libs/data/venue_http.py",
                  "why": "the second-venue reader exists and nothing feeds or calls it"},
    }


def readings(root: Path) -> list[Reading]:
    """A verdict per construction, with the blocker named."""
    have = _have(root)
    out: list[Reading] = []
    for c in CONSTRUCTIONS:
        missing = [n for n in c.needs if not have[n]["present"]]
        art = artifact_state(root, c.artifact)
        artifact_ok = art["state"] == "PRESENT"

        if not missing and artifact_ok:
            verdict, blocker, fixable = LIVE, "", False
        elif art["state"] == "NEVER_PRODUCED":
            # THE STRONGEST FINDING AVAILABLE FROM A RESEARCH CHECKOUT, and it outranks a missing
            # input: the producer has never run on ANY machine, so wiring it is the work whether
            # or not this particular tree can see the tape.
            verdict = STARVED
            blocker = f"{c.artifact} has never been produced on any machine -- {art['why']}"
            fixable = True
        elif DEPTH in missing and not have[DEPTH].get("unmeasured"):
            verdict = UNBUILDABLE
            blocker = ("the venue publishes no resting depth: "
                       + str(have[DEPTH].get("why", "")))
            fixable = False
        elif FUTURES in missing or BROKERS in missing:
            verdict = EXTERNAL
            blocker = str(have[FUTURES if FUTURES in missing else BROKERS]["why"])
            fixable = False
        elif missing:
            verdict = STARVED
            blocker = "input absent: " + ", ".join(f"{n} ({have[n]['path']})" for n in missing)
            fixable = True
        else:
            verdict = STARVED
            blocker = (f"the input is present and nothing produces {c.artifact}"
                       if c.artifact else
                       "the input is present and no clock computes this")
            fixable = True

        out.append(Reading(c, verdict, blocker, fixable,
                           evidence={"inputs": {n: have[n] for n in c.needs},
                                     "artifact": art}))
    return out


def census(root: Path | None = None) -> dict[str, Any]:
    """The picture, and the only two numbers worth reading off it."""
    root = Path(root or _ROOT)
    rows = readings(root)
    by = {v: [r.construction.key for r in rows if r.verdict == v] for v in VERDICTS}
    reachable = [r for r in rows if r.verdict != UNBUILDABLE]
    fixable = [r for r in rows if r.fixable_here]

    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "n_constructions": len(rows),
        "by_verdict": {v: len(by[v]) for v in VERDICTS},
        "verdicts": by,
        "venue_depth": depth_verdict(root),
        "inputs": _have(root),
        # THE HEADLINE, and it is deliberately a fraction of the REACHABLE set. Scoring against
        # every construction ever named would charge this desk for a limit order book its broker
        # does not have, which is not a gap it can close and not a number it can act on.
        "live_of_reachable": (round(len(by[LIVE]) / len(reachable), 3) if reachable else None),
        # THE NUMBER THAT IS A WORK-LIST. Everything here is blocked by a missing clock or a
        # missing hop, not by the market.
        "fixable_here": [r.construction.key for r in fixable],
        "n_fixable_here": len(fixable),
        "constructions": [r.to_dict() for r in rows],
        "rule": (
            "STARVED and UNBUILDABLE_ON_VENUE are never averaged together. Collapsing the first "
            "into the second is how a desk stops working on the half it could fix today; the "
            "reverse is how it spends a quarter building a model of a synthesised book. The "
            "headline scores LIVE against REACHABLE, so a venue with no order book costs this "
            "desk nothing it could have earned"),
    }


def render(doc: dict[str, Any]) -> str:
    lines = [
        f"MICROSTRUCTURE  {doc['by_verdict'][LIVE]} live of "
        f"{doc['n_constructions'] - doc['by_verdict'][UNBUILDABLE]} reachable "
        f"({doc['live_of_reachable']})   {doc['n_fixable_here']} fixable here",
        f"  venue depth: {doc['venue_depth']['state']} -- {doc['venue_depth']['why']}",
    ]
    for v in VERDICTS:
        keys = doc["verdicts"][v]
        if keys:
            lines.append(f"  {v:22s} {len(keys):2d}  {', '.join(keys)}")
    lines.append("  BLOCKED HERE (a clock or a hop, not the market):")
    for row in doc["constructions"]:
        if row["fixable_here"]:
            lines.append(f"    {row['key']:32s} {row['blocker']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="which microstructure constructions this desk can compute")
    ap.add_argument("--root", default=str(_ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = census(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
