"""Adapters for the three mechanisms this desk could already measure and was not.

WHY THESE THREE FIRST (measured 2026-08-29)

Of the five mechanisms `family_generic` could not honestly measure, three were blocked by WIRING
rather than by missing data. The observables were sitting on disk, unused, while a price proxy
stood in for them:

    positioning_extreme   COT parquets present     -> used distance from a 60-bar mean
    carry_change          carry_state.json, 388KB  -> used a 24-bar price return
    cross_market_move     251 instruments with bars -> used ONE instrument's own return

That is the highest-return work available on this desk: no data to acquire, no model to call, no
threshold to argue about. Each one turns a mechanism the search had to skip into one it can
measure directly.

POINT-IN-TIME IS THE HARD PART, and it is where a careless version of this file would
manufacture a spectacular backtest. COT is published on a lag -- a report dated Tuesday is not
public until the following Friday -- so a naive merge on report_date leaks three days of future
positioning into every bar. `CotPositioningAdapter` lags explicitly and says by how much.

WHAT AN ADAPTER REFUSES TO DO. If its file is missing, it reports UNAVAILABLE with the path it
wanted. It never falls back to a price feature: the fallback is the defect this whole package
exists to remove.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research_os.adapters.base import MeasurementResult, ResearchAdapter

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"

#: COT is released Friday for the preceding Tuesday. Anything less than this leaks.
#: Deliberately generous -- an extra day of lag costs a little power; a day too few costs the
#: entire result and looks like a discovery while it does it.
_COT_PUBLICATION_LAG_DAYS = 4

#: Currency code -> the COT file that carries its positioning.
_COT_FILES = {
    "AUD": "aud", "CAD": "cad", "CHF": "chf", "EUR": "eur", "GBP": "gbp",
    "JPY": "jpy", "NZD": "nzd", "USD": "usd", "MXN": "mxn", "BRL": "brl",
    "XAU": "gold", "XAG": "silver",
}


def _as_utc_index(idx: pd.Index) -> pd.DatetimeIndex:
    """A tz-AWARE UTC index. Naive stamps are assumed UTC, which is what this desk stores."""
    di = pd.DatetimeIndex(idx)
    return di.tz_localize("UTC") if di.tz is None else di.tz_convert("UTC")


def _as_utc(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.index = _as_utc_index(out.index)
    return out


def _currencies(symbol: str) -> tuple[str, str]:
    s = symbol.upper()
    if len(s) >= 6:
        return s[:3], s[3:6]
    return s, ""


class CotPositioningAdapter(ResearchAdapter):
    """Real COT/TFF net positioning, lagged to publication. Replaces a price-extension proxy."""

    mechanism = "positioning_extreme"
    requires = ("desks/mt5/data/cot/<ccy>.parquet",)

    def compatibility(self, spec: dict[str, Any]) -> float:
        sym = str(spec.get("symbol") or "")
        base, quote = _currencies(sym)
        have = [c for c in (base, quote) if _COT_FILES.get(c)
                and (DESK / "data" / "cot" / f"{_COT_FILES[c]}.parquet").exists()]
        if not have:
            return 0.0
        # Both legs measurable is a genuine differential; one leg is still a real positioning
        # measure for that currency, which is more than a price proxy ever was.
        return 1.0 if len(have) == 2 else 0.7

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        base, quote = _currencies(sym)
        legs: dict[str, pd.Series] = {}
        missing: list[str] = []

        for ccy in (base, quote):
            key = _COT_FILES.get(ccy)
            if not key:
                continue
            path = DESK / "data" / "cot" / f"{key}.parquet"
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
                continue
            try:
                df = pd.read_parquet(path)
            except Exception as exc:
                missing.append(f"{path.name} unreadable: {type(exc).__name__}")
                continue
            if "report_date" not in df.columns:
                missing.append(f"{path.name} has no report_date")
                continue
            d = df.copy()
            d["report_date"] = pd.to_datetime(d["report_date"], utc=True, errors="coerce")
            d = d.dropna(subset=["report_date"]).sort_values("report_date")
            longs = pd.to_numeric(d.get("noncomm_positions_long_all"), errors="coerce")
            shorts = pd.to_numeric(d.get("noncomm_positions_short_all"), errors="coerce")
            oi = pd.to_numeric(d.get("open_interest_all"), errors="coerce")
            # NET AS A FRACTION OF OPEN INTEREST, so the number means the same thing across
            # currencies and across years as contract sizes drift.
            net = (longs - shorts) / oi.replace(0, np.nan)
            # PUBLICATION LAG: the value becomes knowable only days after its report date.
            d["_available_at"] = d["report_date"] + pd.Timedelta(days=_COT_PUBLICATION_LAG_DAYS)
            leg = pd.Series(net.to_numpy(), index=d["_available_at"]).dropna()
            if not leg.empty:
                legs[ccy] = leg

        if not legs:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CotPositioningAdapter",
                notes=(f"no COT series for {sym}; wanted {missing or list(_COT_FILES)}. This is a "
                       f"data-acquisition task -- substituting price extension would test "
                       f"momentum and call it positioning."))

        idx = bars.index
        combined: pd.Series | None = None
        for ccy, leg in legs.items():
            leg = _as_utc(leg)
            uidx = _as_utc_index(idx)
            aligned = leg.reindex(leg.index.union(uidx)).sort_index().ffill().reindex(uidx)
            aligned.index = idx
            sign = 1.0 if ccy == base else -1.0
            combined = aligned * sign if combined is None else combined + aligned * sign

        assert combined is not None
        # The CLAIM is "positioning extreme", so the observable is the z-score of net positioning
        # against its own history, not the raw level.
        z = (combined - combined.rolling(52, min_periods=8).mean()) / \
            combined.rolling(52, min_periods=8).std()
        both = len(legs) == 2
        return MeasurementResult(
            status="DIRECT" if both else "VALIDATED_PROXY",
            adapter="CotPositioningAdapter",
            feature_ids=[f"cot_net_z:{c}" for c in legs],
            confidence=1.0 if both else 0.7,
            pit_safe=True,
            series=z,
            notes=(f"net non-commercial positioning as a share of open interest, z-scored over 52 "
                   f"weeks, for {'/'.join(legs)}; lagged {_COT_PUBLICATION_LAG_DAYS} days to "
                   f"publication so no bar sees a report before it was public"
                   + ("" if both else ". Only one leg available, so this is the currency's "
                                      "positioning rather than the pair's differential.")))

    def pit_check(self, series: pd.Series, bars: pd.DataFrame) -> tuple[bool, str]:
        return True, (f"COT values are stamped at report_date + {_COT_PUBLICATION_LAG_DAYS}d and "
                      f"forward-filled, so a bar can only see a report already published")


class CarryAdapter(ResearchAdapter):
    """The swap actually paid, from recorded contract terms. Replaces a 24-bar price return."""

    mechanism = "carry_change"
    requires = ("desks/mt5/data/carry_state.json",)

    def _state(self) -> dict[str, Any]:
        p = DESK / "data" / "carry_state.json"
        try:
            loaded = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def compatibility(self, spec: dict[str, Any]) -> float:
        st = self._state()
        syms = (st.get("symbols") or {})
        sym = str(spec.get("symbol") or "")
        if not syms:
            return 0.0
        row = syms.get(sym) or {}
        # Both sides recorded means a real differential; one side is still the financing actually
        # paid on that side.
        have = sum(1 for side in ("long", "short") if isinstance(row.get(side), dict))
        return {0: 0.0, 1: 0.7, 2: 1.0}[have]

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        st = self._state()
        row = (st.get("symbols") or {}).get(sym)
        if not isinstance(row, dict):
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CarryAdapter",
                notes=(f"{sym} has no recorded contract terms in carry_state.json. Using a price "
                       f"return instead would measure momentum and call it carry."))

        def _side(name: str) -> float | None:
            side = row.get(name)
            if not isinstance(side, dict):
                return None
            # FIELD NAMES READ FROM THE FILE, not guessed. A first version tried
            # money_per_lot_night/carry_per_lot_night/swap and found none of them, reporting
            # UNAVAILABLE on a symbol whose financing was recorded all along -- a guessed schema
            # produces a data gap that does not exist and sends the desk hunting for data it has.
            # `swap_money_per_lot_night` is the CREDIT (positive = broker pays the desk);
            # `swap_cost_per_lot_night` is the same figure as a cost.
            for key in ("swap_money_per_lot_night", "money_per_lot_night",
                        "carry_per_lot_night", "swap"):
                v = side.get(key)
                if isinstance(v, (int, float)):
                    return float(v)
            return None

        long_c, short_c = _side("long"), _side("short")
        if long_c is None and short_c is None:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CarryAdapter",
                notes=(f"{sym} terms recorded but no financing figure among "
                       f"money_per_lot_night/carry_per_lot_night/swap"))

        # THE CARRY DIFFERENTIAL is what the mechanism is about: what you are paid to be long
        # minus what you are paid to be short.
        # Narrow explicitly rather than with a ternary mypy cannot follow: the differential is
        # the mechanism when both sides are known, and one side alone is still the financing
        # actually paid on that side.
        if long_c is not None and short_c is not None:
            both = True
            level = (long_c - short_c) / 2.0
        else:
            both = False
            level = float(long_c) if long_c is not None else -float(short_c or 0.0)
        # carry_state is a SNAPSHOT, not a time series: the honest observable is a constant level
        # per symbol, and that is exactly what it is -- a cross-sectional carry, not a change.
        series = pd.Series(level, index=bars.index, dtype=float)
        return MeasurementResult(
            status="VALIDATED_PROXY",
            adapter="CarryAdapter",
            feature_ids=[f"carry_diff:{sym}"],
            confidence=1.0 if both else 0.7,
            pit_safe=True,
            series=series,
            notes=(f"financing actually paid per lot per night from recorded terms "
                   f"({'both sides' if both else 'one side'}). VALIDATED_PROXY rather than "
                   f"DIRECT because carry_state is a SNAPSHOT: it gives the current level, not "
                   f"its history, so a cell using it measures a cross-sectional carry rather "
                   f"than a carry CHANGE. Recording a time series would make this DIRECT."))


class CrossAssetAdapter(ResearchAdapter):
    """A genuine second instrument's lead. Replaces one instrument's own return."""

    mechanism = "cross_market_move"
    requires = ("desks/mt5/data/universe/<peer>_H1.parquet",)

    def compatibility(self, spec: dict[str, Any]) -> float:
        peer = spec.get("peer_symbol") or spec.get("peer")
        if peer:
            return 1.0 if (DESK / "data" / "universe" / f"{peer}_H1.parquet").exists() else 0.0
        # No peer named: the adapter can still pick a defensible one from the same asset class,
        # but a chosen peer is weaker evidence than a named one.
        return 0.6

    def _default_peer(self, symbol: str) -> str | None:
        """A defensible lead instrument when the hypothesis did not name one.

        Chosen by SHARED CURRENCY or asset class, never by correlation -- picking the
        highest-correlated peer from the same data the test then runs on is selection on the
        outcome, and would manufacture a lead-lag that is not there.
        """
        base, quote = _currencies(symbol)
        uni = DESK / "data" / "universe"
        for cand in (f"{base}USD", f"USD{quote}", "XAUUSD", "US500"):
            if cand != symbol and (uni / f"{cand}_H1.parquet").exists():
                return cand
        return None

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        peer = spec.get("peer_symbol") or spec.get("peer") or self._default_peer(sym)
        if not peer:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=(f"no peer instrument for {sym}. A single-instrument feature contains no "
                       f"cross-market information at all -- this is not a weaker measure of the "
                       f"mechanism, it is a measure of something else."))
        path = DESK / "data" / "universe" / f"{peer}_H1.parquet"
        if not path.exists():
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=f"peer {peer} has no bars at {path.relative_to(ROOT)}")
        try:
            pdf = pd.read_parquet(path).rename(columns=str.lower)
        except Exception as exc:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=f"peer {peer} unreadable: {type(exc).__name__}")

        lag = int(spec.get("lead_bars", 1))
        # THE PEER'S PAST MOVE, shifted so the bar cannot see the peer's current bar. `lag>=1` is
        # the non-anticipation guarantee, and it is asserted rather than assumed.
        if lag < 1:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="CrossAssetAdapter",
                notes=(f"lead_bars={lag} would let this bar see the peer's contemporaneous move; "
                       f"a lead-lag claim needs a strictly positive lag"))
        peer_ret = pdf["close"].pct_change().shift(lag)
        # NORMALISE BOTH INDICES TO UTC BEFORE ANY UNION. Some universe parquets are tz-aware and
        # some are tz-naive; unioning them raises "Cannot compare tz-naive and tz-aware", and the
        # tempting fix -- dropping the tz -- would silently shift a peer by the broker offset and
        # invent a lead-lag that is purely a timezone error.
        peer_ret = _as_utc(peer_ret)
        target_index = _as_utc_index(bars.index)
        aligned = peer_ret.reindex(peer_ret.index.union(target_index)).sort_index() \
            .ffill().reindex(target_index)
        aligned.index = bars.index
        named = bool(spec.get("peer_symbol") or spec.get("peer"))
        return MeasurementResult(
            status="DIRECT" if named else "VALIDATED_PROXY",
            adapter="CrossAssetAdapter",
            feature_ids=[f"peer_ret:{peer}:lag{lag}"],
            confidence=1.0 if named else 0.6,
            pit_safe=True,
            series=aligned,
            notes=(f"{peer}'s return lagged {lag} bar(s), aligned to {sym}'s index"
                   + ("" if named else f". The hypothesis named no peer, so {peer} was chosen by "
                                       f"shared currency/asset class -- NEVER by correlation, "
                                       f"which would select on the outcome being tested.")))
