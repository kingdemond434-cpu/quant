"""COLLECTOR LAB -- `scripts/collector_author.py` brought back with NO model-written code run.

WHY IT EXISTS. collector_author closed the desk's conversion bottleneck: the breadth expander finds
free public sources (data/breadth_expansion.jsonl), and something has to turn each one into a
series a family can read. It did that by having a model write `fetch()` and EXECUTING it, behind a
regex deny-list, in a child that inherited every key. A canary beat the deny-list on 2026-10-13 and
the organ was stood down (#362). This is its replacement inside the LLM lab.

THE MODEL NEVER WRITES CODE HERE. It is shown the source and a sample of the source's own response
and returns a DECLARATIVE SPEC -- one JSON object naming a URL, a format, a record path, a date
field and a value field. Fixed code in this file does the fetch and the parse. So there is nothing
to sandbox: no interpreter is handed model text, no key is in reach of a model, no file is written
where a model chose, and the only network a spec can reach is:

  * the source row's own host (or a host under the same registered domain), and
  * only when every address it resolves to is public (`libs.ops.public_host`), with redirects
    off, robots.txt honoured, no credentials or auth headers ever sent, a size cap and a timeout.

A WORKING SPEC IS A COLLECTOR, AND IT IS WIRED. The spec is kept in `collectors.json` and re-run
every pass with no model call, so the series stays fresh -- the original wrote a .py file nothing
ever ran again. The series lands in the lake (`data/lake/series/col_<id>.csv`) in the envelope
`exogenous_conditioner` reads, and exact conditioner cells are donated for the instruments the
spec names. The cells are hypotheses: the canonical gauntlet decides; nothing here has promotion
authority.

POINT-IN-TIME. A source like this publishes no vintages, so the release lag is UNMEASURED. The
conservative reading is used: an observation dated D is available at D + max(1 day, 2 x the
series' median spacing) -- a monthly print is not used until about two months after its period
opens. The conditioner then lags a further 24h. The cells carry the lab's look-ahead stamp
(evidence_from = the later of the model's cutoff and the spec's birth), because the model chose
the source-to-instrument mapping and may have read the history.

FREE ONLY. Calls go through `libs.ops.free_chain`, whose OpenRouter rung is `:free` only and
whose requests pass `openrouter_guard`. A dark chain means no new specs this pass; existing specs
still refresh.
"""

from __future__ import annotations

import csv
import io
import itertools
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.parse
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FEED = ROOT / "data" / "breadth_expansion.jsonl"
STATE_DIR = BASE / "data" / "llm_lab" / "collector"
SPECS = STATE_DIR / "collectors.json"
ATTEMPTS = STATE_DIR / "attempts.jsonl"
SERIES_DIR = BASE / "data" / "lake" / "series"
DONATE_DIR = BASE / "data" / "intelligence" / "llm_lab"
ROLE = "COLLECTOR"
UNMEASURED = "UNMEASURED"
AGENT = "quant-desk-collector/1.0"
MAX_BYTES = 8_000_000
SAMPLE_CHARS = 4000
MIN_POINTS = 90                # collector_author.validate's floor, unchanged
MIN_OBSERVATIONS = 30          # family_exogenous_conditioner.MIN_OBSERVATIONS
MAX_ATTEMPTS = 2               # per source; two failed specs are recorded, never retried
TRANSFORMS = (("level_z", 1.0), ("delta", 0.5))
FORMATS = ("json", "csv")

SYSTEM = (
    "You map a public data source onto a DECLARATIVE COLLECTOR SPEC for a quant desk. You do not "
    "write code. You are shown the source and the first characters of its real response.\n"
    "Return ONE JSON object and nothing else:\n"
    '{"url": "<https URL on the same site that returns the DAILY or longer history>", '
    '"format": "json" or "csv", '
    '"records": "<dot path to the list of observations in the JSON, e.g. data.observations; '
    'empty for the top level or for csv>", '
    '"date": "<field or csv column holding the date; an integer index for list rows; '
    '@key when records is a {date: value} object>", '
    '"value": "<field or column holding the number; an integer index for list rows; @value for '
    'a {date: value} object>", '
    '"date_format": "<strptime format, or empty if ISO dates or epoch numbers>", '
    '"symbols": ["<MT5 symbols this series should lead, from the list given>"], '
    '"side_when_high": 1 or -1, '
    '"mechanism": "<why a high reading moves those symbols, <=25 words>"}\n'
    "Rules: use only fields you can SEE in the sample; never invent one. Open public endpoints "
    "only: if the history needs a sign-in or a registered key, return {}."
)

