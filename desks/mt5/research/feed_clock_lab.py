"""THE FEED/CLOCK LAB -- the observatory and the impact lab, on the desk's own tape and fills.

TWO PARTS, ONE ORGAN, TWO CLOCKS (hourly_cycle legs `feed_clock_lab` and `impact_lab`, both in
the execution department, both 600 s):

  --part observatory   FEED HEALTH per instrument from the tick tape (libs/research/
                       feed_observatory): receipt latency (recv_utc vs the venue's time_msc,
                       negatives kept), stamp continuity, staleness probability from the feed's
                       own in-session gaps, the drop PROXY (MT5 carries no sequence numbers,
                       and the report says so), reference consistency against the H1 bars at
                       every whole-hour lag (the best lag IS the venue's clock offset), then
                       P(observed market is trustworthy | all feeds) stamped into
                       data/feed_health.json; the causally admissible propagation graph over the
                       sleeves' instruments; and the TIMING-CORRUPTION test on every LIVE and
                       STANDBY sleeve's recent signals at the instrument's MEASURED noise --
                       a sleeve whose edge halves is TIMING_FRAGILE, recorded in the registry
                       and published as a candidate_prior the compiler already reads.
  --part impact        THE EXECUTION / MARKET-IMPACT LAB (libs/research/impact_lab) from the
                       desk's own fill corpus, order intents, live ledger and the gateway's
                       retcode lines, joined to the tape at the order's own second: spread by
                       session, fill probability, rejection behaviour, slippage by order type,
                       partial fills, stop behaviour, Kyle-lambda impact with a permutation
                       null split permanent/transient, the queue/latency effect, session cost
                       curves and the toxicity STATE; execution cells recorded as discoveries
                       and execution-conditioned candidate seeds donated to the compiler in the
                       seat shape it reads.

WHAT IT REUSES AND NEVER DUPLICATES. `latency_lab` owns the act clock (its published threshold
is read here, not re-derived) and the JSON/JSONL helpers; the tape day naming rule is
`moat_series.tape_index`'s (both conventions, larger file wins) re-stated for a caller-supplied
root so tests can plant a tape; `scalp_family_expansion` rebuilds the scalp sleeves' exact
signals; every other sleeve's signals are its own shadow ledger (reports/shadow/ledger_*.json).
`cost_surface.json` is the bar-based spread reference the tape spreads are checked against.

WHAT IT REFUSES. It sizes nothing and vetoes nothing. Feed health is an INPUT: the roster
stamps it on every admitted sleeve (mt5desk/decision_core.load_sleeves_verbose) for entry
timing to read, and a low reading never removes a sleeve (GROWTH_GOVERNANCE Rule 1). A fragile
sleeve is a research finding routed through the candidate_prior channel, never a size change.

UNMEASURED IS A VALUE (L1.28a). On the box the tape's freshest day may be days old: every
feed then reads CLOSED with the freshest day named, the market number is UNMEASURED, and the
consumers see exactly that rather than a stale probability wearing a fresh timestamp.

    python desks/mt5/research/feed_clock_lab.py --part all --dry-run
    python desks/mt5/research/feed_clock_lab.py --part observatory --budget-s 600
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import latency_lab as ll  # noqa: E402

from libs.research import feed_observatory as fo  # noqa: E402
from libs.research import impact_lab as il  # noqa: E402

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
GENERATOR = "feed_clock_lab"
SOURCE_TYPE = "feed_clock_lab"
FEED_HEALTH = DESK / "data" / "feed_health.json"
OUT_FEED = DESK / "reports" / "FEED_CLOCK_LAB.json"
OUT_IMPACT = DESK / "reports" / "IMPACT_LAB.json"
DONATE_DIR = DESK / "data" / "intelligence" / "feed_clock_lab"
#: Rows read from the tail of each tape day; the trading box has 8 GB (re-measured 2026-09-15).
MAX_TAPE_ROWS = 60_000
#: Bars used for the reference check: the last two weeks of H1 is plenty to fit a whole-hour lag.
REF_BARS = 400
#: The reference tolerance: a tape mid and a bar close of the same instant within this agree.
REF_TOL_BPS = 5.0
#: Candidate venue-vs-UTC offsets, whole hours (Fusion runs UTC+2/+3; measured, never assumed).
REF_LAGS_H: tuple[int, ...] = (-4, -3, -2, -1, 0, 1, 2, 3, 4)
#: Impact horizons on the venue's own stamps.
SHORT_MS = 5_000
LONG_MS = 300_000
#: Fragility draws per multiplier (64 x 3 x ~70 sleeves is seconds, not minutes).
DRAWS = 64
#: Lags the propagation graph is judged at: the latency lab's own grid, reused.
GRAPH_LAGS_MS: tuple[int, ...] = ll.TAUS_MS
#: MT5 retcodes the gateway log carries, named so a census reads as words.
RETCODES: dict[str, str] = {"10009": "done", "10008": "placed", "10004": "requote",
                            "10006": "rejected", "10015": "invalid_price",
                            "10016": "invalid_stops", "10018": "market_closed",
                            "10019": "no_money", "10021": "price_off", "10027": "autotrading_off",
                            "10030": "invalid_fill", "10031": "no_connection"}
INPUT_NOT_CAP = ("feed health is an INPUT for entry timing and research routing; it is never a"
                 " cap, a veto or a shrink (GROWTH_GOVERNANCE Rule 1)")
CONSUMERS: tuple[str, ...] = (
    "mt5desk/decision_core.load_sleeves_verbose stamps data/feed_health.json onto every admitted"
    " sleeve row as `feed_health` (input, never a filter)",
    "this organ's own timing-fragility test takes each instrument's measured noise from it",
    "libs/moat/registry candidate_prior `prior:timing_fragile` (the channel the compiler reads)",
    "reports/FEED_CLOCK_LAB.json for the issue board and the dashboards",
)
DEBT = ("roster() rebuilds each emitted sleeve with named keys and the gateway's entry-timing"
        " branch does not yet read `feed_health` off the row: carrying the stamp through"
        " roster() and reading it at entry is the named debt (a capital-path edit, principal"
        " visibility)")


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _f(value: Any) -> float | None:
    return ll._f(value)


# ------------------------------------------------------------------------------------ tape
_DAY_RE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})$")


def tape_days(root: Path) -> dict[str, dict[str, Path]]:
    """{SYMBOL: {YYYY-MM-DD: path}} under `root`; both naming conventions, larger file wins --
    `moat_series.tape_index`'s rule, restated for a caller-supplied root."""
    out: dict[str, dict[str, Path]] = {}
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        days: dict[str, Path] = {}
        for f in d.glob("*.parquet"):
            m = _DAY_RE.match(f.stem)
            if m is None:
                continue
            key = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            try:
                if key in days and f.stat().st_size <= days[key].stat().st_size:
                    continue
            except OSError:
                continue
            days[key] = f
        if days:
            out[d.name] = days
    return out


