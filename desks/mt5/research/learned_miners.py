"""Two LEARNED miners that emit gauntlet cells: graph propagation and attention, numpy only.

WHAT THIS IS. `libs/research/adapters/pyg_temporal.py` trains a GConvGRU on the symbol graph and
returns a REPRESENTATION packet -- embeddings and a loss curve -- that nothing downstream can
certify, and it needs torch, which the trading box does not have. These two miners are the same
ideas built so their output is a CELL:

  learned_gnn      family `gnn_propagation`: next-day forecast from 1-2 hops of propagation over
                   a lead-lag (or co-movement) graph measured on the training window, ridge
                   readout shared by every node. Mechanism: cross-asset information diffusion --
                   news priced first in one market reaches the slower one with a lag
                   (`alpha_schema.EVENTS["cross_market_lead"]`).
  learned_attention family `attention_ts`: next-day forecast from scaled dot-product attention
                   over each instrument's last L daily tokens, weights shared across the panel.
                   Mechanism: state-dependent continuation versus reversal -- whether a move is
                   absorbed (a liquidity concession that reverts) or propagates depends on the
                   recent path (`alpha_schema.EVENTS["inventory_shock"]`).

THE DOOR IS THE ONE EVERY PROPOSER USES. Exactly `cross_asset_graph`'s path: the family's own
signals on the desk's own bars go through `proposer_common.screen` (forward return at the cell's
own hold, net of the desk's round trip, non-overlapping), `proposer_common.deflate` charges the
whole sweep, `best_per_cell` keeps one proposal per (symbol, family), `candidate` writes the row
and `donate` stamps, pre-registers and writes `data/intelligence/<source>/discoveries_*.json` and
the canonical registry. `miner_candidate_compiler` admits the rows as EXACT_RECIPE because both
families are registered in `mt5desk.families_orthogonal`, and `external_gauntlet.build_cell`
rebuilds them from (symbol, family, params) with no new wiring -- the family resolves its own
peer panel.

EVERY CONFIGURATION IS A TRIAL. The model grids are declared in `libs/models/learned_propagation`
(four configurations each, fixed before any result). Each (configuration x symbol x entry
threshold) the miner evaluates is charged, whether or not the screen could score it, and the
deflation uses that attempted count -- never the count of rows that happened to screen. The same
trials are priced by `libs/research/trial_ledger` (effective count beside raw) and appended to
`data/learned_miners_trials.jsonl`.

THE MEASURABLE CONTRACT (`--contract`). On the bars in git (`desks/mt5/universe/*_H1.parquet`),
walk-forward, it reports OOS IC / rank-IC / hit rate / a cost-charged long-short Sharpe for every
configuration of both models against ridge on the same features, the naive last-return forecast
and the zero forecast, plus a time-shuffled falsification control, and writes
`reports/learned_miners_contract.json`. Whatever it shows is what it reports.

SCHEDULING: this organ runs DAILY as a `daily_cycle` proposer (`daily_cycle._proposers`, which
calls `run(budget_s=...)`), on its own budget. It is deliberately not on the hourly roster, so it
takes no share of any hourly miner's time. `--once` runs one pass by hand.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_learned_propagation as FLP  # noqa: E402

from libs.models import learned_propagation as LP  # noqa: E402
from libs.research import trial_ledger as TL  # noqa: E402
from research import proposer_common as pc  # noqa: E402

REPORT = _DESK / "reports" / "learned_miners.json"
CONTRACT_REPORT = _DESK / "reports" / "learned_miners_contract.json"
TRIALS = _DESK / "data" / "learned_miners_trials.jsonl"
GIT_BARS = _DESK / "universe"
BUDGET_S = 900.0

#: The declared panel: every FX / metals / crypto-CFD instrument whose H1 history is held in git.
#: The panel IS the hypothesis for both families (the graph is measured over it, the attention
#: weights are shared over it), so it is fixed here rather than re-chosen per run.
PANEL: tuple[str, ...] = (
    "AUDCAD", "AUDJPY", "AUDNZD", "AUDUSD", "BTCUSD", "CADJPY", "CHFJPY", "ETHUSD", "EURAUD",
    "EURCHF", "EURGBP", "EURJPY", "EURUSD", "GBPAUD", "GBPJPY", "GBPUSD", "NZDCAD", "NZDJPY",
    "NZDUSD", "USDCAD", "USDCHF", "USDJPY", "XAGUSD", "XAUUSD")

#: Entry thresholds on forecast strength (|pred| / trailing RMS). Each is a trial.
ENTRY_Z: tuple[float, ...] = (1.0, 1.5)
#: Fixed signal geometry (not searched): act at 02:00 broker on the day after the close the
#: forecast used, hold to ~23:00, trailing-RMS window of 120 days.
FIXED = {"norm": 120, "hold_bars": 20, "signal_hour": 2}

MINERS: dict[str, dict[str, Any]] = {
    "gnn": {
        "source": "learned_gnn", "family": "gnn_propagation", "grid": LP.GNN_GRID,
        "event": "cross_market_lead",
        "mechanism": ("cross-asset information diffusion: {sym}'s next-day return is forecast by "
                      "propagating the panel's latest moves {hops} hop(s) through a {adj} graph "
                      "measured on the training window only, so markets that price shared "
                      "news first lead the slower ones"),
        "falsifier": ("the out-of-sample IC of the propagated forecast is no better than ridge "
                      "on the instrument's own lags, or the learned edges reverse between "
                      "walk-forward windows, or a time-shuffled panel shows the same edge"),
        "constraint": ("attention, mandate and session-hour limits make some markets reprice "
                       "shared news later than others"),
        "failure_mode": ("the lead-lag edges are a closing-time artefact of instruments that "
                         "stop quoting at different hours, so the lag disappears once the "
                         "daily closes are synchronised"),
        "crowding_prior": "high",
    },
    "attention": {
        "source": "learned_attention", "family": "attention_ts", "grid": LP.ATTENTION_GRID,
        "event": "inventory_shock",
        "mechanism": ("state-dependent continuation versus reversal on {sym}: attention over the "
                      "last {lookback} daily tokens ({heads} head(s), weights shared across the "
                      "panel) decides whether yesterday's move is a liquidity concession that "
                      "reverts or information that continues"),
        "falsifier": ("the out-of-sample IC of the attention forecast is no better than ridge on "
                      "the same flattened lags, or the attended positions carry no information "
                      "beyond the last return"),
        "constraint": ("dealer inventory and risk limits force temporary price concessions that "
                       "unwind once the inventory is laid off"),
        "failure_mode": ("the attention weights fit a volatility-regime artefact of the training "
                         "window, and the learned continuation/reversal switch flips sign "
                         "out of sample"),
        "crowding_prior": "medium",
    },
}

#: The dominant participant structure of the instruments the cell trades (the desk's vocabulary:
#: retail_heavy, institutional, tax_driven, policy_driven, physical_flow, broker_specific,
#: settlement_constrained). Crypto CFDs are retail-heavy venues; pegged or managed crosses are
#: policy-driven; the metals carry physical flow; every other liquid FX pair is institutional.
_PARTICIPANTS: dict[str, str] = {"BTCUSD": "retail_heavy", "ETHUSD": "retail_heavy",
                                 "EURCHF": "policy_driven", "XAUUSD": "physical_flow",
                                 "XAGUSD": "physical_flow"}


def participant_structure(symbol: str) -> str:
    return _PARTICIPANTS.get(str(symbol).upper(), "institutional")


def _event(name: str) -> dict[str, str]:
    try:
        from libs.research.alpha_schema import EVENTS
        return dict(EVENTS.get(name, {}))
    except Exception:
        return {}


def _config_key(model: str, cfg: Mapping[str, Any]) -> str:
    return f"{model}:" + ",".join(f"{k}={cfg[k]}" for k in sorted(cfg))


# =========================================================================== candidates
def make_candidate(model: str, row: dict[str, Any], *, panel: Sequence[str],
                   tests_run: int, n_effective: float) -> dict[str, Any]:
    """One screened row as a miner-discovery contract row, via `proposer_common.candidate`.

    `family` + `params` + `symbol` is what the compiler's EXACT_RECIPE path needs; the params are
    exactly the arguments the screen called the family with, plus the chart pin (`timeframe`),
    which stops the compiler multiplying a once-a-day forecast across the intraday charts.
    """
    spec = MINERS[model]
    ev = _event(spec["event"])
    cfg = dict(row["config"])
    sym = str(row["symbol"])
    params = {"symbol": sym, "peer_symbols": list(panel), **cfg, "entry_z": row["entry_z"],
              **FIXED, "timeframe": "H1"}
    mech = spec["mechanism"].format(sym=sym, hops=cfg.get("layers"), adj=cfg.get("adjacency"),
                                    lookback=cfg.get("lookback"), heads=cfg.get("heads"))
    title = (f"{sym}.{spec['family']} {_config_key(model, cfg)} z>={row['entry_z']} "
             f"hold={FIXED['hold_bars']}")
    # The miner's own walk-forward IC stays in its REPORT and off the row: `libs.tiers.blinding`
    # strips any `oos_*` field at the write door and counts the row as a proposer that read
    # held-out outcomes, which would withhold this seat from the independent-discovery count.
    evidence = {k: row.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}
    evidence.update({"tests_attempted": tests_run, "effective_trials": round(n_effective, 3),
                     "model_config": _config_key(model, cfg)})
    c = pc.candidate(spec["source"], sym, spec["family"], params, mechanism=mech, title=title,
                     evidence=evidence)
    c.update({
        "mechanism_event": spec["event"],
        "payer": ev.get("payer", ""),
        "constraint": spec["constraint"],
        "source_culture": "global/model",
        "participant_structure": participant_structure(sym),
        "failure_mode_hypothesis": spec["failure_mode"],
        "crowding_prior": spec["crowding_prior"],
        "economic_rationale": ev.get("mechanism", ""),
        "falsifier": spec["falsifier"],
        "effective_trials": round(n_effective, 3),
        "tests_run": tests_run,
        "trial_family": f"{spec['source']}:{spec['family']}",
        "model_family": model,
        "lineage": {"root": f"learned_miners:{model}", "parent_family": "ridge_own_lags",
                    "novelty_key": f"{spec['family']}|{_config_key(model, cfg)}",
                    "source": spec["source"]},
    })
    return c


def _redeflate(rows: list[dict[str, Any]], n_attempted: int) -> list[dict[str, Any]]:
    """`proposer_common.deflate` charges len(rows) -- the rows that SCREENED. A configuration
    whose signals were too few to screen was still tried, so the charge is re-applied at the
    attempted count whenever that is larger. Same rule, same threshold, larger n."""
    from research.multiplicity import deflate_t
    rows = pc.deflate(rows)
    if n_attempted > len(rows):
        for r in rows:
            r["n_tests_sweep"] = n_attempted
            r["t_deflated_sweep"] = round(deflate_t(float(r["t_gross"]), n_attempted), 3)
            r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > pc.PROPOSE_T
                                 and int(r.get("n_independent", 0)) >= pc.MIN_TRADES)
    return rows


# ================================================================================ miner
def mine(model: str, bars: Mapping[str, pd.DataFrame], meta: Mapping[str, Any], *,
         deadline: float, grid: Sequence[Mapping[str, Any]] | None = None,
         entry_z: Sequence[float] = ENTRY_Z) -> dict[str, Any]:
    """Walk-forward every configuration, screen every (config, symbol, threshold), charge all."""
    spec = MINERS[model]
    fam_fn = (FLP.family_gnn_propagation if model == "gnn" else FLP.family_attention_ts)
    panel_syms = sorted(bars)
    tick = {s: float((meta.get(s) or {}).get("tick_size") or 0.0) for s in panel_syms}
    eval_panel = LP.daily_panel(bars, tick)
    des = LP.design(eval_panel)
    rows: list[dict[str, Any]] = []
    trials: list[TL.Trial] = []
    configs: dict[str, Any] = {}
    skipped: dict[str, str] = {}
    attempted = 0
    unf = {s: pc.artifact_hours(bars[s]) for s in panel_syms}
    costs = {s: pc.cost_frac(s, dict(meta), bars[s]["close"]) for s in panel_syms}
    for cfg in (grid or spec["grid"]):
        ck = _config_key(model, cfg)
        if time.monotonic() > deadline:
            configs[ck] = {"verdict": "UNMEASURED", "why": "budget exhausted before this config"}
            continue
        t0 = time.monotonic()
        got = FLP.panel_predictions(bars[panel_syms[0]], panel_syms[0], panel_syms, bars,
                                    "gnn" if model == "gnn" else "attention", cfg)
        if got is None:
            configs[ck] = {"verdict": "UNMEASURED", "why": "panel too short or a peer missing"}
            continue
        _panel, preds = got
        configs[ck] = {"config": dict(cfg), "fit_seconds": round(time.monotonic() - t0, 2),
                       **LP.evaluate(preds, eval_panel, des)}
        per_sym = LP.per_symbol_ic(preds, eval_panel)
        for sym in panel_syms:
            for z in entry_z:
                attempted += 1
                trials.append(TL.Trial(
                    trial_id=f"{sym}:{ck}:z{z}", family=f"{spec['source']}:{spec['family']}",
                    descriptors={"symbol": sym, "model_family": model, "horizon": "1d",
                                 "mechanism": spec["event"], "representation": ck},
                    params={**{k: v for k, v in cfg.items() if not isinstance(v, str)},
                            "entry_z": z}))
                if costs[sym] is None:
                    skipped[sym] = "no contract terms to price the round trip"
                    continue
                sig = fam_fn(bars[sym], symbol=sym, peer_symbols=panel_syms, peers=bars,
                             entry_z=z, **FIXED, **cfg)
                sc = pc.screen(bars[sym], sig, float(costs[sym]), unf[sym])
                if sc is None:
                    continue
                rows.append({"cell": f"{sym}.{spec['family']}", "symbol": sym,
                             "config": dict(cfg), "entry_z": z, **sc,
                             "wf_ic_symbol": (per_sym.get(sym) or {}).get("ic"),
                             "wf_ic_t_symbol": (per_sym.get(sym) or {}).get("t")})
    rows = _redeflate(rows, attempted)
    census = TL.census(trials)
    proposals = pc.best_per_cell(rows)
    return {"model": model, "source": spec["source"], "family": spec["family"],
            "panel": panel_syms, "configs": configs, "tests_attempted": attempted,
            "tests_screened": len(rows), "effective_trials": round(census.n_effective, 3),
            "trial_census": census.to_dict(), "skipped": skipped, "rows": rows,
            "proposals": proposals, "_trials": trials}


# ================================================================ the indirect door: axes
#: What a forecast row is knowable at: the next calendar day's 03:00 on the bar clock. The close
#: a forecast uses is broker 24:00 (21:00-22:00 UTC), so 03:00 the next day is after it whether a
#: reader joins on true UTC or on the broker-labelled bar index -- late by a few hours, never
#: early.
KNOWABLE_HOUR = 3


def forecast_axis(model: str, bars: Mapping[str, pd.DataFrame] | None = None,
                  config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The PRIMARY configuration's walk-forward forecast as an `axis_ingest` document.

    Shape `rows` keyed by (symbol, knowable_at), the same shape as the COT axis, so
    `libs.research.alpha_dsl.axis_fields` exposes `<id>.forecast`, `<id>.strength` and
    `<id>.xs_rank` per instrument with a causal `knowable_at` rule, and every family the
    expression search conditions or interacts can bind them. Only the pre-declared primary
    configuration is published: publishing the whole grid would hand the downstream search eight
    near-copies of one variable and charge none of the selection.
    """
    spec = MINERS[model]
    cfg = dict(config or spec["grid"][0])
    bars = dict(bars) if bars is not None else load_bars()
    syms = sorted(bars)
    got = FLP.panel_predictions(bars[syms[0]], syms[0], syms, bars,
                                "gnn" if model == "gnn" else "attention", cfg)
    rows: list[dict[str, Any]] = []
    if got is not None:
        panel, preds = got
        strength = np.column_stack([FLP.forecast_strength(preds[:, j], int(FIXED["norm"]))
                                    for j in range(len(panel.symbols))])
        for t, day in enumerate(panel.dates):
            p = preds[t]
            ok = np.isfinite(p) & np.isfinite(panel.ret[t])
            if ok.sum() == 0:
                continue
            ranks = np.full(p.size, np.nan)
            if ok.sum() > 1:
                order = np.argsort(np.argsort(p[ok]))
                ranks[ok] = order / (ok.sum() - 1)
            knowable = (day + pd.Timedelta(days=1, hours=KNOWABLE_HOUR)).isoformat()
            for j in np.where(ok)[0]:
                rows.append({"symbol": panel.symbols[j], "knowable_at": knowable,
                             "as_of": str(day.date()),
                             "forecast": round(float(p[j]), 5),
                             "strength": (None if not np.isfinite(strength[t, j])
                                          else round(float(strength[t, j]), 4)),
                             "xs_rank": (None if not np.isfinite(ranks[j])
                                         else round(float(ranks[j]), 4))})
    return {"axis": "learned_forecast", "id": f"{model}_forecast",
            "source": "desks/mt5/research/learned_miners.py",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "family": spec["family"], "model": model, "config": cfg,
            "walk_forward": {"min_train_days": LP.MIN_TRAIN, "refit_every_days": LP.REFIT_EVERY,
                             "train_window_days": LP.TRAIN_WINDOW},
            "n_rows": len(rows), "symbols": sorted({r["symbol"] for r in rows}),
            "n_symbols": len({r["symbol"] for r in rows}),
            "knowable_rule": (f"next calendar day {KNOWABLE_HOUR:02d}:00 after the broker close "
                              "of `as_of`; the model was fitted on closes before `as_of`"),
            "shape": ("rows indexed by (symbol, knowable_at): forecast = next-day vol-scaled "
                      "return forecast, strength = forecast / trailing RMS, xs_rank = "
                      "cross-sectional percentile that day"),
            "rows": rows}


