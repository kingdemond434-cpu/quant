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


def _graph_judged() -> tuple[int, dict[str, int], set[str]]:
    """(judged cells, per family, their graph node ids) from the hypothesis graph."""
    try:
        from libs.research.hypothesis_graph import Graph
        cur = Graph().current()
    except Exception:
        return 0, {}, set()
    by_fam: dict[str, int] = {}
    ids: set[str] = set()
    for nid, r in cur.items():
        if r.get("fate") in ("FAILED", "BURIED", "CERTIFIED", "JUDGED"):
            f = str(r.get("family") or "?")
            by_fam[f] = by_fam.get(f, 0) + 1
            ids.add(str(nid))
    return sum(by_fam.values()), by_fam, ids


def _graph_counts() -> tuple[int, dict[str, int]]:
    total, by_fam, _ids = _graph_judged()
    return total, by_fam


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


#: THE MASS SCREEN'S TRIAL LEDGER (desks/mt5/research/mass_screen.py). Every rule cell it screens
#: -- the millions that never reach a judge included -- is counted in a row's `cells_screened`,
#: per grammar family. A screen that looked at a cell has TESTED it, however cheaply, so the count
#: joins the lifetime total here and the per-family count the winner's-curse shrinkage reads.
MASS_SCREEN_TRIALS = DESK / "data" / "MASS_SCREEN_TRIALS.jsonl"


def _mass_screen_counts(path: Path | None = None) -> tuple[int, dict[str, int]]:
    """(cells screened, per family) from the mass screen's ledger. Dry runs are not trials of the
    desk's search and are skipped. Absent ledger: (0, {}) -- nothing was screened."""
    total = 0
    by_fam: dict[str, int] = {}
    try:
        lines = (path or MASS_SCREEN_TRIALS).read_text("utf-8").splitlines()
    except OSError:
        return 0, {}
    for ln in lines:
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
            if not isinstance(row, dict) or row.get("dry_run"):
                continue
            k = int(row.get("cells_screened") or 0)
        except (ValueError, TypeError):
            continue
        fam = str(row.get("family") or "mass_screen")
        total += k
        by_fam[fam] = by_fam.get(fam, 0) + k
    return total, by_fam


#: THE UNKNOWN-UNKNOWN MINER'S TRIAL LEDGER (desks/mt5/research/unknown_unknown.py), same row
#: shape: every expression-rule cell it screens is a trial of its grammar family `uu_<grammar>`,
#: charged on the FULL screened width, the GP population and the novel-but-rejected included.
UNKNOWN_UNKNOWN_TRIALS = DESK / "data" / "UNKNOWN_UNKNOWN_TRIALS.jsonl"


def _unknown_unknown_counts(path: Path | None = None) -> tuple[int, dict[str, int]]:
    """(cells screened, per family) from the unknown-unknown ledger; dry runs skipped."""
    return _mass_screen_counts(path or UNKNOWN_UNKNOWN_TRIALS)


#: THE REGIME-SPLIT MINER'S UNION LEDGER (desks/mt5/research/regime_split_miner.py, PR #124, with
#: the producer-swarm follow-up patch): each (symbol, base, regime) cell charged ONCE over the
#: lifetime union, same row shape. Absent until that miner writes it: 0 cells, never an error.
REGIME_SPLIT_TRIALS = DESK / "data" / "REGIME_SPLIT_TRIALS.jsonl"


#: THE PRODUCER SWARM'S MINT LEDGER (desks/mt5/research/producer_swarm.py). Every cell the swarm
#: GENERATES is a trial of its family from the moment it is minted -- not only once a judge gets to
#: it, because a cell that sits unjudged in a 10^5-row docket was still drawn from the search and
#: the family-wise error budget must know it. Each row names its cells by the hypothesis graph's
#: node id (`cells`), so a cell is charged ONCE: a cell the graph already holds as judged is
#: counted there and skipped here, and a cell minted in two rows is counted once. A legacy row
#: without `cells` cannot be deduplicated and is charged by its `cells_screened` (deflate more,
#: never less).
PRODUCER_SWARM_TRIALS = DESK / "data" / "PRODUCER_SWARM_TRIALS.jsonl"


