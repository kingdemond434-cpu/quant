"""Q6 -- THE CAUSAL LAB: every edge here is a TEST ON POINT-IN-TIME DATA, and it carries its class.

THE PRINCIPAL, 2026-09-16: a formal causal discovery lab on point-in-time data, with EDGE CLASSES.

WHY A CLASS AND NOT A SCORE. `causal_discovery.py` runs the PC skeleton and says honestly that a
chain and a common cause leave the same footprint; `world_causal_graph.py` measures lead-lag edges
and charges them for multiplicity. Neither answers what an allocator asks first: HOW MUCH WEIGHT
DOES THIS ARROW CARRY? A correlation that survives FDR, one with an economic mechanism behind it,
and one confirmed by a natural experiment are three different objects, and flattening them into a
single number is how a story becomes a position. So every edge is stamped, in ascending strength:

    OBSERVATIONAL          the partial correlation survives Benjamini-Hochberg at q=0.05 with Y's
                           own lags and every other variable's lag-1 conditioned out -- a
                           dependence the rest of the panel does not explain. Nothing more.
    PLAUSIBLE_MECHANISM    observational AND `mechanism_ontology` names a mechanism connecting the
                           two node KINDS. The ontology is open; an unregistered pair is not
                           promoted for sounding sensible.
    INTERVENTION_SUPPORTED observational AND a natural experiment agrees: around the source axis's
                           release days, `natural_experiment.difference_in_differences` puts the
                           responder's reaction against a control leg of untreated peers and the
                           effect's t clears 2. The only class with an exogenous shock behind it,
                           and only an edge OUT OF A RELEASE SERIES can reach it.

THREE METHODS ON A PIT-ALIGNED DAILY PANEL. (1) PCMCI-style lagged discovery over l=1..3 with ONE
FDR charge across every test run. (2) A NOTEARS-lite contemporaneous DAG -- gradient descent on a
linear SEM with the acyclicity penalty h(W)=tr(e^(W.W))-d and an L1 term, thresholded at 0.05.
(3) Economic restrictions applied BEFORE anything is tested: no market series points INTO a release
or axis series at lag 0 (releases are exogenous to the tape), no future lags, and COT positioning
enters only at lag >= 1 because it is published four days after it is true. Chains of classed edges
are reported AT THEIR WEAKEST LINK -- macro -> rates -> USD -> gold is one claim, exactly as strong
as the flimsiest arrow in it. And the rule: an LLM never invents an edge. Every row in the artifact
is a test on PIT data with its class attached, or it is not here.

    python desks/mt5/research/causal_lab.py [--dry-run] [--symbols EURUSD XAUUSD ...] [--days 500]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI, AXES = DESK / "data" / "universe", DESK / "data" / "axes"
OUT = DESK / "reports" / "CAUSAL_LAB.json"

#: The default panel. Small on purpose: d ~ 20 keeps the DAG objective to a few seconds and the FDR
#: denominator honest. US500 stays in the list though this box has no US500 parquet -- an absent
#: symbol is COUNTED as unmeasured, never quietly swapped for a neighbour.
DEFAULT_SYMBOLS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "XAUUSD", "XAGUSD", "XTIUSD", "US500", "NAS100", "GER40", "JPN225",
)
DAYS, MAX_LAG, FDR_Q, DAG_THRESHOLD = 500, 3, 0.05, 0.05
#: Aligned days below which the conditioning set (3 own lags + d-1 lag-1 terms) eats the degrees of
#: freedom and every partial correlation is noise wearing a p-value.
MIN_DAYS, MAX_VARS, MAX_EDGES, MAX_CHAINS = 120, 24, 80, 40
#: Axis columns per source file. WITHOUT IT the panel fills with near-duplicates: the first real run
#: took seven BIS carry series that all share a USD leg, they crowded out every macro and
#: positioning axis, and all nine surviving edges were carry-on-carry accounting.
MAX_AXIS_PER_STEM = 3
#: |corr| against any market column, at lag 0 or 1, above which an "axis" is refused as a PRICE
#: rather than a state. MEASURED 2026-09-16: the ECB's EUR/USD reference fixing reads 0.49 against
#: EURUSD contemporaneously and 0.47 at one lag -- it IS the tape, stamped 14:15 CET, so the lag-1
#: half is the stale-fixing artifact, and it was this lab's top "discovery" (q<1e-4) until the
#: screen ran. Every genuine axis measured <= 0.31, so the bar separates them cleanly.
DUP_R = 0.40
#: DiD windows in trading days -- `natural_experiment`'s own floors: below them parallel trends has
#: no power and the post leg is a point rather than a mean.
DID_PRE, DID_POST, DID_T_BAR = 10, 3, 2.0
#: Release days an axis needs before its intervention test runs (event_study's MIN_EVENTS), and the
#: share of days above which the series is a STATE variable rather than a release calendar.
MIN_RELEASES, MAX_RELEASE_SHARE = 20, 0.40
MIN_REGIME_N, VOL_WINDOW = 40, 20

MARKET_KINDS = ("fx", "metal", "energy", "index")
AXIS_KINDS = ("rate", "positioning", "macro")
CLASS_RANK = {"OBSERVATIONAL": 0, "PLAUSIBLE_MECHANISM": 1, "INTERVENTION_SUPPORTED": 2}
RULE = "an LLM never invents an edge; every edge here is a test on PIT data with its class"

_METALS = {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD"}
_ENERGY = {"XTIUSD", "XBRUSD", "XNGUSD"}
_INDEX = {"US500", "US30", "US2000", "NAS100", "GER40", "UK100", "FRA40", "JPN225", "HK50",
          "AUS200", "CHINAH"}

#: Desk mechanisms for the MT5 kinds, registered onto the OPEN ontology at runtime as
#: (id, licensed kind pairs, economic rationale, falsifier). `register` refuses any of them with no
#: falsifier, which is the whole reason this routes through the ontology instead of a dict here.
_MECHANISMS: tuple[tuple[str, tuple[tuple[str, str], ...], str, str], ...] = (
    ("CARRY_DIFFERENTIAL", (("rate", "fx"),),
     "a rate differential is the price of holding one currency against the other, paid daily",
     "the currency does not move with the differential once the dollar cycle is conditioned out"),
    ("REAL_RATE_OPPORTUNITY_COST", (("rate", "metal"),),
     "a metal pays no coupon, so the yield forgone to hold it IS its cost and rates set that cost",
     "the metal does not respond at any horizon the opportunity cost could act over"),
    ("DISCOUNT_RATE_REPRICING", (("rate", "index"), ("rate", "energy")),
     "an index is a claim on a cash-flow stream and a rate move changes the discount on it",
     "the level is unrelated to the discount rate with earnings expectations held fixed"),
    ("DOLLAR_NUMERAIRE", (("fx", "metal"), ("fx", "energy")),
     "metal and barrel are quoted in dollars, so a dollar move reprices the quote, not the thing",
     "the commodity's non-USD price moves one-for-one with the USD one, leaving no channel"),
    ("RISK_APPETITE_ROTATION", (("index", "fx"), ("fx", "index")),
     "funding currencies and the equity cycle are two readings of one appetite for risk, and one "
     "book adds or cuts both legs on the same day",
     "the pair's response to equity drawdowns is indistinguishable from its unconditional drift"),
    ("MACRO_SURPRISE_REPRICING",
     (("macro", "fx"), ("macro", "rate"), ("macro", "index"), ("macro", "metal"),
      ("macro", "energy")),
     "a release is new information at a known instant; what moves is what it repriced",
     "the response is present on non-release days too, which makes it drift rather than news"),
    ("POSITIONING_CROWDING",
     (("positioning", "fx"), ("positioning", "metal"), ("positioning", "energy"),
      ("positioning", "index")),
     "a crowded book is an inventory of people who must eventually trade the other way, and that "
     "forced actor shows in the COT before it shows in the tape",
     "extreme net positioning has no forward return spread once trend is controlled for"),
    ("INPUT_COST_PASSTHROUGH", (("energy", "index"),),
     "energy is an input cost to the earnings an index capitalises; margins move before guidance",
     "index earnings are insensitive to the energy move at any horizon the cost could act on"),
)
#: Same-kind market pairs licensed as CROSS_VENUE_PRICE_DISCOVERY (already in the core ontology):
#: two grades of one barrel, two monetary metals, two indices on one session. ("fx","fx") is
#: DELIBERATELY ABSENT -- two crosses share a leg by construction, so a mechanism there is an
#: accounting identity dressed as an economic claim, and the class would stop meaning anything.
_SAME_KIND = (("metal", "metal"), ("energy", "energy"), ("index", "index"))

RESTRICTION_TEXT = {
    "NO_FUTURE_LAGS": "a cause cannot be dated after its effect; a negative lag is never formed",
    "NO_EDGE_INTO_RELEASE_AT_LAG0": ("a release or policy axis is exogenous to the tape on its own "
                                     "day -- an arrow from a market series into it at lag 0 is the "
                                     "tape explaining the calendar"),
    "POSITIONING_LAG_GE_1": ("COT is published four days after the Tuesday it describes, so a "
                             "contemporaneous positioning arrow is look-ahead in a causal hat"),
}


@dataclass
class Panel:
    """A PIT-aligned daily panel. `x` is raw (log returns for markets, first differences for axes);
    `releases[name]` marks the days an axis changed, which IS its release calendar once the level
    has been as-of forward-filled onto the panel's own trading days."""

    names: list[str]
    kinds: dict[str, str]
    x: np.ndarray
    dates: list[str]
    releases: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def z(self) -> np.ndarray:
        sd = self.x.std(axis=0, ddof=1)
        return (self.x - self.x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)


