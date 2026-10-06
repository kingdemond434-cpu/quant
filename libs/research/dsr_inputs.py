"""DSR INPUTS, MEASURED: the deflated-Sharpe hurdle's two inputs, measured from the desk's own
judged trials and published with their provenance.

    sr0 = expected_max_sharpe(n_trials, variance_of_sharpes)      (libs/validation/dsr.py)

Until this organ, both inputs were constants. `fixed_trial_count` sat in `policy/gate_spec.yaml`
and `fixed_variance_of_sharpes` beside it (0.0002 there; 0.014863 in the code's fallback when the
spec could not be read). A constant cannot say where it came from or how old it is. The
principal's order (2026-09-30): the variance is MEASURED, per family, from judged trial records;
the trial count is lifetime and adaptive; both carry their source files, n, window, method,
timestamp and hash; and the judge FAILS CLOSED when the measurement is absent or stale. It must
never fall back to a constant.

WHAT IS MEASURED, AND IN WHICH UNITS
------------------------------------
* A TRIAL is one judged cell: a verdict in `reports/universal_gates_external.json` that carries
  `stages.in_sample_screen.sharpe` on at least 60 development days. That Sharpe is
  `libs.validation.dsr.sharpe_ratio(arr)` on the cell's development-window DAILY series: the
  same estimator, the same series and the same per-period (daily, NOT annualised) units as the
  observed Sharpe that `deflated_sharpe_ratio` deflates. The variance is therefore in the units
  `expected_max_sharpe` expects, and no annualisation factor enters anywhere.
* The gauntlet overwrites that report every sweep, so each hour this organ HARVESTS it into an
  append-only ledger, `data/dsr_trial_sharpes.jsonl`: one row per (cell, Sharpe) with the sweep's
  time, id and campaign. A cell re-judged on the same data gives the same Sharpe and is not
  written again, so the ledger grows with distinct evaluations, not with sweeps.
* VARIANCE: the sample variance (ddof=1) of the latest Sharpe of every distinct cell judged in
  the trailing `WINDOW_DAYS`, per family, pooled, and per campaign (reported). Nothing is
  winsorised, floored or shrunk: every one of those moves would lower the bar.
* EFFECTIVE TRIALS: lifetime, per family. The sweep report carries the judge's own correlation
  census (`trial_census`: `mt5desk.canonical.calibrated_census_report`, the null-calibrated
  participation ratio of the eigenvalues of the sweep's daily-return correlation matrix). Its
  ratio rho = n_effective / n_raw is the measured share of independent information in that
  sweep. Each distinct cell contributes the rho of the sweep that first judged it (1.0 when that
  sweep's census was unmeasurable, the harsh direction), and a family's effective count is
  ceil(sum rho), floored at its number of distinct symbols (a different instrument is a different
  test) and capped at its distinct cells. It is ADAPTIVE: every new cell raises it, and nothing
  ever lowers it but a re-measurement of redundancy the data itself shows.

WHAT THE JUDGE DOES WITH IT (the sealed half, shipped as a patch)
------------------------------------------------------------------
`load_verified` is the judge's only door. It returns the document, or a reason, when the file
is absent, unparseable, of another schema, UNMEASURED, older than `MAX_AGE_S`, dated in the
future, or when its `content_sha256` does not recompute. Any of those makes the cell's DSR stage
UNKNOWN with the named reason `dsr_inputs_unmeasured`. `cell_inputs` gives one cell its family's
variance (or the pooled one, named as such, when the family has fewer than `MIN_FAMILY_N` cells in
the window) and its family's lifetime effective trials. The judge charges
max(campaign charge, lifetime family trials, measured effective trials): the lifetime rule the
mass screen and the sharded sweep already charge over the full union stands, and the effective
count can only add to it.

IT NEVER REMOVES A CELL, CAPS A PRODUCER OR MOVES A GATE ON ITS OWN. It measures and publishes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "DSR_INPUTS.json"
LEDGER = DESK / "data" / "dsr_trial_sharpes.jsonl"
GAUNTLET_REPORT = DESK / "reports" / "universal_gates_external.json"

SCHEMA = "dsr_inputs/v1"
#: The named reason every fail-closed path gives the judge.
UNMEASURED_REASON = "dsr_inputs_unmeasured"
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: "Current" dispersion: distinct cells judged in this trailing window.
WINDOW_DAYS = 30
#: A family's own variance is used only from this many distinct cells in the window; below it the
#: pooled variance is used and named as such.
MIN_FAMILY_N = 30
#: Below this many distinct cells in the window nothing is measured and the judge fails closed.
MIN_POOLED_N = 100
#: CPCV's floor, and the judge's: a cell under it was never judged.
MIN_DAYS = 60
#: The organ runs every hour; four missed hours and the judge stops trusting it.
MAX_AGE_S = 4 * 3600
#: Clock skew tolerated before a document dated in the future is refused.
FUTURE_SKEW_S = 300
#: The census methods whose ratio is a measurement of dependence.
MEASURED_CENSUS_METHODS = frozenset({"null_calibrated_participation_ratio",
                                     "participation_ratio"})

VARIANCE_METHOD = (
    "sample variance (ddof=1) of the latest per-period Sharpe (libs.validation.dsr.sharpe_ratio "
    "on the development-window daily series, the units expected_max_sharpe takes; not "
    "annualised) of every distinct cell judged in the window; no winsorising, floor or shrinkage")
EFFECTIVE_METHOD = (
    "lifetime per family: sum over distinct judged cells of rho = n_effective / n_raw of the "
    "judge's own correlation census (null-calibrated participation ratio of the eigenvalues of "
    "the sweep's daily-return correlation matrix) for the sweep that first judged the cell, 1.0 "
    "when that census was unmeasurable; ceil, floored at the family's distinct symbols, capped at "
    "its distinct cells")


def trial_count_basis(campaign_trials: int) -> str:
    """The attested `trial_count_basis` for a spec whose DSR variance is measured here. Static
    text: it names the source and the rule, never an hourly value, because admission
    exact-matches the attestation."""
    return (f"effective_campaign_trials({int(campaign_trials)}) + "
            f"measured_variance_of_sharpes(reports/DSR_INPUTS.json): the campaign charge is "
            f"measured in EFFECTIVE independent tests -- the participation ratio of (grid cell, "
            f"content) identities within each mechanism -- not in docket rows, and each cell is "
            f"charged at least its family's lifetime trials and its family's measured lifetime "
            f"effective trials; the variance of Sharpes is measured per family from the desk's "
            f"judged trials over a trailing window, with provenance, and the judge fails closed "
            f"(UNKNOWN, {UNMEASURED_REASON}) when it is absent, stale or does not verify -- "
            f"never a constant")


# ------------------------------------------------------------------------------ small helpers
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def _parse(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _file_sha256(path: Path) -> str | None:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def canonical_sha256(doc: Mapping[str, Any]) -> str:
    """The hash of a document with its own `content_sha256` removed, over canonical JSON."""
    body = {k: v for k, v in doc.items() if k != "content_sha256"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str,
                      allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _variance(xs: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean = math.fsum(xs) / n
    var = math.fsum((x - mean) ** 2 for x in xs) / (n - 1)
    return var if math.isfinite(var) else None


def _finite(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


# ------------------------------------------------------------------------------ the ledger
def read_ledger(path: Path | None = None) -> list[dict[str, Any]]:
    """Every harvested row; a malformed line is skipped, an absent ledger is empty."""
    rows: list[dict[str, Any]] = []
    try:
        with (path or LEDGER).open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def _census_ratio(report: Mapping[str, Any]) -> tuple[float, str]:
    """rho = n_effective / n_raw of the sweep's own correlation census, or 1.0, named."""
    census = report.get("trial_census")
    if not isinstance(census, Mapping):
        return 1.0, "absent"
    method = str(census.get("method") or "")
    n_raw = _finite(census.get("n_raw"))
    n_eff = _finite(census.get("n_effective"))
    if method not in MEASURED_CENSUS_METHODS or not n_raw or n_eff is None or n_eff <= 0:
        return 1.0, f"unmeasurable ({method or 'no method'})"
    rho = n_eff / n_raw
    if not (0.0 < rho <= 1.0):
        return 1.0, f"implausible ratio {rho:.4f}"
    return rho, method


