"""THE BOX NEVER FILLS UP (principal 2026-11-25 02:49Z, PERMANENT).

"we dont want it to ever fill up have caps from growing wtv without reducing any research or
healing". Measured the same night: C: is 1,200 GB, spans the whole disk (no unallocated space to
extend into) and had 38.8 GB free (~97% used) -- while the guardian's only disk check fired at
5 GB, 0.4% of this volume, and libs/ops/disk.py's recorders pause at 80% used. Nothing measured
the box between the two, and nothing published a number Claude could read (stall_watch's last
free_gb was from 11-10).

WHAT THIS DOES, every guardian pass (15 min), box-natively:
  1. MEASURES every shared resource against its own early-warning line and publishes
     desks/mt5/reports/DISK_HEADROOM.json (free_gb, used_frac, days_to_pause, at) and
     desks/mt5/reports/BOX_HEADROOM.json (disk, RAM, CPU, MT5 terminals, LLM relay quotas).
  2. ACTS on disk only where the action cannot lose a fact:
       - derived caches (__pycache__, .pytest_cache, .mypy_cache, .ruff_cache, .hypothesis) are
         removed when the disk is past the warning line; they rebuild on demand;
       - log files over LOG_CAP_MB are ROLLED: compressed to <name>.<stamp>.gz beside the log
         (the bytes stay, smaller) and the live file restarts;
       - cold log files (untouched for COLD_DAYS) are compressed in place to .gz, verified by
         reading the archive back before the original goes.
     It NEVER deletes evidence (ledgers, reports, tape, data, logs' content) and never touches
     the tick tape at any threshold. Compression is the only thing it does to evidence.
  3. NEVER SHEDS research, healing or live trading. RAM, CPU, terminals and quotas are measured
     and alerted on; the only load the guardian itself sheds is its own (it stops compressing
     when the CPU is past its line).

If the disk keeps growing past what compression recovers, the honest fix is more storage
(Contabo disk upgrade) or moving cold evidence to a second volume: an ops action this module
names in its report with the days left, rather than pretending a deletion would be safe.

    python desks/mt5/research/box_headroom.py            # measure only
    python desks/mt5/research/box_headroom.py --apply    # measure + reclaim
"""
from __future__ import annotations

import contextlib
import gzip
import json
import os
import shutil
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DISK_FILE = "desks/mt5/reports/DISK_HEADROOM.json"
BOX_FILE = "desks/mt5/reports/BOX_HEADROOM.json"
#: Box-local growth history (one row per pass, the last HISTORY_KEEP kept) for days_to_pause.
HISTORY = "data/box_headroom_history.jsonl"
HISTORY_KEEP = 2000

#: EARLY WARNING: used fraction at which the guardian alerts AND starts reclaiming. It is below
#: libs/ops/disk.py's 80% recorder pause on purpose: act before the tape stops, not after.
DISK_WARN_FRAC = 0.75
#: Days of headroom (to the 80% pause) under which the disk is a fault even below the line.
DISK_WARN_DAYS = 14.0
#: RAM and CPU lines: research may use up to ~75% of the box (principal 02:58Z) on top of what
#: live needs; past these lines the box itself, live included, is at risk (OOM, starved ticks).
RAM_WARN_FRAC = 0.90
CPU_WARN_PCT = 95.0
#: MT5 terminals the box is sized for (E8, FTMO, Fusion and the research terminals); a count over
#: it means a duplicate launch is eating RAM and broker sessions.
TERMINAL_CAP = int(os.environ.get("QUANT_MT5_TERMINAL_CAP", "8") or 8)
#: A relay at this fraction of its daily cap is near a ban line; past 1.0 is a breach.
QUOTA_WARN_FRAC = 0.9

LOG_CAP_MB = 256
COLD_DAYS = 14
#: Where the box writes logs. Only *.log / *.txt / *.out files here are rolled or compressed.
LOG_DIRS = ("desks/mt5/logs", "logs", "data/logs")
EXTRA_LOG_DIRS = (r"C:\ProgramData\QuantBox\logs",)
LOG_SUFFIXES = (".log", ".txt", ".out", ".err")
DERIVED_DIRS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis")
#: Never walked, at any threshold: the tick tape and the venv/site-packages.
PROTECTED_PARTS = ("tape", ".git", ".venv", "site-packages")
#: Bound one pass's work so the guardian never becomes the load (15-min task, 12-min limit).
MAX_ACTIONS = 200


