#!/usr/bin/env python3
"""Measure every STEP 4B duty from the artifacts its own row names; absent means MISSED.

The duty table in `docs/cro/CRO_CYCLE.md` is the registry: each `| Dn | **name** | ... |` row
names its artifacts in backticks (`reports/X.json`, `data/Y.json`). This script reads those
artifacts on the host it runs on and writes `desks/mt5/reports/CRO_DUTIES.json`:

  - an artifact that is absent or unreadable is UNMEASURED; one older than the duty's
    `max_age_h` (docs/cro/cro_duty_metrics.json, default 26h) is STALE;
  - each counter the duty must carry (cro_duty_metrics.json) is looked up by key anywhere in
    the duty's artifacts; a counter none of them carries is UNMEASURED;
  - a duty with any UNMEASURED or STALE artifact, or any UNMEASURED counter, counts as MISSED.
    Plain-comparison targets are scored MET / NOT_MET; the rest stay MEASURED for the CRO.

`--review PATH --started-at ISO` then applies the verdicts to the TIER1_BREADTH_REVIEW.json the
pass just wrote: a duty the pass scored MET or OPTIMAL whose artifacts are UNMEASURED, or whose
measured target comparison failed, is downgraded to MISSED, keeping its claim under
`status_claimed`. A duty from D15 on (`artifact_backed_from`) whose row names no artifact is
UNMEASURED: only the procedure duties D1..D14 are left to the pass's own record. A review written before
`--started-at` belongs to an earlier pass and is never rewritten.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.win_write import write_text_resilient  # noqa: E402

DESK = ROOT / "desks" / "mt5"
CYCLE = ROOT / "docs" / "cro" / "CRO_CYCLE.md"
METRICS = ROOT / "docs" / "cro" / "cro_duty_metrics.json"
OUT = DESK / "reports" / "CRO_DUTIES.json"

ROW = re.compile(r"^\| (D\d+) \| \*\*(.+?)\*\* \|(.*)$")
ARTIFACT = re.compile(r"`((?:desks/mt5/)?(?:reports|data)/[A-Za-z0-9_./-]+\.jsonl?)`")
#: statuses a pass may claim that an unmeasured artifact cannot support
_CLAIMS = {"MET", "OPTIMAL"}


def duty_rows(text: str) -> dict[str, dict[str, Any]]:
    """`{Dn: {"name", "artifacts"}}` for every duty row, artifacts in order of mention."""
    out: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        duty, name, rest = m.groups()
        metric_cell = rest.split(" | ")[0] if " | " in rest else rest
        arts = list(dict.fromkeys(ARTIFACT.findall(metric_cell)))
        out[duty] = {"name": name, "artifacts": arts}
    return out


def resolve(rel: str, root: Path = ROOT) -> Path:
    if rel.startswith("desks/mt5/"):
        return root / rel
    desk = root / "desks" / "mt5" / rel
    return desk if desk.exists() or not (root / rel).exists() else root / rel


def _parse_ts(s: Any) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    t = re.sub(r"(\.\d{6})\d+", r"\1", s.strip().replace("Z", "+00:00"))
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _load(path: Path) -> tuple[Any, str | None]:
    try:
        text = path.read_text("utf-8-sig")
    except OSError as e:
        return None, f"unreadable: {type(e).__name__}"
    try:
        if path.suffix == ".jsonl":
            rows = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
            return (rows[-1] if rows else None), None if rows else "empty"
        return json.loads(text), None
    except ValueError:
        return None, "not JSON"


def _git_time(path: Path, root: Path) -> datetime | None:
    """When `path` was last committed. Adoption rewrites files in place on the box, so a file's
    mtime there says when it was LANDED, not when it was measured; a commit time cannot move."""
    try:
        out = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%cI", "--",
                              str(path.relative_to(root))], capture_output=True, text=True,
                             timeout=10, check=False).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return _parse_ts(out)


def _stamp(doc: Any, path: Path, root: Path = ROOT) -> tuple[datetime | None, str]:
    """The artifact's own measurement time, else its last commit time, else None (UNSTAMPED).
    Never the file's mtime: that is reset whenever the box adopts a release."""
    if isinstance(doc, Mapping):
        for k in ("at", "generated_at", "generated_utc", "measured_at", "updated", "swept_at"):
            ts = _parse_ts(doc.get(k))
            if ts is not None:
                return ts, k
    ts = _git_time(path, root)
    return (ts, "git_commit") if ts is not None else (None, "none")


