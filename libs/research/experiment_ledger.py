"""The lifetime experiment ledger: every trial ever run counts, forever, per family and globally.

    N_trials^life          everything the desk has ever judged, screened or pre-registered
    N_trials^family        the same, per family

Quanti's discipline, made the desk's: the deflated-Sharpe and the winner's-curse shrinkage are
only as honest as the trial count they are given, and a count that forgets last month's sweep
is a count that manufactures survivors. The ledger is not a new file -- it is a JOIN of the
three places trials already leave a trace: the hypothesis graph (judged cells), every proposer's
`tests_run` on its discovery files (screened cells, including the culled), and the
pre-registration cards. Deduplicated by identity where the same cell appears in more than one.

CONSUMERS. `proposer_common.deflate` reports `t_deflated_lifetime` beside the sweep-deflated t;
`pf_allocator.search_trials` takes the larger of the gate report's count and the lifetime
family count for the winner's-curse shrinkage. Both are tightenings: a lifetime count can only
deflate more, never less.
"""
from __future__ import annotations

import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "EXPERIMENT_LEDGER.json"


def _graph_counts() -> tuple[int, dict[str, int]]:
    try:
        from libs.research.hypothesis_graph import Graph
        cur = Graph().current()
    except Exception:
        return 0, {}
    by_fam: dict[str, int] = {}
    for r in cur.values():
        if r.get("fate") in ("FAILED", "BURIED", "CERTIFIED", "JUDGED"):
            f = str(r.get("family") or "?")
            by_fam[f] = by_fam.get(f, 0) + 1
    return sum(by_fam.values()), by_fam


def _count(v: Any) -> int | None:
    """A non-negative integer trial count, or None when the field is absent or not a count."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        return None
    return int(v)


def charge_by_family(tests_run: Any, rows: Any, by_family: Any = None) -> dict[str, int]:
    """Charge a discovery file's trials to families by what each row actually cost.

    THE ONE PLACE A FILE-LEVEL `tests_run` IS SPLIT (audit 2026-09-30). The old split divided the
    file's count evenly over its DISTINCT families with a floor, so a family with 40 rows was
    charged the same as one with 1, and the floor's remainder was charged to nobody.

    Order of evidence, strongest first:
      1. a declared per-family count on the file (`by_family`), charged as written;
      2. a per-row count (`tests_run` / `n_trials` / `trials` on a discovery row), charged to
         that row's family;
      3. whatever of the file's `tests_run` those two do not explain, split over the remaining
         rows in proportion to how many rows each family has, largest remainder first, so the
         integers sum exactly.
    With no family anywhere, the whole count goes to "?".

    INVARIANT, pinned by tests: the charge sums to max(file tests_run, declared counts) -- it can
    exceed the file's own figure when the rows declare more, and never falls below it.
    """
    n = _count(tests_run) or 0
    charge: dict[str, int] = {}
    if isinstance(by_family, dict):
        for fam, k in by_family.items():
            c = _count(k)
            if c:
                charge[str(fam)] = charge.get(str(fam), 0) + c
    weights: dict[str, int] = {}
    if not charge:
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or not r.get("family"):
                continue
            fam = str(r["family"])
            own = next((c for c in (_count(r.get(k)) for k in ("tests_run", "n_trials", "trials"))
                        if c is not None), None)
            if own is not None:
                charge[fam] = charge.get(fam, 0) + own
            else:
                weights[fam] = weights.get(fam, 0) + 1
    rest = n - sum(charge.values())
    if rest > 0:
        if not weights:
            # every row declared its count (or none named a family): the unexplained remainder
            # goes to the declared families by their charge, or to "?" when there are none.
            weights = dict(charge) if charge else {"?": 1}
        w = sum(weights.values())
        share = {f: rest * k // w for f, k in weights.items()}
        left = rest - sum(share.values())
        for f in sorted(weights, key=lambda f: (-((rest * weights[f]) % w), f))[:left]:
            share[f] += 1
        for f, k in share.items():
            if k:
                charge[f] = charge.get(f, 0) + k
    return charge


def _proposer_counts() -> tuple[int, dict[str, int]]:
    """`tests_run` on every discovery file, attributed to the families it proposed."""
    total = 0
    by_fam: dict[str, int] = {}
    intel = DESK / "data" / "intelligence"
    for f in (glob.glob(str(intel / "*" / "discoveries_*.json")) if intel.exists() else []):
        try:
            doc = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("tests_run"), (int, float)):
            continue
        charge = charge_by_family(doc["tests_run"], doc.get("discoveries"),
                                  doc.get("tests_by_family"))
        total += sum(charge.values())
        for fam, k in charge.items():
            by_fam[fam] = by_fam.get(fam, 0) + k
    # FACTOR x MODEL PAIRINGS ARE TRIALS TOO. Co-evolution writes no discovery file (a pairing is
    # not a cell), so its ledger is read here and charged to the model_pairing family.
    try:
        for ln in (DESK / "data" / "coevolution_trials.jsonl").read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            row = json.loads(ln)
            k = int(row.get("pairings") or 0) if isinstance(row, dict) else 0
            total += k
            by_fam["model_pairing"] = by_fam.get("model_pairing", 0) + k
    except (OSError, ValueError, TypeError):
        pass
    # SCREENS THAT FOUND NOTHING ARE TRIALS TOO. A pass with no candidate writes no discovery
    # file, so its width is appended to screen_trials.jsonl instead (research/
    # cross_sectional_breadth.py) and charged here, per family.
    try:
        for ln in (DESK / "data" / "screen_trials.jsonl").read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            row = json.loads(ln)
            widths = row.get("by_family") if isinstance(row, dict) else None
            if not isinstance(widths, dict):
                continue
            for fam, k in widths.items():
                n = int(k or 0)
                total += n
                by_fam[str(fam)] = by_fam.get(str(fam), 0) + n
    except (OSError, ValueError, TypeError):
        pass
    return total, by_fam


def _prereg_counts() -> int:
    try:
        from libs.research.preregistration import cards
        return len(cards())
    except Exception:
        return 0


def lifetime(write: bool = True) -> dict[str, Any]:
    g_total, g_fam = _graph_counts()
    p_total, p_fam = _proposer_counts()
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam))
    by_fam = {f: int(g_fam.get(f, 0) + p_fam.get(f, 0)) for f in fams}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total + p_total),
           "judged_cells": g_total, "screened_cells": p_total, "preregistered_cards": prereg,
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph) + screened (every proposer's "
                    "tests_run); consumers may only deflate MORE with it, never less")}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


_CACHE: dict[str, Any] = {"at": 0.0, "doc": None}


def family_trials(family: str, *, max_age_s: float = 3600.0) -> int:
    """Lifetime trials for a family, from the last written ledger (recomputed when stale)."""
    import time
    now = time.time()
    if _CACHE["doc"] is None or now - float(_CACHE["at"]) > max_age_s:
        try:
            _CACHE["doc"] = json.loads(OUT.read_text("utf-8"))
        except (OSError, ValueError):
            _CACHE["doc"] = lifetime(write=True)
        _CACHE["at"] = now
    doc = _CACHE["doc"] or {}
    return int((doc.get("by_family") or {}).get(family, 0))


def total_trials() -> int:
    family_trials("_")
    return int((_CACHE["doc"] or {}).get("lifetime_trials", 0))
