"""FIRST PRINTS FROM THE PUBLISHER -- the hourly leg that fills `data/lake/first_prints/`.

WHY (World sensor's #204 fix, 2026-11-14). `macro/release_vintages.py` reads every release's
actual from ONE store, `data/lake/first_prints/<desk series>`, holding (observation_date,
realtime_date, value) rows captured from the agency that publishes the number. FRED/ALFRED is
terms-refused for every automated fetch (governance/fred-terms-ruling-2026-11-13.md), and nothing
wrote that path, so every release read UNMEASURED_NO_PRIMARY_VINTAGE. This leg writes it.

BLS FIRST. The ten BLS series in `release_vintages.PRIMARY` come from the BLS Public Data API v2
(US federal government work, public domain; BLS API terms), one POST per pass, through a
fail-closed robots.txt read under this leg's own honest User-Agent. `BLS_API_KEY` is used when the
box holds it (higher daily limit) and is never written anywhere; without it the keyless v2 tier is
asked. DOL, BEA, Census and the Fed are NOT BUILT yet: each is reported UNMEASURED with its
missed_growth line, never silently absent.

A FIRST PRINT IS ONLY EVER RECORDED WHEN IT IS SEEN BEING BORN. The API serves today's value for
every period, not the value as first published, and BLS revises payrolls twice and seasonal
factors yearly. So:

* The first pass for a series records a BASELINE (the newest period it served) and writes no rows:
  a value already on the API when the leg first looked may be a revision, and a revised number
  written as a first print is exactly the substitution release_vintages forbids.
* A period newer than the baseline that appears for the first time is a first print, stamped with
  the UTC date the leg saw it (`realtime_date`). The leg runs hourly and BLS publishes at 08:30 ET,
  so that date is the release date; a later date only ever errs late, never early (PIT-safe).
* A later pass that serves a DIFFERENT value for a period whose first print is held appends a
  revision row with its own realtime_date. Periods older than the baseline are never written.

The store is append-only: rows are never rewritten or dropped, and a store that cannot be read is
never overwritten (the pass reports UNMEASURED for that series and moves on).

    python research/first_print_capture.py --once
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FIRST_PRINTS = DESK / "data" / "lake" / "first_prints"
STATE = FIRST_PRINTS / "_capture_state.json"
REPORT = DESK / "reports" / "FIRST_PRINT_CAPTURE.json"

UA = "quant-desk-first-prints/1.0 (research; robots-respecting)"
TIMEOUT = 30.0
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_LICENCE = "US federal government work (public domain); BLS Public Data API terms"
FIELDS = ("observation_date", "realtime_date", "value")

#: desk series -> BLS series id. The same ten pairs as release_vintages.PRIMARY's "bls" rows
#: (a test holds the two tables equal wherever release_vintages is importable).
BLS: dict[str, str] = {
    "PAYEMS": "CES0000000001", "UNRATE": "LNS14000000", "CES0500000003": "CES0500000003",
    "CPIAUCSL": "CUSR0000SA0", "CPIAUCNS": "CUUR0000SA0", "CPILFESL": "CUSR0000SA0L1E",
    "CPILFENS": "CUUR0000SA0L1E", "PPIFIS": "WPSFD4", "PPIFES": "WPSFD49104",
    "JTSJOL": "JTS000000000000000JOL",
}

#: The publishers whose capture route is not built yet, and the desk series each one owns.
NOT_BUILT: dict[str, tuple[str, ...]] = {
    "dol": ("ICSA",),
    "bea": ("PCEPILFE", "PI", "PCE", "GDPC1"),
    "census": ("RSAFS", "RSFSXMV", "DGORDER", "ADXTNO", "PERMIT", "HOUST", "BOPGSTB", "HSN1F"),
    "fed": ("INDPRO",),
}

Getter = Callable[[urllib.request.Request], bytes]


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------------------- robots (closed)
def robots_refusal(url: str, agent: str = UA, get: Getter | None = None) -> str | None:
    """None when robots.txt allows `url` for `agent`, else why not. FAIL CLOSED (Governance
    2026-11-10): 404/410 means no rules; 401/403/429/451, a 5xx, an unreadable or HTML body, or
    any transport error refuses the pass."""
    from libs.data.robots_body import robots_rules_or_refusal
    parts = urllib.parse.urlsplit(url)
    req = urllib.request.Request(f"{parts.scheme}://{parts.netloc}/robots.txt",
                                 headers={"User-Agent": agent})
    try:
        got = robots_rules_or_refusal(200, None, (get or _http)(req))
    except urllib.error.HTTPError as e:
        code = int(e.code)
        e.close()
        got = robots_rules_or_refusal(code, None, b"")
    except Exception as e:
        return f"robots.txt unreadable ({type(e).__name__})"
    # One reader for every robots read (libs.data.robots_body): 404/410 = no rules; any markup
    # or non-text body is unread; every other status refuses the pass.
    if isinstance(got, str):
        return got
    rp = got
    return None if rp.can_fetch(agent, url) else "robots.txt disallows this path"


class PinnedHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to the SAME host over https. Anything else is not followed, so it
    surfaces as the 30x HTTPError and the pass reads UNMEASURED: a POST carrying the key is never
    replayed to wherever a Location points, and robots.txt is never read from another host."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> Any:
        was, now = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if ((was.hostname or "").lower() != (now.hostname or "").lower()
                or now.scheme != "https" or req.data is not None):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(PinnedHostRedirect())


def _http(req: urllib.request.Request) -> bytes:
    with _OPENER.open(req, timeout=TIMEOUT) as r:
        data: bytes = r.read(5_000_000)
    return data


# ------------------------------------------------------------------------------------ BLS
def bls_request(ids: list[str], key: str, year: int) -> urllib.request.Request:
    doc: dict[str, Any] = {"seriesid": ids, "startyear": str(year - 1), "endyear": str(year)}
    if key:
        doc["registrationkey"] = key
    return urllib.request.Request(BLS_URL, data=json.dumps(doc).encode("utf-8"), method="POST",
                                  headers={"User-Agent": UA, "Content-Type": "application/json"})


def parse_bls(body: bytes) -> tuple[dict[str, dict[str, float]], str]:
    """{bls id: {observation_date ISO (first of month): value}}, and an error ('' when fine).
    Annual averages (M13) and non-monthly periods are skipped."""
    try:
        doc = json.loads(body)
    except ValueError:
        return {}, "BLS answered something that is not JSON"
    if not isinstance(doc, dict) or str(doc.get("status")) != "REQUEST_SUCCEEDED":
        # Only BLS's status code is published, never its free-text `message`.
        status = str(doc.get("status") if isinstance(doc, dict) else "?")
        status = "".join(c for c in status if c.isalnum() or c == "_")[:40] or "?"
        return {}, f"BLS status {status}: the request was not served"
    out: dict[str, dict[str, float]] = {}
    for s in (doc.get("Results") or {}).get("series") or []:
        sid = str((s or {}).get("seriesID") or "")
        for d in (s or {}).get("data") or []:
            per = str((d or {}).get("period") or "")
            if not (len(per) == 3 and per.startswith("M") and per[1:].isdigit()
                    and 1 <= int(per[1:]) <= 12):
                continue
            try:
                obs = date(int(d.get("year")), int(per[1:]), 1).isoformat()
                val = float(str(d.get("value")).replace(",", ""))
            except (TypeError, ValueError):
                continue
            out.setdefault(sid, {})[obs] = val
    return out, ""


# ------------------------------------------------------------------------------------ store
def read_store(series: str, folder: Path) -> list[dict[str, str]] | None:
    """The held rows ([] when there is no file yet), or None when the file cannot be read."""
    p = folder / f"{series}.csv"
    if not p.exists():
        return []
    try:
        with p.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error, UnicodeDecodeError):
        return None
    if rows and not set(FIELDS) <= set(rows[0]):
        return None
    return rows


def _write_rows(series: str, folder: Path, rows: list[dict[str, str]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{series}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(FIELDS))
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, folder / f"{series}.csv")
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
        os.replace(tmp, p)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def absorb(series: str, served: Mapping[str, float], state: dict[str, Any], seen_on: str,
           folder: Path) -> dict[str, Any]:
    """Fold one pass's served values into the series' store. Returns the series' census row."""
    held = read_store(series, folder)
    if held is None:
        return {"status": "UNMEASURED", "why": f"{series}.csv unreadable: not overwritten"}
    if not served:
        return {"status": "UNMEASURED", "why": "BLS served no monthly values for this id",
                "rows": len(held)}
    st = state.setdefault(series, {})
    newest = max(served)
    if "baseline" not in st:
        st["baseline"] = newest
        st["baselined_on"] = seen_on
        return {"status": "BASELINED", "baseline": newest, "rows": len(held),
                "why": ("first look: values already on the API may be revisions, so nothing "
                        "before or at the baseline is ever written as a first print")}
    last: dict[str, float] = {}
    for r in held:
        with contextlib.suppress(ValueError):
            last[r["observation_date"]] = float(r["value"])
    new_rows: list[dict[str, str]] = []
    firsts = revisions = 0
    for obs in sorted(served):
        val = served[obs]
        if obs <= st["baseline"]:
            continue
        if obs not in last:
            firsts += 1
        elif last[obs] != val:
            revisions += 1
        else:
            continue
        new_rows.append({"observation_date": obs, "realtime_date": seen_on, "value": repr(val)})
    if new_rows:
        _write_rows(series, folder, held + new_rows)
    return {"status": "CAPTURED" if held or new_rows else "WAITING_FIRST_RELEASE",
            "baseline": st["baseline"], "new_first_prints": firsts, "new_revisions": revisions,
            "rows": len(held) + len(new_rows), "newest_served": newest}


