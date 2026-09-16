"""POSTERIOR ALPHA -- every sleeve publishes a DISTRIBUTION over (mu, sigma, rho, decay).

A point Sharpe is the one number this desk can least afford to quote: a sleeve reaches a table
BECAUSE it measured well, so the estimate carries a winner's curse, and the curse is largest where
the sample is smallest -- the new clocks, the only kind that can still be promoted. `mean/std` on
7 trades and on 700 print the same way and mean entirely different things. This organ replaces
that single number, per live sleeve and per running forward clock, with the joint posterior:

    p(mu, sigma, rho, decay)

    mu     per-trade R, Normal-Inverse-Gamma posterior against a NO-EDGE prior
    sigma  the same posterior's dispersion, in R
    rho    the sleeve's measured daily-R correlation with the REST of the book
    decay  p_die_k from the hazard engine's health card (reports/ALPHA_HAZARD.json)

IT IS TWO-SIDED, AND THAT IS THE POINT (GROWTH_GOVERNANCE rules 1 and 2). A wide posterior is not
a licence to cut: it says the evidence has not EARNED size either way, and the honest reading of a
fat left tail on 5 trades is "unmeasured", never "dangerous". A tight posterior far from zero is a
reason to PRESS -- `p_positive` at 0.99 on 60 trades is exactly the evidence rule 2 exists to let
the allocator act on. Nothing here sizes, caps, vetoes, shrinks or gates: it publishes, the
allocator decides by dE[log W], and a number that is published but not fed cannot cut a lot.

THE MODEL. Conjugate Normal-Inverse-Gamma on per-trade R:

    mu | sigma^2 ~ N(mu0, sigma^2 / kappa0)        sigma^2 ~ Inv-Gamma(a0, b0)

    kappa_n = kappa0 + n
    mu_n    = (kappa0 * mu0 + n * xbar) / kappa_n
    a_n     = a0 + n / 2
    b_n     = b0 + S / 2 + kappa0 * n * (xbar - mu0)^2 / (2 * kappa_n)      S = sum (x - xbar)^2

with mu0 = 0 (PRIOR_MEAN) and kappa0 = n0 = 30 pseudo-trades (PRIOR_N0): a 5-trade sleeve at
+0.30R posts mu_n = +0.043, which is the shrinkage doing its job, and a 600-trade sleeve is barely
moved. The marginal posterior of mu is Student-t(nu = 2 a_n) at mu_n with scale^2 = b_n /
(a_n kappa_n) -- that gives mu_sd, the 5th/95th percentiles and P(mu > 0) in closed form. The
posterior PREDICTIVE for the next trade is Student-t at mu_n with scale^2 = b_n (kappa_n + 1) /
(a_n kappa_n), and `sharpe_pp = mu_n / sd_predictive` is the per-trade Sharpe WITH parameter
uncertainty inside it -- always below the sample Sharpe, by more the thinner the evidence.

READ `sigma_mean` WITH THE MODEL IN MIND. The b_n update carries a prior-conflict term: under a
no-edge prior worth 30 pseudo-trades, a large sample mean is itself evidence that sigma is large,
so a sleeve with a real edge reports a posterior sigma above its sample sd. That is the model
speaking, not a bug, and `sigma_sample` is published beside it so both readings are visible.

WHAT COUNTS AS EVIDENCE, AND WHAT IS ONLY A CLAIM -- `basis` says which, on every row.
  * `live_ledger`: fills in data/live_ledger.jsonl. A row stamped `r_multiple: 0.0` on a fill with
    non-zero P&L is an UNRECONSTRUCTED R, not an observation of zero edge, and is dropped and
    counted (`live_rows_dropped`) -- 141 of 151 rows in the shipped ledger are that shape.
  * `shadow_ledger_forward`: `phase == "forward"` rows of reports/shadow/ledger_<key>.json only.
    HISTORICAL rows predate pre-registration and the desk excludes them from every threshold.
  * `shadow_moments`: a clock with no ledger falls back to its (n, exp_r), dispersion IMPUTED from
    the family's pooled sigma. An imputed sigma is not a measured one, and a reader who cannot
    tell them apart is reading a story.
  * `prior_only`: nothing at all -- mu_mean = 0 with the prior's percentiles. UNMEASURED is a real
    answer (L1.28a); an absent input is never a clean verdict.

FAMILY POOLING. Every sleeve and clock of one mechanism pools into a family posterior on the same
model, by the within/between decomposition, so a moments-only clock contributes its (n, mean) like
any other. Each row publishes `mu_family` (the LEAVE-ONE-OUT family mean, so no sleeve shrinks
toward itself), `shrink_to_family` = n0 / (n + n0) and the blend `mu_shrunk_family`. The family
also supplies the prior sigma for a row with fewer than FAMILY_SIGMA_MIN_N trades -- measured from
MEASURED per-trade R only, never from another row's imputed dispersion.

NOT WIRED TO A CLOCK YET (III.16, stated rather than hidden): this ships with its test and no
scheduler leg -- it must be added as an hourly leg by the session that owns hourly_cycle, or it is
a defect. `python -m research.posterior_alpha` writes the artifact; `--dry-run` prints only.

numpy only (plus stdlib `math` for the Student-t special functions): no scipy, no pandas.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
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

SLEEVES = BASE / "data" / "sleeves.json"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_STATE = SHADOW_DIR / "shadow_state.json"
HAZARD = BASE / "reports" / "ALPHA_HAZARD.json"
OUT = BASE / "reports" / "POSTERIOR_ALPHA.json"

UNMEASURED = "UNMEASURED"
#: Prior pseudo-trades on mu. Bigger = harder shrink toward no edge for thin samples.
PRIOR_N0 = 30.0
PRIOR_MEAN = 0.0
#: Inverse-Gamma shape. 1.5 is deliberately weak (3 pseudo-observations of sigma^2) so the prior
#: sigma informs a 5-trade row and is invisible by 60; >1 keeps E[sigma^2] and the predictive sd
#: finite at n = 0.
PRIOR_A0 = 1.5
#: An R-multiple's natural unit: one unit of risk. Used when no family sigma is measurable.
DEFAULT_SIGMA = 1.0
FAMILY_SIGMA_MIN_N = 10
MIN_RHO_DAYS = 20
CREDIBLE_P = 0.90
CREDIBLE_N = 20
#: Only clocks the desk still runs forward carry a posterior; retired/refused ones are counted.
FORWARD_STATUSES = ("ACTIVE", "PROMOTION CANDIDATE")
#: MT5 truncates the order comment, so a live fill can carry a PREFIX of the sleeve name.
COMMENT_LIMIT = 27
_SESSIONS = frozenset({"asia", "london_am", "afternoon", "overlap", "ny", "all"})

RULE = ("a sleeve carries a posterior, never a point Sharpe: mu shrunk toward no edge by n0 "
        "pseudo-trades, sigma/rho/decay published beside it, UNMEASURED where the evidence is "
        "absent. This organ sizes nothing, caps nothing and vetoes nothing -- it publishes the "
        "distribution the allocator's dE[log W] is entitled to act on, in both directions.")


# --------------------------------------------------------------------------- tolerant readers
def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text("utf-8-sig").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def _day(value: Any) -> str | None:
    try:
        return datetime.fromisoformat(str(value).strip()).date().isoformat()
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ Student-t, in numpy/stdlib
def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz). Scalar; ~200 calls per pass."""
    tiny, qab, qap, qam = 1e-30, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (tiny if abs(d) < tiny else d)
    h, delta = d, 0.0
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            c = 1.0 + aa / c
            d = tiny if abs(d) < tiny else d
            c = tiny if abs(c) < tiny else c
            d = 1.0 / d
            delta = d * c
            h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t: float, nu: float) -> float:
    """P(T <= t) for Student-t with nu degrees of freedom."""
    if not math.isfinite(t):
        return 1.0 if t > 0 else 0.0
    tail = 0.5 * _betainc(nu / 2.0, 0.5, nu / (nu + t * t))
    return 1.0 - tail if t >= 0 else tail


