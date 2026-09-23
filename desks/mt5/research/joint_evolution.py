"""F5 -- EVOLVE THE WHOLE EXECUTABLE OBJECT, and MEASURE that the layers interact.

THE PRINCIPAL, 2026-09-12, ranking this fifth of the remaining blueprint:

    Evolve the whole executable object -- representation, predictive model, state condition,
    horizon, entry, exit, execution policy, portfolio role -- so search discovers INTERACTION
    STRUCTURE instead of optimising each layer separately.

THE GAP, AS THE LEDGER STATES IT AND THE CODE CONFIRMS. `alpha_evolution` searches expressions
brilliantly and then wraps every one of them in

    RECIPE = {"norm": 240, "entry_z": 1.5, "hold_bars": 8, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}

-- six constants, identical for every mechanism it has ever found. And the registered families
declare param grids of nine points (`momentum_volgate`: mom_thresh x rr). So the desk searches one
layer exhaustively and holds six others fixed at numbers nobody has re-derived, which is only
correct if the layers are SEPARABLE: if the best exit for a momentum signal is the best exit for a
reversal signal, if the best horizon does not depend on the volatility gate, if the best execution
policy does not depend on the horizon.

THAT IS AN EMPIRICAL CLAIM AND IT HAS NEVER BEEN TESTED HERE. So this organ does not begin by
asserting joint search is better. It SAMPLES the joint genome, fits a functional ANOVA over the
sampled fitness surface, and reports -- per axis pair -- how much of the fitness variance lives in
the INTERACTION beyond the two main effects. A desk whose interaction terms are negligible should
keep optimising layer by layer and spend the compute elsewhere; a desk whose interaction terms
dominate has been searching a projection of its own problem.

THE GENOME, and which blueprint layer each axis is:

    representation / model   the family's own signal-shape kwargs (lookbacks, thresholds)
    state condition          a post-hoc regime filter: volatility band and session
    horizon                  ttl_bars -- how long the position may live
    entry                    resting trigger at an ATR offset, or next open
    exit                     rr, partial bank fraction, breakeven protection, trailing stop
    execution policy         whether the entry is a resting order and how long it rests
    portfolio role           NOT searched -- SCORED, as marginal contribution to the book

PORTFOLIO ROLE IS A SCORE AND NOT A KNOB, deliberately. "Diversifier" is not something a strategy
can be built to be; it is a relationship to the book that already exists, and it changes every
time the book changes. So each genome is scored twice -- standalone, and by its marginal
contribution to the live book's growth -- and the two rankings are published side by side, because
the gap between them is the whole of what a portfolio view buys.

ONE CANONICAL VALIDATOR. Fitness comes from `external_gauntlet.daily_series` and `costs_for` --
the desk's own evaluator, on the desk's own cost model. A second implementation here would prove
only that two programs agree, and this repo forbids that for good reason.

SEARCH IS ON TRAIN, REPORTING IS ON TEST. The genome is sampled and ranked on the first 70% of
bars; every number that leaves this organ is computed on the held-out remainder. Nothing here
certifies: the winners are DONATED through `proposer_common.donate`, which stamps them
point-in-time and pre-registers the hypothesis card, and they then face the identical ten gates.

    python desks/mt5/research/joint_evolution.py [--apply]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "JOINT_EVOLUTION.json"

#: Families searched jointly. Chosen because each carries a real signal shape AND real exit
#: parameters, so the genome spans more than one layer from the start. Deliberately few: this
#: organ's product is the interaction table, and a wide family sweep would buy a longer report
#: at the cost of a thinner sample per surface.
FAMILIES: tuple[str, ...] = ("momentum_volgate", "session_range_breakout", "mean_reversion_rsi")

#: Genomes sampled per (symbol, family). 160 random draws over ~8 axes is sparse for an exhaustive
#: optimum and ample for a variance decomposition, which is what this organ is for -- the ANOVA
#: needs the surface's shape, not its maximum.
DRAWS = 160

#: Symbols. The search cost is linear in this and the interaction structure is the thing being
#: measured, so breadth across a few instruments beats depth on one.
MAX_SYMBOLS = 4

BARS = 6000
TRAIN_FRAC = 0.70
EMBARGO = 240

#: The fixed risk fraction at which a daily R series is turned into log growth. It is NOT a sizing
#: decision and nothing downstream reads it: it is the monotone transform that makes ranking by
#: growth rather than by mean R meaningful, and it is stated so the ranking is reproducible.
RANK_RISK_FRAC = 0.01

#: How many train-ranked genomes are carried to the test window, and the minimum number of trades
#: one must place there to be reportable. A genome that wins on train by trading twelve times and
#: then never fires out of sample is not a result, and reporting it as `None` hides which of
#: "over-filtered" and "no data" happened.
TOP_K = 8
MIN_TEST_SIGNALS = 20

SEED = 20260912


def _live_symbols(limit: int = MAX_SYMBOLS) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


# ------------------------------------------------------------------------------- the genome

#: The axes OUTSIDE the family function -- the layers `alpha_evolution` holds at RECIPE constants.
#: Each is applied to the family's own Signal list, so it works for every registered family
#: without touching one of them.
STATE_BANDS: tuple[str, ...] = ("any", "calm", "active")
SESSIONS: tuple[str, ...] = ("any", "london", "ny", "asia")
TRIGGER_ATR: tuple[float, ...] = (0.0, 0.25, 0.5)       # 0 = market at next open
REST_BARS: tuple[int, ...] = (1, 3, 6)                  # how long a resting order lives
TTL_MULT: tuple[float, ...] = (0.5, 1.0, 2.0)           # horizon, relative to the family default
RR_MULT: tuple[float, ...] = (0.7, 1.0, 1.5)            # exit distance, relative to the default
BANK_FRAC: tuple[float, ...] = (0.0, 0.5)               # partial exit at target
TRAIL_K: tuple[float, ...] = (0.0, 1.0, 2.0)            # chandelier trail, 0 = fixed stop

#: Which blueprint layer each axis belongs to. The interaction table is reported in these terms,
#: because "ttl_mult interacts with rr_mult" is a fact about two variables and "horizon interacts
#: with exit" is a fact about the desk's architecture.
AXIS_LAYER: dict[str, str] = {
    "state_band": "state condition", "session": "state condition",
    "trigger_atr": "entry / execution policy", "rest_bars": "execution policy",
    "ttl_mult": "horizon", "rr_mult": "exit",
    "bank_frac": "exit", "trail_k": "exit",
}


def _family_axes(defaults: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    """The family's OWN numeric kwargs, laddered around their registered defaults.

    Taken from EVERY registered default rather than from the declared param grid, on purpose: the
    grids are nine points wide (`momentum_volgate` declares mom_thresh x rr and holds mom_n,
    atr_n, vol_gate_q and ttl_bars fixed), and the kwargs the grid omits are exactly the ones
    nobody has re-derived. That is where the fixed recipe actually lives.
    """
    axes: dict[str, tuple[Any, ...]] = {}
    for name, d in (defaults or {}).items():
        if isinstance(d, bool):
            continue
        if isinstance(d, int):
            axes[name] = tuple(sorted({max(1, int(d * m)) for m in (0.5, 1.0, 1.75)}))
        elif isinstance(d, float):
            axes[name] = tuple(sorted({round(d * m, 6) for m in (0.6, 1.0, 1.6)}))
    return axes


def _draw(rng: random.Random, axes: dict[str, tuple[Any, ...]]) -> dict[str, Any]:
    return {k: rng.choice(list(v)) for k, v in axes.items()}


# ---------------------------------------------------------- applying the non-family layers

#: The layer genes, applied by `mt5desk.families.apply_layers`. ONE IMPLEMENTATION, used by this
#: search and by the gauntlet's own `family_joint_genome` -- because a search that scores an
#: object the judge cannot build produces candidates that die silently at `build_cell`, which is
#: exactly the zombie-certificate shape this desk has already paid for once.
LAYER_GENES: tuple[str, ...] = ("state_band", "session", "trigger_atr", "rest_bars",
                                "ttl_mult", "rr_mult", "bank_frac", "trail_k")


# ---------------------------------------------------------------------------- the evaluator

def _growth(ds: Any) -> float:
    """Mean log growth of a daily R series at a FIXED fraction. The desk's objective, not Sharpe.

    Sharpe would rank a genome that makes money smoothly above one that compounds faster, and the
    standing objective on this desk is E[log W]. `RANK_RISK_FRAC` is a stated constant, not a
    sizing decision: it is the transform that makes the ranking a growth ranking.
    """
    import numpy as np
    if ds is None or len(ds) < 20:
        return float("nan")
    r = np.asarray(ds, dtype=float) * RANK_RISK_FRAC
    r = r[np.isfinite(r)]
    if r.size < 20 or np.any(r <= -1.0):
        return float("nan")
    return float(np.mean(np.log1p(r)))


#: Days of realised book history required before a portfolio-role score means anything. Below
#: this a correlation is an artefact of a handful of fills, and "diversifier" would be a label
#: applied to noise -- which is worse than admitting the book is too young to say.
MIN_BOOK_DAYS = 30


def _book_daily() -> tuple[Any, str | None]:
    """The live book's own daily R series, and WHY it is absent when it is.

    Read from `live_ledger.jsonl`, which is the desk's record of realised deals. The shadow lanes
    were the obvious source and cannot supply this: their rows carry aggregates (n, cum_r,
    first_entry, last_entry) and no per-trade list, so no daily series is reconstructible from
    them at all. Saying so is the point -- a portfolio-role score silently computed off the wrong
    file would be a number about nothing.
    """
    import pandas as pd
    p = DESK / "data" / "live_ledger.jsonl"
    if not p.exists():
        return (None, f"no live ledger at {p.relative_to(ROOT)}")
    rows: dict[str, float] = {}
    n_deals = 0
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        r = d.get("r_multiple")
        day = str(d.get("time") or "")[:10]
        if day and isinstance(r, (int, float)):
            n_deals += 1
            rows[day] = rows.get(day, 0.0) + float(r)
    if len(rows) < MIN_BOOK_DAYS:
        return (None, (f"the live ledger holds {n_deals} closed deal(s) across {len(rows)} "
                       f"day(s); a portfolio-role score needs at least {MIN_BOOK_DAYS} days, "
                       f"below which a correlation is an artefact of a handful of fills"))
    return (pd.Series(rows).sort_index(), None)


# ----------------------------------------------------------------- the interaction structure

def _anova(rows: list[dict[str, Any]], axes: list[str]) -> dict[str, Any]:
    """Functional ANOVA over the sampled genomes: main effects, then interaction beyond them.

    For each axis, the variance of the per-level conditional mean fitness is its MAIN EFFECT. For
    each pair, the variance of the per-cell conditional mean is the joint effect, and the excess
    over the two main effects is the INTERACTION. Everything is expressed as a share of total
    fitness variance, so the numbers compare across symbols and families.

    IT IS AN ESTIMATE FROM A SPARSE SAMPLE AND SAYS SO. With 160 draws over eight axes a pair cell
    holds a handful of genomes, so a small interaction share is not evidence of separability -- it
    is a measurement with wide error. A LARGE share is the finding that matters, because sampling
    noise inflates nothing systematically and cannot manufacture structure at this sample size
    without also inflating the main effects it is measured against.
    """
    import numpy as np
    ys = np.asarray([r["fitness"] for r in rows], dtype=float)
    ok = np.isfinite(ys)
    if ok.sum() < 40:
        return {"status": "UNMEASURED",
                "why": f"only {int(ok.sum())} genome(s) produced a finite fitness"}
    ys = ys[ok]
    sel = [r for r, k in zip(rows, ok, strict=False) if k]
    total = float(np.var(ys))
    if total <= 0:
        return {"status": "UNMEASURED", "why": "every sampled genome scored identically"}

    def _cond(keys: list[str]) -> float:
        groups: dict[tuple[Any, ...], list[float]] = {}
        for r, y in zip(sel, ys, strict=False):
            groups.setdefault(tuple(r["genome"].get(k) for k in keys), []).append(float(y))
        means = [float(np.mean(v)) for v in groups.values() if len(v) >= 3]
        w = [len(v) for v in groups.values() if len(v) >= 3]
        if len(means) < 2:
            return 0.0
        mbar = float(np.average(means, weights=w))
        return float(np.average([(m - mbar) ** 2 for m in means], weights=w))

    main = {a: round(_cond([a]) / total, 4) for a in axes}
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(axes):
        for b in axes[i + 1:]:
            joint = _cond([a, b]) / total
            inter = joint - main[a] - main[b]
            pairs.append({"axes": [a, b],
                          "layers": [AXIS_LAYER.get(a, "representation / model"),
                                     AXIS_LAYER.get(b, "representation / model")],
                          "joint_share": round(joint, 4),
                          "interaction_share": round(inter, 4)})
    pairs.sort(key=lambda r: -float(r["interaction_share"]))
    top = [p for p in pairs if float(p["interaction_share"]) > 0.05]
    return {"status": "OK", "n_genomes": int(ok.sum()),
            "main_effect_share": main,
            "top_interactions": pairs[:12],
            "n_pairs_over_5pct": len(top),
            "verdict": (
                "SEPARABLE -- no axis pair carries more than 5% of fitness variance in its "
                "interaction, so optimising layer by layer loses little and the compute is "
                "better spent elsewhere"
                if not top else
                f"NOT SEPARABLE -- {len(top)} axis pair(s) carry more than 5% of fitness "
                f"variance in their interaction alone, the largest being "
                f"{top[0]['axes'][0]} x {top[0]['axes'][1]} "
                f"({float(top[0]['interaction_share']):.1%}), i.e. "
                f"{top[0]['layers'][0]} x {top[0]['layers'][1]}. A search that fixes one while "
                f"tuning the other is searching a projection of its own problem.")}


# --------------------------------------------------------------------------------- assembly

def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy/pandas unavailable ({exc})"}
    try:
        import external_gauntlet as eg  # type: ignore[import-not-found]
        from mt5desk import families as FAM
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": (f"the canonical evaluator is not importable ({exc}). This organ refuses "
                        f"to score with a second implementation -- that would prove only that "
                        f"two programs agree.")}

    try:
        meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"universe registry unreadable: {exc}"}

    book, book_why = _book_daily()
    rng = random.Random(SEED)  # noqa: S311 -- a published search seed, never a secret
    surfaces: list[dict[str, Any]] = []
    winners: list[dict[str, Any]] = []
    evaluated = 0

    for sym in _live_symbols():
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p).tail(BARS)
        except (OSError, ValueError):
            continue
        if len(df) < 2000:
            continue
        ntr = int(len(df) * TRAIN_FRAC)
        train, test = df.iloc[:ntr], df.iloc[ntr + EMBARGO:]
        if len(test) < 500:
            continue
        try:
            costs = eg.costs_for(sym, meta)
        except Exception:
            continue

        for fam in FAMILIES:
            # THE REGISTRY HOLDS A RECORD, NOT A FUNCTION -- {func, name, defaults, param_grid,
            # tags}. Unpacked here rather than introspected, because the record's `defaults` is
            # the family's own declaration of its full knob set and the signature is a second
            # source for the same fact.
            entry = FAM.FAMILY_REGISTRY.get(fam)
            fn: Any = (entry.get("func") if isinstance(entry, dict)
                       else getattr(FAM, f"family_{fam}", None))
            if fn is None or not callable(fn):
                continue
            defaults: dict[str, Any] = (
                (entry.get("defaults") or {}) if isinstance(entry, dict) else {})
            fam_axes = _family_axes(defaults)
            if not fam_axes:
                continue
            axes: dict[str, tuple[Any, ...]] = {
                **fam_axes,
                "state_band": STATE_BANDS, "session": SESSIONS,
                "trigger_atr": TRIGGER_ATR, "rest_bars": REST_BARS,
                "ttl_mult": TTL_MULT, "rr_mult": RR_MULT,
                "bank_frac": BANK_FRAC, "trail_k": TRAIL_K,
            }
            rows: list[dict[str, Any]] = []
            for _ in range(DRAWS):
                g = _draw(rng, axes)
                kw = {k: v for k, v in g.items() if k in fam_axes}
                try:
                    with contextlib.redirect_stdout(None):
                        sigs = fn(train, **kw)
                    sigs = FAM.apply_layers(list(sigs or []), FAM._h1(train),
                                            **{k: g[k] for k in LAYER_GENES})
                    ds = eg.daily_series(train, sigs, costs) if sigs else None
                except Exception:
                    continue
                evaluated += 1
                rows.append({"genome": g, "n_signals": len(sigs),
                             "fitness": _growth(ds) if ds is not None else float("nan")})

            anova = _anova(rows, list(axes))
            live = [r for r in rows if math.isfinite(float(r["fitness"]))]
            live.sort(key=lambda r: -float(r["fitness"]))
            # THE INCUMBENT: every family kwarg at its declared default and every outside layer
            # at the value alpha_evolution's RECIPE implies. This is what the desk searches today.
            base_g = {**{k: v[len(v) // 2] for k, v in fam_axes.items()},
                      "state_band": "any", "session": "any", "trigger_atr": 0.0,
                      "rest_bars": 1, "ttl_mult": 1.0, "rr_mult": 1.0,
                      "bank_frac": 0.0, "trail_k": 0.0}

            def _test_fit(g: dict[str, Any], _fn: Any = fn, _fa: dict[str, Any] = fam_axes,
                          _test: Any = test, _costs: Any = costs) -> tuple[float, int]:
                kw = {k: v for k, v in g.items() if k in _fa}
                try:
                    with contextlib.redirect_stdout(None):
                        s = _fn(_test, **kw)
                    s = FAM.apply_layers(list(s or []), FAM._h1(_test),
                                         **{k: g[k] for k in LAYER_GENES})
                    if not s:
                        return (float("nan"), 0)
                    return (_growth(eg.daily_series(_test, s, _costs)), len(s))
                except Exception:
                    return (float("nan"), 0)

            base_fit, base_n = _test_fit(base_g)
            # THE CARRY-FORWARD RULE, PRE-DECLARED AND NOT A TEST-SET SELECTION. The single
            # train-best genome is very often over-filtered -- it wins on train by trading twelve
            # times and then produces nothing at all out of sample, which reports as `None` and
            # tells the reader nothing. So the top TOP_K train genomes are carried in TRAIN RANK
            # ORDER and the first one that TRADES out of sample is the one reported. The
            # criterion is "does it trade", never "does it win": the fitness of the carried
            # genome is still whatever the held-out window gives it, including negative.
            best = None
            best_fit, best_n, best_rank = float("nan"), 0, None
            for rank, cand in enumerate(live[:TOP_K], start=1):
                f, nn = _test_fit(cand["genome"])
                if nn >= MIN_TEST_SIGNALS:
                    best, best_fit, best_n, best_rank = cand, f, nn, rank
                    break
            if best is None and live:
                best = live[0]
                best_fit, best_n = _test_fit(best["genome"])
                best_rank = 1
            surfaces.append({
                "symbol": sym, "family": fam,
                "n_sampled": len(rows), "n_scored": len(live),
                "interaction": anova,
                "incumbent_recipe": {"genome": base_g, "test_growth": None
                                     if not math.isfinite(base_fit) else round(base_fit, 8),
                                     "test_signals": base_n},
                "best_joint": None if not best else {
                    "genome": best["genome"],
                    "train_rank_carried": best_rank,
                    "train_growth": round(float(best["fitness"]), 8),
                    "test_growth": None if not math.isfinite(best_fit) else round(best_fit, 8),
                    "test_signals": best_n},
                "joint_beats_incumbent_out_of_sample": (
                    None if not (math.isfinite(best_fit) and math.isfinite(base_fit))
                    else bool(best_fit > base_fit)),
            })
            if best and math.isfinite(best_fit) and best_fit > 0 and best_n >= MIN_TEST_SIGNALS:
                corr = None
                if book is not None:
                    with contextlib.suppress(Exception):
                        raw = list(fn(test, **{k: v for k, v in best["genome"].items()
                                               if k in fam_axes}))
                        s = eg.daily_series(test, FAM.apply_layers(
                            raw, FAM._h1(test),
                            **{k: best["genome"][k] for k in LAYER_GENES}), costs)
                        j = pd.concat([pd.Series(s), book], axis=1).dropna()
                        if len(j) >= 20:
                            corr = round(float(np.corrcoef(j.iloc[:, 0], j.iloc[:, 1])[0, 1]), 4)
                winners.append({
                    "symbol": sym, "family": fam, "genome": best["genome"],
                    "test_growth": round(best_fit, 8), "test_signals": best_n,
                    "correlation_to_book": corr,
                    "portfolio_role": (f"UNMEASURED -- {book_why}"
                                       if corr is None else
                                       "diversifier" if abs(corr) < 0.3 else "return_seeker"),
                })

    if not surfaces:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no (symbol, family) pair produced a scorable sample -- no live symbol "
                        "has enough history, or the canonical evaluator returned nothing")}

    beats = [s for s in surfaces if s["joint_beats_incumbent_out_of_sample"] is True]
    measured = [s for s in surfaces if s["interaction"].get("status") == "OK"]
    not_sep = [s for s in measured if s["interaction"]["n_pairs_over_5pct"] > 0]
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_surfaces": len(surfaces), "n_genomes_evaluated": evaluated,
        "protocol": {"families": list(FAMILIES), "draws_per_surface": DRAWS,
                     "bars": BARS, "train_frac": TRAIN_FRAC, "embargo": EMBARGO,
                     "rank_risk_frac": RANK_RISK_FRAC, "seed": SEED,
                     "evaluator": "external_gauntlet.daily_series + costs_for (canonical)"},
        "surfaces": surfaces,
        "n_joint_beats_incumbent": len(beats),
        "n_surfaces_not_separable": len(not_sep),
        "headline": (
            f"{len(not_sep)} of {len(measured)} measured surfaces are NOT separable -- at least "
            f"one axis pair carries more than 5% of fitness variance in its interaction alone. "
            f"The joint genome beats the fixed recipe out of sample on {len(beats)} of "
            f"{len(surfaces)} surfaces."
            if measured else
            "no surface produced enough finite genomes for a variance decomposition"),
        "winners": winners,
        "boundary": (
            "NOTHING HERE CERTIFIES OR SIZES. Winners are DONATED through proposer_common.donate, "
            "which stamps them point-in-time and pre-registers the hypothesis card, and they then "
            "face the identical ten gates as every other candidate. Search runs on train; every "
            "number that leaves this organ is computed on the held-out remainder."),
        "why": (
            "alpha_evolution wraps every expression it evolves in six constants -- norm 240, "
            "entry_z 1.5, hold 8, atr_n 20, stop 2.0 ATR, rr 1.5 -- and the registered families "
            "declare param grids nine points wide. That is only correct if the layers are "
            "separable, which is an empirical claim the desk has never tested. This measures it."),
    }


def _donate(doc: dict[str, Any]) -> dict[str, Any]:
    """Winners into the gauntlet's intake, through the stamped contract and nothing else."""
    rows = doc.get("winners") or []
    if not rows:
        return {"donated": 0, "why": "no genome cleared a positive out-of-sample growth"}
    try:
        from research.proposer_common import donate
    except ImportError as exc:
        return {"donated": 0, "why": f"proposer_common unavailable ({exc})"}
    cands: list[dict[str, Any]] = []
    for w in rows:
        g = w["genome"]
        # THE DONATED FAMILY IS `joint_genome`, NOT THE BASE FAMILY, and that is the whole
        # difference between a candidate and a zombie. `build_cell` calls the named family with
        # these params; handing `momentum_volgate` a `trigger_atr` kwarg it does not accept makes
        # the cell unbuildable and the row dies silently in the intake. `family_joint_genome`
        # takes the base family by name and applies the identical layer transform this search
        # scored, so the gauntlet judges the object that won.
        cands.append({
            "symbol": w["symbol"], "family": "joint_genome",
            "params": {"base_family": w["family"], **dict(g)},
            "base_family": w["family"],
            "exp_r": None, "n": w["test_signals"],
            "source": "joint_evolution",
            "mechanism_status": "NAMED",
            "mechanism": "joint_layer_interaction",
            "mechanism_note": (
                "the family's own mechanism, executed under a jointly searched state condition, "
                "horizon, entry, exit and execution policy rather than the desk's fixed recipe"),
            "falsifier": (
                "re-run the SAME family at its declared defaults on the same out-of-sample "
                "window; if the fixed recipe scores as well, the joint genome found nothing and "
                "the interaction structure this cell claims is sampling noise"),
            "payer": "whoever is on the other side of a worse execution policy",
            "measurement_class": "DIRECT",
            "selection_trials": int(doc.get("n_genomes_evaluated") or 0),
        })
    try:
        path = donate("joint_evolution", cands, int(doc.get("n_genomes_evaluated") or 0))
    except Exception as exc:
        return {"donated": 0, "why": f"donation refused: {type(exc).__name__}: {exc}"}
    return {"donated": len(cands) if path else 0,
            "path": str(path) if path else None,
            "why": None if path else "every row was refused at the point-in-time door"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report and donate winners")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") == "UNMEASURED":
        print(f"joint evolution: UNMEASURED -- {doc.get('why')}")
        return 0
    print(f"joint evolution: {doc['status']}   {doc['n_surfaces']} surface(s), "
          f"{doc['n_genomes_evaluated']} genome(s) evaluated")
    print(f"  {doc['headline']}")
    for s in doc["surfaces"]:
        iv = s["interaction"]
        inc = s["incumbent_recipe"]["test_growth"]
        bj = (s["best_joint"] or {}).get("test_growth")
        print(f"  {s['symbol']:<9} {s['family']:<24} "
              f"incumbent {inc if inc is None else f'{inc:+.6f}'}  "
              f"joint {bj if bj is None else f'{bj:+.6f}'}  "
              f"{iv.get('n_pairs_over_5pct', '-')} interacting pair(s)")
        for p in (iv.get("top_interactions") or [])[:2]:
            if float(p["interaction_share"]) > 0.05:
                print(f"       {p['axes'][0]} x {p['axes'][1]}: "
                      f"{float(p['interaction_share']):.1%} of fitness variance "
                      f"({p['layers'][0]} x {p['layers'][1]})")
    for w in doc["winners"][:8]:
        print(f"  WINNER {w['symbol']:<9} {w['family']:<24} growth {w['test_growth']:+.6f} "
              f"n={w['test_signals']} role={w['portfolio_role']}")
    if not a.apply:
        print("  --apply not given; nothing written, nothing donated")
        return 0
    doc["donation"] = _donate(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"  donated {doc['donation'].get('donated', 0)} candidate(s) to the gauntlet intake"
          f"{'' if not doc['donation'].get('why') else ' -- ' + str(doc['donation']['why'])}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
