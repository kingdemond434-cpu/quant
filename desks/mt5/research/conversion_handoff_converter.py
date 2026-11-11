#!/usr/bin/env python3
"""THE CONVERSION-HANDOFF CONVERTER -- the organ the judge's parked cells were handed to.

WHAT WAS MISSING (box read JG3, 2026-11-11). `judge_coverage.write_conversion_handoff` writes
every parked cell the converter owns to `data/hypotheses/conversion_handoff.json` with its class
and route axes (coarser_timeframe, regime_child, cross_asset_transplant, event_study,
proxy_series, family_defect_report). Measured on the trading box: 718,558 rows, none resolved,
no status field, and NOTHING in the repository read the axes. A queue with no consumer is a
parking lot (III.16: unwired is a defect).

WHAT THIS ORGAN DOES, PER HANDOFF REASON, AND WHY IT STOPS WHERE IT STOPS.

  build_failed              A FAMILY DEFECT, NOT A HYPOTHESIS. The cell's signal construction
                            raised; minting variants of it would spend trials on code that does
                            not run. Every row is aggregated by (family, failure message) into
                            `reports/FAMILY_BUILD_DEFECTS.json`, ranked by count with sample
                            cells and the family's source file as its owner, and resolves
                            DEFECT_REPORTED. No trial is minted or charged.
  short_history_after_cut   ROUTED TO `cross_asset_transplant`. The cell traded, but its chart's
                            whole history sits after the lockbox cut. The SAME family and params
                            are minted on a same-class peer (universe_policy.peer_class, from the
                            broker registry) whose history on the same chart starts well before.
                            Each transplant is a NEW TRIAL charged to its trial_family and enters
                            the judge's normal intake; the parent cell id rides on it as lineage.
  lockbox_consumed_history  NOT_CONVERTIBLE. The cell's history exists but the campaign lockbox
                            consumed its development window. Every axis the route offers on the
                            same instrument (coarser chart, regime child, proxy series) reads the
                            SAME calendar span, so it would develop on the consumed holdout --
                            and holdout boundaries are an immutable rail (LAWS §4b "sealed
                            holdouts", §5c "holdout boundaries"; RESEARCH §6a gate 9 "untouched
                            20% holdout"). The judge's own bank re-admits the cell as its history
                            grows past the cut; that is the only legal road back.
  never_fires / too_rare /  HELD. Each conversion of these is a new trial on a shared family-wise
  build_input_missing       error budget (L1.60: multiplicity is judged once, in deflated_sharpe,
                            on every trial the desk ran). 560k fan-outs would raise the bar for
                            every FX and metals cell. They stay UNRESOLVED and are counted as
                            "awaiting a multiple-testing budget"; nothing is written for them.

THE MULTIPLE-TESTING BUDGET. At most MAX_TRANSPLANTS_PER_PASS new transplants a pass and
MAX_TRANSPLANTS_PER_FAMILY_PER_DAY per trial_family per UTC day. A row over either cap is
DEFERRED_BUDGET: counted, never ledgered as resolved, and reached again by the cursor.

TRIAL CHARGING. A transplant is donated through `proposer_common.donate` -- one contract file per
trial_family with `tests_run` = the new transplants of that family -- which is the mechanism
`libs.research.experiment_ledger._proposer_counts` reads into the lifetime and per-family trial
census, and which also writes the registry candidate the judge's lease drinks from. One family
per file, so the charge lands on the right family exactly (the ledger splits a mixed file evenly).
No `search_trials` or effective-N is attached to any row (L1.60).

IDEMPOTENT BY CONSTRUCTION. `conversion_handoff_resolved.jsonl` is append-only and keyed by
(cell, reason, first_parked_utc): a row resolves once; a cell the judge re-parks later carries a
new parked stamp and is a new handoff row. A transplant child that this organ has already charged
is never charged again -- a second parent that lands on the same child resolves CONVERTED with
`trials_charged: 0` and its lineage recorded. The donation is written BEFORE the resolution row,
so a crash between the two can only over-count a trial, never under-count one.

    python desks/mt5/research/conversion_handoff_converter.py --once --budget-s 420
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "conversion_handoff_converter"
HYP = DESK / "data" / "hypotheses"
HANDOFF = HYP / "conversion_handoff.json"
LEDGER = HYP / "conversion_handoff_resolved.jsonl"
CURSOR = HYP / "conversion_handoff_cursor.json"
DOCKET = HYP / "external_survivors.json"
UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "CONVERSION_HANDOFF.json"
DEFECTS = DESK / "reports" / "FAMILY_BUILD_DEFECTS.json"

# ---- statuses ---------------------------------------------------------------------------------
CONVERTED = "CONVERTED"
DEFECT_REPORTED = "DEFECT_REPORTED"
DEFERRED_BUDGET = "DEFERRED_BUDGET"
NOT_CONVERTIBLE = "NOT_CONVERTIBLE"
UNMEASURED = "UNMEASURED"
#: Not a resolution: the row is left alone until a multiple-testing budget exists for its reason.
AWAITING_BUDGET = "AWAITING_MULTIPLE_TESTING_BUDGET"
#: Not a resolution: the pass's budget ran out before the stream reached the row.
NOT_REACHED = "NOT_REACHED"
TERMINAL = frozenset({CONVERTED, DEFECT_REPORTED, NOT_CONVERTIBLE})

BUILD_FAILED = "build_failed"
SHORT_HISTORY = "short_history_after_cut"
LOCKBOX = "lockbox_consumed_history"
#: Reasons this organ deliberately does not fan out (each conversion is a new trial).
HELD_REASONS = ("never_fires", "too_rare", "build_input_missing")

# ---- the multiple-testing budget (module constants, reported every pass) -----------------------
#: New transplants (new trials) per pass. 44k short-history rows drain in ~9 days at 24 passes.
MAX_TRANSPLANTS_PER_PASS = 200
#: New transplants per trial_family per UTC day, so one family cannot take the whole budget.
MAX_TRANSPLANTS_PER_FAMILY_PER_DAY = 100
#: Short-history rows examined per pass (params lookup + peer search), converted or not.
MAX_EXAMINED_PER_PASS = 800
#: A row whose params could not be found is asked again after this long.
UNMEASURED_RETRY_H = 24.0

# ---- what "enough history" means for a peer ---------------------------------------------
#: The peer's bars on the cell's chart must span at least this many calendar days ...
MIN_PEER_HISTORY_DAYS = 730
#: ... and start at least this many days before the parent's own first bar.
MIN_PEER_LEAD_DAYS = 180

#: Share of the pass budget the work may use; the rest is the write margin.
BUDGET_SHARE = 0.85
DEFAULT_BUDGET_S = 420.0
#: Samples kept per (family, message) in the defect report.
DEFECT_SAMPLES = 5
DEFECT_FAMILIES_LISTED = 200
DEFECT_MESSAGES_PER_FAMILY = 10

LOCKBOX_RULE = (
    "NOT_CONVERTIBLE: every route axis on the same instrument (coarser_timeframe, regime_child, "
    "proxy_series) reads the same calendar span, so its development window would sit inside the "
    "consumed lockbox. Holdout boundaries are an immutable rail (LAWS §4b 'sealed holdouts', "
    "§5c 'holdout boundaries'; RESEARCH §6a gate 9 'untouched 20% holdout') and a consumed "
    "lockbox is never reused. The judge's bank re-admits the cell as its history grows past the "
    "cut (judge_coverage.readmit_due), which is the only legal road back.")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat()


# =============================================================================================
# STREAMING READS -- the handoff is a 718k-row JSON object written with indent=1; never load it.
# =============================================================================================

_DECODER = json.JSONDecoder()
_WS = " \t\r\n"


def _iter_array(fh: Any, buf: str, pos: int, chunk: int) -> Iterator[Any]:
    """Yield each element of a JSON array whose '[' is at `buf[pos-1]`, reading `fh` lazily."""
    eof = False
    while True:
        while True:
            while pos < len(buf) and buf[pos] in _WS + ",":
                pos += 1
            if pos < len(buf) or eof:
                break
            more = fh.read(chunk)
            if not more:
                eof = True
            buf, pos = buf[pos:] + more, 0
        if pos >= len(buf):
            return                      # truncated file: what was read stands, nothing invented
        if buf[pos] == "]":
            return
        try:
            obj, end = _DECODER.raw_decode(buf, pos)
        except ValueError:
            if eof:
                return
            more = fh.read(chunk)
            if not more:
                eof = True
            buf, pos = buf[pos:] + more, 0
            continue
        yield obj
        pos = end
        if pos > chunk:
            buf, pos = buf[pos:], 0


def handoff_header(path: Path) -> dict[str, Any]:
    """schema_version / generated_utc / n and the file's format, from its first 64 KiB."""
    out: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not out["exists"]:
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.read(65536)
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    first = head.split("\n", 1)[0].strip()
    try:
        row = json.loads(first) if first else None
    except ValueError:
        row = None
    if isinstance(row, dict) and "cell" in row:
        out["format"] = "jsonl"
        return out
    out["format"] = "json"
    for key, pat in (("schema_version", r'"schema_version"\s*:\s*(\d+)'),
                     ("generated_utc", r'"generated_utc"\s*:\s*"([^"]*)"'),
                     ("n", r'"n"\s*:\s*(\d+)')):
        m = re.search(pat, head.split('"rows"', 1)[0])
        if m:
            out[key] = int(m.group(1)) if key != "generated_utc" else m.group(1)
    return out


