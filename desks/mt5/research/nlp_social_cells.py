"""NLP + SOCIAL CELLS -- the admission test and the direct cells for the text-derived indices.

    python desks/mt5/research/nlp_social_cells.py --ingest     # organ battery: fetch + publish
    python desks/mt5/research/nlp_social_cells.py              # daily proposer: test + donate
    python desks/mt5/research/nlp_social_cells.py --dry-run    # measure, write nothing

TWO CLOCKS, BOTH EXISTING. `--ingest` is rostered on the ORGANS battery (hourly rotation) and runs
the two publishers -- `nlp_event_factors` (Part A: event/policy factors from collected text) and
`blog_social_mining` (Part B: Asian retail attention and mood). `run()` is on `daily_cycle`'s
proposer list: it refreshes both, runs the ADMISSION TEST, and donates the pre-declared direct
cells through `proposer_common.donate` -- the door every proposer uses (PIT stamp, lane filter,
pre-registration, blinding, canonical registry, and `tests_run` charged to the lifetime ledger).

THE ADMISSION TEST (subsystem admission rule). For every published index and every instrument it
is declared to touch: Spearman IC of the index on day d against the log return from the first
close AFTER d over 1 and 5 trading days, against a placebo that block-shuffles the index's dates,
with a block-bootstrap interval and Benjamini-Hochberg across the whole grid
(`libs.research.nlp_gain_test`). The verdict is GAIN, NO_GAIN_SHOWN or UNMEASURED -- and every
test in the grid is a trial charged on the donation.

THE DIRECT CELLS ARE PRE-DECLARED, NOT MINED. Two mechanisms, each with its sign fixed here
before any data is seen, run by `family_exogenous_conditioner` on the lake frames:

  policy_tone_drift         the 20-day EWM of a country's signed monetary tone, z-scored; the
                            side is the currency-leg consequence of a tightening drift
  attention_shock_reversal  retail attention z times the sign of the mood change, z-scored; the
                            side FADES the crowd when attention spikes (side_when_high = -1)

A cell is donated only when its series holds MIN_HISTORY_DAYS observations AND its own
(index, instrument) passed the shuffled-date placebo gate above (`gain` in the grid: BH q <= alpha
over every test run, bootstrap interval excluding zero). Before the history exists it is listed as
WAITING_FOR_HISTORY -- a count of days, not a verdict; with the history but no gain it is listed
as FAILED_GAIN and not donated. Single-name share CFDs (the semis names)
are never donated: the two-lane mandate keeps them in the event lane, where the allocation-intel
artifact still carries their crowd context.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

from libs.research import asia_alt_digest  # noqa: E402
from libs.research import event_factors as ef  # noqa: E402
from libs.research import nlp_gain_test as gt  # noqa: E402

SOURCE = "nlp_social_cells"
SERIES_DIR = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "NLP_SOCIAL_CELLS.json"
GIT_BARS = DESK / "universe"
MIN_HISTORY_DAYS = 60
#: The history a cell needs is RECENT history: 60 points scattered over thirty years of speech
#: titles are not a series the conditioner's 250-row z-window can read today.
HISTORY_WINDOW_DAYS = 365
HORIZONS = (1, 5)

#: (country, symbol, side_when_high) for policy_tone_drift. Tightening drift strengthens the home
#: currency (USDJPY down on a hawkish JP drift, up on a hawkish US one) and weighs on the home
#: index. Declared here, before any data, and never re-signed by a result.
POLICY_CELLS: tuple[tuple[str, str, int], ...] = (
    ("JP", "USDJPY", -1), ("JP", "JPN225", -1), ("US", "USDJPY", 1), ("US", "EURUSD", -1),
    ("US", "XAUUSD", -1), ("US", "US500", -1), ("CN", "USDCNH", -1), ("CN", "CHINAH", -1),
    ("KR", "USDKRW", -1), ("EU", "EURUSD", 1), ("GB", "GBPUSD", 1),
)
#: Instruments the attention-shock reversal is donated on (share CFDs excluded by mandate).
ATTENTION_SYMBOLS: tuple[str, ...] = ("JPN225", "USDJPY", "USDKRW", "CHINAH", "HK50", "USDCNH")

#: Tier S orthogonality schema per culture: who trades there, and why its version of the
#: mechanism should fail at different times than the English-language one.
CULTURE: dict[str, dict[str, Any]] = {
    "JP": {"source_culture": "JP/ja", "participant_structure": ["retail_heavy", "tax_driven"],
           "crowding_prior": "low",
           "failure_mode_hypothesis": ("JP retail FX/Nikkei crowds sell into the March tax-year "
                                       "end and chase carry, so their overreaction reverses on "
                                       "a different calendar than US retail's")},
    "KR": {"source_culture": "KR/ko", "participant_structure": ["retail_heavy",
                                                                "settlement_constrained"],
           "crowding_prior": "low",
           "failure_mode_hypothesis": ("KR retail trades KOSPI with leverage under KRX daily "
                                       "limits and the onshore won's closed hours, so reversals "
                                       "come on foreign-selling and limit days")},
    "CN": {"source_culture": "CN/zh", "participant_structure": ["retail_heavy", "policy_driven",
                                                                "settlement_constrained"],
           "crowding_prior": "low",
           "failure_mode_hypothesis": ("A-share retail is T+1 with daily limits and follows "
                                       "policy signals, so a mood extreme cannot unwind "
                                       "same-day and reverses after policy days")},
    "US": {"source_culture": "US/en", "participant_structure": ["policy_driven",
                                                                "institutional"],
           "crowding_prior": "high",
           "failure_mode_hypothesis": ("FOMC tone is the most-read text in the market, so a "
                                       "drift it carries is priced fastest; fails first here")},
    "EU": {"source_culture": "EU/en", "participant_structure": ["policy_driven",
                                                                "institutional"],
           "crowding_prior": "high",
           "failure_mode_hypothesis": ("ECB tone is diluted by 20 national central banks' "
                                       "speakers, so drift reads late and noisy")},
    "GB": {"source_culture": "GB/en", "participant_structure": ["policy_driven",
                                                                "institutional"],
           "crowding_prior": "high",
           "failure_mode_hypothesis": ("BoE tone is split by a nine-member MPC vote, so drift "
                                       "shows before the decision and fails on split votes")},
}
_SYMBOL_CULTURE = {"JPN225": "JP", "USDJPY": "JP", "USDKRW": "KR", "CHINAH": "CN", "HK50": "CN",
                   "USDCNH": "CN"}


# --------------------------------------------------------------------------------------- data
def daily_closes(symbol: str) -> pd.Series | None:
    """Daily last close, weekdays only, from the bar store (box) or the git bars (anywhere)."""
    frame = None
    try:
        from research import proposer_common as pc
        frame = pc.bars(symbol)
    except Exception:
        frame = None
    if frame is None:
        path = GIT_BARS / f"{symbol}_H1.parquet"
        if not path.exists():
            return None
        try:
            frame = pd.read_parquet(path, columns=["close"])
        except (OSError, ValueError, ImportError):
            return None
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
    daily = frame["close"].astype(float).resample("1D").last().dropna()
    weekday = pd.DatetimeIndex(daily.index).dayofweek < 5
    out: pd.Series = daily[weekday]
    return out if len(out) else None


def load_lake(name: str, series_dir: Path = SERIES_DIR) -> pd.DataFrame | None:
    path = series_dir / f"{name}.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None


def _index(frame: pd.DataFrame, col: str) -> pd.Series | None:
    """The column on its DESCRIBED day (`period` / `day`), which `nlp_gain_test.align` then
    trades from the first close AFTER -- the day's value is only knowable at its end."""
    if col not in frame.columns:
        return None
    key = "period" if "period" in frame.columns else "day"
    s = pd.Series(pd.to_numeric(frame[col], errors="coerce").to_numpy(),
                  index=pd.to_datetime(frame[key], errors="coerce")).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index() if len(s) else None


