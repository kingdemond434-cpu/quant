"""PROPRIETARY LABEL FACTORY -- event labels as versioned research assets (RANK 6).

WHAT A LABEL IS, AND THE TRAP THIS IS BUILT AROUND. A label marks that something HAPPENED
(liquidity stress, forced deleveraging, accumulation, a regime turn). It is not an alpha and it is
not a signal, and the single most dangerous thing about labels is that the most natural way to
define one uses the very window it describes. "Forced deleveraging happened here" is usually
recognised FROM the cascade -- so if you then test whether the label predicts the cascade's returns,
you have measured your own definition and it will look spectacular.

So every label declares KNOWN_AT_LAG: how many bars after ``t`` before ``label[t]`` could actually
have been known. Three of the four families below are knowable at the close of ``t`` (lag 0). The
fourth, ``regime_transition``, genuinely is NOT -- a regime turn is only a turn once it persists, so
it carries an honest confirmation lag. Encoding that as a field rather than a comment is the whole
point: this is the class that produced the bithumb KST/UTC IC-0.72 fake and the kimchi
construction bug, and both were arithmetic that looked fine and was aligned wrong.

VALIDATION IS ABOUT THE LABEL, NOT ABOUT PROFIT. ``validate`` asks whether the label is a
well-formed event marker: does it fire at a testable rate, is it an EVENT rather than a state
wearing an event's name, and is it free of lookahead at its declared lag. Whether a label predicts
returns is a separate hypothesis, screened through ``libs.research.axis_screen`` with every
multiplicity cost that implies. Keeping those two questions apart matters: "my label is well
formed" is a data-quality claim, "my label predicts returns" is a trial, and a factory that blurs
them manufactures trials nobody counted.

THE CAUSALITY TEST IS TRUNCATION, and arriving there took two wrong turns worth recording, because
both LOOKED like working guards. The obvious approach is `libs/features/validation.py`'s
future-invariance mechanism -- mutate future bars, require past values unchanged -- generalised to
allow a declared lag. It does not work here:

  * mutating by a CONSTANT multiple (what that module does, correctly, for level-based features)
    leaves every future ``pct_change`` identical except at one boundary bar, so it is nearly blind
    to return-based labels -- which is most of them;
  * per-bar RANDOM mutation compared at sampled ``t`` fails differently: event labels are sparse, so
    a sampled point almost always compares 0 against 0, and scrambling a whole tail makes everything
    uniformly "stepped", which an onset rule (``fires & ~fired_before``) then absorbs.

A deliberately mislabelled lag-0 ``regime_transition`` -- openly reading five bars ahead -- passed
BOTH. What works is the definition itself: recompute the label on ``bars[:t + lag + 1]``, the data
that existed when the label claims to be knowable, and require ``label[t]`` unchanged. Sampling is
weighted to FIRING positions for the same sparsity reason. That version rejects the mislabelled
label at 20 of 31 checked positions and passes the honest lag-5 one cleanly.

VERSIONING IS BY CONTENT, NOT BY HAND. ``LabelSpec.version`` is a hash of the family plus its
parameters, so retuning a threshold produces a new version automatically and an old validation
record can never silently describe a redefined label. Lineage (``inputs``) names the RANK 4
registry asset ids the label was built from, so a label whose source panel is 17 days long cannot
be mistaken for one built on the 267-symbol 2019-09 panel.

numpy + pandas. Import from ``libs.research.label_factory``; CLI is ``scripts/build_labels.py``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

#: A label firing this rarely cannot be tested -- there is no power at any horizon.
MIN_BASE_RATE = 0.005
#: A label firing this often is describing a STATE, not an event. "Stressed 40% of the time" is a
#: regime variable; calling it an event invites event-study machinery that assumes rarity.
MAX_BASE_RATE = 0.35
#: Longest allowed consecutive run, as a fraction of all firings. A label that fires in one
#: contiguous blob is a period flag (one 2022 blob = "the year 2022"), not a repeatable event.
MAX_RUN_FRACTION = 0.5

VERDICT_VALID = "VALID"
VERDICT_RARE = "DEGENERATE-RARE"
VERDICT_COMMON = "DEGENERATE-COMMON"
VERDICT_BLOB = "BLOB-NOT-EVENT"
VERDICT_LEAKING = "LEAKING"
VERDICT_INERT = "INERT"


@dataclass(frozen=True)
class LabelSpec:
    """A label DEFINITION. Immutable; retuning a parameter yields a different ``version``."""

    id: str
    family: str
    params: Mapping[str, float] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()          #: RANK 4 registry asset ids -- lineage, not decoration
    known_at_lag: int = 0                 #: bars after t before label[t] is knowable
    rationale: str = ""

    @property
    def version(self) -> str:
        """Content hash: family + sorted params. A retuned threshold is a NEW label, not an edit."""
        payload = json.dumps({"family": self.family,
                              "params": {k: float(v) for k, v in sorted(self.params.items())},
                              "known_at_lag": self.known_at_lag}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @property
    def qualified_id(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass
class LabelValidation:
    """Whether the label is a well-formed EVENT marker. Says nothing about profitability."""

    verdict: str
    base_rate: float
    n_events: int
    n_firings: int
    max_run: int
    leak_checked: int = 0
    leak_failures: int = 0
    responds_to_inputs: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.verdict == VERDICT_VALID


# ------------------------------------------------------------------ helpers on the bronze panel


def _mask(cond: pd.Series) -> pd.Series:
    """A boolean event MASK, where a missing observation means "no event".

    `cond.fillna(False)` on an object-dtype comparison silently DOWNCASTS. pandas 2.x deprecates
    that and this repo runs `filterwarnings = error`, so eight label-factory tests were RED on a
    warning -- a suite failing for a pandas-version reason teaches the desk to ignore it.

    `.where(notna, False)` rather than the `infer_objects(copy=False)` the warning suggests:
    measured on pandas 2.x, the deprecation fires INSIDE `fillna` itself, so chaining
    infer_objects afterwards is too late and still errors. `where` never downcasts, so the mask
    is built without the deprecated path at all. Applied ONCE so the intent -- "absent data is
    not an event" -- lives in one place instead of ten call sites.
    """
    return cond.where(cond.notna(), False).astype(bool)

def _need(bars: pd.DataFrame, *cols: str) -> bool:
    return all(c in bars.columns for c in cols)


def _roll_q(s: pd.Series, win: int, q: float) -> pd.Series:
    """Rolling quantile with a CAUSAL window (closed on the left of t+1, includes t)."""
    return s.rolling(win, min_periods=max(5, win // 4)).quantile(q)


def _true_range(bars: pd.DataFrame) -> pd.Series:
    hi, lo, cl = bars["high"], bars["low"], bars["close"]
    prev = cl.shift(1)
    return pd.concat([hi - lo, (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)


# ------------------------------------------------------------------ the four label families

def liquidity_stress(bars: pd.DataFrame, *, atr_win: int = 20, range_mult: float = 2.0,
                     vol_q: float = 0.9, vol_win: int = 60) -> np.ndarray:
    """Range blows out relative to its own recent ATR **and** volume confirms.

    Mechanism: stress is not a big move, it is a big move that needed unusual volume to clear --
    depth was thin. Requiring both is what separates stress from a clean repricing on normal flow.
    Knowable at the close of t (lag 0): every input is same-bar or earlier.
    """
    atr_win, vol_win = int(atr_win), int(vol_win)
    if not _need(bars, "high", "low", "close"):
        return np.zeros(len(bars), dtype=np.int8)
    tr = _true_range(bars)
    atr = tr.rolling(atr_win, min_periods=max(5, atr_win // 4)).mean().shift(1)  # prior ATR only
    wide = _mask(tr > range_mult * atr)
    if _need(bars, "volume"):
        heavy = _mask(bars["volume"] > _roll_q(bars["volume"], vol_win, vol_q).shift(1))
    else:
        heavy = pd.Series(True, index=bars.index)
    return np.asarray((wide & heavy).to_numpy(), dtype=np.int8)


def forced_deleveraging(bars: pd.DataFrame, *, ret_q: float = 0.05, win: int = 60,
                        oi_drop: float = 0.02) -> np.ndarray:
    """Adverse move while OPEN INTEREST FALLS -- positions closing, not new ones opening.

    This is the actual signature of a liquidation cascade and it is why OI is load-bearing: a sharp
    drop on RISING OI is new shorts (a directional bet), the same drop on FALLING OI is existing
    longs being removed. Without OI the two are indistinguishable, so this family refuses to emit
    rather than guess -- an all-zero label is honest, a lookalike built from price alone is not.
    Knowable at the close of t (lag 0).
    """
    win = int(win)
    if not _need(bars, "close", "open_interest"):
        return np.zeros(len(bars), dtype=np.int8)
    ret = bars["close"].pct_change()
    thresh = _roll_q(ret, win, ret_q).shift(1)           # prior distribution only
    sharp_down = _mask(ret < thresh)
    oi_falling = _mask(bars["open_interest"].pct_change() < -abs(oi_drop))
    return np.asarray((sharp_down & oi_falling).to_numpy(), dtype=np.int8)


def accumulation_window(bars: pd.DataFrame, *, win: int = 20, vol_q: float = 0.3,
                        drift_max: float = 0.02, oi_rise: float = 0.05) -> np.ndarray:
    """Quiet price, compressed realised vol, and OI BUILDING -- positioning without repricing.

    Mechanism: someone is taking size without moving the market. Requires all three, because low
    vol alone is just a quiet market and rising OI alone is just growth.
    Knowable at the close of t (lag 0): the window looks BACKWARD from t.
    """
    win = int(win)
    if not _need(bars, "close"):
        return np.zeros(len(bars), dtype=np.int8)
    ret = bars["close"].pct_change()
    rv = ret.rolling(win, min_periods=max(5, win // 4)).std()
    calm = _mask(rv < _roll_q(rv, win * 5, vol_q).shift(1))
    drift = (bars["close"] / bars["close"].shift(win) - 1.0).abs()
    flat = _mask(drift < abs(drift_max))
    if _need(bars, "open_interest"):
        oi = bars["open_interest"]
        building = _mask(oi / oi.shift(win) - 1.0 > abs(oi_rise))
    else:
        building = pd.Series(True, index=bars.index)
    return np.asarray((calm & flat & building).to_numpy(), dtype=np.int8)


#: ``regime_transition``'s honest confirmation lag. A vol-regime turn is only a turn once it holds.
REGIME_CONFIRM_BARS = 5


def regime_transition(bars: pd.DataFrame, *, win: int = 20, ratio: float = 1.8,
                      confirm: int = REGIME_CONFIRM_BARS) -> np.ndarray:
    """Realised vol steps to a new level **and stays there** for ``confirm`` bars.

    THE LAGGED FAMILY, and the reason ``known_at_lag`` exists at all. Persistence is what separates
    a regime change from a single loud bar, and persistence can only be observed after the fact. So
    ``label[t]`` marks that a transition began at ``t`` and is only KNOWABLE at ``t + confirm``.
    Using it as a same-bar predictor is lookahead; ``validate`` allows exactly this lag and no more.
    """
    win, confirm = int(win), int(confirm)
    if not _need(bars, "close"):
        return np.zeros(len(bars), dtype=np.int8)
    ret = bars["close"].pct_change()
    rv = ret.rolling(win, min_periods=max(5, win // 4)).std()
    prior = rv.shift(win)
    stepped = _mask(rv > ratio * prior)
    # held: the step is still in force through the confirmation window
    held = stepped.copy()
    for k in range(1, max(1, confirm) + 1):
        held &= _mask(rv.shift(-k) > ratio * prior)
    fresh = held & ~_mask(held.shift(1))          # mark the ONSET, not every held bar
    return np.asarray(fresh.to_numpy(), dtype=np.int8)


#: family -> (generator, honest knowability lag)
FAMILIES: dict[str, tuple[Callable[..., np.ndarray], int]] = {
    "liquidity_stress": (liquidity_stress, 0),
    "forced_deleveraging": (forced_deleveraging, 0),
    "accumulation_window": (accumulation_window, 0),
    "regime_transition": (regime_transition, REGIME_CONFIRM_BARS),
}


def generate(spec: LabelSpec, bars: pd.DataFrame) -> np.ndarray:
    fn, _lag = FAMILIES[spec.family]
    return fn(bars, **dict(spec.params))


# ------------------------------------------------------------------ validation

def _runs(y: np.ndarray) -> list[int]:
    out: list[int] = []
    run = 0
    for v in y:
        if v:
            run += 1
        elif run:
            out.append(run)
            run = 0
    if run:
        out.append(run)
    return out


def _mutate_from(bars: pd.DataFrame, cols: list[str], start: int, seed: int = 0) -> pd.DataFrame:
    """Scramble bars from ``start`` onward. Used for the RESPONSIVENESS check only.

    Causality is tested by truncation (see ``leakage_check``), not by this. Mutation survives here
    for the opposite question -- does the label react to its inputs at all? -- and the factors are
    independent PER BAR rather than a constant multiple, because a constant multiple leaves every
    pct_change unchanged and so is invisible to any return-based label.
    """
    rng = np.random.default_rng(seed)
    out = bars.copy()
    n_tail = len(out) - start
    if n_tail <= 0:
        return out
    factors = rng.lognormal(0.0, 1.5, size=n_tail)         # wildly different returns AND levels
    # POSITIONAL, never label-based: the bronze panel carries duplicate timestamps, and
    # ``.loc[index[start:]]`` on a duplicated index fans out to every matching row
    # (measured: 9,956 labels -> 1,218,352 rows), crashing the broadcast. R0095.
    for c in cols:
        vals = out[c].to_numpy(copy=True).astype(float)
        vals[start:] *= factors
        out[c] = vals
    return out


def leakage_check(spec: LabelSpec, bars: pd.DataFrame, *,
                  sample: int = 24) -> tuple[int, int, bool]:
    """(checked, failures, responds_to_inputs): is ``label[t]`` computable at ``t + known_at_lag``?

    TRUNCATION, NOT MUTATION -- this is the definition of knowability rather than a proxy for it.
    Recompute the label on ``bars[:t + lag + 1]``, i.e. exactly the data that existed at the moment
    the label claims to be knowable, and require the value at ``t`` to be unchanged. Two earlier
    designs were tried here and BOTH passed a label that openly read five bars ahead:

      * ``libs/features/validation.py``'s mutate-the-future-by-*1000. A constant multiple leaves
        every future pct_change identical except at one boundary bar, so it is nearly blind to any
        return-based label -- which is most of them.
      * Per-bar random mutation, compared at sampled ``t``. Event labels are SPARSE, so a sampled
        point almost always compares 0 against 0; and mutating a whole tail makes everything
        uniformly "stepped", which an onset rule (``fires & ~fired_before``) then absorbs.

    Truncation has neither weakness, and SAMPLING IS WEIGHTED TO FIRING POSITIONS for the same
    sparsity reason: a violation shows up where the label actually fires, so those are the positions
    that must be checked, plus a spread of quiet ones to catch the reverse error.

    The third return value guards the OPPOSITE failure: a label that ignores its inputs passes any
    causality test perfectly -- an all-zero array is maximally causal and entirely useless.
    """
    cols = [c for c in ("open", "high", "low", "close", "volume", "open_interest")
            if c in bars.columns]
    n = len(bars)
    if not cols or n < 60:
        return 0, 0, True
    base = generate(spec, bars)
    lag = max(0, spec.known_at_lag)
    warmup = int(n * 0.25)                     # below this, rolling windows are still filling
    hi = n - lag - 2

    firing = [int(t) for t in np.flatnonzero(base) if warmup < t < hi]
    quiet = [int(t) for t in np.linspace(warmup + 1, hi, num=max(3, sample // 2)) if t < hi]
    points = sorted(set(firing[:sample] + quiet))
    if not points:
        return 0, 0, bool(base.sum())

    failures = 0
    for t in points:
        knowable_at = generate(spec, bars.iloc[:t + lag + 1])
        if len(knowable_at) > t and int(knowable_at[t]) != int(base[t]):
            failures += 1

    responds = bool(np.any(generate(spec, _mutate_from(bars, cols, 0, seed=99)) != base)
                    or base.sum())
    return len(points), failures, responds


def validate(spec: LabelSpec, bars: pd.DataFrame, *, sample: int = 24) -> LabelValidation:
    """Is this a well-formed EVENT marker?

    Profitability is a separate, multiplicity-counted test through axis_screen.
    """
    y = generate(spec, bars)
    n = max(1, len(y))
    firings = int(y.sum())
    runs = _runs(y)
    max_run = max(runs) if runs else 0
    base_rate = firings / n
    checked, failures, responds = leakage_check(spec, bars, sample=sample)

    v = LabelValidation(verdict=VERDICT_VALID, base_rate=round(base_rate, 5),
                        n_events=len(runs), n_firings=firings, max_run=max_run,
                        leak_checked=checked, leak_failures=failures,
                        responds_to_inputs=responds)

    # ORDER MATTERS: leakage is fatal and must not be masked by a base-rate complaint.
    if failures:
        v.verdict = VERDICT_LEAKING
        v.notes.append(f"label[t] changed when bars after t+{spec.known_at_lag} were mutated at "
                       f"{failures}/{checked} sampled points -- it reads the future it claims to "
                       "predate; fix the construction or raise known_at_lag with a reason")
        return v
    if not responds:
        v.verdict = VERDICT_INERT
        v.notes.append("the label never fires and never changes under a drastic input mutation -- "
                       "it is not measuring anything (missing input column, or a threshold no real "
                       "data reaches)")
        return v
    if base_rate < MIN_BASE_RATE:
        v.verdict = VERDICT_RARE
        v.notes.append(f"fires {base_rate:.4%} of bars (<{MIN_BASE_RATE:.1%}) -- too rare to carry "
                       "power at any horizon; loosen the threshold or accept it is untestable")
    elif base_rate > MAX_BASE_RATE:
        v.verdict = VERDICT_COMMON
        v.notes.append(f"fires {base_rate:.1%} of bars (>{MAX_BASE_RATE:.0%}) -- this is a STATE, "
                       "not an event. Event-study machinery assumes rarity; use it as a regime "
                       "variable or tighten it")
    elif firings and max_run > MAX_RUN_FRACTION * firings:
        v.verdict = VERDICT_BLOB
        v.notes.append(f"{max_run} of {firings} firings are one contiguous run -- that is a PERIOD "
                       "flag (one blob = 'that year'), not a repeatable event, and n_events is "
                       "effectively 1 however many bars it covers")
    return v


# ------------------------------------------------------------------ the default catalogue

def default_specs(inputs: Sequence[str] = ()) -> list[LabelSpec]:
    """The four families the queue names, at their default parameters, with lineage attached."""
    src = tuple(inputs)
    return [
        LabelSpec("liquidity_stress", "liquidity_stress",
                  {"atr_win": 20, "range_mult": 2.0, "vol_q": 0.9, "vol_win": 60},
                  src, 0,
                  "range blowout confirmed by unusual volume: a big move that needed unusual "
                  "volume to clear means depth was thin, which a clean repricing does not"),
        LabelSpec("forced_deleveraging", "forced_deleveraging",
                  {"ret_q": 0.05, "win": 60, "oi_drop": 0.02}, src, 0,
                  "adverse move with OI FALLING -- existing positions removed, not new shorts "
                  "opened; the distinction is invisible without open interest"),
        LabelSpec("accumulation_window", "accumulation_window",
                  {"win": 20, "vol_q": 0.3, "drift_max": 0.02, "oi_rise": 0.05}, src, 0,
                  "compressed vol + flat price + OI building: size being taken without repricing"),
        LabelSpec("regime_transition", "regime_transition",
                  {"win": 20, "ratio": 1.8, "confirm": float(REGIME_CONFIRM_BARS)},
                  src, REGIME_CONFIRM_BARS,
                  "realised-vol step that HOLDS; persistence is what distinguishes a regime turn "
                  "from a loud bar, and it can only be observed after the fact -- hence the lag"),
    ]


def build_catalogue(bars: pd.DataFrame, specs: Sequence[LabelSpec] | None = None,
                    inputs: Sequence[str] = ()) -> list[dict[str, Any]]:
    """Generate + validate every spec, returning one research-asset record each."""
    out = []
    for spec in (specs if specs is not None else default_specs(inputs)):
        v = validate(spec, bars)
        out.append({
            "id": spec.id, "version": spec.version, "qualified_id": spec.qualified_id,
            "family": spec.family, "params": dict(spec.params),
            "known_at_lag": spec.known_at_lag, "inputs": list(spec.inputs),
            "rationale": spec.rationale, "validation": asdict(v), "usable": v.usable,
        })
    return out
