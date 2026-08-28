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
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return r.read().decode("utf-8", "replace")
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=50, help="accounts to harvest this run")
    ap.add_argument("--offset", type=int, default=0, help="rotation cursor into the population")
    ap.add_argument("--stride", type=int, default=1, help="sample every Nth handle -- the population is "
                    "BLOCK-STRUCTURED (contiguous bulk-registered runs like `22-*`), so a contiguous "
                    "slice measures one block, not the population")
    ap.add_argument("--delay", type=float, default=0.35, help="seconds between requests (politeness)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

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
    batch = pop[args.offset :: args.stride][: args.limit]
    out_path = Path(args.out) if args.out else OUT / "track_records.jsonl"
    stage_path = stage_dir / f"{out_path.name}.staging"

    has_data = shell = dead = failed = 0
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

    print(f"DONE offset={args.offset} n={len(batch)} data={has_data} shell={shell} dead={dead} failed={failed} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
