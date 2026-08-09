"""Forecast calibration -- log every probability forecast, score it when the outcome resolves.

The constitution (Phase 9) requires continuously calibrating forecasts of Engineering ROI, alpha
survival, and deployment success via Bayesian updating, and detecting systematic bias. This is the
persistent scoring layer: each forecast (engineering-task p_success, alpha survival prob, leverage
confidence) is stored by id; when the outcome later resolves (task done, alpha survived/killed)
it is scored. Calibration = Brier score + a Beta(a,b) posterior over hit-rate + a bias term
(mean forecast - mean outcome). Until enough outcomes resolve it honestly reports insufficient data
-- no fabricated calibration. Pure/deterministic; the store is data/forecast_log.json.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG = Path("data/forecast_log.json")


def _load(store: Path | None = None) -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads((store or _LOG).read_text("utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return {"forecasts": {}}


def _save(d: dict[str, Any], store: Path | None = None) -> None:
    path = store or _LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, indent=2), "utf-8")


def log_forecast(key: str, p: float, kind: str, resolve_by: str | None = None,
                 claim: str | None = None, store: Path | None = None,
                 resolver: str | None = None) -> None:
    """Record (or refresh, while unresolved) a probability forecast keyed by a stable id.

    resolve_by (ISO date/datetime, optional) is the deadline by which the outcome must be scored
    -- an unresolved forecast past it is the 'never score yourself' defect check_calibration.py
    hunts: a desk that predicts but never grades its predictions has beliefs, not forecasts.

    ``resolver`` names WHO will grade this row -- a script path, or a one-line statement of the
    artifact the answer will be read off. Optional so no existing writer breaks, but supplying it
    is the only way a HAND-LOGGED forecast (no organ owns its namespace, claim not in the price
    shape the automatic scorer parses) escapes :func:`unowned`. A deadline with no grader is a
    row that will pin the L1.29 fence the day it comes due and can never be cleared -- R0260.

    ``store`` overrides the module-level store, and exists because R0254 measured what happens
    without it. An organ that takes a ``root`` and writes SOME of its outputs under that root
    while writing the rest through a module global is only half-parameterised: the caller thinks
    it has redirected the organ and has redirected half of it. run_calibration_probe.pose() was
    exactly that shape, so a unit test handing it a tmp_path got its questions file isolated and
    injected the matching forecast into the LIVE calibration store -- 68 fabricated rows, and all
    44 forecasts holding the L1.29 fence OVERDUE on 2026-08-05 were test fixtures. Isolation that
    depends on each caller remembering to monkeypatch a global is not isolation; passing the path
    the caller already supplied is.
    """
    d = _load(store)
    f = d["forecasts"].get(key, {})
    if f.get("resolved"):
        return                                            # never overwrite a scored forecast
    f.update({"p": round(float(p), 4), "kind": kind,
              "updated": datetime.now(tz=UTC).isoformat()})
    if resolve_by is not None:
        f["resolve_by"] = resolve_by
    if claim is not None:
        f["claim"] = claim
    if resolver is not None:
        f["resolver"] = resolver
    d["forecasts"][key] = f
    _save(d, store)


def get_forecast(key: str) -> dict[str, Any] | None:
    """Read-only copy of one stored forecast row, or None if never logged.

    Exists so writers can PRE-REGISTER a forecast exactly once -- checking for an existing row
    before logging keeps resolve_by FIXED at first assertion instead of rolling forward on every
    pass (a rolling deadline can never go overdue, which would blind the check_calibration
    fence) -- and can grade only rows that were actually pre-registered."""
    f = _load()["forecasts"].get(key)
    return dict(f) if f is not None else None


def overdue(now: datetime | None = None) -> list[dict[str, Any]]:
    """Unresolved forecasts past their resolve_by -- predictions the desk refused to grade."""
    now = now or datetime.now(tz=UTC)
    out = []
    for key, f in _load()["forecasts"].items():
        rb = f.get("resolve_by")
        if f.get("resolved") or not rb:
            continue
        try:
            due = datetime.fromisoformat(rb)
            due = due if due.tzinfo else due.replace(tzinfo=UTC)
        except ValueError:
            continue
        if due < now:
            out.append({"key": key, "p": f.get("p"), "resolve_by": rb,
                        "claim": f.get("claim", "")})
    return out


#: Key namespace (text before the first ':') -> the organ that grades it. R0260 named the failure
#: this exists to surface: a forecast namespace with a WRITER and no RESOLVER ages past its
#: deadline, `check_calibration` fires OVERDUE, and no organ on the desk can ever clear it -- so
#: the desk's #1 max_push item is pinned by construction and a permanently-red fence gets switched
#: off (L1.43). The four `calib-quiz-*` rows the row was raised for were eventually graded by
#: score_forecasts' price parser, but 13 hand-logged judgement forecasts now sit in the store with
#: the same shape and the earliest comes due 2026-08-14.
#:
#: A namespace ABSENT from this map is UNOWNED, never assumed fine -- the map can only ever
#: subtract from the orphan count for a namespace someone explicitly vouched for, so a new writer
#: cannot quietly inherit a grader it does not have. The paths are checked against disk by
#: :func:`unowned`, because a resolver that was deleted is exactly the regression worth catching.
ORGAN_RESOLVERS: dict[str, str] = {
    "probe": "scripts/run_calibration_probe.py",
    "rec": "scripts/recommendations.py",
    "eng": "scripts/research_cycle.py",
    "llm_trader": "scripts/resolve_llm_trader_book.py",
    "conviction": "scripts/score_forecasts.py",
}


def unowned(is_auto_resolvable: Any = None, root: Path | None = None,
            store: Path | None = None) -> list[dict[str, Any]]:
    """Unresolved forecasts that NOTHING on this desk can grade -- the orphan check.

    A row is owned if any of three things is true: it declares its own ``resolver``; its key
    namespace maps to a resolver script that still EXISTS on disk; or its claim is shaped so the
    automatic price scorer can parse it (``is_auto_resolvable``, supplied by the caller that owns
    those patterns -- omitted, every claim counts as unparseable, which over-reports rather than
    under-reports).

    Reported BEFORE the deadline on purpose. OVERDUE already fails once the date passes, and at
    that point the desk has no move left; this names the same rows while grading is still
    possible, with the days remaining, so the queue is actionable instead of terminal.
    """
    root = root or Path(".")
    out: list[dict[str, Any]] = []
    for key, f in _load(store)["forecasts"].items():
        if f.get("resolved") or not f.get("resolve_by"):
            continue
        if f.get("resolver"):
            continue
        ns = key.split(":")[0] if ":" in key else ""
        owner = ORGAN_RESOLVERS.get(ns)
        if owner and (root / owner).exists():
            continue
        claim = str(f.get("claim") or "")
        if is_auto_resolvable is not None and is_auto_resolvable(claim):
            continue
        out.append({"key": key, "kind": f.get("kind"), "resolve_by": f.get("resolve_by"),
                    "claim": claim[:110],
                    "why": (f"namespace {ns!r} maps to {owner} which is MISSING" if owner else
                            "no declared resolver, no organ owns this namespace, and the claim "
                            "is not in a shape the automatic price scorer can parse")})
    out.sort(key=lambda r: str(r["resolve_by"]))
    return out


def calibrated_confidence(raw_p: float) -> dict[str, Any]:
    """Shrink a raw probability by the desk's MEASURED bias -- the closed loop.

    THE GAP THIS CLOSES: report() computed a bias term for months and the docstring claimed it
    was 'applied as a shrinkage', but nothing consumed it -- so a systematically over-confident
    desk kept sizing on its raw, un-corrected estimates, which is exactly how a Kelly bettor
    over-bets into ruin. This subtracts the measured bias (over-confidence) from a raw forecast,
    N-gated: below 5 resolved outcomes it returns raw unchanged and says so, because a
    correction from noise is worse than no correction. Advisory by construction -- the caller
    decides whether to consume it; it never mutates state."""
    rep = report()
    bias = rep.get("bias")
    if bias is None:
        return {"raw": round(float(raw_p), 4), "adjusted": round(float(raw_p), 4),
                "applied": False, "why": rep["status"]}
    adj = min(1.0, max(0.0, float(raw_p) - float(bias)))   # bias>0 (over-confident) lowers p
    return {"raw": round(float(raw_p), 4), "adjusted": round(adj, 4),
            "applied": abs(bias) > 0.05, "bias": bias, "bias_label": rep.get("bias_label"),
            "why": f"desk is {rep.get('bias_label')} by {bias:+.3f} over {rep['n_resolved']} "
                   "resolved forecasts"}


def resolve(key: str, outcome: bool, store: Path | None = None) -> None:
    """Mark a forecast's outcome (True = the predicted event happened). Idempotent.

    ``store`` carries the same meaning as in :func:`log_forecast` -- a scorer handed a root must
    grade in the same store its writer logged into, or it grades a different desk's book.
    """
    d = _load(store)
    f = d["forecasts"].get(key)
    if not f or f.get("resolved"):
        return
    f["resolved"] = True
    f["outcome"] = 1.0 if outcome else 0.0
    f["resolved_at"] = datetime.now(tz=UTC).isoformat()
    _save(d, store)


def _claim_signature(f: dict[str, Any]) -> str:
    """The identity a duplicate-claim collapses on. ONE definition, used by both the numerator
    and the denominator, because two parallel filter chains over the same store is how they came
    to describe different populations in the first place (see :func:`eligible`)."""
    return " ".join(str(f.get("claim") or f["_key"]).split()).lower()


def eligible(forecasts: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows that COULD ever enter the calibration numerator -- resolved or not.

    THE DENOMINATOR THIS EXISTS TO BE. `_scoreable` draws the numerator from a filtered
    population (has resolve_by, kind is sizing, claim not already counted); `check_calibration`
    compared that numerator against the RAW store size. Measured 2026-08-05: 42 scoreable against
    a denominator of 172, of which 43 rows -- 33 retrospective `eng:*`, 9 non-sizing declines, 1
    deduped duplicate -- can never enter the numerator by construction. `42 < 172//4` fired BLIND
    and exited 2; on the matched population it is `42 < 129//4 = 32`, which does not fire. The
    L1.29 fence, the desk's own #1 max_push item, was pinned red by a category error.

    The direction is what makes it a defect rather than a quirk: every exclusion lowers the
    numerator AND raises the denominator, so the ratio is hit twice. Filtering retrospective rows
    was the fix for the calibration SIGN INVERSION that fed 6.00x leverage -- so the arithmetic
    punished the desk for the hygiene it was told to adopt. That is L1.53(4)'s named failure: a
    gauge improvable by doing less of the thing it exists to encourage.

    Numerator-inside-denominator is guaranteed structurally, not by inspection: `_scoreable`'s
    rows satisfy strictly more predicates than these, and both dedup on `_claim_signature`.
    """
    rows = [{**f, "_key": k} for k, f in forecasts.items() if f.get("resolve_by")]
    rows.sort(key=lambda f: str(f.get("updated") or ""))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for f in rows:
        sig = _claim_signature(f)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(f)
    return out


