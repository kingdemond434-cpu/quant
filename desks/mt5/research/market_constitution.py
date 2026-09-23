#!/usr/bin/env python3
"""MARKET CONSTITUTION -- the organ: rule states stamped on the desk's tapes, rule changes run
as natural experiments, every result a discovery, the survivors seeds for the compiler.

WHAT ONE PASS DOES, in the order the budget is spent:

    1. STUDIES. Every dated rule change in `libs.research.market_constitution.
       rule_change_calendar()` is run as a difference in differences of a window statistic
       between the affected MT5 instrument and an unaffected control venue's instrument, with
       the null drawn from PLACEBO change dates on the same two tapes. A change before the tape
       begins is UNMEASURED with the first bar date named; a change in the future is
       PROSPECTIVE and pre-registered in the registry's research memory, never measured early.
    2. REGISTER. Each MEASURED result -- an effect or its absence -- is one discovery of
       source_type `rule_state_effect`, origin DESK, with the statistics in its payload. A null
       is recorded too: the docket must know a rule change that moved nothing.
    3. DONATE. A measured effect that clears p <= 0.10 seeds the compiler with a rule-
       conditioned hypothesis in the shape `miner_candidate_compiler` reads outright
       (`kind=hypothesis`, a registered price-only family, declared symbols), written under
       `data/intelligence/market_constitution/`. The gauntlet judges; this organ ranks nothing.
    4. STAMP. For every venue -- the four Asian constitutions, the broker's own clock, and one
       venue per `Exchange` row of every country pack (consumed through `country_lab`, never
       re-declared) -- the point-in-time column set is written to
       `data/rule_states/<venue>.parquet` (JSON when parquet cannot be written) for the desk's
       H1 bars of the venue's instruments. Venues the budget did not reach are named.
    5. REPORT `reports/MARKET_CONSTITUTION.json`: the calendar, every study with its verdict,
       the reading list of DECLARED_VERIFY rules, the preregistrations, and what was skipped.
    6. COMPILE. The broker registry (`data/universe/universe.json`, MetaTrader's own tick
       size, digits, contract size, volume step and swaps per symbol) is joined to the venue
       rules in force on the broker's local date -- sessions, halts, settlement, the desk's
       own close -- into ONE machine-readable file, `data/market_constraints.json`
       (`libs.research.market_constitution.compile_constraints`). Its consumers read it
       without importing anything: the gateway door
       (`mt5desk/decision_core.stamp_market_constraints`) stamps each admitted sleeve row with
       its instrument's clauses as an INPUT, and the campaign runner
       (`side_channels/run_external_backtest.constraints_coverage`) records which docket
       symbols ran under a compiled constitution. An axis the registry does not carry (margin,
       the stops/freeze distance) is UNMEASURED by name on the row; nothing here caps, vetoes
       or filters (GROWTH_GOVERNANCE Rule 1).

WHAT IT NEVER DOES. It sizes nothing, it promotes nothing, it edits no state file another
organ writes, and `--dry-run` writes nothing at all -- no parquet, no report, no registry row,
no donation -- and prints what a live pass would have written.

    python market_constitution.py --once --budget-s 900
    python market_constitution.py --once --budget-s 60 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from contextlib import suppress
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from libs.research import country_lab as lab  # noqa: E402
from libs.research import market_constitution as mc  # noqa: E402

UNIVERSE = _DESK / "data" / "universe" / "universe.json"
RULE_STATES_DIR = _DESK / "data" / "rule_states"
INTEL_DIR = _DESK / "data" / "intelligence" / "market_constitution"
REPORT = _DESK / "reports" / "MARKET_CONSTITUTION.json"
CONSTRAINTS = _DESK / "data" / "market_constraints.json"
COUNTRIES_DIR = _DESK / "research" / "countries"
#: Who reads `data/market_constraints.json`. Named on the file itself so a reader that finds it
#: on a box knows what else depends on it.
CONSTRAINT_CONSUMERS: tuple[str, ...] = (
    "desks/mt5/mt5desk/decision_core.py stamp_market_constraints (the gateway door: every "
    "admitted sleeve row carries its instrument's tick, session, halt and settlement clauses as "
    "`constraints`, an INPUT and never a filter)",
    "desks/mt5/side_channels/run_external_backtest.py constraints_coverage (the campaign "
    "runner records which docket symbols ran under a compiled constitution in "
    "reports/BACKTEST_COVERAGE.json)",
    "reports/MARKET_CONSTITUTION.json `constraints` (the counts, for the issue board)",
)

MAX_STAMP_BARS = 60_000         # H1 bars per (symbol, class); the box holds the live terminal
PRE_DAYS = 120                  # trading days each side of a rule change
POST_DAYS = 120
PLACEBO_STEP = 10               # a placebo date every ten trading days
DONATE_P = 0.10                 # a measured effect at or under this p is a seed, not a claim
SOURCE = "market_constitution"

#: Which price-only family a rule change of each kind seeds, and the session phrase the
#: compiler's `text_session` resolves (`_SESSION_VOCAB`): every venue here trades in Asia.
_FAMILY_BY_KIND: dict[str, str] = {
    "session": "session_range_breakout", "auction": "session_range_breakout",
    "price_band": "session_range_breakout", "short": "overnight_gap_decay",
    "hft": "overnight_gap_decay", "fee": "overnight_gap_decay"}


# --------------------------------------------------------------------------- small helpers
def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def _atomic_table(path: Path, columns: dict[str, list[Any]]) -> Path:
    """Write the stamp as parquet through a temp file; fall back to JSON beside it when the
    parquet stack is unavailable. Returns the path actually written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd

        frame = pd.DataFrame(columns)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".parquet", dir=path.parent)
        os.close(fd)
        try:
            frame.to_parquet(name, index=False)
            os.replace(name, path)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(name)
        return path
    except Exception:
        alt = path.with_suffix(".json")
        _atomic_json(alt, {"columns": list(columns), "n": len(next(iter(columns.values()), [])),
                           "rows": columns})
        return alt