def capture_bls(*, now: datetime, folder: Path, state: dict[str, Any], key: str,
                get: Getter) -> dict[str, Any]:
    refused = robots_refusal(BLS_URL, UA, get)
    if refused:
        return {s: {"status": "UNMEASURED", "why": f"robots: {refused} (fail closed)"}
                for s in BLS}
    try:
        body = get(bls_request(list(BLS.values()), key, now.year))
    except urllib.error.HTTPError as e:
        code = int(e.code)
        e.close()
        why = f"BLS HTTP {code}" + (" (hard stop)" if code in (401, 403, 429, 451) else "")
        return {s: {"status": "UNMEASURED", "why": why} for s in BLS}
    except Exception as e:
        return {s: {"status": "UNMEASURED", "why": f"BLS unreachable ({type(e).__name__})"}
                for s in BLS}
    by_id, err = parse_bls(body)
    if err:
        return {s: {"status": "UNMEASURED", "why": err} for s in BLS}
    seen_on = now.date().isoformat()
    return {s: absorb(s, by_id.get(bid, {}), state, seen_on, folder) for s, bid in BLS.items()}


def _bls_key() -> str:
    try:
        from libs.ops.env_keys import read_key
    except ImportError:
        return ""
    try:
        return str(read_key("BLS_API_KEY") or "").strip()
    except Exception:
        return ""


