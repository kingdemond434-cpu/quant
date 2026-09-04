"""Graveyard intelligence: what kills hypotheses here, predicted before the next one is run.

    P(failure class | hypothesis)      the pre-mortem
    P(survivor | hypothesis)           the meta-model of research success

fitted on the hypothesis graph -- every judged cell with its family, symbol, source, parameter
region and the gates it failed -- by a naive-Bayes-with-Laplace over declared categorical
features. Deliberately simple: the graph holds tens of thousands of FAILED rows and a few dozen
CERTIFIED ones, and a model that can be read off as counts is one whose authority can be
audited. It has none anyway: the compiler annotates candidates with the pre-mortem and the
deepening queue's VOI order uses P(survivor) in place of the pooled family rate, with the same
20% exploration the bandit keeps, so the machine cannot become trapped by its own history.

FAILURE CLASSES are read from the gates a cell failed:

    COST_DEATH            stress_costs / cost gates
    NO_EDGE               expectancy / t-stat / power gates
    SELECTION_BIAS        deflated sharpe / multiplicity
    STATE_FRAGILE         regime / walk-forward stability
    TAIL_FAILURE          drawdown / tail gates
    CORRELATION_DUPLICATE redundancy against the book
    LEAKAGE               lookahead / placebo
    LOW_SAMPLE            too few trades
    EXECUTION_FAILURE     fill / spread refusals
    UNKNOWN               judged FAILED with no gate detail

A new candidate's pre-mortem names the class it most resembles dying of and the cheap falsifier
that class implies (`FIRST_TEST`), which is what `falsifiers` runs first.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

CLASSES: tuple[str, ...] = ("COST_DEATH", "NO_EDGE", "SELECTION_BIAS", "STATE_FRAGILE",
                            "TAIL_FAILURE", "CORRELATION_DUPLICATE", "LEAKAGE", "LOW_SAMPLE",
                            "EXECUTION_FAILURE", "UNKNOWN")
GATE_CLASS: tuple[tuple[str, str], ...] = (
    ("cost", "COST_DEATH"), ("stress", "COST_DEATH"), ("spread", "EXECUTION_FAILURE"),
    ("fill", "EXECUTION_FAILURE"), ("deflated", "SELECTION_BIAS"),
    ("multiplic", "SELECTION_BIAS"), ("placebo", "LEAKAGE"), ("lookahead", "LEAKAGE"),
    ("leak", "LEAKAGE"), ("walk", "STATE_FRAGILE"), ("regime", "STATE_FRAGILE"),
    ("stability", "STATE_FRAGILE"), ("drawdown", "TAIL_FAILURE"), ("tail", "TAIL_FAILURE"),
    ("redund", "CORRELATION_DUPLICATE"), ("corr", "CORRELATION_DUPLICATE"),
    ("sample", "LOW_SAMPLE"), ("n_trades", "LOW_SAMPLE"), ("power", "NO_EDGE"),
    ("expect", "NO_EDGE"), ("t_stat", "NO_EDGE"), ("sharpe", "NO_EDGE"),
)
FIRST_TEST: dict[str, str] = {
    "COST_DEATH": "cost surface at 1x/1.5x/2x before any backtest",
    "NO_EDGE": "quick out-of-sample screen on the last third of the history",
    "SELECTION_BIAS": "deflate by the family's lifetime trial count first",
    "STATE_FRAGILE": "split by regime / half-sample stability",
    "TAIL_FAILURE": "worst-decile world drawdown before the mean",
    "CORRELATION_DUPLICATE": "residualise against the book's factor set",
    "LEAKAGE": "timestamp-shift and placebo controls",
    "LOW_SAMPLE": "count independent trades before scoring anything",
    "EXECUTION_FAILURE": "refuse artifact-hour fills and re-screen",
    "UNKNOWN": "the standard gauntlet order",
}
FEATURES: tuple[str, ...] = ("family", "symbol", "source", "asset_class", "n_params")
ALPHA = 1.0


def failure_class(gates: dict[str, Any] | None, why: str = "") -> str:
    text = " ".join(k for k, v in (gates or {}).items()
                    if isinstance(v, dict) and v.get("passed") is False) + " " + why
    low = text.lower()
    for needle, cls in GATE_CLASS:
        if needle in low:
            return cls
    return "UNKNOWN"


def _asset_class(symbol: str) -> str:
    s = symbol.upper()
    if s.startswith("XAU") or s.startswith("XAG"):
        return "metal"
    if len(s) == 6 and s.isalpha():
        return "fx"
    if any(s.startswith(x) for x in ("US", "NAS", "UK", "GER", "JP", "AUS", "HK", "CHINA")):
        return "index"
    if s.startswith("X") or (s.endswith("USD") and len(s) > 6):
        return "commodity_or_crypto_cfd"
    return "other"


def features_of(row: dict[str, Any]) -> dict[str, str]:
    sym = str(row.get("symbol") or "").upper()
    params = row.get("params") or {}
    return {"family": str(row.get("family") or ""), "symbol": sym,
            "source": str(row.get("source") or "").split(":")[0],
            "asset_class": _asset_class(sym),
            "n_params": str(min(len(params), 6)) if isinstance(params, dict) else "0"}


class GraveyardModel:
    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.feat_counts: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter))
        self.survive_counts: Counter[str] = Counter()          # "CERTIFIED" | "FAILED"
        self.survive_feat: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter))
        self.n = 0

    def fit(self, rows: Iterable[dict[str, Any]]) -> GraveyardModel:
        latest: dict[str, dict[str, Any]] = {}
        for r in rows:
            if isinstance(r, dict) and r.get("id"):
                latest[str(r["id"])] = r
        for r in latest.values():
            fate = str(r.get("fate"))
            if fate not in ("FAILED", "BURIED", "CERTIFIED"):
                continue
            f = features_of(r)
            self.n += 1
            outcome = "CERTIFIED" if fate == "CERTIFIED" else "FAILED"
            self.survive_counts[outcome] += 1
            for k, v in f.items():
                self.survive_feat[outcome][k][v] += 1
            if outcome == "FAILED":
                cls = failure_class(r.get("gates"), str(r.get("why") or ""))
                self.class_counts[cls] += 1
                for k, v in f.items():
                    self.feat_counts[cls][k][v] += 1
        return self

    def _posterior(self, f: dict[str, str], labels: Iterable[str], prior: Counter[str],
                   feat: dict[str, dict[str, Counter[str]]]) -> dict[str, float]:
        total = sum(prior.values())
        logp = {}
        for c in labels:
            n_c = prior.get(c, 0)
            lp = math.log((n_c + ALPHA) / (total + ALPHA * max(1, len(list(labels)))))
            for k, v in f.items():
                cnt = feat[c][k] if c in feat else Counter()
                lp += math.log((cnt.get(v, 0) + ALPHA) / (n_c + ALPHA * (len(cnt) + 1)))
            logp[c] = lp
        m = max(logp.values())
        z = sum(math.exp(v - m) for v in logp.values())
        return {c: math.exp(v - m) / z for c, v in logp.items()}

    def premortem(self, row: dict[str, Any]) -> dict[str, Any]:
        f = features_of(row)
        if self.n == 0:
            return {"p_survivor": None, "failure_class": "UNKNOWN", "why": "no judged history"}
        surv = self._posterior(f, ("CERTIFIED", "FAILED"), self.survive_counts,
                               self.survive_feat)
        classes = [c for c in CLASSES if self.class_counts.get(c, 0) > 0] or ["UNKNOWN"]
        cls = self._posterior(f, classes, self.class_counts, self.feat_counts)
        top = max(cls, key=lambda c: cls[c])
        return {"p_survivor": round(surv.get("CERTIFIED", 0.0), 4),
                "failure_class": top, "p_class": round(cls[top], 3),
                "first_test": FIRST_TEST.get(top, FIRST_TEST["UNKNOWN"]),
                "classes": {c: round(p, 3) for c, p in sorted(cls.items(),
                                                              key=lambda kv: -kv[1])[:4]},
                "n_judged": self.n}

    def summary(self) -> dict[str, Any]:
        return {"n_judged": self.n, "survivors": self.survive_counts.get("CERTIFIED", 0),
                "failure_classes": dict(self.class_counts.most_common())}
