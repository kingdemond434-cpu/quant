"""WEEKLY FIRE DRILLS: prove every watchdog still PAGES when its condition happens.

    python scripts/watchdog_drill.py [--force] [--no-canary] [--print]

Writes desks/mt5/reports/WATCHDOG_DRILL.json (published by `publish_state`); rc 2 when any drill
fails. Runs as the core hourly leg `watchdog_drill`, which returns at once unless a week has
passed since the last full drill (or --force).

WHY (Hourly pass idea 592, 2026-11-11). Tonight the box ran out of disk (1.9 GB free) and a money
task went dark, and nothing paged. A watchdog is only ever exercised by a real incident, so one
that has quietly stopped paging -- a refactor that broke its trigger, a dedup state that swallows
the new failure, a pager with no channel armed -- looks exactly like a quiet desk until the night
it matters. A drill makes the incident happen on purpose, in a sandbox, every week.

EACH DRILL runs the watchdog's OWN code (never a copy of its rule) against a synthetic failing
reading, in a temporary directory, with its sender replaced by a recorder, and passes only when
the watchdog decided to page and the page names the condition. Nothing on the box is touched: no
real report, state file or dedup record is read or written by a drill.

THE CHANNEL DRILL is the one real send: a CANARY through libs.ops.alert_channels.send_all
(canary=True: channels with a silent probe use it, so a drill does not wake anybody). It fails
when no channel is armed or none delivered -- a watchdog that decides to page into an unarmed
pager has paged nobody. That drill reports channel KINDS and counts only, never a credential.

THE BOX'S OWN LAST WORD is carried beside the drills: the heartbeat's latest verdict, what it
failed on, and whether its last page reached a channel, so "it would page" and "it did page" sit
on one row.

A FAILED DRILL PAGES (through the same send_all) with the watchdog's name and what it did
instead, ONCE: it is re-drilled every pass until it passes, but pages again only when another
drill joins the failing set. The report names the channels with no silent probe, on which the
weekly canary is visible.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "desks" / "mt5" / "reports" / "WATCHDOG_DRILL.json"
STATE = ROOT / "desks" / "mt5" / "data" / "watchdog_drill_state.json"
HEARTBEAT = ROOT / "desks" / "mt5" / "reports" / "BOX_HEARTBEAT.json"
EVERY = timedelta(days=7)
CANARY = "alert_channels:canary"

Pages = list[tuple[str, str]]


def _load(rel: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    if spec is None or spec.loader is None:
        raise ImportError(rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def _recording_send_all(pages: Pages) -> Iterator[None]:
    """Replace libs.ops.alert_channels.send_all with a recorder for the duration of a drill."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from libs.ops import alert_channels

    real = alert_channels.send_all

    def rec(title: str, body: str, **_kw: Any) -> dict[str, Any]:
        pages.append((title, body))
        return {"armed": 1, "delivered": 1, "results": [{"channel": "drill", "ok": True}]}

    alert_channels.send_all = rec  # type: ignore[assignment]
    try:
        yield
    finally:
        alert_channels.send_all = real  # type: ignore[assignment]


# ----------------------------------------------------------------------------- the drills


def drill_heartbeat_disk(tmp: Path) -> tuple[bool, str]:
    """The box heartbeat must page when free disk drops below its floor."""
    hb = _load("desks/mt5/scripts/box_heartbeat.py", "_drill_box_heartbeat")
    low = max(0.0, float(hb.DISK_MIN_GB) - 3.1)
    reading = hb.measure(time.time(), research={"age_days": 0.0}, disk_free_gb=low)
    if "disk" not in reading["failing"]:
        return False, f"measure() did not fail `disk` at {low:.1f} GB free (floor {hb.DISK_MIN_GB})"
    pages: Pages = []
    with _recording_send_all(pages):
        doc = hb.run(reading=reading, out=tmp / "BOX_HEARTBEAT.json", secrets=())
    if not pages:
        return False, f"run() decided not to page (paged={doc.get('paged')})"
    if "disk" not in pages[0][1]:
        return False, f"it paged but the page does not name disk: {pages[0][0]!r}"
    return True, f"paged {pages[0][0]!r} at {low:.1f} GB free"


