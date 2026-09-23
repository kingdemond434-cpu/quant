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

THE CLOSURE (2026-09-22, Tier-1 items 2, 3, 7, 10, 13, 14, 15, 17, 18). The breeding above is
half a loop: it selects pairings and stops. `run_closure` closes it, so one experiment changes
the next instead of only being scored.

  DATA -> REPRESENTATION -> FACTOR -> MODEL -> RESIDUAL -> NEW HYPOTHESIS -> (back to DATA)

* MULTI-ISLAND (15). Four populations with DIFFERENT priors over how the world is shaped and
  DIFFERENT slices of the vocabulary. A concept that survives on two islands survived on two
  information sets; `migrate` moves only concepts strictly stronger than the destination's own
  best, so migration cannot collapse the archipelago into one population.
* BOTH SIDES MUTATE FROM THE RESIDUAL (2). The next generation's feature sets AND its model
  families are mutated by what the last generation got WRONG: residual structure on the session
  axis pushes an hour feature into the set, structure on the state axis pushes a volatility
  feature, and a structured residual under a linear family promotes a nonlinear challenger. A
  generation that mutates only the factors is a factor search wearing a co-evolution label.
* RESIDUALS ARE A DATASET (3). The champion's out-of-sample residuals are pooled across the
  swept instruments and interrogated by state, session, country, macro, participant, asset and
  horizon; every structured axis raises a typed request into its own queue.
* FAILURE EMITS DESCENDANTS (10). Every non-earning pairing is classified and emits the
  descendant its failure KIND implies -- never nothing.
* SELF-PLAY (17). A champion must beat the strongest SIMPLER pairing by the complexity it added,
  survive its own fold spread, and agree with an independent re-implementation.
* ACTIVE DESIGN (13). When the islands disagree about WHICH theory holds, the next experiment is
  the one with the most expected bits about the disagreement, not both theories run blindly.
* SYNTHETIC WORLDS (18). The rediscovery score is measured every run: structures the desk planted
  itself, and whether each research method finds them (with the null world's false positives
  published beside the score, never netted into it).
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

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import feature_store as fs  # noqa: E402
from libs.models.zoo import TAX  # noqa: E402
from libs.research import coevolution_lab as CL  # noqa: E402
from libs.research import model_families as MF  # noqa: E402
from libs.research import trial_ledger as TL  # noqa: E402
from libs.research.coevolution import VOCAB, evolve, live_vocab, target  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "factor_model_coevolution"
KIND = "model_pairing"
REPORT = _DESK / "reports" / "COEVOLUTION.json"
TRIALS = _DESK / "data" / "coevolution_trials.jsonl"
#: Residual rows pooled across instruments before the residual study runs. Pooling is what makes
#: the `asset` and `country` axes informative at all: within one symbol they are constants.
RESIDUAL_POOL_MAX = 4000
#: Islands get a slice of the sweep budget; the rest stays with the classic breeding above.
CLOSURE_SHARE = 0.45
#: Synthetic-world rediscovery rows. Small on purpose: this is a self-check, not a campaign.
WORLD_ROWS = 300
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
        chosen: dict[str, Any] = {"source": "explicit"}
        pool = sorted({s for s in symbols if s in have})
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
        write_queue: bool = True) -> dict[str, Any]:
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


# ===================================================================== THE CLOSURE
_REGIONS: tuple[tuple[str, str], ...] = (
    ("XAU", "metals"), ("XAG", "metals"), ("JPY", "asia_pac"), ("AUD", "asia_pac"),
    ("NZD", "asia_pac"), ("CNH", "asia_pac"), ("SGD", "asia_pac"), ("HKD", "asia_pac"),
    ("EUR", "europe"), ("GBP", "europe"), ("CHF", "europe"), ("SEK", "europe"),
    ("NOK", "europe"), ("PLN", "europe"), ("HUF", "europe"), ("USD", "americas"),
    ("CAD", "americas"), ("MXN", "americas"), ("BRL", "americas"),
)


def _region(sym: str) -> str:
    """The instrument's geography, from the symbol's own legs. UNCLASSIFIED is a verdict: a name
    nothing matches is never silently filed under `other`.

    METALS WIN OUTRIGHT. XAUUSD carries a USD leg, but gold's geography is the metals complex,
    not the Americas -- reading it as `americas+metals` would pool it with USDCAD on the country
    axis and make the residual study's country verdict meaningless for the desk's deepest book.
    """
    up = sym.upper()
    metals = {r for tag, r in _REGIONS if r == "metals" and tag in up}
    if metals:
        return "metals"
    hits = sorted({r for tag, r in _REGIONS if tag in up})
    return "+".join(hits) if hits else "UNCLASSIFIED"


