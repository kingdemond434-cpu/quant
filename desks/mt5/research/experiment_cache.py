#!/usr/bin/env python3
"""P39 / P40 -- THE EXPERIMENT CACHE AND THE SCALING-LAW LAB.

P39. An experiment is identified by everything that could change its answer, and by nothing else:

    data fingerprint   which rows, over which window, at which revision
    feature set        which inputs, in a canonical order
    model              the estimator and its hyper-parameters
    code               the SHA of the code that would run it
    seed               the draw

Anything outside that set -- the wall clock, the host, who asked -- must not change the key, or
the cache never hits. Anything inside it that is OMITTED is worse: the cache would then return a
result computed under different conditions, which is not a saved hour, it is a wrong answer
delivered instantly. That asymmetry is why the key is explicit and why a missing component is a
REFUSAL rather than a default.

CODE SHA IS IN THE KEY AND THAT IS THE POINT. The desk's most expensive recurring error is
believing a result that was computed by code which has since changed. A cache keyed without the
code SHA institutionalises exactly that: it would serve yesterday's number for today's estimator
forever, and it would look like a spectacular hit rate.

P40. THE SCALING-LAW LAB fits OOS skill against data, model size and compute -- and it exists to
answer a question this desk keeps guessing at: does the next increment BUY anything? A scaling
curve that has flattened means more data or more capacity is spend, not investment, and every
hour put there is an hour not spent on breadth. The fit is deliberately simple (a log-log slope
per axis) because the decision it supports is coarse: keep spending, or stop.

WHAT IS NEVER CLAIMED. A slope fitted on three points is reported WITH its n and its span, and
`sufficient` is False until both clear a stated floor. An exponent quoted from a handful of runs
is numerology, and numerology that recommends spending money is worse than no answer at all.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
CACHE = BASE / "data" / "experiment_cache.jsonl"
REPORT = BASE / "reports" / "EXPERIMENT_CACHE.json"

#: Every component of the key. A key missing one of these can collide across experiments that
#: are genuinely different, and a cache that collides returns a wrong answer instantly -- strictly
#: worse than no cache, because it is fast and confident.
KEY_PARTS: tuple[str, ...] = ("data", "features", "model", "code_sha", "seed")

#: A scaling slope needs at least this many runs, spanning at least this many doublings, before
#: it is allowed to call itself sufficient. Both floors, not either: five points inside one
#: doubling describe noise, and two points three doublings apart describe a line through two dots.
MIN_SCALING_RUNS = 6
MIN_SCALING_DOUBLINGS = 2.0


@dataclass(frozen=True)
class Experiment:
    """Everything that could change the answer. Nothing that could not."""

    data: str
    features: tuple[str, ...]
    model: str
    code_sha: str
    seed: int
    #: Recorded, never keyed. Changing the host or the hour must not miss the cache.
    context: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        canon = json.dumps({
            "data": self.data,
            # SORTED. The same feature set in a different order is the same experiment, and a key
            # sensitive to list order would miss on every re-run for no reason at all.
            "features": sorted(self.features),
            "model": self.model,
            "code_sha": self.code_sha,
            "seed": int(self.seed),
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest()[:32]


def missing_parts(e: Experiment) -> list[str]:
    """Which key components are absent. A cache lookup with any of these is REFUSED.

    Defaulting a missing component would produce a key that matches experiments run under
    different conditions -- a wrong answer served instantly, which is the one failure mode a
    cache must never have.
    """
    out = []
    if not str(e.data).strip():
        out.append("data -- no fingerprint of which rows, window or revision were used")
    if not e.features:
        out.append("features -- an experiment with no named inputs cannot be reproduced")
    if not str(e.model).strip():
        out.append("model -- the estimator and its hyper-parameters are part of the answer")
    if not str(e.code_sha).strip():
        out.append("code_sha -- without it the cache serves results computed by code that has "
                   "since changed, which is this desk's most expensive recurring error")
    if not isinstance(e.seed, int):
        out.append("seed -- the draw is part of the result")
    return out


def code_sha(root: Path | None = None) -> str:
    """The SHA the experiment would run at, or a marker that says it is unknown.

    UNKNOWN IS NOT BLANK. A blank would silently key every dirty tree identically; the marker
    makes such an entry refuse to be cached at all, which is the correct behaviour -- a result
    from a tree nobody can name is not reusable evidence.
    """
    try:
        r = subprocess.run(["git", "-C", str(root or ROOT), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10, check=False)
        sha = (r.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
    if not sha:
        return ""
    try:
        d = subprocess.run(["git", "-C", str(root or ROOT), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=15, check=False)
        if (d.stdout or "").strip():
            # A DIRTY TREE IS NOT A CACHEABLE IDENTITY. Two different working trees share a HEAD,
            # so caching against it would serve one tree's result to the other.
            return f"{sha}-dirty"
    except (OSError, subprocess.SubprocessError):
        return f"{sha}-unknown"
    return sha


def _rows(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or CACHE
    out = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        return []
    return out


def lookup(e: Experiment, path: Path | None = None) -> tuple[dict[str, Any] | None, str]:
    """(result, why). A refusal explains itself; a miss is not a refusal."""
    bad = missing_parts(e)
    if bad:
        return None, "REFUSED: " + "; ".join(bad)
    if "-dirty" in e.code_sha or "-unknown" in e.code_sha:
        return None, (f"REFUSED: code_sha {e.code_sha!r} does not identify a tree -- two working "
                      "trees share a HEAD, so a result cached against it could be served to the "
                      "wrong one")
    k = e.key()
    for row in reversed(_rows(path)):
        if row.get("key") == k:
            return row.get("result"), f"HIT {k}"
    return None, f"MISS {k}"


def store(e: Experiment, result: dict[str, Any], seconds: float,
          path: Path | None = None) -> tuple[bool, str]:
    """Record a result under its key. Refuses the same cases lookup refuses."""
    bad = missing_parts(e)
    if bad:
        return False, "REFUSED: " + "; ".join(bad)
    if "-dirty" in e.code_sha or "-unknown" in e.code_sha:
        return False, f"REFUSED: code_sha {e.code_sha!r} does not identify a tree"
    p = path or CACHE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "key": e.key(), "data": e.data, "features": sorted(e.features), "model": e.model,
            "code_sha": e.code_sha, "seed": e.seed, "result": result,
            "seconds": float(seconds), "context": e.context,
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
        }, default=str) + "\n")
    return True, f"STORED {e.key()}"


def _slope(xs: list[float], ys: list[float]) -> float | None:
    """Least-squares slope in log-log space. None when the axis does not actually vary."""
    pts = [(math.log(x), y) for x, y in zip(xs, ys, strict=False) if x and x > 0]
    if len(pts) < 3:
        return None
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    if den <= 1e-12:
        return None
    return sum((p[0] - mx) * (p[1] - my) for p in pts) / den


def scaling(axis: str, path: Path | None = None) -> dict[str, Any]:
    """P40. Fit OOS skill against one axis, and say honestly whether the fit means anything."""
    rows = [r for r in _rows(path)
            if isinstance((r.get("result") or {}).get("oos_skill"), (int, float))
            and isinstance((r.get("context") or {}).get(axis), (int, float))]
    xs = [float(r["context"][axis]) for r in rows]
    ys = [float(r["result"]["oos_skill"]) for r in rows]
    doublings = (math.log2(max(xs) / min(xs)) if xs and min(xs) > 0 else 0.0)
    s = _slope(xs, ys)
    enough = len(rows) >= MIN_SCALING_RUNS and doublings >= MIN_SCALING_DOUBLINGS
    return {
        "axis": axis, "runs": len(rows), "doublings_spanned": round(doublings, 2),
        "log_slope": None if s is None else round(s, 5),
        "sufficient": bool(enough and s is not None),
        "verdict": (
            f"needs {MIN_SCALING_RUNS} runs over {MIN_SCALING_DOUBLINGS} doublings; have "
            f"{len(rows)} over {doublings:.1f}. An exponent from this is numerology, and "
            "numerology that recommends spending money is worse than no answer"
            if not enough else
            f"slope {s:+.4f} per e-fold of {axis}: "
            + ("still buying skill -- keep spending" if (s or 0) > 0.01 else
               "flat -- more of this axis is spend, not investment; the hour goes further on "
               "breadth")),
    }


def report(path: Path | None = None) -> dict[str, Any]:
    rows = _rows(path)
    hits = sum(1 for r in rows if r.get("replayed"))
    saved = sum(float(r.get("seconds") or 0) for r in rows if r.get("replayed"))
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entries": len(rows),
        "distinct_keys": len({r.get("key") for r in rows}),
        "replays": hits,
        "hours_saved": round(saved / 3600.0, 2),
        "key_parts": list(KEY_PARTS),
        "scaling": {a: scaling(a, path) for a in ("rows", "params", "compute_seconds")},
        "why_code_sha": ("The desk's most expensive recurring error is believing a result "
                         "computed by code that has since changed. A cache keyed without the "
                         "code SHA institutionalises it, and does so behind a spectacular "
                         "hit rate."),
    }


def main(argv: list[str] | None = None) -> int:
    doc = report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"experiment cache: {doc['entries']} entr(ies), {doc['distinct_keys']} distinct key(s), "
          f"{doc['replays']} replay(s), {doc['hours_saved']}h saved")
    for axis, s in doc["scaling"].items():
        print(f"   {axis:16} runs={s['runs']:<4} span={s['doublings_spanned']:<5} "
              f"{'slope ' + str(s['log_slope']) if s['sufficient'] else 'INSUFFICIENT'}")
    if not doc["entries"]:
        print("   EMPTY -- no experiment has been recorded, so nothing can be replayed and no "
              "scaling law can be fitted. This is a gap, not a clean cache.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
