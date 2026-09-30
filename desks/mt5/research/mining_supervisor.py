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
import statistics
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.mining import acquirer as acq  # noqa: E402
from libs.mining import compiler, dedup, extractor, prereg, rejection  # noqa: E402
from libs.mining.pit_store import PitStore, iso, parse_time, utcnow  # noqa: E402
from libs.mining.registry import Cell, CellRegistry  # noqa: E402

SOURCE = "global_mining"
DATA = _DESK / "data" / "mining"
REPORTS = _DESK / "reports" / "mining"
#: The organ's own artifact (read by the component registry and the runtime attestation).
REPORT = REPORTS / "MINING_METRICS.json"
#: THE COMMITTED DIGEST. reports/ and data/mining/ are box-only; this one small file is tracked,
#: sits under a state prefix, and is pushed by the box's hourly capture commit, so a reader on
#: GitHub sees the day's metrics, the latest rejections and every source -> cell -> prereg ->
#: verdict chain (the six-event trace's event 1-3 evidence) without the box.
DIGEST = _DESK / "data" / "mining_digest.json"
DIGEST_REJECTIONS = 300
DIGEST_CHAINS = 300

#: THE MECHANICS FEED'S CONSUMER. Every broker/prop page's numeric facts become a point-in-time
#: series in the lake directory the `exogenous_conditioner` family reads (its SERIES_DIR), one
#: row per real vintage stamped with the vintage's own `available_for_decision_at`. Once a series
#: holds the family's minimum observations, each changing column mints conditioner cells on the
#: source's target instruments, judged by the one gauntlet like every other cell.
#: 60, not the family's own 30: the gauntlet needs 60 days of returns before it will judge a
#: cell at all (`external_gauntlet` "no valid cells"), so a shorter series keeps accumulating as
#: UNMEASURED rather than minting cells the judge can only refuse.
try:
    from mt5desk.family_exogenous_conditioner import MIN_OBSERVATIONS as _FAMILY_MIN_OBS
except Exception:                                          # tests and a bare checkout
    _FAMILY_MIN_OBS = 30
COND_MIN_OBS = max(60, int(_FAMILY_MIN_OBS))
#: The committed input for the cost and risk models: every page's latest PIT vintage, split
#: into cost facts and prop-rule limits (extractor.COST_FACTS / RULE_FACTS). Never minted as cells.
#: THE CONTRACT another lane registers a source against (roster row) and reads back (registry row).
REGISTRY_SCHEMA = _ROOT / "libs" / "mining" / "source_registry.schema.json"
MECHANICS_FACTS = _DESK / "data" / "mechanics_facts.json"
COND_TRANSFORMS: tuple[str, ...] = ("level_z", "delta")
UNI = _DESK / "data" / "universe"
HYP = _DESK / "data" / "hypotheses"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
GATE_INDEX = HYP / "gate_verdict_index.json"

ACTIVE_WINDOW = timedelta(days=30)
REJECTION_RATE_FLOOR = 0.90
QUEUE_AGE_LIMIT_DAYS = 7.0
DEGRADED_SHARE = 0.5
DEEPENING_CAP = 400
DONATE_BATCH = 5_000

#: THE DOCKET'S AXIS EXPANSION, mirrored. `miner_candidate_compiler.expand_axes` turns every
#: donated H1 row that names no chart or session into one docket cell per intraday chart (with
#: bars) x session, H1 last -- up to 16 gauntlet cells per mining cell. Every one is sealed into
#: the preregistration up front and joined back, so the verdict counts are the docket's.
try:
    from research.miner_candidate_compiler import INTRADAY_CHARTS as _CHARTS
    from research.miner_candidate_compiler import SESSION_AXIS as _SESSIONS
except Exception:                                          # tests and a bare checkout
    _CHARTS, _SESSIONS = ("M5", "M15", "M30"), ("all", "asia", "london", "ny")


