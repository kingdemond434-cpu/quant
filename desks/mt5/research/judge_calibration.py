"""THE JUDGE CALIBRATION LOOP (LOOP_COVERAGE L2, 2026-11-25): forward results reach the judge.

THE GAP. Finding F2: outside-data join families keep 14-41% of their certified edge forward while
price-only families keep 95-100%, and nothing carries that back. The sealed judge certifies the
next join cell at the same bar the last one leaked through. This loop measures the judge against
the only evidence it could not have been fitted on -- MATURED forward clocks -- and writes what
it would change, per family and per gate, to an input file. It edits no judge.

WHAT IT MEASURES (`desks/mt5/reports/JUDGE_CALIBRATION.json`), per family and per gate:

  (a) forward-over-backtest: the clock's realised mean R per trade (`exp_r`, repriced at today's
      cost by the forward engine) over the certificate's own per-trade R (`expected_value.ev`),
      on clocks whose 14-day verdict has been taken (PROMOTION CANDIDATE = kept, KILL = failed).
      An ACTIVE clock is never read: a ratio on an immature clock is a ratio on its luck.
  (b) LEAKS: certified, then KILL forward. Per gate, a leak is attributed to the gate it cleared
      by the narrowest relative margin -- the gate that let it through most narrowly.
  (c) FALSE KILLS: rejected near-misses (the judge's own POWER_CURE roster) whose forward clock
      matured kept. The lane that gave near-misses a clock was deleted 2026-09-24
      (`shadow_admission.authorized_runs`), so on a tree where no rostered cell holds a matured
      clock this reads UNMEASURED with the missing input named -- never 0.

WHAT IT MAY PROPOSE (`desks/mt5/data/JUDGE_CALIBRATION_PROPOSALS.json`, before/after values):

  * per-family shrink PRIORS on the backtest edge, fitted on matured clocks, two-sided (P20: a
    family that beats its backtest gets a prior above 1; never a blanket haircut). A prior is
    the family's sum(forward)/sum(backtest), shrunk toward the pool of the OTHER families.
  * gate THRESHOLD moves in either direction. Tightening is judged on certified clocks (a leak
    it would have stopped against a keeper it would have killed, the keeper's R reported as
    missed growth); loosening needs forward outcomes on rejected cells and is UNMEASURED without
    them. At most one move per build (R3), the rest queued.
  * join-family certificates (a family that reads another instrument or a non-price dataset)
    flagged PROVISIONAL until the desk's point-in-time fence (`scripts/check_known_by_date.py`
    -> `reports/KNOWN_BY_DATE.json` certificate_inputs) audits its input provider clean.

RAILS. Every prior and every move is validated leave-one-family-out: a prior is published only
when predicting each of its family's clocks with that clock left out AND the pool fitted without
the family beats no prior (auto-revert, R5); a move only when thresholds picked without each
family beat the current bar on that family, summed. A published prior that does worse than no
prior on clocks that matured since it was published is reverted, the evidence kept. A random
share of eligible families is held as CONTROLS each ISO week and changed by nothing (R3). Every
candidate threshold evaluated is charged as a trial to each family in the sample through the
desk's ONE trial count (`data/judge_calibration_trials.jsonl`, joined by
`libs/research/experiment_ledger.lifetime`); the fixed 597 the judge charges is never touched.

CONSUMERS. The thresholds live in the SEALED judge (`research/gate_policy.py` constants and its
`ATTESTATION`, mirrored at `scripts/external_gauntlet.py`); `SEALED_CALL_SITE` names where a
principal-approved re-seal would read the proposals. Priors are published, not wired: the only
reader of a forward-vs-backtest shrink is the allocator's posterior (`libs/portfolio/
robust_elog._posterior_mu`), a money-path organ where no change is small.

CADENCE. Recomputes when a clock has matured since the last build, or when the last build is 7+
days old; every other pass re-stamps `checked_at` so the artifact never reads stale. No model
call, reads only artifacts.

    python desks/mt5/research/judge_calibration.py [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
SCHEMA = "judge_calibration/v1"
#: Forward verdicts the engine writes at maturity (`shadow_forward`, 14-day clause).
MATURED = {"PROMOTION CANDIDATE": "KEPT", "KILL": "FAILED"}
REBUILD_AFTER = timedelta(days=7)
#: Pseudo-clocks the family ratio is shrunk toward the other families' pool by.
PRIOR_K = 5.0
MIN_CLOCKS_FOR_PRIOR = 2
#: A move needs this many families and matured rows, or it is not even evaluated.
MIN_FAMILIES_FOR_MOVE = 3
MIN_ROWS_FOR_MOVE = 10
MAX_CANDIDATES = 5
MAX_MOVES_PER_BUILD = 1
CONTROL_FRACTION = 0.2
#: A backtest edge below this cannot carry a ratio (division by a rounding error).
MIN_BACKTEST_EDGE = 0.02
#: A join family whose forward leak rate exceeds the price-only families' by this, on at least
#: this many matured clocks each, has its clean PIT-fence reading reopened (F2's own symptom).
LEAK_GAP_REOPENS_AUDIT = 0.25
MIN_MATURED_FOR_CONTRADICTION = 10

#: gate -> (stage field, "higher" | "lower" is better, attestation key, default bar).
GATE_METRICS: dict[str, tuple[str, str, str | None, float | None]] = {
    "in_sample_screen": ("sharpe", "higher", None, None),
    "deflated_sharpe": ("dsr", "higher", "dsr_threshold", 0.95),
    "pbo": ("pbo", "lower", "pbo_max", 0.5),
    "reality_check_spa": ("p_value", "lower", "spa_alpha", 0.05),
    "cpcv": ("mean_oos_sharpe", "higher", "cpcv_mean_oos_sharpe_min_exclusive", 0.0),
    "walk_forward": ("oos_sharpe", "higher", "wf_min_oos_sharpe", 0.0),
    "stress_costs": ("exp_x3", "higher", None, 0.0),
    "lockbox": ("lockbox_sharpe", "higher", "lockbox_oos_sharpe_min", 0.0),
    "expected_value": ("ev", "higher", "expected_value_min_exclusive", 0.0),
}

#: Where a re-sealed judge would read the proposals; this loop never edits either file.
SEALED_CALL_SITE = {
    "file": "desks/mt5/research/gate_policy.py",
    "lines": "47-49 (DSR_THRESHOLD, PBO_THRESHOLD, SPA_ALPHA) and 95-117 (ATTESTATION: "
             "wf_min_oos_sharpe, cpcv_mean_oos_sharpe_min_exclusive, lockbox_oos_sharpe_min, "
             "expected_value_min_exclusive)",
    "mirror": "desks/mt5/scripts/external_gauntlet.py:62-64 (DSR_THRESHOLD, PBO_THRESHOLD, "
              "SPA_ALPHA)",
    "consequence": "any applied move re-versions ATTESTATION, so gate_policy.is_exact_policy "
                   "(line 222) refuses every certificate minted under the old bar until it is "
                   "re-minted -- a principal-approved re-seal, never a loop's act",
}
PRIOR_READER = {
    "status": "PUBLISHED_NOT_WIRED",
    "candidate": "libs/portfolio/robust_elog.py:_posterior_mu (the family-mean limb of the "
                 "allocator's hierarchical shrink)",
    "why": "the only forward-vs-backtest shrink reader is the allocator's posterior, a money-path "
           "organ where a change is not small; the priors are published for it to adopt",
}
#: axis_registry information sources that are a join of data the cell's own bars do not hold.
JOIN_AXIS_INFO = frozenset({"cross_asset", "positioning", "event", "macro", "carry",
                            "microstructure"})


@dataclass(frozen=True)
class Paths:
    out: Path
    proposals: Path
    trials: Path
    lanes: tuple[Path, ...]
    canons: tuple[Path, ...]
    near_miss: tuple[Path, ...]
    digest: Path
    known_by_date: Path

    @classmethod
    def under(cls, desk: Path) -> Paths:
        rep, data = desk / "reports", desk / "data"
        return cls(out=rep / "JUDGE_CALIBRATION.json",
                   proposals=data / "JUDGE_CALIBRATION_PROPOSALS.json",
                   trials=data / "judge_calibration_trials.jsonl",
                   lanes=tuple(rep / "shadow" / f for f in (
                       "shadow_state.json", "qquant_shadow_state.json",
                       "scalp_shadow_state.json")),
                   canons=(data / "UNIVERSAL_SURVIVORS.canon.json",
                           rep / "UNIVERSAL_SURVIVORS.json"),
                   near_miss=(rep / "FORWARD_CURE_ROSTER.json",
                              rep / "POWER_CURE_CANDIDATES.json"),
                   digest=rep / "GATE_VERDICT_DIGEST.json",
                   known_by_date=rep / "KNOWN_BY_DATE.json")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


# ------------------------------------------------------------------------------------- inputs
def read_clocks(paths: Paths) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Every forward clock row across the lanes, and which lane files were readable."""
    rows: dict[str, dict[str, Any]] = {}
    seen: dict[str, Any] = {}
    for p in paths.lanes:
        doc = _read(p)
        if not isinstance(doc, dict):
            seen[p.name] = UNMEASURED
            continue
        n = 0
        for key, row in doc.items():
            if isinstance(row, dict) and "status" in row and "n" in row:
                rows[str(key)] = row
                n += 1
        seen[p.name] = n
    return rows, seen


