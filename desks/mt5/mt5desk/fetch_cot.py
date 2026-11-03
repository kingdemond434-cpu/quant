"""Fetch CFTC legacy futures-only COT for the full desk universe.

Data: CFTC Socrata "Disaggregated Futures-Only" schema 6dca-aqww (legacy
noncomm/comm series, history to 1986). Weekly, report date = Tuesday,
published Friday ~19:30 UTC. noncomm = large speculators; comm = commercials.

Contracts: gold, silver, FX currencies (each MT5 pair maps to one currency
future), US dollar index, S&P 500, NASDAQ 100 (conditioning-only).

Output: data/cot/{slug}.parquet per contract + data/cot_gold.parquet (legacy).
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
from mt5desk.config import DATA  # noqa: E402

OUT = DATA / "cot"

# THE DESK'S HONEST USER-AGENT, never a browser string (auditor ruling 2026-10-14). This sent
# "Mozilla/5.0". The one definition is `libs.data.polite_fetch.DESK_UA`, which lands with the data
# line; until that module carries it this falls back to the identical text, and it switches to
# the import the moment the attribute exists -- no edit here.
try:
    from libs.data import polite_fetch as _pf
    UA: str = str(_pf.DESK_UA)  # type: ignore[attr-defined,unused-ignore]
except (ImportError, AttributeError):
    UA = ("quant-mt5-research-desk/1.0 (+https://github.com/kingdemond434-cpu/quant/issues; "
          "internal research; honours robots.txt)")
UA_PRODUCT = UA.split("/", 1)[0]
#: AN ACCESS CONTROL is a HARD STOP, never retried around: the run ends and the leg holds until a
#: person clears it (`research/cot_fx_refresh.py`). That is LAWS 5e's hard boundary act 2 ("no
#: bypassing an access control"), and it is the ONLY refusal here: a robots.txt Disallow and an
#: unreadable robots.txt are routing labels on the row, never a stop (5e REMOVED_BRAKES).
HARD_STOP_STATUS: frozenset[int] = frozenset({401, 403, 429})


class HardStop(RuntimeError):
    """An access control answered (401/403/429, or a WAF / challenge page). Nothing more is
    fetched, and the clock holds until a person clears it."""


Opener = Callable[[urllib.request.Request, float], Any]


def _open(req: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(req, timeout=timeout)


def robots_url(url: str) -> str:
    """The robots.txt that governs `url`: its own scheme and host."""
    u = urllib.parse.urlsplit(url)
    return f"{u.scheme}://{u.netloc}/robots.txt"


#: THE ACCESS LABELS this writer can put on a fetch, in LAWS 5e's vocabulary
#: (`libs.research.access_classifier.ACCESS_LABELS`). CFTC data is an official public release.
PUBLIC = "PUBLIC"
PUBLIC_WITH_TERMS = "PUBLIC_WITH_TERMS"
ACCESS_UNCLEAR = "ACCESS_UNCLEAR"


def redistribute_allowed(label: str) -> bool:
    """Whether the label keeps `redistribute` among its allowed uses (access_classifier.ROUTING);
    False when the classifier cannot be read, because redistribution is the one use a label can
    withhold and it is never assumed."""
    try:
        from libs.research.access_classifier import ROUTING
    except ImportError:
        return False
    row = ROUTING.get(label)  # type: ignore[call-overload]
    return bool(row) and "redistribute" in tuple(row.get("allowed_uses") or ())


def access_label(url: str, opener: Opener = _open) -> dict[str, Any]:
    """robots.txt READ AS A LABEL, never as a refusal (LAWS 5e: "robots.txt Disallow read as a
    refusal" is a deleted brake). Read from the URL's own host (shared with `fetch_tff`, whose
    bulk files live on www.cftc.gov):

        allowed, or absent (404)   -> PUBLIC
        an explicit Disallow       -> PUBLIC_WITH_TERMS, the Disallow carried as terms_note
        unreadable (timeout, DNS,  -> ACCESS_UNCLEAR, mined with the label attached
          a 5xx, any transport error)
        401 / 403 / 429            -> HardStop: an access control (hard boundary act 2)

    `redistribute_allowed` comes from the classifier's routing table: false for all three here,
    since none of them is an open-data licence."""
    req = urllib.request.Request(robots_url(url), headers={"User-Agent": UA})
    label, note = PUBLIC, ""
    try:
        with opener(req, 30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in HARD_STOP_STATUS:
            raise HardStop(f"robots.txt answered HTTP {exc.code}") from exc
        if exc.code == 404:
            note = "robots.txt absent (404): no rules"
        else:
            label, note = ACCESS_UNCLEAR, f"robots.txt unreadable (HTTP {exc.code})"
        text = ""
    except (OSError, ValueError) as exc:
        label, note = ACCESS_UNCLEAR, f"robots.txt unreadable ({type(exc).__name__})"
        text = ""
    if text:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(text.splitlines())
        if rp.can_fetch(UA_PRODUCT, url):
            note = "robots.txt allows"
        else:
            label = PUBLIC_WITH_TERMS
            note = (f"robots.txt Disallow for {UA_PRODUCT} on this path: mined in full, "
                    "redistribution withheld (LAWS 5e)")
    return {"access_label": label, "terms_note": note,
            "redistribute_allowed": redistribute_allowed(label)}


def label_rows(df: pd.DataFrame, access: dict[str, Any]) -> pd.DataFrame:
    """The fetch's access label ON THE DATA ROWS, so it travels with every reader."""
    out = df.copy()
    for k in ("access_label", "terms_note", "redistribute_allowed"):
        out[k] = access[k]
    return out