def drill_heartbeat_new_failure(tmp: Path) -> tuple[bool, str]:
    """A box ALREADY failing one check must still page when disk joins it (audit R2 shape)."""
    hb = _load("desks/mt5/scripts/box_heartbeat.py", "_drill_box_heartbeat2")
    out = tmp / "BOX_HEARTBEAT.json"
    out.write_text(json.dumps({"verdict": "FAIL", "failing": ["research"], "checks": {}}), "utf-8")
    reading = hb.measure(time.time(), research={"age_days": 99.0}, disk_free_gb=0.5)
    pages: Pages = []
    with _recording_send_all(pages):
        hb.run(reading=reading, out=out, secrets=())
    if not pages:
        return False, "a box already failing `research` did not page when `disk` joined it"
    return True, "paged when disk joined an already-failing box"


def drill_judge_stall(tmp: Path) -> tuple[bool, str]:
    """The judge stall pager must page a newly opened incident."""
    js = _load("desks/mt5/scripts/judge_stall_pager.py", "_drill_judge_stall")
    pages: Pages = []

    def sender(title: str, body: str) -> dict[str, Any]:
        pages.append((title, body))
        return {"armed": 1, "delivered": 1}

    reading = {"at": datetime.now(UTC).isoformat(),
               "incidents": {"resident_dead": {"open": True, "why": "watchdog drill"}}}  # fmt: skip
    out = js.page(reading, root=tmp, sender=sender)
    if not pages:
        return False, f"page() did not send for an opened incident ({out})"
    if "resident_dead" not in pages[0][0]:
        return False, f"it paged but not for the incident: {pages[0][0]!r}"
    return True, f"paged {pages[0][0]!r}"


def drill_merge_flow(tmp: Path) -> tuple[bool, str] | None:
    """The release-train SLO must page a silent merge sweep (skipped until it exists on LIVE)."""
    if not (ROOT / "scripts/merge_flow.py").exists():
        return None
    mf = _load("scripts/merge_flow.py", "_drill_merge_flow")
    now = datetime.now(UTC)
    doc = mf.assess(now, [{"number": 1, "head": {"sha": "a"}}],
                    {1: {"pr": 1, "sha": "a", "verdict": "CLEAR", "at": now.isoformat()}},
                    None, {1: None}, (True, "drill"))  # fmt: skip
    due = mf.page(doc, {}, now)
    if due is None:
        return False, f"page() stayed quiet on {doc['reasons']}"
    return True, f"would page {due[0]!r}"


#: name -> drill. A drill returning None is SKIPPED (its watchdog is not on this tree yet).
DRILLS: dict[str, Callable[[Path], tuple[bool, str] | None]] = {
    "box_heartbeat:disk": drill_heartbeat_disk,
    "box_heartbeat:new_failure": drill_heartbeat_new_failure,
    "judge_stall_pager:opened": drill_judge_stall,
    "merge_flow:gate_silent": drill_merge_flow,
}

#: Watchdogs this file cannot drill yet, named so the gap is on the report instead of absent.
NOT_DRILLED = {
    "stall_watch.ps1": "PowerShell; its paging leg needs a Windows drill harness",
    "money_task_pager": "pages CPU starvation by its symptom (a money task killed twice at its "
    "time limit) once #930 lands; its drill is added when it is on LIVE",
}


def run_drills(drills: dict[str, Callable[[Path], tuple[bool, str] | None]]) -> list[dict]:
    rows = []
    for name, fn in drills.items():
        with tempfile.TemporaryDirectory(prefix="drill-") as d:
            try:
                got = fn(Path(d))
            except Exception as exc:  # a drill that crashes is a watchdog that would crash
                got = (False, f"crashed: {type(exc).__name__}: {str(exc)[:160]}")
        if got is None:
            rows.append({"drill": name, "result": "SKIPPED", "detail": "not on this tree"})
        else:
            rows.append({"drill": name, "result": "PASS" if got[0] else "FAIL",
                         "detail": got[1]})  # fmt: skip
    return rows


def channel_drill(
    send: Callable[..., dict[str, Any]] | None = None, silent: frozenset[str] | None = None
) -> dict[str, Any]:
    """One real canary through every armed channel. Kinds and counts only."""
    try:
        if send is None:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from libs.ops.alert_channels import send_all as send
        if silent is None:
            try:
                from libs.ops.alert_channels import _CANARY_AWARE as silent
            except ImportError:
                silent = frozenset()
        res = send("Watchdog drill canary", "weekly proof the pager path delivers", canary=True)
    except Exception as exc:
        return {"drill": "alert_channels:canary", "result": "FAIL",
                "detail": f"send_all raised {type(exc).__name__}"}  # fmt: skip
    armed, delivered = int(res.get("armed") or 0), int(res.get("delivered") or 0)
    kinds = sorted({str(r.get("channel")) for r in res.get("results") or [] if r.get("ok")})
    # S1: a channel with no silent probe shows the canary to whoever reads it, once a week.
    loud = sorted({str(r.get("channel")) for r in res.get("results") or []} - set(silent or ()))
    if armed == 0:
        ok, why = False, "NO CHANNEL ARMED: every watchdog's page goes nowhere"
    elif delivered == 0:
        ok, why = False, f"{armed} channel(s) armed, none delivered"
    else:
        ok, why = True, f"{delivered}/{armed} channel(s) delivered ({', '.join(kinds)})"
    return {"drill": "alert_channels:canary", "result": "PASS" if ok else "FAIL", "detail": why,
            "armed": armed, "delivered": delivered,
            "canary_visible_on": loud}  # fmt: skip