def find_key(doc: Any, key: str, depth: int = 6) -> tuple[bool, Any]:
    """First value under `key` anywhere in `doc` (breadth-first, bounded depth)."""
    level: list[Any] = [doc]
    for _ in range(depth):
        nxt: list[Any] = []
        for node in level:
            if isinstance(node, Mapping):
                if key in node:
                    return True, node[key]
                nxt.extend(node.values())
            elif isinstance(node, list):
                nxt.extend(node[:200])
        if not nxt:
            break
        level = nxt
    return False, None


def _summarise(v: Any) -> Any:
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return {"len": len(v)}
    if isinstance(v, Mapping):
        if all(isinstance(x, (int, float)) for x in v.values()) and len(v) <= 24:
            return dict(v)
        return {"keys": len(v)}
    return str(v)[:80]


def _target(op: str, v: Any, want: Any) -> bool | None:
    try:
        if op.startswith("len"):
            v, op = len(v), op[3:]
        return bool({"==": v == want, "<=": v <= want, ">=": v >= want,
                     "<": v < want, ">": v > want}[op])
    except (TypeError, KeyError):
        return None


def measure(rows: Mapping[str, Mapping[str, Any]], spec: Mapping[str, Any],
            now: datetime | None = None, root: Path = ROOT) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    default_age = float(spec.get("default_max_age_h", 26))
    backed_from = int(spec.get("artifact_backed_from", 15))
    per = spec.get("duties") or {}
    duties: dict[str, Any] = {}
    for duty, row in rows.items():
        cfg = per.get(duty) or {}
        max_age = float(cfg.get("max_age_h", default_age))
        # the row's own artifacts first, then any the metrics file names for it -- the place a
        # publisher's path goes while another branch owns the duty's row in CRO_CYCLE.md
        named = list(dict.fromkeys([*row["artifacts"], *(cfg.get("artifacts") or [])]))
        arts: dict[str, Any] = {}
        docs: list[Any] = []
        per_art = cfg.get("artifact_max_age_h") or {}
        for rel in named:
            art_age = float(per_art.get(rel, max_age))
            path = resolve(rel, root)
            if not path.exists():
                arts[rel] = {"status": "UNMEASURED", "why": "absent on this host"}
                continue
            doc, err = _load(path)
            if err:
                arts[rel] = {"status": "UNMEASURED", "why": err}
                continue
            stamp, basis = _stamp(doc, path, root)
            if stamp is None:
                arts[rel] = {"status": "UNSTAMPED",
                             "why": "no measurement time in the artifact and no commit of it; "
                                    "its mtime is reset by adoption and proves nothing"}
                continue
            age_h = (now - stamp).total_seconds() / 3600
            arts[rel] = {"status": "STALE" if age_h > art_age else "FRESH",
                         "age_h": round(age_h, 2), "max_age_h": art_age, "stamp_basis": basis}
            if age_h <= art_age:
                docs.append(doc)
        metrics: dict[str, Any] = {}
        for key in cfg.get("metrics") or []:
            for doc in docs:
                ok, v = find_key(doc, key)
                if ok:
                    metrics[key] = {"status": "MEASURED", "value": _summarise(v), "_raw": v}
                    break
            else:
                metrics[key] = {"status": "UNMEASURED", "why": "no artifact of this duty carries it"}
        targets = []
        for t in cfg.get("targets") or []:
            m = metrics.get(t["metric"]) or {}
            res = _target(t["op"], m.get("_raw"), t["value"]) if m.get("status") == "MEASURED" \
                else None
            targets.append({**t, "result": "UNMEASURED" if res is None
                            else ("MET" if res else "NOT_MET")})
        for m in metrics.values():
            m.pop("_raw", None)
        missing = [a for a, v in arts.items() if v["status"] != "FRESH"]
        unmeasured = [k for k, v in metrics.items() if v["status"] == "UNMEASURED"]
        if not named and int(duty[1:]) >= backed_from:
            # an artifact-backed duty whose row names only counters has nothing on this host that
            # can back a MET: that is UNMEASURED, never a free pass (L1.28a)
            status = "UNMEASURED"
            why = "the row names counters but no artifact path; nothing on this host backs them"
        elif not named:
            # a procedure duty (D1..D14) is judged from the pass's own record, which the CRO
            # scores; this check has nothing to say about it either way
            status, why = "NO_ARTIFACT_NAMED", "the duty row names no artifact to check"
        elif not docs or unmeasured:
            # rows name alternatives ("until X exists, Y"), so one fresh artifact is enough;
            # a counter no fresh artifact carries is not
            status = "UNMEASURED"
            why = "; ".join(filter(None, [
                f"no fresh artifact: {', '.join(missing)}" if not docs else "",
                f"counters unpublished: {', '.join(unmeasured)}" if unmeasured else ""]))
        elif any(t["result"] == "NOT_MET" for t in targets):
            status, why = "NOT_MET", "a target comparison failed"
        elif targets and all(t["result"] == "MET" for t in targets):
            status, why = "MET", "every target comparison held"
        else:
            status, why = "MEASURED", "values measured; the CRO judges the target"
        if docs and missing and status != "UNMEASURED":
            why += f"; also not fresh: {', '.join(missing)}"
        duties[duty] = {"name": row["name"], "status": status, "why": why,
                        "counts_as": "MISSED" if status in ("UNMEASURED", "NOT_MET") else None,
                        "artifacts": arts, "metrics": metrics, "targets": targets}
    counts: dict[str, int] = {}
    for d in duties.values():
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    return {"schema": "cro_duties/1", "at": now.isoformat(timespec="seconds"),
            "rule": "an artifact absent, unreadable or stale, or a counter no artifact carries, "
                    "is UNMEASURED and counts as MISSED; never resolve absence to MET",
            "counts": counts, "missed": sorted((k for k, v in duties.items()
                                                if v["counts_as"] == "MISSED"),
                                               key=lambda k: int(k[1:])),
            "duties": duties}