def default_key_fn() -> Callable[[Mapping[str, Any]], str] | None:
    """The forward engine's own clock key for a certificate's shadow_spec -- never re-derived."""
    try:
        import shadow_forward as sf
    except Exception:
        return None

    def key(spec: Mapping[str, Any]) -> str:
        return str(sf.sleeve_key(str(spec["symbol"]), str(spec["selector"]),
                                 dict(spec.get("params") or {}),
                                 str(spec.get("family") or "session_range_breakout"),
                                 str(spec.get("side") or "LONG")))
    return key


def _spec_rows(doc: Any) -> Iterable[tuple[str, dict[str, Any]]]:
    if not isinstance(doc, dict):
        return
    for block in ("survivors", "retired_certificates", "candidates", "rows"):
        rows = doc.get(block)
        if isinstance(rows, dict):
            for cid, row in rows.items():
                if isinstance(row, dict) and isinstance(row.get("shadow_spec"), dict):
                    yield str(cid), row


def index_by_clock(docs: Iterable[Any], key_fn: Callable[[Mapping[str, Any]], str]
                   ) -> dict[str, dict[str, Any]]:
    """clock key -> {cert_id, family, gates, backtest_edge} for every spec-carrying row."""
    out: dict[str, dict[str, Any]] = {}
    for doc in docs:
        for cid, row in _spec_rows(doc):
            spec = row["shadow_spec"]
            try:
                k = key_fn(spec)
            except Exception:
                continue
            gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
            ev = gates.get("expected_value") if isinstance(gates.get("expected_value"), dict) \
                else {}
            out.setdefault(k, {"cert_id": cid, "family": str(spec.get("family") or "?"),
                               "symbol": str(spec.get("symbol") or ""), "gates": gates,
                               "params": dict(spec.get("params") or {}),
                               "backtest_edge": _num(ev.get("ev"))})
    return out


