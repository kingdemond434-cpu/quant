"""KEYED FREE SOURCES -- the hourly leg that turns every free-key dataset the principal registers
into point-in-time lake series, DIRECT and INDIRECT cells and allocation intelligence.

WHY (2026-09-30). The principal is setting free API keys on the trading box (EIA, Nasdaq Data
Link, e-Stat, KOSIS, Bank of Korea ECOS, BLS, Reddit OAuth, Telegram). A key with no fetcher
unlocks nothing; a fetcher with no clock produces nothing; a series with no producer mints nothing.
This organ is all three for the sources no other lane builds (`libs/data/credentials.py` names
which lane owns every other key), and until a key is set its row reads BLOCKED_AUTH:<VAR> --
never UNMEASURED-as-success and never 0.

ONE PASS, inside `--budget-s`:

  1. READS THE ROSTER `data/source_rosters/keyed_sources.json` (id, cadence, auth, licence,
     region, lang, url, plus series, release rule, culture and `uses` per row).
  2. VISITS DUE SOURCES STALEST FIRST. Cursor state (`data/keyed_sources/state.json`) is written
     after EVERY source, so a pass cut by the cycle cap still advanced what it touched.
  3. STORES POINT-IN-TIME (`data/keyed_sources/obs/<id>.json`): the first value seen for a
     (series, period) is kept for ever; a later different value is a revision beside it. A value
     from the source's FIRST successful fetch is BACKFILL, timed at the release rule (period end +
     the row's lag, late by construction); every later value is timed at max(rule, first seen).
  4. PUBLISHES `data/lake/series/ks_<id>__<series>.csv` in the lake's PIT envelope -- the exact
     frame `mt5desk.family_exogenous_conditioner` loads -- with `value`, `z`, `chg`, `chg_z`
     (trailing statistics over strictly earlier points only).
  5. MINTS CELLS through `proposer_common.donate` (the stamped, lane-filtered, pre-registered
     registry door), `tests_run` = cells minted so every one is charged to the trial census:
       DIRECT    exogenous_conditioner on each mapped instrument: {level_z, delta_z} x
                 {1.0, 1.5} x {+1, -1} per (series, instrument), a ring slice per pass.
       INDIRECT  each certified parent on the instrument, gated by the series' change regime
                 (`params.conditioner = "alt:ks_<id>__<series>:chg_z:gt|lt:0"`), which
                 `mt5desk.cell_modifiers` applies once #131's alt: conditioner lands. Before
                 that the arm reads BLOCKED_DEPENDENCY and mints nothing: a cell the gauntlet
                 must refuse is a trial charged for nothing.
  6. WRITES `reports/KEYED_SOURCES_ALLOCATION_INTEL.json` (per instrument, the latest
     PIT-available z / chg_z of every mapped series; read-only, sizes nothing) and
     `reports/KEYED_SOURCES.json` (per source status and yield, cells by arm and by credential).

NO KEY IS EVER PRINTED, LOGGED OR WRITTEN. Values are read here through
`libs.data.credentials.accepted_names` and go into the request only; every error string is passed
through `redact` before it is stored.

    python desks/mt5/research/keyed_sources.py --once [--budget-s 300] [--dry-run] [--no-fetch]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import credentials as cred  # noqa: E402
from libs.data import keyed_sources as ks  # noqa: E402

SEAT = "keyed_sources"
INDIRECT_SEAT = "keyed_sources_indirect"
UNMEASURED = "UNMEASURED"
TIMEOUT = 30.0
MAX_BYTES = 16 * 1024 * 1024
CADENCE_H = {"hourly": 1.0, "4h": 4.0, "daily": 24.0, "weekly": 24.0}
#: Points a series needs before cells are minted on it: the family itself emits nothing below
#: `family_exogenous_conditioner.MIN_OBSERVATIONS`, so a cell minted earlier is a wasted trial.
MIN_POINTS = 30
Z_WINDOW = 52
EXO_GRID = {"transform": ("level_z", "delta_z"), "threshold": (1.0, 1.5),
            "side_when_high": (1, -1)}
PARENTS_PER_SYMBOL = 3
#: Rows donated per pass. NOT A BRAKE ON BREADTH: the ring cursor walks the whole grid.
PER_PASS = cred.KS_PER_PASS
CULTURE_KEYS = ("source_culture", "participant_structure", "failure_mode_hypothesis",
                "crowding_prior")


@dataclass(frozen=True)
class Paths:
    desk: Path = DESK

    @property
    def roster(self) -> Path:
        return self.desk / "data" / "source_rosters" / "keyed_sources.json"

    @property
    def state(self) -> Path:
        return self.desk / "data" / "keyed_sources" / "state.json"

    @property
    def obs(self) -> Path:
        return self.desk / "data" / "keyed_sources" / "obs"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe" / "universe.json"

    @property
    def survivors(self) -> Path:
        return self.desk / "reports" / "UNIVERSAL_SURVIVORS.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "KEYED_SOURCES.json"

    @property
    def allocation(self) -> Path:
        return self.desk / "reports" / "KEYED_SOURCES_ALLOCATION_INTEL.json"


class Blocked(Exception):
    """A named state (BLOCKED_AUTH:<VAR>, BLOCKED_DEPENDENCY:<x>, BLOCKED_SESSION ...)."""


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def _t(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------- roster ------
REQUIRED = ("id", "kind", "cadence", "auth", "licence", "region", "lang", "url", "key_env",
            "series", "rule", "uses", *CULTURE_KEYS)


def load_roster(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    doc = _read(path, {})
    out: list[dict[str, Any]] = []
    bad: list[str] = []
    for r in (doc.get("sources") if isinstance(doc, dict) else None) or []:
        if not isinstance(r, dict):
            continue
        miss = [k for k in REQUIRED if k not in r]
        if miss:
            bad.append(f"{r.get('id', '<unnamed>')}: missing {', '.join(miss)}")
            continue
        if not all(k in (r.get("uses") or {}) for k in ("direct", "indirect", "allocation")):
            bad.append(f"{r['id']}: uses must name direct, indirect and allocation")
            continue
        out.append(r)
    return out, bad


# ------------------------------------------------------------------------------- keys -----
def resolve_keys(row: Mapping[str, Any], environ: Mapping[str, str] | None = None
                 ) -> dict[str, str]:
    """Every var the row needs -> its value, read through the registry's accepted names.
    Raises Blocked("BLOCKED_AUTH:<VAR>") naming the first missing canonical var."""
    env = os.environ if environ is None else environ
    out: dict[str, str] = {}
    for var in row.get("key_env") or []:
        val = ""
        for name in cred.accepted_names(str(var)):
            val = str(env.get(name, "")).strip()
            if val:
                break
        if not val:
            raise Blocked(f"BLOCKED_AUTH:{var}")
        out[str(var)] = val
    return out


# ------------------------------------------------------------------------------- http -----
def _tls() -> Any:
    with contextlib.suppress(Exception):
        from research import asia_collector
        make: Any = asia_collector._tls_context
        return make()
    return None


def http(req: ks.Request) -> bytes:
    r = urllib.request.Request(req.url, data=req.data, method=req.method,
                               headers={"User-Agent": "quant-desk-keyed-sources/1.0",
                                        "Accept": "application/json", **req.headers})
    with urllib.request.urlopen(r, timeout=TIMEOUT, context=_tls()) as resp:
        return bytes(resp.read(MAX_BYTES))


Getter = Callable[[ks.Request], bytes]


# ------------------------------------------------------------------------- collection -----
def _estat_parser() -> Callable[..., list[Any]]:
    try:
        from research.alt_proxies import Ctx, parse_estat_cpi
    except Exception as exc:
        raise Blocked("BLOCKED_DEPENDENCY:research.alt_proxies.parse_estat_cpi (lands with "
                      f"#131; {type(exc).__name__})") from None

    def parse(body: bytes, name: str) -> list[ks.Obs]:
        return [ks.Obs(name, o.period, float(o.value)) for o in parse_estat_cpi(body, Ctx())]
    return parse


def fetch_estat(row: Mapping[str, Any], keys: Mapping[str, str], get: Getter
                ) -> list[ks.Obs]:
    parse = _estat_parser()
    out: list[ks.Obs] = []
    for name, spec in (row.get("series") or {}).items():
        s = spec or {}
        sid = os.environ.get(str(s.get("stats_id_env") or ""), "") or str(s.get("statsDataId"))
        q = f"appId={keys['ESTAT_APP_ID']}&statsDataId={sid}"
        if s.get("query"):
            q += "&" + str(s["query"])
        out += parse(get(ks.Request(f"{row['url']}?{q}", part=name)), name)
    return out


def fetch_reddit(row: Mapping[str, Any], keys: Mapping[str, str], get: Getter,
                 now: datetime) -> list[ks.Obs]:
    tok = ks.parse_reddit_token(get(ks.reddit_token_request(keys["REDDIT_CLIENT_ID"],
                                                            keys["REDDIT_SECRET"])))
    if not tok:
        raise Blocked("BLOCKED_AUTH:REDDIT_CLIENT_ID (the token endpoint refused the pair)")
    items: list[tuple[datetime, str]] = []
    for req in ks.reddit_listing_requests(row, tok):
        items += ks.parse_reddit_listing(get(req))
    return ks.count_mentions(items, row, now.date())


def fetch_telegram(row: Mapping[str, Any], keys: Mapping[str, str], now: datetime,
                   paths: Paths, client_factory: Callable[[], Any] | None = None
                   ) -> list[ks.Obs]:
    """Full channel history through a USER session the principal created by hand.

    NEVER CREATES A SESSION OR AN ACCOUNT: `connect()` and `is_user_authorized()` only; a missing
    or unauthorised session is BLOCKED_SESSION, which names the one manual step."""
    session = paths.desk.parents[1] / str(row.get("session_file") or "")
    if client_factory is None:
        try:
            from telethon.sync import TelegramClient  # type: ignore[import-not-found]
        except Exception:
            raise Blocked("BLOCKED_DEPENDENCY:telethon (pip install telethon)") from None
        if not session.exists():
            raise Blocked(f"BLOCKED_SESSION: no session at {row.get('session_file')}; create it "
                          "once by hand with Telethon's interactive login -- this organ never "
                          "logs in")

        def client_factory() -> Any:
            return TelegramClient(str(session.with_suffix("")), int(keys["TELEGRAM_API_ID"]),
                                  keys["TELEGRAM_API_HASH"])
    client = client_factory()
    client.connect()
    try:
        if not client.is_user_authorized():
            raise Blocked("BLOCKED_SESSION: the session is not authorised; re-create it by hand")
        since = now - timedelta(days=30)
        items: list[tuple[datetime, str]] = []
        for ch in row.get("channels") or []:
            for msg in client.iter_messages(ch, limit=2000):
                ts = getattr(msg, "date", None)
                if ts is None or ts < since:
                    break
                items.append((ts, str(getattr(msg, "message", "") or "")))
    finally:
        with contextlib.suppress(Exception):
            client.disconnect()
    return ks.count_mentions(items, row, now.date())


def fetch_generic(row: Mapping[str, Any], keys: Mapping[str, str], get: Getter,
                  start: str | None) -> list[ks.Obs]:
    kind = str(row["kind"])
    key = next(iter(keys.values()), "")
    out: list[ks.Obs] = []
    empty: list[str] = []
    for req in ks.BUILDERS[kind](row, key, start):
        try:
            body = get(req)
        except Exception as exc:
            empty.append(f"{req.part or kind}: {type(exc).__name__}: {exc}")
            continue
        got = ks.PARSERS[kind](body, row, req.part)
        if not got:
            # The publisher's own error text (a wrong table id, a refused key) is the record.
            empty.append(f"{req.part or kind}: no rows; "
                         f"{body[:160].decode('utf-8', errors='replace')}")
        out += got
    if empty:
        PARTIAL_ERRORS.extend(ks.redact(e, keys.values())[:240] for e in empty)
    if not out and empty:
        raise RuntimeError("; ".join(PARTIAL_ERRORS[-3:]))
    return out


#: Per-request failures of the source being collected, redacted; `run` drains it per source.
PARTIAL_ERRORS: list[str] = []


def collect(row: Mapping[str, Any], *, get: Getter, now: datetime, paths: Paths,
            start: str | None, environ: Mapping[str, str] | None = None,
            telegram_factory: Callable[[], Any] | None = None) -> list[ks.Obs]:
    keys = resolve_keys(row, environ)
    kind = str(row["kind"])
    try:
        if kind == "estat":
            return fetch_estat(row, keys, get)
        if kind == "reddit":
            return fetch_reddit(row, keys, get, now)
        if kind == "telegram":
            return fetch_telegram(row, keys, now, paths, telegram_factory)
        if kind in ks.BUILDERS:
            return fetch_generic(row, keys, get, start)
    except Blocked:
        raise
    except Exception as exc:
        raise RuntimeError(ks.redact(f"{type(exc).__name__}: {exc}", keys.values())[:300]) from None
    raise Blocked(f"BLOCKED_DEPENDENCY:no fetcher for kind {kind!r}")


# ------------------------------------------------------------------------ PIT store -------
def _lag(row: Mapping[str, Any], series: str) -> tuple[int, int]:
    rule = row.get("rule") or {}
    spec = (row.get("series") or {}).get(series) or {}
    return int(spec.get("lag_days", rule.get("lag_days", 1))), int(rule.get("hour", 0))


def rule_time(row: Mapping[str, Any], series: str, period: date) -> datetime:
    lag, hour = _lag(row, series)
    return datetime(period.year, period.month, period.day, hour, tzinfo=UTC) + timedelta(days=lag)


def merge(store: dict[str, Any], row: Mapping[str, Any], obs: list[ks.Obs], seen: datetime,
          backfill: bool) -> dict[str, int]:
    added = revised = 0
    stamp = seen.isoformat(timespec="seconds")
    for o in obs:
        k = f"{o.series}|{o.period.isoformat()}"
        r = store.get(k)
        if r is None:
            rt = rule_time(row, o.series, o.period)
            avail = rt if backfill else max(rt, seen)
            store[k] = {"series": o.series, "period": o.period.isoformat(),
                        "value_first": o.value, "value_last": o.value, "first_seen_at": stamp,
                        "available_time": avail.isoformat(timespec="seconds"),
                        "pit_quality": "backfill" if backfill else "live",
                        "revision_time": None, "n_revisions": 0}
            added += 1
        elif not math.isclose(float(r["value_last"]), o.value, rel_tol=1e-9, abs_tol=1e-12):
            r["value_last"] = o.value
            r["revision_time"] = stamp
            r["n_revisions"] = int(r.get("n_revisions") or 0) + 1
            revised += 1
    return {"added": added, "revised": revised}


def _z(prior: list[float], x: float) -> float | None:
    w = prior[-Z_WINDOW:]
    if len(w) < 5:
        return None
    m = sum(w) / len(w)
    sd = math.sqrt(sum((v - m) ** 2 for v in w) / len(w))
    return round((x - m) / sd, 6) if sd > 0 else None


def points(store: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Per series, PIT points in AVAILABILITY order with z / chg / chg_z over strictly earlier
    points. The FIRST value seen is the value; a revision never back-dates."""
    by: dict[str, list[dict[str, Any]]] = {}
    for r in store.values():
        if isinstance(r, dict) and r.get("series"):
            by.setdefault(str(r["series"]), []).append(r)
    out: dict[str, list[dict[str, Any]]] = {}
    for name, rows in by.items():
        rows.sort(key=lambda r: (str(r["available_time"]), str(r["period"])))
        vals: list[float] = []
        chgs: list[float] = []
        pts: list[dict[str, Any]] = []
        for r in rows:
            v = float(r["value_first"])
            chg = v - vals[-1] if vals else None
            pts.append({"event_time": r["period"], "available_time": r["available_time"],
                        "first_seen_at": r["first_seen_at"], "revision_time": r.get(
                            "revision_time"), "pit_quality": r.get("pit_quality"),
                        "value": v, "z": _z(vals, v),
                        "chg": None if chg is None else round(chg, 8),
                        "chg_z": None if chg is None else _z(chgs, chg)})
            vals.append(v)
            if chg is not None:
                chgs.append(chg)
        out[name] = pts
    return out


