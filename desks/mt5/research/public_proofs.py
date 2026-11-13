#!/usr/bin/env python3
"""THE PROOFS BEHIND THE DONE ROWS, PUBLISHED: redacted projections of box-local artifacts.

    python desks/mt5/research/public_proofs.py              # core hourly leg `public_proofs`
    python desks/mt5/research/public_proofs.py --json       # also print the manifest
    python desks/mt5/research/public_proofs.py --disk-budget-s 120

WHY (underbuilt audit 2026-11-13). Several rows marked DONE could not be verified from the
branch because the artifact that proves them existed only on the trading box:

  L141 recovery drills        RECOVERY_DRILLS.json ("residual FAIL rows remain" -- which?)
  L144 six committees         COMMITTEES.json, COMMITTEE_HEALTH.json
  L230 Asia alpha capture     ANALYST_VIEWS*, ALPHA_CAPTURE_ALLOCATION_INTEL, ALT_PROXIES*,
                              PAID_SUBSTITUTE_COVERAGE
  L115 CPU cleanup            the memecoin 10% cap and the judge's measured CPU share
  L310 memecoin paper trading an end-to-end paper fill
  L318 memecoin backups       whether the 493 GB of old backups are gone
  and, from ops/organ_contract.py, the box-local artifacts behind L110/L111/L113/L126/L218/L77

DONE MEANS IT RUNS AND LEAVES AN ARTIFACT WE CAN SEE (III.16). The box's sync
(`desks/mt5/scripts/sync_shadow_to_git.ps1`, `$reportPaths`) publishes every file this writes,
under `desks/mt5/reports/public/`, and nothing else from here.

THE REPOSITORY IS PUBLIC. No source is copied raw. Each goes through `libs/ops/public_redact.py`
(identity keys dropped, errors reduced to their exception TYPE, paths made repo-relative, host
names, IPs, tokens, e-mails and declared account numbers replaced) and is bounded to MAX_BYTES.
The serialised result is then scanned (`public_redact.violations`); a projection that still
trips the scan is replaced by its reduced summary (counts, verdicts, timestamps), and one that
trips it even then is written as a REFUSED stub naming only the categories. Ledgers and tape are
never read whole and never published.

ABSENT IS A VERDICT (L1.28a). A source missing on this host is published as an ABSENT stub, so
the branch says "the organ has not written here", never nothing.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import public_redact as R  # noqa: E402

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT_DIR = REPORTS / "public"
MANIFEST = OUT_DIR / "PUBLIC_PROOFS.json"
SCHEMA = "public_proofs/1"

#: The largest published projection. A report, never a ledger.
MAX_BYTES = 96 * 1024
#: A source above this is not parsed at all: only its size and age are published.
MAX_SOURCE_BYTES = 64 * 1024 * 1024
#: The memecoin bot's resource-limit root (zuck's box layout, read 2026-11-10/11) and where its
#: role status files live. Overridable; read-only.
MEMECOIN_LIMITS_ENV = "MEMECOIN_LIMITS_ROOT"
MEMECOIN_LIMITS_DEFAULT = r"C:\ProgramData\MemecoinResourceLimits"
MEMECOIN_EVIDENCE_ENV = "MEMECOIN_EVIDENCE_PATHS"     # os.pathsep list of JSONL files
MEMECOIN_DISK_ROOTS_ENV = "MEMECOIN_DISK_ROOTS"       # os.pathsep list of directories
MEMECOIN_CAP_PERCENT = 10.0
MEMECOIN_OWNER = "Memecoin thread (kingdemond434-cpu/memecoin; 'Finish the memecoin bot work')"
PAPER_FILL_MAX_AGE_H = 48.0
TAIL_BYTES = 512 * 1024
DISK_CENSUS_EVERY_H = 20.0

PUBLISHED, REDUCED, ABSENT, UNREADABLE, TOO_LARGE, REFUSED = (
    "PUBLISHED", "REDUCED", "ABSENT", "UNREADABLE", "TOO_LARGE", "REFUSED")
UNMEASURED = "UNMEASURED"

#: (published name, source path relative to the repository, the DONE rows it backs, the keys
#: whose (large) value is published as a count only).
SOURCES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("RECOVERY_DRILLS", "desks/mt5/reports/RECOVERY_DRILLS.json", ("L141",), ()),
    # the drills' own inputs, so a FAIL row can be traced to the organ that reported it
    ("OPS_REDUNDANCY", "desks/mt5/reports/OPS_REDUNDANCY.json", ("L141",), ()),
    ("REBOOT_DRILL", "desks/mt5/reports/REBOOT_DRILL.json", ("L141", "L111"), ()),
    ("OFFSITE_BACKUP", "desks/mt5/reports/OFFSITE_BACKUP.json", ("L141",), ()),
    ("COMMITTEES", "desks/mt5/reports/COMMITTEES.json", ("L144",),
     ("experiments_ranked", "contradictions", "minority_reports", "trees_sample", "traps",
      "settled_this_pass")),
    ("COMMITTEE_HEALTH", "desks/mt5/reports/COMMITTEE_HEALTH.json", ("L144", "L145"), ()),
    ("ANALYST_VIEWS", "desks/mt5/reports/ANALYST_VIEWS.json", ("L230",), ()),
    ("ANALYST_VIEWS_CONTRACT", "desks/mt5/reports/ANALYST_VIEWS_CONTRACT.json", ("L230",), ()),
    ("ALPHA_CAPTURE_ALLOCATION_INTEL",
     "desks/mt5/reports/ALPHA_CAPTURE_ALLOCATION_INTEL.json", ("L230",), ()),
    ("ALT_PROXIES", "desks/mt5/reports/ALT_PROXIES.json", ("L230",), ()),
    ("ALT_PROXIES_ALLOCATION_INTEL",
     "desks/mt5/reports/ALT_PROXIES_ALLOCATION_INTEL.json", ("L230",), ()),
    ("PAID_SUBSTITUTE_COVERAGE", "desks/mt5/reports/PAID_SUBSTITUTE_COVERAGE.json",
     ("L230",), ()),
    # ops/organ_contract.py rows whose artifact is box-local and backs a DONE claim
    ("TAPE_RECORDER", "desks/mt5/reports/TAPE_RECORDER.json", ("L113", "L228"), ()),
    ("TERMINAL_BOOT", "desks/mt5/data/terminal_boot_ok.json", ("L111",), ()),
    ("RELEASE_AUTHORITY_AUDIT", "desks/mt5/reports/RELEASE_AUTHORITY_AUDIT.json", ("L110",), ()),
    ("VIDEO_MINING_COVERAGE", "desks/mt5/reports/VIDEO_MINING_COVERAGE.json", ("L218",), ()),
    ("WEAK_SIGNAL_COMPILER", "desks/mt5/reports/weak_signal_compiler.json", ("L126",), ()),
    ("CONVERSION_HANDOFF", "desks/mt5/data/hypotheses/conversion_handoff.json", ("L77",),
     ("cells", "rows", "handoff", "items")),
    ("NEVER_STALE", "desks/mt5/reports/NEVER_STALE.json", ("L113", "L111"), ()),
)
#: The generated proofs (no single source file); their published names.
GENERATED = ("MEMECOIN_PROOF", "CPU_SHARE", "DISK_USAGE")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime | None) -> str | None:
    return t.isoformat(timespec="seconds") if t else None


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return R.ABS


def out_path(name: str) -> Path:
    return OUT_DIR / f"{name}.json"


def published_paths() -> list[str]:
    """Every repo-relative path this writes: the sync's list is pinned against this."""
    names = [n for n, *_ in SOURCES] + list(GENERATED)
    return [f"desks/mt5/reports/public/{n}.json" for n in names] + [
        "desks/mt5/reports/public/PUBLIC_PROOFS.json"]


