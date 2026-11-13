#!/usr/bin/env python3
"""SLEEVE COST IN R -- what a round trip costs each sleeve, in R, at the hours it actually enters.

WHY (idea 656). The management sweep (reports/management_sweep/RESULT.md, 2026-11-11) found
1/ATR vol-targeting wins GROSS geometric growth in 96% of arms and NET in only 15%: it sizes up
in quiet hours, where spread/ATR is highest, so the spread takes a bigger bite in R. Before any
cost-aware sizing arm (ideas 415/531) can be judged, the desk must know -- per live, standby
and certified sleeve -- what the round trip costs in R at that sleeve's own entry hours, what
its certificate CHARGED, and whether the certificate's edge survives the measured cost.

PER SLEEVE
    cost_R_measured  = (spread at entry hour + commission + slippage) / stop distance
    cost_R_charged   = what the certificate's own gauntlet charged, in R
    gap              = measured / charged - 1
    gross_edge_R     = cert ev (net of charged cost) + cost_R_charged
    net_edge_R       = gross_edge_R - cost_R_measured
    spread/ATR at entry against the symbol's median spread/ATR over all measured hours
    flags: COST_EATS_EDGE (net <= 0), UNDERCHARGED (measured > 1.25 x charged)

WHERE EACH NUMBER COMES FROM
  * spread at hour: data/cost_surface.json (the bar tape's spread x broker-hour surface, p50).
    A venue other than Fusion is read from data/cost_surface_<venue>.json when that file
    exists (same schema); absent, the venue is UNMEASURED by name.
  * entry hours: the sleeve's own live entries in live_ledger.jsonl, read AS BROKER CLOCK
    (the gateway stamps MT5 deal.time, which is trade-server wall time, with a false +00:00;
    see ledger_broker_hm); else the session window's placement hour
    (research/entry_timing.WINDOWS, broker clock); else UNMEASURED.
  * stop distance: median |entry - sl| over the sleeve's own live entries; else the cert-
    implied stop (see below); else spec stop_atr x H1 ATR20 for an H1 sleeve; else UNMEASURED.
  * charged cost: the gauntlet charges 2 spread crossings at baseline and 3 under stress with
    commission unchanged (universal_gate, COST_SCENARIO 3). So ev - exp_x3 is ONE spread
    crossing in R, the charged spread is 2(ev - exp_x3), and the implied stop is
    (one crossing of the registry median spread, in price) / (ev - exp_x3).
    CAVEAT, stated: the gauntlet's series is R summed per DAY; for a one-trade-a-day session
    sleeve that is per trade, for others it is per active day.
  * commission: 2.00 account currency per lot per side (engine.Costs), converted to price units
    through tick_value; no tick_value -> UNMEASURED.
  * slippage: median slip_r over the sleeve's rows in fill_corpus.jsonl with >= MIN_SLIP_N
    observations; else UNMEASURED.

MISSING IS UNMEASURED, NEVER 0 (L1.28a). When slippage is unmeasured the measured cost is
published as a FLOOR (spread + commission), named as such; a floor that already eats the edge
or exceeds the charge is conclusive for the flag, since the true cost can only be higher.

REPORT ONLY. Sizes, vetoes and promotes nothing: report_only true, consumer null.

    python desks/mt5/research/sleeve_cost_in_r.py --once
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))
from mt5desk.calendar_us import us_eastern_offset  # noqa: E402

DATA = DESK / "data"
REPORTS = DESK / "reports"
SLEEVES = DATA / "sleeves.json"
SURFACE = DATA / "cost_surface.json"
UNIVERSE = DATA / "universe" / "universe.json"
LEDGER = DATA / "live_ledger.jsonl"
CORPUS = DATA / "fill_corpus.jsonl"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
#: The Judge's SM1 spike-minute sweep: the AUTHORITY for every certificate key it covers.
SM1 = Path("/mnt/project-files/reports/box_reads/spike_minute_sweep_SM1_slice_2026-11-11.json")
SM1_LOCAL = REPORTS / "box_reads" / "spike_minute_sweep_SM1_slice.json"
OUT = REPORTS / "SLEEVE_COST_IN_R.json"

SCHEMA = "sleeve-cost-in-r-1"
UNMEASURED = "UNMEASURED"
UNMEASURED_BASIS = "UNMEASURED_BASIS"
UNMEASURED_MINUTE = "UNMEASURED_MINUTE"
#: Chart minutes per timeframe label, for the engine's fill rule (open of the next bar).
TF_MINUTES: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
#: engine.Costs.commission_per_lot -- measured on the live Fusion account, per lot per SIDE.
COMMISSION_PER_LOT_SIDE = 2.00
#: universal_gate: baseline crosses the spread twice, stress (COST_SCENARIO 3) three times.
BASELINE_CROSSINGS = 2.0
UNDERCHARGE_TOL = 0.25
MIN_SLIP_N = 3
#: Session placement hours on the broker clock (mirrors research/entry_timing.WINDOWS).
WINDOW_HOURS: dict[str, int] = {"asia": 7, "london_am": 13, "ny_open": 14, "afternoon": 17}
#: Families whose fill hour is fixed by construction, whatever the session label says:
#: overnight_gap_decay fills at broker hour 01 (engine.Costs.from_symbol docstring).
FAMILY_HOURS: dict[str, int] = {"overnight_gap_decay": 1}
#: A surface cell whose bars are mostly zero-spread is a degenerate reading, not a quote.
SUSPECT_ZERO_FRAC = 0.5
VENUES = ("fusion", "e8", "ftmo")
LEDGER_NAME_LEN = 27  # MT5 order comments truncate the sleeve name


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _um(why: str) -> dict[str, str]:
    return {"status": UNMEASURED, "why": why}


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def broker_hour(ts: datetime) -> int:
    """UTC -> broker clock. The broker runs NY+7, so it follows US DST: UTC+3 while US Eastern
    is UTC-4, UTC+2 while it is UTC-5. The rule is the desk's own calendar_us one, not a copy."""
    ts = ts.astimezone(UTC)
    return (ts.hour - us_eastern_offset(ts.date()) + 7) % 24


