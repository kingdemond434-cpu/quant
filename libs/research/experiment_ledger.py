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
import hashlib
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


def _graph_judged() -> dict[str, str]:
    """Judged node id -> family.

    A graph node id IS the spec identity (`hypothesis_graph.node_id` over symbol, family and
    params), so a judged cell joins a screened one by spec, never by a donation's own row id."""
    try:
        from libs.research.hypothesis_graph import Graph
        g = Graph()
        cur = g.current()
    except Exception:
        return {}
    return {i: str(r.get("family") or "?") for i, r in cur.items()
            if r.get("fate") in ("FAILED", "BURIED", "CERTIFIED", "JUDGED")}


def judged_screened_overlap(screened: dict[str, Any], mass_fam: dict[str, int],
                            judged: dict[str, str] | None = None) -> dict[str, int]:
    """Per family, the judged cells that were ALREADY charged as screened (audit, 2026-10-06).

    A proposer's `tests_run` counts every cell it screened, the ones it donated included; the
    compiler turns a donation into a docket cell, the gauntlet judges it, and the old join charged
    it a second time as a graph node. The same for a mass-screen cell forwarded to the judge.

    THE JOIN IS ON SPEC IDENTITY. `screened["ids"]` holds the node id of every donated row that
    names symbol, family and params, from a file whose `tests_run` was charged; a judged node is
    already charged exactly when its id is one of them. NOT by seat: the compiler expands one
    donated row into cells along chart/session axes the proposer never screened, and those are
    new trials. Each identity is subtracted once however many seats donated it, and never more
    per family than the proposers charged -- the double count over-deflated, so the correction
    must never under-charge. Mass-screen
    families exist only through the mass screen, so their judged cells are capped at its count."""
    judged = _graph_judged() if judged is None else judged
    ids = set(screened.get("ids") or ())
    charged = dict(screened.get("by_family") or {})
    out: dict[str, int] = {}
    for i, fam in judged.items():
        if i in ids:
            out[fam] = out.get(fam, 0) + 1
    out = {f: min(k, int(charged.get(f, k))) for f, k in out.items()}
    for fam, m in mass_fam.items():
        j = sum(1 for f in judged.values() if f == fam)
        k = min(j - out.get(fam, 0), m)
        if k > 0:
            out[fam] = out.get(fam, 0) + k
    return {f: k for f, k in out.items() if k > 0}


def _note_screened(screened: dict[str, Any], doc: dict[str, Any], n: int,
                   fams: set[str]) -> None:
    from libs.research.hypothesis_graph import node_id_for_spec, spec_identity
    ids = screened.setdefault("ids", set())
    by_fam = screened.setdefault("by_family", {})
    for r in doc.get("discoveries") or []:
        if not isinstance(r, dict):
            continue
        sym, fam, params = spec_identity(r)
        if sym and fam and params:
            ids.add(node_id_for_spec(r))
    for fam in fams or {"?"}:
        by_fam[fam] = by_fam.get(fam, 0) + n // max(1, len(fams))


