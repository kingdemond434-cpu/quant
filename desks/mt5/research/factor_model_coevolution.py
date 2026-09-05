"""Factor x model co-evolution, daily: breed feature sets with models per book instrument and
hand the pairings that earn their tax to the deepening queue as state-conditioning recipes.

    (F*, M*) = argmax_{F, M}  logscore_OOS(F, M) - baseline - tax(M)

`libs.research.coevolution.evolve` does the breeding -- feature sets from the store's vocabulary
crossed with the zoo's models, every pairing scored walk-forward on the sign of the 6-bar forward
return. This module is the desk-side schedule around it: which instruments, how many bars, how
much time, and what leaves.

WHAT LEAVES IS A TASK, NOT A CELL. A pairing whose verdict is the zoo's EARNS_ITS_PLACE (net gain
after tax > 0 nats per prediction) is a CANDIDATE CONDITIONING MODEL; it has no entry, no stop
and no family, so it cannot be donated as a recipe. It goes to the deepening queue as kind
`model_pairing`, naming the features, the model, the measured net gain and n, for the worker to
write a state-conditioned family recipe around -- and that recipe walks the gauntlet like
anything else.

EVERY PAIRING IS A TRIAL. Measured 2026-09-04 on EURUSD (6,000 bars, pop 10, gens 3): 20
pairings in 11s, best net gain -0.0006 nats, zero earning -- which is the honest baseline a
model has to beat and exactly why the count must be carried. `tests_run` on the report is the
sum of pairings, and every run appends {generated_utc, symbol, pairings} to
data/coevolution_trials.jsonl so the lifetime ledger can charge the whole history, not the
flattering subset that earned.

BOUNDED BY CONSTRUCTION. At most MAX_SYMBOLS instruments per run (the book rotates through them
by calendar day so no name is excluded, only deferred), the last N_BARS bars each, the budget
split evenly, and the feature store shared so a repeated feature is computed once.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import feature_store as fs  # noqa: E402
from libs.models.zoo import TAX  # noqa: E402
from libs.research.coevolution import VOCAB, evolve  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "factor_model_coevolution"
KIND = "model_pairing"
REPORT = _DESK / "reports" / "COEVOLUTION.json"
TRIALS = _DESK / "data" / "coevolution_trials.jsonl"
#: Where feature blocks live; the store's own default, exposed so a test can point it at tmp.
FEATURE_ROOT = fs.STORE
#: The zoo's positive verdict. Read from the zoo's rule -- "EARNS_ITS_PLACE if net > 0 else
#: TAXED_OUT" -- and pinned here so a renamed verdict fails loudly in the test, not silently here.
POSITIVE = "EARNS_ITS_PLACE"
N_BARS = 6000
MIN_BARS = 3000
MAX_SYMBOLS = 6
POP, GENS = 10, 3
HORIZON = 6
BUDGET_S = 900.0
#: Pairings reported per instrument and the most that may become tasks from one run of it.
TOP = 3


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:
        return []


def _symbols(symbols: list[str] | None) -> tuple[list[str], dict[str, Any]]:
    """Explicit > certified book > fallback; always capped, rotated by calendar day."""
    have = sorted(p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet"))
    if symbols:
        pool, chosen = sorted({s for s in symbols if s in have}), {"source": "explicit"}
    else:
        book = sorted({s for s in _book_symbols() if s in have})
        if book:
            pool, chosen = book, {"source": "book"}
        else:
            pool = [s for s in have if (d := pc.bars(s)) is not None and len(d) >= MIN_BARS]
            chosen = {"source": "fallback",
                      "why": (f"certified book empty on this tree; up to {MAX_SYMBOLS} "
                              f"instruments with >= {MIN_BARS} H1 bars instead")}
    if len(pool) > MAX_SYMBOLS:
        # DEFERRED, NOT EXCLUDED. The offset walks one step per calendar day, so a 20-name book
        # is covered every four runs rather than the first six names alphabetically forever.
        off = datetime.now(tz=UTC).timetuple().tm_yday % len(pool)
        rotated = pool[off:] + pool[:off]
        chosen["deferred"] = rotated[MAX_SYMBOLS:]
        pool = rotated[:MAX_SYMBOLS]
    return pool, chosen


def _task(sym: str, pairing: dict[str, Any], pairings: int) -> dict[str, Any]:
    feats = list(pairing.get("features") or [])
    gain, tax, net = pairing.get("gain"), pairing.get("tax"), pairing.get("net_gain")
    return {"source": SOURCE, "kind": KIND,
            "title": (f"{sym}: {pairing.get('model')} on {len(feats)} features earns "
                      f"{float(net or 0):+.5f} nats/prediction after tax"),
            "description": (
                f"Co-evolution on {sym}: model {pairing.get('model')} on features "
                f"[{', '.join(feats)}] earned net {float(net or 0):+.5f} nats per prediction "
                f"(OOS log-score gain {float(gain or 0):+.5f} minus tax {tax}) over n="
                f"{pairing.get('n')} non-overlapping {HORIZON}-bar sign targets, verdict "
                f"{pairing.get('verdict')}, selected from {pairings} pairings this run (every "
                "one charged as a trial). The pairing is a CANDIDATE CONDITIONING MODEL, never "
                "a position: write a state-conditioned family recipe whose entry is gated on "
                "this pairing's out-of-sample probability and send it through the gauntlet."),
            "symbols": [sym], "family": None,
            "params": {"features": feats, "model": pairing.get("model"), "horizon": HORIZON,
                       "net_gain": net, "gain": gain, "tax": tax, "n": pairing.get("n"),
                       "brier": pairing.get("brier"), "pairings_this_run": pairings},
            "status": None,
            "consumer": "deepening_worker (model_pairing) -> a state-conditioned family recipe"}


def _append_trials(rows: list[dict[str, Any]]) -> str:
    try:
        TRIALS.parent.mkdir(parents=True, exist_ok=True)
        with TRIALS.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
        return ""
    except OSError as exc:
        return f"trial ledger not written: {type(exc).__name__}: {exc}"


def run(symbols: list[str] | None = None, budget_s: float = BUDGET_S, seed: int = 0,
        pop: int = POP, gens: int = GENS, models: tuple[str, ...] | None = None,
        write_queue: bool = True) -> dict:
    todo, chosen = _symbols(symbols)
    models = tuple(models) if models else tuple(TAX)
    per_sym = budget_s / max(1, len(todo))
    store = fs.FeatureStore(FEATURE_ROOT)
    per_symbol: dict[str, dict[str, Any]] = {}
    skipped: dict[str, str] = {}
    tasks: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for i, sym in enumerate(todo):
        if time.monotonic() - started > budget_s:
            skipped[sym] = "sweep budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            skipped[sym] = f"under {MIN_BARS} H1 bars"
            continue
        d = d.tail(N_BARS)
        try:
            # THE TAX ALREADY PRICES INSTABILITY. sklearn's MLP warns on every fold it fails to
            # converge in 300 iterations; the zoo charges that architecture 0.0025 nats for
            # exactly that, so the warning is the log repeating the rule.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = evolve(d, symbol=sym, store=store, pop=pop, gens=gens, budget_s=per_sym,
                             seed=seed + i, horizon=HORIZON, models=models)
        except Exception as exc:
            skipped[sym] = f"{type(exc).__name__}: {exc}"
            continue
        n_pair = int(res.get("pairings_evaluated") or 0)
        best = [{k: b.get(k) for k in ("features", "model", "net_gain", "gain", "tax",
                                       "verdict", "n", "brier")}
                for b in (res.get("best") or [])[:TOP]]
        per_symbol[sym] = {"pairings_evaluated": n_pair, "best": best,
                           "n_earning": int(res.get("n_earning") or 0), "bars": len(d),
                           "budget_s": round(per_sym, 1)}
        trial_rows.append({"generated_utc": datetime.now(tz=UTC).isoformat(), "symbol": sym,
                           "pairings": n_pair, "n_earning": int(res.get("n_earning") or 0),
                           "seed": seed + i, "source": SOURCE})
        tasks.extend(_task(sym, b, n_pair) for b in best
                     if b.get("verdict") == POSITIVE and float(b.get("net_gain") or 0.0) > 0.0)
    tests_run = sum(r["pairings_evaluated"] for r in per_symbol.values())
    ledger_err = _append_trials(trial_rows) if trial_rows else ""
    try:
        census = store.census()
    except Exception as exc:
        census = {"why": f"{type(exc).__name__}: {exc}"}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
           "symbols": {**chosen, "n": len(todo)}, "tests_run": tests_run,
           "per_symbol": per_symbol, "skipped": skipped, "n_tasks": len(tasks),
           "tasks": [{k: t[k] for k in ("title", "symbols", "params")} for t in tasks],
           "budget_s": budget_s, "models": list(models), "vocabulary": len(VOCAB),
           "bars_per_symbol": N_BARS, "pop": pop, "gens": gens, "horizon": HORIZON,
           "positive_verdict": POSITIVE, "feature_store": census,
           "trial_ledger": {"path": str(TRIALS), "rows_appended": len(trial_rows),
                            "error": ledger_err},
           "rule": ("every pairing evaluated is a trial (tests_run, and the jsonl ledger); only "
                    f"a pairing with verdict {POSITIVE} and net_gain > 0 becomes a "
                    f"{KIND} task, and a task is a conditioning-model candidate for a family "
                    "recipe, never a position")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    # A run that evaluated nothing must not erase the last real run's tasks.
    if write_queue and tests_run > 0:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source=SOURCE)
            doc["queue_merged"] = True
        except Exception as exc:
            doc["queue_merged"] = f"{type(exc).__name__}: {exc}"
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--pop", type=int, default=POP)
    ap.add_argument("--gens", type=int, default=GENS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    doc = run(symbols=a.symbol, budget_s=a.budget_s, seed=a.seed, pop=a.pop, gens=a.gens,
              write_queue=not a.no_queue)
    print(f"COEVOLUTION  {doc['symbols_swept']} symbols [{doc['symbols']['source']}], "
          f"{doc['tests_run']} pairings, {doc['n_tasks']} {KIND} tasks")
    for sym, r in doc["per_symbol"].items():
        b = r["best"][0] if r["best"] else None
        print(f"  {sym:8s} pairings={r['pairings_evaluated']:3d} earning={r['n_earning']:2d}"
              + (f"  best={b['model']} net={b['net_gain']:+.5f} {b['verdict']} "
                 f"n={b['n']}  {b['features']}" if b else "  best=-"))
    for k, v in doc["skipped"].items():
        print(f"  skipped {k}: {v}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