def box_last_word(path: Path = HEARTBEAT) -> dict[str, Any]:
    """The heartbeat's own latest verdict and page outcome, as it wrote them."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"heartbeat": "UNREADABLE"}
    paged = doc.get("paged")
    return {"heartbeat": doc.get("verdict"), "at": doc.get("at"), "since": doc.get("since"),
            "failing": doc.get("failing"),
            "disk_free_gb": ((doc.get("checks") or {}).get("disk") or {}).get("free_gb"),
            "ping": (doc.get("ping") or {}).get("status"),
            "last_page": ({k: paged.get(k) for k in ("armed", "delivered", "status")}
                          if isinstance(paged, dict) else paged)}  # fmt: skip


def weekly_due(state: dict[str, Any], now: datetime) -> bool:
    try:
        last = datetime.fromisoformat(str(state["last_full"]))
    except (KeyError, ValueError):
        return True
    return now - last >= EVERY


def due(state: dict[str, Any], now: datetime) -> bool:
    """A failing drill re-runs every pass until it passes (it PAGES only when the failing set
    gains a drill: see `newly_failed`); otherwise once a week."""
    return bool(state.get("failed")) or weekly_due(state, now)


def newly_failed(failed: list[str], state: dict[str, Any]) -> list[str]:
    """The drills failing now that were not failing last run. Only these page (Auditor M1 on
    #947): one broken watchdog pages once, not every hour until someone fixes it, and a second
    one breaking pages again. The same rule as box_heartbeat's `newly`."""
    before = set(state.get("failed") or [])
    return [d for d in failed if d not in before]


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="drill now, whatever the schedule")
    ap.add_argument("--no-canary", action="store_true", help="skip the one real channel send")
    ap.add_argument("--print", action="store_true", help="stdout only: no report, state or page")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    state = _read(STATE)
    if not (a.force or a.print or due(state, now)):
        print(f"watchdog_drill: not due (last full drill {state.get('last_full')})")
        return 0
    rows = run_drills(DRILLS)
    # The canary is weekly. On an hourly re-drill it is re-sent only if IT is what failed, so a
    # broken heartbeat drill never turns into an hourly canary on every channel.
    canary_due = a.force or weekly_due(state, now) or CANARY in (state.get("failed") or [])
    if not a.no_canary and not a.print and canary_due:
        rows.append(channel_drill())
    elif CANARY in (state.get("failed") or []):
        rows.append({"drill": CANARY, "result": "FAIL", "detail": "not re-sent this pass"})
    failed = [r["drill"] for r in rows if r["result"] == "FAIL"]
    doc = {"schema": "watchdog_drill/1", "at": now.isoformat(),
           "verdict": "FAIL" if failed else "PASS", "failed": failed, "drills": rows,
           "not_drilled": NOT_DRILLED, "box_last_word": box_last_word(),
           "every_days": EVERY.days}  # fmt: skip
    if a.print:
        print(json.dumps(doc, indent=1))
        return 2 if failed else 0
    fresh = newly_failed(failed, state)
    doc["newly_failed"] = fresh
    if fresh:
        body = "; ".join(f"{r['drill']}: {r['detail']}" for r in rows if r["result"] == "FAIL")
        try:
            from libs.ops.alert_channels import send_all

            res = send_all(f"Watchdog drill FAILED: {', '.join(fresh)}", body[:3000])
            doc["paged"] = {"armed": res.get("armed"), "delivered": res.get("delivered")}
        except Exception as exc:  # the report below is the second voice
            doc["paged"] = f"not sent ({type(exc).__name__})"
    _write(REPORT, doc)
    last_full = now.isoformat() if canary_due else state.get("last_full", now.isoformat())
    _write(STATE, {"last_full": last_full, "failed": failed})
    print(f"watchdog_drill: {doc['verdict']} {' '.join(failed)}".rstrip())
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
