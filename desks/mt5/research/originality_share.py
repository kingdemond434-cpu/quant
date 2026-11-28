"""H2 NOVEL MECHANISM CREATION vs COPYING: how much of the docket, and of the certificates, is the
desk's own invention -- per producer, every hour.

WHY. The desk mints most of its docket by converting other people's claims (a public video, a
forum strategy, a published recipe) or by re-parameterising a mechanism somebody else already
put on the docket. Both are legitimate, and neither is the desk creating a mechanism. Until this
file nothing measured the difference, so "novel mechanisms per week" (a Tier-1 moat KPI) had no
numerator and the judge had no way to make sure the desk's own inventions were ever judged early.

THE CLASSIFICATION (per docket row, deterministic, declared here):

    COPIED    the row converts somebody else's claim: its producer is a declared copier (video,
              forum, social, published-recipe and public-playbook grounds, `COPY_PRODUCERS`) or
              its own note says so (`COPY_NOTE`, e.g. "converted from a public video",
              "source supplied exact recipe").
    VARIANT   not copied, but its MECHANISM FINGERPRINT was born on the docket by another
              producer or by a copied row -- a re-parameterisation or re-use of a mechanism
              somebody else brought.
    ORIGINAL  not copied, and the producer that wrote it is the one whose row FIRST carried the
              fingerprint (earliest `first_seen`, ties broken by producer name): the desk
              created that mechanism here.

THE FINGERPRINT IS HYPMAX'S, NOT A NEW ONE. `libs/hypmax/hypothesis_max.fingerprint` (feature
family | signal transform | horizon bucket) is the spec's mechanism identity, already used by the
trivial-variation blocker; here the family is the feature family, the parameter SHAPE (names, not
values) is the transform, and the chart's bar length is the horizon. So `rr=1.5` and `rr=3.0` of
one mechanism are one fingerprint, which is what makes VARIANT honest. Hypmax component #6
(`batch_diversity`) runs on the same fingerprints over the last day's births, per producer, so
generator collapse is measured on this clock too.

CERTIFICATES are joined by the desk's one cell identity (`frontier_identity.cell_id`) from
`certificate_provenance.json` (the birth record) to the docket row's class; a certificate whose
cell is not on the docket any more is UNMEASURED, never guessed from its family name.

This module classifies and publishes. The ordering quota that USES the classification lives in
`research/judge_docket_order.py` (`priority_tilt`), and it only changes which cells are warmed --
and therefore judged -- first. No gate, verdict or certificate reads this.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from libs.hypmax.hypothesis_max import batch_diversity, fingerprint

ORIGINAL = "ORIGINAL"
VARIANT = "VARIANT"
COPIED = "COPIED"
CLASSES = (ORIGINAL, VARIANT, COPIED)

#: Producer roots whose rows convert somebody else's claim. Matched as substrings of the
#: normalised producer name, so `miner:youtube` and `ext_reddit_EURUSD_...` both land.
COPY_PRODUCERS: tuple[str, ...] = (
    "video", "youtube", "reddit", "forexfactory", "github", "collective2", "myfxbook",
    "stocktwits", "fund_playbook", "world_crawler", "formula_library", "alpha158", "gtja",
    "deep_forest", "story_mechanism", "forum", "paper", "ssrn", "arxiv", "competition",
    "leaderboard", "track_record", "fxblue")

#: A row whose own note declares it a conversion of a published claim.
COPY_NOTE = re.compile(
    r"converted from a public|public (video|claim|paper|post|strategy|backtest)|"
    r"source supplied exact recipe|reported sharpe|from a (paper|video|forum|blog|post)|"
    r"as published|verbatim claim", re.I)

#: Bar length in hours per chart, the horizon hypmax buckets.
TF_HOURS: dict[str, float] = {"M1": 1 / 60, "M5": 5 / 60, "M15": 0.25, "M30": 0.5, "H1": 1.0,
                              "H4": 4.0, "D1": 24.0, "W1": 168.0, "MN1": 720.0}

#: Parameters that place a cell rather than shape its signal.
_PLACEMENT = frozenset({"timeframe", "session", "symbol", "sym", "selector"})


def producer_of(row: Mapping[str, Any]) -> str:
    """The row's producer, normalised: `miner:` dropped, per-cell suffixes folded."""
    s = str(row.get("source") or row.get("producer") or "?").strip()
    if s.startswith("miner:"):
        s = s[len("miner:"):]
    m = re.match(r"ext_([a-z]+)_", s)
    if m:
        return f"ext:{m.group(1)}"
    if s.startswith("gold_hour_sweep"):
        return "gold_hour_sweep"
    if s.startswith("session_chart_equivalent"):
        return "session_chart_equivalent"
    return s or "?"