# ------------------------------------------------------------------ ontology, kinds, restrictions

def kind_of(name: str) -> str:
    """fx / metal / energy / index for a market series, rate / positioning / macro for an axis."""
    if name.startswith(("bis.", "cot.", "ecb.", "fred.")):
        head, _, tail = name.partition(".")
        if head in ("cot", "bis"):
            return "positioning" if head == "cot" else "rate"
        low = tail.lower()
        return "rate" if any(k in low for k in ("aaa", "yield", "dgs", "t10y", "rate")) else "macro"
    if name in _METALS:
        return "metal"
    if name in _ENERGY:
        return "energy"
    return "index" if name in _INDEX else "fx"


def build_ontology() -> tuple[dict[str, Any], dict[tuple[str, str], str]]:
    """(ontology, kind-pair -> mechanism_id). An unavailable library costs the PLAUSIBLE_MECHANISM
    class and is REPORTED -- never silently downgraded to a bare observational graph."""
    pair_map: dict[tuple[str, str], str] = {}
    try:
        from libs.research.mechanism_ontology import CORE_MECHANISMS, Mechanism, register
    except ImportError:
        return {}, pair_map
    ont: dict[str, Any] = dict(CORE_MECHANISMS)
    for mid, pairs, why, falsifier in _MECHANISMS:
        ont = register(ont, Mechanism(
            mechanism_id=mid, economic_rationale=why,
            expected_actors="the participant the rationale names, acting under its constraint",
            observables=("return", "level", "carry_differential", "net_pct_oi"),
            valid_transforms=("LEVEL", "DIFFERENCE", "ZSCORE", "SURPRISE", "PERSISTENCE"),
            valid_horizons=("DAILY", "MULTI_DAY", "WEEKLY"), falsifiers=(falsifier,)))
        pair_map.update(dict.fromkeys(pairs, mid))
    pair_map.update(dict.fromkeys(_SAME_KIND, "CROSS_VENUE_PRICE_DISCOVERY"))
    return ont, pair_map


