"""ONE TYPED REGISTRY OF THE DESK'S ANALYTICS TOOLS, so research agents and LLM seats can find and
call them instead of re-deriving them in a prompt.

THE CAPABILITY, AND WHERE IT CAME FROM. `desks/mt5/docs/CAPABILITY_AUDIT.md` lists "Universal
tool registry / MCP: MISSING -- queued (Fincept)". Fincept Terminal (AGPL-3.0-or-later) exposes
its analytics to its AI layer as named tools; the desk re-implements the IDEA only -- a typed
catalogue -- and copies no code. The desk had the analytics (`mt5desk/microstructure.py`,
`mt5desk/flow_toxicity.py`, the proposer screen, the deflation charge, the DataHub) but no single
place that said what each one takes, returns and reads, so an agent could not discover them.

WHAT A TOOL ENTRY CARRIES
    name        stable id an agent calls it by
    target      `module:qualname`, importable from the repo root (desks/mt5 on the path)
    inputs      parameter names the caller supplies; VERIFIED against the real signature
    outputs     what comes back, in words a model can act on
    contracts   DataHub contracts it reads; VERIFIED against `desk_hub().contracts()`
    layer       which of `libs/research/layers.LAYERS` the tool serves
    authority   always "propose_only"

PROPOSE ONLY, BY CONSTRUCTION. No tool here sizes, admits or vetoes. `call()` refuses any entry
whose authority is not "propose_only", and the test suite fails if a live-sizing module imports
this registry. An LLM's tool result is research input that reaches capital only through the
sealed gauntlet like every other proposal.

THE ARTIFACT. `scripts/build_tool_registry.py` (hourly leg `tool_registry`) imports every tool,
checks inputs and contracts, and writes `desks/mt5/reports/TOOL_REGISTRY.json` with a per-tool
status (OK / IMPORT_FAILED / SIGNATURE_MISMATCH / UNKNOWN_CONTRACT). `prompt_block()` renders the
OK tools as a compact catalogue for a model's context.
"""
from __future__ import annotations

import importlib
import inspect
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "TOOL_REGISTRY.json"
PROPOSE_ONLY = "propose_only"


@dataclass(frozen=True)
class Tool:
    name: str
    target: str
    inputs: tuple[str, ...]
    outputs: str
    description: str
    layer: str
    contracts: tuple[str, ...] = ()
    authority: str = PROPOSE_ONLY