def _t_ppf(p: float, nu: float) -> float:
    """Inverse Student-t CDF by bisection -- deterministic, no scipy."""
    lo, hi = -1e4, 1e4
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _t_cdf(mid, nu) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-11:
            break
    return 0.5 * (lo + hi)


# ------------------------------------------------------------------------------ the NIG update
def nig_update(n: float, mean: float, sumsq: float, *, n0: float = PRIOR_N0,
               mu0: float = PRIOR_MEAN, a0: float = PRIOR_A0,
               sigma0: float = DEFAULT_SIGMA) -> dict[str, float]:
    """Normal-Inverse-Gamma posterior parameters from a sample's (n, mean, sum of squares).

    `sumsq` is sum (x - xbar)^2, NOT sum x^2. b0 is set so the prior's E[sigma^2] is sigma0^2.
    """
    a0 = max(float(a0), 1.0 + 1e-9)
    b0 = (a0 - 1.0) * float(sigma0) ** 2
    n, n0 = max(float(n), 0.0), max(float(n0), 0.0)
    kappa_n = n0 + n
    mu_n = (n0 * float(mu0) + n * float(mean)) / kappa_n if kappa_n > 0 else float(mu0)
    conflict = (n0 * n * (float(mean) - float(mu0)) ** 2) / (2.0 * kappa_n) if kappa_n > 0 else 0.0
    return {"n": n, "mean": float(mean), "sumsq": float(sumsq), "kappa_n": kappa_n,
            "mu_n": mu_n, "a_n": a0 + n / 2.0, "b_n": b0 + float(sumsq) / 2.0 + conflict}


