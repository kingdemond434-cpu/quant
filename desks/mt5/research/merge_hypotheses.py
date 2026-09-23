"""MERGE EVERY HYPOTHESIS SOURCE INTO THE ONE FILE THE GAUNTLET READS.

THE GAP THIS CLOSES (found 2026-08-26 while answering "will new certificates form in an hour?").
`external_gauntlet` reads exactly one input: `data/hypotheses/external_survivors.json`. Meanwhile
the generic search wrote `edge_search_results.json` and the orthogonal sweep wrote
`orthogonal_candidates.json`, and NOTHING read either. Both ran, both produced candidates, and
both were stranded one file away from the only door that grants certificates.

That is the same defect as the eight-gate barrier with no producer, pointed the other way: there
the gate had no input, here the producers had no consumer. A pipeline stage whose output nothing
consumes is not a stage, it is a log line -- and it would have kept the book at 95% one family
indefinitely while every dashboard showed the searcher running nightly.

WHAT THIS DOES, and what it deliberately does not. It merges the sources and deduplicates by
executable identity. It applies NO threshold of its own AND attaches no deflation input -- L1.60:
discovery → backtest → the ten gates AS DEFINED → certificate → forward → live. Everything
discovered reaches the gauntlet; the gauntlet decides, using its own sealed constants.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
TARGET = HYP / "external_survivors.json"

#: THE STUDY BANK. Rows of a family that is BANNED FROM LIVE CAPITAL keep existing here -- they
#: are not deleted and the miners keep producing them -- but they are not put in front of the
#: judge, because a cell that cannot reach the book cannot repay a gate-second however it scores.
STUDY_BANK = HYP / "study_bank.json"

#: The gate ledger, read ONLY to count how much of the judge each family has already consumed.
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
GATE_LEDGER_TAIL = 200_000


def live_banned_families() -> frozenset[str]:
    """Families the desk has already forbidden from live capital.

    READ FROM THE LIVE POLICY ITSELF (`mt5desk.live_policy.DEFAULT_BANNED_FAMILIES`), never
    copied here: a second list is a second truth, and the day the policy changes the docket must
    change with it in the same commit. An unreadable policy falls back to the measured ban so a
    broken import cannot quietly re-open 18% of the judge to a family that passed zero of 22,009.
    """
    try:
        from mt5desk.live_policy import DEFAULT_BANNED_FAMILIES
        return frozenset(str(f) for f in DEFAULT_BANNED_FAMILIES)
    except Exception:                                                    # pragma: no cover
        return frozenset({"discovered"})


def judged_by_family(path: Path | None = None, tail: int = GATE_LEDGER_TAIL) -> dict[str, int]:
    """How many judgements each family has already consumed, from the gate ledger's tail."""
    out: dict[str, int] = {}
    try:
        with (path or GATE_LEDGER).open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-tail:]
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            fam = str(json.loads(line).get("family") or "")
        except ValueError:
            continue
        if fam:
            out[fam] = out.get(fam, 0) + 1
    return out


#: The RL agent's own artifact. Read, never written, here.
ALPHA_RL = BASE / "reports" / "ALPHA_RL.json"


