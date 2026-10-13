#!/usr/bin/env python3
"""GATE -2 AND THE NO-LIMBO CELL STATE LEDGER: every docket cell has a state, a reason and an owner.

WHY. A cell that cannot be judged used to fail in one of three silent ways: it reached the sealed
judge and burned build time on a fault a dictionary lookup could have named (bars absent, a family
that does not resolve, a peer the broker never quoted); it was parked in the unrunnable bank and
waited for an event nobody was asked to cause; or it simply stayed "unjudged" with no record of
why. None of those is a verdict, and "waiting" with no named dependency is limbo.

GATE -2 (`gate_minus2`). Cheap, deterministic checks run on every docket row BEFORE the judge
spends build time, against data already on this host:

    duplicate          the same executable identity or judge cell twice in one docket, or one
                       genome_id under two different judge cells (a genome twin)
    pit                the row's point-in-time stamp (`libs.data.pit.is_stamped`) and whether its
                       `available_time` parses and is not in the future
    bars               the cell's OWN chart, and each named peer's chart, exists on this host
                       (`data/universe/<SYM>_<TF>.parquet`); the broker's skip ledger
                       (`bar_coverage_skips.json`) decides NOT_OFFERED vs repairable
    asset_mapping      the symbol and every named peer are MT5 instruments: in the registry
                       `data/universe/universe.json` (case-insensitive) or with a bar file here
    observations       an upper bound on the daily observations the chart can give:
                       min(bar rows, calendar span in days), read from the parquet footer only.
                       Under CPCV_MIN_DAYS (60) the cell cannot be judged however it fires
    costs              the registry's cost terms are finite (tick_size, tick_value > 0; spread
                       >= 0), and the net-edge spine's CONSERVATIVE `COST_DEAD` verdict (a
                       negative upper bound with every one-signed term priced)
    family             the family resolves in `mt5desk.families.live_family_names`
    inputs             a peer/driver/factor/triangle family names the instrument it needs
                       (judge_coverage.REQUIRED_INPUT_KEY, pinned to discovery_compiler)
    already_tested     the exact judge cell already carries a real verdict in the gate ledger

WHAT A VERDICT MAY DO. Only ROUTE. A HOLD is a repairable fault: the cell's state becomes
BLOCKED_DEPENDENCY with a named dependency and repair owner, and it enters the DEPENDENCY_QUEUE.
A would-be terminal becomes CONVERT (below) with its reason, conversion, owner, next
action and reopen conditions. Either way the
row gets a `prejudge.flags` entry (`gate_minus2:<check>`) so `prejudge_screen.demote_flagged` moves
it behind the clean rows of its OWN family -- the family-balanced prefix is unchanged, no row is
removed, no trial is charged, no gate is touched, and the flagged cell is still judged after its
clean siblings. An UNMEASURED check (the input is unreadable on this host) never flags.

THE LEDGER (`publish`). One state per cell, durable across passes:

    CREATED -> PREFLIGHT -> READY -> JUDGING -> JUDGED_PASS | JUDGED_FAIL   (the only absorbing)
                         -> BLOCKED_DEPENDENCY -> REPAIRING -> READY
                         -> CONVERT -> READY (the converted child, ranked by UnlockValue)

NO CELL EVER ENDS UNTESTABLE (principal, 2026-10-13). What used to be a terminal --
IMPOSSIBLE_TO_BUILD, INSUFFICIENT_PUBLIC_HISTORY, PIT_UNVERIFIABLE, NOT_MT5_EXPRESSIBLE,
DATA_SOURCE_PERMANENTLY_UNAVAILABLE, or a parked never-fires / too-rare bank cell -- is kept as
`convert_from`, and the cell enters CONVERT with a named `conversion_reason` (proxy_series,
coarser_timeframe, event_study_form, regime_child, cross_asset_transplant). The cells are
handed to the Breadth converter through `data/hypotheses/cell_convert_queue.json` (Breadth owns
the converter; nothing here converts), UNMEASURED_UNTIL_CONSUMED until the consumer acks in
`cell_convert_acks.json`. `--fence` fails when a cell sits in CONVERT past CONVERT_STALE_H.

Sources: the shipped docket (stamped above), the unrunnable bank (`judge_coverage`'s parked
cells, which never reach the docket while parked) and the gate ledger. JUDGING is the READY
prefix of the shipped docket inside the judge's measured hourly capacity. REPAIRING is a blocked
cell whose repair is being worked THIS hour: its chart is in the refresh_bars fetch list, or its
bank row is `readmit_due`.

THE INVARIANT: no potentially judgeable cell sits passively. Every BLOCKED_DEPENDENCY / REPAIRING
cell names its dependency and its repair owner; one that does not is counted, by name, in
`kpi.unexplained_waiting_cells`, whose target is 0.

THE DEPENDENCY RESOLVER. `UnlockValue(d)` = the summed priority of the cells blocked on d (a
cell's priority is its premortem survival probability when it carries one, else 1). The queue is
published ranked; `hourly_cycle.bars_wanted_symbols` reads its `bars` head (via
`bars_queue_symbols`) so the hour's targeted chart fetch goes where it unlocks the most, and
falls back to JUDGE_COVERAGE's parked-cell count when this report is absent or stale.

    python desks/mt5/research/cell_state.py --show       # print the KPIs of the last pass
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
SKIP_LEDGERS = (UNIVERSE / "bar_coverage_skips.json", UNIVERSE / "bar_coverage_targeted.json")
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
LEDGER = HYP / "cell_state_ledger.json"
REPORT = BASE / "reports" / "CELL_STATE.json"
#: THE HAND-OFF TO THE BREADTH CONVERTER. Breadth owns the converter and its fence; this ledger
#: only emits the queue. Until a consumer writes CONVERT_ACKS, the queue is
#: UNMEASURED_UNTIL_CONSUMED -- a list nobody has read is not a conversion.
CONVERT_QUEUE = HYP / "cell_convert_queue.json"
CONVERT_ACKS = HYP / "cell_convert_acks.json"
CONVERT_QUEUE_MAX = 20000

SCHEMA = "cell-state/1"
FLAG_PREFIX = "gate_minus2:"

CREATED, PREFLIGHT, READY, JUDGING = "CREATED", "PREFLIGHT", "READY", "JUDGING"
BLOCKED, REPAIRING = "BLOCKED_DEPENDENCY", "REPAIRING"
JUDGED_PASS, JUDGED_FAIL = "JUDGED_PASS", "JUDGED_FAIL"
#: NO CELL EVER ENDS UNTESTABLE (principal's standing rule, 2026-10-13 16:45Z). What would have
#: been a terminal "cannot be judged" verdict is recorded as the cell's `convert_from` and the
#: cell enters CONVERT: a conversion reason is named and the cell is handed to the Breadth
#: converter (`CONVERT_QUEUE`), whose converted child re-enters the judge queue ranked by
#: UnlockValue. The only absorbing states are the two JUDGED verdicts.
IMPOSSIBLE = "IMPOSSIBLE_TO_BUILD"
NO_HISTORY = "INSUFFICIENT_PUBLIC_HISTORY"
PIT_BAD = "PIT_UNVERIFIABLE"
NOT_MT5 = "NOT_MT5_EXPRESSIBLE"
NO_SOURCE = "DATA_SOURCE_PERMANENTLY_UNAVAILABLE"
CONVERT_FROM: tuple[str, ...] = (IMPOSSIBLE, NO_HISTORY, PIT_BAD, NOT_MT5, NO_SOURCE,
                                 "PARKED_UNRUNNABLE")
CONVERT = "CONVERT"
#: the converter's vocabulary: how an untestable-as-specified cell becomes a testable one
CONVERSIONS: tuple[str, ...] = ("proxy_series", "coarser_timeframe", "event_study_form",
                                "regime_child", "cross_asset_transplant")
CONVERTER_OWNER = "breadth_converter"
TERMINALS: tuple[str, ...] = (JUDGED_PASS, JUDGED_FAIL)
WAITING: tuple[str, ...] = (BLOCKED, REPAIRING, CONVERT)
STATES: tuple[str, ...] = (CREATED, PREFLIGHT, READY, JUDGING, BLOCKED, REPAIRING, CONVERT,
                           *TERMINALS)
#: the legal edges. Every state except a JUDGED verdict has an edge OUT of itself.
TRANSITIONS: dict[str, frozenset[str]] = {
    CREATED: frozenset({PREFLIGHT}),
    PREFLIGHT: frozenset({READY, BLOCKED, CONVERT}),
    READY: frozenset({JUDGING, PREFLIGHT, BLOCKED, CONVERT, *TERMINALS}),
    JUDGING: frozenset({JUDGED_PASS, JUDGED_FAIL, READY, BLOCKED, PREFLIGHT}),
    BLOCKED: frozenset({REPAIRING, READY, PREFLIGHT, CONVERT}),
    REPAIRING: frozenset({READY, BLOCKED, PREFLIGHT, CONVERT}),
    CONVERT: frozenset({READY, PREFLIGHT, BLOCKED}),      # the converted child re-enters
    **{t: frozenset({JUDGED_PASS, JUDGED_FAIL}) for t in TERMINALS},   # absorbing: re-verdict only
}
#: A cell in CONVERT longer than this with no consumer acting on it fails the fence.
CONVERT_STALE_H = 72.0

#: Same constant as judge_coverage.CPCV_MIN_DAYS (a test pins them together).
CPCV_MIN_DAYS = 60
#: Same constant as hourly_cycle.BARS_WANTED_PER_HOUR (a test pins them together).
BARS_PER_HOUR = 25
#: A report older than this is not steering anything; refresh_bars falls back.
STALE_AFTER_H = 6.0
#: The bars checks need a bar lake on this host: at least this share of the registry's H1 files.
MIN_LAKE_SHARE = 0.5
#: Report sizes (the box sync caps a report at 4 MB; this stays far under it).
QUEUE_TOP = 200
EXAMPLES = 3
HISTORY_KEEP = 48
PEER_KEYS: tuple[str, ...] = ("peer_symbol", "driver_symbol", "leg_b_symbol", "leg_c_symbol",
                              "factor_symbols")
#: What each repair owner IS, so a reader can find the organ.
OWNERS: dict[str, str] = {
    "refresh_bars": "hourly_cycle.refresh_bars -> fetch_universe --symbols (targeted charts)",
    "complete_inputs": "discovery_compiler.complete_inputs / family_input_descendants "
                       "(mints the twin that names the missing instrument)",
    "readmit": "judge_coverage.update_unrunnable_bank / readmit_due (re-admits on history "
               "growth, or after the retry window)",
    "build_failure_bank": "build_failure_bank (ranks the build fault as fix work); readmitted "
                          "after judge_coverage.BUILD_FAILED_RETRY_DAYS",
    "merge_hypotheses": "merge_hypotheses.recover_banked_provenance (canonical PIT stamper)",
    "external_gauntlet": "the sealed judge, through the twin's own docket row",
    "fusion_cost": "fusion_cost / cost_construction (the registry's cost terms)",
    "net_edge_spine": "net_edge_spine (donates the lower-turnover descendant of a COST_DEAD "
                      "cell)",
    "clock": "the cell becomes usable when its available_time passes",
    "universe_registry": "fetch_universe (the registry gains the symbol)",
    "family_registry": "mt5desk.families (the family resolves)",
    "breadth_converter": "the Breadth converter (owned by the Breadth session): consumes "
                         "data/hypotheses/cell_convert_queue.json and mints the converted child",
}


# ------------------------------------------------------------------------------------------------
# small readers
# ------------------------------------------------------------------------------------------------

def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(raw: object) -> datetime | None:
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        t = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).astimezone(UTC)


def _sym(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or row.get("sym") or "")


def _tf(row: Mapping[str, Any]) -> str:
    params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    return str((params or {}).get("timeframe") or row.get("timeframe") or "H1").upper()


def _peers(row: Mapping[str, Any]) -> list[str]:
    params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    out: list[str] = []
    for key in PEER_KEYS:
        v = (params or {}).get(key)
        if v is None or v == "":
            continue
        vals = v if isinstance(v, (list, tuple)) else str(v).split(",")
        out.extend(str(s).strip() for s in vals if str(s).strip())
    return out


def identity(row: Mapping[str, Any]) -> str:
    """merge_hypotheses._identity / prejudge_screen.identity, spelled once more."""
    params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    params = params or {}
    return json.dumps({"symbol": _sym(row), "family": str(row.get("family") or ""),
                       "params": {k: params[k] for k in sorted(params)}},
                      sort_keys=True, default=str)


def cell_of(row: Mapping[str, Any]) -> str | None:
    """The judge's own identity for a docket row, imported, never re-implemented."""
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research.frontier_identity import docket_cell_id
        return str(docket_cell_id(dict(row)))
    except Exception:
        return None


