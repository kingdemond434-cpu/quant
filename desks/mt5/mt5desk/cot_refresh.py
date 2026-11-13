"""The weekly COT refresher: legacy, disaggregated and TFF positioning, kept current on the box.

WHY IT EXISTS (Mining v1 / Hourly pass, 2026-11-13). The in-tree COT parquets end 2026-08-11.
Nothing on the box refreshed them, because the three fetchers that wrote them were never
scheduled: two read with TLS verification off and all three sent "Mozilla/5.0". So every COT
family `flow_seeder` revives reads STALE, and a certified COT cell cannot fire forward.

WHAT IT DOES. It reads CFTC Public Reporting (Socrata) through `libs.data.cftc_socrata`, which
verifies TLS, obeys robots.txt and its crawl delay, and sends an honest agent. It writes the SAME
files with the SAME columns the readers already open (`data/cot/<slug>.parquet` plus the legacy
`data/cot_gold.parquet` alias, `data/cot_disagg/<slug>.parquet`, `data/cot_tff/<slug>.parquet`).

  * INCREMENTAL AND LOSSLESS. Each slug re-reads from eight weeks before its newest held date,
    because CFTC re-states recent weeks, and merges with the held rows: fresh wins on a date that
    both carry, and no held date is dropped. A failed fetch leaves the held file exactly as it was.
  * EXACT MARKETS. Rows are selected by exact market name, never by substring. The old TFF
    fetcher matched "EURO FX" as a substring, so `cot_tff/eur.parquet` held EURO FX/BRITISH POUND
    and EURO FX/JAPANESE YEN cross-rate rows on the same dates as the outright, and
    `drop_duplicates` kept whichever came last. sp500 held nine different markets. A held file
    carrying any market outside the slug's accepted names is REBUILT from full history.
  * WEEKLY, SELF-THROTTLED. The CFTC releases Tuesday's positions on Friday at 15:30 ET. A pass
    that finds every slug already holding the latest released Tuesday fetches nothing. That lets
    it ride the box's existing two-hourly `Quant-SideChannelMiners` task, and it still lands
    within two hours of each Friday release.
  * REPORTED. `reports/COT_REFRESH.json` names each slug's newest date, row count and status:
    FRESH, REFRESHED, REBUILT, STALE, FAILED (with why), or DELISTED (a contract the CFTC
    stopped reporting).

    python -m mt5desk.cot_refresh            # from desks/mt5
    python -m mt5desk.cot_refresh --force    # ignore the weekly throttle
"""
from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.append(_p)

from libs.data import cftc_socrata as S  # noqa: E402

DATA = _DESK / "data"
REPORT = _DESK / "reports" / "COT_REFRESH.json"
#: Weeks re-read behind the newest held date; CFTC re-states recent reports.
OVERLAP_WEEKS = 8
#: A held series this many days behind the latest release is STALE in the report.
STALE_DAYS = 10

LEGACY_COLS = ("report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,open_interest_all,"
               "noncomm_positions_long_all,noncomm_positions_short_all,"
               "comm_positions_long_all,comm_positions_short_all,"
               "change_in_noncomm_long_all,change_in_noncomm_short_all,"
               "change_in_open_interest_all")
DISAGG_COLS = ("report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,"
               "futonly_or_combined,open_interest_all,"
               "m_money_positions_long_all,m_money_positions_short_all,"
               "swap_positions_long_all,swap__positions_short_all,"
               "other_rept_positions_long,other_rept_positions_short,"
               "conc_net_le_4_tdr_long_all,conc_net_le_4_tdr_short_all")
TFF_COLS = ("report_date_as_yyyy_mm_dd,market_and_exchange_names,open_interest_all,"
            "dealer_positions_long_all,dealer_positions_short_all,"
            "asset_mgr_positions_long,asset_mgr_positions_short,"
            "lev_money_positions_long,lev_money_positions_short")
#: Socrata TFF field -> the column name the held `cot_tff` files carry.
TFF_RENAME = {"report_date_as_yyyy_mm_dd": "report_date", "market_and_exchange_names": "market",
              "open_interest_all": "oi",
              "dealer_positions_long_all": "dealer_l", "dealer_positions_short_all": "dealer_s",
              "asset_mgr_positions_long": "am_l", "asset_mgr_positions_short": "am_s",
              "lev_money_positions_long": "lm_l", "lev_money_positions_short": "lm_s"}

_CME = " - CHICAGO MERCANTILE EXCHANGE"


@dataclass(frozen=True)
class Target:
    family: str          # "legacy" | "disagg" | "tff"
    slug: str
    names: tuple[str, ...]  # exact contract_market_name (legacy/disagg) or market name (tff)
    delisted: bool = False