def apply_to_review(review: Path, measured: Mapping[str, Any],
                    started_at: str | None, root: Path = ROOT) -> dict[str, Any]:
    out: dict[str, Any] = {"applied": False, "changed": []}
    try:
        doc = json.loads(review.read_text("utf-8-sig"))
    except (OSError, ValueError) as e:
        out["why"] = f"review unreadable: {type(e).__name__}"
        return out
    latest = doc.get("latest") if isinstance(doc, dict) else None
    if not isinstance(latest, dict):
        out["why"] = "review has no latest block"
        return out
    start, wrote = _parse_ts(started_at), _parse_ts(latest.get("at"))
    if start is not None and (wrote is None or wrote < start):
        out["why"] = "review predates this pass; not rewritten"
        return out
    duties = latest.setdefault("duties", {})
    if not isinstance(duties, dict):
        out["why"] = "review duties is not a mapping"
        return out
    for duty in _changed(duties, measured.get("duties") or {}):
        out["changed"].append(duty)
    missed_q = score_pass_questions(latest, root)
    out["pass_questions_missed"] = missed_q
    out["judging_sweep_missed"] = score_judging_sweep(latest, root)
    latest["artifact_check"] = {"at": measured.get("at"), "missed": measured.get("missed"),
                                "source": "scripts/check_cro_duties.py"}
    write_text_resilient(review, json.dumps(doc, indent=1, ensure_ascii=False))
    out["applied"] = True
    return out


#: ARCH-30 pass questions every pass must answer (CRO_CYCLE.md STEP 4B, PASS QUESTIONS)
PASS_QUESTIONS = tuple(f"Q{i}" for i in range(1, 8))
#: the JUDGING BOTTLENECK SWEEP items every pass must record (CRO_CYCLE.md STEP 4B)
JUDGING_SWEEP = tuple("abcdefg")


LEDGER = DESK / "data" / "cro_cycle_ledger.jsonl"
_SHA = re.compile(r"^(?:sha:|commit:)?([0-9a-f]{7,40})$")


def _ledger_ids(root: Path) -> set[str]:
    """Row ids the cycle ledger can resolve: `<lane>-<date>` per row and each work item's id."""
    ids: set[str] = set()
    try:
        lines = (root / LEDGER.relative_to(ROOT)).read_text("utf-8-sig").splitlines()
    except OSError:
        return ids
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("lane") and row.get("date"):
            ids.add(f"{row['lane']}-{row['date']}")
        for item in row.get("work_items") or []:
            if isinstance(item, dict) and item.get("id"):
                ids.add(str(item["id"]))
    return ids


def _sha_resolves(sha: str, root: Path) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"],
                           capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def citation_resolves(ev: Any, root: Path = ROOT, ledger: set[str] | None = None) -> bool:
    """A citation is box evidence only in one of three resolvable forms:
    `<artifact path>@<ISO timestamp>` naming a file that exists on this host,
    `ledger:<row id>` naming a cro_cycle_ledger row (`<lane>-<date>`) or work item id,
    or a commit sha (`sha:<hex>` or bare 7-40 hex) that this checkout resolves."""
    if not isinstance(ev, str) or not ev.strip():
        return False
    ev = ev.strip()
    if ev.startswith("ledger:"):
        ids = ledger if ledger is not None else _ledger_ids(root)
        return ev[len("ledger:"):] in ids
    m = _SHA.match(ev)
    if m:
        return _sha_resolves(m.group(1), root)
    path, sep, stamp = ev.rpartition("@")
    when = _parse_ts(stamp)
    if not sep or not path or when is None or when > datetime.now(UTC) + timedelta(minutes=5):
        return False                    # no stamp, or one from the future, is not evidence
    rel = Path(path)
    if rel.is_absolute() or rel.drive or ".." in rel.parts:
        return False                    # evidence lives in the repo, never outside it
    top = root.resolve()
    for cand in (root / rel, resolve(path, root)):
        try:
            real = cand.resolve()
        except OSError:
            continue
        if real.is_relative_to(top) and real.is_file():
            return True
    return False