TOOLS: tuple[Tool, ...] = (
    # ---- data door -----------------------------------------------------------------------
    Tool("datahub_contracts", "libs.data.datahub:desk_hub", (),
         "a DataHub; .contracts() lists names, .get(name, **kw) returns payload + provenance",
         "every typed point-in-time dataset the desk serves, with the provider that answered",
         "information",
         ("bars.h1", "terms.swap_diff", "calendar.events", "micro.flow_bars", "micro.depth_probe",
          "micro.surfaces", "tape.spread_flow", "macro.fred_daily", "cot.positioning")),
    Tool("datahub_coverage", "libs.data.datahub_desk:coverage", ("probe",),
         "per contract: refresh clocks known?, provider answers?, judged verdicts, verdict",
         "which data contracts are refreshed on a schedule and actually reach judged cells",
         "information"),
    # ---- tick microstructure: cost side --------------------------------------------------
    Tool("quote_frame", "mt5desk.microstructure:quote_frame", ("ticks", "point"),
         "tick frame + mid, spread, spread_pts, microprice (mid_fallback basis)",
         "normalise a raw MT5 tick frame; drops one-sided rows rather than zero-filling",
         "execution", ("tape.spread_flow",)),
    Tool("effective_spread", "mt5desk.microstructure:effective_spread_pts",
         ("df", "latency_ms", "point", "side"),
         "array of crossing cost in points per decision instant",
         "what a market order really costs at a given decision-to-fill latency",
         "execution", ("tape.spread_flow",)),
    Tool("hour_cell", "mt5desk.microstructure:hour_cell", ("df", "symbol", "hour", "point"),
         "QuoteStats: spread percentiles, latency slip, realised spread, intensity, OFI proxy",
         "every cost-side microstructure statistic for one symbol-hour, or UNMEASURED with n",
         "execution", ("tape.spread_flow",)),
    Tool("realized_variation", "mt5desk.microstructure:realized_variation", ("df", "freq"),
         "per bar: realised vol, bipower vol, jump share, jump count",
         "split a bar's travel into diffusion and jumps from the tick path",
         "prediction", ("tape.spread_flow",)),
    Tool("intrabar_path", "mt5desk.microstructure:intrabar_path", ("df", "freq"),
         "per bar: whether the high came before the low, and when",
         "the true intrabar order a stop/target backtest otherwise has to assume",
         "exit", ("tape.spread_flow",)),
    # ---- tick microstructure: information side (flow, toxicity, impact, regime) ---------
    Tool("tick_rule_signs", "mt5desk.flow_toxicity:tick_rule_signs", ("mid",),
         "(carried sign per revision, moved mask)",
         "Lee-Ready tick test: up +1, down -1, zero-tick inherits the last sign",
         "information", ("micro.flow_bars",)),
    Tool("bvc_buckets", "mt5desk.flow_toxicity:bvc_buckets", ("mid", "bucket_ticks"),
         "(bucket order imbalance |2Phi(z)-1|, bucket end index)",
         "bulk-volume classification on equal-count buckets, PIT-standardised",
         "information", ("micro.flow_bars",)),
    Tool("flow_bar_aggregates", "mt5desk.flow_toxicity:bar_aggregates",
         ("ticks", "point", "rule", "bucket_ticks"),
         "additive per-bar aggregates (flow, OFI, spread, path, BVC sums)",
         "the per-bar sums that let a flow series accumulate past the tape window",
         "information", ("micro.flow_bars",)),
    Tool("flow_toxicity_series", "mt5desk.flow_toxicity:derive", ("agg", "point", "rule"),
         "tick_rule_imbalance, quote_imbalance (sign_only), vpin, signed_vpin, kyle_lambda, "
         "spread_regime_rank, tick_intensity, available_time",
         "VPIN-style toxicity, Kyle-lambda impact and spread regime per bar, PIT-stamped",
         "information", ("micro.flow_bars",)),
    Tool("microstructure_census", "libs.research.microstructure_census:census", ("root",),
         "per construction: LIVE / STARVED / UNBUILDABLE_ON_VENUE / NEEDS_EXTERNAL_FEED",
         "which microstructure constructions this venue supports and what blocks each",
         "execution", ("micro.depth_probe",)),
    # ---- conditioning and screening ------------------------------------------------------
    Tool("exogenous_conditioner_series", "mt5desk.family_exogenous_conditioner:conditioner",
         ("source", "signal", "transform", "lag_hours", "z_window"),
         "a lagged, transformed series on its own available_time clock, or None",
         "the exact PIT join the judge uses to condition an instrument on a lake series",
         "prediction", ("micro.flow_bars",)),
    Tool("proposer_screen", "research.proposer_common:screen",
         ("d", "signals", "cost", "unfillable"),
         "n_independent, gross/net per trade, t_gross, clears_cost -- or None under 30 trades",
         "the shared non-overlapping, net-of-cost proposal screen every proposer uses",
         "prediction", ("bars.h1",)),
    Tool("deflate_t", "research.multiplicity:deflate_t", ("t_obs", "n_tests"),
         "the t-statistic after the expected-max charge for n tests",
         "charge a search for its own multiplicity before proposing anything",
         "prediction"),
    Tool("flow_toxicity_screen", "research.flow_toxicity_miner:screen_symbol",
         ("symbol", "bars", "cost", "unfillable", "series_root", "series_start"),
         "screened grid rows (exogenous_conditioner / alt_series_momentum on micro_ series)",
         "screen one symbol's microstructure cells exactly as the judge will rebuild them",
         "prediction", ("micro.flow_bars", "bars.h1")),
)