def read_policy(paths: Paths) -> dict[str, Any] | None:
    """The attestation the certificates were minted under (the canon's own copy, no import)."""
    for p in paths.canons:
        doc = _read(p)
        if isinstance(doc, dict) and isinstance(doc.get("gate_policy"), dict):
            return dict(doc["gate_policy"])
    return None


def family_info(family: str) -> dict[str, Any]:
    """Information class from the judge's own buildability read and the axis registry."""
    out: dict[str, Any] = {}
    try:
        import gauntlet_buildability as gb
        out["information_class"] = gb.information_class(family)
    except Exception as exc:
        out["information_class"] = f"{UNMEASURED}: {type(exc).__name__}"
    try:
        import axis_registry as ar
        out["axis_information_source"] = ar.classify_family(family)[1]
    except Exception as exc:
        out["axis_information_source"] = f"{UNMEASURED}: {type(exc).__name__}"
    ic, ax = out["information_class"], out["axis_information_source"]
    known = [v for v in (ic, ax) if not str(v).startswith(UNMEASURED) and v != "UNKNOWN"]
    if not known:
        out["join"] = None
    else:
        out["join"] = ic in ("conditioned", "exogenous") or ax in JOIN_AXIS_INFO
    return out


def pit_status(family: str, kbd: Any) -> dict[str, Any]:
    """AUDITED when the known-by-date fence clears the family's certificate-input provider with
    no assumed lag; otherwise NOT_AUDITED with the reason; UNMEASURED without the artifact."""
    if not isinstance(kbd, dict) or not isinstance(kbd.get("certificate_inputs"), dict):
        return {"status": UNMEASURED,
                "why": "reports/KNOWN_BY_DATE.json absent or carries no certificate_inputs"}
    provs = kbd["certificate_inputs"].get("providers") or {}
    mine = {k: v for k, v in provs.items()
            if isinstance(v, dict) and family in (v.get("families") or [])}
    if not mine:
        return {"status": "NOT_AUDITED",
                "why": "no certificate-input provider declares this family "
                       "(libs/tiers/data_os.CERTIFICATE_INPUTS), so its join has no audited lag"}
    bad = {k: v.get("verdict") for k, v in mine.items() if v.get("verdict") != "OK"}
    assumed = sorted({s for v in mine.values() for s in (v.get("assumed") or [])})
    if bad or assumed:
        return {"status": "NOT_AUDITED", "providers": sorted(mine), "failing": bad,
                "assumed_lags": assumed,
                "why": "a provider fails the fence or rests on an ASSUMED publication lag"}
    return {"status": "AUDITED", "providers": sorted(mine),
            "at": kbd.get("generated_utc"), "basis": "scripts/check_known_by_date.py"}


# ---------------------------------------------------------------------------------- sample
def _metric(gates: Mapping[str, Any], gate: str) -> float | None:
    st = gates.get(gate)
    return _num(st.get(GATE_METRICS[gate][0])) if isinstance(st, dict) else None


def bars_of(policy: Mapping[str, Any] | None) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for gate, (_f, _d, key, default) in GATE_METRICS.items():
        v = _num((policy or {}).get(key)) if key else None
        out[gate] = v if v is not None else default
    return out


def _passes(m: float, bar: float, direction: str) -> bool:
    return m > bar if direction == "higher" else m < bar


def _margin(m: float, bar: float, direction: str) -> float:
    scale = max(abs(bar), 1e-3)
    return (m - bar) / scale if direction == "higher" else (bar - m) / scale


