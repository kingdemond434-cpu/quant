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
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "EXPERIMENT_LEDGER.json"


def _graph_stamp(path: Path) -> dict[str, Any]:
    """Cheap content fence for an append-only graph; size/mtime alone miss replacements."""
    st = path.stat()
    with path.open("rb") as fh:
        head = fh.read(65536)
        fh.seek(max(0, st.st_size - 65536))
        tail = fh.read(65536)
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns,
            "head_sha256": hashlib.sha256(head).hexdigest(),
            "tail_sha256": hashlib.sha256(tail).hexdigest()}


#: The graph fates charged as judged trials. `research/judge_prescreen` joins its kill charges
#: against exactly these (a test pins the two equal), so a cell is charged once, by one of them.
GRAPH_COUNTED_FATES = frozenset({"FAILED", "BURIED", "CERTIFIED", "JUDGED"})


def _graph_counts() -> tuple[int, dict[str, int]]:
    """Count latest fates with compact state, caching only an exact graph version.

    ``Graph.current()`` retains every nested gates/params blob of a 3.7 GB ledger in memory.
    The allocator's fifteen-minute fast pass spent 50+ minutes and ~20 GB rebuilding that
    dictionary before it could price a book. Only id, family and fate are needed here. A new
    append invalidates the small aggregate cache and triggers one bounded-memory rescan.
    """
    try:
        from libs.research.hypothesis_graph import LEDGER
        stamp = _graph_stamp(LEDGER)
    except OSError:
        return 0, {}
    cache_path = DESK / "data" / "experiment_graph_counts.json"
    try:
        cached = json.loads(cache_path.read_text("utf-8"))
        counts = cached.get("by_family")
        if cached.get("graph_stamp") == stamp and isinstance(counts, dict):
            return int(cached["judged_cells"]), {str(k): int(v) for k, v in counts.items()}
    except (OSError, ValueError, TypeError, KeyError):
        pass
    current: dict[str, tuple[str, str]] = {}
    with LEDGER.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                current[str(row.get("id"))] = (str(row.get("fate") or ""),
                                                str(row.get("family") or "?"))
    by_fam: dict[str, int] = {}
    for fate, f in current.values():
        if fate in GRAPH_COUNTED_FATES:
            by_fam[f] = by_fam.get(f, 0) + 1
    total = sum(by_fam.values())
    # If a concurrent judge appended while we scanned, this answer is a dated snapshot. Leave
    # the cache invalid so the next pass re-reads; never label a partial version exact.
    try:
        if _graph_stamp(LEDGER) == stamp:
            doc = {"graph_stamp": stamp, "judged_cells": total, "by_family": by_fam}
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, cache_path)
    except OSError:
        pass  # a missing cache costs time, never a smaller trial count
    return total, by_fam


def _intel_roots() -> tuple[Path, Path]:
    """Both intelligence roots the compiler reads and `scripts/disk_guard.INTEL_DIRS` rolls up.
    Derived from DESK at call time, so a caller (or test) that points DESK elsewhere moves both."""
    return DESK / "data" / "intelligence", DESK.parent.parent / "data" / "intelligence"


def _doc_key(doc: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"),
                                     default=str).encode("utf-8")).hexdigest()


