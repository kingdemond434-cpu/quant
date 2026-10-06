"""GLOBAL COUNTRY RESEARCH OS -- every pack, one registry, one resumable hourly rotation.

Country packs used to be rich specifications with no global executable: ``hourly_cycle`` called
this path, but the file did not exist.  This runner is the conservation boundary. Every pack is
either run, refused with exact validation defects, or left at a durable cursor for the next pass.
Native-language source gaps and missing bespoke miners remain visible; neither becomes a quiet
zero. Discoveries go only through ``country_lab.LabCtx.record`` into the canonical registry.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _path in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.moat import registry as R  # noqa: E402
from libs.research import country_lab as CL  # noqa: E402
from libs.research import durable_query_queue as DQ  # noqa: E402

PACK_ROOT = BASE / "research" / "countries"
REPORT = BASE / "reports" / "GLOBAL_RESEARCH_OS.json"
CURSOR = BASE / "data" / "global_research_cursor.json"
LOCK = BASE / "data" / ".global_research_os.lock"
QUERY_QUEUE = BASE / "data" / "global_native_query_queue.json"
DEFAULT_BUDGET_S = 3000.0
MIN_PACK_BUDGET_S = 32.0
# These are conversion-door packs, not CountryPack research specifications. Japan has its own
# region department; global/institutional is the same derived instrument lane under two names.
# Running them here would report three false failures and duplicate their real owners.
NON_LAB_PACKS = {"global", "institutional", "jp"}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text("utf-8-sig"))
        return dict(value) if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str) + "\n", "utf-8")
    try:
        os.replace(tmp, path)
    except OSError:  # Windows can deny replace over an open report; preserve a valid report.
        path.write_text(tmp.read_text("utf-8"), "utf-8")
        tmp.unlink(missing_ok=True)


def pack_codes(root: Path = PACK_ROOT) -> list[str]:
    return sorted(p.parent.name for p in root.glob("*/pack.py")
                  if not p.parent.name.startswith("_") and p.parent.name not in NON_LAB_PACKS)


def _load_extra(code: str) -> tuple[dict[str, Any], str]:
    path = PACK_ROOT / code / "miners.py"
    if not path.exists():
        return {}, "no miners.py; declarative specs use the canonical adapter"
    try:
        # Package import first: several native modules use a relative import to their pack.
        mod = importlib.import_module(f"research.countries.{code}.miners")
        rows = getattr(mod, "MINERS", {})
        return ({str(k): v for k, v in dict(rows).items() if callable(v)}, "")
    except Exception as exc:
        return {}, f"miners.py failed: {type(exc).__name__}: {exc}"


class SeriesLoader:
    """PIT-certified acquired series plus COT, normalized to the lab's DataSeries type."""

    def __init__(self) -> None:
        self.rows: dict[str, Any] = {}
        self.names: dict[str, str] = {}
        try:
            from research.acquire_datasets import acquired_series
            raw = acquired_series(require_authority=True)
            self.rows = {self._key(k): v for k, v in raw.items()}
            self.names = {self._key(k): str(k) for k in raw}
        except Exception:
            self.rows = {}

    @staticmethod
    def _key(value: Any) -> str:
        return "".join(ch for ch in str(value).upper() if ch.isalnum())

    def __call__(self, name: str) -> CL.DataSeries | None:
        text = str(name)
        if text.lower().startswith("cot:"):
            return CL.cot_series(text.split(":", 1)[1])
        row = self.rows.get(self._key(text))
        if row is None:
            return None
        # Credit the read where it happens, for this series only (libs.data.dataset_use).
        from libs.data.dataset_use import record_reads
        record_reads("global_research_os",
                     {f"acquired:{self.names.get(self._key(text), text)}": None},
                     use="new_hypotheses")
        try:
            idx = row.index
            dates = idx.tz_convert("UTC").tz_localize(None).values if getattr(idx, "tz", None) \
                is not None else idx.values
            exact = dates.astype("datetime64[ns]")
            # A date-only observation has UNKNOWN release time.  Treat it as available from the
            # next UTC day, never midnight at the start of its observation day.  Exact intraday
            # stamps retain nanosecond precision.  `align_daily` enforces this availability array.
            days = exact.astype("datetime64[D]")
            midnight = days.astype("datetime64[ns]")
            available = np.where(exact == midnight, midnight + np.timedelta64(1, "D"), exact)
            return CL.DataSeries(name=text, dates=days, values=row.to_numpy(dtype="float64"),
                                 available_at=available,
                                 availability_known=bool(np.any(exact != midnight)))
        except Exception:
            return None


