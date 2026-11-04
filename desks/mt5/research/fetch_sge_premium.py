"""Shanghai gold premium: the price of physical gold in China against the international price.

THE MECHANISM, WHICH IS WHY THIS IS WORTH FETCHING

China is the largest physical gold consumer, and its domestic market is not freely arbitrageable:
bullion import requires a PBoC licence, so the SGE price can and does detach from London/COMEX.
The spread between them is therefore not a quote artefact — it is a direct read on physical
demand pressure that cannot equalise itself.

    premium > 0   domestic demand exceeding licensed import supply
    premium < 0   domestic weakness, or import quota running ahead of demand

The premium widened sharply through 2013 and 2016 physical-buying episodes and went NEGATIVE
during 2020 Chinese demand collapse while the Western price rallied — the two markets moving
oppositely, which no single-venue feed can see. For a desk whose armed book is three legs of
XAUUSD, a demand signal orthogonal to the Western session is worth more than another Western
indicator.

    XAU_SGE_USD = SGE_Au9999_CNY_per_gram * 31.1035 / USDCNY      (USD per troy ounce)
    premium     = XAU_SGE_USD - XAUUSD_fusion_0700Z_close

WHAT THIS MODULE WILL NOT DO

The SGE publishes no bulk free history (the CN s12 dig's bulk pull was throttle-blocked), so
history is SELF-RECORDED FORWARD (free-frontier law): each daily run captures that session's
last print into data/lake/sge_daily.parquet, and the premium series grows from the wiring date.
This fails closed. If it cannot obtain a genuine SGE print it writes UNAVAILABLE and stops.
It does NOT interpolate, does not carry the last value forward across a gap, and does not
substitute a proxy while calling it SGE. A fabricated premium would be worse than no premium:
the whole value of this series is that it disagrees with the Western price, so a filled-in
version would disagree in invented places and the desk would trade the invention.

Provenance is recorded per row — which source, fetched when — because a number whose origin is
unknown cannot be audited later, and this series will be used to justify positions.

    python research/fetch_sge_premium.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
try:
    from libs.data.polite_fetch import polite_requests_get
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import polite_requests_get

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "lake"
OUT.mkdir(parents=True, exist_ok=True)
REPORTS = BASE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
#: Forward-accumulated raw SGE prints, one row per Beijing trading date.
HISTORY = OUT / "sge_daily.parquet"

GRAMS_PER_TROY_OZ = 31.1034768

#: The international USD/oz leg is the desk's OWN broker feed: the XAUUSD H1 close of the
#: 07:00 UTC bar — the bar containing the SGE day-session close (15:30 Beijing = 07:30 UTC).
#: This replaced the LBMA PM fix after FRED 404'd GOLDPMGBD228NLBM (series withdrawn; measured
#: 2026-08-26), and it is the better leg anyway: the premium conditions XAUUSD trades, so the
#: spread vs the desk's actually-tradeable price IS the signal, and the file is on disk with no
#: network dependency.
XAU_H1 = BASE / "data" / "universe" / "XAUUSD_H1.parquet"
#: The fix this leg replaced is a third-party series (terms_fence `fred_copyrighted`: LBMA/IBA,
#: deleted from FRED 2022) and is REFUSED as live input, never a fallback. The USD gold leg is
#: carried under its OWN name and label, never under the fix's id.
REFUSED_INTL_SERIES = "GOLDPMGBD228NLBM"
INTL_LEG = {"series": "XAUUSD", "source": "fusion_xauusd_h1_0700Z",
            "label": ("the desk's own MT5 XAUUSD spot, 07:00 UTC H1 close -- NOT the LBMA PM "
                      "fix, which is refused (terms_fence fred_copyrighted)")}

#: USDCNY primary: ECB reference rates, USD and CNY from the SAME 16:00 CET snapshot, crossed.
#: Keyless, daily, ~0-1 day lag. Fallback: FRED DEXCHUS (H.10 noon-NY), keyless but published
#: with weeks of lag. One source per run for the WHOLE join — never mixed day-by-day — and the
#: report records which.
ECB_90D = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
USDCNY_FRED_SERIES = "DEXCHUS"

#: SGE official graph endpoint (R0649, verified live 2026-08-26). Serves ONE contract's
#: current-session minute curve:
#:   {"times": ["20:00", ...], "data": ["990.08", null, ...], "heyue": "Au99.99",
#:    "delaystr": "2026年08月26日 02:29:56", "min": ..., "max": ...}
#: `instid` selects the contract; `delaystr` is the LAST-QUOTE Beijing timestamp (not wall
#: clock), which is what dates the print. The previous parser here expected dated rows with
#: instid/close keys and could parse nothing from this shape — the exact III.16
#: built-never-run defect the CN s12 card recorded.
SGE_GRAPH = "https://www.sge.com.cn/graph/quotations"
#: history column -> SGE contract. Au99.99 is the REQUIRED spot leg; Au(T+D) is the deferred
#: contract whose basis to spot carries the 递延费 (deferred-fee) pressure direction.
SGE_CONTRACTS = {"au9999_cny_g": "Au99.99", "au_td_cny_g": "Au(T+D)"}

_DELAY_RE = re.compile(r"(\d{4})年(\d{2})月(\d{2})日")


def _free_data():
    import free_data as fd
    return fd


def _fred_series(series_id: str, col: str) -> pd.Series | None:
    """A FRED series through free_data.fred_series: the method fence, the desk UA, and the
    third-party refusal (terms_fence `fred_copyrighted`) before any request -- never a bare GET.
    None when refused or unavailable; the caller fails closed."""
    try:
        obs = _free_data().fred_series(series_id, start="2015-01-01", alternate=False)
    except Exception as exc:                                        # noqa: BLE001
        print(f"  {col}: {type(exc).__name__}: {exc}", flush=True)
        return None
    if not obs:
        return None
    s = pd.Series({pd.Timestamp(k): float(v) for k, v in obs.items()}, dtype=float).sort_index()
    s.name = col
    return s


def _parse_graph(payload: object, instid: str) -> tuple[pd.Timestamp, float] | None:
    """(session date, last traded price) from one graph payload, or None.

    The date comes from `delaystr` — the Beijing timestamp of the LAST QUOTE — never from the
    fetch clock: a weekend fetch returns Friday's session and must be dated Friday. `heyue` is
    checked against the requested contract because the endpoint silently falls back to Au99.99
    for an unknown instid, and recording that fallback under Au(T+D) would fabricate a zero
    basis.
    """
    if not isinstance(payload, dict) or payload.get("heyue") != instid:
        return None
    m = _DELAY_RE.search(str(payload.get("delaystr") or ""))
    if m is None:
        return None
    vals = [v for v in (payload.get("data") or []) if v not in (None, "", "null")]
    try:
        last = float(vals[-1])
    except (IndexError, ValueError, TypeError):
        return None
    if not 10.0 < last < 100_000.0:   # CNY/gram sanity: gold ~1000, silver ~10
        return None
    return pd.Timestamp(f"{m.group(1)}-{m.group(2)}-{m.group(3)}"), last


#: SGE daily quotation page (每日交易行情, /sjzx/quotation_daily_new). Its table carries, per
#: contract and date, the 交收方向 (deferral-fee payment direction) and 交收量 (delivery lots) the
#: Au(T+D) deferral state reads (IDEA_QUEUE row 215; `asia_gold_physical.sge_deferral_state`).
#: NOT FETCHED: the SGE site prints no terms beyond "All Right Reserved", so its policy row
#: (terms_fence.SOURCE_POLICY["cn_sge_deferral"]) is IDEAS_ONLY; the parser is ready on fixtures.
SGE_DAILY_QUOTATION = "https://www.sge.com.cn/sjzx/quotation_daily_new"
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def parse_daily_quotation(html: str) -> list[dict[str, object]]:
    """Rows of the daily quotation table -> [{date, contract, close, open_interest, direction,
    delivery_lots}]. Columns are located by their HEADER text (日期, 合约, 收盘价, 市场持仓,
    交收方向, 交收量), so a reordered table still parses; a table without 合约 and 交收方向
    headers parses to nothing, never to a guess."""
    rows = [[_TAG.sub("", c).replace("&nbsp;", " ").strip() for c in _TD.findall(tr)]
            for tr in _TR.findall(html)]
    head: dict[str, int] = {}
    out: list[dict[str, object]] = []
    for cells in rows:
        if not head:
            if any(c.startswith("合约") for c in cells) and any("交收方向" in c for c in cells):
                for i, c in enumerate(cells):
                    for key in ("日期", "合约", "收盘价", "市场持仓", "交收方向", "交收量"):
                        if c.startswith(key) and key not in head:
                            head[key] = i
            continue
        if len(cells) <= max(head.values()) or not re.match(r"\d{4}-\d{2}-\d{2}$",
                                                             cells[head.get("日期", 0)]):
            continue

        def _f(key: str, cells: list[str] = cells) -> float | None:
            try:
                return float(cells[head[key]].replace(",", ""))
            except (KeyError, ValueError):
                return None
        out.append({"date": cells[head.get("日期", 0)], "contract": cells[head["合约"]],
                    "close": _f("收盘价"), "open_interest": _f("市场持仓"),
                    "direction": cells[head["交收方向"]], "delivery_lots": _f("交收量")})
    return out


#: THE SGE POLICY ROW (terms_fence.SOURCE_POLICY["sge"]). Every sge.com.cn request goes through
#: `polite_fetch.get(live_input=True)`: robots.txt and the site's person-held access holds decide,
#: the agent is DESK_UA, 401/403/429/WAF is a hard stop, and an IDEAS_ONLY or held route is refused
#: BEFORE anything is sent. SGE's terms are UNREAD (fail closed, auditor ruling 2026-10-14), so
#: the row is IDEAS_ONLY and this fetch is refused until a person quotes a permitting clause into
#: it; the refusal is written as UNMEASURED, never as a zero or an empty series.
SGE_POLICY_ROW = "sge"
_REFUSALS = ("IDEAS_ONLY", "METHOD_BLOCKED", "NEEDS_KEY")


def fetch_sge(get: object | None = None) -> tuple[dict[str, tuple[pd.Timestamp, float]], str]:
    """Latest SGE print per contract. Returns ({col: (date, cny_per_gram)}, provenance).

    An empty dict (or one missing au9999_cny_g) means the REQUIRED leg failed; Au(T+D) is
    enrichment and its absence is logged, not fatal. A REFUSED fetch (terms, robots, a hold)
    returns provenance `REFUSED:<reason>` so the caller writes UNMEASURED with the reason.
    `get` replaces `polite_fetch.get` in tests.
    """
    from urllib.parse import urlencode

    from libs.data import polite_fetch
    getter = get if callable(get) else polite_fetch.get
    prints: dict[str, tuple[pd.Timestamp, float]] = {}
    for col, instid in SGE_CONTRACTS.items():
        url = f"{SGE_GRAPH}?{urlencode({'instid': instid})}"
        r = getter(url, timeout=45, leg="sge_premium", live_input=True)
        # A refusal sends nothing: robots / an access hold set `verdict`; the terms fence (an
        # IDEAS_ONLY or held route asked for as live input) names its status in `error`.
        if r.verdict or (r.status is None and str(r.error).split(":")[0] in _REFUSALS):
            return {}, f"REFUSED:{(r.error or r.verdict)[:200]}"
        parsed = None
        if r.ok:
            try:
                parsed = _parse_graph(json.loads(r.text), instid)
            except ValueError as exc:
                print(f"  {instid}: {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"  {instid}: {r.status} {r.error}", flush=True)
        if parsed is None:
            print(f"  {instid}: no usable print", flush=True)
            continue
        prints[col] = parsed
    return prints, "sge_official_graph"


def refused_report(at: str, prov: str) -> dict[str, object]:
    """The report a refused SGE fetch writes: UNMEASURED with the named reason and the policy
    row's missed-growth line. Nothing is recorded and no existing history is extended."""
    from libs.data import terms_fence as tf
    line = tf.held_missed_growth(SGE_POLICY_ROW, None, source="sge_premium",
                                 live_input_refusal=True)
    return {"at": at, "status": "UNMEASURED", "refusal": prov[len("REFUSED:"):],
            "policy_row": SGE_POLICY_ROW, "policy_status": tf.status(SGE_POLICY_ROW),
            "missed_growth": line,
            "consumers": list(tf.SOURCE_POLICY[SGE_POLICY_ROW].get("consumers") or ()),
            "reason": ("the SGE fetch was refused before any request was sent (terms UNREAD: "
                       "IDEAS_ONLY, never live input); nothing recorded, no carry-forward -- the "
                       "premium is UNMEASURED, never zero")}


