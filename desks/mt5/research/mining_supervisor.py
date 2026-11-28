"""MT5_GLOBAL_MINING_V1 supervisor: one bounded pass of the global mining pipeline per hour.

    fetch -> PIT store -> extract -> dedup -> compile -> preregister -> gauntlet -> verdict join

RUN BY THE EXISTING HOURLY CYCLE (`research/hourly_cycle.py`, leg `global_mining`), never by a
scheduler of its own: MT5Hourly.cmd is the desk's only launcher and this is one more leg of it,
self-stopping inside the budget the leg grants (`--budget-s`, `QUANT_LEG_BUDGET_S`).

WHAT ONE PASS DOES
1. Acquire: every DUE source in `libs/mining/sources.yaml` (+ external rosters), in parallel
   across hosts, each writing a durable cursor after every record.
2. Process: every record still ACQUIRED is extracted, deduplicated by mechanism, compiled onto a
   registered family, and sealed (preregistrations/<cell_id>.json with its SHA) before anything
   else sees it. Claims nothing here can compile go to the deepening worker's LLM seat.
3. Donate: sealed cells enter the gauntlet's intake through `proposer_common.donate` -- the same
   door every proposer uses, which stamps PIT, preregisters again in the desk registry and
   refuses wrong-lane rows. The gauntlet itself is not touched.
4. Join: the gauntlet's append-only verdict ledger (`gate_verdict_ledger.jsonl`) is read from
   the last offset; each verdict for one of our cells is checked against its sealed contract
   (a mutated or mismatched contract is FAILS_PREREG) and mapped to a rejection code or a
   survivor.
5. Publish: `reports/mining/metrics_<date>.json` (and MINING_METRICS.json, the latest), the
   end-to-end trace, and the mechanics feed (`data/mining/mechanics_feed.jsonl`). Its consumer
   is `conditioners`: each page's facts become a PIT series in the lake the
   `exogenous_conditioner` family reads, and conditioner cells once a series is long enough.
   Risk and cost consumers are money-path work queued for the desktop pass.

NOTHING HERE HAS CAPITAL AUTHORITY. A survivor is a gauntlet survivor like any other; the
promoter and allocator decide what happens to it, through their own sealed paths.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.mining import acquirer as acq  # noqa: E402
from libs.mining import compiler, dedup, extractor, prereg, rejection  # noqa: E402
from libs.mining.pit_store import PitStore, iso, utcnow  # noqa: E402
from libs.mining.registry import Cell, CellRegistry  # noqa: E402
# Split for size: the wiring, the verdict side and the published side live in three
# sibling modules; every public name stays importable from here.
from research.mining_supervisor_wiring import (  # noqa: E402, F401
    SOURCE,
    DATA,
    REPORTS,
    REPORT,
    DIGEST,
    DIGEST_REJECTIONS,
    DIGEST_CHAINS,
    _FAMILY_MIN_OBS,
    COND_MIN_OBS,
    _WAYBACK,
    _scout_seats,
    producer_of,
    _INDEX_PAGE,
    _SECOND_LEVEL,
    _site,
    REGISTRY_SCHEMA,
    MECHANICS_FACTS,
    COND_TRANSFORMS,
    UNI,
    HYP,
    GATE_LEDGER,
    GATE_INDEX,
    ACTIVE_WINDOW,
    REJECTION_RATE_FLOOR,
    QUEUE_AGE_LIMIT_DAYS,
    DEGRADED_SHARE,
    DEEPENING_CAP,
    DONATE_BATCH,
    _CHARTS,
    _SESSIONS,
    axis_variants,
    Hooks,
    _fallback_gcell,
    desk_hooks,
    PassReport,
    _pct,
)
from research.mining_supervisor_report import (  # noqa: E402, F401
    Reporting,
    trial_family_summary,
)
from research.mining_supervisor_verdicts import VerdictJoin  # noqa: E402



class Pipeline(VerdictJoin, Reporting):
    def __init__(self, data_dir: Path = DATA, reports_dir: Path = REPORTS, *,
                 roster: list[acq.Source] | None = None, hooks: Hooks | None = None,
                 gate_ledger: Path = GATE_LEDGER, root: Path = _ROOT,
                 digest: Path | None = None, lake: Path | None = None) -> None:
        self.data = Path(data_dir)
        # beside data_dir: desks/mt5/data/mining -> desks/mt5/data/lake/series (the family's own)
        self.lake = Path(lake) if lake is not None else self.data.parent / "lake" / "series"
        self.mechanics_facts = self.data.parent / MECHANICS_FACTS.name
        # beside data_dir: desks/mt5/data/mining -> desks/mt5/data/mining_digest.json (DIGEST)
        self.digest = Path(digest) if digest is not None else self.data.parent / DIGEST.name
        self.reports = Path(reports_dir)
        self.root = root
        db = self.data / "mining.db"
        self.store = PitStore(db)
        self.cells = CellRegistry(db)
        self.dedup = dedup.DedupIndex(db)
        self.prereg = prereg.PreregStore(self.data / "preregistrations")
        self.ledger = rejection.RejectionLedger(self.data / "rejections.jsonl")
        self.cursors = acq.CursorStore(self.data / "cursors")
        self.feed = self.data / "mechanics_feed.jsonl"
        self.gate_ledger = Path(gate_ledger)
        # THE docket the judge reads, beside its ledger: data/hypotheses/external_survivors.json.
        # Its rows keep the producer's `source` string (`miner:asia:rbnz_series`) and URL; the
        # compiler's miner_candidates.json does not (0 of 53,174 rows carry a URL).
        self.docket = self.gate_ledger.parent / "external_survivors.json"
        self.roster = roster if roster is not None else acq.load_roster(root=root)
        self.by_id = {s.id: s for s in self.roster}
        self.hooks = hooks or Hooks()

    # --------------------------------------------------------------------- 1. acquire
    def acquire(self, budget_s: float, http_get: acq.HttpGet | None = None, *,
                workers: int = 8, force: bool = False,
                now: datetime | None = None) -> list[acq.AcquireReport]:
        from libs.data.polite_fetch import run_concurrently
        deadline = time.monotonic() + max(1.0, budget_s)
        get = http_get or acq.polite_http(deadline)
        t = now or utcnow()
        due = sorted(self.roster, key=lambda s: (s.priority, s.id))
        robots = acq.RobotsCache()

        def one(src: acq.Source) -> acq.AcquireReport:
            ctx = acq.FetchContext(http_get=get, deadline=deadline, now=t, root=self.root,
                                   robots=robots)
            return acq.acquire(src, self.store, self.cursors, ctx, root=self.root, force=force)
        out: list[acq.AcquireReport] = []
        for src, rep, err in run_concurrently(due, one, workers=workers):
            if rep is None:
                self.store.log_run(src.id, "ERROR", 0, 0, err, now=t)
                out.append(acq.AcquireReport(src.id, "ERROR", detail=err))
                continue
            out.append(rep)
            for res in rep.put:
                if "backdated_revision" in res.flags:
                    self.ledger.reject(res.record_id, "LEAKAGE_REVISION", "pit",
                                       subject_kind="record", source_id=src.id,
                                       detail="content changed under an immutable timestamp")
            for target, found in rep.discovered.items():
                self._discover(target, found)
        return out

    def _discover(self, target: str, found: Iterable[str]) -> None:
        if target not in self.by_id:
            return
        cur = self.cursors.get(target)
        disc = list(dict.fromkeys([*(cur.get("discovered") or []), *found]))
        cur["discovered"] = disc[-2000:]
        self.cursors.save(target, cur)

    # --------------------------------------------------------------------- 2. process
    def process(self, limit: int = 5_000, now: datetime | None = None) -> tuple[int, int]:
        n_rec = n_cells = 0
        for rec in self.store.pending(limit):
            n_rec += 1
            try:
                n_cells += self._process_one(rec, now=now)
            except Exception as exc:
                # A record that breaks the extractor is recorded as such, never dropped.
                self.store.set_state(rec["record_id"], "REJECTED",
                                     reason="NO_ECONOMIC_MECHANISM", stage="extract")
                self.ledger.reject(rec["record_id"], "NO_ECONOMIC_MECHANISM", "extract",
                                   subject_kind="record", source_id=rec["source_id"],
                                   detail=f"extractor error {type(exc).__name__}: {exc}")
        return n_rec, n_cells

    def _process_one(self, rec: dict[str, Any], now: datetime | None = None) -> int:
        src = self.by_id.get(str(rec["source_id"]))
        kind = str((rec.get("meta") or {}).get("kind") or (src.kind if src else "text"))
        ex = extractor.extract(rec, kind=kind, universe=self.hooks.universe)
        rid = str(rec["record_id"])
        if kind == "mechanics":
            self._publish_mechanics(rec, ex.facts)
            self.store.set_state(rid, "FEED_PUBLISHED", n_cells=0)
            return 0
        if ex.empty:
            self.store.set_state(rid, "REJECTED", reason="NO_ECONOMIC_MECHANISM",
                                 stage="extract", n_cells=0)
            self.ledger.reject(rid, "NO_ECONOMIC_MECHANISM", "extract", subject_kind="record",
                               source_id=str(rec["source_id"]),
                               detail="no rule, no mechanism claim, no fact")
            return 0
        made = 0
        compiled_any = False
        for rule in ex.rules:
            made_rule, compiled = self._cells_from_rule(rec, ex, rule, now=now)
            made += made_rule
            compiled_any = compiled_any or compiled
        handoff = src.handoff_deepening if src else True
        for claim in ex.claims:
            made += self._claim_cell(rec, ex, claim, handoff=handoff and not compiled_any)
        state = "EXTRACTED" if compiled_any else "HANDED_OFF"
        self.store.set_state(rid, state, n_cells=made)
        return made

    def _base(self, rec: Mapping[str, Any], ex: extractor.Extraction) -> dict[str, Any]:
        meta = rec.get("meta") or {}
        return {"source_id": rec["source_id"], "source_uri": rec["source_uri"],
                "source_version": rec["source_version"], "content_hash": rec["content_hash"],
                "publication_time": rec.get("publication_time"),
                "acquisition_time": rec["acquisition_time"],
                "available_for_decision_at": rec["available_for_decision_at"],
                "original_language": ex.language or str(rec.get("original_language") or ""),
                "translation_provenance": str(meta.get("translated_from") or "original"),
                "record_id": rec["record_id"]}

    def _cells_from_rule(self, rec: Mapping[str, Any], ex: extractor.Extraction,
                         rule: Mapping[str, Any], now: datetime | None = None
                         ) -> tuple[int, bool]:
        mfam = str(rule.get("mechanism_family") or ex.mechanism_family or "other")
        res = compiler.compile_rule(rule, universe=self.hooks.universe,
                                    family_params=self.hooks.family_params)
        base = self._base(rec, ex)
        if res.reason is not None:
            cid = "mc_" + hashlib.sha256(f"{rec['record_id']}|{res.reason}".encode()
                                         ).hexdigest()[:20]
            cell = Cell(cell_id=cid, mechanism_family=mfam, mechanism_subtype="unexecutable",
                        reconstructed_rules=dict(rule), status=f"BLOCKED_{res.reason.value}",
                        rejection_reason=res.reason.value, rejection_stage="compile",
                        claim=str(rule.get("claim") or "")[:500], **base)
            if self.cells.add(cell, stage="compile", now=now):
                self.ledger.reject(cid, res.reason.value, "compile", detail=res.detail,
                                   source_id=cell.source_id)
            return 1, False
        if res.research_only:
            return 0, False
        made = 0
        parent = ""
        for spec in res.specs:
            n, cid = self._spec_cell(rec, ex, rule, spec, mfam, parent=parent,
                                     use="direct_cells", now=now)
            made += n
            parent = parent or cid
            # INDIRECT CELLS: the same family, multiplied by the regime conditions the gauntlet
            # applies honestly. Children of the direct cell, charged to its trial family.
            for child in compiler.indirect_variants(spec, rule):
                made += self._spec_cell(rec, ex, rule, child, mfam, parent=cid or parent,
                                        use="indirect_cells", now=now,
                                        family_subtype=spec.subtype)[0]
        return made, True

    def _spec_cell(self, rec: Mapping[str, Any], ex: extractor.Extraction,
                   rule: Mapping[str, Any], spec: compiler.CompiledSpec, mfam: str, *,
                   parent: str, use: str, now: datetime | None = None,
                   family_subtype: str = "") -> tuple[int, str]:
        """One compiled spec -> one cell (sealed, or blocked with its reason). (made, cell_id);
        cell_id is "" when the spec was a duplicate or already existed."""
        base = self._base(rec, ex)
        s = spec.spec()
        cid = extractor.cell_id_for(str(rec["record_id"]), s)
        mh = dedup.mechanism_hash(mechanism_family=mfam, spec=s)
        tfid = prereg.trial_family_id(mfam, family_subtype or spec.subtype, spec.family)
        gcell = self.hooks.gauntlet_cell(s)
        rules = {"family": spec.family, "params": spec.params, "sym": spec.sym,
                 "timeframe": spec.timeframe, "source_rule": dict(rule)}
        cell = Cell(cell_id=cid, mechanism_family=mfam, mechanism_subtype=spec.subtype,
                    directly_published_rules=rules if spec.published else None,
                    reconstructed_rules=None if spec.published else rules,
                    required_data=list(spec.required_data), required_instruments=[spec.sym],
                    falsifier=compiler.falsifier_for(spec), trial_lineage_id=tfid,
                    trial_family_id=tfid, parent_cell_id=parent, mechanism_hash=mh, spec=s,
                    gauntlet_cell=gcell, status="TESTABLE", use=use,
                    claim=str(rule.get("claim") or "")[:500], **base)
        owner = self.dedup.claim(mh, cid, language=cell.original_language)
        prior = self.hooks.prior_verdict(gcell) if owner is None else None
        if owner is not None or prior is not None:
            dup_of = owner or f"gauntlet:{gcell}"
            cell.status = "BLOCKED_DUPLICATE_MECHANISM"
            cell.rejection_reason, cell.rejection_stage = "DUPLICATE_MECHANISM", "dedup"
            cell.duplicate_of = dup_of
            if prior is not None and owner is None:
                self.dedup.seed_prior_art(mh, dup_of, "gauntlet")
            if self.cells.add(cell, stage="dedup", now=now):
                self.ledger.reject(cid, "DUPLICATE_MECHANISM", "dedup",
                                   source_id=cell.source_id, duplicate_of=dup_of,
                                   detail=f"{cell.original_language} telling of {dup_of}"
                                   + (f"; prior verdict {prior}" if prior else ""))
                return 1, ""
            return 0, ""
        if not self.cells.add(cell, stage="compile", now=now):
            return 0, ""                                  # same record re-processed
        self._seal(cell, now=now)
        return 1, cid

    def _seal(self, cell: Cell, now: datetime | None = None) -> None:
        """TESTABLE -> QUEUED only through the seal. No bars is BLOCKED_DATA (retried)."""
        spec = cell.spec or {}
        if not self.hooks.bars_available(str(spec.get("sym")), str(spec.get("timeframe"))):
            self.cells.transition(cell.cell_id, "BLOCKED_DATA", stage="compile", now=now)
            return
        if not self.hooks.may_hypothesise(str(spec.get("sym")), str(spec.get("family"))):
            self.cells.transition(cell.cell_id, "BLOCKED_LANE", stage="compile", now=now)
            return
        contract = {"cell_id": cell.cell_id, "spec": spec, "falsifier": cell.falsifier,
                    "trial_family_id": cell.trial_family_id,
                    "parent_cell_id": cell.parent_cell_id,
                    "mechanism_family": cell.mechanism_family,
                    "mechanism_subtype": cell.mechanism_subtype,
                    "required_data": cell.required_data, "source_uri": cell.source_uri,
                    "available_for_decision_at": cell.available_for_decision_at,
                    "gauntlet_cell": cell.gauntlet_cell,
                    "gauntlet_cells_expanded": self._expanded(spec),
                    "evaluator": "desks/mt5/scripts/external_gauntlet.py (sealed)"}
        sha = self.prereg.seal(contract, now=now)
        self.cells.add_aliases(cell.cell_id, [(cell.gauntlet_cell, "as_donated"),
                                              *[(g, a) for a, g in
                                                contract["gauntlet_cells_expanded"].items()]])
        self.cells.transition(cell.cell_id, "QUEUED", stage="preregister",
                              updates={"preregistration_id": sha}, now=now)

    def _expanded(self, spec: Mapping[str, Any]) -> dict[str, str]:
        return {axis: self.hooks.gauntlet_cell(v) for axis, v in axis_variants(spec)}

    def _claim_cell(self, rec: Mapping[str, Any], ex: extractor.Extraction,
                    claim: Mapping[str, Any], *, handoff: bool) -> int:
        key = str(claim.get("mechanism_key") or claim.get("claim_hash") or "")
        if not key:
            return 0
        mfam = str(claim.get("mechanism_class") or ex.mechanism_family or "other")
        mh = dedup.mechanism_hash(mechanism_family=mfam, claim_key=key)
        cid = "mc_" + hashlib.sha256(f"{rec['record_id']}|claim|{key}".encode()
                                     ).hexdigest()[:20]
        inst = claim.get("instruments") or {}
        cell = Cell(cell_id=cid, mechanism_family=mfam, mechanism_subtype="claim",
                    reconstructed_rules={"claim": claim.get("claim"),
                                         "direction": claim.get("direction"),
                                         "horizon": claim.get("horizon"),
                                         "quantities": claim.get("quantities")},
                    required_instruments=list(inst.get("analogues") or inst.get("indirect")
                                              or []),
                    falsifier="compiled by the deepening worker into a registered family, "
                              "then the sealed gauntlet",
                    mechanism_hash=mh, status="RESEARCH_ONLY",
                    claim=str(claim.get("claim") or "")[:500], **self._base(rec, ex))
        owner = self.dedup.claim(mh, cid, language=cell.original_language)
        if owner is not None:
            cell.status = "BLOCKED_DUPLICATE_MECHANISM"
            cell.rejection_reason, cell.rejection_stage = "DUPLICATE_MECHANISM", "dedup"
            cell.duplicate_of = owner
            if self.cells.add(cell, stage="dedup"):
                self.ledger.reject(cid, "DUPLICATE_MECHANISM", "dedup", duplicate_of=owner,
                                   source_id=cell.source_id,
                                   detail=f"{cell.original_language} telling of {owner}")
                return 1
            return 0
        if handoff:
            cell.verdict = {"handoff": "deepening_worker (story_mechanism)"}
        return 1 if self.cells.add(cell, stage="extract") else 0

    def _publish_mechanics(self, rec: Mapping[str, Any], facts: Mapping[str, Any]) -> None:
        prev = self.store.get(str(rec.get("revision_of") or "")) if rec.get("revision_of") \
            else None
        prev_facts = extractor.read_facts(f"{prev['title']}\n{prev['body']}") if prev else {}
        changed = sorted(k for k in set(facts) | set(prev_facts)
                         if facts.get(k) != prev_facts.get(k)) if prev else []
        row = {"source_id": rec["source_id"], "source_uri": rec["source_uri"],
               "record_id": rec["record_id"], "vintage": rec.get("revision_n", 0),
               "revision_of": rec.get("revision_of") or "",
               "available_for_decision_at": rec["available_for_decision_at"],
               "label": (rec.get("meta") or {}).get("label"), "facts": dict(facts),
               "changed_fields": changed, "page_changed": bool(prev),
               "published_at": iso(utcnow()),
               "feeds_to": (self.by_id[str(rec["source_id"])].feeds
                            if str(rec["source_id"]) in self.by_id else [])}
        self.feed.parent.mkdir(parents=True, exist_ok=True)
        with self.feed.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def feed_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            with self.feed.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict):
                        rows.append(r)
        except OSError:
            pass
        return rows

    @staticmethod
    def series_id(source_id: str, source_uri: str) -> str:
        return (f"mining_{source_id}_"
                f"{hashlib.sha256(source_uri.encode()).hexdigest()[:8]}")

    def conditioners(self, now: datetime | None = None) -> dict[str, Any]:
        """Mechanics feed -> lake series -> exogenous_conditioner cells. Returns a per-series
        report for the digest; a series below the family's minimum says so, never a zero."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in self.feed_rows():
            key = self.series_id(str(r.get("source_id")), str(r.get("source_uri")))
            groups.setdefault(key, []).append(r)
        report: dict[str, Any] = {}
        minted = 0
        for sid, rows in sorted(groups.items()):
            rows.sort(key=lambda r: str(r.get("available_for_decision_at") or ""))
            cols = sorted({k for r in rows for k, v in (r.get("facts") or {}).items()
                           if isinstance(v, (int, float))})
            self._write_series(sid, rows, cols)
            varying = [c for c in cols if c in extractor.SIGNAL_FACTS
                       and len({(r.get("facts") or {}).get(c) for r in rows}) > 1]
            entry: dict[str, Any] = {"source_id": rows[-1].get("source_id"),
                                     "source_uri": rows[-1].get("source_uri"),
                                     "vintages": len(rows), "columns": cols,
                                     "varying": varying, "cells_minted": 0}
            if len(rows) < COND_MIN_OBS:
                entry["status"] = (f"UNMEASURED: {len(rows)} vintages < {COND_MIN_OBS} the "
                                   "conditioner family needs")
            elif not varying:
                entry["status"] = ("no signal column (swap) has changed across vintages: "
                                   "nothing to condition on; cost and rule facts go to "
                                   "mechanics_facts.json")
            else:
                entry["status"] = "MINTING"
                entry["cells_minted"] = self._mint_conditioner_cells(sid, rows[-1], varying,
                                                                     now=now)
                minted += entry["cells_minted"]
            report[sid] = entry
        self.cells.kv_set("conditioners", json.dumps(report, default=str))
        self._write_mechanics_facts(groups)
        return {"series": len(report), "cells_minted": minted}

    def _write_mechanics_facts(self, groups: Mapping[str, list[dict[str, Any]]]) -> None:
        """Latest vintage per page, cost facts and prop-rule limits apart, with each fact's
        PIT time and the time it last changed. The cost and risk models' input; not a cell."""
        pages: dict[str, Any] = {}
        for sid, rows in groups.items():
            rows = sorted(rows, key=lambda r: str(r.get("available_for_decision_at") or ""))
            last = rows[-1]
            facts = dict(last.get("facts") or {})
            changed: dict[str, str] = {}
            prev: dict[str, Any] = {}
            for r in rows:
                for k, v in (r.get("facts") or {}).items():
                    if prev.get(k) != v:
                        changed[k] = str(r.get("available_for_decision_at"))
                prev = dict(r.get("facts") or {})
            pages[sid] = {"source_id": last.get("source_id"), "source_uri": last.get("source_uri"),
                          "label": last.get("label"), "vintages": len(rows),
                          "available_for_decision_at": last.get("available_for_decision_at"),
                          "cost": {k: v for k, v in facts.items() if k in extractor.COST_FACTS},
                          "prop_rules": {k: v for k, v in facts.items()
                                         if k in extractor.RULE_FACTS},
                          "financing": {k: v for k, v in facts.items()
                                        if k in extractor.SIGNAL_FACTS},
                          "last_changed_at": changed}
        doc = {"schema": "mechanics_facts/1", "generated_at": iso(utcnow()),
               "rule": ("published broker/prop terms as read, point-in-time; inputs for the cost "
                        "and risk models, never cells and never a sizing change by themselves"),
               "pages": pages}
        dest = self.mechanics_facts
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n",
                       "utf-8")
        with contextlib.suppress(OSError):
            os.chmod(dest, 0o644)
        os.replace(tmp, dest)

    def _write_series(self, sid: str, rows: list[dict[str, Any]], cols: list[str]) -> None:
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["available_time", "vintage_id", "source_id", *cols])
        for r in rows:
            f = r.get("facts") or {}
            w.writerow([r.get("available_for_decision_at"), r.get("record_id"),
                        r.get("source_id"),
                        *[(float(f[c]) if isinstance(f.get(c), (int, float)) else "")
                          for c in cols]])
        self.lake.mkdir(parents=True, exist_ok=True)
        dest = self.lake / f"{sid}.csv"
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(buf.getvalue(), "utf-8")
        with contextlib.suppress(OSError):
            os.chmod(dest, 0o644)
        os.replace(tmp, dest)

    def _mint_conditioner_cells(self, sid: str, last: Mapping[str, Any], cols: list[str], *,
                                now: datetime | None = None) -> int:
        rec = self.store.get(str(last.get("record_id") or ""))
        if rec is None:
            return 0
        src = self.by_id.get(str(rec["source_id"]))
        targets = [str(t).upper() for t in ((src.config.get("targets") if src else None)
                                            or compiler.DEFAULT_TRANSFER)]
        if self.hooks.universe is not None:
            targets = [t for t in targets if t in self.hooks.universe]
        ex = extractor.Extraction(language=str(rec.get("original_language") or ""),
                                  mechanism_family="broker_mechanics")
        made_n, parent = 0, ""
        for col in cols:
            for tr in COND_TRANSFORMS:
                for sym in targets:
                    key = f"cond:{sid}:{col}:{tr}:{sym}"
                    if self.cells.kv_get(key, ""):
                        continue                          # minted on an earlier pass
                    spec = compiler.CompiledSpec(
                        sym=sym, family="exogenous_conditioner",
                        params={"source": sid, "signal": col, "transform": tr},
                        timeframe="H1", subtype=f"mechanics:{col}", published=False,
                        transferred=True,
                        required_data=[f"bars:{sym}:H1", f"series:{sid}"])
                    rule = {"claim": f"{rec['source_id']} {col} ({tr}) conditions {sym}"}
                    n, cid = self._spec_cell(rec, ex, rule, spec, "broker_mechanics",
                                             parent=parent, use="allocation_intel", now=now,
                                             family_subtype=f"mechanics:{sid}")
                    made_n += n
                    parent = parent or cid
                    self.cells.kv_set(key, cid or "duplicate")
        return made_n

    def retry_blocked_data(self, now: datetime | None = None) -> int:
        n = 0
        for cell in self.cells.by_status("BLOCKED_DATA", limit=20_000):
            spec = cell.spec or {}
            if self.hooks.bars_available(str(spec.get("sym")), str(spec.get("timeframe"))):
                self.cells.transition(cell.cell_id, "TESTABLE", stage="compile", now=now)
                cell.status = "TESTABLE"
                self._seal(cell, now=now)
                n += 1
        return n

    # --------------------------------------------------------------------- 3. donate
    def donate(self, now: datetime | None = None) -> int:
        queued = self.cells.by_status("QUEUED", limit=DONATE_BATCH)
        if not queued or self.hooks.donate is None:
            return 0
        rows = []
        for c in queued:
            spec = c.spec or {}
            rows.append({
                "symbol": spec.get("sym"), "family": spec.get("family"),
                "params": dict(spec.get("params") or {}), "timeframe": spec.get("timeframe"),
                "title": f"{c.source_id}: {c.mechanism_subtype} on {spec.get('sym')}",
                "mechanism": c.mechanism_family, "mechanism_status": "NAMED",
                "mechanism_note": f"registered family {spec.get('family')} compiled from "
                                  f"{c.source_uri}",
                "available_time": c.available_for_decision_at,
                "published_at": c.publication_time or c.acquisition_time,
                "preregistration_id": c.preregistration_id, "mining_cell_id": c.cell_id,
                "trial_family_id": c.trial_family_id, "parent_cell_id": c.parent_cell_id,
                "source_uri": c.source_uri, "url": c.source_uri})
        ok, detail = self.hooks.donate(rows)
        if not ok:
            # The door refused the batch (stamping or lane); the cells stay QUEUED and the
            # reason is on the report. Nothing moves to EVALUATING that did not enter the intake.
            self.cells.kv_set("last_donation_refusal", detail)
            return 0
        for c in queued:
            self.cells.transition(c.cell_id, "EVALUATING", stage="gauntlet", now=now,
                                  updates={"verdict": {"donated": detail}})
        return len(queued)

    # --------------------------------------------------------------------- one pass
    def run_pass(self, budget_s: float, *, http_get: acq.HttpGet | None = None,
                 fetch: bool = True, now: datetime | None = None) -> dict[str, Any]:
        t0 = time.monotonic()
        rep = PassReport(started=iso(now or utcnow()))
        if fetch:
            try:
                for r in self.acquire(budget_s * 0.6, http_get, now=now):
                    rep.sources.append({"id": r.source_id, "outcome": r.outcome,
                                        "fetched": r.fetched, "new": r.new,
                                        "detail": r.detail})
            except Exception as exc:                      # the rest of the pass still runs
                rep.errors.append(f"acquire: {type(exc).__name__}: {exc}"[:300])
        for step in ("process", "conditioners", "retry", "donate", "join", "judged", "register",
                     "handoff"):
            if time.monotonic() - t0 > budget_s * 0.95:
                rep.errors.append(f"budget exhausted before {step}")
                break
            try:
                if step == "process":
                    rep.records_processed, rep.cells_created = self.process(now=now)
                elif step == "conditioners":
                    rep.cells_created += int(self.conditioners(now=now)["cells_minted"])
                elif step == "retry":
                    self.retry_blocked_data(now=now)
                elif step == "donate":
                    rep.donated = self.donate(now=now)
                elif step == "join":
                    rep.verdicts_joined = self.join_verdicts(now=now)
                elif step == "judged":
                    self.index_judged(now=now)
                elif step == "register":
                    self.register_cursors(now=now)
                elif step == "handoff":
                    rep.handed_off = self.handoff_deepening()
            except Exception as exc:
                rep.errors.append(f"{step}: {type(exc).__name__}: {exc}"[:300])
        return self.publish(rep, now=now)