def universe_symbols() -> set[str]:
    try:
        doc = json.loads(UNIVERSE.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(k).upper() for k, v in doc.items() if isinstance(v, dict)}


def universe_rows() -> dict[str, dict[str, Any]]:
    """The registry's rows in the broker's own spelling, {} when absent or unreadable."""
    try:
        doc = json.loads(UNIVERSE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


def _fallback_may_hypothesise(symbol: str) -> bool:
    """The lane fence by asset class from the registry file, for a tree where the policy
    module cannot be imported: share CFDs are the event lane and never a seed."""
    try:
        doc = json.loads(UNIVERSE.read_text("utf-8"))
        klass = str(doc.get(symbol, {}).get("asset_class", "")).lower()
    except (OSError, ValueError, AttributeError):
        return False
    return bool(klass) and not any(k in klass for k in ("share", "stock", "equit", "cfd"))


def _may_hypothesise() -> Callable[[str], bool]:
    try:
        from universe_policy import may_hypothesise
    except ImportError:
        try:
            from research.universe_policy import may_hypothesise
        except ImportError:
            return _fallback_may_hypothesise
    return lambda symbol: bool(may_hypothesise(symbol))


def load_bars(symbol: str, timeframe: str = "H1") -> lab.Bars | None:
    """The desk's H1 tape for one symbol, through country_lab's lazy parquet reader."""
    return lab.default_bars_loader(symbol, timeframe)


# --------------------------------------------------------------------------- venues
def _holiday_sets(years: Iterable[int]) -> tuple[dict[str, list[str]], list[str]]:
    """Per-venue holiday dates from the sources the desk already holds: the Japan calendar
    for TSE, the KR and CN packs for KRX and the mainland. A missing source is named."""
    out: dict[str, list[str]] = {}
    notes: list[str] = []
    ys = list(years)
    try:
        from japan import calendars as jc
        days: list[str] = []
        for y in ys:
            with suppress(Exception):
                days.extend(d.isoformat() for d in jc.exchange_holidays(y))
        out["TSE"] = days
    except Exception:
        notes.append("TSE holidays UNMEASURED: research/japan/calendars.py not importable")
    for venue, code in (("KRX", "kr"), ("SSE_SZSE", "cn"), ("CFFEX", "cn")):
        pack = lab.resolve_pack(code)
        if pack is None:
            notes.append(f"{venue} holidays UNMEASURED: no {code} pack")
            continue
        out[venue] = [str(d)[:10] for d in pack.holidays_rule.dates]
    return out, notes


def pack_venues() -> tuple[list[mc.Venue], list[str]]:
    """One venue per Exchange row of every country pack under research/countries."""
    venues: list[mc.Venue] = []
    notes: list[str] = []
    if not COUNTRIES_DIR.exists():
        return venues, ["no country pack directory"]
    for d in sorted(COUNTRIES_DIR.iterdir()):
        if not (d / "pack.py").exists():
            continue
        pack = lab.resolve_pack(d.name)
        if pack is None:
            notes.append(f"pack {d.name} did not resolve")
            continue
        venues.extend(mc.venue_from_pack_rows(
            d.name, pack.exchanges, pack.session_windows, pack.holidays_rule,
            pack.settlement_conventions, mt5_symbols=tuple(pack.executable_instruments[:1])))
    return venues, notes


def all_venues(years: Iterable[int]) -> tuple[list[mc.Venue], list[str]]:
    holidays, notes = _holiday_sets(years)
    built = list(mc.builtin_venues(holidays).values())
    packs, pack_notes = pack_venues()
    return built + packs, notes + pack_notes


# --------------------------------------------------------------------------- stamping
def stamp_venue(venue: mc.Venue, universe: set[str], deadline: float,
                dry_run: bool) -> dict[str, Any]:
    """The PIT column set for one venue over its instruments' H1 bars."""
    syms = [s for s in venue.mt5_symbols if s.upper() in universe]
    out: dict[str, Any] = {"venue": venue.venue_id, "symbols": syms, "rows": 0,
                           "n_rules": len(venue.rules),
                           "n_unverified": sum(1 for r in venue.rules
                                               if r.source.verified != mc.VERIFIED)}
    if not syms:
        out["verdict"] = "UNMEASURED"
        out["why"] = "none of the venue's instruments is in the broker registry"
        return out
    cols: dict[str, list[Any]] = {"time": [], "symbol": [], "instrument_class": [],
                                  **{c: [] for c in mc.STAMP_COLUMNS}}
    missing: list[str] = []
    for sym in syms:
        bars = load_bars(sym)
        if bars is None:
            missing.append(sym)
            continue
        times = bars.times[-MAX_STAMP_BARS:].astype("datetime64[s]").tolist()
        for cls in venue.instrument_classes:
            if time.monotonic() > deadline:
                out["verdict"] = "POORLY_MEASURED"
                out["why"] = f"budget exhausted before {sym}/{cls}"
                break
            stamped = mc.stamp(venue, times, cls)
            n = len(times)
            cols["time"].extend(times)
            cols["symbol"].extend([sym] * n)
            cols["instrument_class"].extend([cls] * n)
            for c in mc.STAMP_COLUMNS:
                cols[c].extend(stamped[c])
    out["rows"] = len(cols["time"])
    if missing:
        out["missing_tapes"] = missing
    if out["rows"] == 0:
        out["verdict"] = "UNMEASURED"
        out["why"] = f"no H1 tape for {syms}"
        return out
    out.setdefault("verdict", "STAMPED")
    if not dry_run:
        written = _atomic_table(RULE_STATES_DIR / f"{mc._slug(venue.venue_id)}.parquet", cols)
        out["path"] = str(written.relative_to(_DESK)) if written.is_relative_to(_DESK) \
            else str(written)
    return out


# --------------------------------------------------------------------------- the studies
def run_studies(universe: set[str], today: date | None = None) -> list[dict[str, Any]]:
    """Every rule change as a natural experiment on the desk's own tapes."""
    tapes: dict[str, lab.Bars | None] = {}

    def tape(sym: str) -> lab.Bars | None:
        if sym not in tapes:
            tapes[sym] = load_bars(sym) if sym.upper() in universe else None
        return tapes[sym]

    out: list[dict[str, Any]] = []
    for ch in mc.rule_change_calendar():
        row: dict[str, Any] = {"change_id": ch.change_id, "venue": ch.venue, "date": ch.date,
                               "kind": ch.kind, "mechanism": ch.mechanism,
                               "experiment": ch.experiment, "window_utc": list(ch.window_utc),
                               "prospective": ch.prospective, "verified": ch.source.verified,
                               "results": []}
        if not ch.affected_symbols:
            row["verdict"] = "UNMEASURED"
            row["why"] = ch.experiment
            out.append(row)
            continue
        ctrl_sym = ch.control_symbols[0] if ch.control_symbols else ""
        ctrl = tape(ctrl_sym) if ctrl_sym else None
        for sym in ch.affected_symbols:
            res: dict[str, Any] = {"symbol": sym, "control": ctrl_sym}
            bars = tape(sym)
            if bars is None or ctrl is None:
                res["verdict"] = "UNMEASURED"
                res["why"] = (f"no H1 tape for {sym}" if bars is None
                              else f"no H1 tape for control {ctrl_sym or '(none named)'}")
            else:
                res.update(mc.rule_change_effect(bars.times, bars.close, ctrl.times, ctrl.close,
                                                 ch.date, ch.window_utc, pre_days=PRE_DAYS,
                                                 post_days=POST_DAYS, step=PLACEBO_STEP,
                                                 today=today))
            row["results"].append(res)
        verdicts = [r["verdict"] for r in row["results"]]
        row["verdict"] = ("MEASURED" if "MEASURED" in verdicts else
                          "PROSPECTIVE" if "PROSPECTIVE" in verdicts else
                          "POORLY_MEASURED" if "POORLY_MEASURED" in verdicts else "UNMEASURED")
        out.append(row)
    return out


# --------------------------------------------------------------------------- registering
def register(studies: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    """MEASURED results become discoveries; PROSPECTIVE ones become preregistrations."""
    out: dict[str, Any] = {"discoveries_created": 0, "discoveries_existing": 0,
                           "preregistered": [], "would_register": 0}
    for st in studies:
        for res in st["results"]:
            if res.get("verdict") == "MEASURED":
                if dry_run:
                    out["would_register"] += 1
                    continue
                sig = bool(res.get("significant_10pct"))
                _did, created = reg.record_discovery(
                    source_id=f"{SOURCE}:{st['change_id']}:{res['symbol']}",
                    source_type="rule_state_effect", mechanism=st["mechanism"], origin="DESK",
                    generator=SOURCE, assets=[res["symbol"]],
                    exact_rule=f"rule_state:{st['venue']}:{st['kind']}:{st['date']}:"
                               f"window={st['window_utc'][0]}-{st['window_utc'][1]}",
                    information=st["experiment"],
                    economic_rationale=("effect measured" if sig else
                                        "no effect measured: the rule change moved nothing "
                                        "the window statistic can see"),
                    falsifier="the placebo null: |DiD| inside the 90th placebo percentile",
                    confidence=round(1.0 - float(res.get("p_placebo", 1.0)), 4),
                    payload={"kind": "rule_state_effect", **res})
                out["discoveries_created" if created else "discoveries_existing"] += 1
            elif res.get("verdict") == "PROSPECTIVE":
                key = f"{SOURCE}:prereg:{st['change_id']}:{res['symbol']}"
                statement = (f"PRE-REGISTERED {st['change_id']} on {res['symbol']} "
                             f"({st['date']}): {st['experiment']}")
                if not dry_run and hasattr(reg, "remember"):
                    reg.remember(SOURCE, statement, kind="preregistration", memory_key=key,
                                 payload={"change_id": st["change_id"], "symbol": res["symbol"],
                                          "date": st["date"], "window_utc": st["window_utc"],
                                          "pre_days": PRE_DAYS, "post_days": POST_DAYS,
                                          "placebo_step": PLACEBO_STEP,
                                          "decision_rule": "|DiD| beyond the 95th placebo "
                                                           "percentile",
                                          "registered_at": _now()})
                out["preregistered"].append(key)
    return out


# --------------------------------------------------------------------------- donations
def seeds(studies: list[dict[str, Any]], may_hyp: Callable[[str], bool]) -> list[dict[str, Any]]:
    """Rule-conditioned hypotheses for the compiler, one per measured effect per instrument."""
    rows: list[dict[str, Any]] = []
    for st in studies:
        family = _FAMILY_BY_KIND.get(str(st["kind"]), "")
        if not family:
            continue
        for res in st["results"]:
            if res.get("verdict") != "MEASURED" or not res.get("significant_10pct"):
                continue
            sym = str(res["symbol"])
            if not may_hyp(sym):
                continue
            side = "rose" if float(res.get("did", 0.0)) > 0 else "fell"
            rows.append({
                "kind": "hypothesis", "family": family, "symbols": [sym], "source": SOURCE,
                "claim": (f"{sym}: the {st['window_utc'][0]}-{st['window_utc'][1]} UTC share of "
                          f"the day's absolute move {side} after the {st['venue']} rule change "
                          f"of {st['date']} ({st['change_id']}); an asian session {family} "
                          f"conditioned on the post-change rule state"),
                "mechanism": st["mechanism"],
                "rule_state": {"venue": st["venue"], "kind": st["kind"],
                               "effective_from": st["date"], "window_utc": st["window_utc"]},
                "evidence": {"did": res.get("did"), "p_placebo": res.get("p_placebo"),
                             "n_placebo": res.get("n_placebo")},
                "verified": st["verified"], "origin": "DESK"})
    return rows


def donate(rows: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(rows), "path": None}
    if not rows or dry_run:
        return out
    stamp_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = INTEL_DIR / f"discoveries_{stamp_ts}.json"
    _atomic_json(path, {"source": SOURCE, "generated_at": _now(), "discoveries": rows})
    out["path"] = str(path.relative_to(_DESK)) if path.is_relative_to(_DESK) else str(path)
    return out


# --------------------------------------------------------------------------- one pass
def compile_constraints(venues: list[mc.Venue], dry_run: bool,
                        now: datetime | None = None) -> dict[str, Any]:
    """Step 6: the registry joined to the rules in force, written as `data/market_constraints.json`
    for the gateway door and the campaign runner. Returns the report's summary block; an absent
    registry is UNMEASURED by name and writes nothing."""
    rows = universe_rows()
    if not rows:
        return {"status": "UNMEASURED", "n_symbols": 0,
                "why": f"no registry rows at {UNIVERSE}; nothing to compile"}
    doc = mc.compile_constraints(rows, venues, now or datetime.now(UTC))
    doc["writer"] = "desks/mt5/research/market_constitution.py"
    doc["consumers"] = list(CONSTRAINT_CONSUMERS)
    summary: dict[str, Any] = {
        "status": "MEASURED", "generated_at": doc["generated_at"],
        "rules_version": doc["rules_version"], "n_symbols": doc["n_symbols"],
        "by_status": doc["by_status"], "by_instrument_class": doc["by_instrument_class"],
        "unmeasured_axes": doc["unmeasured_axes"], "axes": doc["axes"],
        "consumers": list(CONSTRAINT_CONSUMERS), "rule": doc["rule"],
    }
    if not dry_run:
        _atomic_json(CONSTRAINTS, doc)
        summary["path"] = (str(CONSTRAINTS.relative_to(_DESK)) if CONSTRAINTS.is_relative_to(_DESK)
                           else str(CONSTRAINTS))
    return summary


def run_once(budget_s: float, dry_run: bool, today: date | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(5.0, float(budget_s))
    universe = universe_symbols()
    now = today or datetime.now(UTC).date()
    now_dt = (datetime.now(UTC) if today is None
              else datetime(today.year, today.month, today.day, 12, tzinfo=UTC))
    venues, notes = all_venues(range(2008, now.year + 3))
    studies = run_studies(universe, today=now)
    registered = register(studies, dry_run)
    donated = donate(seeds(studies, _may_hypothesise()), dry_run)
    # THE CONSTRAINTS ARE COMPILED BEFORE THE STAMPS, which are the step the budget can cut: a
    # pass that runs out of time still leaves the placer and the campaign a current file.
    constraints = compile_constraints(venues, dry_run, now_dt)
    stamps: list[dict[str, Any]] = []
    skipped: list[str] = []
    for v in venues:
        if time.monotonic() > deadline:
            skipped.append(v.venue_id)
            continue
        stamps.append(stamp_venue(v, universe, deadline, dry_run))
    reading_list = mc.unverified_rules(venues)
    by_verdict: dict[str, int] = {}
    for st in studies:
        by_verdict[st["verdict"]] = by_verdict.get(st["verdict"], 0) + 1
    report: dict[str, Any] = {
        "generated_at": _now(), "rules_version": mc.RULES_VERSION, "dry_run": dry_run,
        "budget_s": float(budget_s), "elapsed_s": round(time.monotonic() - t0, 2),
        "venues": {"n": len(venues), "builtin": sorted(mc.builtin_venues()),
                   "from_packs": sum(1 for v in venues if ":" in v.venue_id),
                   "n_rules": sum(len(v.rules) for v in venues),
                   "n_unverified_rules": len(reading_list), "notes": notes},
        "calendar": [c.as_row() for c in mc.rule_change_calendar()],
        "studies": studies, "studies_by_verdict": by_verdict,
        "registry": registered, "donations": donated,
        "constraints": constraints,
        "stamps": stamps, "stamps_skipped_for_budget": skipped,
        "unmeasured": [{"change_id": st["change_id"], "why": st.get("why") or
                        [r.get("why") for r in st["results"]]}
                       for st in studies if st["verdict"] == "UNMEASURED"],
        "reading_list": reading_list,
        "rule": ("a rule state is a column, never a footnote; a change is a natural experiment "
                 "with a control venue and a placebo null; DECLARED_VERIFY rows are named until "
                 "their document is read; a change outside the tape is UNMEASURED with the "
                 "first bar named; a future change is PROSPECTIVE and pre-registered"),
    }
    if not dry_run:
        _atomic_json(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    args = ap.parse_args(argv)
    rep = run_once(args.budget_s, args.dry_run)
    r, v = rep["registry"], rep["venues"]
    print(f"market_constitution rules={rep['rules_version']} venues={v['n']} "
          f"rules={v['n_rules']} unverified={v['n_unverified_rules']} "
          f"studies={rep['studies_by_verdict']} "
          f"discoveries=+{r['discoveries_created']}/{r['discoveries_existing']} "
          f"seeds={rep['donations']['n']} "
          f"constraints={rep['constraints'].get('n_symbols')} "
          f"({rep['constraints'].get('by_status') or rep['constraints'].get('status')}) "
          f"stamped={sum(1 for s in rep['stamps'] if s.get('verdict') == 'STAMPED')} "
          f"skipped={len(rep['stamps_skipped_for_budget'])} elapsed={rep['elapsed_s']}s")
    for st in rep["studies"]:
        r0 = st["results"][0] if st["results"] else {}
        print(f"  {st['change_id']:<32} {st['verdict']:<16} did={r0.get('did')} "
              f"p={r0.get('p_placebo')} n_placebo={r0.get('n_placebo', 0)}")
    print("  (dry run: nothing written)" if args.dry_run else f"  wrote {REPORT}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
