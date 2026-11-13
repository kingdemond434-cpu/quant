"""The desk's DataHub contracts beyond the first three, WHO REFRESHES EACH, WHICH CELLS IT FEEDS.

`libs/data/datahub.py` gave the desk one typed, point-in-time door and registered three contracts
(`bars.h1`, `terms.swap_diff`, `calendar.events`). Nothing said, per contract, whether a clock
keeps it fresh or whether any judged cell ever read it -- so a contract could hold data that no
schedule refreshed and no family consumed, and nothing would notice (III.16: UNWIRED OR IDLE IS A
DEFECT). This module closes that in two halves:

  1. MORE CONTRACTS, bound to the loaders the gauntlet ALREADY uses, so the hub's answer and the
     judge's input are the same bytes:
        micro.flow_bars     tick-rule flow / VPIN toxicity / Kyle-lambda impact / spread regime
                            per H1 bar, accumulated in `data/lake/series/micro_<SYM>.parquet` by
                            the `flow_toxicity` leg (new; see research/flow_toxicity_miner.py)
        micro.depth_probe   the venue's measured depth-of-market verdict per symbol
        micro.surfaces      spread/activity by weekday-hour (`microstructure_miner`)
        tape.spread_flow    the spread + sign flow series `liquidity_regime` and
                            `orderflow_imbalance` condition on (`orthogonal_sweep._tape_series`)
        macro.fred_daily    the PIT-lagged daily FRED regime series (`_macro_series`)
        cot.positioning     the release-lagged CFTC frame (`_cot_frame`)
     Names never collide with the other thread's `ais.*`, `tanker.*` or `openbb.*`.

  2. A COVERAGE AUDIT (`coverage()`), run hourly as leg `datahub_coverage`, which writes
     `desks/mt5/reports/DATAHUB_COVERAGE.json`. Per contract it measures:
        provider    does a provider answer on this host for a sample symbol (or UNMEASURED)
        refresh     is every declared clock one the repo knows (VPS timer, box task in
                    box_tasks.manifest, or an hourly/daily cycle leg) -- the same resolver
                    `scripts/check_tier1_program.py` gates the Tier-1 ledger with
        judged      how many judged verdicts the cells that read it have earned: the families'
                    `judged_total` in `reports/JUDGE_COVERAGE.json`, or for a series contract the
                    gate-ledger lines naming its series
     and a verdict: REACHES_JUDGE, AWAITING_JUDGE (cells exist, none judged yet), NO_REFRESH,
     NO_CONSUMER, UNBUILDABLE_ON_VENUE or UNMEASURED. An absent artifact is UNMEASURED, never a
     zero (L1.28a).

Nothing here sizes, vetoes or gates anything; it is a door and a measurement.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
SERIES_DIR = DESK / "data" / "lake" / "series"
DEPTH_PROBE = DESK / "data" / "tape" / "depth_probe.json"
SURFACES = DESK / "reports" / "MICROSTRUCTURE_SURFACES.json"
JUDGE_COVERAGE = DESK / "reports" / "JUDGE_COVERAGE.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
FLOW_REPORT = DESK / "reports" / "FLOW_TOXICITY.json"
OUT = DESK / "reports" / "DATAHUB_COVERAGE.json"

#: Bytes of the gate ledger's tail scanned for series names. Bounded: the ledger holds every
#: verdict the desk ever wrote, and the audit is a report, not a judge.
LEDGER_TAIL_BYTES = 64 * 1024 * 1024

REACHES = "REACHES_JUDGE"
AWAITING = "AWAITING_JUDGE"
NO_REFRESH = "NO_REFRESH"
NO_CONSUMER = "NO_CONSUMER"
UNBUILDABLE = "UNBUILDABLE_ON_VENUE"
UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class ContractMeta:
    """What keeps a contract fresh and what reads it. `clocks` uses the Tier-1 checker's grammar:
    `quant-x.timer` | `MT5-<Task>` | `hourly_cycle:<leg>` | `daily_cycle:<leg>`."""

    clocks: tuple[str, ...]
    #: Families whose cells condition on this contract. ("*",) = every price-reading family.
    families: tuple[str, ...] = ()
    #: For a lake-series contract: the series-name prefix its cells carry in `params.source`.
    series_prefix: str = ""
    #: Keyword arguments a provider probe uses on this host.
    probe: dict[str, Any] = field(default_factory=dict)
    #: The module:function the judge itself rebuilds the input with.
    consumer: str = ""
    #: Why a contract has no consumer, when that is a measured property of the venue.
    unbuildable: str = ""


META: dict[str, ContractMeta] = {
    "bars.h1": ContractMeta(("hourly_cycle:refresh_bars",), ("*",), probe={"symbol": "EURUSD"},
                            consumer="research/proposer_common.py:bars"),
    "terms.swap_diff": ContractMeta(("hourly_cycle:record_tape",), ("carry", "style_premia"),
                                    probe={"symbol": "AUDJPY"},
                                    consumer="mt5desk/family_inputs.py:resolve"),
    "calendar.events": ContractMeta(("quant-seed-miners.timer",), ("event_reaction",),
                                    consumer="research/orthogonal_sweep.py:_event_index"),
    "micro.flow_bars": ContractMeta(("hourly_cycle:flow_toxicity",),
                                    ("exogenous_conditioner", "alt_series_momentum"),
                                    series_prefix="micro_", probe={"symbol": "EURUSD"},
                                    consumer="mt5desk/family_exogenous_conditioner.py:conditioner"),
    "micro.depth_probe": ContractMeta(
        ("hourly_cycle:flow_toxicity",), (),
        unbuildable=("the venue publishes no depth of market (depth_probe: every symbol "
                     "NO_DEPTH); queue, true OFI and microprice are not buildable on a book "
                     "synthesised from bid/ask -- re-probed weekly")),
    "micro.surfaces": ContractMeta(("daily_cycle:_proposers",),
                                   ("execution_state",), probe={"symbol": "EURUSD"},
                                   consumer="research/orthogonal_sweep.py:_surface_for"),
    "tape.spread_flow": ContractMeta(("hourly_cycle:record_tape", "MT5-TickRecorder"),
                                     ("liquidity_regime", "orderflow_imbalance"),
                                     probe={"symbol": "EURUSD"},
                                     consumer="research/orthogonal_sweep.py:_tape_series"),
    "macro.fred_daily": ContractMeta(("hourly_cycle:fred_macro",), ("macro_conditional",),
                                     consumer="research/orthogonal_sweep.py:_macro_series"),
    "cot.positioning": ContractMeta(("quant-cot-fetch.timer",), ("cot_positioning",),
                                    probe={"symbol": "XAUUSD"},
                                    consumer="research/orthogonal_sweep.py:_cot_frame"),
}


# ----------------------------------------------------------------------------- providers
def _sweep():
    """The gauntlet's own input readers. Imported lazily: it is a large module."""
    for p in (str(DESK), str(DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import orthogonal_sweep
    return orthogonal_sweep


def _flow_bars(symbol: str) -> Any:
    import pandas as pd
    p = SERIES_DIR / f"micro_{symbol}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def _depth_probe() -> list[dict[str, Any]] | None:
    try:
        doc = json.loads(DEPTH_PROBE.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    syms = doc.get("symbols") if isinstance(doc, dict) else None
    if not isinstance(syms, dict):
        return None
    at = doc.get("at")
    return [{"symbol": s, **r, "probed_at": at, "available_time": at}
            for s, r in sorted(syms.items()) if isinstance(r, dict)]


def _surfaces(symbol: str | None = None) -> list[dict[str, Any]] | None:
    try:
        doc = json.loads(SURFACES.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    syms = (doc or {}).get("symbols")
    if not isinstance(syms, dict):
        return None
    at = doc.get("generated_at")
    rows = [{"symbol": s, **v, "available_time": at} for s, v in sorted(syms.items())
            if isinstance(v, dict) and (symbol is None or s == symbol)]
    return rows or None


def _tape_spread_flow(symbol: str, tf: str = "H1") -> Any:
    import pandas as pd
    osw = _sweep()
    t = osw._ticks(symbol)
    if t is None:
        return None
    idx = pd.date_range(t.index.min().floor("h"), t.index.max().ceil("h"), freq="1h", tz="UTC")
    spread, flow = osw._tape_series(symbol, idx, tf)
    if spread is None:
        return None
    return pd.DataFrame({"spread": spread, "flow": flow})


def _fred_daily(name: str | None = None) -> Any:
    import pandas as pd
    osw = _sweep()
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("D"), periods=400, freq="D")
    s = osw._macro_series(idx, name)
    return None if s is None else s.to_frame("regime_rank")


def _cot(symbol: str | None = None) -> Any:
    return _sweep()._cot_frame(symbol)


def extend(hub: Any) -> Any:
    """Register the contracts above on a `DataHub` (called from `datahub.desk_hub`)."""
    from libs.data.datahub import Contract, Provider
    hub.register(Contract("micro.flow_bars", "frame",
                          description="tick-rule flow, sign-only quote imbalance, VPIN-style "
                                      "toxicity, Kyle-lambda impact, spread regime per H1 bar "
                                      "(available_time = bar close, UTC)",
                          providers=[Provider("lake_series_micro", _flow_bars, "primary")]))
    hub.register(Contract("micro.depth_probe", "rows",
                          description="per-symbol depth-of-market verdict from MarketBookGet",
                          providers=[Provider("tape_depth_probe", _depth_probe, "primary")]))
    hub.register(Contract("micro.surfaces", "rows",
                          description="spread and activity by weekday-hour per instrument",
                          providers=[Provider("microstructure_miner", _surfaces, "primary")]))
    hub.register(Contract("tape.spread_flow", "frame",
                          description="mean spread and sign flow on the bar clock, from ticks",
                          providers=[Provider("orthogonal_sweep_tape", _tape_spread_flow,
                                              "primary")]))
    hub.register(Contract("macro.fred_daily", "frame",
                          description="trailing-rank daily FRED regime, publication-lagged",
                          providers=[Provider("orthogonal_sweep_macro", _fred_daily,
                                              "primary")]))
    hub.register(Contract("cot.positioning", "frame",
                          description="CFTC positioning, lagged to its Friday release",
                          providers=[Provider("orthogonal_sweep_cot", _cot, "primary")]))
    return hub


# ----------------------------------------------------------------------------- audit
def _clock_resolver(root: Path) -> Callable[[str], bool]:
    """The Tier-1 checker's own resolver, so this audit and that gate agree on what a clock is."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_tier1_check",
                                                  root / "scripts" / "check_tier1_program.py")
    if spec is None or spec.loader is None:
        return lambda _s: False
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    clocks = mod._schedulers(root)
    return lambda s: bool(mod._scheduler_known(s, clocks))


def _judged_by_family(path: Path) -> tuple[dict[str, int], dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}, {}
    fams = doc.get("families") if isinstance(doc, dict) else None
    out = {str(k): int((v or {}).get("judged_total") or 0)
           for k, v in (fams or {}).items() if isinstance(v, dict)}
    return out, {"at": doc.get("at"), "judged_verdicts": (doc.get("totals") or {})
                 .get("judged_verdicts")}


def _ledger_series_hits(prefix: str, identities: set[str], path: Path,
                        tail: int = LEDGER_TAIL_BYTES) -> dict[str, Any]:
    """Judged verdict lines that name a `prefix*` series or a donated identity, in the tail."""
    if not path.exists():
        return {"status": UNMEASURED, "why": f"{path.name} absent on this host"}
    judged = lines = 0
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > tail:
                fh.seek(size - tail)
                fh.readline()
            for raw in fh:
                line = raw.decode("utf-8", errors="replace")
                if prefix not in line and not any(i in line for i in identities):
                    continue
                lines += 1
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
                    continue
                if row.get("passed") is not True and str(row.get("terminal_gate") or "") in (
                        "", "UNKNOWN"):
                    continue
                judged += 1
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "MEASURED", "lines_naming_series": lines, "judged": judged,
            "scanned_tail_bytes": min(tail, size)}


def _donated(report: Path) -> tuple[int, set[str]]:
    try:
        doc = json.loads(report.read_text("utf-8"))
    except (OSError, ValueError):
        return 0, set()
    cells = doc.get("cells") or {}
    ids = {str(i) for i in (cells.get("identities") or [])}
    return int(((cells.get("donation") or {}).get("donated")) or 0), ids


def _probe(hub: Any, name: str, kw: dict[str, Any]) -> dict[str, Any]:
    try:
        got = hub.get(name, **kw)
    except LookupError as exc:
        return {"status": UNMEASURED, "why": str(exc)[:200]}
    except Exception as exc:
        return {"status": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    payload = got.get("payload")
    n = None
    try:
        n = len(payload)
    except TypeError:
        n = 1
    return {"status": "ANSWERED", "provider": got.get("provider"), "rows": n}


def coverage(*, hub: Any | None = None, root: Path = ROOT,
             judge_coverage: Path = JUDGE_COVERAGE, ledger: Path = GATE_LEDGER,
             flow_report: Path = FLOW_REPORT, probe: bool = True) -> dict[str, Any]:
    """Per contract: provider, refresh clocks, judged cells, verdict. Writes nothing."""
    if hub is None:
        from libs.data.datahub import desk_hub
        hub = desk_hub()
    known = _clock_resolver(root)
    judged_fam, jc = _judged_by_family(judge_coverage)
    donated, ids = _donated(flow_report)
    rows: dict[str, dict[str, Any]] = {}
    for name in hub.contracts():
        meta = META.get(name)
        row: dict[str, Any] = {"contract": name}
        if meta is None:
            row.update({"verdict": NO_CONSUMER, "why": "no ContractMeta: nobody declared what "
                        "refreshes it or which cells read it"})
            rows[name] = row
            continue
        clocks = {c: known(c) for c in meta.clocks}
        row["clocks"] = clocks
        row["refreshed"] = any(clocks.values())
        row["consumer"] = meta.consumer
        row["families"] = list(meta.families)
        row["provider"] = _probe(hub, name, meta.probe) if probe else {"status": "SKIPPED"}
        if meta.series_prefix:
            hits = _ledger_series_hits(meta.series_prefix, ids, ledger)
            row["judged_basis"] = "gate-ledger lines naming the series or a donated identity"
            row["judged"] = hits.get("judged") if hits.get("status") == "MEASURED" else None
            row["ledger"] = hits
            row["cells_donated_last_pass"] = donated
        elif meta.families == ("*",):
            row["judged_basis"] = "every judged verdict (every family reads the bars)"
            jv = jc.get("judged_verdicts")
            row["judged"] = int(jv) if jv is not None else None
        elif meta.families:
            row["judged_basis"] = "JUDGE_COVERAGE.json judged_total of its families"
            row["judged_by_family"] = {f: judged_fam.get(f) for f in meta.families}
            row["judged"] = (sum(int(v or 0) for v in row["judged_by_family"].values())
                             if judged_fam else None)
        else:
            row["judged"] = 0
        if not row["refreshed"]:
            verdict, why = NO_REFRESH, "no declared clock is one the repo knows"
        elif meta.unbuildable:
            verdict, why = UNBUILDABLE, meta.unbuildable
        elif not meta.families:
            verdict, why = NO_CONSUMER, "refreshed, but no family reads it"
        elif row["judged"] is None:
            verdict, why = UNMEASURED, "the judge's record is not on this host"
        elif row["judged"] > 0:
            verdict, why = REACHES, ""
        else:
            verdict, why = AWAITING, ("cells read it but none has a judged verdict yet; see "
                                      "JUDGE_COVERAGE.json not_testable/never_fires for the "
                                      "family")
        row["verdict"], row["why"] = verdict, why
        rows[name] = row
    counts: dict[str, int] = {}
    for r in rows.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {"schema": "datahub_coverage/1",
            "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "clock": "hourly_cycle:datahub_coverage", "judge_coverage_at": jc.get("at"),
            "contracts": len(rows), "reaching_judge": counts.get(REACHES, 0),
            "by_verdict": counts,
            "defects": sorted(n for n, r in rows.items()
                              if r["verdict"] in (NO_REFRESH, NO_CONSUMER)),
            "rows": rows}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="DataHub contract coverage audit")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--no-probe", action="store_true")
    a = ap.parse_args(argv)
    rep = coverage(probe=not a.no_probe)
    if not a.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
        try:
            tmp.replace(OUT)
        except PermissionError:
            OUT.write_text(tmp.read_text("utf-8"), "utf-8")
            tmp.unlink(missing_ok=True)
    print(f"DATAHUB COVERAGE  {rep['reaching_judge']}/{rep['contracts']} contracts reach the "
          f"judge; {rep['by_verdict']}")
    for n, r in sorted(rep["rows"].items()):
        print(f"  {n:<18} {r['verdict']:<20} judged={r.get('judged')}  {r.get('why', '')[:70]}")
    return 0


if __name__ == "__main__":
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
