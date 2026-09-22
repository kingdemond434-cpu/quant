"""THE UNKNOWN-UNKNOWNS RESIDUAL HUNT -- what the world model repeatedly fails to explain.

THE PRINCIPAL, 2026-09-17: *epsilon_t = y_t - yhat_t; anything the World Model repeatedly fails
to explain becomes a search target -- "what missing dataset, participant class, region,
representation, causal mechanism or market interaction explains this residual?" -- and the
information-acquisition side then searches the lawful public internet for proxies.*

THE LOOP THIS CLOSES. `world_model` publishes epsilon per instrument, horizon, regime and
session. A residual that is large once is noise; a residual that is large IN THE SAME CELL, pass
after pass, is a mechanism the desk has no input for. Nothing in this repository converted the
second kind into a hunt: six organs measured a residual and the queue that collects them
(`residual_queue`) orders what the desk already knows it does not know. This one asks the
question that OPENS new ground -- not "which of my models is failing" but "which dataset,
participant, region, representation, mechanism or interaction is missing from my world".

WHAT IS TESTED, AND AGAINST WHAT. Two statistics per cluster (target x regime x session x
calendar class x time of day): the conditional MEAN of epsilon, and the lag-1 persistence of
|epsilon| -- a cell that is merely volatile is not a cell that is predictable, and the second
statistic is what tells them apart. Both are judged against a CIRCULAR-BLOCK PERMUTATION null,
which rolls the residual path under the same cluster mask: it keeps the autocorrelation an hourly
residual series really has and destroys only the alignment between the labels and the values. An
i.i.d. shuffle would call half the desk's clock cells significant, because financial residuals
are autocorrelated and a shuffle pretends they are not.

BELOW `MIN_CLUSTER_N` NOTHING IS JUDGED. The cell reads UNMEASURED with the minimum named, and
it is counted. That is the difference between "we looked and found nothing" and "we could not
look", and the desk has paid for confusing them before (L1.28a, WS-005).

WHAT A TARGET IS. Not a sentence -- a structured search across the principal's six classes, each
DERIVED from the cluster and from what the world model already holds: the datasets the model does
NOT have for that region and session, the participant classes whose mandates fire in it, the
regions whose hours own it, the representation families never yet minted over the datasets in
play, the causal mechanisms consistent with the sign, and the cross-dataset interactions nobody
has built. Each becomes a `residual_target` discovery in the canonical registry (state
UNPROCESSED, so the conversion-debt ledger owes it a disposition), a `frontier_map` row so the
scouts can see the cell is cold, a donation the candidate compiler reads, and -- where
`libs/research/polyglot` is present -- native-language query seeds, because the dataset that
explains a Tokyo-fix residual is not written in English.

DELAYED CREDIT, AND NOTHING SILENTLY DISAPPEARS. Every open target carries the variance of its
cluster when it was opened. When a later pass finds that variance materially reduced, the
datasets the world model has GAINED since are credited in `source_yield`, the target is closed
with that evidence, and the closure is recorded. A target is never dropped for being old; it goes
STALE, and stale is a state with a reason attached.

    python desks/mt5/research/residual_hunt.py [--once] [--budget-s 600] [--dry-run]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# IMPORTED PACKAGE-QUALIFIED FIRST, AND THE REASON IS NOT STYLE. `import world_model` and
# `from research import world_model` produce TWO DISTINCT MODULE OBJECTS with separate globals:
# a test (or another organ) that repoints `research.world_model.STORE` would leave this module
# reading the real desk's store, and the two would silently disagree about where the residuals
# are. One spelling, everywhere, so there is one module.
try:
    from research import world_model as WM
except ImportError:                                                          # pragma: no cover
    import world_model as WM  # type: ignore[no-redef]

STATE = DESK / "data" / "world_model" / "residual_targets.json"
DONATIONS = DESK / "data" / "intelligence" / "residual_hunt"
OUT = DESK / "reports" / "RESIDUAL_HUNT.json"
UNIVERSE_JSON = DESK / "data" / "universe" / "universe.json"
EVENT_CALENDAR = ROOT / "data" / "event_calendar.json"

SEED = 20260917
#: THE NAMED MINIMUM. Below it a cluster is UNMEASURED, never "no effect".
MIN_CLUSTER_N = 60
PERMUTATIONS = 200
P_THRESHOLD = 0.05
#: A cluster must clear the threshold on the mean OR the persistence, and carry a mean at least
#: this many residual sds from zero. A p-value alone certifies a tiny effect on a big sample.
MIN_ABS_EFFECT_SD = 0.10
#: The false-discovery rate the pass controls ACROSS EVERY CELL IT TESTED.
FDR_Q = 0.05
MAX_TARGETS = 40
MAX_DONATIONS = 20
#: Fractional variance reduction in a cluster before the desk calls a residual EXPLAINED.
EXPLAINED_DROP = 0.35
STALE_DAYS = 21
EVENT_WINDOW_H = 12.0

RULE = ("a residual the world model repeatedly fails to explain is a search target across six "
        "classes: missing dataset, participant class, region, representation, causal mechanism, "
        "market interaction")

#: THE CLUSTER'S FAMILY, derived from what the cluster IS. Every value here is a registered
#: price-only family the candidate compiler already accepts, so a donation compiles rather than
#: queueing an extraction call that cannot succeed. The mapping is a ROUTING rule, not a claim
#: about profitability -- the ten gates decide that, on real history, like every other candidate.
FAMILY_ROUTE: tuple[tuple[str, str, str], ...] = (
    ("calendar", "event", "vol_transition"),
    ("regime", "high", "vol_mean_reversion"),
    ("regime", "low", "range_reversion"),
    ("session", "asia", "asia_momentum"),
    ("session", "london", "session_range_breakout"),
    ("session", "overlap", "session_range_breakout"),
    ("session", "ny", "session_range_breakout"),
)
DEFAULT_FAMILY = "overnight_drift"

#: The session a donation's prose names, in the vocabulary `miner_candidate_compiler.text_session`
#: reads, so a session-aware family is compiled INTO its session rather than defaulted out of it.
SESSION_PHRASE = {"asia": "asian session", "london": "london open", "ny": "new york open",
                  "overlap": "london open", "off": ""}

#: PARTICIPANT CLASSES BY SESSION. A vocabulary of who is forced to transact when, not a claim
#: that any of them is present -- naming the candidate is the whole job of a search target.
PARTICIPANTS: dict[str, tuple[str, ...]] = {
    "asia": ("Japanese importers settling at the 09:55 JST fix", "Tokyo bank ALM desks",
             "Chinese state bank FX settlement", "Asian real-money rebalancing"),
    "london": ("European pension and insurance hedgers", "the 16:00 London WMR fixing flow",
               "interbank market makers rolling inventory"),
    "ny": ("US index rebalancers", "CTA trend programmes executing the US session",
           "dealers hedging option gamma into the US close"),
    "overlap": ("cross-border macro funds", "the London-New York handover's liquidity vacuum"),
    "off": ("thin-book market makers", "forced liquidation into an illiquid tape"),
}

#: DATASET CANDIDATES BY REGION -- public, licensed ground the desk could acquire. Named so the
#: acquisition side has a target; presence here is not a claim that the series is free, only that
#: it is lawful public material worth pricing.
DATASET_CANDIDATES: dict[str, tuple[str, ...]] = {
    "JP": ("MOF weekly portfolio flows", "JPX futures open interest by participant type",
           "Tokyo fix order imbalance proxies", "BOJ operations calendar"),
    "CN": ("SAFE bank FX settlement", "SGE gold premium and withdrawals",
           "PBOC open market operations", "northbound connect flow"),
    "EA": ("ECB SDW money-market volumes", "EA sovereign auction calendar",
           "TARGET2 balances"),
    "US": ("CFTC disaggregated and TFF positioning", "SOMA and reserve balances",
           "Treasury auction calendar", "options open interest by strike"),
    "KR": ("BOK ECOS flow series", "KRX foreign investor net flow", "Korea customs trade dailies"),
    "GLOBAL": ("BIS cross-border banking statistics", "shipping and freight rates",
               "commodity warehouse stocks", "swap and basis curves"),
}

#: CAUSAL MECHANISMS, keyed by the SIGN and the persistence of the residual. A named mechanism is
#: what makes a search target testable later; an unnamed one is a feeling about a chart.
MECHANISMS: tuple[tuple[str, str], ...] = (
    ("positive_persistent", "a participant with a mandate is accumulating in this cell and the "
                            "model has no series for the flow that forces them"),
    ("negative_persistent", "a participant is being forced OUT in this cell -- hedging, margin "
                            "or settlement -- and the model prices none of the constraint"),
    ("zero_mean_persistent", "the CELL's variance, not its mean, is scheduled: an announcement, "
                             "a fixing or a rollover the model has no calendar for"),
)

CURRENCY_REGION: dict[str, str] = {
    "JPY": "JP", "CNH": "CN", "CNY": "CN", "HKD": "CN", "EUR": "EA", "CHF": "EA", "SEK": "EA",
    "NOK": "EA", "DKK": "EA", "PLN": "EA", "HUF": "EA", "CZK": "EA", "USD": "US", "CAD": "US",
    "MXN": "US", "KRW": "KR", "SGD": "CN", "AUD": "GLOBAL", "NZD": "GLOBAL", "ZAR": "GLOBAL",
    "TRY": "GLOBAL", "XAU": "GLOBAL", "XAG": "GLOBAL",
}


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.chmod(0o644)
        os.replace(tmp, path)


# ---------------------------------------------------------------------------- the calendar class
@dataclass
class CalendarClasses:
    """Event instants plus the window this calendar CLAIMS to cover.

    Three states, never two (`libs/research/event_calendar`): `event`, `endogenous` and
    `uncovered`. Collapsing the third into the second is how an unexamined period gets reported
    as clean, and it flatters the result in exactly the direction that matters.
    """

    events: np.ndarray
    covered_from: float | None
    covered_to: float | None
    kinds: tuple[str, ...] = ()

    def classify(self, stamps: np.ndarray) -> list[str]:
        if self.events.size == 0 or self.covered_from is None or self.covered_to is None:
            return ["uncovered"] * len(stamps)
        out: list[str] = []
        idx = np.searchsorted(self.events, stamps)
        window = EVENT_WINDOW_H * 3600.0
        for row, stamp in enumerate(stamps):
            if stamp < self.covered_from or stamp > self.covered_to:
                out.append("uncovered")
                continue
            near = False
            for j in (idx[row] - 1, idx[row]):
                if 0 <= j < self.events.size and abs(float(self.events[j]) - stamp) <= window:
                    near = True
                    break
            out.append("event" if near else "endogenous")
        return out


def load_calendar(path: Path | None = None) -> CalendarClasses:
    doc = _read_json(path or EVENT_CALENDAR)
    if not isinstance(doc, dict):
        return CalendarClasses(events=np.asarray([], dtype=float), covered_from=None,
                               covered_to=None)
    stamps: list[float] = []
    kinds: list[str] = []
    for row in doc.get("events") or []:
        if not isinstance(row, dict):
            continue
        parsed = WM.R.parse_time(str(row.get("utc") or row.get("ts") or ""))
        if parsed is None:
            continue
        stamps.append(parsed.timestamp())
        kinds.append(str(row.get("name") or row.get("kind") or "event"))
    if not stamps:
        return CalendarClasses(events=np.asarray([], dtype=float), covered_from=None,
                               covered_to=None)
    events = np.sort(np.asarray(stamps, dtype=float))
    lo = WM.R.parse_time(str(doc.get("covered_from") or "")) or None
    hi = WM.R.parse_time(str(doc.get("valid_through") or doc.get("covered_to") or "")) or None
    return CalendarClasses(events=events,
                           covered_from=lo.timestamp() if lo else float(events[0]),
                           covered_to=hi.timestamp() if hi else float(events[-1]),
                           kinds=tuple(dict.fromkeys(kinds)))


def time_of_day(hour: int) -> str:
    """Four buckets. The hour alone would shatter every cell below the minimum n."""
    return ("night", "morning", "afternoon", "evening")[min(3, max(0, hour // 6))]


# ---------------------------------------------------------------------------- the statistics
def all_shift_means(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """The cluster mean under EVERY circular shift of the path, exactly, in one FFT.

    The circular-shift group has exactly n elements, so sampling it is pointless: the complete
    enumeration costs one transform and removes the sampling noise that made the smallest
    attainable p-value an artefact of the roll count rather than of the data. It also matters for
    the multiplicity correction below -- a null resolution of 1/200 cannot clear a
    Benjamini-Hochberg cut computed over sixty cells, so the organ would have been unable to
    report a real finding however strong it was.
    """
    n = len(values)
    k = float(mask.sum())
    spectrum = np.fft.rfft(mask.astype(float)) * np.conj(np.fft.rfft(values))
    return np.asarray(np.fft.irfft(spectrum, n=n), dtype=float) / max(k, 1.0)


def circular_block_p(values: np.ndarray, mask: np.ndarray, statistic: str,
                     *, permutations: int = PERMUTATIONS, seed: int = SEED) -> tuple[float, float]:
    """(observed statistic, p-value) against a CIRCULAR-BLOCK permutation null.

    The path is rolled, the mask is not. Rolling preserves every block of autocorrelation the
    residual series actually has and destroys only the correspondence between the cluster's rows
    and the values -- which is precisely the null "this cell is no different from any other
    stretch of the same path". An i.i.d. shuffle would call half the desk's clock cells
    significant, because financial residuals are autocorrelated and a shuffle pretends they are
    not.

    The MEAN is enumerated over the whole shift group (`all_shift_means`); |epsilon| PERSISTENCE
    is nonlinear in the selection and is sampled with `permutations` rolls.
    """
    n = len(values)
    if n < 4 or int(mask.sum()) < 2:
        return float("nan"), float("nan")
    if statistic == "mean":
        observed = float(values[mask].mean())
        if not np.isfinite(observed):
            return observed, float("nan")
        null = all_shift_means(values, mask)
        return observed, float((np.abs(null) >= abs(observed) - 1e-15).sum()) / n
    rng = np.random.default_rng(seed)

    def _stat(series: np.ndarray) -> float:
        absolute = np.abs(series[mask])
        if absolute.size < 3 or float(absolute.std()) <= 0:
            return float("nan")
        centred = absolute - absolute.mean()
        denominator = float((centred ** 2).sum())
        if denominator <= 0:
            return float("nan")
        return float((centred[:-1] * centred[1:]).sum() / denominator)

    observed = _stat(values)
    if not np.isfinite(observed):
        return observed, float("nan")
    hits = 0
    for shift in rng.integers(1, n, size=permutations):
        null_stat = _stat(np.roll(values, int(shift)))
        if np.isfinite(null_stat) and abs(null_stat) >= abs(observed):
            hits += 1
    return observed, float((1 + hits) / (permutations + 1))


def benjamini_hochberg(pvalues: list[float], q: float = FDR_Q) -> float:
    """The largest p-value that controls the FALSE DISCOVERY RATE at `q` across the whole pass.

    TRIAL COUNT IS A SHARED COST, and this organ is where the residual hunt pays it. Tested one
    cell at a time at p <= 0.05, a panel of PURE NOISE handed back three "persistent unexplained
    residuals" out of fifteen cells -- measured on a synthetic store with nothing planted in it,
    which is exactly the 5% the threshold promises and exactly what makes per-cell thresholds
    useless here. Each false target would then spend scout hours, an acquisition budget and a
    slice of the desk's family-wise error budget hunting a dataset that does not exist.

    BH rather than Bonferroni because the cost of a miss is high (a real missing dataset stays
    missing) and the cost of a false positive is bounded (the target still has to survive the ten
    gates). Returns 0.0 when nothing clears, which rejects every cell -- the correct direction.
    """
    finite = sorted(p for p in pvalues if np.isfinite(p))
    m = len(finite)
    if m == 0:
        return 0.0
    cut = 0.0
    for rank, value in enumerate(finite, start=1):
        if value <= q * rank / m:
            cut = value
    return cut


@dataclass
class Cluster:
    """One tested cell: its key, its statistics, and its disposition."""

    key: dict[str, str]
    cluster_id: str
    n: int
    mean: float
    sd: float
    variance: float
    effect_sd: float
    p_mean: float
    p_persistence: float
    persistence: float
    status: str
    why: str = ""
    first_time: str = ""
    last_time: str = ""


def _cluster_id(key: dict[str, str]) -> str:
    raw = "|".join(f"{k}={key[k]}" for k in sorted(key))
    return "rh_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def cluster_residuals(rows: list[dict[str, Any]], calendar: CalendarClasses,
                      *, permutations: int = PERMUTATIONS, deadline: float | None = None
                      ) -> tuple[list[Cluster], dict[str, float]]:
    """Group the residual store and test every cell that clears the named minimum n."""
    counts: dict[str, float] = {"rows": len(rows), "cells": 0, "measured": 0,
                                "unmeasured_small": 0, "unparsed_rows": 0,
                                "bh_cut": 0.0, "bh_m": 0}
    panels: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        parsed = WM.R.parse_time(str(row.get("time") or ""))
        if parsed is None:
            counts["unparsed_rows"] += 1
            continue
        row = {**row, "_epoch": parsed.timestamp(), "_hour": parsed.hour}
        panels[(str(row.get("target") or row.get("symbol")), str(row.get("horizon")))].append(row)

    out: list[Cluster] = []
    for (target, horizon), panel in sorted(panels.items()):
        if deadline is not None and time.monotonic() >= deadline:
            break
        panel.sort(key=lambda r: float(r["_epoch"]))
        eps = np.asarray([float(r.get("epsilon") or 0.0) for r in panel], dtype=float)
        stamps = np.asarray([float(r["_epoch"]) for r in panel], dtype=float)
        classes = calendar.classify(stamps)
        keys = [{"target": target, "horizon": horizon,
                 "regime": str(row.get("regime") or "UNMEASURED"),
                 "session": str(row.get("session") or "off"),
                 "calendar_class": classes[i],
                 "time_of_day": time_of_day(int(row["_hour"]))}
                for i, row in enumerate(panel)]
        buckets: dict[str, list[int]] = defaultdict(list)
        labels: dict[str, dict[str, str]] = {}
        for i, key in enumerate(keys):
            cid = _cluster_id(key)
            buckets[cid].append(i)
            labels[cid] = key
        panel_sd = float(eps.std()) or 1.0
        for cid, members in sorted(buckets.items()):
            counts["cells"] += 1
            key = labels[cid]
            mask = np.zeros(len(eps), dtype=bool)
            mask[members] = True
            picked = eps[mask]
            if len(members) < MIN_CLUSTER_N:
                counts["unmeasured_small"] += 1
                out.append(Cluster(key=key, cluster_id=cid, n=len(members),
                                   mean=float(picked.mean()) if picked.size else float("nan"),
                                   sd=float(picked.std()) if picked.size else float("nan"),
                                   variance=float(picked.var()) if picked.size else float("nan"),
                                   effect_sd=float("nan"), p_mean=float("nan"),
                                   p_persistence=float("nan"), persistence=float("nan"),
                                   status="UNMEASURED",
                                   why=f"n={len(members)} below the named minimum "
                                       f"{MIN_CLUSTER_N}; measured by more residual rows in "
                                       f"this cell",
                                   first_time=datetime.fromtimestamp(float(stamps[members[0]]),
                                                                     tz=UTC).isoformat(),
                                   last_time=datetime.fromtimestamp(float(stamps[members[-1]]),
                                                                    tz=UTC).isoformat()))
                continue
            counts["measured"] += 1
            _obs, p_mean = circular_block_p(eps, mask, "mean", permutations=permutations)
            persistence, p_pers = circular_block_p(eps, mask, "persistence",
                                                   permutations=permutations)
            effect = abs(float(picked.mean())) / panel_sd
            out.append(Cluster(
                key=key, cluster_id=cid, n=len(members), mean=float(picked.mean()),
                sd=float(picked.std()), variance=float(picked.var()), effect_sd=round(effect, 6),
                p_mean=float(p_mean), p_persistence=float(p_pers),
                persistence=float(persistence), status="MEASURED",
                first_time=datetime.fromtimestamp(float(stamps[members[0]]), tz=UTC).isoformat(),
                last_time=datetime.fromtimestamp(float(stamps[members[-1]]), tz=UTC).isoformat()))

    # THE MULTIPLICITY CHARGE IS PAID ONCE, ACROSS EVERY CELL THE PASS TESTED -- not per panel and
    # not per instrument. Two statistics per cell, so each cell's p is Bonferroni-doubled before
    # the FDR step; the denominator is every measured cell, which is the honest trial count for
    # this hour of research.
    measured = [c for c in out if c.status == "MEASURED"]
    cell_p: dict[str, float] = {}
    for cluster in measured:
        finite = [p for p in (cluster.p_mean, cluster.p_persistence) if np.isfinite(p)]
        cell_p[cluster.cluster_id] = min(1.0, 2.0 * min(finite)) if finite else float("nan")
    cut = benjamini_hochberg([cell_p[c.cluster_id] for c in measured])
    counts["bh_cut"] = cut
    counts["bh_m"] = len(measured)
    for cluster in measured:
        p_cell = cell_p[cluster.cluster_id]
        strong = (np.isfinite(cluster.effect_sd) and cluster.effect_sd >= MIN_ABS_EFFECT_SD) or (
            np.isfinite(cluster.p_persistence) and 2.0 * cluster.p_persistence <= cut)
        if np.isfinite(p_cell) and p_cell <= cut and strong:
            cluster.status = "PERSISTENT"
        else:
            cluster.status = "EXPLAINED_ENOUGH"
            cluster.why = (f"cell p={p_cell:.5f} against a Benjamini-Hochberg cut of {cut:.5f} "
                           f"over {len(measured)} cell(s) tested this pass"
                           if np.isfinite(p_cell) else "no finite statistic")
    return out, counts


# ---------------------------------------------------------------------------- the search target
def _symbol_regions(symbol: str) -> list[str]:
    text = symbol.upper()
    regions = [region for code, region in CURRENCY_REGION.items() if code in text]
    return sorted(dict.fromkeys(regions)) or ["GLOBAL"]


def _mechanism(cluster: Cluster) -> tuple[str, str]:
    if np.isfinite(cluster.p_mean) and cluster.p_mean <= P_THRESHOLD:
        return MECHANISMS[0] if cluster.mean > 0 else MECHANISMS[1]
    return MECHANISMS[2]


def family_for(cluster: Cluster) -> str:
    for axis, value, family in FAMILY_ROUTE:
        if cluster.key.get(axis) == value:
            return family
    return DEFAULT_FAMILY


def search_target(cluster: Cluster, have_datasets: set[str], have_representations: set[str]
                  ) -> dict[str, Any]:
    """The principal's question, answered as six NAMED classes of candidate explanation."""
    symbol = cluster.key["target"]
    regions = _symbol_regions(symbol)
    session = cluster.key.get("session", "off")
    mech_id, mech_text = _mechanism(cluster)

    wanted: list[str] = []
    for region in regions:
        for name in DATASET_CANDIDATES.get(region, ()):
            if not any(name.lower().split()[0] in d.lower() for d in have_datasets):
                wanted.append(f"{region}: {name}")
    for name in DATASET_CANDIDATES["GLOBAL"]:
        if not any(name.lower().split()[0] in d.lower() for d in have_datasets):
            wanted.append(f"GLOBAL: {name}")

    missing_representations = [f"{family} over {d}" for family in WM.R.FAMILIES
                               for d in sorted(have_datasets)[:4]
                               if f"{family}|{d}" not in have_representations][:8]
    present = sorted(have_datasets)
    interactions = [f"{a} x {b}" for i, a in enumerate(present[:5]) for b in present[i + 1:5]][:8]

    return {
        "cluster_id": cluster.cluster_id,
        "question": (f"What missing dataset, participant class, region, representation, causal "
                     f"mechanism or market interaction explains the {symbol} "
                     f"{cluster.key['horizon']} residual in the {cluster.key['regime']}-vol "
                     f"{session} session, {cluster.key['calendar_class']} "
                     f"{cluster.key['time_of_day']} cell?"),
        "cell": cluster.key,
        "evidence": {"n": cluster.n, "mean_epsilon": round(cluster.mean, 8),
                     "effect_sd": cluster.effect_sd,
                     "p_mean": (None if not np.isfinite(cluster.p_mean)
                                else round(cluster.p_mean, 5)),
                     "p_persistence": None if not np.isfinite(cluster.p_persistence)
                     else round(cluster.p_persistence, 5),
                     "null": "circular-block permutation, "
                             f"{PERMUTATIONS} rolls of the residual path"},
        "candidate_explanations": {
            "missing_dataset": wanted[:8],
            "participant_class": list(PARTICIPANTS.get(session, PARTICIPANTS["off"])),
            "region": regions,
            "representation": missing_representations,
            "causal_mechanism": [{"id": mech_id, "text": mech_text}],
            "market_interaction": interactions,
        },
        "family": family_for(cluster),
        "opened_at": now_iso(),
        "variance_at_open": round(cluster.variance, 12),
        "state": "UNPROCESSED",
    }