def trial_rows(report: Mapping[str, Any], *, sweep_id: str, judged_at: str
               ) -> list[dict[str, Any]]:
    """The judged trials of one sweep report, as ledger rows."""
    rho, rho_method = _census_ratio(report)
    campaign = str(report.get("hunt") or "?")
    out: list[dict[str, Any]] = []
    for v in report.get("verdicts") or []:
        if not isinstance(v, Mapping) or v.get("unmeasured"):
            continue
        stage = (v.get("stages") or {}).get("in_sample_screen")
        sr = _finite(stage.get("sharpe")) if isinstance(stage, Mapping) else None
        days = v.get("days")
        if sr is None or not isinstance(days, int) or days < MIN_DAYS:
            continue
        cell = str(v.get("cell") or "")
        if not cell:
            continue
        out.append({"cell": cell, "family": str(v.get("family") or "?"),
                    "sym": str(v.get("sym") or "?"), "campaign": campaign,
                    "sharpe": sr, "days": days, "judged_at": judged_at,
                    "sweep_id": sweep_id, "rho": round(rho, 6), "rho_method": rho_method})
    return out


def harvest(report_path: Path | None = None, ledger_path: Path | None = None) -> dict[str, Any]:
    """Append the latest sweep's judged trials to the ledger. Idempotent per sweep and per
    (cell, Sharpe): re-harvesting the same report writes nothing."""
    rpath = report_path or GAUNTLET_REPORT
    lpath = ledger_path or LEDGER
    sha = _file_sha256(rpath)
    if sha is None:
        return {"status": UNMEASURED, "why": f"{_rel(rpath)} is absent or unreadable",
                "appended": 0}
    try:
        report = json.loads(rpath.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": UNMEASURED, "why": f"{_rel(rpath)}: {type(exc).__name__}",
                "appended": 0, "sha256": sha}
    if not isinstance(report, dict):
        return {"status": UNMEASURED, "why": f"{_rel(rpath)} is not a mapping", "appended": 0,
                "sha256": sha}
    sweep_id = sha[:16]
    at = _parse(report.get("swept_at"))
    if at is None:
        try:
            at = datetime.fromtimestamp(rpath.stat().st_mtime, tz=UTC)
        except OSError:
            at = _now()
    existing = read_ledger(lpath)
    if any(r.get("sweep_id") == sweep_id for r in existing):
        return {"status": MEASURED, "appended": 0, "sweep_id": sweep_id, "sha256": sha,
                "why": "this sweep is already in the ledger"}
    seen = {(str(r.get("cell")), _finite(r.get("sharpe"))) for r in existing}
    rows = [r for r in trial_rows(report, sweep_id=sweep_id, judged_at=_iso(at))
            if (r["cell"], r["sharpe"]) not in seen]
    if rows:
        lpath.parent.mkdir(parents=True, exist_ok=True)
        with lpath.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return {"status": MEASURED, "appended": len(rows), "sweep_id": sweep_id, "sha256": sha,
            "swept_at": _iso(at), "campaign": str(report.get("hunt") or "?")}


