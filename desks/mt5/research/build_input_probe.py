"""Will the judge's build of this cell fail for want of an input this host does not hold?

A library of `research/judge_coverage.py` (it runs inside that organ's hourly pass, the docket
funnel). The read-only census over the docket on this host, from the repository root:

    python -c "import sys; sys.path[:0] = ['desks/mt5', '.']; \
               from research.build_input_probe import census; census()"

WHY (2026-10-22). A never-judged cell whose build fails is never stamped seen and never gets a
verdict, so the sealed judge sorts it to the FRONT of every sweep (`_is_new` is its first key)
and its pre-warm pool tries the same build again. When the pool, not the serial loop, finds the
failure, the cell has no cache file when the budget runs out and is recorded
NOT_RUN_BUILD_BUDGET_DEFERRED -- so `judge_coverage`, which parks NOT_RUN_BUILD_FAILED rows by
name, never sees it either. Measured on the box: `prewarm_fail_share` 0.589 on the last sweep
(JUDGE_COVERAGE.json totals), against a build-failure rate of 31 in 658 attempted cells (4.7%)
in the same day's random census of the docket (UNKNOWN_SHARE_CENSUS.json): the head of the
judge's order is saturated by the same failing cells, sweep after sweep. The judge is sealed;
its memo for this is still riding a reseal. Re-ordering the docket does not help either: the
judge re-sorts every row by its own keys, so only MEMBERSHIP of the docket reaches its pool.

WHAT THIS DOES. It names, BEFORE the docket ships, the cells whose `external_gauntlet.build_cell`
must refuse because an input it loads by name is ABSENT on this host, and nothing else:

  * a peer, factor, triangle leg, lead_lag driver or usd_session_shock FX driver whose
    `<SYM>_<TF>.parquet` does not exist under the bar store `orthogonal_sweep._bars` reads
    (that loader has no terminal fallback: `if not path.exists(): return None`);
  * an execution_state symbol absent from a NON-EMPTY published microstructure surface map;
  * a raw-COT family on a symbol with no COT mapping (`load_cot` raises KeyError) or whose
    mapped COT file is absent.

`judge_coverage` parks each named cell in the unrunnable bank as `build_input_missing`, with the
inputs it lacks, and re-admits it the pass every named input is present again (or after
READMIT_MAX_DAYS, like every parked cell). THE BACKSTOP REALLY FIRES (audit of 9bf6542be, M1):
a row parked READMIT_MAX_DAYS ago is no longer restated, so the bank's age clock releases it,
and a released cell is not re-named until the judge has RULED on it (v1.2: it is judged, or the
judge wrote a bank row for it after the release) -- it goes to the judge, however long the judge
takes, and the judge's own word on it (a verdict, or its own build failure) stands. That is the
only guard against this probe drifting from the sealed builder, so it must be reachable in the
real flow. A torn release file is set aside and read UNMEASURED: no hold is dropped, nothing new
is parked, and nothing is written over it until it is resolved by hand. BY DESIGN, a cell that
leaves the docket after day 90 loses its hold and may be parked again if it comes back.

COMPACT ROWS (audit S3). A parked row carries only what re-admission and the converter read:
the reason, the cell's symbol/family/chart, its own chart's size, and the missing inputs as
short labels (`bars:EURUSD_H1.parquet`, `surface:XAUUSD`, `cot_mapping:SYM`, `cot_file:F`).

The bank keeps every row; the coverage table and `judging_failures.parked` count them by
reason, and they stay in the unjudged backlog (a DEFECT class: the desk still owes the input),
so no backlog number moves by parking.

EXACT, OR SILENT. A cell is named only when the probe can prove the refusal:
  * its own chart and H1 file are present, its symbol is in the registry and tradeable, and its
    mechanism passes `economic_prior` -- so the judge would not reject it at gate 0 instead (and
    the probe never calls the MT5 terminal fallback the judge uses for an absent own chart);
  * the judge's own `modifier_preflight` passes -- a cell it refuses there costs no worker and
    keeps the judge's own disposition;
  * every global input it reads is readable and non-empty (an absent surface map or registry is
    UNMEASURED, never "every cell lacks it").
Anything else -- an unprobed family, an exception, a malformed identity -- is UNMEASURED and the
cell goes to the judge exactly as before (fail open toward judging). No gate, bar, trial or order
is touched: a cell whose build fails contributes no series and no trial, so parking it changes
no other cell's verdict.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent

SCHEMA = "build-input-probe/1"
#: The bank reason this probe writes. A DEFECT class (`judge_coverage.UNKNOWN_REASON_CLASS`).
REASON = "build_input_missing"
MISSING = "MISSING"
PRESENT = "PRESENT"
UNMEASURED = "UNMEASURED"

PEER_FAMILIES = ("relative_value", "correlation_regime")
FACTOR_FAMILIES = ("cross_asset_residual", "pca_residual")
LEG_KEYS = ("leg_b_symbol", "leg_c_symbol")
RAW_COT_FAMILIES = ("cot_net_fade", "cot_change_fade", "cot_change_momentum", "cot_comm_follow")
#: The sources `legacy_inputs` accepts for a raw-COT family; any other is its own refusal.
RAW_COT_SOURCES = (None, "cftc_legacy", "cot_legacy", "raw_cot")
PROBED: frozenset[str] = frozenset({*PEER_FAMILIES, *FACTOR_FAMILIES, "triangle", "lead_lag",
                                    "execution_state", "usd_session_shock", *RAW_COT_FAMILIES})
#: Bank reasons the probe may restate with the exact input: the judge's own generic build failure
#: and its own earlier naming. Every other reason in the bank is the judge's word and stands.
RESTATABLE = frozenset({"build_failed", REASON})
#: Mirrors `judge_coverage.READMIT_MAX_DAYS` (pinned equal by a test): a row this probe parked
#: that long ago is released, and a released cell is not named again until the judge rules.
READMIT_MAX_DAYS = 90.0
#: Top-N kept in the census tables; the counts are exact, the tables are for a reader.
TOP = 25


def _paths() -> None:
    for p in (str(DESK / "scripts"), str(DESK), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)


class _Pass:
    """One pass's readers: the sealed judge's helpers, the input loaders, a stat memo."""

    def __init__(self) -> None:
        _paths()
        import external_gauntlet as G  # type: ignore[import-not-found]  # the judge's rules
        from mt5desk import data as cot_data
        from mt5desk.legacy_family_inputs import fx_driver

        from research import orthogonal_sweep as inputs
        from research.frontier_identity import docket_cell

        self.G, self.inputs, self.cot, self.fx_driver = G, inputs, cot_data, fx_driver
        self.docket_cell = docket_cell
        self._stat: dict[str, bool] = {}
        try:
            meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
        except (OSError, ValueError):
            meta = None
        self.meta = meta if isinstance(meta, dict) and meta else None
        try:
            surfaces = inputs._surfaces()
        except Exception:
            surfaces = {}
        self.surfaces_known = bool(surfaces)

    def exists(self, path: Path) -> bool:
        """`path.exists()`, once per path per pass (keyed by its string: hashing a Path is not
        free, and a box-scale docket asks about the same few thousand files a million times)."""
        key = str(path)
        hit = self._stat.get(key)
        if hit is None:
            hit = self._stat[key] = path.exists()
        return hit

    def bars_item(self, symbol: str, tf: str) -> dict[str, Any] | None:
        """The bar file `orthogonal_sweep._bars(symbol, tf)` reads, when it is absent."""
        sym, chart = str(symbol), str(tf).upper()
        name = f"{sym}_{chart}.parquet"
        hit = self._stat.get(name)
        if hit is None:
            hit = self._stat[name] = (self.inputs.UNIVERSE / name).exists()
        if hit:
            return None
        return {"kind": "bars", "symbol": sym, "timeframe": chart, "file": name}


def label(item: dict[str, Any]) -> str:
    """One short, stable spelling of a missing input, for counting and for a reader."""
    kind = str(item.get("kind") or "")
    if kind == "bars":
        return f"bars:{item.get('file')}"
    if kind == "surface":
        return f"surface:{item.get('symbol')}"
    if kind == "cot_mapping":
        return f"cot_mapping:{item.get('symbol')}"
    if kind == "cot_file":
        return f"cot_file:{item.get('file')}"
    return kind or "unknown"


def parse_label(text: str) -> dict[str, Any] | None:
    """The input a compact label names, as `present` reads it; None for an unknown spelling."""
    kind, _, rest = str(text).partition(":")
    if not rest:
        return None
    if kind == "bars":
        return {"kind": "bars", "file": rest}
    if kind in ("surface", "cot_mapping"):
        return {"kind": kind, "symbol": rest}
    if kind == "cot_file":
        return {"kind": "cot_file", "file": rest}
    return None


def bar_charts(items: Any) -> list[str]:
    """`SYM_TF` for every missing bar file a parked row names (the `bars_wanted` key)."""
    out: list[str] = []
    for i in items if isinstance(items, list) else ():
        item = parse_label(i) if isinstance(i, str) else i
        if isinstance(item, dict) and item.get("kind") == "bars":
            f = str(item.get("file") or "")
            if f.endswith(".parquet") and "_" in f:
                out.append(f[: -len(".parquet")])
    return out


def missing_inputs(ctx: _Pass, sym: str, family: str, params: dict[str, Any],
                   tf: str) -> list[dict[str, Any]] | None:
    """The inputs `build_cell` will find absent ([] when none), or None when it cannot say.

    Mirrors the branches of `external_gauntlet.build_cell` that refuse on an absent input; the
    drift test (`test_build_input_probe.py`) runs the sealed builder beside this on the same
    files, so a change to either side fails there before it can park a buildable cell.
    """
    if family in PEER_FAMILIES:
        peer = params.get("peer_symbol")
        if not isinstance(peer, str) or not peer.strip():
            return None                     # the judge's own preflight names this one
        item = ctx.bars_item(peer, tf)
        return [item] if item else []
    if family in FACTOR_FAMILIES:
        names = params.get("factor_symbols")
        if not isinstance(names, (list, tuple)) or not names or any(
                not isinstance(n, str) or not n.strip() for n in names):
            return None
        return [i for i in (ctx.bars_item(n, tf) for n in names) if i]
    if family == "triangle":
        legs = [params.get(k) for k in LEG_KEYS]
        if any(not isinstance(leg, str) or not leg.strip() for leg in legs):
            return None
        return [i for i in (ctx.bars_item(str(leg), tf) for leg in legs) if i]
    if family == "lead_lag":
        driver = params.get("driver_symbol")
        if not isinstance(driver, str) or not driver.strip():
            return None
        item = ctx.bars_item(driver, tf)
        return [item] if item else []
    if family == "usd_session_shock":
        driver, why = ctx.fx_driver(params)
        if why != "ok" or not driver:
            return None
        item = ctx.bars_item(str(driver), "H1")    # the family conditions on H1 FX, any chart
        return [item] if item else []
    if family == "execution_state":
        if not ctx.surfaces_known:
            return None                     # no map at all: UNMEASURED, never "all lack it"
        if ctx.inputs._surface_for(sym):
            return []
        return [{"kind": "surface", "symbol": sym}]
    if family in RAW_COT_FAMILIES:
        if params.get("input_source") not in RAW_COT_SOURCES:
            return None
        slug = ctx.cot._SYMBOL_SLUG.get(sym)
        if slug is None:
            return [{"kind": "cot_mapping", "symbol": sym}]
        if sym == "XAUUSD":
            return None                     # gold has a legacy fallback file; not probed
        name = f"{slug}.parquet"
        if ctx.exists(ctx.cot._COT / name):
            return []
        return [{"kind": "cot_file", "file": name, "symbol": sym}]
    return None


def _gate0_clear(ctx: _Pass, spec: dict[str, Any], tf: str) -> bool:
    """True only when the judge would pass this cell through gate 0 on files it can see."""
    G, meta = ctx.G, ctx.meta
    if meta is None:
        return False
    canon = spec["sym"]
    if canon not in meta:
        return False
    if not ctx.exists(G.UNI / f"{canon}_H1.parquet"):
        return False                        # the judge may still reach the terminal: UNMEASURED
    row = meta.get(canon)
    if isinstance(row, dict) and row.get("tradeable") is False:
        return False
    if tf != "H1" and not ctx.exists(G.UNI / f"{canon}_{tf}.parquet"):
        return False
    return bool(G.economic_prior(spec).get("passed"))


def probe_row(ctx: _Pass, row: dict[str, Any]) -> dict[str, Any]:
    """{status, ...} for one docket row: MISSING with the inputs, PRESENT, or UNMEASURED."""
    family = str(row.get("family") or "")
    if family not in PROBED:
        return {"status": UNMEASURED, "why": "family not probed"}
    cell = ctx.docket_cell(row)
    params = cell.get("params") if isinstance(cell.get("params"), dict) else None
    sym = str(cell.get("sym") or "")
    if params is None or not sym or ctx.meta is None:
        return {"status": UNMEASURED, "why": "no identity or no registry"}
    canon = ctx.G.canonical_symbol(sym, ctx.meta)
    tf = ctx.G.timeframe_of(params, family)
    missing = missing_inputs(ctx, canon, family, params, tf)
    if missing is None:
        return {"status": UNMEASURED, "why": "the probe cannot settle this identity"}
    if not missing:
        return {"status": PRESENT}
    spec = {"sym": canon, "family": family, "params": params,
            "mechanism_status": row.get("mechanism_status"),
            "mechanism_note": row.get("mechanism_note")}
    if not _gate0_clear(ctx, spec, tf):
        return {"status": UNMEASURED, "why": "gate 0 would rule this cell, or cannot be read"}
    if ctx.G.modifier_preflight(spec):
        return {"status": UNMEASURED, "why": "the judge's preflight conserves it, no worker"}
    own = ctx.G.UNI / f"{canon}_{tf}.parquet"
    try:
        own_bytes = own.stat().st_size
    except OSError:
        own_bytes = 0
    return {"status": MISSING, "sym": canon, "tf": tf, "missing": missing,
            "bar_bytes": own_bytes}


def present(item: dict[str, Any] | str, ctx: _Pass | None = None) -> bool:
    """Is one recorded missing input present now? An unknown kind reads present (fail open)."""
    if isinstance(item, str):
        parsed = parse_label(item)
        if parsed is None:
            return True
        item = parsed
    ctx = ctx or _Pass()
    kind = str(item.get("kind") or "")
    if kind == "bars":
        return bool((ctx.inputs.UNIVERSE / str(item.get("file") or "")).exists())
    if kind == "surface":
        # No readable map at all says nothing about this symbol: fail open, as naming does.
        return (not ctx.surfaces_known
                or bool(ctx.inputs._surface_for(str(item.get("symbol") or ""))))
    if kind == "cot_mapping":
        return str(item.get("symbol") or "") in ctx.cot._SYMBOL_SLUG
    if kind == "cot_file":
        return bool((ctx.cot._COT / str(item.get("file") or "")).exists())
    return True


def all_present(items: Any, ctx: _Pass | None = None) -> bool:
    """Re-admission test for a parked row: every named input present, or nothing to test."""
    if not isinstance(items, list) or not items:
        return True
    ctx = ctx or _Pass()
    return all(present(i, ctx) for i in items if isinstance(i, (dict, str)))


def _parse(stamp: Any) -> datetime | None:
    if not stamp:
        return None
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _age_days(stamp: Any, now: datetime) -> float | None:
    t = _parse(stamp)
    return None if t is None else (now.timestamp() - t.timestamp()) / 86400.0


def name(rows: Iterable[dict[str, Any]], *, judged: set[str] | frozenset[str],
         bank: dict[str, dict[str, Any]], banned: Iterable[str] = (),
         ctx: _Pass | None = None, now: datetime | None = None,
         released: dict[str, str] | None = None, released_unmeasured: bool = False
         ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """(bank rows to park, census) for every never-judged docket row whose build must fail.

    Rows carry `_cell` (the judge's key, stamped by `judge_coverage._build`). A row already in
    the bank under a reason the probe may not restate is left to that reason. A row this probe
    parked READMIT_MAX_DAYS ago is NOT restated (the bank's age clock releases it), and a cell in
    `released` (cell -> when the backstop released it) is not named until the judge rules.
    `released_unmeasured` (the release file is torn or set aside): which cells are held is
    unknown, so only rows this probe already parks are restated -- nothing new is named.

    BY DESIGN: a hold lives in the release file only while its cell is in the docket or younger
    than READMIT_MAX_DAYS (`judge_coverage._record_build_input_released` bounds the file so). A
    cell that leaves the docket after day 90 and later comes back is therefore a new cell to
    this probe and may be parked again on a fresh clock.
    """
    now = now or datetime.now(tz=UTC)
    released = released or {}
    t0 = time.monotonic()
    named: dict[str, dict[str, Any]] = {}
    census: dict[str, Any] = {"schema": SCHEMA, "status": "MEASURED"}
    counts: Counter[str] = Counter()
    by_family: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_input: Counter[str] = Counter()
    by_symbol: Counter[str] = Counter()
    unmeasured_why: Counter[str] = Counter()
    try:
        ctx = ctx or _Pass()
    except Exception as exc:                       # never costs the pass: name nothing
        return {}, {"schema": SCHEMA, "status": UNMEASURED,
                    "why": f"{type(exc).__name__}: {str(exc)[:200]}"}
    banned_set = set(banned)
    for row in rows:
        family = str(row.get("family") or "")
        if family not in PROBED:
            continue
        counts["rows_in_scope"] += 1
        cid = row.get("_cell")
        if not cid or cid in judged or family in banned_set:
            continue
        prev = bank.get(str(cid))
        if isinstance(prev, dict) and prev.get("reason") not in RESTATABLE:
            continue
        if isinstance(prev, dict) and prev.get("reason") == REASON:
            age = _age_days(prev.get("parked_at"), now)
            if age is not None and age >= READMIT_MAX_DAYS:
                counts["released_max_age"] += 1      # the backstop: back to the judge once
                continue
        if released_unmeasured and not (isinstance(prev, dict)
                                        and prev.get("reason") == REASON):
            counts["release_file_unmeasured"] += 1   # a hold may exist: never park new here
            continue
        rel = released.get(str(cid))
        if rel is not None:
            # HELD UNTIL THE JUDGE RULES (audit of v1.1, MF1), never on a calendar. A judged cell
            # left above; here the ruling is a bank row the judge wrote AFTER the release (its
            # build failure, say), which ends the hold and lets the probe restate it by name.
            t_row = _parse(prev.get("parked_at")) if isinstance(prev, dict) else None
            t_rel = _parse(rel)
            ruled = t_row is not None and t_rel is not None and t_row > t_rel
            if not ruled:
                counts["in_release_grace"] += 1      # the judge's turn; its word stands
                continue
            counts["release_ended_by_ruling"] += 1
        counts["rows_probed"] += 1
        try:
            got = probe_row(ctx, row)
        except Exception as exc:
            got = {"status": UNMEASURED, "why": f"raised {type(exc).__name__}"}
        status = got.get("status")
        if status == PRESENT:
            counts["present"] += 1
            continue
        if status != MISSING:
            counts["unmeasured"] += 1
            unmeasured_why[str(got.get("why") or "")] += 1
            continue
        labels = [label(i) for i in got["missing"]]
        # COMPACT (audit S3): the labels are the whole record of what is missing; `why` and the
        # route are rendered from them where a reader needs prose (`judge_coverage`).
        named[str(cid)] = {"reason": REASON, "sym": got["sym"], "family": family,
                           "tf": got["tf"], "bar_bytes": got["bar_bytes"], "missing": labels}
        by_family[family] += 1
        by_symbol[got["sym"]] += 1
        for i, lab in zip(got["missing"], labels, strict=True):
            by_kind[str(i.get("kind"))] += 1
            by_input[lab] += 1
    census.update({
        **{k: counts.get(k, 0) for k in ("rows_in_scope", "rows_probed", "present",
                                         "unmeasured", "released_max_age",
                                         "in_release_grace", "release_ended_by_ruling",
                                         "release_file_unmeasured")},
        "named": len(named),
        "by_family": dict(by_family.most_common()),
        "by_missing_kind": dict(by_kind.most_common()),
        "top_missing_inputs": dict(by_input.most_common(TOP)),
        "top_symbols": dict(by_symbol.most_common(TOP)),
        "unmeasured_by_why": dict(unmeasured_why.most_common(TOP)),
        "seconds": round(time.monotonic() - t0, 3),
        "rule": ("a never-judged cell whose build provably refuses for want of a named input "
                 "absent on this host is parked by name and re-admitted the pass that input is "
                 "present; anything the probe cannot prove goes to the judge as before"),
    })
    return named, census


def census(docket: Path | None = None, *, echo: bool = True) -> dict[str, Any]:
    """Read-only census over the docket on this host: what would be named, by family/input.

    Writes nothing: it reads the docket, the gate ledger, the unrunnable bank and the inputs.
    """
    _paths()
    from research import judge_coverage as jc
    from research.frontier_identity import docket_cell_id

    path = docket or DESK / "data" / "hypotheses" / "external_survivors.json"
    rows = [r for r in (jc._read(path) or []) if isinstance(r, dict)]
    for r in rows:
        try:
            r["_cell"] = str(docket_cell_id(r))
        except Exception:
            r["_cell"] = None
    judged, _, _ = jc.judged_index()
    _named, out = name(rows, judged=judged, bank=jc.unrunnable_bank(),
                       banned=jc.banned_from_capital(), released=jc.build_input_released() or {},
                       released_unmeasured=jc.build_input_released() is None)
    out["docket_rows"] = len(rows)
    out["docket"] = str(path)
    if echo:
        print(json.dumps(out, indent=1, default=str))
    return out