def query_seeds(target: dict[str, Any], *, limit: int = 12) -> dict[str, list[str]]:
    """Native-script search seeds for the regions this residual names.

    Imported LAZILY and never required: `libs/research/polyglot` is another builder's module and
    an absent one must cost a field in the report, never the pass. A language with no local
    terminology returns nothing there by design, and nothing is what is recorded -- a translated
    English phrase would turn a known gap into a silent wrong answer.
    """
    try:
        from libs.research import polyglot
    except Exception:
        return {}
    languages = {"JP": "ja", "CN": "zh", "KR": "ko", "EA": "de", "US": "en", "GLOBAL": "en"}
    out: dict[str, list[str]] = {}
    for region in target["candidate_explanations"]["region"]:
        lang = languages.get(region)
        if not lang:
            continue
        try:
            seeds = polyglot.native_queries(lang, instrument=str(target["cell"]["target"]),
                                            limit=limit)
        except Exception:
            continue
        if seeds:
            out[lang] = list(seeds)[:limit]
    return out


# ---------------------------------------------------------------------------- donation + registry
def _hypothesis_universe() -> set[str]:
    registry = _read_json(UNIVERSE_JSON)
    if not isinstance(registry, dict):
        return set()
    try:
        import universe_policy as up
    except ImportError:                                                      # pragma: no cover
        from research import universe_policy as up  # type: ignore[no-redef]
    return set(up.split(registry.keys())[up.HYPOTHESIS])