def _write(path: Path, doc: Any) -> int:
    text = R.dumps_public(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    try:
        from libs.ops.win_write import replace_resilient
        replace_resilient(tmp, path)
    except ImportError:
        os.replace(tmp, path)
    return len(text.encode("utf-8"))


# ------------------------------------------------------------------ the generic projection
def _row_verdicts(doc: Any) -> dict[str, dict[str, int]]:
    """For every top-level collection of rows that carry a verdict/status: the histogram."""
    out: dict[str, dict[str, int]] = {}
    if not isinstance(doc, dict):
        return out
    for k, v in doc.items():
        rows = list(v.values()) if isinstance(v, dict) else v if isinstance(v, list) else []
        c: Counter[str] = Counter()
        for r in rows:
            if isinstance(r, dict):
                for vk in ("verdict", "status", "state"):
                    if isinstance(r.get(vk), str) and len(r[vk]) <= 40:
                        c[R.public_text(r[vk], 40)] += 1
                        break
        if c:
            out[R.public_text(k, 80)] = dict(c)
    return out


def _stamp(doc: Any) -> str | None:
    if isinstance(doc, dict):
        for k in ("generated_utc", "generated_at", "at", "checked_at", "measured_at", "ts",
                  "updated_at", "last_pass"):
            if isinstance(doc.get(k), str) and len(doc[k]) <= 40:
                return R.public_text(doc[k], 40)
    return None


def reduced(doc: Any) -> dict[str, Any]:
    """Counts, verdicts and timestamps only: what is published when a projection is unsafe."""
    out: dict[str, Any] = {"generated_utc": _stamp(doc), "row_verdicts": _row_verdicts(doc)}
    if isinstance(doc, dict):
        shape: dict[str, Any] = {}
        for k, v in doc.items():
            if R.is_drop_key(k) or R.is_error_key(k):
                continue
            key = R.public_text(k, 80)
            if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
                shape[key] = v
            elif isinstance(v, str):
                if re.fullmatch(r"[A-Z][A-Z0-9_]{1,39}", v):      # an enum-shaped verdict
                    shape[key] = v
            elif isinstance(v, (list, dict)):
                shape[key] = {"n": len(v)}
        out["fields"] = shape
    return out


def project(doc: Any, *, count_only: tuple[str, ...] = ()) -> tuple[Any, dict[str, Any]]:
    """The largest redacted projection of `doc` that fits MAX_BYTES and passes the scan."""
    if isinstance(doc, dict) and count_only:
        doc = {k: ({"n": len(v)} if k in count_only and isinstance(v, (list, dict)) else v)
               for k, v in doc.items()}
    for depth, lst in ((6, 50), (5, 25), (4, 12), (3, 6), (2, 3)):
        proj, removed = R.public_fields(doc, max_depth=depth, max_list=lst)
        text = R.dumps_public(proj)
        if len(text.encode("utf-8")) > MAX_BYTES:
            continue
        bad = R.violations(text)
        if bad:
            return None, {"violations": bad, **removed}
        return proj, {"max_depth": depth, "max_list": lst, **removed}
    return None, {"violations": ["over_size"]}


def publish_source(name: str, rel: str, backs: tuple[str, ...], count_only: tuple[str, ...],
                   now: datetime, root: Path = ROOT) -> dict[str, Any]:
    src = root / rel
    head: dict[str, Any] = {"schema": SCHEMA, "name": name, "source": rel, "backs": list(backs),
            "generated_utc": _iso(now)}
    row: dict[str, Any] = {"name": name, "source": rel, "backs": list(backs),
                           "out": f"desks/mt5/reports/public/{name}.json"}
    try:
        st = src.stat()
    except OSError:
        doc = head | {"status": ABSENT, "verdict": UNMEASURED,
                      "why": "the source is absent on this host: its organ has not written here"}
        row.update(status=ABSENT, bytes=_write(out_path(name), doc))
        return row
    mtime = datetime.fromtimestamp(st.st_mtime, UTC)
    meta = {"source_bytes": st.st_size, "source_mtime_utc": _iso(mtime),
            "source_age_h": round((now - mtime).total_seconds() / 3600, 2)}
    row.update(meta)
    if st.st_size > MAX_SOURCE_BYTES:
        doc = head | meta | {"status": TOO_LARGE,
                             "why": f"over {MAX_SOURCE_BYTES} bytes: size and age only"}
        row.update(status=TOO_LARGE, bytes=_write(out_path(name), doc))
        return row
    try:
        raw = json.loads(src.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        doc = head | meta | {"status": UNREADABLE, "verdict": UNMEASURED,
                             "why": f"unreadable: {type(exc).__name__}"}
        row.update(status=UNREADABLE, bytes=_write(out_path(name), doc))
        return row
    raw_hits = R.violations(json.dumps(raw, default=str)[:4_000_000])
    custom = CUSTOM.get(name)
    body = custom(raw) if custom else raw
    proj, how = project(body, count_only=count_only)
    status = PUBLISHED
    if proj is None:
        proj, how2 = project(reduced(raw))
        how = {**how, "reduced": how2}
        status = REDUCED
        if proj is None:
            proj = {"why": "even the reduced summary tripped the public scan",
                    "categories": how2.get("violations")}
            status = REFUSED
    doc = head | meta | {"status": status, "redaction": how, "found_in_source": raw_hits,
                         "row_verdicts": _row_verdicts(raw), "body": proj}
    row.update(status=status, found_in_source=raw_hits, bytes=_write(out_path(name), doc))
    return row


# ------------------------------------------------------------------- per-source shaping
def _recovery_drills(doc: Any) -> Any:
    """L141: every mode's verdict and its PASS/FAIL tally, without the raw history list."""
    if not isinstance(doc, dict):
        return doc
    rows = doc.get("drills") or []
    got = doc.get("per_mode")
    per: dict[str, Any] = got if isinstance(got, dict) else {}
    keep = ("drill", "failure_mode", "verdict", "evidence", "why", "gap", "fix",
            "needs_principal", "faults", "age_h")
    return {
        "generated_utc": doc.get("generated_utc"), "verdict": doc.get("verdict"),
        "counts": doc.get("counts"), "n": doc.get("n"), "rule": doc.get("rule"),
        "valid_until": doc.get("valid_until"),
        "failing_modes": doc.get("failing_modes") or [
            r.get("drill") for r in rows if isinstance(r, dict) and r.get("verdict") == "FAIL"],
        "drills": [{k: r.get(k) for k in keep if k in r} for r in rows if isinstance(r, dict)],
        "per_mode": {k: {kk: vv for kk, vv in v.items() if kk != "recent"}
                     for k, v in per.items() if isinstance(v, dict)},
        "per_mode_status": "CARRIED" if per else
        "ABSENT (the writer on this host predates the per-mode tally)",
    }


CUSTOM: dict[str, Callable[[Any], Any]] = {"RECOVERY_DRILLS": _recovery_drills}


# ------------------------------------------------------------------- memecoin (L310 / L115)
def _limits_root() -> Path:
    return Path(os.environ.get(MEMECOIN_LIMITS_ENV) or MEMECOIN_LIMITS_DEFAULT)


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _roles(doc: Any) -> dict[str, dict[str, Any]]:
    """roles.json in whichever shape it has: {role: {...}}, {"roles": ...} or [{role: ..}]."""
    if isinstance(doc, dict) and isinstance(doc.get("roles"), (dict, list)):
        doc = doc["roles"]
    out: dict[str, dict[str, Any]] = {}
    if isinstance(doc, dict):
        for k, v in doc.items():
            if isinstance(v, dict):
                out[str(k)] = v
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            if isinstance(v, dict):
                out[str(v.get("role") or v.get("name") or f"role{i}")] = v
    return out


def _epoch_or_iso(v: Any) -> datetime | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        if x > 1e12:
            x /= 1000.0
        if 1e9 < x < 1e10:
            return datetime.fromtimestamp(x, UTC)
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _f(v: Any) -> float | None:
    try:
        return None if isinstance(v, bool) or v is None else float(v)
    except (TypeError, ValueError):
        return None


def memecoin_limits(now: datetime) -> dict[str, Any]:
    """The 10% cap, as the memecoin launcher records it per role (status/<role>.json)."""
    root = _limits_root()
    roles = _roles(_read_json(root / "roles.json"))
    status_dir = root / "status"
    rows: list[dict[str, Any]] = []
    try:
        files = sorted(status_dir.glob("*.json"))
    except OSError:
        files = []
    for f in files:
        d = _read_json(f)
        if not isinstance(d, dict):
            rows.append({"role": R.public_text(f.stem, 40), "state": UNREADABLE})
            continue
        obs = _epoch_or_iso(d.get("observed_at"))
        role = str(d.get("role") or f.stem)
        rows.append({
            "role": R.public_text(role, 40),
            "task": R.public_text((roles.get(role) or {}).get("task") or "", 60) or None,
            "state": R.public_text(d.get("state") or "", 30) or None,
            "observed_utc": _iso(obs),
            "age_h": round((now - obs).total_seconds() / 3600, 2) if obs else None,
            "cpu_percent_cap": _f(d.get("cpu_percent")),
            "cpu_rate": _f(d.get("cpu_rate")),
            "total_configured_percent": _f(d.get("total_configured_percent")),
            "exit_code": d.get("exit_code") if isinstance(d.get("exit_code"), int) else None,
            "live_authority_changed": d.get("live_authority_changed")
            if isinstance(d.get("live_authority_changed"), bool) else None,
        })
    if not rows:
        return {"verdict": UNMEASURED, "roles": [], "n_roles_declared": len(roles),
                "why": "no memecoin role status file is readable on this host "
                       f"(set {MEMECOIN_LIMITS_ENV} if the limits root moved)"}
    bounded = [r for r in rows if r.get("state") == "BOUNDED"]
    caps = [r["cpu_percent_cap"] for r in bounded if r.get("cpu_percent_cap") is not None]
    totals = {r["total_configured_percent"] for r in rows
              if r.get("total_configured_percent") is not None}
    total = max(totals) if totals else None
    cap_sum = round(sum(caps), 3)
    unbounded_running = [r["role"] for r in rows
                         if r.get("state") not in ("BOUNDED", "EXITED", "STOPPED", None)]
    held = (total is not None and total <= MEMECOIN_CAP_PERCENT and cap_sum <= total
            and not unbounded_running)
    return {"verdict": "CAP_CONFIGURED_AND_BOUND" if held else
            UNMEASURED if total is None else "CAP_NOT_PROVEN",
            "cap_percent_of_machine": MEMECOIN_CAP_PERCENT,
            "total_configured_percent": total, "bounded_roles_cap_sum_percent": cap_sum,
            "n_roles": len(rows), "n_bounded": len(bounded),
            "roles_running_unbounded": unbounded_running,
            "live_authority_changed_any": any(r.get("live_authority_changed") for r in rows),
            "roles": rows,
            "reads": "per-role status written by the memecoin launcher (job-object CPU rate); "
                     "the measured share is CPU_SHARE.json"}


_FILL_KEYS = frozenset({"fill", "fills", "filled", "fillprice", "filledqty", "filledsize",
                        "filledamount", "executedqty", "executedprice", "execprice",
                        "fillid", "filledat"})
_EVENT_KEYS = ("event", "kind", "type", "status", "action", "outcome", "phase")
_TS_KEYS = ("filled_at", "ts", "at", "time", "timestamp", "observed_at", "created_at", "t")


def _evidence_files() -> list[tuple[str, Path]]:
    env = os.environ.get(MEMECOIN_EVIDENCE_ENV)
    if env:
        return [(f"env{i}", Path(p)) for i, p in enumerate(env.split(os.pathsep)) if p]
    roles = _roles(_read_json(_limits_root() / "roles.json"))
    out: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for role, spec in roles.items():
        wd = spec.get("working_directory")
        if not isinstance(wd, str) or not wd:
            continue
        state = Path(wd) / "data" / "state"
        cands = [state / "trade_evidence.jsonl"]
        with contextlib.suppress(OSError):
            cands += sorted(p for p in state.glob("*.jsonl")
                            if re.search(r"(?i)fill|paper|trade|order|execution", p.name))
        for p in cands:
            k = str(p).lower()
            if k not in seen and p.is_file():
                seen.add(k)
                out.append((role, p))
    return out


def _tail_rows(p: Path, n_bytes: int = TAIL_BYTES) -> list[dict[str, Any]]:
    with open(p, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - n_bytes))
        data = fh.read()
    lines = data.split(b"\n")
    if size > n_bytes:
        lines = lines[1:]          # the first line is cut mid-row
    rows = []
    for ln in lines:
        with contextlib.suppress(ValueError, UnicodeDecodeError):
            d = json.loads(ln)
            if isinstance(d, dict):
                rows.append(d)
    return rows


def _is_fill(row: dict[str, Any]) -> bool:
    keys = {re.sub(r"[^a-z]", "", str(k).lower()) for k in row}
    if keys & _FILL_KEYS:
        return True
    return any(isinstance(row.get(k), str) and "fill" in row[k].lower() for k in _EVENT_KEYS)


def _row_time(row: dict[str, Any]) -> datetime | None:
    for k in _TS_KEYS:
        if k in row:
            t = _epoch_or_iso(row[k])
            if t:
                return t
    return None


def _is_live(row: dict[str, Any]) -> bool:
    mode = str(row.get("mode") or row.get("trading_mode") or "").lower()
    return mode == "live" or row.get("paper") is False or row.get("live") is True


def memecoin_paper_fill(now: datetime) -> dict[str, Any]:
    """L310: an end-to-end PAPER fill, read from the bot's own evidence file (counts only)."""
    files = _evidence_files()
    if not files:
        return {"verdict": UNMEASURED, "owned_by": MEMECOIN_OWNER,
                "why": "no memecoin trade-evidence file is readable on this host: the bot's "
                       "roles.json names no working directory with data/state/*.jsonl, or this "
                       f"account cannot read it (set {MEMECOIN_EVIDENCE_ENV}). The quant repo "
                       "defines no paper-fill contract of its own; the memecoin repo owns it."}
    per: list[dict[str, Any]] = []
    newest_fill: datetime | None = None
    fills = live = rows_n = 0
    for role, p in files:
        try:
            rows = _tail_rows(p)
            size = p.stat().st_size
        except OSError as exc:
            per.append({"role": R.public_text(role, 40), "file": R.public_text(p.name, 80),
                        "status": UNREADABLE, "why": type(exc).__name__})
            continue
        f_rows = [r for r in rows if _is_fill(r)]
        times = [t for t in (_row_time(r) for r in f_rows) if t]
        last = max(times) if times else None
        n_live = sum(1 for r in rows if _is_live(r))
        per.append({"role": R.public_text(role, 40), "file": R.public_text(p.name, 80),
                    "bytes": size, "tail_rows": len(rows), "fill_rows_in_tail": len(f_rows),
                    "live_rows_in_tail": n_live, "newest_fill_utc": _iso(last),
                    "newest_row_utc": _iso(max((t for t in (_row_time(r) for r in rows) if t),
                                               default=None))})
        rows_n += len(rows)
        fills += len(f_rows)
        live += n_live
        if last and (newest_fill is None or last > newest_fill):
            newest_fill = last
    age = round((now - newest_fill).total_seconds() / 3600, 2) if newest_fill else None
    if live:
        verdict = "LIVE_ROWS_SEEN"
    elif fills and age is not None and age <= PAPER_FILL_MAX_AGE_H:
        verdict = "PAPER_FILL_PROVEN"
    elif fills:
        verdict = "FILL_SEEN_STALE" if age is not None else "FILL_SEEN_UNDATED"
    elif rows_n:
        verdict = "NO_FILL_IN_TAIL"
    else:
        verdict = UNMEASURED
    return {"verdict": verdict, "owned_by": MEMECOIN_OWNER, "newest_fill_utc": _iso(newest_fill),
            "newest_fill_age_h": age, "max_age_h": PAPER_FILL_MAX_AGE_H, "fill_rows": fills,
            "live_rows": live, "rows_read": rows_n, "files": per,
            "rule": f"PAPER_FILL_PROVEN = a fill-shaped row in the last {TAIL_BYTES} bytes of the "
                    f"bot's evidence, newer than {PAPER_FILL_MAX_AGE_H:g}h, and no live row"}


# ------------------------------------------------------------------------- CPU share (L115)
_JUDGE = re.compile(r"(?i)gauntlet|judge|external_backtest|judging|resident_judge|deepen")
_MEME = re.compile(r"(?i)memecoin")


def cpu_share(sample_s: float = 1.0) -> dict[str, Any]:
    """Measured CPU share of this machine, by process class (no names, no command lines)."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return {"verdict": UNMEASURED, "why": "psutil is not installed here"}
    procs = []
    for p in psutil.process_iter(["name"]):
        with contextlib.suppress(psutil.Error):
            p.cpu_percent(None)
            procs.append(p)
    time.sleep(max(0.2, sample_s))
    ncpu = psutil.cpu_count() or 1
    share: Counter[str] = Counter()
    count: Counter[str] = Counter()
    for p in procs:
        try:
            pct = p.cpu_percent(None)
            name = (p.info.get("name") or "").lower()
        except psutil.Error:
            continue
        try:
            cmd = " ".join(p.cmdline())
            readable = True
        except psutil.Error:
            cmd, readable = "", False
        if _MEME.search(cmd):
            cls = "memecoin"
        elif "terminal64" in name or "metatrader" in name:
            cls = "mt5_terminal"
        elif "python" in name and _JUDGE.search(cmd):
            cls = "judge"
        elif "python" in name and readable:
            cls = "research_python"
        elif "python" in name:
            cls = "python_unreadable"
        elif name in ("system idle process", "idle"):
            continue
        else:
            cls = "other"
        share[cls] += pct
        count[cls] += 1
    pct_machine = {k: round(v / ncpu, 2) for k, v in share.items()}
    meme = pct_machine.get("memecoin")
    tp = _read_json(REPORTS / "JUDGING_THROUGHPUT.json")
    judge_tp = {k: tp.get(k) for k in ("busy_judge_cores", "workers", "generated_utc",
                                       "verdicts_last_hour")
                if isinstance(tp, dict) and k in tp} if isinstance(tp, dict) else {}
    return {
        "verdict": ("MEMECOIN_WITHIN_CAP" if meme is not None and meme <= MEMECOIN_CAP_PERCENT
                    else "MEMECOIN_OVER_CAP" if meme is not None else UNMEASURED),
        "why": None if meme is not None else
        "no process readable as memecoin from this account (its tasks run under another "
        "principal); MEMECOIN_PROOF.limits carries the configured cap instead",
        "cores": ncpu, "sample_s": sample_s,
        "percent_of_machine": pct_machine, "processes": dict(count),
        "machine_percent": round(psutil.cpu_percent(None), 2),
        "judge_cores_busy_measured": round(share.get("judge", 0.0) / 100.0, 2),
        "judging_throughput": judge_tp,
    }


# --------------------------------------------------------------------- disk usage (L318)
_BACKUP = re.compile(r"(?i)backup|bak\b|snapshot|archive|\bold\b|copy|_old|-old")


def _default_disk_roots() -> list[Path]:
    if os.name == "nt":
        roots = [Path(os.environ.get("USERPROFILE") or r"C:\Users\Administrator"),
                 Path(r"C:\ProgramData"), Path("C:\\")]
        roots += [Path(f"{d}:\\") for d in "DEF" if Path(f"{d}:\\").exists()]
        return roots
    return [Path.home()]


def _dir_size(p: Path, deadline: float) -> tuple[int, int, bool]:
    total = files = 0
    stack = [p]
    while stack:
        if time.monotonic() > deadline:
            return total, files, False
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(Path(e.path))
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, files, True


def disk_usage(now: datetime, budget_s: float, prior: Any = None) -> dict[str, Any]:
    """Drive totals every pass; the memecoin directory census once per DISK_CENSUS_EVERY_H."""
    drives: list[dict[str, Any]] = []
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        parts = psutil.disk_partitions(all=False)
        for i, part in enumerate(parts):
            mp = part.mountpoint
            label = mp.rstrip("\\/") if re.fullmatch(r"[A-Za-z]:[\\/]?", mp) else (
                "/" if mp == "/" else f"vol{i}")
            with contextlib.suppress(OSError, PermissionError):
                u = psutil.disk_usage(mp)
                if u.total < 1e9:          # pseudo and boot volumes say nothing about backups
                    continue
                drives.append({"volume": label, "total_gb": round(u.total / 1e9, 1),
                               "used_gb": round(u.used / 1e9, 1),
                               "free_gb": round(u.free / 1e9, 1)})
    except ImportError:
        pass
    census = (prior or {}).get("memecoin_dirs") if isinstance(prior, dict) else None
    last = _epoch_or_iso((census or {}).get("measured_utc")) if isinstance(census, dict) else None
    due = (last is None or (now - last).total_seconds() / 3600 >= DISK_CENSUS_EVERY_H
           or not (census or {}).get("complete"))
    if due:
        census = memecoin_dir_census(now, budget_s)
    return {"drives": drives, "memecoin_dirs": census,
            "census_every_h": DISK_CENSUS_EVERY_H,
            "reads": "drive totals each pass; directory sizes (names only, no paths) once a day"}


def memecoin_dir_census(now: datetime, budget_s: float) -> dict[str, Any]:
    env = os.environ.get(MEMECOIN_DISK_ROOTS_ENV)
    roots = [Path(p) for p in env.split(os.pathsep) if p] if env else _default_disk_roots()
    in_use = {str(Path(v["working_directory"])).lower()
              for v in _roles(_read_json(_limits_root() / "roles.json")).values()
              if isinstance(v.get("working_directory"), str)}
    found: list[tuple[int, Path]] = []
    for ri, root in enumerate(roots):
        level = [root]
        for _depth in range(2):
            nxt = []
            for d in level:
                try:
                    kids = [Path(e.path) for e in os.scandir(d)
                            if e.is_dir(follow_symlinks=False)]
                except OSError:
                    continue
                for k in kids:
                    if _MEME.search(k.name):
                        if not any(k == f or f in k.parents for _, f in found):
                            found.append((ri, k))
                    else:
                        nxt.append(k)
            level = nxt
    deadline = time.monotonic() + max(1.0, budget_s)
    rows: list[dict[str, Any]] = []
    complete = True
    for ri, d in found:
        size, files, done = _dir_size(d, deadline)
        complete &= done
        low = str(d).lower()
        rows.append({"root": f"root{ri}", "name": R.public_text(d.name, 80),
                     "class": "in_use" if any(u == low or u.startswith(low + os.sep.lower())
                                              or u.startswith(low + "/") for u in in_use)
                     else "backup_like" if _BACKUP.search(d.name) or re.search(r"\d{8}", d.name)
                     else "other",
                     "gb": round(size / 1e9, 2), "files": files, "complete": done})
    by: dict[str, float] = {}
    for r in rows:
        by[str(r["class"])] = by.get(str(r["class"]), 0.0) + float(r["gb"])
    return {"measured_utc": _iso(now), "complete": complete, "budget_s": budget_s,
            "n_dirs": len(rows), "gb_total": round(sum(by.values()), 2),
            "gb_by_class": {k: round(v, 2) for k, v in by.items()},
            "dirs": rows[:40], "n_roots": len(roots),
            "rule": "a directory whose name contains 'memecoin', two levels below each root; "
                    "in_use = holds a role's working directory (roles.json); sizes are lower "
                    "bounds when complete is false"}


# ------------------------------------------------------------------------------ the pass
def _memecoin(now: datetime) -> dict[str, Any]:
    fill = memecoin_paper_fill(now)
    return {"verdict": fill["verdict"], "owned_by": MEMECOIN_OWNER, "paper_fill": fill,
            "limits": memecoin_limits(now)}


def _generated(name: str, body: dict[str, Any], backs: list[str],
               now: datetime) -> dict[str, Any]:
    proj, how = project(body)
    status = PUBLISHED
    if proj is None:
        proj, how2 = project(reduced(body))
        how = {**how, "reduced": how2}
        status = REDUCED if proj is not None else REFUSED
        if proj is None:
            proj = {"categories": how2.get("violations")}
    doc = {"schema": SCHEMA, "name": name, "backs": backs, "generated_utc": _iso(now),
           "status": status, "redaction": how, "body": proj}
    return {"name": name, "source": "measured on this host", "backs": backs,
            "out": f"desks/mt5/reports/public/{name}.json", "status": status,
            "verdict": (proj or {}).get("verdict") if isinstance(proj, dict) else None,
            "bytes": _write(out_path(name), doc)}


def run(now: datetime | None = None, *, disk_budget_s: float = 90.0,
        cpu_sample_s: float = 1.0, root: Path = ROOT) -> dict[str, Any]:
    now = now or _now()
    rows: list[dict[str, Any]] = []
    for name, rel, backs, count_only in SOURCES:
        try:
            rows.append(publish_source(name, rel, backs, count_only, now, root))
        except Exception as exc:          # one source's defect is not the manifest's silence
            rows.append({"name": name, "source": rel, "status": UNREADABLE,
                         "why": f"projection raised {type(exc).__name__}"})
    gens: list[tuple[str, Callable[[], dict[str, Any]], list[str]]] = [
        ("MEMECOIN_PROOF", lambda: _memecoin(now), ["L310", "L115"]),
        ("CPU_SHARE", lambda: cpu_share(cpu_sample_s), ["L115"]),
        ("DISK_USAGE", lambda: disk_usage(now, disk_budget_s,
                                          (_read_json(out_path("DISK_USAGE")) or {}).get("body")),
         ["L318"]),
    ]
    for name, fn, gbacks in gens:
        try:
            rows.append(_generated(name, fn(), gbacks, now))
        except Exception as exc:
            rows.append({"name": name, "status": UNREADABLE, "backs": gbacks,
                         "why": f"measurement raised {type(exc).__name__}"})
            with contextlib.suppress(OSError):
                _write(out_path(name), {"schema": SCHEMA, "name": name, "status": UNREADABLE,
                                        "generated_utc": _iso(now),
                                        "why": f"measurement raised {type(exc).__name__}"})
    counts = Counter(r.get("status") for r in rows)
    manifest: dict[str, Any] = {"schema": SCHEMA, "generated_utc": _iso(now), "n": len(rows),
                "counts": dict(counts), "proofs": rows,
                "rule": "each file is a redacted projection of a box-local artifact "
                        "(libs/ops/public_redact.py); ABSENT means the organ has not written on "
                        "this host; REDUCED means only counts, verdicts and times were safe"}
    bad = R.violations(R.dumps_public(manifest))
    if bad:
        manifest = {"schema": SCHEMA, "generated_utc": _iso(now), "counts": dict(counts),
                    "status": REFUSED, "categories": bad}
    _write(MANIFEST, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--disk-budget-s", type=float, default=90.0)
    ap.add_argument("--cpu-sample-s", type=float, default=1.0)
    a = ap.parse_args(argv)
    m = run(disk_budget_s=a.disk_budget_s, cpu_sample_s=a.cpu_sample_s)
    if a.json:
        print(R.dumps_public(m))
    else:
        print(f"public_proofs: {m.get('counts')} -> {_rel(MANIFEST)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