def timeframe_of(row: Mapping[str, Any]) -> str:
    p = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    for src in (p, row):
        v = src.get("timeframe") if isinstance(src, Mapping) else None
        if v:
            return str(v).upper()
    return "H1"


def mechanism_fingerprint(row: Mapping[str, Any]) -> str:
    """hypmax `fingerprint(family, parameter shape, chart horizon)`."""
    p = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    shape = ",".join(sorted(str(k) for k in p if str(k) not in _PLACEMENT)) or "none"
    return fingerprint(str(row.get("family") or "?"), shape,
                       TF_HOURS.get(timeframe_of(row), 1.0))


def copy_basis(row: Mapping[str, Any]) -> str:
    """Why a row counts as COPIED ("" when it does not)."""
    prod = producer_of(row).lower()
    for tok in COPY_PRODUCERS:
        if tok in prod:
            return f"producer:{tok}"
    note = f"{row.get('mechanism_note') or ''} {row.get('source_title') or ''}"
    m = COPY_NOTE.search(note)
    return f"note:{m.group(0).lower()}" if m else ""


class Originality:
    """Two passes over one docket: `observe` every row, then `classify` any row."""

    def __init__(self) -> None:
        #: fingerprint -> (first_seen, producer, copied?) of its earliest row
        self.birth: dict[str, tuple[str, str, bool]] = {}

    def observe(self, row: Mapping[str, Any]) -> None:
        self.observe_parts(mechanism_fingerprint(row), str(row.get("first_seen") or "9999"),
                           producer_of(row), bool(copy_basis(row)))

    def observe_parts(self, fp: str, first_seen: str, producer: str, copied: bool) -> None:
        cand = (first_seen or "9999", producer, copied)
        cur = self.birth.get(fp)
        if cur is None or cand[:2] < cur[:2]:
            self.birth[fp] = cand

    def classify(self, row: Mapping[str, Any]) -> tuple[str, str]:
        """(class, basis)."""
        return self.classify_parts(mechanism_fingerprint(row), producer_of(row), copy_basis(row))

    def classify_parts(self, fp: str, producer: str, basis: str) -> tuple[str, str]:
        if basis:
            return COPIED, basis
        born = self.birth.get(fp)
        if born is None:
            return ORIGINAL, "first row of its fingerprint"
        if born[2]:
            return VARIANT, f"fingerprint born on a copied row ({born[1]})"
        if born[1] != producer:
            return VARIANT, f"fingerprint born by {born[1]}"
        return ORIGINAL, "this producer created the fingerprint"


def _share(c: Mapping[str, int]) -> float | None:
    n = sum(int(c.get(k, 0)) for k in CLASSES)
    return round(int(c.get(ORIGINAL, 0)) / n, 6) if n else None