def _parse_ts(s: Any) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


# ----------------------------------------------------------------------------- population
def population(sleeves: Any, survivors: Any) -> list[dict[str, Any]]:
    """Every LIVE/STANDBY sleeve, plus every certified survivor no sleeve already carries."""
    out: list[dict[str, Any]] = []
    cells: set[str] = set()
    rows = (sleeves or {}).get("sleeves") if isinstance(sleeves, dict) else None
    for s in rows or []:
        if not isinstance(s, dict) or s.get("status") not in ("LIVE", "STANDBY"):
            continue
        c = s.get("certificate")
        cert: dict[str, Any] = c if isinstance(c, dict) else {}
        if cert.get("cell"):
            cells.add(str(cert["cell"]))
        out.append({"name": s.get("name"), "status": s.get("status"), "symbol": s.get("symbol"),
                    "session": s.get("selector") or s.get("window") or s.get("session"),
                    "cell": cert.get("cell"), "spec": s})
    surv = (survivors or {}).get("survivors") if isinstance(survivors, dict) else None
    for key, row in (surv or {}).items() if isinstance(surv, dict) else []:
        if key in cells or not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        out.append({"name": key, "status": "CERTIFIED",
                    "symbol": row.get("sym") or spec.get("symbol"),
                    "session": spec.get("selector"), "cell": key, "spec": spec})
    return out