def summarise(post: dict[str, float]) -> dict[str, Any]:
    """Posterior mean/sd/percentiles of mu, P(mu > 0), E[sigma], and the predictive Sharpe."""
    kappa_n, mu_n, a_n, b_n = post["kappa_n"], post["mu_n"], post["a_n"], post["b_n"]
    nu = 2.0 * a_n
    ok = a_n > 0 and kappa_n > 0 and b_n > 0
    scale = math.sqrt(b_n / (a_n * kappa_n)) if ok else 0.0
    fat = math.sqrt(nu / (nu - 2.0)) if nu > 2.0 else float("inf")
    pred_sd = (math.sqrt(b_n * (kappa_n + 1.0) / (a_n * kappa_n)) * fat
               if ok and math.isfinite(fat) else 0.0)
    if scale <= 0:
        p_pos = 1.0 if mu_n > 0 else (0.0 if mu_n < 0 else 0.5)
    else:
        p_pos = _t_cdf(mu_n / scale, nu)
    return {
        "mu_mean": round(mu_n, 6),
        "mu_sd": round(scale * fat, 6) if math.isfinite(fat) else UNMEASURED,
        "mu_p05": round(mu_n + scale * _t_ppf(0.05, nu), 6),
        "mu_p95": round(mu_n + scale * _t_ppf(0.95, nu), 6),
        "p_positive": round(p_pos, 6),
        "sigma_mean": round(math.sqrt(b_n / (a_n - 1.0)), 6) if a_n > 1.0 else UNMEASURED,
        "sharpe_pp": round(mu_n / pred_sd, 6) if pred_sd > 0 else UNMEASURED,
    }


# -------------------------------------------------------------------------------- the evidence
@dataclass
class Obs:
    """One row's raw evidence: per-trade R, its daily sums, and where both came from."""

    name: str
    lane: str
    family: str
    symbol: str
    status: str = ""
    basis: str = "prior_only"
    r: list[float] = field(default_factory=list)
    days: dict[str, float] = field(default_factory=dict)
    n_moments: int = 0
    mean_moments: float = 0.0

    def add(self, value: float, day: str | None) -> None:
        self.r.append(value)
        if day:
            self.days[day] = self.days.get(day, 0.0) + value

    def moments(self, sigma_family: float) -> tuple[float, float, float]:
        """(n, mean, sum of squares). A moments-only clock has its dispersion IMPUTED."""
        if self.r:
            a = np.asarray(self.r, dtype=float)
            return float(a.size), float(a.mean()), float(((a - a.mean()) ** 2).sum())
        if self.n_moments > 0:
            return (float(self.n_moments), float(self.mean_moments),
                    max(self.n_moments - 1, 0) * float(sigma_family) ** 2)
        return 0.0, 0.0, 0.0


