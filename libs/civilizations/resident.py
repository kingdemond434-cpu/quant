"""THE RESIDENT: the civilizations' per-record router and per-pass workers, inside the #133 spine.

Wiring (desks/mt5/research/mining_supervisor.py):

    acquire (all lanes, cursors)                         -- spine, unchanged
    process: for a civilization record  Resident.route() -> ontology outcomes
             non-alpha -> outcome ledgers, record ROUTED   (never the gauntlet)
             alpha     -> extractor rules + LEAN rule + WQ expression rules
                          -> Resident.park()   (dedup, falsify, novelty, buildability, PARKED)
    civilizations step: Resident.after_pass()
             release parked candidates at the judge's drain rate -> spine compile/dedup/prereg
             frontier (discovered repos -> new git_mirror lanes), LLM hand-back verification,
             forward laboratory, Alpha101 lineage, ROI, coverage tensor + missions, feed fence
    donate / join / handoff                              -- spine, unchanged

Runs every hourly `global_mining` pass, and continuously when `civilization_resident.py --loop`
holds the heartbeat (the hourly leg then leaves the civilization lanes to it). Either way the
same registry, the same dedup index and the same trial families: the LLM hunter, this Python
lane and every other miner never count one mechanism twice.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import re
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from libs.civilizations import backpressure as BP
from libs.civilizations import coverage as CV
from libs.civilizations import expression as E
from libs.civilizations import fetchers  # noqa: F401  (registers git_mirror / sitemap)
from libs.civilizations import forward as FW
from libs.civilizations import graph as G
from libs.civilizations import lean as L
from libs.civilizations import ontology as O
from libs.civilizations import roi as R
from libs.civilizations import worldquant as WQ

ROSTER = Path("desks/mt5/data/source_rosters/civilizations.yaml")
FRONTIER = Path("desks/mt5/data/source_rosters/civilizations_frontier.jsonl")
JUDGE_COVERAGE = Path("desks/mt5/reports/JUDGE_COVERAGE.json")
HEARTBEAT_FRESH = timedelta(minutes=20)
FRONTIER_PER_PASS = 25
HANDBACK_SOURCE = "brain_llm_handback"
CRYPTO_VENUE = re.compile(r"(?<![a-z])(binance|bybit|okx|hyperliquid|kraken|coinbase|bitfinex|"
                          r"gdax|ftx|dydx|kucoin|huobi|deribit|bitmex)", re.I)
CULTURE_FIELDS = ("source_culture", "participant_structure", "failure_mode_hypothesis",
                  "crowding_prior")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def culture_of(meta: Mapping[str, Any]) -> dict[str, Any]:
    """The four #139 fields as the lane DECLARED them; absent is UNMEASURED, never guessed."""
    row = {f: meta.get(f) or "UNMEASURED" for f in CULTURE_FIELDS}
    if row["source_culture"] == "UNMEASURED" or row["participant_structure"] == "UNMEASURED":
        row["failure_mode_hypothesis"] = "UNMEASURED"
    row["culture_derivation"] = {f: ("declared" if meta.get(f) else "UNMEASURED")
                                 for f in CULTURE_FIELDS}
    try:                                          # #139's validator, once it is merged
        cc = importlib.import_module("libs.research.cell_culture")
        row["culture_problems"] = cc.validate(row)
    except Exception:                             # optional organ
        row["culture_problems"] = "UNMEASURED: libs.research.cell_culture not on this tree"
    return row


def load_meta(root: Path) -> dict[str, dict[str, Any]]:
    """source id -> civilization metadata, from the roster and the frontier file."""
    out: dict[str, dict[str, Any]] = {}
    try:
        doc = yaml.safe_load((root / ROSTER).read_text("utf-8")) or {}
    except (OSError, yaml.YAMLError):
        doc = {}
    for r in doc.get("sources") or []:
        if isinstance(r, Mapping) and r.get("id") and r.get("civilization"):
            out[str(r["id"])] = dict(r)
    for r in G.iter_json_rows(root / FRONTIER):
        if r.get("id") and r.get("civilization") and str(r["id"]) not in out:
            out[str(r["id"])] = dict(r)
    out.setdefault(HANDBACK_SOURCE, {
        "id": HANDBACK_SOURCE, "civilization": "worldquant", "lane": "llm_handback",
        "ontology_hint": ["ALPHA_MECHANISM"], "source_culture": "GLOBAL",
        "participant_structure": "mixed", "crowding_prior": "UNMEASURED",
        "failure_mode_hypothesis": "semantic-lane proposals, verified here"})
    return out


@dataclass
class RouteResult:
    alpha: bool
    outcomes: list[O.Outcome]
    rules: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


