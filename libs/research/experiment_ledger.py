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


def _claim_family_floors() -> dict[str, int]:
    """{strategy family: the largest claim selection swept into it} (claim_selection.family_floors).
    The family term of the DSR charge is max(family's own trials, that claim N): a strategy family
    that carried a searched claim's cells cannot be charged less than the claim's own search."""
    try:
        from libs.research.claim_selection import family_floors
        return family_floors()
    except Exception:
        return {}


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
    s_total, s_fam = _claim_selection_counts()
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam) | set(s_fam))
    by_fam = {f: int(g_fam.get(f, 0) + p_fam.get(f, 0) + s_fam.get(f, 0)) for f in fams}
    # THE CLAIM CHARGE REACHES THE FAMILY TERM (follow-up to #169, 2026-10-01). The judge charges
    # DSR max(campaign, family, union) and reads `family` from `by_family`; a claim family's N sat
    # under its own `claim:` key, so the strategy family that swept the claim was charged its own
    # slice only. Each strategy family is raised to the largest claim N swept into it -- a max,
    # so nothing is counted twice and no family figure ever falls. The union is unchanged.
    floors = _claim_family_floors()
    for f, n in floors.items():
        by_fam[f] = max(int(by_fam.get(f, 0)), int(n))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total + p_total + s_total),
           "judged_cells": g_total, "screened_cells": p_total,
           "source_selection_trials": s_total, "preregistered_cards": prereg,
           "claim_trials": dict(sorted(s_fam.items(), key=lambda kv: -kv[1])),
           "family_claim_floor": dict(sorted(floors.items(), key=lambda kv: -kv[1])),
           "mass_screen_cells": m_total,
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph) + screened (every proposer's "
                    "tests_run, plus every mass-screen cell in MASS_SCREEN_TRIALS.jsonl) + "
                    "each claim family's stated source selection, once; a strategy family's "
                    "count is at least the largest claim selection swept into it; "
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


_RO: dict[str, Any] = {"key": None, "doc": {}}


def _read_only() -> dict[str, Any]:
    """The last written ledger, re-read when the file changes, and NEVER recomputed or written:
    the judge reads this through `claim_campaign` and must not write another organ's artifact.
    Unreadable is {} -- the max() then falls back to its other terms, never below them."""
    try:
        st = OUT.stat()
        key = (str(OUT), st.st_mtime_ns, st.st_size)
    except OSError:
        return {}
    if _RO["key"] != key:
        try:
            doc = json.loads(OUT.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        _RO.update({"key": key, "doc": doc if isinstance(doc, dict) else {}})
    cached: dict[str, Any] = _RO["doc"]
    return cached


def family_charge(campaign: int, family: str, claim_family: str | None = None, *,
                  doc: dict[str, Any] | None = None) -> tuple[int, str]:
    """THE FAMILY CHARGE = max(campaign, family, claim) -- the provider the deflated-Sharpe trial
    count reads. `family` is the strategy family's lifetime trials (already floored at every claim
    N swept into it), `claim` the cell's own claim family's N. Never below the campaign charge."""
    if doc is None:
        doc = _read_only()
    fam_n = int((doc.get("by_family") or {}).get(family, 0) or 0)
    fam_n = max(fam_n, int((doc.get("family_claim_floor") or {}).get(family, 0) or 0))
    claim_n = int((doc.get("claim_trials") or {}).get(claim_family or "", 0) or 0)
    n = max(int(campaign), fam_n, claim_n)
    return n, (f"max(campaign {int(campaign)}, family {family or '?'} {fam_n}, "
               f"claim {claim_family or 'none'} {claim_n}) = {n}")


def claim_campaign(campaign: int, cell: dict[str, Any]) -> int:
    """`campaign` raised to the cell's claim charge and its family's claim floor: the ONE value
    the sealed judge's `charged_lifetime_trials` needs in its campaign slot for
    max(campaign, family, claim) to reach DSR. A cell that names no searched claim gets
    `campaign` back unchanged; this can only raise the count, never lower it."""
    n = int(campaign)
    try:
        from libs.research.claim_selection import claim_charge
        row = dict(cell)
        if not row.get("symbol") and row.get("sym"):
            row["symbol"] = row["sym"]
        if not row.get("genome_id") and row.get("symbol") and row.get("family"):
            try:
                from libs.research.alpha_genome import genome_id
                row["genome_id"] = genome_id(str(row["symbol"]), str(row["family"]),
                                             dict(row.get("params") or {}))
            except Exception:
                pass
        n = max(n, claim_charge(row))
        floor = (_read_only().get("family_claim_floor") or {}).get(str(cell.get("family") or ""), 0)
        n = max(n, int(floor or 0))
    except Exception:
        return int(campaign)
    return n
