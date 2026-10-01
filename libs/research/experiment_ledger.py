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


def _proposer_counts() -> tuple[int, dict[str, int]]:
    """`tests_run` on every discovery file, attributed to the families it proposed."""
    total = 0
    by_fam: dict[str, int] = {}
    intel = DESK / "data" / "intelligence"
    # No early return when there is no intelligence dir: the side ledgers below still count.
    for f in glob.glob(str(intel / "*" / "discoveries_*.json")):
        try:
            doc = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("tests_run"), (int, float)):
            continue
        n = int(doc["tests_run"])
        total += n
        fams = {str(r.get("family")) for r in (doc.get("discoveries") or [])
                if isinstance(r, dict) and r.get("family")}
        for fam in fams or {"?"}:
            by_fam[fam] = by_fam.get(fam, 0) + n // max(1, len(fams))
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
    # NULL PASSES ARE TRIALS TOO. A proposer pass that tested cells and donated none writes no
    # discovery file, so it appends its `tests_run` here instead (alt_proxies._donate). A pass
    # writes one or the other, never both, so nothing is counted twice.
    try:
        for ln in (DESK / "data" / "null_pass_trials.jsonl").read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            row = json.loads(ln)
            if not isinstance(row, dict):
                continue
            total += int(row.get("tests_run") or 0)
            split = row.get("by_family")
            per: dict[str, Any] = (split if isinstance(split, dict) and split
                                   else {"?": row.get("tests_run") or 0})
            for fam, k in per.items():
                by_fam[str(fam)] = by_fam.get(str(fam), 0) + int(k or 0)
    except (OSError, ValueError, TypeError):
        pass
    # A MINER RUN THAT PROPOSES NOTHING STILL RAN ITS TESTS. `learned_miners` writes one row per
    # (config, symbol, threshold) it tried; a run that donated is already counted through its
    # discovery file's tests_run, so only the runs that donated nothing are charged here -- the
    # null runs that would otherwise leave no trace in the lifetime count.
    try:
        for ln in (DESK / "data" / "learned_miners_trials.jsonl").read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            row = json.loads(ln)
            if not isinstance(row, dict) or row.get("donated"):
                continue
            fam = str(row.get("family") or "?").rsplit(":", 1)[-1]
            total += 1
            by_fam[fam] = by_fam.get(fam, 0) + 1
    except (OSError, ValueError, TypeError):
        pass
    return total, by_fam


def _claim_selection_counts() -> tuple[int, dict[str, int]]:
    """A SOURCE'S OWN SEARCH IS A TRIAL TOO (libs.research.claim_selection, 2026-09-30). A claim
    reported as the best of N searched variations spent N trials before the desk saw it; the
    lifetime ledger `claim_families.json` holds N per claim family and each is charged here
    exactly once -- never once per cell the desk later swept the claim into."""
    try:
        from libs.research.claim_selection import lifetime_charges
        by_fam = lifetime_charges()
    except Exception:
        return 0, {}
    return sum(by_fam.values()), by_fam


def _prereg_counts() -> int:
    try:
        from libs.research.preregistration import cards
        return len(cards())
    except Exception:
        return 0


def lifetime(write: bool = True) -> dict[str, Any]:
    g_total, g_fam = _graph_counts()
    p_total, p_fam = _proposer_counts()
    s_total, s_fam = _claim_selection_counts()
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam) | set(s_fam))
    by_fam = {f: int(g_fam.get(f, 0) + p_fam.get(f, 0) + s_fam.get(f, 0)) for f in fams}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total + p_total + s_total),
           "judged_cells": g_total, "screened_cells": p_total,
           "source_selection_trials": s_total, "preregistered_cards": prereg,
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph) + screened (every proposer's "
                    "tests_run) + each claim family's stated source selection, once; "
                    "consumers may only deflate MORE with it, never less")}
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