INTEL_REPORT = _DESK / "reports" / "GNN_ATTENTION_ALLOCATION_INTEL.json"


def _contract_verdicts(path: Path = CONTRACT_REPORT) -> dict[str, str]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return {m: str(b.get("verdict")) for m, b in (doc.get("miners") or {}).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def allocation_intel(axis_docs: Mapping[str, Mapping[str, Any]],
                     evidence: Mapping[str, Mapping[str, Any]] | None = None,
                     contract: Path = CONTRACT_REPORT) -> dict[str, Any]:
    """Per instrument, the LATEST point-in-time forecast of each miner, with the evidence behind it.

    INFORMATIONAL. `allocation_eligible` is True for a model only when the measurable contract's
    verdict for it is GAIN; otherwise the forecast is published so it can be read and audited but
    no allocator should size on it (a capital modifier must first show a robust E[log W] gain).
    """
    verdicts = _contract_verdicts(contract)
    per: dict[str, dict[str, Any]] = {}
    models: dict[str, Any] = {}
    for model, doc in axis_docs.items():
        v = verdicts.get(model, "UNMEASURED")
        models[model] = {"family": doc.get("family"), "config": doc.get("config"),
                         "contract_verdict": v, "allocation_eligible": v == "GAIN",
                         "oos_evidence": dict((evidence or {}).get(model) or {})}
        latest: dict[str, dict[str, Any]] = {}
        for r in doc.get("rows") or []:
            s = str(r.get("symbol"))
            if s not in latest or str(r["knowable_at"]) > str(latest[s]["knowable_at"]):
                latest[s] = r
        for s, r in latest.items():
            per.setdefault(s, {})[model] = {k: r.get(k) for k in ("as_of", "knowable_at",
                                                                   "forecast", "strength",
                                                                   "xs_rank")}
    return {"generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "pit": ("every value is the walk-forward forecast knowable at its knowable_at; "
                    "nothing here was fitted on data after its as_of date"),
            "rule": ("informational only: a model is allocation_eligible only when "
                     "reports/learned_miners_contract.json measures GAIN for it"),
            "models": models, "instruments": dict(sorted(per.items()))}