def _now() -> datetime:
    return datetime.now(UTC)


def _gb(n: float) -> float:
    return round(n / (1024 ** 3), 2)


def _protected(p: Path) -> bool:
    return any(part.lower() in PROTECTED_PARTS for part in p.parts)


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------- measurement

def disk(root: Path, now: datetime, *, usage: Callable[[str], Any] = shutil.disk_usage,
         history: Path | None = None) -> dict[str, Any]:
    u = usage(str(root))
    used_frac = u.used / max(1, u.total)
    hist = history or (root / HISTORY)
    rows: list[dict[str, Any]] = []
    with contextlib.suppress(OSError):
        for ln in hist.read_text("utf-8").splitlines()[-HISTORY_KEEP:]:
            with contextlib.suppress(ValueError):
                rows.append(json.loads(ln))
    growth = None
    old = next((r for r in rows if _age_days(r.get("at"), now) is not None
                and 1.0 <= (_age_days(r.get("at"), now) or 0) <= 8.0), None)
    if old is not None:
        days = _age_days(old.get("at"), now) or 1.0
        growth = (u.used - int(old.get("used", u.used))) / days
    pause_at = 0.80 * u.total
    headroom = max(0.0, min(pause_at - u.used, u.free))
    if u.used >= pause_at:
        days_to_pause: float | None = 0.0
    elif growth and growth > 0:
        days_to_pause = round(headroom / growth, 1)
    else:
        days_to_pause = None
    ok = used_frac < DISK_WARN_FRAC and (days_to_pause is None or days_to_pause >= DISK_WARN_DAYS)
    return {"total_gb": _gb(u.total), "free_gb": _gb(u.free), "used_frac": round(used_frac, 4),
            "warn_frac": DISK_WARN_FRAC, "pause_frac": 0.80,
            "growth_gb_per_day": None if growth is None else _gb(growth),
            "days_to_pause": days_to_pause, "ok": ok, "used": u.used,
            "why": ("holds" if ok else
                    f"{used_frac:.1%} used (line {DISK_WARN_FRAC:.0%}), "
                    f"days to the 80% recorder pause: {days_to_pause}")}


