"""REGIME ROUTER -- which reading of a sleeve is live RIGHT NOW, and P(alpha > 0 | state).

Ledger item D8 (TRA / DoubleAdapt) and Q16 (AlphaCrafter state-conditioned alpha), principal
2026-09-16. Every other organ prices a sleeve with ONE number -- an expectancy, a posterior mu,
a Sharpe -- and that number is an average over states the sleeve is not in. A breakout sleeve
that makes +0.4R when the tape moves and -0.2R when it is dead publishes +0.1R, and the
allocator sizes a sleeve that does not exist: the average of two mechanisms, live in neither.
Microsoft's TRA answers that by routing each SAMPLE to the predictor that explains it;
DoubleAdapt answers the drift half by re-fitting the representation when the incoming
distribution moves -- the desk's small, auditable version of both, per LIVE sleeve and per
running forward clock:

    unconditional   the NIG posterior of `research.posterior_alpha` -- imported, not re-derived
    by_state        the SAME posterior per state bucket, with n0 pseudo-trades AT THE
                    UNCONDITIONAL MEAN, so a 2-trade bucket says what the sleeve says and a
                    40-trade bucket is allowed to disagree with it
    router          `libs.models.router.SoftMoE`: K = 2..3 mean-R experts under a gate on the
                    state features, scored WALK-FORWARD against the unrouted mean
    p_alpha_now     P(alpha > 0 | the state the desk is in this minute)

THE STATE, six axes, each measured from the desk's own bars and clock -- none is a claim.
`vol`: the symbol's trailing 24-bar realised vol, cut into terciles on the distribution BEFORE
the sleeve's first trade, a causal cut so no trade helps define its own bucket (the z-score the
gate sees is standardised on that same pre-window). `session`: `mt5desk.family_call.SESSIONS`
server hours. `usd`: the basket's sign against its own 120-bar mean (USDX, else a signed
major). `dow`: day of week, as sin/cos so Friday sits next to Monday. `risk`: the cross-asset
sign, US500's 20-day trend, where the box carries US500 bars. `hmm`: the LATENT one, below.

WHY THIS ORGAN WAS DARK, AND WHAT THE HMM AXIS FIXES (2026-09-24). Measured on the box: 258
sleeves, 208 with no trade at all, 50 published, and ZERO SCORED -- 34 under the 24-trade fold
minimum and 16 with no state feature that varied over their trades. The largest sleeve in the
whole book had 23 trades, so the walk-forward path could not score ONE, and "no router beats its
unrouted model" was a negative result for a test that had never run. The cause was architectural:
the organ was fitting a regime model per sleeve, out of that sleeve's own trades, and most
sleeves will never trade enough for that. A hidden Markov model describes the MARKET, not the
sleeve. `hmm` is fitted by Baum-Welch on the symbol's OWN H1 BARS (`libs.regime.bar_states`),
labels every hour causally, and so needs no sleeve to have traded even once. Its state count is
chosen by held-out predictive log-density, not by taste. Alongside it, `pooled_router` scores the
sleeves the fold minimum refuses, by PREQUENTIAL partial pooling (`libs.regime.pooling`): a thin
sleeve borrows its family's state effect instead of being refused an answer, because small n is a
WIDE answer, not an absent one. The bar did not move -- the same proper score and the same tax
judge both paths, and a sleeve with nothing to predict from is still published UNMEASURED.

ACTIVATION IS MEASURED AND TWO-SIDED, which is the whole point (GROWTH_GOVERNANCE 1 and 2). The
router is ACTIVE for a sleeve only where its out-of-sample log-score beats the unrouted mean
AFTER paying `libs.models.zoo.TAX["soft_moe"]` -- the zoo's own tax, imported so the two cannot
drift. Where the state carries no information the router says so and the sleeve keeps its
unconditional posterior; where it does, the router may raise a sleeve's expected edge as readily
as lower it. NOTHING HERE SIZES, CAPS, VETOES OR SHRINKS: it writes a report the allocator is
entitled to read, the heat floor is untouched, and `pf_allocator` is not edited.

THE DOUBLEADAPT HALF. A gate fitted on the whole history represents a state distribution that
may have moved. Each sleeve's recent window is tested against its past on the feature means
(diagonal Hotelling, permutation null -- so the statistic's small-sample bias is inside the null
that judges it), and where the distribution HAS moved the gate is re-fitted on the recent window
and the row says `representation_adapted: true` with the statistic that fired. That is
adaptation at drift time, not on a calendar. What it adapts is the SYMBOLIC state vocabulary;
the learned lane that competes with it lives in `representation_discovery.py` and reaches the
book the way everything else does -- through a hypothesis and the gauntlet's ten gates.

WIRED: `hourly_cycle.py` runs this as the heavy leg `regime_router` in the `forward` department.
(This docstring claimed "NOT WIRED TO A CLOCK YET" until 2026-09-24, long after the leg landed --
a status line that rots is worse than none, because III.16 is judged on it.)
`python desks/mt5/research/regime_router.py` writes the artifact; `--dry-run` prints the table and
writes nothing. numpy only (pandas optionally, to read parquet).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The posterior machinery AND the evidence readers come from `posterior_alpha`, imported rather
# than re-derived: two organs that price the same fills must not drift on what a fill is.
from libs.models.router import SoftMoE  # noqa: E402
from libs.models.zoo import TAX  # noqa: E402
from libs.regime import pooling  # noqa: E402
from libs.regime.bar_states import (  # noqa: E402
    BarStates,
    choose_k,
    fit_states,
    run_length_path,
)
from libs.regime.features import regime_features  # noqa: E402
from libs.regime.transitions import forecast as transition_forecast  # noqa: E402
from research.posterior_alpha import (  # noqa: E402
    DEFAULT_SIGMA,
    PRIOR_N0,
    UNMEASURED,
    _family_of_key,
    _family_of_name,
    _num,
    _read_json,
    _read_jsonl,
    nig_update,
    summarise,
)

try:                                                        # the one call that owns the axis
    from mt5desk.family_call import SESSIONS as _SESSION_WINDOWS
except Exception:                                           # pragma: no cover - box-only import
    _SESSION_WINDOWS = {"asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None}

SLEEVES = BASE / "data" / "sleeves.json"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_STATE = SHADOW_DIR / "shadow_state.json"
UNI = BASE / "data" / "universe"
OUT = BASE / "reports" / "REGIME_ROUTER.json"
#: THE STATE'S OWN HISTORY, and it did not exist until 2026-09-24. This organ published the
#: CURRENT state every pass and kept nothing, so the desk that trades regime switches could not
#: say when the regime last switched -- the one question a switch-trader asks. The sidecar is
#: append-only and holds a row per OBSERVED CHANGE, never one per pass: a file that grows by
#: 24 identical rows a day is a log, and the transition time is what a reader actually needs.
HISTORY = BASE / "data" / "regime_state_history.jsonl"
#: Rows kept. At one row per change and a handful of changes a day, this is months of history
#: and a file small enough to read whole on every pass.
HISTORY_KEEP = 4000

#: Bars per symbol per timeframe. 6,000 H1 is ~8 months: the whole live/forward trade span with
#: months of pre-trade tape left over for the causal tercile cut.
BARS = 6000
VOL_LOOKBACK = 24           # trailing bars of realised vol: one session's worth of H1
USD_LOOKBACK = 120          # ~5 trading days of H1 for the basket's own mean
RISK_DAYS = 20              # the cross-asset trend horizon, in days
PRE_MIN = 200               # finite pre-trade vol readings before a tercile cut is honest
STALE_DAYS = {"H1": 14, "H4": 21, "D1": 45}
USD_PROXIES: tuple[tuple[str, int], ...] = (("USDX", 1), ("EURUSD", -1), ("USDJPY", 1))
RISK_SOURCES: tuple[tuple[str, str], ...] = (("US500", "D1"), ("US500", "H4"), ("US500", "H1"))
BARS_PER_DAY = {"D1": 1, "H4": 6, "H1": 24}
AXES = ("vol", "session", "usd", "dow", "risk", "hmm")
PRIMARY_AXIS = "vol"        # the axis `current_bucket` names: per-symbol, and monotone
#: THE HMM AXIS, added 2026-09-24. The five axes above are OBSERVABLE labels -- a clock reading,
#: a sign, a tercile. `hmm` is the first LATENT one: the argmax of a forward filter over a
#: Baum-Welch state model fitted on the symbol's own H1 bars (`libs.regime.bar_states`). It is
#: the axis that does not need the sleeve to have traded, because it is a property of the tape.
#: Its parameters are fitted strictly before the first trade in the book, so every label it
#: assigns over the trade window is out of sample, and it is read from `filter_posterior` and
#: never from Viterbi (L0307).
HMM_AXIS = "hmm"
#: Sleeves the walk-forward refuses (n < MIN_ROUTER_TRADES) are scored by the PREQUENTIAL pooled
#: path instead. This is the floor for that path: below it there is not enough to predict from
#: even once, and the sleeve is published UNMEASURED with its n.
MIN_POOLED_TRADES = 2
#: The HMM's EM seed. Declared so a state path is reproducible pass to pass: a regime label that
#: changes because EM restarted differently is not a regime change.
HMM_SEED = 20260924
#: H1 bars the HMM is FITTED on. `GaussianHMM._forward_backward` is a Python loop over bars, so
#: this is the leg's cost knob and it is stated here rather than buried. 1,500 H1 bars is ~62
#: trading days, which identifies a handful of volatility states many times over. MEASURED on the
#: box 2026-09-24: 25 symbols at k=4 cost 730s wall on a machine already at 100% CPU.
HMM_MAX_BARS = 1500
#: HOW MANY STATES: asked ONCE PER PASS, on the most-traded symbols, and then used for the whole
#: book. The state count is a book-level question -- asking it per symbol costs len(K_GRID) fits
#: for every symbol instead of one, which is a 4x bill on an hourly leg for the same answer, and
#: it would also give two symbols different label vocabularies that cannot be pooled.
HMM_K_GRID = (2, 3, 4)
HMM_K_SAMPLE = 4
FEATURES = ("vol_z", "sess_asia", "sess_london", "sess_ny", "usd_trend", "dow_sin", "dow_cos",
            "risk_sign")
#: Pseudo-trades a bucket is shrunk toward the UNCONDITIONAL posterior by -- the same 30 the
#: desk's no-edge prior uses, so a bucket must bring 30 trades before it half-disagrees.
BUCKET_N0 = PRIOR_N0
MIN_ROUTER_TRADES = 24      # below this the walk-forward folds are not scorable
K_GRID = (2, 3)
RESTARTS = 3                # EM starts per fit; the highest likelihood is the one published
ROUTER_FOLDS = 4
MIN_T_GAIN = 1.0          # fold-level gain / its standard error: chance does not route
MIN_TEST_ROWS = 4
#: An expert may not declare itself 5x more certain than the pooled model on the training fold:
#: a two-row expert with a tiny residual would otherwise win every log-score it entered.
SD_FLOOR_FRAC = 0.2
DRIFT_WINDOW = 20           # trades in the "recent" window of the two-sample test
DRIFT_MIN = 6               # rows each side before the statistic means anything
DRIFT_PERMS = 200
DRIFT_P = 0.05
ADAPT_MIN = 10              # rows the recent window needs before the gate is re-fitted on it
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

RULE = ("alpha value is state dependent; the router is active only where it beats the unrouted "
        "model out of sample; never below the floor")

_BARS: dict[tuple[str, str], tuple[np.ndarray, np.ndarray] | None] = {}
_VOL: dict[str, tuple[np.ndarray, np.ndarray] | None] = {}


def reset_caches() -> None:
    """Drop the bar/vol caches: one pass reads the tape once, and a test reads another tape."""
    _BARS.clear()
    _VOL.clear()


def _ts(value: Any) -> datetime | None:
    try:
        out = datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def _ns(when: datetime) -> int:
    return int(when.timestamp() * 1_000_000_000)


# ------------------------------------------------------------------------------------- the tape
def bars(symbol: str, timeframe: str = "H1") -> tuple[np.ndarray, np.ndarray] | None:
    """(bar times in ns, close) for a symbol, oldest first -- or None where the box has no tape."""
    key = (str(symbol), str(timeframe))
    if key not in _BARS:
        _BARS[key] = _load_bars(*key)
    return _BARS[key]


def _load_bars(symbol: str, timeframe: str) -> tuple[np.ndarray, np.ndarray] | None:
    try:
        import pandas as pd
    except ImportError:                                  # pragma: no cover - pandas is installed
        return None
    path = UNI / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=["close"]).tail(BARS)
    except (OSError, ValueError, KeyError):
        return None
    index = frame.index
    with contextlib.suppress(TypeError, AttributeError):     # a tz-naive index is already UTC
        index = index.tz_convert("UTC").tz_localize(None)
    try:
        times = np.asarray(index.values, dtype="datetime64[ns]").astype("int64")
    except (TypeError, ValueError):
        return None
    close = np.asarray(frame["close"].to_numpy(), dtype=float)
    keep = np.isfinite(close)
    return (times[keep], close[keep]) if keep.sum() >= VOL_LOOKBACK + 2 else None


def _roll(x: np.ndarray, w: int, kind: str) -> np.ndarray:
    """Trailing mean or std over w points, NaN until the window fills. Cumsum, so it is O(n)."""
    out = np.full(x.size, np.nan)
    if x.size < w or w < 2:
        return out
    c1 = np.concatenate(([0.0], np.cumsum(x)))
    mean = (c1[w:] - c1[:-w]) / w
    if kind == "mean":
        out[w - 1:] = mean
        return out
    c2 = np.concatenate(([0.0], np.cumsum(x * x)))
    out[w - 1:] = np.sqrt(np.maximum((c2[w:] - c2[:-w]) / w - mean ** 2, 0.0))
    return out


def _at(series: tuple[np.ndarray, np.ndarray] | None, ns: int, timeframe: str) -> float | None:
    """The series' value at the last bar at or before `ns`, refusing a stale read."""
    if series is None:
        return None
    times, values = series
    i = int(np.searchsorted(times, ns, side="right")) - 1
    if i < 0 or ns - int(times[i]) > STALE_DAYS[timeframe] * 86_400_000_000_000:
        return None
    return float(values[i]) if math.isfinite(float(values[i])) else None


