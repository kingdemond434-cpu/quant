"""AN ATTESTATION CHANGE FREEZES ENROLMENT. THIS ORGAN MAKES THE NEXT SWEEP RE-JUDGE, AND TIMES IT.

THE FREEZE (measured 2026-09-30). Sealed pass 1 changed `gate_policy.ATTESTATION` (lockbox v4, DSR
variance 0.0002). `shadow_admission.authorized_runs()` reads the canon through `is_exact_policy`,
which is byte-equality outside `trial_count_basis`, so BOTH `reports/UNIVERSAL_SURVIVORS.json`
(58 rows, `...-v2-calibrated-inputs`) and `data/UNIVERSAL_SURVIVORS.canon.json` (52 rows) were
refused whole: 0 of 58 authorized, `promoter.load_cert_specs()` empty. LIVE sleeves are untouched;
no new clock enrols and nothing new promotes until a certificate store carries the new attestation.

THE TRAP ON THE WAY OUT, and why this organ does not simply wait. The sealed writer
(`external_gauntlet.py` main, the UNIVERSAL_SURVIVORS block) MERGES into the rows it loaded and
then stamps `gate_policy: ATTESTATION` on the whole file. So the first sweep that writes after an
attestation change re-stamps every old row with the new attestation WITHOUT re-judging one of
them, and `canon_publication` then carries the seal's old rows under the report's new header the
same way. That is a re-stamp, not a re-judge: enrolment would un-freeze on evidence the new bar
never saw. And the rows cannot reach the judge first on their own: the sealed sort's first key is
`_is_new`, which is 1 for every cell already in `gauntlet_seen_cells.json` -- every certificate --
so they sort BEHIND the whole never-judged backlog, and the novelty screen can set a certificate
aside as REDUNDANT against itself.

WHAT THIS DOES, EVERY HOUR, BEFORE THE JUDGE:

  1. MEASURES the attestation in force (fingerprint + the time it came into force), the attestation
     of the report and of the canon, and which rows of each were judged BEFORE it came into force
     (`gated_at < in_force_since`) -- whatever header they sit under. Rows under a current header
     that predate it are counted as RESTAMPED_NOT_REJUDGED, by name.
  2. QUEUES every such certificate for re-judgement: one PIT-stamped docket row with the
     certificate's own exact params (the params that passed; never family defaults) is APPENDED to
     `data/hypotheses/external_survivors.json` when that cell is not already there under this
     attestation. Appended in place, never rewritten: the docket is ~440 MB on the trading box.
     Presence is a byte scan for this organ's `remint_tag`, so the pass costs one read.
  3. WRITES `data/hypotheses/priority_remint.json` -- the cell ids, the certificate keys and the
     full ATTESTATION they must be judged under. The sealed patch
     `/mnt/project-files/patches/v4_remint/` makes the judge read it: those cells go to the
     FRONT of the sweep, are exempt from the novelty screen and the yield trim, and the report is
     re-minted honestly (re-judged passes stay, re-judged failures are retired with their NEW
     gates, unreached rows wait in `pending_rejudge` -- never under the new header).
  4. PUBLISHES `reports/REMINT_STATUS.json`: attestation in force, the report's and canon's, match,
     certificates pending, oldest pending age, the ETA from the measured judge rate, when the
     freeze began and when it ended.

THE FENCE. `breach` is set, and the leg exits 3, when enrolment is still frozen after a sweep that
STARTED after the freeze has completed (one sweep is the whole allowance), or when any row sits
under the current header while predating it (a re-stamp). `--check` re-reads the artifact and
exits 1 on a breach without touching anything.

NO FREE TRIALS AND NO NEW AUTHORITY. Every queued row goes through the one docket, so the sealed
judge charges it to the trial census and the gate ledger like any other cell. This organ writes no
certificate, no verdict and no attestation; it never edits the report, the canon or gate_policy.

Clock: leg `attestation_remint` in `research/hourly_cycle.py`, core plan, immediately before the
`external_gauntlet` leg. Artifacts: `reports/REMINT_STATUS.json`,
`data/hypotheses/priority_remint.json`. Consumers: the sealed judge (with the patch applied),
`research/canon_publication.py` (parks rows that predate the attestation), and the leg outcome.

    python desks/mt5/research/attestation_remint.py [--apply] [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
PRIORITY = DESK / "data" / "hypotheses" / "priority_remint.json"
#: This organ's own artifact (the name the component registry reads).
OUT = DESK / "reports" / "REMINT_STATUS.json"
STATUS = OUT
JUDGING_RATE = DESK / "reports" / "JUDGING_RATE.json"
GAUNTLET_ORDER = DESK / "reports" / "GAUNTLET_ORDER.json"
GATES_OUTPUT = DESK / "reports" / "universal_gates_external.json"
GAUNTLET_SRC = DESK / "scripts" / "external_gauntlet.py"
GATE_POLICY_SRC = DESK / "research" / "gate_policy.py"

SOURCE = "attestation_remint"
UNMEASURED = "UNMEASURED"
#: The string the sealed patch adds to the judge. Its presence is how this organ knows whether the
#: re-judge will be put first, rather than asserting it.
PATCH_MARKER = "priority_remint.json"
#: One docket row per (attestation, cell); the byte scan looks for exactly this field.
TAG_FIELD = "remint_tag"
_TAG_RE = re.compile(rb'"remint_tag"\s*:\s*"([^"]+)"')
_SCAN_CHUNK = 1 << 22
#: The scalp lane is re-judged daily by `scripts/scalp_gauntlet.py` against the same ATTESTATION;
#: its rows are counted here and never put on the H1 docket.
SCALP_PREFIX = "scalp."
EXIT_BREACH = 3


# --------------------------------------------------------------------------- small readers

def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(UTC) if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(t: datetime | None) -> str | None:
    return None if t is None else t.isoformat(timespec="seconds")


def _atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _policy() -> tuple[dict[str, Any], Any]:
    from gate_policy import ATTESTATION, is_exact_policy
    return dict(ATTESTATION), is_exact_policy


def fingerprint(attestation: Any) -> str:
    """The attestation's identity for dating purposes.

    `trial_count_basis` is left out on purpose: `gate_policy.is_exact_policy` accepts evidence
    judged under a superseded, HARDER trial charge, so a change in that field alone does not
    invalidate a single certificate and must not restart the clock on every row. Any other field
    changing is a new attestation.
    """
    if isinstance(attestation, dict):
        attestation = {k: v for k, v in attestation.items() if k != "trial_count_basis"}
    payload = json.dumps(attestation, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _git_changed_at(path: Path) -> datetime | None:
    """When the file holding ATTESTATION last changed in git, or None. Never later than now.

    Used only to date an attestation this organ sees for the first time. It is an UPPER bound on
    when the attestation came into force (a later unrelated edit moves it later, never earlier),
    so a row it misclassifies is a row that is re-judged once more -- never one that escapes.
    """
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", str(path)],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return _ts(out.stdout.strip()) if out.returncode == 0 else None


def in_force_since(fp: str, previous: dict[str, Any], now: datetime,
                   git_time: datetime | None = None) -> tuple[datetime, str]:
    """(when the attestation `fp` came into force, how that was established)."""
    if previous.get("attestation_fingerprint") == fp:
        t = _ts(previous.get("in_force_since"))
        if t is not None:
            return t, str(previous.get("in_force_basis") or "carried from the previous pass")
    if git_time is not None and git_time <= now:
        return git_time, "git: last commit of research/gate_policy.py (an upper bound)"
    return now, "first observed by this organ (an upper bound)"


def row_evidence_time(row: dict[str, Any]) -> datetime | None:
    """When the gates on this row were evaluated: `gated_at`, or a recovered sweep's stamp."""
    rec = row.get("recovered_from_gate_output")
    stamps = [_ts(row.get("gated_at"))]
    if isinstance(rec, dict):
        stamps.append(_ts(rec.get("gate_swept_at")))
    got = [t for t in stamps if t is not None]
    return max(got) if got else None