def build_sample(clocks: Mapping[str, Mapping[str, Any]], certs: Mapping[str, Mapping[str, Any]],
                 near: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Matured clocks joined to the certificate (or near-miss) that earned them."""
    rows: list[dict[str, Any]] = []
    unjoined: list[str] = []
    immature = 0
    no_edge = 0
    for key, st in clocks.items():
        outcome = MATURED.get(str(st.get("status") or ""))
        if outcome is None:
            immature += 1
            continue
        src, cert = ("certified", certs.get(key)) if key in certs else ("near_miss", near.get(key))
        if cert is None:
            # NO CERTIFICATE ROW ON THIS TREE, BUT THE CLOCK SAYS IT WAS CERTIFIED: it still
            # counts as a leak or a keeper (b); it carries no backtest figure for (a) and no
            # stage values for a threshold, and is counted as unjoined for both.
            unjoined.append(key)
            fam = family_of_key(key)
            if "PASS" not in str(st.get("gate_admission") or "") or fam is None:
                continue
            src, cert = "certified", {"cert_id": None, "family": fam, "gates": {},
                                      "backtest_edge": None}
        fwd, bt = _num(st.get("exp_r")), cert.get("backtest_edge")
        if fwd is None:
            no_edge += 1
            continue
        rows.append({"key": key, "cert_id": cert["cert_id"], "family": cert["family"],
                     "source": src, "outcome": outcome, "n": int(_num(st.get("n")) or 0),
                     "forward": fwd, "backtest": bt, "joined": cert["cert_id"] is not None,
                     "ratio": (fwd / bt) if bt is not None and bt >= MIN_BACKTEST_EDGE else None,
                     "gates": cert.get("gates") or {}})
    return {"rows": rows, "unjoined_matured": sorted(unjoined), "immature": immature,
            "matured_without_forward_edge": no_edge}


def family_of_key(key: str) -> str | None:
    """The family a clock key names, by the desk's one key parser (`certificate_truth`)."""
    try:
        from certificate_truth import parse_clock_key
    except Exception:
        return None
    parsed = parse_clock_key(key)
    return str(parsed["family"]) if parsed and parsed.get("family") else None


def matured_keys(clocks: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return sorted(k for k, st in clocks.items() if str(st.get("status") or "") in MATURED)


# ---------------------------------------------------------------------------------- priors
def _ratio_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [r for r in rows if r.get("ratio") is not None and r["source"] == "certified"]


def pooled_ratio(rows: Iterable[Mapping[str, Any]]) -> float | None:
    rs = list(rows)
    den = sum(float(r["backtest"]) for r in rs)
    return sum(float(r["forward"]) for r in rs) / den if rs and den > 0 else None


def fit_prior(rows: list[Mapping[str, Any]], pool: float | None, k: float = PRIOR_K) -> float:
    """The family's sum(forward)/sum(backtest) shrunk toward the other families' pool (1.0 when
    there is none) by k pseudo-clocks. Two-sided by construction: no floor, no ceiling."""
    anchor = 1.0 if pool is None else pool
    own = pooled_ratio(rows)
    if own is None:
        return anchor
    n = float(len(rows))
    return (n * own + k * anchor) / (n + k)


def _sq(rows: Iterable[Mapping[str, Any]], prior: float) -> float:
    return sum((float(r["forward"]) - prior * float(r["backtest"])) ** 2 for r in rows)


def validate_prior(fam_rows: list[Mapping[str, Any]], pool_without_family: float | None
                   ) -> dict[str, Any]:
    """Leave-one-family-out (the pool never sees the family) and leave-one-clock-out (each clock
    predicted by a prior fitted without it). Published only when that beats no prior."""
    err_prior = 0.0
    for i, r in enumerate(fam_rows):
        rest = fam_rows[:i] + fam_rows[i + 1:]
        err_prior += _sq([r], fit_prior(rest, pool_without_family))
    err_none = _sq(fam_rows, 1.0)
    n = len(fam_rows)
    return {"loo_sq_error_prior": round(err_prior / n, 6), "loo_sq_error_no_prior":
            round(err_none / n, 6), "beats_no_prior": err_prior < err_none}


def control_families(families: Iterable[str], now: datetime,
                     fraction: float = CONTROL_FRACTION) -> set[str]:
    """A deterministic random share held unchanged this ISO week (R3)."""
    fams = sorted(set(families))
    if len(fams) < 2 or fraction <= 0:
        return set()
    iso = now.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    ranked = sorted(fams, key=lambda f: hashlib.sha256(f"{week}|{f}".encode()).hexdigest())
    return set(ranked[:max(1, round(fraction * len(fams)))])


def priors(sample: list[dict[str, Any]], before: Mapping[str, Any], prev_keys: set[str],
           controls: set[str]) -> dict[str, dict[str, Any]]:
    rows = _ratio_rows(sample)
    fams = sorted({str(r["family"]) for r in rows})
    out: dict[str, dict[str, Any]] = {}
    for fam in fams:
        own = [r for r in rows if r["family"] == fam]
        pool = pooled_ratio(r for r in rows if r["family"] != fam)
        prev = before.get(fam) if isinstance(before.get(fam), dict) else {}
        prior_before = _num(prev.get("prior")) if prev.get("published") else None
        rec: dict[str, Any] = {
            "n_clocks": len(own), "forward_over_backtest": round(pooled_ratio(own) or 0.0, 4),
            "pool_without_family": None if pool is None else round(pool, 4),
            "prior_before": prior_before, "control": fam in controls}
        eff_before = 1.0 if prior_before is None else prior_before
        rec["forward_error_before"] = round(_sq(own, eff_before) / len(own), 6)
        # R5: a published prior judged on the clocks that matured AFTER it was published
        fresh = [r for r in own if r["key"] not in prev_keys]
        if prior_before is not None and fresh and _sq(fresh, prior_before) > _sq(fresh, 1.0):
            rec.update({"published": False, "prior": None, "status": "REVERTED",
                        "why": f"worse than no prior on {len(fresh)} clock(s) matured since it "
                               "was published; evidence kept in the history"})
            rec["forward_error_after"] = round(_sq(own, 1.0) / len(own), 6)
            out[fam] = rec
            continue
        if len(own) < MIN_CLOCKS_FOR_PRIOR:
            rec.update({"published": prior_before is not None, "prior": prior_before,
                        "status": "TOO_FEW_CLOCKS",
                        "why": f"{len(own)} matured clock(s) < {MIN_CLOCKS_FOR_PRIOR}"})
            rec["forward_error_after"] = rec["forward_error_before"]
            out[fam] = rec
            continue
        fitted = fit_prior(own, pool)
        val = validate_prior(own, pool)
        rec.update({"fitted": round(fitted, 4), "validation": val})
        if fam in controls:
            rec.update({"published": prior_before is not None, "prior": prior_before,
                        "status": "CONTROL", "why": "held unchanged this week as a control"})
            rec["forward_error_after"] = rec["forward_error_before"]
        elif not val["beats_no_prior"]:
            rec.update({"published": False, "prior": None, "status": "REJECTED_LOFO",
                        "why": "leave-one-out error is worse than no prior: not published"})
            rec["forward_error_after"] = val["loo_sq_error_no_prior"]
        else:
            rec.update({"published": True, "prior": round(fitted, 4), "status": "PUBLISHED",
                        "side": "above_1" if fitted > 1.0 else "below_1"})
            rec["forward_error_after"] = val["loo_sq_error_prior"]
        out[fam] = rec
    return out


# ------------------------------------------------------------------------------ thresholds
def _gate_rows(sample: list[dict[str, Any]], gate: str, bars: Mapping[str, float | None]
               ) -> list[dict[str, Any]]:
    """Rows that can speak to this gate: every certificate, and the near-misses whose ONLY
    failure under today's bars is this gate (so this gate alone decides their admission)."""
    out = []
    for r in sample:
        m = _metric(r["gates"], gate)
        if m is None:
            continue
        if r["source"] == "near_miss":
            others = []
            for g in GATE_METRICS:
                if g == gate or bars.get(g) is None:
                    continue
                v = _metric(r["gates"], g)
                if v is not None:
                    others.append(_passes(v, float(bars[g]), GATE_METRICS[g][1]))
            if not all(others):
                continue
        out.append({"family": r["family"], "kept": r["outcome"] == "KEPT", "m": m,
                    "forward": r["forward"], "now": r["source"] == "certified"})
    return out


def _err(rows: Iterable[Mapping[str, Any]], admit: Callable[[Mapping[str, Any]], bool]) -> int:
    return sum(1 for r in rows if admit(r) != r["kept"])


def evaluate_gate(gate: str, rows: list[dict[str, Any]], bar: float | None) -> dict[str, Any]:
    """Two-sided candidate bars, chosen leave-one-family-out against today's bar."""
    _field, direction, _k, _d = GATE_METRICS[gate]
    near = [r for r in rows if not r["now"]]
    rec: dict[str, Any] = {
        "before": bar, "after": bar, "direction": direction, "n_rows": len(rows),
        "loosening": ({"status": UNMEASURED,
                       "why": "no rejected cell holds a matured forward clock: loosening needs "
                              "forward outcomes on cells this gate killed (the false-kill input)"}
                      if not near else {"status": "MEASURED", "n_near_miss": len(near)})}
    fams = sorted({r["family"] for r in rows})
    if bar is None:
        rec.update({"move": "NONE", "why": "the attestation carries no numeric bar for this gate",
                    "candidates": []})
        return rec
    if len(fams) < MIN_FAMILIES_FOR_MOVE or len(rows) < MIN_ROWS_FOR_MOVE:
        rec.update({"move": "NONE", "candidates": [],
                    "why": f"{len(fams)} famil(ies), {len(rows)} row(s) < "
                           f"{MIN_FAMILIES_FOR_MOVE} / {MIN_ROWS_FOR_MOVE}: not evaluated"})
        return rec
    vals = sorted({round(r["m"], 6) for r in rows if round(r["m"], 6) != round(bar, 6)})
    if len(vals) > MAX_CANDIDATES:
        step = (len(vals) - 1) / (MAX_CANDIDATES - 1)
        vals = sorted({vals[round(i * step)] for i in range(MAX_CANDIDATES)})
    rec["candidates"] = vals

    def admit_at(t: float | None) -> Callable[[Mapping[str, Any]], bool]:
        if t is None:
            return lambda r: bool(r["now"])
        # a bar ON an observed value admits that value (the candidate is the edge, inclusive)
        return (lambda r: r["m"] >= t) if direction == "higher" else (lambda r: r["m"] <= t)

    def best(train: list[dict[str, Any]]) -> float | None:
        choice, score = None, _err(train, admit_at(None))
        for t in vals:
            e = _err(train, admit_at(t))
            if e < score:
                choice, score = t, e
        return choice

    lofo_new = lofo_old = 0
    for f in fams:
        held = [r for r in rows if r["family"] == f]
        t = best([r for r in rows if r["family"] != f])
        lofo_new += _err(held, admit_at(t))
        lofo_old += _err(held, admit_at(None))
    t_all = best(rows)
    rec.update({"error_before": _err(rows, admit_at(None)), "lofo_error_before": lofo_old,
                "lofo_error_after": lofo_new})
    if t_all is None or lofo_new >= lofo_old:
        rec.update({"move": "NONE", "why": "no candidate bar beats today's leave-one-family-out"})
        return rec
    tighten = (t_all > bar) if direction == "higher" else (t_all < bar)
    killed = [r for r in rows if r["now"] and not admit_at(t_all)(r) and r["kept"]]
    rec.update({"move": "TIGHTEN" if tighten else "LOOSEN", "after": t_all,
                "error_after": _err(rows, admit_at(t_all)),
                "missed_growth": {"keepers_rejected": len(killed),
                                  "forward_r_per_trade_forgone": round(
                                      sum(float(r["forward"]) for r in killed), 6)}})
    return rec


def thresholds(sample: list[dict[str, Any]], bars: Mapping[str, float | None]
               ) -> dict[str, dict[str, Any]]:
    out = {g: evaluate_gate(g, _gate_rows(sample, g, bars), bars.get(g)) for g in GATE_METRICS}
    movers = sorted((g for g, r in out.items() if r.get("move") in ("TIGHTEN", "LOOSEN")),
                    key=lambda g: out[g]["lofo_error_after"] - out[g]["lofo_error_before"])
    for g in movers[MAX_MOVES_PER_BUILD:]:
        out[g].update({"move": "QUEUED", "queued_after": out[g]["after"],
                       "after": out[g]["before"],
                       "why": "one move per build (R3): attributable, the rest wait"})
    return out


# ------------------------------------------------------------------------------ per family
def per_gate_counts(sample: list[dict[str, Any]], bars: Mapping[str, float | None],
                    digest: Any, near_status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    certs = [r for r in sample if r["source"] == "certified"]
    leaks = [r for r in certs if r["outcome"] == "FAILED"]
    attributed: dict[str, int] = {}
    for r in leaks:
        best_g, best_m = None, None
        for g, bar in bars.items():
            m = _metric(r["gates"], g)
            if m is None or bar is None:
                continue
            mg = _margin(m, float(bar), GATE_METRICS[g][1])
            if best_m is None or mg < best_m:
                best_g, best_m = g, mg
        if best_g:
            attributed[best_g] = attributed.get(best_g, 0) + 1
    ledger = digest.get("ledger") if isinstance(digest, dict) else None
    rej = (ledger or {}).get("rejections_by_terminal_gate_id") if isinstance(ledger, dict) \
        else None
    out: dict[str, dict[str, Any]] = {}
    for g in GATE_METRICS:
        fk = _false_kills([r for r in sample if r["source"] == "near_miss"], g, bars,
                          near_status)
        out[g] = {"bar": bars.get(g), "certified_matured": len(certs),
                  "leaks_narrowest_here": attributed.get(g, 0),
                  "rejections_ledger": (int(rej.get(g, 0)) if isinstance(rej, dict)
                                        else UNMEASURED),
                  "false_kills": fk}
    return out


def _false_kills(near: list[dict[str, Any]], gate: str, bars: Mapping[str, float | None],
                 near_status: dict[str, Any]) -> Any:
    if not near:
        return {"status": UNMEASURED, "why": near_status.get("why")}
    mine = [r for r in near if (m := _metric(r["gates"], gate)) is not None
            and bars.get(gate) is not None
            and not _passes(m, float(bars[gate]), GATE_METRICS[gate][1])]
    return {"status": "MEASURED", "near_miss_matured": len(mine),
            "false_kills": sum(1 for r in mine if r["outcome"] == "KEPT"),
            "true_kills": sum(1 for r in mine if r["outcome"] == "FAILED")}


def near_miss_status(paths: Paths, near: Mapping[str, Any], sample: list[dict[str, Any]]
                     ) -> dict[str, Any]:
    present = [p.name for p in paths.near_miss if p.exists()]
    n_matured = sum(1 for r in sample if r["source"] == "near_miss")
    if not present:
        return {"status": UNMEASURED, "roster": None,
                "why": "no near-miss roster on this tree (reports/FORWARD_CURE_ROSTER.json, "
                       "reports/POWER_CURE_CANDIDATES.json): false kills need the judge's "
                       "rejected near-misses AND a matured forward clock on each"}
    if n_matured == 0:
        return {"status": UNMEASURED, "roster": present, "near_miss_cells": len(near),
                "why": f"0 of {len(near)} rostered near-miss cell(s) holds a matured forward "
                       "clock: the lane that enrolled them was deleted 2026-09-24 "
                       "(research/shadow_admission.py authorized_runs), so no rejected cell "
                       "is ever measured forward"}
    return {"status": "MEASURED", "roster": present, "near_miss_cells": len(near),
            "near_miss_matured": n_matured}


def per_family(sample: list[dict[str, Any]], clocks: Mapping[str, Mapping[str, Any]],
               certs: Mapping[str, Mapping[str, Any]], kbd: Any, prior_rows: Mapping[str, Any],
               moves: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fams = sorted({str(c["family"]) for c in certs.values()} | {r["family"] for r in sample})
    infos = {f: family_info(f) for f in fams}
    price = [r for r in sample if r["source"] == "certified"
             and infos[r["family"]].get("join") is False]
    price_leak = (sum(1 for r in price if r["outcome"] == "FAILED") / len(price)
                  if len(price) >= MIN_MATURED_FOR_CONTRADICTION else None)
    out: dict[str, Any] = {}
    provisional: list[dict[str, Any]] = []
    for fam in fams:
        rows = [r for r in sample if r["family"] == fam and r["source"] == "certified"]
        kept = sum(1 for r in rows if r["outcome"] == "KEPT")
        failed = len(rows) - kept
        info = infos[fam]
        pit = pit_status(fam, kbd) if info.get("join") else {"status": "NOT_APPLICABLE"}
        if info.get("join") is None:
            cert_status = UNMEASURED
        elif info["join"] and pit["status"] != "AUDITED":
            cert_status = "PROVISIONAL"
        elif (info["join"] and price_leak is not None
              and len(rows) >= MIN_MATURED_FOR_CONTRADICTION
              and failed / len(rows) > price_leak + LEAK_GAP_REOPENS_AUDIT):
            # THE FENCE PROVES A LAG IS DECLARED, NOT THAT THE JOIN IS RIGHT. A join family that
            # leaks forward far above the price-only families is the F2 symptom itself, so its
            # clean fence reading does not close the audit.
            cert_status = "PROVISIONAL"
            pit = {**pit, "status": "REOPENED_BY_FORWARD",
                   "why": f"fence clear, but forward leak rate {failed / len(rows):.2f} on "
                          f"{len(rows)} matured clocks vs price-only {price_leak:.2f}: the "
                          "declared lag does not prove the point-in-time join"}
        else:
            cert_status = "STANDING"
        rec: dict[str, Any] = {
            "information": info, "pit_join_audit": pit, "certificate_status": cert_status,
            "certificates": sum(1 for c in certs.values() if c["family"] == fam),
            "matured": len(rows), "kept": kept, "leaks": failed,
            "leak_rate": round(failed / len(rows), 4) if rows else UNMEASURED,
            "forward_over_backtest": (round(v, 4) if (v := pooled_ratio(_ratio_rows(rows)))
                                      is not None else UNMEASURED),
            "prior": prior_rows.get(fam) or {"status": UNMEASURED,
                                             "why": "no matured clock with a backtest edge"},
            "thresholds": {g: {"before": m["before"], "after": m["after"]}
                           for g, m in moves.items()}}
        out[fam] = rec
        if cert_status == "PROVISIONAL":
            for key, c in certs.items():
                if c["family"] == fam:
                    provisional.append({"cert_id": c["cert_id"], "clock": key, "family": fam,
                                        "status": "PROVISIONAL", "why": pit.get("why")})
    return out, provisional


# ------------------------------------------------------------------------------ trial charge
def charge_trials(path: Path, build_id: str, at: str, families: Iterable[str],
                  moves: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Append one row per family: the candidate bars this build evaluated are trials of that
    family's search (R2). Idempotent per build; nothing already written is ever rewritten."""
    per_gate = {g: len(m.get("candidates") or []) for g, m in moves.items()
                if m.get("candidates")}
    k = sum(per_gate.values())
    fams = sorted(set(families))
    if k == 0 or not fams:
        return {"charged": 0, "why": "no candidate bar was evaluated this build"}
    try:
        for ln in path.read_text("utf-8").splitlines():
            if f'"build_id": "{build_id}"' in ln:
                return {"charged": 0, "why": f"build {build_id} already charged"}
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for f in fams:
            fh.write(json.dumps({"at": at, "build_id": build_id, "source": "judge_calibration",
                                 "family": f, "trials": k, "candidates_by_gate": per_gate})
                     + "\n")
    return {"charged": k * len(fams), "per_family": k, "families": len(fams),
            "ledger": str(path.name), "joined_by": "libs/research/experiment_ledger.lifetime"}


# ---------------------------------------------------------------------------------- build
def due(prev: Any, keys: list[str], now: datetime) -> tuple[bool, str]:
    if not isinstance(prev, dict) or not prev.get("built_at"):
        return True, "no previous build"
    built = _ts(prev.get("built_at"))
    if built is None:
        return True, "previous build carries no readable built_at"
    new = sorted(set(keys) - set(prev.get("matured_keys") or []))
    if new:
        return True, f"{len(new)} clock(s) matured since the last build"
    if now - built >= REBUILD_AFTER:
        return True, f"last build {(now - built).days} day(s) old"
    return False, "no clock matured since the last build and it is under 7 days old"


def build(paths: Paths, *, now: datetime | None = None, force: bool = False,
          key_fn: Callable[[Mapping[str, Any]], str] | None = None,
          control_fraction: float = CONTROL_FRACTION) -> dict[str, Any]:
    now = now or _now()
    at = now.isoformat(timespec="seconds")
    clocks, lanes = read_clocks(paths)
    keys = matured_keys(clocks)
    prev = _read(paths.out)
    go, why = (True, "forced") if force else due(prev, keys, now)
    if not go and isinstance(prev, dict):
        prev.update({"checked_at": at, "cadence": {"recomputed": False, "why": why}})
        return prev
    key_fn = key_fn or default_key_fn()
    canon_docs = [_read(p) for p in paths.canons]
    near_docs = [_read(p) for p in paths.near_miss]
    inputs: dict[str, Any] = {
        "lanes": lanes,
        "canons": {p.name: ("READ" if isinstance(d, dict) else UNMEASURED)
                   for p, d in zip(paths.canons, canon_docs, strict=True)},
        "near_miss": {p.name: ("READ" if isinstance(d, dict) else UNMEASURED)
                      for p, d in zip(paths.near_miss, near_docs, strict=True)}}
    if key_fn is None:
        certs: dict[str, dict[str, Any]] = {}
        near: dict[str, dict[str, Any]] = {}
        inputs["join"] = f"{UNMEASURED}: research/shadow_forward.sleeve_key not importable"
    else:
        certs = index_by_clock([d for d in canon_docs if isinstance(d, dict)], key_fn)
        near = {k: v for k, v in index_by_clock(
            [d for d in near_docs if isinstance(d, dict)], key_fn).items() if k not in certs}
        inputs["join"] = "shadow_forward.sleeve_key(shadow_spec)"
    policy = read_policy(paths)
    bars = bars_of(policy)
    inputs["gate_policy"] = (policy or {}).get("version", UNMEASURED)
    digest = _read(paths.digest)
    inputs["gate_verdict_digest"] = "READ" if isinstance(digest, dict) else UNMEASURED
    kbd = _read(paths.known_by_date)
    inputs["known_by_date"] = "READ" if isinstance(kbd, dict) else UNMEASURED

    s = build_sample(clocks, certs, near)
    sample = s["rows"]
    prev_prop = _read(paths.proposals)
    before = (prev_prop or {}).get("priors") if isinstance(prev_prop, dict) else None
    prev_keys = set((prev or {}).get("matured_keys") or []) if isinstance(prev, dict) else set()
    fams = sorted({r["family"] for r in _ratio_rows(sample)})
    controls = control_families(fams, now, control_fraction)
    prior_rows = priors(sample, before if isinstance(before, dict) else {}, prev_keys, controls)
    moves = thresholds(sample, bars)
    nm = near_miss_status(paths, near, sample)
    gates = per_gate_counts(sample, bars, digest, nm)
    families, provisional = per_family(sample, clocks, certs, kbd, prior_rows, moves)
    build_id = hashlib.sha256(("|".join(keys) + at).encode()).hexdigest()[:16]
    charge = charge_trials(paths.trials, build_id, at,
                           {r["family"] for r in sample}, moves)

    certified = [r for r in sample if r["source"] == "certified"]
    doc = {
        "schema": SCHEMA, "generated_at": at, "built_at": at, "checked_at": at,
        "build_id": build_id, "producer": "desks/mt5/research/judge_calibration.py",
        "cadence": {"recomputed": True, "why": why,
                    "rule": "a clock matured since the last build, or the last build >= 7 days"},
        "inputs": inputs,
        "summary": {
            "matured_clocks": len(keys),
            "n_matured_joined": sum(1 for r in certified if r["joined"]),
            "n_matured_certified": len(certified),
            "unjoined_matured": len(s["unjoined_matured"]),
            "immature_clocks_excluded": s["immature"],
            "leaks": sum(1 for r in certified if r["outcome"] == "FAILED"),
            "false_kills": (sum(1 for r in sample if r["source"] == "near_miss"
                                and r["outcome"] == "KEPT")
                            if nm["status"] == "MEASURED" else UNMEASURED),
            "measured_families": len(fams),
            "forward_over_backtest_all": (round(v, 4) if (v := pooled_ratio(
                _ratio_rows(sample))) is not None else UNMEASURED),
            "priors_published": sum(1 for p in prior_rows.values() if p.get("status")
                                    == "PUBLISHED"),
            "priors_rejected_lofo": sum(1 for p in prior_rows.values()
                                        if p.get("status") == "REJECTED_LOFO"),
            "priors_reverted": sum(1 for p in prior_rows.values()
                                   if p.get("status") == "REVERTED"),
            "threshold_moves": sum(1 for m in moves.values()
                                   if m.get("move") in ("TIGHTEN", "LOOSEN")),
            "provisional_certificates": len(provisional),
            "control_families": sorted(controls)},
        "false_kills": nm,
        "per_gate": gates, "per_family": families, "threshold_moves": moves,
        "trials": charge, "sealed_call_site": SEALED_CALL_SITE, "prior_reader": PRIOR_READER,
        "matured_keys": keys, "unjoined_matured_sample": s["unjoined_matured"][:25],
        "rule": "UNMEASURED is a verdict, never 0; nothing here edits the judge or a size",
    }
    proposals = {
        "schema": SCHEMA, "generated_at": at, "build_id": build_id,
        "status": "PROPOSED_NOT_APPLIED", "sealed_call_site": SEALED_CALL_SITE,
        "prior_reader": PRIOR_READER,
        "threshold_moves": {g: {k: m.get(k) for k in ("before", "after", "move", "direction",
                                                      "lofo_error_before", "lofo_error_after",
                                                      "missed_growth", "why")}
                            for g, m in moves.items()},
        "priors": {f: {k: p.get(k) for k in ("prior_before", "prior", "published", "status",
                                             "n_clocks", "forward_error_before",
                                             "forward_error_after", "control", "why")}
                   for f, p in prior_rows.items()},
        "provisional_certificates": provisional,
        "provisional_families": sorted(f for f, r in families.items()
                                       if r["certificate_status"] == "PROVISIONAL"),
        "history": [*((prev_prop or {}).get("history") or [])[-50:],
                    {"build_id": build_id, "at": at,
                     "published": {f: p["prior"] for f, p in prior_rows.items()
                                   if p.get("published")},
                     "reverted": [f for f, p in prior_rows.items()
                                  if p.get("status") == "REVERTED"]}],
    }
    doc["_proposals"] = proposals
    return doc


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def run(paths: Paths, **kw: Any) -> dict[str, Any]:
    doc = build(paths, **kw)
    proposals = doc.pop("_proposals", None)
    if proposals is not None:
        _write(paths.proposals, proposals)
    _write(paths.out, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="recompute regardless of cadence")
    a = ap.parse_args(argv)
    doc = run(Paths.under(DESK), force=a.force)
    print(json.dumps({"cadence": doc.get("cadence"), "summary": doc.get("summary")},
                     default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
