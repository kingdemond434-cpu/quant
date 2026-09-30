"""THE PYTHON WORLDQUANT RESIDENT: deterministic workers over public BRAIN / Alpha101 material.

    zuck, 2026-09-30: "Do not replace your existing BRAIN Hunter. Add a second, deterministic
    Python WorldQuant civilization running 24/7 ... They should feed the same registry and never
    duplicate work."

The existing LLM BRAIN hunter (ops/run_brain_hunter.sh) stays the SEMANTIC lane: prose, video,
community, obscure relationships. This module is the EXHAUSTIVE lane: every record from a
`civilization: worldquant` source passes through the workers below, and anything the LLM hunter
hands back (`llm_handback.jsonl`) is re-parsed and re-verified here before it may become a cell.

    operator miner          OperatorCatalogue: names, arities, keyword args, window ranges
    data-field miner        FieldTaxonomy: identifiers by category, unknowns kept, never dropped
    expression archaeologist  expression.extract_formulas + genome_of
    Alpha101 lineage miner  lineage(): per-alpha implementation disagreement vs the paper
    research-method miner   METHOD_PATTERNS -> RESEARCH_METHOD rows (search machinery, not rules)
    failure miner           FAILURE_PATTERNS -> FAILURE_KNOWLEDGE rows
    MT5 translator          expression.to_mt5 -> the desk's `formula` family
    representation compiler  representation_gaps(): operators public practice uses that the
                            desk grammar cannot say, ranked by how often they block translation
    candidate generator     descendants(): window neighbours, sign flip, regime-gated children --
                            all charged to the PARENT's trial family (never a new family)
    dedup / ancestry        GenomeIndex: genome hash -> first owner; skeleton -> siblings
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from libs.civilizations import expression as E

DATA = Path(__file__).resolve().parent / "data"
ALPHA101 = DATA / "alpha101_formulas.json"


# ---------------------------------------------------------------------------- operator miner
@dataclass
class OperatorCatalogue:
    """Every operator the public corpus uses, with what was observed about it."""
    ops: dict[str, dict[str, Any]] = field(default_factory=dict)

    def observe(self, node: E.Node, *, source_id: str) -> list[str]:
        new: list[str] = []
        for n in E.walk(node):
            if n[0] != "call":
                continue
            name = n[1]
            row = self.ops.get(name)
            if row is None:
                row = self.ops[name] = {
                    "name": name, "class": E.OPERATOR_CLASS.get(name, "unknown"),
                    "arities": [], "kwargs": [], "window_min": None, "window_max": None,
                    "n": 0, "sources": []}
                new.append(name)
            row["n"] += 1
            if len(n[2]) not in row["arities"]:
                row["arities"] = sorted({*row["arities"], len(n[2])})
            row["kwargs"] = sorted({*row["kwargs"], *(k for k, _ in n[3])})
            if E.OPERATOR_CLASS.get(name) == "time_series":
                for a in n[2][1:]:
                    if a[0] == "num" and a[1] >= 1:
                        w = round(a[1])
                        row["window_min"] = w if row["window_min"] is None else min(
                            row["window_min"], w)
                        row["window_max"] = w if row["window_max"] is None else max(
                            row["window_max"], w)
            if source_id not in row["sources"] and len(row["sources"]) < 50:
                row["sources"].append(source_id)
        return new

    def to_json(self) -> dict[str, Any]:
        return {"n_operators": len(self.ops),
                "unknown_class": sorted(k for k, v in self.ops.items() if v["class"] == "unknown"),
                "operators": dict(sorted(self.ops.items()))}

    @classmethod
    def load(cls, path: Path) -> OperatorCatalogue:
        try:
            doc = json.loads(Path(path).read_text("utf-8"))
            return cls(dict(doc.get("operators") or {}))
        except (OSError, ValueError):
            return cls()


# --------------------------------------------------------------------------- data-field miner
@dataclass
class FieldTaxonomy:
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)

    def observe(self, node: E.Node, *, source_id: str) -> list[str]:
        new = []
        for f in E.fields_in(node):
            row = self.fields.get(f)
            if row is None:
                row = self.fields[f] = {"field": f, "category": E.field_category(f), "n": 0,
                                        "sources": [], "on_mt5_bars": f in E.BAR_FIELDS
                                        or f in E.APPROX_FIELDS
                                        or bool(re.fullmatch(r"adv\d+", f))}
                new.append(f)
            row["n"] += 1
            if source_id not in row["sources"] and len(row["sources"]) < 50:
                row["sources"].append(source_id)
        return new

    def by_category(self) -> dict[str, int]:
        return dict(Counter(v["category"] for v in self.fields.values()))

    def to_json(self) -> dict[str, Any]:
        return {"n_fields": len(self.fields), "by_category": self.by_category(),
                "fields": dict(sorted(self.fields.items()))}

    @classmethod
    def load(cls, path: Path) -> FieldTaxonomy:
        try:
            doc = json.loads(Path(path).read_text("utf-8"))
            return cls(dict(doc.get("fields") or {}))
        except (OSError, ValueError):
            return cls()


# ------------------------------------------------------------------------- dedup / ancestry
@dataclass
class GenomeIndex:
    """genome hash -> first owner (the discovery); skeleton -> every genome sharing it."""
    owner: dict[str, str] = field(default_factory=dict)
    siblings: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def claim(self, g: E.Genome, item_id: str) -> str | None:
        """None when `g` is new (and now owned by item_id); else the existing owner."""
        prior = self.owner.get(g.genome)
        if prior is not None:
            return prior
        self.owner[g.genome] = item_id
        if g.genome not in self.siblings[g.skeleton]:
            self.siblings[g.skeleton].append(g.genome)
        return None

    def to_json(self) -> dict[str, Any]:
        return {"owner": self.owner, "siblings": dict(self.siblings)}

    @classmethod
    def load(cls, path: Path) -> GenomeIndex:
        try:
            doc = json.loads(Path(path).read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        gi = cls(dict(doc.get("owner") or {}))
        for k, v in (doc.get("siblings") or {}).items():
            gi.siblings[k] = list(v)
        return gi


# ------------------------------------------------------------------ research-method / failure
METHOD_PATTERNS: dict[str, re.Pattern[str]] = {
    "genetic_programming": re.compile(r"genetic programming|gplearn|\bGP\b|symbolic regression"
                                      r"|evolutionary", re.I),
    "mcts": re.compile(r"monte carlo tree search|\bMCTS\b", re.I),
    "bayesian_optimisation": re.compile(r"bayesian optimi[sz]|gaussian process|optuna|hyperopt",
                                        re.I),
    "llm_generation": re.compile(r"\bLLM\b|large language model|gpt-?\d|prompt", re.I),
    "neutralisation_choice": re.compile(r"neutrali[sz]ation|neutralize|market neutral|sector "
                                        r"neutral|industry neutral", re.I),
    "turnover_control": re.compile(r"turnover|decay_linear|trade_when|hump|holding period", re.I),
    "correlation_screening": re.compile(r"self[- ]correlation|prod(uction)? correlation|"
                                        r"correlation (check|cutoff|threshold)", re.I),
    "diversity_maintenance": re.compile(r"diversity|novelty|niche|crowding distance|"
                                        r"orthogonal", re.I),
    "fitness_function": re.compile(r"fitness|sharpe \* sqrt|returns? / turnover|IC ?IR|"
                                   r"information coefficient", re.I),
    "factor_combination": re.compile(r"combin(e|ation) (of )?(alphas|factors|signals)|"
                                     r"mega[- ]alpha|super[- ]alpha|ensemble", re.I),
    "data_field_selection": re.compile(r"data ?field (selection|exploration)|field importance|"
                                       r"dataset exploration", re.I),
    "memory_and_queues": re.compile(r"candidate queue|alpha pool|memory|archive of alphas|"
                                    r"hall of fame", re.I),
    "experiment_scheduling": re.compile(r"schedul|batch simulat|simulation queue|rate limit",
                                        re.I),
    "failure_storage": re.compile(r"failed alphas|rejected|negative results|blacklist", re.I),
}
FAILURE_PATTERNS: dict[str, re.Pattern[str]] = {
    "overfitting": re.compile(r"overfit|curve[- ]fit|in[- ]sample only|data[- ]snoop", re.I),
    "self_correlation_rejection": re.compile(r"self[- ]correlation|too correlated|"
                                             r"prod(uction)? correlation", re.I),
    "turnover_failure": re.compile(r"turnover (too|is) high|high turnover|churn", re.I),
    "decay_after_submission": re.compile(r"decay|stopped working|out[- ]of[- ]sample (drop|fail)"
                                         r"|OS (sharpe|performance)", re.I),
    "data_leakage": re.compile(r"look[- ]?ahead|leak|future (data|information)|survivorship",
                               re.I),
    "concentration": re.compile(r"concentrat|weight (too|is) high|max weight|few stocks", re.I),
    "sub_universe_failure": re.compile(r"sub[- ]universe|fails? on (top|small)", re.I),
    "cost_blowup": re.compile(r"transaction cost|slippage|after costs", re.I),
}


def tag(text: str, bank: Mapping[str, re.Pattern[str]]) -> list[str]:
    return [k for k, rx in bank.items() if rx.search(text or "")]


# -------------------------------------------------------------------------- Alpha101 lineage
def canonical_alpha101() -> dict[int, str]:
    try:
        doc = json.loads(ALPHA101.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {int(k): str(v) for k, v in (doc.get("formulas") or {}).items()}


def lineage(implementations: Mapping[str, Mapping[int, str]]) -> dict[str, Any]:
    """Per alpha: which implementations agree with the paper (same genome), which differ by
    constants only (same skeleton), and which are a DIFFERENT expression (a disagreement or a
    bug worth a cell of its own). `implementations` is {source_id: {alpha_no: formula}}."""
    paper = canonical_alpha101()
    out: dict[str, Any] = {}
    for n, ref in paper.items():
        try:
            gref = E.genome_of(ref)
        except (E.ParseError, RecursionError):
            continue
        row: dict[str, Any] = {"paper": gref.canonical, "agree": [], "constants_differ": [],
                               "different": [], "unparsed": []}
        for src, impl in implementations.items():
            f = impl.get(n)
            if not f:
                continue
            try:
                g = E.genome_of(f)
            except (E.ParseError, RecursionError):
                row["unparsed"].append(src)
                continue
            if g.genome == gref.genome:
                row["agree"].append(src)
            elif g.skeleton == gref.skeleton:
                row["constants_differ"].append(src)
            else:
                row["different"].append({"source": src, "expr": g.canonical})
        if any(row[k] for k in ("agree", "constants_differ", "different", "unparsed")):
            out[str(n)] = row
    n_diff = sum(1 for r in out.values() if r["different"])
    return {"alphas_seen": len(out), "alphas_with_disagreement": n_diff, "per_alpha": out}


# ------------------------------------------------------------------ representation compiler
def representation_gaps(untranslated: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Why public expressions could not be said on MT5 bars, ranked by how many they block:
    the representation compiler's queue (a grammar operator added there unlocks every one)."""
    c: Counter[str] = Counter()
    ex: dict[str, str] = {}
    for r in untranslated:
        reason = str(r.get("reason") or "")
        c[reason] += 1
        ex.setdefault(reason, str(r.get("expr") or "")[:160])
    return [{"blocker": k, "expressions_blocked": v, "example": ex[k]}
            for k, v in c.most_common()]