def vol_series(symbol: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Trailing realised vol of the symbol's H1 log returns, aligned to the bar times."""
    if symbol not in _VOL:
        tape = bars(symbol, "H1")
        if tape is None:
            _VOL[symbol] = None
        else:
            times, close = tape
            ret = np.zeros(close.size)
            ret[1:] = np.diff(np.log(np.maximum(close, 1e-12)))
            _VOL[symbol] = (times, _roll(ret, VOL_LOOKBACK, "std"))
    return _VOL[symbol]


def _trend(symbol: str, timeframe: str, window: int) -> tuple[np.ndarray, np.ndarray] | None:
    """Sign of close against its own trailing mean: a direction, never a size."""
    tape = bars(symbol, timeframe)
    if tape is None:
        return None
    return tape[0], np.sign(tape[1] - _roll(tape[1], window, "mean"))


# ------------------------------------------------------------------------------ the state space
class States:
    """The five state axes, measured once per pass and readable at any timestamp.

    An axis the box cannot measure returns UNMEASURED at every timestamp and is DROPPED from the
    gate with a note. It is never quietly imputed to zero, which would be a state nobody traded.
    """

    def __init__(self, notes: list[str], hmm_train_end_ns: int | None = None) -> None:
        self._cuts: dict[tuple[str, int], tuple[float, float, float, float] | None] = {}
        self._usd: tuple[np.ndarray, np.ndarray] | None = None
        self._risk: tuple[np.ndarray, np.ndarray] | None = None
        #: Per-symbol latent state model, fitted lazily and cached for the pass. `None` records a
        #: symbol whose tape cannot support a fit, so the axis reads UNMEASURED there rather than
        #: being retried on every trade.
        self._hmm: dict[str, BarStates | None] = {}
        self._hmm_notes = notes
        #: Every HMM parameter is fitted on bars strictly BEFORE this instant, so the labels over
        #: the trade window are out of sample. `None` means "fit on everything", which is honest
        #: only for describing history and is never used by the scoring path.
        self.hmm_train_end_ns = hmm_train_end_ns
        #: The book's state count, fixed once per pass by `choose_state_count`.
        #: `None` means it has not been asked, and each symbol then picks its own.
        self.hmm_k: int | None = None
        self.usd_symbol, self.risk_symbol, self._risk_tf = UNMEASURED, UNMEASURED, "D1"
        for symbol, sign in USD_PROXIES:
            found = _trend(symbol, "H1", USD_LOOKBACK)
            if found is not None:
                self._usd, self.usd_symbol = (found[0], found[1] * sign), f"{symbol}{sign:+d}"
                break
        for symbol, timeframe in RISK_SOURCES:
            found = _trend(symbol, timeframe, RISK_DAYS * BARS_PER_DAY[timeframe])
            if found is not None:
                self._risk, self.risk_symbol, self._risk_tf = found, symbol, timeframe
                break
        for axis, series in (("usd", self._usd), ("risk", self._risk)):
            if series is None:
                notes.append(f"{axis} axis UNMEASURED: the box carries no bars for its proxy")

    def cuts(self, symbol: str, before_ns: int) -> tuple[float, float, float, float] | None:
        """(tercile low, tercile high, mean, sd) of realised vol STRICTLY BEFORE `before_ns`.

        Causal by construction: the cut that labels a trade is fitted on tape that closed before
        the sleeve's first trade, so no trade helps decide which bucket it lands in.
        """
        key = (symbol, before_ns)
        if key not in self._cuts:
            self._cuts[key] = None
            series = vol_series(symbol)
            if series is not None:
                pre = series[1][series[0] < before_ns]
                pre = pre[np.isfinite(pre)]
                if pre.size >= PRE_MIN and float(pre.std()) > 0:
                    lo, hi = (float(v) for v in np.quantile(pre, [1 / 3, 2 / 3]))
                    self._cuts[key] = (lo, hi, float(pre.mean()), float(pre.std()))
        return self._cuts[key]

    def _observations(self, symbol: str) -> np.ndarray | None:
        """The canonical 3-column regime observation matrix for a symbol's H1 tape.

        `libs.regime.features` owns those three columns; a second implementation of them is the
        drift this desk keeps paying for, so it is imported rather than re-derived.
        """
        tape = bars(symbol, "H1")
        if tape is None:
            return None
        try:
            import pandas as pd

            feats, _ = regime_features(pd.Series(tape[1].astype("float64")))
        except (ValueError, ImportError) as exc:
            self._hmm_notes.append(f"hmm axis UNMEASURED for {symbol}: "
                                   f"{type(exc).__name__}: {exc}")
            return None
        return np.asarray(feats, dtype="float64")

    def choose_state_count(self, symbols: list[str]) -> dict[str, Any]:
        """Ask the EVIDENCE how many states, ONCE, on a sample -- then use it for the book.

        The score is the held-out one-step-ahead predictive log-density of the chain on bars the
        fit never saw; a k that merely fits better in sample cannot win it. Fitting the whole grid
        per symbol would cost four times as much for the same book-level answer AND would hand two
        symbols different label vocabularies, which cannot then be pooled across sleeves.
        """
        agg: dict[int, list[float]] = defaultdict(list)
        for symbol in symbols[:HMM_K_SAMPLE]:
            x = self._observations(symbol)
            if x is None:
                continue
            x = x[np.isfinite(x).all(axis=1)]
            tape = bars(symbol, "H1")
            if tape is None:
                continue
            cut = (x.shape[0] if self.hmm_train_end_ns is None
                   else int(np.searchsorted(tape[0][-x.shape[0]:], self.hmm_train_end_ns)))
            xtr = x[max(0, cut - HMM_MAX_BARS):cut]
            if xtr.shape[0] < 400:
                continue
            try:
                _k, scores = choose_k(xtr, grid=HMM_K_GRID, seed=HMM_SEED)
            except (ValueError, np.linalg.LinAlgError):
                continue
            for kk, vv in scores.items():
                agg[kk].append(vv)
        if not agg:
            self.hmm_k = None
            return {"status": UNMEASURED, "sample": symbols[:HMM_K_SAMPLE],
                    "why": "no sampled symbol carried enough pre-trade tape to score a state count"}
        means = {k: float(np.mean(v)) for k, v in agg.items() if v}
        self.hmm_k = int(max(means, key=lambda k: means[k]))
        return {"status": "MEASURED", "k": self.hmm_k,
                "scores": {str(k): round(v, 5) for k, v in sorted(means.items())},
                "sample": symbols[:HMM_K_SAMPLE], "grid": list(HMM_K_GRID),
                "score": "held-out one-step-ahead predictive log-density on bars, nats/bar",
                "why": "the state count is a book-level question, asked once on the sample above"}

    def hmm(self, symbol: str) -> BarStates | None:
        """The symbol's latent state model, fitted once per pass on its H1 tape.

        UNMEASURED is a real answer here: a symbol whose tape is too short returns None, the
        axis reads UNMEASURED for every one of its trades, and `_gate_matrix` drops it. Nothing
        is imputed -- an imputed regime is a state nobody was ever in.
        """
        if symbol not in self._hmm:
            self._hmm[symbol] = None
            tape = bars(symbol, "H1")
            x = self._observations(symbol) if tape is not None else None
            if tape is not None and x is not None:
                try:
                    self._hmm[symbol] = fit_states(
                        tape[0], x, symbol=symbol, timeframe="H1",
                        train_end_ns=self.hmm_train_end_ns, k=self.hmm_k, seed=HMM_SEED,
                        grid=HMM_K_GRID, max_train_bars=HMM_MAX_BARS)
                except (ValueError, np.linalg.LinAlgError) as exc:
                    self._hmm_notes.append(f"hmm axis UNMEASURED for {symbol}: "
                                           f"{type(exc).__name__}: {exc}")
        return self._hmm[symbol]

    @staticmethod
    def session(when: datetime) -> str:
        hits = [name for name, win in _SESSION_WINDOWS.items()
                if win is not None and win[0] <= when.hour < win[1]]
        return "overlap" if len(hits) > 1 else (hits[0] if hits else "off")

    @staticmethod
    def _sign(value: float | None, names: tuple[str, str, str]) -> tuple[str, float | None]:
        if value is None:
            return UNMEASURED, None
        return (names[0] if value > 0 else names[1] if value < 0 else names[2]), value

    def read(self, symbol: str, when: datetime, cuts: tuple[float, float, float, float] | None
             ) -> tuple[dict[str, str], np.ndarray]:
        """(bucket label per axis, the raw gate feature row) for one symbol at one instant."""
        ns, dow = _ns(when), when.weekday()
        raw = _at(vol_series(symbol), ns, "H1")
        vol_label, vol_z = UNMEASURED, None
        if raw is not None and cuts is not None:
            lo, hi, mean, sd = cuts
            vol_label = "low" if raw < lo else ("high" if raw > hi else "mid")
            vol_z = (raw - mean) / sd if sd > 0 else 0.0
        session = self.session(when)
        usd_label, usd = self._sign(_at(self._usd, ns, "H1"), ("up", "down", "flat"))
        risk_label, risk = self._sign(_at(self._risk, ns, self._risk_tf), ("on", "off", "flat"))
        bs = self.hmm(symbol) if symbol else None
        hmm_label = (bs.label_at(ns) or UNMEASURED) if bs is not None else UNMEASURED
        labels = {"vol": vol_label, "session": session, "usd": usd_label, "dow": DAYS[dow],
                  "risk": risk_label, HMM_AXIS: hmm_label}
        row = np.array([vol_z if vol_z is not None else np.nan,
                        float(session == "asia"), float(session in ("london", "overlap")),
                        float(session in ("ny", "overlap")),
                        usd if usd is not None else np.nan,
                        math.sin(2 * math.pi * dow / 7), math.cos(2 * math.pi * dow / 7),
                        risk if risk is not None else np.nan], dtype=float)
        return labels, row


# -------------------------------------------------------------------------------- the evidence
@dataclass
class Sleeve:
    """One sleeve's trades with their timestamps, and where the evidence came from."""

    name: str
    lane: str
    symbol: str
    status: str = ""
    basis: str = "none"
    times: list[datetime] = field(default_factory=list)
    r: list[float] = field(default_factory=list)

    def add(self, when: datetime, value: float) -> None:
        self.times.append(when)
        self.r.append(value)


def collect(notes: list[str], counts: dict[str, Any]) -> list[Sleeve]:
    """LIVE/STANDBY registry rows against the live ledger, plus every running forward clock.

    The evidence rules are `posterior_alpha`'s, unchanged: an `r_multiple: 0.0` on a fill that
    PAID is an unreconstructed R and is dropped rather than read as an observation of no edge,
    and a shadow ledger contributes `forward` rows only -- historical rows predate the
    pre-registration and the desk excludes them from every threshold.
    """
    out: dict[str, Sleeve] = {}
    raw = _read_json(SLEEVES)
    rows = raw.get("sleeves") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        notes.append(f"live sleeve registry unreadable or absent: {SLEEVES}")
        rows = []
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            status = str(row.get("status") or "")
            out[str(row["name"])] = Sleeve(str(row["name"]),
                                           "live" if status == "LIVE" else "registry",
                                           str(row.get("symbol") or ""), status=status)
    ledger = _read_jsonl(LIVE_LEDGER)
    if not ledger:
        notes.append(f"live fills unreadable or absent: {LIVE_LEDGER}")
    dropped = 0
    for row in ledger:
        name = str(row.get("sleeve") or "").strip()
        value, when = _num(row.get("r_multiple")), _ts(row.get("time"))
        if not name or name.startswith("["):
            continue                                        # a broker comment, not a sleeve
        if (row.get("r_unreconstructible") or value is None or when is None
                or (value == 0.0 and (_num(row.get("pl_quote")) or 0.0) != 0.0)):
            dropped += 1
            continue
        found = out.setdefault(name, Sleeve(name, "live", str(row.get("symbol") or ""),
                                            status="LEDGER_ONLY"))
        found.symbol = found.symbol or str(row.get("symbol") or "")
        found.basis = "live_ledger"
        found.add(when, value)
    counts["live_rows_dropped"] = dropped

    state = _read_json(SHADOW_STATE)
    if not isinstance(state, dict):
        notes.append(f"forward clocks unreadable or absent: {SHADOW_STATE}")
        state = {}
    for key, row in state.items():
        if not isinstance(row, dict) or str(row.get("status") or "") not in (
                "ACTIVE", "PROMOTION CANDIDATE"):
            continue
        sleeve = Sleeve(str(key), "forward", str(key).split(".")[0],
                        status=str(row.get("status") or ""))
        trades = _read_json(SHADOW_DIR / f"ledger_{str(key).replace('.', '_')}.json", [])
        for trade in trades if isinstance(trades, list) else []:
            if not isinstance(trade, dict) or str(trade.get("phase") or "") != "forward":
                continue
            value = _num(trade.get("r_multiple"))
            when = _ts(trade.get("exit_time") or trade.get("entry_time"))
            if value is not None and when is not None:
                sleeve.add(when, value)
                sleeve.basis = "shadow_ledger_forward"
        out[str(key)] = sleeve
    for sleeve in out.values():          # a posterior is order-free; the drift test is not
        pairs = sorted(zip(sleeve.times, sleeve.r, strict=True), key=lambda row: row[0])
        sleeve.times = [t for t, _ in pairs]
        sleeve.r = [v for _, v in pairs]
    return list(out.values())


def _post(values: np.ndarray, *, n0: float, mu0: float, sigma0: float) -> dict[str, Any]:
    """{mu, p_positive, n}: the desk's NIG posterior, shrunk toward `mu0` by n0 pseudo-trades."""
    n = int(values.size)
    mean = float(values.mean()) if n else float(mu0)
    sumsq = float(((values - mean) ** 2).sum()) if n else 0.0
    row = summarise(nig_update(n, mean, sumsq, n0=n0, mu0=mu0, sigma0=sigma0))
    return {"mu": row["mu_mean"], "p_positive": row["p_positive"], "n": n}


# ----------------------------------------------------------------------------------- the router
def _logscore(y: np.ndarray, mu: np.ndarray, sd: float) -> float:
    """Mean Gaussian predictive log-density, nats per trade -- a PROPER score for a mean-R
    predictor, so a model that fits its training fold tighter than it deserves pays for the
    confidence out of sample instead of being rewarded for it."""
    var = max(sd, 1e-9) ** 2
    return float(np.mean(-0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)))