# ============================================================================ CLI
def fixture_trace(data_dir: Path) -> dict[str, Any]:
    """An offline end-to-end trace through the REAL sealed gauntlet, on the desk's own bars.

    For a machine with no network (the cloud build box): one fixture record in the shape of an
    MQL5 CodeBase page goes through the full pipeline, and the compiled cell is judged by
    `external_gauntlet.run_gauntlet` exactly as `placebo_audit` judges its controls; the verdict
    is written in the gate-ledger row shape and joined back. The live trace comes from the
    hourly pass on the box, where the gauntlet's own ledger supplies the verdict."""
    sys.path.insert(0, str(_DESK / "scripts"))
    import external_gauntlet as eg

    hooks = desk_hooks()
    hooks.donate = lambda rows: (True, json.dumps({"donated": len(rows),
                                                   "path": "fixture (not written)"}))
    hooks.handoff = None
    hooks.prior_verdict = lambda gcell: None
    ledger = data_dir / "fixture_gate_ledger.jsonl"
    src = acq.Source(id="fixture_mql5_codebase", fetcher="external_feed", kind="code",
                     priority=1, name="fixture", uses=list(acq.DEFAULT_USES["code"]))
    pipe = Pipeline(data_dir, data_dir / "reports", roster=[src], hooks=hooks,
                    gate_ledger=ledger, digest=data_dir / "mining_digest.json")
    body = ("//+ RSI Reversal EA for EURUSD H1\n"
            "input int RSI_Period = 14;\ninput int RSI_Oversold = 25;\n"
            "input int RSI_Overbought = 75;\n"
            "int h = iRSI(_Symbol, PERIOD_H1, RSI_Period, PRICE_CLOSE);\n"
            "// buy when RSI crosses up through the oversold level, sell at overbought\n")
    from libs.mining.pit_store import RawRecord
    pipe.store.put(RawRecord(source_id=src.id,
                             source_uri="fixture://mql5.com/en/code/rsi-reversal-eurusd",
                             title="RSI Reversal EA (EURUSD, H1)", body=body,
                             acquisition_time=iso(utcnow()), original_language="en",
                             meta={"kind": "code"}))
    pipe.process()
    pipe.donate()
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    rows = []
    for c in pipe.cells.by_status("EVALUATING"):
        spec = c.spec or {}
        built = eg.build_cell(str(spec["sym"]), str(spec["family"]),
                              dict(spec.get("params") or {}), meta)
        if built is None:
            continue
        built.setdefault("sym", spec["sym"])
        built.setdefault("family", spec["family"])
        built.setdefault("params", dict(spec.get("params") or {}))
        out = eg.run_gauntlet([built], "global-mining-fixture-trace", meta)
        for v in out.get("verdicts") or []:
            # The ledger row carries the id the GAUNTLET judged, never ours: if the two ever
            # disagree the join reads FAILS_PREREG and the fixture test fails on it.
            rows.append({"at": utcnow().isoformat(), "cell": v.get("cell") or "UNKNOWN",
                         "sym": v.get("sym"), "family": v.get("family"),
                         "passed": bool(v.get("passed")),
                         "terminal_gate": v.get("terminal_gate") or "UNKNOWN",
                         "downstream_status": v.get("downstream_status"),
                         "judged_cell": v.get("cell")})
    with ledger.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    pipe.join_verdicts()
    return pipe.publish(PassReport(started=iso(utcnow())))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    env_cap = os.environ.get("QUANT_LEG_BUDGET_S")
    ap.add_argument("--budget-s", type=float, default=float(env_cap) * 0.9 if env_cap
                    else 900.0)
    ap.add_argument("--no-fetch", action="store_true", help="process/donate/join only")
    ap.add_argument("--fixture-trace", type=Path, default=None,
                    help="offline end-to-end trace into this directory")
    args = ap.parse_args(argv)
    if args.fixture_trace is not None:
        m = fixture_trace(args.fixture_trace)
        print(json.dumps(m["trace"], indent=1, default=str))
        return 0
    pipe = Pipeline(hooks=desk_hooks())
    m = pipe.run_pass(args.budget_s, fetch=not args.no_fetch)
    print(json.dumps({k: m[k] for k in ("sources_active", "sources_total",
                                        "cells_acquired_24h", "cells_evaluated_24h",
                                        "rejection_rate", "binding_constraint", "warnings")},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
