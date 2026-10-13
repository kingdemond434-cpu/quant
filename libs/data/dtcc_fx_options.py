"""The public FX option tape: DTCC's CFTC swap-data dissemination, reduced to daily pair features.

Source: OpenBB-finance/OpenBB `openbb_platform/providers/cftc/openbb_cftc/utils/` (Apache-2.0,
Copyright (c) 2021-2026 OpenBB Inc.). The manifest URL, the slice layout, the field names and
the rule for reading a vanilla option's premium per unit of base currency come from its
`dtcc.py`, `fx_options.py`, `fx_vol.py` and `curve.parse_notional`. This is a desk-native
rewrite with no dependency on openbb_core; the licence is `libs/data/LICENSE_OpenBB`.

WHAT IT IS. Every swap dealer reports each OTC FX option it prints under CFTC Part 43, and DTCC
publishes a cumulative daily slice per asset class, keyless, retained for 366 days. That is the
only free, public record of who is paying for FX optionality, and nothing on the desk read it.

WHAT LEAVES, per MT5 FX pair and dissemination day (vanilla prints, new trades only):
  * `atm_vol` -- a near-the-money implied-volatility proxy. Premium per unit of base, as a
    fraction of the reference level, over 0.3989 * sqrt(T) (Brenner-Subrahmanyam), median over
    prints within 0.5% of the reference and 7..95 days to expiry. The reference is the day's
    median strike, because PPD carries no spot; a declared approximation, not a GK inversion.
  * `call_share` -- call-on-base notional over all vanilla notional. PPD does not say who bought,
    so this is where strikes were traded, not a directional flow.
  * `otm_call_share` -- out-of-the-money calls over out-of-the-money calls plus puts: the tape's
    own risk-reversal side.
  * `log_notional` -- total base notional traded, logged.
A day's slice is complete only after the day closes, so every row is stamped available at 06:00
UTC the next day; the rows are declared final at publication (a correction arrives as its own
later print, never as a rewritten one).
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

MANIFEST_URL = "https://pddata.dtcc.com/ppd/api/cumulative/CFTC/FX"
#: The MT5 FX symbols the tape is reduced for. A pair outside this set is not tallied.
PAIRS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "EURGBP", "EURJPY",
    "GBPJPY", "EURCHF", "AUDJPY", "USDMXN", "USDZAR", "USDNOK", "USDSEK", "USDCNH", "USDSGD",
    "USDTRY", "USDPLN", "USDHUF", "USDCZK", "EURNOK", "EURSEK", "EURPLN", "AUDNZD",
)
SLICES_PER_PASS = 6
AVAILABLE_AFTER = timedelta(days=1, hours=6)
MIN_PRINTS = 3


def parse_amount(value: str | None) -> float | None:
    """A disseminated amount, with the cap marker dropped and the all-nines mask read as absent
    (OpenBB `curve.parse_notional`)."""
    text = (value or "").strip().rstrip("+")
    digits = text.replace(",", "").replace(".", "")
    if not text or (digits and set(digits) == {"9"}):
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _day(value: str | None) -> date | None:
    try:
        return datetime.fromisoformat((value or "").strip()[:10]).date()
    except ValueError:
        return None


def slice_rows(payload: bytes) -> Iterator[dict[str, str]]:
    """The CSV member of a cumulative slice zip, as records."""
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not members:
            return
        with z.open(members[0]) as fh:
            yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig",
                                                       errors="replace"))


def _prints(records: Iterable[dict[str, str]], day: date) -> dict[str, list[dict[str, Any]]]:
    """Vanilla new-trade prints executed on `day`, by MT5 pair symbol."""
    wanted = set(PAIRS)
    out: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        if not (r.get("UPI FISN") or "").strip().startswith("NA/O Van"):
            continue
        if (r.get("Action type") or "").strip() != "NEWT":
            continue
        if _day(r.get("Execution Timestamp")) != day:
            continue
        legs = (r.get("UPI Underlier Name") or "").strip().upper().split()
        if len(legs) != 2:
            continue
        base, quote = legs
        if base + quote not in wanted:
            if quote + base not in wanted:
                continue
            base, quote = quote, base
        call_ccy = (r.get("Call currency") or "").strip().upper()
        put_ccy = (r.get("Put currency") or "").strip().upper()
        if call_ccy == base:
            is_call, notional = True, parse_amount(r.get("Call amount"))
        elif put_ccy == base:
            is_call, notional = False, parse_amount(r.get("Put amount"))
        else:
            continue
        expiry = _day(r.get("Expiration Date"))
        strike = parse_amount(r.get("Strike Price"))
        if not (notional and expiry and strike and strike > 0):
            continue
        out.setdefault(base + quote, []).append({
            "is_call": is_call, "notional": notional, "strike": strike,
            "tenor": (expiry - day).days, "premium": parse_amount(r.get("Option Premium Amount")),
            "premium_ccy": (r.get("Option Premium Currency") or "").strip().upper(),
            "base": base, "quote": quote})
    return out


def reduce_pair(prints: list[dict[str, Any]]) -> dict[str, float] | None:
    """The day's features for one pair, or None when too few prints to say anything."""
    if len(prints) < MIN_PRINTS:
        return None
    raw = median(p["strike"] for p in prints)
    for p in prints:                       # a strike quoted the other way up is inverted
        if abs(math.log(1.0 / p["strike"] / raw)) < abs(math.log(p["strike"] / raw)):
            p["strike"] = 1.0 / p["strike"]
    ref = median(p["strike"] for p in prints)
    total = sum(p["notional"] for p in prints)
    calls = sum(p["notional"] for p in prints if p["is_call"])
    otm_c = sum(p["notional"] for p in prints if p["is_call"] and p["strike"] > ref)
    otm_p = sum(p["notional"] for p in prints if not p["is_call"] and p["strike"] < ref)
    vols = []
    for p in prints:
        if not (p["premium"] and 7 <= p["tenor"] <= 95):
            continue
        if abs(math.log(p["strike"] / ref)) > 0.005:
            continue
        per_unit = p["premium"] / p["notional"]
        if p["premium_ccy"] == p["base"]:
            per_unit *= ref
        elif p["premium_ccy"] != p["quote"]:
            continue
        vols.append(per_unit / ref / (0.3989 * math.sqrt(p["tenor"] / 365.0)))
    vols = [v for v in vols if 0.005 < v < 1.0]
    return {"atm_vol": median(vols) if len(vols) >= MIN_PRINTS else float("nan"),
            "call_share": calls / total,
            "otm_call_share": otm_c / (otm_c + otm_p) if otm_c + otm_p > 0 else float("nan"),
            "log_notional": math.log(total), "n_prints": float(len(prints))}


