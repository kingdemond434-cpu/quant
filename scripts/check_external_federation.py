"""THE FEDERATION FENCE -- the open-source research federation law, made mechanical.

LAWS.md 5h turns the desk RED when an eligible public research system has no disposition, when a
DIRECT or WRAPPED worker has no schedule, when a process lives while its watermark stalls, when
output exists with no consumer, when external candidates bypass trial accounting, when discovered
data is ingested and stranded, when the lineage from system to candidate to gauntlet breaks, when
an upstream agent keeps its own survivor authority, when third-party code touches credentials or
live authority, when a named seed is declared integrated with no observed output, when a source
list is treated as exhaustive, or when a delta scan goes stale.

TWO MODES, AND THE DIFFERENCE IS THE ONLY REASON THIS FENCE WILL STILL BE ON IN A MONTH. In the
portable mode (CI, the pre-push hook, a fresh clone) the desk's live state does not exist and its
absence is NOT a breach: the fence reports UNMEASURED and exits 0. With `--require-state` -- the
box, where the organ runs hourly -- a missing artifact IS the defect, because there the organ
either ran or did not.

RATCHETS, NEVER ABSOLUTES. The roster ships with fifty-one seeds whose licences nobody has read
yet, so a fence demanding zero undisposed systems on day one would be red on day one and muted by
the end of the week (L1.43). `MAX_UNDISPOSED` and `MAX_UNSCHEDULED` are today's measurement and
they may FALL, never rise -- the same discipline as the box-task fence's `MAX_UNDECLARED`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.research import external_federation as fed  # noqa: E402

STATE = ROOT / "desks" / "mt5" / "data" / "external_federation.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "EXTERNAL_FEDERATION.json"
OUT = ROOT / "desks" / "mt5" / "reports" / "FEDERATION_FENCE.json"

#: TODAY'S MEASUREMENT, AND IT MAY ONLY FALL. Every seed on the roster whose licence has not been
#: read at its pinned commit is UNDISPOSED by construction, which is the honest count of how much
#: of the federation is still a plan rather than a worker.
MAX_UNDISPOSED = len(fed.SEEDS)
#: How many disposed workers may still lack a schedule. Falls as the sandbox runner lands.
MAX_UNSCHEDULED = len(fed.SEEDS)
#: A delta scan older than this is stale: an unchanged source is cheap, an unwatched one is a lie.
DELTA_STALE_DAYS = 14
#: A report older than this on the box means the hourly leg is not running.
REPORT_STALE_HOURS = 6


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _age_hours(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(stamp)).total_seconds() / 3600.0
    except ValueError:
        return None


def check(*, require_state: bool = False) -> dict:
    problems: list[str] = []
    notes: list[str] = []
    state = _read(STATE)
    report = _read(REPORT)
    rows: dict[str, dict] = {}
    if isinstance(state, dict) and isinstance(state.get("systems"), dict):
        rows = {str(k): v for k, v in state["systems"].items() if isinstance(v, dict)}

    # ---- the roster itself is law-shaped even with no state at all -----------------------
    ids = [s.system_id for s in fed.SEEDS]
    if len(set(ids)) != len(ids):
        problems.append("the bootstrap roster has duplicate system ids: one lineage, one row")
    for s in fed.SEEDS:
        if s.unknown_capabilities():
            problems.append(f"{s.system_id}: capabilities outside the vocabulary "
                            f"{s.unknown_capabilities()}")
        if s.unknown_axes():
            problems.append(f"{s.system_id}: axes outside the vocabulary {s.unknown_axes()}")
        if s.integration not in fed.DISPOSITIONS:
            problems.append(f"{s.system_id}: integration {s.integration!r} is not a disposition")
    bad_policy = fed.POLICY.violations()
    if bad_policy:
        problems.append(f"the sandbox policy itself is unsafe: {bad_policy}")
    # A packet that could carry a verdict would make an external engine a validator.
    try:
        fed.ExternalResearchPacket(system_id="fence", run_id="fence", commit="fence",
                                   candidates=({"survivor": True},))
    except ValueError:
        pass
    else:
        problems.append("the packet contract accepted a verdict-shaped field: an external engine "
                        "must never be able to donate a survivor (LAWS 5h)")
    # Ten reposts of one system must collapse to one lineage.
    twin = fed.ExternalSystem("twin", "twin", "public:twin", "fork", "DIRECT",
                              fed.SEED_BY_ID["tradingagents"].capabilities,
                              fed.SEED_BY_ID["tradingagents"].axes)
    if fed.admit(twin, list(fed.SEEDS)).disposition != "DUPLICATE":
        problems.append("admission let a capability twin in as a new system: that is fake breadth")

    # ---- the live half ------------------------------------------------------------------
    if not rows:
        why = (f"{STATE.relative_to(ROOT).as_posix()} is absent or empty: the federation organ "
               f"has not written state here")
        if require_state:
            problems.append(why + " -- on the box that is the defect, not a condition")
        else:
            notes.append(why + " (portable mode: UNMEASURED, not a breach)")
    undisposed = sorted(k for k, v in rows.items()
                        if str(v.get("disposition")) in ("UNDISPOSED", "UNMEASURED", "None"))
    if len(undisposed) > MAX_UNDISPOSED:
        problems.append(f"{len(undisposed)} systems carry no disposition, above the ratchet "
                        f"{MAX_UNDISPOSED}: TEXT_ONLY is not a resting state (LAWS 5h)")
    unscheduled = sorted(k for k, v in rows.items()
                         if str(v.get("disposition")) in fed.RUNNING_DISPOSITIONS
                         and not v.get("scheduled"))
    if len(unscheduled) > MAX_UNSCHEDULED:
        problems.append(f"{len(unscheduled)} DIRECT/WRAPPED/REBUILT workers have no schedule, "
                        f"above the ratchet {MAX_UNSCHEDULED}")
    for sid, row in sorted(rows.items()):
        if row.get("scheduled") and row.get("executed") and not row.get("progressed"):
            problems.append(f"{sid}: scheduled and executed with a stalled progress watermark -- "
                            f"a live process is not health (LAWS 7)")
        if row.get("produced") and not row.get("consumed"):
            problems.append(f"{sid}: produced output that no consumer acknowledged")
        try:
            descendants = float(row.get("descendants_generated") or 0)
        except (TypeError, ValueError):
            descendants = 0.0
        if descendants > 0 and str(row.get("trials_donated")) in ("UNMEASURED", "", "None"):
            problems.append(f"{sid}: donated {descendants:.0f} descendants with no trial "
                            f"accounting -- every trial is reported (LAWS 2)")
        try:
            datasets = float(row.get("datasets_extracted") or 0)
        except (TypeError, ValueError):
            datasets = 0.0
        if datasets > 0 and str(row.get("data_axes_extracted")) in ("UNMEASURED", "", "None"):
            problems.append(f"{sid}: {datasets:.0f} datasets extracted and no downstream route: "
                            f"DATA STRANDING (LAWS 5c)")
        if row.get("authority_claimed"):
            problems.append(f"{sid}: claims survivor, backtest or capital authority -- an "
                            f"external engine is a researcher, never a validator (LAWS 5h)")
        for forbidden in ("broker_credentials", "live_order_authority",
                          "canonical_write_authority", "secrets"):
            if row.get(forbidden):
                problems.append(f"{sid}: third-party code holds {forbidden} (external code "
                                f"sandbox law)")
        if str(row.get("status")) == "INTEGRATED" and not (row.get("produced")
                                                           or descendants > 0):
            problems.append(f"{sid}: declared INTEGRATED with no observed output")
        last = str(row.get("last_delta_scan") or "")
        if last and last != "UNMEASURED":
            try:
                if datetime.fromisoformat(last) < datetime.now(tz=UTC) - timedelta(
                        days=DELTA_STALE_DAYS):
                    problems.append(f"{sid}: delta scan is {DELTA_STALE_DAYS}+ days stale")
            except ValueError:
                notes.append(f"{sid}: last_delta_scan {last!r} is unparseable")
    # The roster may never be treated as exhaustive: discovery must keep running.
    if isinstance(report, dict):
        age = _age_hours(report.get("at"))
        if require_state and (age is None or age > REPORT_STALE_HOURS):
            problems.append(f"{REPORT.name} is {('unreadable' if age is None else f'{age:.1f}h')} "
                            f"old: the federation leg is not running hourly")
        if report.get("newly_discovered") == [] and report.get("systems", 0) <= len(fed.SEEDS) \
                and require_state:
            notes.append("no new system discovered this pass: acceptable for one hour, a breach "
                         "of the no-fixed-source-list rule if it holds for days")
    elif require_state:
        problems.append(f"{REPORT.name} is absent: the federation organ has never reported")

    status = "BREACH" if problems else ("OK" if rows else "UNMEASURED")
    return {"status": status, "systems": len(rows) or len(fed.SEEDS),
            "seeds": len(fed.SEEDS), "undisposed": len(undisposed),
            "undisposed_ratchet": MAX_UNDISPOSED, "unscheduled": len(unscheduled),
            "unscheduled_ratchet": MAX_UNSCHEDULED, "problems": problems, "notes": notes,
            "law": "docs/LAWS.md 5h (the open-source research federation law)"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-state", action="store_true",
                    help="the box: a missing artifact is the defect, not a condition")
    a = ap.parse_args(argv)
    out = check(require_state=a.require_state)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    except OSError:
        pass
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"federation: {out['systems']} systems, {out['undisposed']} undisposed "
              f"(ratchet {out['undisposed_ratchet']}), {out['unscheduled']} unscheduled "
              f"-- {out['status']}")
        for n in out["notes"]:
            print(f"  note {n}")
        for p in out["problems"]:
            print(f"  BREACH {p}")
    return 2 if out["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
