#!/usr/bin/env python3
"""LOCKBOX v4 RE-CERTIFICATION LEDGER: every canon certificate, its lockbox Sharpe BEFORE and AFTER.

    python desks/mt5/research/lockbox_recert.py            # write reports/LOCKBOX_RECERT.json
    python desks/mt5/research/lockbox_recert.py --check    # exit 1 unless the re-mint is DONE

WHY (pass-2 PRIORITY 0, 2026-09-30). All 52 canonical certificates were judged under
`...-v2-calibrated-inputs`, where the lockbox gate read the walk-forward OOS series: on every one
of them, as committed, `gates.lockbox.lockbox_sharpe == gates.walk_forward.oos_sharpe`. No
certificate had ever been held out. Lockbox v4 (`gate_policy.ATTESTATION`,
`...-v3-reserved-lockbox`) carves a reserved final calendar fraction BEFORE the program matrix.
The re-mint itself is the `attestation_remint` leg (PR #126) plus the sealed patch
`/mnt/project-files/patches/v4_remint/v4_remint.patch`: it queues the 52 at the front of the
sweep and re-mints the report honestly (pass stays, fail retires with its v4 gates, unreached
waits in `pending_rejudge`). Neither half records what the lockbox Sharpe WAS and what it IS, so
"0 of 52 still show lockbox == WF" was not measurable anywhere. This is that measurement.

WHAT IT DOES. For each certificate in the baseline, it finds where the certificate stands now:

  REMINTED   a row under the attestation in force, gated AFTER the baseline row (re-judged), in
             the canon or the report -- directly, or through `reattestation.superseded`
  RETIRED    in `retired_certificates` (a v4 failure carries its old gates as `gates_superseded`)
  PENDING    in `pending_rejudge`, or still under a stale header: not yet reached by a sweep
  RESTAMPED  under the header in force but with the baseline's own `gated_at`: the re-stamp the
             re-mint exists to prevent. A breach, never a pass
  ABSENT     in none of the above

and records both Sharpes before and after. DONE is: every certificate REMINTED or RETIRED, none
RESTAMPED, and no REMINTED row with lockbox Sharpe equal to its WF Sharpe.

THE BASELINE IS WRITE-ONCE. `docs/research/lockbox_v4_recert_baseline.json` holds the 52 as
committed at the start (measured from git, source commit recorded). A pre-v4 canon row on the box
that the seed does not name is captured into this artifact's `before` the first time it is seen
and never overwritten, so the pass is IDEMPOTENT: re-running it on the same inputs writes the same
rows, and a later pass can never rewrite what a certificate looked like before the re-mint.

READ-ONLY on every store. It mints nothing, re-judges nothing and edits no certificate, canon,
report or gate policy. Leg `lockbox_recert` in `research/hourly_cycle.py`, right after
`canon_publication`; the box's sync publishes the artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
REPORT = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
BASELINE = ROOT / "docs" / "research" / "lockbox_v4_recert_baseline.json"
OUT = DESK / "reports" / "LOCKBOX_RECERT.json"
UNMEASURED = "UNMEASURED"
STATES = ("REMINTED", "RETIRED", "PENDING", "RESTAMPED", "ABSENT")


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _num(v: Any) -> float | None:
    try:
        return None if v is None or isinstance(v, bool) else round(float(v), 4)
    except (TypeError, ValueError):
        return None


def sharpes(row: Any, gates_key: str = "gates") -> dict[str, Any]:
    """The lockbox and walk-forward OOS Sharpe a row's gates carry, and whether they are equal."""
    gates = row.get(gates_key) if isinstance(row, dict) else None
    gates = gates if isinstance(gates, dict) else {}
    lb = _num((gates.get("lockbox") or {}).get("lockbox_sharpe")
              if isinstance(gates.get("lockbox"), dict) else None)
    wf = _num((gates.get("walk_forward") or {}).get("oos_sharpe")
              if isinstance(gates.get("walk_forward"), dict) else None)
    lbp = (gates.get("lockbox") or {}).get("passed") if isinstance(gates.get("lockbox"),
                                                                   dict) else None
    return {"lockbox_sharpe": lb, "wf_sharpe": wf, "lockbox_passed": lbp,
            "lockbox_equals_wf": (lb is not None and wf is not None and lb == wf)}


def attestation_version() -> str:
    try:
        import gate_policy
        return str(gate_policy.ATTESTATION["version"])
    except Exception as exc:                     # the judge's module is the only source
        return f"{UNMEASURED}: gate_policy unreadable ({type(exc).__name__})"


def _version(doc: Any) -> str | None:
    gp = doc.get("gate_policy") if isinstance(doc, dict) else None
    return str(gp.get("version")) if isinstance(gp, dict) and gp.get("version") else None


def _block(doc: Any, key: str) -> dict[str, Any]:
    v = doc.get(key) if isinstance(doc, dict) else None
    return v if isinstance(v, dict) else {}


def baseline_row(key: str, row: dict[str, Any], version: str | None) -> dict[str, Any]:
    return {**sharpes(row), "gated_at": row.get("gated_at"), "attestation": version,
            "shadow_spec": row.get("shadow_spec")}