def build_grid(series_dir: Path = SERIES_DIR) -> tuple[dict[str, pd.Series],
                                                        list[tuple[str, str]],
                                                        dict[str, int]]:
    """Every published index and the instruments it is declared to touch."""
    indices: dict[str, pd.Series] = {}
    pairs: list[tuple[str, str]] = []
    history: dict[str, int] = {}
    for country, per in ef.COUNTRY_INSTRUMENTS.items():
        frame = load_lake(f"nlp_events_{country}", series_dir)
        if frame is None:
            continue
        for factor in ef.FACTORS:
            s = _index(frame, f"{factor}_drift")
            if s is None:
                continue
            name = f"nlp:{country}.{factor}_drift"
            indices[name] = s
            history[name] = _recent(s)
            pairs += [(name, sym) for sym in per]
    for sym in sorted({i for per in _topics().values() for i in per}):
        frame = load_lake(f"blog_social_{sym}", series_dir)
        if frame is None:
            continue
        for sig in ("attention_delta_z", "mood_delta", "attention_shock_signed"):
            s = _index(frame, sig)
            if s is None:
                continue
            name = f"blog:{sym}.{sig}"
            indices[name] = s
            history[name] = _recent(s)
            pairs.append((name, sym))
    return indices, pairs, history


def _recent(s: pd.Series) -> int:
    """Observations inside the last HISTORY_WINDOW_DAYS -- the history a cell is ready on."""
    floor = pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(days=HISTORY_WINDOW_DAYS)
    idx = pd.DatetimeIndex(s.index)
    idx = idx.tz_localize(None) if idx.tz is not None else idx
    return int((idx >= floor).sum())


