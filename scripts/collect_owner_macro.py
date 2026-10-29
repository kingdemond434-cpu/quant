"""The public-domain owners' own macro feeds -> `data/owner_macro.json` (box-local, gitignored).

FRED/ALFRED is held as an input to fitted models (coordinator ruling on prohibition (j),
2026-10-07). This collector reads the same series from the agencies that publish them -- the US
Treasury yield curves (no key), BLS CPI-U (BLS_API_KEY) and the EIA Weekly Petroleum Status Report
(EIA_API_KEY) -- see `libs/data/owner_feeds.py` for the series, the clocks and the archive shape.

FAIL SOFT, NEVER ZERO. Each feed (and each EIA series, each Treasury year) is fetched on its own;
one that fails keeps the rows the archive already held and is named FAILED in `feeds`, so a dead
host never erases history and never kills the rest. No key -> that feed is NO_KEY (UNMEASURED),
never an empty series. Always exits 0: the leg reports, the cycle stays green.

Keys are read the way the desk reads every key (`libs.ops.env_secret.lookup`); no key is ever
printed, logged or written. Errors are reported by type and HTTP code only, because an EIA URL
carries its key in the query string.

Run by the hourly `fred_macro` leg (`research/hourly_cycle.py`) when the archive is older than
`OWNER_REFRESH_S`; by hand:

    python scripts/collect_owner_macro.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.data import owner_feeds as of  # noqa: E402

#: This organ's artifact (the same path as `owner_feeds.ARCHIVE`, bound here so the component
#: registry reads it from the source): box-local and gitignored, like data/fred_macro.json.
OUT = _ROOT / "data" / "owner_macro.json"

_UA = {"User-Agent": "quant-owner-macro/1.0 (public-domain statistics; contact via repository)"}
Fetch = Callable[[str, dict[str, Any] | None], bytes]


def _http(url: str, body: dict[str, Any] | None = None) -> bytes:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = dict(_UA, **({"Content-Type": "application/json"} if body is not None else {}))
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return bytes(r.read())


def _err(exc: BaseException) -> str:
    """Type and HTTP code only -- never str(exc), which can carry a URL with a key in it."""
    code = getattr(exc, "code", None)
    return f"{type(exc).__name__}{f' {code}' if code else ''}"


def _keys() -> dict[str, str | None]:
    from libs.ops.env_secret import lookup
    sec = _ROOT / "data" / "secrets"
    return {"bls": lookup(of.BLS_KEY_NAMES, (sec / "bls.json",))[0],
            "eia": lookup(of.EIA_KEY_NAMES, (sec / "eia.json",))[0]}


def _years_needed(prev: dict[str, Any], anchor: str, now: datetime) -> list[int]:
    """This year first (and last year in January, when its final days may still be landing),
    then every year from TREASURY_FIRST_YEAR the archive's `anchor` series lacks, newest first."""
    have = {str(r[0])[:4] for r in (prev.get(anchor) or [])}
    years = [now.year] + ([now.year - 1] if now.month == 1 else [])
    years += [y for y in range(now.year - 1, of.TREASURY_FIRST_YEAR - 1, -1)
              if str(y) not in have and y not in years]
    return years


#: Consecutive failures after which a curve's remaining years are skipped this pass: a dead host
#: would otherwise cost one timeout per backfill year.
MAX_CONSECUTIVE_FAILS = 2


