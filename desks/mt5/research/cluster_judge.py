"""CLUSTER JUDGE (P8-J1): the forward clocks at the Tier S bar judged as ONE hypothesis.

WHAT IT ANSWERS. On 2026-10-14 the tracked shadow state held about fifty forward clocks with a
large forward t at n >= 5, nearly all `overnight_gap_decay`, `spread_state` or `formula` on ZAR /
SEK / NOK / DKK / MXN / SGD crosses. One at a time they look like many edges; they are one
mechanism on correlated currencies, several of them byte-identical trade streams under different
expression names. This leg measures that BEFORE any promotion reads it.

THE BAR IS THE CANONICAL DEFLATED SHARPE, NOT A t CONSTANT. Every member is judged by
`libs.validation.dsr.deflated_sharpe_ratio(r, n_trials=bar_n(), variance_of_sharpes=1/(T-1))`
with a pass at DSR >= 0.95 -- the owner's T8 bar, N fixed by
`libs.research.trial_count_guard.bar_n()` and by nothing else. The canonical function carries the
sqrt(T-1) and the skew / kurtosis terms; "t about 2.84" is only its large-T, normal-returns limit
(the t it actually needs is 4.56 at n = 5, 3.45 at n = 10, 3.14 at n = 18, 2.89 at n = 100).
  * a clock whose OWN per-key ledger holds exactly its state row's forward trades is judged by the
    canonical function on those returns (basis `own_ledger_canonical`);
  * otherwise, when the state row carries n, exp_r and forward_t, its per-trade Sharpe is
    t / sqrt(n) (the engine's t is mean / (sd_ddof1 / sqrt n)) and the DSR is the canonical
    formula at NORMAL moments -- skew 0, kurtosis 3, because the row does not carry them -- and the
    basis says so (`state_row_normal_moments`); `test_cluster_judge` pins this form to the
    canonical function on returns whose moments are supplied;
  * a clock with neither is UNMEASURED. There is no fall-back to a t constant anywhere.
The coordinator's "t >= 2.84" list (its cut derived from the canonical bar's large-T limit,
never written down) is still enumerated and published beside the canonical pass list so the two
counts can be read together; only the canonical list is the cluster.

THE LEDGER IS THE CLOCK'S OWN. Read through `libs/research/forward_ledger.py`: a clock whose only
file is a legacy ledger several keys wrote is UNMEASURED_SHARED_LEDGER (named, counted, never read
from a sibling). Rows count only at or after the clock's OWN forward boundary (forward_start plus
broker offset, `decay_verdicts.forward_boundary` / `forward_rows`, the same cut shadow_forward
makes); a clock with no forward_start is UNMEASURED_NO_FORWARD_START.

DEPENDENCE, WITHOUT A BIAS TOWARD "FEWER BETS".
  * pairwise rho of daily R on the days BOTH clocks traded; fewer than MIN_OVERLAP_DAYS is an
    UNMEASURED pair, never a zero;
  * a pair is SIGNIFICANT when |rho| > z / sqrt(n_overlap), z Bonferroni over each clock's own
    k - 1 pairs at FAMILY_ALPHA, so k independent clocks come out INDEPENDENT about 95% of the
    time instead of almost never;
  * independent_bets = k^2 / (k + sum_{i != j} (rho_ij^2 - 1/(n_ij - 1))): the eigenvalue N_eff
    (sum lambda)^2 / sum lambda^2 with each rho^2 de-biased by its null expectation, capped at k.
    It is UNMEASURED when any member lacks a series or any pair is unmeasured (no clock is ever
    dropped to manufacture a number), and when the matrix's smallest eigenvalue is below
    MIN_EIGENVALUE;
  * clusters are the connected components of significant positive pairs.

ONE HYPOTHESIS, ONE TRIAL ON RECORD, AND IN-SAMPLE BY NAME. The equal-weight and inverse-variance
composite book is judged by the same canonical DSR. It reuses the forward data that selected the
members, so it is labelled IN_SAMPLE and can never by itself say the cluster clears; the
out-of-sample half needs book days after the published `selection_at` with membership frozen, and
is UNMEASURED until a consumer runs it. `trials_charged: 1` is a report field: nothing here writes a
trial ledger or moves a bar.

WHAT IT IS NOT. It sizes nothing, gates nothing, touches no roster, promoter or door.
`promotion_input(key)` is the reader an allocator or the E8 independence count may call later;
the sizing hook is the Max-growth thread's and is published as NOT_WIRED. Every flag is two-sided
information (GROWTH_GOVERNANCE Rule 2): INDEPENDENT says a clock IS a separate bet as loudly as
CONCENTRATED says it is not, and neither is a veto.

    python desks/mt5/research/cluster_judge.py        # writes reports/CLUSTER_JUDGE.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import forward_ledger as fl  # noqa: E402


def _fixed_bar_n(_requested: Any = None) -> int:
    """The owner's fixed T8 bar (N = 5), used only while `trial_count_guard.bar_n` is not on this
    tree; it ignores any count it is handed, exactly as the guard's does."""
    return 5


def _load_bar_n() -> Callable[..., int]:
    """THE BAR'S N is owned by libs/research/trial_count_guard.py (claude/trial-count-guard).
    Loaded by name so this file needs no edit (and no type-ignore) the day the guard lands."""
    try:
        fn: Callable[..., int] = importlib.import_module(
            "libs.research.trial_count_guard").bar_n
        return fn
    except (ImportError, AttributeError):  # pragma: no cover - depends on the branch
        return _fixed_bar_n


bar_n = _load_bar_n()
#: Published when the guard is absent from this tree (audit of 2ca3d7098, should-fix).
FALLBACK_HARD_5 = "FALLBACK_HARD_5"


def n_trials_source(fn: Callable[..., int] | None = None) -> str:
    """Where the bar's N actually came from: the guard's `bar_n`, or the hard-5 fallback.
    Never names the guard while the fallback is the function in use."""
    f = bar_n if fn is None else fn
    if f is _fixed_bar_n:
        return FALLBACK_HARD_5
    return f"{getattr(f, '__module__', '?')}.{getattr(f, '__name__', '?')}"