def _proposer_counts(screened: dict[str, Any] | None = None) -> tuple[int, dict[str, int]]:
    """`tests_run` on every discovery file, attributed to the families it proposed.

    `screened`, when given, is filled with the spec ids and per-family charge of every
    `tests_run` file: `judged_screened_overlap` needs to know WHICH screened cells the judge saw."""
    total = 0
    by_fam: dict[str, int] = {}
    llm_files: list[tuple[str, Any]] = []
    intel = DESK / "data" / "intelligence"
    # No early return when there is no intelligence dir: the side ledgers below still count.
    # A union-charged seat's files are skipped only when its union file EXISTS: until the
    # writer (committee_ensembles, #160) has run, the files' own tests_run is the only charge.
    union_on = (DESK / COMMITTEE_UNION).is_file()
    for f in glob.glob(str(intel / "*" / "discoveries_*.json")):
        if union_on and Path(f).parent.name in UNION_CHARGED_SEATS:
            continue                       # charged once from its own lifetime union, below
        try:
            doc = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("tests_run"), (int, float)):
            if Path(f).parent.name in LLM_IDEA_SEATS:
                llm_files.append((Path(f).parent.name, doc))
            continue
        n = int(doc["tests_run"])
        total += n
        fams = {str(r.get("family")) for r in (doc.get("discoveries") or [])
                if isinstance(r, dict) and r.get("family")}
        for fam in fams or {"?"}:
            by_fam[fam] = by_fam.get(fam, 0) + n // max(1, len(fams))
        if screened is not None:
            _note_screened(screened, doc, n, fams)
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
    # EVERY LLM IDEA IS A TRIAL (audit, 2026-10-06). An LLM seat's donation carries no
    # `tests_run`: the seat looked at the world and kept these ideas out of everything it
    # considered, so each idea is charged once at donation -- identity-deduplicated across files,
    # so a re-donated idea is not charged twice. (The analyst panel's own side ledger is #166's.)
    seen: set[str] = set()
    for seat, doc in llm_files:
        rows = doc.get("discoveries") if isinstance(doc, dict) else doc
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            # (url, title, body): three ideas citing one URL are three ideas (audit 2026-10-06);
            # only the stamp fields a re-donation rewrites are left out of the body.
            body = {k: v for k, v in r.items() if k not in _DONATION_STAMPS}
            ident = "|".join((seat, str(r.get("url") or ""), str(r.get("title") or ""),
                              hashlib.sha256(json.dumps(body, sort_keys=True, default=str)
                                             .encode()).hexdigest()[:20]))
            if ident in seen:
                continue
            seen.add(ident)
            fam = str(r.get("family") or "llm_idea")
            total += 1
            by_fam[fam] = by_fam.get(fam, 0) + 1
    # EVERY COMMITTEE FALSIFIER LOOK IS A TRIAL. The committees keep the lifetime union of
    # (cell, seat) looks at return data; each distinct line is charged exactly once here, and the
    # committees' discovery files are skipped above so nothing is counted twice.
    try:
        looks = {ln.strip() for ln in (DESK / COMMITTEE_UNION).read_text("utf-8").splitlines()
                 if ln.strip()}
    except OSError:
        looks = set()
    total += len(looks)
    if looks:
        by_fam["committee_falsifier"] = by_fam.get("committee_falsifier", 0) + len(looks)
    # THE METHOD TRIAL'S EVALUATIONS (factor_model_coevolution.challenger): both arms' pairings.
    try:
        for ln in (DESK / "data" / "coevolution_h2h.jsonl").read_text("utf-8").splitlines():
            row = json.loads(ln) if ln.strip() else None
            k = int(row.get("trials") or 0) if isinstance(row, dict) else 0
            total += k
            by_fam["model_pairing"] = by_fam.get("model_pairing", 0) + k
    except (OSError, ValueError, TypeError):
        pass
    return total, by_fam


#: Fields a re-donation of the same idea rewrites; left out of the idea's identity.
_DONATION_STAMPS = frozenset({"ingested_time", "available_time", "donated_at", "at", "ts",
                              "generated_utc", "pass_id", "run_id"})
#: LLM seats whose donation rows are ideas, each charged once (scout_roster names the seats).
LLM_IDEA_SEATS = frozenset({"kimi", "deepseek", "scheduled_chatgpt", "committees", "openrouter"})
#: Seats charged from a lifetime union file instead of their discovery files' tests_run.
UNION_CHARGED_SEATS = frozenset({"committee_ensembles"})
COMMITTEE_UNION = Path("data") / "committees" / "trial_union.txt"     # under DESK


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


def _prereg_counts() -> int:
    try:
        from libs.research.preregistration import cards
        return len(cards())
    except Exception:
        return 0


def lifetime(write: bool = True) -> dict[str, Any]:
    g_total, g_fam = _graph_counts()
    screened: dict[str, Any] = {}
    p_total, p_fam = _proposer_counts(screened)
    m_total, m_fam = _mass_screen_counts()
    overlap = judged_screened_overlap(screened, m_fam)
    overlap = {f: min(k, g_fam.get(f, 0)) for f, k in overlap.items()}
    o_total = sum(overlap.values())
    for fam, k in m_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += m_total
    s_total, s_fam = _claim_selection_counts()
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam) | set(s_fam))
    by_fam = {f: int(g_fam.get(f, 0) - overlap.get(f, 0) + p_fam.get(f, 0) + s_fam.get(f, 0))
              for f in fams}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total - o_total + p_total + s_total),
           "judged_cells": g_total, "screened_cells": p_total,
           "judged_already_screened": o_total,
           "source_selection_trials": s_total, "preregistered_cards": prereg,
           "mass_screen_cells": m_total,
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph) + screened (every proposer's "
                    "tests_run, plus every mass-screen cell in MASS_SCREEN_TRIALS.jsonl) + "
                    "each claim family's stated source selection, once; a judged cell its "
                    "proposer or "
                    "the mass screen already charged is not charged again; "
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
