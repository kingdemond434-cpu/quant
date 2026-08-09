#!/usr/bin/env python3
"""PAPER-SLEEVE FORWARD RUNNER -- the organ that makes a spawned clock actually breathe.

THE GAP THIS CLOSES, and it is the last link in the chain between mining and a survivor. On
2026-08-05 the desk got ten forward clocks spawned for the first time in its life -- and every one
of them read `evidence: UNMEASURED`, because NOTHING RAN THEM. A sleeve was born (a state file
carrying `shadow_start`), registered (a roster row, paying its multiplicity from birth), and then
left alone. `slot_registry._EVIDENCE` maps eight hardcoded names to eight hardcoded artifacts;
a sleeve spawned tomorrow appears in none of them, so it can never publish a day count, so it can
never accrue, so it can NEVER RESOLVE. Born, registered, charged for, and structurally unable to
finish -- the desk's most expensive recurring defect class (built-never-wired) landed on the one
pipeline whose whole purpose is to produce a survivor.

WHAT ACCRUAL MEANS HERE, stated exactly, because this is the number promotion will rest on. Each
sleeve's state file carries a BASELINE captured at spawn: (n_eff, ic) as its screen measured them
the moment the clock started. This runner re-reads the SAME source artifact each day and records
the cell's current (n_eff, ic). Two facts come out, and they are kept apart on purpose:

  * ROWS ADDED  = n_now - n_baseline. Genuinely out-of-sample observations. This is the clock.
  * IC FORWARD  = (n*ic - n0*ic0) / (n - n0), the increment implied by the two sample statistics.

The second is DERIVED BY DIFFERENCE and labelled so on every row. It is exact when the screen's IC
is a mean of per-observation products, and APPROXIMATE when it is a Pearson correlation computed
over the whole window (the standardisation changes as the sample grows). No screen here declares
which it uses, so the number is published as an estimate and never as a measurement -- a forward
statistic that quietly assumed the friendlier of two definitions would be the phantom-edge
direction, and the desk's whole two-stage law exists to keep that out of Stage B.

ZERO ROWS ADDED IS THE NORMAL STATE ON DAY ONE, and it is recorded as NO-EVIDENCE rather than as
zero effect. A source artifact that has not been regenerated since the clock started supplies no
new observations, and saying "IC forward is 0.0" about a window containing no data is a fabricated
measurement. Progress is reported against `n_needed` -- the rows the cell needs for a forward
rejection at the cohort's own Holm bar -- so every sleeve carries a visible distance-to-resolution
instead of an open-ended wait.

NO PROMOTION AUTHORITY, and it cannot acquire any: this writes evidence artifacts. Nothing here
reads or moves a threshold, sizes a position, or touches capital.

    python scripts/run_paper_sleeve_forward.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.screen_conversion import canonical_row, is_scored_row  # noqa: E402
from libs.research.slot_admission import forward_resolution_days  # noqa: E402

_ROSTER = "data/shadow_sleeves.json"
#: The artifact slot_registry reads for a roster sleeve's day count. One file for every paper
#: sleeve, keyed by name -- so a sleeve spawned tomorrow is covered without editing any map.
OUT = "web/paper_sleeve_forward.json"
#: Append-only observation ledger. The published artifact is a snapshot; this is the history, and
#: a forward clock whose history can be silently rewritten is not evidence.
LEDGER = "data/paper_sleeve_forward.jsonl"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _load(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _find_cell(root: Path, artifact: str, key: str, trial: str) -> dict[str, Any] | None:
    """Re-read the cell this sleeve was screened from, in its ORIGINAL artifact.

    Matching is on the canonical name the converter builds, so a source that reorders its rows
    still resolves to the same hypothesis -- an index-based match would silently re-point a live
    clock at a different cell the first time the screen changed its output order.
    """
    doc = _load(root / artifact) if artifact else None
    if not isinstance(doc, dict):
        return None
    rows = doc.get(key)
    if not isinstance(rows, list):
        return None
    for i, raw in enumerate(rows):
        if not is_scored_row(raw):
            continue
        cell = canonical_row(raw, i)
        if str(cell.get("name")) == trial:
            return cell
    return None


def _observe_full_sweep(
        root: Path, name: str, state: dict[str, Any], *, m_cohort: int) -> dict[str, Any]:
    """Accrue a full-sweep clock from timestamped pooled returns, never vector length.

    Pooled symbol blocks move when an earlier symbol gains a bar, so length differencing relabels
    old returns as forward evidence. Schema v2's (timestamp, symbol) provenance lets this select
    only observations strictly later than the immutable baseline window end. Returns sharing one
    timestamp are averaged into one cross-sectional portfolio observation before evidence is
    counted; forty symbols reacting to one market impulse are not forty independent events.
    """
    artifact = str(state.get("pnl_artifact") or "data/full_sweep_survivor_pnl.npz")
    key = str(state.get("pnl_key") or state.get("trial") or "")
    baseline_end = str(state.get("baseline_window_end") or "")
    row: dict[str, Any] = {
        "name": name, "observed_utc": _now().isoformat(timespec="seconds"),
        "shadow_start": state.get("shadow_start"), "origin_artifact": artifact,
        "origin_key": key, "trial": state.get("trial"), "source_kind": "full_sweep_npz",
    }
    try:
        base_dt = datetime.fromisoformat(baseline_end.replace("Z", "+00:00"))
        if base_dt.tzinfo is None:
            base_dt = base_dt.replace(tzinfo=UTC)
        baseline_ns = int(base_dt.timestamp() * 1_000_000_000)
    except (ValueError, OverflowError):
        row["evidence"] = "UNRUNNABLE"
        row["why"] = "state carries no parseable immutable baseline_window_end"
        return row

    path = root / artifact
    try:
        with np.load(path, allow_pickle=False) as z:
            if key not in z.files:
                raise KeyError(f"candidate return key {key!r} absent")
            if "__timestamp_ns" not in z.files or "__symbol" not in z.files:
                row["evidence"] = "NO-EVIDENCE"
                row["why"] = (
                    "survivor PnL sidecar predates provenance schema v2. Re-run full_sweep once; "
                    "old vector length cannot be used because pooled blocks shift as bars arrive.")
                return row
            values = np.asarray(z[key], dtype=float)
            times = np.asarray(z["__timestamp_ns"], dtype=np.int64)
            symbols = np.asarray(z["__symbol"]).astype(str)
    except (OSError, ValueError, KeyError) as exc:
        row["evidence"] = "SOURCE-GONE"
        row["why"] = f"{artifact} unreadable for {key!r}: {type(exc).__name__}: {exc}"
        return row

    if len(values) != len(times) or len(values) != len(symbols):
        row["evidence"] = "UNRUNNABLE"
        row["why"] = (
            f"provenance length mismatch: returns={len(values)}, timestamps={len(times)}, "
            f"symbols={len(symbols)}")
        return row
    mask = (times > baseline_ns) & np.isfinite(values) & (symbols != "")
    if not np.any(mask):
        row.update({"evidence": "NO-EVIDENCE", "rows_added": 0,
                    "raw_rows_added": 0, "distinct_timestamps": 0})
        row["why"] = (
            "no finite return is later than the immutable baseline window end. This is normal "
            "until full_sweep is regenerated on newly collected bars; zero observations is not "
            "a measured zero effect.")
        return row

    t_new = times[mask]
    r_new = values[mask]
    unique_t, inverse = np.unique(t_new, return_inverse=True)
    sums = np.bincount(inverse, weights=r_new)
    counts = np.bincount(inverse)
    portfolio_returns = sums / np.maximum(counts, 1)

    baseline = state.get("baseline") if isinstance(state.get("baseline"), dict) else {}
    horizon_days = float(baseline.get("horizon_days") or 0.0)
    step_s = (float(np.median(np.diff(unique_t))) / 1_000_000_000.0
              if len(unique_t) > 1 else 0.0)
    overlap = max(1.0, horizon_days * 86400.0 / step_s) if step_s > 0 else 1.0
    from libs.validation.forward_stats import autocorr_factor, holm_bar, nw_tstat
    dependence = max(overlap, autocorr_factor(portfolio_returns))
    n_eff = float(len(portfolio_returns)) / dependence
    base_ic = baseline.get("ic")
    n_needed = None
    if isinstance(base_ic, (int, float)) and float(base_ic) != 0.0:
        n_needed = (holm_bar(m_cohort) / abs(float(base_ic))) ** 2

    row.update({
        "evidence": "ACCRUING",
        "raw_rows_added": int(mask.sum()),
        "distinct_symbols": len(np.unique(symbols[mask])),
        "distinct_timestamps": len(unique_t),
        "overlap_factor": round(overlap, 3),
        "dependence_factor": round(dependence, 3),
        "rows_added": len(unique_t),
        "effective_observations": round(n_eff, 3),
        "forward_mean_bps": round(float(np.mean(portfolio_returns)) * 1e4, 6),
        "forward_nw_t": nw_tstat(portfolio_returns),
        "fixed_sample_holm_bar_diagnostic": holm_bar(m_cohort),
        "n_needed_for_forward_rejection": (
            round(float(n_needed), 1) if n_needed is not None else None),
        "progress_to_resolution": (
            round(n_eff / float(n_needed), 4) if n_needed else None),
        "why": (
            "ACCRUING at zero capital. The t/bar fields are diagnostics only: daily repeated "
            "looks have no promotion authority; the promotion gate must use the standing "
            "anytime-valid process at the same Holm alpha."),
    })
    return row


def _observe(root: Path, name: str, state: dict[str, Any], *, m_cohort: int) -> dict[str, Any]:
    """One day's reading for one sleeve. Never asserts -- reports what it could not determine."""
    if state.get("source_kind") == "full_sweep_npz":
        return _observe_full_sweep(root, name, state, m_cohort=m_cohort)

    started = state.get("shadow_start")
    _base = state.get("baseline")
    base: dict[str, Any] = _base if isinstance(_base, dict) else {}
    artifact = str(state.get("origin_artifact") or "")
    key = str(state.get("origin_key") or "")
    trial = str(state.get("trial") or "")
    row: dict[str, Any] = {
        "name": name, "observed_utc": _now().isoformat(timespec="seconds"),
        "shadow_start": started, "origin_artifact": artifact, "origin_key": key, "trial": trial,
    }
    ts = None
    if isinstance(started, str):
        try:
            ts = datetime.fromisoformat(started)
        except ValueError:
            ts = None
    if ts is not None:
        row["forward_days"] = round((_now() - (ts if ts.tzinfo else ts.replace(tzinfo=UTC)))
                                    .total_seconds() / 86400.0, 3)

    if not artifact or not key or not trial:
        row["evidence"] = "UNRUNNABLE"
        row["why"] = ("the sleeve's state file names no origin artifact/key/trial, so there is "
                      "nothing to re-read. Spawned before the spawner recorded provenance; it "
                      "must be retired by a ledgered decision or re-spawned, never left standing "
                      "-- a clock that cannot be run still charges the cohort its multiplicity.")
        return row

    cell = _find_cell(root, artifact, key, trial)
    if cell is None:
        row["evidence"] = "SOURCE-GONE"
        row["why"] = (f"{artifact}#{key} no longer carries a cell named {trial!r}. The clock "
                      "cannot accrue and is NOT counted as a measured zero: a vanished source is "
                      "an unknown, and an unknown that reads as 'no effect' is how a fail-open "
                      "becomes a false negative.")
        return row

    n_now = float(cell.get("n_eff") or cell.get("n") or 0.0)
    ic_now = cell.get("ic")
    n_0 = float(base.get("n_eff") or 0.0)
    ic_0 = base.get("ic")
    horizon = float(base.get("horizon_days") or cell.get("horizon_days") or 0.0)
    row.update({"n_now": n_now, "ic_now": ic_now, "n_baseline": n_0, "ic_baseline": ic_0})

    if isinstance(ic_now, (int, float)) and horizon > 0:
        _, n_needed, bar_z = forward_resolution_days(float(ic_now), horizon, m=m_cohort)
        row["n_needed_for_forward_rejection"] = (None if not math.isfinite(n_needed)
                                                 else round(n_needed, 1))
        row["forward_bar_z"] = bar_z

    added = n_now - n_0
    row["rows_added"] = round(added, 2)
    if added <= 0:
        # NOT "no effect". The source has supplied nothing new since the clock started, which is
        # the expected reading on day one and after any day the collector did not run.
        row["evidence"] = "NO-EVIDENCE"
        row["why"] = ("no rows added since the baseline -- the source artifact has not been "
                      "regenerated since this clock started. An IC over an empty window is a "
                      "fabricated number, so none is reported.")
        return row

    if isinstance(ic_now, (int, float)) and isinstance(ic_0, (int, float)) and added > 0:
        row["ic_forward_estimate"] = round((n_now * float(ic_now) - n_0 * float(ic_0)) / added, 6)
        row["ic_forward_basis"] = (
            "DERIVED BY DIFFERENCE from the two sample statistics, not measured on the forward "
            "rows directly. Exact if the screen's IC is a mean of per-observation products; "
            "APPROXIMATE if it is a Pearson correlation over the whole window, because the "
            "standardisation moves as the sample grows. Published as an estimate on purpose -- "
            "assuming the friendlier definition would run in the phantom-edge direction.")
    row["evidence"] = "ACCRUING"
    frac = (added / row["n_needed_for_forward_rejection"]
            if row.get("n_needed_for_forward_rejection") else None)
    row["progress_to_resolution"] = round(frac, 4) if frac is not None else None
    return row


