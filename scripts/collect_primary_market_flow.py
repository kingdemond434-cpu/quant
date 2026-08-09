#!/usr/bin/env python3
# INTENDED CADENCE (NOT wired here -- ops/crontab.manifest is owned by another agent this wave, so
# this comment is the request, not the installation):
#
#     41 23 * * *  cd /opt/quant && python3 scripts/collect_primary_market_flow.py
#
# ONCE A DAY, LATE. 23:41 UTC is after the US equity close (21:00Z) plus the margin Farside needs
# to post the day's issuer table, so a run at this hour sees the flow for the trading day that just
# ended rather than a row of placeholders. It is the natural cadence of the data and not a choice:
# ETF flow publishes once per trading day and the stablecoin aggregates roll once per UTC day, so
# a second daily run would re-fetch identical rows and buy nothing. The minute is offset off the
# hour so it never collides with the recorders' rotation.
#
# The collector is idempotent -- re-running it appends a run record and only those observations it
# has never seen -- so a missed night costs nothing and a double run costs one duplicate run row.
"""PRIMARY-MARKET CREATION FLOW COLLECTOR -- the data the desk's #2 ranked untested mechanism class
has never had, written append-only with every source's status and its reason.

WHY THIS CLASS. `scripts/run_mechanism_census.py` ranks `primary_market_creation_flow` #2 of 20
economic classes (gap 0.364 = plausibility 0.70 x orthogonality 0.65 x feasibility 0.80 x depth
deficit 1.00), coverage NAMED-UNTESTED: FOUR named constructions, ZERO tested candidates, and no
screen artifact anywhere in the tree. `scripts/measure_cross_mechanism_corr.py` measured the
desk's 44-candidate maximum-power campaign occupying 2.787 effective classes (diversity 0.139) at
a cross-mechanism N_eff of 4.08 against the ~100 independent bets a weak-edge portfolio needs.
More rules on the same OHLCV tape cannot move that number. A DISTINCT mechanism can, and this is
the highest-ranked one whose data is free and keyless.

THE MECHANISM, so the collector's choices can be judged against it. Spot-ETF creations and
redemptions and on-chain stablecoin mint/burn are NON-DISCRETIONARY primary-market flows. An
authorised participant creating ETF units must acquire the underlying regardless of price; a
stablecoin mint is fiat that has already arrived and must be deployed. WHO PAYS: the liquidity
provider who fills that inelastic demand and carries the inventory until he can work it off. Why
it persists: the flow is mandated by the creation mechanism, not chosen on price, so no amount of
the trade becoming known changes the AP's obligation to source the underlying.

WHAT THIS WRITES, AND WHY IT IS A FIRST-SEEN LEDGER RATHER THAN A SNAPSHOT
--------------------------------------------------------------------------
`data/primary_market_flow.jsonl`, append-only, two record kinds:

    {"kind": "run", ...}          one per run: every source with status, reason, timing, coverage
    {"kind": "observation", ...}  one per (source, stamp) the desk has NEVER SEEN BEFORE, carrying
                                  `first_seen_utc`

The first-seen field is the entire reason this is a ledger. Both flow sources serve their FULL
history on every fetch, so a snapshot would be redundant -- but a snapshot cannot answer the only
question the screen's validity depends on: WHEN DID THIS ROW BECOME READABLE. ETF flow is stamped
by trade date and published a business day later; the screen's alignment charges that lag as an
assumption. Recording the instant the desk first observed each stamp turns that assumption into a
MEASUREMENT going forward, and any row whose measured lag exceeds the assumed one can be found and
dropped instead of silently trading a number that did not exist.

Rows collected before this ledger existed carry `backfilled: true` and their first_seen is the
bootstrap instant, NOT evidence about publication time. The artifact says so rather than letting a
later reader mistake the bootstrap for a measurement.

SOURCES -- all free, all keyless, each isolated so one failure cannot take the run down
---------------------------------------------------------------------------------------
  etf_btc_farside          spot-BITCOIN ETF daily creation/redemption per issuer (US$m)
  etf_eth_farside          spot-ETHEREUM ETF, same shape
  stablecoin_usdt_llama    Tether daily circulating + authorised-but-unissued (US$)
  stablecoin_usdc_llama    Circle, same
  float_btc_blockchain     BTC circulating supply history -- the denominator
  price_btc_coinbase       daily UTC closes for the target leg
  price_eth_coinbase       daily UTC closes for the target leg
  l1_stablecoin_supply     LIVE Ethereum L1 USDT+USDC totalSupply via libs.data.onchain_flows
  l1_exchange_reserves     LIVE exchange stablecoin reserves via libs.data.onchain_flows

THE TWO L1 SOURCES ARE ACCRUAL-ONLY AND THE ARTIFACT SAYS SO. Keyless public Ethereum RPC serves
only the most recent ~128 blocks: an archive `eth_call` for a historical block returns HTTP 403
(measured on this box, 2026-08-05, against publicnode / cloudflare / llamarpc / ankr). So the L1
readers give ONE POINT PER RUN and no history, which is why the screen's stablecoin constructions
are built on the vendor's daily aggregate and the L1 readings serve as an independent cross-check
that accrues forward. That is a limitation of keyless access, not of the mechanism, and inventing
history for it would be the exact failure this desk graveyards.

`libs.data.onchain_flows` is the ONE reader for both L1 quantities and is imported, not
re-implemented -- it already owns the RPC fallback list, the labelled exchange wallets and the
decimals.

FAILURE POLICY. Every source is fetched inside its own guard. A source that fails is recorded with
status and the exception's own text; it is NEVER silently skipped and its absence NEVER becomes a
zero row. The run exits 0 whatever happens, because a partial collection is a real and useful
outcome, and the exit code is not where a data problem should be reported -- the artifact is.

PACING AND BOUNDS. One request at a time with a fixed inter-request delay, a per-request timeout, a
capped number of paginated price windows, and a wall-clock budget after which remaining sources are
recorded as `skipped_budget` rather than started. Nothing here hammers a free endpoint.

Zero promotion authority: this script fetches, records and writes one artifact. It screens nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.onchain_flows import exchange_reserves, stablecoin_supply  # noqa: E402
from libs.data.venue_http import BROWSER_UA, get_json  # noqa: E402
from libs.research.primary_market_flow import (  # noqa: E402
    parse_farside_table,
    parse_llama_chart,
)

SCHEMA_VERSION = "1.0.0"
MECHANISM_CLASS = "primary_market_creation_flow"
LEDGER = ROOT / "data/primary_market_flow.jsonl"

FARSIDE_BTC = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
FARSIDE_ETH = "https://farside.co.uk/ethereum-etf-flow-all-data/"
LLAMA_USDT = "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1"
LLAMA_USDC = "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=2"
BTC_SUPPLY = "https://api.blockchain.info/charts/total-bitcoins?timespan=5years&format=json"
COINBASE = "https://api.exchange.coinbase.com/products/{product}/candles"

#: Seconds between outbound requests. These are free, unauthenticated, community-funded endpoints;
#: the collector runs once a day and has no reason to be fast.
PACE_S = 1.2
REQUEST_TIMEOUT_S = 45.0

#: Wall-clock budget for the whole run. Past it, remaining sources are recorded `skipped_budget`
#: with the elapsed time, so a hung endpoint degrades the run instead of pinning a cron slot.
RUN_BUDGET_S = 300.0

#: Coinbase serves 300 daily candles per call, so full ETF-era coverage needs pagination. Five
#: windows of 290 days reach back ~1450 days, comfortably past the 2024-01-11 ETF launch, and the
#: cap is what stops a bug from walking the endpoint back to genesis.
CANDLE_WINDOW_DAYS = 290
MAX_CANDLE_WINDOWS = 5


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _get_text(url: str) -> str:
    """Fetch an HTML page with the browser header the desk already learned is load-bearing.

    `libs.data.venue_http` documents the measurement: the library-default User-Agent draws a 403
    from CDN bot filters, which then gets recorded as a venue refusal and preserved as a WRONG
    diagnosis. Its `get_json` cannot be reused directly here because Farside serves HTML, so the
    header constant is imported rather than re-typed -- a second copy is a second thing to forget.
    """
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA,
                                               "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as fh:
        return str(fh.read().decode("utf-8", errors="replace"))


class Budget:
    """Wall-clock guard plus the inter-request pacing, in one object the sources share."""

    def __init__(self, seconds: float) -> None:
        self.deadline = time.monotonic() + float(seconds)
        self.started = _now()
        self._last = 0.0

    def exhausted(self) -> bool:
        return time.monotonic() >= self.deadline

    def pace(self) -> None:
        wait = PACE_S - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()


def _fetch_farside(url: str, series: str, budget: Budget) -> tuple[list[dict[str, Any]],
                                                                  dict[str, Any]]:
    """Issuer-flow table -> observation rows in US DOLLARS, plus the parse accounting.

    Farside reports US$ MILLIONS. The conversion happens once, here, so nothing downstream has to
    remember which unit a column is in -- a unit that lives only in a docstring is a unit that
    eventually gets multiplied by a price.
    """
    budget.pace()
    table = parse_farside_table(_get_text(url))
    rows = [{"series": series, "stamp": r.trade_date.isoformat(),
             "value": round(r.total_musd * 1e6, 2),
             "n_issuers_reported": r.n_issuers_reported,
             "per_issuer_musd": r.per_issuer}
            for r in table.rows]
    detail: dict[str, Any] = {
        "issuers": list(table.issuers),
        "dropped": dict(table.dropped),
        "total_vs_issuer_sum_mismatches": table.total_mismatch,
        "unit": "USD (converted from the page's US$ millions)",
        "placeholder_policy": ("a row whose issuer cells are all em-dashes is NOT read as zero -- "
                               "its Total column says 0.0 and both US market holidays and the "
                               "not-yet-published current day render exactly that way"),
    }
    return rows, detail


def _fetch_llama(url: str, series: str, budget: Budget) -> tuple[list[dict[str, Any]],
                                                                 dict[str, Any]]:
    budget.pace()
    supply = parse_llama_chart(get_json(url, timeout=REQUEST_TIMEOUT_S))
    rows = [{"series": series, "stamp": s.day.isoformat(),
             "value": round(s.circulating_usd, 2),
             "unreleased_usd": round(s.unreleased_usd, 2)}
            for s in supply]
    return rows, {"unit": "USD circulating at the UTC day boundary",
                  "carries_unreleased": True,
                  "why_unreleased": ("authorised-but-not-issued issuer inventory; the field that "
                                     "separates Tether's pre-minted treasury staging from capital "
                                     "actually arriving")}


def _fetch_btc_float(budget: Budget) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    budget.pace()
    payload = get_json(BTC_SUPPLY, timeout=REQUEST_TIMEOUT_S)
    vals = payload.get("values", []) if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    for p in vals:
        if not isinstance(p, dict):
            continue
        try:
            day = datetime.fromtimestamp(int(p["x"]), tz=UTC).date()
            v = float(p["y"])
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            continue
        if v > 0:
            rows.append({"series": "float_btc", "stamp": day.isoformat(), "value": v})
    return rows, {"unit": "BTC in circulation", "n_points": len(rows)}


def _fetch_candles(product: str, series: str, budget: Budget) -> tuple[list[dict[str, Any]],
                                                                      dict[str, Any]]:
    """Daily UTC closes, paginated backwards. THE TARGET LEG, and it is deliberately not Binance.

    `fapi.binance.com` answers this container with HTTP 451 (geo-refusal at the proxy's egress),
    which is recorded rather than worked around: the desk's own `venue_http` docstring warns that
    a refusal recorded without a header re-test can preserve a wrong diagnosis, and this one was
    re-tested with a browser User-Agent and still 451s. Coinbase answers, so Coinbase is the leg.
    """
    end = _now()
    closes: dict[str, float] = {}
    windows = 0
    for _ in range(MAX_CANDLE_WINDOWS):
        if budget.exhausted():
            break
        start = end - timedelta(days=CANDLE_WINDOW_DAYS)
        budget.pace()
        url = (f"{COINBASE.format(product=product)}?granularity=86400"
               f"&start={start.isoformat()}&end={end.isoformat()}")
        batch = get_json(url, timeout=REQUEST_TIMEOUT_S)
        windows += 1
        if not isinstance(batch, list) or not batch:
            break
        for c in batch:
            if not isinstance(c, list) or len(c) < 5:
                continue
            try:
                day = datetime.fromtimestamp(int(c[0]), tz=UTC).date().isoformat()
                close = float(c[4])
            except (TypeError, ValueError, OSError, OverflowError):
                continue
            if close > 0:
                closes[day] = close
        end = start
    rows = [{"series": series, "stamp": d, "value": closes[d]} for d in sorted(closes)]
    return rows, {"unit": "USD daily close", "windows_fetched": windows,
                  "venue": "coinbase exchange public candles (keyless)",
                  "binance_note": "fapi.binance.com returns HTTP 451 from this container even "
                                  "with a browser User-Agent -- recorded, not worked around"}


def _fetch_l1_supply(budget: Budget) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """LIVE L1 totalSupply -- ONE point, today. Reuses libs.data.onchain_flows verbatim."""
    budget.pace()
    d = stablecoin_supply()
    day = _now().date().isoformat()
    rows = [{"series": "l1_stablecoin_supply", "stamp": day,
             "value": float(d["total_supply_usd"]), "per_token": d["per_token"]}]
    return rows, {"unit": "USD total supply on Ethereum L1",
                  "history": "NONE AVAILABLE KEYLESSLY -- archive eth_call for a historical block "
                             "returns HTTP 403 on every public RPC tried (publicnode, cloudflare, "
                             "llamarpc, ankr), measured 2026-08-05. This accrues one point per "
                             "run and is a cross-check on the vendor aggregate, not a series the "
                             "screen can be built on today.",
                  "reader": "libs.data.onchain_flows.stablecoin_supply (reused, not reimplemented)"}


def _fetch_l1_reserves(budget: Budget) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """LIVE exchange stablecoin reserves -- the census's `stablecoin_exchange_flows` construction.

    ACCRUAL ONLY, AND DELIBERATELY OUTSIDE THE SCREEN'S PRE-REGISTERED FAMILY. The same keyless
    archive limit applies, so there is no history to screen; and `scripts/screen_exchange_netflow.py`
    already owns the exchange-flow question on a source that HAS history. Collecting it here without
    screening it is the honest position -- the construction is named by the census, so its absence
    from the family is recorded as a decision rather than left as a hole.
    """
    budget.pace()
    d = exchange_reserves()
    day = _now().date().isoformat()
    rows = [{"series": "l1_exchange_reserves", "stamp": day,
             "value": float(d["total_reserve_usd"]), "per_exchange": d["per_exchange"],
             "n_wallets": d["n_wallets"]}]
    return rows, {"unit": "USD USDT+USDC held by labelled exchange hot wallets",
                  "history": "none keylessly; accrues one point per run",
                  "not_in_screen_family": ("no history to screen, and screen_exchange_netflow.py "
                                           "already owns this question on a source that has it"),
                  "reader": "libs.data.onchain_flows.exchange_reserves (reused)"}


#: (source id, human purpose, fetcher). Order is deliberate: the two irreplaceable flow sources
#: run FIRST, so a budget exhaustion degrades the price leg (re-fetchable any time) rather than
#: the mechanism leg.
Fetcher = Callable[[Budget], tuple[list[dict[str, Any]], dict[str, Any]]]
SOURCES: tuple[tuple[str, str, Fetcher], ...] = (
    ("etf_btc_farside", "daily spot-BTC ETF creation/redemption per issuer",
     lambda b: _fetch_farside(FARSIDE_BTC, "etf_flow_btc", b)),
    ("etf_eth_farside", "daily spot-ETH ETF creation/redemption per issuer",
     lambda b: _fetch_farside(FARSIDE_ETH, "etf_flow_eth", b)),
    ("stablecoin_usdt_llama", "Tether daily circulating supply (mint/burn denominator)",
     lambda b: _fetch_llama(LLAMA_USDT, "stablecoin_usdt", b)),
    ("stablecoin_usdc_llama", "Circle daily circulating supply (mint/burn denominator)",
     lambda b: _fetch_llama(LLAMA_USDC, "stablecoin_usdc", b)),
    ("float_btc_blockchain", "BTC circulating supply -- the float denominator", _fetch_btc_float),
    ("price_btc_coinbase", "BTC daily UTC closes -- target leg",
     lambda b: _fetch_candles("BTC-USD", "price_btc", b)),
    ("price_eth_coinbase", "ETH daily UTC closes -- target leg",
     lambda b: _fetch_candles("ETH-USD", "price_eth", b)),
    ("l1_stablecoin_supply", "live L1 USDT+USDC totalSupply (cross-check, accrual)",
     _fetch_l1_supply),
    ("l1_exchange_reserves", "live exchange stablecoin reserves (accrual)", _fetch_l1_reserves),
)


def read_ledger(path: Path) -> tuple[dict[str, set[str]], int, int]:
    """({series: seen stamps}, observation rows, unparseable lines) from an existing ledger.

    UNPARSEABLE LINES ARE COUNTED AND LEFT ALONE, never rewritten. A torn line is evidence about a
    crash; deleting it to tidy the file destroys the only record that the crash happened.
    """
    seen: dict[str, set[str]] = {}
    n_obs = 0
    bad = 0
    if not path.exists():
        return seen, 0, 0
    for line in path.read_text("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(rec, dict) or rec.get("kind") != "observation":
            continue
        s, stamp = rec.get("series"), rec.get("stamp")
        if isinstance(s, str) and isinstance(stamp, str):
            seen.setdefault(s, set()).add(stamp)
            n_obs += 1
    return seen, n_obs, bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Primary-market creation-flow collector")
    ap.add_argument("--out", type=Path, default=LEDGER, help="append-only ledger path")
    ap.add_argument("--budget-s", type=float, default=RUN_BUDGET_S,
                    help="wall-clock budget; sources past it are recorded skipped_budget")
    ap.add_argument("--only", action="append", default=None,
                    help="restrict to named source id(s); repeatable")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen, prior_obs, bad_lines = read_ledger(out)
    bootstrap = prior_obs == 0
    budget = Budget(float(args.budget_s))
    started = budget.started

    statuses: list[dict[str, Any]] = []
    new_records: list[dict[str, Any]] = []
    wanted = set(args.only) if args.only else None

    for src_id, purpose, fetch in SOURCES:
        if wanted is not None and src_id not in wanted:
            statuses.append({"source": src_id, "purpose": purpose, "status": "skipped_filter",
                             "reason": "not named in --only"})
            continue
        if budget.exhausted():
            statuses.append({
                "source": src_id, "purpose": purpose, "status": "skipped_budget",
                "reason": (f"wall-clock budget of {args.budget_s:.0f}s exhausted before this "
                           "source was started; it was NOT attempted and nothing was written "
                           "for it")})
            continue
        t0 = time.monotonic()
        try:
            rows, detail = fetch(budget)
        # A BARE `Exception` IS THE DESIGN, NOT LAZINESS. Per-source isolation means this
        # handler must survive whatever a third-party endpoint invents -- a urllib error, a
        # JSON decode failure, a socket reset, an RPC library raising its own type. Narrowing
        # it would let one unanticipated exception class take down the eight sources that
        # were fine, which is exactly the failure this collector is built to avoid.
        except Exception as exc:
            statuses.append({
                "source": src_id, "purpose": purpose, "status": "FAILED",
                "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
                "elapsed_s": round(time.monotonic() - t0, 2),
                "policy": ("recorded, never silently skipped; no row is written for a failed "
                           "source and its absence never becomes a zero")})
            continue

        elapsed = round(time.monotonic() - t0, 2)
        if not rows:
            statuses.append({
                "source": src_id, "purpose": purpose, "status": "EMPTY",
                "reason": "the request succeeded but yielded no usable rows after parsing",
                "elapsed_s": elapsed, "detail": detail})
            continue

        fresh = 0
        by_series: dict[str, int] = {}
        for row in rows:
            series = str(row["series"])
            stamp = str(row["stamp"])
            by_series[series] = by_series.get(series, 0) + 1
            if stamp in seen.get(series, set()):
                continue
            seen.setdefault(series, set()).add(stamp)
            fresh += 1
            new_records.append({
                "kind": "observation", "source": src_id,
                "first_seen_utc": _now().isoformat(),
                # BOOTSTRAP ROWS ARE MARKED. Their first_seen is when this ledger started, not
                # when the row was published -- so they are evidence of coverage and NOT evidence
                # about publication lag. Conflating the two is how an assumed alignment becomes a
                # "verified" one without anything having been verified.
                "backfilled": bootstrap,
                **row,
            })
        stamps = sorted({str(r["stamp"]) for r in rows})
        statuses.append({
            "source": src_id, "purpose": purpose, "status": "OK", "elapsed_s": elapsed,
            "rows_served": len(rows), "rows_new": fresh,
            "rows_per_series": by_series,
            "span": [stamps[0], stamps[-1]] if stamps else None,
            "detail": detail,
        })

    run = {
        "kind": "run", "schema_version": SCHEMA_VERSION,
        "run_utc": started.isoformat(),
        "finished_utc": _now().isoformat(),
        "elapsed_s": round((_now() - started).total_seconds(), 2),
        "mechanism_class": MECHANISM_CLASS,
        "script": "scripts/collect_primary_market_flow.py",
        "bootstrap": bootstrap,
        "prior_observations": prior_obs,
        "unparseable_ledger_lines": bad_lines,
        "new_observations": len(new_records),
        "budget_s": float(args.budget_s),
        "pace_s": PACE_S,
        "sources": statuses,
        "ledger_contract": (
            "append-only. One 'run' record per invocation carrying every source's status and its "
            "reason, and one 'observation' record per (series, stamp) the desk had never seen, "
            "carrying first_seen_utc. The first-seen field exists so the screen's assumed "
            "publication lag becomes a measured one: both flow sources serve full history on every "
            "fetch, so nothing but the observation instant is unrecoverable."),
        "authority": "NONE -- this script fetches, records and writes. It screens nothing.",
    }

    with out.open("a", encoding="utf-8") as fh:
        for rec in new_records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.write(json.dumps(run, sort_keys=True) + "\n")

    ok = [s for s in statuses if s["status"] == "OK"]
    print(f"primary-market-flow collector -> {out}")
    print(f"  {len(ok)}/{len(statuses)} source(s) OK, {len(new_records)} new observation(s), "
          f"{run['elapsed_s']}s"
          + ("  [BOOTSTRAP -- first-seen is the bootstrap instant, not publication time]"
             if bootstrap else ""))
    for s in statuses:
        mark = "OK  " if s["status"] == "OK" else "!!  "
        extra = (f"served {s['rows_served']:>5} new {s['rows_new']:>5}  {s['span']}"
                 if s["status"] == "OK" else str(s.get("reason", ""))[:96])
        print(f"  {mark}{s['source']:<24} {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