Getter = Callable[[str], tuple[int, bytes]]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "source"


# ============================================================================ the fixed fetcher
def _domain(host: str) -> str:
    parts = host.lower().rstrip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def same_site(url: str, source_url: str) -> bool:
    """A spec may only move within the source's own registered domain."""
    a = urllib.parse.urlsplit(url).hostname or ""
    b = urllib.parse.urlsplit(source_url).hostname or ""
    return bool(a and b) and (a.lower() == b.lower() or _domain(a) == _domain(b))


def _default_get(url: str) -> tuple[int, bytes]:
    import requests
    # No redirects (a public URL that 302s to a private one would skip the host check), no auth,
    # no cookies, a byte cap: the response is read as data and nothing else.
    with requests.get(url, timeout=25, allow_redirects=False, stream=True,
                      headers={"User-Agent": AGENT, "Accept": "*/*"}) as r:
        body = b""
        for chunk in r.iter_content(65536):
            body += chunk
            if len(body) > MAX_BYTES:
                return 413, b""
        return r.status_code, body


def fetch(url: str, source_url: str, *, get: Getter | None = None,
          resolve: Callable[[str], list[str]] | None = None) -> tuple[bytes, str]:
    """(body, "") or (b"", why). Every refusal is named."""
    from libs.ops.public_host import public_url
    if not same_site(url, source_url):
        return b"", "OFF_SITE: the spec left the source's own domain"
    why = public_url(url, resolve=resolve)
    if why:
        return b"", f"REFUSED:{why}"
    g = get or _default_get
    parts = urllib.parse.urlsplit(url)
    try:
        code, robots = g(f"{parts.scheme}://{parts.netloc}/robots.txt")
        if code == 200:
            from urllib.robotparser import RobotFileParser
            rp = RobotFileParser()
            rp.parse(robots.decode("utf-8", errors="replace").splitlines())
            if not rp.can_fetch(AGENT, url):
                return b"", "ROBOTS_DISALLOW"
        code, body = g(url)
    except Exception as exc:
        return b"", f"UNREACHABLE:{type(exc).__name__}"
    if code in (401, 402, 403, 407, 429):
        return b"", f"GATED:HTTP_{code}"
    if code != 200:
        return b"", f"HTTP_{code}"
    if re.search(rb"(?i)captcha|verify you are human|cf-chl", body[:20000]):
        return b"", "GATED:CHALLENGE"
    return body, ""


# ============================================================================ the fixed parser
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_YM = re.compile(r"^(\d{4})-(\d{2})$")