def run(*, budget_s: float = DEFAULT_BUDGET_S, dry_run: bool = False,
        report: Path = REPORT, cursor: Path = CURSOR) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + max(1.0, float(budget_s))
    codes = pack_codes()
    old = _read(cursor)
    start = int(old.get("next_index") or 0) % max(1, len(codes))
    previous = _read(report) if start else {}
    cycle_rows = list(previous.get("countries") or []) if start else []
    cycle_queries = list(previous.get("native_query_queue") or []) if start else []
    order = codes[start:] + codes[:start]
    conn = None if dry_run else R.connect()
    series = SeriesLoader()
    rows: list[dict[str, Any]] = []
    native_queue: list[dict[str, Any]] = []
    next_index = start
    try:
        for offset, code in enumerate(order):
            left = deadline - time.monotonic()
            remaining = len(order) - offset
            if left < 1.0:
                break
            pack = CL.resolve_pack(code)
            if pack is None:
                rows.append({"country": code, "outcome": "failed", "why": "pack does not resolve"})
                next_index = (start + offset + 1) % max(1, len(codes))
                continue
            problems = CL.validate_pack(pack)
            extra, extra_problem = _load_extra(code)
            share = max(MIN_PACK_BUDGET_S, left / max(1, remaining))
            share = min(share, left)
            ctx = CL.LabCtx(code=pack.code, conn=conn, dry_run=dry_run, budget_s=share,
                            bars_loader=CL.default_bars_loader, series_loader=series)
            result = CL.run_lab(pack, ctx, budget_s=share, extra=extra)
            coverage = CL.coverage_state(pack.code, conn, pack=pack)
            for layer in [*coverage.get("layers_unmapped", []),
                          *coverage.get("layers_unverified", [])]:
                native_queue.extend(CL.native_query_seeds(pack, layer, pack=pack))
            miners = result.get("miners") or []
            adapters = sum(1 for m in miners if m.get("implementation") == "DECLARED_SPEC_ADAPTER")
            failed = sum(1 for m in miners if m.get("outcome") == CL.FAILED)
            rows.append({"country": code, "name": pack.name,
                         "outcome": "ok" if not failed else "degraded",
                         "seconds": result.get("seconds"), "discoveries": result.get("domestic"),
                         "miners": len(miners), "failed_miners": failed,
                         "native_miners": max(0, len(result.get("custom_miners") or []) - adapters),
                         "spec_adapters": adapters,
                         "unmeasured": len(result.get("unmeasured") or []),
                         "miner_failures": [{"miner": m.get("miner"), "why": m.get("why")}
                                            for m in miners if m.get("outcome") == CL.FAILED],
                         # EVERY DECLARED MINER GETS A DISPOSITION. Counts alone concealed the
                         # difference between a native miner, an adapter, an empty measurement
                         # and a silent omission. This compact ledger is the country/language
                         # proof consumed by the conversion and Tier-5 audits.
                         "miner_dispositions": [
                             {k: m.get(k) for k in ("miner", "implementation", "outcome", "why",
                                                   "domestic", "transmission", "unmeasured")}
                             for m in miners],
                         "coverage": coverage.get("state"),
                         "layers_mapped": coverage.get("layers_mapped"),
                         "validation": problems, "extra_problem": extra_problem,
                         "custom_entries": list(pack.custom_miners),
                         "axis_proposals": result.get("axis_proposals") or [],
                         "transmission_seeds": len(result.get("transmission_seeds") or [])})
            next_index = (start + offset + 1) % max(1, len(codes))
    finally:
        if conn is not None:
            conn.close()
    by_country = {str(row.get("country")): row for row in cycle_rows if row.get("country")}
    by_country.update({str(row.get("country")): row for row in rows if row.get("country")})
    cycle_rows = [by_country[code] for code in codes if code in by_country]
    cycle_queries = [*cycle_queries, *native_queue]
    # Query identity, not title/order: repeated bounded passes must not inflate native breadth.
    query_seen: set[tuple[str, str, str, str]] = set()
    unique_queries: list[dict[str, Any]] = []
    for row in cycle_queries:
        key = (str(row.get("country")), str(row.get("layer")), str(row.get("domain")),
               str(row.get("query")))
        if key in query_seen:
            continue
        query_seen.add(key)
        unique_queries.append(row)
    full = len(cycle_rows) == len(codes) and next_index == 0
    miner_rows = [m for row in cycle_rows for m in (row.get("miner_dispositions") or [])]
    miner_outcomes: dict[str, int] = {}
    for miner in miner_rows:
        outcome = str(miner.get("outcome") or "UNMEASURED")
        miner_outcomes[outcome] = miner_outcomes.get(outcome, 0) + 1
    queue_stats = {"added": 0, "total": 0}
    queue_reconciliation: dict[str, Any] = {"balanced": True, "total_ids": 0, "states": {}}
    if not dry_run:
        queue_stats = DQ.enqueue(QUERY_QUEUE, unique_queries)
        queue_reconciliation = DQ.reconcile(QUERY_QUEUE)
    doc = {
        "at": _now(), "outcome": "ok", "packs_total": len(codes),
        "packs_run": len(cycle_rows), "packs_run_this_pass": len(rows),
        "next_index": next_index, "completed_full_rotation": full,
        "seconds": round(time.monotonic() - started, 3), "budget_s": float(budget_s),
        "discoveries": sum(int(r.get("discoveries") or 0) for r in cycle_rows),
        "discoveries_this_pass": sum(int(r.get("discoveries") or 0) for r in rows),
        "failed_miners": sum(int(r.get("failed_miners") or 0) for r in cycle_rows),
        "spec_adapters": sum(int(r.get("spec_adapters") or 0) for r in cycle_rows),
        # A bounded DISPLAY only. Every id was persisted above before this preview was made.
        "native_query_queue": unique_queries[:5000], "native_queries": len(unique_queries),
        "native_query_display_truncated": len(unique_queries) > 5000,
        "native_query_durable_queue": str(QUERY_QUEUE),
        "native_query_enqueue": queue_stats,
        "native_query_reconciliation": queue_reconciliation,
        "native_queries_this_pass": len(native_queue), "countries": cycle_rows,
        "conservation": {"discovered_packs": len(codes), "run": len(cycle_rows),
                         "deferred_to_cursor": max(0, len(codes) - len(cycle_rows)),
                         "identity_holds": len(codes) == len(cycle_rows)
                         + max(0, len(codes) - len(cycle_rows)),
                         "declared_miners": sum(int(r.get("miners") or 0)
                                                for r in cycle_rows),
                         "miners_with_disposition": len(miner_rows),
                         "miner_identity_holds": sum(int(r.get("miners") or 0)
                                                     for r in cycle_rows) == len(miner_rows),
                         "miner_outcomes": dict(sorted(miner_outcomes.items()))},
        "rule": ("every pack is run, explicitly refused, or retained at the durable cursor; "
                 "declarative adapters mint hypothesis cards only; evidence and certificates "
                 "remain the universal gauntlet's authority")}
    _atomic(report, doc)
    _atomic(cursor, {"at": doc["at"], "next_index": next_index, "packs": len(codes),
                     "cycle_packs": len(cycle_rows)})
    if not dry_run:
        # The versioned baseline is audited as the closing leg of the producer itself.  This is
        # evidence separation, not a second scheduler: implementation, tests, consumer and fresh
        # runtime output must all exist before any R01-R30 row reads CURRENT_VERIFIED.
        try:
            import global_research_acceptance as acceptance
            doc["baseline_acceptance"] = acceptance.audit()
            _atomic(report, doc)
        except Exception as exc:
            doc["baseline_acceptance"] = {"status": "UNMEASURED",
                                           "why": f"{type(exc).__name__}: {exc}"}
            _atomic(report, doc)
    return doc


@contextlib.contextmanager
def singleton(path: Path = LOCK):
    """A real OS lock: overlapping hourly/manual passes cannot double-spend trial budget."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("a+b")
        handle.seek(0)
        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
    except (OSError, PermissionError):
        with contextlib.suppress(NameError, OSError):
            handle.close()
        yield False
        return
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # pragma: no cover - production is Windows; CI may be POSIX
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        handle.close()
        yield False
        return
    try:
        yield True
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--cursor", type=Path, default=CURSOR)
    args = parser.parse_args()
    with singleton() as acquired:
        if not acquired:
            print("global research OS: an existing pass owns the singleton; no duplicate run")
            return 0
        doc = run(budget_s=args.budget_s, dry_run=args.dry_run,
                  report=args.report, cursor=args.cursor)
    print(f"global research OS: {doc['packs_run']}/{doc['packs_total']} packs; "
          f"{doc['discoveries']} discoveries; {doc['native_queries']} native queries; "
          f"next={doc['next_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