TARGETS: tuple[Target, ...] = (
    *(Target("legacy", s, n) for s, n in (
        ("gold", ("GOLD",)), ("silver", ("SILVER",)), ("jpy", ("JAPANESE YEN",)),
        ("eur", ("EURO FX",)), ("gbp", ("BRITISH POUND", "BRITISH POUND STERLING")),
        ("cad", ("CANADIAN DOLLAR",)), ("aud", ("AUSTRALIAN DOLLAR",)),
        ("nzd", ("NZ DOLLAR", "NEW ZEALAND DOLLAR")), ("chf", ("SWISS FRANC",)),
        ("dxy", ("USD INDEX", "U.S. DOLLAR INDEX")), ("nasdaq100", ("NASDAQ MINI",)),
        # CFTC VIX futures positioning (Cboe Futures Exchange, code 1170E1, from 2006): the
        # lawful implied-vol conditioner for US500/NAS100 now Yahoo and FRED are refused.
        ("vix", ("VIX FUTURES",)))),
    # The big S&P 500 contract stopped trading in 2021; its file is kept, never extended with
    # the E-mini (a different contract on the same dates would contaminate it).
    Target("legacy", "sp500", ("S&P 500 STOCK INDEX",), delisted=True),
    Target("disagg", "gold", ("GOLD",)),
    Target("disagg", "silver", ("SILVER",)),
    Target("tff", "vix", ("VIX FUTURES - CBOE FUTURES EXCHANGE",)),
    *(Target("tff", s, tuple(n + _CME for n in names)) for s, names in (
        ("jpy", ("JAPANESE YEN",)), ("eur", ("EURO FX",)),
        ("gbp", ("BRITISH POUND", "BRITISH POUND STERLING")), ("cad", ("CANADIAN DOLLAR",)),
        ("aud", ("AUSTRALIAN DOLLAR",)), ("nzd", ("NZ DOLLAR", "NEW ZEALAND DOLLAR")),
        ("chf", ("SWISS FRANC",)),
        ("sp500", ("E-MINI S&P 500", "E-MINI S&P 500 STOCK INDEX")),
        ("nasdaq100", ("NASDAQ MINI", "NASDAQ-100 STOCK INDEX (MINI)")))),
)

DATASET = {"legacy": S.LEGACY, "disagg": S.DISAGG, "tff": S.TFF}
FOLDER = {"legacy": "cot", "disagg": "cot_disagg", "tff": "cot_tff"}
NAME_FIELD = {"legacy": "contract_market_name", "disagg": "contract_market_name",
              "tff": "market_and_exchange_names"}
HELD_NAME = {"legacy": "contract_market_name", "disagg": "contract_market_name", "tff": "market"}
SELECT = {"legacy": LEGACY_COLS, "disagg": DISAGG_COLS, "tff": TFF_COLS}
TEXT = {"commodity_name", "contract_market_name", "futonly_or_combined", "market"}


def latest_release(now: datetime) -> pd.Timestamp:
    """The newest Tuesday whose report is public at `now`: Friday 15:30 ET, taken as 21:00 UTC
    so the check never runs ahead of the release in either daylight regime."""
    now = now.astimezone(UTC)
    day = now.date()
    friday = day - timedelta(days=(day.weekday() - 4) % 7)
    released = datetime(friday.year, friday.month, friday.day, 21, tzinfo=UTC)
    if now < released:
        friday -= timedelta(days=7)
    return pd.Timestamp(friday - timedelta(days=3), tz="UTC")


def path_of(t: Target, data: Path = DATA) -> Path:
    return data / FOLDER[t.family] / f"{t.slug}.parquet"


def held(t: Target, data: Path = DATA) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path_of(t, data))
    except Exception:
        return None
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True)
    return df


def contaminated(t: Target, df: pd.DataFrame | None) -> bool:
    """True when the held file carries a market outside the slug's accepted names."""
    if df is None or HELD_NAME[t.family] not in df.columns:
        return False
    return bool(set(df[HELD_NAME[t.family]].astype(str)) - set(t.names))


