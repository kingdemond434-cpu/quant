"""DATASET SUBSTITUTES: a lawful, registered substitute for every enrolled dataset behind a wall.

THE GAP (measured 2026-09-30, D18 after #168). Three intelligence seats are walled at their own
source and were UNFED by construction: `google_trends` (HTTP 429 on every explore query),
`investing` (403 to the page and to /robots.txt) and `china` (zhihu's anti-bot 403). The fence
routed each to the deep forest as a search, which is a hunt, not a feed.

THE FIX, without going round a single wall. Each walled dataset gets REGISTERED substitutes in
`desks/mt5/data/dataset_substitutes.json`, each with its own terms verdict:

    route    an organ that already produces the substitute (Wikipedia pageviews through
             #162's `attention_substitutes`; FRED/ALFRED through `fred_fetch`; the PBoC, SAFE,
             CFETS and NBS releases already in the Asia packs). Nothing is duplicated: the
             walled dataset inherits the uses of the substitute's datasets (`members`).
    fetch    a keyless series this module fetches itself (DBnomics' NBS republication), written
             to `data/lake/series/sub_<source>_<key>.csv` in the lake's point-in-time envelope.
    blocked  a candidate whose terms are not clean (the Nasdaq calendar JSON): registered, named,
             and never requested.

THE TERMS FENCE runs before every request: `libs.data.terms_fence.fenced_url` where that module is
present (#162) and the registry's own `terms` verdict always. No request is retried past a 403 or
a 429, and every request sends this organ's own identifying User-Agent.

POINT-IN-TIME. A fetched observation is stamped `available_time` = its period's END + the series'
declared release lag -- and only series declared `revises: false` are fetched this way (a revised
series labelled point-in-time is worse than none; ALFRED is the route for those). A later
DIFFERENT value for a period already held is ignored: the first sighting stands.

Runs inside the hourly `dataset_exploitation` leg, bounded by `budget_s`, and writes
`reports/DATASET_SUBSTITUTES.json`.
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REGISTRY = DESK / "data" / "dataset_substitutes.json"
LAKE = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "DATASET_SUBSTITUTES.json"
UA = "quant-desk-dataset-substitutes/1.0 (research; keyless public APIs)"
TIMEOUT = 30
DBNOMICS = "https://api.db.nomics.world/v22"
CLEAN = "CLEAN"
BLOCKED_TERMS = "BLOCKED_TERMS"
FETCH_FAILED_ENV = "FETCH_FAILED_ENV"
#: Statuses that end a source's pass: the publisher said no, and a wall is never pushed.
WALL_CODES = (401, 403, 429)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def registry(path: Path | None = None) -> dict[str, Any]:
    doc = _read(path or REGISTRY, {}) or {}
    walled = doc.get("walled") if isinstance(doc, dict) else None
    return walled if isinstance(walled, dict) else {}


def members(path: Path | None = None) -> dict[str, tuple[tuple[str, ...], str]]:
    """{walled dataset id: (member id patterns, why)} in dataset_exploitation.MEMBERS' shape:
    every CLEAN substitute's datasets. A BLOCKED_TERMS substitute contributes nothing."""
    out: dict[str, tuple[tuple[str, ...], str]] = {}
    for wid, w in registry(path).items():
        pats: list[str] = []
        names: list[str] = []
        for s in w.get("substitutes") or []:
            if not isinstance(s, dict) or s.get("terms") != CLEAN:
                continue
            pats += [str(m) for m in s.get("members") or []]
            names.append(str(s.get("id")))
        if pats:
            out[str(wid)] = (tuple(dict.fromkeys(pats)),
                             f"walled ({w.get('wall', 'its source')}); fed through its lawful "
                             f"registered substitute(s): {', '.join(names)}")
    return out


def terms_verdict(url: str, declared: str) -> tuple[str, str]:
    """(verdict, basis). The shared terms fence first (#162's libs/data/terms_fence, when this
    tree has it), then the registry's own declaration. Anything but CLEAN is never requested."""
    try:
        from libs.data import terms_fence  # type: ignore[attr-defined,unused-ignore]
        hit = terms_fence.fenced_url(url)
        if hit:
            return BLOCKED_TERMS, f"libs/data/terms_fence: {hit}"
        fence = "libs/data/terms_fence: not fenced"
    except Exception:
        fence = "libs/data/terms_fence absent on this tree (PR #162); registry verdict only"
    if declared != CLEAN:
        return BLOCKED_TERMS, f"registry declares {declared}; {fence}"
    return CLEAN, fence


# ------------------------------------------------------------------ fetch (DBnomics)
def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 - https only
        return r.read()


