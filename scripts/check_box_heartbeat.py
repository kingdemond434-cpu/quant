#!/usr/bin/env python3
"""FENCE: is the trading box's outside alarm armed, and is its reading fresh? Read OFF the box.

`desks/mt5/scripts/box_heartbeat.py` (MT5-BoxHeartbeat, every 5 minutes) pings an external
dead-man and writes `desks/mt5/reports/BOX_HEARTBEAT.json`, which the box publisher carries to
origin. Until this reader existed nothing off the box looked at it, so "nobody will be paged if
the box dies" was a line in a file nobody read.

VERDICTS, from the report as it sits at a git ref (default: the live branch's remote-tracking
ref, else HEAD) or at a path given with --file:

    UNMEASURED  the report is absent, unparseable, or carries no readable `at`
    STALE       `at` is older than MAX_AGE_MIN: the heartbeat or its publication has stopped,
                and whatever it last said about arming is no longer evidence
    NOT_ARMED   fresh, but the ping did not go out (`ping.status` NOT_ARMED, ERROR or DRY_RUN)
    ARMED       fresh AND `ping.status == "SENT"`: the only reading under which a dead box
                pages someone

Exit 0 only on ARMED. Every other verdict exits 1 -- absence is not health (L1.28a).

THE AGE LINE IS 40 MINUTES, derived rather than tuned: the heartbeat writes every 5 minutes
and the publisher (MT5-ShadowSync) copies it off the box every 15, so a healthy copy at origin is
at most about 20 minutes old plus the push itself. 40 minutes is two missed publications.

A STATE FENCE, NOT A COMMIT GATE: it is read by the hourly stale sweep and never by
`--laws-only`, because arming the alarm needs a secret only the principal can place on the box
and a push must never wait on that.

    python scripts/check_box_heartbeat.py [--json] [--ref REF | --file PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_REL = "desks/mt5/reports/BOX_HEARTBEAT.json"
LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
HEARTBEAT_PERIOD_MIN = 5
PUBLISH_PERIOD_MIN = 15
MAX_AGE_MIN = 2 * PUBLISH_PERIOD_MIN + 2 * HEARTBEAT_PERIOD_MIN     # 40


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return r.returncode, r.stdout


def resolve_ref(root: Path, ref: str | None) -> str | None:
    for cand in ([ref] if ref else [f"refs/remotes/origin/{LIVE_BRANCH}", "HEAD"]):
        if _git(root, "rev-parse", "--verify", "-q", f"{cand}^{{commit}}")[0] == 0:
            return cand
    return None


def judge(text: str | None, now: datetime, max_age_min: float = MAX_AGE_MIN) -> dict[str, Any]:
    """The verdict on one copy of the report. Pure, so every branch is testable."""
    if text is None:
        return {"verdict": "UNMEASURED", "why": f"{REPORT_REL} is absent"}
    try:
        doc = json.loads(text)
        at = datetime.fromisoformat(str(doc["at"]))
    except (ValueError, KeyError, TypeError) as exc:
        return {"verdict": "UNMEASURED",
                "why": f"{REPORT_REL} is unreadable ({type(exc).__name__})"}
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = (now - at).total_seconds() / 60.0
    ping = (doc.get("ping") or {}).get("status") if isinstance(doc.get("ping"), dict) else None
    out: dict[str, Any] = {"at": at.isoformat(), "age_min": round(age, 1), "ping": ping,
                           "box_verdict": doc.get("verdict"), "failing": doc.get("failing")}
    if not age <= max_age_min:
        out.update(verdict="STALE", why=(f"the heartbeat reading is {age:.0f} min old (line "
                                         f"{max_age_min:.0f}); its arming claim is not evidence"))
    elif ping == "SENT":
        out.update(verdict="ARMED", why="fresh, and the outside ping went out")
    else:
        out.update(verdict="NOT_ARMED",
                   why=(f"fresh, but ping status is {ping or 'absent'}: nothing outside the box "
                        "will notice if it dies (create data/secrets/box_heartbeat_url.json "
                        "on the box)"))
    return out


def measure(root: Path = ROOT, *, ref: str | None = None, file: Path | None = None,
            now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if file is not None:
        try:
            text: str | None = file.read_text("utf-8")
        except OSError:
            text = None
        src = str(file)
    else:
        use = resolve_ref(root, ref)
        if use is None:
            return {"verdict": "UNMEASURED", "why": "no git ref to read the report at",
                    "source": None, "measured_at": now.isoformat(timespec="seconds")}
        rc, body = _git(root, "show", f"{use}:{REPORT_REL}")
        text = body if rc == 0 else None
        src = f"{use}:{REPORT_REL}"
    return {**judge(text, now), "source": src, "measured_at": now.isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ref")
    g.add_argument("--file", type=Path)
    a = ap.parse_args(argv)
    doc = measure(ref=a.ref, file=a.file)
    print(json.dumps(doc, indent=1) if a.json else f"box heartbeat: {doc['verdict']} -- {doc['why']}")
    return 0 if doc["verdict"] == "ARMED" else 1


if __name__ == "__main__":
    sys.exit(main())
