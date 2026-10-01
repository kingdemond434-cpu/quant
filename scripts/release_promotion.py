#!/usr/bin/env python3
"""Release promotion and the box's release gate. See `libs.ops.release_promotion`.

    # CI (ci.yml): suite counts for a job output, then the promotion itself
    python scripts/release_promotion.py counts --junit quality-junit.xml --law-log law_gate.txt
    python scripts/release_promotion.py promote --target <sha> --tested <sha> --run-id <id> ...

    # the trading box (Adopt-And-Seal.ps1): which commit may this box adopt?
    python scripts/release_promotion.py gate --branch claude/llm-auto-upgrade-verify-gcjac3

`counts` prints `key=value` lines ready to append to $GITHUB_OUTPUT. `promote` and `gate` print
one JSON object. `gate` exits 0 with a decision (ADOPT_TIP, ADOPT_RELEASE, HOLD, LEGACY_TIP,
OVERRIDE_TIP) and 3 when it could not decide -- the adopter then falls back to today's behaviour
and says so, because a gate that cannot run must never strand the box.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: The box's last gate decision, rewritten on every `gate` run (Adopt-And-Seal, hourly): which
#: commit it chose, why, and what code it held back. The heartbeat carries the same decision;
#: this file carries it for a reader that does not know the heartbeat exists.
REPORT = ROOT / "desks" / "mt5" / "reports" / "RELEASE_GATE.json"

from libs.ops import release_promotion as rp  # noqa: E402


def _counts(a: argparse.Namespace) -> int:
    out: list[str] = []
    if a.junit:
        try:
            c = rp.junit_counts(Path(a.junit))
            out.append(f"suite={rp.summarize_counts(c)}")
        except (OSError, ValueError) as exc:
            out.append(f"suite=UNMEASURED ({type(exc).__name__}: {exc})")
    if a.law_log:
        try:
            text = Path(a.law_log).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            text = f"(law gate log unreadable: {exc})"
        out.append(f"law_gate={rp.law_gate_line(text)}")
    print("\n".join(line.replace("\n", " ") for line in out))
    return 0


def _promote(a: argparse.Namespace) -> int:
    ev = rp.Evidence(tested_sha=a.tested, run_id=a.run_id, run_attempt=a.run_attempt,
                     run_url=a.run_url, law_gate=a.law_gate, quality_suite=a.quality_suite,
                     mt5_suite=a.mt5_suite)
    try:
        res = rp.promote(Path(a.root), a.target, ev, remote=a.remote, live_branch=a.branch,
                         dry_run=a.dry_run)
    except (rp.GitError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        print(f"::error::release promotion refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **res.as_dict()}, indent=1))
    return 0


def _write_report(root: Path, doc: dict[str, object]) -> None:
    """Best-effort: an unwritable report is a lost diagnostic, never a failed adoption."""
    out = root / REPORT.relative_to(ROOT)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"measured_at": datetime.now(UTC).isoformat(), **doc},
                                  indent=1, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def _gate(a: argparse.Namespace) -> int:
    root = Path(a.root)
    try:
        d = rp.gate(root, branch=a.branch, remote=a.remote,
                    allow_unreleased=a.allow_unreleased, fetch=not a.no_fetch)
    except Exception as exc:  # any failure means "fall back", never "stuck"
        doc: dict[str, object] = {"decision": "ERROR", "target": None, "adopts": False,
                                  "reason": f"release gate could not decide: "
                                            f"{type(exc).__name__}: {exc}"}
        _write_report(root, doc)
        print(json.dumps(doc))
        return 3
    _write_report(root, d.as_dict())
    print(json.dumps(d.as_dict(), sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("counts", help="suite counts / law-gate verdict as GITHUB_OUTPUT lines")
    c.add_argument("--junit", default=None)
    c.add_argument("--law-log", default=None)
    c.set_defaults(fn=_counts)

    p = sub.add_parser("promote", help="tag, fast-forward production, tree-take master")
    p.add_argument("--target", required=True, help="the commit to release (seal commit or tested)")
    p.add_argument("--tested", required=True, help="the commit the suites ran on")
    p.add_argument("--run-id", default="")
    p.add_argument("--run-attempt", default="")
    p.add_argument("--run-url", default="")
    p.add_argument("--law-gate", default="")
    p.add_argument("--quality-suite", default="")
    p.add_argument("--mt5-suite", default="")
    p.add_argument("--branch", default=rp.LIVE_BRANCH)
    p.add_argument("--remote", default="origin")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=_promote)

    g = sub.add_parser("gate", help="which commit may the box adopt (JSON)")
    g.add_argument("--branch", default=rp.LIVE_BRANCH)
    g.add_argument("--remote", default="origin")
    g.add_argument("--root", default=str(ROOT))
    g.add_argument("--allow-unreleased", action="store_true")
    g.add_argument("--no-fetch", action="store_true")
    g.set_defaults(fn=_gate)

    a = ap.parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