def collect(fetch: Fetch, keys: dict[str, str | None], now: datetime,
            prev_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """The archive document, from `prev_doc` plus whatever each feed returned this pass."""
    prev = dict((prev_doc or {}).get("series") or {})
    seen_at = now.isoformat(timespec="seconds")
    fresh: dict[str, dict[str, float]] = {}
    feeds: dict[str, Any] = {}

    # ---- Treasury: par and real curves, one CSV per (curve, year)
    failed: list[str] = []
    asked: dict[str, list[int]] = {}
    got_any = False
    for kind, columns, anchor in ((of.TREASURY_NOMINAL_KIND, of.TREASURY_NOMINAL, "DGS10"),
                                  (of.TREASURY_REAL_KIND, of.TREASURY_REAL, "DFII10")):
        asked[kind] = []
        streak = 0
        for y in _years_needed(prev, anchor, now):
            if streak >= MAX_CONSECUTIVE_FAILS:
                failed.append(f"{kind}: {streak} consecutive failures, remaining years skipped")
                break
            asked[kind].append(y)
            try:
                text = fetch(of.TREASURY_URL.format(year=y, kind=kind), None).decode(
                    "utf-8", "replace")
            except Exception as exc:                     # one dead year never kills the rest
                failed.append(f"{kind}/{y}: {_err(exc)}")
                streak += 1
                continue
            streak = 0
            got_any = True
            for sid, rows in of.parse_treasury_csv(text, columns).items():
                fresh.setdefault(sid, {}).update(rows)
    feeds["treasury"] = {"status": "FAILED" if failed and not got_any else (
        "PARTIAL" if failed else "OK"), "years": asked, "failed": failed,
        "points": {s: len(v) for s, v in fresh.items()}}

    # ---- BLS CPI-U
    if not keys.get("bls"):
        feeds["bls"] = {"status": "NO_KEY", "why": f"none of {list(of.BLS_KEY_NAMES)} is set: "
                                                   "CPI is UNMEASURED from the owner"}
    else:
        try:
            start = now.year - of.BLS_MAX_YEARS + 1
            body = of.bls_payload(of.BLS_SERIES, start, now.year, keys["bls"])
            got, status = of.parse_bls(json.loads(fetch(of.BLS_URL, body)))
            for sid, rows in got.items():
                if sid in of.BLS_SERIES and rows:
                    fresh[sid] = rows
            feeds["bls"] = {"status": "OK" if got else "EMPTY", "bls_status": status,
                            "points": {s: len(v) for s, v in got.items()}}
        except Exception as exc:
            feeds["bls"] = {"status": "FAILED", "why": _err(exc)}

    # ---- EIA weekly petroleum, one series per request
    if not keys.get("eia"):
        feeds["eia"] = {"status": "NO_KEY", "why": f"none of {list(of.EIA_KEY_NAMES)} is set: "
                                                   "the WPSR is UNMEASURED from the owner"}
    else:
        eia_failed: dict[str, str] = {}
        pts: dict[str, int] = {}
        for sid in of.EIA_SERIES:
            url = of.EIA_URL.format(series=sid) + "?api_key=" + str(keys["eia"])
            try:
                rows = of.parse_eia(json.loads(fetch(url, None)))
            except Exception as exc:
                eia_failed[sid] = _err(exc)
                continue
            if rows:
                fresh[sid] = rows
            pts[sid] = len(rows)
        feeds["eia"] = {"status": "FAILED" if len(eia_failed) == len(of.EIA_SERIES) else (
            "PARTIAL" if eia_failed else "OK"), "failed": eia_failed, "points": pts}

    # ---- merge onto the previous archive, then the spreads from the merged legs
    series: dict[str, list[list[Any]]] = {}
    for sid in dict.fromkeys([*prev, *fresh]):
        if sid in of.TREASURY_DERIVED or sid not in of.PROVIDER:
            continue
        series[sid] = of.merge(prev.get(sid), fresh.get(sid) or {}, seen_at)
    legs = {sid: {r[0]: r[1] for r in rows} for sid, rows in series.items()}
    seen = {sid: {r[0]: r[2] for r in rows} for sid, rows in series.items()}
    for name, rows in of.derive(legs).items():
        a, b = of.TREASURY_DERIVED[name]
        if rows:   # a spread is first seen when its LATER leg was
            series[name] = [[d, v, max(seen[a][d], seen[b][d])] for d, v in sorted(rows.items())]
    return {"updated": seen_at, "series": series,
            "source_ids": {sid: of.source_id(sid) for sid in series},
            "feeds": feeds, "held": dict(of.HELD),
            "terms": "17 U.S.C. 105 (libs.data.terms_hold.TERMS_EVIDENCE treasury/bls/eia)",
            "fresh": {sid: len(v) for sid, v in fresh.items()}}


def main(fetch: Fetch = _http, path: Path | None = None) -> int:
    target = Path(path or OUT)
    try:
        prev_doc = json.loads(target.read_text("utf-8"))
    except (OSError, ValueError):
        prev_doc = {}
    now = datetime.now(UTC)
    doc = collect(fetch, _keys(), now, prev_doc if isinstance(prev_doc, dict) else {})
    # vintages BEFORE the overwrite, under the owner's id (R0316): the store appends only changes
    revised = 0
    try:
        from libs.research.vintage import record
        for sid in doc["fresh"]:
            rows = {r[0]: r[1] for r in doc["series"].get(sid) or []}
            if rows:
                revised += record(_ROOT, of.source_id(sid), rows, vintage=doc["updated"])
    except Exception as exc:                             # the archive still lands
        doc["vintages"] = f"not recorded: {type(exc).__name__}"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc), "utf-8")
    tmp.replace(target)
    print("owner-macro: " + "; ".join(f"{k}={v.get('status')}" for k, v in doc["feeds"].items())
          + f"; {len(doc['series'])} series, {sum(doc['fresh'].values())} fresh points, "
            f"{revised} new-or-revised vintages -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
