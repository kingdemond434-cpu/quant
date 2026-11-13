"""The global mining supervisor's published side: metrics, the end-to-end trace, the chains,
the registry summary and the digest.

Split out of `mining_supervisor.py` for size only; `Pipeline` inherits these methods.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import statistics
import sys
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.mining import acquirer as acq  # noqa: E402
from libs.mining import compiler, prereg, rejection  # noqa: E402
from libs.mining.pit_store import iso, parse_time, utcnow  # noqa: E402
from research.mining_supervisor_wiring import (  # noqa: E402
    DIGEST_REJECTIONS,
    DIGEST_CHAINS,
    REGISTRY_SCHEMA,
    ACTIVE_WINDOW,
    REJECTION_RATE_FLOOR,
    QUEUE_AGE_LIMIT_DAYS,
    DEGRADED_SHARE,
    PassReport,
    _pct,
)


def trial_family_summary(fams: Mapping[str, Any]) -> dict[str, Any]:
    """THE LINEAGE VIEW OF THE MINED TRIALS, from `CellRegistry.trial_families()`.

    A mined rule, its symbol transfers and its regime children share one `trial_family_id`.
    Their docket cells are already counted by `libs/research/experiment_ledger.py` (judged in the
    hypothesis graph, screened in the donation's `tests_run`), so this adds nothing to any charge:
    it shows how many judged trials each mined mechanism spent, so a family whose charge came
    from one source's variants is visible as such. No families is UNMEASURED."""
    rows = {k: v for k, v in (fams or {}).items() if isinstance(v, dict)}
    if not rows:
        return {"status": "UNMEASURED: no mined trial families yet"}
    top = sorted(rows.items(), key=lambda kv: -int(kv[1].get("docket_judged") or 0))[:20]
    return {"status": "MEASURED", "trial_families": len(rows),
            "cells": sum(int(v.get("cells") or 0) for v in rows.values()),
            "docket_judged": sum(int(v.get("docket_judged") or 0) for v in rows.values()),
            "docket_passed": sum(int(v.get("docket_passed") or 0) for v in rows.values()),
            "top_by_docket_judged": [k for k, _ in top],
            "rule": "lineage view of trials already counted; never added to the charge"}


class Reporting:
    """Methods of `mining_supervisor.Pipeline`; never instantiated alone."""

    def metrics(self, now: datetime | None = None) -> dict[str, Any]:
        t = now or utcnow()
        day = t - timedelta(hours=24)
        events = self.cells.events_since(day)

        def entered(status_pred: Callable[[str], bool]) -> int:
            return len({e["cell_id"] for e in events if status_pred(str(e["to_status"]))})

        srcs = self.source_status(t)
        active = sum(1 for v in srcs.values() if v["status"] == "ACTIVE")
        evaluated = entered(lambda s: s == "EVALUATED")
        by_reason_eval = self.ledger.counts(day, stages=rejection.EVALUATION_STAGES)
        rejected = sum(by_reason_eval.values())
        axis_rows = self.cells.axis_verdicts_since(day)
        survived = len({e["cell_id"] for e in events if e["to_status"] == "EVALUATED"
                        and not e["reason"]} | {r["cell_id"] for r in axis_rows if r["passed"]})
        lat = self._latency_hours(t)
        ages = self.cells.open_ages(t)
        p95 = {stage: (_pct(v, 95) if v else None) for stage, v in ages.items()}
        binding = self._binding(p95, ages)
        rate = (rejected / evaluated) if evaluated else None
        warnings = []
        if rate is not None and rate < REJECTION_RATE_FLOOR:
            warnings.append(f"rejection_rate {rate:.3f} < {REJECTION_RATE_FLOOR}: the screen is "
                            "too loose")
        for stage, v in p95.items():
            if v is not None and v > QUEUE_AGE_LIMIT_DAYS:
                warnings.append(f"queue_age p95 at {stage} is {v:.1f}d > "
                                f"{QUEUE_AGE_LIMIT_DAYS}d: binding constraint")
        if srcs and active < DEGRADED_SHARE * len(srcs):
            warnings.append(f"sources_active {active}/{len(srcs)} < {DEGRADED_SHARE:.0%}: "
                            "mining coverage is degraded")
        return {
            "generated_at": iso(t), "spec": "MT5_GLOBAL_MINING_V1",
            "sources_active": active, "sources_total": len(srcs),
            "sources_active_ratio": round(active / len(srcs), 4) if srcs else None,
            "cells_acquired_24h": self.store.count(since=day),
            "cells_compiled_24h": entered(lambda s: s == "TESTABLE"),
            "cells_preregistered_24h": entered(lambda s: s == "QUEUED"),
            "cells_evaluated_24h": evaluated,
            "cells_rejected_24h": rejected,
            "cells_rejected_24h_by_reason": by_reason_eval,
            "kills_before_evaluation_24h_by_reason": self.ledger.counts(
                day, stages=[s for s in rejection.STAGES
                             if s not in rejection.EVALUATION_STAGES]),
            "gauntlet_kills_24h_by_class": self.ledger.kill_classes(day),
            "cells_survived_24h": survived,
            "docket_cells_judged_24h": len(axis_rows),
            "docket_cells_passed_24h": sum(1 for r in axis_rows if r["passed"]),
            "cells_by_use_24h": self._by_use(day),
            "rejection_rate": round(rate, 4) if rate is not None else None,
            "median_time_source_to_evaluation_hours": lat,
            "queue_age_p95_days": p95,
            "queue_depth": {k: len(v) for k, v in ages.items()},
            "binding_constraint": binding,
            "warnings": warnings,
            "record_states": self.store.state_counts(),
            "cell_statuses": self.cells.status_counts(),
            "dedup": self.dedup.stats(),
            "sources": srcs,
            "notes": {
                "cells_acquired_24h": "records fetched into the PIT store in 24h (a record "
                                      "becomes 0..n cells)",
                "rejection_rate": "rejected at preregister+gauntlet / evaluated; None when "
                                  "nothing was evaluated (UNMEASURED, not zero)",
                "sources_active": "ACTIVE = >=1 cell EVALUATED in the last 30 days"},
        }

    def _by_use(self, since: datetime) -> dict[str, Any]:
        """Cells created per use in the window, and what became of them; allocation_intel is
        counted in mechanics-feed rows, since it produces facts rather than cells."""
        out: dict[str, Any] = {u: {"created": 0, "sealed": 0, "evaluated": 0, "survived": 0}
                               for u in compiler.USES}
        for c in self.cells.created_since(since):
            b = out.get(c.use or "direct_cells")
            if b is None:
                continue
            b["created"] += 1
            b["sealed"] += int(bool(c.preregistration_id))
            b["evaluated"] += int(c.status == "EVALUATED")
            b["survived"] += int(bool((c.verdict or {}).get("survivor")))
        feed = 0
        try:
            with self.feed.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    t = parse_time(row.get("published_at"))
                    feed += int(t is not None and t >= since)
        except OSError:
            pass
        out["allocation_intel"]["feed_rows"] = feed
        return out

    def _latency_hours(self, now: datetime) -> float | None:
        """Median hours from acquisition to verdict, over cells evaluated in the last 30 days."""
        done = {e["cell_id"]: e["at"] for e in self.cells.events_since(now - ACTIVE_WINDOW)
                if e["to_status"] == "EVALUATED"}
        vals = []
        for c in self.cells.by_status("EVALUATED", limit=100_000):
            a, b = parse_time(c.acquisition_time), parse_time(done.get(c.cell_id))
            if a and b:
                vals.append((b - a).total_seconds() / 3600)
        return round(statistics.median(vals), 2) if vals else None

    @staticmethod
    def _binding(p95: Mapping[str, float | None], ages: Mapping[str, list[float]]) -> str:
        over = {k: v for k, v in p95.items() if v is not None and v > QUEUE_AGE_LIMIT_DAYS}
        if over:
            return max(over, key=lambda k: over[k] or 0.0)
        depth = {k: len(v) for k, v in ages.items() if v}
        if depth:
            return f"{max(depth, key=lambda k: depth[k])} (deepest queue; none over 7d)"
        return "UNMEASURED (no cell waiting in any stage)"

    def trace(self) -> dict[str, Any]:
        """One end-to-end chain: source URI -> cell_id -> prereg SHA -> verdict -> reason."""
        order = ["EVALUATED", "EVALUATING", "QUEUED", "TESTABLE"]
        for st in order:
            cells = self.cells.by_status(st, limit=100_000)
            if cells:
                c = cells[-1]
                sha = ""
                try:
                    sha = self.prereg.sha(c.cell_id) if self.prereg.exists(c.cell_id) else ""
                except prereg.PreregMutationError as exc:
                    sha = f"MUTATED: {exc}"
                return {"complete": st == "EVALUATED", "stage_reached": st,
                        "source_id": c.source_id, "source_uri": c.source_uri,
                        "record_id": c.record_id, "cell_id": c.cell_id,
                        "mechanism_hash": c.mechanism_hash, "spec": c.spec,
                        "preregistration_sha256": sha,
                        "preregistration_file": str(self.prereg.path(c.cell_id)),
                        "gauntlet_cell": c.gauntlet_cell, "verdict": c.verdict,
                        "outcome": ("SURVIVOR" if (c.verdict or {}).get("survivor")
                                    else c.rejection_reason or "PENDING")}
        return {"complete": False, "stage_reached": "NONE",
                "why": "no cell has compiled yet"}

    def publish(self, report: PassReport, now: datetime | None = None) -> dict[str, Any]:
        t = now or utcnow()
        m: dict[str, Any] = {}
        try:
            m = self.metrics(t)
            m["last_pass"] = {"started": report.started,
                              "records_processed": report.records_processed,
                              "cells_created": report.cells_created,
                              "donated": report.donated,
                              "verdicts_joined": report.verdicts_joined,
                              "handed_off": report.handed_off, "errors": report.errors[:20],
                              "fetch": report.sources}
            m["trace"] = self.trace()
            self.reports.mkdir(parents=True, exist_ok=True)
            text = json.dumps(m, indent=1, ensure_ascii=False, default=str)
            (self.reports / f"metrics_{t:%Y-%m-%d}.json").write_text(text, "utf-8")
            (self.reports / "MINING_METRICS.json").write_text(text, "utf-8")
            (self.reports / "MINING_TRACE.json").write_text(
                json.dumps(m["trace"], indent=1, ensure_ascii=False, default=str), "utf-8")
        finally:
            # The committed digest is written whatever failed above, carrying the errors.
            self.write_digest(m or {"errors": report.errors[:20],
                                    "publish": "FAILED before metrics"}, t)
        return m

    def chains(self, now: datetime, limit: int = DIGEST_CHAINS) -> list[dict[str, Any]]:
        """Source URL -> mining cell -> sealed prereg (hash, time) -> docket cell -> verdict,
        newest verdicts first. Every field is read from the record, the cell or the sealed
        contract; nothing is reconstructed."""
        rows = sorted(self.cells.axis_verdicts_since(now - ACTIVE_WINDOW),
                      key=lambda r: str(r["at"]), reverse=True)[:limit]
        out: list[dict[str, Any]] = []
        sealed: dict[str, tuple[str, str]] = {}
        for r in rows:
            c = self.cells.get(str(r["cell_id"]))
            if c is None:
                continue
            if c.cell_id not in sealed:
                try:
                    k = self.prereg.load(c.cell_id)
                    sealed[c.cell_id] = (self.prereg.sha(c.cell_id), str(k.get("sealed_at")))
                except (OSError, ValueError, prereg.PreregMutationError):
                    sealed[c.cell_id] = ("", "")
            sha, sealed_at = sealed[c.cell_id]
            out.append({"source_id": c.source_id, "source_url": c.source_uri,
                        "collected_at": c.acquisition_time,
                        "available_for_decision_at": c.available_for_decision_at,
                        "cell_id": c.cell_id, "use": c.use,
                        "trial_family_id": c.trial_family_id,
                        "prereg_sha256": sha, "prereg_sealed_at": sealed_at,
                        "gauntlet_cell": r["gauntlet_cell"], "axis": r["axis"],
                        "verdict_at": r["at"], "passed": bool(r["passed"]),
                        "terminal_gate": r["terminal_gate"], "reason": r["reason"] or None})
        return out

    def ledger_digest(self) -> dict[str, Any]:
        """THE WHOLE REJECTION LEDGER, COMMITTED AS A DIGEST: every row counted by day, stage,
        reason, source and kill class, plus the row count and the SHA-256 of the file's bytes,
        so the box-only ledger can be checked against it row for row. The latest rows ride
        beside it in `rejections_latest`."""
        by: dict[str, dict[str, int]] = {"day": {}, "stage": {}, "reason": {}, "source": {},
                                         "kill_class": {}, "day_reason": {}}
        n = 0
        for r in self.ledger.rows():
            n += 1
            day = str(r.get("at") or "")[:10]
            for k, v in (("day", day), ("stage", r.get("stage")), ("reason", r.get("reason")),
                         ("source", r.get("source_id") or "?"),
                         ("kill_class", r.get("kill_class") or ""),
                         ("day_reason", f"{day}|{r.get('reason')}")):
                if k == "kill_class" and not v:
                    continue
                by[k][str(v)] = by[k].get(str(v), 0) + 1
        sha = hashlib.sha256()
        size = 0
        try:
            with self.ledger.path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    sha.update(chunk)
                    size += len(chunk)
        except OSError:
            pass
        return {"rows": n, "bytes": size, "sha256": sha.hexdigest() if size else None,
                "path": "desks/mt5/data/mining/rejections.jsonl (box-only)", "by": by}

    def registry_summary(self, srcs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        """The one registry, bounded: per owner (sources, ACTIVE, COLD by reason), the join's
        basis and the schema other lanes register against. Row detail is the box report."""
        by_owner: dict[str, dict[str, Any]] = {}
        cold_ids: dict[str, list[str]] = {}
        for sid, v in sorted(srcs.items()):
            if v.get("status") != "ACTIVE":
                cold_ids.setdefault(str(v.get("cold_reason") or "?"), []).append(sid)
        for v in srcs.values():
            o = by_owner.setdefault(str(v.get("owner") or "?"), {"sources": 0, "active": 0,
                                                                 "cold": {}})
            o["sources"] += 1
            if v.get("status") == "ACTIVE":
                o["active"] += 1
            else:
                r = str(v.get("cold_reason") or "")
                o["cold"][r] = o["cold"].get(r, 0) + 1
        return {"schema": REGISTRY_SCHEMA.relative_to(_ROOT).as_posix(),
                "rule": "ACTIVE = a cell of this source EVALUATED by the gauntlet within 30 "
                        "days (its own mining cells, or a docket cell attributed to it by URL "
                        "or seat); everything else is COLD with its reason",
                "sources": len(srcs),
                "active": sum(1 for v in srcs.values() if v.get("status") == "ACTIVE"),
                "aliases": sum(len(v.get("aliases") or []) for v in srcs.values()),
                "sharing_a_page": sum(1 for v in srcs.values() if v.get("shares_page")),
                "attribution": getattr(self, "_attribution", {}),
                "url_collisions": self.url_collisions(),
                "roster_files": acq.roster_files(root=self.root),
                "by_owner": dict(sorted(by_owner.items())),
                # EVERY COLD source by id, under its reason: committed, so a lane can see which
                # of its sources has not reached the judge without asking the box
                "cold_by_reason": cold_ids}

    def write_digest(self, m: Mapping[str, Any], now: datetime) -> None:
        """The committed digest (DIGEST): bounded, scalars and short rows only."""
        try:
            rej = list(self.ledger.rows())[-DIGEST_REJECTIONS:]
            chains = self.chains(now)
        except Exception as exc:                          # the digest still lands, saying why
            rej, chains = [], [{"error": f"{type(exc).__name__}: {exc}"[:300]}]
        try:
            ledger_digest = self.ledger_digest()
        except Exception as exc:
            ledger_digest = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        try:
            tfams: dict[str, Any] = self.cells.trial_families()
        except Exception as exc:
            tfams = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        try:
            conds = json.loads(self.cells.kv_get("conditioners", "{}") or "{}")
        except ValueError:
            conds = {}
        doc = {"schema": "mining_digest/1", "generated_at": iso(now),
               "metrics": {k: v for k, v in m.items() if k not in ("trace", "last_pass",
                                                                   "sources")},
               "sources": {sid: {k: v.get(k) for k in ("status", "uses", "cold_reason",
                                                        "last_outcome", "evaluated_cells_30d",
                                                        "evaluated_via")}
                           for sid, v in (m.get("sources") or {}).items()
                           if v.get("status") == "ACTIVE" or v.get("owner") == "global_mining"},
               "registry": self.registry_summary(m.get("sources") or {}),
               "trace": m.get("trace"),
               "rejection_ledger": ledger_digest,
               "conditioner_series": conds,
               "trial_families": tfams,
               "trial_family_summary": trial_family_summary(tfams),
               "chains": chains,
               "rejections_latest": rej}
        self.digest.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.digest.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n",
                       "utf-8")
        with contextlib.suppress(OSError):
            os.chmod(self.digest, 0o644)                  # Windows: never replace a read-only file
        os.replace(tmp, self.digest)