def priority(row: Mapping[str, Any]) -> float:
    """The weight a blocked cell adds to its dependency's unlock value."""
    pm = row.get("premortem") if isinstance(row.get("premortem"), Mapping) else None
    try:
        p = float((pm or {}).get("p_survivor"))
    except (TypeError, ValueError):
        return 1.0
    return p if math.isfinite(p) and 0.0 < p <= 1.0 else 1.0


# ------------------------------------------------------------------------------------------------
# the per-pass context: everything a check reads, read once
# ------------------------------------------------------------------------------------------------

class Context:
    """What Gate -2 reads, loaded once per pass. A source that cannot be read is UNMEASURED and
    the checks that need it never flag (L1.28a)."""

    def __init__(self, *, now: datetime | None = None, universe: Path | None = None,
                 gate_ledger: Path | None = None, live_families: Iterable[str] | None = None,
                 judged: Mapping[str, bool] | None = None) -> None:
        self.now = now or datetime.now(tz=UTC)
        self.universe = universe or UNIVERSE
        reg = _read(self.universe / REGISTRY.name)
        self.registry: dict[str, dict[str, Any]] = (
            {str(k): v for k, v in reg.items() if isinstance(v, dict)}
            if isinstance(reg, dict) else {})
        self.registry_upper = {k.upper(): k for k in self.registry}
        try:
            self.files = {p.name for p in self.universe.glob("*.parquet")}
        except OSError:
            self.files = set()
        self.bar_syms = {f.rsplit("_", 1)[0] for f in self.files}
        h1 = sum(1 for k in self.registry if f"{k}_H1.parquet" in self.files)
        self.lake = bool(self.registry) and h1 >= MIN_LAKE_SHARE * len(self.registry)
        self.skips: dict[str, str] = {}
        for p in SKIP_LEDGERS:
            doc = _read(self.universe / p.name)
            reasons = doc.get("reasons") if isinstance(doc, dict) else None
            if isinstance(reasons, dict):
                for s, r in reasons.items():
                    if isinstance(r, dict) and r.get("reason"):
                        self.skips[str(s).upper()] = str(r["reason"])
        self.families = (frozenset(live_families) if live_families is not None
                         else _live_families())
        self.judged: dict[str, bool] = (dict(judged) if judged is not None
                                        else judged_outcomes(gate_ledger or GATE_LEDGER))
        self._days: dict[tuple[str, str], int | None] = {}
        self.measured = {
            "registry": bool(self.registry), "bar_lake": self.lake,
            "skip_ledger": bool(self.skips) or any((self.universe / p.name).exists()
                                                   for p in SKIP_LEDGERS),
            "families": bool(self.families), "gate_ledger": bool(self.judged),
        }

    def has_bars(self, sym: str, tf: str) -> bool:
        return f"{sym}_{tf}.parquet" in self.files

    def expressible(self, sym: str) -> bool:
        return sym.upper() in self.registry_upper or sym in self.bar_syms

    def possible_days(self, sym: str, tf: str) -> int | None:
        """Upper bound on distinct days the chart holds, from the parquet footer alone."""
        key = (sym, tf)
        if key in self._days:
            return self._days[key]
        out: int | None = None
        try:
            import pyarrow.parquet as pq
            meta = pq.ParquetFile(self.universe / f"{sym}_{tf}.parquet").metadata
            rows = int(meta.num_rows)
            lo = hi = None
            names = [meta.schema.column(j).name for j in range(meta.num_columns)]
            if "time" in names:
                j = names.index("time")
                for g in range(meta.num_row_groups):
                    st = meta.row_group(g).column(j).statistics
                    if st is None or not st.has_min_max:
                        lo = hi = None
                        break
                    lo = st.min if lo is None or st.min < lo else lo
                    hi = st.max if hi is None or st.max > hi else hi
            if lo is not None and hi is not None:
                out = min(rows, int((hi - lo).total_seconds() // 86400) + 1)
            elif tf == "D1":
                out = rows
        except Exception:
            out = None
        self._days[key] = out
        return out


def _live_families() -> frozenset[str]:
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from mt5desk.families import live_family_names
        return frozenset(live_family_names())
    except Exception:
        return frozenset()


def judged_outcomes(path: Path) -> dict[str, bool]:
    """cell -> passed, over the gate ledger, with judge_coverage.judged_index's own filter: a
    NOT_RUN deferral or an UNKNOWN without a pass is not a verdict. The LAST verdict wins."""
    out: dict[str, bool] = {}
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            if '"cell"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or not row.get("cell"):
                continue
            if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
                continue
            passed = row.get("passed") is True
            if not passed and str(row.get("terminal_gate") or "") in ("", "UNKNOWN"):
                continue
            out[str(row["cell"])] = passed
    return out


# ------------------------------------------------------------------------------------------------
# Gate -2
# ------------------------------------------------------------------------------------------------

def _hold(check: str, reason: str, dep: str, owner: str, action: str,
          reopen: list[str]) -> dict[str, Any]:
    return {"check": check, "verdict": "HOLD", "state": BLOCKED, "reason": reason,
            "dependency": dep, "owner": owner, "next_action": action,
            "reopen_conditions": reopen}


def _terminal(check: str, convert_from: str, conversion: str, reason: str, owner: str,
              action: str, reopen: list[str]) -> dict[str, Any]:
    """What used to be a terminal: now CONVERT, with the would-be terminal kept as
    `convert_from`, a named conversion, and the Breadth converter as the owner. The organ that
    would have reopened it (`origin_owner`) and its reopen conditions are kept beside."""
    return {"check": check, "verdict": CONVERT, "state": CONVERT, "reason": reason,
            "convert_from": convert_from, "conversion_reason": conversion,
            "dependency": f"convert:{conversion}", "owner": CONVERTER_OWNER,
            "origin_owner": owner,
            "next_action": f"convert by {conversion} (Breadth converter queue); {action}",
            "reopen_conditions": [*reopen, "the converted child is judged"]}


def _bars_missing(sym: str, tf: str, ctx: Context, *, peer: bool) -> dict[str, Any]:
    who = "peer " if peer else ""
    skip = ctx.skips.get(sym.upper())
    if skip == "NOT_OFFERED":
        return _terminal("bars", NO_SOURCE, "cross_asset_transplant",
                         f"{who}{sym} has no {tf} bars and the broker does not quote it "
                         "(fetch_universe skip ledger: NOT_OFFERED)", "universe_registry",
                         "none until the broker lists the symbol",
                         [f"{sym} leaves the NOT_OFFERED skip ledger",
                          f"{sym}_{tf}.parquet appears on this host"])
    if skip == "INSUFFICIENT_HISTORY":
        return _terminal("bars", NO_HISTORY, "proxy_series",
                         f"{who}{sym} has no {tf} bars: the broker's history is below the "
                         "walk-forward minimum (skip ledger: INSUFFICIENT_HISTORY)",
                         "refresh_bars", "re-fetched as the symbol ages",
                         [f"{sym}_{tf}.parquet appears on this host",
                          f"{sym} leaves the INSUFFICIENT_HISTORY skip ledger"])
    return _hold("bars", f"{who}{sym} has no {tf} bar file on this host", f"bars:{sym}_{tf}",
                 "refresh_bars", f"fetch {sym} (fetch_universe --symbols {sym})",
                 [f"{sym}_{tf}.parquet appears on this host"])


def gate_minus2(row: Mapping[str, Any], ctx: Context, *,
                seen: dict[str, str] | None = None,
                genomes: dict[str, str] | None = None,
                cell: str | None = None) -> list[dict[str, Any]]:
    """Every Gate -2 verdict this row earns, most binding first. [] means the row is clean.

    `seen` / `genomes` carry the duplicate check across one pass (identity or cell -> the first
    cell that claimed it; genome_id -> its first cell). Pure apart from them.
    """
    out: list[dict[str, Any]] = []
    sym, tf, fam = _sym(row), _tf(row), str(row.get("family") or "")
    # family: the implementation must resolve, or the judge can only fail to build it
    if ctx.families and fam not in ctx.families:
        out.append(_terminal("family", IMPOSSIBLE, "event_study_form",
                             f"family {fam!r} does not resolve in mt5desk.families on this host",
                             "family_registry", "implement or register the family",
                             [f"{fam} appears in live_family_names()"]))
    # asset mapping: the symbol and every named peer must be MT5 instruments
    if ctx.registry:
        for s in [sym, *_peers(row)]:
            if s and not ctx.expressible(s):
                out.append(_terminal("asset_mapping", NOT_MT5,
                                     "cross_asset_transplant",
                                     f"{s} is not in the MT5 universe registry and has no bar "
                                     "file here", "universe_registry",
                                     "map the instrument to an MT5 symbol or re-mint the cell",
                                     [f"{s} appears in data/universe/universe.json"]))
                break
    # pit: the stamp must exist and say when the row became knowable
    try:
        from libs.data.pit import is_stamped
        if not is_stamped(dict(row)):
            out.append(_hold("pit", "the row carries no complete point-in-time stamp",
                             "pit:stamp", "merge_hypotheses",
                             "re-stamp through recover_banked_provenance",
                             ["available_time, ingested_time, source_version and payload_hash "
                              "are present"]))
        else:
            avail = _ts(row.get("available_time"))
            if avail is None:
                out.append(_terminal("pit", PIT_BAD, "proxy_series",
                                     "available_time does not parse, so when this row became "
                                     "knowable cannot be verified", "merge_hypotheses",
                                     "the producer re-emits the row with a valid stamp",
                                     ["available_time parses as ISO-8601"]))
            elif (avail - ctx.now).total_seconds() > 300:
                out.append(_hold("pit", "available_time is in the future", "pit:available_time",
                                 "clock", "wait for available_time",
                                 [f"now >= {avail.isoformat(timespec='seconds')}"]))
    except ImportError:
        pass
    # duplicate / genome twin: the docket's first copy is judged; this one rides on it
    if seen is not None and cell:
        first = seen.get(cell) or seen.get(identity(row))
        if first is not None:
            out.append(_hold("duplicate", f"the same judge cell is already in this docket "
                                          f"({first})", f"twin:{first}", "external_gauntlet",
                             "judged through its first copy",
                             ["the first copy leaves the docket"]))
        else:
            seen[cell] = cell
            seen[identity(row)] = cell
    gid = str(row.get("genome_id") or "")
    if genomes is not None and gid and cell:
        other = genomes.setdefault(gid, cell)
        if other != cell:
            out.append(_hold("duplicate", f"genome {gid} is already in this docket as {other}",
                             f"twin:{other}", "external_gauntlet",
                             "judged through its genome twin",
                             ["the twin leaves the docket", "the genome ids diverge"]))
    # inputs: a peer/driver/factor/triangle family must name its other instrument
    need = _required_input(fam)
    params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    if need and not (params or {}).get(need):
        out.append(_hold("inputs", f"{fam} trades against a second instrument and this cell "
                                   f"names no {need}, so it can fire nowhere",
                         f"input:{fam}.{need}", "complete_inputs",
                         "its twin with the input named is minted by complete_inputs",
                         [f"params.{need} is set"]))
    # bars + observations: the cell's own chart and each peer's
    if ctx.lake and sym:
        if not ctx.has_bars(sym, tf):
            out.append(_bars_missing(sym, tf, ctx, peer=False))
        else:
            days = ctx.possible_days(sym, tf)
            if days is not None and days < CPCV_MIN_DAYS:
                out.append(_terminal("observations", NO_HISTORY,
                                     "proxy_series",
                                     f"{sym}_{tf} spans at most {days} day(s); CPCV needs "
                                     f"{CPCV_MIN_DAYS} daily observations",
                                     "refresh_bars", "re-judged as the history grows",
                                     [f"{sym}_{tf} spans >= {CPCV_MIN_DAYS} days"]))
        for p in _peers(row):
            canon = ctx.registry_upper.get(p.upper(), p)
            if ctx.expressible(p) and not ctx.has_bars(canon, tf) \
                    and not ctx.has_bars(canon, "H1"):
                out.append(_bars_missing(canon, tf, ctx, peer=True))
                break
    # costs: finite cost terms, and the spine's conservative COST_DEAD
    meta = ctx.registry.get(sym) or ctx.registry.get(ctx.registry_upper.get(sym.upper(), ""))
    if isinstance(meta, dict):
        bad = []
        for k in ("tick_size", "tick_value"):
            try:
                v = float(meta.get(k))
                if not math.isfinite(v) or v <= 0:
                    bad.append(k)
            except (TypeError, ValueError):
                bad.append(k)
        try:
            sp = float(meta.get("median_spread_pts"))
            if not math.isfinite(sp) or sp < 0:
                bad.append("median_spread_pts")
        except (TypeError, ValueError):
            bad.append("median_spread_pts")
        if bad:
            out.append(_hold("costs", f"{sym}'s registry cost terms are not finite: "
                                      f"{', '.join(bad)}", f"cost_terms:{sym}", "fusion_cost",
                             "re-measure the instrument's cost terms",
                             [f"{', '.join(bad)} finite and positive in universe.json"]))
    if str(row.get("net_verdict") or "") == "COST_DEAD":
        out.append(_hold("costs", "the net-edge spine's conservative bound is negative after "
                                  "costs on this (symbol, family)",
                         f"net_edge_descendant:{sym}|{fam}", "net_edge_spine",
                         "the lower-turnover descendant is donated through the net_edge seat",
                         ["net_verdict leaves COST_DEAD on data/net_edge_ranks.json"]))
    terminal_first = sorted(out, key=lambda v: 0 if v["state"] == CONVERT else 1)
    return terminal_first


def _required_input(fam: str) -> str | None:
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research.judge_coverage import REQUIRED_INPUT_KEY
        return REQUIRED_INPUT_KEY.get(fam)
    except Exception:
        return None


def stamp(rows: list[dict[str, Any]], ctx: Context | None = None
          ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Stamp every row with its Gate -2 state and flag the HOLDs and terminals. Same rows, same
    order, same count; `prejudge.flags` gains `gate_minus2:<check>` entries (existing flags are
    kept). Returns (rows, summary)."""
    ctx = ctx or Context()
    at = ctx.now.isoformat(timespec="seconds")
    seen: dict[str, str] = {}
    genomes: dict[str, str] = {}
    by_check: Counter[str] = Counter()
    by_state: Counter[str] = Counter()
    flagged = 0
    for row in rows:
        cell = cell_of(row)
        verdicts = gate_minus2(row, ctx, seen=seen, genomes=genomes, cell=cell)
        judged = ctx.judged.get(cell) if cell else None
        if verdicts:
            top = verdicts[0]
            keep = ("state", "reason", "dependency", "owner", "next_action",
                    "reopen_conditions", "convert_from", "conversion_reason", "origin_owner")
            stamp_: dict[str, Any] = {k: top[k] for k in keep if k in top}
            stamp_["check"] = top["check"]
            stamp_["checks"] = sorted({v["check"] for v in verdicts})
            flags = [f"{FLAG_PREFIX}{c}" for c in stamp_["checks"]]
            pj = dict(row["prejudge"]) if isinstance(row.get("prejudge"), Mapping) else {}
            pj["flags"] = list(dict.fromkeys([*(pj.get("flags") or []), *flags]))
            row["prejudge"] = pj
            flagged += 1
            for c in stamp_["checks"]:
                by_check[c] += 1
        elif judged is not None:
            stamp_ = {"state": JUDGED_PASS if judged else JUDGED_FAIL,
                      "reason": "this exact judge cell already carries a verdict in the gate "
                                "ledger (identical mechanism already tested)",
                      "owner": "external_gauntlet",
                      "next_action": "none; judge_coverage orders it after unjudged cells",
                      "reopen_conditions": ["judge_coverage re-asks judged cells as history "
                                            "grows"]}
            by_check["already_tested"] += 1
        else:
            stamp_ = {"state": READY}
        stamp_["at"] = at
        if cell:
            stamp_["cell"] = cell
        row["cell_state"] = stamp_
        by_state[stamp_["state"]] += 1
    return rows, {"rows": len(rows), "flagged": flagged, "by_check": dict(sorted(by_check.items())),
                  "by_state": dict(sorted(by_state.items())), "measured": ctx.measured,
                  "unmeasured_checks": unmeasured_checks(ctx)}


def unmeasured_checks(ctx: Context) -> list[str]:
    """Checks that could not run on this host, by name: never a clean pass."""
    out = []
    if not ctx.registry:
        out += ["asset_mapping", "costs:registry"]
    if not ctx.lake:
        out += ["bars", "observations"]
    if not ctx.families:
        out.append("family")
    if not ctx.judged:
        out.append("already_tested")
    return out


# ------------------------------------------------------------------------------------------------
# the ledger, the dependency queue and the KPIs
# ------------------------------------------------------------------------------------------------

#: A parked cell untestable AS SPECIFIED is converted, never left parked; readmit_due still
#: re-admits the original on history growth in parallel. Build faults, missing charts and
#: missing inputs are repairable HOLDs with their own owners, not conversions.
BANK_CONVERSION: dict[str, str] = {"never_fires": "coarser_timeframe",
                                   "too_rare": "event_study_form",
                                   "lockbox_consumed_history": "proxy_series",
                                   "short_history_after_cut": "proxy_series"}


def _bank_entry(cell: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """A parked unrunnable-bank cell as a ledger entry with its dependency and owner."""
    reason = str(row.get("reason") or "")
    sym, tf, fam = str(row.get("sym") or ""), str(row.get("tf") or "H1"), str(row.get("family")
                                                                             or "")
    if reason == "data_missing":
        dep, owner = f"bars:{sym}_{tf}", "refresh_bars"
    elif reason in ("build_failed", "series_exception"):
        dep, owner = f"code:{fam}", "build_failure_bank"
    elif reason in BANK_CONVERSION:
        conv = BANK_CONVERSION[reason]
        return {"state": CONVERT, "reason": f"unrunnable bank: {reason}",
                "dependency": f"convert:{conv}", "owner": CONVERTER_OWNER,
                "origin_owner": "readmit", "convert_from": "PARKED_UNRUNNABLE",
                "conversion_reason": conv, "priority": 1.0,
                "since": str(row.get("parked_at") or ""), "source": "unrunnable_bank",
                "check": reason, "sym": sym, "tf": tf, "family": fam}
    elif reason == "missing_identity_input":
        dep, owner = f"input:{fam}", "complete_inputs"
    else:
        dep, owner = None, None
    return {"state": BLOCKED, "reason": f"unrunnable bank: {reason or 'unnamed'}",
            "dependency": dep, "owner": owner, "priority": 1.0,
            "since": str(row.get("parked_at") or ""), "source": "unrunnable_bank",
            "check": reason or "unnamed"}


def bars_queue_symbols(doc: Mapping[str, Any] | None, limit: int = BARS_PER_HOUR,
                       *, now: datetime | None = None) -> list[str]:
    """The symbols the dependency queue's `bars` head unlocks most, best first. [] when the
    report is absent, unmeasured or older than STALE_AFTER_H (the caller then falls back)."""
    if not isinstance(doc, Mapping):
        return []
    at = _ts(doc.get("at"))
    t = now or datetime.now(tz=UTC)
    if at is None or (t - at).total_seconds() > STALE_AFTER_H * 3600:
        return []
    by_sym: dict[str, float] = {}
    for d in doc.get("dependency_queue") or []:
        if not isinstance(d, Mapping) or d.get("kind") != "bars":
            continue
        sym = str(d.get("key") or "").rsplit("_", 1)[0].strip()
        if sym:
            by_sym[sym] = by_sym.get(sym, 0.0) + float(d.get("unlock_value") or 0.0)
    return [s for s, _ in sorted(by_sym.items(), key=lambda kv: (-kv[1], kv[0]))][:limit]


def build(rows: list[dict[str, Any]], *, bank: Mapping[str, Mapping[str, Any]],
          prior: Mapping[str, Any] | None, capacity: int = 0,
          readmit: Mapping[str, bool] | None = None,
          now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """(new ledger, report). Pure: the caller reads and writes."""
    t = now or datetime.now(tz=UTC)
    at = t.isoformat(timespec="seconds")
    prior_cells: dict[str, Any] = dict((prior or {}).get("cells") or {})
    entries: dict[str, dict[str, Any]] = {}
    ready_seen: set[str] = set()
    for i, row in enumerate(rows):
        cs = row.get("cell_state") if isinstance(row.get("cell_state"), Mapping) else None
        cell = str((cs or {}).get("cell") or "")
        if not cell or cs is None or cell in entries:
            continue                       # a twin's second copy: the first copy's state holds
        state = str(cs.get("state") or READY)
        if state == READY:
            if capacity and i < capacity:
                state = JUDGING
            ready_seen.add(cell)
            entries[cell] = {"state": state}
            continue
        entries[cell] = {"state": state, "reason": cs.get("reason"),
                         "dependency": cs.get("dependency"), "owner": cs.get("owner"),
                         "priority": priority(row), "source": "docket",
                         "check": cs.get("check") or (
                             "already_tested" if state in (JUDGED_PASS, JUDGED_FAIL) else "")}
        if state == CONVERT:
            entries[cell].update(convert_from=cs.get("convert_from"),
                                 conversion_reason=cs.get("conversion_reason"),
                                 sym=_sym(row), tf=_tf(row), family=row.get("family"),
                                 params=row.get("params"))
    for cell, brow in bank.items():
        if cell in entries or not isinstance(brow, Mapping):
            continue
        e = _bank_entry(str(cell), brow)
        if readmit and readmit.get(cell) and e["dependency"] and e["state"] == BLOCKED:
            e["state"] = REPAIRING
        entries[str(cell)] = e
    # the dependency queue, before REPAIRING is decided for the bars head
    queue: dict[str, dict[str, Any]] = {}
    for cell, e in entries.items():
        if e["state"] not in WAITING or not e.get("dependency"):
            continue
        dep = str(e["dependency"])
        kind, _, key = dep.partition(":")
        q = queue.setdefault(dep, {"dependency": dep, "kind": kind, "key": key,
                                   "owner": e.get("owner"), "cells": 0, "unlock_value": 0.0,
                                   "examples": []})
        q["cells"] += 1
        q["unlock_value"] += float(e.get("priority") or 1.0)
        if len(q["examples"]) < EXAMPLES:
            q["examples"].append(cell)
    ranked = sorted(queue.values(), key=lambda q: (-q["unlock_value"], q["dependency"]))
    for q in ranked:
        q["unlock_value"] = round(q["unlock_value"], 4)
    head_syms = set(bars_queue_symbols({"at": at, "dependency_queue": ranked}, now=t))
    for e in entries.values():
        dep = str(e.get("dependency") or "")
        if e["state"] == BLOCKED and dep.startswith("bars:") \
                and dep[5:].rsplit("_", 1)[0] in head_syms:
            e["state"] = REPAIRING
    # since: carried while a cell stays in the same state family
    cells_out: dict[str, Any] = {}
    unlocked = converted = 0
    transitions: Counter[str] = Counter()
    for cell, e in entries.items():
        before = prior_cells.get(cell)
        b_state = before[0] if isinstance(before, list) and before else None
        if b_state is not None and b_state != e["state"]:
            transitions[f"{b_state}->{e['state']}"] += 1
        if b_state in WAITING and e["state"] in (READY, JUDGING, JUDGED_PASS, JUDGED_FAIL):
            unlocked += 1
        if b_state != CONVERT and e["state"] == CONVERT:
            converted += 1
        if e["state"] in (READY, JUDGING, JUDGED_PASS, JUDGED_FAIL):
            continue                                  # not persisted: the docket/ledger hold it
        # BLOCKED <-> REPAIRING keeps its clock; CONVERT starts its own at the hand-off, so the
        # staleness fence measures the converter's latency, not the cell's parked history
        same_family = b_state is not None and (
            b_state == e["state"] or ({b_state, e["state"]} <= {BLOCKED, REPAIRING}))
        if same_family and isinstance(before, list) and len(before) > 1:
            since = before[1]
        elif e["state"] == CONVERT:
            since = at
        else:
            since = e.get("since") or at
        cells_out[cell] = [e["state"], since, e.get("dependency"), e.get("owner"),
                           e.get("check")]
        e["since"] = since
    left = sum(1 for c, v in prior_cells.items()
               if c not in entries and isinstance(v, list) and v and v[0] in WAITING)
    prior_at = _ts((prior or {}).get("at"))
    hours = (t - prior_at).total_seconds() / 3600.0 if prior_at else None
    waiting = [(c, e) for c, e in entries.items() if e["state"] in WAITING]
    unexplained = [c for c, e in waiting if not e.get("dependency") or not e.get("owner")]
    oldest = min(waiting, key=lambda ce: str(ce[1].get("since") or at), default=None)
    oldest_doc = None
    if oldest is not None:
        o_at = _ts(oldest[1].get("since"))
        oldest_doc = {"cell": oldest[0], "since": oldest[1].get("since"),
                      "age_h": round((t - o_at).total_seconds() / 3600.0, 2) if o_at else None,
                      "dependency": oldest[1].get("dependency"), "owner": oldest[1].get("owner"),
                      "reason": oldest[1].get("reason")}
    states = Counter(e["state"] for e in entries.values())
    converting = [(c, e) for c, e in entries.items() if e["state"] == CONVERT]
    stale = []
    for c, e in converting:
        s_at = _ts(e.get("since"))
        if s_at is not None and (t - s_at).total_seconds() > CONVERT_STALE_H * 3600:
            stale.append(c)
    convert_rows = sorted(
        ({"cell": c, "symbol": e.get("sym"), "family": e.get("family"), "timeframe": e.get("tf"),
          "params": e.get("params"), "convert_from": e.get("convert_from"),
          "conversion_reason": e.get("conversion_reason"), "reason": e.get("reason"),
          "unlock_value": round(float(e.get("priority") or 1.0), 4), "since": e.get("since"),
          "source": e.get("source")} for c, e in converting),
        key=lambda r: (-float(r["unlock_value"] or 0.0), str(r["since"] or ""), str(r["cell"])))
    blocked_by_reason = Counter(str(e.get("check") or "unnamed") for _, e in waiting)
    rate = round(unlocked / hours, 4) if hours and hours > 0 and prior_cells else None
    history = list((prior or {}).get("history") or [])[-(HISTORY_KEEP - 1):]
    history.append({"at": at, "unlocked": unlocked, "waiting": len(waiting),
                    "ready": states.get(READY, 0) + states.get(JUDGING, 0)})
    ledger = {"schema": SCHEMA, "at": at, "cells": cells_out, "history": history,
              "fields": ["state", "since", "dependency", "owner", "check"]}
    report = {
        "schema": SCHEMA, "at": at,
        "kpi": {
            "unexplained_waiting_cells": len(unexplained),
            "unexplained_examples": unexplained[:10],
            "oldest_blocked": oldest_doc,
            "blocked_by_reason": dict(blocked_by_reason.most_common()),
            "waiting": len(waiting),
            "repairing": states.get(REPAIRING, 0),
            "unlocked_last_pass": unlocked if prior_cells else None,
            "unlocked_per_hour": rate,
            "hours_since_prior_pass": round(hours, 3) if hours is not None else None,
            "converted_last_pass": converted if prior_cells else None,
            "convert": states.get(CONVERT, 0),
            "convert_stale": len(stale),
            "convert_stale_bound_h": CONVERT_STALE_H,
            "left_without_verdict_last_pass": left if prior_cells else None,
            "target": "unexplained_waiting_cells == 0",
        },
        "states": {s: states.get(s, 0) for s in STATES},
        "terminals_by_state": {s: states.get(s, 0) for s in TERMINALS},
        "convert": {
            "by_conversion": dict(Counter(str(e.get("conversion_reason"))
                                          for _, e in converting).most_common()),
            "by_convert_from": dict(Counter(str(e.get("convert_from"))
                                            for _, e in converting).most_common()),
            "stale_examples": stale[:10],
            "fence": "FAIL" if stale else ("PASS" if converting else "PASS_EMPTY"),
            "rule": ("no cell ends untestable: every would-be terminal is CONVERT with a named "
                     "conversion, handed to the Breadth converter; a cell in CONVERT longer "
                     f"than {CONVERT_STALE_H:.0f}h fails the fence"),
        },
        "transitions_last_pass": dict(transitions.most_common(40)),
        "dependency_queue": ranked[:QUEUE_TOP],
        "dependency_queue_size": len(ranked),
        "dependency_kinds": dict(Counter(q["kind"] for q in ranked).most_common()),
        "capacity_basis": {"capacity_measured": capacity,
                           "rule": "JUDGING = the READY rows inside the judge's measured hourly "
                                   "capacity prefix of the shipped docket"},
        "owners": OWNERS,
        "_convert_queue": convert_rows,
        "history": history[-24:],
        "rule": ("Gate -2 only routes: a HOLD or terminal row is flagged and demoted inside its "
                 "own family, never removed, never billed a trial; every waiting cell names its "
                 "dependency and repair owner"),
    }
    return ledger, report


def publish(rows: list[dict[str, Any]], *, ledger_path: Path | None = None,
            report_path: Path | None = None, capacity: int = 0,
            bank: Mapping[str, Mapping[str, Any]] | None = None,
            now: datetime | None = None, gate2: Mapping[str, Any] | None = None
            ) -> dict[str, Any]:
    """Read the prior ledger and the unrunnable bank, build, write both. Returns the KPIs."""
    lp, rp = ledger_path or LEDGER, report_path or REPORT
    t = now or datetime.now(tz=UTC)
    readmit: dict[str, bool] = {}
    if bank is None:
        bank, readmit = _bank_with_readmit(t)
    prior = _read(lp)
    ledger, report = build(rows, bank=bank, prior=prior if isinstance(prior, dict) else None,
                           capacity=capacity, readmit=readmit, now=t)
    qrows = report.pop("_convert_queue", [])
    qp = lp.parent / CONVERT_QUEUE.name
    acks = _read(lp.parent / CONVERT_ACKS.name)
    consumed_at = _ts(acks.get("consumed_at")) if isinstance(acks, dict) else None
    consumer = ("CONSUMING" if consumed_at is not None
                and (t - consumed_at).total_seconds() <= CONVERT_STALE_H * 3600
                else "UNMEASURED_UNTIL_CONSUMED")
    report["convert"].update(queue=str(qp.name), queue_rows=len(qrows), consumer=consumer,
                             consumer_last_ack=consumed_at.isoformat() if consumed_at else None)
    queue_doc = {
        "schema": "cell-convert-queue/1", "at": report["at"], "status": consumer,
        "rows_total": len(qrows), "rows": qrows[:CONVERT_QUEUE_MAX],
        "producer": "desks/mt5/research/cell_state.py (Gate -2 / no-limbo ledger)",
        "consumer": "the Breadth converter (Breadth session owns it and its fence)",
        "contract": ("each row is a cell untestable AS SPECIFIED, with `convert_from` (the "
                     "terminal it would have been) and `conversion_reason` (one of "
                     f"{list(CONVERSIONS)}). The consumer mints the converted child into the "
                     "docket, where it is judged ranked by `unlock_value`, and writes "
                     f"{CONVERT_ACKS.name} = {{\"consumed_at\": <iso>, \"cells\": [...]}}. "
                     "Rows are rewritten every pass and never deleted from the ledger"),
        "conversions": list(CONVERSIONS),
    }
    report.pop("_convert_queue", None)
    if gate2 is not None:
        report["gate_minus2"] = dict(gate2)
    for path, doc, indent in ((lp, ledger, None), (qp, queue_doc, None), (rp, report, 1)):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=indent, default=str), "utf-8")
        os.replace(tmp, path)
    return dict(report["kpi"])


def _bank_with_readmit(now: datetime) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research import judge_coverage as jc
        bank = jc.unrunnable_bank()
        sizes: dict[tuple[str, str], int] = {}
        return bank, {c: bool(jc.readmit_due(r, now=now, bar_sizes=sizes))
                      for c, r in bank.items()}
    except Exception:
        return {}, {}


def fence(doc: Mapping[str, Any] | None) -> list[str]:
    """THE CONVERSION STALENESS FENCE: a problem per breach, [] when clean. A cell sitting in
    CONVERT past CONVERT_STALE_H fails; so does a waiting cell with no dependency or owner.
    An absent report is UNMEASURED and is returned as no problem (the caller says so)."""
    if not isinstance(doc, Mapping):
        return []
    kpi = doc.get("kpi") if isinstance(doc.get("kpi"), Mapping) else {}
    out = []
    stale = int((kpi or {}).get("convert_stale") or 0)
    if stale:
        ex = ((doc.get("convert") or {}).get("stale_examples") or [])[:3]
        out.append(f"{stale} cell(s) in CONVERT longer than {CONVERT_STALE_H:.0f}h with no "
                   f"converted child judged (e.g. {ex}); consumer status "
                   f"{(doc.get('convert') or {}).get('consumer')}")
    unexplained = int((kpi or {}).get("unexplained_waiting_cells") or 0)
    if unexplained:
        out.append(f"{unexplained} waiting cell(s) name no dependency or repair owner")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", action="store_true", help="print the last pass's KPIs")
    ap.add_argument("--fence", action="store_true",
                    help="exit 1 when a cell sits in CONVERT past the staleness bound")
    args = ap.parse_args(argv)
    doc = _read(REPORT)
    if args.fence:
        if not isinstance(doc, dict):
            print("cell_state fence: UNMEASURED -- no CELL_STATE.json on this host")
            return 0
        problems = fence(doc)
        for p in problems:
            print(f"  FAIL: {p}")
        print("cell_state fence: " + ("FAILED" if problems else "OK"))
        return 1 if problems else 0
    if not isinstance(doc, dict):
        print("cell_state: UNMEASURED -- no CELL_STATE.json yet (merge_hypotheses writes it)")
        return 0
    print(json.dumps({"at": doc.get("at"), "kpi": doc.get("kpi"), "states": doc.get("states")},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
