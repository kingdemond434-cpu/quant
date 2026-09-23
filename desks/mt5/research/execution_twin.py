"""The hourly Execution Digital Twin: live intents become simulation test cases, every hour.

THE PRINCIPAL'S ORDER. "Every live intent becomes a simulation test case. Compare PredictedFill
vs ActualFill ... Collect broker-specific empirical distributions continuously. This is a Fusion
execution moat public frameworks cannot hand you." `libs.execution.digital_twin` is the pure
arithmetic; this organ is the clock, the ledgers and the dataset. Once an hour it reads the three
ledgers the gateway already writes, joins them into cases, appends the NEW or newly RESOLVED
cases to `data/execution_twin_cases.jsonl` -- the private Fusion quote/spread/fill/reject/
latency/slippage history the principal wants kept -- and writes `reports/EXECUTION_TWIN.json`:
the calibration tables, the per-symbol recalibration the simulator should apply, and the
verdicts, every one with its n.

THE WATERMARK IS THE LEDGERS' OWN LENGTH. The three ledgers are append-only, so the row counts
in `data/execution_twin_state.json` say whether anything new can exist; when nothing grew the
pass returns UNCHANGED and touches no file, so an hourly re-run never double counts. When
something grew, the join is rebuilt in full (a few thousand rows; cheap) rather than
incrementally, because a case can RESOLVE after it was first written -- a resting bracket's
deal arrives when the position closes, hours or days after the intent -- and only a full rebuild
sees that. A case is appended to the dataset when its key is new or its `resolution` changed, so
the file is append-only and its last row per key is the truth.

WHAT IT DOES NOT DO. It fabricates nothing: with no intent ledger on the box it returns
UNMEASURED with the reason and writes nothing (this research container has no ledgers; the
trading box does). It applies nothing: the recalibration it reports is consumed by nobody yet --
`engine.Costs` and `external_gauntlet.costs_for` still charge the registry's spread with a
hand-set `mult` -- and that wiring is the next handoff, named in the report under `consumers`.

THE FILL CORPUS (2026-09-05, the principal's second order). "Turn every live fill into
proprietary data ... for every execution retain full market state, reason for entry, strategy
DNA, posterior edge estimate, predicted distribution, spread, slippage, regime, cross-asset
state, MAE, MFE, path after entry, exit reason, alternative exits, counterfactual entries,
realized R, prediction error." That row is a JOIN, not a new capture point: this pass already
holds the intent-versus-fill half, the decision ledger holds the reason and the DNA, the
decision dataset holds the world and the priced alternatives, `excursions.jsonl` holds MAE and
MFE, and the tick tape holds the post-fill path. `libs.execution.fill_corpus` assembles them
into one append-only record per execution and reports, field by field, what is NOT yet captured
-- because an unrecorded fill cannot be recovered later and a capture gap is only fixable
forward.

ON TOP OF THE CORPUS, THREE MEASUREMENTS, EVERY ONE GATED. `alpha_capture` (realised edge over
predicted frictionless edge, per sleeve, session and symbol, plus adverse selection),
`execution_choice_model` (E[post-fill alpha | style, spread, vol, momentum, session]) and
`meta_label` (SKIP / 0.5x / 1x / 1.5x / MAX). The last two are HARNESSES first: each computes
the sample its own power calculation demands and reports UNMEASURED with the shortfall until the
corpus reaches it. Neither is wired to anything that sends an order, and the meta-labeler can
never re-admit a signal a gate refused -- it is a sizing refinement strictly downstream of
admission, and its unfitted state is a no-op on the upside.

    python3 research/execution_twin.py [--budget-s N] [--symbols XAUUSD,EURUSD]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import execution_registry  # noqa: E402

from libs.execution import alpha_capture as ac  # noqa: E402
from libs.execution import digital_twin as dt  # noqa: E402
from libs.execution import execution_choice_model as ecm  # noqa: E402
from libs.execution import fill_corpus as fc  # noqa: E402
from libs.execution import meta_label as ml  # noqa: E402

#: The gateway's three ledgers (declared on the gateway node of the capability graph).
INTENTS = BASE / "data" / "order_intents.jsonl"
OUTCOMES = BASE / "data" / "execution_algo_outcomes.jsonl"
LEDGER = BASE / "data" / "live_ledger.jsonl"
#: The registry the simulator prices from, for the spread it charges per symbol.
UNIVERSE = BASE / "data" / "universe" / "universe.json"
#: This organ's own: the watermark, the private dataset, the report.
STATE = BASE / "data" / "execution_twin_state.json"
CASES = BASE / "data" / "execution_twin_cases.jsonl"
REPORT = BASE / "reports" / "EXECUTION_TWIN.json"
#: THE FILL CORPUS and the ledgers it joins. All five are written by organs that already own
#: them; this pass only reads them and writes the joined row.
CORPUS = BASE / "data" / "fill_corpus.jsonl"
DECISIONS = BASE / "data" / "decision_ledger.jsonl"
DATASET = BASE / "data" / "decision_dataset.jsonl"
EXCURSIONS = BASE / "data" / "excursions.jsonl"

#: Corpus columns the meta-labeler is allowed to scan. Kept SHORT and declared here rather than
#: discovered from the row, because the Bonferroni charge is linear in the number of columns
#: looked at and a scan that quietly widens is a scan whose gate quietly loosens.
META_LABEL_FEATURES: tuple[str, ...] = (
    "posterior_edge_r", "spread_frac_at_decision", "vol_frac", "momentum_z", "slip_r",
    "predicted_p_fill", "latency_decision_to_send_ms",
)

YIELD_PREFIX = "YIELD "
#: The counters this organ yields, by name, for the hourly pass.
YIELD_KEYS = ("cases_joined", "symbols_calibrated", "symbols_unmeasured")

#: Where the recalibration should be applied, stated in the report so a reader of the report
#: knows the number is advisory until that wiring exists.
CONSUMERS: dict[str, str] = {
    "desks/mt5/mt5desk/engine.py": ("Costs.from_symbol(meta, mult=...): multiply `mult` by the "
                                    "symbol's slippage_multiplier"),
    "desks/mt5/scripts/external_gauntlet.py": ("costs_for(sym, meta, mult=...): same multiplier "
                                               "on the gauntlet's own call"),
    "status": "NOT WIRED -- the report is advisory until a consumer reads it",
}


def _rows(path: Path) -> list[dict[str, Any]]:
    """Every JSON row in an append-only ledger; a torn final line is skipped, never fatal."""
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(x: Any) -> float | None:
    """A positive finite number or None; registry fields are hand-maintained and can be absent."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v and v not in (float("inf"), float("-inf")) else None