def frame(t: Target, rows: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Socrata rows -> the held file's schema, one row per report date."""
    df = pd.DataFrame(list(rows))
    if df.empty:
        return df
    if t.family == "tff":
        df = df.rename(columns=TFF_RENAME)
    else:
        df = df.rename(columns={"report_date_as_yyyy_mm_dd": "report_date"})
    df["report_date"] = pd.to_datetime(df["report_date"], format="ISO8601", utc=True)
    for c in df.columns:
        if c not in TEXT and c != "report_date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("report_date").drop_duplicates("report_date", keep="last")


#: When this desk FIRST saw each row (UTC), an upper bound on its public release time. CFTC
#: releases slip (holiday Mondays push Friday to Monday; a shutdown backlogs weeks), so a reader
#: that needs point-in-time truth bounds availability by this, never by report_date + 3 days.
#: Rows held before the column existed carry NaT: their first sight was never recorded, and the
#: refresher does not invent one (Auditor note, 2026-11-13).
SEEN = "release_seen_utc"


def merge(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Held rows plus fresh rows; fresh wins on a shared date; no held date is lost. A date
    already held keeps its FIRST-seen time, so a CFTC restatement never moves it later."""
    if old is None or old.empty:
        return new.reset_index(drop=True)
    old = old.copy()
    if SEEN not in old.columns:
        old[SEEN] = pd.Series(pd.NaT, index=old.index, dtype="datetime64[ns, UTC]")
    cols = list(old.columns) + [c for c in new.columns if c not in old.columns]
    both = pd.concat([old.reindex(columns=cols), new.reindex(columns=cols)], ignore_index=True)
    out = (both.sort_values("report_date", kind="stable")
           .drop_duplicates("report_date", keep="last").reset_index(drop=True)[cols])
    if SEEN in old.columns:
        first = old.set_index("report_date")[SEEN].dropna()
        held_at = out["report_date"].map(first)
        out[SEEN] = held_at.where(held_at.notna(), out[SEEN])
    return out


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Atomic: tmp in the same folder, then os.replace (a read-only target is made writable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def refresh_one(t: Target, client: S.Client, release: pd.Timestamp, *, force: bool = False,
                data: Path = DATA, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    old = held(t, data)
    newest = old["report_date"].max() if old is not None and len(old) else None
    dirty = contaminated(t, old)
    row: dict[str, Any] = {"family": t.family, "slug": t.slug, "file": str(path_of(t, data))}
    if t.delisted:
        row.update(status="DELISTED", newest=str(newest.date()) if newest is not None else None,
                   rows=0 if old is None else len(old))
        return row
    if not force and not dirty and newest is not None and newest >= release:
        row.update(status="FRESH", newest=str(newest.date()), rows=len(old))
        return row
    names = ",".join(S.quote(n) for n in t.names)
    where = f"{NAME_FIELD[t.family]} in({names})"
    if t.family == "disagg":
        where += " AND futonly_or_combined='FutOnly'"
    if newest is not None and not dirty:
        since = (newest - pd.Timedelta(weeks=OVERLAP_WEEKS)).strftime("%Y-%m-%dT00:00:00")
        where += f" AND report_date_as_yyyy_mm_dd >= '{since}'"
    try:
        fresh = frame(t, client.rows(DATASET[t.family], where=where, select=SELECT[t.family]))
    except Exception as e:
        row.update(status="FAILED", why=f"{type(e).__name__}: {str(e)[:160]}",
                   newest=str(newest.date()) if newest is not None else None,
                   rows=0 if old is None else len(old))
        return row
    if fresh.empty:
        row.update(status="FAILED", why="no rows for the accepted market names",
                   newest=str(newest.date()) if newest is not None else None,
                   rows=0 if old is None else len(old))
        return row
    fresh[SEEN] = pd.Series(pd.Timestamp(now), index=fresh.index).astype("datetime64[ns, UTC]")
    out = fresh.reset_index(drop=True) if dirty else merge(old, fresh)
    if old is not None and not dirty:
        out = out[[*old.columns, *([SEEN] if SEEN not in old.columns else [])]]
    write_parquet(out, path_of(t, data))
    last = out["report_date"].max()
    status = "REBUILT" if dirty else "REFRESHED"
    if last < release - pd.Timedelta(days=STALE_DAYS):
        status = "STALE"
    row.update(status=status, newest=str(last.date()), rows=len(out),
               added=len(out) - (0 if old is None or dirty else len(old)))
    if t.family == "legacy" and t.slug == "gold":
        write_parquet(out, data / "cot_gold.parquet")       # the legacy alias readers open
    return row


def refresh(*, force: bool = False, client: S.Client | None = None, now: datetime | None = None,
            data: Path = DATA, report: Path | None = REPORT) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    release = latest_release(now)
    client = client or S.Client()
    rows = [refresh_one(t, client, release, force=force, data=data, now=now) for t in TARGETS]
    doc = {"generated_at": now.isoformat(timespec="seconds"),
           "latest_release": str(release.date()), "requests": client.requests,
           "source": f"{S.HOST} (CFTC Public Reporting; TLS verified; robots obeyed)",
           "counts": {s: sum(1 for r in rows if r["status"] == s)
                      for s in sorted({r["status"] for r in rows})},
           "slugs": rows}
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        tmp = report.with_name(report.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        os.replace(tmp, report)
    return doc


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    doc = refresh(force="--force" in args)
    print(f"cot-refresh: release {doc['latest_release']}, {doc['requests']} requests, "
          f"{doc['counts']}")
    for r in doc["slugs"]:
        if r["status"] not in ("FRESH", "DELISTED"):
            print(f"  {r['family']}/{r['slug']}: {r['status']} newest={r.get('newest')} "
                  f"{r.get('why', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