def _family_of_name(name: str) -> str:
    """`symbol_family_selector_p_hash` -> family; a bare `symbol_session` is the session lane."""
    parts = str(name).split("_p_", 1)[0].split("_")
    tail = "_".join(parts[1:-1])
    if len(parts) > 2 and tail:
        return "session_range_breakout" if tail in _SESSIONS else tail
    if len(parts) >= 2 and ("_".join(parts[1:]) in _SESSIONS or parts[-1] in _SESSIONS):
        return "session_range_breakout"
    return "unclassified"


def _family_of_key(key: str) -> str:
    """`SYMBOL.family.selector#params` -> family (shadow_cycle's convention); `SYMBOL.session`
    is the original session-window lane, which `promoter` names session_range_breakout."""
    parts = str(key).split("#", 1)[0].split(".")
    if len(parts) >= 3:
        return parts[1]
    if len(parts) == 2:
        return "session_range_breakout" if parts[1] in _SESSIONS else parts[1]
    return "unclassified"


def _join_live(token: str, names: list[str]) -> str:
    """The registry name a ledger row belongs to. An ambiguous truncation keeps its own row --
    dropping a real fill is worse than publishing it under the name the broker recorded."""
    if token in names:
        return token
    if len(token) >= COMMENT_LIMIT:
        hits = [n for n in names if n.startswith(token)]
        if len(hits) == 1:
            return hits[0]
    return token


def collect_live(notes: list[str], stats: dict[str, Any]) -> list[Obs]:
    """Registry rows (LIVE and STANDBY) plus any sleeve the live ledger alone knows about."""
    raw = _read_json(SLEEVES)
    rows = raw.get("sleeves") if isinstance(raw, dict) else raw
    obs: dict[str, Obs] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            name, status = str(row["name"]), str(row.get("status") or "")
            family = str(row.get("family") or "") or (
                "session_range_breakout" if row.get("window") else _family_of_name(name))
            obs[name] = Obs(name, "live" if status == "LIVE" else (status.lower() or "registry"),
                            family, str(row.get("symbol") or ""), status=status)
    else:
        notes.append(f"live sleeve registry unreadable or absent: {SLEEVES}")
    ledger = _read_jsonl(LIVE_LEDGER)
    if not ledger:
        notes.append(f"live fills unreadable or absent: {LIVE_LEDGER}")
    dropped, names = 0, list(obs)
    for row in ledger:
        token = str(row.get("sleeve") or "").strip()
        if not token or token.startswith("["):
            continue                                   # a broker comment, not a sleeve
        value = _num(row.get("r_multiple"))
        pl = _num(row.get("pl_quote")) or 0.0
        if row.get("r_unreconstructible") or value is None or (value == 0.0 and pl != 0.0):
            dropped += 1
            continue
        name = _join_live(token, names)
        found = obs.get(name)
        if found is None:
            found = obs[name] = Obs(name, "live", _family_of_name(name),
                                    str(row.get("symbol") or ""), status="LEDGER_ONLY")
            names.append(name)
        found.add(value, _day(row.get("time")))
        found.basis = "live_ledger"
    stats["live_rows_dropped"] = dropped
    return list(obs.values())


