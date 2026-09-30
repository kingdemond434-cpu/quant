#!/usr/bin/env python3
"""MECHANISM ATTRIBUTION (R0137) -- a sleeve may not read as SURVIVED on P&L its mechanism
cannot explain.

WHAT PRODUCED THIS FENCE, on 2026-07-31. The dashboard showed funding carry as a survivor. The
numbers behind it:

    equity $18,669 from $15,000  ->  net +$3,669.55 (+24.5%) over 29 days, Sharpe 13.13
    FUNDING HARVEST COLLECTED:   +$113.06

Funding is 3.1% of the P&L. The other $3,556 did not come from carry. A cash-and-carry book is
spot-long / perp-short and delta-neutral BY CONSTRUCTION: its price legs cancel, so its P&L should
be funding plus basis, near-100%. The desk already owns the fence that says this --
``libs.execution.carry_accounting.carry_bleed_report``, deliberately TWO-SIDED so that a large
POSITIVE non-funding P&L alarms as loudly as a loss, because on a hedged book a windfall that size
is a NAKED LEG rather than edge. Run on those numbers it returns:

    BLEED(inverted): non-funding PnL +3556.49 is 3146% of +113.06 funding harvest

So the desk's own logic already disagreed with the dashboard. The verdict was computed, written to
a JSON field, rendered -- AND GATED NOTHING. `max_audit` raises a defect only when funding is
UNMEASURED; when the alarm actually trips, nothing fails. That is the recurring defect shape on
this desk in its most expensive form: a fence firing into a field nobody reads, while a survival
claim built on the same numbers goes to the principal for a capital decision.

WHY IT IS A SEPARATE, GENERAL FENCE. The specific bug is one `if` in max_audit. The general bug is
that ANY sleeve can be credited with P&L its stated mechanism does not explain -- a hedge with an
untracked leg, a market-neutral book carrying beta, or a sleeve's line item quietly aggregating an
account it does not own. So the rule is stated once and applied to every sleeve with a measurable
mechanism term:

    A sleeve whose P&L is not attributable to its stated mechanism is UNATTRIBUTED. It may not
    read as survived, validated or promotable, whatever its return looks like -- and an
    unattributed WIN is treated exactly as seriously as an unattributed loss, because the
    directional exposure that produced it is still there and still unhedged.

UNMEASURED never reads as OK: a venue income read that failed makes attribution UNDECIDABLE, not
clean, and the fence says so rather than passing.

WHICH BOOK. THE MT5 LIVE ROSTER, from 2026-09-23. Until today this fence looked for deployed state
in `research_state.json` and `data/cashcarry_positions.json` -- and on the trading box the first
EXISTS with `deployed: {}` (a crypto-era blob last written 2026-08-29) while the second is the
output of an executor deleted on 2026-09-05. So `_load_state` reported "schema-missing-key; absent"
and the fence published `n_sleeves: 0` every hour: an UNDECIDABLE verdict about a book it had
never looked at, on a desk with seven live sleeves. A denominator of zero is the shape of failure
this whole fence exists to name, and it was in the fence itself.

The MT5 desk publishes its deployed roster at `desks/mt5/data/sleeves.json` (written hourly by
`desks/mt5/research/promoter.py`; status LIVE / STANDBY / RETIRED), and a sleeve's STATED MECHANISM
is its `family`. That is what the fence reads now. The legacy crypto path below is untouched and
still runs when a `research_state.json`-shaped blob is the only thing on the host.

WHAT IT FINDS THERE IS THE LAW'S OWN TARGET CONDITION, not a clean bill (measured 2026-09-23): six
of the seven LIVE sleeves are the gold window book, every one of them carries `family: null` and
`canonical_identity: "UNIDENTIFIABLE"`, and those windows are the account's largest realised
winner. A sleeve that states no mechanism cannot have its P&L attributed to one -- so attribution
is UNDECIDABLE, which is exactly what R0137 says may never read as survived.

    python scripts/check_mechanism_attribution.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: ATTRIBUTED is this fence's OK. UNMEASURED -- no rows, or every sleeve's mechanism term
#: unreadable -- previously exited 0, so "we cannot tell whether any edge is attributed" was
#: reported to cron as "every edge is attributed" (L1.16, L1.28a).
_PASSING = frozenset({"ATTRIBUTED"})

_OUT = "data/mechanism_attribution.json"

#: Flagged sleeves printed to the console before the rest are counted. Every row is in the
#: artifact either way; this only stops one verdict filling a law-gate log.
_CONSOLE_ROWS = 10

#: How much of a sleeve's P&L may come from outside its stated mechanism before the claim is
#: UNATTRIBUTED. 0.5 matches carry_bleed_report's own alert_frac -- the same number the desk
#: already chose for the same question, reused rather than re-picked (see check_sizing_derivation).
UNATTRIBUTED_FRAC = 0.5

#: Sleeves with a MEASURABLE mechanism term, and where to read it. A sleeve whose mechanism cannot
#: be measured separately from its P&L is not listed: it would be judged by a number that does not
#: exist, which is worse than not judging it. That absence is itself reported.
_SLEEVES: dict[str, dict[str, str]] = {
    "cash_and_carry": {
        "mechanism": "funding harvest on a delta-neutral spot/perp pair; price legs cancel by "
                     "construction, so P&L should be funding + basis, near-100%",
        "total_key": "net_pnl",
        "mechanism_key": "funding",
    },
}


def attribute(name: str, spec: dict[str, str], state: dict[str, Any]) -> dict[str, Any]:
    total = state.get(spec["total_key"])
    mech = state.get(spec["mechanism_key"])
    row: dict[str, Any] = {"sleeve": name, "mechanism": spec["mechanism"],
                           "total_pnl": total, "mechanism_pnl": mech}
    if total is None or mech is None:
        return {**row, "state": "UNMEASURED",
                "why": (f"missing {spec['total_key'] if total is None else spec['mechanism_key']} "
                        "-- attribution is UNDECIDABLE, which is not the same as clean")}
    try:
        total, mech = float(total), float(mech)
    except (TypeError, ValueError):
        return {**row, "state": "UNMEASURED", "why": "non-numeric P&L terms"}

    unexplained = round(total - mech, 2)
    row["unexplained_pnl"] = unexplained
    row["mechanism_share"] = round(mech / total, 4) if total else None
    if mech > 0:
        ratio = abs(unexplained) / mech
        bad = ratio >= UNATTRIBUTED_FRAC
    else:
        ratio = float("inf") if unexplained != 0 else 0.0
        bad = unexplained != 0.0
    row["unexplained_vs_mechanism"] = (None if ratio == float("inf") else round(ratio, 3))
    if not bad:
        share = row["mechanism_share"]
        return {**row, "state": "ATTRIBUTED",
                "why": (f"{share:.0%} of P&L explained by the stated mechanism" if share is not None
                        else "no P&L to attribute -- nothing earned, nothing unexplained")}
    direction = "WIN" if unexplained > 0 else "LOSS"
    return {**row, "state": "UNATTRIBUTED",
            "why": (f"unexplained {direction} {unexplained:+,.2f} is "
                    + (f"{ratio:.0%} of " if ratio != float("inf") else "present with no ")
                    + f"the {mech:+,.2f} mechanism term -- this sleeve is being credited with P&L "
                      "its mechanism cannot produce. An unexplained WIN is not better news than a "
                      "loss: the exposure that made it is still on, still unhedged, and will "
                      "reverse. NOT survived, NOT promotable, whatever the return looks like.")}


#: The executor's LIVE book state, per sleeve -- the same artifact max_audit's carry checks read
#: (R0352). Consulted ONLY when a sleeve has already been judged UNATTRIBUTED, to decide whether
#: that verdict is a live claim or a closed accounting episode. It never touches the threshold.
_LIVE_BOOK: dict[str, str] = {"cash_and_carry": "web/cashcarry_live.json"}


def _closed_episode(root: Path, rel: str) -> tuple[bool, str]:
    """Is this sleeve's book FLAT with its lifetime gap ATTRIBUTED by reconciliation? (R0493)

    Mirrors scripts/max_audit.py:check_carry_funding_measured (R0352), reading the STRUCTURED
    recon fields rather than parsing the verdict string. The UNATTRIBUTED ratio is built from
    CUMULATIVE-LIFETIME totals, so a book holding no positions cannot move either term: with
    exposure at zero the verdict is arithmetically incapable of ever clearing -- an absorbing
    state in the LAW GATE, which is the thing L1.43 says gets switched off. Measured live:
    funding_harvested pinned at 113.06 since 2026-08-05 while n_carries was 0.

    THE THRESHOLD IS NOT TOUCHED (UNATTRIBUTED_FRAC unchanged): a book with ANY exposure is
    judged exactly as before. ABSENCE IS NOT ZERO (WS-005): only a PRESENT-and-zero exposure
    reading plus explained=True AND measured=True earns the closed-episode reading; a missing
    file, key or recon falls through and the live verdict stands.
    """
    try:
        live = json.loads((root / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, f"{rel} unreadable -- live-book state unknown, verdict stands"
    if not isinstance(live, dict):
        return False, f"{rel} malformed -- verdict stands"
    legs, notl = live.get("n_carries"), live.get("deployed_notional")
    flat = (isinstance(legs, int) and legs == 0
            and isinstance(notl, int | float) and float(notl) == 0.0)
    if not flat:
        return False, "book has (or may have) exposure -- live verdict stands"
    recon = live.get("fut_leg_reconciliation") or {}
    if not (recon.get("explained") is True and recon.get("measured") is True):
        return False, ("book FLAT but the lifetime gap is unexplained "
                       f"(explained={recon.get('explained')!r} "
                       f"measured={recon.get('measured')!r}) -- verdict stands")
    return True, (f"book FLAT (0 carries, 0 notional) and the futures-leg reconciliation "
                  f"attributes the lifetime gap to the ledgered inception re-base "
                  f"(rebase_usd={recon.get('rebase_usd')}) -- a closed ACCOUNTING episode, not "
                  "P&L the mechanism owes an explanation for. With zero exposure the cumulative "
                  "ratio is frozen by construction and could never clear (R0352/R0493)")


#: Where a deployed-state blob may live, in priority order. The trailing entry was
#: data/cashcarry_state.json (R0333) -- a path NO organ writes, so the fallback could never fire
#: and its silence was indistinguishable from a healthy read; it became
#: data/cashcarry_positions.json, which the executor wrote until that executor was deleted on
#: 2026-09-05. THE MT5 ROSTER LEADS THE LIST because it is the only one of the three with a live
#: writer: `desks/mt5/research/promoter.py` re-judges it every hour. The crypto candidates stay
#: behind it rather than being deleted -- a host that still holds one is still audited -- but they
#: can no longer be the reason this fence reports on nothing.
_STATE_CANDIDATES = ("desks/mt5/data/sleeves.json", "research_state.json",
                     "data/cashcarry_positions.json")

#: The MT5 desk's own per-sleeve inputs. Each is DECLARED, so an unreadable one makes a sleeve's
#: attribution UNDECIDABLE rather than silently zero-P&L (WS-005: absence is not zero).
_MT5_ROSTER = "desks/mt5/data/sleeves.json"
#: deal -> roster name. `attribution_reconcile` exists because MetaTrader truncates the order
#: comment to 27 characters, so the ledger's own `sleeve` field is a PREFIX for most rows and
#: joining on it would credit the wrong sleeve.
_MT5_RECONCILE = "desks/mt5/reports/ATTRIBUTION_RECONCILE.json"
#: deal -> realised P&L. The gateway writes one row per closed deal under its own magic.
_MT5_LEDGER = "desks/mt5/data/live_ledger.jsonl"
#: The desk's existing unexplained-fraction organ, read as CONTEXT and never as the mechanism
#: term -- see `_mt5_rows` for why the two are different questions.
_MT5_CFA = "desks/mt5/reports/COUNTERFACTUAL_ATTRIBUTION.json"

#: The field on a roster row that names the sleeve's mechanism. `family` is the desk's mechanism
#: vocabulary end to end: the gauntlet certificates it in `shadow_spec.family`, the promoter copies
#: it onto the roster row, `mt5desk/families.py` holds the generator behind each name, and
#: PROP_FIRM_E8 counts readiness in INDEPENDENT MECHANISMS drawn from it.
_MT5_MECHANISM_FIELD = "family"

#: A blob is a deployed-state artifact only if it carries a deployed/molded block or at least one
#: sleeve-shaped key. Treating ANY readable JSON object as the deployed state is how a positions
#: file becomes a silent, sleeve-less "clean" attribution.
_SHAPE_KEYS = ("sleeves", "live_sleeves", "net_pnl", "funding")


def _load_state(root: Path, rel: str) -> tuple[dict[str, Any] | None, str]:
    """One deployed-state candidate, with the failure NAMED (R0333).

    "absent", "unparseable" and "schema-missing-key" are three different facts and the fence
    reports which one it hit -- an UNDECIDABLE attribution must say WHY it is undecidable, or the
    next reader assumes the artifact simply had nothing to report.
    """
    try:
        raw = (root / rel).read_text("utf-8")
    except FileNotFoundError:
        return None, f"{rel}: absent"
    except OSError as exc:
        return None, f"{rel}: unreadable ({type(exc).__name__})"
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{rel}: unparseable (not valid JSON, line {exc.lineno})"
    if not isinstance(blob, dict):
        return None, f"{rel}: unparseable (holds a {type(blob).__name__}, not an object)"
    for key in ("deployed", "molded"):
        block = blob.get(key)
        if isinstance(block, dict) and block:
            return block, "ok"
    if any(k in blob for k in _SHAPE_KEYS):
        return blob, "ok"
    return None, (f"{rel}: schema-missing-key (no deployed/molded block and none of "
                  f"{', '.join(_SHAPE_KEYS)} -- not a deployed-state artifact)")


def _mt5_realised(root: Path) -> tuple[dict[str, dict[str, float]], str]:
    """Realised P&L per LIVE sleeve name, and how it was measured (or why it was not).

    THE JOIN IS THE MEASUREMENT AND IT IS TWO HOPS, deliberately. MetaTrader truncates the order
    comment to 27 characters, so `live_ledger.jsonl`'s own `sleeve` field is a PREFIX on most rows
    and 14 rows carry no name at all -- summing P&L on it would credit the wrong sleeve and call
    the result attribution. `attribution_reconcile` already resolves deal -> roster name (EXACT /
    PREFIX / GEOMETRY, with AMBIGUOUS and UNATTRIBUTED kept separate), so the fence joins on
    `deal` and inherits that organ's own refusals rather than inventing a second opinion.

    Deals the reconciler could not attribute are NOT distributed and NOT dropped: they are counted
    and reported. An unattributed deal is P&L this desk cannot assign to any mechanism, which is
    the finding, not a rounding error.
    """
    try:
        recon = json.loads((root / _MT5_RECONCILE).read_text("utf-8"))
        rows = recon.get("rows")
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"{_MT5_RECONCILE} unreadable ({type(exc).__name__}) -- P&L UNMEASURED"
    if not isinstance(rows, list):
        return {}, f"{_MT5_RECONCILE} holds no rows[] -- P&L UNMEASURED"
    by_deal: dict[Any, str] = {}
    unresolved = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = r.get("sleeve")
        if isinstance(name, str) and name and r.get("route") not in ("AMBIGUOUS", "UNATTRIBUTED"):
            by_deal[r.get("deal")] = name
        else:
            unresolved += 1

    try:
        lines = (root / _MT5_LEDGER).read_text("utf-8").splitlines()
    except OSError as exc:
        return {}, f"{_MT5_LEDGER} unreadable ({type(exc).__name__}) -- P&L UNMEASURED"
    out: dict[str, dict[str, float]] = {}
    unjoined = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        name = by_deal.get(row.get("deal"))
        if name is None:
            unjoined += 1
            continue
        acc = out.setdefault(name, {"n": 0.0, "pl_quote": 0.0, "r": 0.0})
        acc["n"] += 1
        for src_key, dst in (("pl_quote", "pl_quote"), ("r_multiple", "r")):
            try:
                acc[dst] += float(row.get(src_key) or 0.0)
            except (TypeError, ValueError):
                continue
    return out, (f"joined {sum(int(v['n']) for v in out.values())} deal(s) to "
                 f"{len(out)} roster name(s) via {_MT5_RECONCILE}; {unresolved} deal(s) the "
                 f"reconciler left AMBIGUOUS/UNATTRIBUTED and {unjoined} ledger row(s) with no "
                 f"reconciled name are EXCLUDED and counted, never distributed")


def _mt5_context(root: Path) -> dict[str, dict[str, Any]]:
    """The desk's already-measured unexplained fraction per sleeve, READ AS CONTEXT ONLY.

    `desks/mt5/research/counterfactual_attribution.py` runs hourly and publishes, per live sleeve,
    the share of realised R that its decomposition leaves unexplained. It is tempting to use that
    as this fence's mechanism term, and it would be wrong: CFA's explanatory baseline is THE
    SLEEVE'S OWN trailing mean plus a macro-state bucket plus the modelled cost surface. It answers
    "is this P&L explained by this sleeve's own history and its costs". L1.6 asks "is this P&L
    explained by the MECHANISM the sleeve STATES" -- and every CFA residual row carries
    `family: null`, so it does not even hold the mechanism label. Substituting one for the other
    would be a confident number standing in for an unmeasured one, which is the failure this fence
    was built to stop. It is published beside the verdict, named for what it is.
    """
    try:
        doc = json.loads((root / _MT5_CFA).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("residual_rows") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "")
        name = key.split(":", 1)[1] if ":" in key else key
        if name:
            out[name] = {"unexplained_fraction": row.get("unexplained_fraction"),
                         "measured": row.get("unexplained_measured"),
                         "magnitude_r": row.get("magnitude")}
    return out


def _mt5_rows(root: Path, roster: list[Any]) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """One attribution row per LIVE sleeve on the MT5 account.

    THE VERDICT CANNOT BE ATTRIBUTED TODAY AND THE FENCE SAYS WHY, PER SLEEVE. Two distinct
    blockers, and collapsing them would hide the one that is actually fixable:

      NO STATED MECHANISM -- the row's `family` is null. Six of the seven LIVE sleeves are the
          gold windows and every one of them carries `family: null` with
          `canonical_identity: "UNIDENTIFIABLE"`. A sleeve that states no mechanism cannot have
          its P&L attributed to one, however large that P&L is -- and these windows are the
          account's largest realised winner, which is R0137's exact target condition rather than
          an exemption from it.

      NO MECHANISM TERM -- the row states a family, and nothing on this desk publishes the P&L
          that family PREDICTS. `mech_split.json` holds backtested per-state expectancy for the
          gold book and `families.py` holds the generators, but no artifact carries a live
          predicted-vs-realised term to attribute against. Until one exists the comparison has no
          left-hand side, and a fence that judged anyway would be judging by a number that does
          not exist -- worse than not judging (see `_SLEEVES`, which lists a sleeve only when its
          mechanism is separately measurable).
    """
    realised, pl_why = _mt5_realised(root)
    context = _mt5_context(root)
    live = [r for r in roster if isinstance(r, dict) and str(r.get("status")) == "LIVE"]
    rows: list[dict[str, Any]] = []
    for r in live:
        name = str(r.get("name") or "<unnamed>")
        mech = r.get(_MT5_MECHANISM_FIELD)
        mech = str(mech) if isinstance(mech, str) and mech.strip() else None
        pnl = realised.get(name) or realised.get(name.rsplit("_v", 1)[0])
        row: dict[str, Any] = {
            "sleeve": name, "symbol": r.get("symbol"),
            "mechanism": mech,
            "canonical_identity": r.get("canonical_identity"),
            "total_pnl": None if pnl is None else round(pnl["pl_quote"], 2),
            "realised_r": None if pnl is None else round(pnl["r"], 4),
            "n_deals": None if pnl is None else int(pnl["n"]),
            "mechanism_pnl": None,
            "self_referential_unexplained": context.get(name)
            or context.get(name.rsplit("_v", 1)[0]),
            "state": "UNMEASURED",
        }
        if mech is None:
            row["why"] = (
                f"the roster row states NO mechanism ({_MT5_MECHANISM_FIELD} is null, "
                f"canonical_identity={r.get('canonical_identity')!r}) -- P&L cannot be attributed "
                "to a mechanism the sleeve does not state, so attribution is UNDECIDABLE, which "
                "is not the same as clean. Owner: desks/mt5/research/promoter.py writes this row; "
                "the family it would copy comes from the gauntlet's shadow_spec")
        else:
            row["why"] = (
                f"mechanism '{mech}' is stated, but no artifact on this desk publishes the P&L "
                f"that mechanism PREDICTS, so there is no term to attribute against. "
                "Owner: the mechanism->prediction half is unbuilt (mech_split.json holds "
                "backtested per-state expectancy, not a live predicted term). Judging anyway "
                "would use a number that does not exist")
        rows.append(row)
    # ABSENCE IS NOT ZERO (WS-005). When no deal could be joined to any roster name, the P&L
    # carried by the mechanism-less sleeves is UNMEASURED -- publishing 0.00 there would read as
    # "those sleeves earned nothing", which is a claim, and the opposite of the true one on this
    # book: the gold windows are the account's largest realised winner.
    measured_pnl = [r for r in rows if r["mechanism"] is None and r["total_pnl"] is not None]
    summary = {
        "n_live": len(live),
        "n_without_stated_mechanism": sum(1 for r in rows if r["mechanism"] is None),
        "pnl_measurement": pl_why,
        "pnl_without_stated_mechanism": (
            round(sum(float(r["total_pnl"]) for r in measured_pnl), 2) if measured_pnl else None),
    }
    return rows, pl_why, summary


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    src: str | None = None
    deployed: dict[str, Any] = {}
    why: list[str] = []
    for cand in _STATE_CANDIDATES:
        blob, verdict = _load_state(root, cand)
        if blob is not None:
            src, deployed = cand, blob
            break
        why.append(verdict)
    if src is None:
        return {"generated": datetime.now(tz=UTC).isoformat(), "status": "UNMEASURED",
                "detail": "no deployed-state artifact readable on this host -- attribution "
                          "UNDECIDABLE, which never reads as clean; " + "; ".join(why),
                "n_sleeves": 0, "sleeves": []}

    named = list(deployed.get("sleeves") or deployed.get("live_sleeves") or [])
    # THE MT5 ROSTER IS A LIST OF ROWS, not a list of names -- that shape is how this branch is
    # recognised, so a legacy `research_state.json` blob (whose `sleeves` is a list of strings)
    # still takes the path below it and the crypto sleeve table keeps working unchanged.
    if src == _MT5_ROSTER and named and all(isinstance(s, dict) for s in named):
        rows, pl_why, summary = _mt5_rows(root, named)
        bad = [r for r in rows if r["state"] == "UNATTRIBUTED"]
        status = "UNATTRIBUTED" if bad else "ATTRIBUTED" if rows and not any(
            r["state"] == "UNMEASURED" for r in rows) else "UNMEASURED"
        no_mech = [r["sleeve"] for r in rows if r["mechanism"] is None]
        return {
            "generated": datetime.now(tz=UTC).isoformat(),
            "source": src,
            "law": "L1.6/L2.6 -- a sleeve may not read as survived on P&L its stated mechanism "
                   "cannot explain. An unattributed WIN is as disqualifying as an unattributed "
                   "loss: the exposure that produced it is unhedged and will reverse.",
            "status": status,
            "n_sleeves": len(rows),
            "n_unattributed": len(bad),
            "sleeves": rows,
            "mechanism_unjudgeable": no_mech,
            "roster_summary": summary,
            "detail": (
                f"{summary['n_live']} LIVE sleeve(s) on the MT5 account; "
                f"{summary['n_without_stated_mechanism']} of them state NO mechanism "
                f"({_MT5_MECHANISM_FIELD} null) and hold "
                + (f"{summary['pnl_without_stated_mechanism']:+,.2f} quote of"
                   if summary["pnl_without_stated_mechanism"] is not None else "an UNMEASURED")
                + " realised P&L -- attribution UNDECIDABLE for those, which never reads as clean"
                + (f"; UNATTRIBUTED: {', '.join(r['sleeve'] for r in bad)}" if bad else "")
                + f". P&L: {pl_why}"),
            "next_action": (
                "TWO OWNERS, BOTH NAMED. (1) desks/mt5/research/promoter.py writes the roster "
                "row: carry the gauntlet certificate's shadow_spec.family onto every promoted "
                "sleeve so the gold windows stop reaching the live account with family=null and "
                "canonical_identity=UNIDENTIFIABLE. (2) The mechanism->prediction term is "
                "UNBUILT: nothing publishes the P&L a stated family predicts, so there is no "
                "left-hand side to attribute against. Until (2) exists this fence reports "
                "UNMEASURED by construction, and that is the honest reading, not a failure to "
                "try -- see desks/mt5/reports/COUNTERFACTUAL_ATTRIBUTION.json, which measures a "
                "DIFFERENT residual (against the sleeve's own history, not its stated mechanism) "
                "and is published here as context only."),
        }

    rows = []
    for name, spec in _SLEEVES.items():
        if named and not any(name in str(s) for s in named):
            continue                                   # this sleeve is not deployed here
        row = attribute(name, spec, deployed)
        if row["state"] == "UNATTRIBUTED" and name in _LIVE_BOOK:
            # NOT `why` -- that name already holds the list of state-candidate refusals above, and
            # rebinding it to a string here shadowed the list for every reader after this point.
            closed, episode_why = _closed_episode(root, _LIVE_BOOK[name])
            if closed:
                row = {**row, "state": "ATTRIBUTED", "closed_episode": True, "why": episode_why}
            else:
                row["closed_episode_check"] = episode_why
        rows.append(row)
    unjudged = [str(s) for s in named
                if not any(k in str(s) for k in _SLEEVES) and "paper" not in str(s)]

    bad = [r for r in rows if r["state"] == "UNATTRIBUTED"]
    unmeasured = [r for r in rows if r["state"] == "UNMEASURED"]
    status = ("UNATTRIBUTED" if bad else "UNMEASURED" if unmeasured or not rows else "ATTRIBUTED")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "source": src,
        "law": "L1.6/L2.6 -- a sleeve may not read as survived on P&L its stated mechanism cannot "
               "explain. An unattributed WIN is as disqualifying as an unattributed loss: the "
               "exposure that produced it is unhedged and will reverse.",
        "status": status,
        "n_sleeves": len(rows), "n_unattributed": len(bad),
        "sleeves": rows,
        "mechanism_unjudgeable": unjudged,
        "detail": (f"{len(rows)} sleeve(s) with a measurable mechanism term"
                   + (f"; UNATTRIBUTED: {', '.join(r['sleeve'] for r in bad)}" if bad else "")
                   + (f"; UNMEASURED: {', '.join(r['sleeve'] for r in unmeasured)}"
                      if unmeasured else "")
                   + (f"; no mechanism term to judge: {', '.join(unjudged)}" if unjudged else "")),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"mechanism attribution (L1.6): {rep['status']} -- {rep['detail']}")
        # CAPPED FOR THE CONSOLE ONLY, and the remainder is COUNTED rather than dropped: the
        # artifact carries every row, and a law-gate line that scrolls for forty identical
        # sentences is a line nobody reads to the end.
        flagged = [r for r in rep["sleeves"] if r["state"] != "ATTRIBUTED"]
        for r in flagged[:_CONSOLE_ROWS]:
            print(f"  {r['sleeve']}: {r['state']} -- {r['why']}")
        if len(flagged) > _CONSOLE_ROWS:
            print(f"  ... and {len(flagged) - _CONSOLE_ROWS} more in {_OUT}")
        if rep.get("next_action"):
            print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_sleeves"],
                      of="sleeves with a measurable mechanism term")


if __name__ == "__main__":
    sys.exit(main())