# ------------------------------------------------------------------------------ measurement
def _latest_per_cell(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        cell = str(r.get("cell") or "")
        at = _parse(r.get("judged_at"))
        if not cell or at is None or _finite(r.get("sharpe")) is None:
            continue
        prev = out.get(cell)
        if prev is None or at >= prev["_at"]:
            out[cell] = {**r, "_at": at}
    return out


def _first_per_cell(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        cell = str(r.get("cell") or "")
        at = _parse(r.get("judged_at"))
        if not cell or at is None:
            continue
        prev = out.get(cell)
        if prev is None or at < prev["_at"]:
            out[cell] = {**r, "_at": at}
    return out


def _group_variance(rows: list[dict[str, Any]], key: str, min_n: int) -> dict[str, Any]:
    groups: dict[str, list[float]] = {}
    for r in rows:
        groups.setdefault(str(r.get(key) or "?"), []).append(float(r["sharpe"]))
    out: dict[str, Any] = {}
    for name, xs in sorted(groups.items()):
        var = _variance(xs)
        measured = var is not None and len(xs) >= min_n and var > 0
        out[name] = {"n": len(xs), "variance": None if var is None else round(var, 10),
                     "status": MEASURED if measured else UNMEASURED,
                     **({} if measured else {"why": f"{len(xs)} distinct cells in the window, "
                                                    f"{min_n} required"})}
    return out


def effective_trials(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Lifetime effective independent trials per family (see EFFECTIVE_METHOD)."""
    first = _first_per_cell(rows)
    fams: dict[str, dict[str, Any]] = {}
    for r in first.values():
        f = fams.setdefault(str(r.get("family") or "?"),
                            {"nominal": 0, "rho_sum": 0.0, "symbols": set()})
        f["nominal"] += 1
        rho = _finite(r.get("rho"))
        f["rho_sum"] += rho if rho is not None and 0.0 < rho <= 1.0 else 1.0
        f["symbols"].add(str(r.get("sym") or "?"))
    by_family: dict[str, Any] = {}
    for name, f in sorted(fams.items()):
        n_sym = len(f["symbols"])
        eff = min(f["nominal"], max(math.ceil(f["rho_sum"] - 1e-9), n_sym))
        by_family[name] = {"nominal": f["nominal"], "effective": int(eff),
                           "distinct_symbols": n_sym, "rho_sum": round(f["rho_sum"], 4)}
    return {"nominal": sum(f["nominal"] for f in by_family.values()),
            "effective": sum(f["effective"] for f in by_family.values()),
            "by_family": by_family, "method": EFFECTIVE_METHOD}


def measure(*, ledger_path: Path | None = None, report_path: Path | None = None,
            now: datetime | None = None, window_days: int = WINDOW_DAYS,
            harvest_result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The published document: variance per family (window), effective trials (lifetime),
    provenance, and `content_sha256` over all of it."""
    now = now or _now()
    lpath = ledger_path or LEDGER
    rpath = report_path or GAUNTLET_REPORT
    rows = read_ledger(lpath)
    latest = _latest_per_cell(rows)
    start = now - timedelta(days=window_days)
    window = [r for r in latest.values() if start <= r["_at"] <= now + timedelta(
        seconds=FUTURE_SKEW_S)]
    pooled_xs = [float(r["sharpe"]) for r in window]
    pooled_var = _variance(pooled_xs)
    life_var = _variance([float(r["sharpe"]) for r in latest.values()])
    pooled_ok = pooled_var is not None and pooled_var > 0 and len(pooled_xs) >= MIN_POOLED_N
    eff = effective_trials(rows)
    try:
        from libs.validation.dsr import expected_max_sharpe
        sr0_eff = (round(float(expected_max_sharpe(max(2, int(eff["effective"])), pooled_var)), 6)
                   if pooled_ok and pooled_var is not None else None)
    except Exception:
        sr0_eff = None
    status = MEASURED if pooled_ok else UNMEASURED
    why = (None if pooled_ok else
           f"{len(pooled_xs)} distinct judged cells in the last {window_days} days, "
           f"{MIN_POOLED_N} required (ledger rows {len(rows)})")
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        **({"why": why} if why else {}),
        "unmeasured_reason": None if pooled_ok else UNMEASURED_REASON,
        "measured_at": _iso(now),
        "max_age_s": MAX_AGE_S,
        "variance": {
            "units": "per-period (daily) Sharpe, not annualised: the units of "
                     "libs.validation.dsr.expected_max_sharpe",
            "method": VARIANCE_METHOD,
            "window": {"days": window_days, "start": _iso(start), "end": _iso(now)},
            "min_family_n": MIN_FAMILY_N, "min_pooled_n": MIN_POOLED_N,
            "pooled": {"n": len(pooled_xs),
                       "variance": None if pooled_var is None else round(pooled_var, 10),
                       "status": MEASURED if pooled_ok else UNMEASURED},
            "lifetime_pooled": {"n": len(latest),
                                "variance": None if life_var is None else round(life_var, 10)},
            "by_family": _group_variance(window, "family", MIN_FAMILY_N),
            "by_campaign": _group_variance(window, "campaign", MIN_FAMILY_N),
        },
        "effective_trials": eff,
        "sr0_pooled_at_lifetime_effective": sr0_eff,
        "provenance": {
            "sources": [
                {"path": _rel(lpath), "role": "append-only ledger of judged trial Sharpes",
                 "sha256": _file_sha256(lpath), "rows": len(rows),
                 "distinct_cells": len(latest)},
                {"path": _rel(rpath), "role": "latest sweep report harvested into the ledger",
                 "sha256": _file_sha256(rpath)},
            ],
            "harvest": dict(harvest_result or {}),
            "code": {"path": _rel(Path(__file__)), "sha256": _file_sha256(Path(__file__))},
            "n": len(pooled_xs),
            "window": {"days": window_days, "start": _iso(start), "end": _iso(now)},
            "method": {"variance": VARIANCE_METHOD, "effective_trials": EFFECTIVE_METHOD},
            "timestamp": _iso(now),
        },
    }
    doc["content_sha256"] = canonical_sha256(doc)
    return doc


def write(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    """Write atomically: a reader sees the old document or the new one, never half of one."""
    out = path or REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False, default=str), encoding="utf-8")
    os.replace(tmp, out)
    return out


# ------------------------------------------------------------------------------ the judge's door
def load_verified(path: Path | None = None, *, now: datetime | None = None,
                  max_age_s: float | None = None) -> tuple[dict[str, Any] | None, str]:
    """(document, "") when it may be used, else (None, why). Never a default, never a constant."""
    p = path or REPORT
    try:
        doc = json.loads(p.read_text("utf-8"))
    except OSError:
        return None, f"{UNMEASURED_REASON}: {_rel(p)} is absent"
    except ValueError as exc:
        return None, f"{UNMEASURED_REASON}: {_rel(p)} does not parse ({exc})"
    if not isinstance(doc, dict):
        return None, f"{UNMEASURED_REASON}: {_rel(p)} is not a mapping"
    if doc.get("schema") != SCHEMA:
        return None, f"{UNMEASURED_REASON}: schema {doc.get('schema')!r}, expected {SCHEMA!r}"
    try:
        recomputed = canonical_sha256(doc)
    except ValueError as exc:
        return None, f"{UNMEASURED_REASON}: content does not hash ({exc})"
    if doc.get("content_sha256") != recomputed:
        return None, (f"{UNMEASURED_REASON}: provenance hash does not verify "
                      f"(file {str(doc.get('content_sha256'))[:12]}, recomputed "
                      f"{recomputed[:12]})")
    if doc.get("status") != MEASURED:
        return None, f"{UNMEASURED_REASON}: status {doc.get('status')} ({doc.get('why')})"
    at = _parse(doc.get("measured_at"))
    if at is None:
        return None, f"{UNMEASURED_REASON}: measured_at unreadable"
    now = now or _now()
    age = (now - at).total_seconds()
    limit = float(MAX_AGE_S if max_age_s is None else max_age_s)
    if age > limit:
        return None, f"{UNMEASURED_REASON}: stale, measured {age / 3600:.1f} h ago (limit " \
                     f"{limit / 3600:.1f} h)"
    if age < -FUTURE_SKEW_S:
        return None, f"{UNMEASURED_REASON}: measured_at is {-age:.0f} s in the future"
    pooled = (doc.get("variance") or {}).get("pooled") or {}
    pv = _finite(pooled.get("variance"))
    if pv is None or pv <= 0 or pooled.get("status") != MEASURED:
        return None, f"{UNMEASURED_REASON}: pooled variance unmeasured"
    return doc, ""


def cell_inputs(doc: Mapping[str, Any], family: str) -> dict[str, Any] | None:
    """One cell's DSR inputs from a VERIFIED document: its family's variance (pooled, named, when
    the family is thin in the window) and its family's lifetime effective trials (None when the
    family has never been judged: the judge's other charges apply). None when unusable."""
    var = doc.get("variance") or {}
    fam = (var.get("by_family") or {}).get(family) or {}
    fv = _finite(fam.get("variance"))
    window = var.get("window") or {}
    if fam.get("status") == MEASURED and fv is not None and fv > 0:
        v, basis = fv, (f"measured_variance_of_sharpes(family {family}, n={fam.get('n')}, "
                        f"{window.get('days')}d)")
    else:
        pooled = var.get("pooled") or {}
        pv = _finite(pooled.get("variance"))
        if pv is None or pv <= 0 or pooled.get("status") != MEASURED:
            return None
        v, basis = pv, (f"measured_variance_of_sharpes(pooled, n={pooled.get('n')}, "
                        f"{window.get('days')}d; family {family} has {fam.get('n', 0)} cells, "
                        f"{var.get('min_family_n')} required)")
    eff_row = ((doc.get("effective_trials") or {}).get("by_family") or {}).get(family) or {}
    eff = eff_row.get("effective")
    return {"variance": float(v), "variance_basis": basis,
            "effective_trials": int(eff) if isinstance(eff, int) and eff > 0 else None,
            "content_sha256": doc.get("content_sha256"), "measured_at": doc.get("measured_at")}


def run(*, report_path: Path | None = None, ledger_path: Path | None = None,
        out: Path | None = None, now: datetime | None = None,
        window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    """One pass: harvest, measure, publish."""
    h = harvest(report_path, ledger_path)
    doc = measure(ledger_path=ledger_path, report_path=report_path, now=now,
                  window_days=window_days, harvest_result=h)
    write(doc, out)
    return doc