def read_tape(path: Path, *, max_rows: int = MAX_TAPE_ROWS) -> dict[str, np.ndarray] | None:
    """time_msc/bid/ask plus recv_ms and recv_mono WHERE THE WRITER CARRIED THEM. Sorted by the
    venue's stamp for the price columns; the receipt columns stay in arrival order so the
    local clock's own continuity can be judged. None on a file this box cannot read."""
    try:
        import pyarrow.parquet as pq
        names = set(pq.read_schema(path).names)
        cols = [c for c in ("time_msc", "bid", "ask", "recv_utc", "recv_mono") if c in names]
        if not {"time_msc", "bid", "ask"} <= set(cols):
            return None
        table = pq.read_table(path, columns=cols)
        if table.num_rows > max_rows:
            table = table.slice(table.num_rows - max_rows)
        frame = table.to_pandas()
    except Exception:
        return None
    ms = np.asarray(frame["time_msc"], dtype=float)
    bid = np.asarray(frame["bid"], dtype=float)
    ask = np.asarray(frame["ask"], dtype=float)
    ok = np.isfinite(ms) & (bid > 0) & (ask > 0) & (ask >= bid)
    out: dict[str, np.ndarray] = {"arrival_ms": ms[ok]}
    if "recv_utc" in frame.columns:
        try:
            import pandas as pd
            recv = pd.to_datetime(frame["recv_utc"], utc=True, errors="coerce")
            rm = recv.astype("int64").to_numpy(dtype=float) / 1e6
            rm[recv.isna().to_numpy()] = np.nan
            out["recv_ms"] = rm[ok]
        except Exception:
            pass
    if "recv_mono" in frame.columns:
        out["recv_mono"] = np.asarray(frame["recv_mono"], dtype=float)[ok]
    order = np.argsort(ms[ok], kind="stable")
    mid = (bid[ok] + ask[ok]) / 2.0
    out.update({"ms": ms[ok][order], "mid": mid[order],
                "spread_bps": ((ask[ok] - bid[ok]) / mid * 1e4)[order],
                "bad": np.array([int((~ok).sum())])})
    return (out["ms"].size >= 2 and out) or None


def sibling_receipt(path: Path, *, max_rows: int = MAX_TAPE_ROWS) -> dict[str, np.ndarray] | None:
    """The OTHER writer's file for the same day, read for its receipt clock only. The larger
    file wins the price columns (moat_series' rule) and is usually the `ts` writer, which
    carries no recv_utc -- so the receipt clock would read UNMEASURED on every instrument the
    recorder also covers. Measured on the box 2026-09-22: XAUUSD, both writers, one clock."""
    stem = path.stem
    alt = stem.replace("-", "") if "-" in stem else f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}"
    other = path.with_name(alt + path.suffix)
    if not other.exists() or other == path:
        return None
    tape = read_tape(other, max_rows=max_rows)
    return tape if tape is not None and tape.get("recv_ms") is not None else None


