"""ALLOCATOR TRIGGERS -- the book re-solves when the world changes, not when the clock says so.

PRINCIPAL, 2026-09-23: "make sure the allocator is 24/7 and not slow, and trades on instant macro
news -- the allocation dynamically switches sleeves, instant, for maximum growth, cross-asset."

WHAT WAS WRONG. `pf_allocator` re-solved on a clock and on nothing else. A macro surprise at
:03, a regime transition at :07, a certificate minted at :11 and a fill at :19 all waited for the
top of the hour, and the book that traded through them was solved against a world that no longer
existed. An hour is not "instant", and the cost is not theoretical: the sleeve the new state
favours is the one the book is NOT holding for up to sixty minutes.

WHAT THIS DOES. It watches the artifacts that carry a state change, each with the signature that
makes it a CHANGE rather than a rewrite, and when one moves it fires `pf_allocator --mode fast`
immediately. The slow full solve keeps its own cadence as the backstop -- this adds reactions, it
never replaces the hourly pass.

  macro_surprise          reports/MACRO_VIEW.json        the macro labels / surprise block
  regime_transition       data/regime_state.json,
                          reports/REGIME_ROUTER.json     the regime the router is routing to
  certificate_change      data/sleeve_registry.json      a certificate arriving or dying
  fill                    data/gateway_state.json        realised risk moved at the venue
  cost_capacity_revision  reports/NET_EDGE.json          net-of-cost or capacity was re-priced

WHY IT IS SAFE UNDER GROWTH GOVERNANCE. It fires the SAME solver the hourly leg fires, with the
same heat law, the same floor and the same certificate contest. It sets no fraction and passes no
override: a re-solve can only reallocate between sleeves inside the heat the law already
resolved. Every re-solve records `heat_before` and `heat_after` so the two-sidedness is a
MEASUREMENT -- a reaction that lowered total heat would show up here as its own defect rather
than hiding inside an average.

CROSS-ASSET BY CONSTRUCTION, and that is the solver's property, not this organ's: `pf_allocator`
solves E[log W] over the WHOLE book at once, so gold, FX, indices and the rest compete for the
same heat on their conditional expected log growth. This organ only decides WHEN that joint solve
happens.

REACTION LATENCY IS PUBLISHED, so "not slow" is a number. Every firing records the triggering
artifact's OWN timestamp, the moment this organ detected it, and the timestamp of the allocation
that came out; `reports/ALLOCATOR_REACTION.json` carries per-kind n / last / median / worst, and
a regression is visible the hour it happens.

    python desks/mt5/research/allocator_trigger.py --once --budget-s 600
    python desks/mt5/research/allocator_trigger.py --resident --interval-s 20   # the 24/7 shape
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "ALLOCATOR_REACTION.json"
#: Append-only: one row per firing. The report is a summary and is overwritten; this is the
#: record a latency regression is measured against.
LOG = DATA / "allocator_reactions.jsonl"
#: What each watched source looked like when it was last acted on.
STATE = DATA / "allocator_trigger_state.json"
ALLOCATION = REPORTS / "pf_allocation.json"

#: The poll interval of the 24/7 resident. Not a tuning knob: it is the smallest interval at
#: which the watched artifacts can change (their producers are minute-scale at best), and a
#: faster poll would spend CPU re-hashing files that cannot have moved.
DEFAULT_INTERVAL_S = 20.0
#: A fast solve costs ~15-30s on this box. Two firings inside one of those would queue behind the
#: allocator's own lock and the second would stand down with nothing to add, so a firing waits
#: this long for the previous one to land. It is a DEBOUNCE, not a rate limit: a trigger that
#: arrives during the wait is still served, just by the next pass.
MIN_SOLVE_GAP_S = 60.0


class Source:
    """One watched artifact: what makes it a CHANGE, and when the change happened."""

    def __init__(self, kind: str, path: Path, keys: tuple[str, ...], why: str) -> None:
        self.kind, self.path, self.keys, self.why = kind, path, keys, why


def sources() -> list[Source]:
    return [
        Source("macro_surprise", REPORTS / "MACRO_VIEW.json",
               ("labels", "regime", "surprise", "state", "now"),
               "a macro release moved the state the book is conditioned on"),
        Source("regime_transition", DATA / "regime_state.json",
               ("current", "regime", "label", "state", "probs"),
               "the regime the worlds are drawn from changed"),
        Source("regime_transition", REPORTS / "REGIME_ROUTER.json",
               ("current", "route", "regime", "routed_to"),
               "the router changed which regime a sleeve is routed to"),
        Source("certificate_change", DATA / "sleeve_registry.json",
               ("sleeves",),
               "a certificate arrived or died: the roster the book solves over moved"),
        Source("fill", DATA / "gateway_state.json",
               ("position", "netting_booked", "brackets", "lot"),
               "a fill moved realised risk at the venue"),
        Source("cost_capacity_revision", REPORTS / "NET_EDGE.json",
               ("capacity_by_sleeve", "n_sign_flips", "ranked_if_net_were_the_only_ranking"),
               "net-of-cost or per-sleeve capacity was re-priced"),
    ]


def _read(p: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _signature(doc: dict[str, Any] | None, keys: tuple[str, ...]) -> str:
    """A hash of the DECISION-RELEVANT part only.

    Hashing the whole file would fire on every rewrite -- these artifacts all carry an `at` stamp
    that changes when nothing else does, so a whole-file hash would make every producer a trigger
    and the allocator would re-solve continuously on no new information.
    """
    if doc is None:
        return "absent"
    part = {k: doc.get(k) for k in keys if k in doc}
    if not part:
        return "no-watched-key"
    blob = json.dumps(part, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _event_at(doc: dict[str, Any] | None, p: Path) -> tuple[str, str]:
    """The artifact's OWN timestamp -- the instant the world changed, not the instant we looked.

    Latency measured from our own detection would flatter every number by exactly the poll
    interval, which is the part this organ controls and the part that matters least.
    """
    for field in ("at", "generated_utc", "measured_at", "as_of", "timestamp"):
        val = (doc or {}).get(field)
        if isinstance(val, str) and val.strip():
            return val, f"artifact field {field!r}"
    try:
        return (datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).isoformat(timespec="seconds"),
                "file mtime (the artifact carries no timestamp field)")
    except OSError:
        return datetime.now(tz=UTC).isoformat(timespec="seconds"), "absent artifact"


def _parse(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).timestamp()


def _heat_now() -> float | None:
    art = _read(ALLOCATION)
    if art is None:
        return None
    h = art.get("heat") or {}
    for k in ("resolved", "total", "heat_deployed"):
        try:
            return float(h[k])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _allocation_stamp() -> tuple[str | None, float | None]:
    art = _read(ALLOCATION)
    stamp = (art or {}).get("generated_utc")
    return (str(stamp) if stamp else None), _parse(stamp)


def _solve(budget_s: float) -> dict[str, Any]:
    """Fire the SAME solver the hourly leg fires, in its fast mode. Never in-process: the solver
    allocates heavily and a crash inside it must not take the watcher down with it."""
    started = time.time()
    try:
        r = subprocess.run(
            [sys.executable, "-u", str(DESK / "research" / "pf_allocator.py"),
             "--mode", "fast"],
            cwd=str(DESK), capture_output=True, text=True,
            timeout=max(60.0, float(budget_s)), check=False)
        return {"rc": int(r.returncode), "wall_s": round(time.time() - started, 2),
                "tail": ((r.stdout or "") + (r.stderr or ""))[-400:]}
    except subprocess.TimeoutExpired:
        return {"rc": None, "wall_s": round(time.time() - started, 2),
                "tail": f"TIMEOUT after {budget_s}s"}
    except OSError as exc:
        return {"rc": None, "wall_s": round(time.time() - started, 2),
                "tail": f"{type(exc).__name__}: {exc}"}


def poll(*, budget_s: float = 600.0, state: dict[str, Any] | None = None,
         write: bool = True, solve: bool = True) -> dict[str, Any]:
    """One pass: look at every source, fire once if anything moved, record what happened."""
    st = state if state is not None else (_read(STATE) or {})
    seen: dict[str, Any] = dict(st.get("seen") or {})
    fired: list[dict[str, Any]] = []
    watch: list[dict[str, Any]] = []
    now = time.time()
    last_solve = float(st.get("last_solve_at") or 0.0)

    changes: list[tuple[Source, dict[str, Any] | None, str]] = []
    for src in sources():
        doc = _read(src.path)
        sig = _signature(doc, src.keys)
        key = f"{src.kind}:{src.path.name}"
        prev = (seen.get(key) or {}).get("sig")
        moved = prev is not None and sig != prev
        event_at, basis = _event_at(doc, src.path)
        watch.append({"kind": src.kind, "path": str(src.path.relative_to(ROOT)).replace("\\", "/"),
                      "signature": sig, "previous": prev, "changed": bool(moved),
                      "event_at": event_at, "event_at_basis": basis, "why": src.why,
                      "first_seen": prev is None})
        seen[key] = {"sig": sig, "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
        if moved:
            changes.append((src, doc, event_at))

    debounced = bool(changes) and (now - last_solve) < MIN_SOLVE_GAP_S
    if changes and solve and not debounced:
        heat_before = _heat_now()
        _, alloc_before = _allocation_stamp()
        res = _solve(budget_s)
        alloc_stamp, alloc_after = _allocation_stamp()
        heat_after = _heat_now()
        landed = bool(alloc_after is not None
                      and (alloc_before is None or alloc_after > alloc_before))
        for src, _doc, event_at in changes:
            ev = _parse(event_at)
            fired.append({
                "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "kind": src.kind,
                "source": str(src.path.relative_to(ROOT)).replace("\\", "/"),
                "why": src.why,
                "event_at": event_at,
                "detected_at": datetime.fromtimestamp(now, tz=UTC).isoformat(timespec="seconds"),
                "allocation_at": alloc_stamp,
                # THE NUMBER THE PRINCIPAL ASKED FOR: the triggering artifact's own stamp to the
                # allocation that answered it. `None` when either side is unparseable, which is
                # UNMEASURED and not a zero.
                "latency_s": (round(alloc_after - ev, 2)
                              if (ev is not None and alloc_after is not None) else None),
                "detect_latency_s": round(now - ev, 2) if ev is not None else None,
                "solve_wall_s": res["wall_s"], "solver_rc": res["rc"],
                "allocation_landed": landed,
                "heat_before": heat_before, "heat_after": heat_after,
                # TWO-SIDED, MEASURED. A reaction reallocates; it must not shrink the book. This
                # is reported, never enforced -- the heat law owns the total and this organ has
                # no path to it.
                "heat_preserved": (None if (heat_before is None or heat_after is None)
                                   else bool(heat_after >= heat_before - 5e-4)),
                "note": res["tail"][-200:] if not landed else "",
            })
        last_solve = time.time()
    elif changes and debounced:
        for src, _doc, event_at in changes:
            fired.append({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                          "kind": src.kind,
                          "source": str(src.path.relative_to(ROOT)).replace("\\", "/"),
                          "event_at": event_at, "allocation_at": None, "latency_s": None,
                          "stood_down": "DEBOUNCED",
                          "why": f"a solve landed {now - last_solve:.0f}s ago "
                                 f"(< {MIN_SOLVE_GAP_S:.0f}s); this trigger is served by the "
                                 f"next pass, not dropped"})
    elif changes and not solve:
        for src, _doc, event_at in changes:
            fired.append({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                          "kind": src.kind,
                          "source": str(src.path.relative_to(ROOT)).replace("\\", "/"),
                          "event_at": event_at, "allocation_at": None, "latency_s": None,
                          "stood_down": "SOLVE_DISABLED", "why": "--no-solve: watch only"})

    st = {"seen": seen, "last_solve_at": last_solve,
          "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
    if write:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, indent=1, default=str) + "\n", encoding="utf-8")
        if fired:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as fh:
                for row in fired:
                    fh.write(json.dumps(row, default=str) + "\n")
    return {"watch": watch, "fired": fired, "state": st, "debounced": debounced}


def _tail(n: int = 400) -> list[dict[str, Any]]:
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def latency_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per trigger kind: how many, how fast, and the worst one -- so "not slow" is a number."""
    by: dict[str, list[float]] = {}
    last: dict[str, dict[str, Any]] = {}
    for r in rows:
        kind = str(r.get("kind") or "unknown")
        lat = r.get("latency_s")
        if isinstance(lat, (int, float)):
            by.setdefault(kind, []).append(float(lat))
        prev = last.get(kind)
        if prev is None or str(r.get("at") or "") >= str(prev.get("at") or ""):
            last[kind] = r
    out: dict[str, Any] = {}
    for kind in sorted(set(list(by) + list(last))):
        vals = sorted(by.get(kind) or [])
        out[kind] = {
            "n_fired": sum(1 for r in rows if str(r.get("kind")) == kind),
            "n_measured": len(vals),
            "median_latency_s": (vals[len(vals) // 2] if vals else None),
            "worst_latency_s": (vals[-1] if vals else None),
            "best_latency_s": (vals[0] if vals else None),
            "last_at": (last.get(kind) or {}).get("at"),
            "last_latency_s": (last.get(kind) or {}).get("latency_s"),
            "status": "MEASURED" if vals else "UNMEASURED",
            "why": ("" if vals else "fired but no allocation timestamp to measure against, or "
                    "no firing yet on this host"),
        }
    return out


def run(*, budget_s: float = 600.0, write: bool = True, solve: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    res = poll(budget_s=budget_s, write=write, solve=solve)
    rows = _tail()
    heats = [r for r in rows if r.get("heat_preserved") is False]
    rep = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "schema": 1,
        "watch": res["watch"],
        "n_watched": len(res["watch"]),
        "n_changed_this_pass": sum(1 for w in res["watch"] if w["changed"]),
        "fired_this_pass": res["fired"],
        "debounced": res["debounced"],
        "reaction_latency_by_kind": latency_report(rows),
        "recent": rows[-12:],
        "n_recorded": len(rows),
        "heat_reductions": len(heats),
        "heat_reduction_rows": heats[-4:],
        "poll_interval_s": DEFAULT_INTERVAL_S,
        "min_solve_gap_s": MIN_SOLVE_GAP_S,
        "backstop": ("the hourly `pf_allocator` leg still runs its full solve on its own "
                     "cadence; these reactions are added to it, never instead of it"),
        "boundary": ("fires the same solver with the same heat law. It sets no fraction, no cap "
                     "and no veto, and it cannot move the 20% heat floor or the 0.02-lot gold "
                     "floor; heat_before/heat_after are recorded so a reaction that shrank the "
                     "book would be visible as its own defect"),
        "elapsed_s": round(time.monotonic() - started, 3),
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        try:
            from libs.ops.events import leg_events
            leg_events("allocator_trigger", "OK", n_fired=len(res["fired"]),
                       n_changed=rep["n_changed_this_pass"], artifact=str(OUT))
        except Exception:                                      # pragma: no cover - events opt.
            pass
    return rep


def _print(rep: dict[str, Any]) -> None:
    print(f"ALLOCATOR TRIGGERS  watched={rep['n_watched']} changed={rep['n_changed_this_pass']} "
          f"fired={len(rep['fired_this_pass'])} recorded={rep['n_recorded']}")
    for k, v in (rep["reaction_latency_by_kind"] or {}).items():
        print(f"  {k:24} n={v['n_fired']:4} median={v['median_latency_s']}s "
              f"worst={v['worst_latency_s']}s last={v['last_latency_s']}s ({v['status']})")
    for f in rep["fired_this_pass"]:
        print(f"  FIRED {f['kind']}: latency={f.get('latency_s')}s "
              f"heat {f.get('heat_before')} -> {f.get('heat_after')} "
              f"{f.get('stood_down') or ''}")
    if rep["heat_reductions"]:
        print(f"  WARNING: {rep['heat_reductions']} recorded reaction(s) lowered total heat")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one poll (the scheduled leg shape)")
    ap.add_argument("--resident", action="store_true", help="poll forever (the 24/7 shape)")
    ap.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--no-solve", action="store_true",
                    help="watch and record, never fire the solver")
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.resident:
        # 24/7. The keep-alive task restarts this if the box reboots or the process dies; the
        # loop itself never exits on a bad pass, because a watcher that dies on one unreadable
        # artifact is a watcher that is not watching.
        deadline_interval = max(5.0, float(args.interval_s))
        while True:
            try:
                rep = run(budget_s=args.budget_s, write=not args.dry_run,
                          solve=not args.no_solve)
                if rep["fired_this_pass"]:
                    _print(rep)
            except Exception as exc:                           # pragma: no cover - resident
                print(f"allocator_trigger pass failed ({type(exc).__name__}: {exc}); "
                      f"the next poll retries in {deadline_interval:.0f}s", flush=True)
            time.sleep(deadline_interval)
    rep = run(budget_s=args.budget_s, write=not args.dry_run, solve=not args.no_solve)
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        _print(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