def collect_forward(notes: list[str], stats: dict[str, Any]) -> list[Obs]:
    """Forward clocks still running, with forward-phase ledger rows or their (n, exp_r) moments."""
    state = _read_json(SHADOW_STATE)
    if not isinstance(state, dict):
        notes.append(f"forward clocks unreadable or absent: {SHADOW_STATE}")
        return []
    skipped: dict[str, int] = defaultdict(int)
    out: list[Obs] = []
    for key, row in state.items():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        if status not in FORWARD_STATUSES:
            skipped[status or "UNKNOWN"] += 1
            continue
        obs = Obs(str(key), "forward", _family_of_key(key), str(key).split(".")[0], status=status)
        ledger = _read_json(SHADOW_DIR / f"ledger_{str(key).replace('.', '_')}.json", [])
        for trade in ledger if isinstance(ledger, list) else []:
            if not isinstance(trade, dict) or str(trade.get("phase") or "") != "forward":
                continue                               # historical rows predate pre-registration
            value = _num(trade.get("r_multiple"))
            if value is not None:
                obs.add(value, _day(trade.get("exit_time") or trade.get("entry_time")))
        if obs.r:
            obs.basis = "shadow_ledger_forward"
        else:
            n, exp_r = _num(row.get("n")), _num(row.get("exp_r"))
            if n and exp_r is not None:
                obs.n_moments, obs.mean_moments = int(n), exp_r
                obs.basis = "shadow_moments"
        out.append(obs)
    stats["skipped_clocks_by_status"] = dict(sorted(skipped.items()))
    return out


# ---------------------------------------------------------------------------------- rho, decay
def rho_vs_book(own: dict[str, float], book: dict[str, float]) -> tuple[float | str, int]:
    """Correlation of this sleeve's daily R with the REST of the book's, on ITS OWN days.

    A day the sleeve did not exist is not an observation of zero return for the sleeve (defect #4,
    libs/portfolio/robust_elog.SleeveEvidence.own_r), but the REST of the book genuinely earned
    zero on a day it did not trade -- flat is a portfolio-level fact. So the sleeve's own days set
    the calendar and the remainder is zero-filled on them.
    """
    days = sorted(own)
    if len(days) < MIN_RHO_DAYS:
        return UNMEASURED, len(days)
    mine = np.asarray([own[d] for d in days], dtype=float)
    rest = np.asarray([book.get(d, 0.0) - own[d] for d in days], dtype=float)
    if mine.std() <= 0 or rest.std() <= 0:
        return UNMEASURED, len(days)
    return round(float(np.corrcoef(mine, rest)[0, 1]), 6), len(days)


def _p_die(row: dict) -> float | None:
    """p_die_k from a hazard health card: a scalar, or a per-horizon map/list (longest k wins)."""
    value = row.get("p_die_k", row.get("p_die"))

    def _horizon(item: tuple[str, Any]) -> float:
        try:
            return float(str(item[0]).strip("kK_ "))
        except ValueError:
            return math.inf

    if isinstance(value, dict):
        vals = [_num(v) for _, v in sorted(value.items(), key=_horizon)]
    elif isinstance(value, (list, tuple)):
        vals = [_num(v) for v in value]
    else:
        return _num(value)
    live = [v for v in vals if v is not None]
    return live[-1] if live else None


def hazard_cards() -> tuple[dict[str, float], str]:
    """name -> p_die_k, read tolerantly: its producer (hazard_engine) ships beside this one."""
    raw = _read_json(HAZARD)
    if raw is None:
        return {}, "absent"
    rows: list[dict] = []
    if isinstance(raw, list):
        rows = [r for r in raw if isinstance(r, dict)]
    elif isinstance(raw, dict):
        for key in ("sleeves", "cards", "names", "hazards", "per_sleeve"):
            block = raw.get(key)
            if isinstance(block, list):
                rows.extend(r for r in block if isinstance(r, dict))
            elif isinstance(block, dict):
                for name, row in block.items():
                    rows.append({"name": name, **row} if isinstance(row, dict)
                                else {"name": name, "p_die_k": row})
    out: dict[str, float] = {}
    for row in rows:
        name = str(row.get("name") or row.get("sleeve") or row.get("key") or "")
        value = _p_die(row)
        if name and value is not None:
            out[name] = round(value, 6)
    return out, ("present" if out else "present_but_empty")