class Walled(Exception):
    """The publisher refused (401/403/429). The pass stops for this source; nothing retries."""


def _json(url: str, get: Callable[[str], bytes]) -> dict[str, Any]:
    try:
        body = get(url)
    except urllib.error.HTTPError as exc:
        if exc.code in WALL_CODES:
            raise Walled(f"HTTP {exc.code}") from exc
        raise
    doc = json.loads(body.decode("utf-8", "replace"))
    return doc if isinstance(doc, dict) else {}


def resolve_series(provider: str, spec: dict[str, Any], get: Callable[[str], bytes]
                   ) -> tuple[dict[str, Any] | None, str]:
    """The ONE series of `provider` whose name holds every `must` token, found through DBnomics'
    own search -- or (None, why). Ambiguity is never resolved by guessing: two matches is
    UNRESOLVED with both named, exactly as zero is."""
    q = urllib.parse.urlencode({"q": spec["search"], "limit": 20})
    found = _json(f"{DBNOMICS}/search?{q}", get)
    datasets = [d for d in ((found.get("results") or {}).get("docs") or [])
                if isinstance(d, dict) and str(d.get("provider_code")) == provider]
    must = [str(m).lower() for m in spec.get("must") or []]
    hits: list[dict[str, Any]] = []
    for d in datasets[:5]:
        qq = urllib.parse.urlencode({"observations": 1, "limit": 50, "format": "json",
                                     "q": " ".join(must)})
        doc = _json(f"{DBNOMICS}/series/{provider}/{d.get('code')}?{qq}", get)
        for s in ((doc.get("series") or {}).get("docs") or []):
            name = str(s.get("series_name") or "").lower()
            if isinstance(s, dict) and all(m in name for m in must):
                hits.append(s)
    if len(hits) != 1:
        names = [f"{h.get('dataset_code')}/{h.get('series_code')}: {h.get('series_name')}"
                 for h in hits[:6]]
        return None, (f"UNRESOLVED: {len(hits)} series match {must}"
                      + (f" ({'; '.join(names)})" if names else ""))
    return hits[0], "resolved by name through DBnomics search"