def stale_keys(doc: Any, since: datetime) -> list[str]:
    """Rows whose evidence predates the attestation in force (or carries no date at all)."""
    rows = doc.get("survivors") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return []
    out = []
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        t = row_evidence_time(row)
        if t is None or t < since:
            out.append(str(key))
    return sorted(out)


# --------------------------------------------------------------------------- what to re-judge

def _cell_id(sym: str, family: str, params: dict[str, Any]) -> str:
    from frontier_identity import cell_id
    return str(cell_id({"sym": sym, "family": family, "params": params}))


def rejudge_target(key: str, row: dict[str, Any]) -> dict[str, Any]:
    """The exact cell a certificate must be re-judged as, or why it cannot be queued."""
    if key.startswith(SCALP_PREFIX):
        return {"key": key, "queue": False, "lane": "scalp",
                "why": "re-judged daily by scripts/scalp_gauntlet.py under the same ATTESTATION"}
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    sym = str(spec.get("symbol") or row.get("sym") or "")
    fam = str(spec.get("family") or "")
    params = spec.get("params")
    if not sym or not fam:
        return {"key": key, "queue": False, "lane": "h1",
                "why": "no symbol/family on the certificate's shadow_spec"}
    if not isinstance(params, dict):
        # Never guessed: the params that passed are the strategy. `rejudge_evicted` owns this case.
        return {"key": key, "queue": False, "lane": "h1",
                "why": "shadow_spec.params was never recorded; re-judging defaults would judge a "
                       "different strategy"}
    cid = _cell_id(sym, fam, params)
    recorded = row.get("cell")
    return {"key": key, "queue": True, "lane": "h1", "symbol": sym, "family": fam,
            "params": dict(params), "cell_id": cid,
            "identity_matches_certificate": (None if not recorded else recorded == cid)}


