#!/usr/bin/env python3
"""STRATEGY-FAMILY COVERAGE (R0200) -- what KINDS of edge has the desk hunted, and what has it
never looked at once.

PRINCIPAL ORDER (2026-07-31): *"miners n explorers kimi etc all should find every ... strat
even discretionary n all n never limit to just one thing"* + *"discretionary section can copy
discretionary findings to self improve"*. The order's SUBJECT was narrowed by the universe
mandate (2026-08-18) from crypto to the MT5/Fusion book; its INSTRUCTION -- never limit to just
one thing -- is unchanged and is what this organ enforces. See the FAMILIES map for what that
narrowing removed and what it repointed.

THE GAP THIS CLOSES, and it is a whole axis the desk was blind on. Every existing coverage organ
maps WHERE the miners look -- source families, regions, languages (prospector_coverage.md tracks
9 source families across 7 regional seats). NOTHING maps WHAT KIND OF EDGE they come back with.
So the desk could report healthy source coverage while every card it ever carded came from three
mechanism families, and no organ could see it. 42 strategies are buried in the graveyard; they
cluster, and until now nobody counted the clusters.

WHY THE CLUSTER COUNT IS THE POINT. A miner that has tested twelve cross-sectional factors and
zero execution-microstructure mechanisms has not covered the space, it has covered ONE family
twelve times -- and the twelve are correlated by construction, so they die together and the
desk learns roughly one thing. Coverage is the count of DISTINCT FAMILIES touched, never the
count of candidates tested, and the two diverge exactly when a miner gets comfortable.

THE FAMILIES are enumerated below from the desk's own record -- every one is either present in
docs/graveyard.md, in the recommendation ledger, or named here as NEVER-HUNTED, which is the
output that earns this organ its place. UNHUNTED is a finding, not an omission.

THE DISCRETIONARY IMPORT, and the rule that keeps it safe. Families adjacent to the conviction
sleeve's own method (trend/structure, breakout, level-reaction, positioning-extreme) are routed
to the sleeve as PROVISIONAL playbook candidates -- never SUPPORTED. An outside finding may
SUGGEST a method change; only the sleeve's own closed trades may AUTHORISE one. That asymmetry
is the whole safety property: run_trade_review requires N_SUPPORT=3 of the desk's OWN
confirmations before a lesson reaches the trading brief, and an imported claim that could skip
that queue would let a miner's untested assertion silently rewrite the money path. So imports
enter the queue at the back, marked with their origin, and earn promotion the same way
everything else does.

    python scripts/run_strategy_coverage.py [--json] [--import-discretionary]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/strategy_coverage.json"
_PLAYBOOK = "data/trading_playbook.json"

#: Minimum distinct candidates in a family before its coverage counts as real. 3 because one
#: test is an anecdote and two is a coincidence: a family "covered" by a single dead candidate
#: is the exact self-report this organ exists to refuse.
THIN_BELOW = 3

#: THE FAMILY MAP. Each: (matcher patterns against graveyard/ledger names, discretionary-adjacent,
#: what the family actually claims). Adjacency marks families whose mechanism the CONVICTION
#: sleeve could act on -- those are the ones whose findings route to its playbook.
#
# REPOINTED ONTO THE MT5 UNIVERSE, 2026-09-05 (principal's standing order 2026-08-18). This map is
# a SCORING VOCABULARY, and the mandate names scoring vocabulary explicitly: no vocabulary may
# target crypto-exchange-native opportunities. Three families were deleted outright because they
# have no MT5 instrument behind them at all --
#
#   CROSS-VENUE-PREMIUM  kimchi / bithumb / coinone / coinbase cross-exchange premium. The desk
#                        trades ONE broker; there is no second venue to lead the first.
#   COPY-TRADER-SKILL    Hyperliquid leaderboards and elite-account mirroring. A crypto-exchange
#                        product, not an instrument.
#   ONCHAIN-FLOW         exchange netflow, stablecoin supply, mint/burn, TVL. Settlement-layer
#                        data for a settlement layer no MT5 symbol sits on.
#
# and four were repointed at their real MT5 analogue rather than deleted, because the MECHANISM is
# venue-neutral and only the instrument was crypto: CARRY-FUNDING (perp funding -> broker swap /
# rollover / futures term structure), ORDER-FLOW-POSITIONING (exchange OI-and-long/short ratios ->
# COT/CFTC reported positioning), EVENT-AND-CALENDAR (token unlocks and exchange listings ->
# releases, NFP/CPI/FOMC, earnings), LEAD-LAG (BTC leading alts -> DXY/yields/gold leading FX).
#
# WHAT THIS DOES TO THE BREADTH FENCE, said out loud rather than discovered later. Three of the
# eight families that read HUNTED were hunted ONLY on the retired universe, and the repointed rows
# lose the crypto-native candidates that used to match them, so measured coverage falls from 8/14
# to 4/11 and check_strategy_breadth.py now reports NARROW where it reported OK. It still EXITS 0
# -- NARROW is a finding about where to dig next, not a breach -- and the finding it prints is the
# right one: the next dig belongs in ORDER-FLOW-POSITIONING, i.e. the COT positioning this desk
# can actually read. That is the correct reading, not a regression: an MT5 desk claiming breadth on
# the strength of kimchi premium, copy-trading leaderboards and on-chain netflow is claiming
# coverage of a map it no longer trades. The floor (MIN_HUNTED_FRACTION) is NOT moved to absorb
# this, and no family is invented to pad the denominator back.
FAMILIES: dict[str, dict[str, Any]] = {
    "CARRY-FUNDING": {
        # "funding" stays as a matcher: it is how the desk's own record NAMES this family, and the
        # MT5 financing leg (swap, rollover, term structure) is the same mechanism priced by a
        # different counterparty. "premium_arb" went with CROSS-VENUE-PREMIUM.
        "patterns": ("funding", "carry", "basis", "swap_rate", "rollover", "term_structure",
                     "rate_differential"),
        "discretionary": False,
        "claim": "the financing leg -- broker swap/rollover, futures term structure -- is "
                 "harvestable after costs"},
    "CROSS-SECTIONAL-FACTOR": {
        "patterns": ("xsec", "lowvol", "size_and_volume", "illiquidity", "reversal", "breadth"),
        "discretionary": False,
        "claim": "rank the universe on a characteristic and go long/short the tails"},
    "TREND-AND-STRUCTURE": {
        "patterns": ("trend", "breakout", "trailbreak", "atrexit", "kama", "squeeze",
                     "ta_indicator", "momentum"),
        "discretionary": True,
        "claim": "price structure persists -- the conviction sleeve's OWN family"},
    "ORDER-FLOW-POSITIONING": {
        # The venue-neutral half of the old row is kept ("order_flow", "positioning"); the
        # exchange-native half (OI/long-short ratios, elite accounts, liquidation cascades,
        # smart-vs-dumb money feeds) is replaced by the reported positioning this desk can
        # actually read -- CFTC Commitments of Traders, which scripts/fetch_cot.py already
        # collects and scripts/screen_cot_positioning.py already screens.
        "patterns": ("order_flow", "positioning", "cot", "commitments", "net_long", "net_short",
                     "managed_money", "swap_dealer", "dealer_net", "commercial"),
        "discretionary": True,
        "claim": "crowded or extreme REPORTED positioning predicts the next move"},
    "ATTENTION-SENTIMENT": {
        "patterns": ("wikipedia", "attention", "sentiment", "social", "commit_velocity"),
        "discretionary": False,
        "claim": "measurable attention leads returns"},
    "MARKET-MAKING-EXECUTION": {
        "patterns": ("grid", "ladder", "market_mak", "spread_capture", "maker", "microstructure"),
        "discretionary": False,
        "claim": "earn the spread / earn better fills rather than predict direction"},
    "VOL-AND-OPTIONS": {
        "patterns": ("vol-target", "vol_target", "options", "variance", "skew", "gamma"),
        "discretionary": False,
        "claim": "implied-vs-realised volatility and its surface are tradeable"},
    "EVENT-AND-CALENDAR": {
        # "listing" (exchange listing watch) and "unlock" (token unlock schedules) are gone; the
        # scheduled events an MT5 book actually trades are macro releases and earnings, which
        # scripts/build_event_calendar.py already enumerates.
        "patterns": ("event", "announce", "calendar", "release", "nfp", "cpi", "fomc",
                     "earnings", "regime_rotation", "inout_regime"),
        "discretionary": True,
        "claim": "scheduled or announced events move price predictably"},
    "LEVEL-REACTION": {
        "patterns": ("level", "support", "resistance", "range_edge", "liquidity_pool", "sweep"),
        "discretionary": True,
        "claim": "price reacts at levels a crowd can see -- the sleeve's stop-placement thesis"},
    "STATISTICAL-ARBITRAGE": {
        "patterns": ("pairs", "cointegrat", "statarb", "mean_revert", "spread_trade"),
        "discretionary": False,
        "claim": "a modelled relationship between instruments reverts",
        # R0296 (RU practitioner corpus, 2026-08-01) -- binds whoever tests this family FIRST:
        "test_prior": ("spend the test budget on COST/CAPACITY measurement, never the estimator "
                       "(Kalman/polynomial ~= OLS+sigma per practitioner reply chains). Prior: "
                       "~4.78%/yr gross per contract over 80 cointegrated pairs; capacity ceiling "
                       "~USD 3-11k/pair before MMs reclaim it -- under L1.18a that is this desk's "
                       "band, not a disqualifier; slippage+colocation is the binding constraint "
                       "named by every source")},
    "LEAD-LAG": {
        # "btc_leadlag" (BTC leading the alt complex) replaced by the leaders an MT5 book has:
        # the dollar index, the rates curve, and gold against the FX crosses that carry it.
        "patterns": ("leadlag", "lead_lag", "dxy", "yield_lead", "gold_lead", "index_lead",
                     "correlation_regime"),
        "discretionary": False,
        "claim": "one instrument's move predicts another's with a lag"},
}


def _corpus(root: Path, *, errors: list[str] | None = None) -> list[tuple[str, str]]:
    """(name, origin) for every strategy the desk has a record of testing.

    Read failures are APPENDED to `errors`, never swallowed: an unreadable graveyard yields an
    empty corpus, and an empty corpus reports every family NEVER-HUNTED -- the loudest verdict
    this organ has, produced by a missing file rather than by a real gap. The caller surfaces it
    so the two are never confused."""
    errs = errors if errors is not None else []
    out: list[tuple[str, str]] = []
    try:
        lines = (root / "docs/graveyard.md").read_text("utf-8", errors="ignore").splitlines()
        for i, ln in enumerate(lines):
            # A row whose NEXT line is the |---| separator is a table HEADER, not a strategy.
            # Checking that rather than blacklisting header words handles the file's several
            # tables, and it is why "name" stopped being counted as a buried candidate.
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(r"\s*\|\s*:?-{2,}", nxt) or re.match(r"\s*\|\s*:?-{2,}", ln):
                continue
            # The name is the first cell's leading token; most rows continue with a
            # parenthetical description ("kama_squeeze (TTM squeeze + KAMA...)"), so anchoring on
            # a closing pipe silently dropped 31 of 42 rows -- and a coverage organ that reads a
            # quarter of the record reports NEVER-HUNTED for families the desk has genuinely
            # worked, which is worse than not reporting at all.
            m = re.match(r"\|\s*([a-z0-9_-]{3,})\b", ln)
            if m:
                out.append((m.group(1), "graveyard"))
    except OSError as exc:
        errs.append(f"graveyard unreadable ({type(exc).__name__}: {exc})")
    try:
        led = json.loads((root / "docs/research/recommendation_ledger.json").read_text("utf-8"))
        rows = led["recommendations"] if isinstance(led, dict) else led
        for r in rows:
            s = str(r.get("summary") or "")
            if s:
                out.append((s.lower()[:400], "ledger"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errs.append(f"ledger unreadable ({type(exc).__name__}: {exc})")
    return out


def coverage(root: Path | None = None) -> dict[str, Any]:
    """Distinct families touched, and which have never been looked at once."""
    root = root or _ROOT
    errors: list[str] = []
    corpus = _corpus(root, errors=errors)
    graveyard = [(n, o) for n, o in corpus if o == "graveyard"]
    fams: dict[str, Any] = {}
    for name, spec in FAMILIES.items():
        hits = sorted({n for n, o in graveyard
                       if any(p in n for p in spec["patterns"])})
        mentions = sum(1 for n, o in corpus if o == "ledger"
                       and any(p in n for p in spec["patterns"]))
        state = ("HUNTED" if len(hits) >= THIN_BELOW else
                 "THIN" if hits else
                 "MENTIONED-NEVER-TESTED" if mentions else "NEVER-HUNTED")
        fams[name] = {
            "state": state, "n_tested": len(hits), "tested": hits[:8],
            "ledger_mentions": mentions,
            "discretionary_adjacent": bool(spec["discretionary"]),
            "claim": spec["claim"],
            # An operative prior rides WITH the gap it governs (R0296): the artifact that tells
            # a reader "never tested" is the artifact that reader opens before testing.
            **({"test_prior": spec["test_prior"]} if "test_prior" in spec else {}),
            "why": (f"{len(hits)} distinct candidates buried -- this family has been genuinely "
                    "worked" if state == "HUNTED" else
                    f"only {len(hits)} candidate(s) tested; one test is an anecdote and two a "
                    "coincidence, so this family is NOT covered" if state == "THIN" else
                    f"{mentions} ledger mention(s) but nothing ever reached the graveyard -- "
                    "discussed, never tested" if state == "MENTIONED-NEVER-TESTED" else
                    "NEVER HUNTED -- no candidate of this family has ever been tested or rowed. "
                    "This is a finding, not an omission"),
        }
    unhunted = [k for k, v in fams.items() if v["state"] in ("NEVER-HUNTED",
                                                             "MENTIONED-NEVER-TESTED")]
    thin = [k for k, v in fams.items() if v["state"] == "THIN"]
    hunted = [k for k, v in fams.items() if v["state"] == "HUNTED"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.32/L1.31 -- coverage is the count of DISTINCT FAMILIES touched, never the "
               "count of candidates tested. Twelve candidates from one family are correlated by "
               "construction: they die together and the desk learns roughly one thing.",
        # UNREADABLE outranks every substantive verdict. With no corpus every family reads
        # NEVER-HUNTED -- this organ's loudest output -- produced by a missing file rather than
        # by a real gap, and a reader cannot tell the two apart from the families alone.
        "status": ("UNREADABLE" if errors and not graveyard else
                   "UNCOVERED" if unhunted else "THIN" if thin else "COVERED"),
        "read_errors": errors,
        "n_families": len(FAMILIES),
        "n_hunted": len(hunted), "n_thin": len(thin), "n_unhunted": len(unhunted),
        "n_candidates_seen": len(graveyard),
        "families": fams,
        "unhunted": unhunted, "thin": thin,
        "next_family": (unhunted[0] if unhunted else thin[0] if thin else None),
        "detail": ("; ".join(errors) + " -- no corpus, so the family verdicts below are an "
                   "artefact of the read failure, NOT a coverage finding"
                   if errors and not graveyard else
                   f"{len(hunted)}/{len(FAMILIES)} families genuinely hunted across "
                   f"{len(graveyard)} buried candidates; {len(unhunted)} never hunted, "
                   f"{len(thin)} thin"),
        "never_narrow": ("the miners' next dig must open a family from `unhunted`, not deepen "
                         "one from `hunted` -- a family already worked returns correlated "
                         "candidates, and correlated candidates are one bet wearing many names"
                         if unhunted else
                         "every family has been touched; depth in the THIN ones is now the "
                         "higher-value direction"),
    }


def discretionary_candidates(root: Path | None = None) -> list[dict[str, Any]]:
    """Families the CONVICTION sleeve could act on, as playbook candidates.

    Only families flagged discretionary_adjacent -- a carry or vol-surface finding is real
    research but the sleeve cannot express it, so routing it there would be noise in the one brief
    that has to stay sharp."""
    root = root or _ROOT
    cov = coverage(root)
    out = []
    for name, f in cov["families"].items():
        if not f["discretionary_adjacent"]:
            continue
        out.append({"family": name, "state": f["state"], "claim": f["claim"],
                    "n_tested": f["n_tested"], "tested": f["tested"]})
    return out


def import_to_playbook(root: Path | None = None) -> dict[str, Any]:
    """File discretionary-family findings as PROVISIONAL playbook lessons.

    THE ASYMMETRY THAT MAKES THIS SAFE: an outside finding may SUGGEST a method change; only the
    sleeve's OWN closed trades may authorise one. run_trade_review requires N_SUPPORT confirmations
    before a lesson reaches the trading brief, and an import that skipped that queue would let an
    untested external claim rewrite the money path silently. So imports enter at the back of the
    same queue, carry their origin, and earn promotion exactly like a lesson the sleeve learned
    itself. Re-running is idempotent: an already-imported family is not re-filed.
    """
    root = root or _ROOT
    path = root / _PLAYBOOK
    try:
        pb = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        pb = {"lessons": [], "reviewed_keys": []}
    have = {lv.get("imported_from") for lv in pb.get("lessons", [])}
    filed = []
    for c in discretionary_candidates(root):
        key = f"strategy_coverage:{c['family']}"
        if key in have or c["state"] == "NEVER-HUNTED":
            continue                       # nothing to import from a family with no record yet
        pb.setdefault("lessons", []).append({
            "lesson": (f"{c['family']}: {c['claim']}. The desk's own record has {c['n_tested']} "
                       f"buried candidate(s) here ({', '.join(c['tested'][:4]) or 'none named'}) "
                       f"-- state {c['state']}."),
            "status": "PROVISIONAL", "support": 0,
            "origin": "IMPORTED from strategy-family coverage (R0200), NOT from a closed trade",
            "imported_from": key,
            "authority": "SUGGESTS ONLY. An external finding never reaches the trading brief on "
                         "its own -- it needs the sleeve's own confirmations like any lesson.",
            "trades": [],
            "at": datetime.now(tz=UTC).isoformat(),
        })
        filed.append(c["family"])
    if filed:
        path.parent.mkdir(parents=True, exist_ok=True)
        pb["updated"] = datetime.now(tz=UTC).isoformat()
        path.write_text(json.dumps(pb, indent=2), "utf-8")
    return {"filed": filed, "n_filed": len(filed),
            "why": (f"filed {len(filed)} discretionary-family finding(s) as PROVISIONAL with "
                    "support=0 -- they reach the trading brief only after the sleeve's own "
                    "closed trades confirm them" if filed else
                    "nothing new to import; every discretionary-adjacent family with a record "
                    "is already queued")}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--import-discretionary", action="store_true",
                    help="file discretionary-family findings as PROVISIONAL playbook lessons")
    args = ap.parse_args()
    rep = coverage(_ROOT)
    if args.import_discretionary:
        rep["import"] = import_to_playbook(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"strategy coverage (L1.32): {rep['status']} -- {rep['detail']}")
        for k in rep["unhunted"]:
            print(f"  NEVER-HUNTED  {k:<26} {rep['families'][k]['claim'][:58]}")
        for k in rep["thin"]:
            print(f"  THIN          {k:<26} {rep['families'][k]['n_tested']} tested")
        if rep.get("import"):
            print(f"  imported: {rep['import']['n_filed']} provisional playbook lesson(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