def alpha_rl_family_values(path: Path | None = None) -> tuple[dict[str, float], str]:
    """Per-FAMILY learned value from `reports/ALPHA_RL.json`, and the basis of that reading. G4.

    THE AGENT HAD NO CONSUMER, WHICH IS THE ONLY THING WRONG WITH IT. `libs/research/alpha_rl.py`
    learns Q(prefix, next decision) over the construction MDP whose first layer is `family`, the
    runner publishes the ranked table hourly, and its ledger row said in as many words that
    nothing read it -- "EXISTS-DARK code inside a PARTIAL row". A ranking nobody sorts on is a
    ranking of nothing.

    WHAT IS READ. Only rows whose prefix is EMPTY -- i.e. the first decision of an episode, whose
    `decision` is a family name -- because those are the only values that are about a family
    rather than about a family CONDITIONED on a symbol chosen later. `status` other than MEASURED
    returns nothing at all: an UNMEASURED table means no episode ran, and ordering the desk's
    judging docket by an unrun agent's opinions is worse than not ordering it.
    """
    p = ALPHA_RL if path is None else path
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}, f"{p.name} absent or unreadable"
    if not isinstance(doc, dict):
        return {}, f"{p.name} is not an object"
    if str(doc.get("status") or "") != "MEASURED":
        return {}, (f"{p.name} status={doc.get('status')!r}: "
                    f"{str(doc.get('reward_why') or doc.get('why') or 'no episode ran')[:120]}")
    out: dict[str, float] = {}
    for row in doc.get("top") or []:
        # A non-empty prefix is a CONDITIONAL value, not a statement about the family alone.
        if not isinstance(row, dict) or row.get("prefix"):
            continue
        fam, val = str(row.get("decision") or ""), row.get("value")
        if fam and isinstance(val, (int, float)) and (fam not in out or val > out[fam]):
            out[fam] = float(val)
    if not out:
        return {}, f"{p.name} MEASURED but carries no first-layer (family) decision"
    best = max(out.items(), key=lambda kv: kv[1])[0]
    return out, f"{p.name}: {len(out)} family value(s), best {best}"


def breadth_order(rows: list[dict], judged: dict[str, int]) -> list[dict]:
    """ORDER THE DOCKET SO UNTESTED FAMILIES REACH THE GATES.

    MEASURED 2026-09-23: the docket's largest families -- cross_asset_residual 55,190,
    overnight_drift 26,721, clock_transition 20,081, execution_state 13,660 -- barely appear
    among judged cells, while a handful are re-judged every hour. The gauntlet takes the docket
    in order under a bar budget, so the ORDER IS THE SELECTION: a family at the tail is not
    "lower priority", it is never judged at all.

    The key is judgements ALREADY SPENT PER DOCKET ROW of that family. A family with a large
    docket and no verdicts sorts first; one that has been judged ten times per row sorts last.
    Within a family the existing order is preserved, so this re-orders families and never rows.
    """
    docket: dict[str, int] = {}
    for row in rows:
        fam = str(row.get("family") or "")
        docket[fam] = docket.get(fam, 0) + 1

    def spend(fam: str) -> float:
        return judged.get(fam, 0) / max(docket.get(fam, 1), 1)

    # G4's CONSUMER. Breadth still decides the TIER -- an unjudged family outranks a re-judged
    # one, and that ratchet is untouched -- but families that have been spent on equally are no
    # longer separated by their own spelling. The RL agent's learned value for the family
    # decision breaks that tie, which is exactly the budget it was built to redirect. A family
    # the agent has never valued sorts at 0.0, which is the NEUTRAL point of a signed dE[log W]
    # value, so an unvalued family loses nothing to one the agent dislikes.
    rl, _rl_why = alpha_rl_family_values()
    order = {fam: i for i, fam in
             enumerate(sorted(docket, key=lambda f: (spend(f), -rl.get(f, 0.0), f)))}
    return sorted(rows, key=lambda r: order.get(str(r.get("family") or ""), len(order)))