OUT = DESK / "reports" / "CLUSTER_JUDGE.json"
SHADOW = DESK / "reports" / "shadow"
SLEEVES_FILE = DESK / "data" / "sleeves.json"
CLOCK_LAW = DESK / "reports" / "CERTIFICATE_CLOCK_LAW.json"
#: The two places a clock's ledger lives: the live shadow directory and the tracked backup the
#: decay monitor also reads (`decay_monitor.SHADOW_LEDGER_DIRS`, the same two, in that order).
LEDGER_DIRS: tuple[Path, ...] = (SHADOW, ROOT / "backups" / "moat" / "shadow_ledgers")
LANE_FILES: dict[str, str] = {"main": "shadow_state.json", "qquant": "qquant_shadow_state.json",
                              "scalp": "scalp_shadow_state.json",
                              "external": "external_shadow_state.json"}
SCHEMA = 2

#: THE BAR: canonical DSR at bar_n() trials, per-cell null variance 1/(T-1), pass at 0.95.
DSR_PASS = 0.95
TIER_S_MIN_N = 5

#: FROZEN MEASUREMENT RULES (2026-10-14, before any cluster was scored with them).
MIN_OVERLAP_DAYS = 10          # a pair sharing fewer trading days is an UNMEASURED pair
FAMILY_ALPHA = 0.05            # per clock, Bonferroni over its k - 1 pairs
CONCENTRATED_RHO = 0.7         # a SIGNIFICANT pair at or above this is the same bet
DETECTABLE_RHO = 0.7           # INDEPENDENT needs every pair able to detect a rho this large
#: ...at this power (audit of 2ca3d7098, should-fix). A pair "detects" DETECTABLE_RHO only when
#: (z_alpha + z_beta) / sqrt(n_overlap) <= DETECTABLE_RHO; the bare significance threshold z/sqrt(n)
#: at DETECTABLE_RHO is only ~50% power. Approximation: rho_hat ~ N(rho, 1/n), the same one the
#: significance test uses; it overstates the variance under the alternative, so the power it
#: reports is a lower bound, never a claim of more.
DETECT_POWER = 0.80
MIN_EIGENVALUE = -0.1          # below this the pairwise matrix is not a correlation matrix
TOP_K_PAIRS = 50               # the pairs list is a summary plus the strongest k, never O(k^2)
CURRENCY_SHARE_FLAG = 0.25     # a currency carrying >= 25% of the cluster's legs is named

UNMEASURED = "UNMEASURED"
UNMEASURED_SHARED_LEDGER = fl.UNMEASURED_SHARED_LEDGER
UNMEASURED_NO_LEDGER = "UNMEASURED_NO_LEDGER"
UNMEASURED_NO_FORWARD_START = "UNMEASURED_NO_FORWARD_START"
UNMEASURED_TOO_FEW_ROWS = "UNMEASURED_TOO_FEW_LEDGER_ROWS"
DEAD_CLOCK = frozenset({"KILL", "KILLED", "RETIRED"})

FLAG_INDEPENDENT = "INDEPENDENT"
FLAG_MODERATE = "MODERATE"
FLAG_CONCENTRATED = "CONCENTRATED"
FLAG_DUPLICATE = "DUPLICATE_TRADES"

SIZING_HOOK = {
    "status": "NOT_WIRED",
    "owner": "Max-growth thread",
    "reader": "desks/mt5/research/cluster_judge.py::promotion_input",
    "note": ("information only: no size, door, gate, promoter or roster reads this today. A "
             "consumer reads both directions -- INDEPENDENT clocks are MORE separate bets inside "
             "the same heat (Rule 2), CONCENTRATED ones are one bet counted several times -- and "
             "whoever wires it owes the Rule-1 proof (robust forward E[log W] rises)."),
}


# ------------------------------------------------------------------------------- the bar
def canonical_dsr(returns: Sequence[float]) -> dict[str, Any]:
    """The canonical Tier S judgement on a return series: the repo's own
    `libs.validation.dsr.deflated_sharpe_ratio(r, n_trials=bar_n(), variance_of_sharpes=1/(T-1))`
    at 0.95 -- the same call shape as `tier_s_threshold.tier_s_passes` on
    claude/trial-count-guard, so the swap is one line once that branch lands."""
    import numpy as np

    from libs.validation.dsr import deflated_sharpe_ratio
    r = np.asarray(list(returns), dtype="float64")
    t_obs = len(r)
    if t_obs < TIER_S_MIN_N or float(r.std(ddof=1)) == 0.0:
        return {"dsr": None, "passed": None, "T": t_obs,
                "why": f"T={t_obs} < {TIER_S_MIN_N} or zero variance"}
    res = deflated_sharpe_ratio(r, n_trials=bar_n(), variance_of_sharpes=1.0 / (t_obs - 1),
                                threshold=DSR_PASS)
    return {"dsr": round(float(res.dsr), 6), "passed": bool(res.passed), "T": t_obs,
            "sr": round(float(res.sr_observed), 6), "sr0": round(float(res.sr0_threshold), 6)}


def dsr_from_moments(sr: float, t_obs: int, g3: float = 0.0, g4: float = 3.0) -> float:
    """The canonical DSR for a series KNOWN ONLY BY ITS MOMENTS (per-period Sharpe `sr`, length
    `t_obs`, skew `g3`, non-excess kurtosis `g4`), used only where the returns are absent.

    It is `deflated_sharpe_ratio`'s own two halves: the benchmark is the library's
    `expected_max_sharpe(bar_n(), 1/(T-1))`, and the PSR line is the expression
    `probabilistic_sharpe_ratio` evaluates on a sample's moments (this base has no moment entry
    point; `libs.validation.dsr.psr_from_moments` on claude/trial-count-guard replaces these two
    lines when it lands). `test_cluster_judge` pins it to the canonical function to 1e-12."""
    from scipy.stats import norm

    from libs.validation.dsr import expected_max_sharpe
    if t_obs < 3:
        return 0.0
    sr0 = expected_max_sharpe(n_trials=bar_n(), variance_of_sharpes=1.0 / (t_obs - 1))
    denom = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr ** 2
    if denom <= 0:
        return 0.0
    return float(norm.cdf((sr - sr0) * math.sqrt(t_obs - 1) / math.sqrt(denom)))