def locate(key: str, before: dict[str, Any], stores: list[tuple[str, Any]],
           current: str) -> dict[str, Any]:
    """Where certificate `key` stands now, and its Sharpes there."""
    b_at = _ts(before.get("gated_at"))

    def rejudged(row: dict[str, Any]) -> bool:
        a = _ts(row.get("gated_at"))
        return a is not None and (b_at is None or a > b_at)

    for name, doc in stores:                      # 1. re-judged under the header in force
        if _version(doc) != current:
            continue
        surv = _block(doc, "survivors")
        new_key = str(_block(_block(doc, "reattestation"), "superseded").get(key) or key)
        for k in dict.fromkeys((key, new_key)):
            row = surv.get(k)
            if isinstance(row, dict) and rejudged(row):
                return {"state": "REMINTED", "store": name, "key": k, **sharpes(row),
                        "gated_at": row.get("gated_at"), "attestation": current}
    for name, doc in stores:                      # 2. retired (a v4 failure keeps its old gates)
        row = _block(doc, "retired_certificates").get(key)
        if isinstance(row, dict):
            return {"state": "RETIRED", "store": name, "key": key, **sharpes(row),
                    "retired_at": row.get("retired_at"),
                    "retired_reason": str(row.get("retired_reason") or "")[:300],
                    "rejudged_under_v4": "gates_superseded" in row}
    for name, doc in stores:                      # 3. waiting for its re-judge
        if key in _block(doc, "pending_rejudge"):
            return {"state": "PENDING", "store": name, "key": key,
                    "why": "in pending_rejudge: not yet reached by a sweep under the new header"}
    for name, doc in stores:                      # 4. the re-stamp, or still under a stale header
        row = _block(doc, "survivors").get(key)
        if isinstance(row, dict):
            if _version(doc) == current:
                return {"state": "RESTAMPED", "store": name, "key": key, **sharpes(row),
                        "gated_at": row.get("gated_at"),
                        "why": "under the attestation in force with the baseline's own gated_at: "
                               "re-stamped, never re-judged"}
            return {"state": "PENDING", "store": name, "key": key,
                    "why": f"still under {_version(doc)}; the store has not been re-minted"}
    return {"state": "ABSENT", "key": key, "why": "in no survivor, retired or pending block"}


def build(*, canon: Path = CANON, report: Path = REPORT, baseline: Path = BASELINE,
          previous: Any = None, current: str | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    current = current or attestation_version()
    stores = [("canon", _read(canon)), ("report", _read(report))]
    seed = _read(baseline) or {}
    before: dict[str, dict[str, Any]] = {}
    for k, v in (seed.get("certificates") or {}).items():
        if isinstance(v, dict):
            before[str(k)] = {**v, "source": "baseline"}
    for k, v in ((previous or {}).get("certificates") or {}).items():
        if isinstance(v, dict) and isinstance(v.get("before"), dict) and k not in before:
            before[str(k)] = v["before"]
    # A pre-v4 canon row the seed does not name (the box may hold more than git): captured once.
    canon_doc = stores[0][1]
    if _version(canon_doc) not in (None, current):
        for k, row in _block(canon_doc, "survivors").items():
            if isinstance(row, dict) and k not in before:
                before[k] = {**baseline_row(k, row, _version(canon_doc)), "source": "box_canon"}
    rows: dict[str, dict[str, Any]] = {}
    for k in sorted(before):
        rows[k] = {"before": before[k], "after": locate(k, before[k], stores, current)}
    counts = {s: sum(1 for r in rows.values() if r["after"]["state"] == s) for s in STATES}
    reminted = [r for r in rows.values() if r["after"]["state"] == "REMINTED"]
    after_eq = sum(1 for r in reminted if r["after"].get("lockbox_equals_wf"))
    before_eq = sum(1 for r in rows.values() if r["before"].get("lockbox_equals_wf"))
    done = bool(rows) and counts["REMINTED"] + counts["RETIRED"] == len(rows) and after_eq == 0
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "attestation_in_force": current,
        "canon_attestation": _version(canon_doc), "report_attestation": _version(stores[1][1]),
        "baseline": {"path": str(baseline.relative_to(ROOT)) if baseline.is_relative_to(ROOT)
                     else str(baseline), "source_commit": seed.get("source_commit"),
                     "n": len(seed.get("certificates") or {})},
        "n_certificates": len(rows), "counts": counts,
        "before_lockbox_equals_wf": before_eq, "after_lockbox_equals_wf": after_eq,
        "restamped": counts["RESTAMPED"],
        "done": done,
        "done_rule": ("every certificate REMINTED or RETIRED under the attestation in force, none "
                      "RESTAMPED, and 0 REMINTED rows with lockbox Sharpe == WF Sharpe"),
        "status": ("DONE" if done else "BREACH: re-stamped without a re-judge"
                   if counts["RESTAMPED"] else "IN_PROGRESS" if rows else UNMEASURED),
        "certificates": rows,
    }


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{out.name}.", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=False, default=str)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="re-read the artifact; exit 1 unless DONE (writes nothing)")
    a = ap.parse_args(argv)
    if a.check:
        doc = _read(OUT)
        if not isinstance(doc, dict):
            print(f"lockbox_recert: {OUT.name} absent -- UNMEASURED, not done")
            return 1
        print(json.dumps({k: doc.get(k) for k in ("status", "n_certificates", "counts",
                                                  "before_lockbox_equals_wf",
                                                  "after_lockbox_equals_wf")}))
        return 0 if doc.get("done") else 1
    doc = build(previous=_read(OUT))
    write(doc)
    print(json.dumps({k: doc[k] for k in ("status", "n_certificates", "counts",
                                          "before_lockbox_equals_wf",
                                          "after_lockbox_equals_wf")}))
    print(f"  -> {OUT}")
    # A re-stamp is the one outcome the re-mint exists to prevent: fail the leg so it is seen.
    return 3 if doc["restamped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