def _tercile(values: np.ndarray, names: tuple[str, str, str]) -> list[str]:
    finite = values[np.isfinite(values)]
    if finite.size < 3:
        return [names[1]] * int(values.size)
    q1, q2 = float(np.quantile(finite, 1 / 3)), float(np.quantile(finite, 2 / 3))
    return [names[0] if (not np.isfinite(v) or v <= q1) else (names[1] if v <= q2 else names[2])
            for v in values]


def _labels(df: Any, rows: np.ndarray, sym: str, horizon: int) -> dict[str, list[str]]:
    """One label per residual row on each of the residual study's seven axes."""
    idx = df.index[rows]
    hour = np.asarray(idx.hour, dtype=int)
    close = df["close"].to_numpy(dtype=float)
    with np.errstate(all="ignore"):
        ret = np.abs(np.diff(np.log(close), prepend=np.log(close[0])))
    vol = np.convolve(ret, np.ones(24) / 24.0, mode="same")[rows]
    tv = (df["tick_volume"].to_numpy(dtype=float)[rows] if "tick_volume" in df.columns
          else np.full(rows.size, np.nan))
    session = ["asia" if h < 7 else ("london" if h < 12 else ("ny" if h < 17 else "off_hours"))
               for h in hour]
    out: dict[str, list[str]] = {
        "session": session,
        "state": _tercile(vol, ("low_vol", "mid_vol", "high_vol")),
        "participant": _tercile(tv, ("thin_flow", "normal_flow", "heavy_flow")),
        "macro": [str(d) for d in np.asarray(idx.dayofweek, dtype=int)],
        "country": [_region(sym)] * int(rows.size),
        "asset": [sym] * int(rows.size),
        "horizon": [f"h{horizon}"] * int(rows.size),
    }
    return out