def _period_end(per: str) -> datetime | None:
    s = str(per).strip()
    try:
        if len(s) == 7:                                   # 2026-08: a month
            d = datetime.strptime(s, "%Y-%m").replace(tzinfo=UTC)
            return (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        if "Q" in s:                                      # 2026-Q2
            y, q = s.split("-Q")
            m = int(q) * 3
            d = datetime(int(y), m, 1, tzinfo=UTC)
            return (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        d = datetime.fromisoformat(s[:10]).replace(tzinfo=UTC)
        return d + timedelta(days=1)
    except (ValueError, TypeError):
        return None


def pit_rows(series: dict[str, Any], spec: dict[str, Any], source_id: str, now: datetime,
             held: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The lake envelope, keyed by the period's END (`event_time`). `available_time` is that end
    + the series' declared `lag_days` (conservative: the release is at or before it). A period
    already held keeps its FIRST sighting -- a later different value is ignored, so a revision
    can never be read at the original instant."""
    lag = timedelta(days=int(spec.get("lag_days") or 30))
    out = dict(held)
    for per, val in zip(series.get("period") or [], series.get("value") or [], strict=False):
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        end = _period_end(str(per))
        if v != v or end is None:
            continue
        key = end.isoformat(timespec="seconds")
        if key in out:
            continue
        out[key] = {"event_time": key,
                    "available_time": (end + lag).isoformat(timespec="seconds"),
                    "value": v, "source_id": source_id,
                    "vintage_id": f"{source_id}:{now:%Y%m%dT%H%M%S}"}
    return [out[k] for k in sorted(out)]


def _held(path: Path) -> dict[str, dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        per = str(r.get("event_time") or "")
        if per:
            out[per] = {k: r[k] for k in ("event_time", "available_time", "value", "source_id",
                                          "vintage_id") if k in r}
    return out


def write_lake(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["event_time", "available_time", "value",
                                           "source_id", "vintage_id"])
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def fetch_source(sub: dict[str, Any], now: datetime, get: Callable[[str], bytes],
                 lake: Path) -> dict[str, Any]:
    provider = str(sub.get("provider") or "")
    res: dict[str, Any] = {}
    for spec in sub.get("series") or []:
        key = str(spec.get("key"))
        if spec.get("revises") is not False:
            res[key] = {"status": "SKIPPED", "why": "a revising series is fetched only as "
                        "ALFRED-style vintages; a current-vintage copy is never stamped PIT"}
            continue
        try:
            s, why = resolve_series(provider, spec, get)
        except Walled as exc:
            res[key] = {"status": "WALLED", "why": f"{exc}: stopped, never retried"}
            break
        except Exception as exc:
            res[key] = {"status": FETCH_FAILED_ENV if not isinstance(exc, urllib.error.HTTPError)
                        else "FETCH_FAILED_HTTP", "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
            continue
        if s is None:
            res[key] = {"status": "UNRESOLVED", "why": why}
            continue
        pack = f"sub_{str(sub.get('id'))}_{key}"
        path = lake / f"{pack}.csv"
        sid = f"dbnomics:{provider}/{s.get('dataset_code')}/{s.get('series_code')}"
        rows = pit_rows(s, spec, sid, now, _held(path))
        write_lake(path, rows)
        res[key] = {"status": "OK", "pack": pack, "rows": len(rows), "source_id": sid,
                    "series_name": s.get("series_name"), "resolved": why}
    return res


def run(now: datetime | None = None, *, budget_s: float = 90.0,
        get: Callable[[str], bytes] | None = None, lake: Path | None = None,
        path: Path | None = None, write: bool = True) -> dict[str, Any]:
    """One pass: every walled dataset's substitutes, terms-checked, fetch ones fetched."""
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    get = get or _get
    out: dict[str, Any] = {}
    for wid, w in sorted(registry(path).items()):
        subs: dict[str, Any] = {}
        for s in w.get("substitutes") or []:
            if not isinstance(s, dict):
                continue
            verdict, basis = terms_verdict(str(s.get("url") or ""), str(s.get("terms") or ""))
            row: dict[str, Any] = {"kind": s.get("kind"), "terms": verdict,
                                   "terms_basis": basis if verdict != CLEAN
                                   else s.get("terms_basis"),
                                   "members": s.get("members") or [], "organ": s.get("organ")}
            if verdict != CLEAN:
                row["status"] = BLOCKED_TERMS
            elif s.get("kind") == "fetch":
                if time.monotonic() - t0 > budget_s:
                    row["status"] = "DEFERRED: budget spent; next pass"
                else:
                    row["series"] = fetch_source(s, now, get, lake or LAKE)
                    row["status"] = "FETCHED"
            else:
                row["status"] = "ROUTED"
            subs[str(s.get("id"))] = row
        out[wid] = {"wall": w.get("wall"), "substitutes": subs}
    doc = {"generated_at": now.isoformat(timespec="seconds"), "generator": "dataset_substitutes",
           "rule": ("a walled dataset is fed through lawful registered substitutes only: the "
                    "terms fence before every request, no retry past 401/403/429, the organ's own "
                    "User-Agent, first sighting per period kept"),
           "walled": out, "wall_s": round(time.monotonic() - t0, 2)}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_name(REPORT.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, REPORT)
    return doc


# ------------------------------------------------------------------ the fence's post-pass
FETCH_FAILED_PREFIX = "FETCH_FAILED_ENV"


def unmeasured_by_environment(rows: dict[str, dict[str, Any]], ds: list[dict[str, Any]],
                              aliases: dict[str, tuple[tuple[str, ...], str]]) -> list[str]:
    """Datasets whose fetch never reached the publisher (FETCH_FAILED_ENV) and that have no
    evidence of their own: the ENVIRONMENT failed, not the dataset, so the fence reads them
    UNMEASURED with that reason instead of UNFED -- and so does an alias whose every member is
    in that state. Mutates `rows` in place; returns the ids changed."""
    by_id = {d["id"]: d for d in ds}
    env = {i for i, d in by_id.items()
           if str((d.get("pit") or {}).get("fetch_status") or "").startswith(FETCH_FAILED_PREFIX)}
    for i, (pats, _why) in aliases.items():
        mem = [x for x in by_id if x != i and any(fnmatch(x, p) for p in pats)]
        if mem and all(m in env for m in mem):
            env.add(i)
    changed: list[str] = []
    for i in sorted(env):
        r = rows.get(i)
        if not r or r.get("status") != "UNFED":
            continue
        r["uses"] = dict.fromkeys(r.get("uses") or ("direct", "conditioner", "allocation"),
                                  "UNMEASURED")
        r["missing"] = []
        r["status"] = "UNMEASURED"
        r["breach"] = False
        r["unmeasured_why"] = ("FETCH_FAILED_ENV: no host has reached the publisher yet (proxy "
                               "refusal / reset / timeout); an environment failure is not the "
                               "dataset being unfed. It reads UNMEASURED until the box fetches it "
                               "(research/fred_fetch.py)")
        changed.append(i)
    return changed