def sim_costs(cases: list[dt.TwinCase], universe: dict[str, Any] | None = None
              ) -> dict[str, dt.SimCost]:
    """What the simulator assumes per symbol, on the twin's axis.

    `engine.run_backtest` fills at the bar open or the trigger with no slip and charges the
    registry's `median_spread_pts` (x `mult`) plus commission; so slip 0.0, p_fill 1.0, and the
    round-trip spread as a fraction of price is `median_spread_pts x point / price` with `point`
    the registry's `tick_size` or 10^-digits (MT5's definition of a point) and `price` the mean
    reference quote of the symbol's own cases. A symbol the registry does not know gets no
    spread_frac, and its correction is reported as slip to add rather than as a multiplier.
    """
    uni = universe if universe is not None else _read_json(UNIVERSE)
    out: dict[str, dt.SimCost] = {}
    by: dict[str, list[float]] = {}
    for c in cases:
        by.setdefault(c.symbol, []).append(c.price_ref)
    for sym, prices in by.items():
        meta = uni.get(sym) if isinstance(uni.get(sym), dict) else {}
        pts = _num(meta.get("median_spread_pts"))
        point = _num(meta.get("tick_size"))
        digits = _num(meta.get("digits"))
        if point is None and digits is not None:
            point = 10.0 ** (-int(digits))
        price = sum(prices) / len(prices) if prices else 0.0
        spread_frac = (pts * point / price if pts is not None and point is not None
                       and price > 0 else None)
        out[sym] = dt.SimCost(slip_frac=0.0, p_fill=1.0, spread_frac=spread_frac)
    return out


def _append_cases(cases: list[dt.TwinCase], path: Path) -> int:
    """Append cases whose key is new or whose resolution changed since the last stored row.
    Returns how many rows were appended -- the hour's donation to the private dataset."""
    last: dict[str, str] = {}
    for r in _rows(path):
        k = str(r.get("intent_id") or "")
        if k:
            last[k] = dt.case_from_row(r).resolution
    new = [c for c in cases if last.get(c.intent_id) != c.resolution]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for c in new:
                f.write(json.dumps(c.to_row(), default=str) + "\n")
    return len(new)