def docket_row(t: dict[str, Any], fp: str, version: str, now: datetime) -> dict[str, Any]:
    from libs.data.pit import stamp
    params = dict(t["params"])
    body: dict[str, Any] = {
        "symbol": t["symbol"], "family": t["family"], "params": params,
        "source": SOURCE, "producer": SOURCE,
        "priority": "REMINT_UNDER_CURRENT_ATTESTATION",
        TAG_FIELD: f"{fp}:{t['cell_id']}",
        "certificate_key": t["key"],
        "attestation_version": version,
        # Gate 1 reads this. Every certificate already passed it once under its own family.
        "mechanism_status": "NAMED",
        "mechanism_note": (f"re-judge of certificate {t['key']} under attestation {version} "
                           f"({fp}); its gates predate the attestation in force"),
        "first_seen": now.isoformat(timespec="seconds"),
    }
    if isinstance(params.get("timeframe"), str):
        body["timeframe"] = params["timeframe"]
    return stamp(body, SOURCE, now=now)


def docket_tags(path: Path) -> set[str] | None:
    """Every `remint_tag` already on the docket, by a byte scan. None when unreadable."""
    tags: set[str] = set()
    tail = b""
    try:
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(_SCAN_CHUNK)
                if not chunk:
                    break
                buf = tail + chunk
                for m in _TAG_RE.finditer(buf):
                    tags.add(m.group(1).decode("utf-8", "replace"))
                tail = buf[-512:]
    except OSError:
        return None
    return tags