def _design(df: Any, store: Any, vocab: tuple[tuple[str, dict[str, Any]], ...], sym: str,
            horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """(X over the whole vocabulary, y as the forward sign, the bar rows kept)."""
    specs = [(n, ({**p, "symbol": sym} if "symbol" in p else p)) for n, p in vocab]
    try:
        x = store.matrix(df, specs)
    except Exception:
        return None
    y_raw = target(df, horizon)
    rows = np.where(np.isfinite(y_raw))[0][::horizon]
    if rows.size < MF.MIN_ROWS:
        return None
    sub = np.asarray(x, dtype=float)[rows]
    # A FEATURE THAT IS MOSTLY NaN ON THIS FRAME IS NOT A FEATURE HERE. The vocabulary carries
    # instrument-specific blocks (COT, swaps) that are an all-NaN column on most frames; keeping
    # them would force the row filter to drop every row, and requiring every column finite
    # everywhere would drop the whole design over one rolling warmup. Columns first, then rows.
    keep_c = [j for j in range(sub.shape[1])
              if float(np.isfinite(sub[:, j]).mean()) >= 0.8]
    if len(keep_c) < 2:
        return None
    sub = sub[:, keep_c]
    keep_r = np.where(np.isfinite(sub).all(axis=1))[0]
    if keep_r.size < MF.MIN_ROWS:
        return None
    full = np.full((keep_r.size, x.shape[1]), np.nan)
    full[:, keep_c] = sub[keep_r]
    return full, (y_raw[rows[keep_r]] > 0).astype(float), rows[keep_r]


def _usable(x: np.ndarray, cols: list[int]) -> list[int]:
    """Columns that are finite everywhere and not constant -- a dead block is not information."""
    keep = []
    for c in cols:
        col = x[:, c]
        if np.isfinite(col).all() and float(np.nanstd(col)) > 0:
            keep.append(c)
    return keep


def _score(x: np.ndarray, y: np.ndarray, cols: list[int], family: str,
           allow_heavy: bool) -> dict[str, Any]:
    sub = [[float(v) for v in row] for row in x[:, cols]]
    return MF.walk_forward(family, sub, [float(v) for v in y], allow_heavy=allow_heavy)


def _residuals_of(x: np.ndarray, y: np.ndarray, cols: list[int], family: str,
                  allow_heavy: bool) -> tuple[list[float], np.ndarray] | None:
    """Out-of-sample residuals of one pairing on a 70/30 split, with the rows they belong to."""
    n = len(y)
    cut = int(n * 0.7)
    if cut < MF.MIN_ROWS // 2 or n - cut < CL.MIN_BUCKET:
        return None
    xs = [[float(v) for v in row] for row in x[:, cols]]
    xtr, xte = MF._standardise(xs[:cut], xs[cut:])
    ytr = [float(v) for v in y[:cut]]
    if len(set(ytr)) < 2:
        return None
    probs, _ = MF.fit_predict(family, xtr, ytr, xte, allow_heavy=allow_heavy)
    if probs is None:
        return None
    return CL.residuals([float(v) for v in y[cut:]], probs), np.arange(cut, n)


#: Which vocabulary entry a structured residual axis asks to be ADDED to the feature set. This
#: is the residual mutating the FACTOR side (item 2); the model side is mutated by the failure
#: rules in `libs.research.coevolution_lab`.
_AXIS_FEATURE = {"session": "hour", "state": "realised_vol", "participant": "tick_imbalance",
                 "macro": "hour", "horizon": "log_return", "asset": "zscore",
                 "country": "session_participation"}
#: The challenger a structured residual promotes when the incumbent family cannot represent it.
_CHALLENGER = {"linear": "boosting", "sparse": "tree", "bayesian": "neural",
               "tree": "mixture_of_experts", "boosting": "neural", "neural": "boosting",
               "state_space": "mixture_of_experts", "sequence": "state_space",
               "graph": "sparse", "mixture_of_experts": "boosting"}


def _feature_for(axis: str, vocab: tuple[tuple[str, dict[str, Any]], ...],
                 cols: list[int]) -> int | None:
    want = _AXIS_FEATURE.get(axis)
    if not want:
        return None
    for c in cols:
        if vocab[c][0] == want:
            return c
    return None


def _island_pass(island: CL.Island, x: np.ndarray, y: np.ndarray, sym: str, df: Any,
                 rows: np.ndarray, vocab: tuple[tuple[str, dict[str, Any]], ...], *,
                 gens: int, pop: int, budget_s: float, deadline: float, horizon: int,
                 allow_heavy: bool) -> dict[str, Any]:
    """One island's generations, with BOTH populations mutated by the residual (item 2)."""
    rng = np.random.default_rng(island.seed)
    cols_all = _usable(x, [c for c in island.info_subset if c < x.shape[1]])
    if len(cols_all) < 2:
        return {"island": island.name, "verdict": CL.UNMEASURED, "pairings": 0,
                "why": "fewer than two usable feature columns in this island's information subset",
                "best": None, "results": [], "requests": []}
    families = [f for f in island.prior_models if f in MF.FAMILIES] or ["linear"]

    def _rand_cols() -> list[int]:
        k = int(rng.integers(2, min(5, len(cols_all)) + 1))
        return sorted(rng.choice(cols_all, size=k, replace=False).tolist())

    population = [(_rand_cols(), families[int(rng.integers(len(families)))]) for _ in range(pop)]
    seen: dict[str, dict[str, Any]] = {}
    started = time.monotonic()
    residual_axes: list[str] = []
    for _gen in range(gens):
        scored: list[tuple[list[int], str, dict[str, Any]]] = []
        for cols, fam in population:
            if time.monotonic() - started > budget_s or time.monotonic() > deadline:
                break
            key = json.dumps({"c": cols, "f": fam})
            if key not in seen:
                try:
                    r = _score(x, y, cols, fam, allow_heavy)
                except Exception as exc:
                    r = {"family": fam, "verdict": "FAILED", "net_gain": None,
                         "why": f"{type(exc).__name__}: {exc}"}
                r = {**r, "cols": cols, "model": fam, "complexity": len(cols) + 1,
                     "features": [f"{vocab[c][0]}:{json.dumps(vocab[c][1], sort_keys=True)}"
                                  for c in cols],
                     "concept": f"{fam}[{'+'.join(vocab[c][0] for c in cols)}]"}
                seen[key] = r
            scored.append((cols, fam, seen[key]))
        ranked = [s for s in scored if s[2].get("net_gain") is not None]
        if not ranked:
            break
        ranked.sort(key=lambda s: -float(s[2]["net_gain"]))
        champ_cols, champ_fam, _champ = ranked[0]
        # --- THE RESIDUAL MUTATES BOTH POPULATIONS -------------------------------------
        got = _residuals_of(x, y, champ_cols, champ_fam, allow_heavy)
        add_col: int | None = None
        challenger = _CHALLENGER.get(champ_fam)
        if got is not None:
            resid, sub_rows = got
            ctx = _labels(df, rows[sub_rows], sym, horizon)
            struct = CL.residual_structure(resid, ctx)
            hits = [a for a, r in struct.items()
                    if isinstance(r, dict) and r.get("verdict") == "STRUCTURED"]
            residual_axes = sorted(set(residual_axes) | set(hits))
            for axis in hits:
                add_col = _feature_for(axis, vocab, cols_all)
                if add_col is not None and add_col not in champ_cols:
                    break
                add_col = None
        elite = ranked[: max(2, len(ranked) // 3)]
        children: list[tuple[list[int], str]] = [(c, f) for c, f, _ in elite]
        while len(children) < pop:
            ca, fa, _ = elite[int(rng.integers(len(elite)))]
            cb, _fb, _ = elite[int(rng.integers(len(elite)))]
            cut = int(rng.integers(1, max(2, len(ca))))
            cols = sorted(set(ca[:cut]) | set(cb[cut:]))
            if add_col is not None and rng.random() < 0.6:
                cols = sorted(set(cols) | {add_col})              # residual -> FACTOR mutation
            cols = [c for c in cols if c in cols_all][:5] or ca
            fam = fa
            if challenger and residual_axes and rng.random() < 0.4:
                fam = challenger                                  # residual -> MODEL mutation
            elif rng.random() < 0.25:
                fam = families[int(rng.integers(len(families)))]
            children.append((cols, fam))
        population = children
    results = sorted((v for v in seen.values() if v.get("net_gain") is not None),
                     key=lambda v: -float(v["net_gain"]))
    return {"island": island.name, "prior": list(island.prior_models),
            "info_subset": list(cols_all), "pairings": len(seen), "note": island.note,
            "residual_axes": residual_axes,
            "best": results[0] if results else None,
            "n_earning": sum(1 for r in results if r.get("verdict") == MF.POSITIVE),
            "results": [{k: r.get(k) for k in ("concept", "model", "features", "net_gain",
                                               "gain", "n", "verdict", "complexity", "backend",
                                               "heavy_verdict")}
                        for r in results[:TOP]],
            "verdict": "MEASURED" if results else CL.UNMEASURED}


def _enqueue_survivor(row: dict[str, Any], sym: str, island: str, selfplay: dict[str, Any],
                      n_eff: float) -> dict[str, Any]:
    """A survivor reaches the ONE registry as a candidate with its provenance and its trials."""
    try:
        from libs.moat import registry as R
    except Exception as exc:
        return {"enqueued": False, "why": f"registry unavailable: {type(exc).__name__}: {exc}"}
    params = {"features": row.get("features"), "model_family": row.get("model"),
              "horizon": HORIZON, "net_gain": row.get("net_gain"), "island": island,
              "backend": row.get("backend")}
    mech = (f"co-evolved pairing: {row.get('model')} on {len(row.get('features') or [])} "
            f"features, island {island}, net {float(row.get('net_gain') or 0):+.6f} nats")
    try:
        conn = R.connect()
        try:
            did, _ = R.record_discovery(
                source_id=f"island:{island}", source_type="factor_model_pairing",
                mechanism=mech, origin=SOURCE, generator=SOURCE, assets=[sym],
                horizons=[HORIZON],
                exact_rule=json.dumps({"family": "conditioning_model", "params": params},
                                      sort_keys=True, default=str),
                economic_rationale=("a conditioning model, never a position: the recipe gates a "
                                    "family's entry on this pairing's out-of-sample probability"),
                falsifier=("net gain <= 0 on the next walk-forward, or a strictly simpler "
                           "pairing matching it in self-play"),
                confidence=min(1.0, max(0.0, float(row.get("net_gain") or 0.0) * 200.0)),
                payload={"self_play": selfplay, "effective_trials": n_eff,
                         "island": island, "result": row}, conn=conn)
            R.set_discovery_state(did, "QUEUED", possible_cells=1, generated_cells=1,
                                  compiled_cells=1, queued_cells=1, conn=conn)
            cid, created = R.enqueue_candidate(
                family="conditioning_model", symbol=sym, params=params, origin=SOURCE,
                mechanism=mech, generator=SOURCE, department="mathlab", discovery_id=did,
                trial_family=f"coevolution:{row.get('model')}", horizon=str(HORIZON),
                model_family=str(row.get("model") or ""),
                effective_trials=n_eff,
                falsifier=("a strictly simpler pairing that matches it, or net gain <= 0 "
                           "out of sample"),
                exact_rules=json.dumps({"family": "conditioning_model", "params": params},
                                       default=str),
                lineage_json=json.dumps({"island": island, "source": SOURCE,
                                         "self_play": selfplay.get("verdict"),
                                         "roles": [r.get("role") for r in
                                                   selfplay.get("roles") or []]}, default=str),
                conn=conn)
            return {"enqueued": True, "candidate_id": cid, "created": created,
                    "discovery_id": did}
        finally:
            conn.close()
    except Exception as exc:
        return {"enqueued": False, "why": f"{type(exc).__name__}: {exc}"}


def run_closure(symbols: list[str] | None = None, budget_s: float = BUDGET_S, seed: int = 0,
                pop: int = POP, gens: int = GENS, write_queue: bool = True,
                allow_heavy: bool = True, base: dict[str, Any] | None = None,
                worlds: bool = True) -> dict[str, Any]:
    """Islands, residual research, self-play, active design and the synthetic-world score."""
    deadline = time.monotonic() + budget_s
    todo, chosen = _symbols(symbols)
    store = fs.FeatureStore(FEATURE_ROOT)
    vocab, dropped = live_vocab(store)
    vocab = vocab or VOCAB
    islands = CL.default_islands(len(vocab), seed=seed)
    queues = CL.QueueSet()
    per_island: dict[str, list[dict[str, Any]]] = {i.name: [] for i in islands}
    per_symbol: dict[str, Any] = {}
    residual_pool: list[float] = []
    residual_ctx: dict[str, list[str]] = {a: [] for a in CL.RESIDUAL_AXES}
    compat_cells: list[dict[str, Any]] = []
    trials: list[TL.Trial] = []
    survivors: list[dict[str, Any]] = []
    selfplays: list[dict[str, Any]] = []
    per_sym_budget = max(30.0, budget_s / max(1, len(todo)))
    for si, sym in enumerate(todo):
        if time.monotonic() > deadline:
            per_symbol[sym] = {"verdict": CL.UNMEASURED, "why": "closure budget exhausted"}
            continue
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            per_symbol[sym] = {"verdict": CL.UNMEASURED, "why": f"under {MIN_BARS} H1 bars"}
            continue
        d = d.tail(N_BARS)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            design = _design(d, store, vocab, sym, HORIZON)
        if design is None:
            per_symbol[sym] = {"verdict": CL.UNMEASURED,
                               "why": "feature matrix or target unusable on this frame"}
            continue
        x, y, rows = design
        isl_rows: dict[str, Any] = {}
        for island in islands:
            if time.monotonic() > deadline:
                break
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = _island_pass(island, x, y, sym, d, rows, vocab, gens=gens,
                                 pop=max(4, pop // 2),
                                 budget_s=per_sym_budget / max(1, len(islands)),
                                 deadline=deadline, horizon=HORIZON, allow_heavy=allow_heavy)
            isl_rows[island.name] = r
            per_island[island.name].extend(r.get("results") or [])
            for cell in r.get("results") or []:
                compat_cells.append({"representation": "+".join(
                    sorted({f.split(":")[0] for f in (cell.get("features") or [])})) or "?",
                    "model": cell.get("model"), **{k: cell.get(k) for k in
                                                   ("net_gain", "verdict", "n", "backend",
                                                    "heavy_verdict")}})
                trials.append(TL.Trial(
                    trial_id=f"{sym}:{island.name}:{cell.get('concept')}",
                    family=f"coevolution:{cell.get('model')}",
                    descriptors={"symbol": sym, "model_family": str(cell.get("model") or ""),
                                 "representation": "+".join(sorted(
                                     {f.split(':')[0] for f in (cell.get('features') or [])})),
                                 "horizon": str(HORIZON), "state": island.name},
                    params={"complexity": cell.get("complexity")},
                    declared_width=max(1, int(r.get("pairings") or 1) // max(1, TOP))))
            # The champion's residuals join the pooled research dataset (item 3).
            best = r.get("best")
            if best and best.get("cols"):
                got = _residuals_of(x, y, list(best["cols"]), str(best["model"]), allow_heavy)
                if got is not None and len(residual_pool) < RESIDUAL_POOL_MAX:
                    resid, sub = got
                    ctx = _labels(d, rows[sub], sym, HORIZON)
                    residual_pool.extend(resid)
                    for axis in CL.RESIDUAL_AXES:
                        residual_ctx[axis].extend(ctx.get(axis, ["?"] * len(resid)))
        per_symbol[sym] = {"verdict": "MEASURED" if isl_rows else CL.UNMEASURED,
                           "islands": isl_rows, "bars": len(d),
                           "rows": len(y)}
        # --- SELF-PLAY on this instrument's champion (item 17) --------------------------
        allr = [c for r in isl_rows.values() for c in (r.get("results") or [])
                if c.get("net_gain") is not None]
        if allr:
            allr.sort(key=lambda c: -float(c["net_gain"]))
            champ = allr[0]
            sp = CL.self_play(champ, list(allr[1:]))
            sp = {**sp, "symbol": sym,
                  "island": next((k for k, r in isl_rows.items()
                                  if champ in (r.get("results") or [])), "?")}
            selfplays.append(sp)
            if sp["verdict"] == "SURVIVES_SELF_PLAY" and float(champ["net_gain"]) > 0:
                survivors.append({**champ, "symbol": sym, "island": sp["island"],
                                  "self_play": sp})
            else:
                queues.extend(CL.descendants_for(
                    {**champ, "residual_structured": bool(residual_pool)}, symbol=sym,
                    parent=str(champ.get("concept"))))
        # --- every non-earning pairing emits its descendants (item 10) ------------------
        for r in isl_rows.values():
            for cell in (r.get("results") or []):
                if cell.get("verdict") != MF.POSITIVE:
                    queues.extend(CL.descendants_for(
                        {**cell, "residual_structured": bool(residual_pool)}, symbol=sym,
                        parent=str(cell.get("concept"))))
        if si == 0 and not allr:
            per_symbol[sym]["why"] = "no island produced a scorable pairing on this frame"

    # --- RESIDUAL RESEARCH over the pooled residuals (item 3) ---------------------------
    structure = CL.residual_structure(residual_pool, residual_ctx) if residual_pool else {
        a: {"verdict": CL.UNMEASURED, "why": "no residual rows pooled this run"}
        for a in CL.RESIDUAL_AXES}
    res_requests = CL.residual_requests(structure, model="island_champions",
                                        symbol=",".join(todo[:3]) or "book",
                                        parent=SOURCE) if residual_pool else []
    queues.extend(res_requests)

    # --- MIGRATION: only strong concepts (item 15) --------------------------------------
    migrations = CL.migrate({k: v for k, v in per_island.items() if v})

    # --- ACTIVE EXPERIMENT DESIGN between the two leading islands (item 13) --------------
    rank = sorted(((k, max((float(c["net_gain"]) for c in v if c.get("net_gain") is not None),
                           default=float("-inf"))) for k, v in per_island.items()),
                  key=lambda kv: -kv[1])
    design_doc: dict[str, Any] = {"verdict": CL.UNMEASURED,
                                  "why": "fewer than two islands produced a scorable pairing"}
    if len(rank) >= 2 and rank[1][1] > float("-inf"):
        (h1, g1), (h2, g2) = rank[0], rank[1]
        sep = min(1.0, abs(g1 - g2) * 400.0)
        design_doc = CL.design_discriminating_experiment(
            {"name": h1, "best_net_gain": round(g1, 6)},
            {"name": h2, "best_net_gain": round(g2, 6)},
            [{"name": "hold_out_next_quarter", "cost_s": 300.0,
              "discriminations": [sep, sep * 0.8]},
             {"name": "second_instrument_replication", "cost_s": 180.0,
              "discriminations": [sep * 0.6, sep * 0.5]},
             {"name": "run_both_populations_again", "cost_s": 900.0,
              "discriminations": [0.02, 0.01]}],
            prior_h1=float(CL.prior_for(f"island:{h1}", 0.5)["prior"]))
        queues.push(CL.Request(
            kind="falsification",
            title=f"discriminate {h1} vs {h2}: {design_doc['chosen']['name']}",
            why=("Two islands disagree about which theory holds; this design carries the most "
                 "expected bits about WHICH is true per second of compute, so the other "
                 f"{design_doc['saved_trials']} design(s) are not run."),
            payload={"h1": h1, "h2": h2, "design": design_doc["chosen"]}, priority=2.5,
            source=SOURCE, parent=SOURCE))

    # --- SYNTHETIC WORLDS (item 18) ------------------------------------------------------
    world = ({"verdict": "SKIPPED", "why": "--no-worlds"} if not worlds else
             CL.rediscovery_score(n=WORLD_ROWS, seed=seed, allow_heavy=allow_heavy,
                                  min_rows=min(MF.MIN_ROWS, WORLD_ROWS // 3)))

    # --- SURVIVORS -> the ONE registry, trials charged (LAWS: one registry) --------------
    census = TL.census(trials)
    enqueued = []
    for s in survivors:
        enqueued.append({"symbol": s["symbol"], "island": s["island"],
                         "concept": s.get("concept"),
                         **_enqueue_survivor(s, s["symbol"], s["island"], s["self_play"],
                                             census.n_effective)})
    compat = CL.compatibility_matrix(compat_cells)
    dead = CL.dead_representations(compat)
    free_slots = max(0, int(deadline - time.monotonic()) // 60)
    idle = queues.idle_defect(free_slots=free_slots, value_floor=1.5)
    for s in survivors:
        CL.record_outcome(f"island:{s['island']}", "SURVIVED_SELF_PLAY",
                          net_gain=s.get("net_gain"), symbol=s["symbol"])
        CL.link_experiment(SOURCE, str(s.get("concept")), "coevolved_survivor")
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(), "symbols": {**chosen, "n": len(todo)},
        "vocabulary_census": {"size": len(vocab), "withdrawn": dropped},
        "islands": [{"name": i.name, "prior_models": list(i.prior_models),
                     "info_subset": list(i.info_subset), "note": i.note} for i in islands],
        "closure_per_symbol": per_symbol,
        "pairings_tested": sum(int(r.get("pairings") or 0)
                               for s in per_symbol.values() if isinstance(s, dict)
                               for r in (s.get("islands") or {}).values()),
        "compatibility_matrix": compat, "representation_verdicts": dead,
        "migrations": migrations, "n_migrations": len(migrations),
        "self_play": selfplays,
        "self_play_rejected": [s for s in selfplays if s["verdict"] == "REJECTED"],
        "residual_research": {"rows_pooled": len(residual_pool), "structure": structure,
                              "requests": [r.to_dict() for r in res_requests]},
        "queues": {"depth": queues.depth(), "idle": idle,
                   "top": {k: [r.to_dict() for r in queues.top(k, 3)] for k in CL.QUEUE_KINDS}},
        "active_design": design_doc,
        "synthetic_world": world,
        "model_families": MF.availability(),
        "trials": {**census.to_dict(), "charged_by": "libs/research/trial_ledger.py"},
        "survivors": [{"symbol": s["symbol"], "island": s["island"],
                       "concept": s.get("concept"), "net_gain": s.get("net_gain"),
                       "model": s.get("model"), "features": s.get("features")}
                      for s in survivors],
        "registry": enqueued,
        "closure_rule": ("every pairing is a trial and every failure emits a descendant; a "
                         "survivor must beat the strongest SIMPLER explanation, not only the "
                         "null; an untried (R, M) cell is UNMEASURED, never a zero"),
    }
    if write_queue and (queues.depth() or res_requests):
        doc["queue_merged"] = _merge_requests(queues)
    if base:
        doc["breeding"] = {k: base.get(k) for k in
                           ("tests_run", "n_tasks", "per_symbol", "skipped", "trial_ledger")}
    return doc


def _merge_requests(queues: CL.QueueSet) -> Any:
    """The seven queues' requests reach the desk's deepening queue as typed tasks."""
    tasks: list[dict[str, Any]] = [
        {"source": SOURCE, "kind": f"{r.kind}_request", "title": r.title,
              "description": r.why, "symbols": [], "family": None,
              "params": {**r.payload, "queue": r.kind, "priority": r.priority,
                         "request_id": r.request_id},
              "status": None,
              "consumer": f"deepening_worker ({r.kind} queue)"}
             for r in queues.all_requests()]
    if not tasks:
        return "no requests this run"
    try:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source=SOURCE)
        return len(tasks)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def run_all(symbols: list[str] | None = None, budget_s: float = BUDGET_S, seed: int = 0,
            pop: int = POP, gens: int = GENS, write_queue: bool = True,
            closure: bool = True, allow_heavy: bool = True, worlds: bool = True
            ) -> dict[str, Any]:
    """The breeding pass above, then the closure, into ONE COEVOLUTION.json."""
    share = CLOSURE_SHARE if closure else 0.0
    base = run(symbols=symbols, budget_s=budget_s * (1.0 - share), seed=seed, pop=pop,
               gens=gens, write_queue=write_queue)
    if not closure:
        return base
    try:
        doc = run_closure(symbols=symbols, budget_s=budget_s * share, seed=seed, pop=pop,
                          gens=gens, write_queue=write_queue, allow_heavy=allow_heavy,
                          base=base, worlds=worlds)
    except Exception as exc:                                   # the breeding pass still stands
        doc = {**base, "closure": {"verdict": "FAILED",
                                   "why": f"{type(exc).__name__}: {exc}"}}
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        return doc
    merged = {**base, **doc, "breeding": doc.get("breeding")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(merged, indent=1, default=str), "utf-8")
    try:
        from libs.ops import events
        events.emit("coevolution", leg="coevolution",
                    pairings=int(merged.get("pairings_tested") or 0),
                    survivors=len(merged.get("survivors") or []),
                    migrations=int(merged.get("n_migrations") or 0),
                    rediscovery=(merged.get("synthetic_world") or {}).get("desk_score"))
    except Exception:
        pass
    return merged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--pop", type=int, default=POP)
    ap.add_argument("--gens", type=int, default=GENS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-queue", action="store_true")
    ap.add_argument("--once", action="store_true",
                    help="one pass and exit (the scheduler's contract; this organ never loops)")
    ap.add_argument("--no-closure", action="store_true",
                    help="breed only, skip islands / residuals / self-play / worlds")
    ap.add_argument("--no-worlds", action="store_true",
                    help="skip the synthetic-world rediscovery score")
    ap.add_argument("--no-heavy", action="store_true",
                    help="refuse every heavy backend; the pure-Python fallbacks carry the run")
    a = ap.parse_args()
    doc = run_all(symbols=a.symbol, budget_s=a.budget_s, seed=a.seed, pop=a.pop, gens=a.gens,
                  write_queue=not a.no_queue, closure=not a.no_closure,
                  allow_heavy=not a.no_heavy, worlds=not a.no_worlds)
    print(f"COEVOLUTION  {doc.get('symbols_swept', 0)} symbols "
          f"[{doc['symbols']['source']}], {doc.get('tests_run', 0)} bred pairings, "
          f"{doc.get('n_tasks', 0)} {KIND} tasks")
    for sym, r in (doc.get("per_symbol") or {}).items():
        if not isinstance(r, dict) or "best" not in r:
            continue
        b = r["best"][0] if r["best"] else None
        print(f"  {sym:8s} pairings={r['pairings_evaluated']:3d} earning={r['n_earning']:2d}"
              + (f"  best={b['model']} net={b['net_gain']:+.5f} {b['verdict']} "
                 f"n={b['n']}  {b['features']}" if b else "  best=-"))
    for k, v in (doc.get("skipped") or {}).items():
        print(f"  skipped {k}: {v}")
    if not a.no_closure:
        w = doc.get("synthetic_world") or {}
        print(f"  CLOSURE  islands={len(doc.get('islands') or [])} "
              f"pairings={doc.get('pairings_tested', 0)} "
              f"migrations={doc.get('n_migrations', 0)} "
              f"survivors={len(doc.get('survivors') or [])} "
              f"self_play_rejected={len(doc.get('self_play_rejected') or [])} "
              f"rediscovery={w.get('desk_score')}")
        q = (doc.get("queues") or {}).get("idle") or {}
        print(f"  QUEUES   {(doc.get('queues') or {}).get('depth')}  idle={q.get('verdict')}"
              f" -- {q.get('why')}")
        struct = (doc.get("residual_research") or {}).get("structure") or {}
        hit = [a2 for a2, r2 in struct.items()
               if isinstance(r2, dict) and r2.get("verdict") == "STRUCTURED"]
        print(f"  RESIDUAL rows={(doc.get('residual_research') or {}).get('rows_pooled', 0)} "
              f"structured_axes={hit or '-'}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