def _paths() -> None:
    for p in (str(ROOT), str(DESK), str(DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)


def resolve(tool: Tool) -> Callable[..., Any]:
    _paths()
    module, _, qual = tool.target.partition(":")
    obj: Any = importlib.import_module(module)
    for part in qual.split("."):
        obj = getattr(obj, part)
    if not callable(obj):
        raise TypeError(f"{tool.target} is not callable")
    fn: Callable[..., Any] = obj
    return fn


def by_name(name: str) -> Tool:
    for t in TOOLS:
        if t.name == name:
            return t
    raise KeyError(f"no tool named {name!r}; known: {sorted(t.name for t in TOOLS)}")


def call(name: str, **kwargs: Any) -> Any:
    """Call a registered tool by name. Propose-only entries are the only callable kind."""
    tool = by_name(name)
    if tool.authority != PROPOSE_ONLY:
        raise PermissionError(f"{name}: authority {tool.authority!r}; only {PROPOSE_ONLY!r} tools "
                              "are callable from research or an LLM seat")
    unknown = set(kwargs) - set(tool.inputs)
    if unknown:
        raise TypeError(f"{name}: unknown inputs {sorted(unknown)}; declared {list(tool.inputs)}")
    return resolve(tool)(**kwargs)


def verify(tool: Tool, contracts: set[str] | None) -> dict[str, Any]:
    row: dict[str, Any] = asdict(tool)
    row["inputs"] = list(tool.inputs)
    row["contracts"] = list(tool.contracts)
    try:
        fn = resolve(tool)
    except Exception as exc:
        row.update({"status": "IMPORT_FAILED", "why": f"{type(exc).__name__}: {str(exc)[:160]}"})
        return row
    try:
        params = set(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        params = set()
    missing = [i for i in tool.inputs if params and i not in params]
    if missing:
        row.update({"status": "SIGNATURE_MISMATCH",
                    "why": f"declared inputs not in the signature: {missing}"})
        return row
    if contracts is not None:
        bad = [c for c in tool.contracts if c not in contracts]
        if bad:
            row.update({"status": "UNKNOWN_CONTRACT", "why": f"not registered in desk_hub: {bad}"})
            return row
    if tool.authority != PROPOSE_ONLY:
        row.update({"status": "AUTHORITY_REFUSED", "why": "registry tools are propose-only"})
        return row
    row["status"] = "OK"
    return row


def build() -> dict[str, Any]:
    _paths()
    try:
        from libs.data.datahub import desk_hub
        contracts: set[str] | None = set(desk_hub().contracts())
        hub_status = "OK"
    except Exception as exc:
        contracts, hub_status = None, f"UNMEASURED: {type(exc).__name__}: {exc}"
    rows = [verify(t, contracts) for t in TOOLS]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    names = [t.name for t in TOOLS]
    return {"schema": "tool_registry/1",
            "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "clock": "hourly_cycle:tool_registry", "authority": PROPOSE_ONLY,
            "datahub": hub_status, "datahub_contracts": sorted(contracts or []),
            "tools": len(rows), "ok": counts.get("OK", 0), "by_status": counts,
            "duplicate_names": sorted({n for n in names if names.count(n) > 1}),
            "rows": rows,
            "usage": "libs.research.tool_registry.call(name, **inputs); propose-only"}


def prompt_block(report: dict[str, Any] | None = None, max_chars: int = 6000) -> str:
    """The OK tools as a compact catalogue for a model's context. Read-only, propose-only."""
    rep = report or build()
    lines = ["DESK ANALYTICS TOOLS (propose-only; results are research input, never sizing):"]
    for r in rep.get("rows", []):
        if r.get("status") != "OK":
            continue
        c = f" reads {','.join(r['contracts'])}" if r.get("contracts") else ""
        lines.append(f"- {r['name']}({', '.join(r['inputs'])}) -> {r['outputs']}.{c} "
                     f"[{r['layer']}] {r['description']}")
    return "\n".join(lines)[:max_chars]


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="build and verify the analytics tool registry")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    rep = build()
    if not a.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
        try:
            tmp.replace(OUT)
        except PermissionError:
            OUT.write_text(tmp.read_text("utf-8"), "utf-8")
            tmp.unlink(missing_ok=True)
    print(f"TOOL REGISTRY  {rep['ok']}/{rep['tools']} OK  {rep['by_status']}  "
          f"datahub={rep['datahub']}")
    for r in rep["rows"]:
        if r["status"] != "OK":
            print(f"  {r['name']:<28} {r['status']}: {r.get('why', '')}")
    return 0 if rep["ok"] == rep["tools"] else 1
