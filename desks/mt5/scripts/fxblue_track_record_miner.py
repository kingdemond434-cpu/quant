"""FX Blue public track-record miner -- MT5-native black-box reverse-engineering corpus.

RESEARCH.md §4 (track-record / winner-forensics ground). Universe: MT5/Fusion only.

ROUTES (all keyless, §13-clean: www.fxblue.com robots is `Allow: /`, api.fxblue.com has no
robots.txt; internal research only, never redistribution -- OP-096: robots is not a reuse grant).

  population : Wayback CDX over `fxblue.com/users/*`  -> 5,077 handles (2026-08-27)
  liveness   : api.fxblue.com/strivewidget.aspx?displayUserId=<u>   (52KB live / 88b dead)
  headline   : api.fxblue.com/wl/view.aspx?id=<u>&mode=overview&isinline=1
  mechanism  : api.fxblue.com/wl/charts/<chart>.aspx?id=<u>   -- 51 charts, numbers are
               literal in a Google-Charts `addRows([...])` block.

The mechanism charts are the point: hour-of-day (session bias), symbol (instrument set),
duration (holding time), direction, day-of-week and lots (sizing) reconstruct a published
trader's MECHANISM without ever copying a trade -- which is what §4 asks for.

Every extracted mechanism becomes a PREREGISTERED HYPOTHESIS in the desk's own families and
enters the unchanged ten gates. Leaderboard populations are maximally survivorship-biased
(RESEARCH §4, master 23): this corpus is a hypothesis SOURCE, never evidence of an edge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "data" / "intelligence" / "fxblue"
API = "https://api.fxblue.com"
CDX = (
    "http://web.archive.org/cdx/search/cdx?url=fxblue.com/users/*"
    "&output=text&fl=original&collapse=urlkey&limit=40000&filter=statuscode:200"
)
UA = "Mozilla/5.0 (compatible; quant-desk research; contact zararsyedv8@gmail.com)"

# The mechanism-bearing subset. Kept SMALL and named: each entry is here because it
# reconstructs one axis of a black box (§4), not because the site offers it.
MECHANISM_CHARTS = {
    "ch_hourprofit": "session bias -- net profit by hour of day",
    "ch_hourtrades": "session bias -- trade count by hour of day",
    "ch_symbolprofit": "instrument set -- net profit by symbol",
    "ch_symboltrades": "instrument set -- trade count by symbol",
    "ch_directionprofit": "long/short asymmetry",
    "ch_dowprofit": "day-of-week seasonality",
    "ch_tradedurationprofit": "holding-time structure vs profitability",
    "ch_balancedrawdown": "drawdown geometry",
    "ch_lotstradedmonthly_bysymbol": "sizing habits by instrument",
    "ch_cumulativeprofit": "equity curve",
}

# `addRows([ ... ])` -- Google Charts literal. Rows are ["label", number] or [number, number].
_ROWS = re.compile(r"addRows\(\s*(\[.*?\])\s*\)\s*;", re.S)
_ROW = re.compile(r"\[\s*(?:\"([^\"]*)\"|(-?[\d.]+))\s*,\s*(-?[\d.eE+]+)")
_COL = re.compile(r"data\.addColumn\(\s*'(\w+)'\s*,\s*\"([^\"]*)\"")


def _get(url: str, timeout: int = 25) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return str(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def enumerate_population(cache: Path) -> list[str]:
    """Wayback CDX is the POPULATION ENUMERATOR. FX Blue's own sitemap lists exactly one
    user (`/users/example`), so the site itself offers no population route -- the archive's
    URL index does. This is the generalisable operator, not an FX Blue quirk."""
    if cache.exists():
        return [ln for ln in cache.read_text().split("\n") if ln]
    raw = _get(CDX, timeout=240) or ""
    users = sorted({m.group(1).lower() for m in re.finditer(r"fxblue\.com/users/([A-Za-z0-9_\-]+)", raw)})
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(users))
    return users


def parse_chart(html: str) -> dict[str, Any] | None:
    """Return {label: value} from the addRows literal, plus the declared column names.

    Returns None (never {}) when the block is absent -- an unparsed chart and an
    empty chart are different facts and the caller must not collapse them (L1.28a)."""
    m = _ROWS.search(html)
    if not m:
        return None
    rows: list[tuple[str, float]] = []
    for r in _ROW.finditer(m.group(1)):
        label = r.group(1) if r.group(1) is not None else r.group(2)
        try:
            rows.append((str(label), float(r.group(3))))
        except ValueError:
            continue
    return {"columns": [c[1] for c in _COL.findall(html)], "rows": rows}


def parse_overview(html: str) -> dict[str, Any]:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    out: dict[str, Any] = {}
    for key, pat in (
        ("balance", r"Balance:\s*([\d,\-.]+)"),
        ("equity", r"Equity:\s*([\d,\-.]+)"),
        ("closed_profit", r"Closed profit:\s*\+?(-?[\d,.]+)"),
    ):
        mm = re.search(pat, text)
        if mm:
            try:
                out[key] = float(mm.group(1).replace(",", ""))
            except ValueError:
                pass
    for key, pat in (
        ("currency", r"\(([A-Z]{3})\)"),
        ("account_type", r"Account type:\s*(\w+)"),
        ("last_update", r"Last update:\s*([\d/]+)"),
    ):
        mm = re.search(pat, text)
        if mm:
            out[key] = mm.group(1)
    return out


def _has_data(rec: dict[str, Any]) -> bool:
    """A record is mineable only if some mechanism chart carries a NON-ZERO number."""
    for parsed in rec.get("charts", {}).values():
        for _, value in parsed.get("rows") or []:
            if value:
                return True
    ov = rec.get("overview") or {}
    return bool(ov.get("closed_profit") or ov.get("balance"))


def harvest_user(user: str, delay: float) -> dict[str, Any]:
    rec: dict[str, Any] = {"user": user, "charts": {}}
    widget = _get(f"{API}/strivewidget.aspx?displayUserId={user}")
    # A dead/never-populated account returns ~88 bytes. That is a real status, not an error.
    if widget is None:
        rec["status"] = "fetch_failed"
        return rec
    if len(widget) < 2000:
        rec["status"] = "dead"
        rec["bytes"] = len(widget)
        return rec
    # BYTES ARE NOT CONTENT. A 52KB widget is only the page SHELL: the 2026-08-27 first harvest
    # graded 95/120 "live" at offset 400 and every one of them carried zeros -- the block is a
    # bulk-registered `22-*` series with balance 0.0 and no trades. Liveness is decided BELOW,
    # from whether the mechanism charts contain a non-zero number, never from the byte count.
    rec["status"] = "shell"
    uid = (re.search(r'glbUserId\s*=\s*"([^"]+)"', widget) or [None, user])[1]
    rec["user_id"] = uid
    time.sleep(delay)
    ov = _get(f"{API}/wl/view.aspx?id={uid}&mode=overview&isinline=1")
    if ov:
        rec["overview"] = parse_overview(ov)
    for chart in MECHANISM_CHARTS:
        time.sleep(delay)
        html = _get(f"{API}/wl/charts/{chart}.aspx?id={uid}")
        if html is None:
            continue
        parsed = parse_chart(html)
        if parsed is not None:
            rec["charts"][chart] = parsed
    # THE REAL LIVENESS TEST: usable output. `has_data` and `shell` are different facts and the
    # consumer must never collapse them -- a shell is a real account with nothing to mine, which
    # is neither a fetch failure nor a mineable record.
    rec["status"] = "has_data" if _has_data(rec) else "shell"
    return rec


def compact_latest(path: Path) -> tuple[int, int, int, int]:
    """Keep only the NEWEST record per handle. Returns (rows_in, rows_out, bytes_in, bytes_out).

    The rotation is a CYCLE (L1.61), so every lap re-harvests the whole population and the
    artifact grows without bound even once the quadratic republication bug above is fixed: one
    lap is ~5,077 records (~210 MB) every ~3.5 days on the hourly timer, which fills the
    remaining disk in about six weeks. A track record has no history worth keeping per lap --
    the newest snapshot per handle strictly dominates every older one -- so compaction is
    lossless for the reader and bounds the artifact at exactly one lap.

    Two streaming passes and a dict of ~5k offsets: never loads the artifact into memory, which
    matters because this service runs under MemoryHigh=320M and the old publish step read a
    151 MB staging file with `read_text()`.
    """
    if not path.exists():
        return (0, 0, 0, 0)
    bytes_in = path.stat().st_size
    last: dict[str, int] = {}
    rows_in = 0
    with path.open("rb") as fh:
        while True:
            off = fh.tell()
            line = fh.readline()
            if not line:
                break
            rows_in += 1
            try:
                user = json.loads(line).get("user")
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(user, str):
                last[user] = off
    tmp = path.with_suffix(path.suffix + ".compact")
    rows_out = 0
    with path.open("rb") as src, tmp.open("wb") as dst:
        for off in sorted(last.values()):
            src.seek(off)
            dst.write(src.readline())
            rows_out += 1
    tmp.replace(path)
    return (rows_in, rows_out, bytes_in, path.stat().st_size)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=50, help="accounts to harvest this run")
    ap.add_argument("--offset", type=int, default=0, help="rotation cursor into the population")
    ap.add_argument("--stride", type=int, default=1, help="sample every Nth handle -- the population is "
                    "BLOCK-STRUCTURED (contiguous bulk-registered runs like `22-*`), so a contiguous "
                    "slice measures one block, not the population")
    ap.add_argument("--delay", type=float, default=0.35, help="seconds between requests (politeness)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cursor-file", default=None, help="UNATTENDED ROTATION (L1.61: coverage is a "
                    "CYCLE, not a sweep). Position into a deterministic stride-7 interleave of the "
                    "whole population; advanced by --limit after a successful run, wrapped at the "
                    "end, so repeated timer firings cover 100% and then start over on newer data. "
                    "Overrides --offset/--stride.")
    ap.add_argument("--compact", action="store_true", help="after publishing, keep only the "
                    "NEWEST record per handle in --out. Bounds the artifact at one lap of the "
                    "rotation; lossless, since a newer track-record snapshot dominates an older.")
    ap.add_argument("--compact-only", action="store_true",
                    help="compact --out and exit; no harvest")
    args = ap.parse_args()

    if args.compact_only:
        target = Path(args.out) if args.out else OUT / "track_records.jsonl"
        ri, ro, bi, bo = compact_latest(target)
        print(f"compacted {target}: rows {ri} -> {ro}, bytes {bi} -> {bo}")
        return 0

    # WRITE OUTSIDE THE TRACKED TREE, PUBLISH AT THE END (defect found 2026-08-28, live).
    # `desks/mt5/data/` is git-TRACKED and this box's automation (auto_push every 10 minutes, the
    # hourly cycle) checks files out from under long-running processes. A harvest appending here
    # for 30 minutes had its output file UNLINKED and replaced by a stale snapshot mid-run: both
    # workers kept writing happily into orphaned inodes -- `/proc/<pid>/fd/N -> ...(deleted)` --
    # and 22 of 50 harvested records existed nowhere a reader could find them. Nothing errored.
    # The staging file lives outside the repo and is appended there; the tracked artifact is
    # written ONCE, at the end, so the window in which a checkout can eat it is a single rename.
    OUT.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(os.environ.get("FXBLUE_STAGE", "/home/quant/fxblue_scratch"))
    stage_dir.mkdir(parents=True, exist_ok=True)
    pop = enumerate_population(OUT / "population.txt")
    print(f"population: {len(pop)} handles")
    cursor_path = Path(args.cursor_file) if args.cursor_file else None
    if cursor_path is not None:
        # The population is BLOCK-STRUCTURED (contiguous bulk-registered `22-*` runs), so a
        # contiguous slice measures one block. Concatenating the seven stride-7 lanes gives a
        # PERMUTATION of the whole population that is block-spread inside every window -- so any
        # cursor slice is a spread sample AND the cycle still reaches every handle exactly once.
        perm = [u for off in range(7) for u in pop[off::7]]
        start = 0
        if cursor_path.exists():
            try:
                raw_cur = json.loads(cursor_path.read_text()).get("cursor", 0)
                start = int(raw_cur) % max(len(perm), 1)
            except (ValueError, OSError, json.JSONDecodeError):
                start = 0
        batch = perm[start : start + args.limit]
        if len(batch) < args.limit:  # wrap: the cycle restarts rather than stalling at the end
            batch += perm[: args.limit - len(batch)]
        print(f"cursor: {start}/{len(perm)} (lap {start // max(len(perm), 1)})")
    else:
        batch = pop[args.offset :: args.stride][: args.limit]
    out_path = Path(args.out) if args.out else OUT / "track_records.jsonl"
    # PER-RUN STAGING (defect measured 2026-09-04, live). The staging path used to be a single
    # fixed name opened in APPEND mode, and the publish step appended the WHOLE staging file to
    # the tracked artifact. So run N republished every row from runs 1..N: growth was QUADRATIC,
    # not linear. Measured: the timer's runs produced 99,180 rows for 4,805 distinct handles
    # (60*(1+2+...+57) = 99,180 exactly) and 4.0 GB on a disk with 2.7 GB free -- roughly 15 more
    # hourly runs from filling the disk and taking every organ on this box down with it.
    # A per-run staging name keeps the orphan-safe replay property the fixed name was written for
    # (rows still land outside the tracked tree first, and a crashed run is still replayable from
    # its own file) while publishing exactly the rows THIS run harvested.
    stage_path = stage_dir / f"{out_path.name}.{os.getpid()}.{int(time.time())}.staging"

    has_data = shell = dead = failed = 0
    # ORPHAN-SAFE: `stage_path` is outside the tracked tree by construction and the tracked
    # artifact is written in one pass below, which is the repair this fence looks for.
    with stage_path.open("a", encoding="utf-8") as fh:
        for i, user in enumerate(batch, 1):
            rec = harvest_user(user, args.delay)
            rec["harvested_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            has_data += rec["status"] == "has_data"
            shell += rec["status"] == "shell"
            dead += rec["status"] == "dead"
            failed += rec["status"] == "fetch_failed"
            if i % 10 == 0:
                print(f"  {i}/{len(batch)} data={has_data} shell={shell} dead={dead} failed={failed}", flush=True)
            time.sleep(args.delay)

    # Publish: append the staged rows to the tracked artifact in one pass. If a checkout races
    # THIS, the staging file still holds every row and the run is replayable -- which is exactly
    # what the orphaned-inode failure destroyed.
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(stage_path.read_text(encoding="utf-8"))
    print(f"published {stage_path} -> {out_path}")

    if args.compact:
        ri, ro, bi, bo = compact_latest(out_path)
        print(f"compacted {out_path}: rows {ri} -> {ro}, bytes {bi} -> {bo}")

    if cursor_path is not None:
        # Advance ONLY after publication -- a cursor advanced before the write turns a crashed run
        # into permanently skipped ground, which is the silent-coverage-hole class (L1.51).
        nxt = (start + args.limit) % max(len(perm), 1)
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cursor_path.write_text(json.dumps(
            {"cursor": nxt, "population": len(perm), "advanced_utc": stamp}))
        print(f"cursor advanced -> {nxt}/{len(perm)}")

    print(f"DONE offset={args.offset} n={len(batch)} data={has_data} shell={shell} dead={dead} failed={failed} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