def _age_days(raw: Any, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return (now - t).total_seconds() / 86400


def _psutil() -> Any:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        return psutil
    except Exception:
        return None


def ram(ps: Any = None) -> dict[str, Any]:
    ps = ps or _psutil()
    if ps is None:
        return {"ok": True, "why": "UNMEASURED: psutil not installed here"}
    m = ps.virtual_memory()
    frac = m.percent / 100.0
    return {"total_gb": _gb(m.total), "available_gb": _gb(m.available), "used_frac": round(frac, 4),
            "warn_frac": RAM_WARN_FRAC, "ok": frac < RAM_WARN_FRAC,
            "why": "holds" if frac < RAM_WARN_FRAC else f"RAM {frac:.0%} used: OOM risk"}


def cpu(ps: Any = None) -> dict[str, Any]:
    ps = ps or _psutil()
    if ps is None:
        return {"ok": True, "why": "UNMEASURED: psutil not installed here"}
    pct = float(ps.cpu_percent(interval=0.5))
    return {"cores": ps.cpu_count(), "pct": pct, "warn_pct": CPU_WARN_PCT,
            "ok": pct < CPU_WARN_PCT,
            "why": "holds" if pct < CPU_WARN_PCT else f"CPU {pct:.0f}% busy"}


#: Live-trading processes (principal 2026-11-25 02:58Z: live always has priority, research may
#: use up to ~75% of the box). MT5-LivePriority raises them; this checks it held.
LIVE_NAMES = ("terminal64.exe",)
#: The share of the box research/judge/mining/data may take (CPU and RAM). Past it, live trading
#: must still be at raised priority; that, not a cut to research, is what protects the live side.
RESEARCH_SHARE = 0.75
_LIVE_OK_PRIORITIES = {"ABOVE_NORMAL_PRIORITY_CLASS", "HIGH_PRIORITY_CLASS",
                       "REALTIME_PRIORITY_CLASS"}


def _priority_name(ps: Any, value: Any) -> str:
    for name in ("IDLE_PRIORITY_CLASS", "BELOW_NORMAL_PRIORITY_CLASS", "NORMAL_PRIORITY_CLASS",
                 "ABOVE_NORMAL_PRIORITY_CLASS", "HIGH_PRIORITY_CLASS", "REALTIME_PRIORITY_CLASS"):
        if hasattr(ps, name) and getattr(ps, name) == value:
            return name
    return str(value)


#: The live recorders, by the script or module on their own command line.
LIVE_RECORDER_MARKS = (("tick_recorder", "recorders.tick_recorder"),
                       ("e8_spread_sampler", "e8_spread_sampler.py"),
                       ("moat_recorder", "moat_recorder.py"))


def _live_recorder(p: Any) -> str | None:
    """The recorder a python process is, by its own command line; None for anything else."""
    name = str(p.info.get("name") or "").lower()
    if not (name.startswith("python") or name.startswith("py")):
        return None
    try:
        args = [str(a).replace("\\", "/").lower() for a in (p.cmdline() or [])]
    except Exception:
        return None
    for label, mark in LIVE_RECORDER_MARKS:
        if any(a == mark or a.endswith("/" + mark) for a in args):
            return label
    return None


def terminals(ps: Any = None) -> dict[str, Any]:
    """MT5 terminal count against its cap, and every live process at raised priority."""
    ps = ps or _psutil()
    if ps is None:
        return {"ok": True, "why": "UNMEASURED: psutil not installed here"}
    n, live_mem = 0, 0
    low: list[str] = []
    rec_low: list[str] = []
    for p in ps.process_iter(["name", "pid"]):
        with contextlib.suppress(Exception):
            if str(p.info.get("name") or "").lower() not in LIVE_NAMES:
                # A LIVE RECORDER (tick tape, E8 spread sampler, moat recorder) must sit strictly
                # above every research class (Audit 2026-11-25 13:09Z), read by its command line.
                rec = _live_recorder(p)
                if rec and hasattr(ps, "ABOVE_NORMAL_PRIORITY_CLASS"):
                    prio = _priority_name(ps, p.nice())
                    if prio not in _LIVE_OK_PRIORITIES:
                        rec_low.append(f"{rec} pid {p.info.get('pid')} {prio}")
                continue
            n += 1
            prio = _priority_name(ps, p.nice())
            if hasattr(ps, "ABOVE_NORMAL_PRIORITY_CLASS") and prio not in _LIVE_OK_PRIORITIES:
                low.append(f"pid {p.info.get('pid')} {prio}")
            with contextlib.suppress(Exception):
                live_mem += int(p.memory_info().rss)
    why = []
    if n > TERMINAL_CAP:
        why.append(f"{n} MT5 terminals, cap {TERMINAL_CAP}")
    if low:
        why.append(f"live terminal(s) not at raised priority: {', '.join(low[:4])} "
                   "(MT5-LivePriority should hold them ABOVE_NORMAL)")
    if rec_low:
        why.append(f"live recorder(s) in a research priority class: {', '.join(rec_low[:4])} "
                   "(MT5-LivePriority should hold them ABOVE_NORMAL)")
    return {"count": n, "cap": TERMINAL_CAP, "below_priority": low,
            "recorders_below_priority": rec_low,
            "live_rss_gb": _gb(live_mem), "research_share_line": RESEARCH_SHARE,
            "ok": not why, "why": "; ".join(why) or "holds"}


#: LIVE OUTRANKS RESEARCH (coordinator for zuck 2026-11-25 17:36Z, PERMANENT). Box 11-25: the tick
#: tape went dark 12:54Z while the recorder ran BELOW_NORMAL beside ~60 research threads on an
#: ~85%-busy box, and MT5-LivePriority was never registered, so nothing noticed the inversion.
#: The rule: every live process (judge_priority.own_class == "live": terminals, gateway,
#: executors, recorders, guardian) runs at ABOVE_NORMAL, and no other python process sits at or
#: above the lowest live one. research_share is MEASURED (non-live python CPU over a short sample,
#: as a share of the whole box) and published against RESEARCH_SHARE; the scheduler, not a cut to
#: research, is what keeps live first, so the share alone is reported, and it is a fault only
#: when it coincides with a live process that has lost its class.
PRIORITY_SAMPLE_S = 1.0


def _jp() -> Any:
    desk = Path(__file__).resolve().parents[1]
    if str(desk) not in sys.path:
        sys.path.insert(0, str(desk))
    from scripts import judge_priority  # the one classifier of live vs research
    return judge_priority


def _label(jp: Any, name: str, cmd: list[Any]) -> str:
    named = sorted(jp._modules(cmd) | {a for a in jp._script_names(cmd)
                                       if a.endswith((".py", ".cmd"))})
    return named[0] if named else name.lower()


def priority(ps: Any = None, *, sample_s: float = PRIORITY_SAMPLE_S,
             sleep: Callable[[float], Any] | None = None) -> dict[str, Any]:
    """Every live process above every research process; research CPU share measured."""
    ps = ps or _psutil()
    if ps is None or not hasattr(ps, "ABOVE_NORMAL_PRIORITY_CLASS"):
        return {"ok": True, "why": "UNMEASURED: no Windows priority classes here"}
    jp = _jp()
    rows: list[tuple[Any, str, str, int | None, str]] = []
    for p in ps.process_iter(["name", "pid"]):
        with contextlib.suppress(Exception):
            name = str(p.info.get("name") or "")
            if not (jp._is_python(name) or name.lower() in jp._LIVE_NAMES):
                continue
            try:
                cmd = list(p.cmdline() or [])
            except Exception:
                cmd = []
            cls = jp.own_class(name, cmd) or "research"
            nice = p.nice()
            rows.append((p, cls, _priority_name(ps, nice), jp.rank_of(nice),
                         _label(jp, name, cmd)))
    target = jp.CLASS_RANK[jp.ABOVE_NORMAL]
    live = [r for r in rows if r[1] == "live"]
    others = [r for r in rows if r[1] != "live"]
    below = [f"{r[4]} pid {r[0].info.get('pid')} {r[2]}" for r in live
             if r[3] is not None and r[3] < target]
    floor = min((r[3] for r in live if r[3] is not None), default=None)
    inverted = [f"{r[4]} pid {r[0].info.get('pid')} {r[2]}" for r in others
                if floor is not None and r[3] is not None and r[3] >= floor]
    share = None
    with contextlib.suppress(Exception):
        for r in others:
            with contextlib.suppress(Exception):
                r[0].cpu_percent(None)
        (sleep or __import__("time").sleep)(sample_s)
        busy = 0.0
        for r in others:
            with contextlib.suppress(Exception):
                busy += float(r[0].cpu_percent(None))
        share = round(busy / (100.0 * max(1, int(ps.cpu_count() or 1))), 4)
    why = []
    if below:
        why.append(f"PRIORITY_INVERSION: live below ABOVE_NORMAL: {', '.join(below[:4])}")
    if inverted:
        why.append(f"PRIORITY_INVERSION: research at or above live: {', '.join(inverted[:4])}")
    if why and share is not None and share > RESEARCH_SHARE:
        why.append(f"research holds {share:.0%} of the box (line {RESEARCH_SHARE:.0%})")
    return {"live": len(live), "research": len(others), "live_below": below,
            "research_at_or_above_live": inverted, "research_share": share,
            "research_share_line": RESEARCH_SHARE, "ok": not why,
            "why": "; ".join(why) or "holds"}


def quotas(root: Path, now: datetime) -> dict[str, Any]:
    """Each LLM relay's calls today against its own daily cap (cn_ensemble's ledger)."""
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from libs.ops import cn_ensemble as cn
    except Exception as exc:
        return {"ok": True, "why": f"UNMEASURED: cn_ensemble not importable ({type(exc).__name__})"}
    relay_daily = int(os.environ.get("CN_ENSEMBLE_RELAY_DAILY", "240") or 240)
    rows, worst = {}, 0.0
    for p in cn.PROVIDERS:
        if not p.relay:
            continue
        cap = int(getattr(p, "daily_cap", 0) or relay_daily)
        used = cn._relay_calls_today(root, p.name, now)
        frac = used / max(1, cap)
        worst = max(worst, frac)
        rows[p.name] = {"calls_today": used, "cap": cap, "frac": round(frac, 3)}
    ok = worst <= 1.0
    return {"providers": rows, "worst_frac": round(worst, 3), "warn_frac": QUOTA_WARN_FRAC,
            "ok": ok, "near": [k for k, v in rows.items() if v["frac"] >= QUOTA_WARN_FRAC],
            "why": "holds" if ok else "a relay is past its daily cap (ban risk)"}


# ---------------------------------------------------------------- reclaim (disk only)

def _walk_dirs(top: Path, *, stop: tuple[str, ...] = ()):
    """Yield every directory under top, pruning protected dirs BEFORE descending, so the walk
    never enters the tape, .git or the venv (Audit SF 11-25). A dir named in stop is yielded
    and not descended into (a derived cache is removed whole, its insides need no walk)."""
    for dirpath, dirnames, _files in os.walk(top, onerror=lambda _e: None):
        keep = []
        for name in dirnames:
            if name.lower() in PROTECTED_PARTS:
                continue
            if name in stop:
                yield Path(dirpath) / name
                continue
            keep.append(name)
        dirnames[:] = keep
        yield Path(dirpath)


def _log_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for d in (*(root / x for x in LOG_DIRS), *(Path(x) for x in EXTRA_LOG_DIRS)):
        if not d.is_dir() or _protected(d):
            continue
        with contextlib.suppress(OSError):
            for sub in _walk_dirs(d):
                for f in sub.iterdir():
                    if f.is_file() and f.suffix.lower() in LOG_SUFFIXES and not _protected(f):
                        out.append(f)
    return out


def _gzip_verified(src: Path, dst: Path, n: int) -> bool:
    """Write exactly the first n bytes of src to dst and prove the archive reads back to n.
    Bytes a writer appends after the stat are not in the archive, so the caller may only drop
    the source if it is still exactly n bytes (Audit MF1 11-25)."""
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    left = n
    with src.open("rb") as fi, gzip.open(tmp, "wb", compresslevel=6) as fo:
        while left > 0 and (chunk := fi.read(min(left, 1 << 20))):
            fo.write(chunk)
            left -= len(chunk)
    got = 0
    with gzip.open(tmp, "rb") as fr:
        while chunk := fr.read(1 << 20):
            got += len(chunk)
    if left or got != n:
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, dst)
    return True