def _append_trials(rows: list[dict[str, Any]], path: Path) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
        return ""
    except OSError as exc:
        return f"trial ledger not written: {type(exc).__name__}: {exc}"


def load_bars(symbols: Sequence[str] = PANEL, base: Path | None = None
              ) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for s in symbols:
        if base is None:
            b = pc.bars(s)
        else:
            p = base / f"{s}_H1.parquet"
            b = None
            if p.exists():
                b = pd.read_parquet(p)
                b.index = pd.DatetimeIndex(pd.to_datetime(b.index, utc=True, errors="coerce"))
                b = b[~b.index.isna()]
        if b is not None and len(b) > 0:
            out[s] = b
    return out


def run(budget_s: float = BUDGET_S, models: Sequence[str] = ("gnn", "attention"),
        bars: Mapping[str, pd.DataFrame] | None = None, meta: Mapping[str, Any] | None = None,
        donate: bool = True, report: Path | None = None,
        trials_path: Path | None = None, publish_axes: bool = True,
        axes_dir: Path | None = None, intel_path: Path | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + float(budget_s)
    bars = dict(bars) if bars is not None else load_bars()
    meta = dict(meta) if meta is not None else pc.universe_meta()
    out: dict[str, Any] = {"generated_at": datetime.now(tz=UTC).isoformat(),
                           "panel": sorted(bars), "miners": {}}
    total_proposed = 0
    axis_docs: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for model in models:
        res = mine(model, bars, meta, deadline=deadline)
        # THE INDIRECT DOOR: the primary configuration's forecast (already computed above, so
        # this is a cache hit) becomes a dated conditioning axis every expression family can bind.
        prim = _config_key(model, MINERS[model]["grid"][0])
        evidence[model] = {k: (res["configs"].get(prim) or {}).get(k)
                           for k in ("ic_mean", "ic_t", "rank_ic_t", "hit_rate",
                                     "ls_sharpe_net", "oos_days")}
        if publish_axes and "config" in (res["configs"].get(prim) or {}):
            doc = forecast_axis(model, bars)
            axis_docs[model] = doc
            try:
                import axis_ingest
                res["axis_published"] = str(axis_ingest.publish(doc["id"], doc, axes_dir,
                                                                report=None))
            except Exception as exc:
                res["axis_published"] = f"NOT WRITTEN: {type(exc).__name__}: {exc}"
            res["axis_rows"] = doc["n_rows"]
        trials = res.pop("_trials")
        cands = [make_candidate(model, r, panel=res["panel"], tests_run=res["tests_attempted"],
                                n_effective=res["effective_trials"])
                 for r in res["proposals"]]
        res["candidates"] = len(cands)
        donated_file = False
        if donate and cands:
            door = pc.donate(res["source"], cands, res["tests_attempted"])
            res["donated"] = str(door)
            # The door can refuse every candidate (lane, blinding, pre-registration) and write no
            # discovery file; then nothing charged the trials there, so the side ledger must.
            donated_file = door is not None
            res["donation"] = pc.donation_counts()
        res["rows"] = res["rows"][:200]
        total_proposed += len(cands)
        led = _append_trials([{"generated_utc": out["generated_at"], "source": res["source"],
                               "trial_id": t.trial_id, "family": t.family,
                               "descriptors": dict(t.descriptors),
                               "donated": donated_file} for t in trials],
                             trials_path or TRIALS)
        res["trial_ledger_error"] = led
        out["miners"][model] = res
    out["cells_proposed"] = total_proposed
    if axis_docs:
        ip = intel_path or INTEL_REPORT
        ip.parent.mkdir(parents=True, exist_ok=True)
        ip.write_text(json.dumps(allocation_intel(axis_docs, evidence), indent=1, default=str),
                      "utf-8")
        out["allocation_intel"] = str(ip)
    path = report or REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    try:
        from libs.ops import events
        events.emit("learned_miners", leg="learned_miners", cells=total_proposed)
    except Exception:
        pass
    return out


# ============================================================================ contract
def _git_meta() -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for p in (_DESK / "data" / "universe" / "universe.json", GIT_BARS / "universe.json"):
        with contextlib.suppress(OSError, ValueError):
            meta.update({k: v for k, v in json.loads(p.read_text("utf-8")).items()
                         if isinstance(v, dict)})
    return meta


def _shuffled(panel: LP.Panel, seed: int = 11) -> LP.Panel:
    """The falsification control: each instrument's return series permuted in time on its own,
    which destroys every lead-lag and every serial dependence while keeping each marginal."""
    rng = np.random.default_rng(seed)
    ret = panel.ret.copy()
    for j in range(ret.shape[1]):
        ok = np.where(np.isfinite(ret[:, j]))[0]
        ret[ok, j] = ret[rng.permutation(ok), j]
    return LP.Panel(panel.dates, panel.symbols, ret, panel.cost)



def _cell_screen(bars: Mapping[str, pd.DataFrame], meta: Mapping[str, Any],
                 deflate_t: Any) -> dict[str, Any]:
    """EVERY (config, symbol, threshold) test the miner charges, committed, not only the best.

    The claim "best of N, deflated to t" is only checkable if all N rows are in the artifact."""
    out: dict[str, Any] = {}
    keep = ("cell", "config", "symbol", "entry_z", "t_gross", "t_deflated_sweep",
            "t_deflated_lifetime", "n_independent", "net_per_trade", "clears_cost", "proposed")
    for model in MINERS:
        res = mine(model, bars, meta, deadline=time.monotonic() + 3600.0)
        rows = [{k: r.get(k) for k in keep} for r in res["rows"]]
        tried: dict[str, int] = {}
        for t in res["_trials"]:
            sym = str(t.trial_id).split(":", 1)[0]
            tried[sym] = tried.get(sym, 0) + 1
        got: dict[str, int] = {}
        for r in rows:
            got[str(r.get("symbol"))] = got.get(str(r.get("symbol")), 0) + 1
        unscreened = {sym: k - got.get(sym, 0) for sym, k in sorted(tried.items())
                      if k > got.get(sym, 0)}
        rows.sort(key=lambda r: -abs(float(r.get("t_gross") or 0.0)))
        best = rows[0] if rows else None
        n = int(res["tests_attempted"])
        out[model] = {
            "tests_attempted": n, "tests_screened": len(rows),
            "not_screened": n - len(rows), "effective_trials": res["effective_trials"],
            "not_screened_by_symbol": unscreened,
            "not_screened_reason": ("tried and CHARGED, but too few forecast signals cleared the "
                                    "entry threshold on the walk-forward window for the screen to "
                                    "score them (the symbol's bar history in git is shorter than "
                                    "the panel's)"),
            "best": best,
            "best_t_deflated_by_attempted": (round(float(deflate_t(float(best["t_gross"]), n)), 3)
                                             if best and best.get("t_gross") is not None
                                             else None),
            "proposed": sum(1 for r in rows if r.get("proposed")),
            "rows": rows}
    m_union = sum(int(v["tests_attempted"]) for v in out.values())
    out["union_headline"] = {
        "m": m_union,
        "rule": "each miner's best t deflated over the UNION of every test both miners ran",
        **{model: (round(float(deflate_t(float(v["best"]["t_gross"]), m_union)), 3)
                   if v.get("best") and v["best"].get("t_gross") is not None else None)
           for model, v in out.items() if isinstance(v, dict) and "best" in v}}
    return out


def measure_contract(base: Path = GIT_BARS, out_path: Path | None = None) -> dict[str, Any]:
    """Walk-forward OOS metrics for both miners against their baselines on the bars in git."""
    from research.multiplicity import deflate_t
    meta = _git_meta()
    bars = load_bars(PANEL, base)
    tick = {s: float((meta.get(s) or {}).get("tick_size") or 0.0) for s in bars}
    panel = LP.daily_panel(bars, tick)
    des = LP.design(panel)
    results: dict[str, Any] = {}
    timings: dict[str, float] = {}

    def score(name: str, model: str, cfg: Mapping[str, Any]) -> None:
        t0 = time.monotonic()
        p = LP.predictions(des, model, cfg)
        timings[name] = round(time.monotonic() - t0, 2)
        results[name] = {"model": model, "config": dict(cfg), **LP.evaluate(p, panel, des)}

    cell_screen = _cell_screen(bars, meta, deflate_t)
    score("zero", "zero", {})
    score("naive_last", "naive_last", {})
    score("ridge_own_lags", "ridge", {})
    for L in sorted({int(c["lookback"]) for c in LP.ATTENTION_GRID}, reverse=True):
        score(f"ridge_lags_L{L}", "ridge_lags", {"lookback": L})
    for cfg in LP.GNN_GRID:
        score(_config_key("gnn", cfg), "gnn", cfg)
    for cfg in LP.ATTENTION_GRID:
        score(_config_key("attention", cfg), "attention", cfg)
    shuf = _shuffled(panel)
    sdes = LP.design(shuf)
    control = LP.evaluate(LP.predictions(sdes, "gnn", LP.GNN_GRID[0]), shuf, sdes)

    def block(model: str, grid: Sequence[Mapping[str, Any]], baseline: str) -> dict[str, Any]:
        keys = [_config_key(model, c) for c in grid]
        prim = results[keys[0]]
        base_r = results[baseline]
        ts = [(k, results[k].get("ic_t")) for k in keys if results[k].get("ic_t") is not None]
        best_k, best_t = max(ts, key=lambda kv: kv[1]) if ts else (None, None)
        return {
            "family": MINERS[model]["family"],
            "primary_config (declared before any result)": keys[0],
            "primary": {k: prim.get(k) for k in ("ic_mean", "ic_t", "rank_ic_mean", "rank_ic_t",
                                                 "hit_rate", "ls_sharpe_gross", "ls_sharpe_net")},
            "baseline": baseline,
            "baseline_metrics": {k: base_r.get(k) for k in ("ic_mean", "ic_t", "rank_ic_mean",
                                                           "rank_ic_t", "hit_rate",
                                                           "ls_sharpe_gross", "ls_sharpe_net")},
            "primary_minus_baseline": {
                k: (None if prim.get(k) is None or base_r.get(k) is None
                    else round(float(prim[k]) - float(base_r[k]), 5))
                for k in ("ic_mean", "rank_ic_mean", "hit_rate", "ls_sharpe_net")},
            "best_of_grid_by_ic_t": best_k,
            "best_of_grid_ic_t": best_t,
            "best_of_grid_ic_t_deflated": (None if best_t is None
                                           else round(deflate_t(float(best_t), len(keys)), 3)),
            "configs_tried_trials_charged": len(keys),
        }

    gnn_b = block("gnn", LP.GNN_GRID, "ridge_own_lags")
    att_b = block("attention", LP.ATTENTION_GRID,
                  f"ridge_lags_L{int(LP.ATTENTION_GRID[0]['lookback'])}")

    def verdict(b: dict[str, Any]) -> str:
        p = b["primary"]
        gain = b["primary_minus_baseline"]
        ic_ok = (p.get("ic_t") or 0) >= 2.0 and (gain.get("ic_mean") or 0) > 0
        sr_ok = (p.get("ls_sharpe_net") or -9) > 0 and (gain.get("ls_sharpe_net") or 0) > 0
        if ic_ok and sr_ok:
            return "GAIN"
        why = [f"IC t {p.get('ic_t')} < 2" if not ic_ok else "",
               f"net Sharpe {p.get('ls_sharpe_net')} not > 0 and above baseline"
               if not sr_ok else ""]
        above = [k for k in ("ic_mean", "ls_sharpe_net") if (gain.get(k) or 0) > 0]
        return ("NO_GAIN: " + "; ".join(w for w in why if w)
                + (f" (directionally above baseline on {', '.join(above)}, not significant)"
                   if above else ""))

    gnn_b["verdict"] = verdict(gnn_b)
    att_b["verdict"] = verdict(att_b)
    doc = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "data": {"bars": "desks/mt5/universe/*_H1.parquet (in git)", "resample": "broker-date "
                 "daily closes, Monday-Friday grid", "symbols": panel.symbols,
                 "n_symbols": len(panel.symbols), "first_date": str(panel.dates[0].date()),
                 "last_date": str(panel.dates[-1].date()), "n_days": len(panel.dates)},
        "protocol": {
            "walk_forward": {"min_train_days": LP.MIN_TRAIN, "refit_every_days": LP.REFIT_EVERY,
                             "rolling_train_window_days": LP.TRAIN_WINDOW},
            "target": "next broker-day log return, volatility-scaled for fitting",
            "ic": "daily cross-sectional Pearson of forecast vs realised next-day return, mean "
                  "and t over days",
            "portfolio": "dollar-neutral, demeaned forecast ranks / sigma_t, gross 1, daily "
                         "rebalance; cost = |dw| x (half the day's median H1 spread from the "
                         "bars' spread column / price + 0.25bp commission) per side",
            "no_tuning": "every constant and both grids were fixed before the first run; every "
                         "configuration is reported and charged",
        },
        "miners": {"gnn": gnn_b, "attention": att_b},
        "falsification_control": {
            "what": "gnn primary on a panel with each instrument's returns permuted in time",
            **{k: control.get(k) for k in ("ic_mean", "ic_t", "rank_ic_t", "hit_rate",
                                           "ls_sharpe_net")}},
        "all_models": results,
        "cell_screen": cell_screen,
        "fit_seconds": timings,
        "trials_charged": {"gnn_configs": len(LP.GNN_GRID),
                           "attention_configs": len(LP.ATTENTION_GRID),
                           "baselines_not_charged": ["zero", "naive_last", "ridge_own_lags"] +
                           [k for k in results if k.startswith("ridge_lags")],
                           "cell_level": ("the miner charges configs x symbols x "
                                          f"{len(ENTRY_Z)} entry thresholds per model = "
                                          f"{len(LP.GNN_GRID) * len(PANEL) * len(ENTRY_Z)} "
                                          "per miner run")},
    }
    path = out_path or CONTRACT_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def _fmt(v: Any) -> str:
    return "  n/a" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:+.4f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="one pass and exit")
    ap.add_argument("--contract", action="store_true",
                    help="measure the OOS contract on the bars in git and exit")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--model", action="append", choices=list(MINERS), default=None)
    ap.add_argument("--no-donate", action="store_true")
    ap.add_argument("--no-axes", action="store_true",
                    help="do not publish the forecast axes or the allocation-intel artifact")
    a = ap.parse_args()
    if a.contract:
        doc = measure_contract()
        print(f"LEARNED MINERS CONTRACT  {doc['data']['n_symbols']} symbols, "
              f"{doc['data']['first_date']}..{doc['data']['last_date']} "
              f"({doc['data']['n_days']} days)")
        print(f"  {'model':34s} {'IC':>8s} {'IC_t':>8s} {'rkIC':>8s} {'hit':>8s} "
              f"{'SRgross':>8s} {'SRnet':>8s}")
        for k, r in doc["all_models"].items():
            print(f"  {k:34s} {_fmt(r.get('ic_mean'))} {_fmt(r.get('ic_t'))} "
                  f"{_fmt(r.get('rank_ic_mean'))} {_fmt(r.get('hit_rate'))} "
                  f"{_fmt(r.get('ls_sharpe_gross'))} {_fmt(r.get('ls_sharpe_net'))}")
        for m, b in doc["miners"].items():
            prim = b["primary_config (declared before any result)"]
            print(f"  {m}: {b['verdict']} (primary {prim} vs {b['baseline']}; "
                  f"{b['configs_tried_trials_charged']} configs charged)")
        c = doc["falsification_control"]
        print(f"  control (time-shuffled): IC_t={_fmt(c.get('ic_t'))} "
              f"SRnet={_fmt(c.get('ls_sharpe_net'))}")
        print(f"written: {CONTRACT_REPORT}")
        return 0
    doc = run(budget_s=a.budget_s, models=tuple(a.model or MINERS), donate=not a.no_donate,
              publish_axes=not a.no_axes)
    for m, r in doc["miners"].items():
        print(f"LEARNED {m}: {r['tests_attempted']} tests attempted, {r['tests_screened']} "
              f"screened, N_eff={r['effective_trials']}, {r['candidates']} proposed"
              + (f" -> {r['donated']}" if r.get("donated") else ""))
    print(f"YIELD {json.dumps({'cells_proposed': doc['cells_proposed']})}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