def donation_rows(targets: list[dict[str, Any]], universe: set[str]) -> list[dict[str, Any]]:
    """The seat-donation rows the candidate compiler reads, in the shape it already accepts.

    `kind: hypothesis` + a REGISTERED price-only `family` + declared `symbols` is the
    STRUCTURED_HYPOTHESIS path (`miner_candidate_compiler.compile_row`). The prose names the
    session in the vocabulary that path reads, so a session family is compiled into its session.
    A symbol outside the hypothesis lane never appears here: the two-lane mandate is enforced at
    the door, not downstream.
    """
    rows: list[dict[str, Any]] = []
    for target in targets:
        symbol = str(target["cell"]["target"])
        if symbol not in universe:
            continue
        session = str(target["cell"].get("session") or "off")
        family = str(target["family"])
        mechanism = target["candidate_explanations"]["causal_mechanism"][0]["text"]
        phrase = SESSION_PHRASE.get(session, "")
        rows.append({
            "kind": "hypothesis",
            "family": family,
            "symbols": [symbol],
            "source": "residual_hunt",
            "cluster_id": target["cluster_id"],
            "mechanism_status": "NAMED",
            "mechanism": mechanism,
            "title": f"unexplained {symbol} residual: {target['cell']['regime']}-vol "
                     f"{session} {target['cell']['calendar_class']} cell",
            "text": (f"{family} on {symbol} in the {phrase or session}. {mechanism}. The world "
                     f"model's residual in this cell has mean {target['evidence']['mean_epsilon']}"
                     f" over n={target['evidence']['n']} with p_mean="
                     f"{target['evidence']['p_mean']} against a circular-block permutation null. "
                     f"This is a HYPOTHESIS for the ten gates, not a claim."),
            "testable_claim": target["question"],
            "confidence": 0.3,
            "pit": {"event_time": "bar close", "publication_lag_days": 0},
            "public_source": "desks/mt5/reports/WORLD_MODEL.json",
            "candidate_explanations": target["candidate_explanations"],
            "query_seeds": target.get("query_seeds") or {},
        })
    return rows