def append_to_docket(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Append rows inside the docket's top-level JSON array, in place. Never rewrites the file."""
    if not rows:
        return {"appended": 0}
    try:
        with path.open("r+b") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            back = min(size, 4096)
            fh.seek(size - back)
            end = fh.read(back)
            close = end.rstrip().rfind(b"]")
            if close < 0 or end.rstrip()[-1:] != b"]":
                return {"appended": 0, "refused": "docket does not end in a JSON array close"}
            before = end[:close].rstrip()
            empty = before.endswith(b"[")
            blob = ",\n".join(json.dumps(r, default=str) for r in rows).encode("utf-8")
            fh.seek(size - back + close)
            fh.write((b"\n" if empty else b",\n") + blob + b"\n]\n")
            fh.truncate()
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        return {"appended": 0, "refused": f"{type(exc).__name__}: {exc}"}
    return {"appended": len(rows)}


# --------------------------------------------------------------------------- sweeps and rates

def _sweep_times() -> dict[str, Any]:
    """Last sweep START (GAUNTLET_ORDER.json `at`) and last sweep COMPLETION (gate output)."""
    order = _read(GAUNTLET_ORDER)
    started = _ts(order.get("at")) if isinstance(order, dict) else None
    completed = None
    try:
        completed = datetime.fromtimestamp(GATES_OUTPUT.stat().st_mtime, tz=UTC)
    except OSError:
        completed = None
    return {"last_sweep_started_at": started, "last_sweep_completed_at": completed}


def judge_rate() -> dict[str, Any]:
    doc = _read(JUDGING_RATE)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": f"{JUDGING_RATE.name} absent or unreadable"}
    vph = doc.get("verdicts_per_hour")
    if not isinstance(vph, (int, float)) or isinstance(vph, bool):
        return {"status": UNMEASURED, "why": f"{JUDGING_RATE.name} verdicts_per_hour={vph!r}",
                "measured_at": doc.get("at")}
    return {"status": "MEASURED", "verdicts_per_hour": float(vph), "measured_at": doc.get("at"),
            "backlog": doc.get("backlog"), "eta_to_drain": doc.get("eta_to_drain"),
            "source": f"{JUDGING_RATE.name} verdicts_per_hour (24h window of the gate ledger)"}


def eta(pending: int, rate: dict[str, Any], patched: bool) -> dict[str, Any]:
    if pending == 0:
        return {"status": "NONE_PENDING", "hours": 0.0}
    vph = rate.get("verdicts_per_hour") if rate.get("status") == "MEASURED" else None
    front = (round(pending / vph, 2) if isinstance(vph, float) and vph > 0 else None)
    if patched:
        return {"status": "FRONT_OF_DOCKET" if front is not None else UNMEASURED,
                "hours": front,
                "basis": ("pending certificates / measured verdicts per hour; they are judged "
                          "first, so the next sweep reaches them before any other cell"),
                "rate": rate}
    drain = rate.get("eta_to_drain") if isinstance(rate.get("eta_to_drain"), dict) else {}
    return {"status": "AWAITING_SEALED_PATCH", "hours": None,
            "hours_if_patched": front,
            "hours_behind_backlog": drain.get("hours"),
            "basis": ("the unpatched sealed sort puts every already-judged cell behind the "
                      "never-judged backlog (_is_new=1), and its next write re-stamps the stale "
                      "rows instead of re-judging them; apply "
                      "/mnt/project-files/patches/v4_remint/"),
            "rate": rate}


def _authorized_runs() -> dict[str, Any]:
    try:
        from shadow_admission import authorized_runs
        return {"status": "MEASURED", "n": len(authorized_runs(DESK))}
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:200]}


# --------------------------------------------------------------------------- the pass

def _store(doc: Any, is_exact: Any, att: dict[str, Any], since: datetime) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {"status": "ABSENT", "exact": False, "n": 0, "stale": [], "pending_rejudge": 0}
    gp = doc.get("gate_policy")
    exact = bool(is_exact(gp))
    stale = sorted((doc.get("survivors") or {}).keys()) if not exact else stale_keys(doc, since)
    pend = doc.get("pending_rejudge")
    return {"status": "READ", "exact": exact,
            "version": gp.get("version") if isinstance(gp, dict) else None,
            "fingerprint": fingerprint(gp) if isinstance(gp, dict) else None,
            "differs_in": (sorted(k for k in set(gp) | set(att) if gp.get(k) != att.get(k))
                           if isinstance(gp, dict) else "no attestation"),
            "swept_at": doc.get("swept_at"), "n": len(doc.get("survivors") or {}),
            "stale": [str(k) for k in stale],
            "restamped_not_rejudged": (stale_keys(doc, since) if exact else []),
            "pending_rejudge": len(pend) if isinstance(pend, dict) else 0}


def _public(store: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in store.items() if k != "stale"}
    out["n_stale"] = len(store["stale"])
    return out


