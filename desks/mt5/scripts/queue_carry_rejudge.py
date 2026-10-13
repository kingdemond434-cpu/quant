"""Queue every carry certificate minted on the look-ahead `family_carry` for re-judgement.

WHY (2026-10-07, EliteQuant review). Until `carry_pit`, `family_carry` applied the NEWEST recorded
swap to every past bar, so a certificate it produced was judged on years of bars carrying a swap
nobody could have known (CHFNOK carry: `days: 1120` on a swap tape that starts 2026-08-27). The
family is now point-in-time, and its old certificates must be re-judged by the ten gates under
the fixed family -- never demoted by hand, never capped.

WHAT IT WRITES, into `data/hypotheses/priority_remint.json` under the attestation in force:
  * `cells`: the certificate cells, which the judge already reads and judges FIRST;
  * `verdict_bound_keys`: the certificate keys. They are NOT `stale_certificate_keys`. A stale key
    leaves the survivor set on the first sweep, which takes the forward clock with it
    (`clock_certificate.retire_unbacked`), and a stale key retires on ANY verdict carrying
    stages -- an UNMEASURED "too short" verdict included (audit PR269 M1/M2). A verdict-bound
    key stays in the survivor set, still backing its clock, until a REAL ten-gate verdict
    lands: PASS replaces it, FAIL retires it, and anything else (not reached, PENDING_HISTORY,
    UNMEASURED) keeps it exactly as it is. The judge reads this field only with the sealed
    `carry_pit` patch. Without that patch the field is inert: the cells are judged first and no
    certificate moves on any verdict, which is the status quo and never a wrong retirement.

THE CUTOFF IS ADOPTION, NOT A DATE. A certificate is the look-ahead family's if it was gated
before this code first ran on the host. The first `--write` pass stamps that instant in
`data/hypotheses/carry_pit_adoption.json` and every later pass reads it. A certificate gated
between adoption and the first pass is re-judged needlessly, which is harmless (it is held
until its verdict); the reverse error is impossible.

Runs hourly as the `carry_rejudge` leg of hourly_cycle (`--write`); by hand on the box:

    py -3 desks\\mt5\\scripts\\queue_carry_rejudge.py           # dry run: lists the queue
    py -3 desks\\mt5\\scripts\\queue_carry_rejudge.py --write    # writes the queue

It never replaces a queue written for another attestation (that belongs to an attestation change
in flight): the report reads WAITING and the next hour tries again. It never edits a certificate,
a sleeve or a cap.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVOR_FILES = (DESK / "reports" / "UNIVERSAL_SURVIVORS.json",
                  DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json")
SLEEVES = DESK / "data" / "sleeves.json"
PRIORITY = DESK / "data" / "hypotheses" / "priority_remint.json"
#: The instant this code first ran here, stamped once and read back on every pass.
ADOPTION = DESK / "data" / "hypotheses" / "carry_pit_adoption.json"
#: What each pass found and did; its consumer is the judge, through PRIORITY.
REPORT = DESK / "reports" / "CARRY_REJUDGE.json"
_TERMINAL = ("RETIRED", "VOID", "REFUSED", "KILLED", "DEAD")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` whole or not at all: a temp file beside it, then `os.replace`.

    WINDOWS-SAFE BY REFUSAL, NOT BY FORCE. On Windows `os.replace` onto a read-only destination
    raises PermissionError (WinError 5); a read-only bit there was set by someone on purpose, so
    it is never cleared here. The temp file is removed, the destination is left untouched, and
    the error propagates for the caller to report. A half-written queue is never possible.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".carry_pit.tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def adoption_cutoff(path: Path = ADOPTION, *, stamp: bool = False) -> str | None:
    """The adoption instant: read, or (with `stamp`) written once on the first pass."""
    doc = _read(path)
    at = doc.get("adopted_at") if isinstance(doc, dict) else None
    try:
        if at:
            datetime.fromisoformat(str(at))
            return str(at)
    except ValueError:
        pass                               # an unreadable stamp is re-stamped, never guessed
    if not stamp:
        return None
    at = datetime.now(UTC).isoformat(timespec="seconds")
    atomic_write(path, json.dumps({
        "adopted_at": at,
        "why": ("the first pass of the point-in-time family_carry on this host: a carry "
                "certificate gated before this instant was judged by the look-ahead family")},
        indent=1))
    return at


def _gated_before(gated: Any, cutoff: datetime) -> bool:
    try:
        return not (gated and datetime.fromisoformat(str(gated)) >= cutoff)
    except (TypeError, ValueError):
        return True                        # unreadable stamp: re-judge, never assume clean


def _reason(symbol: Any, gated: Any) -> str:
    return (f"{symbol or '?'} carry certificate gated {gated or 'at an unrecorded time'} by the "
            f"old family_carry, which applied the newest recorded swap to every past bar. "
            f"Re-judged with the swap knowable at each bar. It stays in force until a real "
            f"ten-gate verdict: PASS replaces it, FAIL retires it, anything else keeps it.")


def carry_certificates(cutoff_iso: str, files: tuple[Path, ...] = SURVIVOR_FILES,
                       sleeves: Path = SLEEVES) -> dict[str, dict[str, Any]]:
    """{certificate key: record} for every carry certificate gated before `cutoff_iso`.

    Read from both survivor files AND from every non-terminal carry sleeve, so a sleeve whose
    row names its certificate another way (`CHFNOK.carry.asia#input_symbol=CHFNOK`) still
    reaches its exact cell. A sleeve whose cell holds a certificate gated after the cutoff, or
    one already retired, is not queued."""
    cutoff = datetime.fromisoformat(cutoff_iso)
    out: dict[str, dict[str, Any]] = {}
    seen: dict[str, Any] = {}
    retired: set[str] = set()
    for f in files:
        doc = _read(f)
        if not isinstance(doc, dict):
            continue
        retired |= {str(k) for k in (doc.get("retired_certificates") or {})}
        rows = doc.get("survivors")
        if not isinstance(rows, dict):
            continue
        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
            raw = row.get("shadow_spec")
            spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
            if spec.get("family") != "carry" and ".carry.p=" not in str(key):
                continue
            gated = row.get("gated_at")
            seen[str(key)] = gated
            if not _gated_before(gated, cutoff):
                continue                    # judged by the point-in-time family already
            symbol = spec.get("symbol") or row.get("sym")
            rec = out.setdefault(str(key), {"cell": row.get("cell") or str(key)[9:],
                                            "symbol": symbol, "gated_at": gated,
                                            "source": [], "sleeves": [],
                                            "reason": _reason(symbol, gated)})
            rec["source"].append(f.name)
    doc = _read(sleeves)
    rows = doc.get("sleeves") if isinstance(doc, dict) else None
    for s in rows if isinstance(rows, list) else []:
        if not isinstance(s, dict) or s.get("family") != "carry":
            continue
        if str(s.get("status") or "").upper().startswith(_TERMINAL):
            continue
        cert = s.get("certificate")
        cell = None
        if isinstance(cert, dict) and str(cert.get("cell") or "").startswith("external."):
            cell = str(cert["cell"])[9:]
        else:
            try:
                from research.frontier_identity import cell_id
                cell = cell_id({"sym": s.get("symbol"), "family": "carry",
                                "params": s.get("params") or {}})
            except Exception:
                cell = None                 # a spec the judge cannot name is not guessed at
        if not cell:
            continue
        key = f"external.{cell}"
        if key in retired and key not in seen:
            continue                        # the judge already retired it; the promoter follows
        if key in seen and not _gated_before(seen[key], cutoff):
            continue
        gated = (cert.get("gated_at") if isinstance(cert, dict) else None) or seen.get(key)
        rec = out.setdefault(key, {"cell": cell, "symbol": s.get("symbol"), "gated_at": gated,
                                   "source": [], "sleeves": [],
                                   "reason": _reason(s.get("symbol"), gated)})
        rec["sleeves"].append(str(s.get("name")))
        if sleeves.name not in rec["source"]:
            rec["source"].append(sleeves.name)
    return out


def build_queue(certs: dict[str, dict[str, Any]], existing: Any,
                attestation: Any) -> tuple[dict[str, Any] | None, str]:
    """The queue, or (None, why) when an existing queue belongs to another attestation.

    This module OWNS `verdict_bound_keys` and its own share of `cells` (`carry_pit_cells`), and
    replaces both each pass, so a certificate that got its verdict drains out of the queue.
    Every other field, and every cell another writer put there, is kept as it was."""
    if isinstance(existing, dict) and existing and existing.get("attestation") != attestation:
        return None, ("priority_remint.json holds a queue for ANOTHER attestation; it belongs to "
                      "an attestation change in flight and is not replaced. The next hour "
                      "tries again.")
    base = dict(existing) if isinstance(existing, dict) else {}
    mine_before = {str(c) for c in (base.get("carry_pit_cells") or []) if c}
    mine = {str(r["cell"]) for r in certs.values() if r.get("cell")}
    others = {str(c) for c in (base.get("cells") or []) if c} - mine_before
    # NEVER A STALE KEY: a stale key leaves the survivor set and retires on any verdict.
    stale = [k for k in (base.get("stale_certificate_keys") or []) if k not in certs]
    reasons = base.get("reasons") if isinstance(base.get("reasons"), dict) else {}
    reasons = {k: v for k, v in reasons.items()
               if not str(k).startswith("external.") or ".carry." not in str(k) or k in certs}
    reasons.update({k: r["reason"] for k, r in certs.items()})
    base.update({"attestation": attestation, "cells": sorted(others | mine),
                 "carry_pit_cells": sorted(mine), "verdict_bound_keys": sorted(certs),
                 "reasons": reasons,
                 "carry_pit_queued_at": datetime.now(UTC).isoformat(timespec="seconds")})
    if stale or "stale_certificate_keys" in base:
        base["stale_certificate_keys"] = sorted(stale)
    return base, "ok"


def _report(certs: dict[str, dict[str, Any]], status: str, why: str, cutoff: str | None) -> None:
    try:
        atomic_write(REPORT, json.dumps({
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": status, "why": why, "adopted_at": cutoff, "n_queued": len(certs),
            "consumer": ("external_gauntlet: `cells` via remint_cells (judged first); "
                         "`verdict_bound_keys` via the sealed carry_pit patch"),
            "certificates": {k: {f: r.get(f) for f in ("cell", "symbol", "gated_at", "sleeves",
                                                       "source", "reason")}
                             for k, r in sorted(certs.items())},
        }, indent=1, default=str))
    except OSError as exc:
        print(f"report not written: {type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="write the queue and the report (stamps the adoption instant once)")
    ap.add_argument("--cutoff", default=None,
                    help="override the adoption instant (ISO 8601); never written")
    args = ap.parse_args(argv)
    from research.gate_policy import ATTESTATION

    cutoff = args.cutoff or adoption_cutoff(stamp=args.write) \
        or datetime.now(UTC).isoformat(timespec="seconds")
    certs = carry_certificates(cutoff)
    print(f"carry certificates gated before {cutoff}: {len(certs)}")
    for key, r in sorted(certs.items()):
        print(f"  {key}  sym={r['symbol']}  gated_at={r['gated_at']}  "
              f"in={','.join(r['source'])}  sleeves={','.join(r['sleeves']) or '-'}")
    doc, why = build_queue(certs, _read(PRIORITY), ATTESTATION)
    if doc is None:
        print(f"WAITING: {why}")
        if args.write:
            _report(certs, "WAITING", why, cutoff)
        return 0
    if not args.write:
        print(f"dry run: would hold {len(doc['verdict_bound_keys'])} certificate(s) until "
              f"their verdict and judge {len(doc['carry_pit_cells'])} cell(s) first -> {PRIORITY}")
        return 0
    try:
        atomic_write(PRIORITY, json.dumps(doc, indent=1, default=str))
    except OSError as exc:
        why = (f"priority_remint.json not replaced ({type(exc).__name__}: {exc}); the file "
               f"is left exactly as it was and the next hour tries again")
        print(f"WRITE_REFUSED: {why}")
        _report(certs, "WRITE_REFUSED", why, cutoff)
        return 1
    _report(certs, "QUEUED" if certs else "CLEAN",
            "written to priority_remint.json under the attestation in force" if certs else
            "no carry certificate gated before adoption remains", cutoff)
    print(f"queued -> {PRIORITY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
