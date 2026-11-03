"""COPY-TRADE CROWD BOOK: thousands of public retail accounts as one per-symbol crowd net.

Tier-1 footprint sweep row #10 (class A2, 2026-11-03). The desk already mines MQL5, FX Blue and
Myfxbook as STRATEGY DONORS; nothing turned their populations into a CROWD. This does, as two
books per symbol and three cohorts per book:

  POSITIONS BOOK  open positions read from public, logged-out statement pages (FX Blue,
                  Myfxbook). net_acct = (accounts long - accounts short) / accounts holding;
                  net_lots the same on lots.
  FLOW BOOK       MQL5 open positions are login-only (measured 2026-11-03), so MQL5 gives FLOW:
                  the public page's per-symbol Distribution table and Long/Short trade counts,
                  differenced between visits. New deals per symbol, signed when the page splits
                  them by side or when one symbol carries >= 80% of the signal's new deals.

  COHORTS         all | smart | dumb, preregistered here and not tuned:
                  score = log(1 + growth) / max(drawdown, 5%);
                  smart = at least 26 weeks of record and score in the top decile of those;
                  dumb  = growth <= 0, or score at or below the cross-sectional median.
                  smart_minus_dumb is the signal tier-1 desks read: the informed crowd against
                  the uninformed one, on the same symbol at the same hour.

POINT IN TIME. Every observation is stamped `captured_at` (UTC) when it was fetched; a book only
aggregates observations captured in the last FRESH_H hours, and each per-symbol row lands in
`data/lake/series/ctc_<SYMBOL>.parquet` with `available_time` = the pass's capture time.
`family_exogenous_conditioner` adds its own publication-day lag before any bar can see it.
Raw observations are appended to `data/crowd/copytrade/raw/<day>.jsonl.gz`: this history cannot
be bought later, so every pass that does not run is history lost.

HONEST ACCESS. Public pages only; robots.txt is read per host and a Disallow (or an unreadable
robots.txt) bars the route; a login wall is recorded as BLOCKED_AUTH and that route stops for the
pass; 401/403/429/451 is a HARD STOP written to state and the source is not fetched again until
`--release <source>`. No login, cookie, proxy, CAPTCHA or paywall step exists here.

CELLS. Once a symbol's series holds 30 rows, its columns become `exogenous_conditioner` cells
through `futures_state.mint` (the same door, each cell minted once in its life).

    python desks/mt5/research/copytrade_crowd.py --once [--budget-s 600] [--dry-run]
    python desks/mt5/research/copytrade_crowd.py --release mql5_signals
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
import time
import urllib.parse
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.crowd_symbols import canonical  # noqa: E402

REGISTRY = DESK / "research" / "copytrade_crowd_sources.json"
STATE = DESK / "data" / "crowd" / "copytrade" / "state.json"
RAW = DESK / "data" / "crowd" / "copytrade" / "raw"
SERIES = DESK / "data" / "lake" / "series"
OUT = DESK / "reports" / "COPYTRADE_CROWD.json"

LEG = "copytrade_crowd"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; copytrade_crowd)"
HARD_STOP = frozenset({401, 403, 429, 451})
FRESH_H = 6.0
SMART_MIN_WEEKS = 26
SMART_PCT = 0.90
DUMB_PCT = 0.50
CONCENTRATION = 0.80
MIN_FLOW_DEALS = 1
SERIES_PREFIX = "ctc_"

LOGIN_WALL = re.compile(
    r"(please\s+log\s*in|you\s+are\s+not\s+(currently\s+)?logged\s+in|log\s*in\s+or\s+register"
    r"|sign\s+in\s+to\s+(see|view)|login\s+required|members\s+only)", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


# ----------------------------------------------------------------------------- small helpers

def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(p)


def page_text(html: str) -> str:
    """Tags out, one line per block, whitespace collapsed. Every parser here reads TEXT, not
    markup, so a class rename on the page does not silently zero a book."""
    s = _SCRIPT.sub(" ", html or "")
    s = re.sub(r"<(br|/p|/div|/tr|/li|/h\d|/td|/th|/dt|/dd|/span)\b[^>]*>", "\n", s, flags=re.I)
    s = _TAG.sub(" ", s)
    for a, b in (("&nbsp;", " "), ("&#160;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&#37;", "%"), ("\u00a0", " "), ("\u2009", " "), ("\u202f", " ")):
        s = s.replace(a, b)
    lines = [_WS.sub(" ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    t = str(s).replace(" ", "").replace("\u00a0", "").replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _first(patterns: Iterable[str], text: str) -> float | None:
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            v = _num(m.group(1))
            if v is not None:
                return v
    return None


# ----------------------------------------------------------------------------- robots

def robots_rules(txt: str, agent: str = "quant-research") -> list[tuple[str, bool]]:
    """(path pattern, allow) for the group that applies to `agent`, else the '*' group."""
    groups: list[tuple[list[str], list[tuple[str, bool]]]] = []
    cur_agents: list[str] = []
    cur_rules: list[tuple[str, bool]] = []
    last_was_agent = False
    for raw in (txt or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not last_was_agent and (cur_agents or cur_rules):
                groups.append((cur_agents, cur_rules))
                cur_agents, cur_rules = [], []
            cur_agents.append(v.lower())
            last_was_agent = True
        elif k in ("allow", "disallow"):
            last_was_agent = False
            if v or k == "allow":
                cur_rules.append((v, k == "allow"))
        else:
            last_was_agent = False
    if cur_agents or cur_rules:
        groups.append((cur_agents, cur_rules))
    a = agent.lower()
    for agents, rules in groups:
        if any(x != "*" and x in a for x in agents):
            return rules
    for agents, rules in groups:
        if "*" in agents:
            return rules
    return []


def robots_allows(rules: list[tuple[str, bool]], url: str) -> bool:
    """Google semantics: '*' wildcard, '$' anchor, the longest matching rule wins, Allow wins
    a tie. No matching rule allows."""
    p = urllib.parse.urlsplit(url)
    path = (p.path or "/") + (f"?{p.query}" if p.query else "")
    best: tuple[int, bool] | None = None
    for pat, allow in rules:
        if not pat:
            continue
        rx = "^" + re.escape(pat).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path):
            key = (len(pat), allow)
            if best is None or key > best:
                best = key
    return True if best is None else best[1]


# ----------------------------------------------------------------------------- fetching

class Fetcher:
    """One honest GET per URL through the desk's polite client: no retries, our own UA, robots
    per host, hard stops recorded. `get` is injectable so tests run offline."""

    def __init__(self, state: dict[str, Any], deadline: float,
                 get: Callable[[str], tuple[int | None, str]] | None = None) -> None:
        self.state = state
        self.deadline = deadline
        self._get = get or self._polite
        self._robots: dict[str, list[tuple[str, bool]] | None] = {}
        self.stats: dict[str, dict[str, int]] = {}

    @staticmethod
    def _polite(url: str) -> tuple[int | None, str]:
        from libs.data import polite_fetch
        r = polite_fetch.get(url, headers={"User-Agent": UA}, retries=0, leg=LEG, timeout=25.0)
        return r.status, r.text or ""

    def _stat(self, source: str, key: str) -> None:
        self.stats.setdefault(source, {}).setdefault(key, 0)
        self.stats[source][key] += 1

    def robots_ok(self, url: str) -> bool:
        host = urllib.parse.urlsplit(url).netloc.lower()
        if host not in self._robots:
            code, body = self._get(f"https://{host}/robots.txt")
            if code == 404:
                self._robots[host] = []
            elif code is not None and 200 <= code < 300:
                self._robots[host] = robots_rules(body)
            else:
                self._robots[host] = None      # unread is not consent
        rules = self._robots[host]
        return rules is not None and robots_allows(rules, url)

    def fetch(self, source: str, url: str) -> str | None:
        if time.monotonic() >= self.deadline:
            self._stat(source, "deadline")
            return None
        if source in (self.state.get("hard_stops") or {}):
            self._stat(source, "hard_stopped")
            return None
        if not self.robots_ok(url):
            self._stat(source, "robots_barred")
            return None
        code, body = self._get(url)
        self._stat(source, "fetched")
        if code in HARD_STOP:
            self.state.setdefault("hard_stops", {})[source] = {
                "code": code, "url": url, "at": _iso(_now())}
            self._stat(source, f"http_{code}")
            return None
        if code is None or not 200 <= code < 300:
            self._stat(source, f"http_{code}")
            return None
        self._stat(source, "ok")
        return body


# ----------------------------------------------------------------------------- parsers

def parse_quality(text: str) -> dict[str, float | None]:
    """Track-record headline from a statement's text: growth %, drawdown %, weeks of record."""
    growth = _first((r"Growth[:\s]*(-?[\d\s.,]+?)\s*%", r"Abs\.?\s*Gain[:\s]*(-?[\d\s.,]+?)\s*%",
                     r"\bGain[:\s]*(-?[\d\s.,]+?)\s*%", r"Total\s+return[:\s]*(-?[\d\s.,]+?)\s*%",
                     r"\bReturn[:\s]*(-?[\d\s.,]+?)\s*%"), text)
    dd = _first((r"By\s+Equity[:\s]*([\d\s.,]+?)\s*%", r"Max(?:imal|imum)?\.?\s+drawdown[^%\n]*?"
                 r"\(([\d.,]+)\s*%\)", r"Max(?:imal|imum)?\.?\s+drawdown[:\s]*([\d.,]+)\s*%",
                 r"Drawdown[:\s]*([\d.,]+)\s*%",
                 r"Peak[- ]to[- ]trough[:\s]*-?([\d.,]+)\s*%"), text)
    weeks = _first((r"Weeks[:\s]*(\d+)",), text)
    if weeks is None:
        m = re.search(r"(?:Started|Start(?:ed)?\s+date|Tracking\s+since)[:\s]*"
                      r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})", text, re.I)
        if m:
            try:
                d0 = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=UTC)
                weeks = max(0.0, (_now() - d0).days / 7.0)
            except ValueError:
                weeks = None
    subs = _first((r"Subscribers[:\s]*(\d[\d\s]*)",), text)
    return {"growth_pct": growth, "dd_pct": dd, "weeks": weeks, "subscribers": subs}