def _entry_miss(q: Any, text_key: str, root: Path = ROOT,
                ledger: set[str] | None = None) -> str | None:
    """Why a pass-question or sweep entry counts as MISSED, or None when it is cited."""
    if not isinstance(q, Mapping):
        return "absent"
    answer = q.get(text_key)
    if not isinstance(answer, str) or not answer.strip():
        return f"no_{text_key}"
    if "UNMEASURED" in answer.upper() or str(q.get("status") or "").upper() == "UNMEASURED":
        return "unmeasured"
    ev = q.get("evidence")
    items = [ev] if isinstance(ev, str) else list(ev) if isinstance(ev, list) else []
    if not any(isinstance(e, str) and e.strip() for e in items):
        return "no_evidence"
    if not any(citation_resolves(e, root, ledger) for e in items):
        return "evidence_unresolvable"
    return None


def _score_block(latest: dict[str, Any], block: str, keys: Iterable[str], text_key: str,
                 ok_status: str, root: Path = ROOT) -> list[str]:
    ledger = _ledger_ids(root)
    raw = latest.get(block)
    entries: dict[str, Any] = dict(raw) if isinstance(raw, Mapping) else {}
    missed: list[str] = []
    for key in keys:
        cur = entries.get(key)
        why = _entry_miss(cur, text_key, root, ledger)
        entry: dict[str, Any] = dict(cur) if isinstance(cur, Mapping) else {}
        if why is None:
            entry.setdefault("status", ok_status)
        else:
            missed.append(key)
            prior = str(entry.get("status") or "")
            if prior and prior != "MISSED":
                entry["status_claimed"] = prior
            entry["status"] = "MISSED"
            entry["reason"] = why
        entries[key] = entry
    latest[block] = entries
    latest[f"{block}_missed"] = missed
    return missed


def score_pass_questions(latest: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Rewrite `pass_questions` so an absent, unanswered, UNMEASURED or uncited answer reads
    MISSED (claim kept under `status_claimed`); set `pass_questions_missed`. Returns the misses."""
    return _score_block(latest, "pass_questions", PASS_QUESTIONS, "answer", "ANSWERED", root)


def score_judging_sweep(latest: dict[str, Any], root: Path = ROOT) -> list[str]:
    """The same for the judging sweep's items (a)-(g): `judging_sweep_missed`."""
    return _score_block(latest, "judging_sweep", JUDGING_SWEEP, "finding", "MEASURED", root)


def _changed(duties: dict[str, Any], measured: Mapping[str, Any]) -> Iterable[str]:
    for duty, m in sorted(measured.items(), key=lambda kv: int(kv[0][1:])):
        if m.get("status") not in ("UNMEASURED", "NOT_MET"):
            continue
        verdict = m["status"]
        cur = duties.get(duty)
        entry: dict[str, Any] = dict(cur) if isinstance(cur, Mapping) else {}
        prior = str(entry.get("status") or "")
        entry["artifact_check"] = m.get("why")
        entry["counts_as"] = "MISSED"
        if prior in _CLAIMS or not prior:
            if prior:
                entry["status_claimed"] = prior
            entry["status"] = "MISSED"
            entry["verdict"] = verdict
            entry["reason"] = ("artifact_unmeasured" if verdict == "UNMEASURED"
                               else "measured_target_not_met")
            duties[duty] = entry
            yield duty
        else:
            duties[duty] = entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--review", type=Path)
    ap.add_argument("--started-at")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows = duty_rows(CYCLE.read_text("utf-8"))
    spec = json.loads(METRICS.read_text("utf-8"))
    doc = measure(rows, spec)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    write_text_resilient(a.out, json.dumps(doc, indent=1, ensure_ascii=False))
    res: dict[str, Any] = {"status": "WRITTEN", "out": str(a.out), "counts": doc["counts"],
                           "missed": doc["missed"]}
    if a.review is not None:
        res["review"] = apply_to_review(a.review, doc, a.started_at)
    print(json.dumps(res) if a.json else
          f"cro duties: {doc['counts']}; MISSED {len(doc['missed'])}: {', '.join(doc['missed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