# ------------------------------------------------------------------------------------ the pass
def pool(parts: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Combine rows' (n, mean, sumsq) into one sample's, by the within/between decomposition:
    sum of squares about the pooled mean is each row's own plus n_i (mean_i - pooled)^2."""
    total = sum(n for n, _, _ in parts)
    if total <= 0:
        return 0.0, 0.0, 0.0
    mean = sum(n * m for n, m, _ in parts) / total
    return total, mean, sum(ss + n * (m - mean) ** 2 for n, m, ss in parts)


def run(n0: float = PRIOR_N0, write: bool = True) -> dict[str, Any]:
    """Every live sleeve and running forward clock, posterior-priced, written atomically."""
    notes: list[str] = []
    stats: dict[str, Any] = {}
    rows = collect_live(notes, stats) + collect_forward(notes, stats)
    decay, decay_state = hazard_cards()
    if decay_state != "present":
        notes.append(f"decay (p_die_k): hazard report {decay_state}: {HAZARD}")

    by_family: dict[str, list[int]] = defaultdict(list)
    for i, obs in enumerate(rows):
        by_family[obs.family or "unclassified"].append(i)
    # The family's sigma comes from MEASURED per-trade R only: imputing a row's dispersion from a
    # sigma that was itself imputed would manufacture evidence out of arithmetic.
    sigma_family: dict[str, float] = {}
    measured: dict[str, int] = {}
    for fam, members in by_family.items():
        sample = np.asarray([v for i in members for v in rows[i].r], dtype=float)
        sd = float(sample.std(ddof=1)) if sample.size >= 2 else 0.0
        sigma_family[fam], measured[fam] = (sd if sd > 0 else DEFAULT_SIGMA), int(sample.size)

    moments = [obs.moments(sigma_family.get(obs.family or "unclassified", DEFAULT_SIGMA))
               for obs in rows]
    book: dict[str, float] = defaultdict(float)
    for obs in rows:
        for day, value in obs.days.items():
            book[day] += value

    families: dict[str, Any] = {}
    for fam, members in sorted(by_family.items()):
        n_pooled, mean_pooled, sumsq_pooled = pool([moments[i] for i in members])
        families[fam] = {
            "n_members": len(members), "n_obs": int(n_pooled), "n_measured": measured[fam],
            "sigma_pooled": round(sigma_family[fam], 6) if measured[fam] >= 2 else UNMEASURED,
            **summarise(nig_update(n_pooled, mean_pooled, sumsq_pooled,
                                   n0=n0, sigma0=DEFAULT_SIGMA))}

    published: list[dict[str, Any]] = []
    for i, obs in enumerate(rows):
        fam = obs.family or "unclassified"
        n, mean, sumsq = moments[i]
        sigma0 = sigma_family.get(fam, DEFAULT_SIGMA) if n < FAMILY_SIGMA_MIN_N else DEFAULT_SIGMA
        summary = summarise(nig_update(n, mean, sumsq, n0=n0, sigma0=sigma0))
        others = pool([moments[j] for j in by_family[fam] if j != i])
        mu_family = (float(summarise(nig_update(*others, n0=n0, sigma0=DEFAULT_SIGMA))["mu_mean"])
                     if others[0] > 0 else PRIOR_MEAN)
        weight = n0 / (n + n0) if (n + n0) > 0 else 1.0
        rho, rho_days = rho_vs_book(obs.days, book)
        sample_sd = float(np.asarray(obs.r, dtype=float).std(ddof=1)) if len(obs.r) >= 2 else None
        published.append({
            "name": obs.name, "lane": obs.lane, "family": fam, "symbol": obs.symbol,
            "status": obs.status, "n": int(n), **summary,
            "sigma_sample": round(sample_sd, 6) if sample_sd is not None else UNMEASURED,
            "rho_book": rho, "rho_days": rho_days,
            "decay_p": decay.get(obs.name, decay.get(obs.symbol, decay.get(fam, UNMEASURED))),
            "edge_credible": bool(float(summary["p_positive"]) >= CREDIBLE_P and n >= CREDIBLE_N),
            "mu_family": round(mu_family, 6), "shrink_to_family": round(weight, 6),
            "mu_shrunk_family": round((1.0 - weight) * float(summary["mu_mean"])
                                      + weight * mu_family, 6),
            "basis": obs.basis,
        })
    published.sort(key=lambda r: (-float(r["p_positive"]), -int(r["n"]), str(r["name"])))

    if not any(isinstance(r["rho_book"], float) for r in published):
        notes.append(f"rho: no sleeve has {MIN_RHO_DAYS}+ daily observations against the book")
    if not published:
        notes.append("no live sleeve and no running forward clock: nothing to price")

    payload = {
        "at": datetime.now(UTC).isoformat(),
        "rule": RULE,
        "n_sleeves": len(published),
        "n_credible": sum(1 for r in published if r["edge_credible"]),
        "prior": {"n0": float(n0), "mean": PRIOR_MEAN, "a0": PRIOR_A0,
                  "sigma_default": DEFAULT_SIGMA,
                  "sigma_source": f"family pooled sigma when n < {FAMILY_SIGMA_MIN_N}"},
        "credible_rule": {"p_positive_min": CREDIBLE_P, "n_min": CREDIBLE_N},
        "sleeves": published,
        "families": families,
        "unmeasured": notes,
        "counts": stats,
        "inputs": {str(p): ("present" if p.exists() else "absent")
                   for p in (SLEEVES, LIVE_LEDGER, SHADOW_STATE, HAZARD)},
    }
    if write:
        _write_atomic(OUT, payload)
    return payload


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
    """The table a human reads: the strongest posteriors first, then the families."""
    prior = payload["prior"]
    lines = [f"POSTERIOR ALPHA  n_sleeves={payload['n_sleeves']}  "
             f"credible={payload['n_credible']}  "
             f"prior(n0={prior['n0']:g}, mean={prior['mean']:g})",
             f"{'sleeve':28s} {'lane':9s} {'n':>4s} {'mu':>8s} {'sd':>8s} {'p05':>8s} "
             f"{'p95':>8s} {'P(mu>0)':>8s} {'sigma':>8s} {'Spp':>8s} {'rho':>8s} {'decay':>8s} c"]
    for row in payload["sleeves"][:limit]:
        lines.append(
            f"{str(row['name'])[:28]:28s} {str(row['lane'])[:9]:9s} {int(row['n']):>4d} "
            f"{_cell(row['mu_mean'])} {_cell(row['mu_sd'])} {_cell(row['mu_p05'])} "
            f"{_cell(row['mu_p95'])} {_cell(row['p_positive'])} {_cell(row['sigma_mean'])} "
            f"{_cell(row['sharpe_pp'])} {_cell(row['rho_book'])} {_cell(row['decay_p'])} "
            f"{'Y' if row['edge_credible'] else '-'}")
    if len(payload["sleeves"]) > limit:
        lines.append(f"  ... {len(payload['sleeves']) - limit} more rows in the artifact")
    for fam, block in payload["families"].items():
        lines.append(f"  family {str(fam)[:26]:26s} members={block['n_members']:>4d} "
                     f"obs={block['n_obs']:>5d} measured={block['n_measured']:>5d} "
                     f"mu={_cell(block['mu_mean'])} P(mu>0)={_cell(block['p_positive'])} "
                     f"sigma={_cell(block['sigma_mean'])}")
    for note in payload["unmeasured"]:
        lines.append(f"  UNMEASURED  {note}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publish the joint posterior per sleeve and clock.")
    ap.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    ap.add_argument("--n0", type=float, default=PRIOR_N0, help="prior pseudo-trades on mu")
    ap.add_argument("--limit", type=int, default=25, help="rows in the printed table")
    args = ap.parse_args(argv)
    payload = run(n0=args.n0, write=not args.dry_run)
    print(render(payload, limit=args.limit))
    print("(dry run, nothing written)" if args.dry_run else f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