def run(root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    roster = _load(base / _ROSTER)
    names = sorted({str(x) for x in roster if str(x).strip()}) if isinstance(roster, list) else []
    try:
        from libs.research.slot_registry import derive_slots
        m_cohort = int(derive_slots().get("m_upper") or 12)
    except Exception:
        m_cohort = 12

    sleeves: dict[str, Any] = {}
    skipped: list[dict[str, str]] = []
    for name in names:
        state = _load(base / "data" / f"{name}_shadow_state.json")
        if not isinstance(state, dict) or not state.get("shadow_start"):
            # A roster row with no birth certificate is one of the BUILT-IN derivative sleeves,
            # which publish through their own artifact. Named, never silently counted as run.
            skipped.append({"name": name,
                            "why": "no data/<name>_shadow_state.json with a shadow_start -- not a "
                                   "paper sleeve (built-in derivative clocks publish elsewhere)"})
            continue
        sleeves[name] = _observe(base, name, state, m_cohort=m_cohort)

    accruing = [s for s in sleeves.values() if s.get("evidence") == "ACCRUING"]
    payload = {
        "updated": _now().isoformat(timespec="seconds"),
        "m_cohort": m_cohort,
        "n_sleeves": len(sleeves),
        "n_accruing": len(accruing),
        "sleeves": sleeves,
        "skipped": skipped,
        # slot_registry reads these two keys per sleeve; published at the top level too so a
        # reader that wants the cohort's health does not have to walk every sleeve.
        "authority": ("PAPER only -- accrues forward evidence, never touches capital (L1.6). "
                      "Nothing here reads or moves a threshold."),
        "note": ("`rows_added` is the clock. `ic_forward_estimate` is DERIVED BY DIFFERENCE and "
                 "labelled per row -- it is an estimate, never a measurement, until a screen "
                 "declares its IC definition. Zero rows added is NO-EVIDENCE, not zero effect."),
    }
    (base / OUT).parent.mkdir(parents=True, exist_ok=True)
    (base / OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    ledger = base / LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for srow in sleeves.values():
            fh.write(json.dumps(srow) + "\n")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run()
    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    print(f"paper-sleeve forward: {rep['n_sleeves']} sleeve(s), {rep['n_accruing']} ACCRUING "
          f"(Holm cohort m={rep['m_cohort']})")
    for name, s in sorted(rep["sleeves"].items(),
                          key=lambda kv: -(kv[1].get("progress_to_resolution") or 0.0)):
        need = s.get("n_needed_for_forward_rejection")
        prog = s.get("progress_to_resolution")
        bar = f"{prog:6.1%}" if prog is not None else "   n/a"
        print(f"  {s.get('evidence','?'):12s} {bar}  +{s.get('rows_added', 0):>9,.0f} rows "
              f"of {need if need is not None else '?':>10}  {name[:52]}")
    for s in rep["skipped"]:
        print(f"  SKIPPED      {s['name'][:52]}: {s['why'][:70]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
