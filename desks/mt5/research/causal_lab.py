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

THE GLOBAL STREAMS (section 4, 2026-10-13). The same oracle, run over the non-Western and "ugly"
public streams the desk already lands -- every data/lake/series frame (alt_proxies incl. GDELT,
free stack, country packs, blog_social, nlp_events), raw landings, COT positioning, the forum text
store and the world dataset hunter -- each read at its OWN known-by stamp (anything unstamped is
excluded and counted). Surviving links become STATE-CONDITIONED cells ("when S is in regime R,
I does X") under `exogenous_conditioner` / `world_macro_state`, are refused when #377's style
classifier names a style the book already holds, are donated once through
`proposer_common.donate`, and every forum / local-language / axis stream is
LANDED as a lake series (`data/lake/series/cg_*.csv`, PIT envelope) for the collector and pack
cells; links and novelty verdicts stay in `reports/causal_global_links.json`.

    python desks/mt5/research/causal_lab.py [--dry-run] [--symbols EURUSD XAUUSD ...] [--days 500]
                                            [--no-global] [--no-donate]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
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

from libs.research import set_aside as sa  # noqa: E402

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
    # MAX_EDGES IS A BATCH BUDGET, NOT A SCREEN (LAWS 7). `n_edges` already publishes the true
    # count; the named refusal below says which ones were carried and by what ordering.
    return {"edges": sa.take(edges, MAX_EDGES, organ="causal_lab", stage="dag_edges",
                             ordering="-abs(weight)"),
            "n_edges": len(edges), "threshold": threshold,
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
    return sa.take(out, MAX_CHAINS, organ="causal_lab", stage="mechanism_chains",
                   ordering="-class_rank, -len(nodes), -min_abs_r")


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


# ================================================================== (4) THE GLOBAL STREAMS
#
# THE PRINCIPAL, 2026-10-13: hunt UNKNOWN styles. Tier-1 #377 measured the 43 certificates and found
# none novel -- every one a passive session window, a range breakout or a drift. Those styles are
# what a desk finds when the only inputs are its own bars and the four Western axis files above.
# The desk already LANDS far stranger inputs -- the alt_proxies panels (GDELT among them), the
# free stack, the country packs' canonical frames, the retail-forum text store, COT positioning,
# the world dataset hunter's official statistics -- and none of them reached this lab. This
# section reads each of them POINT IN TIME, tests its lead over MT5 instrument returns with the
# same partial-correlation oracle and ONE Benjamini-Hochberg charge, and turns each surviving link
# into a STATE-CONDITIONED cell ("when stream S is in regime R, instrument I does X") under a
# family the gauntlet can already rebuild: `exogenous_conditioner` for a lake frame,
# `world_macro_state` for a world series. A forum, local-language or axis stream with no lake
# frame is LANDED as one (`land_streams`), which is what makes it executable; COT stays
# measured-only because the cot_* families already trade it.
#
# POINT IN TIME. A value is placed at its own known-by stamp (`available_time` on a lake or raw
# frame, `knowable_at` + 1 day on COT, `first_seen_at` + 1 day on a forum count, the hunter's own
# `pit_series` clock on a world series). The stream's z is taken on its OWN observations, then read
# as of 00:00 UTC of each trading day and used only at lag >= 1, so the value a day-t return is
# tested against was knowable before day t-1's broker close (21:00-22:00 UTC) at the latest. A
# stream with no stamp is EXCLUDED AND COUNTED, never assumed.
#
# TRIALS. Every test run is in the one BH denominator below. A donated cell is charged by the
# gauntlet exactly once, through the existing trial ledger: this section writes no trial row, and
# a cell already in this seat's donation contract is never donated again.

LAKE_SERIES = DESK / "data" / "lake" / "series"
LAKE_VAULT = DESK / "data" / "lake" / "vault"
RAW_LANDINGS = DESK / "data" / "dfraw"
TEXT_STORE = DESK / "data" / "text_store"
WORLD_STORE = DESK / "data" / "world_datasets"
STYLE_NOVELTY = DESK / "reports" / "STYLE_NOVELTY.json"
INTEL = DESK / "data" / "intelligence"
GLOBAL_OUT = DESK / "reports" / "causal_global_links.json"
GLOBAL_SOURCE = "causal_global"

GLOBAL_DAYS, GLOBAL_LAGS = 750, (1, 2, 3)
OWN_LAGS = 3
MAX_STREAMS, MAX_TARGETS, MAX_COLS_PER_FILE, MAX_LINKS = 400, 48, 2, 200
#: `family_exogenous_conditioner.MIN_OBSERVATIONS`: below it the family emits nothing, so a link
#: on a shorter stream could never execute and is not worth a slot in the BH denominator.
MIN_STREAM_OBS = 30
#: The two families' own z windows, so the regime the lab measures IS the regime the cell trades.
LAKE_Z_WINDOW, WORLD_Z_OBS, Z_MIN_PERIODS = 250, 24, 20
#: Days an as-of value may be carried before it is stale: a stream that stopped publishing is not
#: a state that persists forever.
MAX_STALE_DAYS = 120
REGIME_Z, MIN_REGIME_DAYS = 1.0, 20
MAX_DONATIONS = 20
GLOBAL_BUDGET_S = 300.0
MAX_TEXT_LINES = 200_000

#: The asset classes this lane tests, read from the broker's own registry (never a symbol list).
#: Single-name equities are absent by the two-lane mandate; crypto CFDs and bonds are not targets
#: of this pass.
TARGET_CLASSES = frozenset({"forex", "forex majors", "forex crosses", "forex exotics", "fx",
                            "indices", "index", "commodities", "commodity", "soft commodity",
                            "soft commodities", "energy", "metal", "metals"})

#: Styles #377 found the whole book already IS: passive window (carry, session/calendar drift),
#: range breakout and the 20-day breakout. The artifact's `dominant_style_counts` is added on top.
REPEAT_STYLES_BASE = ("passive_window", "range_breakout_12bar", "breakout_20d")
NOVEL_T_FALLBACK = 0.5

#: The PIT envelope columns of a lake frame -- the stamp, never a signal (the same set
#: `family_exogenous_conditioner.STAMP_COLUMNS` strips; read from there when importable).
_STAMP_FALLBACK = frozenset({"event_time", "published_time", "available_time", "revision_time",
                             "retrieval_time", "ingested_time", "source_id", "vintage_id",
                             "first_seen_at", "period", "lag_days"})
#: Named stream families the order asked for, and how this pass recognises each by name.
NAMED_FAMILIES: dict[str, tuple[str, ...]] = {
    "gdelt": ("gdelt",),
    "cn_retail_posts / guba / paxnet": ("cn_retail", "guba", "taoguba", "paxnet"),
    "alt_proxies": ("alt_",),
    "free_stack": ("fs_",),
    "blog_social": ("blog_social",),
    "nlp_events": ("nlp_events",),
    "cot": ("cot:",),
    "world_dataset_hunt": ("world:",),
    "dfraw": ("raw:",),
}
GLOBAL_RULE = ("a stream enters only at its own known-by stamp and only at lag >= 1; every test is "
               "in one BH charge; a link is a cell only under a family the gauntlet already "
               "rebuilds, and never in a style the book already holds")


@dataclass
class Stream:
    """One global stream: values on their own known-by clock (UTC), and how a cell trades it."""

    name: str
    store: str
    series: Any                      # pd.Series, index = known-by instant (UTC), float values
    z_window: int
    cell: dict[str, Any] | None = None
    why_not_executable: str = ""
    targets: tuple[str, ...] | None = None


def _stamp_columns() -> frozenset[str]:
    try:
        from mt5desk.family_exogenous_conditioner import STAMP_COLUMNS
        return frozenset(STAMP_COLUMNS) | _STAMP_FALLBACK
    except Exception:
        return _STAMP_FALLBACK


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _excl(rows: list[dict[str, Any]], stream: str, store: str, why: str, **extra: Any) -> None:
    rows.append({"stream": stream, "store": store, "why": why, **extra})


def read_tabular(path: Path, store: str, excluded: list[dict[str, Any]]) -> list[Stream]:
    """A lake or raw frame. `available_time` is required; a row without a parseable one is dropped
    and COUNTED, and a file without the column is excluded whole."""
    import pandas as pd
    stem = path.stem
    try:
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception as exc:
        _excl(excluded, stem, store, f"unreadable ({type(exc).__name__})")
        return []
    if "available_time" not in df.columns:
        _excl(excluded, stem, store, (
            "no available_time column: a row with no known-by stamp cannot be placed in time, so "
            "the file is excluded and counted, never assumed"), n_rows=len(df))
        return []
    stamps = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    n_unstamped = int(stamps.isna().sum())
    skip = _stamp_columns()
    cols = [c for c in df.columns if str(c) not in skip and pd.api.types.is_numeric_dtype(df[c])
            and not pd.api.types.is_bool_dtype(df[c])]
    cols.sort(key=lambda c: (-int(df[c].notna().sum()), str(c)))
    out: list[Stream] = []
    for col in cols[:MAX_COLS_PER_FILE]:
        s = pd.Series(pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float64"),
                      index=stamps)
        s = s[s.index.notna()].dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        name = f"{store}:{stem}.{col}"
        if len(s) < MIN_STREAM_OBS:
            _excl(excluded, name, store, f"{len(s)} stamped observation(s) < {MIN_STREAM_OBS}")
            continue
        executable = store == "lake"
        out.append(Stream(
            name=name, store=store, series=s, z_window=LAKE_Z_WINDOW,
            cell=({"family": "exogenous_conditioner",
                   "params": {"source": stem, "signal": str(col), "transform": "level_z"}}
                  if executable else None),
            why_not_executable=("" if executable else
                                "a raw landing, not a canonical data/lake/series frame: "
                                "exogenous_conditioner cannot read it")))
    if len(cols) > MAX_COLS_PER_FILE:
        _excl(excluded, f"{store}:{stem}", store,
              f"{len(cols) - MAX_COLS_PER_FILE} further numeric column(s) beyond "
              f"MAX_COLS_PER_FILE={MAX_COLS_PER_FILE} (densest kept)", kind="set_aside")
    if n_unstamped:
        _excl(excluded, f"{store}:{stem}", store,
              f"{n_unstamped} row(s) with no parseable available_time dropped", kind="rows")
    return out


def read_cot(axes_dir: Path, excluded: list[dict[str, Any]]) -> list[Stream]:
    """COT net positioning per instrument, at knowable_at + 1 day (the stamp is a date)."""
    import pandas as pd
    try:
        doc = json.loads((axes_dir / "cot.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _excl(excluded, "cot", "cot", f"axes/cot.json unreadable ({type(exc).__name__})")
        return []
    by: dict[str, list[tuple[Any, float]]] = {}
    unstamped = 0
    for row in doc.get("rows") or []:
        if not isinstance(row, dict):
            continue
        t = pd.to_datetime(str(row.get("knowable_at") or ""), errors="coerce", utc=True)
        try:
            v = float(row["net_pct_oi"])
        except (KeyError, TypeError, ValueError):
            continue
        if pd.isna(t) or len(str(row.get("knowable_at") or "")) < 10:
            unstamped += 1
            continue
        by.setdefault(str(row.get("symbol") or ""), []).append((t + pd.Timedelta(days=1), v))
    if unstamped:
        _excl(excluded, "cot", "cot", f"{unstamped} COT row(s) without a day-precise knowable_at "
                                       "dropped", kind="rows")
    out: list[Stream] = []
    for sym, pts in sorted(by.items()):
        if not sym:
            continue
        s = pd.Series([v for _, v in pts], index=pd.DatetimeIndex([t for t, _ in pts])).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if len(s) < MIN_STREAM_OBS:
            _excl(excluded, f"cot:{sym}", "cot", f"{len(s)} observation(s) < {MIN_STREAM_OBS}")
            continue
        out.append(Stream(
            name=f"cot:{sym}.net_pct_oi", store="cot", series=s, z_window=LAKE_Z_WINDOW,
            targets=(sym,), why_not_executable=(
                "COT positioning is already expressed by the cot_* families on the docket; the "
                "link is kept in the artifact rather than re-minted as a new cell")))
    return out


def read_axis_series(axes_dir: Path, lake_stems: set[str],
                     excluded: list[dict[str, Any]]) -> list[Stream]:
    """Every OTHER axis file in the `series[...].points` shape, point by point on `available_time`.
    bis/ecb/fred/cot feed the core panel above; a file already landed as a lake frame is read
    there instead, so one stream is never tested twice."""
    import pandas as pd
    out: list[Stream] = []
    for path in sorted(axes_dir.glob("*.json")) if axes_dir.is_dir() else []:
        stem = path.stem
        if stem in ("bis", "cot", "ecb", "fred"):
            continue
        if any(s.startswith(stem) for s in lake_stems):
            _excl(excluded, f"axis:{stem}", "axes", "read through its data/lake/series frame",
                  kind="duplicate")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _excl(excluded, f"axis:{stem}", "axes", f"unreadable ({type(exc).__name__})")
            continue
        for sid, blob in sorted((doc.get("series") or {}).items()):
            pts = (blob or {}).get("points") or [] if isinstance(blob, dict) else []
            stamped = [(p.get("available_time"), p.get("v")) for p in pts
                       if isinstance(p, dict) and p.get("available_time")
                       and p.get("v") is not None]
            name = f"axis:{stem}.{sid}"
            if len(stamped) < len(pts):
                _excl(excluded, name, "axes", f"{len(pts) - len(stamped)} point(s) without "
                                              "available_time dropped", kind="rows")
            if len(stamped) < MIN_STREAM_OBS:
                _excl(excluded, name, "axes", f"{len(stamped)} stamped point(s) < {MIN_STREAM_OBS}")
                continue
            s = pd.Series(pd.to_numeric([v for _, v in stamped], errors="coerce"),
                          index=pd.to_datetime([t for t, _ in stamped], errors="coerce", utc=True))
            s = s[s.index.notna()].dropna().sort_index()
            s = s[~s.index.duplicated(keep="last")]
            out.append(Stream(name=name, store="axes", series=s, z_window=LAKE_Z_WINDOW,
                              why_not_executable="an axis file with no lake frame; no family "
                                                 "reads it by name"))
    return out


def read_text_store(root: Path, excluded: list[dict[str, Any]]) -> list[Stream]:
    """Daily post counts per forum (and per source within it), each day knowable at the next
    00:00 UTC after the posts were FIRST SEEN. A day counts as zero only when the store's own
    observed_days.json says the crawler was there; otherwise the day is simply absent."""
    import pandas as pd
    out: list[Stream] = []
    for posts in sorted(root.glob("*/posts.jsonl")) if root.is_dir() else []:
        forum = posts.parent.name
        try:
            every = posts.read_text("utf-8", errors="replace").splitlines()
            truncated = len(every) > MAX_TEXT_LINES
            lines = every[-MAX_TEXT_LINES:]
        except OSError as exc:
            _excl(excluded, f"text:{forum}", "text_store", f"unreadable ({type(exc).__name__})")
            continue
        counts: dict[str, dict[str, int]] = {}
        unstamped = 0
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                unstamped += 1
                continue
            t = pd.to_datetime(str((r or {}).get("first_seen_at") or ""), errors="coerce", utc=True)
            if pd.isna(t):
                unstamped += 1
                continue
            day = str(t.date())
            for key in ("*", str(r.get("source") or "")):
                if key:
                    counts.setdefault(key, {})[day] = counts.setdefault(key, {}).get(day, 0) + 1
        if unstamped:
            _excl(excluded, f"text:{forum}", "text_store",
                  f"{unstamped} post(s) without a parseable first_seen_at dropped", kind="rows")
        try:
            observed = set(json.loads((posts.parent / "observed_days.json").read_text("utf-8")))
        except (OSError, ValueError, TypeError):
            observed = set()
        # THE TAIL CUT IS NOT A QUIET DAY. Reading only the last MAX_TEXT_LINES posts drops the
        # early days' posts; zero-filling those days from observed_days would write a false zero
        # where the truth is "not read". When the file was cut, every day before the first kept
        # day -- and that first day itself, which the cut may have split -- is MISSING, never 0.
        if truncated and counts.get("*"):
            first_kept = min(counts["*"])
            for per_key in counts.values():
                per_key.pop(first_kept, None)
            observed = {str(d) for d in observed if str(d) > first_kept}
            _excl(excluded, f"text:{forum}", "text_store",
                  f"{len(every) - MAX_TEXT_LINES} early post(s) beyond MAX_TEXT_LINES not read: "
                  f"days up to {first_kept} are MISSING, not zero", kind="rows")
        keys = ["*", *sorted(k for k in counts if k != "*")] if len(counts) > 2 else ["*"]
        for key in keys:
            per = dict(counts.get(key) or {})
            for d in observed:
                per.setdefault(str(d), 0)
            name = f"text:{forum}.posts" if key == "*" else f"text:{forum}.{key}.posts"
            if len(per) < MIN_STREAM_OBS:
                _excl(excluded, name, "text_store", f"{len(per)} day(s) < {MIN_STREAM_OBS}")
                continue
            idx = pd.to_datetime(sorted(per), utc=True) + pd.Timedelta(days=1)
            s = pd.Series([float(per[d]) for d in sorted(per)], index=idx)
            out.append(Stream(name=name, store="text_store", series=s, z_window=LAKE_Z_WINDOW,
                              why_not_executable=("a raw forum count has no executable family; "
                                                  "its canonical lake frame (blog_social_<SYM>) "
                                                  "is the executable sibling")))
    return out


def read_world(store: Path, targets: list[str], excluded: list[dict[str, Any]]) -> list[Stream]:
    """The world dataset hunter's core exposure per target, on the hunter's own PIT clock."""
    import pandas as pd
    if not (store / "keys.json").exists():
        _excl(excluded, "world_dataset_hunt", "world_datasets",
              "no data/world_datasets/keys.json on this host")
        return []
    try:
        from research import world_dataset_hunter as W
    except Exception as exc:
        _excl(excluded, "world_dataset_hunt", "world_datasets",
              f"world_dataset_hunter unimportable ({type(exc).__name__})")
        return []
    try:
        doc = json.loads((store / "exposure.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    core = int(doc.get("core", 8) or 8)
    wanted: dict[str, list[str]] = {}
    for sym in targets:
        for key in list((doc.get("symbols") or {}).get(sym) or [])[:core]:
            wanted.setdefault(str(key), []).append(sym)
    out: list[Stream] = []
    for key, syms in sorted(wanted.items()):
        try:
            s = W.raw_world_series(key)
        except Exception:
            s = None
        name = f"world:{key}"
        if s is None or len(s) < WORLD_Z_OBS + 2:
            _excl(excluded, name, "world_datasets", "no PIT series behind the key on this host")
            continue
        idx = pd.DatetimeIndex(s.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        s = pd.Series(s.to_numpy(dtype="float64"), index=idx).dropna().sort_index()
        out.append(Stream(name=name, store="world_datasets", series=s, z_window=WORLD_Z_OBS,
                          cell={"family": "world_macro_state",
                                "params": {"series_key": key, "z_obs": WORLD_Z_OBS}},
                          targets=tuple(syms)))
    return out


def load_streams(*, lake: Path = LAKE_SERIES, raw: Path = RAW_LANDINGS, vault: Path = LAKE_VAULT,
                 axes_dir: Path = AXES, text: Path = TEXT_STORE, world: Path = WORLD_STORE,
                 targets: list[str] | None = None,
                 ) -> tuple[list[Stream], list[dict[str, Any]], dict[str, Any]]:
    """(streams, excluded, census). Every store is visited; an absent one is a census row."""
    excluded: list[dict[str, Any]] = []
    census: dict[str, Any] = {}
    streams: list[Stream] = []

    def _files(d: Path) -> list[Path]:
        return sorted(p for p in d.rglob("*") if p.suffix in (".parquet", ".csv")) \
            if d.is_dir() else []

    lake_files = []
    for p in _files(lake):
        if p.stem.startswith(LANDING_PREFIX):
            _excl(excluded, f"lake:{p.stem}", "lake", "this organ's own landing; read through its "
                                                      "origin store", kind="own_landing")
        else:
            lake_files.append(p)
    for store, files in (("lake", lake_files), ("raw", _files(raw))):
        got: list[Stream] = []
        for p in files:
            got.extend(read_tabular(p, store, excluded))
        where = lake if store == "lake" else raw
        census[store] = {"present": where.is_dir(), "files": len(files), "streams": len(got)}
        streams.extend(got)
    n_vault = sum(1 for p in vault.rglob("*") if p.is_file()) if vault.is_dir() else 0
    census["vault"] = {"present": vault.is_dir(), "files": n_vault, "streams": 0}
    if n_vault:
        _excl(excluded, "lake:vault", "vault", (
            f"{n_vault} raw vault file(s): bytes as fetched, no available_time column; each "
            "country pack's canonical frame is read from data/lake/series instead"),
            kind="raw_bytes")
    readers: tuple[tuple[str, Callable[[], list[Stream]]], ...] = (
        ("cot", lambda: read_cot(axes_dir, excluded)),
        ("axes", lambda: read_axis_series(axes_dir, {p.stem for p in lake_files}, excluded)),
        ("text_store", lambda: read_text_store(text, excluded)),
        ("world_datasets", lambda: read_world(world, list(targets or []), excluded)))
    for store, fn in readers:
        got = fn()
        census[store] = {"streams": len(got)}
        streams.extend(got)
    census["text_store"]["present"] = text.is_dir()
    census["world_datasets"]["present"] = (world / "keys.json").exists()
    names = [s.name for s in streams]
    census["named_families"] = {
        fam: {"streams": sum(1 for n in names if any(tok in n.lower() for tok in toks)),
              "status": ("READ" if any(any(tok in n.lower() for tok in toks) for n in names)
                         else "ABSENT_ON_HOST")}
        for fam, toks in NAMED_FAMILIES.items()}
    return streams, excluded, census


#: Prefix of the lake series this organ lands. The lake reader skips them (each is read through
#: its origin store), so one stream is never tested twice.
LANDING_PREFIX = "cg_"
#: Stores whose streams have no lake frame of their own and are landed as one (COT is not: the
#: cot_* families already trade it; world series are not: world_macro_state reads them by key).
LANDED_STORES = ("text_store", "axes", "raw")


def landing_id(name: str) -> str:
    """`text:cn_retail_posts.guba.posts` -> `cg_text__cn_retail_posts_guba_posts`."""
    store, _, rest = name.partition(":")
    slug = "".join(ch if ch.isalnum() else "_" for ch in rest.lower()).strip("_")
    return f"{LANDING_PREFIX}{store}__{slug}"[:120]


def land_streams(streams: list[Stream], series_dir: Path = LAKE_SERIES) -> dict[str, Any]:
    """THE HAND-OFF (coordinator, 2026-10-13). Every forum, local-language and axis stream with no
    lake frame is LANDED as `data/lake/series/<id>.csv` in the lake's PIT envelope, through the
    repo's one lake-series writer (`alt_proxies.write_series_csv`). From then on it is an ordinary
    lake series: `exogenous_conditioner` reads it by id, the collector and pack cells see it, and
    #385's novelty screen applies downstream. The stream becomes executable THIS pass."""
    import pandas as pd
    try:
        from research.alt_proxies import write_series_csv
    except Exception as exc:
        return {"status": "UNMEASURED", "landed": [], "why": (
            f"alt_proxies.write_series_csv unimportable ({type(exc).__name__}); nothing landed "
            "and no stream was made executable")}
    landed: list[str] = []
    failed: list[dict[str, str]] = []
    for st in streams:
        if st.store not in LANDED_STORES or st.cell is not None:
            continue
        sid = landing_id(st.name)
        stamps = [t.isoformat() for t in pd.DatetimeIndex(st.series.index)]
        frame = pd.DataFrame({"event_time": stamps, "available_time": stamps,
                              "source_id": st.name, "value": st.series.to_numpy(dtype="float64"),
                              "pit_quality": "known_by_stamp_of_origin_store"})
        try:
            write_series_csv(series_dir, sid, frame)
        except (OSError, ValueError) as exc:
            failed.append({"stream": st.name, "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        st.cell = {"family": "exogenous_conditioner",
                   "params": {"source": sid, "signal": "value", "transform": "level_z"}}
        st.why_not_executable = ""
        landed.append(f"{sid}.csv")
    return {"status": "OK", "dir": _rel(series_dir), "landed": landed, "n_landed": len(landed),
            "failed": failed}


# ------------------------------------------------------------------ targets and PIT alignment

def global_targets(uni: Path = UNI) -> tuple[list[str], list[dict[str, str]]]:
    """FX, metals, indices, energy and softs from the broker's registry that have bars here and
    that the two-lane mandate lets this lane hypothesise on."""
    refused: list[dict[str, str]] = []
    try:
        reg = json.loads((uni / "universe.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reg = {}
    try:
        from research.universe_policy import may_hypothesise
    except Exception as exc:
        # FAIL CLOSED: without the lane policy no symbol's lane is known, so none is admitted.
        why = (f"research.universe_policy unimportable ({type(exc).__name__}): the lane is "
               "unknown, so nothing is admitted")
        return [], [{"symbol": "*", "why": why}]
    rank = {s: k for k, s in enumerate(DEFAULT_SYMBOLS)}
    picked: list[tuple[int, str, str]] = []
    rows = reg.items() if isinstance(reg, dict) and reg else \
        ((s, {"asset_class": "fx"}) for s in DEFAULT_SYMBOLS)
    for sym, meta in rows:
        cls = str((meta or {}).get("asset_class") or "").strip().lower()
        if cls not in TARGET_CLASSES and sym not in rank:
            continue
        if not (uni / f"{sym}_H1.parquet").exists():
            continue
        if not may_hypothesise(sym):
            refused.append({"symbol": sym, "why": "the two-lane mandate: event lane only"})
            continue
        picked.append((rank.get(sym, len(rank)), cls, str(sym)))
    picked.sort()
    syms = [s for _, _, s in picked]
    return sa.take(syms, MAX_TARGETS, organ="causal_lab", stage="global_targets",
                   ordering="book symbols first, then registry class, then symbol"), refused


def stream_z(stream: Stream) -> Any:
    """The stream's trailing z on its OWN observations (each point against its own past only)."""
    s = stream.series.astype(float)
    r = s.rolling(int(stream.z_window), min_periods=min(Z_MIN_PERIODS, int(stream.z_window)))
    z = (s - r.mean()) / r.std(ddof=1)
    return z.replace([np.inf, -np.inf], np.nan).dropna()


def asof_days(z: Any, days: list[str]) -> np.ndarray:
    """z as of 00:00 UTC of each day: the last value whose known-by instant is at or before it,
    carried at most MAX_STALE_DAYS. NaN where nothing was knowable yet."""
    out = np.full(len(days), np.nan)
    if z is None or len(z) == 0 or not days:
        return out
    import pandas as pd
    # ONE UNIT ON BOTH SIDES. `asi8` is in the index's OWN unit (s, ms, us or ns -- pandas 2
    # keeps the unit a frame was built with, and pandas 3 infers it per input), so comparing raw
    # integers mixed units: an s/ms stream read a June value on a January day (look-ahead), an
    # ns stream read all-NaN against a coarser day index, and the ns staleness limit below was
    # 1000x off. Both sides are converted to ns before a single integer is compared.
    t = np.asarray(pd.to_datetime(z.index, utc=True).as_unit("ns").asi8, dtype="int64")
    v = z.to_numpy(dtype="float64")
    d = np.asarray(pd.to_datetime(days, utc=True).as_unit("ns").asi8, dtype="int64")
    k = np.searchsorted(t, d, side="right") - 1
    ok = k >= 0
    stale = np.zeros(len(d), dtype=bool)
    stale[ok] = (d[ok] - t[k[ok]]) > MAX_STALE_DAYS * 86_400 * 10**9
    use = ok & ~stale
    out[use] = v[k[use]]
    return out


def _lagged_test(r: np.ndarray, x: np.ndarray, lag: int) -> dict[str, Any] | None:
    """Partial correlation of r_t on x_{t-lag} given r's own OWN_LAGS lags."""
    n = len(r)
    start = max(OWN_LAGS, lag)
    if n - start < MIN_DAYS:
        return None
    y = r[start:]
    xs = x[start - lag: n - lag]
    own = np.column_stack([r[start - k: n - k] for k in range(1, OWN_LAGS + 1)])
    ok = np.isfinite(y) & np.isfinite(xs) & np.isfinite(own).all(axis=1)
    m = int(ok.sum())
    if m < MIN_DAYS or float(np.std(xs[ok])) <= 1e-12:
        return None
    ry, rx = _resid(y[ok], own[ok]), _resid(xs[ok], own[ok])
    rr, denom = _corr(rx, ry), float(rx @ rx)
    return {"r": rr, "coef": float(rx @ ry) / denom if denom > 1e-12 else 0.0,
            "p": fisher_p(rr, m, OWN_LAGS), "n": m}


def regime_reading(r: np.ndarray, x: np.ndarray, lag: int) -> dict[str, Any]:
    """The instrument's next-day return inside each band of the stream's lagged z."""
    y, xs = r[lag:], x[:len(x) - lag]
    ok = np.isfinite(y) & np.isfinite(xs)
    out: dict[str, Any] = {"z": REGIME_Z}
    for label, sel in (("high", ok & (xs >= REGIME_Z)), ("mid", ok & (np.abs(xs) < REGIME_Z)),
                       ("low", ok & (xs <= -REGIME_Z))):
        k = int(sel.sum())
        out[label] = {"n": k, "mean": round(float(y[sel].mean()), 7) if k else None,
                      "status": "OK" if k >= MIN_REGIME_DAYS else "UNMEASURED"}
    return out


# ------------------------------------------------------------------ novelty

def _style_classifier() -> Any:
    """#377's own classifier (`style_novelty.style_matrix` + `project`) through a GUARDED import.
    It lives on branch claude/style-novelty-lane; until that merges this returns None and the
    verdict falls back to the published artifact, then to UNMEASURED."""
    try:
        from research import style_novelty as sn  # type: ignore[attr-defined]
    except Exception:
        return None
    return sn if all(hasattr(sn, a) for a in ("style_matrix", "project")) else None


def novelty_context(path: Path = STYLE_NOVELTY) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    sn = _style_classifier()
    dom = dict((doc or {}).get("dominant_style_counts") or {}) if isinstance(doc, dict) else {}
    repeat = sorted(set(REPEAT_STYLES_BASE) | {str(k) for k, v in dom.items() if v})
    return {"artifact": str(path.name), "artifact_present": isinstance(doc, dict),
            "classifier": "style_novelty.style_matrix+project" if sn else "UNAVAILABLE",
            "classifier_note": ("" if sn else
                                "desks/mt5/research/style_novelty.py is not on this branch "
                                "(PR #377, claude/style-novelty-lane); guarded import, no copy"),
            "dominant_style_counts": dom, "repeat_styles": repeat,
            "per_family": dict((doc or {}).get("per_family") or {}) if isinstance(doc, dict)
            else {},
            "novel_t": float(getattr(sn, "NOVEL_T", NOVEL_T_FALLBACK)) if sn else
            NOVEL_T_FALLBACK, "_sn": sn}


def classify_novelty(ctx: dict[str, Any], family: str, days: list[str], r: np.ndarray,
                     x: np.ndarray, lag: int, band: str, side: int) -> dict[str, Any]:
    """REPEAT_STYLE (never donated), NOVEL, KNOWN_STYLE, or UNMEASURED (donated, nothing claimed).

    With the classifier: the cell's own daily signals -- every day the lagged stream z sits in the
    traded band -- projected onto #377's ten known styles on the same bars. Without it: the
    artifact's per-family saturation, else UNMEASURED."""
    sn = ctx.get("_sn")
    if sn is not None:
        from types import SimpleNamespace

        import pandas as pd
        close = np.exp(np.cumsum(np.nan_to_num(r)))
        idx = pd.DatetimeIndex(pd.to_datetime(days, utc=True))
        sigs = []
        for t in range(lag, len(days)):
            v = x[t - lag]
            if not np.isfinite(v):
                continue
            if (band == "high" and v >= REGIME_Z) or (band == "low" and v <= -REGIME_Z):
                sd = side
            elif band == "both" and abs(v) >= REGIME_Z:
                sd = side * int(np.sign(v))
            else:
                continue
            sigs.append(SimpleNamespace(time=idx[t - 1], side=sd, ttl_bars=1, trigger=None,
                                        wait_bars=1))
        try:
            y, X = sn.style_matrix(close, idx, sigs)
            proj = sn.project(y, X)
        except Exception as exc:
            return {"verdict": "UNMEASURED", "why": f"classifier raised {type(exc).__name__}",
                    "by": "classifier"}
        if proj.get("status") != "MEASURED":
            return {"verdict": "UNMEASURED", "why": str(proj.get("why") or "not measured"),
                    "by": "classifier", "n": proj.get("n")}
        dom = proj.get("dominant_style")
        nr = float(proj.get("novelty_return") or 0.0)
        verdict = ("REPEAT_STYLE" if dom in ctx["repeat_styles"] else
                   "NOVEL" if nr >= float(ctx["novel_t"]) else "KNOWN_STYLE")
        return {"verdict": verdict, "by": "classifier", "dominant_style": dom,
                "novelty_return": round(nr, 4), "n": proj.get("n"),
                "basis": "daily bars of the instrument, the cell's own band days"}
    fam = (ctx.get("per_family") or {}).get(family)
    if isinstance(fam, dict) and fam.get("saturation") == "SATURATED":
        return {"verdict": "REPEAT_STYLE", "by": "artifact", "why": (
            f"STYLE_NOVELTY.json marks family {family} SATURATED: it holds certificates and none "
            "is novel")}
    return {"verdict": "UNMEASURED", "by": "artifact" if ctx.get("artifact_present") else "none",
            "why": ("classifier not importable on this branch; the artifact does not mark the "
                    "family saturated" if ctx.get("artifact_present") else
                    "STYLE_NOVELTY.json absent and the classifier not importable: novelty is "
                    "UNMEASURED, neither blocked nor assumed novel")}


# ------------------------------------------------------------------ the pass

def _prior_identities(seat: Path) -> set[str]:
    """Cells this seat already donated: the donation contract IS the record, so a cell is charged
    once and never re-donated hourly."""
    import gzip

    from research.proposer_common import identity
    seen: set[str] = set()

    def _take(doc: Any) -> None:
        rows = (doc.get("discoveries") if isinstance(doc, dict) and "discoveries" in doc
                else doc if isinstance(doc, list) else [doc])
        for c in rows or []:
            if isinstance(c, dict) and c.get("family"):
                seen.add(identity(str(c.get("symbol")), str(c.get("family")),
                                  dict(c.get("params") or {})))

    for f in sorted(seat.glob("discoveries_*.json")) if seat.is_dir() else []:
        try:
            _take(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    # scripts/disk_guard.py `rollup` compacts aged discovery files into rollup_<day>.jsonl.gz,
    # one JSON document per line; a cell rolled up there was still donated.
    for f in sorted(seat.glob("rollup_*.jsonl.gz")) if seat.is_dir() else []:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        _take(json.loads(line))
                    except ValueError:
                        continue
        except (OSError, EOFError):
            continue
    return seen


def _cell_for(stream: Stream, target: str, lag: int, coef: float,
              regimes: dict[str, Any]) -> tuple[dict[str, Any] | None, str, int, str]:
    """(family+params, band, side, why-none). The band is where the measured effect is strongest
    among bands with enough days; its sign must agree with the linear link's."""
    sgn = int(np.sign(coef)) or 1
    bands = [(b, regimes[b]) for b in ("high", "low") if regimes[b]["status"] == "OK"]
    if not bands:
        return None, "", 0, f"no band holds {MIN_REGIME_DAYS} days: the regime is UNMEASURED"
    band, info = max(bands, key=lambda kv: abs(float(kv[1]["mean"] or 0.0)))
    side = int(np.sign(float(info["mean"] or 0.0)))
    if side == 0 or side != (sgn if band == "high" else -sgn):
        return None, band, side, ("the strongest band's mean return disagrees in sign with the "
                                  "linear link: the regime and the line tell different stories")
    if stream.cell is None:
        return None, band, side, stream.why_not_executable or "no executable family"
    fam = str(stream.cell["family"])
    params = dict(stream.cell["params"])
    if fam == "exogenous_conditioner":
        params.update({"threshold": REGIME_Z, "side_when_high": sgn, "lag_hours": 24 * lag,
                       "ttl_bars": 24})
    elif fam == "world_macro_state":
        params.update({"z_lo": REGIME_Z, "z_hi": 99.0} if band == "high" else
                      {"z_lo": -99.0, "z_hi": -REGIME_Z})
        params.update({"direction": "long" if side > 0 else "short", "hold_bars": 24})
    return {"family": fam, "params": params}, band, side, ""


def build_global(*, streams: list[Stream] | None = None, excluded: list[dict[str, Any]] | None
                 = None, census: dict[str, Any] | None = None,
                 returns: dict[str, tuple[list[str], np.ndarray]] | None = None,
                 targets: list[str] | None = None, novelty: dict[str, Any] | None = None,
                 prior: set[str] | None = None, budget_s: float = GLOBAL_BUDGET_S,
                 now: str | None = None, land: bool = False,
                 series_dir: Path = LAKE_SERIES) -> dict[str, Any]:
    """Read the global streams, test them against MT5 returns, emit conditioned cells."""
    import time as _time
    t0 = _time.monotonic()
    at = now or datetime.now(tz=UTC).isoformat(timespec="seconds")
    refused_targets: list[dict[str, str]] = []
    if targets is None:
        targets, refused_targets = global_targets()
    if returns is None:
        returns = {}
        for sym in targets:
            bars = _daily_returns(UNI / f"{sym}_H1.parquet")
            if bars is not None:
                returns[sym] = bars
    if streams is None:
        streams, excluded, census = load_streams(targets=list(returns))
    excluded = list(excluded or [])
    census = dict(census or {})
    ctx = novelty if novelty is not None else novelty_context()
    landing = (land_streams(streams, series_dir) if land else
               {"status": "SKIPPED", "why": "dry run: nothing landed", "landed": []})
    usable = list(streams)
    usable.sort(key=lambda s: (-len(s.series), s.name))
    kept = sa.take(usable, MAX_STREAMS, organ="causal_lab", stage="global_streams",
                   ordering="-n_observations, name")
    for s in usable[MAX_STREAMS:]:
        _excl(excluded, s.name, s.store, f"MAX_STREAMS={MAX_STREAMS} reached (densest kept)",
              kind="set_aside")
    tests: list[dict[str, Any]] = []
    aligned: dict[tuple[str, str], np.ndarray] = {}
    short_overlap = 0
    reached: list[str] = []
    errored: list[str] = []
    for s in kept:
        if _time.monotonic() - t0 > budget_s:
            _excl(excluded, s.name, s.store, f"NOT_REACHED: the {budget_s:.0f}s budget was spent "
                                             "first", kind="not_reached")
            continue
        reached.append(s.name)
        # ONE STREAM THAT RAISES IS ONE STREAM EXCLUDED: its partial tests are discarded whole
        # (never half-charged to BH) and the pass goes on to the next stream.
        s_tests: list[dict[str, Any]] = []
        s_aligned: dict[tuple[str, str], np.ndarray] = {}
        s_short = 0
        try:
            z = stream_z(s)
            for sym in (s.targets or tuple(returns)):
                if sym not in returns:
                    continue
                days, r = returns[sym]
                days, r = days[-GLOBAL_DAYS:], r[-GLOBAL_DAYS:]
                x = asof_days(z, days)
                s_aligned[(s.name, sym)] = x
                for lag in GLOBAL_LAGS:
                    got = _lagged_test(r, x, lag)
                    if got is None:
                        s_short += 1
                        continue
                    s_tests.append({"stream": s.name, "store": s.store, "instrument": sym,
                                    "lag": lag, **got})
        except Exception as exc:
            errored.append(s.name)
            _excl(excluded, s.name, s.store, f"ERROR: the stream raised {type(exc).__name__}: "
                                             f"{str(exc)[:160]}", kind="error")
            continue
        tests.extend(s_tests)
        aligned.update(s_aligned)
        short_overlap += s_short
    links: list[dict[str, Any]] = []
    if tests:
        rej, qv = bh_fdr(np.array([t["p"] for t in tests], dtype="float64"), FDR_Q)
        for t, rj, qq in zip(tests, rej, qv, strict=True):
            if rj:
                links.append({**t, "q": float(qq)})
    links.sort(key=lambda t: (t["q"], -abs(float(t["r"]))))
    links = sa.take(links, MAX_LINKS, organ="causal_lab", stage="global_links",
                    ordering="q, -abs(r)")
    by_name = {s.name: s for s in kept}
    try:
        seen = prior if prior is not None else _prior_identities(INTEL / GLOBAL_SOURCE)
    except Exception:
        seen = set()
    from research.proposer_common import identity
    candidates: list[dict[str, Any]] = []
    verdicts: dict[str, int] = {}
    cell_status: dict[str, int] = {}
    for ln in links:
        s = by_name[ln["stream"]]
        days, r = returns[ln["instrument"]]
        days, r = days[-GLOBAL_DAYS:], r[-GLOBAL_DAYS:]
        x = aligned[(s.name, ln["instrument"])]
        lag = int(ln["lag"])
        regimes = regime_reading(r, x, lag)
        cell, band, side, why = _cell_for(s, ln["instrument"], lag, float(ln["coef"]), regimes)
        ln.update({"r": round(float(ln["r"]), 5), "coef": round(float(ln["coef"]), 6),
                   "p": round(float(ln["p"]), 8), "q": round(float(ln["q"]), 6),
                   "regimes": regimes, "band": band, "side": side,
                   "statement": (f"when {s.name} is {band or '?'} (z "
                                 f"{'>=' if band == 'high' else '<='} "
                                 f"{REGIME_Z if band == 'high' else -REGIME_Z:+.1f}), "
                                 f"{ln['instrument']} {'rises' if side > 0 else 'falls'} over "
                                 f"the day {lag} day(s) later") if band and side else ""})
        if cell is None:
            ln["cell_status"] = "NOT_EMITTED"
            ln["why"] = why
            cell_status["NOT_EMITTED"] = cell_status.get("NOT_EMITTED", 0) + 1
            ln["novelty"] = {"verdict": "NOT_CLASSIFIED", "why": "no cell to classify"}
            continue
        band_for_signals = "both" if cell["family"] == "exogenous_conditioner" else band
        sig_side = (int(np.sign(float(ln["coef"]))) or 1) if band_for_signals == "both" else side
        nov = classify_novelty(ctx, cell["family"], days, r, x, lag, band_for_signals, sig_side)
        ln["novelty"] = nov
        ln["cell"] = cell
        verdicts[nov["verdict"]] = verdicts.get(nov["verdict"], 0) + 1
        ident = identity(ln["instrument"], cell["family"], cell["params"])
        ln["identity"] = ident
        if nov["verdict"] == "REPEAT_STYLE":
            ln["cell_status"] = "REFUSED_REPEAT_STYLE"
        elif ident in seen:
            ln["cell_status"] = "ALREADY_DONATED"
        elif len(candidates) >= MAX_DONATIONS:
            ln["cell_status"] = "SET_ASIDE_MAX_DONATIONS"
        else:
            ln["cell_status"] = "EMITTED"
            candidates.append({
                "source": GLOBAL_SOURCE, "kind": "hypothesis", "symbol": ln["instrument"],
                "symbols": [ln["instrument"]], "family": cell["family"],
                "params": cell["params"], "url": "",
                "title": f"causal global: {s.name} -> {ln['instrument']} lag {lag} ({band})"[:120],
                "mechanism": (f"{ln['statement']}. Partial r={ln['r']:+.3f} given the "
                              f"instrument's own {OWN_LAGS} lags, BH q={ln['q']:.4f} over "
                              f"{len(tests)} tests; the stream is read at its own known-by "
                              "stamp, so the claim is about information the desk held "
                              "before the move.")[:400],
                "falsifier": (f"the {band} band of {s.name} carries no forward return on "
                              f"{ln['instrument']} net of cost out of sample"),
                "evidence": {"stream": s.name, "store": s.store, "lag_days": lag,
                             "r": ln["r"], "coef": ln["coef"], "p": ln["p"], "q": ln["q"],
                             "n": ln["n"], "regimes": regimes, "band": band,
                             "novelty": nov, "tests_in_bh": len(tests),
                             "screen": GLOBAL_RULE}})
        cell_status[ln["cell_status"]] = cell_status.get(ln["cell_status"], 0) + 1
    per_store: dict[str, dict[str, int]] = {}
    for s in kept:
        per_store.setdefault(s.store, {"streams": 0, "links": 0})["streams"] += 1
    for ln in links:
        per_store.setdefault(str(ln["store"]), {"streams": 0, "links": 0})["links"] += 1
    excl_kinds: dict[str, int] = {}
    for e in excluded:
        excl_kinds[str(e.get("kind") or "excluded")] = excl_kinds.get(
            str(e.get("kind") or "excluded"), 0) + 1
    n_not_reached = len(kept) - len(reached)
    n_tested = len(reached) - len(errored)
    # OK ONLY WHEN THE PASS DID ITS WORK. No test run is UNMEASURED (a budget spent before the
    # first test, or every pair too short, is not a clean "no links"); a pass that tested some
    # streams but not all is PARTIAL with its counts, never OK.
    if not returns or not kept:
        status = "UNMEASURED"
        why = ("no target returns on this host" if not returns else
               "no stamped global stream on this host: every store is absent or excluded -- "
               "UNMEASURED, not zero")
    elif not tests:
        status = "UNMEASURED"
        why = (f"0 tests ran: {len(reached)} of {len(kept)} stream(s) reached, "
               f"{n_not_reached} not reached inside the budget, {len(errored)} raised, "
               f"{short_overlap} pair(s) too short -- UNMEASURED, not zero")
    elif n_not_reached or errored:
        status = "PARTIAL"
        why = (f"{n_tested} of {len(kept)} stream(s) tested ({len(tests)} test(s)); "
               f"{n_not_reached} not reached inside the {budget_s:.0f}s budget, "
               f"{len(errored)} raised and excluded")
    else:
        status, why = "OK", ""
    return {
        "at": at, "status": status,
        "why": why, "n_streams_not_reached": n_not_reached, "n_streams_errored": len(errored),
        "targets": list(returns), "n_targets": len(returns), "targets_refused": refused_targets,
        "census": census, "per_store": per_store,
        "streams_read": [s.name for s in kept], "n_streams_read": len(kept),
        "n_streams_reached": len(reached),
        "streams_excluded": excluded[:400], "n_streams_excluded": len(excluded),
        "excluded_by_kind": excl_kinds,
        "n_tests": len(tests), "n_pairs_short_overlap": short_overlap, "fdr_q": FDR_Q,
        "lags_days": list(GLOBAL_LAGS), "n_links": len(links), "links": links,
        "cell_status": cell_status, "n_cells_emitted": len(candidates),
        "novelty": {k: v for k, v in ctx.items() if not k.startswith("_")},
        "novelty_verdicts": verdicts,
        "candidates": candidates,
        "landing": landing,
        "handoff": ("forum, local-language and axis streams are LANDED as data/lake/series/"
                    f"{LANDING_PREFIX}*.csv with available_time; the collector / pack cells turn "
                    "them into exogenous_conditioner cells and #385's novelty screen applies "
                    "there. This artifact keeps the causal links and novelty verdicts; it is "
                    "not a second LLM-lab input"),
        "pit": ("each stream at its own known-by stamp; z on its own observations; read as of "
                "00:00 UTC of a trading day and used only at lag >= 1"),
        "trials": ("one BH charge across every test above; a donated cell is charged once by the "
                   "gauntlet through the existing trial ledger, and a cell already donated by "
                   "this seat is never donated again"),
        "seconds": round(_time.monotonic() - t0, 2),
        "rule": GLOBAL_RULE,
    }


def donate_global(doc: dict[str, Any]) -> dict[str, Any]:
    """The seam: one call through the shared door, which stamps, lane-filters and pre-registers."""
    cands = list(doc.get("candidates") or [])
    if not cands:
        return {"donated": 0, "why": "no cell emitted this pass"}
    from research import proposer_common as pc
    path = pc.donate(GLOBAL_SOURCE, cands, int(doc.get("n_tests") or 0))
    out = pc.donation_counts()
    out["path"] = str(path) if path else None
    return {k: v for k, v in out.items() if k in ("donated", "refused_unstamped",
                                                   "refused_wrong_lane", "path", "source")}


def global_summary(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in ("status", "why", "n_targets", "n_streams_read",
                                    "n_streams_excluded", "n_tests", "n_links",
                                    "n_cells_emitted", "cell_status", "novelty_verdicts",
                                    "donation")} | {
        "n_landed": (doc.get("landing") or {}).get("n_landed", 0)} | {"artifact": _rel(GLOBAL_OUT)}


def global_lines(doc: dict[str, Any]) -> list[str]:
    head = (f"global streams: {doc['status']}   {doc.get('n_streams_read', 0)} stream(s) read, "
            f"{doc.get('n_streams_excluded', 0)} excluded row(s), {doc.get('n_targets', 0)} "
            "target(s)")
    if doc["status"] not in ("OK", "PARTIAL"):
        return [head, f"  {doc.get('why')}"]
    return [head, *([f"  PARTIAL: {doc.get('why')}"] if doc["status"] == "PARTIAL" else []),
            f"  {doc['n_tests']} test(s) l={','.join(map(str, GLOBAL_LAGS))}, BH q={FDR_Q} -> "
            f"{doc['n_links']} link(s); cells: {doc['cell_status']}",
            f"  novelty: {doc['novelty_verdicts'] or 'none classified'} "
            f"(classifier {doc['novelty']['classifier']})"]


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
    ap.add_argument("--no-global", action="store_true", help="skip the global-streams pass")
    ap.add_argument("--no-donate", action="store_true",
                    help="write both artifacts but donate no cell (a dry run that leaves files)")
    a = ap.parse_args(argv)
    doc = build(symbols=a.symbols, days=max(1, int(a.days)))
    for line in summary_lines(doc):
        print(line)
    if not a.dry_run:
        # THE CORE ARTIFACT LANDS FIRST: the global pass can run for its whole budget or be
        # killed by the cycle cap, and the core lab's hour must not be lost with it.
        _write_atomic(OUT, doc)
        print(f"-> {OUT} (core)")
    gdoc: dict[str, Any] | None = None
    if not a.no_global:
        try:
            gdoc = build_global(land=not a.dry_run)
        except Exception as exc:  # the core lab's artifact must not die with the global pass
            gdoc = {"status": "UNMEASURED", "why": f"global pass raised {type(exc).__name__}: "
                                                   f"{exc}", "candidates": []}
        gdoc["donation"] = ({"donated": 0, "why": "--dry-run / --no-donate"}
                            if a.dry_run or a.no_donate else donate_global(gdoc))
        for line in global_lines(gdoc):
            print(line)
        doc["global_streams"] = global_summary(gdoc)
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    _write_atomic(OUT, doc)
    print(f"-> {OUT}")
    if gdoc is not None:
        _write_atomic(GLOBAL_OUT, gdoc)
        print(f"-> {GLOBAL_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