def reclaim(root: Path, now: datetime, *, past_line: bool, apply: bool) -> dict[str, Any]:
    acts: list[dict[str, Any]] = []
    freed = 0
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    for f in _log_files(root):
        if len(acts) >= MAX_ACTIONS:
            break
        try:
            st = f.stat()
        except OSError:
            continue
        age_d = (now.timestamp() - st.st_mtime) / 86400
        if st.st_size > LOG_CAP_MB * 1024 * 1024:
            kind, dst = "roll", f.with_name(f"{f.name}.{stamp}.gz")
        elif age_d >= COLD_DAYS and st.st_size > 64 * 1024:
            kind, dst = "compress_cold", f.with_name(f.name + ".gz")
        else:
            continue
        row = {"kind": kind, "path": str(f.relative_to(root)) if f.is_relative_to(root)
               else str(f), "mb": round(st.st_size / 1048576, 1)}
        if apply:
            try:
                if dst.exists() or not _gzip_verified(f, dst, st.st_size):
                    row["done"] = False
                else:
                    after = dst.stat().st_size
                    if kind == "roll":
                        with f.open("r+b") as fh:     # the writer keeps its handle
                            # re-stat on the open handle: only a file still exactly the
                            # archived size may be emptied, else appended lines would be lost
                            grew = os.fstat(fh.fileno()).st_size != st.st_size
                            if not grew:
                                fh.truncate(0)
                    else:
                        now_st = f.stat()
                        grew = (now_st.st_size, now_st.st_mtime) != (st.st_size, st.st_mtime)
                        if not grew:
                            f.unlink()
                    if grew:
                        dst.unlink()                  # a partial copy; the source is intact
                        row["done"] = False
                        row["why"] = "grew_after_copy"
                    else:
                        freed += st.st_size - after
                        row["done"] = True
            except OSError as exc:
                row["done"] = False
                row["why"] = type(exc).__name__
        acts.append(row)
    if past_line:
        for name in DERIVED_DIRS:
            if len(acts) >= MAX_ACTIONS:
                break
            with contextlib.suppress(OSError):
                for d in _walk_dirs(root, stop=(name,)):
                    if len(acts) >= MAX_ACTIONS:
                        break
                    if d.name != name or not d.is_dir() or _protected(d.relative_to(root)):
                        continue
                    size = sum(x.stat().st_size for x in d.rglob("*") if x.is_file())
                    row = {"kind": "derived_cache", "path": str(d.relative_to(root)),
                           "mb": round(size / 1048576, 1)}
                    if apply:
                        shutil.rmtree(d, ignore_errors=True)
                        row["done"] = not d.exists()
                        freed += size if row["done"] else 0
                    acts.append(row)
    return {"applied": apply, "actions": acts, "freed_gb": _gb(freed),
            "rule": "derived caches removed past the line; logs rolled/compressed, never "
                    "deleted; tape, data, ledgers and reports never touched"}


