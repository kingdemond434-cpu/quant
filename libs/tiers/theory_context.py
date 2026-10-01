"""THE THEORY-EVIDENCE GRAPH'S CONTEXT AND MEMORY (Tier S layer 18).

`theory.TheoryGraph` weighs every experiment live 3 / forward 2 / backtest 1 into one Beta
posterior per mechanism. Two things were missing, and both change what a posterior means:

JURISDICTION AND REGIME AS EVIDENCE CONTEXT. A mechanism that works on the yen and fails on the
euro, or pays in a high-volatility regime and bleeds in a calm one, is not "CONTESTED" -- it is
CONDITIONAL, and a pooled posterior hides the condition it should be naming. Every evidence item
now carries

    jurisdiction   the monetary jurisdictions the instrument settles in, from its currency legs
                   (EURUSD -> EU+US, XAUUSD -> US, JP225 -> JP); UNMEASURED when unresolvable
    regime         BACKTEST evidence spans every regime of its sample and says so (`full_sample`);
                   a cell that DECLARES a condition carries it (`vol_filter=high`); FORWARD and
                   LIVE evidence carries the instrument's volatility regime at the reading
                   (`vol_high` / `vol_low` from its own H1 bars), or UNMEASURED with the reason

and `context_report()` re-derives the posterior within each jurisdiction and each regime. A theory
whose statuses DISAGREE across contexts (SUPPORTED in one, REFUTED or clearly weaker in another)
is marked CONTEXT_DEPENDENT and names the contexts -- a hypothesis about the condition, which is
exactly what the composition step then tests.

PERSISTENCE BETWEEN PASSES. The graph was rebuilt from the ledgers every hour, so evidence whose
source row disappeared (a certificate dropped from the survivors file, a forward clock retired, a
replication verdict rotated out) vanished from the posterior with it -- the graph forgot its own
contradictions. `merge_persisted()` keeps every evidence item the graph has ever held under
`desks/mt5/data/tier_s/theory_graph.json`, keyed (theory, experiment, source): this pass's reading
of an item replaces the stored one; an item this pass did not see is CARRIED (flagged, still
counted). A per-theory confidence trajectory is kept across passes as well.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from libs.tiers import theory

UNMEASURED = "UNMEASURED"
MAX_EVIDENCE_PER_THEORY = 4000
MAX_HISTORY = 240

#: currency / prefix -> jurisdiction
CURRENCY_JURISDICTION: dict[str, str] = {
    "USD": "US", "EUR": "EU", "JPY": "JP", "GBP": "GB", "AUD": "AU", "NZD": "NZ", "CAD": "CA",
    "CHF": "CH", "CNH": "CN", "CNY": "CN", "HKD": "HK", "SGD": "SG", "SEK": "SE", "NOK": "NO",
    "DKK": "DK", "PLN": "PL", "HUF": "HU", "CZK": "CZ", "MXN": "MX", "ZAR": "ZA", "TRY": "TR",
    "ILS": "IL", "THB": "TH", "INR": "IN", "KRW": "KR", "BRL": "BR", "RUB": "RU",
}
#: index / commodity roots whose jurisdiction is not a currency leg
ROOT_JURISDICTION: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("US", ("US500", "US30", "US100", "USTEC", "NAS100", "SPX", "DJ30", "US2000", "VIX",
            "USDX", "DXY")),
    ("DE", ("GER40", "DE40", "GER30", "DAX")),
    ("GB", ("UK100", "FTSE")),
    ("JP", ("JP225", "JPN225", "NIKKEI")),
    ("AU", ("AUS200", "ASX")),
    ("HK", ("HK50", "HSI", "CHINAH")),
    ("CN", ("CHINA50", "CN50", "A50")),
    ("FR", ("FRA40", "CAC")),
    ("EU", ("EU50", "STOXX50", "EUSTX50")),
    ("ES", ("ESP35", "SPA35", "IBEX")),
)
METAL_OR_ENERGY = ("XAU", "XAG", "XPT", "XPD", "XCU", "XTI", "XBR", "XNG", "XZN", "XAL", "XNI")


def jurisdiction_of(symbol: str, meta: Mapping[str, Any] | None = None) -> str:
    """The instrument's settlement jurisdictions, '+'-joined in a stable order."""
    s = re.sub(r"[^A-Z0-9]", "", str(symbol or "").upper())
    if not s:
        return UNMEASURED
    for j, roots in ROOT_JURISDICTION:
        if any(s.startswith(r) for r in roots):
            return j
    if s.startswith(METAL_OR_ENERGY) and len(s) >= 6:
        return CURRENCY_JURISDICTION.get(s[3:6], UNMEASURED)
    if len(s) >= 6 and s[:3] in CURRENCY_JURISDICTION and s[3:6] in CURRENCY_JURISDICTION:
        return "+".join(sorted({CURRENCY_JURISDICTION[s[:3]], CURRENCY_JURISDICTION[s[3:6]]}))
    cur = str((meta or {}).get("currency_profit") or "")
    return CURRENCY_JURISDICTION.get(cur, UNMEASURED)


def declared_regime(cell: str) -> str | None:
    """A condition the cell names itself (`vol_filter=high`, `trend_filter=aligned`)."""
    m = re.search(r"(vol_filter|trend_filter|regime|state)[=:_-]([A-Za-z0-9]+)", str(cell or ""))
    return f"{m.group(1)}={m.group(2).lower()}" if m else None