def _discovery_docs(stats: dict[str, Any] | None = None) -> Any:
    """(seat, document, origin) for every proposer contract that carries a `tests_run`: the live
    `discoveries_*.json` files AND the `rollup_<day>.jsonl.gz` archives `disk_guard.rollup`
    compacts them into after RETAIN_DAYS (one document per line, the originals deleted).
    `origin` names where the charge was read (`<seat>/<file stem>` or `<seat>/rollup_<day>#<line>`).

    THE UNDER-COUNT THIS ENDS (audit 2026-10-14). Reading only the live files meant every rolled
    contract's `tests_run` silently left the lifetime count.

    EVERY OCCURRENCE IS A CHARGE; ONLY A TRUE RE-READ IS DROPPED (Audit MF1). Distinct charges
    can be byte-identical -- committee_ensembles writes `{"kind":"trial_charge","tests_run":k,...}`
    with no time or nonce, its uniqueness living only in the file NAME -- so content is never a
    dedup key on its own. Two re-reads are removed, each exactly:
      * the SAME FILE reached twice (the two roots overlapping, a symlinked seat): deduped by the
        resolved path, never by content;
      * a live file AND its rollup line (disk_guard wrote the line, then the unlink failed):
        disk_guard rolls a file into `rollup_<D>` of its own seat directory only when the
        file's stem day is D, so a rollup line is skipped only against a live file of the SAME
        resolved seat directory, the SAME day D and the same canonical-JSON sha256, and at most
        once per such live document. A live file of any other day is never matched, and the
        live file itself is always counted, so the result is never below the live-only count.
    A document is the unit disk_guard writes, so a live list file is read element by element
    exactly as its rollup lines will be (its count is the same before and after).

    STAMPED LINES (Audit ruling C, ledger-rollups 5a7ba77eb). disk_guard now writes each line as
    {"src": <file stem>, "i": <row>, "sha": <canonical sha>, "doc": <document>} and never
    re-appends a row already present. Only a stamped line is ever deduped on rollup content, on
    (resolved seat dir, src, row, sha); an unstamped legacy line is charged exactly as before,
    and the suspected legacy re-appends are REPORTED in `legacy_suspected_reappends`, never
    subtracted."""
    import gzip
    import zlib
    from collections import Counter

    st = stats if stats is not None else {}
    st.update({"live_documents": 0, "rollup_documents": 0, "same_path_skipped": 0,
               "rollup_lines_matched_to_live": 0, "matched_by_rollup": {}, "torn_archives": [],
               "stamped_documents": 0, "stamped_duplicates_skipped": 0,
               "legacy_suspected_reappends": {"documents": 0, "tests_run": 0, "by_seat": {},
                                              "subtracted": False}})
    seen_paths: set[str] = set()
    live_unmatched: Counter[tuple[str, str, str]] = Counter()

    def _first_visit(f: str, primary: bool) -> bool:
        # The desk root is read hit-for-hit exactly as before this change (never fewer charges
        # than the live-only count); only a SECOND-root path that resolves to one already read
        # is the same file twice.
        rp = os.path.realpath(f)
        if rp in seen_paths and not primary:
            st["same_path_skipped"] += 1
            return False
        seen_paths.add(rp)
        return True

    def _charge(doc: Any) -> bool:
        return isinstance(doc, dict) and isinstance(doc.get("tests_run"), (int, float))

    roots = list(dict.fromkeys(_intel_roots()))
    for i, base in enumerate(roots):
        for f in sorted(glob.glob(str(base / "*" / "discoveries_*.json"))):
            if not _first_visit(f, i == 0):
                continue
            p = Path(f)
            try:
                raw = json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            seat_dir = os.path.realpath(p.parent)
            day = p.stem.replace("discoveries_", "")[:8]   # disk_guard.rollup's own stamp
            for doc in (raw if isinstance(raw, list) else [raw]):
                if _charge(doc):
                    live_unmatched[(seat_dir, day, _doc_key(doc))] += 1
                    st["live_documents"] += 1
                    yield p.parent.name, doc, f"{p.parent.name}/{p.stem}"
    stamped_seen: set[tuple[str, str, int, str]] = set()
    for i, base in enumerate(roots):
        for f in sorted(glob.glob(str(base / "*" / "rollup_*.jsonl.gz"))):
            if not _first_visit(f, i == 0):
                continue
            p = Path(f)
            seat = p.parent.name
            seat_dir = os.path.realpath(p.parent)
            day = p.name[len("rollup_"):].split(".", 1)[0]
            tag = f"{seat}/rollup_{day}"
            lines: list[str] = []
            try:
                with gzip.open(f, "rt", encoding="utf-8") as fh:
                    for ln in fh:
                        lines.append(ln)
            except (OSError, EOFError, zlib.error):
                # a torn archive keeps every line read before the tear: never a smaller count
                # than what was readable
                st["torn_archives"].append(tag)
            _legacy_reappends(lines, seat, tag, st)
            for lineno, ln in enumerate(lines, 1):
                if '"tests_run"' not in ln:
                    continue
                try:
                    obj = json.loads(ln)
                except ValueError:
                    continue
                src = obj.get("src") if isinstance(obj, dict) else None
                if isinstance(src, str) and src and "doc" in obj:
                    # STAMPED LINE (disk_guard after 2026-11-25): {"src", "i", "sha", "doc"}.
                    # The ONLY dedupe on rollup content: the same (seat, src, row, sha) twice
                    # is one source row appended twice. Unstamped lines are never deduped.
                    doc = obj["doc"]
                    if not _charge(doc):
                        continue
                    row = obj.get("i")
                    sk = (seat_dir, src, int(row) if isinstance(row, int) else -1, _doc_key(doc))
                    if sk in stamped_seen:
                        st["stamped_duplicates_skipped"] += 1
                        continue
                    stamped_seen.add(sk)
                    st["stamped_documents"] += 1
                else:
                    doc = obj
                    if not _charge(doc):
                        continue
                k = (seat_dir, day, _doc_key(doc))
                if live_unmatched[k] > 0:
                    live_unmatched[k] -= 1
                    st["rollup_lines_matched_to_live"] += 1
                    st["matched_by_rollup"][tag] = st["matched_by_rollup"].get(tag, 0) + 1
                    continue
                st["rollup_documents"] += 1
                yield seat, doc, f"{tag}#{lineno}"