def build(now: datetime | None = None, *, previous: dict[str, Any] | None = None,
          git_time: datetime | None = None, patched: bool | None = None) -> dict[str, Any]:
    t = _now(now)
    att, is_exact = _policy()
    fp = fingerprint(att)
    prev = previous if previous is not None else (_read(STATUS) or {})
    prev = prev if isinstance(prev, dict) else {}
    if git_time is None and prev.get("attestation_fingerprint") != fp:
        git_time = _git_changed_at(GATE_POLICY_SRC)
    since, basis = in_force_since(fp, prev, t, git_time)

    report_doc, canon_doc = _read(REPORT), _read(CANON)
    report = _store(report_doc, is_exact, att, since)
    canon = _store(canon_doc, is_exact, att, since)

    # Every certificate whose evidence predates the attestation, from both stores and from any
    # rows a patched judge already parked. One target per cell identity.
    rows: dict[str, dict[str, Any]] = {}
    for doc, store in ((report_doc, report), (canon_doc, canon)):
        if not isinstance(doc, dict):
            continue
        surv = doc.get("survivors") or {}
        for key in store["stale"]:
            if isinstance(surv.get(key), dict):
                rows.setdefault(key, surv[key])
        pend = doc.get("pending_rejudge")
        if isinstance(pend, dict):
            for key, row in pend.items():
                if isinstance(row, dict):
                    rows.setdefault(str(key), row)
    targets = [rejudge_target(k, rows[k]) for k in sorted(rows)]
    queue = [x for x in targets if x.get("queue")]
    by_cell: dict[str, dict[str, Any]] = {}
    for x in queue:
        by_cell.setdefault(x["cell_id"], x)

    frozen = not (report["exact"] or canon["exact"])
    restamped = sorted(set(report["restamped_not_rejudged"]) | set(canon["restamped_not_rejudged"]))
    pending = len(rows)
    patched = (PATCH_MARKER in GAUNTLET_SRC.read_text("utf-8", errors="replace")
               if patched is None and GAUNTLET_SRC.exists() else bool(patched))

    frozen_at = _ts(prev.get("frozen_at")) if prev.get("attestation_fingerprint") == fp else None
    if frozen and frozen_at is None:
        # Enrolment froze the moment the attestation changed, not when this organ first looked.
        frozen_at = since
    sweeps = _sweep_times()
    first_start = (_ts(prev.get("first_sweep_started_after_freeze"))
                   if prev.get("attestation_fingerprint") == fp else None)
    started = sweeps["last_sweep_started_at"]
    if frozen and frozen_at is not None and first_start is None and started and started > frozen_at:
        first_start = started
    completed = sweeps["last_sweep_completed_at"]
    frozen_past_one_sweep = bool(frozen and first_start is not None and completed is not None
                                 and completed > first_start)
    same = prev.get("attestation_fingerprint") == fp
    reminted_at = _ts(prev.get("reminted_at")) if same else None
    if (not frozen and not restamped and pending == 0 and reminted_at is None
            and prev.get("frozen_at")):
        reminted_at = t
    breach_why = []
    if frozen_past_one_sweep:
        breach_why.append(f"enrolment still frozen after the sweep that started "
                          f"{_iso(first_start)} completed {_iso(completed)}")
    if restamped:
        breach_why.append(f"{len(restamped)} row(s) carry the current attestation but were judged "
                          f"before it came into force ({_iso(since)}): re-stamped, not re-judged")
    rate = judge_rate()
    oldest = min((x for x in (row_evidence_time(r) for r in rows.values()) if x), default=None)
    return {
        "at": _iso(t),
        "attestation_in_force": {"version": att.get("version"), "fingerprint": fp,
                                 "lockbox_basis": att.get("lockbox_basis"),
                                 "trial_count_basis": att.get("trial_count_basis")},
        "attestation_fingerprint": fp,
        "in_force_since": _iso(since), "in_force_basis": basis,
        "report": _public(report),
        "canon": _public(canon),
        "match": {"report": report["exact"], "canon": canon["exact"],
                  "any": report["exact"] or canon["exact"]},
        "enrolment_frozen": frozen,
        "authorized_runs": _authorized_runs(),
        "certificates_pending_rejudge": pending,
        "queueable_cells": len(by_cell),
        "not_queueable": [x for x in targets if not x.get("queue")],
        "restamped_not_rejudged": restamped,
        "oldest_pending_since": _iso(since) if pending else None,
        "oldest_pending_age_hours": (round((t - since).total_seconds() / 3600.0, 2)
                                     if pending else 0.0),
        "oldest_pending_evidence_at": _iso(oldest),
        "sealed_patch_applied": patched,
        "eta": eta(pending, rate, patched),
        "frozen_at": _iso(frozen_at),
        "first_sweep_started_after_freeze": _iso(first_start),
        "last_sweep_started_at": _iso(started), "last_sweep_completed_at": _iso(completed),
        "reminted_at": _iso(reminted_at),
        "frozen_hours": (round(((reminted_at or t) - frozen_at).total_seconds() / 3600.0, 2)
                         if frozen_at else 0.0),
        "breach": bool(breach_why), "breach_why": breach_why,
        "_targets": list(by_cell.values()),
        "rule": ("a certificate whose gates predate the attestation in force is re-JUDGED under "
                 "it, at the front of the next sweep, never re-stamped; enrolment may stay "
                 "frozen for at most one sweep"),
    }