def record_history(prints: dict[str, tuple[pd.Timestamp, float]], prov: str,
                   fetched_at: str) -> pd.DataFrame:
    """Upsert today's prints into the forward-accumulated history, idempotently by date.

    Re-running on the same day overwrites that day's row with the fresher print; it can never
    duplicate a date, so the timer's cadence cannot inflate the series.
    """
    rows: dict[pd.Timestamp, dict[str, object]] = {}
    for col, (d, px) in prints.items():
        rows.setdefault(d.normalize(), {})[col] = px
    add = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    add["source"] = prov
    add["fetched_at"] = fetched_at
    if HISTORY.exists():
        hist = pd.read_parquet(HISTORY)
        hist = add.combine_first(hist)
    else:
        hist = add
    hist = hist.sort_index()
    if {"au9999_cny_g", "au_td_cny_g"} <= set(hist.columns):
        # Au(T+D) trades at a basis to spot; its SIGN is the market-priced read on which side
        # of the 递延费 (deferred fee) is under pressure — the direction leg of this card.
        hist["agtd_basis_cny_g"] = hist["au_td_cny_g"] - hist["au9999_cny_g"]
    hist.to_parquet(HISTORY)
    return hist


def _desk_xau_usd_oz() -> pd.Series | None:
    """XAUUSD close of the 07:00 UTC H1 bar per date, from the desk's own synced feed."""
    if not XAU_H1.exists():
        return None
    df = pd.read_parquet(XAU_H1)
    at7 = df[df.index.hour == 7]["close"]
    if at7.empty:
        return None
    s = at7.copy()
    s.index = s.index.tz_convert("UTC").normalize().tz_localize(None)
    s = s[~s.index.duplicated(keep="last")]
    s.name = "intl_usd_oz"
    return s