def _topics() -> dict[str, dict[str, int]]:
    from libs.research.social_mood import INSTRUMENT_TOPICS
    return INSTRUMENT_TOPICS


# -------------------------------------------------------------------------------------- cells
def _evidence(grid: dict[str, Any], index: str, sym: str) -> list[dict[str, Any]]:
    return [{k: t.get(k) for k in ("horizon", "n_obs", "state", "ic", "p_placebo", "q_bh",
                                   "ci90", "gain")}
            for t in grid["tests"] if t.get("index") == index and t.get("instrument") == sym]


def _passed_gain(grid: dict[str, Any], index: str, sym: str) -> bool:
    """True only when some horizon of this (index, instrument) passed the placebo gate."""
    return any(t.get("gain") is True for t in grid.get("tests") or []
               if t.get("index") == index and t.get("instrument") == sym)


def declared_cells(history: dict[str, int], grid: dict[str, Any]) -> tuple[list[dict[str, Any]],
                                                                         list[dict[str, Any]]]:
    """(ready cells, not-ready cells). A cell is ready once its series has the history to judge
    AND its own (index, instrument) passed the shuffled-date placebo gain test. A not-ready cell
    carries `not_ready` = WAITING_FOR_HISTORY or FAILED_GAIN."""
    ready: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    for country, sym, side in POLICY_CELLS:
        name = f"nlp:{country}.monetary_tone_drift"
        culture = CULTURE.get(country, {"source_culture": f"{country}/en",
                                        "participant_structure": ["policy_driven"],
                                        "crowding_prior": "high", "failure_mode_hypothesis": ""})
        cell = {
            "cell_name": "policy_tone_drift", "symbol": sym, "index": name,
            "params": {"source": f"nlp_events_{country}", "signal": "monetary_tone_drift",
                       "transform": "level_z", "threshold": 1.0, "side_when_high": side,
                       "ttl_bars": 120, "lag_hours": 24},
            "mechanism": (f"{country} policy communication tone drifts ahead of the rate path; "
                          f"{sym} holders who reprice on decisions rather than on tone are late"),
            "payer": "decision-date repricers (benchmarked FX and index holders)",
            "economic_actor": "scheduled_repricer",
            "constraint": "mandates rebalance on realised policy decisions, not on speeches",
            "information_source": "event",
            **culture,
        }
        _sort(cell, name, sym, history, grid, ready, waiting)
    for sym in ATTENTION_SYMBOLS:
        name = f"blog:{sym}.attention_shock_signed"
        culture = CULTURE[_SYMBOL_CULTURE[sym]]
        cell = {
            "cell_name": "attention_shock_reversal", "symbol": sym, "index": name,
            "params": {"source": f"blog_social_{sym}", "signal": "attention_shock_signed",
                       "transform": "level_z", "threshold": 1.5, "side_when_high": -1,
                       "ttl_bars": 24, "lag_hours": 24},
            "mechanism": (f"a spike in {culture['source_culture']} retail attention with a "
                          f"one-sided mood change marks crowd overreaction in {sym}; liquidity "
                          "providers absorb the crowd's flow and are paid on the reversal"),
            "payer": "attention-driven retail traders chasing the day's move",
            "economic_actor": "overextended_liquidity_taker",
            "constraint": ("retail flow concentrates in hours and on one side; dealers' inventory "
                           "limits force them to widen and fade it"),
            "information_source": "event",
            **culture,
        }
        _sort(cell, name, sym, history, grid, ready, waiting)
    for c in ready + waiting:
        c["evidence"] = _evidence(grid, c["index"], c["symbol"])
        c["history_days"] = history.get(c["index"], 0)
    return ready, waiting


