"""CERTIFICATE REALNESS -- how likely a ten-gate certificate is a real edge, for RANKING only.

    p_real = PSR(SR_hat, T; sr0(N*, V*)) x (1 - pi0[family x timeframe])

WHY IT EXISTS (reports/research/DSR_CHARGE_PROBE_2026-11-25.md, sections 4 and 5). The judge's
deflated-Sharpe bar uses a fixed V = 0.0002, below a single trial's own sampling noise 1/(T-1), and
forward evidence splits by timeframe and family far more than by bar height (H1 Storey pi0 0.16,
M5 1.00). The principal's direction (2026-11-25 23:08Z): forward trades are the real fluke filter,
THE BAR STAYS WHERE IT IS, and this work is ranking plus information only. So:

  * NOTHING HERE MOVES A GATE. No threshold, trial count, V, `gate_spec.yaml`,
    `external_gauntlet.py` or certificate file is written; every input is read-only. The score
    orders the forward-slot queue and the replication queue, and is published as information.

THE TWO TERMS, AND WHERE EACH COMES FROM
---------------------------------------
* PSR AT THE MEASURED BASIS. z = (SR - sr0) sqrt(T-1) / sqrt(1 + SR^2/2) (normal approximation:
  certificates carry no skew/kurtosis), sr0 = sqrt(V*) E[max of N* iid N(0,1)] -- the kernel of
  `libs.validation.dsr.expected_max_sharpe`, in stdlib.
    N* = max(campaign floor, the family's LIFETIME EFFECTIVE trials). Lifetime trials per family
         are the judge's own `reports/EXPERIMENT_LEDGER.json` (`by_family`), scaled by the
         measured independence ratio rho of the judged cross-section (`dsr_inputs.
         effective_trials`, the judge's census); without the ledger, the cross-section's own
         effective count; without either, the floor -- each named in the basis.
    V* = max(1/(T-1), V_null[family]). V_null is the family's dispersion of judged trial Sharpes
         NET of their mean sampling noise mean(1/(T_i - 1)), floored at 0. It is measured HERE,
         from the judged cross-section the box holds (the trial-Sharpe ledger when present, else
         the latest sweep report `universal_gates_external.json`, streamed). It never reads
         `DSR_INPUTS.json`, which the box has not written since 2026-11-10.
         THE ESTIMATOR IS ROBUST AND SAYS SO: (1.4826 MAD)^2. The probe measured the raw sample
         variance at 0.04-0.36 per family -- sr0 of 1-2 daily, a level no certificate clears, and
         the probe itself calls that value contaminated (short-T, near-degenerate series) and an
         upper bound, not a null. Subtracting 1/(T-1) (<= 0.017 at the judge's 60-day floor)
         cannot remove that contamination; a robust scale can. The raw variance and the raw net
         figure are PUBLISHED beside it for every family, so the choice is visible, and the
         calibration block below is the test of it.
* (1 - pi0). pi0 is Storey's null share (lambda = 0.5) of the one-sided forward p-values
  1 - Phi(forward_t) of MATURED, DISTINCT clocks (aliases -- same symbol, same n, same cum_r --
  count once) per family x timeframe. Under `MIN_MATURED` such clocks the cell's pi0 is the
  pooled measurement, and under that the declared prior `PRIOR_PI0`; the basis says which
  (L1.28a: absence never resolves to a clean number).

THE FALSIFIER (section 5) is `calibration`: matured distinct clocks joined to their certificate,
binned by score decile, predicted keep (mean p_real) against measured keep (exp_r > 0) with the
binomial SE under the prediction. TRIGGER_LINE is printed with it. It only reports; nothing reads
it to act. It is in-sample for pi0 (the same matured clocks estimate pi0), which is stated in the
block: a well-calibrated reading is necessary, not sufficient.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Any

from libs.research import dsr_inputs as _di

DESK = Path(__file__).resolve().parents[1]

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
#: Euler-Mascheroni: the E[max] kernel of libs/validation/dsr.py.
_G = 0.5772156649015329
_N = NormalDist()
#: `gate_spec.yaml: deflated_sharpe.fixed_trial_count`, read from the file at call time; this
#: literal is used only when the spec cannot be read, and the basis then says so.
FALLBACK_CAMPAIGN_TRIALS = 109
#: Matured distinct clocks a family x timeframe needs before its own pi0 is a measurement.
MIN_MATURED = 10
#: The declared prior null share when not even the pooled forward population is measured.
PRIOR_PI0 = 0.5
STOREY_LAMBDA = 0.5
#: The family needs this many judged trials before its own dispersion is used (dsr_inputs').
MIN_FAMILY_N = _di.MIN_FAMILY_N
MIN_POOLED_N = 30
#: MAD -> sigma for a normal core.
MAD_SCALE = 1.4826
#: The judge's floor on development days.
MIN_DAYS = _di.MIN_DAYS
#: Statuses of a clock that has RULED (the ranker's own vocabulary).
MATURED_POSITIVE = ("PROMOTION CANDIDATE", "PROMOTED", "LIVE", "ALLOCATED", "DEPLOYED")
MATURED_NEGATIVE = ("KILL", "KILLED", "REJECTED", "DEAD", "RETIRED_GATE_FAIL")
#: The PSR level the judge's deflated-Sharpe gate passes at.
DSR_PASS = 0.95
#: Cross-section streaming deadline. A pass that runs out keeps the previous cache.
DEFAULT_BUDGET_S = 240.0
#: The calibration's minimum population and its two-SE trigger (section 5, verbatim rule).
CALIBRATION_MIN_N = 100
CALIBRATION_TOP_DECILES = 3
CALIBRATION_SE = 2.0
TRIGGER_LINE = ("propose raising the bar to Audit only if top-3-decile forward keep is more than "
                "2 SE below predicted over at least 100 matured clocks")
#: DSR-only kills listed (by score) in the published block.
DSR_ONLY_LIST_MAX = 200
#: The ranking floor under (1 - pi0): ordering only, never a probability.
RANK_PI0_FLOOR = 1e-12

_TF = re.compile(r"@(M1|M5|M15|M30|H1|H4|D1|W1)\b")


# --------------------------------------------------------------------------------- small maths
def emax(n: float) -> float:
    """E[max] of n iid N(0,1) (Bailey & Lopez de Prado), as `expected_max_sharpe` with sigma=1."""
    if n < 2:
        return 0.0
    return ((1 - _G) * _N.inv_cdf(1 - 1 / n) + _G * _N.inv_cdf(1 - 1 / (n * math.e)))


def psr_z(sr: float, t: float, sr0: float) -> float:
    return (sr - sr0) * math.sqrt(max(t - 1.0, 1.0)) / math.sqrt(max(1.0 + 0.5 * sr * sr, 1e-12))


def log10_phi(z: float) -> float:
    """log10 Phi(z), finite far into the lower tail (Mills asymptotic past z = -30)."""
    if z > -30.0:
        return math.log10(max(0.5 * math.erfc(-z / math.sqrt(2.0)), 1e-300))
    zz = z * z
    ln = (-0.5 * zz - math.log(-z) - 0.5 * math.log(2 * math.pi)
          + math.log(1 - 1 / zz + 3 / (zz * zz)))
    return ln / math.log(10.0)


def phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def storey_pi0(pvals: list[float], lam: float = STOREY_LAMBDA) -> float:
    """Storey's null share, capped at 1."""
    if not pvals:
        return 1.0
    return min(1.0, sum(p > lam for p in pvals) / ((1.0 - lam) * len(pvals)))