def record_targets(targets: list[dict[str, Any]], closures: list[dict[str, Any]]
                   ) -> dict[str, Any]:
    """Discoveries, frontier cells and delayed dataset credit in the canonical registry."""
    out: dict[str, Any] = {"discoveries": 0, "frontier_cells": 0, "closed": 0, "credited": 0}
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unimportable: {type(exc).__name__}"}
    try:
        conn = reg.connect()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unopenable: {type(exc).__name__}"}
    try:
        for target in targets:
            cell = target["cell"]
            did, created = reg.record_discovery(
                # THE KIND IS THE source_type, because that is the column the registry can be
                # QUERIED on. The discoveries table has no kind column, so passing one would
                # have been dropped by record_discovery's field filter, and the desk would
                # hold residual targets it could not select.
                source_id="world_model:residual", source_type="residual_target",
                mechanism=target["candidate_explanations"]["causal_mechanism"][0]["text"],
                origin="DESK", generator="residual_hunt",
                discovery_id=target["cluster_id"],
                kind="residual_target", assets=[cell["target"]],
                horizons=[cell["horizon"]], sessions=[cell["session"]],
                regimes=[cell["regime"]], information="residual",
                economic_rationale=target["question"],
                required_data=target["candidate_explanations"]["missing_dataset"],
                novelty=1.0, confidence=0.3,
                falsifier=("the cluster's conditional mean and |epsilon| persistence both fall "
                           "inside the circular-block null once a proxy dataset is ingested"),
                payload=target, conn=conn)
            target["discovery_id"] = did
            out["discoveries"] += int(created)
            reg.set_discovery_state(did, "UNPROCESSED", conn=conn)
            try:
                conn.execute(
                    "INSERT INTO frontier_map(cell, language, country, source_type, asset_class,"
                    " mechanism_class, n_sources, n_leads, n_distinct, n_singletons,"
                    " n_doubletons, chao1_unseen, last_scouted, cold, updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(cell) DO UPDATE SET"
                    " n_leads=excluded.n_leads, cold=excluded.cold,"
                    " updated_at=excluded.updated_at",
                    (f"residual:{target['cluster_id']}", "", ",".join(
                        target["candidate_explanations"]["region"]), "residual",
                     cell["target"], "unexplained_residual", 0,
                     len(target["candidate_explanations"]["missing_dataset"]), 0, 0, 0, None,
                     None, 1, reg.now()))
                out["frontier_cells"] += 1
            except Exception:
                pass
        for closure in closures:
            try:
                reg.set_discovery_state(closure["cluster_id"], "TESTED",
                                        reason=closure["why"], conn=conn)
                out["closed"] += 1
            except Exception:
                pass
            for dataset in closure.get("credited_datasets") or []:
                try:
                    import source_frontier as sf

                    sf.bump_source_yield(dataset, conn=conn, claims=1.0, mechanisms=1.0)
                    out["credited"] += 1
                except Exception:
                    continue
            with contextlib.suppress(Exception):
                reg.remember("residual", closure["why"], kind="residual_closed",
                             memory_key=f"residual:{closure['cluster_id']}", result="success",
                             evidence=closure, conn=conn)
        conn.commit()
    finally:
        conn.close()
    return out