def required_t_normal(t_obs: int) -> float | None:
    """The forward t (Sharpe x sqrt(T)) the canonical bar needs at length `t_obs` under normal
    moments, by bisection on `dsr_from_moments`; reported so a reader sees what "about 2.84"
    really costs at small n."""
    if t_obs < 3:
        return None
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if dsr_from_moments(mid / math.sqrt(t_obs), t_obs) >= DSR_PASS:
            hi = mid
        else:
            lo = mid
    return round(hi, 3)


def comparison_t() -> float:
    """The coordinator's comparison list cut, "t about 2.84": the canonical bar's large-T limit,
    derived (never written down) and used ONLY to enumerate the comparison list."""
    return round(float(required_t_normal(10 ** 7) or 0.0), 2)


def judge_clock(row: Mapping[str, Any], trade_r: Sequence[float] | None) -> dict[str, Any]:
    """One clock under the canonical bar: its own returns when the ledger holds exactly the
    state row's forward trades, else the state row at normal moments, else UNMEASURED."""
    n = int(_num(row.get("n")) or 0)
    if trade_r is not None and len(trade_r) == n and n >= TIER_S_MIN_N:
        out = canonical_dsr(trade_r)
        if out.get("dsr") is not None:
            return {**out, "basis": "own_ledger_canonical"}
    t = _num(row.get("forward_t"))
    if n >= TIER_S_MIN_N and t is not None and _num(row.get("exp_r")) is not None and t != 0.0:
        sr = t / math.sqrt(n)
        d = dsr_from_moments(sr, n)
        return {"dsr": round(d, 6), "passed": d >= DSR_PASS, "T": n, "sr": round(sr, 6),
                "basis": "state_row_normal_moments",
                "basis_note": ("per-trade Sharpe t/sqrt(n) from the state row; skew 0 and "
                               "kurtosis 3 assumed because the row does not carry them")}
    return {"dsr": None, "passed": None, "T": n, "basis": UNMEASURED,
            "why": f"no own forward returns matching n={n} and no usable state t"}


# ------------------------------------------------------------------------------- small readers
def _read(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def currencies(symbol: str) -> list[str]:
    """The legs a symbol is exposed to: two legs for a six-letter FX/metal pair (XAUUSD -> XAU,
    USD), else the symbol itself as one leg."""
    s = str(symbol).upper()
    if len(s) == 6 and s.isalpha():
        return [s[:3], s[3:]]
    return [s]


def lane_rows(shadow: Path | None = None) -> tuple[dict[str, tuple[str, dict[str, Any]]],
                                                     set[str], dict[str, Any]]:
    """(live clocks key -> (lane, row), every clock key incl. dead ones, census)."""
    root = Path(shadow or SHADOW)
    rows: dict[str, tuple[str, dict[str, Any]]] = {}
    every: set[str] = set()
    census: dict[str, Any] = {"lanes_read": [], "lanes_absent": [], "dead_clocks_skipped": 0}
    for lane, name in LANE_FILES.items():
        doc = _read(root / name)
        if not isinstance(doc, dict):
            census["lanes_absent"].append(name)
            continue
        census["lanes_read"].append(name)
        items = list(doc.items())
        if isinstance(doc.get("sleeves"), dict):
            items += list(doc["sleeves"].items())
        for key, row in items:
            if not isinstance(row, dict) or "status" not in row:
                continue
            every.add(str(key))
            if str(row.get("status") or "").upper() in DEAD_CLOCK:
                census["dead_clocks_skipped"] += 1
                continue
            rows[str(key)] = (lane, row)
    return rows, every, census


def certificates_by_key(law: Any) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if isinstance(law, dict):
        for c in law.get("certificates") or []:
            if isinstance(c, dict) and c.get("key"):
                out[str(c["key"])].append(c)
    return dict(out)


def roster_by_certificate(roster: Any) -> dict[str, list[tuple[str, str]]]:
    """certificate cell -> [(roster name, status)] from data/sleeves.json."""
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    rows = roster.get("sleeves") if isinstance(roster, dict) else roster
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        cert = r.get("certificate")
        cell = cert.get("cell") if isinstance(cert, dict) else None
        if cell:
            out[str(cell)].append((str(r.get("name")), str(r.get("status") or "")))
    return dict(out)


# ------------------------------------------------------------------------------- the series
def _decay_verdicts() -> Any:
    import decay_verdicts as dv  # type: ignore[import-not-found]
    return dv


def _row_day(r: Mapping[str, Any]) -> str | None:
    for k in ("exit_time", "closed_at", "entry_time", "opened_at"):
        v = r.get(k)
        if isinstance(v, str) and v.strip():
            try:
                ts = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
            ts = ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)
            return ts.date().isoformat()
    return None


def own_forward_record(key: str, state: Mapping[str, Any], *, dirs: Iterable[Path],
                       shared: Mapping[str, Any]) -> dict[str, Any]:
    """The clock's forward record from its OWN ledger, cut at its OWN forward boundary.

    {status, where, trade_r (oldest first), daily (UTC exit date -> summed R)}; status is OWN or
    one of the UNMEASURED_* reasons, never a sibling's rows.
    """
    rows, status, where = fl.read_rows(str(key), tuple(dirs), shared)
    if rows is None:
        return {"status": (UNMEASURED_SHARED_LEDGER if status == fl.UNMEASURED_SHARED_LEDGER
                           else UNMEASURED_NO_LEDGER), "where": where}
    dv = _decay_verdicts()
    boundary = dv.forward_boundary(dict(state))
    if boundary is None:
        return {"status": UNMEASURED_NO_FORWARD_START, "where": where,
                "why": f"clock {key} has no readable forward_start: no row is forward evidence"}
    kept, notes = dv.forward_rows(list(rows), boundary)
    keyed: list[tuple[datetime, int, float, str]] = []
    for i, r in enumerate(kept):
        rv = _num(r.get("r_multiple"))
        day = _row_day(r)
        et = dv._entry_time(r)
        if rv is None or day is None or et is None:
            continue
        keyed.append((et, i, rv, day))
    keyed.sort()
    daily: dict[str, float] = defaultdict(float)
    for _et, _i, rv, day in keyed:
        daily[day] += rv
    return {"status": fl.OWN, "where": where, "trade_r": [x[2] for x in keyed],
            "daily": dict(sorted(daily.items())), "filter": notes,
            "boundary": boundary.isoformat()}


