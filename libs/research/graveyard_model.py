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

import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
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
#: THE DECLARED FAILURE-STAGE TAXONOMY (C24). A failure CLASS says what killed the cell; a
#: STAGE says HOW FAR IT GOT BEFORE DYING, and those are different questions with different
#: consequences. Ten thousand cells dying at `statistics` means the miners are producing noise;
#: ten thousand dying at `execution` means the miners are finding real structure this venue
#: cannot be made to trade. The class alone cannot tell those apart, and the desk was spending
#: its compute as if it could. Ordered EARLIEST-FIRST, which is also cheapest-first: a stage
#: index is how much of the pipeline the cell consumed before it was refused.
STAGES: tuple[str, ...] = ("idea", "data", "pit", "statistics", "cost", "capacity",
                           "execution", "forward", "decay")
#: class -> the stage a cell of that class died at. One mapping, declared, so a rejection's stage
#: is never re-derived differently by two readers.
CLASS_STAGE: dict[str, str] = {
    "NO_EDGE": "statistics", "SELECTION_BIAS": "statistics", "LOW_SAMPLE": "statistics",
    "STATE_FRAGILE": "forward", "TAIL_FAILURE": "forward",
    "COST_DEATH": "cost", "EXECUTION_FAILURE": "execution",
    "CORRELATION_DUPLICATE": "capacity", "LEAKAGE": "pit",
    # UNKNOWN IS NOT A STAGE AND MUST NOT BE GIVEN ONE. A cell judged FAILED with no gate detail
    # did not die at `idea`; the desk simply did not record where it died. Forcing it into the
    # first stage would make the histogram read "our research dies of bad ideas" when what it
    # actually says is "our rejections do not carry their stage" -- the opposite instruction to
    # whoever spends the next compute hour. It maps to "", counted as `unattributed`.
    "UNKNOWN": "",
}
#: Stage names a gate or a refusal reason states OUTRIGHT, checked before the class mapping: a
#: cell refused for a missing panel never reached statistics, whatever gate name it carries.
STAGE_NEEDLE: tuple[tuple[str, str], ...] = (
    ("no bars", "data"), ("no data", "data"), ("unreadable", "data"), ("missing panel", "data"),
    ("point-in-time", "pit"), ("available_at", "pit"), ("vintage", "pit"),
    ("min_lot", "capacity"), ("capacity", "capacity"), ("lot floor", "capacity"),
    ("decay", "decay"), ("half-life", "decay"),
    ("forward", "forward"), ("shadow", "forward"),
    ("unrunnable", "idea"), ("uncompilable", "idea"), ("not executable", "idea"),
)
#: The features P(survival | hypothesis) is conditioned on. The first five are the original
#: five; the last four are the AXIS_REGISTRY vocabulary (C24), which is where the desk keeps the
#: dimensions a hypothesis is actually ABOUT rather than the dimensions of the file it arrived in.
FEATURES: tuple[str, ...] = ("family", "symbol", "source", "asset_class", "n_params",
                             "mechanism", "information_source", "session", "chart")
ALPHA = 1.0


def failure_class(gates: dict[str, Any] | None, why: str = "") -> str:
    text = " ".join(k for k, v in (gates or {}).items()
                    if isinstance(v, dict) and v.get("passed") is False) + " " + why
    low = text.lower()
    for needle, cls in GATE_CLASS:
        if needle in low:
            return cls
    return "UNKNOWN"


def failure_stage(gates: dict[str, Any] | None, why: str = "", klass: str = "") -> str:
    """How far the cell got before it was refused: one of `STAGES`. C24.

    The reason text wins over the class mapping, because a cell refused for a missing panel
    carries whatever gate name happened to be running when the panel was found missing, and
    calling that a statistical death would teach the model the exact opposite of the truth.
    """
    text = (" ".join(k for k, v in (gates or {}).items()
                     if isinstance(v, dict) and v.get("passed") is False) + " " + why).lower()
    for needle, stage in STAGE_NEEDLE:
        if needle in text:
            return stage
    return CLASS_STAGE.get(klass or failure_class(gates, why), "")


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


def _axis(row: dict[str, Any], *names: str) -> str:
    """One AXIS_REGISTRY coordinate off a graph row, wherever the writer put it. C24.

    Rows reach the graph from a dozen organs and the axis fields live at the top level on some
    and inside `axes`/`meta` on others. An absent coordinate returns "" -- which the naive Bayes
    treats as its own level -- rather than a guess, because "this row did not say which mechanism
    it is" is itself predictive of how the row was written and how it died.
    """
    for holder in (row, row.get("axes"), row.get("meta"), row.get("params")):
        if not isinstance(holder, dict):
            continue
        for n in names:
            v = holder.get(n)
            if isinstance(v, str) and v.strip():
                return v.strip()[:40]
    return ""


def features_of(row: dict[str, Any]) -> dict[str, str]:
    sym = str(row.get("symbol") or "").upper()
    params = row.get("params") or {}
    return {"family": str(row.get("family") or ""), "symbol": sym,
            "source": str(row.get("source") or "").split(":")[0],
            "asset_class": _asset_class(sym),
            "n_params": str(min(len(params), 6)) if isinstance(params, dict) else "0",
            # THE AXES THE HYPOTHESIS IS ABOUT (C24), not the axes of the file it arrived in.
            "mechanism": _axis(row, "mechanism", "mechanism_class", "actor"),
            "information_source": _axis(row, "information_source", "info_source", "data_source"),
            "session": _axis(row, "session", "window", "hour_bucket"),
            "chart": _axis(row, "chart", "timeframe", "tf")}


