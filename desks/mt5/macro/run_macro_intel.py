"""THE MACRO INTELLIGENCE ORGAN -- one pass, or perpetual under the supervisor.

    python3 -m macro.run_macro_intel            # one pass, from desks/mt5
    python3 -m macro.run_macro_intel --loop     # perpetual (the supervised form)
    python3 -m macro.run_macro_intel --report   # state and coverage only, no fetch

WHAT ONE PASS DOES, in the order that keeps the learning honest.

    1. read       every registered source; each failure is isolated and counted
    2. score      classify, credit, price, express, and write the ledger row -- EVERY item,
                  including the ones that will never be tradeable, because the record is the
                  asset
    3. discover   promote coherent clusters of unclassified items into new categories
    4. attribute  mark the homework of events whose horizon has passed
    5. learn      refit credibility, factor loadings and the priced calibration from the marked
                  homework
    6. decide     for the highest-importance item, ask `interrupt.should_fire` -- and almost
                  always be told no, correctly
    7. report     coverage, blind spots, and what the layer currently cannot do

STEP 5 IS THE ONE THAT MAKES THIS DIFFERENT FROM A NEWS BOT, and it is why attribution runs
before learning rather than as an afterthought. Adding a source without step 5 produces more rows
nobody learns from.

WHAT A PASS COSTS AND WHAT IT IS WORTH. The rent line is `ModuleRent = E[logW] with - E[logW]
without`, measured forward, and today it is honestly UNMEASURED: the layer has never sized a
position, so there is no with-minus-without to measure. The ledger row count and the replay
clearance list are the leading indicators until then, and the report says so rather than
manufacturing a number.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import (  # noqa: E402
    allocator_price, attribution, expression, factors, interrupt, replay, sources,
)
from macro.assess import assess, recent_vectors  # noqa: E402
from macro.credibility import CredibilityModel  # noqa: E402
from macro.ledger import MACRO_DIR, EventLedger, write_json_atomic  # noqa: E402
from macro.prices import ParquetPriceReader  # noqa: E402
from macro.schema import Status, now_iso, parse_ts  # noqa: E402
from macro.taxonomy import Taxonomy  # noqa: E402

REPORT_PATH = MACRO_DIR / "MACRO_INTEL.json"
LOG_PATH = _DESK / "logs" / "macro_intel.log"

#: Seconds between passes in the perpetual form. Sixty, to match the allocator's fast clock:
#: reading more often than the consumer can act adds latency nowhere useful.
LOOP_SLEEP_S = 60


def log(msg: str) -> None:
    line = f"{now_iso()} {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def one_pass(*, ledger: EventLedger | None = None, fetch: bool = True,
             src: list[Any] | None = None) -> dict[str, Any]:
    """One full cycle. Never raises on a data gap: every refusal is a reported reason."""
    led = ledger or EventLedger()
    universe = expression.load_universe()
    aliases = expression.load_aliases(universe)
    reader = ParquetPriceReader()
    basis = factors.load_basis()
    tax = Taxonomy().load()
    cred = CredibilityModel().load()

    exposures: list[expression.Exposure] = []
    try:
        raw = json.loads((MACRO_DIR / "exposures.json").read_text("utf-8"))
        for row in raw.get("exposures") or []:
            exposures.append(expression.Exposure(
                str(row["symbol"]), str(row["driver"]), float(row["beta"]), float(row["se"]),
                float(row["ci_lo"]), float(row["ci_hi"]), int(row["n"]), int(row["cells"]),
                bool(row["admitted"]), str(row["status"])))
    except (OSError, ValueError, KeyError, TypeError):
        exposures = []

    # -- replay clearance BEFORE scoring, so nothing can be authorised by a stale verdict ------
    rep = replay.replay(led.records(), reader, replay.default_scorer(), strict=False)
    cleared, refused = replay.clearance(rep)

    # -- ATTRIBUTE AND LEARN BEFORE SCORING. Mark the homework of events whose horizon has
    # already closed -- old events, untouched by anything arriving this pass -- and score today's
    # items with what that taught. The other order would make every pass score its arrivals on
    # yesterday's understanding and only learn afterwards, which throws away a full cycle of
    # improvement for no reason. It also closes the loop for the decay half-life, which nothing
    # else in the package measures and which the interrupt gate depends on.
    horizon_cut = time.time() - attribution.DEFAULT_HORIZON_S
    due = [r for r in led.records()
           if (dt := parse_ts(r.received_at)) is not None and dt.timestamp() <= horizon_cut]
    attributions = [attribution.attribute(r, reader, basis=basis) for r in due[-500:]]
    fb = attribution.feedback(attributions)
    decay_samples = fb["decay_samples"]
    cred.fit(fb["source_outcomes"],
             tier_of={r.source_id: r.source_tier for r in led.records()})
    cred.save()

    mult = factors.MultiplicityLedger()
    loadings: dict[str, list[dict[str, Any]]] = {}
    for cat, samples in fb["factor_samples"].items():
        rows = factors.category_loadings(samples, category=cat, ledger=mult)
        loadings[cat] = [row.__dict__ for row in rows]
    mult.save()

    # -- 1 & 2: read and score --------------------------------------------------------------
    srcs = list(src if src is not None else (sources.default_sources() if fetch else []))
    known = recent_vectors(led)
    n_new = 0
    n_seen = 0
    failures: list[str] = []
    scored: list[Any] = []
    for s in srcs:
        try:
            items = s.fetch()
        except Exception as ex:
            failures.append(f"{getattr(s, 'source_id', '?')}: {ex!r}")
            continue
        for item in items:
            n_seen += 1
            if item.event_id in led.seen():
                continue
            a = assess(item, taxonomy=tax, credibility=cred, ledger=led, reader=reader,
                       basis=basis, exposures=exposures, universe=universe, aliases=aliases,
                       source_tier=getattr(s, "tier", "UNKNOWN"),
                       source_licence=getattr(s, "licence", "UNDECLARED"),
                       source_terms=getattr(s, "terms_url", ""),
                       robots_ok=getattr(s, "robots_ok", None),
                       retrieval=getattr(s, "retrieval", "unknown"),
                       replayed_categories=cleared, recent_vectors=known,
                       decay_samples=decay_samples)
            if led.append(a.record):
                n_new += 1
                scored.append(a)

    # -- 3: emergence ------------------------------------------------------------------------
    pool = [(r.event_id, f"{r.title}. {r.body_excerpt}") for r in led.records()
            if r.category == "UNCLASSIFIED"]
    minted = tax.discover(pool)
    tax.fit((r.category, f"{r.title}. {r.body_excerpt}") for r in led.records()
            if r.category != "UNCLASSIFIED")
    tax.save()

    # -- 6: the interrupt decision ------------------------------------------------------------
    decision = None
    top = max(scored, key=lambda a: a.record.importance, default=None)
    # THE HOOK IS LANDED (2026-09-05). This read `expected_gain_per_day=None, expected_turnover=
    # 0.0` with the note "None until the hook is landed" -- and None is HOLD, so every interrupt
    # decision this layer ever made died at the same gate, whatever the event was. The allocator
    # already computed both numbers on every normal pass and simply never published the gain;
    # `allocator_price` reads its own solve rather than estimating anything here.
    gain_per_day, turnover, price_why = allocator_price.price_the_move()
    if top is not None:
        d = interrupt.should_fire(
            importance=top.record.importance,
            importance_status=top.record.importance_status,
            unpriced_fraction=top.priced.unpriced_fraction,
            decay_half_life_s=top.record.decay_half_life_s,
            capital_authority=top.record.capital_authority,
            expected_gain_per_day=gain_per_day, expected_turnover=turnover,
            history=interrupt.history_from_log())
        decision = {"fire": d.fire, "reason": d.reason, "detail": d.detail,
                    "event_id": top.record.event_id, "priced_by_allocator": price_why}
        if d.fire:
            interrupt.request(event_ids=[top.record.event_id], decision=d,
                              importance=top.record.importance,
                              unpriced_fraction=top.priced.unpriced_fraction)

    payload = {
        "at": now_iso(),
        "ledger": led.summary(),
        "items_seen": n_seen, "rows_written": n_new,
        "source_failures": failures,
        "categories_minted": [c.label for c in minted],
        "taxonomy": tax.report(),
        "credibility": cred.report(),
        "coverage": sources.coverage(srcs if srcs else None),
        "price_coverage": reader.coverage(),
        "factor_basis": {"status": basis.status, "n_obs": basis.n_obs,
                         "factors": list(basis.loadings), "note": basis.note},
        "exposures_loaded": len(exposures),
        "replay": replay.coverage(led, rep),
        "replay_cleared": cleared, "replay_refused": refused,
        "attribution": attribution.report(attributions, led),
        "category_loadings": loadings,
        "interrupt": decision,
        "rent": {
            "module": "macro_intel",
            "rule": "E[logW] with - E[logW] without, measured forward",
            "value": None,
            "status": Status.UNMEASURED,
            "why": ("the layer has never sized a position -- no category has passed replay "
                    "clearance -- so there is no with-minus-without to measure. Ledger rows and "
                    "replay clearance are the leading indicators until there is."),
        },
    }
    write_json_atomic(REPORT_PATH, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="macro & event intelligence organ")
    ap.add_argument("--loop", action="store_true", help="run forever (the supervised form)")
    ap.add_argument("--report", action="store_true", help="state and coverage only, no fetch")
    ap.add_argument("--sleep", type=float, default=LOOP_SLEEP_S)
    args = ap.parse_args(argv)

    if args.report:
        out = one_pass(fetch=False)
        print(json.dumps({k: out[k] for k in
                          ("ledger", "coverage", "price_coverage", "replay", "rent")},
                         indent=1, default=str))
        return 0
    if not args.loop:
        out = one_pass()
        log(f"pass: {out['rows_written']} new rows of {out['items_seen']} items; "
            f"cleared={out['replay_cleared']}")
        return 0
    log("macro intel organ: perpetual")
    while True:
        try:
            out = one_pass()
            log(f"pass: {out['rows_written']} new of {out['items_seen']}; "
                f"failures={len(out['source_failures'])}")
        except Exception as ex:
            log(f"pass failed: {ex!r}")
        time.sleep(max(5.0, args.sleep))


if __name__ == "__main__":
    sys.exit(main())