def lake_name(sid: str, series: str) -> str:
    return f"ks_{sid}__{series}"


def write_lake(paths: Paths, sid: str, pts: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    import pandas as pd
    paths.series.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, rows in pts.items():
        if not rows:
            continue
        df = pd.DataFrame([{**p, "source_id": sid,
                            "vintage_id": f"{sid}:{p['first_seen_at']}"} for p in rows])
        target = paths.series / f"{lake_name(sid, name)}.csv"
        tmp = target.with_suffix(f".tmp{os.getpid()}")
        df.to_csv(tmp, index=False)
        os.replace(tmp, target)
        written.append(target.name)
    return written


# ----------------------------------------------------------------------------- cells ------
def _hypothesis_symbols(paths: Paths, syms: list[str]) -> list[str]:
    uni = _read(paths.universe, {}) or {}
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        def may_hypothesise(symbol: str, family: object = None) -> bool:
            return True
    return [s for s in syms if s in uni and may_hypothesise(s)]


def indirect_ready() -> str | None:
    """None when `cell_modifiers` applies `alt:` conditioners; else the named blocker."""
    try:
        from mt5desk import cell_modifiers
    except Exception as exc:
        return f"BLOCKED_DEPENDENCY:mt5desk.cell_modifiers ({type(exc).__name__})"
    if not hasattr(cell_modifiers, "alt_conditioner"):
        return ("BLOCKED_DEPENDENCY:mt5desk.cell_modifiers has no alt: conditioner yet (lands "
                "with #131); the indirect arm mints nothing a gauntlet would refuse")
    return None


def _parents(paths: Paths) -> dict[str, list[dict[str, Any]]]:
    rows = (_read(paths.survivors, {}) or {}).get("survivors")
    out: dict[str, list[dict[str, Any]]] = {}
    for name, v in sorted(rows.items()) if isinstance(rows, dict) else []:
        spec = (v or {}).get("shadow_spec") if isinstance(v, dict) else None
        if isinstance(spec, dict) and spec.get("family") and spec.get("symbol"):
            out.setdefault(str(spec["symbol"]), []).append({"name": name, **spec})
    return out


def _base(row: Mapping[str, Any], sym: str, series: str, now: datetime) -> dict[str, Any]:
    stamp = now.isoformat(timespec="seconds")
    return {"symbols": [sym], "available_time": stamp, "event_time": stamp,
            **{k: row.get(k, UNMEASURED) for k in CULTURE_KEYS},
            "uses": row.get("uses"), "credential_var": (row.get("key_env") or [None])[0],
            "required_data": [f"desks/mt5/data/lake/series/{lake_name(row['id'], series)}.csv"]}


def build_grid(paths: Paths, roster: list[dict[str, Any]], pts_by: Mapping[str, Any],
               now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from proposer_common import candidate
    direct: list[dict[str, Any]] = []
    indirect: list[dict[str, Any]] = []
    blocker = indirect_ready()
    parents = {} if blocker else _parents(paths)
    skipped: dict[str, str] = {}
    for row in roster:
        sid = str(row["id"])
        per = pts_by.get(sid) or {}
        for series, spec in sorted((row.get("series") or {}).items()):
            pts = per.get(series) or []
            if len(pts) < MIN_POINTS:
                skipped[f"{sid}.{series}"] = f"{len(pts)} points < {MIN_POINTS}"
                continue
            syms = _hypothesis_symbols(paths, sorted((spec or {}).get("instruments") or {}))
            src = lake_name(sid, series)
            for sym in syms:
                mech = f"{row.get('mechanism', sid)}; {series} conditions {sym}"
                for t, thr, side in product(*EXO_GRID.values()):
                    c = candidate(SEAT, sym, "exogenous_conditioner",
                                  {"source": src, "signal": "value", "transform": t,
                                   "threshold": thr, "side_when_high": side, "lag_hours": 24},
                                  mech, f"{series} ({t} {thr}) -> {sym} [{sid}]",
                                  {"source_row": sid, "series": series, "arm": "direct"})
                    c.update(_base(row, sym, series, now))
                    c["falsifier"] = (f"{src} {t} beyond {thr} sd carries no out-of-sample "
                                      f"information about {sym} H1 returns")
                    direct.append(c)
                for par in parents.get(sym, [])[:PARENTS_PER_SYMBOL]:
                    for op in ("gt", "lt"):
                        params = dict(par.get("params") or {})
                        if par.get("selector") and "session" not in params:
                            params["session"] = str(par["selector"])
                        params["conditioner"] = f"alt:{src}:chg_z:{op}:0"
                        c = candidate(INDIRECT_SEAT, sym, str(par["family"]), params,
                                      f"{par['family']} gated by {series} change regime",
                                      f"{par['family']} on {sym} while {series} chg_z {op} 0",
                                      {"source_row": sid, "series": series, "arm": "indirect",
                                       "parent": par["name"]})
                        c.update(_base(row, sym, series, now))
                        c["falsifier"] = ("the conditioned child is no better than its certified "
                                          "parent on the same window")
                        indirect.append(c)
    return direct, indirect, {"indirect_blocker": blocker, "skipped": skipped}


def _ring(grid: list[dict[str, Any]], at: int, n: int) -> tuple[list[dict[str, Any]], int]:
    if not grid:
        return [], 0
    start = at % len(grid)
    take = (grid[start:] + grid[:start])[:n]
    return take, (start + len(take)) % len(grid)


Donate = Callable[[str, list[dict[str, Any]], int], dict[str, Any]]


def _donate(seat: str, cands: list[dict[str, Any]], tests_run: int) -> dict[str, Any]:
    if not cands:
        return {"donated": 0, "path": None}
    from proposer_common import donate, donation_counts
    path = donate(seat, cands, tests_run)
    return {**donation_counts(), "path": str(path) if path else None}


# ------------------------------------------------------------------------ allocation ------
def allocation_intel(roster: list[dict[str, Any]], pts_by: Mapping[str, Any],
                     now: datetime) -> dict[str, Any]:
    inst: dict[str, list[dict[str, Any]]] = {}
    for row in roster:
        for series, spec in (row.get("series") or {}).items():
            known = [p for p in (pts_by.get(row["id"]) or {}).get(series) or []
                     if (_t(p["available_time"]) or now) <= now]
            if not known:
                continue
            p = known[-1]
            for sym, prior in ((spec or {}).get("instruments") or {}).items():
                inst.setdefault(sym, []).append({
                    "source": row["id"], "series": series, "prior_sign": prior,
                    "z": p.get("z"), "chg_z": p.get("chg_z"), "period": p["event_time"],
                    "available_time": p["available_time"], "pit_quality": p.get("pit_quality"),
                    "source_culture": row.get("source_culture")})
    return {"generated_at": now.isoformat(timespec="seconds"), "use": "allocation_intel",
            "rule": "read-only PIT state per instrument; sizes nothing, the allocator is not "
                    "edited", "instruments": dict(sorted(inst.items()))}


# ------------------------------------------------------------------------------ pass ------
def run(paths: Paths = Paths(), *, budget_s: float = 300.0, fetch: bool = True,
        dry_run: bool = False, get: Getter = http, donate: Donate = _donate,
        now: datetime | None = None, environ: Mapping[str, str] | None = None,
        telegram_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    deadline = t0 + budget_s * 0.7
    roster, bad = load_roster(paths.roster)
    state = _read(paths.state, {}) or {}
    sst: dict[str, Any] = state.setdefault("sources", {})
    order = sorted(roster, key=lambda r: str((sst.get(r["id"]) or {}).get("last_attempt") or ""))
    recs: dict[str, dict[str, Any]] = {}
    pts_by: dict[str, Any] = {}
    for row in order:
        sid = str(row["id"])
        st = sst.setdefault(sid, {})
        store_p = paths.obs / f"{sid}.json"
        store = _read(store_p, {}) or {}
        rec: dict[str, Any] = {"kind": row["kind"], "credential_vars": row.get("key_env"),
                               "store_rows": len(store)}
        try:
            resolve_keys(row, environ)
            due = _t(st.get("next_due"))
            if not fetch:
                rec["status"] = "NO_FETCH"
            elif due and due > now:
                rec["status"] = "NOT_DUE"
                rec["next_due"] = st["next_due"]
            elif time.monotonic() > deadline:
                rec["status"] = "OWED"
                rec["why"] = "pass budget reached; stalest-first order reaches it next pass"
            else:
                st["last_attempt"] = now.isoformat(timespec="seconds")
                PARTIAL_ERRORS.clear()
                start = (now - timedelta(days=21)).date().isoformat() if store else None
                obs = collect(row, get=get, now=now, paths=paths, start=start,
                              environ=environ, telegram_factory=telegram_factory)
                m = merge(store, row, obs, now, backfill=not st.get("last_success"))
                _atomic(store_p, store)
                st["last_success"] = now.isoformat(timespec="seconds")
                st["errors"] = 0
                rec.update({"status": "OK" if obs else "EMPTY", "parsed": len(obs), **m,
                            "store_rows": len(store)})
                if PARTIAL_ERRORS:
                    rec["partial_errors"] = list(PARTIAL_ERRORS)
                st["next_due"] = (now + timedelta(hours=CADENCE_H.get(str(row["cadence"]),
                                                                      24.0))).isoformat()
        except Blocked as b:
            rec["status"] = str(b)
        except Exception as exc:
            st["errors"] = int(st.get("errors") or 0) + 1
            st["next_due"] = (now + timedelta(hours=CADENCE_H.get(str(row["cadence"]), 24.0))
                              ).isoformat()
            rec.update({"status": "ERROR", "error": str(exc)[:300]})
        _atomic(paths.state, state)
        pts = points(store)
        pts_by[sid] = pts
        rec["lake"] = write_lake(paths, sid, pts) if pts else []
        rec["series_points"] = {k: len(v) for k, v in pts.items()}
        recs[sid] = rec
    direct, indirect, meta = build_grid(paths, roster, pts_by, now)
    take_d, nd = _ring(direct, int(state.get("direct_cursor") or 0), PER_PASS)
    take_i, ni = _ring(indirect, int(state.get("indirect_cursor") or 0),
                       max(0, PER_PASS - len(take_d)))
    don = {"direct": {"donated": 0}, "indirect": {"donated": 0}}
    if not dry_run:
        don["direct"] = donate(SEAT, take_d, len(take_d))
        don["indirect"] = donate(INDIRECT_SEAT, take_i, len(take_i))
        state["direct_cursor"], state["indirect_cursor"] = nd, ni
        _atomic(paths.state, state)
    by_var: dict[str, int] = {}
    for c in take_d + take_i:
        v = str(c.get("credential_var"))
        by_var[v] = by_var.get(v, 0) + 1
    _atomic(paths.allocation, allocation_intel(roster, pts_by, now))
    doc = {"generated_at": now.isoformat(timespec="seconds"),
           "writer": "research/keyed_sources.py", "roster": str(paths.roster.name),
           "roster_complaints": bad, "sources": recs,
           "status_counts": _counts(recs),
           "cells": {"grid_direct": len(direct), "grid_indirect": len(indirect),
                     "built_direct": len(take_d), "built_indirect": len(take_i),
                     "minted": int(don["direct"].get("donated") or 0)
                     + int(don["indirect"].get("donated") or 0),
                     "trials_charged": 0 if dry_run else len(take_d) + len(take_i),
                     "by_var": by_var, "donation": don, **meta},
           "status": "DRY_RUN" if dry_run else "RAN",
           "seconds": round(time.monotonic() - t0, 1),
           "rule": ("BLOCKED_AUTH:<VAR> until the key is set -- a named state, never 0; every "
                    "minted cell is charged through tests_run on its donation file")}
    _atomic(paths.report, doc)
    return doc


def _counts(recs: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in recs.values():
        k = str(r.get("status", "")).split(":", 1)[0]
        out[k] = out.get(k, 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, fetch=not a.no_fetch, dry_run=a.dry_run)
    print(f"keyed_sources: {doc['status_counts']}; grid {doc['cells']['grid_direct']}+"
          f"{doc['cells']['grid_indirect']}, minted {doc['cells']['minted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