def _scoreable(forecasts: dict[str, Any]) -> list[dict[str, Any]]:
    """The resolved forecasts that carry real calibration information.

    TWO exclusions. Both remove rows that carry ZERO independent information, and both were
    silently inflating n and corrupting the bias:

    1. NO resolve_by -> NOT A FORECAST. L1.29(a) requires every consequential probability to be
       logged WITH a resolve-by date AT THE MOMENT IT IS ASSERTED. A row without one was graded
       retrospectively. In this store all 30 such rows were kind=engineering, ALL resolved TRUE,
       a median of 18ms after being logged -- the outcome was already known when the
       "prediction" was made. Pooling them drove the measured bias to -0.146 (under-confident)
       while the pre-registered rows say +0.176 (OVER-confident). run_conviction_trader fed that
       INVERTED correction straight into kelly_leverage, so a call its own model rated 0.44
       (edge<=0, correctly "no-edge") was inflated to 0.586 and sized at 6.00x. The risk cap
       bounds size; it cannot restore the SIGN of the edge, so the cap never saw this.

    2. DUPLICATE claims count ONCE. A re-asked question is not a second observation. The probe
       organ re-logged "Will S2USDT trade ABOVE 102.0 in 24 hours' time?" 17 times in 14h at a
       frozen threshold; all 17 resolve on the same print, so scoring them as 17 would clear the
       n>=5 noise gate on what is arithmetically ONE coin flip. Earliest instance wins.
    """
    res = [{**f, "_key": k} for k, f in forecasts.items()
           if f.get("resolved") and f.get("resolve_by")]
    res.sort(key=lambda f: str(f.get("updated") or ""))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for f in res:
        sig = _claim_signature(f)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(f)
    return out


