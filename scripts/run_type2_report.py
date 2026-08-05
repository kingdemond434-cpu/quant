#!/usr/bin/env python3
"""TYPE-II COST REPORT -- label every recorded negative on this checkout with its own power.

    python -u scripts/run_type2_report.py [--json data/type2_cost.json] [--root .]

WHAT THIS ANSWERS. The desk has produced zero survivors across every screen it runs, and each zero
is written down as "no edge found". This walks the negatives that are ACTUALLY ON DISK and asks one
question of each: could this rejection have SEEN an edge of the size the desk is looking for? A
rejection that could not is absence of evidence and must never be read as evidence of absence.

READS ONLY, WRITES ONE ARTIFACT. It changes no verdict, no threshold and no gate; alpha stays 0.05.
An UNDERPOWERED label is a statement about what the desk KNOWS, never a licence to re-open a
graveyard row -- the graveyard is permanent by construction.

WHAT IT REFUSES TO DO. Artifacts named in the docs but absent from this checkout (runtime-only
files that live on the VPS) are reported as NOT-READABLE-HERE with the reason, never reconstructed
from the prose that cites them. And graveyard rows are labelled INDETERMINATE rather than parsed
for a sample size: the rows contain digits, but "n=5 majors" is a symbol count and "180 bars" is a
per-symbol length, and a regex that cannot tell those apart would MANUFACTURE the evidence whose
absence is the finding. Every row here is computed from a machine-readable field an artifact
actually records.

THE MULTIPLICITY EACH ROW IS CHARGED is the one its own gate applied, taken from the artifact:
the campaign's candidate count for campaign rows, the mechanism count for pooled rows, the
deflation config count for the intraday runs, and N=1 for the Stage-A screens -- whose `powered`
flag is itself computed at N=1, so this module reproduces the screen rather than re-judging it.
Where an artifact records no multiplicity, N=1 is used: the smallest it can be, and therefore the
reading most favourable to the desk's claim of knowledge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.validation.type2_cost import (  # noqa: E402
    CROSS_SYMBOL_STRATEGY_CORR,
    DECLARED_CORRELATION_EFFECTS,
    DECLARED_SHARPES,
    DEFAULT_ALPHA,
    POWERED,
    PPY,
    REFERENCE_CORRELATION_EFFECT,
    REFERENCE_SHARPE,
    UNDERPOWERED,
    Type2Cost,
    correlation_negative,
    headline,
    indeterminate,
    sharpe_negative,
)

_DEFAULT_OUT = Path("data/type2_cost.json")

#: The measured-context documents this instrument is built on. Their EXISTENCE is verified and
#: reported; their contents are cited, never re-derived here.
_CITATIONS = (
    "docs/research/gate_power_audit.md",
    "docs/research/REALITY_CHECK_POWER.md",
    "libs/research/axis_screen.py",
    "reports/reality_check_audit.json",
)

#: Bars per year by artifact interval. The intraday runs differ ONLY in bar size and cover the same
#: 61 out-of-sample days, so converting each with its own clock is what stops the 5-minute run from
#: reading as twelve times the evidence of the hourly one. t = SR_ann * sqrt(YEARS): bar count is
#: not evidence.
_BARS_PER_YEAR = {"5m": 365.0 * 24 * 12, "15m": 365.0 * 24 * 4, "1h": 365.0 * 24}

#: Declared effect sizes for the token-unlock event study, which is on a standardised-mean scale
#: rather than an IC scale. DECLARED IN THIS FILE, in advance, and stated in the artifact: a 0.2
#: standardised abnormal return is a small-but-real event effect. Power at a declared effect is the
#: question; power at the OBSERVED effect would be a restatement of the p-value.
_UNLOCK_EFFECTS = (0.1, 0.2, 0.3)
_UNLOCK_REFERENCE = 0.2


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------ docs/graveyard.md


def _graveyard_rows(text: str) -> list[tuple[str, str]]:
    """(hypothesis, verdict) for every kill row in a table whose first header cell is 'Hypothesis'.

    Scoped by header on purpose: docs/graveyard.md also carries an era/venue table that is
    narrative, not a list of rejections, and counting its rows as negatives would inflate the
    denominator with things that were never tested.

    A table is opened by a `|---|` separator and identified by the pipe row immediately above it,
    and it stays open across intervening PROSE. The first draft closed the table on any non-pipe
    line and silently lost 26 of 44 kills to the "Standing conclusion" paragraph sitting in the
    middle of one -- an undercount that would have flattered the headline by dropping unlabellable
    rows from the denominator, which is the exact defect this instrument names.
    """
    rows: list[tuple[str, str]] = []
    in_kill_table = False
    pending: list[str] | None = None

    def commit() -> None:
        if pending is not None and in_kill_table and len(pending) >= 2:
            rows.append((pending[0], pending[1]))

    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        if all(c and set(c) <= {"-", ":"} for c in cells):
            # A separator identifies the row above it as a HEADER, so that row is discarded rather
            # than committed and the table's kind is decided from it.
            in_kill_table = pending is not None and pending[0].lower().startswith("hypothesis")
            pending = None
            continue
        commit()
        pending = cells
    commit()
    return rows


def read_graveyard(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "docs/graveyard.md"
    if not p.exists():
        return [], [{"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "file absent"}]
    out: list[Type2Cost] = []
    for name, verdict in _graveyard_rows(p.read_text("utf-8")):
        clean = re.sub(r"\s+", " ", re.sub(r"[`*]", "", name)).strip()
        mentions = bool(re.search(r"\bn\s*=|\bbars\b|\bdays\b|\bobs\b|\bd\b", verdict))
        out.append(
            indeterminate(
                clean[:110],
                "permanent kill recorded with a verdict but NO machine-readable sample size, so "
                "whether it is 'looked and it is not there' or 'could not have seen it' cannot be "
                "determined from the row"
                + (
                    " (the prose mentions a sample quantity; it is NOT parsed here because the "
                    "same tokens denote symbol counts and per-symbol lengths in adjacent rows)"
                    if mentions
                    else ""
                ),
                source="docs/graveyard.md",
            )
        )
    return out, []


# ------------------------------------------------------------ reports/real_campaign*.json


def read_real_campaigns(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    out: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for p in sorted((root / "reports").glob("real_campaign*.json")):
        d = _read_json(p)
        if not isinstance(d, dict):
            unread.append(
                {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "unparseable JSON"}
            )
            continue
        dig = _digest(p)
        if dig in seen:
            unread.append(
                {
                    "artifact": str(p),
                    "status": "DUPLICATE",
                    "why": f"byte-identical to {seen[dig]}; counted once",
                }
            )
            continue
        seen[dig] = p.name
        out.extend(_campaign_costs(p.name, d))
    return out, unread


def _campaign_costs(stem: str, d: dict[str, Any]) -> list[Type2Cost]:
    bars: dict[str, float] = {str(k): float(v) for k, v in (d.get("bars_per_symbol") or {}).items()}
    shortest = min(bars.values()) if bars else 0.0
    n_cand = int(d.get("n_candidates") or 0)
    out: list[Type2Cost] = []

    out.append(
        sharpe_negative(
            f"CAMPAIGN {stem}: 0 of {n_cand} candidates clear every gate",
            source=f"reports/{stem}",
            n_bars=shortest,
            ppy=PPY,
            n_tests=max(1, n_cand),
            note=(
                "per-symbol daily campaign; multiplicity charged at the recorded candidate count, "
                "elapsed time at the SHORTEST symbol history in the panel"
            ),
        )
    )

    pooled = d.get("pooled_by_mechanism") or {}
    n_mech = int(pooled.get("n_mechanisms") or 0)
    for row in pooled.get("rows") or []:
        syms = [str(s) for s in row.get("symbols") or []]
        n_units = int(row.get("n_symbols") or len(syms) or 1)
        # THE SHORTEST CONSTITUENT HISTORY, because the artifact does not record the length of the
        # pooled series itself. Taking the shortest is a LOWER bound on the elapsed evidence, so it
        # can only under-state power and over-state how blind the test was -- the direction that
        # claims less. Taking the longest would credit the pooled series with history that only
        # some of its symbols have.
        n_bars = min((bars[s] for s in syms if s in bars), default=shortest)
        out.append(
            sharpe_negative(
                str(row.get("name") or "pooled"),
                source=f"reports/{stem}#pooled",
                n_bars=n_bars,
                ppy=PPY,
                n_tests=max(1, n_mech),
                n_units=n_units,
                cross_corr=CROSS_SYMBOL_STRATEGY_CORR,
                note=(
                    f"pooled across {n_units} symbols at the measured same-mechanism cross-symbol "
                    f"strategy correlation {CROSS_SYMBOL_STRATEGY_CORR}; failed "
                    f"{','.join(str(g) for g in row.get('failed_gates') or []) or 'nothing'}"
                ),
            )
        )

    for row in d.get("top_by_oos") or []:
        failed = [str(g) for g in row.get("failed_gates") or []]
        if not failed:
            continue
        out.append(
            sharpe_negative(
                str(row.get("name") or "candidate"),
                source=f"reports/{stem}#per_symbol",
                n_bars=float(row.get("n_bars") or 0.0),
                ppy=PPY,
                n_tests=max(1, n_cand),
                note=(
                    "one of the artifact's published per-symbol rows (the artifact records only "
                    f"the top {len(d.get('top_by_oos') or [])} of {n_cand} individually); failed "
                    + ",".join(failed)
                ),
            )
        )
    return out


# ------------------------------------------------------- reports/gauntlet_certification.json


def read_gauntlet_certification(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "reports/gauntlet_certification.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    camp = d.get("campaign") or {}
    design = d.get("design") or {}
    t = float(camp.get("T") or 0.0)
    n = int(camp.get("N") or 0)
    return [
        sharpe_negative(
            f"GAUNTLET CERTIFICATION: N={n} candidates over T={t:g} bars, 0 survivors",
            source="reports/gauntlet_certification.json",
            n_bars=t,
            ppy=PPY,
            n_tests=max(1, n),
            note=(
                # This artifact is the MODEL for what the rest should look like: it already records
                # its own blindness rather than reporting a bare zero.
                "the certification records its own hurdle_annual_sharpe "
                f"{design.get('hurdle_annual_sharpe')} and underpowered_below_annual_sharpe "
                f"{design.get('underpowered_below_annual_sharpe')}"
            ),
        )
    ], []


# ------------------------------------------------------------------ Stage-A correlation screens


def _screen_cell(
    cell: dict[str, Any], *, name: str, source: str, n_tests: int, declared_trials: int = 1
) -> Type2Cost:
    """Label one axis-screen-shaped cell, reproducing the screen's own n_eff and power convention.

    The screen's `powered` flag is computed at N=1 with a two-sided 1.96, so `n_tests` is 1 here and
    the agreement with the recorded flag is asserted in the note. Re-judging the cell under a
    different multiplicity would REPLACE the screen's verdict instead of labelling it, which this
    instrument is forbidden from doing.

    `declared_trials` is therefore reported and never applied. When a cell clears its own power
    floor at N=1 but would not clear it at the trial count the artifact itself declares, the note
    says so -- the reader gets the fact, the screen keeps its verdict.
    """
    cost = correlation_negative(
        name,
        source=source,
        n_obs=float(cell.get("n") or 0.0),
        horizon_periods=float(cell.get("horizon_days") or 1.0),
        panel_width=int(cell.get("panel_width") or 1),
        n_tests=n_tests,
        note="",
    )
    rec_powered = cell.get("powered")
    rec_mdi = cell.get("min_detectable_ic")
    # THREE STATES, NOT TWO. A screen that recorded NO `powered` flag has not disagreed with
    # anything -- there is nothing to disagree with. Collapsing "no flag" into DISAGREES manufactures
    # a finding out of a silence, and it fires on exactly the cells least able to defend themselves:
    # the converted screens, whose sources report a verdict and a detection floor but never a
    # boolean. Once every converted cell reads DISAGREES the label stops discriminating, and a REAL
    # disagreement -- the thing this note exists to surface -- is buried among them.
    if not isinstance(rec_powered, bool):
        agree = ("screen recorded NO powered flag -- nothing to agree or disagree with; this "
                 "instrument's own label stands alone for this cell")
    elif rec_powered == (cost.label == POWERED):
        agree = "screen agrees"
    else:
        agree = "DISAGREES WITH THE SCREEN'S OWN FLAG -- inspect"
    fragile = ""
    if cost.label == POWERED and declared_trials > 1:
        at_declared = correlation_negative(
            name, n_obs=cost.n_eff, n_tests=declared_trials, source=source
        )
        if at_declared.label != POWERED:
            fragile = (
                f". FRAGILE: powered only because the screen charges N=1; at the "
                f"{declared_trials} trials this artifact itself declares the floor moves to "
                f"{at_declared.min_detectable_effect:.4f} and the cell would not clear it. "
                "Reported, NOT applied -- the screen's verdict is unchanged"
            )
    return replace(
        cost,
        note=(
            f"screen verdict {cell.get('verdict')}; recorded powered={rec_powered}, "
            f"recorded min_detectable_ic={rec_mdi}; {agree}{fragile}"
        ),
    )


def read_axis_screens(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    out: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    d_dir = root / "reports/axis_screens"
    if not d_dir.exists():
        return [], [
            {
                "artifact": str(d_dir),
                "status": "NOT-READABLE-HERE",
                "why": "no axis-screen artifacts in this checkout",
            }
        ]
    for p in sorted(d_dir.glob("*.json")):
        d = _read_json(p)
        if not isinstance(d, dict):
            unread.append(
                {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "unparseable JSON"}
            )
            continue
        declared = int(d.get("trials_declared") or len(d.get("trials") or []) or 1)
        for cell in d.get("trials") or []:
            if not isinstance(cell, dict) or cell.get("verdict") == "SCREEN-INTERESTING":
                continue
            out.append(
                _screen_cell(
                    cell,
                    name=str(cell.get("name") or p.stem),
                    source=f"reports/axis_screens/{p.name}",
                    n_tests=1,
                    declared_trials=declared,
                )
            )
    return out, unread


def read_exchange_netflow(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "reports/screen_exchange_netflow.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    declared = int(d.get("n_trials") or len(d.get("cells") or []) or 1)
    out = [
        _screen_cell(
            cell,
            name=str(cell.get("name") or "netflow_cell"),
            source="reports/screen_exchange_netflow.json",
            n_tests=1,
            declared_trials=declared,
        )
        for cell in d.get("cells") or []
        if isinstance(cell, dict) and cell.get("verdict") != "SCREEN-INTERESTING"
    ]
    return out, []


# ------------------------------------------------------------------ reports/intraday_rotation*


def read_intraday(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    out: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    for p in sorted((root / "reports").glob("intraday_rotation*.json")):
        d = _read_json(p)
        if not isinstance(d, dict):
            unread.append(
                {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "unparseable JSON"}
            )
            continue
        interval = str(d.get("interval") or "5m")
        ppy = _BARS_PER_YEAR.get(interval)
        if ppy is None:
            unread.append(
                {
                    "artifact": str(p),
                    "status": "NOT-READABLE-HERE",
                    "why": f"unknown bar interval {interval!r}; bars cannot be converted to years",
                }
            )
            continue
        proto = d.get("protocol") or {}
        test_bars = float(proto.get("test_bars") or 0.0)
        n_cfg = int(proto.get("n_configs_deflation") or 1)
        for leg in ("rotation", "continuation"):
            gate = (d.get("deployment_gate") or {}).get(leg) or {}
            if not gate:
                continue
            obs = gate.get("oos_annualised_sharpe")
            out.append(
                sharpe_negative(
                    f"INTRADAY {interval} {leg}: {gate.get('verdict')}",
                    source=f"reports/{p.name}",
                    n_bars=test_bars,
                    ppy=ppy,
                    n_tests=max(1, n_cfg),
                    note=(
                        f"{test_bars:g} out-of-sample {interval} bars = the same 61 elapsed days "
                        f"every interval in this family covers; observed OOS ann. Sharpe {obs}. "
                        "A decisively NEGATIVE observed Sharpe is a valid statement that THIS "
                        "configuration loses money; the label below speaks only to whether a "
                        "genuine POSITIVE edge of the reference size could have been detected."
                    ),
                )
            )
    return out, unread


# ------------------------------------------------------------------------- data/ screen outputs


def read_unlock_screen(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "data/unlock_event_screen.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    n_trials = int(d.get("trials") or 1)
    out: list[Type2Cost] = []
    for cell in d.get("cells") or []:
        if not isinstance(cell, dict) or cell.get("passed"):
            continue
        out.append(
            correlation_negative(
                f"unlock {cell.get('category')} pct>={cell.get('pct_circ_now_min')} "
                f"N={cell.get('window_days')}d",
                source="data/unlock_event_screen.json",
                n_obs=float(cell.get("n_effective") or 0.0),
                n_tests=max(1, n_trials),
                effects=_UNLOCK_EFFECTS,
                reference_effect=_UNLOCK_REFERENCE,
                effect_unit="standardised_mean",
                note=(
                    f"event study, {cell.get('n_events')} events -> n_effective "
                    f"{cell.get('n_effective')} after overlap; declared reference effect "
                    f"{_UNLOCK_REFERENCE} standardised abnormal return (declared in "
                    "scripts/run_type2_report.py, not read off the observed statistic); "
                    f"observed t {cell.get('t_stat')} against the artifact's own bar "
                    f"{cell.get('bar')}"
                ),
            )
        )
    return out, []


def read_cot_screen(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    p = root / "data/cot_screen_summary.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    ghr = d.get("ghr") or {}
    n_trials = int(d.get("trials_charged") or 1)
    out: list[Type2Cost] = []
    for row in ghr.get("rows") or []:
        if not isinstance(row, dict):
            continue
        out.append(
            correlation_negative(
                f"COT {row.get('asset')}/{row.get('construction')} lagged predictability",
                source="data/cot_screen_summary.json",
                n_obs=float(row.get("n") or 0.0),
                n_tests=max(1, n_trials),
                effect_unit="lagged_beta_correlation",
                note=(
                    f"observed lagged t {row.get('t_lagged')}; the artifact's HEADLINE is the "
                    f"POOLED lagged t {ghr.get('pooled_lagged_t')} across all "
                    f"{len(ghr.get('rows') or [])} cells, which is NOT labelled here: the "
                    "artifact records no cross-asset correlation, so the pooled effective sample "
                    "cannot be computed without inventing one"
                ),
            )
        )
    return out, []


def read_moat(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    """The moat screen. On this checkout it is BLOCKED with zero rows -- so it is reported, not read.

    docs/research/VPS_STATE_20260805.md cites a 2026-08-02 moat_campaign.json with 48 candidates,
    n_obs 1,065 and two screen survivors whose OOS Sharpes (0.103, 0.098) sit at the same 0.100
    ceiling every failed mechanism reached. That file is runtime state on the VPS and is NOT in
    this checkout. Reconstructing its rows from the prose that cites them would fabricate exactly
    the kind of record this instrument exists to demand, so it is reported as NOT-READABLE-HERE.
    """
    p = root / "reports/moat_campaign.json"
    d = _read_json(p)
    if not isinstance(d, dict):
        return [], [
            {"artifact": str(p), "status": "NOT-READABLE-HERE", "why": "absent or unparseable"}
        ]
    rows = d.get("rows") or []
    if not rows:
        return [], [
            {
                "artifact": str(p),
                "status": "NOT-READABLE-HERE",
                "why": (
                    f"artifact status {d.get('status')!r}: {d.get('blocker')}. The 48-candidate / "
                    "n_obs 1,065 moat run cited by docs/research/VPS_STATE_20260805.md is VPS "
                    "runtime state and is not in this checkout; its rows are NOT reconstructed"
                ),
            }
        ]
    return [], [
        {
            "artifact": str(p),
            "status": "UNHANDLED-SHAPE",
            "why": f"{len(rows)} rows present but this reader was written against the empty shape",
        }
    ]


_READERS = (
    ("docs/graveyard.md", read_graveyard),
    ("reports/real_campaign*.json", read_real_campaigns),
    ("reports/gauntlet_certification.json", read_gauntlet_certification),
    ("reports/axis_screens/*.json", read_axis_screens),
    ("reports/screen_exchange_netflow.json", read_exchange_netflow),
    ("reports/intraday_rotation*.json", read_intraday),
    ("data/unlock_event_screen.json", read_unlock_screen),
    ("data/cot_screen_summary.json", read_cot_screen),
    ("reports/moat_campaign.json", read_moat),
)


def collect(root: Path) -> tuple[list[Type2Cost], list[dict[str, Any]]]:
    costs: list[Type2Cost] = []
    unread: list[dict[str, Any]] = []
    for _label, reader in _READERS:
        got, missing = reader(root)
        costs.extend(got)
        unread.extend(missing)
    return costs, unread


# ------------------------------------------------------------------------------------- printing


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt(x: float, nd: int = 3) -> str:
    """A number, or an explicit 'n/a'. An unmeasured quantity must never print as a measured one."""
    return f"{x:.{nd}f}" if math.isfinite(x) else "n/a"


def _cost_of_rejecting(c: Type2Cost) -> str:
    """P(this gate rejects | a true edge of the reference size exists) = 1 - power."""
    return _fmt(1.0 - c.power_at_reference) if math.isfinite(c.power_at_reference) else "n/a"


def print_report(costs: list[Type2Cost], unread: list[dict[str, Any]], root: Path) -> None:
    print("\nTYPE-II COST OF THE DESK'S RECORDED NEGATIVES")
    print("  POWERED-NEGATIVE = looked and it is not there   (negative knowledge)")
    print("  UNDERPOWERED     = could not have seen it       (no information either way)")
    print("  INDETERMINATE    = records no sample size       (unlabellable; counted as not powered)")
    print(f"  alpha {DEFAULT_ALPHA} -- unchanged. Reference effects: annualised Sharpe "
          f"{REFERENCE_SHARPE:g}, correlation {REFERENCE_CORRELATION_EFFECT:g}.")

    print("\nCITATIONS (existence verified, contents cited not re-derived)")
    for c in _CITATIONS:
        print(f"  {'OK     ' if (root / c).exists() else 'MISSING'} {c}")

    print(f"\n{'source':<40} {'negative':<52} {'label':<18} {'unit':<24} "
          f"{'min detect':>10} {'pow@ref':>8} {'P(rej|ref)':>10}")
    for c in sorted(costs, key=lambda z: (z.source, z.name)):
        print(
            f"{_trunc(c.source, 40):<40} {_trunc(c.name, 52):<52} {c.label:<18} "
            f"{_trunc(c.effect_unit, 24):<24} {_fmt(c.min_detectable_effect):>10} "
            f"{_fmt(c.power_at_reference):>8} {_cost_of_rejecting(c):>10}"
        )

    print(f"\n{'BY SOURCE':<44} {'n':>5} {'powered':>8} {'under':>8} {'indet':>8} {'% powered':>10}")
    for src in sorted({c.source for c in costs}):
        rows = [c for c in costs if c.source == src]
        h = headline(rows)
        print(f"{_trunc(src, 44):<44} {h.n_negatives:>5} {h.n_powered:>8} {h.n_underpowered:>8} "
              f"{h.n_indeterminate:>8} {h.fraction_powered:>9.1%}")

    if unread:
        print("\nNOT READABLE ON THIS CHECKOUT (reported, never reconstructed)")
        for u in unread:
            print(f"  [{u['status']}] {u['artifact']}\n      {u['why']}")

    h = headline(costs)
    print("\nDESK HEADLINE")
    print(f"  {h.summary()}")
    powered_rows = [c for c in costs if c.label == POWERED]
    if powered_rows:
        worst = max(powered_rows, key=lambda z: z.min_detectable_effect)
        print(f"  weakest powered negative: {_trunc(worst.name, 70)} "
              f"(min detectable {_fmt(worst.min_detectable_effect)} {worst.effect_unit})")
    under_rows = [c for c in costs if c.label == UNDERPOWERED]
    if under_rows:
        best = min(under_rows, key=lambda z: z.min_detectable_effect)
        print(f"  closest to powered but not there: {_trunc(best.name, 70)} "
              f"(min detectable {_fmt(best.min_detectable_effect)} {best.effect_unit}, "
              f"power {_fmt(best.power_at_reference)})")


def build_artifact(costs: list[Type2Cost], unread: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    h = headline(costs)
    by_source: dict[str, Any] = {}
    for src in sorted({c.source for c in costs}):
        s = headline([c for c in costs if c.source == src])
        by_source[src] = {
            "n_negatives": s.n_negatives,
            "n_powered": s.n_powered,
            "n_underpowered": s.n_underpowered,
            "n_indeterminate": s.n_indeterminate,
            "fraction_powered": round(s.fraction_powered, 4)
            if s.fraction_powered == s.fraction_powered
            else None,
        }
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "instrument": "libs/validation/type2_cost.py",
        "authority": (
            "LABELS ONLY. This artifact changes no verdict, no threshold and no gate; alpha is "
            "0.05 and stays there. An UNDERPOWERED label says the desk knows less than it wrote "
            "down -- it is never a licence to re-open a permanent kill."
        ),
        "alpha": DEFAULT_ALPHA,
        "reference_effects": {
            "annualised_sharpe": REFERENCE_SHARPE,
            "correlation": REFERENCE_CORRELATION_EFFECT,
            "standardised_mean_unlock_screen": _UNLOCK_REFERENCE,
        },
        "declared_effects": {
            "annualised_sharpe": list(DECLARED_SHARPES),
            "correlation": list(DECLARED_CORRELATION_EFFECTS),
            "standardised_mean_unlock_screen": list(_UNLOCK_EFFECTS),
        },
        "citations": {c: (root / c).exists() for c in _CITATIONS},
        "headline": {
            "n_negatives": h.n_negatives,
            "n_powered": h.n_powered,
            "n_underpowered": h.n_underpowered,
            "n_indeterminate": h.n_indeterminate,
            "fraction_powered": round(h.fraction_powered, 4)
            if h.fraction_powered == h.fraction_powered
            else None,
            "verdict": h.verdict,
            "summary": h.summary(),
        },
        "by_source": by_source,
        "not_readable_here": unread,
        "negatives": [c.as_dict() for c in costs],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=_DEFAULT_OUT, help="output artifact path")
    ap.add_argument("--root", type=Path, default=_ROOT, help="repo root to walk")
    ap.add_argument("--quiet", action="store_true", help="write the artifact without printing")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    costs, unread = collect(root)
    if not args.quiet:
        print_report(costs, unread, root)

    out = Path(args.json)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_artifact(costs, unread, root), indent=2) + "\n", "utf-8")
    if not args.quiet:
        print(f"\nwrote {out}")
    missing = [c for c in _CITATIONS if not (root / c).exists()]
    if missing:
        print(f"WARNING: cited context missing from this checkout: {missing}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
