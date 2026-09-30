"""How fast the factory turns an idea into a verdict, and where it stalls.

Renaissance's stated investment was in making data immediately usable so an idea could be tested
quickly. The measurable form of that is latency and throughput at each stage of this desk's own
funnel, from the artifacts it already writes:

    intake         rows the miners produced                     data/intelligence/*/discoveries_*
    compiled       executable candidates the compiler admitted  data/hypotheses/miner_candidates
    deepened       tasks the deepening worker decided           data/hypotheses/deepening_worked
    judged         cells the gauntlet built and judged          reports/universal_gates_external
    certified      cells in the canon                           data/UNIVERSAL_SURVIVORS.canon
    forward        sleeves with a forward clock                 backups/moat/shadow_ledgers
    proposed       cells the proposers donated                  data/intelligence/{factor_residual,
                                                                plumbing,transition_alpha,...}
    recommended    recommendation ledger, open vs implemented   docs/research/recommendation_ledger

Per stage: count, count in the last 7 days, and where timestamps allow, the median age of items
that have NOT progressed -- which is the queue's latency, and the number that says which stage is
the bottleneck. A factory that certifies once a week from a thousand intake rows has a conversion
of 0.1%, and the stage where the other 999 stopped is the one to fix.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
OUT = BASE / "reports" / "RESEARCH_PRODUCTIVITY.json"


def _mtime(p: Path) -> datetime:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)


def _recent(paths: list[Path], days: int = 7) -> int:
    cut = datetime.now(tz=UTC) - timedelta(days=days)
    return sum(1 for p in paths if _mtime(p) >= cut)


def _rows(path: Path) -> list:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(d, list):
        return d
    # `hypotheses` added 2026-09-05, and its absence was reporting the desk's headline conversion
    # number as ZERO. `miner_candidate_compiler` writes its admitted candidates under
    # `hypotheses`, not `candidates` -- the only top-level `candidates` in that file is a per-source
    # COUNT inside `per_source`, not a list -- so this helper fell through every key and returned
    # []. Measured on the 2026-09-04 artifact: the compiler had written `executable_candidates:
    # 372` with 372 rows in `hypotheses`, and RESEARCH_PRODUCTIVITY published `compiled: 0` and
    # `intake_to_compiled: 0.0` beside it. A funnel whose second stage always reads zero cannot
    # locate a bottleneck, and it names the wrong one: `deepening` is chosen whenever its backlog
    # exceeds 100, which it does trivially when nothing is ever counted as compiled.
    #
    # Ordered AFTER `candidates` so a file that genuinely uses that key is unaffected; the two
    # never co-occur as lists in the same artifact.
    for k in ("discoveries", "candidates", "hypotheses", "verdicts", "tasks", "rows"):
        if isinstance(d.get(k), list):
            return d[k]
    return []


SHADOW_DIR = BASE / "reports" / "shadow"
ENROLMENT = BASE / "reports" / "FORWARD_ENROLMENT.json"
LANE_FILES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
              "external_shadow_state.json")


def _ts(raw: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _banned(family: object) -> bool:
    try:
        from family_policy import family_banned
    except ImportError:
        try:
            from research.family_policy import family_banned  # type: ignore[no-redef]
        except Exception:
            return False
    try:
        return bool(family_banned(family))
    except Exception:
        return False


def forward_stage(canon_rows: list, moat_ledgers: list[Path] | None = None,
                  shadow_dir: Path | None = None, enrolment: Path | None = None,
                  now: datetime | None = None) -> dict:
    """Certificates against the forward clocks that are ACTUALLY TICKING.

    THE DEFECT THIS REPLACES (measured on the box 2026-09-30). This stage counted files in
    `backups/moat/shadow_ledgers/` -- a BACKUP of the ledgers, written by the moat job -- and
    divided that by the canon. So "certified -> forward 9.1%, 0 ledgers updated in 7 days" was a
    statement about a backup folder, and the desk's headline read the forward book as dead while
    saying nothing about whether a single clock had ticked. The engine's own evidence is the lane
    state files `shadow_forward` writes (`last_attempt_at` on every row it reaches, `n` observed
    days) and the census `forward_enrolment` publishes; this reads those.

    THE DENOMINATOR IS WHAT MAY HOLD A CLOCK. A certificate in a family the principal banned
    (`family_policy`, e.g. `discovered`) can never be enrolled by standing order, so it is named
    and set aside rather than counted as a stall. Everything else that holds no ticking clock is
    counted against the conversion with the reason the census gives.

    An absent census or absent lane files is UNMEASURED (L1.28a), never zero.
    """
    t = now or datetime.now(tz=UTC)
    fams = [str(((r or {}).get("shadow_spec") or {}).get("family") or "")
            for r in canon_rows if isinstance(r, dict)]
    banned = sum(1 for f in fams if _banned(f))
    eligible = len(fams) - banned
    root = Path(shadow_dir or SHADOW_DIR)
    rows: list[dict] = []
    lanes_read = 0
    for name in LANE_FILES:
        try:
            doc = json.loads((root / name).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict):
            lanes_read += 1
            rows += [v for v in doc.values() if isinstance(v, dict)]
    ticks = [x for x in (_ts(r.get("last_attempt_at")) for r in rows) if x is not None]
    out: dict = {
        "source": "reports/shadow/*_state.json + reports/FORWARD_ENROLMENT.json",
        "certificates": len(fams), "banned_family_certificates": banned,
        "forward_eligible_certificates": eligible,
        "moat_backup_ledgers": len(moat_ledgers or []),
        "moat_backup_ledgers_updated_7d": _recent(list(moat_ledgers or [])),
    }
    if lanes_read:
        out.update({
            "clock_rows": len(rows),
            "clocks_ticked_24h": sum(1 for x in ticks if t - x <= timedelta(hours=24)),
            "clocks_ticked_7d": sum(1 for x in ticks if t - x <= timedelta(days=7)),
            "last_tick": max(ticks).isoformat() if ticks else "UNMEASURED",
            "engine_silent_hours": (round((t - max(ticks)).total_seconds() / 3600.0, 1)
                                    if ticks else "UNMEASURED"),
        })
    else:
        out["clock_rows"] = "UNMEASURED"
    try:
        census = json.loads(Path(enrolment or ENROLMENT).read_text("utf-8"))
    except (OSError, ValueError):
        census = None
    if isinstance(census, dict) and census.get("status") == "MEASURED":
        for k in ("n_certificates", "n_enrolled", "n_accruing", "n_blocked", "n_missing",
                  "n_overdue", "n_dropped_at_admission", "blocked_by_status"):
            out[k] = census.get(k)
        out["census_at"] = census.get("at")
    else:
        out["n_accruing"] = "UNMEASURED"
        out["census_why"] = ("reports/FORWARD_ENROLMENT.json absent or not MEASURED"
                             if census is None
                             else str(census.get("why") or census.get("status")))
    return out


def stages() -> dict:
    intel = BASE / "data" / "intelligence"
    intake_files = [Path(p) for p in glob.glob(str(intel / "*" / "discoveries_*.json"))]
    intake_rows = sum(len(_rows(p)) for p in intake_files[-200:])
    proposers = {}
    for src in ("factor_residual", "plumbing", "transition_alpha", "weak_signal_ensemble"):
        fs = sorted(Path(p) for p in glob.glob(str(intel / src / "discoveries_*.json")))
        proposers[src] = {"files": len(fs), "rows_latest": len(_rows(fs[-1])) if fs else 0,
                          "last": (_mtime(fs[-1]).isoformat() if fs else None)}

    cand = _rows(BASE / "data" / "hypotheses" / "miner_candidates.json")
    deep_q = _rows(BASE / "data" / "hypotheses" / "miner_deepening_queue.json")
    worked = 0
    try:
        worked = sum(1 for ln in (BASE / "data" / "hypotheses" / "deepening_worked.jsonl")
                     .read_text("utf-8").splitlines() if ln.strip())
    except OSError:
        pass
    judged = _rows(BASE / "reports" / "universal_gates_external.json")
    canon: dict = {}
    try:
        canon = json.loads((BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json").read_text("utf-8"))
        certified = len(canon.get("survivors") or {})
        cert_dates = sorted(str(v.get("gated_at") or "")[:10]
                            for v in (canon.get("survivors") or {}).values()
                            if isinstance(v, dict) and v.get("gated_at"))
    except (OSError, ValueError):
        certified, cert_dates = 0, []
    ledgers = [Path(p) for p in glob.glob(str(ROOT / "backups" / "moat" / "shadow_ledgers"
                                             / "ledger_*.json"))]
    canon_rows = list((canon.get("survivors") or {}).values()) if isinstance(canon, dict) else []
    try:
        rec = json.loads((ROOT / "docs" / "research" / "recommendation_ledger.json")
                         .read_text("utf-8"))
        rec_rows = rec if isinstance(rec, list) else (rec.get("recommendations")
                                                       or rec.get("items") or [])
        rec_open = [r for r in rec_rows if isinstance(r, dict) and r.get("status") == "open"]
        ages = []
        for r in rec_open:
            try:
                ages.append((datetime.now(tz=UTC)
                             - datetime.fromisoformat(str(r["raised"]))).days)
            except (KeyError, ValueError, TypeError):
                pass
        rec_summary = {"total": len(rec_rows), "open": len(rec_open),
                       "open_median_age_days": (statistics.median(ages) if ages else None)}
    except (OSError, ValueError):
        rec_summary = {}

    return {
        "intake": {"files": len(intake_files), "files_7d": _recent(intake_files),
                   "rows_recent_files": intake_rows},
        "proposers": proposers,
        "compiled": {"candidates": len(cand)},
        "deepening": {"queued": len(deep_q), "decided_total": worked,
                      "backlog": max(0, len(deep_q) - worked)},
        "judged": {"cells": len(judged),
                   "unmeasured": sum(1 for v in judged if isinstance(v, dict) and v.get("unmeasured"))},
        "certified": {"cells": certified,
                      "last_certified": (cert_dates[-1] if cert_dates else None),
                      "certified_last_30d": sum(
                          1 for d in cert_dates
                          if d and d >= (datetime.now(tz=UTC) - timedelta(days=30)).strftime("%Y-%m-%d"))},
        "forward": forward_stage(canon_rows, moat_ledgers=ledgers),
        "recommendations": rec_summary,
    }


def run() -> dict:
    s = stages()
    conv = {}
    if s["intake"]["rows_recent_files"]:
        conv["intake_to_compiled"] = round(s["compiled"]["candidates"]
                                           / max(1, s["intake"]["rows_recent_files"]), 4)
    if s["judged"]["cells"]:
        conv["judged_to_certified"] = round(s["certified"]["cells"] / s["judged"]["cells"], 4)
    fwd = s["forward"]
    if isinstance(fwd.get("n_accruing"), int) and fwd.get("forward_eligible_certificates"):
        # ACCRUING, NOT ENROLLED: an enrolled clock that is blocked gathers no evidence and can
        # never mature, so only a ticking clock counts as the certificate having gone forward.
        conv["certified_to_forward"] = round(fwd["n_accruing"]
                                             / fwd["forward_eligible_certificates"], 4)
        conv["certified_to_clock"] = round((fwd.get("n_enrolled") or 0)
                                           / fwd["forward_eligible_certificates"], 4)
    elif s["certified"]["cells"]:
        conv["certified_to_forward"] = "UNMEASURED"
    bottleneck = "deepening" if s["deepening"]["backlog"] > 100 else (
        "judged" if s["judged"]["cells"] and s["judged"]["unmeasured"] > 0.5 * s["judged"]["cells"]
        else "none obvious")
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "stages": s, "conversion": conv,
           "bottleneck": bottleneck}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    s = d["stages"]
    print(f"RESEARCH PRODUCTIVITY  bottleneck={d['bottleneck']}")
    print(f"  intake files={s['intake']['files']} (7d {s['intake']['files_7d']})  "
          f"compiled={s['compiled']['candidates']}  deepening backlog={s['deepening']['backlog']}")
    print(f"  judged={s['judged']['cells']} (unmeasured {s['judged']['unmeasured']})  "
          f"certified={s['certified']['cells']} (30d {s['certified']['certified_last_30d']})  "
          f"forward accruing={s['forward'].get('n_accruing')} "
          f"ticked_24h={s['forward'].get('clocks_ticked_24h', 'UNMEASURED')}")
    for k, v in s["proposers"].items():
        print(f"  proposer {k:22s} files={v['files']} latest_rows={v['rows_latest']}")
    print(f"  conversion: {d['conversion']}")
    print(f"  recommendations: {s['recommendations']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