def axis_variants(spec: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(axis label, spec) for every docket cell `expand_axes` can make from this spec."""
    params = dict(spec.get("params") or {})
    if "timeframe" in params or "session" in params:
        return [("as_donated", dict(spec))]
    out = []
    for tf in (*_CHARTS, "H1"):
        for sess in _SESSIONS:
            p = dict(params)
            if tf != "H1":
                p["timeframe"] = tf
            if sess != "all":
                p["session"] = sess
            out.append((f"{tf}/{sess}", {**spec, "params": p}))
    return out


# ============================================================================ wiring
@dataclass
class Hooks:
    """Everything the pipeline needs from the desk, injectable so tests run it offline."""
    universe: set[str] | None = None
    family_params: Callable[[str], set[str] | None] | None = None
    bars_available: Callable[[str, str], bool] = lambda sym, tf: True
    gauntlet_cell: Callable[[Mapping[str, Any]], str] = lambda spec: _fallback_gcell(spec)
    may_hypothesise: Callable[[str, str], bool] = lambda sym, fam: True
    prior_verdict: Callable[[str], str | None] = lambda gcell: None
    donate: Callable[[list[dict[str, Any]]], tuple[bool, str]] | None = None
    handoff: Callable[[list[dict[str, Any]]], int] | None = None


def _fallback_gcell(spec: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(spec.get("params") or {}), sort_keys=True, separators=(",", ":"))
    return f"{spec.get('sym')}.{spec.get('family')}.p=" + \
        hashlib.sha256(payload.encode()).hexdigest()[:16]


def desk_hooks() -> Hooks:
    """The live wiring. Every import is guarded: a missing organ degrades to a named state,
    never to a crash of the hourly cycle."""
    h = Hooks()
    try:
        meta = json.loads((UNI / "universe.json").read_text("utf-8"))
        h.universe = {str(k).upper() for k in meta if not str(k).startswith("_")}
    except (OSError, ValueError):
        h.universe = None
    try:
        from mt5desk.families import FAMILY_REGISTRY

        def family_params(name: str) -> set[str] | None:
            row = FAMILY_REGISTRY.get(name)
            return set((row or {}).get("defaults") or {}) if row else None
        h.family_params = family_params
    except Exception:
        h.family_params = None

    def bars_available(sym: str, tf: str) -> bool:
        return (UNI / f"{sym}_{tf}.parquet").exists() or (
            tf != "H1" and (UNI / f"{sym}_H1.parquet").exists() and tf in ("H4", "D1"))
    h.bars_available = bars_available
    try:
        from research.frontier_identity import cell_id as _gcell
        h.gauntlet_cell = lambda spec: str(_gcell(dict(spec)))
    except Exception:
        pass
    try:
        from research.universe_policy import may_hypothesise
        h.may_hypothesise = lambda sym, fam: bool(may_hypothesise(sym, fam))
    except Exception:
        pass
    try:
        idx = json.loads(GATE_INDEX.read_text("utf-8"))
        if isinstance(idx, dict):
            h.prior_verdict = lambda gcell: (str(idx[gcell]) if gcell in idx else None)
    except (OSError, ValueError):
        pass

    def donate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        from research import proposer_common as pc
        path = pc.donate(SOURCE, rows, tests_run=len(rows))
        last = dict(getattr(pc, "LAST_DONATION", {}) or {})
        return path is not None, json.dumps({k: last.get(k) for k in (
            "donated", "refused_unstamped", "refused_wrong_lane", "path")}, default=str)
    h.donate = donate

    def handoff(tasks: list[dict[str, Any]]) -> int:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source=SOURCE)
        return len(tasks)
    h.handoff = handoff
    return h


# ============================================================================ pipeline
@dataclass
class PassReport:
    started: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    records_processed: int = 0
    cells_created: int = 0
    donated: int = 0
    verdicts_joined: int = 0
    handed_off: int = 0
    errors: list[str] = field(default_factory=list)


class Pipeline:
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
        # the docket snapshot beside the gauntlet ledger: data/hypotheses/miner_candidates.json
        self.candidates = self.gate_ledger.parent / "miner_candidates.json"
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

    # --------------------------------------------------------------------- 4. join
    def join_verdicts(self, now: datetime | None = None) -> int:
        try:
            size = self.gate_ledger.stat().st_size
        except OSError:
            return 0
        off = int(self.cells.kv_get("gate_ledger_offset", "0") or 0)
        if off > size:
            off = 0                                       # ledger rotated
        joined = 0
        with self.gate_ledger.open("rb") as fh:
            fh.seek(off)
            for raw in fh:
                if not raw.endswith(b"\n"):
                    break                                 # a row still being written
                off += len(raw)
                try:
                    v = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if not isinstance(v, dict):
                    continue
                for cell, axis in self.cells.by_alias(str(v.get("cell") or "")):
                    if cell.status in ("EVALUATING", "EVALUATED"):
                        joined += self._apply_verdict(cell, v, axis=axis, now=now)
        self.cells.kv_set("gate_ledger_offset", str(off))
        return joined

    # --------------------------------------------------- the one registry: global attribution
    def index_judged(self, now: datetime | None = None) -> int:
        """Every judged docket cell, whoever minted it, into `judged_cells` (own byte offset, so
        the first pass reads the whole ledger once and every later one only what is new)."""
        try:
            size = self.gate_ledger.stat().st_size
        except OSError:
            return 0
        off = int(self.cells.kv_get("judged_offset", "0") or 0)
        off = 0 if off > size else off
        batch: list[tuple[str, str, bool]] = []
        stamp = iso(now or utcnow())
        with self.gate_ledger.open("rb") as fh:
            fh.seek(off)
            for raw in fh:
                if not raw.endswith(b"\n"):
                    break
                off += len(raw)
                try:
                    v = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if not isinstance(v, dict) or not v.get("cell"):
                    continue
                if rejection.reason_for_verdict(v)[1] == "DEFERRED":
                    continue
                batch.append((str(v["cell"]), str(v.get("at") or stamp), bool(v.get("passed"))))
                if len(batch) >= 20_000:
                    self.cells.record_judged(batch)
                    batch = []
        self.cells.record_judged(batch)
        self.cells.kv_set("judged_offset", str(off))
        return off

    def _url_index(self) -> dict[str, list[tuple[str, str]]]:
        idx: dict[str, list[tuple[str, str]]] = {}
        for s in self.roster:
            if s.url_key:
                host, _, path = s.url_key.partition("/")
                idx.setdefault(host, []).append(("/" + path.split("?", 1)[0], s.id))
        return idx

    def attribute_source(self, cand: Mapping[str, Any],
                         idx: Mapping[str, list[tuple[str, str]]]) -> str:
        """The registry source a docket candidate came from, or "" when it names none we hold.

        URL first, longest path prefix on the same host; a host with exactly one registered
        source takes it. Then the seat (`miner:<id>` naming a registry id or alias)."""
        key = acq.canonical_url(cand.get("source_url"))
        if key:
            host, _, path = key.partition("/")
            path = "/" + path.split("?", 1)[0]
            rows = idx.get(host) or []
            hits = sorted(((len(p), sid) for p, sid in rows
                           if path == p or path.startswith(p.rstrip("/") + "/")), reverse=True)
            if hits:
                return hits[0][1]
            if len({sid for _, sid in rows}) == 1:
                return rows[0][1]
        seat = str(cand.get("source") or "").removeprefix("miner:")
        if seat in self.by_id:
            return seat
        return self._alias_of.get(seat, "")

    @property
    def _alias_of(self) -> dict[str, str]:
        return {a: s.id for s in self.roster for a in s.aliases}

    def attributed_evaluations(self, now: datetime | None = None) -> dict[str, Any]:
        """Per registry source: docket cells EVALUATED within ACTIVE_WINDOW, joined through the
        compiler's candidates (source_url / seat -> symbol, family, params -> gauntlet cell and
        its chart x session expansion -> judged_cells). The docket snapshot is the compiler's
        CURRENT one, so a candidate that has left it is not attributed: an undercount, stated."""
        t = now or utcnow()
        try:
            doc = json.loads(self.candidates.read_text("utf-8"))
        except (OSError, ValueError):
            return {"by_source": {}, "basis": f"UNMEASURED: {self.candidates.name} unreadable"}
        cands = doc.get("hypotheses") if isinstance(doc, dict) else doc
        judged = self.cells.judged_since(t - ACTIVE_WINDOW)
        idx = self._url_index()
        by: dict[str, set[str]] = {}
        unattributed = 0
        for c in cands if isinstance(cands, list) else []:
            if not isinstance(c, dict) or not c.get("symbol") or not c.get("family"):
                continue
            spec = {"symbol": c["symbol"], "family": c["family"],
                    "params": dict(c.get("params") or {})}
            ids = {self.hooks.gauntlet_cell(spec), *self._expanded(spec).values()}
            hit = ids & judged.keys()
            if not hit:
                continue
            sid = self.attribute_source(c, idx)
            if not sid:
                unattributed += len(hit)
                continue
            by.setdefault(sid, set()).update(hit)
        return {"by_source": {k: len(v) for k, v in by.items()},
                "unattributed_judged_cells": unattributed,
                "basis": f"{self.candidates.name} x judged_cells ({len(judged)} judged in window)"}

    def register_cursors(self, now: datetime | None = None) -> int:
        """A durable cursor per canonical source, carrying its registration; fetch state kept."""
        wrote = 0
        for s in self.roster:
            reg = {"canonical_id": s.id, "origin": s.origin, "owner": s.owner,
                   "url_key": s.url_key, "aliases": sorted(s.aliases),
                   "shares_page": sorted(s.shares_page)}
            cur = self.cursors.get(s.id)
            old = {k: v for k, v in (cur.get("registered") or {}).items() if k != "first_seen"}
            if old != reg:
                reg["first_seen"] = (cur.get("registered") or {}).get("first_seen") or iso(
                    now or utcnow())
                self.cursors.save(s.id, {**cur, "registered": reg})
                wrote += 1
        return wrote

    def _apply_verdict(self, cell: Cell, v: Mapping[str, Any], *, axis: str = "as_donated",
                       now: datetime | None = None) -> int:
        """One docket cell's verdict onto its mining cell.

        The FIRST judged docket cell settles the mining cell (EVALUATED, with that gate's reason
        or as a survivor). Every later one is recorded per axis, and a later pass on any axis
        makes the mining cell a survivor -- the docket judged it, so the count is the docket's.
        A docket cell outside the sealed expansion is FAILS_PREREG."""
        reason, gate = rejection.reason_for_verdict(v)
        if gate == "DEFERRED":
            return 0
        g = str(v.get("cell") or "")
        try:
            contract = self.prereg.load(cell.cell_id)
            sealed = {str(contract.get("gauntlet_cell") or ""),
                      *[str(x) for x in (contract.get("gauntlet_cells_expanded") or {}).values()]}
            spec = prereg.spec_of(contract)
            recomputed = {self.hooks.gauntlet_cell(spec), *self._expanded(spec).values()}
            ok = g in sealed and g in recomputed
            why = "" if ok else (f"judged {g}, which is not in the sealed expansion "
                                 f"({len(sealed)} cells) or its recomputation")
        except (OSError, ValueError, prereg.PreregMutationError) as exc:
            ok, why = False, str(exc)
        at = str(v.get("at") or iso(now or utcnow()))
        if not self.cells.record_axis_verdict(cell.cell_id, g, axis, at, bool(v.get("passed")),
                                              str(v.get("terminal_gate") or ""),
                                              "" if reason is None else reason.value):
            return 0                                          # this docket cell already joined
        verdict = {"gauntlet_cell": g, "axis": axis, "passed": bool(v.get("passed")),
                   "terminal_gate": v.get("terminal_gate"), "at": v.get("at"),
                   "downstream_status": v.get("downstream_status")}
        if cell.status == "EVALUATED":
            if ok and reason is None and not (cell.verdict or {}).get("survivor"):
                self.cells.update_doc(cell.cell_id, {"verdict": {
                    **(cell.verdict or {}), "survivor": True, "survivor_axis": verdict}})
            return 1
        if not ok:
            self.cells.transition(cell.cell_id, "EVALUATED", stage="preregister",
                                  reason="FAILS_PREREG", now=now, updates={"verdict": verdict})
            self.ledger.reject(cell.cell_id, "FAILS_PREREG", "preregister", detail=why,
                               source_id=cell.source_id)
            return 1
        if reason is None:
            self.cells.transition(cell.cell_id, "EVALUATED", stage="gauntlet", now=now,
                                  updates={"verdict": {**verdict, "survivor": True}})
            return 1
        self.cells.transition(cell.cell_id, "EVALUATED", stage="gauntlet",
                              reason=reason.value, now=now, updates={"verdict": verdict})
        self.ledger.reject(cell.cell_id, reason.value, "gauntlet", source_id=cell.source_id,
                           detail=f"terminal gate {gate} ({axis})",
                           kill_class=rejection.kill_class(gate))
        return 1

    # --------------------------------------------------------------------- deepening
    def handoff_deepening(self) -> int:
        if self.hooks.handoff is None:
            return 0
        cells = [c for c in self.cells.by_status("RESEARCH_ONLY", limit=50_000)
                 if (c.verdict or {}).get("handoff")][-DEEPENING_CAP:]
        tasks = [{
            "source": SOURCE, "kind": "story_mechanism",
            "title": f"{c.source_id}: {c.claim[:90]}",
            "description": (f"Verbatim claim ({c.original_language}): {c.claim}. MT5 "
                            f"instruments: {c.required_instruments or 'none named'}. "
                            f"Provenance: {c.source_uri}, available "
                            f"{c.available_for_decision_at}. Extract the exact mechanism as a "
                            "registered MT5 family and parameters if the text states one; "
                            "otherwise reject with why. Stated performance is not evidence."),
            "url": c.source_uri, "symbols": c.required_instruments,
            "mechanism_class": c.mechanism_family, "mechanism_key": c.mechanism_hash,
            "lang": c.original_language, "available_time": c.available_for_decision_at,
            "mining_cell_id": c.cell_id,
            "consumer": "deepening_worker (story_mechanism) -> miner_candidate_compiler -> "
                        "gauntlet"} for c in cells]
        return self.hooks.handoff(tasks) if tasks else 0

    # --------------------------------------------------------------------- 5. metrics
    def source_status(self, now: datetime | None = None) -> dict[str, dict[str, Any]]:
        t = now or utcnow()
        receipts = self.cells.evaluated_by_source(t - ACTIVE_WINDOW)
        try:
            docket = self.attributed_evaluations(t)
        except Exception as exc:                          # never lets status reporting fail
            docket = {"by_source": {}, "basis": f"ERROR {type(exc).__name__}: {exc}"[:200]}
        self._attribution = {k: v for k, v in docket.items() if k != "by_source"}
        via = docket["by_source"]
        runs = self.store.last_runs()
        recs = self.store.records_by_source()
        out = {}
        for s in self.roster:
            if not s.enabled:
                continue
            n_mine, n_docket = int(receipts.get(s.id, 0)), int(via.get(s.id, 0))
            n = n_mine + n_docket
            r = runs.get(s.id) or {}
            # Every use mints cells now: allocation_intel's facts become exogenous_conditioner
            # cells (see `conditioners`), so each use can carry a receipt.
            cell_use = bool(set(compiler.USES) & set(s.uses))
            out[s.id] = {"status": "ACTIVE" if n >= 1 and cell_use else "COLD",
                         "uses": list(s.uses),
                         "cold_reason": ("" if n >= 1 and cell_use else
                                         "serves no use" if not cell_use else
                                         "no cell EVALUATED in 30 days"),
                         "consumer": s.consumer,
                         "evaluated_cells_30d": n, "priority": s.priority,
                         "evaluated_via": {"mining": n_mine, "docket": n_docket},
                         "origin": s.origin, "url_key": s.url_key, "aliases": list(s.aliases),
                         "shares_page": list(s.shares_page),
                         "last_outcome": r.get("outcome") or "NEVER_RUN",
                         "last_run": r.get("at"), "last_detail": r.get("detail") or "",
                         "records_total": int(recs.get(s.id, 0)), "auth": s.auth,
                         "owner": s.owner, "mode": s.mode}
        return out

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
                "by_owner": dict(sorted(by_owner.items()))}

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
               "chains": chains,
               "rejections_latest": rej}
        self.digest.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.digest.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n",
                       "utf-8")
        with contextlib.suppress(OSError):
            os.chmod(self.digest, 0o644)                  # Windows: never replace a read-only file
        os.replace(tmp, self.digest)

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


def _pct(vals: list[float], q: float) -> float:
    s = sorted(vals)
    k = max(0, min(len(s) - 1, round(q / 100 * (len(s) - 1))))
    return round(s[k], 3)


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