def parse_mql5_flow(text: str) -> dict[str, Any]:
    """MQL5 public page: total Long / Short trade counts, and the Distribution table per symbol.
    A row is a symbol followed by up to three integers; when there are three and the last two
    sum to the first, they are (sell, buy) and the row is SIDED -- the parser checks its own
    reading rather than trusting a column order it cannot see."""
    out: dict[str, Any] = {"long": None, "short": None, "symbols": {}}
    m = re.search(r"\bLong(?:\s+Trades)?[:\s]*(\d[\d\s]*?)\s*\(", text, re.I)
    if m:
        out["long"] = _num(m.group(1))
    m = re.search(r"\bShort(?:\s+Trades)?[:\s]*(\d[\d\s]*?)\s*\(", text, re.I)
    if m:
        out["short"] = _num(m.group(1))
    best: dict[str, dict[str, int]] = {}
    for m in re.finditer("Distribution", text):
        rows = _distribution(text[m.start(): m.start() + 6000])
        if len(rows) > len(best):
            best = rows
    out["symbols"] = best
    return out


def _distribution(seg: str) -> dict[str, dict[str, int]]:
    """Symbol rows of one Distribution table: SYMBOL then 1-3 integer cells (each cell is its
    own line in `page_text`, or all on one line). A decimal ends the row (profit, pips)."""
    rows: dict[str, dict[str, int]] = {}
    toks: list[str] = []
    for ln in seg.split("\n"):
        toks.extend([ln] if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._#+\-]{2,15}(\s+\d+){1,3}", ln)
                    else ln.split())
    for j, tok in enumerate(toks):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._#+\-]{2,15}", tok):
            continue
        sym = canonical(tok)
        if not sym:
            continue
        ints: list[int] = []
        for nxt in toks[j + 1: j + 4]:
            t = nxt.replace(" ", "")
            if re.fullmatch(r"\d+", t):
                ints.append(int(t))
            else:
                break
        if not ints:
            continue
        row = {"deals": ints[0]}
        if len(ints) == 3 and ints[1] + ints[2] == ints[0]:
            row["sell"], row["buy"] = ints[1], ints[2]
        prev = rows.get(sym)
        if prev:     # two broker tickers on one instrument: add them
            for k, v in row.items():
                prev[k] = prev.get(k, 0) + v
        else:
            rows[sym] = row
    return rows