def parse_date(raw: Any, fmt: str = "") -> str | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int | float):
        x = float(raw)
        if not math.isfinite(x):
            return None
        if x > 1e11:
            x /= 1000.0
        if x < 1e8:
            return None
        return datetime.fromtimestamp(x, UTC).date().isoformat()
    s = str(raw).strip()
    if fmt:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            return None
    m = _ISO.match(s)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=UTC).date().isoformat()
        except ValueError:
            return None
    m = _YM.match(s)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), 1, tzinfo=UTC).date().isoformat()
        except ValueError:
            return None
    for f in ("%Y%m%d", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, f).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def parse_value(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        x = float(str(raw).replace(",", "").strip()) if not isinstance(raw, int | float) \
            else float(raw)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _walk(doc: Any, path: str) -> Any:
    for key in [k for k in str(path or "").split(".") if k]:
        if isinstance(doc, dict):
            doc = doc.get(key)
        elif isinstance(doc, list) and key.lstrip("-").isdigit():
            i = int(key)
            doc = doc[i] if -len(doc) <= i < len(doc) else None
        else:
            return None
    return doc


def _pick(row: Any, field_: str) -> Any:
    if isinstance(row, dict):
        return row.get(field_)
    if isinstance(row, list | tuple) and field_.lstrip("-").isdigit():
        i = int(field_)
        return row[i] if -len(row) <= i < len(row) else None
    return None


def parse(body: bytes, spec: dict[str, Any]) -> tuple[dict[str, float], str]:
    """{YYYY-MM-DD: value}, "" or {}, why. The last reading of a day wins."""
    fmt = str(spec.get("format") or "")
    dkey, vkey = str(spec.get("date") or ""), str(spec.get("value") or "")
    dfmt = str(spec.get("date_format") or "")
    if fmt not in FORMATS or not dkey or not vkey:
        return {}, "SPEC_INCOMPLETE"
    text = body.decode("utf-8-sig", errors="replace")
    pairs: list[tuple[Any, Any]] = []
    if fmt == "json":
        try:
            doc = json.loads(text)
        except ValueError:
            return {}, "NOT_JSON"
        recs = _walk(doc, str(spec.get("records") or ""))
        if isinstance(recs, dict) and dkey == "@key":
            pairs = [(k, (v if vkey == "@value" else _pick(v, vkey))) for k, v in recs.items()]
        elif isinstance(recs, list):
            pairs = [(_pick(r, dkey), _pick(r, vkey)) for r in recs]
        else:
            return {}, "RECORDS_NOT_FOUND"
    else:
        try:
            reader = csv.DictReader(io.StringIO(text))
            pairs = [(r.get(dkey), r.get(vkey)) for r in reader]
        except csv.Error:
            return {}, "NOT_CSV"
    out: dict[str, float] = {}
    for d_raw, v_raw in pairs:
        d, v = parse_date(d_raw, dfmt), parse_value(v_raw)
        if d and v is not None:
            out[d] = v
    return dict(sorted(out.items())), ""


def validate(series: dict[str, float]) -> tuple[bool, str]:
    """collector_author's diff-verify step, kept: garbage is worse than no collector."""
    if len(series) < MIN_POINTS:
        return False, f"only {len(series)} points (<{MIN_POINTS})"
    vals = list(series.values())
    if len(set(vals)) < len(vals) * 0.2:
        return False, "near-constant series (stale/placeholder)"
    return True, f"{len(series)} points, {min(series)}..{max(series)}"


# ============================================================================ PIT series
def availability_lag(dates: Sequence[str]) -> timedelta:
    ds = sorted(datetime.fromisoformat(d) for d in dates)
    gaps = [(b - a).days for a, b in itertools.pairwise(ds) if (b - a).days > 0]
    spacing = statistics.median(gaps) if gaps else 1
    return timedelta(days=max(1.0, 2.0 * float(spacing)))


def series_rows(series: dict[str, float], source_id: str, retrieved: str) -> list[dict[str, Any]]:
    if not series:
        return []
    lag = availability_lag(list(series))
    rows = []
    for d, v in series.items():
        at = (datetime.fromisoformat(d).replace(tzinfo=UTC) + lag)
        rows.append({"available_time": at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                     "published_time": "", "retrieval_time": retrieved,
                     "source_id": source_id, "vintage_id": "v1", "value": v})
    return rows


SERIES_COLUMNS = ("available_time", "published_time", "retrieval_time", "source_id",
                  "vintage_id", "value")


def write_series(source_id: str, rows: Sequence[dict[str, Any]]) -> Path:
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    path = SERIES_DIR / f"{source_id}.csv"
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(SERIES_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    return path


# ============================================================================ the model's half
def parse_spec(text: str, uni: dict[str, str]) -> tuple[dict[str, Any], str]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}, "NO_JSON"
    try:
        raw = json.loads(m.group(0))
    except ValueError:
        return {}, "BAD_JSON"
    if not isinstance(raw, dict) or not raw:
        return {}, "DECLINED"
    url = str(raw.get("url") or "")
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        return {}, "BAD_URL"
    fmt = str(raw.get("format") or "").lower()
    if fmt not in FORMATS:
        return {}, "BAD_FORMAT"
    syms = [s for s in (raw.get("symbols") or []) if isinstance(s, str) and s in uni][:6]
    try:
        side = 1 if int(raw.get("side_when_high") or 1) > 0 else -1
    except (TypeError, ValueError):
        side = 1
    spec = {"url": url[:500], "format": fmt, "records": str(raw.get("records") or "")[:120],
            "date": str(raw.get("date") or "")[:60], "value": str(raw.get("value") or "")[:60],
            "date_format": str(raw.get("date_format") or "")[:30], "symbols": syms,
            "side_when_high": side, "mechanism": str(raw.get("mechanism") or "")[:240]}
    return spec, ""


def candidates(feed: Path, specs: dict[str, Any], attempts: list[dict[str, Any]]
               ) -> list[dict[str, Any]]:
    tried: dict[str, int] = {}
    for a in attempts:
        tried[str(a.get("source"))] = tried.get(str(a.get("source")), 0) + 1
    seen: set[str] = set()
    out = []
    for r in _jsonl(feed):
        nm = str(r.get("name") or "")
        if (r.get("_summary") or r.get("duplicate") or not r.get("reachable") or not nm
                or nm in seen or slug(nm) in specs or tried.get(nm, 0) >= MAX_ATTEMPTS):
            continue
        seen.add(nm)
        out.append(r)
    return out


def author(row: dict[str, Any], uni: dict[str, str], *, chat: Any, get: Getter | None,
           resolve: Callable[[str], list[str]] | None, timeout: float) -> dict[str, Any]:
    """One source -> one attempt record (and a spec when it works)."""
    rec: dict[str, Any] = {"source": row.get("name"), "url": row.get("url"), "at": _now()}
    sample, why = fetch(str(row.get("url") or ""), str(row.get("url") or ""), get=get,
                        resolve=resolve)
    if why:
        rec.update(status="SOURCE_UNREADABLE", detail=why)
        return rec
    user = (f"SOURCE: {row.get('name')}\nURL: {row.get('url')}\n"
            f"MODALITY: {row.get('modality', '')}\nWHY IT MATTERS: {row.get('mechanism', '')}\n"
            f"MT5 SYMBOLS: {', '.join(sorted(uni)[:150])}\n\n"
            f"FIRST {SAMPLE_CHARS} CHARACTERS OF THE RESPONSE:\n"
            f"{sample.decode('utf-8', errors='replace')[:SAMPLE_CHARS]}")
    try:
        from libs.research.proposer_seat import PromptRefused, scrub
        scrub(SYSTEM + "\n" + user)
    except PromptRefused as exc:
        rec.update(status="PROMPT_REFUSED", detail=str(exc)[:80])
        return rec
    except Exception:                                  # pragma: no cover
        rec.update(status=UNMEASURED, detail="prompt hygiene unavailable: nothing is sent")
        return rec
    reply = chat(SYSTEM, user, max_tokens=500, temperature=0.0, timeout=timeout)
    model = f"{getattr(reply, 'provider', '')}:{getattr(reply, 'model', '')}"
    rec["model"] = model
    spec, why = parse_spec(str(getattr(reply, "text", "") or ""), uni)
    if why:
        rec.update(status="NO_SPEC", detail=why)
        return rec
    body, why = (sample, "") if spec["url"] == row.get("url") else \
        fetch(spec["url"], str(row.get("url")), get=get, resolve=resolve)
    if why:
        rec.update(status="SPEC_UNREADABLE", detail=why)
        return rec
    series, why = parse(body, spec)
    ok, vmsg = validate(series) if not why else (False, why)
    rec.update(status="WORKS" if ok else "broken", detail=vmsg, n=len(series))
    if ok:
        from llm_lab import lookahead_guard
        rec["spec"] = {**spec, "source": row.get("name"), "source_url": row.get("url"),
                       "model": model, "born": _now(),
                       "lookahead_guard": lookahead_guard(model)}
    return rec


# ============================================================================ cells
def cells(specs: dict[str, Any], counts: dict[str, int], uni: dict[str, str]
          ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import llm_lab
    rows: list[dict[str, Any]] = []
    owed: list[dict[str, Any]] = []
    for sid, spec in specs.items():
        source = f"col_{sid}"
        n = int(counts.get(sid, 0))
        if n < MIN_OBSERVATIONS:
            owed.append({"collector": sid, "blocker": "NEEDS_DATA", "have": n,
                         "need": MIN_OBSERVATIONS})
            continue
        syms = [s for s in spec.get("symbols") or [] if s in uni]
        if not syms:
            owed.append({"collector": sid, "blocker": "NEEDS_INSTRUMENT_MAPPING"})
            continue
        side = int(spec.get("side_when_high") or 1)
        for sym in syms:
            if not llm_lab._lane_ok(sym, "exogenous_conditioner"):
                continue
            for transform, thr in TRANSFORMS:
                params = {"source": source, "signal": "value", "transform": transform,
                          "threshold": thr, "side_when_high": side}
                cell = {"family": "exogenous_conditioner", "params": params, "symbol": sym}
                rows.append({
                    "kind": "hypothesis", "family": "exogenous_conditioner", "params": params,
                    "symbols": [sym], "symbol": sym,
                    "mechanism": str(spec.get("mechanism") or f"{spec.get('source')} leads {sym}"),
                    "falsifier": (f"{sym} returns after an extreme {source} reading ({transform}) "
                                  f"are no different from unconditioned returns once the "
                                  f"conservative publication lag and 24h are applied"),
                    "title": f"llm_lab COLLECTOR: {spec.get('source')} {transform} on {sym}",
                    "lab": ROLE, "lab_name": "collector_lab",
                    "novelty_class": "GENUINELY_NOVEL", "cell_id": llm_lab.cell_identity(cell),
                    "mechanism_class": "alternative_data",
                    "lineage": {"root": f"collector:{sid}", "operator": "llm_lab"},
                    "url": str(spec.get("source_url") or ""),
                    "producer": "llm_lab", "lookahead_guard": spec.get("lookahead_guard") or
                    llm_lab.lookahead_guard(str(spec.get("model") or ""),
                                            at=str(spec.get("born") or "") or None),
                    "copy_trade": False, "credibility_inherited": False,
                    "gauntlet_bypass": False})
    return rows, owed


# ============================================================================ the pass
def refresh(specs: dict[str, Any], *, get: Getter | None, deadline: float,
            resolve: Callable[[str], list[str]] | None = None) -> dict[str, int]:
    """Re-run every working spec with no model call: the collector stays wired."""
    counts: dict[str, int] = {}
    for sid, spec in specs.items():
        if time.time() > deadline:
            break
        body, why = fetch(str(spec["url"]), str(spec.get("source_url") or spec["url"]),
                          get=get, resolve=resolve)
        if why:
            spec["last_error"] = why
            counts[sid] = int(spec.get("points") or 0) if (SERIES_DIR / f"col_{sid}.csv"
                                                         ).exists() else 0
            continue
        series, why = parse(body, spec)
        ok, vmsg = validate(series) if not why else (False, why)
        if not ok:
            spec["last_error"] = vmsg
            continue
        rows = series_rows(series, f"col_{sid}", _now())
        write_series(f"col_{sid}", rows)
        spec.update(last_ok=_now(), points=len(rows))
        spec.pop("last_error", None)
        counts[sid] = len(rows)
    return counts


def run(*, budget_s: float = 120.0, max_llm: int = 4, chat: Any = None, get: Getter | None = None,
        resolve: Callable[[str], list[str]] | None = None, feed: Path | None = None,
        uni: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.time()
    deadline = started + max(10.0, budget_s)
    import llm_lab
    uni = uni if uni is not None else llm_lab.universe()
    specs: dict[str, Any] = _read_json(SPECS, {}) or {}
    attempts = _jsonl(ATTEMPTS)
    out: dict[str, Any] = {"role": ROLE, "generated_at": _now(), "collectors_before": len(specs)}

    new: list[dict[str, Any]] = []
    todo = candidates(feed or FEED, specs, attempts)
    out["unconverted_sources"] = len(todo)
    if max_llm > 0 and todo:
        if chat is None:
            try:
                from libs.ops import free_chain
                chat = free_chain.chat
            except Exception:                          # pragma: no cover
                chat = None
        for row in todo[:max_llm] if chat else []:
            if time.time() > deadline - 20:
                break
            try:
                rec = author(row, uni, chat=chat, get=get, resolve=resolve,
                             timeout=max(10.0, min(90.0, deadline - time.time())))
            except Exception as exc:
                out["chain"] = type(exc).__name__
                break
            new.append(rec)
            if rec.get("spec"):
                specs[slug(str(row.get("name")))] = rec.pop("spec")
    if new:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with ATTEMPTS.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, default=str) + "\n")

    counts = refresh(specs, get=get, deadline=deadline, resolve=resolve)
    _write_json(SPECS, specs)
    donate, owed = cells(specs, counts, uni)
    known = set(_read_json(STATE_DIR / "donated.json", []) or [])
    fresh = [r for r in donate if r["cell_id"] not in known]
    if fresh:
        DONATE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")[:15]
        _write_json(DONATE_DIR / f"discoveries_collector_{stamp}.json",
                    {"source": "llm_lab", "role": ROLE, "generated_at": _now(),
                     "rule": "THE LAB PROPOSES, THE DESK JUDGES", "discoveries": fresh})
        _write_json(STATE_DIR / "donated.json", sorted(known | {r["cell_id"] for r in fresh}))
    status: dict[str, int] = {}
    for r in new:
        status[str(r.get("status"))] = status.get(str(r.get("status")), 0) + 1
    out.update({"asked": len(new), "attempts": status, "collectors": len(specs),
                "series_refreshed": sum(1 for v in counts.values() if v), "cells_donated":
                len(fresh), "cells_total": len(donate), "owed": owed[:20],
                "state": "RAN" if (new or counts) else ("DARK" if todo and not chat
                                                       else "NOTHING_OWED"),
                "seconds": round(time.time() - started, 1)})
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--max-llm", type=int, default=4)
    a = ap.parse_args(argv)
    print(json.dumps(run(budget_s=a.budget_s, max_llm=a.max_llm), indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
