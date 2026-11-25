"""TASK FAILURE DIGEST -- one page that says which box tasks are not doing their job, what each
one was supposed to produce, and whether several of them share one cause.

`ops/process_health.py` already judges every scheduled task (`desks/mt5/reports/
process_health.json`: one row per task with `verdict`, `state`, `last_run`, `last_result_code`,
`last_result`, `artifact`, `artifact_age_min`). It says WHAT is red. It does not say what each red
task feeds, which red tasks are disabled on purpose, or whether seven FAILING rows are really one
fault. This reader joins that file with the box's task manifest (`desks/mt5/ops/box_tasks.manifest`
-- `runs`, `organ`, `installer` per task) and with the text of the scripts those name, and writes
`desks/mt5/reports/TASK_FAILURE_DIGEST.json`.

WHAT IS LISTED. Every row whose verdict is FAILING, STALE, DISABLED or NOT_SCHEDULED, with:

    age          snapshot_age_min (now minus process_health `at`, both UTC),
                 artifact_age_min (as process_health measured it, at its snapshot), and
                 last_run_lag_min: how far this task's last start trails the NEWEST start in the
                 same snapshot. `last_run` is the box's LOCAL clock with no zone on it, so it is
                 only ever compared to other `last_run` values -- never to UTC. A row without a
                 parseable last_run reads UNMEASURED, never 0.
    last rc      the raw `last_result_code`; `error_text` is only a type-like head of
                 process_health's `last_result` (an exception class name, else "rc=N", <= 60
                 characters, never a path or message: Auditor SF1). The host name is withheld.
    produces     process_health's contracted artifact, the manifest row, and every
                 `desks/mt5/{reports,data}/...` path named in the script or installer text
                 (REFERENCED, so it can include inputs -- the label says so)

EXPECTED-DISABLED. A DISABLED task is only a fault when nobody meant it. `EXPECTED_DISABLED`
names the ones that are disabled by design, each with its reason; any other DISABLED row is
flagged `unexpected_disabled`.

SHARED CAUSE. Rows are grouped on (a) identical error text with an identical rc, (b) an identical
start minute on the box clock, and (c) an identical produced artifact. Any group of two or more is
reported. A shared generic message ("the script itself returned 1") is weak evidence and is
labelled so -- it says the scripts died, not why.

UNMEASURED. If process_health.json is missing, unparseable or has no `processes` list, the digest
is written with `status: UNMEASURED` and the reason, and lists nothing -- an absent health file is
not a healthy box.

Report only: it restarts, enables and edits nothing.

    python desks/mt5/research/task_failure_digest.py

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `task_failure_digest` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import task_failure_digest as M; M.main()"
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
HEALTH = DESK / "reports" / "process_health.json"
MANIFEST = DESK / "ops" / "box_tasks.manifest"
OUT = DESK / "reports" / "TASK_FAILURE_DIGEST.json"

SCHEMA = "task-failure-digest/1"
UNMEASURED = "UNMEASURED"
LISTED = ("FAILING", "STALE", "DISABLED", "NOT_SCHEDULED")

#: Disabled on purpose. Anything DISABLED and not here is flagged.
EXPECTED_DISABLED: dict[str, str] = {
    "MT5-AdoptRelease": "disabled by design: inbound code is left to a manual adopt/seal step "
    "(principal directive; never re-enabled from a sweep)",
    "MT5-SealIfClean": "retired legacy registration; box_tasks.manifest says MT5-AdoptRelease "
    "owns sealing",
    "MT5-Gateway": "superseded registration; box_tasks.manifest retires it in favour of "
    "MT5-GatewayResident and leaves the disabled task on the box",
}

#: Messages that say only that the script exited non-zero. Sharing one is weak evidence.
GENERIC_ERRORS = ("generic failure",)
#: SF1 (Auditor): process_health's `last_result` is NEVER copied. `error_text` is a type-like head:
#: the first exception-class-shaped token in it, else "rc=N", capped, with no path in it.
ERROR_HEAD_MAX = 60
_EXC_TOKEN = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Exit|Interrupt|Warning|Timeout|Fault))\b")
#: Path-shaped tokens: a drive letter, a rooted or UNC path, or a home-relative one.
_PATH_TOKEN = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:[\w.$-]+/)+|~[\\/])\S*")
#: The box's host name is withheld: it is an account-number-shaped run (Auditor MF1).
HOST_WITHHELD = "withheld (host names are not published)"

_TASK_LINE = re.compile(r"^TASK\s+(.*)$")
_KV = re.compile(r'(\w+)="([^"]*)"')
_ARTIFACT = re.compile(
    r"(desks[/\\]mt5[/\\](?:reports|data)[/\\][\w.\-/\\]+\.(?:json|jsonl|md|parquet|csv|log))"
)
#: `OUT = DESK / "reports" / "X.json"` -- a path built by joins off the desk or repo root.
_JOIN = re.compile(
    r"^\s*([A-Z][A-Z0-9_]*)\s*(?::[^=]+)?=\s*(_?DESK|_?ROOT|ROOT_DIR|REPO)"
    r"((?:\s*/\s*[\"'][^\"']+[\"'])+)",
    re.M,
)
_JOIN_PART = re.compile(r"[\"']([^\"']+)[\"']")
_OUTPUT_HINT = re.compile(r"OUT|REPORT|ARTIFACT|STATE|LEDGER|DIGEST|SURFACE|RESULT")
_EXT = (".json", ".jsonl", ".md", ".parquet", ".csv", ".log")
_BOX_TIME_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %I:%M:%S %p",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def load_health(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """(doc, None) or (None, reason). Never raises."""
    if not path.exists():
        return None, f"{path.name} absent"
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unparseable: {type(exc).__name__}"
    if not isinstance(doc, dict) or not isinstance(doc.get("processes"), list):
        return None, f"{path.name} has no processes list"
    return doc, None


def manifest_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    """Task name -> its manifest rows (a task may run several scripts)."""
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return {}
    for line in path.read_text("utf-8", errors="replace").splitlines():
        m = _TASK_LINE.match(line.strip())
        if m:
            row = dict(_KV.findall(m.group(1)))
            if row.get("name"):
                out[row["name"]].append(row)
    return dict(out)


def installer_index(root: Path) -> dict[str, list[str]]:
    """Task name -> install_*.ps1 / register_*.ps1 files that name it (fallback when the
    manifest has no row)."""
    out: dict[str, list[str]] = defaultdict(list)
    for pattern in (
        "desks/mt5/**/install_*.ps1",
        "desks/mt5/**/register_*.ps1",
        "ops/install_*.ps1",
    ):
        for p in sorted(root.glob(pattern)):
            try:
                text = p.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for name in set(re.findall(r"MT5-[A-Z][A-Za-z0-9]*", text)):
                out[name].append(p.relative_to(root).as_posix())
    return dict(out)


def _source_paths(row: dict[str, str]) -> list[str]:
    paths = []
    for key in ("runs", "organ", "installer"):
        v = (row.get(key) or "").strip()
        if v and v.upper() not in ("NONE", "UNKNOWN") and "/" in v and " " not in v:
            paths.append(v)
    return paths


def scan_artifacts(root: Path, files: list[str]) -> tuple[list[str], list[str]]:
    """(declared_outputs, referenced) from the text of the run script / installer.

    declared_outputs: module-level constants whose NAME says output (OUT, REPORT, ARTIFACT,
    STATE, ...) built as `DESK / "reports" / "X.json"`. referenced: every other artifact path
    the text names -- may be inputs."""
    outputs: set[str] = set()
    refs: set[str] = set()
    for rel in files:
        p = root / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text("utf-8", errors="replace")
        except OSError:
            continue
        for m in _ARTIFACT.findall(text):
            refs.add(m.replace("\\", "/"))
        for var, base, chain in _JOIN.findall(text):
            parts = _JOIN_PART.findall(chain)
            if not parts or not parts[-1].endswith(_EXT):
                continue
            prefix = "desks/mt5/" if "DESK" in base else ""
            path = prefix + "/".join(parts)
            (outputs if _OUTPUT_HINT.search(var) else refs).add(path)
    return sorted(outputs), sorted(refs - outputs)


def parse_box_time(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    for fmt in _BOX_TIME_FORMATS:
        try:
            # zoneless on purpose: box-local, compared only to other box-local stamps
            return datetime.strptime(s, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    return None


def _measured(v: Any) -> Any:
    return UNMEASURED if v is None else v


def _rc_int(rc: Any) -> int | None:
    if isinstance(rc, bool):
        return None
    if isinstance(rc, int):
        return rc
    if isinstance(rc, str) and re.fullmatch(r"-?\d+", rc.strip()):
        return int(rc.strip())
    return None


def error_head(raw: Any, rc: Any) -> str:
    """The publishable head of a task's failure: the first exception class name in `raw`, else
    `rc=N`, else "". Capped at ERROR_HEAD_MAX characters; never carries a path or free text."""
    m = _EXC_TOKEN.search(str(raw or ""))
    if m:
        return m.group(1)[:ERROR_HEAD_MAX]
    n = _rc_int(rc)
    return f"rc={n}"[:ERROR_HEAD_MAX] if n is not None else ""


def scrub_paths(text: Any, cap: int = 160) -> Any:
    """process_health's own `why`, publishable. A `why` naming an exception class is reduced to
    that class name (the exception's text and any traceback never follow it out); otherwise
    every path-shaped token is replaced and it is capped. Non-strings pass through."""
    if not isinstance(text, str):
        return text
    m = _EXC_TOKEN.search(text)
    if m:
        return m.group(1)[:ERROR_HEAD_MAX]
    return _PATH_TOKEN.sub("<path>", text)[:cap]


def _is_generic(text: str) -> bool:
    low = text.lower()
    return any(g in low for g in GENERIC_ERRORS)


def shared_causes(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    by_err: dict[tuple[Any, str], list[str]] = defaultdict(list)
    by_start: dict[str, list[str]] = defaultdict(list)
    by_art: dict[str, list[str]] = defaultdict(list)
    generic = {e["name"]: bool(e.get("_generic")) for e in entries}
    for e in entries:
        if e["verdict"] in ("FAILING", "STALE") and e["error_text"]:
            by_err[(e["last_rc"], e["error_text"])].append(e["name"])
        if isinstance(e["_start"], datetime):
            by_start[e["_start"].strftime("%Y-%m-%d %H:%M")].append(e["name"])
        arts = e["produces"]["artifacts"]
        for a in arts if isinstance(arts, list) else []:
            by_art[a].append(e["name"])
    for (rc, text), names in sorted(by_err.items(), key=lambda kv: -len(kv[1])):
        if len(names) >= 2:
            groups.append(
                {
                    "kind": "same_error_text",
                    "key": text if text == f"rc={rc}" else f"rc={rc}: {text}",
                    "tasks": sorted(names),
                    "strength": "WEAK (generic exit; says the scripts died, not why)"
                    if any(generic.get(n) for n in names)
                    else "STRONG (identical specific error)",
                }
            )
    for minute, names in sorted(by_start.items()):
        if len(names) >= 2:
            groups.append(
                {
                    "kind": "same_start_minute_box_clock",
                    "key": minute,
                    "tasks": sorted(names),
                    "strength": "MODERATE (co-scheduled)",
                }
            )
    for art, names in sorted(by_art.items()):
        if len(set(names)) >= 2:
            groups.append(
                {
                    "kind": "same_artifact",
                    "key": art,
                    "tasks": sorted(set(names)),
                    "strength": "MODERATE (shared output or input)",
                }
            )
    return groups


def build(
    health_path: Path = HEALTH,
    manifest_path: Path = MANIFEST,
    root: Path = ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _now()
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_utc": now.isoformat(),
        # A repo-relative path, or only the file's NAME: never an absolute path in a report.
        "source": health_path.relative_to(root).as_posix()
        if health_path.is_relative_to(root)
        else health_path.name,
    }
    health, why = load_health(health_path)
    if health is None:
        doc.update(
            {
                "status": UNMEASURED,
                "why": why,
                "tasks": UNMEASURED,
                "counts": UNMEASURED,
                "shared_causes": UNMEASURED,
            }
        )
        return doc

    snap_age: Any = UNMEASURED
    try:
        at = datetime.fromisoformat(str(health.get("at")))
        if at.tzinfo is None:
            raise ValueError("naive")
        snap_age = round((now - at).total_seconds() / 60.0, 1)
    except (TypeError, ValueError):
        pass

    procs = [p for p in health["processes"] if isinstance(p, dict)]
    starts = [parse_box_time(p.get("last_run")) for p in procs]
    newest = max((s for s in starts if s is not None), default=None)
    manifest = manifest_rows(manifest_path)
    installers = installer_index(root)

    entries: list[dict[str, Any]] = []
    for p in procs:
        verdict = str(p.get("verdict") or "")
        if verdict not in LISTED:
            continue
        name = str(p.get("name") or "")
        base = name.split(" (")[0]
        rows = manifest.get(base, [])
        sources = [s for r in rows for s in _source_paths(r)]
        fallback = [] if rows else installers.get(base, [])
        declared, referenced = scan_artifacts(root, sources + fallback)
        arts = set(declared)
        contracted = p.get("artifact")
        if contracted:
            arts.add(str(contracted))
        start = parse_box_time(p.get("last_run"))
        lag = (
            round((newest - start).total_seconds() / 60.0, 1)
            if start is not None and newest is not None
            else UNMEASURED
        )
        raw_error = str(p.get("last_result") or p.get("why") or "")
        error_text = error_head(raw_error, p.get("last_result_code"))
        entry: dict[str, Any] = {
            "name": name,
            "verdict": verdict,
            "state": p.get("state"),
            "why": scrub_paths(p.get("why")),
            "last_run_box_local": p.get("last_run") or UNMEASURED,
            "age": {
                "snapshot_age_min": snap_age,
                "artifact_age_min": _measured(p.get("artifact_age_min")),
                "contract_max_age_min": _measured(p.get("contract_max_age_min")),
                "last_run_lag_min": lag,
            },
            "last_rc": _measured(p.get("last_result_code")),
            "error_text": error_text,
            "produces": {
                "contracted_artifact": contracted or UNMEASURED,
                "manifest": [
                    {
                        k: r.get(k)
                        for k in ("runs", "organ", "installer", "trigger", "lane")
                        if r.get(k)
                    }
                    for r in rows
                ]
                or "NOT_IN_MANIFEST",
                "installers_naming_it": fallback
                if not rows
                else sorted(
                    {
                        r["installer"]
                        for r in rows
                        if r.get("installer") and r["installer"] != "NONE"
                    }
                ),
                "artifacts": sorted(arts) if arts else UNMEASURED,
                "artifacts_note": "process_health's contracted artifact plus output-named "
                "constants in the run script or installer",
                "referenced_paths": sorted(set(referenced) - arts),
                "referenced_note": "other artifact paths named in that text; may be inputs",
            },
            "purpose": p.get("purpose"),
            "_start": start,
            "_generic": _is_generic(raw_error),
        }
        if verdict == "DISABLED":
            reason = EXPECTED_DISABLED.get(base)
            entry["expected_disabled"] = reason is not None
            entry["expected_reason"] = reason
        entries.append(entry)

    causes = shared_causes(entries)
    for e in entries:
        e.pop("_start", None)
        e.pop("_generic", None)
    counts: dict[str, int] = defaultdict(int)
    for e in entries:
        counts[e["verdict"]] += 1
    unexpected = [
        e["name"] for e in entries if e["verdict"] == "DISABLED" and not e.get("expected_disabled")
    ]
    status = "OK" if not entries else "ATTENTION"
    doc.update(
        {
            "status": status,
            "health_at": health.get("at"),
            "health_host": HOST_WITHHELD if health.get("host") else UNMEASURED,
            "box_clock_note": "last_run is the box's local clock (no zone); last_run_lag_min "
            "compares it only to the newest last_run in the same snapshot",
            "newest_box_start": newest.isoformat() if newest else UNMEASURED,
            "counts": dict(counts),
            "unexpected_disabled": unexpected,
            "expected_disabled": sorted(e["name"] for e in entries if e.get("expected_disabled")),
            "not_in_manifest": sorted(
                e["name"] for e in entries if e["produces"]["manifest"] == "NOT_IN_MANIFEST"
            ),
            "shared_causes": causes,
            "tasks": entries,
        }
    )
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--health", type=Path, default=HEALTH)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(a.health, a.manifest, a.root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(a.out)
    print(f"{doc['status']}: {doc.get('counts')} -> {a.out}")
    return 0