#: Kinds that are NOT decisions the desk sized capital on. THIRD exclusion, same logic as the two
#: in _scoreable and the same failure mode if it were missing. A DECLINE -- the llm_trader sleeve's
#: counterfactual "what I would have done had I traded" -- is graded (R0123, so passing on
#: everything can no longer farm a clean record), but it must not enter THIS pool: report()'s bias
#: is consumed by calibrated_confidence, which shrinks the probability run_conviction_trader hands
#: to kelly_leverage. Declines are asserted mostly at p=0.50 and would swamp the handful of real
#: calls, moving LIVE POSITION SIZE on trades the desk never took. Scored in
#: libs.research.decline_value instead, where the statistic answers a question about the filter.
NON_SIZING_KINDS: tuple[str, ...] = ("discretionary_pass", "discretionary_pass_backfill")


def report(*, exclude_kinds: tuple[str, ...] = NON_SIZING_KINDS) -> dict[str, Any]:
    """Calibration over resolved forecasts: Brier, hit-rate posterior, bias. N-gated (honest).

    ``exclude_kinds`` defaults to the non-sizing kinds so the number that reaches live sizing keeps
    meaning what it has always meant. Pass ``exclude_kinds=()`` to see the whole store.
    """
    d = _load()
    forecasts = {k: f for k, f in d["forecasts"].items()
                 if str(f.get("kind") or "") not in exclude_kinds}
    resolved = [f for f in forecasts.values() if f.get("resolved")]
    res = _scoreable(forecasts)
    n = len(res)
    #: The population `n` is drawn from. Published so every consumer divides by the SAME
    #: population it counted (L1.57) instead of reaching for len(store) -- which is what pinned
    #: this fence BLIND. n_eligible >= n holds by construction; see :func:`eligible`.
    n_eligible = len(eligible(forecasts))
    excluded = {"retrospective": sum(1 for f in resolved if not f.get("resolve_by")),
                "duplicate_claim": len(resolved) - n
                - sum(1 for f in resolved if not f.get("resolve_by")),
                "non_sizing_kind": sum(1 for f in d["forecasts"].values()
                                       if f.get("resolved")
                                       and str(f.get("kind") or "") in exclude_kinds)}
    if n < 5:
        return {"n_resolved": n, "n_eligible": n_eligible, "n_excluded": excluded,
                "status": (f"insufficient outcomes ({n}/5) -- accumulating; "
                           f"{excluded['retrospective']} retrospective + "
                           f"{excluded['duplicate_claim']} duplicate row(s) are not scoreable"),
                "brier": None, "reliability": None, "bias": None, "hit_rate_posterior": None}
    brier = sum((f["p"] - f["outcome"]) ** 2 for f in res) / n
    bias = sum(f["p"] - f["outcome"] for f in res) / n     # + = over-confident, - = under-confident
    hits = sum(1 for f in res if (f["p"] >= 0.5) == (f["outcome"] >= 0.5))
    # Beta(1,1) prior updated with hits/misses -> posterior mean hit-rate
    a, b = 1 + hits, 1 + (n - hits)
    return {
        "n_resolved": n, "n_eligible": n_eligible, "n_excluded": excluded, "status": "calibrated",
        "brier": round(brier, 4), "reliability": round(1 - brier, 4),
        "bias": round(bias, 4),
        "bias_label": ("over-confident" if bias > 0.05 else
                       "under-confident" if bias < -0.05 else "well-calibrated"),
        "hit_rate_posterior": round(a / (a + b), 3),
        "note": ("Brier lower=better; reliability=1-Brier; bias>0 means forecasts were too high. "
                 "Applied as a shrinkage on future p_success when |bias| is material."),
    }
