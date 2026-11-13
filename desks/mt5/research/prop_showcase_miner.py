"""PROP-FIRM PAYOUT SHOWCASES -> STRATEGY CLAIMS -> CHARGED GAUNTLET CELLS (2026-11-03).

THE ASK (principal 2026-10-30, BACKLOG row 38): reverse-engineer the top public payout earners
and payout leaderboards of FTMO, Topstep and the famous MT5 prop firms worldwide into gauntlet
cells, as an extension of the absurd-return reverse-engineering miner or beside it, whichever
gives the most focus and ROI -- and make sure the producer actually produces cells.

WHAT THE PUBLIC GROUND ACTUALLY HOLDS (surveyed 2026-11-03, written down so nobody re-surveys it):
  * Payout LEADERBOARDS carry no mechanism. FXIFY shows a masked name, a country and an amount;
    The5ers shows first name + initial + amount; FTMO's leaderboard rows load client-side and the
    served HTML has none; fundedtrading.com publishes firm-wallet totals and says it never shows
    traders. A name and a dollar figure cannot be turned into fills -- doing so would be
    fabrication, the thing provider_reverse refuses (book_forensics header, the HTML-blob rule).
  * The MECHANISM lives in the firms' own published trader stories and interviews (FTMO blog
    "Successful Traders Stories" / "Top Traders: Strategies", e.g. "how a gold scalper secured
    $50,333 in 2 weeks"; The5ers, FundedNext, Topstep, E8, FXIFY spotlights). Those state the
    instrument, the session, the style, the R:R and the holding period in prose.
  * Firms publish SELECTION base rates. Topstep's 2025 disclosure: 16.8% of Combines completed,
    51.8% of individuals reached Funded at least once, 33.3% of Funded participants received a
    payout, 0.71% of Express participants called to Live. That is the survivorship of the ground:
    a showcase is drawn from the top tail of a population that mostly failed.

SO THIS IS SEPARATE FROM THE GENOME, ON PURPOSE. The trader genome (book_forensics) measures
style base rates over alive + dead statements; a story corpus has no dead rows, so feeding it to
those base rates would print survivor-only rates as population ones. Here a story is an IDEA
SOURCE (the 10-13 ruling: idea provenance never blocks a cell; method is what is audited), and
the cells go through the SAME door the genome uses: proposer_common.screen -> deflate -> donate,
with every look charged (alt_proxies._donate, null passes into null_pass_trials.jsonl).

PIPELINE, each stage counted so conversion is visible (PROP_SHOWCASE.json `funnel`):
  harvest   firm sitemaps (robots.txt Sitemap lines, else /sitemap.xml) -> story-slug URLs ->
            polite fetch (robots consulted, unreadable robots = NOT fetched, 3 s spacing, a cap
            per firm per pass, no login, no cookies, no paywall/CAPTCHA/rate-limit crossing) ->
            raw text vaulted under data/intelligence/prop_showcase/ (gitignored; never in the
            public repo -- only the structured claims and the URL leave the box).
  extract   deterministic lexicon: instruments, sessions, styles, stated R:R, holding horizon,
            stated payout. No LLM seat sees the text (cheap, reproducible, auditable).
  cells     (style, session) -> registered family + a SMALL preregistered grid; instruments
            mapped to the desk's MT5 symbols (futures stories -> the CFD on the same underlying).
            Support = distinct stories backing one cell; cells ranked by support.
  screen    pc.screen on the desk's own H1 bars at the fill-hour cost; deflated over every look
            the pass ran (variants included). Proposals donated; nulls charged.

SESSION HOURS ARE BROKER STAMP HOURS (NY+7, the desk's clock; families read stamp hours, see
families._h1). On NY+7 the London and New York opens are fixed stamps year-round (London 08:00
= stamp 10, NY 09:30 = stamp 16:30 -> 16), except the 2-3 weeks a year the US and UK DST dates
differ. Tokyo 09:00 JST = 00:00 UTC = stamp 02 (US winter, EST) / 03 (US summer, EDT); the Asia
window is screened ending at 07 and at 08 (both rows of SESSIONS['asia']).

IT PROPOSES, IT NEVER PROMOTES. Nothing here writes a sleeve, certificate, clock or book.
Yield to certificates, forward enrolment and promotable sleeves is measured downstream by
productivity_census (source `prop_showcase_story`), and this report copies that row back so the
producer sees its own conversion every pass.

    python desks/mt5/research/prop_showcase_miner.py [--apply] [--no-fetch]

CODE LAYOUT: the lexicon and claim->cell mapping are in prop_showcase_lexicon.py, the polite
fetcher and harvest in prop_showcase_fetch.py; this file screens, charges and reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:                # the two halves live beside this file
    sys.path.insert(0, _HERE)

import prop_showcase_fetch as _fetch  # noqa: E402
from prop_showcase_fetch import (  # noqa: E402, F401
    FIRMS,
    SOURCE,
    _Fetcher,
    _story_urls,
    _write_atomic,
    harvest,
    load_claims,
)
from prop_showcase_lexicon import (  # noqa: E402, F401
    INSTRUMENTS,
    SESSIONS,
    STYLES,
    _grid,
    cells,
    extract,
)

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
INTEL = _fetch.INTEL
#: cell -> bar count it was last screened on (box-local state, charge-once ledger).
SCREENED = INTEL / "screened.json"
REPORT = DESK / "reports" / "PROP_SHOWCASE.json"
PRODUCER_YIELD = DESK / "reports" / "PRODUCER_YIELD.json"
PRODUCTIVITY_CENSUS = DESK / "reports" / "PRODUCTIVITY_CENSUS.json"
NULL_TRIALS = DESK / "data" / "null_pass_trials.jsonl"
MIN_BARS = 3000
#: Cells screened per pass at most (the budget is also wall-clock bounded).
MAX_CELLS = 120
#: New H1 bars (~1 month) before a screened cell may be screened (and charged) again.
RESCREEN_BARS = 500

#: Firm-published selection base rates (stamped on every candidate; never a gate).
SELECTION_PRIORS: dict[str, Any] = {
    "topstep_2025": {
        "url": "https://www.topstep.com/",
        "read_utc": "2026-11-03",
        "combines_completed": 0.168, "reached_funded_once": 0.518,
        "funded_received_payout": 0.333, "express_called_to_live": 0.0071,
        "quote": ("33.3% of all individual participants at the Funded Level received a "
                  "payout")},
    "rule": ("a showcase is the top tail of a population that mostly failed; the story is a "
             "hypothesis source, the gauntlet and the forward lane are the evidence"),
}


# ------------------------------------------------------------------------------- screen + donate
def _family_fn(name: str) -> Any:
    try:
        from mt5desk import families
    except ImportError:
        return None
    fn = getattr(families, f"family_{name}", None)
    return fn if callable(fn) else None


def propose(claims: list[dict[str, Any]], budget_s: float = 1200.0,
            write: bool = True) -> dict[str, Any]:
    from research import proposer_common as pc
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        # FAIL CLOSED: without the universe policy no symbol may be hypothesised.
        def may_hypothesise(_s: str) -> bool:                   # type: ignore[misc]
            return False
    started = time.monotonic()
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    allc = cells(claims, {s for s in have if may_hypothesise(s)})
    screened: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}

    def skip(why: str) -> None:
        skipped[why] = skipped.get(why, 0) + 1

    bars_cache: dict[str, Any] = {}
    ledger = _load_screened()
    attempted = 0
    for c in allc:
        if attempted >= MAX_CELLS:
            skip("over the per-pass cell cap (next pass)")
            continue
        if time.monotonic() - started > budget_s:
            skip("budget exhausted")
            continue
        fn = _family_fn(c["family"])
        if fn is None:
            skip(f"family {c['family']} not registered")
            continue
        sym = c["symbol"]
        if sym not in bars_cache:
            bars_cache[sym] = pc.bars(sym)
        d = bars_cache[sym]
        if d is None or len(d) < MIN_BARS:
            skip("too few H1 bars")
            continue
        # CHARGED ONCE PER NEW-BAR WINDOW: the same claim on the same bars is the same look, so
        # a daily pass re-screens a cell only after RESCREEN_BARS new bars have arrived.
        lkey = json.dumps([sym, c["family"], c["params"]], sort_keys=True)
        if len(d) - int(ledger.get(lkey, -10**9)) < RESCREEN_BARS:
            skip("already screened on these bars")
            continue
        attempted += 1
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skip("no contract terms to price the round trip")
            continue
        try:
            sig = fn(d, **c["params"])
        except Exception as exc:
            skip(f"family raised {type(exc).__name__}")
            continue
        sc = pc.screen(d, sig or [], cost, pc.artifact_hours(d)) if sig else None
        body = dict(sc) if sc else {"n_independent": 0, "gross_per_trade": 0.0,
                                     "t_gross": 0.0, "clears_cost": False,
                                     "net_per_trade": round(-cost, 8),
                                     "cost_frac": round(cost, 8)}
        body["t_gross"] = float(body.get("t_gross") or 0.0)
        pid = hashlib.sha256(json.dumps(c["params"], sort_keys=True).encode()).hexdigest()[:8]
        # The cell is (symbol, family): best_per_cell then keeps ONE variant per cell, so
        # shipping every params variant of one winner never smuggles the search back in.
        screened.append({"cell": f"{sym}.{c['family']}.showcase", "variant": pid, **c, **body,
                         "screened": bool(sc), "_lkey": lkey, "_nbars": len(d)})
    swept = pc.deflate(screened)
    proposals = pc.best_per_cell(swept)
    cands = []
    for r in proposals:
        cands.append(pc.candidate(
            SOURCE, r["symbol"], r["family"], dict(r["params"]),
            mechanism=(f"prop-firm payout showcase: {'/'.join(r['styles'])} "
                       f"{'/'.join(r['sessions']) or 'any-session'} on {r['symbol']}, backed by "
                       f"{r['support']} published funded-trader stor(y/ies) across "
                       f"{len(r['firms'])} firm(s) ({', '.join(r['firms'])}); survivor-only "
                       f"ground, see selection_prior"),
            title=f"{r['cell']} from prop-firm payout showcases",
            evidence={**{k: r.get(k) for k in ("n_independent", "gross_per_trade",
                                              "net_per_trade", "cost_frac", "t_gross",
                                              "t_deflated_sweep", "n_tests_sweep",
                                              "t_deflated_lifetime", "n_tests_lifetime")},
                      "showcase_support": r["support"], "showcase_firms": r["firms"],
                      "showcase_stories": r["stories"], "selection_prior": SELECTION_PRIORS}))
    rep: dict[str, Any] = {"cells_built": len(allc), "tests_run": len(screened),
                           "cells_proposed": len(proposals), "skipped": skipped,
                           "top_cells": [{k: r.get(k) for k in (
                               "cell", "support", "firms", "styles", "sessions",
                               "n_independent", "t_gross", "t_deflated_sweep")}
                               for r in swept[:25]]}
    if write and screened:
        from research import alt_proxies as ap
        paths = ap.Paths(NULL_TRIALS.parent.parent)
        by_family: dict[str, int] = {}
        for r in screened:
            by_family[str(r["family"])] = by_family.get(str(r["family"]), 0) + 1
        rep["charge"] = ap._donate(paths, SOURCE, cands, len(screened), by_family,
                                   datetime.now(tz=UTC))
        for r in screened:
            ledger[r["_lkey"]] = r["_nbars"]
        _write_atomic(SCREENED, json.dumps(ledger, indent=0, sort_keys=True))
    return rep


def _load_screened() -> dict[str, int]:
    try:
        doc = json.loads(SCREENED.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _own_yield() -> dict[str, Any]:
    """This producer's conversion, copied back from the census every pass: the PRODUCER_YIELD
    verdict (PRODUCING / STARVED / DEAD) and every PRODUCTIVITY_CENSUS number keyed to it
    (certificates, forward, live -- the census attributes by lineage, never by guesswork)."""
    out: dict[str, Any] = {}
    try:
        doc = json.loads(PRODUCER_YIELD.read_text("utf-8"))
        rows = [r for r in doc.get("producers") or []
                if isinstance(r, dict) and "prop_showcase" in str(r.get("producer", ""))]
        out["producer_yield"] = rows[0] if rows else "not yet in the census (first passes)"
    except (OSError, ValueError):
        out["producer_yield"] = "UNMEASURED: PRODUCER_YIELD.json unreadable"
    found: dict[str, Any] = {}

    def walk(o: Any, path: str, depth: int) -> None:
        if depth > 4 or not isinstance(o, dict):
            return
        for k, v in o.items():
            if "prop_showcase" in str(k):
                found[f"{path}/{k}".lstrip("/")] = v
            else:
                walk(v, f"{path}/{k}", depth + 1)
    try:
        walk(json.loads(PRODUCTIVITY_CENSUS.read_text("utf-8")), "", 0)
        out["census"] = found or "no certificate/forward/live row attributed yet"
    except (OSError, ValueError):
        out["census"] = "UNMEASURED: PRODUCTIVITY_CENSUS.json unreadable"
    return out


def run(budget_s: float = 1800.0, write: bool = True, fetch: bool = True) -> dict[str, Any]:
    """The daily clock: harvest new stories, then screen and donate the claim cells."""
    for p in (str(DESK), str(DESK / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    t0 = time.monotonic()
    h = harvest(budget_s=budget_s * 0.4) if fetch else {"skipped": "--no-fetch"}
    claims = load_claims()
    mech = [c for c in claims if c.get("styles") and c.get("instruments")]
    prop = propose(claims, budget_s=max(60.0, budget_s - (time.monotonic() - t0)),
                   write=write)
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "source": SOURCE,
           "harvest": h,
           "funnel": {"stories_held": len(claims), "stories_with_mechanism": len(mech),
                      "cells_built": prop["cells_built"], "cells_screened": prop["tests_run"],
                      "cells_proposed": prop["cells_proposed"],
                      "donated": (prop.get("charge") or {}).get("donated", 0)},
           "by_firm_claims": {f: sum(1 for c in mech if c["firm"] == f) for f in FIRMS},
           "proposer": prop, "yield": _own_yield(), "selection_prior": SELECTION_PRIORS,
           "rules": {"fetch": "public pages only; robots consulted, unreadable = not fetched; "
                              "walls (401/402/403/429) counted, never crossed; raw text stays "
                              "on the box",
                     "trials": "every screened cell is a look, deflated in-sweep and charged "
                               "to the lifetime count (donation or null_pass_trials)",
                     "promotes": "never"}}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        _write_atomic(REPORT, json.dumps(doc, indent=1, default=str))
    return {"tests_run": prop["tests_run"], "cells_proposed": prop["cells_proposed"],
            "stories": len(claims)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(run(write=a.apply, fetch=not a.no_fetch), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