# --------------------------------------------------------------------------- the fill corpus
def _when(x: Any) -> datetime | None:
    """A ledger timestamp as an aware UTC datetime, or None. Naive strings are read as UTC --
    every ledger on this desk writes UTC, and guessing a local zone would move a markout's t0."""
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=UTC)
    if not isinstance(x, str) or not x.strip():
        return None
    try:
        d = datetime.fromisoformat(x.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _tickets(intents: list[dict[str, Any]], cases: list[dt.TwinCase]) -> dict[str, int]:
    """intent_id -> broker ticket. The deal ledger joins on the ticket and a `TwinCase` does not
    carry one, so without this map every corpus row's EXIT half would be empty.

    Two rules, mirroring `digital_twin.join_cases` exactly: an intent that carries an explicit
    `intent_id` is looked up by it; a synthetic id ends in `|<ticket>` by construction, so the
    tail is the ticket. A tail that is not an integer yields nothing rather than a guess.
    """
    explicit = {str(r.get("intent_id")): r.get("ticket") for r in intents if r.get("intent_id")}
    out: dict[str, int] = {}
    for c in cases:
        raw = explicit.get(c.intent_id)
        if raw is None:
            tail = c.intent_id.rsplit("|", 1)[-1]
            raw = tail if tail.lstrip("-").isdigit() else None
        try:
            if raw is not None and not isinstance(raw, bool):
                out[c.intent_id] = int(raw)
        except (TypeError, ValueError):
            continue
    return out


def _tape_markouts(cases: list[dt.TwinCase], tickets: dict[str, int],
                   deals: list[dict[str, Any]] | None) -> tuple[dict[str, dict[str, Any]], str]:
    """Post-fill markouts, MAE, MFE and the sampled path, from the tick tape. ({}, why) if none.

    A MARKOUT NEEDS A REAL FILL TIMESTAMP, and only a deal row carries one. Approximating it from
    the intent time would be fine at five minutes and meaningless at one second, which is exactly
    the horizon adverse selection lives on -- so a case with no deal contributes nothing here and
    is reported as a capture gap instead. The tape is READ ONLY, through `recorders.tape_store`,
    and its absence is a reason, never an exception: this organ must keep running on a container
    that has no tape.
    """
    if not deals:
        return {}, "no deal ledger: no fill carries a timestamp a markout can start from"
    try:
        from recorders.tape_store import TapeStore
        from recorders.tick_recorder import DEFAULT_TAPE_ROOT
    except Exception as exc:
        return {}, f"tick tape unavailable ({type(exc).__name__}: {exc})"
    store = TapeStore(Path(DEFAULT_TAPE_ROOT))
    have = set(store.symbols())
    if not have:
        return {}, f"tick tape at {store.root} holds no symbol-days yet"
    by_ticket = {t: r for r in deals if (t := r.get("order")) is not None}
    out: dict[str, dict[str, Any]] = {}
    day_cache: dict[tuple[str, str], Any] = {}
    for c in cases:
        tk = tickets.get(c.intent_id)
        d = by_ticket.get(tk) if tk is not None else None
        if d is None or c.symbol not in have or c.stop_frac is None or c.stop_frac <= 0:
            continue
        t0 = _when(d.get("entry_time") or d.get("time"))
        px = d.get("entry_price") if d.get("entry_price") is not None else d.get("fill_price")
        if t0 is None or px is None:
            continue
        day = t0.date().isoformat()
        key = (c.symbol, day)
        if key not in day_cache:
            try:
                day_cache[key] = store.read_day(c.symbol, day)
            except Exception:
                day_cache[key] = None
        df = day_cache[key]
        if df is None or getattr(df, "empty", True):
            continue
        stop_px = float(c.stop_frac) * float(c.price_ref)
        times = df["time_msc"].astype("int64").tolist()
        bid, ask = df["bid"].tolist(), df["ask"].tolist()
        fill_ms = t0.timestamp() * 1000.0
        row: dict[str, Any] = {"source": f"tape:{store.root.name}", "fill_time": t0.isoformat()}
        row.update(fc.markouts_from_ticks(times, bid, ask, fill_ms=fill_ms,
                                          fill_price=float(px), direction=c.direction,
                                          stop_distance=stop_px))
        t1 = _when(d.get("exit_time"))
        row.update(fc.excursions_from_ticks(
            times, bid, ask, fill_ms=fill_ms,
            exit_ms=(t1.timestamp() * 1000.0 if t1 is not None else None),
            fill_price=float(px), direction=c.direction, stop_distance=stop_px))
        out[c.intent_id] = row
    return out, ("" if out else "no fill fell inside a recorded symbol-day of the tape")


def _append_corpus(records: list[fc.FillRecord], path: Path) -> int:
    """Append corpus rows whose key is new or whose resolution changed. Append-only, last row
    per key is the truth -- the same rule the case dataset follows, for the same reason: a fill's
    exit, its excursions and its counterfactuals all arrive AFTER the fill did."""
    last: dict[str, str] = {}
    for r in _rows(path):
        rec = fc.record_from_row(r)
        if rec.key:
            last[rec.key] = rec.resolution
    new = [r for r in records if last.get(r.key) != r.resolution]
    return fc.append_rows(path, new) if new else 0


def _corpus_section(cases: list[dt.TwinCase], intents: list[dict[str, Any]],
                    deals: list[dict[str, Any]] | None, write: bool
                    ) -> tuple[dict[str, Any], list[fc.FillRecord]]:
    """Build the hour's corpus rows, append the new ones, and report what they do and do not
    carry. Returns (the completeness report, the RESOLVED records) so the pass reads the corpus
    once. Every input ledger is optional: an absent one costs columns, never the pass."""
    tickets = _tickets(intents, cases)
    marks, mark_why = _tape_markouts(cases, tickets, deals)
    records = fc.build_records(
        cases, decisions=_rows(DECISIONS), deals=deals or [],
        dataset_rows=_rows(DATASET), excursions=_rows(EXCURSIONS),
        markouts=marks, tickets=tickets)
    appended = _append_corpus(records, CORPUS) if write else 0
    # THE CORPUS IS READ ONCE PER PASS and the resolved records are handed back with the report,
    # so the capture ratio and the two models do not each re-read and re-parse the file. A pass
    # that reads its own dataset three times gets slower exactly as the asset gets valuable.
    latest: dict[str, fc.FillRecord] = {}
    for r in _rows(CORPUS):
        rec = fc.record_from_row(r)
        latest[rec.key] = rec                            # append-only: the last row per key wins
    resolved = list(latest.values()) or records
    comp = fc.completeness(resolved)
    comp.update({"path": str(CORPUS), "appended_this_pass": appended,
                 "built_this_pass": len(records), "markouts": {
                     "n": len(marks), "why": mark_why,
                     "reads_today": ("TapeStore.read_day(symbol, day) -> DataFrame"
                                     "[time_msc, bid, ask] in PRICE units. Works; this is what "
                                     "the markouts above came from."),
                     "wants": [
                         # THE TAPE HANDOFF, stated in the report so the recorder's owner can see
                         # what the corpus needs rather than being told in a message nobody keeps.
                         "read_window(symbol, from_ms, to_ms) -> the same frame for a SLICE. A "
                         "markout needs [fill, fill+5min]; decoding a whole symbol-day per fill "
                         "is the difference between seconds and minutes once fills are frequent.",
                         "covers(symbol, from_ms, to_ms) -> bool, true only when no gap row "
                         "overlaps the window. Without it a markout is silently computed ACROSS "
                         "a RECORDER_DOWN hole and reads as a real price move.",
                         "the aggressor flag on each tick (MT5 TICK_FLAG_BUY/SELL) is already in "
                         "`flags`; libs/execution/passive_impact.py needs one branch on it and "
                         "nothing further from the recorder.",
                     ]}})
    return comp, resolved


def _models_section(records: list[fc.FillRecord]) -> dict[str, Any]:
    """The two gated models: the conditional execution choice and the meta-labeler.

    BOTH ARE HARNESS-FIRST. Each reports its fitted surface when the corpus supports one and
    UNMEASURED with the exact shortfall when it does not, and `requirements` prices every
    conditioning tier so "not yet" comes with a number the desk can plan against.
    """
    surface = ecm.fit(records)
    labeler = ml.fit(records, features=META_LABEL_FEATURES)
    return {
        "execution_choice": {
            **surface.to_row(),
            "requirements": ecm.requirements(),
            "wired_to": ("NOTHING. mt5desk/execution_policy.choose remains the only chooser on "
                         "the money path; this surface is advisory until its own gate opens and "
                         "a consumer is named here."),
        },
        "meta_label": {
            **labeler.to_row(),
            "requirements": ml.requirements(n_features=len(META_LABEL_FEATURES)),
            "wired_to": ("NOTHING. It cannot re-admit a signal a gate refused (gate_passed=False "
                         "returns SKIP at 0.0x unconditionally) and it cannot upsize while "
                         "UNMEASURED, so an unfitted labeler is a no-op on the upside."),
        },
    }


def _gaps(cases: list[dt.TwinCase], n_outcomes: int) -> list[str]:
    """What the ledgers do not carry yet, measured on this hour's cases -- the handoff list."""
    gaps: list[str] = []
    if not cases:
        return gaps
    fuzzy = sum(1 for c in cases if c.join_key == "fuzzy")
    by_id = sum(1 for c in cases if c.join_key == "intent_id")
    if n_outcomes and by_id == 0:
        gaps.append(f"no intent carries intent_id: {fuzzy} of {len(cases)} cases joined on "
                    "(symbol, side, lots, time) -- gateway handoff: write intent_id on the "
                    "intent row and on record_outcome's row")
    if all(c.latency_ms is None for c in cases):
        gaps.append("no intent carries latency_ms: latency_summary is UNMEASURED -- gateway "
                    "handoff: time order_send and record it on the intent row")
    if all(c.spread_at_fill_frac is None for c in cases):
        gaps.append("nothing records the spread at fill: spread_expansion is UNMEASURED -- "
                    "gateway handoff: spread_at_fill on record_outcome's row / the deal row")
    if any(c.order_type == "market" and c.spread_frac is None for c in cases):
        gaps.append("market-path intents carry no spread_at_decision: their reject and slip "
                    "cells fall in the 'unknown' spread bucket -- gateway handoff: record the "
                    "tick's spread on the family/scalp intent rows as the bracket path does")
    unresolved = sum(1 for c in cases if c.filled is None)
    if unresolved:
        gaps.append(f"{unresolved} resting orders unresolved (no deal yet, younger than "
                    f"{dt.RESOLVE_AFTER_S / 3600:.0f}h): neither filled nor unfilled")
    return gaps


def run(symbols: list[str] | set[str] | None = None, budget_s: float | None = None
        ) -> dict[str, Any]:
    """One hourly pass. Returns the organ's report with the yield counters in it."""
    t0 = time.monotonic()
    now = datetime.now(tz=UTC)
    if not INTENTS.exists():
        return {"status": dt.UNMEASURED,
                "why": (f"no intent ledger at {INTENTS}: the gateway has not placed an order "
                        "on this box, so there is no live execution to twin"),
                "cases_joined": 0, "symbols_calibrated": 0, "symbols_unmeasured": 0,
                "donated_rows": 0}
    intents = _rows(INTENTS)
    outcomes = _rows(OUTCOMES) if OUTCOMES.exists() else []
    deals = _rows(LEDGER) if LEDGER.exists() else None
    counts = {"intents": len(intents), "outcomes": len(outcomes),
              "deals": len(deals) if deals is not None else 0}
    state = _read_json(STATE)
    prev = state.get("ledger_rows") if isinstance(state.get("ledger_rows"), dict) else None
    if prev == counts and not symbols:
        last = state.get("last") if isinstance(state.get("last"), dict) else {}
        return {"status": "UNCHANGED", "why": "no ledger grew since the last pass",
                "ledger_rows": counts, "cases_joined": int(last.get("cases_joined") or 0),
                "symbols_calibrated": int(last.get("symbols_calibrated") or 0),
                "symbols_unmeasured": int(last.get("symbols_unmeasured") or 0),
                "donated_rows": 0}
    want = {str(s) for s in symbols} if symbols else None
    if want:
        intents = [r for r in intents if str(r.get("symbol")) in want]
        outcomes = [r for r in outcomes if str(r.get("symbol")) in want]
    cases = dt.join_cases(intents, outcomes, deals, asof=now)
    if not cases:
        return {"status": dt.UNMEASURED,
                "why": f"{len(intents)} intent rows, none usable as a case (no side/lot/price)",
                "ledger_rows": counts, "cases_joined": 0, "symbols_calibrated": 0,
                "symbols_unmeasured": 0, "donated_rows": 0}

    donated = _append_cases(cases, CASES)
    # THE FILL CORPUS. Built from this hour's cases joined to every other ledger that has
    # something to add, appended when new or newly resolved, and reported by COMPLETENESS rather
    # than by row count -- a corpus that is 40% populated and says so is worth more than one that
    # looks full because absent columns were defaulted. A filtered run is a probe and writes none.
    corpus, corpus_records = _corpus_section(cases, intents, deals, write=not want)
    costs = sim_costs(cases)
    recal = dt.recalibration(cases, costs)
    try:
        board = execution_registry.scoreboard(rows=outcomes)
    except Exception as exc:
        board = {"status": dt.UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    verdicts = recal["counts"]
    calibrated = sum(v for k, v in verdicts.items() if k != dt.UNMEASURED)
    unmeasured = int(verdicts.get(dt.UNMEASURED, 0))
    join_keys: dict[str, int] = {}
    provenance: dict[str, int] = {}
    for c in cases:
        join_keys[c.join_key] = join_keys.get(c.join_key, 0) + 1
        provenance[c.account_kind] = provenance.get(c.account_kind, 0) + 1
    report: dict[str, Any] = {
        "generated_utc": now.isoformat(), "status": dt.MEASURED,
        "ledger_rows": counts, "symbols_filter": sorted(want) if want else None,
        "cases": {"n": len(cases), "joined_outcome": sum(1 for c in cases if c.joined_outcome),
                  "joined_deal": sum(1 for c in cases if c.joined_deal),
                  "rejected": sum(1 for c in cases if c.rejected),
                  "filled": sum(1 for c in cases if c.filled),
                  "unresolved": sum(1 for c in cases if c.filled is None),
                  "by_join_key": join_keys, "by_account_kind": provenance,
                  "dataset": str(CASES), "appended_this_pass": donated},
        "fill_calibration": dt.fill_calibration(cases),
        "slippage_calibration": dt.slippage_calibration(cases),
        "reject_model": dt.reject_model(cases),
        "latency": dt.latency_summary(cases),
        "spread_expansion": dt.spread_expansion(cases),
        "impact_proxy": dt.impact_proxy(cases),
        "recalibration": recal,
        "execution_choice_value": dt.execution_choice_value(cases),
        # THE THREE CORPUS-DERIVED SECTIONS. `alpha_capture` is the single number that says how
        # much of the research edge survives the broker; the other two are gated harnesses that
        # report UNMEASURED with their own shortfall until the corpus can support a model.
        "fill_corpus": corpus,
        "alpha_capture": ac.report(corpus_records),
        **_models_section(corpus_records),
        "algo_scoreboard": board,
        "sim_costs": {s: {"slip_frac": c.slip_frac, "p_fill": c.p_fill,
                          "spread_frac": c.spread_frac} for s, c in sorted(costs.items())},
        "consumers": CONSUMERS,
        "gaps": _gaps(cases, len(outcomes)),
        "budget_s": budget_s, "seconds": round(time.monotonic() - t0, 3),
        # the yield counters, in the report so the hourly pass can count them by name
        "cases_joined": len(cases), "symbols_calibrated": calibrated,
        "symbols_unmeasured": unmeasured, "donated_rows": donated,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if not want:
        # a filtered run is a probe, not the hour's pass: it must not move the watermark
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({
            "last_run_utc": now.isoformat(), "ledger_rows": counts,
            "last": {"cases_joined": len(cases), "symbols_calibrated": calibrated,
                     "symbols_unmeasured": unmeasured, "donated_rows": donated},
            "runs": int(state.get("runs") or 0) + 1,
            "donated_total": int(state.get("donated_total") or 0) + donated,
        }, indent=1), "utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--symbols", default="", help="comma-separated; a probe, moves no watermark")
    a = ap.parse_args()
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()] or None
    d = run(symbols=syms, budget_s=a.budget_s)
    status = d.get("status")
    if status in (dt.UNMEASURED, "UNCHANGED"):
        print(f"EXECUTION TWIN  {status}: {d.get('why')}", flush=True)
    else:
        v = d["recalibration"]["counts"]
        print(f"EXECUTION TWIN  cases={d['cases_joined']} "
              f"(outcome-joined {d['cases']['joined_outcome']}, deal-joined "
              f"{d['cases']['joined_deal']}, rejected {d['cases']['rejected']}) verdicts="
              f"{json.dumps(v)} appended={d['donated_rows']} gaps={len(d['gaps'])} -> {REPORT}",
              flush=True)
    print(YIELD_PREFIX + json.dumps({k: int(d.get(k) or 0) for k in YIELD_KEYS}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