# ---------------------------------------------------------------------- candidate generator
def descendants(expr: Any, *, max_n: int = 4) -> list[tuple[str, Any]]:
    """Children of a translated MT5 expression: the neighbouring window on each windowed node
    and the sign flip. All are charged to the parent's trial family by the caller; they widen
    the local search, they are never counted as new mechanisms."""
    windows = E.WINDOWS
    out: list[tuple[str, Any]] = [("sign_flip", ["neg", expr])] if not (
        isinstance(expr, list) and expr and expr[0] == "neg") else [("sign_flip", expr[1])]

    def paths(e: Any, p: tuple[int, ...] = ()) -> Iterable[tuple[int, ...]]:
        if isinstance(e, list):
            if e and isinstance(e[-1], int) and e[-1] in windows:
                yield (*p, len(e) - 1)
            for i, c in enumerate(e[1:], 1):
                yield from paths(c, (*p, i))

    def replace(e: Any, p: tuple[int, ...], v: Any) -> Any:
        if not p:
            return v
        e = list(e)
        e[p[0]] = replace(e[p[0]], p[1:], v)
        return e

    for p in paths(expr):
        node = expr
        for i in p[:-1]:
            node = node[i]
        w = node[p[-1]]
        k = windows.index(w)
        for nb in (k - 1, k + 1):
            if 0 <= nb < len(windows) and len(out) < max_n:
                out.append((f"window_{w}->{windows[nb]}", replace(expr, p, windows[nb])))
        if len(out) >= max_n:
            break
    return out[:max_n]