# ----------------------------------------------------------------------------- inputs
def ledger_entries(name: str, ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = name.rsplit("_v", 1)[0] if name.rsplit("_v", 1)[-1].isdigit() else name
    keys = {name[:LEDGER_NAME_LEN], base[:LEDGER_NAME_LEN]}
    out = []
    for r in ledger:
        sl, ep = _num(r.get("sl")), _num(r.get("entry_price"))
        if str(r.get("sleeve") or "")[:LEDGER_NAME_LEN] in keys and sl and ep and sl != ep:
            out.append(r)
    return out


def ledger_broker_hm(ts: datetime) -> tuple[int, int]:
    """live_ledger entry_time is ALREADY broker wall-clock: gateway.py writes
    datetime.fromtimestamp(deal.time_msc/1000, tz=UTC) and MT5 deal times are trade-server
    seconds, so the +00:00 is a mislabel. Never pass these through broker_hour (that would add
    the +2/+3 twice); broker_hour is for genuine UTC inputs only."""
    return ts.hour, ts.minute


def entry_hours(item: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    hours = [ledger_broker_hm(ts)[0] for r in entries if (ts := _parse_ts(r.get("entry_time")))]
    if hours:
        counts: dict[int, int] = {}
        for h in hours:
            counts[h] = counts.get(h, 0) + 1
        return {"hours": counts, "source": "live_ledger", "n": len(hours)}
    fam = str((item.get("spec") or {}).get("family") or "")
    for key, hour in FAMILY_HOURS.items():
        if key in fam or key in str(item.get("cell") or ""):
            return {"hours": {hour: 1}, "source": f"family_fill_hour:{key}", "n": 0}
    sess = str(item.get("session") or "")
    if sess in WINDOW_HOURS:
        return {"hours": {WINDOW_HOURS[sess]: 1}, "source": f"session_window:{sess}", "n": 0}
    return _um(f"no live entries and no known session window ({sess or 'none'})")


def entry_minutes(item: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Broker (hour, minute) of each fill. Ledger entries first; otherwise the spec's entry rule
    read the way the engine fills (PR #1077, `cost_surface.fill_minutes`): a market signal fills
    at the OPEN of the bar after its signal bar, never signal + wait_bars."""
    spec0 = item.get("spec") or {}
    resting = bool(spec0.get("window")) or "pending" in str(spec0.get("exec") or "")
    fills: list[tuple[int, int]] = []
    for r in entries:
        ts = _parse_ts(r.get("entry_time"))
        if ts:
            fills.append((-1, -1) if resting else ledger_broker_hm(ts))
    if fills:
        return {"fills": fills, "source": "live_ledger"}
    spec = item.get("spec") or {}
    fam = str(spec.get("family") or "")
    for key, hour in FAMILY_HOURS.items():
        if key in fam or key in str(item.get("cell") or ""):
            return {"fills": [(hour, 0)], "source": f"family_fill_minute:{key}"}
    sess = str(item.get("session") or "")
    if sess in WINDOW_HOURS:
        rawp = spec.get("params")
        params: dict[str, Any] = rawp if isinstance(rawp, dict) else {}
        tf = TF_MINUTES.get(str(spec.get("timeframe") or params.get("timeframe") or "H1"), 60)
        m = WINDOW_HOURS[sess] * 60 + tf
        return {"fills": [((m // 60) % 24, m % 60)],
                "source": f"spec: open of the bar after the {sess} signal bar"}
    return _um("no live entries and no spec entry rule")


def minute_spread_pts(ssym: dict[str, Any], fills: list[tuple[int, int]]
                      ) -> dict[str, Any]:
    """Fill-weighted charge where each fill pays max(its hour's p50, its minute's spike p50).
    Only RAISES a charge. No published spike_minutes -> UNMEASURED_MINUTE, never the hour."""
    raw = ssym.get("tick_hours")
    th: dict[str, Any] = raw if isinstance(raw, dict) else {}
    spikes = th.get("spike_minutes")
    if not isinstance(spikes, dict):
        return {"status": UNMEASURED_MINUTE,
                "why": "surface publishes no tick_hours.spike_minutes (PR #1077 not landed)"}
    hrs = ssym.get("hours") or {}
    total, hit, n = 0.0, 0, 0
    minutes: dict[str, int] = {}
    for h, m in fills:
        if h < 0:  # trigger / resting order: fills intrabar at a price, never a spike
            continue
        n += 1
        base = _num((hrs.get(str(h)) or {}).get("p50"))
        if base is None or (hrs.get(str(h)) or {}).get("status") != "MEASURED":
            return {"status": UNMEASURED_MINUTE, "why": f"hour {h} not MEASURED"}
        key = f"{h:02d}:{m:02d}"
        sp = _num((spikes.get(key) or {}).get("p50"))
        if sp is not None and sp > base:
            hit += 1
            minutes[key] = minutes.get(key, 0) + 1
            total += sp
        else:
            total += base
    if not n:
        return {"status": "NO_MARKET_FILLS", "spike_share": 0.0, "minutes": {},
                "why": "every fill is a trigger/resting order: the hour's charge stands"}
    return {"spread_pts": total / n, "spike_share": round(hit / n, 4), "minutes": minutes,
            "n_fills": n}


def spread_at(surface_sym: dict[str, Any], hours: dict[int, int], ts: float
              ) -> tuple[float | None, str]:
    """Entry-weighted p50 spread in PRICE units over the sleeve's entry hours."""
    hrs = surface_sym.get("hours") or {}
    num = den = 0.0
    missing = []
    for h, w in hours.items():
        cell = hrs.get(str(h)) or {}
        p50 = _num(cell.get("p50"))
        if cell.get("status") != "MEASURED" or p50 is None:
            missing.append(h)
            continue
        num += p50 * ts * w
        den += w
    if missing:
        return None, f"spread surface hour(s) {sorted(missing)} not MEASURED"
    return (num / den if den else None), "cost_surface p50 at entry hour"


def spread_atr_ratio(surface_sym: dict[str, Any], hours: dict[int, int]) -> dict[str, Any]:
    atr = _num(surface_sym.get("atr20_h1_pts"))
    if not atr:
        return _um("no atr20_h1_pts on the surface")
    per_hour = {int(h): float(c["p50"]) / atr for h, c in (surface_sym.get("hours") or {}).items()
                if c.get("status") == "MEASURED" and _num(c.get("p50")) is not None}
    if not per_hour or any(h not in per_hour for h in hours):
        return _um("entry hour not MEASURED on the surface")
    w = sum(hours.values())
    at_entry = sum(per_hour[h] * n for h, n in hours.items()) / w
    med = statistics.median(per_hour.values())
    return {"at_entry": round(at_entry, 5), "symbol_median_all_hours": round(med, 5),
            "entry_over_median": round(at_entry / med, 3) if med > 0 else None}


def commission_price(meta: dict[str, Any]) -> float | None:
    """Round-trip commission in PRICE units (engine.Costs.from_symbol conversion)."""
    cs, ts, tv = (_num(meta.get(k)) for k in ("contract_size", "tick_size", "tick_value"))
    if not (cs and ts and tv and cs > 0 and ts > 0 and tv > 0):
        return None
    qpa = cs * ts / tv
    return 2.0 * COMMISSION_PER_LOT_SIDE * qpa / cs


def cert_terms(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return _um("no gauntlet certificate row")
    g = row.get("gates") or {}
    ev = _num((g.get("expected_value") or {}).get("ev"))
    x3 = _num((g.get("stress_costs") or {}).get("exp_x3"))
    if ev is None or x3 is None:
        return _um("certificate lacks ev or exp_x3")
    # The gauntlet's series is R SUMMED PER ACTIVE DAY. ev - exp_x3 is one crossing PER TRADE
    # only once both are divided by trades per active day; without that figure the row is
    # per_day and its measured/charged ratio is not an exact number.
    tpd = _num(row.get("trades_per_active_day"))
    if tpd is None and _num(row.get("n_trades")) and _num(row.get("days")):
        tpd = float(row["n_trades"]) / float(row["days"])
    basis = "per_trade"
    if tpd and tpd > 0:
        ev, x3 = ev / tpd, x3 / tpd
    else:
        basis = "per_day"
    one = ev - x3
    if one <= 0:
        return _um(f"ev - exp_x3 = {one:.4f} <= 0: one spread crossing not recoverable")
    return {"ev_R": ev, "exp_x3_R": x3, "one_crossing_R": one, "ev_basis": basis,
            "trades_per_active_day": tpd if basis == "per_trade" else UNMEASURED}


def slippage_r(name: str, corpus: list[dict[str, Any]]) -> dict[str, Any]:
    base = name.rsplit("_v", 1)[0] if name.rsplit("_v", 1)[-1].isdigit() else name
    vals = [v for r in corpus if r.get("sleeve") in (name, base)
            and (v := _num(r.get("slip_r"))) is not None]
    if len(vals) < MIN_SLIP_N:
        return _um(f"{len(vals)} slip_r observation(s) in fill_corpus, need {MIN_SLIP_N}")
    return {"median_R": round(statistics.median(vals), 5), "n": len(vals)}


# ----------------------------------------------------------------------------- per sleeve
def audit_venue(item: dict[str, Any], surface: dict[str, Any] | None, meta: dict[str, Any],
                hours: dict[str, Any], stop: dict[str, Any], cert: dict[str, Any],
                slip: dict[str, Any], mins: dict[str, Any] | None = None) -> dict[str, Any]:
    sym = str(item.get("symbol") or "")
    out: dict[str, Any] = {}
    if surface is None:
        return _um("no spread surface for this venue on this clone")
    ssym = (surface.get("symbols") or {}).get(sym)
    if not isinstance(ssym, dict):
        return _um(f"{sym} absent from the venue's spread surface")
    if hours.get("status") == UNMEASURED:
        return _um("entry hours " + hours["why"])
    hrs = {int(h): int(n) for h, n in hours["hours"].items()}
    ts = _num(ssym.get("tick_size")) or _num(meta.get("tick_size"))
    out["spread_atr"] = spread_atr_ratio(ssym, hrs)
    if not ts:
        return {**out, **_um("no tick_size")}
    spread, why = spread_at(ssym, hrs, ts)
    if spread is None:
        return {**out, **_um(why)}
    comm = commission_price(meta)
    out["spread_price"] = round(spread, 6)
    zf = [_num(((ssym.get("hours") or {}).get(str(h)) or {}).get("zero_frac")) or 0.0 for h in hrs]
    suspect = max(zf) > SUSPECT_ZERO_FRAC
    if suspect:
        out["surface_suspect"] = (f"zero_frac {max(zf):.2f} > {SUSPECT_ZERO_FRAC} at entry hour: "
                                  "the p50 is read off a minority of non-zero bars")
    out["commission_price"] = round(comm, 6) if comm is not None else UNMEASURED
    stop_px = stop.get("price")
    if stop.get("status") == UNMEASURED or not stop_px:
        return {**out, **_um("stop distance " + stop.get("why", "unmeasured"))}
    if comm is None:
        return {**out, **_um("commission: no tick_value to convert it")}
    spread_r, comm_r = spread / stop_px, comm / stop_px
    floor = spread_r + comm_r
    slip_ok = slip.get("status") != UNMEASURED
    measured = floor + (max(0.0, float(slip["median_R"])) if slip_ok else 0.0)
    out["cost_R_measured"] = {"spread_R": round(spread_r, 5), "commission_R": round(comm_r, 5),
                              "slippage_R": slip.get("median_R") if slip_ok else UNMEASURED,
                              "total_R": round(measured, 5),
                              "kind": "TOTAL" if slip_ok else "FLOOR (slippage UNMEASURED)"}
    if mins is None or mins.get("status") == UNMEASURED:
        minute: dict[str, Any] = {"status": UNMEASURED_MINUTE,
                                  "why": "entry minute " + (mins or {}).get("why", "unknown")}
    else:
        minute = minute_spread_pts(ssym, mins["fills"])
    if "spread_pts" in minute:
        extra = max(0.0, minute["spread_pts"] * ts - spread) / stop_px
        minute = {**minute, "spread_pts": round(minute["spread_pts"], 4)}
        out["cost_R_minute"] = round(measured + extra, 5)
    elif minute.get("status") == "NO_MARKET_FILLS":
        out["cost_R_minute"] = round(measured, 5)
    else:
        out["cost_R_minute"] = UNMEASURED_MINUTE
    out["minute"] = minute
    out["net_R_minute"] = UNMEASURED_MINUTE
    if cert.get("status") == UNMEASURED:
        out["cost_R_charged"] = _um(cert["why"])
        out["gross_edge_R"] = out["net_edge_R"] = UNMEASURED
        out["flags"] = ["SURFACE_SUSPECT"] if suspect else []
        return out
    charged = BASELINE_CROSSINGS * cert["one_crossing_R"] + comm_r
    gross = cert["ev_R"] + charged
    net = gross - measured
    out["cost_R_charged"] = round(charged, 5)
    exact = cert.get("ev_basis") == "per_trade"
    out["ev_basis"] = cert.get("ev_basis")
    out["gap"] = {"measured_minus_charged_R": round(measured - charged, 5) if exact
                  else UNMEASURED_BASIS,
                  "measured_over_charged": (round(measured / charged, 3) if charged > 0 else None)
                  if exact else UNMEASURED_BASIS}
    out["gross_edge_R"] = round(gross, 5)
    out["net_edge_R"] = round(net, 5)
    flags = []
    if net <= 0:
        flags.append("COST_EATS_EDGE")
    # COST_EATS_EDGE survives a per-day basis (k trades a day scale gross and cost alike, so the
    # sign of net is unchanged); UNDERCHARGED is only called on an exact per-trade basis.
    if exact and charged > 0 and measured > charged * (1.0 + UNDERCHARGE_TOL):
        flags.append("UNDERCHARGED")
    if suspect:
        flags.append("SURFACE_SUSPECT")
    if isinstance(out["cost_R_minute"], float):
        net_m = gross - out["cost_R_minute"]
        out["net_R_minute"] = round(net_m, 5)
        if net > 0 >= net_m:
            flags.append("FLIPS_AT_MINUTE")
    out["flags"] = flags
    return out


def stop_distance(item: dict[str, Any], entries: list[dict[str, Any]], cert: dict[str, Any],
                  meta: dict[str, Any], fusion_sym: dict[str, Any] | None) -> dict[str, Any]:
    dists = [abs(float(r["entry_price"]) - float(r["sl"])) for r in entries]
    if dists:
        return {"price": statistics.median(dists), "source": "live_ledger |entry - sl|",
                "n": len(dists)}
    med, ts = _num(meta.get("median_spread_pts")), _num(meta.get("tick_size"))
    if cert.get("status") != UNMEASURED and med and ts:
        return {"price": med * ts / cert["one_crossing_R"],
                "source": "cert-implied: one registry-median spread crossing / (ev - exp_x3)"}
    spec = item.get("spec") or {}
    k, atr = _num(spec.get("stop_atr")), _num((fusion_sym or {}).get("atr20_h1"))
    if k and atr and str(spec.get("timeframe") or "H1") == "H1":
        return {"price": k * atr, "source": "spec stop_atr x H1 ATR20"}
    return _um("no live entries, no recoverable certificate charge, no H1 stop_atr spec")


def sm1_rows() -> dict[str, dict[str, Any]]:
    """SM1 rows by certificate key (its per-cell lists: `rows` when present, else `top10_gt0`)."""
    out: dict[str, dict[str, Any]] = {}
    for path in (SM1_LOCAL, SM1):
        doc = _load(path)
        if not isinstance(doc, dict):
            continue
        for key in ("rows", "top10_gt0"):
            for r in doc.get(key) or []:
                if isinstance(r, dict) and r.get("cell"):
                    out.setdefault(str(r["cell"]), {**r, "sm1_file": str(path)})
    return out


def apply_minute_authority(row: dict[str, Any], sm1: dict[str, dict[str, Any]]) -> None:
    """SM1 wins where the sleeve's spec is a covered certificate key. Otherwise LIVE/STANDBY rows
    keep this module's own minute pricing, flagged not_in_sm1; certified-only rows outside SM1
    are UNMEASURED_MINUTE (the sweep, not this report, prices certificates)."""
    f = row["venues"]["fusion"]
    hit = sm1.get(str(row.get("cell") or ""))
    if hit is not None:
        exp_reg, exp_m = _num(hit.get("exp_registry")), _num(hit.get("exp_fill_minute"))
        row["minute_source"] = "sm1"
        f["minute"] = {k: hit.get(k) for k in ("spike_share", "spike_minutes",
                                               "spread_fill_weighted", "exp_registry",
                                               "exp_fill_minute")}
        f["net_R_minute"] = exp_m if exp_m is not None else UNMEASURED_MINUTE
        f["cost_R_minute"] = "see sm1 (exp_fill_minute is net per-trade R)"
        flags = [x for x in f.get("flags", []) if x != "FLIPS_AT_MINUTE"]
        if exp_reg is not None and exp_m is not None and exp_reg > 0 >= exp_m:
            flags.append("FLIPS_AT_MINUTE")
        f["flags"] = flags
    elif row["status"] in ("LIVE", "STANDBY"):
        row["minute_source"] = "self"
        row["not_in_sm1"] = True
    else:
        row["minute_source"] = None
        f["cost_R_minute"] = f["net_R_minute"] = UNMEASURED_MINUTE
        f["minute"] = {"status": UNMEASURED_MINUTE, "why": "certificate key outside SM1 coverage"}
        f["flags"] = [x for x in f.get("flags", []) if x != "FLIPS_AT_MINUTE"]
    row["flags"] = sorted({x for v in row["venues"].values() for x in v.get("flags", [])})


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sleeves, survivors = _load(SLEEVES), _load(SURVIVORS)
    universe = _load(UNIVERSE) or {}
    uni = universe.get("symbols", universe) if isinstance(universe, dict) else {}
    surfaces: dict[str, Any] = {"fusion": _load(SURFACE)}
    for v in VENUES[1:]:
        surfaces[v] = _load(DATA / f"cost_surface_{v}.json")
    ledger, corpus = _jsonl(LEDGER), _jsonl(CORPUS)
    surv = (survivors or {}).get("survivors") if isinstance(survivors, dict) else {}
    sm1 = sm1_rows()
    rows = []
    for item in population(sleeves, survivors):
        sym = str(item.get("symbol") or "")
        raw = uni.get(sym) if isinstance(uni, dict) else None
        meta: dict[str, Any] = raw if isinstance(raw, dict) else {}
        entries = ledger_entries(str(item["name"]), ledger)
        cert = cert_terms((surv or {}).get(item["cell"]) if item.get("cell") else None)
        fus = ((surfaces["fusion"] or {}).get("symbols") or {}).get(sym)
        hours = entry_hours(item, entries)
        mins = entry_minutes(item, entries)
        stop = stop_distance(item, entries, cert, meta, fus)
        slip = slippage_r(str(item["name"]), corpus)
        venues = {v: audit_venue(item, surfaces[v], meta, hours, stop, cert, slip, mins)
                  for v in VENUES}
        rows.append({"sleeve": item["name"], "status": item["status"], "symbol": sym,
                     "session": item.get("session"), "cell": item.get("cell"),
                     "entry_hours_broker": hours, "stop": stop, "certificate": cert,
                     "slippage": slip, "venues": venues,
                     "flags": sorted({f for v in venues.values() for f in v.get("flags", [])})})
    for r in rows:
        apply_minute_authority(r, sm1)
    fusion_rows = [r["venues"]["fusion"] for r in rows]
    summary = {
        "n_sleeves": len(rows),
        "cost_eats_edge": [r["sleeve"] for r in rows if "COST_EATS_EDGE" in r["flags"]],
        "undercharged": [r["sleeve"] for r in rows if "UNDERCHARGED" in r["flags"]],
        "surface_suspect": [r["sleeve"] for r in rows if "SURFACE_SUSPECT" in r["flags"]],
        "flips_at_minute": [r["sleeve"] for r in rows if "FLIPS_AT_MINUTE" in r["flags"]],
        "n_minute_from_sm1": sum(1 for r in rows if r.get("minute_source") == "sm1"),
        "not_in_sm1": [r["sleeve"] for r in rows if r.get("not_in_sm1")],
        "n_minute_unmeasured": sum(1 for v in fusion_rows
                                   if v.get("cost_R_minute") == UNMEASURED_MINUTE),
        "n_fusion_measured": sum(1 for v in fusion_rows if "cost_R_measured" in v),
        "n_fusion_net_edge_measured": sum(1 for v in fusion_rows
                                          if isinstance(v.get("net_edge_R"), float)),
        "venues_unmeasured": [v for v in VENUES if surfaces[v] is None],
    }
    um: dict[str, int] = {}
    for r in rows:
        f = r["venues"]["fusion"]
        charged = f.get("cost_R_charged")
        why = f.get("why") or (charged.get("why") if isinstance(charged, dict) else None)
        if why:
            um[why] = um.get(why, 0) + 1
    summary["fusion_unmeasured_reasons"] = um
    return {"schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"),
            "report_only": True, "consumer": None,
            "intended_consumer": "allocator / vol-target arm (idea 531/415)",
            "idea": 656, "status": "OK" if rows else "NO_SLEEVES",
            "tolerances": {"undercharged_if_measured_over_charged_gt": 1.0 + UNDERCHARGE_TOL},
            "n_fusion_net_edge_measured": summary["n_fusion_net_edge_measured"],
            # For the CRO: LIVE sleeves whose edge is positive at the hour and gone at the minute.
            "live_flips": [r["sleeve"] for r in rows
                           if r["status"] == "LIVE" and "FLIPS_AT_MINUTE" in r["flags"]],
            "summary": summary, "sleeves": rows}


def write(doc: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-sleeve round-trip cost in R (idea 656)")
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = build()
    write(doc)
    s = doc["summary"]
    print(f"sleeve_cost_in_r: {doc['status']} sleeves={s['n_sleeves']} "
          f"eats_edge={len(s['cost_eats_edge'])} undercharged={len(s['undercharged'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