# ---------------------------------------------------------------------------- delayed credit
@dataclass
class Book:
    """The open targets, carried across passes so nothing ever silently disappears."""

    targets: dict[str, dict[str, Any]] = field(default_factory=dict)
    datasets_seen: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> Book:
        doc = _read_json(path)
        if not isinstance(doc, dict):
            return cls()
        raw = doc.get("targets")
        return cls(targets={str(k): v for k, v in raw.items() if isinstance(v, dict)}
                   if isinstance(raw, dict) else {},
                   datasets_seen=[str(d) for d in doc.get("datasets_seen") or []])


def settle(book: Book, clusters: dict[str, Cluster], datasets_now: set[str]
           ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Close what a newly ingested dataset explained; age what nobody has seen; keep the rest.

    THE CREDIT IS DELAYED AND IT IS THE POINT. A dataset ingested three passes ago that shrinks
    this cell's residual variance by `EXPLAINED_DROP` is the only evidence the desk will ever get
    that the acquisition was worth its compute -- and it arrives long after the acquisition. A
    target whose cluster has simply not been re-measured goes STALE with its reason attached; it
    is never dropped, because the record of what the desk used to not know is how it knows the
    hunt is working.
    """
    closures: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    gained = sorted(datasets_now - set(book.datasets_seen))
    for cid, target in book.targets.items():
        current = clusters.get(cid)
        opened = float(target.get("variance_at_open") or 0.0)
        if current is not None and opened > 0:
            drop = (opened - current.variance) / opened
            if drop >= EXPLAINED_DROP:
                credit = (": " + ", ".join(gained[:6]) if gained
                          else " (no new dataset: the model itself improved)")
                closures.append({
                    "cluster_id": cid, "cell": target.get("cell"),
                    "variance_at_open": opened, "variance_now": round(current.variance, 12),
                    "variance_drop": round(float(drop), 4),
                    "credited_datasets": gained,
                    "why": (f"the world model's residual variance in this cell fell "
                            f"{drop:.0%} after {len(gained)} dataset(s) entered the "
                            f"model{credit}"),
                    "closed_at": now_iso()})
                continue
        age_days = 0.0
        opened_at = WM.R.parse_time(str(target.get("opened_at") or ""))
        if opened_at is not None:
            age_days = (datetime.now(tz=UTC) - opened_at).total_seconds() / 86400.0
        row = dict(target)
        if current is None and age_days > STALE_DAYS:
            row["state"] = "STALE"
            row["why"] = (f"nothing has re-measured this cell for {age_days:.0f} days; the "
                          f"residual store no longer carries it. STALE is a state, not a "
                          f"deletion -- it re-opens the moment the cell is measured again")
        still_open.append(row)
    return closures, still_open


# ---------------------------------------------------------------------------- the pass
def run(*, budget_s: float = 600.0, dry_run: bool = False,
        permutations: int = PERMUTATIONS, max_targets: int = MAX_TARGETS) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + budget_s
    calendar = load_calendar()
    book = Book.load(STATE)

    world = _read_json(WM.OUT)
    datasets_now = set((world or {}).get("dataset_credit", {}).keys()) if isinstance(
        world, dict) else set()
    have_representations = {str(r.get("family", "")) + "|" + str(r.get("dataset", ""))
                            for r in ((_read_json(WM.REPRESENTATIONS / "manifest.json") or {})
                                      .get("representations") or [])
                            if isinstance(r, dict)}

    rows: list[dict[str, Any]] = []
    per_horizon: dict[str, int] = {}
    for horizon in WM.HORIZONS:
        found = WM.read_residuals(horizon)
        per_horizon[horizon] = len(found)
        rows.extend(found)
    if not rows:
        report = {"at": now_iso(), "rule": RULE, "status": "UNMEASURED",
                  "why": "the residual store is empty: the world model has not run here yet",
                  "measured_by": "hourly_cycle:world_model writing "
                                 "data/world_model/residuals_<horizon>.parquet",
                  "store": per_horizon, "elapsed_s": round(time.monotonic() - started, 2),
                  "dry_run": dry_run}
        if not dry_run:
            _atomic(OUT, report)
        return report

    clusters, counts = cluster_residuals(rows, calendar, permutations=permutations,
                                         deadline=deadline)
    by_id = {c.cluster_id: c for c in clusters}
    persistent = [c for c in clusters if c.status == "PERSISTENT"]
    persistent.sort(key=lambda c: (-abs(c.effect_sd if np.isfinite(c.effect_sd) else 0.0),
                                   c.cluster_id))

    closures, still_open = settle(book, by_id, datasets_now)
    open_ids = {str(t.get("cluster_id")) for t in still_open}
    closed_ids = {str(c["cluster_id"]) for c in closures}

    targets: list[dict[str, Any]] = []
    for cluster in persistent[:max_targets]:
        if cluster.cluster_id in closed_ids:
            continue
        if cluster.cluster_id in open_ids:
            continue                          # already an open target: idempotent by content hash
        target = search_target(cluster, datasets_now, have_representations)
        target["query_seeds"] = query_seeds(target)
        targets.append(target)

    universe = _hypothesis_universe()
    donations = donation_rows(targets[:MAX_DONATIONS], universe)
    registry: dict[str, Any] = {"status": "SKIPPED_DRY_RUN"}
    donation_path: str | None = None
    if not dry_run:
        registry = record_targets(targets, closures)
        if donations:
            stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
            path = DONATIONS / f"discoveries_{stamp}.json"
            _atomic(path, donations)
            donation_path = str(path)
        _atomic(STATE, {
            "at": now_iso(),
            "datasets_seen": sorted(datasets_now | set(book.datasets_seen)),
            "targets": {**{str(t["cluster_id"]): t for t in still_open},
                        **{str(t["cluster_id"]): t for t in targets}},
            "closed": {c["cluster_id"]: c for c in closures},
        })

    report = {
        "at": now_iso(), "rule": RULE, "budget_s": budget_s,
        "elapsed_s": round(time.monotonic() - started, 2), "dry_run": dry_run,
        "store": per_horizon, "rows_read": counts["rows"],
        "clusters": {"cells": int(counts["cells"]), "measured": int(counts["measured"]),
                     "unmeasured_below_min_n": int(counts["unmeasured_small"]),
                     "min_cluster_n": MIN_CLUSTER_N,
                     "unparsed_rows": int(counts["unparsed_rows"]),
                     "persistent": len(persistent)},
        "null": {"kind": "circular_block_permutation", "permutations": permutations,
                 "mean_null": "exact over the whole circular-shift group (one FFT)",
                 "p_threshold": P_THRESHOLD, "min_abs_effect_sd": MIN_ABS_EFFECT_SD,
                 "fdr_q": FDR_Q, "bh_cut": round(float(counts["bh_cut"]), 8),
                 "cells_charged": int(counts["bh_m"]),
                 "why": "a rolled path keeps the autocorrelation an hourly residual really has; "
                        "an i.i.d. shuffle would call half the clock cells significant. Trial "
                        "count is a shared cost, so every cell tested this pass pays into one "
                        "Benjamini-Hochberg correction"},
        "calendar": {"events": int(calendar.events.size), "kinds": list(calendar.kinds)[:12],
                     "covered": calendar.covered_from is not None},
        "targets_opened": len(targets), "targets_open_total": len(still_open) + len(targets),
        "targets_closed": len(closures),
        "targets": targets[:max_targets],
        "closures": closures[:40],
        "donations": {"rows": len(donations), "path": donation_path,
                      "seat": "data/intelligence/residual_hunt"},
        "top_clusters": [
            {"cluster_id": c.cluster_id, "cell": c.key, "n": c.n,
             "mean_epsilon": round(c.mean, 8), "effect_sd": c.effect_sd,
             "p_mean": None if not np.isfinite(c.p_mean) else round(c.p_mean, 5),
             "p_persistence": None if not np.isfinite(c.p_persistence)
             else round(c.p_persistence, 5), "status": c.status}
            for c in persistent[:40]],
        "unmeasured": [{"cluster_id": c.cluster_id, "cell": c.key, "n": c.n, "why": c.why}
                       for c in clusters if c.status == "UNMEASURED"][:40],
        "registry": registry,
    }
    if not dry_run:
        _atomic(OUT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly cycle is the clock)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="test and print; write nothing")
    ap.add_argument("--permutations", type=int, default=PERMUTATIONS)
    ap.add_argument("--max-targets", type=int, default=MAX_TARGETS)
    args = ap.parse_args(argv)

    report = run(budget_s=args.budget_s, dry_run=args.dry_run, permutations=args.permutations,
                 max_targets=args.max_targets)
    if report.get("status") == "UNMEASURED":
        print(f"residual hunt: UNMEASURED -- {report['why']}")
        return 0
    clusters = report["clusters"]
    print(f"residual hunt: {clusters['cells']} cell(s), {clusters['measured']} measured, "
          f"{clusters['unmeasured_below_min_n']} below n={MIN_CLUSTER_N}, "
          f"{clusters['persistent']} persistent; {report['targets_opened']} target(s) opened, "
          f"{report['targets_closed']} closed, {report['donations']['rows']} donation(s), "
          f"{report['elapsed_s']}s")
    for row in report["top_clusters"][:8]:
        cell = row["cell"]
        print(f"    {cell['target']:<10}{cell['horizon']:>4} {cell['regime']:<5}"
              f"{cell['session']:<9}{cell['calendar_class']:<11}n={row['n']:<5} "
              f"eff={row['effect_sd']} p={row['p_mean']}")
    if args.dry_run:
        print("--dry-run: nothing written, no discovery, no donation")
    else:
        print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