def _ecb_usdcny() -> pd.Series | None:
    """USDCNY crossed from ECB reference EUR rates (same 16:00 CET snapshot both legs)."""
    import xml.etree.ElementTree as ET
    try:
        r = polite_requests_get(ECB_90D, timeout=45)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:                                        # noqa: BLE001
        print(f"  ecb_usdcny: {type(exc).__name__}: {exc}", flush=True)
        return None
    ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    recs: dict[pd.Timestamp, float] = {}
    for day in root.findall(".//e:Cube[@time]", ns):
        rates = {c.get("currency"): c.get("rate") for c in day.findall("e:Cube", ns)}
        try:
            usd, cny = float(rates["USD"]), float(rates["CNY"])
        except (KeyError, TypeError, ValueError):
            continue
        recs[pd.Timestamp(str(day.get("time")))] = cny / usd
    if not recs:
        return None
    s = pd.Series(recs).sort_index()
    s.name = "usdcny"
    return s


def build_premium(sge_cny_g: pd.Series, intl_usd_oz: pd.Series,
                  usdcny: pd.Series) -> pd.DataFrame:
    """Join on date and compute the premium. INNER JOIN, deliberately.

    A day missing any leg is a day the premium is unknown, and it is dropped rather than
    forward-filled. Carrying yesterday's premium across a Chinese holiday would invent
    agreement or disagreement on a day no Shanghai price existed -- and disagreement is the
    entire signal.
    """
    df = pd.concat({"sge_cny_g": sge_cny_g, "intl_usd_oz": intl_usd_oz,
                    "usdcny": usdcny}, axis=1).dropna()
    df["sge_usd_oz"] = df["sge_cny_g"] * GRAMS_PER_TROY_OZ / df["usdcny"]
    df["premium_usd_oz"] = df["sge_usd_oz"] - df["intl_usd_oz"]
    df["premium_pct"] = df["premium_usd_oz"] / df["intl_usd_oz"] * 100.0
    return df