def vol_regime(closes: Any, window: int = 120, history: int = 2000) -> str:
    """`vol_high` / `vol_low`: the latest `window`-bar realised volatility against the median of
    the same statistic over the trailing `history` bars. UNMEASURED on too short a series."""
    import numpy as np
    c = np.asarray(closes, dtype=float)
    c = c[np.isfinite(c) & (c > 0)]
    if len(c) < window * 3:
        return UNMEASURED
    r = np.diff(np.log(c[-history - 1:]))
    if len(r) < window * 2:
        return UNMEASURED
    rv = np.array([r[i - window:i].std() for i in range(window, len(r) + 1, max(1, window // 4))])
    return "vol_high" if rv[-1] > float(np.median(rv)) else "vol_low"


def add(t: theory.Theory, *, experiment: str, supports: bool, source: str, context: str = "",
        jurisdiction: str = UNMEASURED, regime: str = UNMEASURED, carried: bool = False) -> None:
    """`Theory.add` plus the two context keys on the evidence row it just appended."""
    t.add(experiment=experiment, supports=supports, source=source, context=context)
    t.evidence[-1].update({"jurisdiction": jurisdiction or UNMEASURED,
                           "regime": regime or UNMEASURED})
    if carried:
        t.evidence[-1]["carried"] = True


def _posterior(ev: list[Mapping[str, Any]]) -> dict[str, Any]:
    t = theory.Theory(theory.Mechanism())
    for e in ev:
        t.add(experiment=str(e.get("experiment")), supports=bool(e.get("supports")),
              source=str(e.get("source")))
    p = t.posterior()
    return {k: p[k] for k in ("confidence", "sd", "n_evidence", "status")}


def context_report(g: theory.TheoryGraph, min_n: int = 3) -> dict[str, dict[str, Any]]:
    """Per theory: the posterior within each jurisdiction and each regime, and the verdict
    CONTEXT_DEPENDENT when the contexts with enough evidence disagree."""
    out: dict[str, dict[str, Any]] = {}
    for mid, t in g.theories.items():
        rep: dict[str, Any] = {}
        split: list[str] = []
        for dim in ("jurisdiction", "regime"):
            by: dict[str, list[Mapping[str, Any]]] = {}
            for e in t.evidence:
                by.setdefault(str(e.get(dim) or UNMEASURED), []).append(e)
            posts = {k: _posterior(v) for k, v in sorted(by.items())}
            rep[f"by_{dim}"] = posts
            judged = {k: p for k, p in posts.items() if k != UNMEASURED and p["n_evidence"]
                      >= min_n}
            stats = {p["status"] for p in judged.values()}
            if "SUPPORTED" in stats and stats & {"REFUTED", "CONTESTED"}:
                split.append(dim)
        rep["context_dependent"] = split
        out[mid] = rep
    return out


def _key(mid: str, e: Mapping[str, Any]) -> str:
    return f"{mid}|{e.get('source')}|{e.get('experiment')}"


def merge_persisted(g: theory.TheoryGraph, path: Path, now: str) -> dict[str, Any]:
    """Carry every stored evidence item this pass did not re-observe into `g`, then write the
    merged graph (mechanisms, evidence, confidence trajectory) back to `path`."""
    try:
        old = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        old = {}
    old = old if isinstance(old, dict) else {}
    seen = {_key(mid, e) for mid, t in g.theories.items() for e in t.evidence}
    carried = 0
    for mid, doc in (old.get("theories") or {}).items():
        if not isinstance(doc, dict):
            continue
        t = g.theories.get(mid)
        if t is None:
            m = doc.get("mechanism") or {}
            mech = theory.Mechanism(**{k: str(m.get(k) or "") for k in theory.SLOTS},
                                    parents=tuple(m.get("parents") or ()),
                                    family=str(m.get("family") or ""))
            if mech.mid != mid:
                continue                              # a stored record that no longer hashes
            t = g.theory(mech)
        for e in doc.get("evidence") or []:
            if not isinstance(e, dict) or _key(mid, e) in seen:
                continue
            add(t, experiment=str(e.get("experiment")), supports=bool(e.get("supports")),
                source=str(e.get("source")), context=str(e.get("context") or ""),
                jurisdiction=str(e.get("jurisdiction") or UNMEASURED),
                regime=str(e.get("regime") or UNMEASURED), carried=True)
            seen.add(_key(mid, e))
            carried += 1
    hist: dict[str, Any] = dict(old["history"]) if isinstance(old.get("history"), dict) else {}
    theories: dict[str, Any] = {}
    for mid, t in g.theories.items():
        post = t.posterior()
        h = list(hist.get(mid) or [])
        h.append({"at": now, "confidence": post["confidence"], "n": post["n_evidence"],
                  "status": post["status"]})
        hist[mid] = h[-MAX_HISTORY:]
        theories[mid] = {"mechanism": t.mechanism.to_dict(),
                         "evidence": t.evidence[-MAX_EVIDENCE_PER_THEORY:]}
    doc_out = {"generated_utc": now, "passes": int(old.get("passes") or 0) + 1,
               "theories": theories, "history": hist}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc_out, default=str), encoding="utf-8")
    os.replace(tmp, path)
    n_ev = sum(len(t.evidence) for t in g.theories.values())
    return {"path": str(path), "passes": doc_out["passes"], "carried": carried,
            "evidence": n_ev, "theories": len(g.theories)}


def trajectory(path: Path, mid: str) -> list[dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return list(((doc or {}).get("history") or {}).get(mid) or [])