def run(*, now: datetime | None = None, folder: Path = FIRST_PRINTS, state_path: Path = STATE,
        report: Path = REPORT, get: Getter = _http, key: str | None = None) -> dict[str, Any]:
    now = now or _now()
    state = _read_json(state_path, {})
    if not isinstance(state, dict):
        state = {}
    k = _bls_key() if key is None else key
    series: dict[str, Any] = {}
    for s, row in capture_bls(now=now, folder=folder, state=state, key=k, get=get).items():
        series[s] = {"publisher": "bls", "publisher_series": BLS[s], **row}
    for pub, owned in NOT_BUILT.items():
        for s in owned:
            series[s] = {"publisher": pub, "publisher_series": None, "status": "UNMEASURED",
                         "why": f"{pub} first-print capture route not built yet",
                         "missed_growth": (f"missed_growth: {s} has no primary first print, so "
                                           "release_vintages leaves its surprise "
                                           "UNMEASURED_NO_PRIMARY_VINTAGE")}
    _write_json(state_path, state)
    census: dict[str, int] = {}
    for r in series.values():
        census[r["status"]] = census.get(r["status"], 0) + 1
    doc = {"generated_at": now.isoformat(timespec="seconds"), "store": str(folder.name),
           "licence": {"bls": BLS_LICENCE}, "key_present": bool(k), "census": census,
           "series": series}
    _write_json(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.parse_args(argv)
    doc = run()
    print(f"first_print_capture: {doc['census']} (key_present={doc['key_present']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
