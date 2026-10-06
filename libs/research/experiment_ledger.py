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
from collections.abc import Iterator
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


#: THE SCREENED LEDGER (2026-10-06): one JSON line per distinct cell a SCREEN looked at, with the
#: stage that looked -- `buildability` (desks/mt5/research/merge_hypotheses.py: a minted cell the
#: judge cannot build, held out of the docket, never out of the census) and `stage1` (the two-stage
#: judge's training-window screen, research/stage1_judge.py). Each distinct cell is ONE trial of
#: its family, charged once into the union however many times it is re-screened; a cell that
#: later receives a FULL verdict is counted by the hypothesis graph instead, never twice.
SCREENED_TRIALS = DESK / "data" / "SCREENED_TRIALS.jsonl"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"


def _jsonl_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Every JSON-object line of `path`, streamed; a malformed or non-object line is skipped, an
    unreadable file yields nothing (absence is no rows, never an exception)."""
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for ln in fh:
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def _cell_hash(cell: str) -> int:
    import hashlib
    return int.from_bytes(hashlib.blake2b(cell.encode("utf-8", "replace"),
                                          digest_size=8).digest(), "little")


def _fully_judged_mask(hashes: Any, gate_ledger: Path) -> Any:
    """Boolean mask over sorted unique `hashes`: True where the gate ledger holds a RULED verdict
    for that cell. Streams the ledger in bounded chunks; unreadable -> all False (charge stands)."""
    import numpy as np
    mask = np.zeros(len(hashes), dtype=bool)
    try:
        import sys as _sys
        if str(DESK) not in _sys.path:
            _sys.path.insert(0, str(DESK))
        from research.judging_burndown import classify  # type: ignore[import-not-found]
    except Exception:
        def classify(row: dict[str, Any]) -> str:
            return "ruled" if row.get("terminal_gate") else "unknown"
    buf: list[int] = []

    def flush() -> None:
        if buf:
            mask[:] |= np.isin(hashes, np.fromiter(buf, dtype=np.uint64, count=len(buf)))
            buf.clear()
    for row in _jsonl_rows(gate_ledger):
        cell = str(row.get("cell") or "")
        if cell and classify(row) == "ruled":
            buf.append(_cell_hash(cell))
            if len(buf) >= 1 << 20:
                flush()
    flush()
    return mask


def _screened_counts(path: Path | None = None, gate_ledger: Path | None = None
                     ) -> dict[str, Any]:
    """Distinct screened cells (by family and stage) still owed a charge: each cell once, minus
    those the gate ledger has since RULED (the graph counts those). Memory is 8 bytes per distinct
    cell plus small per-row indices, never the cell strings."""
    from array import array

    import numpy as np
    hs = array("Q")
    fam_ix = array("I")
    stage_ix = array("B")
    fams: dict[str, int] = {}
    stages: dict[str, int] = {}
    for row in _jsonl_rows(path or SCREENED_TRIALS):
        cell = str(row.get("cell") or "")
        if not cell:
            continue
        hs.append(_cell_hash(cell))
        fam_ix.append(fams.setdefault(str(row.get("family") or "screened"), len(fams)))
        stage_ix.append(stages.setdefault(str(row.get("stage") or "buildability"), len(stages)))
    if not hs:
        return {"total": 0, "by_family": {}, "by_stage": {}, "fully_judged_excluded": 0}
    h = np.frombuffer(hs, dtype=np.uint64)
    uniq, first = np.unique(h, return_index=True)
    f = np.frombuffer(fam_ix, dtype=np.uint32)[first]
    st = np.frombuffer(stage_ix, dtype=np.uint8)[first]
    judged = np.zeros(len(uniq), dtype=bool)
    if "stage1" in stages:
        judged = _fully_judged_mask(uniq, gate_ledger or GATE_LEDGER)
    keep = ~judged
    fam_names = {i: n for n, i in fams.items()}
    stage_names = {i: n for n, i in stages.items()}
    by_fam = {fam_names[int(i)]: int(c) for i, c in
              enumerate(np.bincount(f[keep], minlength=len(fams))) if c}
    by_stage = {stage_names[int(i)]: int(c) for i, c in
                enumerate(np.bincount(st[keep], minlength=len(stages))) if c}
    return {"total": int(keep.sum()), "by_family": by_fam, "by_stage": by_stage,
            "fully_judged_excluded": int(judged.sum())}


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
    m_total, m_fam = _mass_screen_counts()
    for fam, k in m_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += m_total
    scr = _screened_counts()
    r_total, r_fam = int(scr["total"]), dict(scr["by_family"])
    for fam, k in r_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += r_total
    s_total, s_fam = _claim_selection_counts()
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam) | set(s_fam))
    by_fam = {f: int(g_fam.get(f, 0) + p_fam.get(f, 0) + s_fam.get(f, 0)) for f in fams}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total + p_total + s_total),
           "judged_cells": g_total, "screened_cells": p_total,
           "source_selection_trials": s_total, "preregistered_cards": prereg,
           "mass_screen_cells": m_total,
           "screened_cells_distinct": r_total,
           "screened_refused_cells": int(scr["by_stage"].get("buildability", 0)),
           # the stage-1 union the two-stage order is drawn from (stage1_record.LEDGER_UNION_KEY)
           "stage1_cells": int(scr["by_stage"].get("stage1", 0)),
           "screened_fully_judged_excluded": int(scr["fully_judged_excluded"]),
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph) + screened (every proposer's "
                    "tests_run, plus every mass-screen cell in MASS_SCREEN_TRIALS.jsonl and "
                    "every distinct cell a screen looked at in SCREENED_TRIALS.jsonl -- "
                    "unbuildable cells and stage-1 cells, once each, minus any since fully "
                    "judged) + "
                    "each claim family's stated source selection, once; "
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