def apply(doc: dict[str, Any], now: datetime | None = None, docket: Path | None = None,
          priority: Path | None = None) -> dict[str, Any]:
    """Write the priority record and append the missing re-judge cells to the docket."""
    t = _now(now)
    docket, priority = docket or DOCKET, priority or PRIORITY
    att, _ = _policy()
    fp = doc["attestation_fingerprint"]
    targets = doc.get("_targets") or []
    _atomic_json(priority, {
        "at": doc["at"], "producer": "research/attestation_remint.py",
        "attestation": att, "attestation_fingerprint": fp,
        "in_force_since": doc["in_force_since"],
        "cells": sorted(x["cell_id"] for x in targets),
        "certificate_keys": {x["key"]: x["cell_id"] for x in targets},
        "stale_certificate_keys": sorted(
            set(doc.get("restamped_not_rejudged") or [])
            | {x["key"] for x in targets}),
        "rule": ("the judge puts these cells first, exempts them from the novelty screen and the "
                 "yield trim, and re-mints the report honestly -- only while `attestation` equals "
                 "its own gate_policy.ATTESTATION"),
    })
    if not targets:
        return {"queued": 0, "already_on_docket": 0, "priority": str(priority)}
    present = docket_tags(docket) if docket.exists() else set()
    if present is None:
        return {"queued": 0, "refused": "docket unreadable; UNMEASURED, retried next pass",
                "priority": str(priority)}
    version = str(att.get("version") or "")
    missing = [x for x in targets if f"{fp}:{x['cell_id']}" not in present]
    res = append_to_docket(docket, [docket_row(x, fp, version, t) for x in missing])
    return {"queued": int(res.get("appended") or 0),
            "already_on_docket": len(targets) - len(missing),
            **({"refused": res["refused"]} if res.get("refused") else {}),
            "priority": str(priority)}


def run(apply_changes: bool, now: datetime | None = None) -> dict[str, Any]:
    doc = build(now)
    if apply_changes:
        doc["applied"] = apply(doc, now)
    out = {k: v for k, v in doc.items() if not k.startswith("_")}
    out["queued_cells"] = [{k: x[k] for k in ("key", "symbol", "family", "cell_id",
                                              "identity_matches_certificate")}
                           for x in doc.get("_targets") or []]
    _atomic_json(STATUS, out)
    return out


def check(path: Path | None = None) -> int:
    doc = _read(path or STATUS)
    if not isinstance(doc, dict):
        print(f"remint: {STATUS.name} absent -- UNMEASURED, not clean")
        return 1
    if doc.get("breach"):
        for why in doc.get("breach_why") or []:
            print(f"REMINT BREACH: {why}")
        return 1
    print(f"remint: frozen={doc.get('enrolment_frozen')} pending="
          f"{doc.get('certificates_pending_rejudge')} eta={doc.get('eta', {}).get('hours')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the priority record and append missing re-judge cells")
    ap.add_argument("--check", action="store_true", help="exit 1 on a recorded breach; no writes")
    a = ap.parse_args(argv)
    if a.check:
        return check()
    doc = run(a.apply)
    print(f"remint: attestation {doc['attestation_in_force']['version']} "
          f"({doc['attestation_fingerprint']}) in force since {doc['in_force_since']}; "
          f"report match={doc['match']['report']} canon match={doc['match']['canon']}; "
          f"frozen={doc['enrolment_frozen']}; pending={doc['certificates_pending_rejudge']} "
          f"({doc['queueable_cells']} queueable cells); patch applied="
          f"{doc['sealed_patch_applied']}; eta={doc['eta'].get('status')} "
          f"{doc['eta'].get('hours')}h; applied={doc.get('applied')}")
    for why in doc["breach_why"]:
        print(f"  BREACH: {why}")
    print(f"-> {STATUS}")
    return EXIT_BREACH if doc["breach"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
