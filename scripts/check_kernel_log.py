#!/usr/bin/env python3
"""KERNEL-LOG READABILITY FENCE (R0350, L1.40 class) -- can this box's kernel log be read AT ALL?

WHY THIS FENCE EXISTS. Every kill/OOM diagnosis on this desk starts from the kernel log, and the
kernel log's READABILITY silently reverts across environment drift: on 2026-08-01 `dmesg -T`
returned "read kernel buffer failed: Operation not permitted" and `journalctl -k` returned "No
entries"; on 2026-08-04's replacement box `dmesg -T` works as root while `journalctl -k` says "No
journal files were found". Same repo, same organs, three different answers in four days -- and the
trap already fired once (R0350): an OOM check ran, matched nothing, and was one step from recording
"not an OOM kill" as a finding on a box where NO kernel event of any kind was visible. That is an
UNMEASURABLE reported as a NEGATIVE RESULT -- the unmeasured-reported-as-OK class (L1.40) applied
to the desk's own diagnostics.

WHAT IT MEASURES: for each kernel-log channel (the dmesg ring buffer; the systemd journal via
`journalctl -k`), can THIS user on THIS box actually read kernel lines right now? Three failure
shapes, all recorded as unreadable with their cause, never as an exception:
  - the probe cannot execute (binary absent, PermissionError, timeout);
  - the probe exits nonzero (the classic "Operation not permitted" denial);
  - the probe exits 0 with ZERO log lines ("No journal files were found", "No entries", or a
    silently empty ring) -- an empty successful read proves nothing, and treating it as readable
    would rebuild the exact L1.40 defect this fence exists to stop.

VERDICT (a gate, not a report):
  READABLE     at least one channel yields real kernel lines -- a "no OOM" conclusion drawn on
               this box today can mean something.
  UNREADABLE   no channel is readable. Exit 2 and PAGE: every "no kernel event" conclusion is
               VOID until readability is restored, and any organ diagnosing a killed process must
               report UNDETERMINED rather than clean.

THE ONE THING THIS FENCE MAY NEVER DO is report READABLE because a probe merely ran. Readability
is proven by lines seen, not by a zero exit code.

CRON WIRING (intended cadence -- daily). The ops/crontab.manifest line is owned by the manifest
owner and will be added by the orchestrator, NOT by this script; do not self-install. Intended:
    15 5 * * * .venv/bin/python scripts/check_kernel_log.py

    python scripts/check_kernel_log.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data/kernel_log_status.json"

#: Kernel-log channels, probed in order. dmesg is primary (the only channel readable on the
#: 2026-08-04 box); journalctl -k is secondary (`-q` drops decoration, `-n 50` bounds output).
_CHANNELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dmesg", ("dmesg",)),
    ("journalctl-k", ("journalctl", "-k", "--no-pager", "-q", "-n", "50")),
)
#: A kernel-log read is local and near-instant; a probe that hangs this long is not readable.
_TIMEOUT_S = 10.0
#: Phrases that mean "the command succeeded but there is no journal behind it" -- rc 0, zero
#: information. Seen verbatim on 2026-08-01 ("No entries") and 2026-08-04 ("No journal files").
_EMPTY_MARKERS = ("no journal files were found", "no entries")


def _probe(cmd: tuple[str, ...]) -> tuple[int | None, str, str]:
    """(returncode, stdout, note). Every way the probe can fail to EXECUTE is caught and returned
    as data -- a fence that crashes on the denial it exists to detect measures nothing."""
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True,
                           timeout=_TIMEOUT_S, check=False)
    except FileNotFoundError:
        return None, "", f"{cmd[0]}: binary not found on this box"
    except PermissionError as exc:
        return None, "", f"{cmd[0]}: permission denied executing probe ({exc})"
    except subprocess.TimeoutExpired:
        return None, "", f"{cmd[0]}: no answer within {_TIMEOUT_S:.0f}s"
    except OSError as exc:
        return None, "", f"{cmd[0]}: {exc}"
    return r.returncode, r.stdout, r.stderr.strip()


def _probe_channel(name: str, cmd: tuple[str, ...], now: datetime) -> dict[str, Any]:
    """One channel's verdict. `readable` is True only when real kernel lines came back."""
    rc, out, note = _probe(cmd)
    # journalctl prints "-- No entries --" style chrome to stdout; a chrome line is not a log line.
    lines = [ln for ln in out.splitlines() if ln.strip() and not ln.lstrip().startswith("--")]
    blob = f"{out}\n{note}".lower()
    empty_marker = any(m in blob for m in _EMPTY_MARKERS)
    readable = rc is not None and rc == 0 and len(lines) > 0 and not empty_marker
    if not readable and note == "":
        if rc is None:
            note = "probe did not execute"
        elif rc != 0:
            note = f"exit {rc} -- channel denied"
        elif empty_marker:
            note = "exit 0 but the channel reports no journal/entries behind it"
        else:
            note = "exit 0 but zero kernel lines -- an empty read proves nothing (L1.40)"
    return {
        "channel": name,
        "command": " ".join(cmd),
        "probed_at": now.isoformat(),
        "returncode": rc,
        "lines_seen": len(lines),
        "readable": readable,
        "note": note if not readable else "",
    }


def build_report(now: datetime | None = None) -> dict[str, Any]:
    """Pure apart from the probes themselves: no writes. Tests call this directly."""
    now = now if now is not None else datetime.now(tz=UTC)
    channels = [_probe_channel(name, cmd, now) for name, cmd in _CHANNELS]
    readable = sorted(c["channel"] for c in channels if c["readable"])
    verdict = "READABLE" if readable else "UNREADABLE"
    if readable:
        detail = (f"kernel log readable via {', '.join(readable)} -- a 'no OOM / no kernel "
                  f"event' conclusion on this box can mean something today")
    else:
        detail = ("NO kernel-log channel is readable -- every 'no OOM / no kernel event' "
                  "conclusion on this box is VOID until this is restored (R0350)")
    return {
        "generated": now.isoformat(),
        "law": ("R0350 / L1.40 -- a kernel-log negative ('no OOM') is only a measurement if the "
                "reader first proved they could see a kernel event at all; UNMEASURED must never "
                "read as OK"),
        "verdict": verdict,
        "detail": detail,
        "readable_channels": readable,
        "channels": channels,
        "next_action": (
            "Nothing -- but organs diagnosing kills must read THIS artifact first, not assume"
            if verdict == "READABLE" else
            "Restore readability for the desk user (root reads the ring directly; a non-root "
            "user needs `usermod -aG adm,systemd-journal <user>` + re-login, per R0350). Until "
            "then every kill diagnosis must report UNDETERMINED rather than clean"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="always exit 0 (record the state without failing a cron)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"kernel log (R0350): {rep['verdict']} -- {rep['detail']}")
        for ch in rep["channels"]:
            state = "readable" if ch["readable"] else f"UNREADABLE ({ch['note']})"
            print(f"    {ch['channel']:13s} rc={ch['returncode']} "
                  f"lines={ch['lines_seen']:4d} {state}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    if rep["verdict"] == "READABLE":
        return 0
    # The fence firing, not an error: the measurement instrument itself is gone.
    print("PAGE kernel-log fence (R0350): UNREADABLE on this box -- kill/OOM diagnostics are "
          "flying blind; every 'no kernel event' finding is void until a channel is restored")
    return 2


if __name__ == "__main__":
    sys.exit(main())