class Resident:
    def __init__(self, *, data_dir: Path, reports_dir: Path, root: Path) -> None:
        self.root = Path(root)
        self.data = Path(data_dir)
        self.reports = Path(reports_dir)
        self.data.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)
        (self.data / "outcomes").mkdir(exist_ok=True)
        self.meta = load_meta(self.root)
        self.kg = G.KnowledgeGraph(self.data / "knowledge.db")
        self.ops = WQ.OperatorCatalogue.load(self.reports / "OPERATOR_CATALOGUE.json")
        self.fields = WQ.FieldTaxonomy.load(self.reports / "FIELD_TAXONOMY.json")
        self.genomes = WQ.GenomeIndex.load(self.data / "genome_index.json")
        self.parked = BP.ParkedQueue(self.data / "parked.jsonl")
        self.tensor = CV.Tensor()
        self.pass_stats: dict[str, Counter[str]] = defaultdict(Counter)
        self.compute: dict[str, float] = defaultdict(float)
        self.untranslated: list[dict[str, Any]] = []
        self.implementations: dict[str, dict[int, str]] = defaultdict(dict)
        self._load_tensor()

    # ------------------------------------------------------------------ identity / heartbeat
    def is_civ(self, source_id: str) -> bool:
        return source_id in self.meta

    def civ_ids(self) -> set[str]:
        return set(self.meta)

    @staticmethod
    def heartbeat_path(data_dir: Path) -> Path:
        return Path(data_dir) / "RESIDENT_HEARTBEAT.json"

    @classmethod
    def loop_is_live(cls, data_dir: Path, now: datetime | None = None) -> bool:
        try:
            doc = json.loads(cls.heartbeat_path(data_dir).read_text("utf-8"))
            at = datetime.fromisoformat(str(doc["at"]).replace("Z", "+00:00"))
        except (OSError, ValueError, KeyError):
            return False
        return (now or _now()) - at < HEARTBEAT_FRESH

    def beat(self, **extra: Any) -> None:
        self.heartbeat_path(self.data).write_text(
            json.dumps({"at": _iso(_now()), **extra}), "utf-8")

    # ------------------------------------------------------------------------------- route
    def route(self, rec: Mapping[str, Any]) -> RouteResult:
        t0 = time.monotonic()
        sid = str(rec.get("source_id") or "")
        try:
            return self._route(rec, sid)
        finally:
            self.compute[sid] += time.monotonic() - t0

    def _route(self, rec: Mapping[str, Any], sid: str) -> RouteResult:
        meta = self.meta.get(sid, {})
        civ = str(meta.get("civilization") or "unknown")
        rmeta = rec.get("meta") or {}
        title = str(rec.get("title") or "")
        body = str(rec.get("body") or "")
        uri = str(rec.get("source_uri") or "")
        hints = tuple(meta.get("ontology_hint") or ())
        st = self.pass_stats[sid]
        st["records"] += 1
        methods_only = bool(meta.get("methods_only"))
        if not methods_only and CRYPTO_VENUE.search(f"{uri}\n{title}\n{rmeta.get('path') or ''}"):
            outs = [O.Outcome(O.NO_VALUE, 0.0, ["crypto venue (MT5 mandate 2026-08-18)"])]
            self._ledger(rec, meta, outs, {"excluded": "crypto_venue"})
            return RouteResult(False, outs, reason="crypto venue excluded")
        extra: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        kind = L.lean_record_kind(rmeta)
        path = str(rmeta.get("path") or "")
        if kind == "file" and path and civ == "quantconnect":
            cls, outs = L.outcomes_for(path, body, hints=hints)
            extra["lean_class"] = cls
            if cls in (L.ALPHA_MODEL, L.PORTFOLIO, L.RISK, L.EXECUTION, L.UNIVERSE, L.REALITY,
                       L.INDICATOR, L.STRATEGY):
                comp = L.component_record(path, body)
                extra["component"] = comp
                self._component_node(civ, comp, uri)
            if cls in (L.REGRESSION, L.TEST, L.REALITY):
                extra["lessons"] = L.regression_lessons(path, body)
            if O.is_alpha(outs):
                lr = L.lean_rule(body)
                if lr["indicators"] or lr["patterns"]:
                    lr["mechanism_family"] = "lean_alpha"
                    lr["claim"] = f"LEAN {cls} {path}"
                    rules.append(lr)
        elif kind == "commit":
            outs = O.classify(f"{title}\n{body}", hints=hints)
            extra["issue_categories"] = L.classify_issue(title, body)
        elif "/issues/" in uri or "/pull/" in uri:
            outs = O.classify(f"{title}\n{body}", hints=hints,
                              forced=(O.FAILURE_KNOWLEDGE,) if "/issues/" in uri else ())
            extra["issue_categories"] = L.classify_issue(title, body)
        else:
            outs = O.classify(f"{title}\n{body}", hints=hints)
            if kind == "file" and path and O.is_alpha(outs):
                # any public code file: indicator calls with stated periods (LEAN, TA-Lib,
                # backtrader, vectorbt all name them the same way) become a published rule
                lr = L.lean_rule(body)
                if lr["indicators"] or lr["patterns"]:
                    lr["mechanism_family"] = "code_rule"
                    lr["claim"] = f"{civ} code {path}"
                    rules.append(lr)
        text = f"{title}\n{body}"
        extra["method_tags"] = WQ.tag(text, WQ.METHOD_PATTERNS)
        extra["failure_tags"] = WQ.tag(text, WQ.FAILURE_PATTERNS)
        if extra["method_tags"] and not any(o.kind == O.RESEARCH_METHOD for o in outs) and \
                O.RESEARCH_METHOD in hints:
            outs.append(O.Outcome(O.RESEARCH_METHOD, O.THRESHOLD, ["method_tags"]))
        # --- the expression archaeologist runs on EVERY civilization record
        found = E.extract_formulas(text)
        if found:
            st["formulas"] += len(found)
            expr_rules, expr_info = self._expression_rules(rec, meta, found)
            rules.extend(expr_rules)
            extra["formulas"] = expr_info
            if expr_rules and not O.is_alpha(outs):
                outs.insert(0, O.Outcome(O.ALPHA_MECHANISM, O.THRESHOLD, ["translated_expr"]))
        if methods_only:
            # a methods-only lane (a competition whose data or venue is outside the mandate):
            # its features, validation and online-learning know-how are kept, its alpha is not
            rules = []
            outs = [o for o in outs if o.kind != O.ALPHA_MECHANISM] or [
                O.Outcome(O.RESEARCH_METHOD, O.THRESHOLD, ["methods_only lane"])]
            extra["methods_only"] = True
        outs = [o for o in outs if o.kind != O.NO_VALUE] or outs
        self._ledger(rec, meta, outs, extra)
        self._tensor_add(civ, meta, rec, outs, extra)
        alpha = O.is_alpha(outs)
        st["alpha" if alpha else "routed"] += 1
        for o in outs:
            st[f"outcome:{o.kind}"] += 1
        return RouteResult(alpha, outs, rules, reason=",".join(O.kinds(outs)))

    # ----------------------------------------------------------------------- expressions
    def _expression_rules(self, rec: Mapping[str, Any], meta: Mapping[str, Any],
                          found: list[tuple[str, str]]) -> tuple[list[dict[str, Any]],
                                                                 list[dict[str, Any]]]:
        sid = str(rec.get("source_id") or "")
        rules: list[dict[str, Any]] = []
        info: list[dict[str, Any]] = []
        for label, text in found:
            try:
                node = E.parse(text)
                g = E.genome_of(text)
            except (E.ParseError, RecursionError):
                continue
            self.ops.observe(node, source_id=sid)
            self.fields.observe(node, source_id=sid)
            if label.startswith("alpha#"):
                with contextlib.suppress(ValueError):
                    self.implementations[sid][int(label[6:])] = text
            novel_skel = g.skeleton not in self.genomes.siblings
            owner = self.genomes.claim(g, f"{rec.get('record_id')}:{label}")
            row = {"label": label, "genome": g.genome, "skeleton": g.skeleton,
                   "operators": g.operators, "fields": g.fields, "duplicate_of": owner}
            self.kg.node(f"expr:{g.genome}", "mechanism", civilization=str(
                meta.get("civilization") or ""), label=g.canonical[:300],
                doc={"skeleton": g.skeleton, "operators": g.operators, "fields": g.fields})
            self.kg.edge(f"source:{sid}", "implements", f"expr:{g.genome}")
            if owner is not None:
                self.pass_stats[sid]["expr_duplicate"] += 1
                info.append(row)
                continue
            try:
                tr = E.to_mt5(node)
            except E.Untranslatable as u:
                row["untranslatable"] = u.reason
                self.untranslated.append({"reason": u.reason, "expr": g.canonical,
                                          "needs": u.needs, "source_id": sid})
                self.pass_stats[sid]["expr_untranslatable"] += 1
                for need in u.needs:
                    self.kg.node(f"field:{need}", "field", label=need,
                                 doc={"category": E.field_category(need)})
                info.append(row)
                continue
            why = BP.cheap_falsify(tr.expr)
            ok, gwhy = E.grammar_valid(tr.expr)
            if why or not ok:
                row["falsified"] = why or gwhy
                self.pass_stats[sid]["expr_falsified"] += 1
                info.append(row)
                continue
            base = {"indicators": {}, "patterns": [], "regimes": [], "hours": [],
                    "lookahead": [], "timeframe": "H1", "symbols": [],
                    "mechanism_family": "formulaic_alpha",
                    "expr_subtype": f"formula:{g.skeleton[:12]}",
                    "claim": f"{label}: {text}"[:480],
                    "approximations": tr.approximations, "genome": g.genome,
                    "skeleton": g.skeleton, "novel_skeleton": novel_skel}
            rules.append({**base, "expr": tr.expr, "expr_published": not tr.approximations})
            for tag_, child in WQ.descendants(tr.expr):
                rules.append({**base, "expr": child, "expr_published": False,
                              "descendant": tag_, "novel_skeleton": False})
            row["translated"] = tr.expr
            self.pass_stats[sid]["expr_translated"] += 1
            info.append(row)
        return rules, info

    # --------------------------------------------------------------------------- parking
    def deepen(self, rec: Mapping[str, Any], route: Any) -> None:
        """An alpha-outcome record the deterministic extractors could not turn into a rule goes
        to the LLM semantic lane (the BRAIN hunter reads llm_deepening.jsonl), never to REJECTED:
        prose naming a mechanism is work for the reader, not a verdict on the mechanism."""
        sid = str(rec.get("source_id") or "")
        meta = self.meta.get(sid, {})
        row = {"at": _iso(_now()), "record_id": rec.get("record_id"), "source_id": sid,
               "civilization": meta.get("civilization"), "lane": meta.get("lane"),
               "uri": rec.get("source_uri"), "title": str(rec.get("title") or "")[:200],
               "outcomes": [o.kind for o in getattr(route, "outcomes", [])],
               "why": "alpha outcome with no deterministic rule"}
        with (self.data / "llm_deepening.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")

    def park(self, rec: Mapping[str, Any], rules: Iterable[Mapping[str, Any]]) -> int:
        """Every alpha rule of a civilization record goes to the durable PARKED queue; the
        release step hands them to the spine at the judge's drain rate."""
        sid = str(rec.get("source_id") or "")
        meta = self.meta.get(sid, {})
        civ = str(meta.get("civilization") or "unknown")
        rows = []
        for r in rules:
            area_key = r.get("skeleton") or r.get("mechanism_family") or "rule"
            body = json.dumps(r, sort_keys=True, default=str)
            cid = "cc_" + hashlib.sha256(f"{rec.get('record_id')}|{body}".encode()
                                         ).hexdigest()[:20]
            rows.append({"candidate_id": cid, "record_id": rec.get("record_id"),
                         "source_id": sid, "civilization": civ, "rule": dict(r),
                         "area": f"{civ}:{area_key}",
                         "novel_skeleton": bool(r.get("novel_skeleton", True)),
                         "crowding_prior": meta.get("crowding_prior") or "UNMEASURED",
                         "published": bool(r.get("expr_published", True)),
                         "parked_at": _iso(_now())})
        self.pass_stats[sid]["parked"] += len(rows)
        return self.parked.park(rows)

    def release(self, pipeline: Any, *, budget: int | None = None,
                now: datetime | None = None) -> dict[str, Any]:
        """Hand the highest-priority parked candidates to the spine's compile/dedup/seal."""
        from libs.mining import extractor
        load = BP.judge_load(self.root / JUDGE_COVERAGE)
        cap = budget if budget is not None else BP.release_budget(load)
        pend = self.parked.pending()
        sat = self.saturated_areas(pipeline)
        chosen = BP.select(pend, cap, sat)
        made = compiled = 0
        done: list[str] = []
        for c in chosen:
            rec = pipeline.store.get(str(c.get("record_id")))
            done.append(str(c["candidate_id"]))
            if rec is None:
                continue
            rule = dict(c.get("rule") or {})
            ex = extractor.Extraction(language=str(rec.get("original_language") or ""),
                                      mechanism_family=str(rule.get("mechanism_family")
                                                           or "other"))
            try:
                n, ok = pipeline._cells_from_rule(rec, ex, rule, now=now)
            except Exception as exc:
                self.pass_stats[str(c.get("source_id"))]["release_error"] += 1
                pipeline.ledger.reject(str(c["candidate_id"]), "NO_ECONOMIC_MECHANISM",
                                       "compile", source_id=str(c.get("source_id")),
                                       detail=f"release {type(exc).__name__}: {exc}"[:300])
                continue
            made += n
            compiled += int(ok)
            self.pass_stats[str(c.get("source_id"))]["cells"] += n
            if n:
                pipeline.store.set_state(str(rec["record_id"]), "EXTRACTED", n_cells=n)
        self.parked.mark_released(done)
        return {"budget": cap, "judge_backlog": load.unjudged if load.measured
                else "UNMEASURED", "pending_before": len(pend), "released": len(done),
                "cells_made": made, "rules_compiled": compiled,
                "saturated_areas": len(sat), "still_parked": len(pend) - len(done)}

    def saturated_areas(self, pipeline: Any) -> set[str]:
        """civilization:skeleton areas with >= SATURATION_JUDGED judged cells, no survivor."""
        judged: Counter[str] = Counter()
        won: Counter[str] = Counter()
        try:
            cells = pipeline.cells.all_cells()
        except Exception:
            return set()
        for cell in cells:
            if cell.source_id not in self.meta:
                continue
            rules = cell.directly_published_rules or cell.reconstructed_rules or {}
            src_rule = rules.get("source_rule") if isinstance(rules, Mapping) else None
            key = (src_rule or {}).get("skeleton") or cell.mechanism_family
            area = f"{self.meta[cell.source_id].get('civilization')}:{key}"
            if cell.verdict:
                judged[area] += 1
                if str((cell.verdict or {}).get("verdict") or cell.status).upper() in (
                        "PASS", "SURVIVOR", "CERTIFIED", "SURVIVED"):
                    won[area] += 1
        return {a for a, n in judged.items() if n >= BP.SATURATION_JUDGED and not won[a]}

    # ------------------------------------------------------------------------ side ledgers
    def _ledger(self, rec: Mapping[str, Any], meta: Mapping[str, Any],
                outs: list[O.Outcome], extra: Mapping[str, Any]) -> None:
        row = {"at": _iso(_now()), "record_id": rec.get("record_id"),
               "source_id": rec.get("source_id"), "civilization": meta.get("civilization"),
               "lane": meta.get("lane"), "uri": rec.get("source_uri"),
               "title": str(rec.get("title") or "")[:200],
               "outcomes": O.kinds(outs), "detail": [o.as_row() for o in outs],
               **culture_of(meta), **{k: v for k, v in extra.items() if v}}
        line = json.dumps(row, default=str, ensure_ascii=False) + "\n"
        for o in outs:
            with (self.data / "outcomes" / f"{o.kind}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(line)

    def _component_node(self, civ: str, comp: Mapping[str, Any], uri: str) -> None:
        if not comp.get("class_name"):
            return
        nid = f"component:{civ}:{comp['class_name']}"
        self.kg.node(nid, "component", civilization=civ, label=str(comp["class_name"]),
                     doc=dict(comp))
        self.kg.edge(nid, "defined_at", uri)

    def _tensor_add(self, civ: str, meta: Mapping[str, Any], rec: Mapping[str, Any],
                    outs: list[O.Outcome], extra: Mapping[str, Any]) -> None:
        lane = str(meta.get("lane") or "")
        fetcher = str(meta.get("fetcher") or "")
        st = ("engine_code" if lane.startswith("lean_") and "regression" not in lane
              else "engine_tests" if "regression" in lane else
              "issues_prs" if lane in ("lean_issues", "lean_prs") else
              "docs_changes" if "docs" in lane else
              "alpha101_lineage" if "alpha101" in lane else
              "public_papers" if "paper" in lane or fetcher == "rss" else
              "public_repositories" if fetcher in ("github_search", "git_mirror") else
              "datasets" if "dataset" in lane or "data_library" in lane else
              "community_discussion" if "forum" in lane or "community" in lane else
              "postmortems" if "fail" in lane else
              "education" if "learning" in lane or "tutorial" in lane else
              "official_docs")
        f = extra.get("formulas") or []
        ops_cls = sorted({E.OPERATOR_CLASS.get(o, "") for r in f for o in r.get("operators", [])}
                         - {""})
        cats = sorted({E.field_category(x) for r in f for x in r.get("fields", [])} - {"unknown"})
        text = f"{rec.get('title') or ''}\n{str(rec.get('body') or '')[:20000]}".lower()
        neut = [n for n in ("market", "sector", "industry", "subindustry", "country")
                if f"{n} neutral" in text or f"indclass.{n}" in text]
        methods = [m for m in extra.get("method_tags") or [] if m in CV.AXES["search_algorithm"]]
        vals = [v for v, words in (("walk_forward", "walk-forward"), ("out_of_sample",
                "out-of-sample"), ("deflated_sharpe", "deflated sharpe"), ("pbo", "backtest "
                "overfitting"), ("bootstrap", "bootstrap"), ("cross_validation", "cross-valid"),
                ("regression_test", "regression")) if words in text]
        hz = [h for h, w in (("intraday", "intraday"), ("daily", "daily"), ("weekly", "weekly"),
                             ("monthly_plus", "monthly")) if w in text]
        self.tensor.add(civ, {"source_type": st, "ontology": O.kinds(outs),
                              "operator_class": ops_cls, "data_category": cats,
                              "neutralization": neut, "search_algorithm": methods,
                              "validation_method": vals, "horizon": hz})

    def _load_tensor(self) -> None:
        """Rebuild marginals from the outcome ledgers, so coverage is lifetime, not per pass."""
        for fp in sorted((self.data / "outcomes").glob("*.jsonl")):
            for row in G.iter_json_rows(fp):
                if row.get("outcomes") and row["outcomes"][0] != fp.stem:
                    continue                           # count each row once (first outcome)
                civ = str(row.get("civilization") or "unknown")
                self.tensor.add(civ, {"ontology": row.get("outcomes") or []})

    # -------------------------------------------------------------------------- after pass
    def after_pass(self, pipeline: Any, *, now: datetime | None = None,
                   budget_s: float = 120.0) -> dict[str, Any]:
        t0 = time.monotonic()
        started = (now or _now()) - timedelta(hours=2)
        out: dict[str, Any] = {}
        steps: tuple[tuple[str, Callable[[], Any]], ...] = (
                 ("release", lambda: self.release(pipeline, now=now)),
                 ("handback", lambda: self.verify_handback(pipeline, now=now)),
                 ("frontier", lambda: self.promote_frontier(pipeline)),
                 ("forward_lab", lambda: self.forward_lab(pipeline)),
                 ("lineage", self.alpha101_lineage),
                 ("ingest", lambda: G.ingest_all(self.kg, self.root)
                  if not (self.data / "INGESTED").exists() else {"skipped": "already"}),
                 ("culture", lambda: self.culture_rows(pipeline, since=started)),
                 ("roi", lambda: self.source_roi(pipeline)),
                 ("coverage", self.coverage),
                 ("fence", lambda: self.feed_fence(pipeline)),
                 ("lanes", lambda: self.lane_status(pipeline, now=now)))
        for name, fn in steps:
            if time.monotonic() - t0 > budget_s and name not in ("culture", "roi", "coverage",
                                                                 "fence", "lanes"):
                out[name] = {"skipped": "budget"}
                continue
            try:
                out[name] = fn()
            except Exception as exc:
                out[name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        if isinstance(out.get("ingest"), dict) and "graph" in out["ingest"]:
            (self.data / "INGESTED").write_text(_iso(_now()), "utf-8")
        self._persist()
        out["pass_stats"] = {k: dict(v) for k, v in self.pass_stats.items()}
        out["graph"] = self.kg.counts()
        self._write("CIVILIZATION_METRICS.json", {"generated_at": _iso(_now()), **out})
        return out

    def _persist(self) -> None:
        self._write("OPERATOR_CATALOGUE.json", self.ops.to_json())
        self._write("FIELD_TAXONOMY.json", self.fields.to_json())
        (self.data / "genome_index.json").write_text(json.dumps(self.genomes.to_json()),
                                                     "utf-8")
        gaps = WQ.representation_gaps(self.untranslated)
        self._write("REPRESENTATION_GAPS.json", {"generated_at": _iso(_now()),
                                                 "blockers": gaps})

    def _write(self, name: str, doc: Any) -> None:
        p = self.reports / name
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
        tmp.replace(p)

    # ------------------------------------------------------------------------ workers
    def verify_handback(self, pipeline: Any, *, now: datetime | None = None
                        ) -> dict[str, Any]:
        """The LLM BRAIN hunter's proposals (llm_handback.jsonl: {text|expression, source_uri,
        why}) become PIT records of `brain_llm_handback`; the spine then re-parses, dedups and
        tests them like any other record. Nothing the LLM says is trusted as parsed."""
        from libs.mining.pit_store import RawRecord, iso, utcnow
        fp = self.data / "llm_handback.jsonl"
        off_p = self.data / "llm_handback.offset"
        try:
            off = int(off_p.read_text("utf-8").strip() or 0)
        except (OSError, ValueError):
            off = 0
        n = new = 0
        try:
            with fp.open(encoding="utf-8") as fh:
                fh.seek(off)
                for line in fh:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    n += 1
                    body = str(row.get("text") or row.get("expression") or "")
                    if not body:
                        continue
                    res = pipeline.store.put(RawRecord(
                        source_id=HANDBACK_SOURCE,
                        source_uri=str(row.get("source_uri") or f"llm:{hash(body)}"),
                        body=body, title=str(row.get("why") or "")[:200],
                        publication_time=None, acquisition_time=iso(now or utcnow()),
                        source_version="v1", original_language="en",
                        immutable_time=False, meta={"kind": "text", "handback": True}),
                        now=now)
                    new += int(res.inserted)
                off = fh.tell()
        except OSError:
            return {"handback_file": "absent", "path": str(fp)}
        off_p.write_text(str(off), "utf-8")
        return {"read": n, "new_records": new}

    def promote_frontier(self, pipeline: Any) -> dict[str, Any]:
        """Repos the WorldQuant/GTJA searches discovered become git_mirror lanes (the source
        frontier: new ground is added as data, never code)."""
        cur = pipeline.cursors.get("wq_repo_frontier")
        found = [str(x) for x in cur.get("discovered") or []]
        have = {str(r.get("id")) for r in G.iter_json_rows(self.root / FRONTIER)}
        added = 0
        rows = []
        for full in found:
            sid = "wqf_" + re.sub(r"[^\w]", "_", full.lower())[:60]
            if sid in have or sid in self.meta or CRYPTO_VENUE.search(full):
                continue
            rows.append({"id": sid, "civilization": "worldquant",
                         "lane": "wq_repository_civilization", "priority": 4,
                         "name": f"frontier repo {full}", "kind": "code",
                         "fetcher": "git_mirror", "cadence_minutes": 1440,
                         "cadence_class": "daily", "immutable_time": True,
                         "uses": ["direct_cells", "indirect_cells"],
                         "ontology_hint": ["ALPHA_MECHANISM", "RESEARCH_METHOD"],
                         "source_culture": "GLOBAL", "participant_structure": "mixed",
                         "crowding_prior": "medium",
                         "failure_mode_hypothesis": "public consultant tooling",
                         "config": {"repo": f"https://github.com/{full}", "files_per_run": 80,
                                    "paths": ["*.py", "*.md", "*.ipynb", "*.txt", "*.json"],
                                    "exclude": ["*/node_modules/*", "*.min.*"]}})
            added += 1
            if added >= FRONTIER_PER_PASS:
                break
        if rows:
            p = self.root / FRONTIER
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
        return {"discovered": len(found), "promoted": added, "frontier_lanes": len(have) + added}

    def forward_lab(self, pipeline: Any) -> dict[str, Any]:
        ids = [s for s, m in self.meta.items() if (m.get("config") or {}).get("forward_track")]
        recs: list[dict[str, Any]] = []
        for sid in ids:
            recs.extend(pipeline.store.vintages(_now(), source_id=sid))
        lab = FW.laboratory(recs)
        self._write("QC_FORWARD_LAB.json", {"generated_at": _iso(_now()), **lab})
        return {k: v for k, v in lab.items() if k != "per_strategy"}

    def alpha101_lineage(self) -> dict[str, Any]:
        lin = WQ.lineage(self.implementations)
        prior = self.reports / "ALPHA101_LINEAGE.json"
        if not self.implementations and prior.exists():
            return {"unchanged": True}
        self._write("ALPHA101_LINEAGE.json", {"generated_at": _iso(_now()), **lin})
        return {k: v for k, v in lin.items() if k != "per_alpha"}

    def lane_status(self, pipeline: Any, *, now: datetime | None = None) -> dict[str, Any]:
        """desks/mt5/reports/CIVILIZATION_LANES.json (CRO D36): every civilization lane with the
        spine's own ACTIVE/COLD verdict (a cell EVALUATED within 30 days) and the last time one
        of its cells was EVALUATED. A lane never evaluated reads NEVER, not a date."""
        t = now or _now()
        status = pipeline.source_status(t)
        try:
            last_eval = pipeline.cells.last_evaluated_by_source()
        except Exception:
            last_eval = {}
        runs: dict[str, Any] = {}
        try:
            runs = pipeline.store.last_runs()
        except Exception:
            runs = {}
        roi_rows: dict[str, Any] = {}
        try:
            roi_rows = json.loads((self.reports / "SOURCE_ROI.json").read_text("utf-8")
                                  ).get("sources") or {}
        except (OSError, ValueError):
            roi_rows = {}
        lanes = []
        for sid in sorted(self.meta):
            m = self.meta[sid]
            st = status.get(sid) or {}
            r = runs.get(sid) or {}
            fun = roi_rows.get(sid) or {}
            lanes.append({
                "id": sid, "civilization": m.get("civilization"), "lane": m.get("lane"),
                "status": st.get("status") or ("DISABLED" if m.get("enabled") is False
                                               else "UNREGISTERED"),
                "cold_reason": st.get("cold_reason", ""),
                "last_evaluated_at": last_eval.get(sid) or "NEVER",
                "evaluated_cells_30d": st.get("evaluated_cells_30d", 0),
                "evaluated_via": st.get("evaluated_via") or {},
                "last_fetch_at": r.get("at") or "NEVER",
                "last_fetch_outcome": r.get("outcome") or "NEVER_RUN",
                "cells_emitted": fun.get("cells_emitted", 0),
                "coverage_depth": fun.get("coverage_depth", "UNMEASURED"),
                "cadence_class": m.get("cadence_class"),
                "methods_only": bool(m.get("methods_only")),
                "source_culture": m.get("source_culture")})
        by: Counter[str] = Counter(str(x["status"]) for x in lanes)
        doc = {"generated_at": _iso(_now()), "rule": "ACTIVE = a cell EVALUATED within 30 days "
               "(libs/mining source_status); last_evaluated_at is all-time",
               "lanes_total": len(lanes), "by_status": dict(by),
               "never_evaluated": sum(1 for x in lanes if x["last_evaluated_at"] == "NEVER"),
               "lanes": lanes}
        p = self.reports.parent / "CIVILIZATION_LANES.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
        tmp.replace(p)
        return {k: v for k, v in doc.items() if k != "lanes"}

    def source_roi(self, pipeline: Any) -> dict[str, Any]:
        since = _now() - timedelta(days=30)
        try:
            recs = pipeline.store.records_by_source()
            new = pipeline.store.records_by_source(since=since)
        except Exception:
            recs, new = {}, {}
        cells: Counter[str] = Counter()
        judged: Counter[str] = Counter()
        won: Counter[str] = Counter()
        mech: Counter[str] = Counter()
        try:
            for c in pipeline.cells.all_cells():
                if c.source_id not in self.meta:
                    continue
                cells[c.source_id] += 1
                mech[c.source_id] += int(not c.duplicate_of)
                if c.verdict:
                    judged[c.source_id] += 1
                    if str((c.verdict or {}).get("verdict") or "").upper() in (
                            "PASS", "SURVIVOR", "CERTIFIED", "SURVIVED"):
                        won[c.source_id] += 1
        except Exception:
            pass
        routed: Counter[str] = Counter()
        for fp in (self.data / "outcomes").glob("*.jsonl"):
            if fp.stem == O.NO_VALUE:
                continue
            for row in G.iter_json_rows(fp):
                routed[str(row.get("source_id"))] += 1
        prior: dict[str, Any] = {}
        try:
            prior = json.loads((self.reports / "SOURCE_ROI.json").read_text("utf-8")
                               ).get("sources") or {}
        except (OSError, ValueError):
            prior = {}
        rows = {}
        for sid in sorted(self.meta):
            acq_s = dict(getattr(pipeline, "acquire_seconds", {}) or {})
            secs = (float((prior.get(sid) or {}).get("compute_seconds") or 0.0)
                    + self.compute.get(sid, 0.0) + float(acq_s.get(sid, 0.0)))
            rows[sid] = R.funnel(sid, cursor=pipeline.cursors.get(sid),
                                 records=int(recs.get(sid, 0)), new=int(new.get(sid, 0)),
                                 mechanisms=mech[sid], cells=cells[sid], judged=judged[sid],
                                 survivors=won[sid], forward=0, outcomes=routed[sid],
                                 compute_seconds=secs)
            rows[sid]["civilization"] = self.meta[sid].get("civilization")
            rows[sid]["lane"] = self.meta[sid].get("lane")
        by_civ: dict[str, Counter[str]] = defaultdict(Counter)
        for r in rows.values():
            for k in ("items_seen", "cells_emitted", "cells_judged", "survivors",
                      "outcomes_routed"):
                by_civ[str(r["civilization"])][k] += int(r[k] or 0)
        budgets = R.budget_shares(rows, total_items=200 * max(1, len(rows)))
        self._write("SOURCE_ROI.json", {"generated_at": _iso(_now()), "weights": R.WEIGHTS,
                                        "sources": rows, "by_civilization":
                                        {k: dict(v) for k, v in by_civ.items()},
                                        "next_pass_item_budget": budgets})
        return {"lanes": len(rows), "by_civilization": {k: dict(v) for k, v in by_civ.items()}}

    def culture_rows(self, pipeline: Any, *, since: datetime) -> dict[str, Any]:
        """Every cell a civilization lane minted gets its lane's four culture fields, keyed by
        cell id and gauntlet cell (the join #139's CELL_CULTURE_INDEX reads)."""
        done_p = self.data / "culture_written.txt"
        try:
            done = set(done_p.read_text("utf-8").split())
        except OSError:
            done = set()
        rows = []
        for c in pipeline.cells.created_since(since):
            if c.source_id not in self.meta or c.cell_id in done:
                continue
            rows.append({"cell_id": c.cell_id, "gauntlet_cell": c.gauntlet_cell,
                         "source_id": c.source_id,
                         "civilization": self.meta[c.source_id].get("civilization"),
                         **culture_of(self.meta[c.source_id])})
        if rows:
            with (self.data / "cell_culture_rows.jsonl").open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, default=str) + "\n")
            with done_p.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(r["cell_id"] for r in rows) + "\n")
        return {"written": len(rows)}

    def coverage(self) -> dict[str, Any]:
        summ = self.tensor.summary()
        miss = CV.missions(self.tensor.empties())
        self._write("COVERAGE_TENSOR.json", {"generated_at": _iso(_now()), **summ})
        self._write("MISSIONS.json", {"generated_at": _iso(_now()), "missions": miss})
        with (self.data / "llm_missions.jsonl").open("w", encoding="utf-8") as fh:
            for m in miss:
                fh.write(json.dumps(m) + "\n")
        return {k: v for k, v in summ.items() if k != "marginals"} | {"missions": len(miss)}

    def feed_fence(self, pipeline: Any) -> dict[str, Any]:
        """The dataset rule: a lane is FED when, within 24h of its first record, it produced a
        routed outcome or a cell. UNFED lanes are listed (target 0); a lane that has fetched
        nothing yet is UNMEASURED, not unfed."""
        first = pipeline.store.first_seen_by_source()
        fed: set[str] = set()
        for fp in (self.data / "outcomes").glob("*.jsonl"):
            if fp.stem == O.NO_VALUE:
                continue
            for row in G.iter_json_rows(fp):
                fed.add(str(row.get("source_id")))
        unfed, unmeasured = [], []
        cutoff = _now() - timedelta(hours=24)
        for sid in sorted(self.meta):
            t = first.get(sid)
            if not t:
                unmeasured.append(sid)
                continue
            try:
                at = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            except ValueError:
                unmeasured.append(sid)
                continue
            if at < cutoff and sid not in fed:
                unfed.append(sid)
        doc = {"generated_at": _iso(_now()), "unfed_count": len(unfed), "target": 0,
               "unfed": unfed, "unmeasured_no_records_yet": unmeasured,
               "fence": "RED" if unfed else "GREEN"}
        self._write("CIV_FEED_FENCE.json", doc)
        return {k: v for k, v in doc.items() if k not in ("unfed", "unmeasured_no_records_yet")}