def _swarm_counts(judged: set[str] | frozenset[str] = frozenset(),
                  path: Path | None = None) -> tuple[int, dict[str, int], int]:
    """(cells charged, per family, cells skipped as already judged) from the swarm's ledger.
    Dry runs are skipped. Absent ledger: (0, {}, 0)."""
    try:
        lines = (path or PRODUCER_SWARM_TRIALS).read_text("utf-8").splitlines()
    except OSError:
        return 0, {}, 0
    seen: set[str] = set()
    by_fam: dict[str, int] = {}
    total = skipped = 0
    for ln in lines:
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("dry_run"):
            continue
        fam = str(row.get("family") or "producer_swarm")
        cells = row.get("cells")
        if isinstance(cells, list):
            k = 0
            for c in cells:
                cid = str(c)
                if cid in seen:
                    continue
                seen.add(cid)
                if cid in judged:
                    skipped += 1
                    continue
                k += 1
        else:
            try:
                k = int(row.get("cells_screened") or 0)
            except (TypeError, ValueError):
                continue
        total += k
        by_fam[fam] = by_fam.get(fam, 0) + k
    return total, by_fam, skipped


#: THE EMPTY-CLUSTER SEEDER'S TRIAL LEDGER (desks/mt5/research/empty_cluster_breadth.py): every
#: cell it MEASURES -- clearing the gauntlet's floor or held back under it -- is a trial of its
#: family, keyed by graph node id. Same row shape and dedup as the swarm's ledger.
EMPTY_CLUSTER_TRIALS = DESK / "data" / "EMPTY_CLUSTER_TRIALS.jsonl"


def _prereg_counts() -> int:
    try:
        from libs.research.preregistration import cards
        return len(cards())
    except Exception:
        return 0


def lifetime(write: bool = True) -> dict[str, Any]:
    g_total, g_fam, g_ids = _graph_judged()
    p_total, p_fam = _proposer_counts()
    s_total, s_fam, s_judged = _swarm_counts(g_ids)
    e_total, e_fam, e_judged = _swarm_counts(g_ids, EMPTY_CLUSTER_TRIALS)
    for fam, k in e_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += e_total
    del g_ids
    for fam, k in s_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += s_total
    m_total, m_fam = _mass_screen_counts()
    for fam, k in m_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += m_total
    u_total, u_fam = _unknown_unknown_counts()
    for fam, k in u_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += u_total
    r_total, r_fam = _mass_screen_counts(REGIME_SPLIT_TRIALS)
    for fam, k in r_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += r_total
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam))
    by_fam = {f: int(g_fam.get(f, 0) + p_fam.get(f, 0)) for f in fams}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total + p_total),
           "judged_cells": g_total, "screened_cells": p_total, "preregistered_cards": prereg,
           "mass_screen_cells": m_total, "unknown_unknown_cells": u_total,
           "regime_split_union_cells": r_total,
           "producer_swarm_cells": s_total,
           "producer_swarm_cells_already_judged": s_judged,
           "empty_cluster_cells": e_total,
           "empty_cluster_cells_already_judged": e_judged,
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph) + screened (every proposer's "
                    "tests_run, plus every mass-screen cell in MASS_SCREEN_TRIALS.jsonl and every "
                    "unknown-unknown cell in UNKNOWN_UNKNOWN_TRIALS.jsonl, and every "
                    "regime-split cell of the lifetime union in REGIME_SPLIT_TRIALS.jsonl, and "
                    "every "
                    "producer-swarm cell at GENERATION from PRODUCER_SWARM_TRIALS.jsonl, "
                    "deduplicated by graph node id against the judged cells, and every "
                    "empty-cluster seeder cell MEASURED, from EMPTY_CLUSTER_TRIALS.jsonl, the "
                    "same way); "
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
