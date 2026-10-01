"""BLOG / SOCIAL MINING -- Japanese, Korean and Chinese retail attention and mood, as deltas.

    python desks/mt5/research/blog_social_mining.py [--no-fetch] [--budget-s 110] [--dry-run]

ONE PASS: fetch every ground in `libs.data.blog_social_sources.SOURCES` (on the box; this cloud
container's proxy refuses these hosts), append every post NEVER SEEN BEFORE to the post store
with its `first_seen_at`, then rebuild the indices from the whole store:

    bot filter (duplicate text, near-identical posts, burst accounts)
      -> per-instrument daily attention and mood on the first-seen clock
      -> DELTAS against each instrument's own trailing 28 observed days

and publish the same signal to all three uses:

  indirect   desks/mt5/data/axes/blog_social.json   (`series[id].points [{d, v}]`, d = knowable)
  direct     desks/mt5/data/lake/series/blog_social_<SYMBOL>.parquet   (for exogenous_conditioner)
  allocation desks/mt5/reports/BLOG_SOCIAL_ALLOCATION_INTEL.json       (advisory crowd context)

OBSERVED DAYS ARE RECORDED, NOT ASSUMED. A UTC day enters the index only if at least one ground
answered OK that day (`observed_days.json`); a day the box was off is UNMEASURED, never a
zero-attention day that would read as a crowd going quiet.

THE STORE: `desks/mt5/data/text_store/blog_social/posts.jsonl` (titles and snippets only, the
same rule as every forest miner) and `seen.json` -- the (source, ident) cursor whose first stamp
is never moved. NOT under `data/intelligence/`: the candidate compiler globs that whole tree as
seat output, and raw post text is not a hypothesis. `text_store/` is gitignored; the store is
bounded by MAX_POSTS.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import blog_social_sources as bss  # noqa: E402
from libs.research import asia_alt_digest  # noqa: E402
from libs.research import social_mood as sm  # noqa: E402

STORE = DESK / "data" / "text_store" / "blog_social"
FEEDS_CFG = DESK / "data" / "blog_social_feeds.json"
AXIS_OUT = DESK / "data" / "axes" / "blog_social.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "BLOG_SOCIAL.json"
INTEL = DESK / "reports" / "BLOG_SOCIAL_ALLOCATION_INTEL.json"
SOURCE = "blog_social_mining"
SIGNALS = ("attention_delta_z", "mood_delta", "mood_delta_z", "attention_shock_signed")
MAX_POSTS = 400_000


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def _post_row(p: sm.Post) -> dict[str, Any]:
    row = asdict(p)
    row["first_seen_at"] = p.first_seen_at.isoformat()
    row["published_at"] = p.published_at.isoformat() if p.published_at else None
    return row


def load_posts(path: Path) -> list[sm.Post]:
    out: list[sm.Post] = []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()[-MAX_POSTS:]
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        seen = _ts(r.get("first_seen_at"))
        if not isinstance(r, dict) or seen is None or not r.get("title"):
            continue
        out.append(sm.Post(source=str(r.get("source") or ""), ident=str(r.get("ident") or ""),
                           title=str(r["title"]), first_seen_at=seen,
                           snippet=str(r.get("snippet") or ""), author=str(r.get("author") or ""),
                           url=str(r.get("url") or ""), lang=str(r.get("lang") or ""),
                           published_at=_ts(r.get("published_at"))))
    return out


# -------------------------------------------------------------------------------------- fetch
def fetch_pass(now: datetime, *, store: Path = STORE, get: bss.Getter | None = None,
               budget_s: float = 110.0, feeds_cfg: Path = FEEDS_CFG,
               sources: tuple[bss.SourceSpec, ...] = bss.SOURCES,
               pause_s: float = 1.5) -> dict[str, Any]:
    """Fetch every ground once, append NEW posts with `first_seen_at = now`, record postures."""
    seen: dict[str, str] = _read_json(store / "seen.json", {}) or {}
    cfg = _read_json(feeds_cfg, {}) or {}
    started = time.monotonic()
    postures: dict[str, Any] = {}
    new_rows: list[dict[str, Any]] = []
    for spec in sources:
        if time.monotonic() - started > budget_s:
            postures[spec.id] = {"posture": "NOT_REACHED", "why": "pass budget exhausted"}
            continue
        ids = [str(x) for x in (cfg.get(spec.id) or []) if str(x).strip()]
        got = bss.fetch(spec, now, get=get, feed_ids=ids, pause_s=pause_s)
        fresh = 0
        for p in got["posts"]:
            key = f"{p.source}|{p.ident}"
            if key in seen:
                continue
            seen[key] = now.isoformat()
            new_rows.append(_post_row(p))
            fresh += 1
        postures[spec.id] = {"posture": got["posture"], "n": got["n"], "new": fresh,
                             "calls": got["calls"], "errors": got["errors"]}
    store.mkdir(parents=True, exist_ok=True)
    if new_rows:
        with (store / "posts.jsonl").open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    _atomic(store / "seen.json", json.dumps(seen))
    ok = sorted(k for k, v in postures.items() if v.get("posture") == bss.POSTURE_OK)
    days: dict[str, Any] = _read_json(store / "observed_days.json", {}) or {}
    if ok:
        day = now.date().isoformat()
        prev = set((days.get(day) or {}).get("sources_ok") or [])
        days[day] = {"sources_ok": sorted(prev | set(ok)), "last_at": now.isoformat()}
        _atomic(store / "observed_days.json", json.dumps(days, sort_keys=True))
    return {"at": now.isoformat(timespec="seconds"), "new_posts": len(new_rows),
            "sources_ok": ok, "postures": postures}


# ------------------------------------------------------------------------------------ publish
def _frames(rows: list[sm.IndexRow]) -> dict[str, list[sm.IndexRow]]:
    by: dict[str, list[sm.IndexRow]] = {}
    for r in rows:
        by.setdefault(r.instrument, []).append(r)
    return by


def axis_doc(rows: list[sm.IndexRow], now: datetime) -> dict[str, Any]:
    block: dict[str, Any] = {}
    for inst, rs in _frames(rows).items():
        for sig in SIGNALS:
            pts = [{"d": r.available_time[:10], "v": getattr(r, sig),
                    "available_time": r.available_time, "period": r.day}
                   for r in rs if math.isfinite(getattr(r, sig))]
            if pts:
                block[f"{inst}.{sig}"] = {"what": f"{sig} of the {inst} retail crowd",
                                          "n": len(pts), "first": pts[0]["d"],
                                          "last": pts[-1]["d"], "points": pts}
    return {"axis": "retail_attention", "id": "blog_social", "source": SOURCE,
            "at": now.isoformat(timespec="seconds"), "n_series": len(block),
            "shape": "series[<SYMBOL>.<signal>].points [{d = knowable date, v}]",
            "pit": "posts count on the UTC day first SEEN; a day is knowable at next 00:00 UTC",
            "series": block}


def write_lake(rows: list[sm.IndexRow], series_dir: Path = SERIES_DIR) -> dict[str, int]:
    import pandas as pd

    out: dict[str, int] = {}
    for inst, rs in _frames(rows).items():
        frame = pd.DataFrame([asdict(r) for r in rs]).drop(columns=["instrument"])
        series_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(series_dir / f"blog_social_{inst}.parquet", index=False)
        out[inst] = len(frame)
    return out


def allocation_intel(rows: list[sm.IndexRow], now: datetime) -> dict[str, Any]:
    inst: dict[str, Any] = {}
    cut = now.isoformat()
    for sym, rs in _frames(rows).items():
        known = [r for r in rs if r.available_time <= cut]
        if not known:
            continue
        r = known[-1]
        shock = r.attention_shock_signed
        label = ("UNMEASURED" if not math.isfinite(shock)
                 else "crowd_chasing_up" if shock >= 1.5
                 else "crowd_chasing_down" if shock <= -1.5 else "normal")
        inst[sym] = {"day": r.day, "available_time": r.available_time, "n_posts": r.n_posts,
                     "attention_delta_z": _f(r.attention_delta_z), "mood_delta": _f(r.mood_delta),
                     "attention_shock_signed": _f(shock), "crowd_state": label}
    return {"generated_at": now.isoformat(timespec="seconds"), "source": SOURCE,
            "use": "allocation_intel", "authority": "none -- advisory crowd context, sizes nothing",
            "instruments": inst}


def _f(x: float) -> float | None:
    return round(x, 4) if math.isfinite(x) else None


def build(now: datetime, *, store: Path = STORE, axis_out: Path = AXIS_OUT,
          series_dir: Path = SERIES_DIR, intel_out: Path = INTEL,
          dry_run: bool = False) -> dict[str, Any]:
    posts = load_posts(store / "posts.jsonl")
    days = sorted((_read_json(store / "observed_days.json", {}) or {}).keys())
    kept, bots = sm.bot_filter(posts)
    rows = sm.daily_index(kept, observed_days=days, asof=now)
    rep = {"n_posts": len(posts), "n_kept": bots.n_kept, "bot_dropped": dict(bots.dropped),
           "observed_days": len(days), "index_rows": len(rows),
           "instruments": sorted({r.instrument for r in rows})}
    if not dry_run:
        _atomic(axis_out, json.dumps(axis_doc(rows, now)))
        rep["lake_rows"] = write_lake(rows, series_dir)
        _atomic(intel_out, json.dumps(allocation_intel(rows, now), indent=1))
    return rep


def run(now: datetime | None = None, *, fetch: bool = True, budget_s: float = 110.0,
        dry_run: bool = False, get: bss.Getter | None = None,
        digest_path: Path = asia_alt_digest.DIGEST) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds")}
    if fetch and not dry_run:
        rep["fetch"] = fetch_pass(now, get=get, budget_s=budget_s)
    else:
        rep["fetch"] = {"state": "SKIPPED", "why": "--no-fetch or --dry-run"}
    rep.update(build(now, dry_run=dry_run))
    rep["live_yield"] = (bss.UNMEASURED_LIVE_YIELD if not rep["fetch"].get("sources_ok")
                         else "MEASURED_THIS_PASS")
    if not dry_run:
        _atomic(REPORT, json.dumps(rep, indent=1, default=str))
        asia_alt_digest.publish(SOURCE, digest_section(rep), digest_path)
    return rep


def digest_section(rep: dict[str, Any]) -> dict[str, Any]:
    """This organ's section of the committed digest: posture per ground, index rows, bot drops.
    The gain verdicts for these indices are `nlp_social_cells`' section."""
    postures = (rep.get("fetch") or {}).get("postures") or {}
    ok = [s for s, v in postures.items() if v.get("posture") == bss.POSTURE_OK]
    return asia_alt_digest.section(
        at=str(rep.get("generated_at")), status=str(rep.get("live_yield")),
        rows=int(rep.get("index_rows") or 0), measured=ok,
        unmeasured=[s.id for s in bss.SOURCES if s.id not in ok], gain={},
        postures={s: str(v.get("posture")) for s, v in sorted(postures.items())},
        n_posts=int(rep.get("n_posts") or 0), n_kept=int(rep.get("n_kept") or 0),
        bot_dropped=dict(sorted((rep.get("bot_dropped") or {}).items())),
        gain_tested_by="nlp_social_cells")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--budget-s", type=float, default=110.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(fetch=not a.no_fetch, budget_s=a.budget_s, dry_run=a.dry_run)
    f = rep["fetch"]
    print(f"blog_social: new={f.get('new_posts', 0)} ok={f.get('sources_ok', [])} "
          f"posts={rep['n_posts']} kept={rep['n_kept']} dropped={rep['bot_dropped']} "
          f"days={rep['observed_days']} rows={rep['index_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