def forbidden(src_kind: str, dst_kind: str, lag: int) -> str | None:
    """The economic restrictions, applied BEFORE a test is run. A refusal returns its rule name."""
    if lag < 0:
        return "NO_FUTURE_LAGS"
    if lag == 0 and dst_kind in AXIS_KINDS and src_kind in MARKET_KINDS:
        return "NO_EDGE_INTO_RELEASE_AT_LAG0"
    if lag == 0 and src_kind == "positioning":
        return "POSITIONING_LAG_GE_1"
    return None


# ------------------------------------------------------------------ statistics

try:  # the Fisher-z oracle already lives next door; reuse it rather than fork it
    from causal_discovery import _fisher_p as fisher_p  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - only where the sibling module is absent
    import math

    def fisher_p(r: float, n: int, n_cond: int) -> float:
        dof = n - n_cond - 3
        if dof <= 0:
            return 1.0
        if abs(r) >= 0.999999:
            return 0.0
        z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(dof)
        return float(math.erfc(abs(z) / math.sqrt(2.0)))


def bh_fdr(p: np.ndarray, q: float) -> tuple[np.ndarray, np.ndarray]:
    """Benjamini-Hochberg over ALL tests run. Returns (rejected, q-values)."""
    m = int(p.size)
    if m == 0:
        return np.zeros(0, dtype=bool), np.zeros(0)
    order = np.argsort(p, kind="stable")
    ranked = p[order]
    qs = np.minimum.accumulate((m / np.arange(m, 0, -1, dtype="float64")) * ranked[::-1])[::-1]
    qvals = np.empty(m, dtype="float64")
    qvals[order] = np.clip(qs, 0.0, 1.0)
    below = ranked <= (np.arange(1, m + 1, dtype="float64") / m) * q
    k = int(np.nonzero(below)[0][-1]) + 1 if below.any() else 0
    rej = np.zeros(m, dtype=bool)
    rej[order[:k]] = True
    return rej, qvals