def iter_handoff(path: Path, chunk: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Every handoff row, streamed. JSONL (one row per line) and the writer's JSON object form
    (`{"schema_version", "generated_utc", "n", "rows": [...]}`, indent=1) are both read."""
    head = handoff_header(path)
    if not head.get("exists") or head.get("error"):
        return
    with path.open("r", encoding="utf-8") as fh:
        if head.get("format") == "jsonl":
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
            return
        buf = ""
        eof = False
        while True:
            m = re.search(r'"rows"\s*:\s*\[', buf)
            if m:
                break
            if eof:
                return
            more = fh.read(chunk)
            if not more:
                eof = True
            buf += more
        for row in _iter_array(fh, buf, m.end(), chunk):
            if isinstance(row, dict):
                yield row


def iter_json_list(path: Path, chunk: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Each element of a top-level JSON list (the docket), streamed."""
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError:
        return
    with fh:
        buf = fh.read(chunk)
        i = buf.find("[")
        if i < 0:
            return
        for row in _iter_array(fh, buf, i + 1, chunk):
            if isinstance(row, dict):
                yield row


# =============================================================================================
# THE RESOLUTION LEDGER
# =============================================================================================

def row_key(row: Mapping[str, Any]) -> str:
    """A handoff row's identity: the judge's cell id, its parked reason and when it was parked.
    The cell id is the judge's own (`frontier_identity.docket_cell_id`, carried as `cell`); the
    parked stamp makes a cell the judge re-admits and re-parks a NEW row, never a resolved one."""
    raw = "|".join(str(row.get(k) or "") for k in ("cell", "reason", "first_parked_utc"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def load_ledger(path: Path) -> dict[str, Any]:
    """What the append-only ledger already settled. A torn line skips itself, never the rest."""
    resolved: dict[str, str] = {}
    unmeasured_at: dict[str, str] = {}
    charged_children: dict[str, str] = {}
    converted_parents: dict[str, list[str]] = {}
    family_day: Counter[str] = Counter()
    lifetime_trials: Counter[str] = Counter()
    lifetime_converted: Counter[str] = Counter()
    today = _now().date().isoformat()
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError:
        fh = None
    if fh is not None:
        with fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or not rec.get("key"):
                    continue
                st = str(rec.get("status") or "")
                key = str(rec["key"])
                if st in TERMINAL:
                    resolved[key] = st
                    unmeasured_at.pop(key, None)
                elif st == UNMEASURED and key not in resolved:
                    unmeasured_at[key] = str(rec.get("at") or "")
                if st == CONVERTED:
                    fam = str(rec.get("trial_family") or rec.get("family") or "?")
                    lifetime_converted[fam] += 1
                    n = int(rec.get("trials_charged") or 0)
                    if n:
                        lifetime_trials[fam] += n
                        if str(rec.get("at") or "")[:10] == today:
                            family_day[fam] += n
                    for cid in rec.get("child_ids") or []:
                        charged_children.setdefault(str(cid), key)
                    if rec.get("cell") and rec.get("child_ids"):
                        converted_parents.setdefault(str(rec["cell"]),
                                                     [str(c) for c in rec["child_ids"]])
    return {"resolved": resolved, "unmeasured_at": unmeasured_at,
            "charged_children": charged_children, "converted_parents": converted_parents,
            "family_day": family_day,
            "lifetime_trials": lifetime_trials, "lifetime_converted": lifetime_converted}


def append_ledger(path: Path, recs: Sequence[Mapping[str, Any]]) -> int:
    if not recs:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        fh.flush()
        with contextlib.suppress(OSError):
            os.fsync(fh.fileno())
    return len(recs)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


# =============================================================================================
# build_failed -> the family defect report
# =============================================================================================

_HEX = re.compile(r"\b[0-9a-f]{8,}\b")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_SPACE = re.compile(r"\s+")


def failure_signature(why: Any, symbol: Any = "") -> str:
    """The failure message with the parts that vary per cell (symbol, hashes, numbers) folded,
    so one defect in one family reads as one line however many cells hit it."""
    s = str(why or "").strip()
    if not s:
        return "(no message recorded)"
    sym = str(symbol or "").strip()
    if sym:
        s = s.replace(sym, "<SYM>")
    s = _HEX.sub("<HEX>", s)
    s = _NUM.sub("N", s)
    return _SPACE.sub(" ", s)[:200]


class DefectAggregate:
    """(family -> signature -> count, samples) over every build_failed row in the handoff."""

    def __init__(self) -> None:
        self.by_family: dict[str, Counter[str]] = defaultdict(Counter)
        self.samples: dict[tuple[str, str], dict[str, Any]] = {}
        self.total = 0

    def add(self, row: Mapping[str, Any]) -> None:
        fam = str(row.get("family") or "?")
        sig = failure_signature(row.get("why"), row.get("symbol"))
        self.total += 1
        self.by_family[fam][sig] += 1
        s = self.samples.setdefault((fam, sig), {"message": str(row.get("why") or "")[:300],
                                                 "cells": [], "symbols": set(),
                                                 "timeframes": Counter()})
        if len(s["cells"]) < DEFECT_SAMPLES:
            s["cells"].append(str(row.get("cell") or ""))
        if len(s["symbols"]) < 50:
            s["symbols"].add(str(row.get("symbol") or ""))
        s["timeframes"][str(row.get("timeframe") or "H1")] += 1

    def report(self, owners: Mapping[str, str], *, at: str, handoff: Mapping[str, Any],
               partial: bool) -> dict[str, Any]:
        fams = sorted(self.by_family.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
        ranked = []
        for fam, sigs in fams[:DEFECT_FAMILIES_LISTED]:
            msgs = []
            for sig, n in sigs.most_common(DEFECT_MESSAGES_PER_FAMILY):
                s = self.samples.get((fam, sig), {})
                msgs.append({"signature": sig, "count": n,
                             "sample_message": s.get("message"),
                             "sample_cells": list(s.get("cells") or []),
                             "sample_symbols": sorted(s.get("symbols") or [])[:DEFECT_SAMPLES],
                             "timeframes": dict(s.get("timeframes") or {})})
            total = sum(sigs.values())
            ranked.append({
                "family": fam, "count": total, "distinct_messages": len(sigs),
                "owner": owners.get(fam) or "UNMEASURED (family constructor not resolvable)",
                "messages": msgs,
                "issue": (f"{fam}: {total} parked cells failed to BUILD (signal construction "
                          f"raised). Top cause ({msgs[0]['count'] if msgs else 0}x): "
                          f"{msgs[0]['signature'] if msgs else '?'}. Fix the constructor; the "
                          "judge re-admits these cells after BUILD_FAILED_RETRY_DAYS once code "
                          "ships. No trial was minted for them.")})
        return {
            "generated_utc": at, "schema_version": 1, "producer": SEAT,
            "handoff": dict(handoff), "partial": partial,
            "build_failed_rows": self.total, "families": len(self.by_family),
            "ranked": ranked,
            "rule": ("build_failed is a family defect report, never a hypothesis: each row "
                     "resolves DEFECT_REPORTED and no trial is minted or charged for it. The "
                     "family's owner is the source file of its constructor "
                     "(mt5desk.families.get_family_func)."),
        }


def family_owners(families: Sequence[str]) -> dict[str, str]:
    """family -> the repo-relative file that builds it, or nothing when it cannot be resolved."""
    out: dict[str, str] = {}
    try:
        import inspect

        from mt5desk.families import get_family_func
    except Exception:
        return out
    for fam in families:
        try:
            fn = get_family_func(fam)
            src = inspect.getsourcefile(fn) if fn is not None else None
        except Exception:
            src = None
        if src:
            try:
                out[fam] = str(Path(src).resolve().relative_to(ROOT)).replace("\\", "/")
            except ValueError:
                out[fam] = str(src)
    return out


# =============================================================================================
# short_history_after_cut -> cross_asset_transplant
# =============================================================================================

def _cell_id(symbol: str, family: str, params: Mapping[str, Any], timeframe: str) -> str:
    try:
        from research.frontier_identity import docket_cell_id
    except ImportError:                                           # pragma: no cover - import ctx
        from frontier_identity import docket_cell_id  # type: ignore[no-redef]
    return str(docket_cell_id({"symbol": symbol, "family": family, "params": dict(params),
                               "timeframe": timeframe}))


_HIST_MEMO: dict[tuple[str, str], datetime | None] = {}


def history_start(symbol: str, timeframe: str, universe: Path | None = None) -> datetime | None:
    """The first bar on `symbol`'s `timeframe` chart, from the parquet footer (no bars read)."""
    k = (str(universe or UNIVERSE), f"{symbol}_{timeframe}")
    if k in _HIST_MEMO:
        return _HIST_MEMO[k]
    p = (universe or UNIVERSE) / f"{symbol}_{timeframe}.parquet"
    out: datetime | None = None
    if p.exists():
        try:
            import pyarrow.parquet as pq
            md = pq.ParquetFile(p).metadata
            names = [md.schema.column(i).name for i in range(md.num_columns)]
            col = names.index("time") if "time" in names else None
            lows = []
            if col is not None:
                for g in range(md.num_row_groups):
                    st = md.row_group(g).column(col).statistics
                    if st is not None and st.has_min_max:
                        lows.append(st.min)
            if lows:
                t = min(lows)
                if isinstance(t, datetime):
                    out = t if t.tzinfo else t.replace(tzinfo=UTC)
                elif isinstance(t, (int, float)):
                    out = datetime.fromtimestamp(float(t) / 1e9, tz=UTC)
        except Exception:
            out = None
    _HIST_MEMO[k] = out
    return out


def _policy() -> Any:
    try:
        import research.universe_policy as up
    except ImportError:                                           # pragma: no cover - import ctx
        import universe_policy as up  # type: ignore[no-redef]
    return up


def lane_allows(symbol: str, family: str) -> bool:
    """The two-lane law: a share CFD only in the cross-sectional class-book families, anything
    else only when the policy says it is hunted for hypotheses."""
    up = _policy()
    if up.is_equity(symbol):
        return family in up.CROSS_SECTIONAL_FAMILIES
    return bool(up.may_hypothesise(symbol, family))


def ranked_peers(symbol: str, family: str, timeframe: str, *,
                 now: datetime | None = None,
                 universe: Path | None = None) -> tuple[list[str], str | None]:
    """Same-class peers with enough history on the same chart, longest history first.

    Returns (peers, why-none). The class is `universe_policy.peer_class`, from the broker
    registry; an unclassified symbol has no peers (absence is not a permission)."""
    up = _policy()
    if not lane_allows(symbol, family):
        return [], ("two-lane law: the parent is a share CFD and the family is not a "
                    "cross-sectional class book (universe_policy.CROSS_SECTIONAL_FAMILIES)")
    klass = up.peer_class(symbol)
    if not klass:
        return [], f"{symbol} has no peer class in the broker registry (universe_policy)"
    members = [m for m in up.class_members(klass) if str(m).upper() != symbol.upper()]
    t_now = now or _now()
    own = history_start(symbol, timeframe, universe)
    scored: list[tuple[datetime, str]] = []
    for m in members:
        if not lane_allows(m, family):
            continue
        start = history_start(m, timeframe, universe)
        if start is None:
            continue
        if (t_now - start).days < MIN_PEER_HISTORY_DAYS:
            continue
        if own is not None and (own - start).days < MIN_PEER_LEAD_DAYS:
            continue
        scored.append((start, str(m)))
    scored.sort()
    if not scored:
        return [], (f"no {klass} peer with >= {MIN_PEER_HISTORY_DAYS}d of {timeframe} bars "
                    f"starting >= {MIN_PEER_LEAD_DAYS}d before {symbol}'s")
    return [m for _, m in scored], None


ParamsLookup = Callable[[Sequence[Mapping[str, Any]], Callable[[], bool]],
                        dict[str, dict[str, Any]]]
ExistsCheck = Callable[[str, str, Mapping[str, Any], str], bool]
Donor = Callable[[str, list[dict[str, Any]], int], dict[str, Any]]


def registry_params(rows: Sequence[Mapping[str, Any]],
                    time_ok: Callable[[], bool]) -> dict[str, dict[str, Any]]:
    """cell -> {"params", "timeframe"} from the canonical registry (`id` or the `donated_cell`
    alias, both indexed), checked against the judge's own identity; the docket is the fallback."""
    out: dict[str, dict[str, Any]] = {}
    want = {str(r.get("cell")): r for r in rows if r.get("cell")}
    try:
        from libs.moat import registry as reg
        conn = reg.connect()
    except Exception:
        conn = None
    if conn is not None:
        try:
            for cell, r in want.items():
                if not time_ok():
                    break
                for hit in conn.execute(
                        "SELECT family, symbol, params_json, chart FROM research_candidates "
                        "WHERE id=? OR donated_cell=? LIMIT 8", (cell, cell)).fetchall():
                    try:
                        params = json.loads(hit[2] or "{}")
                    except ValueError:
                        continue
                    tf = str(hit[3] or r.get("timeframe") or "H1")
                    if _cell_id(str(hit[1]), str(hit[0]), params, tf) == cell:
                        out[cell] = {"params": params, "timeframe": tf, "source": "registry"}
                        break
        except Exception:
            pass
        finally:
            conn.close()
    missing = {c: r for c, r in want.items() if c not in out}
    if missing and time_ok():
        out.update(docket_params(missing, time_ok))
    return out


def docket_params(want: Mapping[str, Mapping[str, Any]], time_ok: Callable[[], bool],
                  path: Path | None = None) -> dict[str, dict[str, Any]]:
    """cell -> params from the docket, streamed; only rows on a wanted (symbol, family) pair are
    hashed, so the scan costs one parse per docket row."""
    pairs = {(str(r.get("symbol") or ""), str(r.get("family") or "")) for r in want.values()}
    out: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(iter_json_list(path or DOCKET)):
        if i % 2000 == 0 and not time_ok():
            break
        pair = (str(row.get("symbol") or row.get("sym") or ""), str(row.get("family") or ""))
        if pair not in pairs or not isinstance(row.get("params"), dict):
            continue
        try:
            from research.frontier_identity import docket_cell_id
            cid = str(docket_cell_id(row))
        except Exception:
            continue
        if cid in want and cid not in out:
            out[cid] = {"params": dict(row["params"]),
                        "timeframe": str(row.get("timeframe") or want[cid].get("timeframe")
                                         or "H1"),
                        "source": "docket"}
            if len(out) == len(want):
                break
    return out


def registry_has(family: str, symbol: str, params: Mapping[str, Any], chart: str) -> bool:
    """True when the exact rule is already a candidate (its trial was charged by its minter)."""
    try:
        from libs.moat import registry as reg
        conn = reg.connect()
    except Exception:
        return False
    try:
        h = reg.content_hash(family, symbol, params, chart)
        return conn.execute("SELECT 1 FROM research_candidates WHERE content_hash=? LIMIT 1",
                            (h,)).fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def donate_family(trial_family: str, candidates: list[dict[str, Any]],
                  tests_run: int) -> dict[str, Any]:
    """ONE contract file per trial_family through the desk's one donation door, so
    `experiment_ledger._proposer_counts` charges exactly `tests_run` trials to that family."""
    import proposer_common as pc
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", trial_family)[:60] or "family"
    path = pc.donate(source=SEAT, candidates=candidates, tests_run=tests_run, suffix=slug)
    last = dict(pc.LAST_DONATION)
    return {"path": str(path) if path else None, "donated": int(last.get("donated") or 0),
            "refused_wrong_lane": int(last.get("refused_wrong_lane") or 0),
            "refused_unstamped": int(last.get("refused_unstamped") or 0),
            "registry_error": last.get("registry_error")}


def transplant_candidate(parent: Mapping[str, Any], peer: str, params: Mapping[str, Any],
                         timeframe: str, child_id: str) -> dict[str, Any]:
    fam = str(parent.get("family") or "")
    return {
        "source": SEAT, "kind": SEAT, "symbol": peer, "family": fam,
        "params": dict(params), "chart": timeframe, "timeframe": timeframe,
        "mechanism": (f"{fam} on {peer}: the same rule as {parent.get('cell')}, transplanted "
                      "to a same-class peer whose history predates the lockbox cut"),
        "title": f"cross_asset_transplant {fam} {parent.get('symbol')} -> {peer} {timeframe}",
        "url": "", "cell": child_id, "trial_family": parent.get("trial_family") or fam,
        "lineage": {"parent_cell": parent.get("cell"), "route": "cross_asset_transplant",
                    "handoff_reason": parent.get("reason"), "parent_symbol": parent.get("symbol"),
                    "converter": SEAT},
        "evidence": {"route": "cross_asset_transplant", "parent_cell": parent.get("cell"),
                     "parent_why": str(parent.get("why") or "")[:200],
                     "screen": "none: a conversion, judged only by the ten gates"},
    }


# =============================================================================================
# THE PASS
# =============================================================================================

def _budget_s(requested: float, env: Mapping[str, str] | None = None) -> float:
    """BUDGET_SHARE of the smaller of --budget-s and the cycle's cap (QUANT_LEG_BUDGET_S)."""
    src = os.environ if env is None else env
    cap = requested
    try:
        leg = float(src.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        leg = 0.0
    if leg > 0:
        cap = min(cap, leg)
    return max(1.0, cap) * BUDGET_SHARE


def run_pass(*, handoff: Path | None = None, ledger: Path | None = None,
             cursor_path: Path | None = None, report: Path | None = None,
             defects: Path | None = None, budget_s: float = DEFAULT_BUDGET_S,
             params_lookup: ParamsLookup | None = None, exists: ExistsCheck | None = None,
             donor: Donor | None = None, universe: Path | None = None,
             max_per_pass: int | None = None, max_per_family_day: int | None = None,
             env: Mapping[str, str] | None = None,
             clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    handoff = handoff or HANDOFF
    ledger = ledger or LEDGER
    cursor_path = cursor_path or CURSOR
    report = report or REPORT
    defects = defects or DEFECTS
    lookup = params_lookup or registry_params
    exists_fn = exists or registry_has
    donate = donor or donate_family
    cap_pass = MAX_TRANSPLANTS_PER_PASS if max_per_pass is None else int(max_per_pass)
    cap_fam = (MAX_TRANSPLANTS_PER_FAMILY_PER_DAY if max_per_family_day is None
               else int(max_per_family_day))
    t0 = clock()
    limit = _budget_s(budget_s, env)

    def time_ok() -> bool:
        return clock() - t0 < limit

    at = _iso()
    head = handoff_header(handoff)
    led = load_ledger(ledger)
    resolved: dict[str, str] = led["resolved"]
    cur = _read_json(cursor_path)
    cur = cur if isinstance(cur, dict) else {}
    cursor_cell = str(cur.get("cursor_cell") or "")

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    agg = DefectAggregate()
    new_defects: list[dict[str, Any]] = []
    lockbox_recs: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    before: list[dict[str, Any]] = []
    sh_unresolved = 0
    rows_read = 0
    stream_complete = True
    retry_cut = _now().timestamp() - UNMEASURED_RETRY_H * 3600.0

    for row in iter_handoff(handoff):
        if rows_read % 1000 == 0 and not time_ok():
            stream_complete = False
            break
        rows_read += 1
        reason = str(row.get("reason") or "unnamed")
        key = row_key(row)
        if reason == BUILD_FAILED:
            agg.add(row)
        done = resolved.get(key)
        if done:
            counts[reason][done] += 1
            continue
        if reason == BUILD_FAILED:
            new_defects.append({"key": key, "cell": row.get("cell"), "reason": reason,
                                "status": DEFECT_REPORTED, "at": at,
                                "family": row.get("family"),
                                "trial_family": row.get("trial_family"),
                                "signature": failure_signature(row.get("why"),
                                                               row.get("symbol")),
                                "trials_charged": 0, "report": str(defects)})
            counts[reason][DEFECT_REPORTED] += 1
        elif reason == LOCKBOX:
            lockbox_recs.append({"key": key, "cell": row.get("cell"), "reason": reason,
                                 "status": NOT_CONVERTIBLE, "at": at,
                                 "family": row.get("family"),
                                 "trial_family": row.get("trial_family"),
                                 "why": LOCKBOX_RULE, "trials_charged": 0})
            counts[reason][NOT_CONVERTIBLE] += 1
        elif reason == SHORT_HISTORY:
            last = led["unmeasured_at"].get(key)
            if last:
                try:
                    if datetime.fromisoformat(last).timestamp() > retry_cut:
                        counts[reason][UNMEASURED] += 1
                        continue
                except ValueError:
                    pass
            sh_unresolved += 1
            slim = {k: row.get(k) for k in ("cell", "family", "trial_family", "symbol",
                                             "timeframe", "reason", "why", "first_parked_utc")}
            slim["key"] = key
            target = after if str(row.get("cell") or "") > cursor_cell else before
            if len(target) < MAX_EXAMINED_PER_PASS:
                target.append(slim)
        else:
            counts[reason][AWAITING_BUDGET] += 1

    # 1. THE DEFECT REPORT FIRST, then the rows it reports are marked -- never the other way.
    fams = [f for f, _ in sorted(agg.by_family.items(),
                                 key=lambda kv: -sum(kv[1].values()))][:DEFECT_FAMILIES_LISTED]
    defect_doc = agg.report(family_owners(fams), at=at, handoff=head,
                            partial=not stream_complete)
    _atomic_write(defects, defect_doc)
    append_ledger(ledger, new_defects)
    append_ledger(ledger, lockbox_recs)

    # 2. TRANSPLANTS, under the multiple-testing budget.
    selected = (after + before)[:MAX_EXAMINED_PER_PASS]
    family_day: Counter[str] = Counter(led["family_day"])
    charged_children: dict[str, str] = dict(led["charged_children"])
    converted_parents: dict[str, list[str]] = dict(led["converted_parents"])
    params_by_cell = lookup(selected, time_ok) if selected and time_ok() else {}
    by_family: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    sh_recs: list[dict[str, Any]] = []
    new_this_pass = 0
    examined = 0
    # THE CURSOR NEVER PASSES A DEFERRED ROW: it stops at the last row settled before the first
    # one the budget turned away, so that row is the first one the next pass examines.
    last_cell: str | None = None
    deferred_seen = False
    deferred_by_family: Counter[str] = Counter()
    out_of_time = False
    for parent in selected:
        if not time_ok():
            out_of_time = True
            break
        if new_this_pass >= cap_pass:
            break
        examined += 1
        fam = str(parent.get("family") or "")
        tfam = str(parent.get("trial_family") or fam)
        base = {"key": parent["key"], "cell": parent.get("cell"), "reason": SHORT_HISTORY,
                "family": fam, "trial_family": tfam, "at": at,
                "route": "cross_asset_transplant"}
        prior = converted_parents.get(str(parent.get("cell") or ""))
        if prior:
            # THE SAME CELL, PARKED AGAIN: its transplant already exists and was charged once.
            # A second peer would be a fan-out of one parked cell; the lineage is recorded.
            if not deferred_seen:
                last_cell = str(parent.get("cell") or "")
            sh_recs.append({**base, "status": CONVERTED, "child_ids": list(prior),
                            "parent_cell": parent.get("cell"), "trials_charged": 0,
                            "why": "this cell was transplanted when it was parked before; the "
                                   "same child stands and no second trial is charged"})
            counts[SHORT_HISTORY][CONVERTED] += 1
            continue
        if family_day[tfam] >= cap_fam:
            counts[SHORT_HISTORY][DEFERRED_BUDGET] += 1
            deferred_by_family[tfam] += 1
            deferred_seen = True
            continue
        if not deferred_seen:
            last_cell = str(parent.get("cell") or "")
        found = params_by_cell.get(str(parent.get("cell") or ""))
        if not found:
            sh_recs.append({**base, "status": UNMEASURED, "trials_charged": 0,
                            "why": "the parent's params are in neither the registry nor the "
                                   "docket; asked again after "
                                   f"{UNMEASURED_RETRY_H:.0f}h"})
            counts[SHORT_HISTORY][UNMEASURED] += 1
            continue
        tf = str(parent.get("timeframe") or found.get("timeframe") or "H1")
        params = dict(found.get("params") or {})
        peers, why_none = ranked_peers(str(parent.get("symbol") or ""), fam, tf,
                                       universe=universe)
        if not peers:
            sh_recs.append({**base, "status": NOT_CONVERTIBLE, "trials_charged": 0,
                            "why": why_none})
            counts[SHORT_HISTORY][NOT_CONVERTIBLE] += 1
            continue
        chosen: tuple[str, str] | None = None
        reuse: tuple[str, str] | None = None
        for peer in peers:
            cid = _cell_id(peer, fam, params, tf)
            if cid in charged_children:
                reuse = reuse or (peer, cid)
                continue
            if exists_fn(fam, peer, params, tf):
                reuse = reuse or (peer, cid)
                continue
            chosen = (peer, cid)
            break
        if chosen is None:
            peer, cid = reuse if reuse else (peers[0], _cell_id(peers[0], fam, params, tf))
            sh_recs.append({**base, "status": CONVERTED, "child_ids": [cid],
                            "child_symbol": peer, "parent_cell": parent.get("cell"),
                            "trials_charged": 0,
                            "why": "every eligible peer's transplant already exists; its trial "
                                   "was charged when it was first minted, so none is charged "
                                   "again and this parent is recorded as its lineage"})
            counts[SHORT_HISTORY][CONVERTED] += 1
            continue
        peer, cid = chosen
        charged_children[cid] = parent["key"]
        family_day[tfam] += 1
        new_this_pass += 1
        by_family[tfam].append((parent, transplant_candidate(parent, peer, params, tf, cid)))

    # 3. DONATE (the charge), THEN RECORD -- a crash between can only over-count.
    donations: dict[str, Any] = {}
    donation_failed = False
    trials_this_pass: Counter[str] = Counter()
    for tfam, pairs in sorted(by_family.items()):
        cands = [c for _, c in pairs]
        try:
            res = donate(tfam, cands, len(cands))
        except Exception as exc:
            res = {"error": f"{type(exc).__name__}: {exc}", "donated": 0}
        donations[tfam] = res
        if res.get("error") or not res.get("path"):
            donation_failed = True
            for _parent, _c in pairs:
                counts[SHORT_HISTORY][DEFERRED_BUDGET] += 1
                deferred_by_family[tfam] += 1
            continue
        trials_this_pass[tfam] += len(cands)
        for parent, c in pairs:
            sh_recs.append({"key": parent["key"], "cell": parent.get("cell"),
                            "reason": SHORT_HISTORY, "family": c["family"],
                            "trial_family": tfam, "at": at, "route": "cross_asset_transplant",
                            "status": CONVERTED, "child_ids": [c["cell"]],
                            "child_symbol": c["symbol"], "parent_cell": parent.get("cell"),
                            "timeframe": c["timeframe"], "trials_charged": 1,
                            "donation": res.get("path")})
            counts[SHORT_HISTORY][CONVERTED] += 1
    append_ledger(ledger, sh_recs)

    # Rows selected but never examined (budget) and the backlog beyond the selection window.
    not_examined = len(selected) - examined
    if sh_unresolved > examined:
        counts[SHORT_HISTORY][DEFERRED_BUDGET] += sh_unresolved - examined
    partial = (not stream_complete) or out_of_time

    # 4. THE CURSOR: the last cell examined; a lap wraps to the start of the sorted handoff.
    lap = int(cur.get("laps") or 0)
    if last_cell is not None and not donation_failed:
        if cursor_cell and last_cell <= cursor_cell:
            lap += 1
        new_cursor = last_cell
    else:
        new_cursor = cursor_cell
    cursor_doc = {"cursor_cell": new_cursor, "laps": lap, "at": at,
                  "handoff_generated_utc": head.get("generated_utc"),
                  "rule": "short_history rows are worked in the handoff's cell order from here"}
    _atomic_write(cursor_path, cursor_doc)

    lifetime_trials = Counter(led["lifetime_trials"])
    lifetime_trials.update(trials_this_pass)
    by_status: Counter[str] = Counter()
    for c in counts.values():
        by_status.update(c)
    held = {r: sum(counts.get(r, Counter()).values()) for r in HELD_REASONS}
    other_held = {r: n.get(AWAITING_BUDGET, 0) for r, n in counts.items()
                  if r not in HELD_REASONS and n.get(AWAITING_BUDGET)}
    doc = {
        "generated_utc": at, "schema_version": 1, "producer": SEAT,
        "handoff": {**head, "rows_read": rows_read, "complete": stream_complete},
        "partial": partial,
        "counts": {r: dict(sorted(c.items())) for r, c in sorted(counts.items())},
        "by_status": dict(sorted(by_status.items())),
        "converted_per_family": {
            "this_pass": dict(sorted(trials_this_pass.items())),
            "lifetime": dict(sorted((Counter(led["lifetime_converted"])
                                     + Counter(trials_this_pass)).items()))},
        "trials_charged": {
            "this_pass": int(sum(trials_this_pass.values())),
            "this_pass_by_family": dict(sorted(trials_this_pass.items())),
            "lifetime": int(sum(lifetime_trials.values())),
            "lifetime_by_family": dict(sorted(lifetime_trials.items())),
            "mechanism": ("proposer_common.donate: one data/intelligence/" + SEAT
                          + "/discoveries_<stamp>_<family>.json per trial_family with tests_run "
                          "= its new transplants; libs.research.experiment_ledger."
                          "_proposer_counts reads tests_run into the lifetime and per-family "
                          "census. One trial per new transplant; none for a reused child, a "
                          "defect report or a refusal. No search_trials is attached (L1.60)."),
        },
        "donations": donations,
        "deferred_backlog": {
            "rows": int(counts[SHORT_HISTORY].get(DEFERRED_BUDGET, 0)),
            "capped_by_family": dict(sorted(deferred_by_family.items())),
            "retried": "every pass, from the cursor"},
        "awaiting_multiple_testing_budget": {
            "by_reason": {**held, **other_held},
            "rows": int(sum(held.values()) + sum(other_held.values())),
            "rule": ("never_fires, too_rare and build_input_missing are NOT fanned out: each "
                     "conversion is a new trial on the shared family-wise budget (L1.60). They "
                     "stay unresolved until a multiple-testing budget is granted for them.")},
        "lockbox": {"decision": NOT_CONVERTIBLE, "rule": LOCKBOX_RULE},
        "caps": {"MAX_TRANSPLANTS_PER_PASS": cap_pass,
                 "MAX_TRANSPLANTS_PER_FAMILY_PER_DAY": cap_fam,
                 "MAX_EXAMINED_PER_PASS": MAX_EXAMINED_PER_PASS,
                 "MIN_PEER_HISTORY_DAYS": MIN_PEER_HISTORY_DAYS,
                 "MIN_PEER_LEAD_DAYS": MIN_PEER_LEAD_DAYS,
                 "UNMEASURED_RETRY_H": UNMEASURED_RETRY_H},
        "cursor": cursor_doc,
        "budget": {"requested_s": budget_s, "work_limit_s": round(limit, 1),
                   "elapsed_s": round(clock() - t0, 2), "examined": examined,
                   "selected": len(selected), "not_examined": not_examined},
        "artifacts": {"ledger": str(ledger), "defects": str(defects), "cursor": str(cursor_path)},
        "family_build_defects": {"rows": agg.total, "families": len(agg.by_family),
                                 "top": [{"family": r["family"], "count": r["count"]}
                                         for r in defect_doc["ranked"][:10]]},
    }
    if not head.get("exists"):
        doc["status"] = UNMEASURED
        doc["why"] = f"{handoff} is absent: the judge has written no handoff here"
    _atomic_write(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="run one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--handoff", type=Path, default=None)
    a = ap.parse_args(argv)
    doc = run_pass(handoff=a.handoff, budget_s=a.budget_s)
    print(json.dumps({"by_status": doc.get("by_status"), "partial": doc.get("partial"),
                      "trials_charged": doc["trials_charged"]["this_pass"],
                      "report": str(REPORT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