_SIDE = re.compile(r"^(buy|sell|long|short)(\s*(limit|stop))?$", re.I)
_LOTS = re.compile(r"^\d{1,4}(\.\d{1,3})?$")


def parse_positions(html: str) -> list[dict[str, Any]]:
    """Open positions from any statement table: a row whose cells hold a placeable symbol, a
    market side and a lot size. Pending orders (buy limit / sell stop) are not positions."""
    rows: list[dict[str, Any]] = []
    for tr in re.findall(r"<tr\b.*?</tr>", _SCRIPT.sub(" ", html or ""), re.S | re.I):
        cells = [_WS.sub(" ", _TAG.sub(" ", c)).strip()
                 for c in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(cells) < 3:
            continue
        sym = side = None
        lots = None
        for j, c in enumerate(cells):
            sm = _SIDE.match(c)
            if sm and side is None:
                if sm.group(3):
                    side = "pending"
                    break
                side = "long" if sm.group(1).lower() in ("buy", "long") else "short"
                for c2 in cells[j + 1:]:
                    if _LOTS.match(c2.replace(",", "")):
                        v = float(c2.replace(",", ""))
                        if 0 < v <= 1000:
                            lots = v
                            break
                continue
            if sym is None and re.fullmatch(r"[A-Za-z][A-Za-z0-9._#+\-]{2,15}", c):
                sym = canonical(c)
        if sym and side in ("long", "short"):
            rows.append({"symbol": sym, "side": side, "lots": lots or 0.0})
    return rows


# ----------------------------------------------------------------------------- population

def mql5_ids(html: str) -> list[str]:
    ids = re.findall(r"/(?:[a-z]{2})/signals/(\d{5,9})(?![\d/]*/)", html or "")
    return list(dict.fromkeys(ids))


def myfxbook_ids(html: str) -> list[str]:
    return list(dict.fromkeys(m for m in re.findall(
        r"/members/([A-Za-z0-9_\-.]+/[A-Za-z0-9_\-.%]+/\d{3,10})", html or "")))


def population(name: str, src: Mapping[str, Any], f: Fetcher, state: dict[str, Any]
               ) -> list[str]:
    """Known accounts for a source: the held list, refreshed from the listing pages once a day."""
    pop_state = state.setdefault("population", {}).setdefault(name, {"ids": [], "at": ""})
    known = list(pop_state.get("ids") or [])
    if src.get("adapter") == "fxblue":
        p = ROOT / str(src.get("population_file") or "")
        try:
            handles = [ln.strip().rstrip("/").rsplit("/", 1)[-1]
                       for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        except OSError:
            handles = []
        return list(dict.fromkeys(known + handles))
    last = pop_state.get("at") or ""
    fresh = bool(last) and (_now() - datetime.fromisoformat(last)) < timedelta(hours=24)
    if fresh and known:
        return known
    found: list[str] = []
    extract = mql5_ids if src.get("adapter") == "mql5" else myfxbook_ids
    for tmpl in src.get("population_pages") or []:
        pages = range(2, int(src.get("population_max_pages") or 1) + 1) if "{n}" in tmpl else [0]
        for n in pages:
            html = f.fetch(name, tmpl.format(n=n))
            if html is None:
                break
            ids = extract(html)
            new = [i for i in ids if i not in found]
            if not new:
                break
            found.extend(new)
    ids = list(dict.fromkeys(known + found))[-20000:]
    pop_state["ids"] = ids
    pop_state["at"] = _iso(_now())
    return ids


def rotation(name: str, ids: list[str], n: int, state: dict[str, Any]) -> list[str]:
    """The next `n` accounts after this source's cursor, so every account is revisited in turn."""
    if not ids:
        return []
    cur = int((state.setdefault("cursor", {})).get(name) or 0) % len(ids)
    take = [ids[(cur + k) % len(ids)] for k in range(min(n, len(ids)))]
    state["cursor"][name] = (cur + len(take)) % len(ids)
    return take


# ----------------------------------------------------------------------------- observe

def flow_delta(prev: Mapping[str, Any] | None, cur: Mapping[str, Any]) -> dict[str, Any] | None:
    """New deals per symbol since the last visit, signed where the page allows it. None when
    there is no baseline or the record went backwards (reset / re-based account)."""
    if not prev or not prev.get("symbols"):
        return None
    ps, cs = prev["symbols"], cur.get("symbols") or {}
    new: dict[str, dict[str, float]] = {}
    for sym, row in cs.items():
        d = int(row.get("deals", 0)) - int((ps.get(sym) or {}).get("deals", 0))
        if d < 0:
            return None
        if d == 0:
            continue
        r: dict[str, float] = {"deals": float(d)}
        if "buy" in row and "buy" in (ps.get(sym) or {"buy": 0}):
            b = int(row["buy"]) - int((ps.get(sym) or {}).get("buy", 0))
            s = int(row["sell"]) - int((ps.get(sym) or {}).get("sell", 0))
            if b >= 0 and s >= 0 and b + s == d:
                r["signed"] = float(b - s)
        new[sym] = r
    if not new:
        return {}
    unsided = [s for s, r in new.items() if "signed" not in r]
    total = sum(r["deals"] for r in new.values())
    dl = (cur.get("long") or 0) - (prev.get("long") or 0)
    ds = (cur.get("short") or 0) - (prev.get("short") or 0)
    if unsided and dl >= 0 and ds >= 0 and dl + ds > 0:
        top = max(new, key=lambda s: new[s]["deals"])
        if top in unsided and new[top]["deals"] / total >= CONCENTRATION:
            new[top]["signed"] = float(new[top]["deals"]) * (dl - ds) / (dl + ds)
    return new


def observe(name: str, src: Mapping[str, Any], acct: str, f: Fetcher, state: dict[str, Any],
            now: datetime) -> dict[str, Any] | None:
    adapter = src.get("adapter")
    html = f.fetch(name, str(src["account_url"]).format(id=acct))
    if html is None:
        return None
    text = page_text(html)
    obs: dict[str, Any] = {"source": name, "account": acct, "captured_at": _iso(now),
                           **parse_quality(text)}
    if adapter == "mql5":
        cur = parse_mql5_flow(text)
        if not cur["symbols"]:
            f._stat(name, "markup_no_distribution")
        key = f"{name}:{acct}"
        prev = (state.setdefault("flow_base", {})).get(key)
        delta = flow_delta(prev, cur)
        if cur["symbols"]:
            state["flow_base"][key] = {**cur, "at": _iso(now)}
        obs["flow"] = delta
        return obs
    pos_html = html
    if src.get("positions_url"):
        pos_html = f.fetch(name, str(src["positions_url"]).format(id=acct)) or ""
    if pos_html and LOGIN_WALL.search(page_text(pos_html)) and not parse_positions(pos_html):
        f._stat(name, "login_wall")
        obs["positions"] = None
        return obs
    obs["positions"] = parse_positions(pos_html)
    if not obs["positions"]:
        f._stat(name, "no_open_positions_parsed")
    return obs


# ----------------------------------------------------------------------------- cohorts / books

def score(o: Mapping[str, Any]) -> float | None:
    g, dd = o.get("growth_pct"), o.get("dd_pct")
    if g is None or g <= -100:
        return None
    return math.log1p(g / 100.0) / max((dd or 0.0) / 100.0, 0.05)


def cohorts(obs: list[dict[str, Any]]) -> dict[str, set[str]]:
    """smart / dumb membership by `source:account`, cross-sectional, preregistered thresholds."""
    keyed = [(f"{o['source']}:{o['account']}", o, score(o)) for o in obs]
    scored = [(k, o, s) for k, o, s in keyed if s is not None]
    smart: set[str] = set()
    dumb: set[str] = set()
    if not scored:
        return {"smart": smart, "dumb": dumb}
    allsc = sorted(s for _k, _o, s in scored)
    med = allsc[(len(allsc) - 1) // 2]
    seasoned = sorted(s for _k, o, s in scored if (o.get("weeks") or 0) >= SMART_MIN_WEEKS)
    cut = seasoned[min(len(seasoned) - 1, math.floor(SMART_PCT * len(seasoned)))] \
        if seasoned else math.inf
    for k, o, s in scored:
        if (o.get("weeks") or 0) >= SMART_MIN_WEEKS and s >= cut and (o.get("growth_pct") or 0) > 0:
            smart.add(k)
        elif (o.get("growth_pct") or 0) <= 0 or s <= med:
            dumb.add(k)
    return {"smart": smart, "dumb": dumb}


def _ratio(a: float, b: float) -> float | None:
    return (a - b) / (a + b) if (a + b) > 0 else None


def books(obs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per symbol: positions and flow nets for all / smart / dumb, and smart minus dumb."""
    groups = cohorts(obs)
    acc: dict[str, dict[str, dict[str, float]]] = {}

    def add(sym: str, cohort: str, key: str, v: float) -> None:
        acc.setdefault(sym, {}).setdefault(cohort, {}).setdefault(key, 0.0)
        acc[sym][cohort][key] += v

    for o in obs:
        k = f"{o['source']}:{o['account']}"
        tags = ["all"] + [c for c in ("smart", "dumb") if k in groups[c]]
        per_sym: dict[str, list[float]] = {}
        for p in o.get("positions") or []:
            s = per_sym.setdefault(p["symbol"], [0.0, 0.0])
            s[0 if p["side"] == "long" else 1] += float(p.get("lots") or 0.0) or 1e-9
        for sym, (lo, sh) in per_sym.items():
            for t in tags:
                add(sym, t, "lots_long", lo)
                add(sym, t, "lots_short", sh)
                if lo > sh:
                    add(sym, t, "acct_long", 1.0)
                elif sh > lo:
                    add(sym, t, "acct_short", 1.0)
        for sym, r in (o.get("flow") or {}).items():
            for t in tags:
                add(sym, t, "flow_deals", r["deals"])
                if "signed" in r:
                    add(sym, t, "flow_signed", r["signed"])
                    add(sym, t, "flow_attr", r["deals"])
    out: dict[str, dict[str, Any]] = {}
    for sym, by in acc.items():
        row: dict[str, Any] = {}
        for t in ("all", "smart", "dumb"):
            a = by.get(t) or {}
            row[f"pos_net_acct_{t}"] = _ratio(a.get("acct_long", 0.0), a.get("acct_short", 0.0))
            row[f"pos_net_lots_{t}"] = _ratio(a.get("lots_long", 0.0), a.get("lots_short", 0.0))
            row[f"pos_n_{t}"] = a.get("acct_long", 0.0) + a.get("acct_short", 0.0)
            row[f"flow_net_{t}"] = (a["flow_signed"] / a["flow_attr"]
                                    if a.get("flow_attr", 0.0) >= MIN_FLOW_DEALS else None)
            row[f"flow_deals_{t}"] = a.get("flow_deals", 0.0)
        for b in ("pos_net_acct", "pos_net_lots", "flow_net"):
            sv, dv = row.get(f"{b}_smart"), row.get(f"{b}_dumb")
            row[f"{b}_smart_minus_dumb"] = (sv - dv) if sv is not None and dv is not None else None
        out[sym] = row
    tot = sum(r["flow_deals_all"] for r in out.values()) or 0.0
    for r in out.values():
        r["flow_share_all"] = (r["flow_deals_all"] / tot) if tot else None
    return out


# ----------------------------------------------------------------------------- store

def append_raw(obs: list[dict[str, Any]], now: datetime) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / f"{now:%Y%m%d}.jsonl.gz"
    with gzip.open(p, "at", encoding="utf-8") as fh:
        for o in obs:
            fh.write(json.dumps(o, sort_keys=True, default=str) + "\n")
    return p


def write_series(book: Mapping[str, Mapping[str, Any]], now: datetime,
                 root: Path | None = None) -> dict[str, Any]:
    """One row per symbol per pass into `ctc_<SYMBOL>.parquet`, available_time = capture time."""
    import pandas as pd
    base = root or SERIES
    base.mkdir(parents=True, exist_ok=True)
    frames: dict[str, Any] = {}
    for sym, row in book.items():
        sid = f"{SERIES_PREFIX}{sym}"
        p = base / f"{sid}.parquet"
        new = pd.DataFrame([{**{k: (float(v) if v is not None else float("nan"))
                                 for k, v in row.items()},
                             "available_time": pd.Timestamp(now),
                             "event_time": pd.Timestamp(now),
                             "retrieval_time": _iso(now), "source_id": sid}])
        try:
            old = pd.read_parquet(p) if p.exists() else None
        except Exception:
            old = None
        df = new if old is None else pd.concat([old, new], ignore_index=True)
        df["available_time"] = pd.to_datetime(df["available_time"], utc=True)
        df = df.drop_duplicates("available_time", keep="last").sort_values("available_time")
        tmp = p.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(p)
        (base / f"{sid}.pit.json").write_text(json.dumps(
            {"available_time": _iso(now), "source_id": sid, "producer": LEG}), encoding="utf-8")
        frames[sid] = df
    return frames


def mint_cells(frames: Mapping[str, Any], state: dict[str, Any], dry_run: bool
               ) -> dict[str, Any]:
    try:
        import futures_state as fs  # type: ignore[import-not-found,unused-ignore]
    except Exception as exc:
        return {"status": "UNAVAILABLE", "why": f"{type(exc).__name__}: {exc}"}
    built = {sid: {"kind": "copytrade_crowd", "targets": [sid[len(SERIES_PREFIX):]],
                   "why": ("Aggregated public copy-trade accounts: positions and new-deal flow "
                           "of the retail crowd, split smart vs dumb by track record; crowd "
                           "extremes fade, smart-minus-dumb follows.")}
             for sid in frames}
    enqueue = None
    if not dry_run:
        try:
            from libs.moat.registry import enqueue_candidate
            enqueue = enqueue_candidate
        except Exception as exc:
            return {"status": "REGISTRY_UNAVAILABLE", "why": type(exc).__name__}
    mstate = state.setdefault("mint", {})
    res: dict[str, Any] = fs.mint(built, dict(frames), fs._universe(), mstate,
                                  dry_run=dry_run, enqueue=enqueue, limit=1500)
    return res


# ----------------------------------------------------------------------------- build

def build(*, budget_s: float = 600.0, dry_run: bool = False,
          get: Callable[[str], tuple[int | None, str]] | None = None,
          registry: Mapping[str, Any] | None = None, state_path: Path | None = None,
          series_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or _now()
    reg = registry if registry is not None else (_read(REGISTRY, {}) or {})
    sp = state_path or STATE
    state = _read(sp, {}) or {}
    f = Fetcher(state, deadline=t0 + budget_s, get=get)
    sources = (reg.get("sources") or {})
    live = {n: s for n, s in sources.items() if s.get("adapter") not in (None, "none")}
    fresh: list[dict[str, Any]] = []
    for name, src in live.items():
        ids = population(name, src, f, state)
        for acct in rotation(name, ids, int(src.get("per_pass_accounts") or 100), state):
            o = observe(name, src, acct, f, state, now)
            if o is not None:
                fresh.append(o)
    held = state.setdefault("obs", {})
    for o in fresh:
        held[f"{o['source']}:{o['account']}"] = o
    cutoff = now - timedelta(hours=FRESH_H)
    for k in [k for k, o in held.items()
              if datetime.fromisoformat(o["captured_at"]) < cutoff]:
        held.pop(k)
    window = list(held.values())
    book = books(window)
    frames: dict[str, Any] = {}
    cells: dict[str, Any] = {"status": "DRY_RUN"}
    if not dry_run and fresh:
        append_raw(fresh, now)
    if not dry_run and book:
        frames = write_series(book, now, series_root)
        cells = mint_cells(frames, state, dry_run)
    groups = cohorts(window)
    doc = {
        "generated_utc": _iso(now),
        "rule": ("Public, logged-out copy-trade pages aggregated into a per-symbol crowd book; "
                 "login walls, robots Disallow and 401/403/429/451 are recorded, never routed "
                 "around. Smart = >=26 weeks and top-decile log-growth/drawdown; dumb = losing "
                 "or below-median. available_time = capture time."),
        "observations_this_pass": len(fresh),
        "observations_in_window": len(window),
        "window_h": FRESH_H,
        "cohort_sizes": {"all": len(window), "smart": len(groups["smart"]),
                         "dumb": len(groups["dumb"])},
        "symbols": len(book),
        "book_top": dict(sorted(book.items(),
                                key=lambda kv: -(kv[1].get("pos_n_all") or 0)
                                - (kv[1].get("flow_deals_all") or 0))[:25]),
        "sources": {n: {"adapter": s.get("adapter"), "positions": s.get("positions"),
                        "stats": f.stats.get(n, {}),
                        "population": len((state.get("population") or {}).get(n, {}).get(
                            "ids") or [])} for n, s in live.items()},
        "gaps": {n: {"blocked_by": s.get("blocked_by"), "next": s.get("next")}
                 for n, s in sources.items() if n not in live},
        "hard_stops": state.get("hard_stops", {}),
        "cells": cells,
        "seconds": round(time.monotonic() - t0, 1),
    }
    if not dry_run:
        _write(sp, state)
        if state_path is None:
            _write(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--release", default="", help="clear a source's hard stop")
    a = ap.parse_args(argv)
    if a.release:
        st = _read(STATE, {}) or {}
        gone = (st.get("hard_stops") or {}).pop(a.release, None)
        _write(STATE, st)
        print(f"copytrade_crowd: released {a.release}: {gone}")
        return 0
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"copytrade_crowd: {doc['observations_this_pass']} observed, "
          f"{doc['observations_in_window']} in {FRESH_H:g}h window, {doc['symbols']} symbols, "
          f"cohorts {doc['cohort_sizes']}, hard stops {list(doc['hard_stops'])}, "
          f"{doc['seconds']}s")
    for n, s in doc["sources"].items():
        print(f"  {n}: pop={s['population']} {s['stats']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