def _terms_check(url: str) -> None:
    """The data line's per-source policy, when it is on this tree: a held source raises. CFTC has
    no SOURCE_POLICY row, so the policy's PUBLIC_PAGE default for an unlisted host applies."""
    try:
        from libs.data import terms_fence  # type: ignore[attr-defined]
    except ImportError:
        return
    check = getattr(terms_fence, "check_url", None)
    if callable(check):
        try:
            check(url)
        except Exception as exc:
            raise HardStop(f"terms_fence holds {url}: {exc}") from exc


SELECT = (
    "report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,open_interest_all,"
    "noncomm_positions_long_all,noncomm_positions_short_all,"
    "comm_positions_long_all,comm_positions_short_all,"
    "change_in_noncomm_long_all,change_in_noncomm_short_all,"
    "change_in_open_interest_all"
)

# commodity_name candidates tried in order (first non-empty wins)
TARGETS: list[tuple[str, list[str]]] = [
    ("gold", ["GOLD"]),
    ("silver", ["SILVER"]),
    ("jpy", ["JAPANESE YEN"]),
    ("eur", ["EURO FX"]),
    ("gbp", ["POUND STERLING"]),
    ("cad", ["CANADIAN DOLLAR"]),
    ("aud", ["AUSTRALIAN DOLLAR"]),
    ("nzd", ["NEW ZEALAND DOLLAR"]),
    ("chf", ["SWISS FRANC"]),
    ("dxy", ["US DOLLAR INDEX", "U.S. DOLLAR INDEX"]),
    ("sp500", ["S&P BROAD BASED STOCK INDICES"]),
    ("nasdaq100", ["NASDAQ  BROADBASED INDICES"]),
]

# MT5 symbol -> cot slug (a pair trades its base-currency future; JPY crosses
# all use the yen contract; conditioning-only symbols DXY/SP500/NDX exposed)
SYMBOL_SLUG = {
    "XAUUSD": "gold", "XAGUSD": "silver",
    "USDJPY": "jpy", "EURJPY": "jpy", "GBPJPY": "jpy", "CADJPY": "jpy",
    "AUDJPY": "jpy", "NZDJPY": "jpy", "CHFJPY": "jpy",
    "EURUSD": "eur", "EURGBP": "eur", "EURCHF": "eur",
    "GBPUSD": "gbp", "USDCAD": "cad", "AUDUSD": "aud", "NZDUSD": "nzd",
    "USDCHF": "chf",
    "DXY": "dxy", "SP500": "sp500", "NDX": "nasdaq100",
}


def fetch_contract(commodity: str, opener: Opener = _open) -> pd.DataFrame | None:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "$where": f"commodity_name='{commodity}'",
            "$select": SELECT,
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": "5000",
            "$offset": str(offset),
        }
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json"})
        try:
            with opener(req, 90) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in HARD_STOP_STATUS:
                raise HardStop(f"HTTP {exc.code} from {BASE}") from exc
            raise
        if raw.lstrip()[:1] not in (b"[", b"{"):
            # A WAF / challenge page answers 200 with HTML. That is a refusal, not data.
            raise HardStop(f"non-JSON answer from {BASE} (a WAF or challenge page)")
        batch = json.load(io.BytesIO(raw))
        rows.extend(batch)
        if len(batch) < 5000:
            break
        offset += 5000
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["report_date_as_yyyy_mm_dd"] = pd.to_datetime(
        df["report_date_as_yyyy_mm_dd"], format="ISO8601", utc=True
    )
    for col in df.columns:
        if col not in ("report_date_as_yyyy_mm_dd", "commodity_name",
                       "contract_market_name"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # prefer the outright contract when multiple markets exist
    best = (df.groupby("contract_market_name").size().idxmax()
            if df["contract_market_name"].nunique() > 1 else df["contract_market_name"].iloc[0])
    df = df[df["contract_market_name"] == best]
    df = df.rename(columns={"report_date_as_yyyy_mm_dd": "report_date"})
    df = df.sort_values("report_date").drop_duplicates("report_date", keep="last")
    return df


def _atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def fetch_all(out: Path | None = None, opener: Opener = _open,
              log: Callable[[str], None] = print) -> dict[str, Any]:
    """Every contract in TARGETS into `out/<slug>.parquet`, each row carrying the fetch's access
    label. Raises HardStop on an access control (nothing after it is fetched); returns per-slug
    rows and newest report date, and the label under "access"."""
    out = out or OUT
    out.mkdir(parents=True, exist_ok=True)
    _terms_check(BASE)
    access = access_label(BASE, opener)
    log(f"access: {access['access_label']} ({access['terms_note']})")
    got: dict[str, Any] = {"access": access}
    for slug, candidates in TARGETS:
        df = None
        for cand in candidates:
            df = fetch_contract(cand, opener)
            if df is not None:
                break
        if df is None or df.empty:
            got[slug] = {"rows": 0, "why": f"no rows for {candidates}"}
            log(f"{slug:>10}: FAILED (no rows for {candidates})")
            continue
        _atomic_parquet(label_rows(df, access), out / f"{slug}.parquet")
        got[slug] = {"rows": len(df), "newest": str(df["report_date"].max().date()),
                     "market": str(df["contract_market_name"].iloc[0])}
        log(f"{slug:>10}: {len(df)} rows  "
            f"{df['report_date'].min().date()} -> {df['report_date'].max().date()}"
            f"  market={df['contract_market_name'].iloc[0]}")
    # legacy gold alias
    g = out / "gold.parquet"
    if g.exists() and out == OUT:
        import shutil
        shutil.copy(g, DATA / "cot_gold.parquet")
        log("legacy cot_gold.parquet refreshed")
    return got


def main() -> None:
    fetch_all()


if __name__ == "__main__":
    main()