class GraveyardModel:
    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.feat_counts: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter))
        self.survive_counts: Counter[str] = Counter()          # "CERTIFIED" | "FAILED"
        self.survive_feat: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter))
        #: C24: the declared STAGE every rejection died at, counted beside the class.
        self.stage_counts: Counter[str] = Counter()
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
                self.stage_counts[failure_stage(r.get("gates"), str(r.get("why") or ""), cls)] += 1
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
                # C24: the stage the model expects this cell to die at, which is what decides
                # WHICH TEST IS WORTH RUNNING FIRST -- a cell expected to die at `data` should
                # never reach a statistical gate at all.
                "failure_stage": CLASS_STAGE.get(top, ""),
                "first_test": FIRST_TEST.get(top, FIRST_TEST["UNKNOWN"]),
                "classes": {c: round(p, 3) for c, p in sorted(cls.items(),
                                                              key=lambda kv: -kv[1])[:4]},
                "n_judged": self.n}

    def summary(self) -> dict[str, Any]:
        return {"n_judged": self.n, "survivors": self.survive_counts.get("CERTIFIED", 0),
                "failure_classes": dict(self.class_counts.most_common()),
                # C24: the same deaths counted by STAGE, in pipeline order, so the reading is
                # "where does this desk's research die" and not only "which gate said no".
                "failure_stages": {s: self.stage_counts.get(s, 0) for s in STAGES},
                # The rejections that carry no evidence of WHERE they died. A large number here
                # is a defect in what the gates record, not a fact about the research.
                "failure_stage_unattributed": self.stage_counts.get("", 0),
                "stage_taxonomy": list(STAGES)}

    def survival_by(self, feature: str) -> dict[str, dict[str, Any]]:
        """P(survival) per level of one declared feature, with its counts. C24.

        The raw material for the compute factor: `source` levels are the arms the budget can
        actually move seconds between. Laplace-smoothed, so a level with one certified row out of
        one does not read as certainty.
        """
        out: dict[str, dict[str, Any]] = {}
        cert = self.survive_feat.get("CERTIFIED", {}).get(feature, Counter())
        fail = self.survive_feat.get("FAILED", {}).get(feature, Counter())
        for level in sorted(set(cert) | set(fail)):
            c, f = cert.get(level, 0), fail.get(level, 0)
            out[level] = {"certified": c, "failed": f,
                          "p_survival": round((c + ALPHA) / (c + f + 2 * ALPHA), 6)}
        return out


# --------------------------------------------------------------------------------- the clock
#: Where the hourly leg's reading lands. Repo-relative so both boxes write the same path.
REPORT = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "reports" / "GRAVEYARD_MODEL.json"


def build(rows: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Fit the model on the hypothesis graph and return the report. C24.

    THE LEG HAD NO ARTIFACT. `hourly_cycle:graveyard_model` has run this module as a script since
    it was wired, and the module was a library with no `main` -- so the leg exited 0 every hour
    and left nothing behind, which is exactly the shape of III.16 ("done means RUNS on a schedule
    and leaves an artifact"). The consumers (`deepening_worker`, `miner_candidate_compiler`,
    `falsifier_run`, `revival_engine`) each re-fit the model in-process, so the fit was never the
    problem; the MEASUREMENT of it was invisible, and nothing could be read, budgeted or argued
    with by anything outside those four call sites.
    """
    if rows is None:
        try:
            from libs.research.hypothesis_graph import Graph
            rows = Graph().rows()
        except Exception as exc:                                        # pragma: no cover
            return {"status": "UNMEASURED",
                    "why": f"hypothesis graph unreadable: {type(exc).__name__}: {exc}"}
    model = GraveyardModel().fit(rows)
    if model.n == 0:
        return {"status": "UNMEASURED", "why": "no judged row in the hypothesis graph",
                "stage_taxonomy": list(STAGES)}
    return {
        "status": "MEASURED",
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        **model.summary(),
        # P(survival) per level of each declared feature. `source` is the one the compute budget
        # can act on, because a source IS an arm; the rest are published for the reader.
        "survival_by": {f: model.survival_by(f) for f in FEATURES},
        "consumer": ("research_budget._graveyard_factor (per-arm compute factor with an "
                     "exploration floor), deepening_worker.voi_order, miner_candidate_compiler, "
                     "falsifier_run, revival_engine"),
        "authority": ("ZERO over capital. It orders RESEARCH compute only, and it may never take "
                      "an arm below par -- the exploration floor is the arm that has not yet "
                      "produced, and starving it is how a desk stops finding anything new"),
    }


def main(argv: list[str] | None = None) -> int:                         # pragma: no cover - clock
    import argparse
    ap = argparse.ArgumentParser(description="fit the graveyard model and publish it")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=0.0, help="advisory; the fit is a count")
    ap.add_argument("--out", type=Path, default=REPORT)
    args = ap.parse_args(argv)
    doc = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"graveyard model: {doc.get('status')} n_judged={doc.get('n_judged')} "
          f"stages={doc.get('failure_stages')}")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