def _resid(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Residual of y on z with an intercept. The residualisation IS the conditioning."""
    a = np.column_stack([np.ones(len(y)), z]) if z.size else np.ones((len(y), 1))
    beta, *_ = np.linalg.lstsq(a, y, rcond=None)
    return y - a @ beta


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    sa, sb = float(a.std()), float(b.std())
    if sa <= 1e-12 or sb <= 1e-12 or len(a) < 3:
        return 0.0
    return float(np.clip(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb), -0.999999, 0.999999))


def _roll_std(y: np.ndarray, w: int = VOL_WINDOW) -> np.ndarray:
    out = np.full(len(y), np.nan)
    if len(y) < w:
        return out
    c1, c2 = np.cumsum(np.insert(y, 0, 0.0)), np.cumsum(np.insert(y * y, 0, 0.0))
    s1, s2 = c1[w:] - c1[:-w], c2[w:] - c2[:-w]
    out[w - 1:] = np.sqrt(np.maximum(0.0, (s2 - s1 * s1 / w) / max(1, w - 1)))
    return out


def _epoch(day: str) -> float:
    return datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp()


# ------------------------------------------------------------------ the PIT panel

def _daily_returns(path: Path) -> tuple[list[str], np.ndarray] | None:
    import pandas as pd
    try:
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, KeyError):
        return None
    c = df["close"].astype(float)
    c = c[c > 0]
    if len(c) < 50:
        return None
    last, count = c.resample("1D").last(), c.resample("1D").count()
    # A calendar day with no bar is a CLOSED market, not a zero return; keeping it would
    # manufacture weekend observations the tape never had (L1.68).
    r = np.log(last[count.to_numpy() > 0].dropna()).diff().dropna()
    return [str(d.date()) for d in r.index], r.to_numpy(dtype="float64")


def _axis_series(axes_dir: Path, symbols: set[str]) -> tuple[dict[str, list[tuple[str, float]]],
                                                             list[dict[str, str]]]:
    """(name -> [(knowable_at, level)]) and the unmeasured rows. LEVELS ONLY: the difference and
    the release calendar are taken after alignment to the panel's own trading days."""
    out: dict[str, list[tuple[str, float]]] = {}
    unmeasured: list[dict[str, str]] = []
    for stem in ("bis", "cot", "ecb", "fred"):
        try:
            doc = json.loads((axes_dir / f"{stem}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            unmeasured.append({"what": f"axis {stem}", "why": f"unreadable ({type(exc).__name__})"})
            continue
        rows, series = doc.get("rows"), doc.get("series")
        if isinstance(rows, list) and rows:
            fld = "carry_differential" if stem == "bis" else "net_pct_oi"
            for row in rows:
                sym, day = str(row.get("symbol") or ""), str(row.get("knowable_at") or "")
                # A "1999-01" month stamp cannot be aligned to a trading day: dropped, not guessed.
                if sym not in symbols or fld not in row or len(day) != 10:
                    continue
                try:
                    out.setdefault(f"{stem}.{sym}", []).append((day, float(row[fld])))
                except (TypeError, ValueError):
                    continue
        elif isinstance(series, dict) and series:
            for sid, blob in series.items():
                vals = [(str(q.get("d")), float(q.get("v"))) for q in (blob or {}).get("points", [])
                        if isinstance(q, dict) and q.get("v") is not None]
                if vals:
                    out[f"{stem}.{sid}"] = vals
        else:
            unmeasured.append({"what": f"axis {stem}", "why": (
                f"no rows or series in the file (n_failed={doc.get('n_failed', '?')}); it "
                "contributes nothing and is counted rather than assumed benign")})
    return {k: sorted(set(v)) for k, v in out.items()}, unmeasured


def load_panel(symbols: list[str], days: int, *, uni: Path = UNI,
               axes_dir: Path = AXES) -> tuple[Panel | None, list[dict[str, str]]]:
    """Market log returns on common trading days, plus each axis as-of forward-filled onto those
    same days and first-differenced. Nothing sees an axis value before its knowable_at stamp."""
    unmeasured: list[dict[str, str]] = []
    try:
        import pandas as pd
    except ImportError as exc:
        return None, [{"what": "panel", "why": f"pandas unavailable ({exc})"}]
    cols: dict[str, Any] = {}
    for sym in symbols:
        path = uni / f"{sym}_H1.parquet"
        if not path.exists():
            unmeasured.append({"what": sym, "why": f"no {path.name} in the universe -- SKIPPED "
                                                   "and counted, never substituted"})
            continue
        got = _daily_returns(path)
        if got is None:
            unmeasured.append({"what": sym, "why": "H1 parquet unreadable or shorter than 50 bars"})
            continue
        cols[sym] = pd.Series(got[1], index=pd.to_datetime(got[0]))
    if len(cols) < 3:
        return None, [*unmeasured, {"what": "panel", "why": (
            f"{len(cols)} market series usable; a conditional independence test needs a third "
            "variable to condition on")}]
    frame = pd.DataFrame(cols).dropna().tail(int(days))
    if len(frame) < MIN_DAYS:
        return None, [*unmeasured, {"what": "panel", "why": (
            f"{len(frame)} common trading days < {MIN_DAYS}; the conditioning set would eat the "
            "degrees of freedom and every p-value would be noise")}]
    axis_raw, axis_unmeasured = _axis_series(axes_dir, set(symbols))
    unmeasured.extend(axis_unmeasured)
    # Order axis candidates by (source file, the requested symbol's own rank) and admit at most
    # MAX_AXIS_PER_STEM of each, so one family cannot fill the panel with its near-duplicates.
    mkt = {sym: frame[sym].to_numpy(dtype="float64") for sym in cols}
    rank = {s: k for k, s in enumerate(symbols)}
    ordered = sorted(axis_raw, key=lambda nm: (nm.split(".")[0],
                                               rank.get(nm.split(".", 1)[1], len(rank)), nm))
    taken: dict[str, int] = {}
    releases: dict[str, np.ndarray] = {}
    for name in ordered:
        stem = name.split(".")[0]
        full = len(cols) + len(releases) >= MAX_VARS
        if full or taken.get(stem, 0) >= MAX_AXIS_PER_STEM:
            unmeasured.append({"what": name, "why": (
                f"MAX_VARS={MAX_VARS} reached" if full else
                f"{MAX_AXIS_PER_STEM} {stem} axis series already admitted")})
            continue
        taken[stem] = taken.get(stem, 0) + 1
        ser = pd.Series([v for _, v in axis_raw[name]],
                        index=pd.to_datetime([d for d, _ in axis_raw[name]]))
        ser = ser[~ser.index.duplicated(keep="last")].sort_index()
        aligned = ser.reindex(frame.index.union(ser.index)).ffill().reindex(frame.index)
        diff = aligned.diff().fillna(0.0).to_numpy(dtype="float64")
        if float(np.std(diff)) <= 1e-12:
            unmeasured.append({"what": name, "why": "the axis never changed inside the window"})
            continue
        dup = max(((abs(_corr(diff[lag:], arr[:len(arr) - lag] if lag else arr)), sym, lag)
                   for sym, arr in mkt.items() for lag in (0, 1)), default=(0.0, "", 0))
        if dup[0] >= DUP_R:
            unmeasured.append({"what": name, "why": (
                f"|r|={dup[0]:.2f} against {dup[1]} at lag {dup[2]} -- a PRICE of something already"
                " in the panel, not an axis, and a lagged edge out of it is a stale-fixing artifact"
                " rather than a cause")})
            continue
        frame[name] = diff
        releases[name] = diff != 0.0
    names = [str(c) for c in frame.columns]
    return Panel(names=names, kinds={n: kind_of(n) for n in names},
                 x=frame.to_numpy(dtype="float64"),
                 dates=[str(d.date()) for d in frame.index], releases=releases), unmeasured


# ------------------------------------------------------------------ (1) PCMCI-style lagged tests

def discover_lagged(panel: Panel, *, max_lag: int = MAX_LAG, q: float = FDR_Q) -> dict[str, Any]:
    """For every ordered pair and lag l=1..L: the partial correlation of Y_t on X_{t-l} given Y's
    own three lags and every other variable's lag-1 value, with ONE BH charge over every test run.
    A restricted pair is never tested, so it never enters the multiplicity denominator either."""
    z = panel.z
    n, d = z.shape
    names, kinds = panel.names, panel.kinds
    m = n - max_lag
    lagged = [z[max_lag - lag: n - lag, :] for lag in range(max_lag + 1)]  # lagged[0] is t itself
    tests: list[dict[str, Any]] = []
    blocked: dict[str, int] = {}
    for j in range(d):
        own = np.column_stack([lagged[k][:, j] for k in range(1, max_lag + 1)])
        y = lagged[0][:, j]
        for i in range(d):
            if i == j:
                continue
            for lag in range(1, max_lag + 1):
                rule = forbidden(kinds[names[i]], kinds[names[j]], lag)
                if rule:
                    blocked[rule] = blocked.get(rule, 0) + 1
                    continue
                others = [v for v in range(d) if v != j and not (v == i and lag == 1)]
                cond = np.column_stack([own, *[lagged[1][:, v] for v in others]])
                ry, rx = _resid(y, cond), _resid(lagged[lag][:, i], cond)
                r, denom = _corr(rx, ry), float(rx @ rx)
                tests.append({
                    "from": names[i], "to": names[j], "from_kind": kinds[names[i]],
                    "to_kind": kinds[names[j]], "lag": lag, "r": round(r, 5),
                    "coef": round(float(rx @ ry) / denom, 5) if denom > 1e-12 else 0.0,
                    "p": fisher_p(r, m, cond.shape[1]), "n": m, "i": i, "j": j})
    if not tests:
        return {"edges": [], "n_tests": 0, "blocked": blocked}
    rej, qv = bh_fdr(np.array([t["p"] for t in tests], dtype="float64"), q)
    for t, rj, qq in zip(tests, rej, qv, strict=True):
        t["p"], t["q"], t["rejected"] = round(float(t["p"]), 8), round(float(qq), 6), bool(rj)
    edges = sorted((t for t in tests if t["rejected"]), key=lambda t: (t["q"], -abs(float(t["r"]))))
    return {"edges": edges, "n_tests": len(tests), "blocked": blocked}


# ------------------------------------------------------------------ (2) NOTEARS-lite

def _expm(a: np.ndarray) -> np.ndarray:
    """Matrix exponential by scaling-and-squaring with a Taylor series. numpy only, by mandate."""
    norm = float(np.abs(a).sum(axis=1).max()) if a.size else 0.0
    s = min(max(int(np.ceil(np.log2(norm))) + 1 if norm > 1.0 else 0, 0), 30)
    b = a / (2.0**s)
    e = term = np.eye(a.shape[0])
    for k in range(1, 18):
        term = term @ b / k
        e = e + term
    for _ in range(s):
        e = e @ e
    return e


def notears_lite(panel: Panel, *, lam: float = 0.25, threshold: float = DAG_THRESHOLD,
                 rhos: tuple[float, ...] = (0.0, 1.0, 10.0, 100.0, 1e3, 1e4), inner: int = 300,
                 lr: float = 0.05) -> dict[str, Any]:
    """Contemporaneous DAG on a linear SEM X = XW + e, by gradient descent (Adam) on

        0.5 * sum_j log(||X_j - XW_j||^2 / n) - log|det(I - W)| + lam|W|_1 + rho/2 * h(W)^2,
        h(W) = tr(e^(W.W)) - d, rho ramped 0 -> 1e4, W thresholded at 0.05.

    THE SCORE IS THE LIKELIHOOD, NOT THE RESIDUAL SUM, AND THE DIFFERENCE IS THE WHOLE RESULT.
    Plain least squares on STANDARDISED columns reversed EVERY planted arrow in the fixture: with
    each variance pinned at 1 the cheapest way to shrink ||X - XW||^2 is to make a SINK of whatever
    can be explained, so the fit ran the causal order backwards and scored better doing it. The
    per-column log-variance score with the log-det Jacobian is scale-free and puts the optimum back
    on the truth -- measured 2026-09-16 on six nodes with two colliders: 9 seeds, 9 correct collider
    orientations, no planted edge missed. What it still cannot do is orient an edge no collider
    touches: that is Markov equivalence, a fact about observational data rather than a defect here.
    The restrictions are a MASK, so a forbidden arrow is never a free parameter."""
    x = panel.z
    n, d = x.shape
    names, kinds = panel.names, panel.kinds
    eye = np.eye(d)
    mask = np.ones((d, d))
    np.fill_diagonal(mask, 0.0)
    blocked: dict[str, int] = {}
    for i in range(d):
        for j in range(d):
            rule = forbidden(kinds[names[i]], kinds[names[j]], 0) if i != j else None
            if rule:
                mask[i, j] = 0.0
                blocked[rule] = blocked.get(rule, 0) + 1
    w, m1, m2, t = np.zeros((d, d)), np.zeros((d, d)), np.zeros((d, d)), 0
    for rho in rhos:
        for _ in range(inner):
            t += 1
            r = x - x @ w
            s = np.maximum((r * r).sum(axis=0) / n, 1e-12)
            ew = _expm(w * w)
            h = float(np.trace(ew) - d)
            try:
                jac = np.linalg.inv(eye - w).T
            except np.linalg.LinAlgError:  # pragma: no cover - W stays far from singular here
                jac = np.zeros((d, d))
            grad = -(x.T @ r) / (n * s) + jac + rho * h * ew.T * 2.0 * w
            m1, m2 = 0.9 * m1 + 0.1 * grad, 0.999 * m2 + 0.001 * grad * grad
            w = w - lr * (m1 / (1 - 0.9**t)) / (np.sqrt(m2 / (1 - 0.999**t)) + 1e-8)
            w = np.sign(w) * np.maximum(np.abs(w) - lr * lam, 0.0) * mask
    h_raw = float(np.trace(_expm(w * w)) - d)
    w = np.where(np.abs(w) >= threshold, w, 0.0) * mask
    floor = 1.0 / np.sqrt(n)
    edges = [{"from": names[i], "to": names[j], "from_kind": kinds[names[i]],
              "to_kind": kinds[names[j]], "weight": round(float(w[i, j]), 4)}
             for i in range(d) for j in range(d) if w[i, j] != 0.0]
    edges.sort(key=lambda e: -abs(float(e["weight"])))
    return {"edges": edges[:MAX_EDGES], "n_edges": len(edges), "threshold": threshold,
            "acyclicity_h": round(h_raw, 9), "iterations": t, "n_vars": d, "blocked": blocked,
            "noise_floor": round(float(floor), 4),
            "n_above_2x_noise_floor": sum(1 for e in edges if abs(float(e["weight"])) >= 2 * floor),
            "note": ("a contemporaneous DAG on daily closes is the WEAKEST object in this file: a "
                     "same-day arrow between two markets is as much a shared shock as a cause, "
                     "only the mask keeps the calendar out of the tape's reach, and a coefficient's"
                     f" own sampling noise at n={n} is {floor:.3f} against a 0.05 threshold -- so "
                     "read the weights above 2x the noise floor and nothing below it")}


# ------------------------------------------------------------------ (3) regimes and interventions

def regime_strengths(panel: Panel, i: int, j: int, lag: int) -> dict[str, Any]:
    """Edge strength inside each realised-vol tercile of the RESPONDER. The lagged correlation, not
    the partial one: a third of the sample cannot carry the conditioning set, and pretending it can
    is how a regime table becomes decoration."""
    z = panel.z
    y, xs = z[lag:, j], z[:-lag, i]
    vol = _roll_std(panel.x[:, j])[lag:]
    ok = np.isfinite(vol)
    if int(ok.sum()) < 3 * MIN_REGIME_N:
        return {"status": "UNMEASURED",
                "why": f"fewer than {3 * MIN_REGIME_N} days carry a {VOL_WINDOW}-day realised vol"}
    lo, hi = (float(v) for v in np.quantile(vol[ok], [1 / 3, 2 / 3]))
    out: dict[str, Any] = {"status": "OK", "cuts": [round(lo, 6), round(hi, 6)]}
    rs: list[float] = []
    for label, sel in (("low", ok & (vol <= lo)), ("mid", ok & (vol > lo) & (vol <= hi)),
                       ("high", ok & (vol > hi))):
        k = int(sel.sum())
        r = _corr(xs[sel], y[sel]) if k >= MIN_REGIME_N else 0.0
        out[label] = {"r": round(r, 5), "n": k,
                      "status": "OK" if k >= MIN_REGIME_N else "UNMEASURED"}
        if k >= MIN_REGIME_N:
            rs.append(r)
    out["sign_stable"] = bool(rs) and all(v != 0.0 and np.sign(v) == np.sign(rs[0]) for v in rs)
    return out


def intervention_test(panel: Panel, axis: str, responder: str, lag: int,
                      coef_sign: float) -> dict[str, Any]:
    """The natural experiment for an edge out of a release axis: the responder's move over the
    edge's own lag window after each release, differenced against its untreated peers over the same
    days, with the shock's sign and the edge's pre-registered direction folded in."""
    if axis not in panel.releases:
        return {"status": "UNMEASURED", "why": "source is not a release series"}
    if panel.kinds.get(responder) not in MARKET_KINDS:
        # Measured: without this guard the top class went to cot.USDJPY -> bis.GBPUSD, two step
        # series sharing a publication rhythm, whose treated leg is mostly zeros.
        return {"status": "UNMEASURED", "why": (
            f"{responder} is not a market series; a natural experiment asks whether the release "
            "moved a PRICE, and one calendar moving another is not an intervention")}
    rel = panel.releases[axis]
    share = float(rel.mean())
    if share > MAX_RELEASE_SHARE:
        return {"status": "UNMEASURED", "why": (
            f"the axis moved on {share:.0%} of days -- that is a STATE variable, not a release "
            "calendar, and there is no untreated period to compare against")}
    jr = panel.names.index(responder)
    peers = [k for k, nm in enumerate(panel.names) if k != jr and panel.kinds[nm] in MARKET_KINDS]
    if len(peers) < 3:
        return {"status": "UNMEASURED", "why": "fewer than three untreated market peers"}
    y, ax, n = panel.x[:, jr], panel.x[:, panel.names.index(axis)], len(panel.dates)
    days = [t for t in np.nonzero(rel)[0]
            if t - DID_PRE >= 0 and t + lag + DID_POST <= n and ax[t] != 0.0]
    if len(days) < MIN_RELEASES:
        return {"status": "UNMEASURED", "why": (
            f"{len(days)} usable release day(s) < {MIN_RELEASES}; an event study below ~20 "
            "observations is a story, not evidence")}
    peer = panel.x[:, peers].mean(axis=1)
    units, effects = [], []
    for t in days:
        # ORIENTATION IS A FUNCTION OF THE TREATMENT, NEVER OF THE OUTCOME: the day's shock sign
        # times the sign the observational edge already claimed, applied to BOTH legs so the
        # difference stays a difference.
        sgn = float(np.sign(ax[t]) * np.sign(coef_sign or 1.0))
        pre, post = slice(t - DID_PRE, t), slice(t + lag, t + lag + DID_POST)
        tp, tq = (sgn * y[pre]).tolist(), (sgn * y[post]).tolist()
        cp, cq = (sgn * peer[pre]).tolist(), (sgn * peer[post]).tolist()
        effects.append((float(np.mean(tq)) - float(np.mean(tp)))
                       - (float(np.mean(cq)) - float(np.mean(cp))))
        units.append({"unit_id": f"{axis}@{panel.dates[t]}", "event_ts": _epoch(panel.dates[t]),
                      "treated_pre": tp, "treated_post": tq, "control_pre": cp, "control_post": cq,
                      "cohort_key": responder})
    try:
        from libs.research.natural_experiment import TreatedUnit, difference_in_differences
    except ImportError:  # pragma: no cover - the library is a hard dependency of the desk
        arr = np.array(effects)
        sd = float(arr.std(ddof=1))
        return {"status": "OK", "engine": "internal", "n_units": len(arr), "identified": False,
                "effect": round(float(arr.mean()), 6), "verdict": "cross-sectional t only",
                "t": round(float(arr.mean() / (sd / np.sqrt(len(arr)))), 3) if sd > 1e-12 else 0.0}
    did = difference_in_differences(
        [TreatedUnit(**u) for u in units], n_control_pool=len(peers), direction="increase",
        exogeneity_note=(f"{axis} changes on a published calendar the responder does not set; the "
                         "release date is exogenous to that day's tape"),
        post_window_s=DID_POST * 86_400.0)
    return {"status": "OK", "engine": "natural_experiment", "n_units": did.n_treated,
            "identified": bool(did.identified), "effect": round(float(did.effect), 6),
            "t": round(float(did.inference.t_stat) if did.inference is not None else 0.0, 3),
            "parallel_trends_t": did.parallel_trends_t, "placebo_t": did.placebo_t,
            "study_passed": bool(did.passed), "verdict": str(did.verdict)[:300]}


# ------------------------------------------------------------------ classes and chains

def classify_edges(panel: Panel, edges: list[dict[str, Any]],
                   pair_map: dict[tuple[str, str], str]) -> dict[str, int]:
    """Stamp every surviving edge with its class. The ladder is strict: nothing is promoted for
    sounding plausible, and only an edge out of a release series can reach the top rung."""
    counts = dict.fromkeys(CLASS_RANK, 0)
    for e in edges:
        e["klass"] = "OBSERVATIONAL"
        e["mechanism"] = pair_map.get((str(e["from_kind"]), str(e["to_kind"])), "")
        if e["mechanism"]:
            e["klass"] = "PLAUSIBLE_MECHANISM"
        e["by_regime"] = regime_strengths(panel, int(e["i"]), int(e["j"]), int(e["lag"]))
        if str(e["from"]) in panel.releases:
            did = intervention_test(panel, str(e["from"]), str(e["to"]), int(e["lag"]),
                                    float(e["coef"]))
            e["intervention"] = did
            if did.get("status") == "OK" and float(did.get("t", 0.0)) > DID_T_BAR:
                e["klass"] = "INTERVENTION_SUPPORTED"
        counts[str(e["klass"])] += 1
    return counts


def find_chains(edges: list[dict[str, Any]], max_edges: int = 3) -> list[dict[str, Any]]:
    """Paths of 2 to `max_edges` classed edges, reported AT THEIR WEAKEST LINK -- a chain is one
    claim, and it is exactly as strong as the flimsiest arrow in it."""
    adj: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        adj.setdefault(str(e["from"]), []).append(e)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(path: list[dict[str, Any]], visited: set[str]) -> None:
        if len(path) >= 2:
            nodes = [str(path[0]["from"]), *[str(p["to"]) for p in path]]
            key = "->".join(nodes) + "|" + ",".join(str(p["lag"]) for p in path)
            if key not in seen:
                seen.add(key)
                weak = min(path, key=lambda p: CLASS_RANK[str(p["klass"])])
                out.append({
                    "nodes": nodes,
                    "kinds": [str(path[0]["from_kind"]), *[str(p["to_kind"]) for p in path]],
                    "lags": [int(p["lag"]) for p in path],
                    "total_lag": sum(int(p["lag"]) for p in path),
                    "klass": str(weak["klass"]),
                    "weakest_link": f"{weak['from']}->{weak['to']}",
                    "min_abs_r": round(min(abs(float(p["r"])) for p in path), 5),
                    "mechanisms": [str(p.get("mechanism") or "") for p in path]})
        if len(path) >= max_edges:
            return
        for nxt in adj.get(str(path[-1]["to"]), []):
            if str(nxt["to"]) not in visited:
                walk([*path, nxt], visited | {str(nxt["to"])})

    for e in edges:
        walk([e], {str(e["from"]), str(e["to"])})
    out.sort(key=lambda c: (-CLASS_RANK[str(c["klass"])], -len(c["nodes"]), -float(c["min_abs_r"])))
    return out[:MAX_CHAINS]


# ------------------------------------------------------------------ the artifact

def build(*, symbols: list[str] | None = None, days: int = DAYS, panel: Panel | None = None,
          pair_map: dict[tuple[str, str], str] | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    unmeasured: list[dict[str, str]] = []
    if panel is None:
        panel, unmeasured = load_panel(list(symbols or DEFAULT_SYMBOLS), days)
    if panel is None:
        return {"at": now, "status": "UNMEASURED", "n_nodes": 0, "n_tests": 0, "fdr_q": FDR_Q,
                "edges": [], "dag": {"edges": []}, "chains": [], "restrictions_applied": {},
                "unmeasured": unmeasured, "n_unmeasured": len(unmeasured), "rule": RULE,
                "why": "; ".join(u["why"] for u in unmeasured[-2:]) or "no panel"}
    ont: dict[str, Any] = {}
    if pair_map is None:
        ont, pair_map = build_ontology()
        if not pair_map:
            unmeasured.append({"what": "mechanism ontology", "why": (
                "libs.research.mechanism_ontology unavailable; PLAUSIBLE_MECHANISM cannot be "
                "awarded on this run and no edge is promoted in its place")})
    lagged = discover_lagged(panel)
    edges = lagged["edges"][:MAX_EDGES]
    counts = classify_edges(panel, edges, pair_map)
    dag = notears_lite(panel)
    chains = find_chains(edges)
    for e in edges:
        for k in ("i", "j", "rejected"):
            e.pop(k, None)
    blocked = dict(lagged["blocked"])
    for rule, k in dag["blocked"].items():
        blocked[rule] = blocked.get(rule, 0) + k
    unmeasured.extend({"what": f"intervention test on {name}", "why":
                       f"changes on {rel.mean():.0%} of days -- a state variable, not a release"}
                      for name, rel in panel.releases.items()
                      if float(rel.mean()) > MAX_RELEASE_SHARE)
    return {
        "at": now, "status": "OK", "days_requested": days, "n_days": len(panel.dates),
        "window": [panel.dates[0], panel.dates[-1]], "n_nodes": len(panel.names),
        "nodes": panel.names, "kinds": panel.kinds, "release_series": sorted(panel.releases),
        "n_tests": int(lagged["n_tests"]), "fdr_q": FDR_Q, "n_edges": len(edges),
        "class_counts": counts, "edges": edges, "dag": dag, "chains": chains,
        "restrictions_applied": {"counts": blocked,
                                 "rules": {k: RESTRICTION_TEXT[k] for k in sorted(blocked)}},
        "unmeasured": unmeasured, "n_unmeasured": len(unmeasured),
        "mechanisms_registered": sorted(m[0] for m in _MECHANISMS if m[0] in ont),
        "assumptions": {
            "pit": ("every axis is stamped at its knowable_at date, forward-filled as-of and "
                    "differenced on the panel's own trading days; nothing sees an axis value "
                    "before its stamp"),
            "linear_gaussian": ("partial correlation and the linear SEM are the right oracles only "
                                "for linear, jointly normal variables -- a non-linear dependence "
                                "reads here as independence"),
            "causal_sufficiency": ("FALSE, as always on this panel: the dollar cycle and the risk "
                                   "cycle are common causes of nearly every pair and neither is a "
                                   "node. An OBSERVATIONAL edge may be their shadow, which is "
                                   "exactly why the class ladder exists"),
        },
        "boundary": ("NOTHING HERE TRADES OR CERTIFIES. A classed edge is a structural hypothesis "
                     "and reaches the book the way everything else does -- through the gauntlet."),
        "rule": RULE,
    }


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only destination is legal on
    POSIX and raises WinError 5 here -- the way a VPS-tested fix once broke the box that trades."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")


def summary_lines(doc: dict[str, Any]) -> list[str]:
    """Ten lines, and the EDGE detail is what gives way when they run out: the rule is the last
    line a reader must not lose."""
    if doc.get("status") != "OK":
        return [f"causal lab: UNMEASURED -- {doc.get('why', 'no panel')}",
                f"  {doc.get('n_unmeasured', 0)} unmeasured row(s); nothing was tested",
                f"  rule: {doc['rule']}"]
    cc, blocked = doc["class_counts"], doc["restrictions_applied"]["counts"]
    head = [
        f"causal lab: OK   {doc['n_nodes']} node(s), {doc['n_days']} PIT day(s) "
        f"{doc['window'][0]}..{doc['window'][1]}",
        f"  lagged: {doc['n_tests']} test(s) l=1..{MAX_LAG}, BH q={doc['fdr_q']} -> "
        f"{doc['n_edges']} edge(s) survive",
        f"  classes: {cc['OBSERVATIONAL']} observational, {cc['PLAUSIBLE_MECHANISM']} with a "
        f"mechanism, {cc['INTERVENTION_SUPPORTED']} intervention-supported",
    ]
    tail = [
        f"  DAG (lag 0): {doc['dag']['n_edges']} edge(s) above {doc['dag']['threshold']}, "
        f"h={doc['dag']['acyclicity_h']:.2e} after {doc['dag']['iterations']} step(s)",
        f"  chains: {len(doc['chains'])} path(s) of 2-3 edges, each at its weakest link",
        "  restrictions: " + (", ".join(f"{k}={v}" for k, v in sorted(blocked.items())) or "none"),
        f"  unmeasured: {doc['n_unmeasured']} row(s) -- absence is a verdict, not a zero",
        f"  rule: {doc['rule']}",
    ]
    return head + [f"    {e['from']:>16} -> {e['to']:<9} lag {e['lag']}  r={float(e['r']):+.3f} "
                   f"q={float(e['q']):.4f}  {e['klass']}"
                   for e in doc["edges"][:max(0, 10 - len(head) - len(tail))]] + tail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="formal causal discovery on the PIT daily panel")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--symbols", nargs="+", default=None, help="panel symbols (default: the book)")
    ap.add_argument("--days", type=int, default=DAYS)
    a = ap.parse_args(argv)
    doc = build(symbols=a.symbols, days=max(1, int(a.days)))
    for line in summary_lines(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    _write_atomic(OUT, doc)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