# ---------------------------------------------------------------- one pass

ACTIONS = "data/box_headroom_actions.jsonl"


def _count(acts: list[dict[str, Any]], done: bool) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in acts:
        if bool(a.get("done")) == done and ("done" in a or not done):
            out[a["kind"]] = out.get(a["kind"], 0) + 1
    return out

def run(root: Path = ROOT, now: datetime | None = None, *, apply: bool = False,
        usage: Callable[[str], Any] = shutil.disk_usage, ps: Any = None) -> dict[str, Any]:
    t = now or _now()
    d = disk(root, t, usage=usage)
    c = cpu(ps)
    rec = reclaim(root, t, past_line=not d["ok"], apply=apply and c.get("ok", True))
    if rec["freed_gb"]:
        d = disk(root, t, usage=usage)
    doc = {"schema": "box_headroom/1", "at": t.isoformat(timespec="seconds"), "disk": d,
           "ram": ram(ps), "cpu": c, "terminals": terminals(ps), "quotas": quotas(root, t),
           "priority": priority(ps),
           # the public file carries counts only; the per-file list stays box-local
           "reclaim": {"applied": rec["applied"], "freed_gb": rec["freed_gb"],
                       "done": _count(rec["actions"], True),
                       "not_done": _count(rec["actions"], False), "rule": rec["rule"]},
           "never": "research, healing and live trading are never shed; evidence is never "
                    "deleted (compressed only); the tick tape is never touched",
           "if_still_growing": "more storage (Contabo disk upgrade) or cold evidence to a "
                               "second volume: an ops action, named here with the days left"}
    doc["holds"] = all(bool(doc[k].get("ok", True)) for k in
                       ("disk", "ram", "cpu", "terminals", "quotas", "priority"))
    d_pub = {k: d[k] for k in ("free_gb", "total_gb", "used_frac", "days_to_pause",
                               "growth_gb_per_day", "warn_frac", "ok", "why")}
    with contextlib.suppress(OSError):
        _write_atomic(root / DISK_FILE, json.dumps({**d_pub, "at": doc["at"]}, indent=1) + "\n")
        _write_atomic(root / BOX_FILE, json.dumps(doc, indent=1, default=str) + "\n")
        hist = root / HISTORY
        lines: list[str] = []
        with contextlib.suppress(OSError):
            lines = hist.read_text("utf-8").splitlines()[-(HISTORY_KEEP - 1):]
        lines.append(json.dumps({"at": doc["at"], "used": d["used"]}))
        _write_atomic(hist, "\n".join(lines) + "\n")
        if rec["actions"]:
            with (root / ACTIONS).open("a", encoding="utf-8") as fh:
                for a in rec["actions"]:
                    fh.write(json.dumps({"at": doc["at"], **a}) + "\n")
    return doc


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    doc = run(apply="--apply" in args)
    print(json.dumps({k: doc[k] for k in ("at", "holds")} |
                     {k: doc[k].get("why") for k in ("disk", "ram", "cpu", "terminals", "quotas",
                                                     "priority")}
                     | {"freed_gb": doc["reclaim"]["freed_gb"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