def minute_mids(tape: Mapping[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """(minute_end_ms, last mid in that minute): the reference series, one point per minute."""
    ms, mid = tape["ms"], tape["mid"]
    minute = (ms // 60_000).astype("int64")
    last = np.r_[np.where(np.diff(minute) != 0)[0], ms.size - 1]
    return (minute[last] + 1).astype(float) * 60_000.0, mid[last]


def _read_bars(base: Path, symbol: str, timeframe: str = "H1") -> Any:
    path = base / "data" / "universe" / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        return df.sort_index() if len(df) else None
    except Exception:
        return None


# ------------------------------------------------------------------------- the observatory
def observe_instrument(symbol: str, tape: Mapping[str, np.ndarray], bars: Any, now_ms: float
                       ) -> tuple[fo.FeedClock, dict[str, Any]]:
    """One instrument's clock and the row that explains it, from its latest tape day."""
    ms = tape["ms"]
    gaps = np.diff(ms)
    row: dict[str, Any] = {"instrument": symbol, "n_ticks": int(ms.size),
                           "bad_quotes_dropped": int(tape["bad"][0]),
                           "last_venue_stamp": datetime.fromtimestamp(
                               float(ms[-1]) / 1000.0, tz=UTC).isoformat(timespec="seconds")}
    # LOCAL RECEIPT vs EXCHANGE STAMP, per tick, negatives kept (latency_lab's rule). The
    # receipt columns may come from the sibling writer's file (`receipt_source`).
    recv = tape.get("recv_ms")
    arrival = tape["arrival_ms"]
    receipt_source = "same file"
    if (recv is None or not np.isfinite(recv).any()) and tape.get("sibling") is not None:
        sib = tape["sibling"]
        recv, arrival, receipt_source = sib["recv_ms"], sib["arrival_ms"], "sibling writer"
    if recv is not None and np.isfinite(recv).any():
        lat = fo.latency_distribution(arrival, recv)
        polls = np.unique(recv[np.isfinite(recv)])
        poll_ms = float(np.median(np.diff(polls))) if polls.size > 2 else None
        tol = max(1000.0, 2.0 * poll_ms) if poll_ms else 120_000.0
        delta = recv - arrival
        delta = delta[np.isfinite(delta)]
        # THE MEDIAN DELAY IS THE RECORDER'S OWN POLL OFFSET -- a constant the act clock
        # (latency_lab) already prices and `offset_ms` above reports. The receipt component
        # measures the EXCESS over it, the part the feed adds, against the poll cadence.
        # MEASURED 2026-09-22: judging the raw delay put a healthy 30 s poller at
        # p_within_tolerance 0 (every tick 15 poll-spacings late) and the whole feed at
        # P(trustworthy) = 0 -- a clock offset read as a dead feed.
        centred = delta - float(np.median(delta)) if delta.size else delta
        p_ok = float(np.mean(np.abs(centred) <= tol)) if delta.size else None
        row["receipt"] = {**lat, "poll_spacing_ms": poll_ms, "tolerance_ms": tol,
                          "p_within_tolerance": p_ok, "receipt_source": receipt_source,
                          "tolerance_basis": "|delay - median delay| <= max(1 s, 2 x poll"
                                             " spacing): the median is the recorder's poll"
                                             " offset (offset_ms), the excess is the feed's",
                          "basis": "tape recv_utc against the venue's time_msc on the same row;"
                                   " the RESEARCH recorder POLLS, so this is the feature"
                                   " staleness clock and not the gateway's read path"}
        local_cont = fo.sequence_continuity(recv)
    else:
        lat = {"status": UNMEASURED, "offset_ms": None, "jitter_ms": None}
        p_ok = None
        row["receipt"] = {"status": UNMEASURED,
                          "why": "this tape day carries no recv_utc: the local receipt clock"
                                 " is UNMEASURED for it (the other writer)"}
        local_cont = {"status": UNMEASURED}
    cont = fo.sequence_continuity(tape["arrival_ms"])
    burst = fo.burst_rate(gaps)
    repeats = float(np.mean(np.diff(tape["mid"]) == 0.0)) if ms.size > 1 else None
    closed_at = fo.closed_threshold_ms(gaps)
    age_ms = float(now_ms - ms[-1])
    in_session = closed_at is not None and age_ms <= closed_at
    stale = fo.staleness_probability(gaps, age_ms) if in_session else None
    row.update({"continuity_venue_stamp": cont, "continuity_local_receipt": local_cont,
                "silence_bursts": burst, "age_s": round(age_ms / 1000.0, 1),
                "closed_threshold_s": None if closed_at is None else round(closed_at / 1000, 1),
                "in_session": in_session, "stale_probability": stale,
                "repeat_rate": repeats, "gaps_ms": fo.quantiles(gaps)})
    # REFERENCE: tape mid at each bar's end against that bar's close, at whole-hour lags. The
    # lag with the smallest disagreement is the venue's clock offset, MEASURED.
    ref_ok: float | None = None
    if bars is not None and "close" in getattr(bars, "columns", ()):
        try:
            tail = bars.tail(REF_BARS)
            ends = tail.index.astype("int64").to_numpy(dtype=float) / 1e6 + 3_600_000.0
            ref_t, ref_mid = minute_mids(tape["full"] if tape.get("full") is not None else tape)
            ref = fo.reference_consistency(ends, tail["close"].to_numpy(dtype=float),
                                           ref_t, ref_mid,
                                           lags_ms=[h * 3_600_000.0 for h in REF_LAGS_H])
            row["reference"] = {**ref, "basis": "H1 close at bar end vs the tape's last mid of"
                                                " that minute, whole-day, inside the tape's"
                                                " span; best lag = venue clock offset"}
            if ref.get("status") == MEASURED:
                ref_ok = 1.0 - min(1.0, float(ref["median_abs_bps_at_best"]) / REF_TOL_BPS)
                row["reference"]["venue_offset_h"] = float(ref["best_lag_ms"]) / 3_600_000.0
        except Exception as exc:
            row["reference"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    else:
        row["reference"] = {"status": UNMEASURED, "why": "no H1 bars for this instrument"}
    why = "" if in_session else (f"CLOSED or recorder not current: last venue stamp is"
                                 f" {age_ms / 1000:.0f}s old against a closed threshold of"
                                 f" {(closed_at or 0) / 1000:.0f}s")
    clock = fo.FeedClock(
        instrument=symbol, n=int(ms.size), offset_ms=_f(lat.get("offset_ms")),
        jitter_ms=_f(lat.get("jitter_ms")),
        inversion_rate=_f(cont.get("inversion_rate")),
        drop_prob=_f(burst.get("rate")), stale_prob=stale, repeat_rate=repeats,
        p_latency_ok=p_ok,
        reference_ok=ref_ok, in_session=in_session, why=why)
    return clock, row


# ---------------------------------------------------------------------- sleeve signals
def _sleeves(base: Path) -> list[dict[str, Any]]:
    try:
        doc = json.loads((base / "data" / "sleeves.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return [r for r in (rows or []) if isinstance(r, dict)
            and r.get("status") in ("LIVE", "STANDBY")]


def _forward_returns(bars: Any, horizon: int) -> tuple[np.ndarray, np.ndarray] | None:
    """(bar_end_ms, close-to-close return over `horizon` bars from that close)."""
    if bars is None or "close" not in bars.columns or len(bars) <= horizon + 1:
        return None
    close = bars["close"].to_numpy(dtype=float)
    step = 0.0
    if len(bars.index) > 1:
        step = float(np.median(np.diff(bars.index.astype("int64").to_numpy(dtype=float)))) / 1e6
    ends = bars.index.astype("int64").to_numpy(dtype=float) / 1e6 + step
    fwd = close[horizon:] / close[:-horizon] - 1.0
    return ends[:-horizon], fwd


def scalp_signal(base: Path, sleeve: Mapping[str, Any]
                 ) -> tuple[list[tuple[float, float]], list[tuple[float, float]], str]:
    """The scalp lane's exact signals, rebuilt by the module that runs its forward clock."""
    tf = str(sleeve.get("timeframe") or "M5")
    bars = _read_bars(base, str(sleeve.get("symbol") or "XAUUSD"), tf)
    if bars is None:
        return [], [], f"no {tf} bars for {sleeve.get('symbol')}"
    try:
        from desks.mt5.research import scalp_family_expansion as families
        signals = families._base_signals(bars)[str(sleeve.get("family"))].astype(float).copy()
        signals[~families._session_mask(bars.index, str(sleeve.get("session") or "all"))] = 0.0
    except Exception as exc:
        return [], [], f"scalp family rebuild failed: {type(exc).__name__}: {exc}"
    hold = max(1, int(sleeve.get("max_hold") or 6))
    fr = _forward_returns(bars, hold)
    if fr is None:
        return [], [], "too few bars for the sleeve's horizon"
    ends, fwd = fr
    sig = [(float(t), float(s)) for t, s in zip(ends, signals[:ends.size], strict=False)
           if s != 0.0]
    return sig, list(zip(ends.tolist(), fwd.tolist(), strict=True)), (
        f"scalp_family_expansion._base_signals on {tf} bars, {len(sig)} signal bar(s)")


def ledger_signal(base: Path, sleeve: Mapping[str, Any]
                  ) -> tuple[list[tuple[float, float]], list[tuple[float, float]], str]:
    """Every other sleeve: its own shadow ledger's entries as the signal, H1 forward returns
    over the sleeve's median holding as the target."""
    symbol = str(sleeve.get("symbol") or "")
    if sleeve.get("window"):
        name = f"ledger_{symbol}_{sleeve['window']}.json"
    else:
        name = f"ledger_{symbol}_{sleeve.get('family')}_{sleeve.get('selector') or 'all'}.json"
    path = base / "reports" / "shadow" / name
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], [], f"no shadow ledger {name}"
    if not isinstance(records, list):
        return [], [], f"{name} is not a record list"
    sig: list[tuple[float, float]] = []
    holds: list[float] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        t = ll._epoch_ms(r.get("entry_time"))
        side = _f(r.get("side"))
        if t is None or side is None or side == 0:
            continue
        sig.append((t, float(np.sign(side))))
        x = ll._epoch_ms(r.get("exit_time"))
        if x is not None and x > t:
            holds.append((x - t) / 3_600_000.0)
    hold = int(min(48, max(1, round(float(np.median(holds))) if holds else 1)))
    fr = _forward_returns(_read_bars(base, symbol), hold)
    if fr is None:
        return sig, [], f"no H1 bars for {symbol}"
    ends, fwd = fr
    return sig, list(zip(ends.tolist(), fwd.tolist(), strict=True)), (
        f"shadow ledger {name}: {len(sig)} entr(ies), H1 forward return over {hold} bar(s)")


def fragility_pass(base: Path, sleeves: Sequence[Mapping[str, Any]],
                   clocks: Mapping[str, fo.FeedClock], *, deadline: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in sleeves:
        row: dict[str, Any] = {"sleeve": s.get("name"), "symbol": s.get("symbol"),
                               "status": s.get("status"), "family": s.get("family"),
                               "exec": s.get("exec") or ("gold_window" if s.get("window")
                                                         else "unknown")}
        if time.monotonic() > deadline:
            row.update({"verdict": UNMEASURED, "why": "budget exhausted before this sleeve"})
            out.append(row)
            continue
        clock = clocks.get(str(s.get("symbol") or ""))
        if clock is None:
            row.update({"verdict": UNMEASURED,
                        "why": f"no measured feed clock for {s.get('symbol')} this pass"})
            out.append(row)
            continue
        noise = fo.noise_from_clock(clock)
        missing = [k for k, v in (("jitter", clock.jitter_ms), ("drops", clock.drop_prob),
                                  ("stale", clock.repeat_rate),
                                  ("inversions", clock.inversion_rate)) if v is None]
        basis = ("measured: jitter=p90-p50 receipt delay, drops=silence-burst proxy,"
                 " stale=repeated-quote rate, inversions=venue-stamp inversion rate"
                 + (f"; UNMEASURED and contributing nothing: {', '.join(missing)}"
                    if missing else ""))
        if s.get("exec") == "scalp_market":
            sig, tgt, how = scalp_signal(base, s)
        else:
            sig, tgt, how = ledger_signal(base, s)
        verdict = fo.timing_fragility(sig, tgt, noise, draws=DRAWS)
        row.update({"signal_source": how, "noise_basis": basis, **verdict})
        out.append(row)
    return out


# ------------------------------------------------------------------------- registry
def _record_fragility(rows: Sequence[Mapping[str, Any]], threshold_ms: Any, *, conn: Any,
                      dry_run: bool) -> dict[str, Any]:
    fragile = [r for r in rows if r.get("verdict") == "TIMING_FRAGILE"]
    payload = {"kind": "timing_fragile", "fragile_specs": [
        {"sleeve": r["sleeve"], "symbol": r["symbol"], "family": r.get("family"),
         "retained": r.get("retained_at_measured_noise")} for r in fragile],
        "survival_fraction": fo.SURVIVAL_FRACTION, "latency_threshold_ms": threshold_ms,
        "routes_not_sizes": ll.ROUTES_NOT_SIZES,
        "artifact": "desks/mt5/reports/FEED_CLOCK_LAB.json"}
    if dry_run:
        return {"status": "DRY_RUN", "discoveries": 0, "memories": 0, "payload": payload}
    try:
        from libs.moat import registry as R
        c = conn or R.connect()
        try:
            n_disc = 0
            for r in fragile:
                _did, new = R.record_discovery(
                    source_id=f"{SOURCE_TYPE}:timing_fragility:{r['sleeve']}",
                    source_type=SOURCE_TYPE, origin="DESK", generator=GENERATOR,
                    mechanism=(f"timing_fragility: {r['sleeve']} keeps"
                               f" {float(r.get('retained_at_measured_noise') or 0):.0%} of its"
                               " edge under the desk's measured timing noise"),
                    information="feed_clock", economic_rationale=INPUT_NOT_CAP,
                    assets=[r["symbol"]], exact_rule_if_known=json.dumps(
                        {"sleeve": r["sleeve"], "noise": r.get("noise")}, sort_keys=True),
                    required_data=["data/tape/ticks/<SYM>/<DAY>.parquet"],
                    pit_requirements=["tape"], falsifier=(
                        "the same sleeve re-measured on a later tape keeps the survival"
                        " fraction at the measured noise"),
                    payload=dict(r), conn=c)
                n_disc += int(new)
            n_mem = 0
            for r in rows:
                if r.get("verdict") in ("TIMING_FRAGILE", "TIMING_ROBUST"):
                    R.remember("feed_clock", (f"{r['sleeve']}: {r['verdict']} -- retained"
                                              f" {r.get('retained_at_measured_noise')} at measured"
                                              f" noise, margin {r.get('margin_multiplier')}x"),
                               kind="timing_fragility",
                               memory_key=f"timing_fragility:{r['sleeve']}",
                               result="success" if r["verdict"] == "TIMING_ROBUST" else "failure",
                               metrics={"retained": r.get("retained_at_measured_noise"),
                                        "margin": r.get("margin_multiplier")},
                               payload=dict(r), conn=c)
                    n_mem += 1
            R.remember("candidate_prior",
                       (f"timing_fragile: {len(fragile)} sleeve spec(s) lose more than"
                        f" {1 - fo.SURVIVAL_FRACTION:.0%} of their edge under the desk's measured"
                        " timing noise; research routes around them, capital is untouched"),
                       kind="candidate_prior", memory_key="prior:timing_fragile",
                       result="success" if rows else "pending", payload=payload, conn=c)
            R.generator_yield_update(GENERATOR, generated=n_disc, compute_s=0.0, conn=c)
            return {"status": "OK", "discoveries": n_disc, "memories": n_mem,
                    "memory_key": "prior:timing_fragile", "payload": payload}
        finally:
            if conn is None:
                c.close()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}", "payload": payload}


def _record_cells(cells: Sequence[Mapping[str, Any]], *, conn: Any, dry_run: bool
                  ) -> dict[str, Any]:
    measured = [c for c in cells if c.get("status") == MEASURED]
    if dry_run:
        return {"status": "DRY_RUN", "discoveries": 0, "measured_cells": len(measured)}
    try:
        from libs.moat import registry as R
        c = conn or R.connect()
        try:
            n = 0
            for cell in measured:
                _did, new = R.record_discovery(
                    source_id=f"{SOURCE_TYPE}:execution_cell:{cell['instrument']}:"
                              f"{cell['session']}",
                    source_type=SOURCE_TYPE, origin="DESK", generator=GENERATOR,
                    mechanism=(f"execution_cell: {cell['instrument']} {cell['session']} --"
                               f" p_fill {cell.get('p_fill')}, toxicity"
                               f" {cell['toxicity'].get('state')}"),
                    information="execution_microstructure", economic_rationale=INPUT_NOT_CAP,
                    assets=[cell["instrument"]], sessions=[cell["session"]],
                    exact_rule_if_known=json.dumps({"instrument": cell["instrument"],
                                                    "session": cell["session"]}, sort_keys=True),
                    required_data=["data/fill_corpus.jsonl", "data/order_intents.jsonl",
                                   "data/tape/ticks/<SYM>/<DAY>.parquet"],
                    pit_requirements=["own fills", "tape"],
                    falsifier="the cell's fill rate or toxicity state changes on later fills",
                    payload=dict(cell), conn=c)
                n += int(new)
            R.generator_yield_update(GENERATOR, generated=n, compute_s=0.0, conn=c)
            return {"status": "OK", "discoveries": n, "measured_cells": len(measured)}
        finally:
            if conn is None:
                c.close()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}


# -------------------------------------------------------------------------- the impact lab
def _side(value: Any) -> int:
    s = str(value or "").lower()
    if s in ("buy", "long", "1", "+1"):
        return 1
    if s in ("sell", "short", "-1"):
        return -1
    return 0


def _corpus_orders(rows: Sequence[Mapping[str, Any]]) -> list[il.OrderRecord]:
    out: list[il.OrderRecord] = []
    for r in rows:
        t = ll._epoch_ms(r.get("sent_at") or r.get("decided_at"))
        if t is None or not r.get("symbol"):
            continue
        hour = int(datetime.fromtimestamp(t / 1000.0, tz=UTC).hour)
        status = str(r.get("status") or "")
        out.append(il.OrderRecord(
            instrument=str(r["symbol"]), t_ms=t, side=_side(r.get("side")),
            lots=float(_f(r.get("lots")) or 0.0), order_type=str(r.get("order_type") or "unknown"),
            session=il.session_of_hour(hour), requested=_f(r.get("requested_price")),
            fill_price=_f(r.get("fill_price")), filled_frac=_f(r.get("filled_frac")),
            rejected=bool(r.get("rejected")) or status == "REJECTED",
            reject_reason=str(r.get("reject_reason") or ""),
            latency_ms=_f(r.get("latency_decision_to_send_ms")),
            done=True if status == "FILLED" else (False if status in ("UNFILLED", "REJECTED")
                                                  else None)))
    return out


def _intent_orders(rows: Sequence[Mapping[str, Any]]) -> list[il.OrderRecord]:
    out: list[il.OrderRecord] = []
    for r in rows:
        t = ll._epoch_ms(r.get("time"))
        if t is None or not r.get("symbol"):
            continue
        code = r.get("retcode")
        hour = int(datetime.fromtimestamp(t / 1000.0, tz=UTC).hour)
        policy = ((r.get("policy_advice") or {}).get("policy") if isinstance(
            r.get("policy_advice"), dict) else None)
        out.append(il.OrderRecord(
            instrument=str(r["symbol"]), t_ms=t, side=_side(r.get("side")),
            lots=float(_f(r.get("lot")) or 0.0),
            order_type=str(policy or "market").lower(), session=il.session_of_hour(hour),
            requested=_f(r.get("intended")), rejected=code not in (10009, 10008),
            reject_reason="" if code in (10009, 10008) else RETCODES.get(str(code), "no_result"),
            latency_ms=_f(r.get("latency_ms")), done=code in (10009, 10008)))
    return out


def _ledger_orders(rows: Sequence[Mapping[str, Any]]) -> list[il.OrderRecord]:
    """Closed deals as FLOW events. The direction comes from the bracket's geometry (tp below
    entry is a short), never from the ambiguous `side` code; the close's flow is its negative."""
    out: list[il.OrderRecord] = []
    for r in rows:
        t = ll._epoch_ms(r.get("time"))
        entry, tp, sl = _f(r.get("entry_price")), _f(r.get("tp")), _f(r.get("sl"))
        if t is None or not r.get("symbol") or entry is None:
            continue
        direction = 0
        if tp is not None and tp != entry:
            direction = 1 if tp > entry else -1
        elif sl is not None and sl != entry:
            direction = 1 if sl < entry else -1
        hour = int(datetime.fromtimestamp(t / 1000.0, tz=UTC).hour)
        out.append(il.OrderRecord(
            instrument=str(r["symbol"]), t_ms=t, side=-direction,
            lots=float(_f(r.get("volume")) or 0.0), order_type="close",
            session=il.session_of_hour(hour), fill_price=_f(r.get("fill_price")), done=True))
    return out


def _dedupe(orders: Sequence[il.OrderRecord]) -> list[il.OrderRecord]:
    seen: set[tuple[str, int, int, float]] = set()
    out: list[il.OrderRecord] = []
    for o in orders:
        key = (o.instrument, int(o.t_ms // 1000), o.side, round(o.lots, 4))
        if key in seen:
            continue
        seen.add(key)
        out.append(o)
    return out


def _join_tape(orders: Sequence[il.OrderRecord], days: Mapping[str, Mapping[str, Path]],
               cache: dict[tuple[str, str], dict[str, np.ndarray] | None], *, deadline: float
               ) -> tuple[list[il.OrderRecord], dict[str, int]]:
    joined: list[il.OrderRecord] = []
    stats = {"joined": 0, "no_tape_day": 0, "budget": 0}
    for o in orders:
        if time.monotonic() > deadline:
            stats["budget"] += 1
            joined.append(o)
            continue
        day = datetime.fromtimestamp(o.t_ms / 1000.0, tz=UTC).strftime("%Y-%m-%d")
        path = (days.get(o.instrument) or {}).get(day)
        if path is None:
            stats["no_tape_day"] += 1
            joined.append(o)
            continue
        key = (o.instrument, day)
        if key not in cache:
            cache[key] = read_tape(path, max_rows=400_000)
        tape = cache[key]
        if tape is None:
            stats["no_tape_day"] += 1
            joined.append(o)
            continue
        ms, mid = tape["ms"], tape["mid"]
        i0 = int(np.searchsorted(ms, o.t_ms, side="right")) - 1
        i1 = int(np.searchsorted(ms, o.t_ms + SHORT_MS, side="left"))
        i2 = int(np.searchsorted(ms, o.t_ms + LONG_MS, side="left"))
        before = float(mid[i0]) if i0 >= 0 else None
        short = float(mid[i1]) if i1 < ms.size else None
        long_ = float(mid[i2]) if i2 < ms.size else None
        spread = float(tape["spread_bps"][i0]) if i0 >= 0 else None
        joined.append(il.OrderRecord(**{**o.__dict__, "mid_before": before, "mid_short": short,
                                        "mid_long": long_, "spread_bps": spread}))
        stats["joined"] += int(before is not None)
    return joined, stats


def _log_retcodes(base: Path, *, max_lines: int = 5000) -> dict[str, Any]:
    path = base / "logs" / "gateway.log"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return {"status": UNMEASURED, "why": f"{path.name} not on this box"}
    counts: dict[str, int] = {}
    for line in lines:
        for code in re.findall(r"retcode=(\d+)", line):
            counts[code] = counts.get(code, 0) + 1
    named = {f"{code} {RETCODES.get(code, 'other')}": n
             for code, n in sorted(counts.items(), key=lambda kv: -kv[1])}
    total = sum(counts.values())
    return {"status": MEASURED if total else UNMEASURED, "lines_read": len(lines),
            "retcodes": named, "n": total,
            "reject_share": None if not total else round(
                1 - (counts.get("10009", 0) + counts.get("10008", 0)) / total, 4)}


def donate_seeds(cells: Sequence[Mapping[str, Any]], sleeves: Sequence[Mapping[str, Any]],
                 cost_curves: Mapping[str, Mapping[str, Mapping[str, Any]]]
                 ) -> list[dict[str, Any]]:
    """Execution-conditioned candidate seeds in the seat shape the compiler reads: a sleeve's
    price-only family on its instrument, conditioned on the session where the desk's measured
    cost is lowest. A family outside the compiler's price-only vocabulary rides as prose and
    becomes a deepening task rather than nothing."""
    try:
        from miner_candidate_compiler import _FAMILY_VOCAB as vocab
    except Exception:
        vocab = {}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for s in sleeves:
        sym, fam = str(s.get("symbol") or ""), str(s.get("family") or "")
        curve = cost_curves.get(sym) or {}
        priced = {k: v for k, v in curve.items() if v.get("cost_bps") is not None}
        if not sym or not priced:
            continue
        best = min(priced.items(), key=lambda kv: float(kv[1]["cost_bps"]))
        session, cost = best[0], float(best[1]["cost_bps"])
        tox = next((c["toxicity"].get("state") for c in cells
                    if c["instrument"] == sym and c["session"] == session), UNMEASURED)
        key = (sym, fam, session)
        if key in seen:
            continue
        seen.add(key)
        sess_word = {"new_york": "new york", "late": "late session"}.get(session, session)
        out.append({"source": GENERATOR, "kind": "hypothesis" if fam in vocab else "execution_cell",
                    "family": fam or None, "symbols": [sym],
                    "title": f"{fam or 'execution cell'} on {sym} in the {sess_word} session",
                    "mechanism": (f"execution-conditioned seed: the desk's own measured cost on"
                                  f" {sym} is lowest in the {sess_word} session ({cost:.2f} bps"
                                  f" half-spread plus slippage), toxicity {tox}; the"
                                  f" {fam or 'cell'} edge is hypothesised to survive its costs"
                                  " there"),
                    "testable_claim": (f"{fam or 'the cell'} on {sym} entered only in the"
                                       f" {sess_word} session clears the ten gates net of the"
                                       f" measured {cost:.2f} bps"),
                    "session": session, "cost_bps": round(cost, 4), "toxicity": tox,
                    "url": f"feed_clock_lab://execution_cell/{sym}/{session}"})
    return out


# ----------------------------------------------------------------------------------- passes
def observatory_pass(*, base: Path, budget_s: float, dry_run: bool, now_ms: float | None = None,
                     conn: Any = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(5.0, budget_s * 0.7)
    now = float(now_ms if now_ms is not None else time.time() * 1000.0)
    days = tape_days(base / "data" / "tape" / "ticks")
    sleeves = _sleeves(base)
    priority = sorted({str(s.get("symbol")) for s in sleeves if s.get("symbol")})
    order = [s for s in priority if s in days] + sorted(k for k in days if k not in priority)
    clocks: dict[str, fo.FeedClock] = {}
    rows: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    freshest = ""
    for sym in order:
        if time.monotonic() > deadline:
            skipped.append(sym)
            continue
        day, path = max(days[sym].items())
        freshest = max(freshest, day)
        tape = read_tape(path)
        if tape is None:
            rows[sym] = {"instrument": sym, "status": UNMEASURED, "day": day,
                         "why": "tape day unreadable or under two usable quotes"}
            continue
        if tape.get("recv_ms") is None:
            sib = sibling_receipt(path)
            if sib is not None:
                tape = {**tape, "sibling": sib}
        full = read_tape(path, max_rows=400_000)
        if full is not None:
            tape = {**tape, "full": full}
        clock, row = observe_instrument(sym, tape, _read_bars(base, sym), now)
        clocks[sym] = clock
        rows[sym] = {**row, "day": day}
    health = fo.feed_health(now, clocks)
    graph_nodes = {k: v for k, v in clocks.items() if k in priority}
    graph = fo.propagation_graph(graph_nodes, GRAPH_LAGS_MS)
    fragility = fragility_pass(base, sleeves, clocks, deadline=t0 + max(5.0, budget_s * 0.95))
    threshold = None
    try:
        lat_doc = json.loads((base / "reports" / "LATENCY_LAB.json").read_text(encoding="utf-8"))
        threshold = (lat_doc.get("threshold") or {}).get("ms")
    except (OSError, ValueError):
        pass
    recorded = _record_fragility(fragility, threshold, conn=conn, dry_run=dry_run)
    stamp: dict[str, Any] = {
        "at": now_iso(), "generated_by": "desks/mt5/research/feed_clock_lab.py --part"
                                         " observatory", "rule": fo.HEALTH_RULE,
        "input_not_cap": INPUT_NOT_CAP, "consumers": list(CONSUMERS), "debt": DEBT,
        "status": health["status"], "p_market_trustworthy": health["p_market_trustworthy"],
        "worst_feed": health["worst_feed"], "n_feeds": health["n_feeds"],
        "n_in_session": health["n_in_session"], "n_closed": health["n_closed"],
        "n_unmeasured": health["n_unmeasured"], "tape_freshest_day": freshest or None,
        "recorder_current": bool(health["n_in_session"]),
        "instruments": {sym: {"status": v["status"], "p_trustworthy": v["p_trustworthy"],
                              "components": v["components"], "why": v["why"],
                              "age_s": rows.get(sym, {}).get("age_s"),
                              "in_session": rows.get(sym, {}).get("in_session")}
                        for sym, v in health["feeds"].items()},
    }
    doc: dict[str, Any] = {
        "at": now_iso(), "part": "observatory", "dry_run": bool(dry_run),
        "elapsed_s": round(time.monotonic() - t0, 2), "budget_s": budget_s,
        "n_tape_instruments": len(days), "n_observed": len(clocks), "skipped_for_budget": skipped,
        "tape_freshest_day": freshest or None,
        "clocks": {"source_event": "UNMEASURED on MT5: the broker does not forward the LP's"
                                   " event time", "exchange": "time_msc (the venue's own stamp)",
                   "vendor_receipt": "UNMEASURED: the terminal stamps nothing on the way",
                   "local_receipt": "recv_utc (the research recorder's poll)",
                   "implied": "kept apart: libs.research.feed_observatory.implied_time"},
        "feed_health": {k: v for k, v in stamp.items() if k != "instruments"},
        "instruments": rows, "propagation_graph": {k: v for k, v in graph.items()
                                                    if k != "edges"},
        "propagation_edges_admissible": [e for e in graph["edges"] if e["admissible"]][:400],
        "timing_fragility": fragility,
        "fragility_summary": {v: sum(1 for r in fragility if r.get("verdict") == v)
                              for v in ("TIMING_FRAGILE", "TIMING_ROBUST", UNMEASURED)},
        "latency_lab_threshold_ms": threshold, "registry": recorded,
        "consumers": list(CONSUMERS), "debt": DEBT,
    }
    if not dry_run:
        ll._write_atomic(base / "data" / "feed_health.json", stamp)
        ll._write_atomic(base / "reports" / "FEED_CLOCK_LAB.json", doc)
    return doc


def impact_pass(*, base: Path, budget_s: float, dry_run: bool, conn: Any = None
                ) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(5.0, budget_s * 0.8)
    corpus = ll.read_jsonl(base / "data" / "fill_corpus.jsonl")
    intents = ll.read_jsonl(base / "data" / "order_intents.jsonl")
    ledger = ll.read_jsonl(base / "data" / "live_ledger.jsonl")
    sent = _dedupe([*_corpus_orders(corpus), *_intent_orders(intents)])
    closes = _ledger_orders(ledger)
    days = tape_days(base / "data" / "tape" / "ticks")
    cache: dict[tuple[str, str], dict[str, np.ndarray] | None] = {}
    sent, join_sent = _join_tape(sent, days, cache, deadline=deadline)
    closes, join_close = _join_tape(closes, days, cache, deadline=deadline)
    flows = [*sent, *closes]
    # SPREADS BY SESSION per instrument, from every tape day the join touched.
    spreads: dict[str, dict[str, dict[str, Any]]] = {}
    for (sym, _day), tape in cache.items():
        if tape is None:
            continue
        hours = ((tape["ms"] // 3_600_000) % 24).astype(int)
        got = il.spread_by_session(hours, tape["spread_bps"])
        cur = spreads.setdefault(sym, {})
        for sess, q in got.items():
            if q.get("status") != UNMEASURED and (cur.get(sess, {}).get("n", 0) < q["n"]):
                cur[sess] = q
    pooled_hours: list[int] = []
    pooled_spread: list[float] = []
    for tape in cache.values():
        if tape is not None:
            pooled_hours.extend(((tape["ms"] // 3_600_000) % 24).astype(int).tolist())
            pooled_spread.extend(tape["spread_bps"].tolist())
    spread_all = il.spread_by_session(pooled_hours, pooled_spread)
    cost_curves = {sym: il.session_cost_curve([o for o in sent if o.instrument == sym], sp)
                   for sym, sp in spreads.items()}
    cells = il.execution_cells(sent, spreads)
    sleeves = _sleeves(base)
    seeds = donate_seeds(cells, sleeves, cost_curves)
    recorded = _record_cells(cells, conn=conn, dry_run=dry_run)
    cost_ref = None
    try:
        cs = json.loads((base / "data" / "cost_surface.json").read_text(encoding="utf-8"))
        cost_ref = {"built_at": cs.get("built_at"), "n_symbols": cs.get("n_symbols"),
                    "basis": "bar-based hourly spread points; the tape spreads above are the"
                             " same venue at tick resolution"}
    except (OSError, ValueError):
        pass
    doc: dict[str, Any] = {
        "at": now_iso(), "part": "impact", "dry_run": bool(dry_run),
        "elapsed_s": round(time.monotonic() - t0, 2), "budget_s": budget_s,
        "inputs": {"fill_corpus_rows": len(corpus), "order_intents_rows": len(intents),
                   "live_ledger_rows": len(ledger), "orders_sent": len(sent),
                   "close_flows": len(closes), "tape_join_sent": join_sent,
                   "tape_join_closes": join_close},
        "spread_by_session": spread_all, "spread_by_instrument": spreads,
        "fill_probability": il.fill_probability(sent),
        "rejection_behaviour": il.rejection_behaviour(sent),
        "gateway_log_retcodes": _log_retcodes(base),
        "slippage_by_order_type": il.slippage(sent), "partial_fills": il.partial_fills(sent),
        "stop_behaviour": il.stop_behaviour(sent),
        "impact": il.impact_decomposition(flows),
        "queue_latency_effect": il.queue_latency_effect(sent),
        "session_cost_curve": cost_curves, "toxicity": {
            "short": il.toxicity(flows, horizon="short"),
            "long": il.toxicity(flows, horizon="long")},
        "execution_cells": cells, "seeds": seeds, "registry": recorded,
        "cost_surface_reference": cost_ref,
        "rule": "an execution cell is a hypothesis for the gauntlet; nothing here sizes, caps"
                " or vetoes (GROWTH_GOVERNANCE Rule 1)",
    }
    if not dry_run:
        ll._write_atomic(base / "reports" / "IMPACT_LAB.json", doc)
        if seeds:
            out = base / "data" / "intelligence" / "feed_clock_lab"
            out.mkdir(parents=True, exist_ok=True)
            stamp = now_iso().replace(":", "").replace("-", "")[:15]
            ll._write_atomic(out / f"discoveries_{stamp}.json",
                             {"source": GENERATOR, "generated_at": now_iso(),
                              "discoveries": seeds})
            doc["donated"] = str(out / f"discoveries_{stamp}.json")
    return doc


def run(*, part: str = "all", budget_s: float = 600.0, dry_run: bool = True,
        base: Path | None = None, now_ms: float | None = None, conn: Any = None
        ) -> dict[str, Any]:
    root = Path(base or DESK)
    out: dict[str, Any] = {"at": now_iso(), "part": part, "dry_run": dry_run}
    if part in ("observatory", "all"):
        out["observatory"] = observatory_pass(base=root, budget_s=budget_s, dry_run=dry_run,
                                              now_ms=now_ms, conn=conn)
    if part in ("impact", "all"):
        out["impact"] = impact_pass(base=root, budget_s=budget_s, dry_run=dry_run, conn=conn)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="feed/clock observatory and market-impact lab")
    ap.add_argument("--part", choices=("observatory", "impact", "all"), default="all")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and write nothing")
    a = ap.parse_args(argv)
    doc = run(part=a.part, budget_s=a.budget_s, dry_run=a.dry_run)
    obs = doc.get("observatory")
    if obs:
        fh = obs["feed_health"]
        print(f"observatory: {obs['n_observed']}/{obs['n_tape_instruments']} instruments,"
              f" freshest tape day {obs['tape_freshest_day']}, market"
              f" {fh['status']} p={fh['p_market_trustworthy']} in_session={fh['n_in_session']}"
              f" closed={fh['n_closed']}; fragility {obs['fragility_summary']};"
              f" registry {obs['registry']['status']}")
    imp = doc.get("impact")
    if imp:
        print(f"impact: {imp['inputs']['orders_sent']} orders, joined"
              f" {imp['inputs']['tape_join_sent']['joined']}; impact {imp['impact']['status']};"
              f" toxicity {imp['toxicity']['short']['state']}; {len(imp['execution_cells'])}"
              f" cells, {len(imp['seeds'])} seed(s); registry {imp['registry']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