def _fit(y: np.ndarray, g: np.ndarray, k: int) -> SoftMoE:
    """A SoftMoE whose experts are INTERCEPT-ONLY: each is a mean-R predictor, the gate carries
    every bit of the state dependence, and the model is `sum_k p(k | state) * mu_k`.

    FITTED FROM SEVERAL STARTS, and that is not tidiness. EM lands where its k-means start puts
    it, and with seven gate features the start can cluster on the four that carry nothing: one
    seed found the vol split on every fold and missed it on the full sample, which would have
    published an expert the out-of-sample score never rewarded. The highest likelihood wins.
    """
    best: SoftMoE | None = None
    for seed in range(RESTARTS):
        moe = SoftMoE(n_experts=k, lam=1.0, tau=1.0, seed=seed).fit(np.zeros((y.size, 1)), y, g)
        if best is None or (math.isfinite(moe.log_likelihood)
                            and not (moe.log_likelihood <= best.log_likelihood)):
            best = moe
    assert best is not None
    return best


def _walk_forward(y: np.ndarray, g: np.ndarray, k: int) -> dict[str, Any]:
    """Expanding-window folds in `libs.models.zoo` geometry: the mean OOS log score, against a
    baseline, less the declared tax. The zoo's own `walk_forward` wants 300 rows and scores a
    binary sign; a sleeve brings tens of trades and a real-valued R, so only the minimum test
    slice moves -- to something a live sleeve can actually produce."""
    n = y.size
    edges = np.linspace(n // 3, n, ROUTER_FOLDS + 1).astype(int)
    routed: list[float] = []
    unrouted: list[float] = []
    for i in range(ROUTER_FOLDS):
        a, b = int(edges[i]), int(edges[i + 1])
        if b - a < MIN_TEST_ROWS or a < 2 * k:
            continue
        ytr, yte = y[:a], y[a:b]
        sd_un = max(float(ytr.std(ddof=1)), 1e-6)
        try:
            moe = _fit(ytr, g[:a], k)
            fit_tr = moe.predict(np.zeros((a, 1)), g[:a])
            fit_te = moe.predict(np.zeros((b - a, 1)), g[a:b])
        except (ValueError, np.linalg.LinAlgError) as exc:
            return {"k": k, "verdict": "FAILED", "why": f"{type(exc).__name__}: {exc}"}
        sd_rt = max(float((ytr - fit_tr).std(ddof=1)), SD_FLOOR_FRAC * sd_un, 1e-6)
        routed.append(_logscore(yte, fit_te, sd_rt))
        unrouted.append(_logscore(yte, np.full(yte.size, float(ytr.mean())), sd_un))
    if not routed:
        return {"k": k, "verdict": UNMEASURED, "why": f"no scorable fold at n={n}"}
    tax = float(TAX["soft_moe"])
    gain = float(np.mean(routed) - np.mean(unrouted))
    diff = np.asarray(routed) - np.asarray(unrouted)
    # A router that wins by chance on two folds of noise is not a router: the fold-level gain
    # must clear its own standard error (two-sided honesty, tested on a planted flat sleeve).
    se = float(diff.std(ddof=1) / np.sqrt(diff.size)) if diff.size > 1 else float("inf")
    t_gain = float(gain / se) if se > 0 else 0.0
    earns = gain - tax > 0 and t_gain >= MIN_T_GAIN
    return {"k": k, "folds": len(routed), "oos_logscore_routed": round(float(np.mean(routed)), 6),
            "oos_logscore_unrouted": round(float(np.mean(unrouted)), 6), "tax": tax,
            "net": round(gain - tax, 6), "t_gain": round(t_gain, 3),
            "verdict": "EARNS_ITS_PLACE" if earns else "TAXED_OUT"}


# -------------------------------------------------------------------------------- the drift test
def _t2(a: np.ndarray, b: np.ndarray) -> float:
    """Diagonal Hotelling: the summed squared t of the per-feature mean difference.

    THE ZERO-WITHIN-VARIANCE CASE IS THE STRONGEST SHIFT THERE IS, not a missing one. A session
    dummy that is 1 on every past trade and 0 on every recent one has NO within-group variance,
    and a naive pooled denominator would divide by zero and drop the one feature that moved --
    so the scale falls back to the feature's variance over both windows, and only a feature
    that is constant across ALL of them is declared immovable.
    """
    n1, n2 = a.shape[0], b.shape[0]
    pooled = ((n1 - 1) * a.var(axis=0, ddof=1) + (n2 - 1) * b.var(axis=0, ddof=1)) / (n1 + n2 - 2)
    both = np.concatenate([a, b]).var(axis=0, ddof=1)
    pooled = np.where(pooled > 0, pooled, np.where(both > 0, both, np.inf))
    diff = a.mean(axis=0) - b.mean(axis=0)
    return float((diff * diff / (pooled * (1.0 / n1 + 1.0 / n2))).sum())


def drift(g: np.ndarray, window: int = DRIFT_WINDOW) -> dict[str, Any]:
    """Has the sleeve's state distribution moved? Permutation null, so the statistic's own
    small-sample bias sits inside the null it is judged against."""
    n = g.shape[0] if g.ndim == 2 else 0
    w = min(window, n // 2)
    if n < 2 * DRIFT_MIN or w < DRIFT_MIN or g.shape[1] == 0:
        return {"t2": UNMEASURED, "p": UNMEASURED, "n_recent": int(max(w, 0)),
                "n_past": int(max(n - w, 0)), "permutations": 0,
                "why": f"need {2 * DRIFT_MIN} rows with {DRIFT_MIN} each side and one feature"}
    observed = _t2(g[-w:], g[:-w])
    rng = np.random.default_rng(0)
    hits = sum(int(_t2(g[(order := rng.permutation(n))[:w]], g[order[w:]]) >= observed)
               for _ in range(DRIFT_PERMS))
    p = (1.0 + hits) / (DRIFT_PERMS + 1.0)
    return {"t2": round(observed, 4), "p": round(p, 4), "n_recent": int(w), "n_past": int(n - w),
            "permutations": DRIFT_PERMS,
            "why": ("recent window differs from its past" if p <= DRIFT_P
                    else "recent window looks like its past")}


# -------------------------------------------------------------------------------------- the pass
def _gate_matrix(rows: list[np.ndarray]) -> tuple[np.ndarray, list[str], np.ndarray]:
    """(kept feature matrix, kept feature names, row mask). A feature unmeasured or FLAT over
    this sleeve's trades is dropped -- never imputed to zero, a state that never happened."""
    raw = np.asarray(rows, dtype=float) if rows else np.zeros((0, len(FEATURES)))
    keep = [j for j in range(raw.shape[1])
            if (col := raw[:, j][np.isfinite(raw[:, j])]).size and float(col.std()) > 0]
    if not keep:
        return np.zeros((raw.shape[0], 0)), [], np.zeros(raw.shape[0], dtype=bool)
    sub = raw[:, keep]
    mask = np.isfinite(sub).all(axis=1)
    return sub[mask], [FEATURES[j] for j in keep], mask


def _router_row(y: np.ndarray, g: np.ndarray, names: list[str], now_row: np.ndarray | None,
                unc_mu: float, sigma0: float
                ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Fit, score, adapt and read the router for one sleeve. Every branch states its `why`."""
    off: dict[str, Any] = {"active": False, "k": UNMEASURED, "oos_logscore_routed": UNMEASURED,
                           "oos_logscore_unrouted": UNMEASURED, "features": names}
    if not names:
        return {**off, "why": "no state feature varies over this sleeve's trades"}, {}, None
    if y.size < MIN_ROUTER_TRADES:
        return {**off, "why": f"{y.size} trades < {MIN_ROUTER_TRADES} needed for folds"}, {}, None
    scored = [_walk_forward(y, g, k) for k in K_GRID]
    usable = [s for s in scored if s.get("net") is not None]
    if not usable:
        return {**off, "why": str(scored[0].get("why", UNMEASURED))}, {}, None
    best = max(usable, key=lambda s: float(s["net"]))
    active = best.get("verdict") == "EARNS_ITS_PLACE"
    row: dict[str, Any] = {
        "active": active, "k": int(best["k"]), "folds": best["folds"], "features": names,
        "oos_logscore_routed": best["oos_logscore_routed"],
        "oos_logscore_unrouted": best["oos_logscore_unrouted"],
        "tax": best["tax"], "net": best["net"], "t_gain": best.get("t_gain"),
        "why": (f"OOS log-score {best['net']:+.4f} nats/trade against the unrouted mean after "
                f"tax {best['tax']} (fold t {best.get('t_gain')})"
                + ("" if active else "; the unrouted mean explains it"))}
    if not active:
        return row, {}, None
    shift = drift(g)
    adapted = (shift["p"] != UNMEASURED and float(shift["p"]) <= DRIFT_P
               and int(shift["n_recent"]) >= ADAPT_MIN)
    take = int(shift["n_recent"]) if adapted else y.size
    fit_y, fit_g = y[-take:], g[-take:]
    try:
        moe = _fit(fit_y, fit_g, int(best["k"]))
        resp = moe.responsibilities(np.zeros((fit_y.size, 1)), fit_y, fit_g)
    except (ValueError, np.linalg.LinAlgError) as exc:      # pragma: no cover - guarded by folds
        row.update({"active": False, "why": f"final fit failed: {type(exc).__name__}: {exc}"})
        return row, {}, None
    experts = []
    for j in range(int(best["k"])):
        w = resp[:, j]
        n_eff = float(w.sum())
        mean = float((w * fit_y).sum() / n_eff) if n_eff > 0 else unc_mu
        post = summarise(nig_update(n_eff, mean, float((w * (fit_y - mean) ** 2).sum()),
                                    n0=BUCKET_N0, mu0=unc_mu, sigma0=sigma0))
        experts.append({"expert": j, "n_eff": round(n_eff, 2), "mu": post["mu_mean"],
                        "p_positive": post["p_positive"]})
    row.update({"fitted_on": "recent_window" if adapted else "all_trades", "experts": experts,
                "expert_usage": [round(float(v), 4) for v in moe.expert_usage()]})
    extra = {"shift": shift, "adapted": adapted}
    if now_row is None:
        row["gate_now"] = UNMEASURED
        return row, extra, None
    gate = moe.gates(now_row.reshape(1, -1))[0]
    pick = int(np.argmax(gate))
    row.update({"gate_now": [round(float(v), 4) for v in gate], "active_expert": pick})
    return row, extra, experts[pick]


def _sleeve_row(sleeve: Sleeve, states: States, when: datetime,
                counts: dict[str, Any]) -> dict[str, Any]:
    """One published row: the unconditional posterior, every bucket, the router, the now-read."""
    values = np.asarray(sleeve.r, dtype=float)
    sigma0 = float(values.std(ddof=1)) if values.size >= 2 and values.std() > 0 else DEFAULT_SIGMA
    unconditional = _post(values, n0=PRIOR_N0, mu0=0.0, sigma0=sigma0)
    cuts = states.cuts(sleeve.symbol, _ns(sleeve.times[0]))
    counts["sleeves_without_vol_axis"] += int(cuts is None)
    reads = [states.read(sleeve.symbol, stamp, cuts) for stamp in sleeve.times]
    buckets: dict[str, list[float]] = defaultdict(list)
    for (labels, _), value in zip(reads, values, strict=True):
        for axis in AXES:
            if labels[axis] != UNMEASURED:
                buckets[f"{axis}={labels[axis]}"].append(float(value))
    by_state = {key: _post(np.asarray(vals, dtype=float), n0=BUCKET_N0,
                           mu0=float(unconditional["mu"]), sigma0=sigma0)
                for key, vals in sorted(buckets.items())}
    gate, names, mask = _gate_matrix([row for _, row in reads])
    counts["rows_without_full_state"] += int(mask.size - mask.sum()) if names else 0
    now_labels, now_raw = states.read(sleeve.symbol, when, cuts)
    now_row: np.ndarray | None = now_raw[[FEATURES.index(n) for n in names]] if names else None
    if now_row is not None and not np.isfinite(now_row).all():
        now_row = None
    router, extra, picked = _router_row(values[mask], gate, names, now_row,
                                        float(unconditional["mu"]), sigma0)
    current = f"{PRIMARY_AXIS}={now_labels[PRIMARY_AXIS]}"
    if picked is not None:
        p_now, basis = picked["p_positive"], "router_expert"
    elif current in by_state:
        p_now, basis = by_state[current]["p_positive"], "state_bucket"
    else:
        p_now, basis = unconditional["p_positive"], "unconditional"
    counts["router_active"] += int(bool(router["active"]))
    counts["representation_adapted"] += int(bool(extra.get("adapted")))
    return {"name": sleeve.name, "lane": sleeve.lane, "symbol": sleeve.symbol,
            "status": sleeve.status, "basis": sleeve.basis, "n": int(values.size),
            "unconditional": unconditional, "by_state": by_state, "router": router,
            "representation_adapted": bool(extra.get("adapted")),
            "shift_stat": extra.get("shift") or drift(gate),
            "current_bucket": current, "current_state": now_labels,
            "p_alpha_positive_now": p_now, "p_alpha_positive_basis": basis}


# ------------------------------------------------------- the pooled router (the small-n path)
def _family_of(sleeve: Sleeve) -> str:
    """The pooling group. `posterior_alpha` owns this parsing; it is imported, never re-derived."""
    name = sleeve.name
    for row in (_read_json(SLEEVES) or {}).get("sleeves") or []:
        if isinstance(row, dict) and row.get("name") == name and row.get("family"):
            return str(row["family"])
    fam = _family_of_key(name) if "." in name else _family_of_name(name)
    return fam or "unclassified"


def _pooled_observations(sleeves: list[Sleeve], states: States) -> list[pooling.Obs]:
    """Every trade in the book, stamped with the latent state that was in force when it ran."""
    obs: list[pooling.Obs] = []
    for sleeve in sleeves:
        if not sleeve.r:
            continue
        bs = states.hmm(sleeve.symbol)
        if bs is None:
            continue
        family = _family_of(sleeve)
        for when, value in zip(sleeve.times, sleeve.r, strict=False):
            ns = _ns(when)
            label = bs.label_at(ns)
            if label is None:
                continue
            obs.append(pooling.Obs(sleeve=sleeve.name, family=family, state=label,
                                   r=float(value), ns=ns))
    return obs


def _pooled_router(obs: list[pooling.Obs]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """THE ANSWER FOR SLEEVES THE FOLD MINIMUM REFUSES, and the book-level verdict.

    The walk-forward path needs 24 trades to cut four folds. Measured on the box 2026-09-24 the
    LARGEST sleeve in the book had 23, so that path could not score a single one and the router
    published DARK. This path asks the same question with an estimator that works at small n:
    every trade is predicted from the trades STRICTLY BEFORE it, the state-conditional mean is
    borrowed from the sleeve's family where the sleeve itself is thin, and the routed and the
    unrouted model are scored on an IDENTICAL trade set with the identical proper score and the
    identical tax. Nothing about the bar was lowered -- the estimator was changed.
    """
    tax = float(TAX["soft_moe"])
    if len(obs) < 8:
        return ({"status": UNMEASURED, "n_observations": len(obs), "tax": tax,
                 "why": (f"{len(obs)} state-labelled trade(s) in the whole book: the pooled "
                         f"router is UNMEASURED, which is a verdict and not a zero")}, {})
    y_u, mu_u, _ = pooling.prequential(obs, use_state=False)
    _y_r, mu_r, detail = pooling.prequential(obs, use_state=True)
    y = np.asarray(y_u, dtype=float)
    pu, pr = np.asarray(mu_u, dtype=float), np.asarray(mu_r, dtype=float)
    if y.size < 4:
        return ({"status": UNMEASURED, "n_observations": len(obs), "n_scored": int(y.size),
                 "tax": tax, "why": f"only {y.size} prequential prediction(s) were possible"}, {})
    sd_book = max(float(np.std([o.r for o in obs], ddof=1)), 1e-6)
    sd_u = max(float(np.std(y - pu, ddof=1)), SD_FLOOR_FRAC * sd_book, 1e-6)
    sd_r = max(float(np.std(y - pr, ddof=1)), SD_FLOOR_FRAC * sd_book, 1e-6)
    ls_u, ls_r = _logscore(y, pu, sd_u), _logscore(y, pr, sd_r)
    gain = ls_r - ls_u
    diff = (-(y - pr) ** 2) - (-(y - pu) ** 2)
    se = float(np.std(diff, ddof=1) / np.sqrt(diff.size)) if diff.size > 1 else float("inf")
    t_gain = float(np.mean(diff) / se) if se > 0 else 0.0
    earns = bool(gain - tax > 0 and t_gain >= MIN_T_GAIN)
    book = {
        "status": "MEASURED", "n_observations": len(obs), "n_scored": int(y.size),
        "oos_logscore_routed": round(ls_r, 6), "oos_logscore_unrouted": round(ls_u, 6),
        "gain": round(gain, 6), "tax": tax, "net": round(gain - tax, 6),
        "t_gain": round(t_gain, 3), "active": earns,
        "state_effect_basis": dict(Counter(p.basis for p in detail)),
        "verdict": "EARNS_ITS_PLACE" if earns else "TAXED_OUT",
        "why": (f"the latent state moved the book's OOS log-score by {gain:+.4f} nats/trade "
                f"before tax {tax} (paired t {t_gain:+.2f}); "
                + ("routing earns its place" if earns else
                   "the unrouted model explains it, which is a MEASURED zero and not a dark one")),
        "score": "mean OOS Gaussian predictive log-density, nats per trade -- the SAME score and "
                 "tax the walk-forward path uses, so the two answers are comparable",
    }
    ordered = sorted(obs, key=lambda o: (o.ns, o.sleeve))
    offset = len(ordered) - y.size
    by_sleeve: dict[str, list[int]] = defaultdict(list)
    for i, o in enumerate(ordered):
        if i >= offset:
            by_sleeve[o.sleeve].append(i - offset)
    rows: dict[str, dict[str, Any]] = {}
    for name, ix in by_sleeve.items():
        a = np.asarray(ix, dtype=int)
        if a.size < MIN_POOLED_TRADES:
            rows[name] = {"scored": False, "n": int(a.size),
                          "why": f"{a.size} prequential prediction(s) < {MIN_POOLED_TRADES}"}
            continue
        lu, lr = _logscore(y[a], pu[a], sd_u), _logscore(y[a], pr[a], sd_r)
        rows[name] = {"scored": True, "n": int(a.size),
                      "oos_logscore_routed": round(lr, 6),
                      "oos_logscore_unrouted": round(lu, 6),
                      "net": round(lr - lu - tax, 6), "tax": tax,
                      "active": bool(lr - lu - tax > 0),
                      "basis": "prequential_partial_pooling"}
    return book, rows


def _hmm_block(states: States, published: list[dict[str, Any]],
               pooled_book: dict[str, Any],
               k_choice: dict[str, Any] | None = None) -> dict[str, Any]:
    """THE STATE, ITS PROBABILITIES AND ITS TRANSITIONS -- published, per symbol.

    A regime call with no probability attached cannot be acted on proportionately, so every row
    carries the full forward-filtered posterior, the transition matrix the chain was fitted with,
    the expected dwell time of the state it is in, and the horizon distribution from
    `libs.regime.transitions` (which is the desk's existing semi-Markov forecaster, reused rather
    than duplicated). `k_scores` carries the held-out evidence that chose the state count, so the
    choice can be checked rather than believed.
    """
    rows: dict[str, Any] = {}
    gaps: dict[str, str] = {}
    for symbol in sorted({str(r["symbol"]) for r in published}):
        bs = states.hmm(symbol)
        if bs is None:
            gaps[symbol] = "tape too short to fit a state model: UNMEASURED, not a state"
            continue
        i = int(bs.labels.size) - 1
        post = np.asarray(bs.posterior[i], dtype=float)
        dwell = [round(float(1.0 / max(1e-9, 1.0 - bs.transmat[j, j])), 2) for j in range(bs.k)]
        row: dict[str, Any] = {
            "k": bs.k, "k_chosen_by": "held-out one-step predictive log-density, nats/bar",
            "k_scores": {str(a): round(b, 5) for a, b in sorted(bs.k_scores.items())},
            "heldout_logdens": (round(bs.heldout_logdens, 5)
                                if np.isfinite(bs.heldout_logdens) else UNMEASURED),
            "state_now": bs.names[int(bs.labels[i])],
            "p_state_now": {bs.names[j]: round(float(post[j]), 4) for j in range(bs.k)},
            "transmat": [[round(float(v), 4) for v in r] for r in bs.transmat],
            "expected_dwell_bars": dict(zip(bs.names, dwell, strict=True)),
            "fitted_on_bars": bs.n_train, "labelled_bars": int(bs.labels.size),
            "transitions_recent": run_length_path(bs)[-12:],
        }
        try:
            fc = transition_forecast(bs.transmat, post, dict(enumerate(bs.names)),
                                     bs.labels.astype(int))
            row["p_ahead"] = {str(h): {k: round(v, 4) for k, v in fc.p_ahead[h].items()}
                              for h in fc.horizons}
            row["p_leave"] = {str(h): round(float(v), 4) for h, v in fc.p_leave.items()}
        except (ValueError, np.linalg.LinAlgError) as exc:
            row["p_ahead"] = f"{UNMEASURED}: {type(exc).__name__}: {exc}"
        rows[symbol] = row
    return {
        "rule": ("the regime is a property of the MARKET, fitted on bars, so it needs no sleeve "
                 "to have traded; the labels are causal (forward filter, never Viterbi -- L0307) "
                 "and their parameters are fitted strictly before the first trade in the book"),
        "model": "libs.regime.bar_states.fit_states (libs.regime.hmm.GaussianHMM, Baum-Welch)",
        "timeframe": "H1", "seed": HMM_SEED, "fit_bars": HMM_MAX_BARS,
        "state_count": k_choice or {"status": UNMEASURED,
                                    "why": "the state count was not asked on this pass"},
        "n_symbols": len(rows), "symbols": rows, "gaps": gaps,
        "pooled_router": pooled_book,
        "pooling": {"model": "libs.regime.pooling (sleeve -> family -> book, and the state "
                             "effect at the family level shrunk toward the book's)",
                    "k_level": pooling.K_LEVEL, "k_state": pooling.K_STATE,
                    "k_global": pooling.K_GLOBAL},
    }


def run(write: bool = True, now: datetime | None = None) -> dict[str, Any]:
    """Every live sleeve and running forward clock, routed by state, written atomically."""
    reset_caches()
    notes: list[str] = []
    counts: dict[str, Any] = defaultdict(int)
    when = now or datetime.now(UTC)
    sleeves = collect(notes, counts)
    # THE HMM'S TRAINING CUTOFF is the first trade anywhere in the book, so every state label the
    # scoring path reads was produced by parameters that had never seen a trade. Without this the
    # comparison below would be fitted on the window it judges, which is not a comparison.
    trade_ns = [_ns(t) for s in sleeves for t in s.times]
    states = States(notes, hmm_train_end_ns=min(trade_ns) if trade_ns else None)
    # HOW MANY STATES, asked once, on the symbols the book actually trades most -- so the answer
    # is paid for once and every symbol shares one label vocabulary.
    traded = sorted({s.symbol for s in sleeves if s.r},
                    key=lambda sy: -sum(len(s.r) for s in sleeves if s.symbol == sy))
    k_choice = states.choose_state_count(traded)
    published: list[dict[str, Any]] = []
    for sleeve in sleeves:
        if not sleeve.r:
            counts["sleeves_without_trades"] += 1
            continue
        counts["trades"] += len(sleeve.r)
        published.append(_sleeve_row(sleeve, states, when, counts))
    pooled_book, pooled_rows = _pooled_router(_pooled_observations(sleeves, states))
    for row in published:
        row["pooled_router"] = pooled_rows.get(
            str(row["name"]), {"scored": False, "n": 0,
                               "why": "no trade of this sleeve carried a latent state label"})
    counts["pooled_scored"] = sum(1 for r in pooled_rows.values() if r.get("scored"))
    counts["pooled_active"] = sum(1 for r in pooled_rows.values() if r.get("active"))
    published.sort(key=lambda r: (not r["router"]["active"], -float(r["p_alpha_positive_now"]),
                                  str(r["name"])))
    # WHAT THIS NOTE USED TO SAY WHEN NOTHING HAD BEEN JUDGED, AND WHY IT HAD TO CHANGE.
    # "no sleeve's router beats its unrouted model out of sample after tax" fired on `active`
    # alone -- so it fired identically whether forty-eight routers were scored and lost, or
    # ZERO were scored because every sleeve was under the fold minimum. MEASURED on the box
    # 2026-09-24: 48 published, 0 scored, 34 short of trades and 14 with no varying state
    # feature. The desk was publishing a negative OOS RESULT for a test that had never run,
    # which is the exact shape of a claim the desk cannot cash (L1.49).
    n_scored = sum(1 for r in published if isinstance(r.get("router"), dict)
                   and r["router"].get("net") is not None)
    if not published:
        notes.append("no live sleeve and no running forward clock has a measured trade: the "
                     "router is UNMEASURED, which is a verdict and not a zero")
    elif not n_scored:
        notes.append(f"no router was SCORED on this host: {len(published)} sleeve(s) reached the "
                     f"router and none produced a walk-forward net, so `router_active: 0` is a "
                     f"DARK ROUTER and not a judgement -- see router_census.not_scored_reasons")
    elif not any(r["router"]["active"] for r in published):
        notes.append(f"none of the {n_scored} SCORED router(s) beats its unrouted model out of "
                     f"sample after tax; this is a measured zero")
    current = {k: v for k, v in states.read("", when, None)[0].items() if k != "vol"}
    transition = _record_state(current, when, write=write)
    payload = {
        "at": when.isoformat(),
        "rule": RULE,
        "n_sleeves": len(published),
        "current_state": current,
        "last_transition": transition,
        "router_census": _router_census(published, counts),
        "state_sources": {"vol": f"trailing {VOL_LOOKBACK}-bar H1 realised vol, terciles cut on "
                                 "pre-trade tape", "usd": states.usd_symbol,
                          "risk": states.risk_symbol, "session": "mt5desk.family_call.SESSIONS",
                          HMM_AXIS: "Baum-Welch Gaussian HMM on the symbol's own H1 bars; label "
                                    "is the argmax of the causal forward filter, never Viterbi"},
        "hmm": _hmm_block(states, published, pooled_book, k_choice),
        "router_spec": {"model": "libs.models.router.SoftMoE", "k_grid": list(K_GRID),
                        "folds": ROUTER_FOLDS, "tax": float(TAX["soft_moe"]),
                        "min_trades": MIN_ROUTER_TRADES,
                        "score": "mean OOS Gaussian predictive log-density, nats per trade"},
        "prior": {"unconditional_n0": float(PRIOR_N0), "bucket_n0": float(BUCKET_N0),
                  "bucket_mu0": "the sleeve's unconditional posterior mean"},
        "sleeves": published,
        "unmeasured": notes,
        "counts": dict(counts),
        "inputs": {str(p): ("present" if p.exists() else "absent")
                   for p in (SLEEVES, LIVE_LEDGER, SHADOW_STATE, UNI)},
    }
    if write:
        _write_atomic(OUT, payload)
    return payload


def _history_rows() -> list[dict[str, Any]]:
    """The observed state changes, oldest first. An unreadable or absent sidecar is empty, and
    that emptiness is reported as "never observed", never as "never changed"."""
    out: list[dict[str, Any]] = []
    try:
        text = HISTORY.read_text("utf-8-sig", errors="replace")
    except OSError:
        return out
    for line in text.splitlines()[-HISTORY_KEEP:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("at"):
            out.append(row)
    return out


def _record_state(current: dict[str, Any], when: datetime, *, write: bool) -> dict[str, Any]:
    """Append this pass's state IF IT CHANGED, and report when the last change was.

    THE DISTINCTION THIS FUNCTION EXISTS TO DRAW. "The regime has not changed" and "nobody was
    watching" are different facts and used to render the same -- UNMEASURED. They are separated
    here by the OBSERVATION WINDOW: the sidecar's first row is when this desk started watching,
    so a state that has held since then is MEASURED-and-unchanged with its watch start beside it,
    and only a desk that has never watched at all reads UNMEASURED.

    A state with an UNMEASURED axis is still recorded. Dropping it would make the history lie by
    omission -- the axis going dark IS a change in what the desk can see, and a later reader
    comparing two rows across the gap would measure a transition that never happened.
    """
    rows = _history_rows()
    previous = rows[-1] if rows else None
    prev_state = previous.get("state") if isinstance(previous, dict) else None
    changed = prev_state != current
    if changed and write:
        try:
            HISTORY.parent.mkdir(parents=True, exist_ok=True)
            with HISTORY.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"at": when.isoformat(), "state": current,
                                         "from": prev_state}) + "\n")
        except OSError:                          # pragma: no cover - a read-only sidecar
            changed = False
        else:
            rows.append({"at": when.isoformat(), "state": current, "from": prev_state})
    if not rows:
        return {"status": UNMEASURED, "at": None, "age_s": None, "from": None, "to": current,
                "n_transitions": 0, "observed_since": None,
                "why": ("no state has ever been recorded on this host, so the time of the last "
                        "regime change is genuinely unknown rather than long ago")}
    last = rows[-1]
    first = rows[0]
    last_at, first_at = _as_utc(str(last.get("at"))), _as_utc(str(first.get("at")))
    age = (when - last_at).total_seconds() if last_at is not None else None
    watched = (when - first_at).total_seconds() if first_at is not None else None
    # ONE ROW AND NO `from` IS THE FIRST OBSERVATION, NOT A TRANSITION. Counting it as one would
    # date the desk's last regime change to the day it started looking.
    n_trans = sum(1 for r in rows if r.get("from"))
    return {
        "status": "MEASURED",
        "at": last.get("at"),
        "age_s": round(age, 1) if age is not None else None,
        "from": last.get("from"),
        "to": last.get("state"),
        "n_transitions": n_trans,
        "observed_since": first.get("at"),
        "observed_s": round(watched, 1) if watched is not None else None,
        "changed_this_pass": bool(changed),
        "source": str(HISTORY),
        "why": ("" if n_trans else
                f"the state has not changed since this desk began watching it at "
                f"{first.get('at')}: a MEASURED steady state over that window, which is a "
                f"different fact from an unmeasured one"),
    }


def _as_utc(stamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _router_census(published: list[dict[str, Any]], counts: dict[str, Any]) -> dict[str, Any]:
    """WHY `router_active` IS ZERO -- judged and rejected, or never judged at all.

    A dashboard reading `router_active: 0` cannot tell a router that ran on every sleeve and
    found none worth its tax from a router that never scored anything, and those are opposite
    facts: the first is a measurement the desk should trust, the second is a dark organ. The
    difference is already in each sleeve's own `router` block -- a SCORED row carries `net`, an
    unscored one carries only its `why` -- so this counts it rather than inventing anything.
    """
    scored = [r for r in published if isinstance(r.get("router"), dict)
              and r["router"].get("net") is not None]
    unscored = [r for r in published if isinstance(r.get("router"), dict)
                and r["router"].get("net") is None]
    reasons: dict[str, int] = {}
    for row in unscored:
        why = str(row["router"].get("why") or UNMEASURED)
        # The trade-count reason names the count, so a thousand sleeves would make a thousand
        # keys; the shape of the reason is what a reader needs, not each sleeve's n.
        key = ("fewer trades than the router's fold minimum"
               if "trades <" in why else
               "no state feature varies over this sleeve's trades"
               if "no state feature" in why else why[:90])
        reasons[key] = reasons.get(key, 0) + 1
    nets = [float(r["router"]["net"]) for r in scored]
    active = sum(1 for r in scored if r["router"].get("active"))
    if not published:
        verdict, why = UNMEASURED, ("no sleeve reached the router at all: the zero is an absence "
                                    "of subjects, not a judgement about routing")
    elif not scored:
        verdict, why = UNMEASURED, (f"{len(published)} sleeve(s) published and NONE was scored: "
                                    f"the router is dark on this host and its zero carries no "
                                    f"judgement. Reasons: {reasons}")
    elif active:
        verdict, why = "MEASURED", f"{active} of {len(scored)} scored router(s) earn their tax"
    else:
        verdict, why = "MEASURED", (
            f"a MEASURED ZERO: all {len(scored)} scored router(s) were judged out of sample and "
            f"none beat its unrouted model after tax (best net {max(nets):+.4f} nats/trade "
            f"against a tax of {float(TAX['soft_moe']):.4f}). This is the router working, not "
            f"the router missing")
    return {
        "status": verdict, "why": why,
        "n_sleeves_in_registry": int(counts.get("sleeves_without_trades", 0)) + len(published),
        "n_without_trades": int(counts.get("sleeves_without_trades", 0)),
        "n_published": len(published),
        "n_scored": len(scored),
        "n_not_scored": len(unscored),
        "not_scored_reasons": reasons,
        "n_active": active,
        "best_net": round(max(nets), 6) if nets else None,
        "median_net": round(float(np.median(nets)), 6) if nets else None,
        "tax": float(TAX["soft_moe"]),
        "min_trades": int(MIN_ROUTER_TRADES),
        "basis": ("a sleeve is SCORED when walk-forward produced a net OOS log-score; it is "
                  "ACTIVE when that net beats the tax with fold t >= the spec's minimum"),
    }


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                  # a read-only destination is WinError 5 on this box
        path.chmod(0o644)
        os.replace(tmp, path)


def _cell(value: Any, width: int = 8) -> str:
    if isinstance(value, float):
        return f"{value:>{width}.3f}"
    return f"{('--' if value == UNMEASURED else str(value))[:width]:>{width}}"


def render(payload: dict[str, Any], limit: int = 25) -> str:
    """The table a human reads: routed sleeves first, then what the state could not say."""
    state = " ".join(f"{k}={v}" for k, v in payload["current_state"].items())
    lines = [f"REGIME ROUTER  n_sleeves={payload['n_sleeves']}  now: {state}",
             f"{'sleeve':28s} {'lane':8s} {'n':>4s} {'mu':>8s} {'P(a>0)':>8s} {'bucket':>9s} "
             f"{'P(a>0|now)':>10s} {'k':>3s} {'routed':>8s} {'unrouted':>8s} {'net':>8s} A D"]
    for row in payload["sleeves"][:limit]:
        router = row["router"]
        lines.append(
            f"{str(row['name'])[:28]:28s} {str(row['lane'])[:8]:8s} {int(row['n']):>4d} "
            f"{_cell(row['unconditional']['mu'])} {_cell(row['unconditional']['p_positive'])} "
            f"{str(row['current_bucket'])[-9:]:>9s} {_cell(row['p_alpha_positive_now'], 10)} "
            f"{_cell(router['k'], 3)} {_cell(router['oos_logscore_routed'])} "
            f"{_cell(router['oos_logscore_unrouted'])} {_cell(router.get('net', UNMEASURED))} "
            f"{'Y' if router['active'] else '-'} {'Y' if row['representation_adapted'] else '-'}")
    if len(payload["sleeves"]) > limit:
        lines.append(f"  ... {len(payload['sleeves']) - limit} more rows in the artifact")
    lines.extend(f"  UNMEASURED  {note}" for note in payload["unmeasured"])
    lines.append(f"  rule: {payload['rule']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Route each sleeve by the state the desk is in.")
    ap.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    ap.add_argument("--limit", type=int, default=25, help="rows in the printed table")
    args = ap.parse_args(argv)
    payload = run(write=not args.dry_run)
    print(render(payload, limit=args.limit))
    print("(dry run, nothing written)" if args.dry_run else f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