def _sort(cell: dict[str, Any], name: str, sym: str, history: dict[str, int],
          grid: dict[str, Any], ready: list[dict[str, Any]],
          waiting: list[dict[str, Any]]) -> None:
    if history.get(name, 0) < MIN_HISTORY_DAYS:
        cell["not_ready"] = "WAITING_FOR_HISTORY"
        waiting.append(cell)
    elif not _passed_gain(grid, name, sym):
        cell["not_ready"] = "FAILED_GAIN"
        waiting.append(cell)
    else:
        ready.append(cell)


def to_candidates(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from research import proposer_common as pc

    out = []
    meta_keys = ("cell_name", "payer", "economic_actor", "constraint", "information_source",
                 "source_culture", "participant_structure", "failure_mode_hypothesis",
                 "crowding_prior")
    for c in cells:
        cand = pc.candidate(
            SOURCE, c["symbol"], "exogenous_conditioner", dict(c["params"]), c["mechanism"],
            title=f"{c['cell_name']} {c['symbol']} <- {c['params']['source']}."
                  f"{c['params']['signal']}",
            evidence={"gain_test": c["evidence"], "history_days": c["history_days"]})
        cand.update({k: c[k] for k in meta_keys})
        cand["provenance"] = {k: c[k] for k in meta_keys}
        cand["chart"] = "H1"
        cand["falsifier"] = (f"the {c['params']['transform']} of {c['params']['source']}."
                             f"{c['params']['signal']} has no measurable relation to "
                             f"{c['symbol']} out of sample")
        cand["required_data"] = [f"desks/mt5/data/lake/series/{c['params']['source']}.parquet"]
        out.append(cand)
    return out


# ---------------------------------------------------------------------------------------- run
def ingest(*, fetch: bool = True, budget_s: float = 110.0) -> dict[str, Any]:
    """Both publishers, each fenced so one failing never costs the other its pass."""
    out: dict[str, Any] = {}
    try:
        import nlp_event_factors  # type: ignore[import-not-found]
        rep = nlp_event_factors.run()
        out["nlp_events"] = {"n_docs": rep["n_docs"], "panel_rows": rep["panel_rows"],
                             "llm": rep["llm_tier"].get("state")}
    except Exception as exc:
        out["nlp_events"] = {"state": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
    try:
        import blog_social_mining  # type: ignore[import-not-found]
        rep = blog_social_mining.run(fetch=fetch, budget_s=budget_s)
        out["blog_social"] = {"new_posts": rep["fetch"].get("new_posts", 0),
                              "sources_ok": rep["fetch"].get("sources_ok", []),
                              "index_rows": rep["index_rows"], "live_yield": rep["live_yield"]}
    except Exception as exc:
        out["blog_social"] = {"state": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
    return out


def run(budget_s: float = 900.0, *, dry_run: bool = False, refresh: bool = True,
        series_dir: Path = SERIES_DIR, out: Path = REPORT, n_placebo: int = 200,
        n_boot: int = 300, digest_path: Path = asia_alt_digest.DIGEST) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "budget_s": budget_s}
    if refresh and not dry_run:
        rep["ingest"] = ingest(fetch=False)
    indices, pairs, history = build_grid(series_dir)
    closes = {sym: c for sym in sorted({p[1] for p in pairs})
              if (c := daily_closes(sym)) is not None}
    grid = gt.gain_grid(indices, closes, pairs, horizons=HORIZONS, n_placebo=n_placebo,
                        n_boot=n_boot, seed=20260930)
    ready, waiting = declared_cells(history, grid)
    cands = to_candidates(ready) if ready else []
    tests_run = int(grid["n_trials"]) + len(cands)
    rep.update({
        "admission": {k: grid[k] for k in ("verdict", "n_trials", "n_unmeasured", "alpha",
                                           "n_placebo", "rule")},
        "gain_tests": [t for t in grid["tests"] if t.get("state") == "MEASURED"],
        "unmeasured_tests": sum(1 for t in grid["tests"] if t.get("state") != "MEASURED"),
        "series_history_days": history,
        "instruments_with_bars": sorted(closes),
        "tests_run": tests_run,
        "cells_proposed": len(cands),
        "cells_waiting_for_history": [{"cell": c["cell_name"], "symbol": c["symbol"],
                                       "history_days": c["history_days"],
                                       "needs": MIN_HISTORY_DAYS} for c in waiting
                                      if c.get("not_ready") == "WAITING_FOR_HISTORY"],
        "cells_failed_gain": [{"cell": c["cell_name"], "symbol": c["symbol"],
                               "history_days": c["history_days"],
                               "why": "no horizon passed the shuffled-date placebo gate"}
                              for c in waiting if c.get("not_ready") == "FAILED_GAIN"],
        "dry_run": dry_run,
    })
    if cands and not dry_run:
        from research import proposer_common as pc
        rep["donated"] = str(pc.donate(SOURCE, cands, tests_run))
        rep["donation"] = pc.donation_counts()
    if not dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(rep, indent=1, default=_safe), "utf-8")
        os.replace(tmp, out)
        asia_alt_digest.publish(SOURCE, digest_section(rep, grid), digest_path)
    return rep


def digest_section(rep: dict[str, Any], grid: dict[str, Any]) -> dict[str, Any]:
    """This organ's section of the committed digest: the admission verdict and every test's."""
    def key(t: dict[str, Any]) -> str:
        return f"{t.get('index')}|{t.get('instrument')}|h{t.get('horizon')}"

    tests = grid.get("tests") or []
    gain = {key(t): ("GAIN" if t.get("gain") else "NO_GAIN")
            if t.get("state") == "MEASURED" else gt.UNMEASURED for t in tests}
    return asia_alt_digest.section(
        at=str(rep["generated_at"]), status=str(rep["admission"]["verdict"]),
        rows=int(rep["admission"]["n_trials"]),
        measured=[key(t) for t in tests if t.get("state") == "MEASURED"],
        unmeasured=[key(t) for t in tests if t.get("state") != "MEASURED"], gain=gain,
        cells_proposed=int(rep["cells_proposed"]),
        cells_waiting_for_history=len(rep["cells_waiting_for_history"]),
        cells_failed_gain=len(rep["cells_failed_gain"]), tests_run=int(rep["tests_run"]))


def _safe(x: Any) -> Any:
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return str(x)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ingest", action="store_true", help="fetch + publish only (battery)")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--budget-s", type=float, default=110.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.ingest:
        print(json.dumps(ingest(fetch=not a.no_fetch, budget_s=a.budget_s), default=str))
        return 0
    rep = run(dry_run=a.dry_run)
    print(f"nlp_social_cells: admission {rep['admission']['verdict']} over "
          f"{rep['admission']['n_trials']} trials; {rep['cells_proposed']} cell(s) proposed, "
          f"{len(rep['cells_waiting_for_history'])} waiting for history, "
          f"{len(rep['cells_failed_gain'])} failed the placebo gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