def manifest_dates(manifest: list[dict[str, Any]]) -> dict[str, str]:
    """report date -> download URL, from the manifest's file names."""
    out: dict[str, str] = {}
    for e in manifest:
        parts = str(e.get("fileName") or "").rsplit(".", 1)[0].split("_")
        if len(parts) >= 3 and all(x.isdigit() for x in parts[-3:]) and e.get("fullFilePath"):
            out["-".join(parts[-3:])] = str(e["fullFilePath"])
    return out


def ingest(root: Path, *, fetch: Callable[[str], tuple[bytes | None, str]],
           now: datetime | None = None, per_pass: int = SLICES_PER_PASS) -> dict[str, Any]:
    """Reduce the newest closed days not yet held, `per_pass` slices at a time, into
    `root/daily.json` ({day: {pair: features}}). Returns what this pass did."""
    now = now or datetime.now(UTC)
    path = root / "daily.json"
    try:
        held: dict[str, Any] = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        held = {}
    raw, _ = fetch(MANIFEST_URL)
    if raw is None:
        return {"status": "UNREACHABLE", "days_held": len(held)}
    try:
        manifest = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return {"status": "UNPARSEABLE_MANIFEST", "days_held": len(held)}
    dates = manifest_dates(manifest if isinstance(manifest, list) else [])
    closed = sorted((d for d in dates if d < now.date().isoformat() and d not in held),
                    reverse=True)
    done: list[str] = []
    for d in closed[:per_pass]:
        payload, _ = fetch(dates[d])
        if payload is None:
            continue
        try:
            by_pair = _prints(slice_rows(payload), date.fromisoformat(d))
        except (zipfile.BadZipFile, csv.Error, UnicodeError):
            by_pair = {}                   # held as an empty day, so it is not refetched forever
        held[d] = {k: v for k, prints in by_pair.items() if (v := reduce_pair(prints))}
        done.append(d)
    root.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(held, sort_keys=True), "utf-8")
    tmp.replace(path)
    return {"status": "OK", "slices_reduced": done, "days_held": len(held),
            "days_pending": max(0, len(closed) - len(done))}


def frames(root: Path, now: datetime | None = None) -> dict[str, pd.DataFrame]:
    """Per (pair, feature): event-dated `value` + `available_time`, for the PIT certificate."""
    now = now or datetime.now(UTC)
    try:
        held = json.loads((root / "daily.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    cols: dict[str, dict[pd.Timestamp, float]] = {}
    for d, pairs in held.items():
        t = pd.Timestamp(d, tz="UTC")
        for pair, feats in pairs.items():
            for k, v in feats.items():
                if k != "n_prints" and isinstance(v, (int, float)) and math.isfinite(v):
                    cols.setdefault(f"dtcc_fx_{pair}_{k}", {})[t] = float(v)
    out: dict[str, pd.DataFrame] = {}
    for name, pts in cols.items():
        s = pd.Series(pts).sort_index()
        avail = s.index + AVAILABLE_AFTER
        f = pd.DataFrame({"value": s.to_numpy(), "available_time": avail}, index=s.index)
        out[name] = f.loc[f["available_time"] <= pd.Timestamp(now)]
    return out