def report(per_row: Iterable[tuple[str, str, str, str]], *, certificates: Mapping[str, Any]
           | None, cell_class: Mapping[str, str], recent_fps: Mapping[str, list[str]],
           prior: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """ORIGINALITY.json from (producer, class, basis, fingerprint) per row.

    `certificates`: certificate_provenance.json's `records` (cell -> {producer, ...}) or None.
    `cell_class`: docket cell_id -> class. `recent_fps`: producer -> fingerprints born in the
    last day (hypmax batch diversity). `prior`: last ORIGINALITY.json, for the entropy trend.
    """
    by_prod: dict[str, dict[str, int]] = {}
    bases: dict[str, int] = {}
    fps_by_class: dict[str, set[str]] = {k: set() for k in CLASSES}
    for prod, cls, basis, fp in per_row:
        slot = by_prod.setdefault(prod, dict.fromkeys(CLASSES, 0))
        slot[cls] += 1
        fps_by_class[cls].add(fp)
        key = basis.split(":", 1)[0] if cls == COPIED else basis.split(" (", 1)[0]
        bases[f"{cls}:{key}"] = bases.get(f"{cls}:{key}", 0) + 1
    tot = {k: sum(v[k] for v in by_prod.values()) for k in CLASSES}

    cert: dict[str, Any]
    if certificates is None:
        cert = {"status": "UNMEASURED", "why": "certificate_provenance.json unreadable"}
    else:
        cprod: dict[str, dict[str, int]] = {}
        for cell, rec in certificates.items():
            who = str((rec or {}).get("producer") or "?") if isinstance(rec, Mapping) else "?"
            cls = cell_class.get(str(cell), "UNMEASURED")
            slot = cprod.setdefault(who, dict.fromkeys((*CLASSES, "UNMEASURED"), 0))
            slot[cls] += 1
        ctot = {k: sum(v[k] for v in cprod.values()) for k in (*CLASSES, "UNMEASURED")}
        cert = {"status": "MEASURED", "n": sum(ctot.values()), "totals": ctot,
                "share_original": _share(ctot),
                "by_producer": {p: {**v, "share_original": _share(v)}
                                for p, v in sorted(cprod.items(), key=lambda kv: -sum(
                                    kv[1].values()))}}

    prior_div = ((prior or {}).get("generator_diversity") or {}).get("by_producer") or {}
    div: dict[str, Any] = {}
    for prod, fps in sorted(recent_fps.items(), key=lambda kv: -len(kv[1])):
        pn = (prior_div.get(prod) or {}).get("normalised")
        bd = batch_diversity(list(fps), prior_normalised=pn if isinstance(pn, (int, float))
                             else None)
        div[prod] = {"n": bd.n, "distinct": bd.distinct, "normalised": bd.normalised,
                     "duplicate_rate": bd.duplicate_rate, "collapsed": bd.collapsed,
                     "reasons": list(bd.reasons)}
    return {
        "law": "H2: every docket row and certificate is ORIGINAL, VARIANT or COPIED by the "
               "declared rule; the share ORIGINAL is published per producer. A measurement and "
               "an ordering quota input, never a gate.",
        "docket": {"n": sum(tot.values()), "totals": tot, "share_original": _share(tot),
                   "fingerprints": {k: len(v) for k, v in fps_by_class.items()},
                   "basis": dict(sorted(bases.items(), key=lambda kv: -kv[1])),
                   "by_producer": {p: {**v, "share_original": _share(v)}
                                   for p, v in sorted(by_prod.items(),
                                                      key=lambda kv: -sum(kv[1].values()))}},
        "certificates": cert,
        "generator_diversity": {
            "window": "fingerprints of rows first seen in the last 24h, per producer "
                      "(hypmax batch_diversity: collapse = duplicate rate > 25% or normalised "
                      "entropy down > 40% on the prior pass)",
            "collapsed": sorted(p for p, v in div.items() if v["collapsed"]),
            "by_producer": div},
        "rule": {"COPIED": "producer in COPY_PRODUCERS or note matches COPY_NOTE",
                 "VARIANT": "fingerprint born by another producer or on a copied row",
                 "ORIGINAL": "this producer's row first carried the fingerprint",
                 "fingerprint": "libs.hypmax.hypothesis_max.fingerprint(family, parameter "
                                "shape, chart horizon)",
                 "copy_producers": list(COPY_PRODUCERS)},
    }
