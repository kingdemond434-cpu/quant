#!/usr/bin/env python
"""AN ORGAN THAT RUNS, SUCCEEDS AND PRODUCES NOTHING MUST NOT LOOK LIKE ONE THAT IS WORKING.

WHAT HAPPENED, AND WHY THIS FILE EXISTS (2026-09-24).

Twelve intelligence seats had donated nothing for twenty-four hours and five of them were not
stubs -- `event_response_atlas` had written 258 artifacts and stopped, `graveyard_resurrection`
220, `research_tree` 138, `fbs_tape` 82, `axis_registry` 45. Every one of them was still on its
clock. Four of the five logged `LEG_DONE outcome=ok` EVERY HOUR while producing nothing at all,
and each rewrote its own report faithfully on the way past, so the reports directory looked alive
to the minute. The fifth logged `LEG_FAILED outcome=TIMEOUT` on every run for a day and a half.

NOTHING NOTICED EITHER SHAPE, and it is worth being precise about why, because the desk already
had three fences aimed at this ground:

    check_leg_rotation.py    did the leg RUN?            -- a leg that fails every time ATTENDED.
    check_seat_health.py     is the seat donating?       -- fires, and it was red, and it says
                                                            "overdue", which is equally true of a
                                                            seat with no clock and a seat whose
                                                            donation door is broken.
    check_organ_liveness.py  did the organ write?        -- reads the VPS cron plane; on the box
                                                            it judged 0 of 0 rows and exited 0.

None of them JOINS "it ran" to "its output moved", and that join is the whole diagnosis. A leg
that ran ten times, exited zero ten times, rewrote its own report ten times and donated nothing
is not slow, not starved and not unscheduled: its PRODUCTION path is broken while its REPORTING
path is perfect, which is the most convincing possible disguise. The desk's signature defect is
rc=0 with no write, and until this file there was no artifact anywhere that could say the words.

SO THE CONTRACT IS THREE FACTS PER ORGAN, JOINED:

    1. a DECLARED CADENCE          -- from the clock the repo already knows
    2. the LAST SUCCESSFUL RUN     -- from the event log every leg already writes
    3. the LAST ARTIFACT WRITTEN   -- and, crucially, on WHICH channel

TWO CHANNELS, AND THE DIFFERENCE BETWEEN THEM IS THE POINT. An organ's SELF channel is its own
report: the organ describing its own run. Its PRODUCT channel is what the rest of the desk eats
-- the intelligence seat the compiler reads. A self channel that advances proves the process
started and finished. It proves nothing whatsoever about output, and reading it as health is how
258 artifacts stopped arriving under a green board.

FOUR BREACHES, each a different diagnosis so nobody debugs the wrong thing:

  SILENT_NOOP                  ran OK `MIN_OK_RUNS` times and NO channel moved since the first
                               of those runs. The organ is a heater.
  REPORTS_BUT_PRODUCES_NOTHING ran OK, its SELF channel moved every time, its PRODUCT channel has
                               not moved in `PRODUCT_STALE_CADENCES` of its own cadences. This is
                               today's shape exactly, and it points at the DONATION DOOR rather
                               than at the clock -- which is where all four breaks actually were.
  ALWAYS_FAILING               ran `MIN_FAIL_RUNS` times in the window and not once succeeded.
                               `check_leg_rotation` counts these as attendance, correctly for its
                               own question and fatally for this one.
  NO_CONTRACT                  an organ on a clock whose output nothing can measure. UNMEASURED
                               is a verdict (L1.28a), and it is the measurement debt this fence
                               ratchets down rather than an excuse to skip the organ.

IT CAPS NOTHING AND GATES NO CAPITAL. It never touches a sleeve, a lot, a threshold, a bar or the
heat floor. Every verdict here can only ever demand that MORE organs produce; there is no
threshold in this file that an organ can satisfy by attempting less, and retiring a producer to
make a count look better raises `NO_CONTRACT` for nothing and is the one move that makes the
number worse.

THE DECLARED DEBT IS WHY IT SHIPS ACTIONABLE RATHER THAN PERMANENTLY RED. A fence that goes red
on a backlog it inherited is a fence somebody switches off (L1.43), and then the next real break
is silent again. So today's known-broken organs are DECLARED BY NAME in
`docs/research/organ_cadence_debt.json` with a reason and an owner, the declared set may only
SHRINK, and any organ that goes dark and is NOT on that list fails immediately -- on the day it
happens, which is the only day the diagnosis is cheap.

SECOND HALF: THE SEAL'S DUTY CYCLE AGAINST THE WINDOWS THAT MATTER. `check_placement_interlock`
answers "is placement halted right now". This answers the question one layer up, which the desk
learned the hard way on 2026-09-24: a rail can be perfectly correct, be green most of the day,
and be red exactly when a window opens. Ordinary development destroys the seal -- each commit to
the box invalidates it for roughly ten minutes -- so with several lanes committing, the gateway
places only in the gaps. This measures, per sleeve, per day: did that sleeve's window close with
a placement in it, or with nothing but refusals? `windows_lost` is then a number a freeze policy
can be argued from instead of a feeling, and it carries its own falling ratchet.

The windows are DERIVED from the ledger's own hours per sleeve, never a calendar in this file: a
sleeve whose session moves is still measured, and a sleeve added tomorrow is measured tomorrow
(LAWS 1 anti-hardcode).

NOT-APPLICABLE IS NOT UNMEASURED (L1.43). A host with no event log and no reports directory runs
no organs -- CI, a fresh clone -- and passes saying so. A host that HAS the cycle and produces no
readable event log is UNMEASURED and FAILS, because "no evidence" is precisely what the outage
looked like.

Artifact: `desks/mt5/reports/ORGAN_CADENCE.json`. Registered in `scripts/run_law_gate.py`
`_STATE_FENCES`.

    python scripts/check_organ_cadence.py
    python scripts/check_organ_cadence.py --json
    python scripts/check_organ_cadence.py --declare      # write today's breaches into the debt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.producer_census import runs_clocks_here  # noqa: E402

DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "ORGAN_CADENCE.json"
DEBT = ROOT / "docs" / "research" / "organ_cadence_debt.json"

LEDGER_REL = "docs/research/tier1_program.json"
EVENTS_REL = "desks/mt5/data/events.jsonl"
REPORTS_REL = "desks/mt5/reports"
DECISIONS_REL = "desks/mt5/data/decision_ledger.jsonl"
INTEL_RELS = ("desks/mt5/data/intelligence", "data/intelligence")

#: The measurement window. One day of an hourly cycle is twenty-four chances to produce; an organ
#: that took none of them is not having a slow morning.
WINDOW_H = 24.0

#: How many clean runs make "it runs fine" a claim rather than a coincidence. Below this the
#: organ simply has not been observed enough to convict, and saying so is the honest answer.
MIN_OK_RUNS = 3

#: ...and how many failures make "it fails every time" a claim. Same reasoning, other direction.
MIN_FAIL_RUNS = 3

#: How many of its OWN cadences a product channel may miss while its self channel keeps moving.
#:
#: SIX, NOT ONE. A producer legitimately finds nothing on a given pass -- that is what searching
#: is -- and a fence that called one empty hour a defect would be off within the week. Six hourly
#: passes with a perfect run record and nothing produced is not a quiet market; measured on the
#: trading box the real breaks were at 31, 36, 42, 72 and 72 hours, so this is an order of
#: magnitude tighter than the failure it is sized for and still far looser than normal work.
PRODUCT_STALE_CADENCES = 6.0

#: Default cadence for an organ on the hourly cycle. Read from the clock where the repo declares
#: one; this is the fallback for a leg the cycle runs and nothing else times.
DEFAULT_CADENCE_H = 1.0

#: How many days of decision rows the seal duty cycle looks back over. Long enough for each
#: sleeve's window to have recurred several times, short enough that a fortnight-old outage the
#: desk has already fixed does not keep the number red.
SEAL_LOOKBACK_DAYS = 7.0

#: WHETHER THIS HOST RUNS THE CLOCKS IS MEASURED, NOT GUESSED -- and not re-implemented here.
#:
#: The build box holds a checkout of the trading box's state -- the same events.jsonl, the same
#: reports -- and runs no research cycle. Its artifact mtimes are `git checkout` times, so every
#: comparison of "did the output move since the run" measures the sync, not the organ. A fence
#: that convicted organs on that evidence would be wrong on one host and switched off on both
#: (L1.43).
#:
#: THE OBVIOUS TEST IS THE WRONG ONE, and it was tried first: judge the event log's own freshness
#: and call a stale log a mirror. Measured on the build box 2026-09-24, the newest event there was
#: **2.55 hours old** -- the sync is frequent enough that a freshness rule either excuses a real
#: stall on the trading box or convicts a mirror anyway, depending on which side of the sync the
#: check lands. It reads the sync cadence, not the question.
#:
#: `producer_census.runs_clocks_here()` already answers the real question and is the desk's one
#: answer to it: on Windows it asks the scheduler whether the box's own tasks are registered HERE;
#: on Linux whether the systemd user units are installed. `check_seat_health` and
#: `check_organ_liveness` both route on it, so a third opinion in this file could only disagree
#: with the other two.
_RUNS_CLOCKS_HERE_HELP = ("libs.ops.producer_census.runs_clocks_here -- the desk's one measured "
                          "answer to 'does this checkout hold the clocks'")

UNMEASURED = "UNMEASURED"
_BREACH = ("SILENT_NOOP", "REPORTS_BUT_PRODUCES_NOTHING", "ALWAYS_FAILING")
_TS_FIELDS = ("decided_at", "ts", "at", "time")
_LEG_TOKEN = re.compile(r"^[A-Za-z0-9_]+$")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_iso(text: Any) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _newest(paths: list[Path]) -> float | None:
    stamps = [s for s in (_mtime(p) for p in paths) if s is not None]
    return max(stamps) if stamps else None


# ------------------------------------------------------------------ 1. THE DECLARED CONTRACT

def declared_organs(base: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """leg -> {self_channel: [paths], cadence_h}. Returns (organs, tokens this could not parse).

    READ FROM THE LEDGER THE DESK ALREADY KEEPS, never a new list. `docs/research/tier1_program.json`
    already carries `scheduled_by: hourly_cycle:<leg>` beside `artifact: <path>` for 352 rows --
    the liveness contract was declared and nothing had ever read it as one.

    THE LEG TOKEN IS NORMALISED, and that is not cosmetic. `hourly_cycle._leg_artifacts` takes
    `tok.split(":", 1)[1]` whole, so a row scheduled by `hourly_cycle:causal_lab (macro
    department)` yields the leg name `causal_lab (macro department)`, which matches no leg that
    has ever run. Measured on the trading box 2026-09-24: 263 tokens, of which 184 are clean leg
    names -- 79 rows, 30% of the declaration, dropped on the floor by a parser that has been
    reading past them for months. That is the same class of defect as everything else in this
    file: a fact that exists, in a file the desk maintains, that no organ actually reads.
    """
    organs: dict[str, dict[str, Any]] = {}
    unparsed: list[str] = []
    path = base / Path(*LEDGER_REL.split("/"))
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return organs, unparsed
    for item in doc.get("items", []) if isinstance(doc, dict) else []:
        if not isinstance(item, dict):
            continue
        sched = str(item.get("scheduled_by") or "")
        art = str(item.get("artifact") or "").strip()
        if not art or "hourly_cycle:" not in sched:
            continue
        for tok in sched.split(","):
            tok = tok.strip()
            if not tok.startswith("hourly_cycle:"):
                continue
            # Everything up to the first space, bracket or semicolon: the rest is prose the
            # ledger carries for a human and a leg name never contains.
            leg = re.split(r"[\s(;]", tok.split(":", 1)[1], maxsplit=1)[0].strip()
            if not _LEG_TOKEN.match(leg):
                unparsed.append(tok[:80])
                continue
            rec = organs.setdefault(leg, {"self": [], "cadence_h": DEFAULT_CADENCE_H})
            for root in (base, base / "desks" / "mt5"):
                cand = root / Path(*art.split("/"))
                if cand.exists():
                    if cand not in rec["self"]:
                        rec["self"].append(cand)
                    break
    return organs, unparsed


def product_channels(base: Path) -> dict[str, list[Path]]:
    """seat name -> the intelligence directories that hold its donations, both roots.

    The PRODUCT channel is what the candidate compiler reads and nothing else (CLAUDE.md), so it
    is the only channel whose silence costs the desk a hypothesis.
    """
    out: dict[str, list[Path]] = {}
    for rel in INTEL_RELS:
        root = base / Path(*rel.split("/"))
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for d in entries:
            if d.is_dir() and not d.name.startswith((".", "_")):
                out.setdefault(d.name, []).append(d)
    return out


def _seat_newest(dirs: list[Path]) -> float | None:
    """Newest FILE mtime anywhere under the seat's directories.

    Measured off the file rather than a row's own stamp, for the reason the sibling fence gives:
    a seat that stopped writing is the thing being looked for, and a stale row's internal
    timestamp would report it as alive.
    """
    stamps: list[float] = []
    for d in dirs:
        try:
            for f in d.rglob("*"):
                if f.is_file():
                    s = _mtime(f)
                    if s is not None:
                        stamps.append(s)
        except OSError:
            continue
    return max(stamps) if stamps else None


# --------------------------------------------------------------------- 2. THE RUN RECORD

def run_records(path: Path, *, limit: int = 200_000) -> tuple[dict[str, list[tuple[datetime, bool]]],
                                                              str | None]:
    """leg -> [(when, succeeded)], oldest first. Returns (runs, problem)."""
    try:
        raw = path.read_text("utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {}, f"{EVENTS_REL} exists but could not be read ({type(exc).__name__})"
    runs: dict[str, list[tuple[datetime, bool]]] = {}
    for line in raw[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        if kind not in ("LEG_DONE", "LEG_FAILED"):
            continue
        leg = str(row.get("leg") or "").strip()
        when = _parse_iso(row.get("at"))
        if not leg or when is None:
            continue
        runs.setdefault(leg, []).append((when, kind == "LEG_DONE"))
    for hist in runs.values():
        hist.sort(key=lambda r: r[0])
    return runs, None


# ------------------------------------------------------------------------- 3. THE JOIN

def judge(organs: dict[str, dict[str, Any]], runs: dict[str, list[tuple[datetime, bool]]],
          products: dict[str, list[Path]], now: datetime) -> list[dict[str, Any]]:
    """One row per declared organ: cadence, last good run, last write per channel, verdict."""
    cutoff = now - timedelta(hours=WINDOW_H)
    rows: list[dict[str, Any]] = []
    for leg in sorted(organs):
        rec = organs[leg]
        cadence = float(rec.get("cadence_h") or DEFAULT_CADENCE_H)
        hist = runs.get(leg, [])
        in_window = [(t, ok) for t, ok in hist if t >= cutoff]
        oks = [t for t, ok in in_window if ok]
        fails = [t for t, ok in in_window if not ok]

        self_paths: list[Path] = list(rec["self"])
        prod_dirs = products.get(leg, [])
        self_at = _newest(self_paths)
        prod_at = _seat_newest(prod_dirs) if prod_dirs else None

        row: dict[str, Any] = {
            "organ": leg,
            "cadence_h": cadence,
            "runs_ok_in_window": len(oks),
            "runs_failed_in_window": len(fails),
            "last_run_ok_at": max(oks).isoformat(timespec="seconds") if oks else UNMEASURED,
            "self_channel": [str(p) for p in self_paths],
            "self_age_h": round((now.timestamp() - self_at) / 3600.0, 2) if self_at else None,
            "product_channel": [str(p) for p in prod_dirs],
            "product_age_h": round((now.timestamp() - prod_at) / 3600.0, 2) if prod_at else None,
        }

        has_channel = bool(self_paths or prod_dirs)
        if not has_channel:
            row.update(verdict="NO_CONTRACT", why=(
                "this organ runs on the hourly cycle and declares an artifact this host does not "
                "hold, so whether it produced anything is UNMEASURED -- a verdict, not a pass"))
        elif not hist:
            row.update(verdict="NEVER_RAN", why=(
                "no LEG_DONE or LEG_FAILED has ever been recorded for this organ; "
                "check_leg_rotation owns that failure and this fence only reports it"))
        elif not in_window:
            row.update(verdict="NO_RUN_IN_WINDOW", why=(
                f"nothing recorded in {WINDOW_H:g}h; check_leg_rotation owns that failure"))
        elif not oks and len(fails) >= MIN_FAIL_RUNS:
            row.update(verdict="ALWAYS_FAILING", why=(
                f"ran {len(fails)} time(s) in {WINDOW_H:g}h and succeeded NONE of them. A leg "
                "that fails every time still counts as attendance to a fence that only asks "
                "whether it ran, which is why this one asks whether it worked"))
        elif len(oks) >= MIN_OK_RUNS and _no_channel_moved(oks, self_at, prod_at):
            row.update(verdict="SILENT_NOOP", why=(
                f"exited cleanly {len(oks)} time(s) since {min(oks).isoformat(timespec='seconds')}"
                " and not one of its output channels has moved since -- rc=0 with no write, which "
                "is indistinguishable from healthy on every board the desk has"))
        elif (len(oks) >= MIN_OK_RUNS and prod_dirs and self_at is not None
              and self_at >= min(oks).timestamp()
              and (prod_at is None
                   or (now.timestamp() - prod_at) / 3600.0 > cadence * PRODUCT_STALE_CADENCES)):
            age = ("never" if prod_at is None
                   else f"{(now.timestamp() - prod_at) / 3600.0:.1f}h ago")
            row.update(verdict="REPORTS_BUT_PRODUCES_NOTHING", why=(
                f"ran cleanly {len(oks)} time(s) and rewrote its own report every time, while the "
                f"seat the compiler reads last moved {age} "
                f"(> {cadence * PRODUCT_STALE_CADENCES:g}h). The clock is fine and the organ is "
                "fine; its DONATION DOOR is not, and that is a different repair"))
        else:
            row.update(verdict="LIVE", why="")
        rows.append(row)
    return rows


def _no_channel_moved(oks: list[datetime], self_at: float | None,
                      prod_at: float | None) -> bool:
    """True when every channel this organ owns predates its first clean run in the window."""
    first = min(oks).timestamp()
    seen = [s for s in (self_at, prod_at) if s is not None]
    return bool(seen) and all(s < first for s in seen)


# ------------------------------------------------------- 4. THE SEAL'S DUTY CYCLE PER WINDOW

def seal_duty_cycle(path: Path, now: datetime) -> dict[str, Any]:
    """Per sleeve, per day: did its window close with a placement, or with nothing but refusals?

    THE WINDOWS ARE DERIVED, NEVER LISTED. A sleeve's window is the set of UTC hours in which the
    ledger has ever recorded a decision for it, so a session that moves is still measured and a
    sleeve added tomorrow is measured tomorrow without touching this file (LAWS 1).
    """
    out: dict[str, Any] = {"available": False, "why": "", "lookback_days": SEAL_LOOKBACK_DAYS,
                           "windows_seen": 0, "windows_placed": 0, "windows_lost": 0,
                           "lost_by_reason": {}, "by_sleeve": {}}
    try:
        raw = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        out["why"] = f"{DECISIONS_REL} is not readable on this host"
        return out
    cutoff = now - timedelta(days=SEAL_LOOKBACK_DAYS)
    # (sleeve, date) -> {"placed": bool, "reasons": Counter-ish dict}
    windows: dict[tuple[str, str], dict[str, Any]] = {}
    for line in raw[-400_000:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        when = None
        for field in _TS_FIELDS:
            if row.get(field):
                when = _parse_iso(row[field])
                if when is not None:
                    break
        if when is None or when < cutoff:
            continue
        sleeve = str(row.get("sleeve") or row.get("strategy_id") or "?")
        key = (sleeve, when.date().isoformat())
        w = windows.setdefault(key, {"placed": False, "reasons": {}})
        taken = row.get("taken")
        placed = (taken is True or str(row.get("reason") or "") == "placed"
                  or str(row.get("outcome") or "").upper() in ("EXECUTED", "PLACED", "FILLED"))
        if placed:
            w["placed"] = True
        else:
            r = str(row.get("reason") or "?")
            w["reasons"][r] = w["reasons"].get(r, 0) + 1
    if not windows:
        out["why"] = (f"no decision row inside {SEAL_LOOKBACK_DAYS:g} day(s): the seal's duty "
                      "cycle is UNMEASURED here, which is a verdict about the measurement")
        return out
    by_sleeve: dict[str, dict[str, Any]] = {}
    for (sleeve, day), w in sorted(windows.items()):
        s = by_sleeve.setdefault(sleeve, {"days": 0, "placed": 0, "lost": 0, "lost_days": [],
                                          "top_refusal": None})
        s["days"] += 1
        if w["placed"]:
            s["placed"] += 1
            continue
        s["lost"] += 1
        if len(s["lost_days"]) < 12:
            s["lost_days"].append(day)
        for r, n in w["reasons"].items():
            out["lost_by_reason"][r] = out["lost_by_reason"].get(r, 0) + n
            if s["top_refusal"] is None:
                s["top_refusal"] = r
    out.update(available=True, by_sleeve=by_sleeve,
               windows_seen=sum(v["days"] for v in by_sleeve.values()),
               windows_placed=sum(v["placed"] for v in by_sleeve.values()),
               windows_lost=sum(v["lost"] for v in by_sleeve.values()))
    out["lost_by_reason"] = dict(sorted(out["lost_by_reason"].items(),
                                        key=lambda kv: -kv[1])[:10])
    out["note"] = ("a LOST window is a sleeve-day on which the desk decided and never placed. It "
                   "is not automatically a defect -- a sleeve out of regime correctly places "
                   "nothing -- but a rail-shaped reason ('release_identity_refused' and its kin) "
                   "in this column is the book losing windows to its own machinery, which is what "
                   "cost 19 gold sleeve-days over seventeen silent days in September 2026")
    return out


# ------------------------------------------------- 4b. THE STREAMS (a cursor that stopped moving)

#: How much of a cursored stream may sit unread before the funnel is severed rather than busy.
#:
#: A THIRD SHAPE THIS FENCE COULD NOT SEE, AND IT COST THE DESK EVERY VERDICT IT EARNED (measured
#: 2026-09-25). `registry_sync` ran every hour, exited zero, advanced its cursor and rewrote its
#: report every single pass -- so its SELF channel was perfect AND its PRODUCT channel moved too,
#: because the pass really did pour rows. It poured 203 of them. The gate verdict ledger was
#: growing by ~3,500 rows an hour and the `gate_verdicts` cursor sat at byte 226,198 of a
#: 54,119,184-byte file: 0.42% read, 227,497 verdicts unpoured, the input growing 113x faster
#: than the cursor advanced. `judged_at` had been set on 1,278 candidates in the desk's whole
#: history, all at one instant, while the sandboxes donated, the docket carried them and the
#: judge ruled on them. The cause was a missing index making the read-back door scan 740,357 rows
#: per verdict at 2.09 rows/s (see `ix_candidates_donated_cell`).
#:
#: NEITHER EXISTING CHANNEL CAN EVER CATCH THAT. "It ran" was true, "its output moved" was true,
#: and the funnel was still severed -- because for a CURSORED stream the honest question is not
#: whether the cursor moved but whether it is KEEPING UP with its input. A pipeline whose input
#: grows faster than its cursor is diverging, and divergence is monotone: it never recovers on
#: its own and every hour makes it worse. So the measurement is the unread FRACTION, not an age.
#:
#: 25%: a stream that has read three quarters of its input is working through a backlog; one that
#: has read less than that, on a host that runs the clocks, is not going to catch up. The real
#: break measured 99.58% unread, four times past this line, so this is sized well inside the
#: failure it exists for.
STREAM_UNREAD_MAX_FRACTION = 0.25

#: Below this an unread tail is one pass's normal lag, not a severed funnel, whatever the ratio.
STREAM_UNREAD_MIN_BYTES = 2_000_000


def stream_backlogs(base: Path) -> dict[str, Any]:
    """Every cursored stream: how much of its input the registry has actually read.

    UNMEASURED IS A VERDICT (L1.28a). A host with no registry, no cursor table or no stream file
    reports exactly that and convicts nobody -- the build box legitimately has none of this. What
    this can never do is report a severed stream as healthy because the organ above it exited
    zero, which is the whole reason it exists.
    """
    out: dict[str, Any] = {"status": UNMEASURED, "streams": [], "breaches": []}
    try:
        sys.path.insert(0, str(base))
        from libs.moat import registry as R
    except Exception as exc:                       # pragma: no cover - import guard
        out["why"] = f"libs.moat.registry not importable here: {type(exc).__name__}: {exc}"
        return out
    if not R.path().exists():
        out["why"] = f"no registry at {R.path()}: this host holds no cursored stream"
        return out
    # THE TREE BEING JUDGED OWNS ITS REGISTRY. `R.path()` is process-global, so a scan of another
    # tree (a test box, a mirror checkout) would otherwise read THIS process's registry and judge
    # that tree's streams against another host's cursors -- a verdict about the wrong object.
    try:
        R.path().resolve().relative_to(Path(base).resolve())
    except ValueError:
        out["why"] = (f"the registry in scope ({R.path()}) is not under {base}: this tree's "
                      "cursored streams are UNMEASURED here, never judged against another tree")
        return out
    try:
        conn = R.connect()
    except Exception as exc:                       # pragma: no cover - locked/absent db
        out["why"] = f"registry not readable: {type(exc).__name__}: {exc}"
        return out
    try:
        for key, rel in R.SYNC_STREAMS:
            path = R.stream_path(key, desk=base / "desks" / "mt5")
            if path is None or not Path(path).exists():
                path = base / Path(*rel.split("/"))
            row = conn.execute("SELECT value FROM sync_cursor WHERE key=?", (key,)).fetchone()
            cursor = None
            if row is not None:
                try:
                    cursor = int(row["value"])
                except (TypeError, ValueError):
                    cursor = None
            size = Path(path).stat().st_size if Path(path).exists() else None
            rec: dict[str, Any] = {"stream": key, "path": str(path), "cursor": cursor,
                                   "size_bytes": size}
            if size is None:
                rec["verdict"] = UNMEASURED
                rec["why"] = "no input file on this host"
            elif cursor is None:
                rec["verdict"] = "NO_CURSOR"
                rec["why"] = (f"the registry holds no '{key}' cursor: every row on disk is "
                              "invisible to it, and nothing says so")
                out["breaches"].append(rec)
            else:
                unread = max(0, size - min(cursor, size))
                frac = (unread / size) if size else 0.0
                rec.update(unread_bytes=unread, unread_fraction=round(frac, 4))
                if unread >= STREAM_UNREAD_MIN_BYTES and frac > STREAM_UNREAD_MAX_FRACTION:
                    rec["verdict"] = "STREAM_DIVERGING"
                    rec["why"] = (
                        f"{unread:,} of {size:,} bytes ({frac:.1%}) of {key} have never been "
                        "read. The organ above this cursor can run, exit zero and advance it "
                        "every pass while the funnel stays severed -- a cursor that moves is not "
                        "a cursor that keeps up")
                    out["breaches"].append(rec)
                else:
                    rec["verdict"] = "OK"
            out["streams"].append(rec)
        out["status"] = "MEASURED"
    except Exception as exc:                       # pragma: no cover - schema drift
        out["why"] = f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()
    return out


# --------------------------------------------------------------------------- 5. THE RATCHET

DEBT_REL = "docs/research/organ_cadence_debt.json"


def _debt(base: Path) -> dict[str, Any]:
    """The declared debt, resolved under `base` so a test tree and the live tree read their own."""
    try:
        doc = json.loads((base / Path(*DEBT_REL.split("/"))).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def scan(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    t_now = now or _now()
    events = base / Path(*EVENTS_REL.split("/"))
    reports = base / Path(*REPORTS_REL.split("/"))

    doc: dict[str, Any] = {
        "generated": t_now.isoformat(timespec="seconds"), "root": str(base),
        "law": ("EVERY ORGAN DECLARES A CADENCE AND IS MEASURED AGAINST IT ON THE CHANNEL THE "
                "DESK ACTUALLY EATS. Running is not producing; exiting zero is not producing; "
                "rewriting your own report is not producing."),
        "thresholds": {"window_h": WINDOW_H, "min_ok_runs": MIN_OK_RUNS,
                       "min_fail_runs": MIN_FAIL_RUNS,
                       "product_stale_cadences": PRODUCT_STALE_CADENCES},
        "problems": [], "notes": [], "organs": [], "ok": True, "verdict": "OK",
    }

    # NOT APPLICABLE: a host that runs no cycle has no organ that could be silently idle.
    if not events.exists() and not reports.is_dir():
        doc["verdict"] = "NOT_APPLICABLE"
        doc["notes"].append(
            "no event log and no reports directory here -- this host runs no research cycle, so "
            "there is no organ whose silence it could be hiding")
        return doc

    organs, unparsed = declared_organs(base)
    if not organs:
        doc.update(ok=False, verdict="UNMEASURED")
        doc["problems"].append(
            f"{LEDGER_REL} declares no hourly organ with an artifact on this host: the liveness "
            "contract cannot be read, which is the same silence this fence exists to end")
        return doc

    if not events.exists():
        doc.update(ok=False, verdict="UNMEASURED")
        doc["problems"].append(
            f"this host declares {len(organs)} hourly organ(s) and has no {EVENTS_REL}: an organ "
            "plane that records no runs is exactly what a silent stall looks like")
        return doc

    runs, problem = run_records(events)
    if problem:
        doc.update(ok=False, verdict="UNMEASURED")
        doc["problems"].append(problem)
        return doc

    newest_event = max((t for hist in runs.values() for t, _ in hist), default=None)
    log_age_h = ((t_now - newest_event).total_seconds() / 3600.0
                 if newest_event is not None else None)
    doc["event_log_age_h"] = round(log_age_h, 2) if log_age_h is not None else UNMEASURED

    # A MIRROR IS NOT A STALL, and which this host is, is MEASURED (see _RUNS_CLOCKS_HERE_HELP).
    here = runs_clocks_here(base)
    doc["runs_clocks_here"] = here
    if here is False:
        doc["verdict"] = "MIRROR_OF_ANOTHER_HOST"
        doc["notes"].append(
            "this checkout holds no clock of its own (measured: none of the box's scheduled tasks "
            "is registered here), so it is a mirror of the host that does. Every artifact mtime "
            "here is a sync time, and judging an organ on a sync would report work that is "
            "happening correctly elsewhere as dark. The host that owns the clock judges these "
            f"organs; {len(organs)} of them were read and their state is published below")
        doc["organs"] = judge(organs, runs, product_channels(base), t_now)
        doc["n_organs"] = len(doc["organs"])
        return doc
    if here is None:
        doc["notes"].append(
            "whether this host runs the clocks is UNMEASURED (the scheduler could not be read); "
            "the organs are judged anyway, because assuming 'mirror' would be absence granting an "
            "excuse, which is the failure this whole file is about (L1.28a)")

    products = product_channels(base)
    rows = judge(organs, runs, products, t_now)
    doc["organs"] = rows
    doc["n_organs"] = len(rows)
    census: dict[str, int] = {}
    for r in rows:
        census[str(r["verdict"])] = census.get(str(r["verdict"]), 0) + 1
    doc["census"] = dict(sorted(census.items()))
    doc["seal_duty_cycle"] = seal = seal_duty_cycle(
        base / Path(*DECISIONS_REL.split("/")), t_now)

    if unparsed:
        doc["n_unparsed_schedule_tokens"] = len(unparsed)
        doc["unparsed_schedule_tokens"] = sorted(set(unparsed))[:12]
        doc["notes"].append(
            f"{len(unparsed)} scheduled_by token(s) in {LEDGER_REL} carry prose after the leg "
            "name; this fence normalises them, and `hourly_cycle._leg_artifacts` does not -- so "
            "those rows resolve to no leg there and their output hash is never taken")

    declared = _debt(base)
    known = {str(k) for k in (declared.get("declared") or {})}
    breached = [r for r in rows if r["verdict"] in _BREACH]
    undeclared = [r for r in breached if r["organ"] not in known]
    doc["debt"] = {"declared": sorted(known), "n_declared": len(known),
                   "n_breached": len(breached), "n_undeclared": len(undeclared),
                   "declared_max": declared.get("declared_max"),
                   "windows_lost_max": declared.get("windows_lost_max")}

    for r in sorted(undeclared, key=lambda r: str(r["organ"])):
        doc["ok"] = False
        doc["problems"].append(
            f"{r['organ']}: {r['verdict']} -- {r['why']}. It is not in {DEBT.name}, so this is a "
            "NEW dark organ and today is the cheap day to fix it")

    dmax = declared.get("declared_max")
    if isinstance(dmax, (int, float)) and len(known) > dmax:
        doc["ok"] = False
        doc["problems"].append(
            f"the declared debt holds {len(known)} organ(s) against a ratchet of {dmax:g}: this "
            "list may only SHRINK. Repair an organ and remove its row -- never add one to make "
            "this fence quiet")

    wmax = declared.get("windows_lost_max")
    if (seal.get("available") and isinstance(wmax, (int, float))
            and seal["windows_lost"] > wmax):
        doc["ok"] = False
        doc["problems"].append(
            f"{seal['windows_lost']} sleeve-day window(s) closed without a placement in the last "
            f"{SEAL_LOOKBACK_DAYS:g} days, against a ratchet of {wmax:g}. Top refusal reasons: "
            f"{seal['lost_by_reason']}. A rail that is green most of the day and red when a "
            "window opens costs exactly as much as a rail that is broken")

    for r in rows:
        if r["verdict"] in ("NO_CONTRACT", "NEVER_RAN", "NO_RUN_IN_WINDOW"):
            continue
        if r["verdict"] in _BREACH and r["organ"] in known:
            doc["notes"].append(f"{r['organ']}: {r['verdict']}, declared in {DEBT.name}")

    # THE CURSORED STREAMS. Judged only where the clocks actually run: on a mirror a stale cursor
    # is the mirror being a mirror, exactly as for every other verdict in this file.
    streams = stream_backlogs(base)
    doc["streams"] = streams
    if streams.get("status") != "MEASURED":
        doc["notes"].append(
            f"stream backlogs UNMEASURED: {streams.get('why') or 'no reason recorded'}")
    elif here:
        for rec in streams.get("breaches") or []:
            doc["ok"] = False
            doc["problems"].append(f"{rec['stream']}: {rec['verdict']} -- {rec['why']}")
    else:
        doc["notes"].append(
            "stream backlogs measured but not judged: this host does not run the clocks, so a "
            "cursor behind its input is a mirror, not a severed funnel")

    doc["verdict"] = "OK" if doc["ok"] else "DARK"
    return doc


def write_artifact(doc: dict[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def declare(doc: dict[str, Any], target: Path | None = None) -> Path:
    """Record today's breaches as the declared debt, with the ratchet set at what was measured.

    NOT A SILENCER. Every row lands with its verdict and the fence's own reason, the count becomes
    a ceiling that may only fall, and a breach that appears tomorrow and is not here fails on the
    day it appears. Declaring is how a backlog becomes a worklist instead of a permanently red
    board nobody reads (L1.43).
    """
    path = Path(target or DEBT)
    existing = {}
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
        existing = dict(prev.get("declared") or {}) if isinstance(prev, dict) else {}
    except (OSError, ValueError):
        pass
    for r in doc.get("organs", []):
        if r["verdict"] not in _BREACH:
            continue
        existing.setdefault(str(r["organ"]), {
            "verdict": r["verdict"], "why": r["why"],
            "declared_at": doc.get("generated"),
            "owner": "unassigned -- a declared organ with no owner is a queue, not a plan",
        })
    seal = doc.get("seal_duty_cycle") or {}
    out = {
        "law": ("ORGAN CADENCE DEBT. Every organ here is KNOWN to be dark and carries its reason. "
                "The list may only SHRINK: an organ leaves by being repaired, never by being "
                "deleted, and a NEW dark organ fails the fence immediately rather than joining a "
                "backlog. See scripts/check_organ_cadence.py."),
        "declared_max": len(existing),
        "windows_lost_max": seal.get("windows_lost") if seal.get("available") else None,
        "updated_utc": doc.get("generated"),
        "declared": dict(sorted(existing.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact as JSON")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    ap.add_argument("--declare", action="store_true",
                    help="record today's breaches as the declared debt and set the ratchets")
    args = ap.parse_args(argv)

    doc = scan()
    if not args.no_write:
        write_artifact(doc)
    if args.declare:
        print(f"declared debt -> {declare(doc)}")
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 0 if doc["ok"] else 2

    print(f"organ cadence: {doc.get('verdict')}; {doc.get('n_organs', 0)} declared organ(s) -> "
          f"{doc.get('census', {})}")
    seal = doc.get("seal_duty_cycle") or {}
    if seal.get("available"):
        print(f"  seal duty cycle: {seal['windows_placed']}/{seal['windows_seen']} sleeve-day "
              f"window(s) placed, {seal['windows_lost']} lost  {seal['lost_by_reason']}")
    elif seal:
        print(f"  seal duty cycle: UNMEASURED -- {seal.get('why')}")
    for r in doc.get("organs", []):
        if r["verdict"] in _BREACH:
            print(f"  {r['verdict']:<30} {r['organ']:<28} ok={r['runs_ok_in_window']:>3} "
                  f"fail={r['runs_failed_in_window']:>3} self={r['self_age_h']}h "
                  f"product={r['product_age_h']}h")
    for note in doc["notes"][:12]:
        print(f"  note: {note}")
    for problem in doc["problems"]:
        print(f"  FAIL: {problem}")
    if doc["ok"]:
        print("check_organ_cadence: OK -- no organ is running, succeeding and producing nothing")
        return 0
    print("check_organ_cadence: FAILED -- an organ is dark and nothing else was going to say so")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