def _finite(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    out = float(v)
    return out if math.isfinite(out) else None


def _variance(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    k = len(s)
    return s[k // 2] if k % 2 else 0.5 * (s[k // 2 - 1] + s[k // 2])


def _robust_variance(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    med = _median(xs)
    return (MAD_SCALE * _median([abs(x - med) for x in xs])) ** 2


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def timeframe_of(text: str, params: Mapping[str, Any] | None = None) -> str:
    """The bar timeframe a spec, a selector or a clock key names; H1 when nothing names one (the
    desk's default bar, as `replication_civilization` reads it)."""
    tf = str((params or {}).get("timeframe") or "") if isinstance(params, Mapping) else ""
    if tf:
        return tf.upper()
    m = _TF.search(str(text or ""))
    return m.group(1) if m else "H1"


# ------------------------------------------------------------------------------- the inputs
def paths_for(reports: Path, desk: Path | None = None) -> dict[str, Path]:
    """Every read-only input, and the one cache this module writes. `reports` is the directory
    the caller publishes into; the desk root is its parent when it is a `reports/` directory,
    else the same directory (a test's tmp tree stays hermetic)."""
    reports = Path(reports)
    desk = Path(desk) if desk is not None else (
        reports.parent if reports.name == "reports" else reports)
    return {"gauntlet_report": reports / "universal_gates_external.json",
            "trial_ledger": desk / "data" / "dsr_trial_sharpes.jsonl",
            "experiment_ledger": reports / "EXPERIMENT_LEDGER.json",
            "gate_spec": desk / "policy" / "gate_spec.yaml",
            "cache": reports / "CERT_REALNESS_CROSS_SECTION.json"}


def campaign_floor(gate_spec: Path) -> tuple[int, str]:
    """`deflated_sharpe.fixed_trial_count`, READ from the spec (never written)."""
    try:
        text = Path(gate_spec).read_text("utf-8")
    except OSError:
        return FALLBACK_CAMPAIGN_TRIALS, (f"gate_spec unreadable: declared literal "
                                          f"{FALLBACK_CAMPAIGN_TRIALS}")
    m = re.search(r"fixed_trial_count:\s*(\d+)", text)
    if not m:
        return FALLBACK_CAMPAIGN_TRIALS, (f"no fixed_trial_count in gate_spec: declared literal "
                                          f"{FALLBACK_CAMPAIGN_TRIALS}")
    return int(m.group(1)), f"gate_spec.yaml fixed_trial_count({m.group(1)})"


def lifetime_trials(experiment_ledger: Path) -> dict[str, Any]:
    """The judge's lifetime trials per family (`EXPERIMENT_LEDGER.json`, `pf_allocator` writes it).
    Read only; an absent ledger is UNMEASURED, never zero."""
    doc = _read_json(experiment_ledger)
    if not isinstance(doc, dict) or not isinstance(doc.get("by_family"), dict):
        return {"status": UNMEASURED, "source": str(experiment_ledger), "by_family": {},
                "why": "EXPERIMENT_LEDGER.json absent or carries no by_family"}
    return {"status": MEASURED, "source": str(experiment_ledger),
            "lifetime_trials": doc.get("lifetime_trials"),
            "by_family": {str(k): int(v) for k, v in doc["by_family"].items()
                          if isinstance(v, (int, float)) and v > 0}}


def _stamp(path: Path) -> dict[str, Any] | None:
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return {"path": str(path), "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def _ledger_trials(path: Path, window_days: int, deadline: float
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Latest Sharpe per distinct cell from the harvested trial ledger, in the trailing window."""
    rows = _di.read_ledger(path)
    if time.monotonic() > deadline:
        raise TimeoutError("trial ledger read past the deadline")
    latest = _di._latest_per_cell(rows)
    if not latest:
        return [], {}
    end = max(r["_at"] for r in latest.values())
    start = end - timedelta(days=window_days)
    window = [r for r in latest.values() if r["_at"] >= start]
    return window, {"window_days": window_days, "start": start.isoformat(),
                    "end": end.isoformat(), "ledger_rows": len(rows),
                    "effective_trials": _di.effective_trials(rows)}


def _iter_verdicts(path: Path, deadline: float,
                   on_meta: Callable[[str, Any], None]) -> Iterable[Any]:
    """Each verdict of a sweep report, streamed with dsr_inputs' own chunked decoder."""
    with Path(path).open(encoding="utf-8") as fh:
        s = _di._Stream(fh, deadline, f"reading {path}")
        if s.peek() != "{":
            return
        s.expect("{")
        if s.peek() == "}":
            return
        n = 0
        while True:
            key = s.value()
            s.expect(":")
            if key == "verdicts" and s.peek() == "[":
                s.pos += 1
                if s.peek() == "]":
                    s.pos += 1
                else:
                    while True:
                        yield s.value()
                        n += 1
                        if n % 1024 == 0 and time.monotonic() > deadline:
                            raise TimeoutError("sweep report read past the deadline")
                        c = s.peek()
                        s.pos += 1
                        if c == "]":
                            break
            elif key in ("hunt", "swept_at", "trial_census"):
                on_meta(str(key), s.value())
            else:
                s.value()
            c = s.peek()
            s.pos += 1
            if c != ",":
                return


def _dsr_only_kill(v: Mapping[str, Any]) -> dict[str, Any] | None:
    """A verdict that FAILED deflated_sharpe and no other gate it evaluated. Later gates the judge
    did not evaluate are counted, never assumed passed."""
    stages = v.get("stages")
    if not isinstance(stages, Mapping):
        return None
    dsr = stages.get("deflated_sharpe")
    if not isinstance(dsr, Mapping) or dsr.get("passed") is not False:
        return None
    others = {g: s for g, s in stages.items() if g != "deflated_sharpe" and isinstance(s, Mapping)}
    if any(s.get("passed") is False for s in others.values()):
        return None
    sr = _finite((stages.get("in_sample_screen") or {}).get("sharpe"))
    days = v.get("days")
    if sr is None or not isinstance(days, int) or days < MIN_DAYS:
        return None
    return {"cell": str(v.get("cell") or ""), "family": str(v.get("family") or "?"),
            "sym": str(v.get("sym") or "?"), "sharpe": sr, "days": days,
            "timeframe": timeframe_of(str(v.get("cell") or ""), v.get("params")
                                      if isinstance(v.get("params"), Mapping) else None),
            "judge_dsr": _finite(dsr.get("dsr")), "judge_sr0": _finite(dsr.get("sr0")),
            "judge_n_trials": dsr.get("n_trials"),
            "other_gates_evaluated": len(others)}


def _report_trials(path: Path, deadline: float
                   ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    meta: dict[str, Any] = {}
    fields: list[Any] = []
    kills: list[dict[str, Any]] = []
    for v in _iter_verdicts(path, deadline, meta.__setitem__):
        if not isinstance(v, Mapping):
            continue
        t = _di._trial_fields(v)
        if t is not None:
            fields.append(t)
        k = _dsr_only_kill(v)
        if k is not None:
            kills.append(k)
    rows = _di._rows_from(fields, meta, sweep_id="current", judged_at=str(meta.get("swept_at")))
    info = {"swept_at": meta.get("swept_at"), "hunt": meta.get("hunt"),
            "rho": rows[0]["rho"] if rows else None,
            "rho_method": rows[0]["rho_method"] if rows else None,
            "effective_trials": _di.effective_trials(rows)}
    return rows, info, kills


def _summarise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per family (and pooled): raw variance, robust variance, mean noise, and V_null for each."""
    def block(xs: list[float], ts: list[int], min_n: int) -> dict[str, Any]:
        raw, rob = _variance(xs), _robust_variance(xs)
        noise = sum(1.0 / (t - 1) for t in ts) / len(ts) if ts else None
        ok = raw is not None and rob is not None and noise is not None and len(xs) >= min_n
        out: dict[str, Any] = {
            "n": len(xs), "status": MEASURED if ok else UNMEASURED,
            "variance_raw": None if raw is None else round(raw, 10),
            "variance_robust": None if rob is None else round(rob, 10),
            "mean_noise": None if noise is None else round(noise, 10)}
        if ok and raw is not None and rob is not None and noise is not None:
            out["v_null"] = round(max(rob - noise, 0.0), 10)
            out["v_null_raw"] = round(max(raw - noise, 0.0), 10)
        else:
            out["why"] = f"{len(xs)} judged trials, {min_n} required"
        return out

    fams: dict[str, tuple[list[float], list[int]]] = {}
    allx: list[float] = []
    allt: list[int] = []
    for r in rows:
        sr, days = _finite(r.get("sharpe")), r.get("days")
        if sr is None or not isinstance(days, int) or days < 2:
            continue
        xs, ts = fams.setdefault(str(r.get("family") or "?"), ([], []))
        xs.append(sr)
        ts.append(days)
        allx.append(sr)
        allt.append(days)
    return {"pooled": block(allx, allt, MIN_POOLED_N),
            "by_family": {f: block(xs, ts, MIN_FAMILY_N) for f, (xs, ts) in sorted(fams.items())}}


def cross_section(paths: Mapping[str, Path], *, budget_s: float = DEFAULT_BUDGET_S,
                  window_days: int = _di.WINDOW_DAYS, write_cache: bool = True
                  ) -> dict[str, Any]:
    """The judged cross-section, summarised, from the best source the host holds. Cached against
    the source's (path, size, mtime) so an unchanged multi-hundred-MB report is read once."""
    deadline = time.monotonic() + max(1.0, float(budget_s))
    cache = _read_json(paths["cache"])
    ledger_stamp = _stamp(paths["trial_ledger"])
    report_stamp = _stamp(paths["gauntlet_report"])
    source = ("trial_ledger", ledger_stamp) if ledger_stamp and ledger_stamp["size"] > 0 else (
        ("gauntlet_report", report_stamp) if report_stamp else (None, None))
    if source[0] is None:
        return {"status": UNMEASURED, "source": None, "pooled": {}, "by_family": {},
                "dsr_only_kills": [],
                "why": (f"neither {paths['trial_ledger']} nor {paths['gauntlet_report']} exists "
                        f"on this host: V_null is UNMEASURED and V* is the 1/(T-1) noise floor")}
    if isinstance(cache, dict) and cache.get("stamp") == source[1] and cache.get("status"):
        return {**cache, "cache": "hit"}
    kills: list[dict[str, Any]] = []
    try:
        if source[0] == "trial_ledger":
            rows, info = _ledger_trials(paths["trial_ledger"], window_days, deadline)
            if report_stamp:                    # the kills live only in the sweep report
                with contextlib.suppress(Exception):
                    _r, _i, kills = _report_trials(paths["gauntlet_report"], deadline)
        else:
            rows, info, kills = _report_trials(paths["gauntlet_report"], deadline)
    except Exception as exc:                    # deadline, malformed JSON, unreadable file
        if isinstance(cache, dict) and cache.get("status"):
            return {**cache, "cache": f"stale ({type(exc).__name__}: source changed, re-read "
                                      f"did not finish; previous summary used and named)"}
        return {"status": UNMEASURED, "source": source[0], "pooled": {}, "by_family": {},
                "dsr_only_kills": [], "why": f"{type(exc).__name__} reading {source[0]}"}
    summ = _summarise(rows)
    doc = {"status": summ["pooled"].get("status", UNMEASURED), "source": source[0],
           "stamp": source[1], "measured_at": datetime.now(UTC).isoformat(),
           "info": info, **summ, "dsr_only_kills": kills, "cache": "miss",
           "estimator": ("V_null = max((1.4826 MAD)^2 - mean(1/(T_i-1)), 0) over the family's "
                         "judged trial Sharpes; raw-variance analogue published as v_null_raw")}
    if write_cache:
        with contextlib.suppress(OSError):
            p = Path(paths["cache"])
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(json.dumps(doc, default=str), "utf-8")
            os.replace(tmp, p)
    return doc


# ----------------------------------------------------------------------------- forward pi0
def _status_class(status: str) -> int | None:
    s = str(status or "").upper()
    if any(s.startswith(g) for g in MATURED_POSITIVE):
        return 1
    if any(s.startswith(b) for b in MATURED_NEGATIVE):
        return 0
    return None


def matured_distinct(states: Mapping[str, Mapping[str, Mapping[str, Any]]]
                     ) -> list[dict[str, Any]]:
    """Every clock that has RULED, aliases counted once: (symbol, n, cum_r to 4 dp) is one trade
    stream whatever expression named it (the probe's de-duplication)."""
    seen: dict[tuple[str, Any, float], dict[str, Any]] = {}
    for lane, rows in states.items():
        for key, raw in rows.items():
            if not isinstance(raw, Mapping):
                continue
            cls = _status_class(str(raw.get("status") or ""))
            t = _finite(raw.get("forward_t"))
            exp_r = _finite(raw.get("exp_r"))
            if cls is None or t is None or exp_r is None:
                continue
            parts = str(key).split("#", 1)[0].split(".")
            sym = parts[0]
            fam = parts[1] if len(parts) >= 2 else "?"
            ident = (sym, raw.get("n"), round(_finite(raw.get("cum_r")) or 0.0, 4))
            seen.setdefault(ident, {"key": str(key), "lane": lane, "symbol": sym, "family": fam,
                                    "timeframe": timeframe_of(str(key)), "forward_t": t,
                                    "exp_r": exp_r, "keep": int(exp_r > 0), "ruled": cls,
                                    "n": raw.get("n")})
    return list(seen.values())


def pi0_table(states: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    """Storey pi0 per family x timeframe from matured distinct clocks, with its fallbacks named.

    A cell under `MIN_MATURED` borrows, in order, its TIMEFRAME's pooled measurement (the probe's
    first finding: forward keep splits by timeframe -- H1 pi0 0.16, M5 1.00), then its FAMILY's,
    then the desk's pooled one, then the declared `PRIOR_PI0`. Each level says which it used."""
    clocks = matured_distinct(states)

    def p_of(c: Mapping[str, Any]) -> float:
        return 1.0 - phi(float(c["forward_t"]))

    def level(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {"n_matured_distinct": len(rows),
                "measured_keep": round(sum(c["keep"] for c in rows) / len(rows), 6) if rows
                else None,
                "pi0": round(storey_pi0([p_of(c) for c in rows]), 6) if rows else None}

    by_cell: dict[str, list[dict[str, Any]]] = {}
    by_tf: dict[str, list[dict[str, Any]]] = {}
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for c in clocks:
        by_cell.setdefault(f"{c['family']}|{c['timeframe']}", []).append(c)
        by_tf.setdefault(c["timeframe"], []).append(c)
        by_fam.setdefault(c["family"], []).append(c)
    if len(clocks) >= MIN_MATURED:
        prior = float(level(clocks)["pi0"])
        prior_basis = f"pooled Storey pi0 over {len(clocks)} matured distinct clocks"
    else:
        prior, prior_basis = PRIOR_PI0, (
            f"DECLARED PRIOR {PRIOR_PI0}: {len(clocks)} matured distinct clock(s), "
            f"{MIN_MATURED} required for a pooled measurement")
    timeframes = {k: level(v) for k, v in sorted(by_tf.items())}
    families = {k: level(v) for k, v in sorted(by_fam.items())}

    def fallback(fam: str, tf: str) -> tuple[float, str]:
        for name, table, key in (("timeframe", timeframes, tf), ("family", families, fam)):
            row = table.get(key)
            if row and row["n_matured_distinct"] >= MIN_MATURED:
                return float(row["pi0"]), (f"{name} {key} pooled Storey pi0 over "
                                           f"{row['n_matured_distinct']} matured distinct clocks")
        return prior, prior_basis

    cells: dict[str, Any] = {}
    for g, rows in sorted(by_cell.items()):
        fam, tf = g.split("|", 1)
        row: dict[str, Any] = {"family": fam, "timeframe": tf, **level(rows)}
        if len(rows) >= MIN_MATURED:
            row["basis"] = "measured: Storey lambda=0.5"
        else:
            row["pi0_own"] = row["pi0"]
            pi0, why = fallback(fam, tf)
            row.update(pi0=round(pi0, 6), basis=f"fallback ({len(rows)} < {MIN_MATURED}): {why}")
        cells[g] = row
    return {"cells": cells, "by_timeframe": timeframes, "by_family": families,
            "prior": round(prior, 6), "prior_basis": prior_basis,
            "n_matured_distinct": len(clocks), "min_matured": MIN_MATURED,
            "method": ("Storey pi0 (lambda 0.5, capped at 1) of one-sided forward p-values "
                       "1 - Phi(forward_t) over matured distinct clocks per family x timeframe; "
                       "thin cells fall back to timeframe, then family, then pooled, then the "
                       "declared prior")}


def pi0_for(table: Mapping[str, Any], family: str, timeframe: str) -> tuple[float, str]:
    row = (table.get("cells") or {}).get(f"{family}|{timeframe}")
    if isinstance(row, Mapping):
        return float(row["pi0"]), f"{family}|{timeframe}: {row['basis']}"
    for name, key in (("by_timeframe", timeframe), ("by_family", family)):
        lv = (table.get(name) or {}).get(key)
        if isinstance(lv, Mapping) and (lv.get("n_matured_distinct") or 0) >= MIN_MATURED:
            return float(lv["pi0"]), (f"{family}|{timeframe}: no matured clock -- {name[3:]} "
                                      f"{key} pooled Storey pi0 over "
                                      f"{lv['n_matured_distinct']} matured distinct clocks")
    return float(table.get("prior", PRIOR_PI0)), (
        f"{family}|{timeframe}: no matured clock -- {table.get('prior_basis')}")


# ------------------------------------------------------------------------------ the score
class Context:
    """Everything a score needs, measured once per pass."""

    def __init__(self, xs: Mapping[str, Any], pi0: Mapping[str, Any], floor: tuple[int, str],
                 lifetime: Mapping[str, Any]) -> None:
        self.xs, self.pi0, self.floor, self.lifetime = xs, pi0, floor, lifetime
        info = xs.get("info") if isinstance(xs.get("info"), Mapping) else {}
        eff = (info or {}).get("effective_trials") or {}
        self.eff_by_family = eff.get("by_family") or {}

    def n_star(self, family: str) -> tuple[int, str]:
        floor, floor_basis = self.floor
        eff = self.eff_by_family.get(family) or {}
        nominal, effective = eff.get("nominal"), eff.get("effective")
        life = (self.lifetime.get("by_family") or {}).get(family)
        if isinstance(life, int) and life > 0:
            rho = (effective / nominal) if isinstance(nominal, int) and nominal > 0 and \
                isinstance(effective, int) else 1.0
            n = max(floor, math.ceil(life * min(max(rho, 0.0), 1.0)))
            return n, (f"max({floor_basis}, lifetime {life} x measured rho {rho:.4f} "
                       f"[EXPERIMENT_LEDGER x cross-section census])")
        if isinstance(effective, int) and effective > 0:
            return max(floor, effective), (f"max({floor_basis}, cross-section effective "
                                           f"{effective}; EXPERIMENT_LEDGER has no lifetime "
                                           f"count for {family})")
        return floor, f"{floor_basis} (family {family}: no lifetime or cross-section count)"

    def v_null(self, family: str) -> tuple[float | None, str]:
        fam = (self.xs.get("by_family") or {}).get(family) or {}
        if fam.get("status") == MEASURED and _finite(fam.get("v_null")) is not None:
            return float(fam["v_null"]), (f"family {family} robust V net of noise "
                                          f"(n={fam.get('n')}, {self.xs.get('source')})")
        pooled = self.xs.get("pooled") or {}
        if pooled.get("status") == MEASURED and _finite(pooled.get("v_null")) is not None:
            return float(pooled["v_null"]), (f"POOLED robust V net of noise (family {family} "
                                             f"has {fam.get('n', 0)} trials, {MIN_FAMILY_N} "
                                             f"required; {self.xs.get('source')})")
        return None, f"V_null UNMEASURED ({self.xs.get('why') or 'no judged cross-section'})"


def score(sr: Any, days: Any, family: str, timeframe: str, ctx: Context) -> dict[str, Any]:
    """One certificate's realness. UNMEASURED (named) when it carries no Sharpe or day count."""
    s, t = _finite(sr), _finite(days)
    if s is None or t is None or t < 2:
        return {"status": UNMEASURED, "p_real": None,
                "why": "certificate carries no in-sample Sharpe and day count"}
    n_star, n_basis = ctx.n_star(family)
    noise = 1.0 / (t - 1.0)
    vnull, v_basis = ctx.v_null(family)
    v_star = max(noise, vnull or 0.0)
    v_from = "noise floor 1/(T-1)" if v_star == noise else v_basis
    sr0 = math.sqrt(v_star) * emax(n_star)
    z = psr_z(s, t, sr0)
    p_dsr = phi(z)
    pi0, pi0_basis = pi0_for(ctx.pi0, family, timeframe)
    p_real = p_dsr * (1.0 - pi0)
    return {"status": MEASURED, "p_real": float(f"{p_real:.6g}"), "p_dsr": float(f"{p_dsr:.6g}"),
            "z": round(z, 4), "log10_p_dsr": round(log10_phi(z), 4), "pi0": round(pi0, 6),
            "sr": s, "days": int(t), "n_star": n_star, "v_star": round(v_star, 10),
            "sr0": round(sr0, 6), "family": family, "timeframe": timeframe,
            "basis": f"N*={n_star} [{n_basis}]; V*={v_star:.6g} [{v_from}; V_null: {v_basis}]; "
                     f"pi0={pi0:.3f} [{pi0_basis}]"}


def rank_key(sc: Mapping[str, Any]) -> float:
    """A total order on scores that stays informative when p_real underflows: log10 p_real, with
    (1 - pi0) floored at `RANK_PI0_FLOOR` so a family x timeframe measured at pi0 = 1 still
    orders its own certificates by their PSR (they all sit below every pi0 < 1 certificate)."""
    if sc.get("status") != MEASURED:
        return -math.inf
    pi0 = float(sc.get("pi0") or 0.0)
    return float(sc["log10_p_dsr"]) + math.log10(max(1.0 - pi0, RANK_PI0_FLOOR))


# ------------------------------------------------------------------------- published blocks
def false_certificate_share(table: Mapping[str, Any]) -> dict[str, Any]:
    """INFORMATION ONLY: pi0 by family x timeframe, the estimated share of certificates that are
    not real edges. No gate, threshold or certificate reads it."""
    return {"by_family_timeframe": table.get("cells") or {},
            "by_timeframe": table.get("by_timeframe") or {},
            "by_family": table.get("by_family") or {}, "prior": table.get("prior"),
            "prior_basis": table.get("prior_basis"),
            "n_matured_distinct": table.get("n_matured_distinct"),
            "method": table.get("method"),
            "boundary": "information only: moves no gate, voids no certificate"}


def dsr_only_kills(ctx: Context, limit: int = DSR_ONLY_LIST_MAX) -> dict[str, Any]:
    """Cells the judge killed at deflated_sharpe alone that would clear PSR >= 0.95 at (N*, V*).
    READ-ONLY LISTING: nothing is re-judged, admitted or certified by it."""
    kills = ctx.xs.get("dsr_only_kills")
    if not isinstance(kills, list) or (not kills and ctx.xs.get("status") != MEASURED):
        return {"status": UNMEASURED, "n_dsr_only_kills": 0, "would_pass_at_v_star": [],
                "why": ("no judged sweep report on this host: the kills the judge recorded "
                        "cannot be read here")}
    passing = []
    for k in kills:
        sc = score(k.get("sharpe"), k.get("days"), str(k.get("family")), str(k.get("timeframe")),
                   ctx)
        if sc.get("status") == MEASURED and float(sc["p_dsr"]) >= DSR_PASS:
            passing.append({**k, "p_dsr_at_v_star": sc["p_dsr"], "z_at_v_star": sc["z"],
                            "sr0_at_v_star": sc["sr0"], "n_star": sc["n_star"],
                            "v_star": sc["v_star"], "p_real": sc["p_real"]})
    passing.sort(key=lambda r: -float(r["z_at_v_star"]))
    return {"status": MEASURED, "n_dsr_only_kills": len(kills),
            "n_would_pass_at_v_star": len(passing), "would_pass_at_v_star": passing[:limit],
            "definition": ("failed deflated_sharpe and no other gate the judge evaluated; "
                           "`other_gates_evaluated` counts what it did evaluate"),
            "boundary": "read-only listing: no gate changes, nothing is re-judged or admitted"}


def calibration(rows: list[tuple[float, int]], *, rank: list[float] | None = None
                ) -> dict[str, Any]:
    """(p_real, keep) per matured distinct clock, binned into score deciles. SE is the binomial SE
    under the PREDICTION (the hypothesis being tested is that the prediction is right).

    `rank`, when given, orders the bins (log-scale score) where p_real ties or underflows."""
    order = sorted(range(len(rows)), key=lambda i: (rank[i] if rank else rows[i][0]))
    n = len(order)
    bins: list[dict[str, Any]] = []
    for d in range(10):
        idx = order[(d * n) // 10:((d + 1) * n) // 10]
        if not idx:
            continue
        pred = sum(rows[i][0] for i in idx) / len(idx)
        keep = sum(rows[i][1] for i in idx) / len(idx)
        se = math.sqrt(max(pred * (1.0 - pred), 0.0) / len(idx))
        bins.append({"decile": d + 1, "n": len(idx), "predicted_keep": round(pred, 6),
                     "measured_keep": round(keep, 6), "se": round(se, 6),
                     "gap_in_se": round((keep - pred) / se, 3) if se > 0 else None})
    top_idx = order[(10 - CALIBRATION_TOP_DECILES) * n // 10:] if n else []
    top: dict[str, Any] = {"n": len(top_idx)}
    if top_idx:
        pred = sum(rows[i][0] for i in top_idx) / len(top_idx)
        keep = sum(rows[i][1] for i in top_idx) / len(top_idx)
        se = math.sqrt(max(pred * (1.0 - pred), 0.0) / len(top_idx))
        top.update(predicted_keep=round(pred, 6), measured_keep=round(keep, 6), se=round(se, 6),
                   gap_in_se=round((keep - pred) / se, 3) if se > 0 else None)
    gap = top.get("gap_in_se")
    enough = n >= CALIBRATION_MIN_N
    fired = bool(enough and gap is not None and gap < -CALIBRATION_SE)
    over = bool(enough and gap is not None and gap > CALIBRATION_SE)
    if not enough:
        reading = (f"INSUFFICIENT: {n} matured distinct clocks joined to a score, "
                   f"{CALIBRATION_MIN_N} required")
    elif fired:
        reading = "TRIGGER MET: top-decile forward keep is more than 2 SE below predicted"
    elif over:
        reading = ("top-decile forward keep is more than 2 SE ABOVE predicted: the score "
                   "under-predicts (over-charges) -- information, no action")
    else:
        reading = "top-decile forward keep within 2 SE of predicted: the bar stays as it is"
    return {"n_matured_distinct_scored": n, "bins": bins, "top_deciles": top,
            "trigger_line": TRIGGER_LINE, "trigger_met": fired, "reading": reading,
            "acts": False,
            "caveat": ("pi0 is estimated from these same matured clocks, so this is in-sample "
                       "for the (1 - pi0) term: calibration here is necessary, not sufficient"),
            "boundary": "reports only; nothing reads this block to act"}