def main() -> int:
    report: dict[str, object] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    refused = _free_data().fred_refusal(REFUSED_INTL_SERIES, "fetch_sge_premium",
                                        substituted=True)
    report["intl_leg"] = {**INTL_LEG, "refused_fred_series": REFUSED_INTL_SERIES}
    if refused is not None:
        report["unmeasured_no_licensed_source"] = {
            REFUSED_INTL_SERIES: {k: v for k, v in refused.items() if k != "missed_growth"}}
        report["missed_growth"] = [refused["missed_growth"]]
    print("SGE Au99.99 + Au(T+D)...", flush=True)
    prints, prov = fetch_sge()
    if prov.startswith("REFUSED:"):
        report = refused_report(str(report["at"]), prov)
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSGE PREMIUM UNMEASURED -- fetch refused: {report['refusal']}")
        return 0
    if "au9999_cny_g" not in prints:
        # FAILS CLOSED. No interpolation, no proxy, no carry-forward: the value of this series
        # is that it DISAGREES with the Western price, so a fabricated version would disagree
        # in invented places and the desk would trade the invention.
        report.update({
            "status": "UNAVAILABLE", "missing_legs": ["SGE"], "sge_detail": prov,
            "reason": ("the SGE graph endpoint yielded no usable Au99.99 print; nothing "
                       "recorded -- no interpolation, no proxy, no carry-forward"),
            "fix": ("check https://www.sge.com.cn/graph/quotations?instid=Au99.99 by hand; "
                    "if the payload shape changed again, update _parse_graph and its fixture "
                    "test in tests/test_sge_premium.py")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("\nSGE PREMIUM UNAVAILABLE -- no SGE print")
        return 2

    hist = record_history(prints, prov, str(report["at"]))
    latest = {col: {"date": str(d.date()), "cny_per_gram": px}
              for col, (d, px) in prints.items()}
    report.update({"history_rows": int(len(hist)), "history_path": str(HISTORY),
                   "source_sge": prov, "latest": latest})
    print(f"history: {len(hist)} day(s) recorded -> {HISTORY}", flush=True)

    print("XAUUSD 07:00Z leg (desk feed) + USDCNY (ECB, FRED fallback)...", flush=True)
    intl = _desk_xau_usd_oz()
    cny = _ecb_usdcny()
    cny_source = "ecb_cross"
    if cny is None:
        cny = _fred_series(USDCNY_FRED_SERIES, "usdcny")
        cny_source = "fred_dexchus"
    missing = [n for n, s in (("XAUUSD_H1", intl), ("USDCNY", cny)) if s is None]
    if missing:
        report.update({
            "status": "SGE_RECORDED_LEG_MISSING", "missing_legs": missing,
            "reason": ("today's SGE print IS recorded (self-recorded history never skips a "
                       "day), but the premium needs the XAUUSD and USDCNY legs and one was "
                       "not obtainable -- see stderr above for the fetch error")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nlegs missing: {', '.join(missing)} -- SGE history still recorded")
        return 1

    assert intl is not None and cny is not None
    report["usdcny_source"] = cny_source
    df = build_premium(hist["au9999_cny_g"].dropna(), intl, cny)
    if df.empty:
        # Expected while the forward-recorded SGE history is younger than FRED's publication
        # lag (LBMA/DEXCHUS trail by days-to-weeks): all legs healthy, no overlapping date yet.
        report.update({"status": "ACCUMULATING",
                       "reason": ("all legs fetched; no common trading day yet between the "
                                  "self-recorded SGE history and the rate legs -- the overlap "
                                  "arrives within a day as the legs publish")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("\nno overlapping days yet (rate-leg publication lag); SGE history recorded and growing")
        return 0

    df["source_sge"] = prov
    df["intl_source"] = INTL_LEG["source"]
    df["usdcny_source"] = cny_source
    df["fetched_at"] = report["at"]
    df.to_parquet(OUT / "sge_premium.parquet")
    recent = df["premium_usd_oz"].tail(20)
    report.update({"status": "OK", "rows": int(len(df)),
                   "first": str(df.index.min().date()), "last": str(df.index.max().date()),
                   "premium_usd_oz_last": float(df["premium_usd_oz"].iloc[-1]),
                   "premium_pct_last": float(df["premium_pct"].iloc[-1]),
                   "premium_usd_oz_mean_20": float(recent.mean()),
                   "path": str(OUT / "sge_premium.parquet")})
    (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{len(df):,} premium day(s) {df.index.min().date()} -> {df.index.max().date()}")
    print(f"latest premium {df['premium_usd_oz'].iloc[-1]:+.2f} USD/oz "
          f"({df['premium_pct'].iloc[-1]:+.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