def _legacy_reappends(lines: list[str], seat: str, tag: str, st: dict[str, Any]) -> None:
    """REPORT ONLY, NEVER SUBTRACTED (Audit ruling C, ledger-rollups 5a7ba77eb). Before the
    src stamp, disk_guard's unlink-retry re-appended a whole day batch, so a legacy archive whose
    unstamped lines are one block B repeated r >= 2 times in order is a suspected re-append of
    (r - 1) copies of B's charges. The lines are still charged exactly as before -- more trials
    is the strict side -- and this only publishes how many of them are suspected."""
    legacy: list[str] = []
    for ln in lines:
        if ln.startswith('{"src"'):
            break                          # stamped appends follow the legacy body
        legacy.append(ln)
    n = len(legacy)
    period = n
    for q in range(1, n // 2 + 1):
        if n % q == 0 and legacy[:q] * (n // q) == legacy:
            period = q
            break
    reps = n // period if n else 0
    if reps < 2:
        return
    docs = 0
    trials = 0
    for ln in legacy[:period]:
        if '"tests_run"' not in ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("tests_run"), (int, float)):
            docs += 1
            trials += int(d["tests_run"])
    if not docs:
        return
    rep = st["legacy_suspected_reappends"]
    by = rep["by_seat"].setdefault(seat, {"documents": 0, "tests_run": 0, "archives": []})
    by["documents"] += docs * (reps - 1)
    by["tests_run"] += trials * (reps - 1)
    by["archives"].append(tag)
    rep["documents"] += docs * (reps - 1)
    rep["tests_run"] += trials * (reps - 1)


def _proposer_counts(stats: dict[str, Any] | None = None) -> tuple[int, dict[str, int]]:
    """`tests_run` on every discovery contract (live files and disk_guard rollups), attributed
    to the families it proposed. `stats`, when given, receives `_discovery_docs`' diagnostics."""
    total = 0
    by_fam: dict[str, int] = {}
    # No early return when there is no intelligence dir: the side ledgers below still count.
    # The learned miners re-run the SAME grid x symbols x thresholds every day, so their daily
    # discovery files repeat one charge; they are reconciled below against the trial ledger.
    learned_files: dict[str, tuple[int, set[str]]] = {}
    for seat, doc, _origin in _discovery_docs(stats):
        n = int(doc["tests_run"])
        fams = {str(r.get("family")) for r in (doc.get("discoveries") or [])
                if isinstance(r, dict) and r.get("family")}
        if seat.startswith("learned_"):
            prev_n, prev_f = learned_files.get(seat, (0, set()))
            learned_files[seat] = (max(prev_n, n), prev_f | fams)
            continue
        total += n
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
    # THE LEARNED MINERS: ONE CHARGE PER DISTINCT TRIAL, EVER (audit 2026-10-13). The miner
    # writes one ledger row per (panel, symbol, config, threshold) it tried, donated or not, and
    # re-runs the same grid daily; a raw row count (or a sum of its daily files' tests_run)
    # charged the same trial once a day and inflated the judge's N. Per seat the charge is the
    # number of DISTINCT trial ids in the ledger, or that seat's largest single discovery file if
    # it is larger (a ledger that began after the seat's first file never undercounts). A max,
    # never a sum, so nothing is counted twice.
    ledger_ids: dict[str, dict[str, str]] = {}
    try:
        for ln in (DESK / "data" / "learned_miners_trials.jsonl").read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            row = json.loads(ln)
            if not isinstance(row, dict):
                continue
            fam_full = str(row.get("family") or "?")
            seat = fam_full.split(":", 1)[0] if ":" in fam_full else str(row.get("source") or "?")
            tid = str(row.get("trial_id") or json.dumps(row, sort_keys=True))
            ledger_ids.setdefault(seat, {}).setdefault(tid, fam_full.rsplit(":", 1)[-1])
    except (OSError, ValueError, TypeError):
        pass
    # BASKETS JUDGED AS ONE CELL ARE TRIALS OF THEIR FAMILY (recovered box patch 13). The basket
    # judge calls the sealed `run_gauntlet` directly and writes no gate ledger, so its baskets
    # never reach the hypothesis graph; it records one row per DISTINCT basket identity instead,
    # and each row is charged here to the family it trades.
    try:
        basket_lines = (DESK / "data" / "srb_basket_trials.jsonl").read_text("utf-8").splitlines()
    except OSError:
        basket_lines = []
    for ln in basket_lines:
        # ONE BAD LINE SKIPS ITSELF, NEVER THE REST: a torn append must not un-charge every
        # basket trial recorded after it.
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        fam = str(row.get("family") or "?")
        total += 1
        by_fam[fam] = by_fam.get(fam, 0) + 1
    for seat in sorted(set(ledger_ids) | set(learned_files)):
        ids = ledger_ids.get(seat, {})
        file_n, file_fams = learned_files.get(seat, (0, set()))
        if len(ids) >= file_n:
            total += len(ids)
            for fam in ids.values():
                by_fam[fam] = by_fam.get(fam, 0) + 1
        else:
            total += file_n
            for fam in file_fams or {"?"}:
                by_fam[fam] = by_fam.get(fam, 0) + file_n // max(1, len(file_fams))
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


#: THE JUDGE CALIBRATION LOOP'S CANDIDATE BARS (desks/mt5/research/judge_calibration.py, LOOP
#: L2). Every threshold it evaluates against the forward record is a variant of the judge tried
#: on that family's evidence, so each row's `trials` joins the screened count here, per family --
#: the one budget, never a second. The judge's fixed campaign charge is untouched.
JUDGE_CALIBRATION_TRIALS = DESK / "data" / "judge_calibration_trials.jsonl"


def _judge_calibration_counts(path: Path | None = None) -> tuple[int, dict[str, int]]:
    """(trials, per family) from the calibration loop's ledger; absent -> (0, {})."""
    total = 0
    by_fam: dict[str, int] = {}
    try:
        lines = (path or JUDGE_CALIBRATION_TRIALS).read_text("utf-8").splitlines()
    except OSError:
        return 0, {}
    for ln in lines:
        try:
            row = json.loads(ln)
            k = int(row.get("trials") or 0) if isinstance(row, dict) else 0
        except (ValueError, TypeError, AttributeError):
            continue
        if k <= 0:
            continue
        fam = str(row.get("family") or "judge_calibration")
        total += k
        by_fam[fam] = by_fam.get(fam, 0) + k
    return total, by_fam


def _prescreen_counts() -> tuple[int, dict[str, int]]:
    """CELLS THE JUDGE'S PRE-BUILD SCREEN KILLED ARE TRIALS, ONE EACH (research/judge_prescreen,
    2026-10-28). A canon kill takes a cell away from the sealed judge before its build; the judge
    would have recorded exactly one fate for it, whatever the outcome, so each standing kill is
    charged here exactly once and joins the JUDGED count. A READMITTED cell stops counting here
    because the judge's own fate then counts it. In SHADOW nothing is killed and this is 0."""
    try:
        if str(DESK) not in sys.path:
            sys.path.insert(0, str(DESK))
        import importlib
        judge_prescreen = importlib.import_module("research.judge_prescreen")
    except Exception:
        # NO KILL CAN EXIST WITHOUT THE MODULE THAT WRITES THEM -- unless its ledger is on disk,
        # in which case a silent 0 would DEFLATE the count: refuse instead (the writer keeps the
        # last good ledger and the judge's DSR fails closed on a stale one).
        if (DESK / "data" / "hypotheses" / "prescreen_verdicts.jsonl").exists():
            raise
        return 0, {}
    n, fam = judge_prescreen.lifetime_kills()
    return int(n), {str(k): int(v) for k, v in fam.items()}


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
    k_total, k_fam = _prescreen_counts()
    for fam, k in k_fam.items():
        g_fam[fam] = g_fam.get(fam, 0) + k
    g_total += k_total
    p_stats: dict[str, Any] = {}
    p_total, p_fam = _proposer_counts(p_stats)
    m_total, m_fam = _mass_screen_counts()
    for fam, k in m_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += m_total
    c_total, c_fam = _judge_calibration_counts()
    for fam, k in c_fam.items():
        p_fam[fam] = p_fam.get(fam, 0) + k
    p_total += c_total

    s_total, s_fam = _claim_selection_counts()
    prereg = _prereg_counts()
    fams = sorted(set(g_fam) | set(p_fam) | set(s_fam))
    by_fam = {f: int(g_fam.get(f, 0) + p_fam.get(f, 0) + s_fam.get(f, 0)) for f in fams}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "lifetime_trials": int(g_total + p_total + s_total),
           "judged_cells": g_total, "screened_cells": p_total,
           "source_selection_trials": s_total, "preregistered_cards": prereg,
           "mass_screen_cells": m_total, "prescreen_killed_cells": k_total,
           "proposer_sources": {
               "live_documents": p_stats.get("live_documents", 0),
               "rollup_documents": p_stats.get("rollup_documents", 0),
               "same_path_skipped": p_stats.get("same_path_skipped", 0),
               "rollup_lines_matched_to_live": p_stats.get("rollup_lines_matched_to_live", 0),
               "matched_by_rollup": dict(sorted((p_stats.get("matched_by_rollup") or {})
                                                .items())[:50]),
               "torn_archives": (p_stats.get("torn_archives") or [])[:50],
               "stamped_documents": p_stats.get("stamped_documents", 0),
               "stamped_duplicates_skipped": p_stats.get("stamped_duplicates_skipped", 0),
               # REPORTED, NEVER SUBTRACTED from lifetime_trials (Audit ruling C)
               "legacy_rollup_suspected_reappends": p_stats.get(
                   "legacy_suspected_reappends",
                   {"documents": 0, "tests_run": 0, "by_seat": {}, "subtracted": False})},
           # inside screened_cells, named so the loop's own charge is readable on its own
           "judge_calibration_trials": c_total,
           "by_family": dict(sorted(by_fam.items(), key=lambda kv: -kv[1])),
           "rule": ("lifetime = judged (hypothesis graph, plus each standing pre-build "
                    "prescreen kill as the one fate the judge would have recorded) + "
                    "screened (every proposer's tests_run, plus every mass-screen cell in "
                    "MASS_SCREEN_TRIALS.jsonl) + "
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