#: Every producer, and how to reach the rows inside it. Adding a producer means adding a line
#: here -- and the job manifest will report the target STALE if this stops running, so a new
#: source cannot go quietly unconsumed the way these two did.
SOURCES = (
    ("external_backtest_results.json", None),
    ("miner_candidates.json", "hypotheses"),
    ("edge_search_results.json", "hypotheses"),
    ("orthogonal_candidates.json", "hypotheses"),
    # Coverage backfill: hypotheses for asset classes the docket has ZERO rows for.
    # A generic producer, not a bond one -- it hunts whichever class the rotation has
    # left uncovered, so it works the same day equities or softs fall out.
    ("coverage_search_results.json", "hypotheses"),
    # THE TICK TAPE, AS CANDIDATES RATHER THAN AS A RANKING NUDGE. Until 2026-09-07 the moat's
    # entire contribution to research was `mined_ground.scan_moat`, which awards a symbol
    # MOAT_WEIGHT * days_of_tape -- a flat +36 against XAUUSD's 5233, or 0.7%. Attention is not a
    # hypothesis: it cannot be backtested, cannot pass a gate and cannot become a sleeve, so no
    # amount of tape could reach the money path through it. `moat_miner` proposes cells for the
    # families that already read the tape (liquidity_regime, orderflow_imbalance) and they face
    # the same ten gates as everything else here.
    ("moat_candidates.json", "hypotheses"),
    # Historical STATISTICAL_ONLY rejects re-stamped after a mechanism-map extension
    # (scripts/requeue_named_mechanisms.py). Merged when freshly rebuilt; hourly runs skip it
    # as stale once consumed -- a map extension re-opens gate 1, never any later gate.
    ("requeue_named.json", "hypotheses"),
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _pipeline_started_at() -> datetime | None:
    """Return this orchestrated run's lower freshness bound, if supplied.

    Manual/recovery invocations remain backwards compatible and may merge the durable corpus.
    The hourly orchestrator always supplies this value, making stale producer output ineligible.
    """
    raw = os.environ.get("QUANT_PIPELINE_STARTED_AT", "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"invalid QUANT_PIPELINE_STARTED_AT={raw!r}") from None
    return parsed.astimezone(UTC)


def _fresh_for_run(path: Path, started_at: datetime | None) -> bool:
    if started_at is None:
        return True
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return False
    # Filesystems and scp can round mtimes to whole seconds.
    return modified.timestamp() >= started_at.timestamp() - 2.0


def _identity(row: dict) -> str:
    """Dedup by what would actually be EXECUTED, not by label.

    Two rows describing the same symbol, family and parameters are one candidate however they are
    titled or whichever producer emitted them -- and letting a duplicate through twice would
    inflate the trial count and the apparent breadth at the same time.
    """
    params = row.get("params") or {}
    return json.dumps({
        "symbol": str(row.get("symbol") or row.get("sym") or ""),
        "family": str(row.get("family") or ""),
        "params": {k: params[k] for k in sorted(params)},
    }, sort_keys=True, default=str)


def tradeable_universe() -> dict[str, str]:
    """UPPERCASE -> the registry's own spelling, for every symbol the desk can actually replay.

    A symbol needs BOTH a registry entry (the broker quotes it) and an H1 parquet (a clock can
    replay it). The uppercase key exists because producers do not agree on casing: `broker_swaps`
    reads Fusion's symbol table and emits `ACCENTURE` where the registry and every parquet spell
    it `Accenture`.

    An unreadable registry returns EMPTY, and the caller then filters NOTHING -- losing this file
    must never silently shrink the docket to zero (L1.28a).
    """
    try:
        meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    uni = BASE / "data" / "universe"
    out: dict[str, str] = {}
    for k, v in meta.items():
        if not (uni / f"{k}_H1.parquet").exists():
            continue
        # TRADEABLE WHEN THE REGISTRY KNOWS, PERMITTED WHEN IT DOES NOT. Fusion offers 250
        # symbols and only 237 are SYMBOL_TRADE_MODE_FULL; the rest are CLOSE_ONLY and no new
        # position can be opened on them, so hunting them spends the sweep on cells that could
        # never trade. Rows written before `trade_mode` was recorded carry no flag, and those
        # are ALLOWED rather than dropped -- a registry that predates the field must not
        # silently collapse the docket to nothing (L1.28a). They tighten on the next fetch.
        if isinstance(v, dict) and v.get("tradeable") is False:
            continue
        out[str(k).upper()] = str(k)
    return out


def _ack(path: Path) -> None:
    """LINEAGE IS ACKNOWLEDGED, NEVER INFERRED (LAWS 7): the merge names every source docket it
    read by that docket's producer run id, so `compile_candidates -> merge_docket` is an observed
    edge. Guarded: a failure to record lineage may not stop the merge."""
    try:
        import sys as _sys
        root = str(BASE.parents[1])
        if root not in _sys.path:
            _sys.path.insert(0, root)
        from libs.ops.control_plane.lease import ack_artifact
        ack_artifact("leg:merge_docket", path)
    except Exception:
        pass


def _lease(path: Path) -> None:
    """The docket carries its own freshness lease and producer run id (sidecar), so the gauntlet
    can acknowledge THIS run of it and the control plane can say when it went stale."""
    try:
        import sys as _sys
        root = str(BASE.parents[1])
        if root not in _sys.path:
            _sys.path.insert(0, root)
        from libs.ops.control_plane.lease import stamp_sidecar
        stamp_sidecar(path, "leg:merge_docket", ttl="hourly", root=BASE.parents[1])
    except Exception:
        pass


def main() -> int:
    now = datetime.now(tz=UTC)
    # HUNT ONLY WHAT THE DESK CAN TRADE (principal, 2026-09-03: "limit all hunting to fusion
    # tradeable symbols only so all compute is used fr tradeable edges").
    #
    # MEASURED 2026-09-02: 3,934 of 23,465 docket cells -- 17% -- were on symbols Fusion does not
    # quote. They were minted, merged, ordered, and then refused at gate 0, having consumed the
    # sweep's ordering and reporting the whole way. Gate 0 refusing them is correct and is not
    # the same as never minting them: the budget they displaced was budget a testable cell did
    # not get, and 5,821 cells were deferred that same run for want of exactly that budget.
    #
    # Filtered HERE because the merge is the one funnel every producer flows through, so a
    # producer that starts emitting an untradeable symbol tomorrow is caught without editing it.
    tradeable = tradeable_universe()
    started_at = _pipeline_started_at()
    merged: dict[str, dict] = {}
    unrouted = 0
    untradeable = 0
    untradeable_syms: dict[str, int] = {}
    per_source: dict[str, int] = {}
    source_state: dict[str, str] = {}

    for name, key in SOURCES:
        source_path = HYP / name
        doc = _read(source_path)
        if doc is None:
            per_source[name] = -1          # ABSENT is distinct from empty; -1 says so
            source_state[name] = "ABSENT"
            continue
        _ack(source_path)
        if not _fresh_for_run(source_path, started_at):
            # A previous run's output remains immutable provenance, but it is not a discovery
            # from THIS run and must not be represented or retested as one.
            per_source[name] = -2
            source_state[name] = "STALE_SKIPPED"
            continue
        rows = doc if isinstance(doc, list) else (doc.get(key) if key else None)
        if not isinstance(rows, list):
            per_source[name] = 0
            source_state[name] = "MALFORMED_OR_EMPTY"
            continue
        kept = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_sym = str(row.get("symbol") or row.get("sym") or "")
            if not raw_sym:
                continue
            if tradeable:
                canon = tradeable.get(raw_sym.upper())
                if canon is None:
                    untradeable += 1
                    untradeable_syms[raw_sym] = untradeable_syms.get(raw_sym, 0) + 1
                    continue
                # CARRY THE REGISTRY'S SPELLING FORWARD. Everything downstream -- the frame
                # loader, the cache key, the certificate, the forward clock -- keys on this
                # string, so admitting a row under a producer's casing only moves the failure.
                if canon != raw_sym:
                    row = {**row, ("symbol" if row.get("symbol") else "sym"): canon}
            ident = _identity(row)
            if ident in merged:
                continue
            enriched = dict(row)
            # A ROW WITH NO FAMILY IS UNROUTABLE, NOT A BREAKOUT. Defaulting to the desk's
            # dominant family silently relabelled every family-less row as the one mechanism
            # the book is already 95% concentrated in -- the docket's own diversity destroyed
            # by a setdefault. Such a row is dropped and counted; a producer that stops naming
            # its family is a defect to see, not a breakout to test.
            if not enriched.get("family"):
                unrouted += 1
                continue
            enriched["producer"] = name
            merged[ident] = enriched
            kept += 1
        per_source[name] = kept
        source_state[name] = "FRESH"

    # NOTHING ABOUT SEARCH WIDTH TRAVELS WITH A ROW. An earlier revision copied the search's
    # trial count onto every hypothesis so `deflated_sharpe` would deflate against it -- making
    # the ten gates harsher than their sealed definition. That is an unsanctioned bar, merely
    # hidden inside the gate instead of sitting in front of it. Trial counts stay in the search's
    # own report, for audit, and reach no gate.

    # THE MECHANISM STAMP IS DERIVED HERE, FROM THE CURRENT MAP -- never trusted from a
    # producer. Discovered rows re-emitted from the banked corpus carried the stamps of the map
    # AS IT WAS when they were first mined; measured 2026-08-27: the behavioural-flow extension
    # named 1,285 features whose corpus rows still said STATISTICAL_ONLY, and the dedupe then
    # kept those stale stamps over freshly re-derived ones. One map, one derivation point, at
    # the last hop before the gauntlet -- a map extension reaches every candidate the same hour.
    try:
        from edge_search import mechanism_for_feature
        restamped = 0
        for row in merged.values():
            if row.get("family") != "discovered":
                continue
            feature = str((row.get("params") or {}).get("feature") or "")
            if not feature:
                continue
            status, note = mechanism_for_feature(feature)
            if status != row.get("mechanism_status"):
                restamped += 1
            row["mechanism_status"], row["mechanism_note"] = status, note
        if restamped:
            print(f"   mechanism map: {restamped} discovered row(s) re-stamped under the "
                  f"current map")
    except ImportError as exc:
        print(f"   mechanism map unavailable ({exc}); producer stamps carried unchanged")

    # THE DOCKET IS A BANK, NOT A SNAPSHOT (principal 2026-08-28: "test as many cells as
    # possible hourly for max certificates"). The freshness contract correctly decides which
    # SOURCES count as this run's discovery -- but it was also deciding the whole docket, so
    # the moment a searcher artifact aged past the pipeline start the docket collapsed from
    # ~6,700 cells to ~460 and the gauntlet had almost nothing to judge (measured 2026-08-28:
    # three sweeps in a row loaded 459/460/460 while 6,024 known candidates sat on disk).
    # Judging a cell again is idempotent and nearly free -- the per-cell series cache reloads
    # it -- so the docket now UNIONS this run's fresh rows with everything already banked,
    # deduped by executable identity. `first_seen` is preserved so no stale row can ever be
    # counted as a fresh discovery; freshness still governs provenance, never capacity.
    banked = _read(TARGET)
    readmitted = 0
    if isinstance(banked, list):
        for row in banked:
            if not isinstance(row, dict):
                continue
            ident = _identity(row)
            if ident in merged:
                merged[ident].setdefault("first_seen", row.get("first_seen")
                                         or row.get("merged_at") or now.isoformat())
                continue
            # THE BANK MUST BE FILTERED TOO. Without this, every untradeable row ever minted is
            # re-admitted from the bank on every run and the filter above only catches the ones
            # arriving fresh -- measured, 262 dropped against 3,934 already banked. A docket bank
            # is a memory of what was proposed, not a licence to re-propose what cannot trade.
            bank_sym = str(row.get("symbol") or row.get("sym") or "")
            if tradeable and bank_sym:
                bank_canon = tradeable.get(bank_sym.upper())
                if bank_canon is None:
                    untradeable += 1
                    untradeable_syms[bank_sym] = untradeable_syms.get(bank_sym, 0) + 1
                    continue
                if bank_canon != bank_sym:
                    row = {**row,
                           ("symbol" if row.get("symbol") else "sym"): bank_canon}
            row.setdefault("first_seen", row.get("merged_at") or now.isoformat())
            row["banked"] = True
            merged[ident] = row
            readmitted += 1
    for row in merged.values():
        row.setdefault("first_seen", now.isoformat(timespec="seconds"))
    if readmitted:
        print(f"   docket bank: {readmitted} previously-known candidate(s) re-admitted "
              f"(idempotent re-judging; freshness still governs provenance)")

    if unrouted:
        print(f"   {unrouted} row(s) dropped as UNROUTABLE (no family named) -- never "
              f"relabelled as the dominant family")

    if untradeable:
        top = sorted(untradeable_syms.items(), key=lambda kv: -kv[1])[:8]
        print(f"   {untradeable} row(s) dropped as UNTRADEABLE across "
              f"{len(untradeable_syms)} symbol(s) Fusion does not quote -- the sweep's budget "
              f"now goes to cells that can certify: {dict(top)}")
    elif not tradeable:
        print("   universe registry unreadable: NOTHING filtered by tradeability this run "
              "(UNMEASURED, not clean -- the docket may carry symbols the desk cannot trade)")

    # THE JUDGE IS SCARCE AND A BANNED FAMILY CANNOT REPAY IT (principal 2026-09-23). Measured on
    # the box from 120,000 gate verdicts: `discovered` consumed 22,009 judgements (~18% of recent
    # capacity) and passed ZERO -- and it is refused at BOTH live doors by
    # `mt5desk/live_policy.py`, so every one of those gate-seconds bought an outcome the desk has
    # already forbidden. The rows are NOT deleted and the miners are NOT restrained: they move to
    # the STUDY BANK with the ban as the recorded reason, and what stops is the spending.
    banned_families = live_banned_families()
    rows_out: list[dict[str, Any]] = []
    study: list[dict[str, Any]] = []
    for row in merged.values():
        (study if str(row.get("family") or "") in banned_families else rows_out).append(row)
    if study:
        stamp = now.isoformat(timespec="seconds")
        for row in study:
            row["judging_status"] = "STUDY_ONLY"
            row["judging_reason"] = (
                f"family {row.get('family')!r} is banned from live capital by the principal's "
                "order and refused at both live doors (mt5desk/live_policy.py "
                "DEFAULT_BANNED_FAMILIES); it cannot reach the book even if it passes, so the "
                "scarce judge is not spent on it. Mining is unrestricted and the rows stay here "
                "for study")
            row["routed_to_study_at"] = stamp
        STUDY_BANK.parent.mkdir(parents=True, exist_ok=True)
        STUDY_BANK.write_text(json.dumps(study, indent=1, default=str), "utf-8")
        print(f"   study bank: {len(study)} row(s) of banned families "
              f"{sorted(banned_families)} routed OUT of the judging docket (kept, never "
              f"deleted) -> {STUDY_BANK.name}")

    # ORDER IS SELECTION: the gauntlet takes this file in order under a bar budget, so a family
    # at the tail is not "lower priority", it is never judged at all.
    #
    # COVERAGE, NOT ROTATION (principal 2026-09-23: "the judge should test 100 percent of what
    # this desk ever mines, every hour"). `research/judge_coverage.py` allocates the hour by
    # UNJUDGED BACKLOG -- an equal floor to every family holding one, then the remainder in
    # proportion -- and interleaves the families so EVERY PREFIX of this docket is
    # family-balanced. Whatever slice the judge's budget reaches, that slice holds every family
    # with backlog. Nothing is dropped; `breadth_order` remains the fallback, and a failure in
    # the allocator can only cost the ORDER, never a row.
    judged = judged_by_family()
    _rl_fam, _rl_why = alpha_rl_family_values()
    print(f"   alpha_rl family values: {_rl_why}")
    coverage: dict[str, Any] = {}
    try:
        # Run as `python research/merge_hypotheses.py`, sys.path[0] is the research directory
        # itself, so the desk root has to be on the path before a sibling package import works.
        import sys as _sys
        if str(BASE) not in _sys.path:
            _sys.path.insert(0, str(BASE))
        from research.judge_coverage import order_docket
        rows_out, coverage = order_docket(rows_out)
    except Exception as exc:
        print(f"   judge coverage unavailable ({type(exc).__name__}: {exc}) -- falling back to "
              f"least-judged-family order")
        if judged:
            rows_out = breadth_order(rows_out, judged)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # NEVER SHRINK THE DOCKET TO NOTHING. The freshness contract makes every source STALE_SKIPPED
    # on any run where producers have not written yet, and this merge then emitted an EMPTY file
    # -- which the pipeline shipped, and on which the gauntlet wiped the authority file to n=0.
    # An hourly cycle where "the searcher was slow this hour" cascades into "all certificates
    # revoked" is not a freshness contract, it is a self-destruct. If this run gathered nothing
    # fresh, the existing docket STANDS: yesterday's candidates are still candidates.
    if not rows_out:
        prior = _read(TARGET)
        if isinstance(prior, list) and prior:
            print(f"merge: 0 fresh rows this run -- PRESERVING the existing docket of "
                  f"{len(prior)} candidate(s) rather than shipping an empty file downstream.")
            return 0
    TARGET.write_text(json.dumps(rows_out, indent=1, default=str), "utf-8")
    _lease(TARGET)
    (HYP / "merge_report.json").write_text(json.dumps({
        "merged_at": now.isoformat(timespec="seconds"),
        "pipeline_started_at": started_at.isoformat(timespec="seconds") if started_at else None,
        "per_source": per_source, "source_state": source_state, "total": len(rows_out),
        "families": {f: sum(1 for r in rows_out if r.get("family") == f)
                     for f in sorted({str(r.get("family")) for r in rows_out})},
        # G4: what the RL agent's table said about families THIS hour, read whichever ordering
        # path won, so "the agent's opinion was consulted" is a checkable claim and not a code
        # path nobody can see from the outside.
        "alpha_rl": {"values": {k: round(v, 6) for k, v in _rl_fam.items()}, "basis": _rl_why,
                     "used_by": "breadth_order tie-break within a spend tier"},
        "study_bank": {"rows": len(study), "families": sorted(banned_families),
                       "path": str(STUDY_BANK),
                       "why": "banned from live capital, so a gate-second spent here buys an "
                              "outcome the desk has already forbidden; kept for study"},
        "judge_order": {"basis": ("unjudged backlog per family: an equal floor to every family "
                                  "holding one, the remainder in proportion, interleaved so "
                                  "every prefix of the docket is family-balanced"),
                        "families_ordered": len({str(r.get("family")) for r in rows_out}),
                        "applied": bool(coverage.get("families")),
                        "fallback_basis": "judgements already spent per docket row, least first",
                        "coverage": {k: (coverage.get("totals") or {}).get(k) for k in
                                     ("families_with_backlog", "families_queued",
                                      "families_starved", "unjudged_total",
                                      "capacity_measured")} if coverage else {},
                        "report": "desks/mt5/reports/JUDGE_COVERAGE.json"},
        "note": ("no threshold applied here (L1.60) -- every candidate of a family that CAN "
                 "reach live capital reaches the ten-gate gauntlet, which is the only arbiter; "
                 "a live-banned family is routed to the study bank, never judged and never "
                 "deleted"),
    }, indent=1), "utf-8")

    print(f"merged hypotheses: {len(rows_out)} unique candidate(s) -> {TARGET.name}")
    for name, n in per_source.items():
        state = source_state[name] if n < 0 else f"{n} new ({source_state[name]})"
        print(f"   {name:34} {state}")
    fam = {}
    for r in rows_out:
        fam[str(r.get("family"))] = fam.get(str(r.get("family")), 0) + 1
    print(f"   families going to the gauntlet: {fam}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
