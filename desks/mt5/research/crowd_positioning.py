#!/usr/bin/env python3
"""CROWD POSITIONING -- record retail long/short share point-in-time, and mint contrarian cells.

WHY (principal 2026-10-13, yes to the retail-behaviour ideas; tier-1 GAP_MAP rows 24-27). The
retail crowd's net position is one of the few behavioural series a desk can observe directly,
and the mechanism is a SUPPLY OF STOPS: when the crowd is heavily one way, the stops that will
be hit sit on the other side of price. The tradable claim is the EXTREMITY and its change, faded
on the same symbol, and the crowd regime as a condition on price families that already exist.

WHAT WAS THERE, AND WHY IT NEVER PRODUCED A ROW. `asia_sources.json` registers
`myfxbook_outlook` against Myfxbook's official API, keyed on `MYFXBOOK_SESSION`. Three things
stopped it: the variable was never set on the box (ASIA_COLLECTOR read UNCONFIGURED), a Myfxbook
session is minted by the API's own `login.json` and expires, so a static value would have died
anyway, and the collector never puts a key into the URL, so even a set session would have been
sent nowhere. The web page itself sits behind a Cloudflare challenge, and that is never crossed.

WHAT THIS DOES, hourly (the free tier allows 100 outlook calls a day):
  1. SESSION. `MYFXBOOK_SESSION` if set; else `login.json` with `MYFXBOOK_EMAIL` and
     `MYFXBOOK_PASSWORD`, the session cached under `data/secrets/` (never committed, never
     printed). An "invalid session" answer re-logs in once. No credentials: BLOCKED_ON_KEY, named.
  2. RECORD. One row per call into `data/lake/series/myfxbook_outlook.parquet`, the pack's own
     canonical frame, stamped `available_time` = the moment this desk received it. Columns per
     symbol: `<SYM>_long_pct`, `<SYM>_long_vol_pct` (volume-weighted), `<SYM>_positions`. That is
     the frame `family_exogenous_conditioner.conditioner` and `pack_cells` already read.
  3. CELLS. Per symbol in the MT5 universe, once its column holds MIN_OBSERVATIONS rows, the
     preregistered grid below is donated ONCE through `proposer_common.donate`:
       fade      exogenous_conditioner on `<SYM>_long_pct`, level_z and delta_z, thresholds 1.0 /
                 1.5 / 2.0, side_when_high -1 (the contrarian claim) AND +1 (its control)
       regime    alt_conditioned children of the price families the desk certifies most on this
                 symbol class, kept only in the crowd's high / low / mid regime
     `lag_hours` is 4: the bars are broker time (UTC+2/+3), so a 4-hour hold-back is the
     shortest that cannot join a reading to a bar before the desk had it.

NO HISTORY EXISTS BEFORE THE FIRST CALL. Myfxbook publishes no outlook history, so every day not
recorded is a day no backtest will ever have. The recorder therefore runs before anything is
minted, and the cells wait on observed history, never on a backfill nobody can make.

Artifact: `reports/CROWD_POSITIONING.json`. Clock: hourly leg `crowd_positioning`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "myfxbook_outlook"
API = "https://www.myfxbook.com/api"
SERIES = BASE / "data" / "lake" / "series" / f"{SOURCE}.parquet"
SESSION_CACHE = BASE / "data" / "secrets" / "myfxbook_session.json"
STATE = BASE / "data" / "crowd_positioning_state.json"
OUT = BASE / "reports" / "CROWD_POSITIONING.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
UNMEASURED = "UNMEASURED"
ENV_SESSION, ENV_EMAIL, ENV_PASSWORD = "MYFXBOOK_SESSION", "MYFXBOOK_EMAIL", "MYFXBOOK_PASSWORD"
MIN_CALL_GAP_S = 50 * 60            # hourly, inside the free tier's 100 calls a day
MIN_OBSERVATIONS = 30               # family_exogenous_conditioner.MIN_OBSERVATIONS
LAG_HOURS = 4
THRESHOLDS = (1.0, 1.5, 2.0)
TRANSFORMS = ("level_z", "delta_z")
REGIMES = ("high", "low", "mid")
#: Price families the crowd regime conditions. Each is price-only and wrappable by
#: `alt_conditioned`; the un-conditioned base cell is the control arm already in the docket.
REGIME_BASES = ("overnight_gap_decay", "session_range_breakout", "mean_reversion_rsi")


class SessionError(Exception):
    """The API refused the session or the login."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A credential-bearing URL never follows a redirect anywhere."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def _get(endpoint: str, query: dict[str, str], timeout: float = 25.0) -> dict[str, Any]:
    """GET one API endpoint. Errors carry the endpoint only: the query holds credentials."""
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(query)}"
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk-collector/1.0"})
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read(2_000_000)
    except urllib.error.HTTPError as e:
        raise OSError(f"{endpoint}: HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise OSError(f"{endpoint}: {type(e).__name__}") from None
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        raise OSError(f"{endpoint}: not JSON (an interstitial, not the API)") from None
    if not isinstance(doc, dict):
        raise OSError(f"{endpoint}: unexpected shape")
    return doc


def read_key(name: str) -> str:
    """One key from wherever the box keeps it: `libs.ops.env_keys.read_key` once it lands, else
    the process environment, then the Windows Machine and User registry scopes.

    THE SCOPE MATTERS (keys thread, 2026-10-13): the Myfxbook pair was set at USER scope, and a
    task running as SYSTEM does not inherit a user's environment. Reading the registry directly
    is what the shared reader does; the caller names BLOCKED_ON_KEY when every scope is empty.
    """
    try:
        import importlib
        return str(importlib.import_module("libs.ops.env_keys").read_key(name) or "")
    except Exception:
        pass
    val = os.environ.get(name, "")
    if val:
        return val
    try:
        import importlib
        winreg: Any = importlib.import_module("winreg")
    except ImportError:
        return ""
    for hive, sub in ((winreg.HKEY_LOCAL_MACHINE,
                       r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(hive, sub) as k:
                got = winreg.QueryValueEx(k, name)[0]
                if got:
                    return str(got)
        except OSError:
            continue
    return ""


def credentials() -> tuple[str, str, str]:
    """(session, email, password) from every scope; empty strings where unset."""
    return (read_key(ENV_SESSION).strip(), read_key(ENV_EMAIL).strip(), read_key(ENV_PASSWORD))


def session(*, fresh: bool = False) -> str:
    """A live session: the environment's, the cached one, or a new login. Raises SessionError."""
    env_session, email, password = credentials()
    if env_session and not fresh:
        return env_session
    if not fresh:
        cached = _read(SESSION_CACHE)
        if isinstance(cached, dict) and cached.get("session"):
            return str(cached["session"])
    if not (email and password):
        raise SessionError(f"BLOCKED_ON_KEY: {ENV_EMAIL} + {ENV_PASSWORD} (or "
                           f"{ENV_SESSION}) unreadable in the process env and the Machine and "
                           f"User registry scopes; the pair was set at User scope, which a "
                           f"SYSTEM task does not see")
    doc = _get("login.json", {"email": email, "password": password})
    if doc.get("error") or not doc.get("session"):
        raise SessionError(f"login refused: {str(doc.get('message') or 'no message')[:80]}")
    tok = urllib.parse.unquote(str(doc["session"]))
    _write(SESSION_CACHE, {"session": tok, "minted_at": _now().isoformat()})
    return tok


def outlook() -> dict[str, Any]:
    """The community outlook, re-logging in once on an invalid session."""
    for attempt in (0, 1):
        doc = _get("get-community-outlook.json", {"session": session(fresh=attempt == 1)})
        if not doc.get("error"):
            return doc
        if attempt == 0 and "session" in str(doc.get("message") or "").lower():
            continue
        raise SessionError(f"outlook refused: {str(doc.get('message') or '')[:80]}")
    raise SessionError("outlook refused twice")             # pragma: no cover - loop exits


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def outlook_row(doc: dict[str, Any], at: datetime) -> dict[str, Any]:
    """One wide PIT row: three columns per symbol plus the envelope stamps."""
    stamp = at.isoformat()
    row: dict[str, Any] = {"available_time": stamp, "retrieval_time": stamp,
                           "source_id": SOURCE}
    for s in doc.get("symbols") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        sym = str(s["name"]).upper().replace("/", "").replace(".", "")
        lp, lv, sv = _f(s.get("longPercentage")), _f(s.get("longVolume")), _f(s.get("shortVolume"))
        if lp is not None:
            row[f"{sym}_long_pct"] = lp
        if lv is not None and sv is not None and lv + sv > 0:
            row[f"{sym}_long_vol_pct"] = round(100.0 * lv / (lv + sv), 4)
        pos = _f(s.get("totalPositions"))
        if pos is not None:
            row[f"{sym}_positions"] = pos
    return row


def append_row(row: dict[str, Any], path: Path | None = None) -> int:
    """Append to the pack's canonical frame; returns the frame's row count."""
    import pandas as pd
    p = path or SERIES
    p.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame([row])
    if p.exists():
        try:
            new = pd.concat([pd.read_parquet(p), new], ignore_index=True, sort=False)
        except Exception:
            # An unreadable frame is moved aside, never overwritten: it is the only history.
            p.rename(p.with_suffix(f".corrupt_{int(time.time())}.parquet"))
    new = new.drop_duplicates(subset=["available_time"], keep="last")
    tmp = p.with_suffix(".parquet.tmp")
    new.to_parquet(tmp, index=False)
    tmp.replace(p)
    return len(new)


def history(path: Path | None = None) -> dict[str, int]:
    """Non-null observations per `<SYM>_long_pct` column."""
    p = path or SERIES
    if not p.exists():
        return {}
    import pandas as pd
    try:
        df = pd.read_parquet(p)
    except Exception:
        return {}
    return {c[:-len("_long_pct")]: int(df[c].notna().sum())
            for c in df.columns if str(c).endswith("_long_pct")}


def universe_symbols() -> set[str]:
    doc = _read(UNIVERSE)
    rows = doc.get("symbols", doc) if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        return {str(k).upper() for k in rows}
    if isinstance(rows, list):
        return {str(r.get("symbol") or r.get("name") or "").upper()
                for r in rows if isinstance(r, dict)} - {""}
    return set()


def grid(sym: str) -> list[tuple[str, str, dict[str, Any]]]:
    """(ident, family, params) for one symbol: the preregistered fade and regime cells."""
    sig = f"{sym}_long_pct"
    base = {"source": SOURCE, "signal": sig, "lag_hours": LAG_HOURS}
    cells: list[tuple[str, str, dict[str, Any]]] = []
    for tf in TRANSFORMS:
        for thr in THRESHOLDS:
            for side in (-1, 1):
                p = {**base, "transform": tf, "threshold": thr, "side_when_high": side}
                cells.append((f"{sym}|fade|{tf}|{thr}|{side}", "exogenous_conditioner", p))
    for fam in REGIME_BASES:
        for regime in REGIMES:
            p = {**base, "transform": "level_z", "regime": regime, "threshold": 1.0,
                 "base_family": fam, "base_params": {}}
            cells.append((f"{sym}|regime|{fam}|{regime}", "alt_conditioned", p))
    return cells


def mint(counts: dict[str, int], universe: set[str], state: dict[str, Any], *,
         dry_run: bool = False) -> dict[str, Any]:
    """Donate every not-yet-donated grid cell on a symbol with enough recorded history."""
    cells = state.setdefault("cells", {})
    ready = sorted(s for s, n in counts.items() if n >= MIN_OBSERVATIONS
                   and (not universe or s in universe))
    waiting = {s: n for s, n in counts.items() if n < MIN_OBSERVATIONS}
    todo = [(sym, ident, fam, p) for sym in ready for ident, fam, p in grid(sym)
            if not (cells.get(ident) or {}).get("donated_at")]
    out: dict[str, Any] = {"symbols_ready": ready, "symbols_waiting": waiting,
                           "cells_due": len(todo), "donated": 0}
    if not todo or dry_run:
        return out
    from research import proposer_common as pc
    mech = ("RETAIL CROWDING, observed: a one-sided crowd is a supply of stops on the other "
            "side of price; the extremity of its long share, and its change, carry the claim")
    rows = [pc.candidate(SOURCE, sym, fam, {**p, "symbol": sym}, mech,
                         f"{sym} {fam} crowd {ident.split('|', 2)[1]}",
                         {"observations": counts.get(sym), "min_observations": MIN_OBSERVATIONS,
                          "lag_hours": LAG_HOURS,
                          "preregistered_grid": "fixed in crowd_positioning.grid"})
            for sym, ident, fam, p in todo]
    path = pc.donate(SOURCE, rows, len(rows))
    got = pc.donation_counts()
    out.update(donated=int(got.get("donated") or 0), path=str(path) if path else None,
               refused_wrong_lane=got.get("refused_wrong_lane"),
               refused_unstamped=got.get("refused_unstamped"))
    if path:
        at = _now().isoformat()
        for _sym, ident, _fam, _p in todo:
            cells[ident] = {"donated_at": at}
    return out


def run(*, dry_run: bool = False, out: Path | None = None) -> dict[str, Any]:
    now = _now()
    state = _read(STATE) or {}
    rec: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "producer": "desks/mt5/research/crowd_positioning.py",
                           "source": SOURCE, "series": f"data/lake/series/{SOURCE}.parquet"}
    last = state.get("last_call_at")
    gap = None
    if last:
        try:
            gap = (now - datetime.fromisoformat(str(last))).total_seconds()
        except ValueError:
            gap = None
    if gap is not None and gap < MIN_CALL_GAP_S:
        rec["record"] = {"status": "NOT_DUE", "seconds_since_last_call": round(gap)}
    elif dry_run:
        rec["record"] = {"status": "DRY_RUN"}
    else:
        state["last_call_at"] = now.isoformat()
        try:
            row = outlook_row(outlook(), now)
            n_sym = sum(1 for k in row if k.endswith("_long_pct"))
            rows = append_row(row) if n_sym else None
            rec["record"] = {"status": "RECORDED" if n_sym else "EMPTY", "symbols": n_sym,
                             "frame_rows": rows}
        except SessionError as exc:
            rec["record"] = {"status": str(exc).split(":")[0] if str(exc).startswith(
                "BLOCKED_ON_KEY") else "REFUSED", "why": str(exc)}
        except OSError as exc:
            rec["record"] = {"status": "UNREACHABLE", "why": str(exc)}
    counts = history()
    rec["history"] = {"symbols": len(counts), "observations": counts or UNMEASURED}
    rec["cells"] = mint(counts, universe_symbols(), state, dry_run=dry_run)
    if not dry_run:
        _write(STATE, state)
    _write(out or OUT, rec)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    rec = run(dry_run=args.dry_run, out=args.out)
    print(f"crowd_positioning: record={rec['record'].get('status')} "
          f"symbols={rec['history']['symbols']} donated={rec['cells'].get('donated')} "
          f"due={rec['cells'].get('cells_due')}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