# ------------------------------------------------------------------------------- the members
def enumerate_clocks(clocks: Mapping[str, tuple[str, Mapping[str, Any]]], *,
                     certs: Mapping[str, list[dict[str, Any]]] | None = None,
                     roster: Mapping[str, list[tuple[str, str]]] | None = None,
                     shared: Mapping[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Every live clock at n >= TIER_S_MIN_N, described (judgement is added by `build`)."""
    out: list[dict[str, Any]] = []
    for key, (lane, row) in clocks.items():
        n = int(_num(row.get("n")) or 0)
        if n < TIER_S_MIN_N:
            continue
        parts = fl.parse_key(key)
        sym = parts.symbol if parts else key.split(".")[0]
        legacy = fl.legacy_name(key)
        sharers = list((shared or {}).get(legacy or "", []))
        cert_rows = list((certs or {}).get(key, []))
        roster_hits: list[tuple[str, str]] = []
        for c in cert_rows:
            roster_hits += list((roster or {}).get(str(c.get("certificate")), []))
        statuses = {s for _n, s in roster_hits}
        out.append({
            "key": key, "lane": lane, "symbol": sym,
            "family": parts.family if parts else "UNPARSED",
            "window": parts.window if parts else None, "currencies": currencies(sym),
            "n": n, "forward_t": _num(row.get("forward_t")), "exp_r": _num(row.get("exp_r")),
            "cum_r": _num(row.get("cum_r")),
            "first_entry": row.get("first_entry"), "last_entry": row.get("last_entry"),
            "forward_start": row.get("forward_start"),
            "broker_offset_h": row.get("broker_offset_h"), "clock_status": row.get("status"),
            "certificate": ([str(c.get("certificate")) for c in cert_rows] or None),
            "certificate_verdict": ([str(c.get("verdict")) for c in cert_rows] or None),
            "roster_status": ("LIVE" if "LIVE" in statuses else "STANDBY" if "STANDBY" in statuses
                              else (sorted(statuses)[0] if statuses else None)),
            "roster_names": [nm for nm, _s in roster_hits] or None,
            "legacy_ledger": legacy, "legacy_ledger_shared": len(sharers) > 1,
            "legacy_ledger_sharers": len(sharers) if len(sharers) > 1 else 0,
        })
    return out


def duplicate_groups(members: Iterable[Mapping[str, Any]]) -> dict[str, str | None]:
    """key -> group id for clocks whose state rows are identical in every summary the engine
    computes from its trades (symbol, n, cum_r to 1e-9, first and last entry): the same trades
    under two names. A row missing cum_r, first_entry or last_entry cannot be compared and maps
    to None (UNMEASURED), never into a group on (symbol, n) alone."""
    sig_to_keys: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    out: dict[str, str | None] = {}
    for m in members:
        cum, fe, le = m.get("cum_r"), m.get("first_entry"), m.get("last_entry")
        if cum is None or not fe or not le or not m.get("n"):
            out[str(m["key"])] = None
            continue
        sig_to_keys[(m.get("symbol"), m.get("n"), round(float(cum), 9), str(fe), str(le))
                    ].append(str(m["key"]))
    for i, (_sig, keys) in enumerate(sorted(sig_to_keys.items(), key=lambda kv: sorted(kv[1]))):
        for k in keys:
            out[k] = f"D{i:03d}"
    return out


# ------------------------------------------------------------------------------- dependence
def pair_z(k: int, alpha: float = FAMILY_ALPHA) -> float | None:
    """Two-sided z for one pair, Bonferroni over each clock's own k - 1 pairs."""
    if k < 2:
        return None
    from scipy.stats import norm
    return float(norm.ppf(1.0 - alpha / (2.0 * (k - 1))))


def detectable_rho(z: float, n: int, power: float = DETECT_POWER) -> float:
    """The smallest rho this pair finds with `power`: (z_alpha + z_beta) / sqrt(n)."""
    from scipy.stats import norm
    return (z + float(norm.ppf(power))) / math.sqrt(n)


def power_at(rho: float, z: float, n: int) -> float:
    """Power of the one-sided rho > z/sqrt(n) test at a true `rho`, rho_hat ~ N(rho, 1/n)."""
    from scipy.stats import norm
    return float(norm.cdf(rho * math.sqrt(n) - z))


def pair_corr(a: Mapping[str, float], b: Mapping[str, float], *, z: float | None = None,
              min_overlap: int = MIN_OVERLAP_DAYS) -> dict[str, Any]:
    """Pearson rho on the days BOTH clocks traded, with its significance threshold z/sqrt(n).
    Fewer than `min_overlap` days, or a constant leg, is UNMEASURED -- never a zero."""
    days = sorted(set(a) & set(b))
    out: dict[str, Any] = {"overlap_days": len(days)}
    if len(days) < min_overlap:
        out.update(status=UNMEASURED, rho=None,
                   why=f"{len(days)} shared trading day(s) < {min_overlap}")
        return out
    import numpy as np
    x = np.array([a[d] for d in days], dtype="float64")
    y = np.array([b[d] for d in days], dtype="float64")
    if float(x.std()) == 0.0 or float(y.std()) == 0.0:
        out.update(status=UNMEASURED, rho=None, why="a constant leg on the shared days")
        return out
    rho = float(np.corrcoef(x, y)[0, 1])
    thr = None if z is None else z / math.sqrt(len(days))
    out.update(status="MEASURED", rho=round(rho, 6),
               threshold=None if thr is None else round(thr, 6),
               detectable_rho=None if z is None else round(detectable_rho(z, len(days)), 6),
               power_at_detectable_rho=(None if z is None else
                                        round(power_at(DETECTABLE_RHO, z, len(days)), 6)),
               significant_pos=bool(thr is not None and rho > thr),
               significant_neg=bool(thr is not None and rho < -thr))
    return out


def n_eff(corr: Any, overlaps: Any = None) -> dict[str, Any]:
    """Effective independent bets of a correlation matrix.

    `n_eff_raw` = (sum lambda)^2 / sum lambda^2 = k^2 / (k + sum_{i != j} rho^2).
    `n_eff` de-biases each rho^2 by its null expectation 1/(n_ij - 1) (`overlaps` gives n_ij),
    then caps at k: sampling noise alone no longer reads as dependence. A smallest eigenvalue
    below MIN_EIGENVALUE means the pairwise matrix is not a correlation matrix: UNMEASURED.
    """
    import numpy as np
    m = np.asarray(corr, dtype="float64")
    k = int(m.shape[0]) if m.ndim == 2 else 0
    if k == 0:
        return {"n_eff": None, "n_eff_raw": None, "k": 0, "min_eigenvalue": None,
                "status": UNMEASURED, "why": "no clocks"}
    sym = (m + m.T) / 2.0
    lam = np.linalg.eigvalsh(sym)
    min_eig = float(lam.min())
    off = sym - np.eye(k)
    raw = float(k * k / (k + float((off ** 2).sum())))
    out: dict[str, Any] = {"k": k, "min_eigenvalue": round(min_eig, 6),
                           "n_eff_raw": round(raw, 4)}
    if min_eig < MIN_EIGENVALUE:
        out.update(n_eff=None, status=UNMEASURED,
                   why=f"smallest eigenvalue {min_eig:.3f} < {MIN_EIGENVALUE}")
        return out
    if overlaps is None:
        bias = np.zeros_like(off)
    else:
        ov = np.asarray(overlaps, dtype="float64")
        bias = np.where(ov > 1, 1.0 / np.maximum(ov - 1.0, 1.0), 0.0)
        np.fill_diagonal(bias, 0.0)
    excess = max(0.0, float((off ** 2 - bias).sum()))
    out.update(n_eff=round(min(float(k), k * k / (k + excess)), 4), status="MEASURED")
    return out


def components(keys: list[str], edges: Iterable[tuple[str, str]]) -> dict[str, int]:
    """Connected components of the significant-positive graph: key -> cluster number (1-based)."""
    parent = {k: k for k in keys}

    def _find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        if a in parent and b in parent:
            parent[_find(a)] = _find(b)
    first: dict[str, str] = {}
    for k in sorted(keys):
        first.setdefault(_find(k), k)
    num = {r: i + 1 for i, r in enumerate(sorted(first, key=lambda r: first[r]))}
    return {k: num[_find(k)] for k in keys}


def book_series(series: Mapping[str, Mapping[str, float]], weights: Mapping[str, float] | None
                = None) -> list[float]:
    """The weighted daily book on the union of trading days (zero on a clock's idle day)."""
    keys = [k for k in series if series[k]]
    if not keys:
        return []
    w = {k: float((weights or {}).get(k, 1.0)) for k in keys}
    tot = sum(w.values())
    if tot <= 0:
        return []
    days = sorted(set().union(*[set(series[k]) for k in keys]))
    return [sum(w[k] / tot * series[k].get(d, 0.0) for k in keys) for d in days]


def composite(series: Mapping[str, Mapping[str, float]], weights: Mapping[str, float] | None
              = None) -> dict[str, Any]:
    """The composite book judged by the canonical DSR, plus its t for reading. IN-SAMPLE."""
    book = book_series(series, weights)
    n = len(book)
    out: dict[str, Any] = {"days": n, "in_sample": True}
    if n < 2:
        return {**out, "t": None, "dsr": None, "why": "fewer than two book days"}
    mean = sum(book) / n
    var = sum((x - mean) ** 2 for x in book) / (n - 1)
    out["t"] = round(mean / math.sqrt(var / n), 4) if var > 0 else None
    return {**out, **{k: v for k, v in canonical_dsr(book).items() if k != "T"}}


def concentration(members: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Equal-weight exposure by currency leg and by family. `leg_share` sums to 1 over legs;
    `clock_share` is the share of clocks touching the currency (sums past 1: a pair has two)."""
    k = len(members)
    legs: Counter[str] = Counter()
    touch: Counter[str] = Counter()
    fams: Counter[str] = Counter()
    for m in members:
        cs = list(m.get("currencies") or [])
        for c in cs:
            legs[c] += 1
        for c in set(cs):
            touch[c] += 1
        fams[str(m.get("family"))] += 1
    n_legs = sum(legs.values())
    cur = {c: {"legs": legs[c], "leg_share": round(legs[c] / n_legs, 4) if n_legs else None,
               "clocks": touch[c], "clock_share": round(touch[c] / k, 4) if k else None}
           for c in sorted(legs, key=lambda c: (-legs[c], c))}
    fam = {f: {"clocks": v, "share": round(v / k, 4) if k else None}
           for f, v in sorted(fams.items(), key=lambda kv: (-kv[1], kv[0]))}
    named = [c for c, r in cur.items() if (r["leg_share"] or 0) >= CURRENCY_SHARE_FLAG]
    return {"by_currency": cur, "by_family": fam,
            "currencies_at_or_above_share": {"threshold": CURRENCY_SHARE_FLAG, "named": named},
            "top_family_share": next(iter(fam.values()))["share"] if fam else None}


def state_first_cut(members: Sequence[Mapping[str, Any]],
                    dup: Mapping[str, str | None]) -> dict[str, Any]:
    """What the in-memory state rows alone say, no ledger needed.

    `distinct_trade_streams_upper_bound` collapses identical-trade duplicate groups (rows that
    cannot be compared stay separate, so it is an UPPER bound on independent bets). The composite
    t bounds -- mean of member t if fully correlated, Stouffer if independent, for non-negative
    correlation -- are IN-SAMPLE first cuts, not a judgement.
    """
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for m in members:
        g = dup.get(str(m["key"]))
        groups[g if g is not None else f"U:{m['key']}"].append(m)
    best = [max(g, key=lambda x: float(x.get("forward_t") or 0.0)) for g in groups.values()]
    ts = [float(x["forward_t"]) for x in best if x.get("forward_t") is not None]
    dups = {g: sorted(str(x["key"]) for x in v) for g, v in groups.items()
            if len(v) > 1 and not g.startswith("U:")}
    return {"clocks": len(members), "distinct_trade_streams_upper_bound": len(groups),
            "duplicate_groups": dict(sorted(dups.items())),
            "clocks_in_duplicate_groups": sum(len(v) for v in dups.values()),
            "clocks_duplicate_unmeasured": sum(1 for m in members
                                               if dup.get(str(m["key"])) is None),
            "composite_t_bounds_distinct_streams_in_sample": (
                {"t_if_fully_correlated": round(sum(ts) / len(ts), 4),
                 "t_if_independent": round(sum(ts) / math.sqrt(len(ts)), 4)} if ts else None),
            "symbols": dict(Counter(str(m["symbol"]) for m in members).most_common()),
            "concentration": concentration(members),
            "concentration_distinct_streams": concentration(best)}


# ------------------------------------------------------------------------------- the report
def _brief(m: Mapping[str, Any]) -> dict[str, Any]:
    j = m["judgement"]
    return {"key": m["key"], "n": m["n"], "forward_t": m["forward_t"], "dsr": j.get("dsr"),
            "passed": j.get("passed"), "basis": j.get("basis")}


def _flag(kk: str, *, dup_g: str | None, dup_n: int, sig_pos: list[float], has_series: bool,
          n_unmeasured: int, detect: float | None, ledger_status: str) -> tuple[str, str | None]:
    """The two-sided concentration flag and, for UNMEASURED, why."""
    if dup_g is not None and dup_n > 1:
        return FLAG_DUPLICATE, None
    if sig_pos and max(sig_pos) >= CONCENTRATED_RHO:
        return FLAG_CONCENTRATED, None
    if sig_pos:
        return FLAG_MODERATE, None
    if not has_series:
        return UNMEASURED, f"no own series ({ledger_status})"
    if n_unmeasured > 0:
        return UNMEASURED, f"{n_unmeasured} unmeasured pair(s)"
    if detect is not None and detect > DETECTABLE_RHO:
        return UNMEASURED, (f"underpowered: at {DETECT_POWER:.0%} power the weakest pair could "
                            f"only detect rho > {detect:.2f}, above {DETECTABLE_RHO}")
    return FLAG_INDEPENDENT, None


def build(*, now: datetime | None = None, shadow: Path | None = None,
          sleeves_file: Path | None = None, clock_law: Path | None = None,
          ledger_dirs: tuple[Path, ...] | None = None) -> dict[str, Any]:
    t_now = now or datetime.now(tz=UTC)
    import numpy as np
    clocks, every, census = lane_rows(shadow)
    shared = fl.collisions(every)
    law = _read(Path(clock_law or CLOCK_LAW))
    roster_doc = _read(Path(sleeves_file or SLEEVES_FILE))
    dirs = tuple(ledger_dirs) if ledger_dirs is not None else LEDGER_DIRS
    candidates = enumerate_clocks(clocks, certs=certificates_by_key(law),
                                  roster=roster_by_certificate(roster_doc), shared=shared)

    # Each candidate: its own forward record, then the canonical judgement.
    records: dict[str, dict[str, Any]] = {}
    for m in candidates:
        rec = own_forward_record(m["key"], clocks[m["key"]][1], dirs=dirs, shared=shared)
        records[m["key"]] = rec
        m["judgement"] = judge_clock(clocks[m["key"]][1], rec.get("trade_r"))
    cmp_t = comparison_t()
    comparison = [m for m in candidates if (m["forward_t"] or 0.0) >= cmp_t]
    members = sorted((m for m in candidates if m["judgement"].get("passed") is True),
                     key=lambda m: (-float(m["judgement"]["dsr"]), -float(m["forward_t"] or 0.0),
                                    m["key"]))
    unjudged = sorted(m["key"] for m in candidates if m["judgement"].get("passed") is None)
    dup = duplicate_groups(members)

    # The members' own daily series.
    series: dict[str, dict[str, float]] = {}
    ledger: dict[str, dict[str, Any]] = {}
    for m in members:
        rec = records[m["key"]]
        row: dict[str, Any] = {"status": rec["status"], "where": rec.get("where")}
        if rec["status"] == fl.OWN:
            daily = rec.get("daily") or {}
            row.update(ledger_trading_days=len(daily), ledger_trades=len(rec.get("trade_r") or []),
                       state_n=m["n"], boundary=rec.get("boundary"))
            if len(daily) < 2:
                row["status"] = UNMEASURED_TOO_FEW_ROWS
            else:
                series[m["key"]] = daily
                if len(rec.get("trade_r") or []) != int(m["n"]):
                    row["note"] = ("the ledger's forward trades differ from the state row's n: "
                                   "the file is behind the clock (a stale copy); measured on "
                                   "what it holds")
        elif rec.get("why"):
            row["why"] = rec["why"]
        ledger[m["key"]] = row

    k = len(members)
    z = pair_z(k)
    keys = sorted(series)
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            pairs[(a, b)] = pair_corr(series[a], series[b], z=z)
    measured_pairs = [((a, b), p) for (a, b), p in pairs.items() if p.get("status") == "MEASURED"]
    n_unmeasured_pairs = k * (k - 1) // 2 - len(measured_pairs)
    if k and len(keys) == k and n_unmeasured_pairs == 0:
        idx = {kk: i for i, kk in enumerate(keys)}
        mat = np.eye(k)
        ov = np.zeros((k, k))
        for (a, b), p in measured_pairs:
            mat[idx[a], idx[b]] = mat[idx[b], idx[a]] = float(p["rho"])
            ov[idx[a], idx[b]] = ov[idx[b], idx[a]] = float(p["overlap_days"])
        neff = n_eff(mat, ov)
    else:
        neff = {"n_eff": None, "status": UNMEASURED, "k": k,
                "why": (f"{k - len(keys)} member(s) without an own series and "
                        f"{n_unmeasured_pairs} unmeasured pair(s): no clock is dropped to "
                        "manufacture a number")}
    sig_edges = [ab for ab, p in measured_pairs if p.get("significant_pos")]
    clusters = components(keys, sig_edges) if keys else {}

    comp_eq = composite({kk: series[kk] for kk in keys})
    inv: dict[str, float] = {}
    for kk in keys:
        v = list(series[kk].values())
        mu = sum(v) / len(v)
        var = sum((x - mu) ** 2 for x in v) / (len(v) - 1)
        if var > 0:
            inv[kk] = 1.0 / var
    comp_iv = composite({kk: series[kk] for kk in inv}, inv) if inv else {
        "dsr": None, "in_sample": True, "why": "no series with positive variance"}

    first_cut = state_first_cut(members, dup)
    dup_size = Counter(g for g in dup.values() if g is not None)

    promo: dict[str, dict[str, Any]] = {}
    for m in members:
        kk = m["key"]
        measured = [p for ab, p in measured_pairs if kk in ab]
        rhos = [float(p["rho"]) for p in measured]
        sig_pos = [float(p["rho"]) for p in measured if p.get("significant_pos")]
        detect = max((float(p["detectable_rho"]) for p in measured
                      if p.get("detectable_rho") is not None), default=None)
        power = min((float(p["power_at_detectable_rho"]) for p in measured
                     if p.get("power_at_detectable_rho") is not None), default=None)
        g = dup.get(kk)
        n_unm = (k - 1) - len(measured)
        flag, why = _flag(kk, dup_g=g, dup_n=dup_size[g] if g else 0, sig_pos=sig_pos,
                          has_series=kk in series, n_unmeasured=n_unm, detect=detect,
                          ledger_status=str(ledger[kk]["status"]))
        cid = clusters.get(kk)
        promo[kk] = {
            "independent_bets": neff.get("n_eff"),
            "independent_bets_status": neff.get("status"),
            "independent_bets_upper_bound_state": first_cut["distinct_trade_streams_upper_bound"],
            "max_pair_corr": round(max(rhos), 6) if rhos else None,
            "significant_positive_pairs": len(sig_pos),
            "measured_pairs": len(measured), "unmeasured_pairs": n_unm,
            "detectable_rho": None if detect is None else round(detect, 4),
            "detectable_rho_power": DETECT_POWER,
            # The weakest pair's MEASURED power at DETECTABLE_RHO (a lower bound): published so
            # the flag never claims more power than the overlaps carry.
            "power_at_detectable_rho": None if power is None else round(power, 4),
            "cluster_id": (f"C{cid:03d}" if cid is not None else None),
            "duplicate_group": g, "duplicate_group_size": dup_size[g] if g else None,
            "ledger_status": ledger[kk]["status"],
            "dsr": m["judgement"].get("dsr"), "dsr_basis": m["judgement"].get("basis"),
            "concentration_flag": flag, **({"flag_why": why} if why else {}),
            "currencies": m["currencies"], "family": m["family"],
        }

    rho_vals = sorted(float(p["rho"]) for _ab, p in measured_pairs)
    top = sorted(measured_pairs, key=lambda ab_p: (-abs(float(ab_p[1]["rho"])), ab_p[0]))
    counts = Counter(r["status"] for r in ledger.values())
    comp_dsr = comp_eq.get("dsr")
    in_sample_verdict = (UNMEASURED if comp_dsr is None
                         else "IN_SAMPLE_DSR_AT_OR_ABOVE_PASS" if comp_dsr >= DSR_PASS
                         else "IN_SAMPLE_DSR_BELOW_PASS")
    membership_hash = hashlib.sha256("\n".join(sorted(m["key"] for m in members))
                                     .encode("utf-8")).hexdigest()[:16]
    return {
        "generated_utc": t_now.isoformat(timespec="seconds"),
        "schema": SCHEMA,
        "organ": "desks/mt5/research/cluster_judge.py (hourly_cycle:cluster_judge)",
        "item": "P8-J1",
        "role": ("report only: judges the Tier-S forward clocks as ONE hypothesis and measures "
                 "their dependence; sizes nothing, gates nothing, mints no trial"),
        "bar": {"function": ("libs.validation.dsr.deflated_sharpe_ratio(r, n_trials=bar_n(), "
                             "variance_of_sharpes=1/(T-1))"),
                "n_trials": bar_n(), "n_trials_source": n_trials_source(),
                "pass": f"DSR >= {DSR_PASS}", "min_n": TIER_S_MIN_N,
                "state_row_basis": ("where own returns are absent: the same DSR at normal moments "
                                    "from the state row's t/sqrt(n) (skew 0, kurtosis 3)"),
                "required_t_at_normal_moments": {str(n): required_t_normal(n)
                                                 for n in (5, 10, 18, 30, 100)}},
        "enumeration": {
            "candidates_n_ge_min": len(candidates),
            "comparison_t_list": {
                "rule": (f"forward_t >= {cmp_t} (the canonical bar's large-T limit, derived) and "
                         f"n >= {TIER_S_MIN_N}: the coordinator's list; comparison only, never "
                         "a bar"),
                "t_cut": cmp_t,
                "count": len(comparison),
                "canonical_pass": sum(1 for m in comparison
                                      if m["judgement"].get("passed") is True),
                "canonical_fail": sorted((_brief(m) for m in comparison
                                          if m["judgement"].get("passed") is False),
                                         key=lambda b: (b["dsr"] or 0.0, b["key"]))},
            "canonical_pass_count": len(members),
            "canonical_unmeasured": unjudged,
            "canonical_pass_not_in_comparison": sorted(
                m["key"] for m in members if (m["forward_t"] or 0.0) < cmp_t),
            "basis_counts": dict(Counter(str(m["judgement"].get("basis")) for m in candidates)),
        },
        "rules": {"min_overlap_days": MIN_OVERLAP_DAYS, "pair_overlap": "days both clocks traded",
                  "significance": ("|rho| > z/sqrt(n_overlap), z two-sided Bonferroni over each "
                                   f"clock's k-1 pairs at alpha {FAMILY_ALPHA}"),
                  "pair_z": None if z is None else round(z, 4),
                  "concentrated_rho": CONCENTRATED_RHO, "detectable_rho": DETECTABLE_RHO,
                  "detectable_rho_power": DETECT_POWER,
                  "detectability": ("a pair detects rho when (z + z_beta)/sqrt(n_overlap) <= "
                                    "rho at the stated power; rho_hat ~ N(rho, 1/n), so the "
                                    "published power is a lower bound"),
                  "n_eff": ("k^2/(k + sum_{i!=j}(rho^2 - 1/(n_ij-1))), capped at k; UNMEASURED "
                            "with any member lacking a series or any pair unmeasured, or a "
                            f"smallest eigenvalue < {MIN_EIGENVALUE}"),
                  "clusters": "connected components of significant positive pairs",
                  "currency_share_flag": CURRENCY_SHARE_FLAG,
                  "daily_series": ("own-ledger rows at/after the clock's own forward boundary "
                                   "(decay_verdicts.forward_boundary/forward_rows), R summed per "
                                   "UTC exit date"),
                  "frozen": "2026-10-14, in code, before any cluster was scored with them"},
        "trials": {"trials_charged": 1, "charged_as": "one hypothesis for the whole cluster",
                   "trial_ledger_writes": 0,
                   "note": ("a report field: this leg writes no trial ledger and changes no "
                            "bar; the per-clock trials already on record are untouched")},
        "sizing_hook": SIZING_HOOK,
        "n_clocks": k,
        "ledger_counts": dict(sorted(counts.items())),
        "n_measured_series": len(series),
        "measured_share": round(len(series) / k, 4) if k else None,
        "n_unmeasured_shared_ledger": counts.get(UNMEASURED_SHARED_LEDGER, 0),
        "n_members_legacy_ledger_shared": sum(1 for m in members if m["legacy_ledger_shared"]),
        "measured": {
            "n_eff": neff,
            "clusters": {f"C{c:03d}": sorted(kk for kk, v in clusters.items() if v == c)
                         for c in sorted(set(clusters.values()))},
            "composite_equal_weight": comp_eq, "composite_inverse_variance": comp_iv,
        },
        "pairs_summary": {
            "pairs_possible": k * (k - 1) // 2, "pairs_measured": len(measured_pairs),
            "pairs_unmeasured": n_unmeasured_pairs,
            "significant_positive": len(sig_edges),
            "significant_negative": sum(1 for _ab, p in measured_pairs
                                        if p.get("significant_neg")),
            "rho_quantiles": ({q: round(rho_vals[min(len(rho_vals) - 1,
                                                    int(float(q) * len(rho_vals)))], 4)
                               for q in ("0.05", "0.25", "0.5", "0.75", "0.95")}
                              if rho_vals else None),
            "top_k": TOP_K_PAIRS,
        },
        "pairs_top": {f"{a} || {b}": p for (a, b), p in top[:TOP_K_PAIRS]},
        "cluster_verdict": {
            "hypothesis": "the canonical-pass forward clocks, taken together, earn positive R",
            "in_sample": {"verdict": in_sample_verdict, "dsr": comp_dsr, "t": comp_eq.get("t"),
                          "why": ("the composite reuses the forward data that selected its "
                                  "members; it can describe the cluster, it cannot clear it")},
            "out_of_sample": {
                "status": UNMEASURED, "selection_at": t_now.isoformat(timespec="seconds"),
                "membership_sha256_16": membership_hash,
                "rule": ("needs canonical DSR >= 0.95 on composite book days AFTER selection_at "
                         "with this membership frozen; no consumer may read a clearance before")},
            "first_cut_in_sample": first_cut["composite_t_bounds_distinct_streams_in_sample"],
        },
        "first_cut": first_cut,
        "sources": {**census, "shared_legacy_ledgers": len(shared),
                    "ledger_dirs": [str(d) for d in dirs],
                    "clock_law": str(clock_law or CLOCK_LAW),
                    "clock_law_read": isinstance(law, dict),
                    "roster": str(sleeves_file or SLEEVES_FILE),
                    "roster_read": roster_doc is not None},
        "members": [{**m, "ledger": ledger[m["key"]]} for m in members],
        "promotion_input": promo,
    }


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = Path(path or OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)
    return p


def promotion_input(key: str, path: Path | None = None) -> dict[str, Any]:
    """The per-clock row a later consumer (allocator, E8 independence count) may read. Never
    raises; an absent artifact or a clock outside the cluster is UNMEASURED by name."""
    doc = _read(Path(path or OUT))
    if not isinstance(doc, dict) or not isinstance(doc.get("promotion_input"), dict):
        return {"concentration_flag": UNMEASURED,
                "why": f"{Path(path or OUT).name} absent or unreadable"}
    row = doc["promotion_input"].get(key)
    if not isinstance(row, dict):
        return {"concentration_flag": UNMEASURED, "why": f"{key} is not in the Tier S cluster"}
    return {**row, "generated_utc": doc.get("generated_utc")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    doc = build()
    p = write(doc, a.out)
    en = doc["enumeration"]
    print(f"cluster judge: canonical DSR pass {en['canonical_pass_count']} (comparison t>="
          f"{en['comparison_t_list']['t_cut']}: {en['comparison_t_list']['count']}, of which "
          f"canonical pass "
          f"{en['comparison_t_list']['canonical_pass']}); ledgers {doc['ledger_counts']}; "
          f"N_eff {doc['measured']['n_eff'].get('n_eff')}; distinct streams <= "
          f"{doc['first_cut']['distinct_trade_streams_upper_bound']}")
    print(f"written: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
