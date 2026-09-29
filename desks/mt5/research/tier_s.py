"""TIER S -- the autonomous research institution's hourly organ.

The principal's Tier S blueprint (30 layers) and its final hardening layer (16 more) were closed on
2026-09-29 with one rule: no subsystem ships because it sounds sophisticated; each must measurably
raise independent-alpha discovery, falsification power, information per compute, calibration or
execution capture, or cut false discoveries or operational risk. `docs/research/tier_s_program.json`
is the ledger of the 46 layers, each with a MEASURABLE CONTRACT; this organ runs every kernel in
`libs/tiers/` against the desk's own artifacts, writes one report per kernel under
`reports/tier_s/`, evaluates every layer's contract on its metric's history, and ends with the
self-model: the desk's largest deficiency, ranked, and the architecture challengers it is running.

WHAT IT CHANGES (research side only -- nothing here sizes, admits, certifies or places):

  * data/intelligence/tier_s/*.json   hypothesis rows for the compiler: MAP-Elites empty niches,
                                      topology-steered orthogonal directions, broken structural
                                      relationships and cross-science labs. ADDS candidates; never
                                      removes, throttles or re-orders a miner.
  * data/tier_s/truth_journal.jsonl   the content-addressed lineage (append-only, hash-chained)
  * data/tier_s/*.json                organ state (Red Queen populations, genomes, ledgers)
  * data/tier_s/PROMOTION_FREEZE.json the immune system's verdict. PUBLISHED, NOT CONSUMED: the
                                      promoter reading it is a money-path change that waits for the
                                      principal's word.

Each kernel runs isolated (one failure never stops the rest) and records its seconds, so the
researcher market can price this organ like any other.

    python desks/mt5/research/tier_s.py [--only immune,formal] [--dry-run]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
import traceback
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.tiers import (  # noqa: E402
    bitemporal,
    chaos,
    contracts,
    cross_science,
    epistemic,
    evolution,
    failure_memory,
    firewall,
    formal,
    frontier,
    meta_benchmark,
    online_fdr,
    opportunity_exchange,
    prediction_accounting,
    red_queen,
    replay,
    researcher_market,
    review_panel,
    self_model,
    test_invention,
    theory,
    topology,
    truth_kernel,
    twin,
    world_edges,
)

PRODUCTION_ARGS: list[str] = []

REPORTS = DESK / "reports"
OUT_DIR = REPORTS / "tier_s"
SUMMARY = REPORTS / "TIER_S.json"
STATE = DESK / "data" / "tier_s"
INTEL = DESK / "data" / "intelligence" / "tier_s"
LEDGER = ROOT / "docs" / "research" / "tier_s_program.json"
CONSTITUTION = ROOT / "docs" / "research" / "tier_s_constitution.json"
RATIFICATIONS = ROOT / "docs" / "research" / "tier_s_ratifications.jsonl"

SURVIVORS = (REPORTS / "UNIVERSAL_SURVIVORS.json", DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json")
REGISTRY = DESK / "data" / "sleeve_registry.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
ORDER_INTENTS = DESK / "data" / "order_intents.jsonl"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
EVENTS = DESK / "data" / "events.jsonl"
COMPUTE = DESK / "data" / "compute_ledger.jsonl"
HGRAPH = DESK / "data" / "hypothesis_graph.jsonl"
UNIVERSE = DESK / "data" / "universe"
SHADOW_STATES = tuple((REPORTS / "shadow").glob("*shadow_state.json")) if (
    REPORTS / "shadow").exists() else ()
PF_ALLOCATION = (REPORTS / "pf_allocation.json", DESK / "data" / "pf_allocation.json")
FORECAST_LOG = DESK / "data" / "pf_forecast_log.jsonl"

#: ledgers that must only ever grow (the evidence seal)
PROTECTED = (GATE_LEDGER, LIVE_LEDGER, ORDER_INTENTS, DECISIONS, FORECAST_LOG,
             DESK / "data" / "hypotheses" / "trial_ledger.jsonl",
             DESK / "data" / "preregistrations.jsonl", DESK / "data" / "decision_dataset.jsonl")

MAX_EMIT_PER_KIND = 150
NOW = datetime.now(UTC)


# ------------------------------------------------------------------------------------------------
# small io helpers
# ------------------------------------------------------------------------------------------------

def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _first(paths: Iterable[Path]) -> Any:
    for p in paths:
        d = _read(p)
        if d is not None:
            return d
    return None


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, sort_keys=False), encoding="utf-8")
    os.replace(tmp, p)


def _jsonl(p: Path, limit: int = 400_000) -> list[dict[str, Any]]:
    return replay.read_jsonl(p, limit)


def _state(name: str) -> dict[str, Any]:
    d = _read(STATE / f"{name}.json")
    return d if isinstance(d, dict) else {}


def _save_state(name: str, doc: Mapping[str, Any]) -> None:
    _write(STATE / f"{name}.json", dict(doc))


def survivors() -> dict[str, Any]:
    d = _first(SURVIVORS)
    if isinstance(d, dict):
        s = d.get("survivors", d)
        return s if isinstance(s, dict) else {}
    return {}


def registry() -> dict[str, Any]:
    d = _read(REGISTRY)
    s = (d or {}).get("sleeves") if isinstance(d, dict) else None
    return s if isinstance(s, dict) else {}


def shadow_rows() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in SHADOW_STATES:
        d = _read(p)
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict) and "n" in v:
                    out.setdefault(str(k), v)
    return out


def _spec(row: Mapping[str, Any]) -> dict[str, Any]:
    s = row.get("shadow_spec") or row.get("identity") or {}
    return s if isinstance(s, dict) else {}


SLEEVES_JSON = DESK / "data" / "sleeves.json"
SELECTORS = ("london_am", "london_pm", "afternoon", "overlap", "asia", "london", "ny", "all")


class Names:
    """One sleeve, five spellings. The survivors key ("external.XAUUSD.session_range_breakout"),
    the registry key ("EURZAR.overnight_gap_decay.asia"), the allocator's book name
    ("EURZAR_overnight_gap_decay_asia", "gold_asia"), the gateway's sleeve name
    ("audcad_discovered_asia_p_7c99...") and the shadow key ("XAUUSD.asia") all name the same
    thing, and every join across them used to miss. `key()` resolves any of them to
    SYM.family.selector (family "*" when the name carries none) and `group()` to SYM.selector,
    the grain the shadow clocks and the gold windows keep."""

    def __init__(self) -> None:
        self.alias: dict[str, tuple[str, str, str]] = {}
        self._families: list[str] = []
        try:
            from mt5desk.families import FAMILY_REGISTRY  # type: ignore[import-not-found]
            self._families = sorted(FAMILY_REGISTRY, key=len, reverse=True)
        except Exception:
            self._families = []
        for k, v in registry().items():
            if isinstance(v, dict):
                idn = v.get("identity") or {}
                self._add(str(k), idn.get("symbol"), idn.get("family"), idn.get("selector"))
        for k, row in survivors().items():
            if isinstance(row, dict):
                s = _spec(row)
                self._add(str(k), s.get("symbol"), s.get("family"), s.get("selector"))
        sj = _read(SLEEVES_JSON)
        rows = sj.get("sleeves") if isinstance(sj, dict) else sj
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and r.get("name"):
                parsed = self._parse(str(r["name"]))
                self._add(str(r["name"]), r.get("symbol") or parsed[0],
                          r.get("family") or parsed[1],
                          r.get("session") if r.get("session") not in (None, "all") else
                          parsed[2])
        # the ticket -> sleeve map: the live ledger's own `sleeve` field is often the close
        # comment ("[tp 4360.71]"), so a fill is joined through the order that opened it
        self.by_ticket: dict[str, str] = {}
        for r in _jsonl(ORDER_INTENTS, 200_000):
            t = str(r.get("ticket") or "")
            if t and t != "0" and r.get("sleeve"):
                self.by_ticket[t] = str(r["sleeve"])

    def _add(self, name: str, sym: Any, fam: Any, sel: Any) -> None:
        sym, fam, sel = str(sym or ""), str(fam or "*"), str(sel or "*")
        if not sym:
            return
        t = (sym, fam, sel)
        for a in (name, f"{sym}.{fam}.{sel}", f"{sym}_{fam}_{sel}"):
            self.alias.setdefault(a, t)

    def _parse(self, name: str) -> tuple[str, str, str]:
        low = name.lower()
        if low.startswith("gold_") or low.startswith("xau_"):
            sym = "XAUUSD"
        else:
            head = name.replace(".", "_").split("_")[0]
            sym = head.upper() if head.isalpha() and len(head) in (6, 7) else ""
        fam = next((f for f in self._families if f in low), "*")
        sel = next((s for s in SELECTORS if f"_{s}" in f"_{low}".replace(".", "_")), "*")
        if low.startswith("gold_"):
            sel = next((s for s in SELECTORS if low[5:].startswith(s)), sel)
        return sym, fam, sel

    def triple(self, name: Any) -> tuple[str, str, str] | None:
        n = str(name or "")
        if not n or n.startswith("["):
            return None
        t = self.alias.get(n)
        if t is None:
            p = self._parse(n)
            t = p if p[0] else None
            if t is not None:
                self.alias[n] = t
        return t

    def key(self, name: Any) -> str:
        t = self.triple(name)
        return ".".join(t) if t else str(name or "")

    def group(self, name: Any) -> str:
        t = self.triple(name)
        return f"{t[0]}.{t[2]}" if t else str(name or "")

    def fill_sleeve(self, row: Mapping[str, Any]) -> str:
        """The sleeve a live-ledger row belongs to: through its opening ticket first."""
        for k in ("entry_order", "position_id", "order"):
            s = self.by_ticket.get(str(row.get(k) or ""))
            if s:
                return s
        s = str(row.get("sleeve") or "")
        return "" if s.startswith("[") else s


_NAMES: Names | None = None


def names() -> Names:
    global _NAMES
    if _NAMES is None:
        _NAMES = Names()
    return _NAMES


def live_rows() -> list[dict[str, Any]]:
    """Live-ledger closing deals with `_key` (SYM.family.selector) resolved through the ticket."""
    nm = names()
    out = []
    for r in _jsonl(LIVE_LEDGER):
        s = nm.fill_sleeve(r)
        if s:
            out.append({**r, "_sleeve": s, "_key": nm.key(s), "_group": nm.group(s)})
    return out


def _asset_class(sym: str) -> str:
    try:
        import universe_policy
        return str(universe_policy.asset_class_of(sym))
    except Exception:
        return "UNCLASSIFIED"


def _may_hypothesise(sym: str) -> bool:
    try:
        import universe_policy
        return bool(universe_policy.may_hypothesise(sym))
    except Exception:
        return False


def _mechanism(family: str) -> str:
    try:
        import axis_registry
        return str(axis_registry.classify_family(family)[0])
    except Exception:
        return family or "UNKNOWN"


def _family_vocab() -> list[str]:
    try:
        import miner_candidate_compiler as mcc
        vocab = getattr(mcc, "_FAMILY_VOCAB", {})
        return sorted(k for k in vocab if mcc._registered_cached(k))
    except Exception:
        return []


_FAILMEM: dict[str, Any] | None = None


def _explored(row: Mapping[str, Any]) -> int:
    """How many judged cells the failure memory already holds in this row's neighbourhood."""
    global _FAILMEM
    if _FAILMEM is None:
        _FAILMEM = _read(STATE / "failure_memory.json") or {}
    if not _FAILMEM or not row.get("family") or not row.get("symbols"):
        return 0
    sym = str(row["symbols"][0])
    params = row.get("params") or {}
    desc = {"mechanism": _mechanism(str(row["family"])), "asset_class": _asset_class(sym),
            "selector": str(params.get("session") or "?")}
    try:
        return int(failure_memory.neighbourhood(desc, _FAILMEM)["explored"])
    except Exception:
        return 0


def _emit(kind: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Write hypothesis rows where the compiler reads (data/intelligence/**).

    ORDER, NEVER A FILTER: rows in regions the failure memory has already mapped as dead go
    LAST, so the cap spends itself on unexplored ground first. Nothing is dropped for having a
    failed neighbour -- a theorem about a region is a prior, not a verdict on a new cell."""
    rows = [r for r in rows if r.get("symbols")]
    rows = sorted(rows, key=_explored)[:MAX_EMIT_PER_KIND]
    if not rows:
        return {"kind": kind, "emitted": 0}
    stamp = NOW.strftime("%Y%m%dT%H")
    for r in rows:
        r.setdefault("found_at", NOW.isoformat())
        r.setdefault("source", f"tier_s:{kind}")
        r.setdefault("seat", "tier_s")
    _write(INTEL / f"{kind}_{stamp}.json", {"kind": kind, "generated_utc": NOW.isoformat(),
                                             "rows": rows})
    return {"kind": kind, "emitted": len(rows)}


def _returns_panel(max_symbols: int = 28, bars: int = 3000) -> tuple[dict[str, np.ndarray],
                                                                        dict[str, np.ndarray],
                                                                        dict[str, np.ndarray]]:
    """H1 log returns (plus closes and tick volumes) for hypothesis-eligible symbols."""
    rets: dict[str, np.ndarray] = {}
    closes: dict[str, np.ndarray] = {}
    vols: dict[str, np.ndarray] = {}
    if not UNIVERSE.exists():
        return rets, closes, vols
    try:
        import pandas as pd
    except ImportError:
        return rets, closes, vols
    files = sorted(UNIVERSE.glob("*_H1.parquet"), key=lambda p: -p.stat().st_size)
    for p in files:
        sym = p.name[: -len("_H1.parquet")]
        if not _may_hypothesise(sym):
            continue
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue
        if "close" not in df or len(df) < 500:
            continue
        c = df["close"].astype(float).to_numpy()[-bars:]
        c = c[np.isfinite(c) & (c > 0)]
        if len(c) < 500:
            continue
        closes[sym] = c
        rets[sym] = np.diff(np.log(c))
        for vk in ("tick_volume", "volume", "real_volume"):
            if vk in df:
                vols[sym] = df[vk].astype(float).to_numpy()[-len(c):]
                break
        if len(rets) >= max_symbols:
            break
    if rets:
        n = min(len(v) for v in rets.values())
        rets = {k: v[-n:] for k, v in rets.items()}
    return rets, closes, vols


# ------------------------------------------------------------------------------------------------
# organs
# ------------------------------------------------------------------------------------------------

def _family_code_hash(fam: str) -> str | None:
    """sha256 of the family's signal function source: the program that compiled the hypothesis."""
    try:
        import inspect

        from mt5desk.families import FAMILY_REGISTRY  # type: ignore[import-not-found]
        fn = (FAMILY_REGISTRY.get(fam) or {}).get("func")
        return truth_kernel.sha256(inspect.getsource(fn))[:16] if fn else None
    except Exception:
        return None


def organ_truth_kernel() -> dict[str, Any]:
    j = truth_kernel.Journal(STATE / "truth_journal.jsonl").load()
    surv = survivors()
    nm = names()
    reg = {nm.key(k): v for k, v in registry().items() if isinstance(v, dict)}

    def cert_of(sleeve: Any) -> str | None:
        return (cert_by_sleeve.get(str(sleeve)) or cert_by_sleeve.get(nm.key(sleeve))
                or cert_by_sleeve.get(nm.group(sleeve)))
    cert_by_sleeve: dict[str, str] = {}
    added: Counter[str] = Counter()
    before = len(j.nodes())
    for key, row in surv.items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sym, fam = str(spec.get("symbol") or row.get("sym") or ""), str(spec.get("family") or "")
        at0 = str(row.get("gated_at") or NOW.isoformat())
        idn = (reg.get(nm.key(key)) or {}).get("identity") or {}
        raw = j.put("raw_data", {"symbol": sym, "timeframe": spec.get("timeframe") or "H1",
                                 "venue": idn.get("data_venue") or "MT5:FusionMarkets",
                                 "cost_hash": idn.get("cost_hash"),
                                 "bars": f"data/universe/{sym}_{spec.get('timeframe') or 'H1'}"
                                         ".parquet"}, at=at0)
        code = j.put("transformation", {"family": fam, "code_hash": idn.get("code_hash")
                                        or _family_code_hash(fam),
                                        "params": row.get("params") or spec.get("params")},
                     at=at0)
        hyp = j.put("hypothesis", {"cell": row.get("cell") or key, "symbol": sym, "family": fam,
                                   "selector": spec.get("selector")}, [raw.id, code.id], at=at0)
        exp = j.put("experiment", {"gates": row.get("gates") or {}, "days": row.get("days"),
                                   "hunt": row.get("hunt")}, [hyp.id],
                    at=str(row.get("gated_at") or NOW.isoformat()))
        cert = j.put("certificate", {"key": key, "gated_at": row.get("gated_at")}, [exp.id],
                     at=str(row.get("gated_at") or NOW.isoformat()))
        for k in (f"{sym}.{spec.get('selector')}", f"{sym}.{fam}.{spec.get('selector')}",
                  str(key), nm.key(key), nm.group(key)):
            cert_by_sleeve.setdefault(k, cert.id)
    alloc_rows = [r for r in _jsonl(FORECAST_LOG, 50_000) if isinstance(r.get("book"), dict)]
    alloc_ids: list[tuple[str, str]] = []
    for r in alloc_rows[-500:]:
        book = r.get("book") or {}
        parents = sorted({c for c in (cert_of(k) for k in book) if c})
        a = j.put("allocation", {"t": r.get("t"), "book": book, "total_heat": r.get("total_heat"),
                                 "certified": r.get("certified")}, parents,
                  at=str(r.get("t") or NOW.isoformat()))
        alloc_ids.append((str(r.get("t") or ""), a.id))
    alloc_ids.sort()

    def alloc_before(t: str) -> str | None:
        prev = None
        for at, aid in alloc_ids:
            if at <= t:
                prev = aid
            else:
                break
        return prev

    order_by_ticket: dict[str, str] = {}
    for r in _jsonl(ORDER_INTENTS, 100_000):
        t = str(r.get("time") or "")
        parents = [p for p in (alloc_before(t), cert_of(r.get("sleeve"))) if p]
        o = j.put("order", {k: r.get(k) for k in ("sleeve", "symbol", "side", "lot", "intended",
                                                  "sl", "tp", "ticket", "retcode", "time")},
                  parents, at=t or NOW.isoformat())
        if r.get("ticket"):
            order_by_ticket[str(r.get("ticket"))] = o.id
    for r in live_rows():
        t = str(r.get("time") or "")
        # a closing deal's `order` is the CLOSE ticket; the intent was journalled under the
        # ticket that OPENED the position, which the ledger carries as entry_order/position_id
        op = next((order_by_ticket[str(r.get(k))] for k in ("entry_order", "position_id",
                                                              "order")
                   if str(r.get(k) or "") in order_by_ticket), None)
        parents = [op] if op else [p for p in (alloc_before(t), cert_of(r["_sleeve"])) if p]
        j.put("fill", {**{k: r.get(k) for k in ("symbol", "side", "volume", "fill_price",
                                                "deal", "order", "entry_order", "pl_quote",
                                                "time")}, "sleeve": r["_sleeve"]},
              parents, at=t or NOW.isoformat())
    for n in j.nodes():
        added[n.kind] += 1
    ver = j.verify()
    cov = j.coverage()
    # the constitution and the evidence seal
    sealed = truth_kernel.constitution_doc()
    live = _read(CONSTITUTION) or sealed
    ratifs, rejected = _verified_ratifications(_jsonl(RATIFICATIONS))
    const = truth_kernel.constitution_status(sealed, live, ratifs)
    const["ratifications_rejected"] = rejected
    prev_seal = _state("evidence_seal")
    seal = truth_kernel.seal_ledgers(list(PROTECTED), prev_seal, DESK)
    hist = list(prev_seal.get("violations_history") or [])
    if seal["violations"]:
        hist.append({"at": NOW.isoformat(), "violations": seal["violations"]})
    _save_state("evidence_seal", {**seal, "violations_history": hist[-200:]})
    return {"verify": ver, "coverage": cov, "nodes_by_kind": dict(added),
            "new_nodes": len(j.nodes()) - before, "constitution": const,
            "evidence_seal": {"n_ledgers": seal["n"], "violations": seal["violations"]},
            "metric": {"fill_reconstructible_share": cov.get("share"),
                       "journal_ok": 1.0 if ver.get("ok") else 0.0,
                       "rewrites": sum(1 for v in seal["violations"] if v["kind"] == "REWRITTEN"),
                       "constitution_violation": 1.0 if const["status"] == "VIOLATION" else 0.0}}


AGENT_MARKERS = ("co-authored-by: claude", "claude-session:", "codex", "noreply@anthropic",
                 "generated with [claude")


def _verified_ratifications(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                                  list[dict[str, Any]]]:
    """Only ratifications a HUMAN committed count. The kernel accepts any row whose `by` starts
    with "principal"; any agent can type that. So each row's hash is traced to the commit that
    added it (`git log -S`), and a row added by a commit carrying an agent's author or trailer
    is refused and named. No git on the host = nothing verifies = nothing is ratified."""
    import subprocess
    ok, bad = [], []
    for r in rows:
        h = str(r.get("hash") or "")
        if not h:
            continue
        try:
            out = subprocess.run(
                ["git", "log", "--format=%an <%ae>%n%B%n--END--", "-S", h, "--",
                 str(RATIFICATIONS.relative_to(ROOT))], cwd=str(ROOT), capture_output=True,
                text=True, timeout=30, check=False).stdout
        except Exception as exc:
            bad.append({"hash": h, "why": f"git unavailable ({type(exc).__name__})"})
            continue
        commits = [c for c in out.split("--END--") if c.strip()]
        if not commits:
            bad.append({"hash": h, "why": "no commit added this ratification"})
            continue
        adding = commits[-1].lower()
        if any(m in adding for m in AGENT_MARKERS):
            bad.append({"hash": h, "why": "added by a commit carrying an agent's identity"})
            continue
        ok.append(r)
    return ok, bad


def organ_firewall() -> dict[str, Any]:
    audit = firewall.audit(ROOT)
    st = _state("firewall")
    base = st.get("baseline")
    rat = firewall.ratchet(audit, base)
    if base is None or len(audit["violations"]) < len((base or {}).get("violations") or []):
        st["baseline"] = {"violations": audit["violations"], "at": NOW.isoformat()}
    _save_state("firewall", st)
    return {"audit": audit, "ratchet": rat,
            "metric": {"violations": audit["n_violations"], "breach": 1.0 if rat["breach"]
                       else 0.0}}


def _incumbent_validator() -> meta_benchmark.ValidatorConfig:
    ad = _state("adopted")
    g = ad.get("validator")
    if isinstance(g, dict):
        try:
            g = dict(g)
            g["extra"] = tuple(tuple(x) for x in g.get("extra") or [])
            return meta_benchmark.ValidatorConfig(**g)
        except TypeError:
            pass
    return meta_benchmark.ValidatorConfig()


def organ_immune() -> dict[str, Any]:
    suite = meta_benchmark.Suite(per_kind=12)
    cfg = _incumbent_validator()
    seal = suite.seal()
    res = meta_benchmark.score(meta_benchmark.reference_validator(cfg), suite)
    st = _state("immune")
    hist = list(st.get("history") or [])
    const = _read(CONSTITUTION) or truth_kernel.constitution_doc()
    floor = float(((const.get("rules") or {}).get("immune.min_trap_rejection") or {})
                  .get("value", 0.9))
    verdict = meta_benchmark.immune_verdict(res, hist, floor=floor, seal=seal)
    hist.append({"at": NOW.isoformat(), "seal": seal, "immune_score": res["immune_score"],
                 "power": res["power"]})
    _save_state("immune", {"history": hist[-500:]})
    _write(STATE / "PROMOTION_FREEZE.json", {
        "verdict": verdict["verdict"], "why": verdict.get("why"), "at": NOW.isoformat(),
        "consumer": "NONE YET -- the promoter reading this is a money-path change awaiting the "
                    "principal's word", "immune_score": res["immune_score"], "seal": seal})
    return {"score": res, "seal": seal, "verdict": verdict, "floor": floor,
            "validator": cfg.genome(),
            "metric": {"immune_score": res["immune_score"], "power": res["power"],
                       "balanced": res["balanced"]}}


def organ_test_invention() -> dict[str, Any]:
    inc = _incumbent_validator()
    out = test_invention.invent(inc, meta_benchmark.Suite(per_kind=6, base_seed=31337),
                                meta_benchmark.Suite(per_kind=6, base_seed=424242))
    st = _state("candidate_gates")
    reg = {json.dumps(g["check"]): g for g in st.get("gates") or []}
    for g in out["candidate_gates"]:
        k = json.dumps(g["check"])
        reg.setdefault(k, {**g, "first_seen": NOW.isoformat(), "confirmations": 0})
        reg[k]["confirmations"] = int(reg[k].get("confirmations", 0)) + 1
        reg[k]["last_seen"] = NOW.isoformat()
    _save_state("candidate_gates", {"gates": list(reg.values())})
    return {**out, "registry_size": len(reg),
            "metric": {"candidate_gates": len(out["candidate_gates"]),
                       "registry": len(reg)}}


def _trap_series(kind: str, seed: int, subtlety: float, n: int = 400
                 ) -> tuple[list[float], list[float]]:
    """(signal, forward return) per bar for one planted case: what a docket cell can carry."""
    from libs.tiers import traps
    case, _truth = traps.generate(kind, seed, n + 2, subtlety)
    px = np.asarray(case.prices, dtype=float)
    sig, fwd = [], []
    for t in range(1, min(len(px) - 1, n + 1)):
        sig.append(float(case.signal_fn(px, t)))
        fwd.append(float(px[t + 1] / px[t] - 1.0))
    return sig, fwd


def _real_gauntlet_attack(attackers: list[dict[str, Any]], gen: int) -> dict[str, Any]:
    """The elite attacks and two genuine planted signals, as ONE docket through the desk's real
    ten-gate certifier (the same route adversary.py drives its canaries through). An attack the
    real gauntlet admits is a blind spot of the gates that certify capital; a genuine signal it
    rejects is lost power. Nothing here writes a certificate: the docket is named for the attack
    and its verdicts are read back and discarded."""
    try:
        import adversary
        gate, blocked = adversary.real_gate()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    if gate is None:
        return {"status": "UNMEASURED", "why": blocked}
    cells, truth = [], {}
    plan = [(str(a.get("kind")), float(a.get("subtlety") or 0.0)) for a in attackers[:6]]
    plan += [("true_signal", 0.0), ("true_weak_signal", 0.0)]
    for k, (kind, sub) in enumerate(plan):
        # the cell name carries no hint of the kind: the certifier judges it blind
        name = f"rq{gen}_" + truth_kernel.sha256(f"{gen}:{k}:{kind}:{sub}")[:10]
        try:
            sig, fwd = _trap_series(kind, gen * 101 + k, sub)
            cells.append(adversary.docket_cell(name, sig, fwd))
            truth[name] = kind
        except Exception:
            continue
    if len(cells) < 2:
        return {"status": "UNMEASURED", "why": "fewer than two attack cells could be built"}
    try:
        out = gate._gauntlet.run_gauntlet(cells, "red-queen-attack", adversary.CANARY_META)
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"run_gauntlet: {type(exc).__name__}: {exc}"}
    rows = []
    for v in out.get("verdicts") or []:
        name = str(v.get("family", "")).removeprefix("canary_")
        if name not in truth:
            continue
        failed = [g for g, st in (v.get("stages") or {}).items() if not st.get("passed")]
        rows.append({"cell": name, "kind": truth[name], "genuine": truth[name].startswith("true"),
                     "passed": bool(v.get("passed")), "unmeasured": bool(v.get("unmeasured")),
                     "failed_gates": failed})
    traps_ = [r for r in rows if not r["genuine"] and not r["unmeasured"]]
    real = [r for r in rows if r["genuine"] and not r["unmeasured"]]
    leaks = [r for r in traps_ if r["passed"]]
    return {"status": "MEASURED", "rows": rows, "leaks": leaks,
            "attack_success": len(leaks) / len(traps_) if traps_ else None,
            "genuine_power": sum(r["passed"] for r in real) / len(real) if real else None}


def organ_red_queen() -> dict[str, Any]:
    st = _state("red_queen")
    attackers = red_queen.from_state(st)
    sealed = list(meta_benchmark.Suite(per_kind=4, base_seed=5150, n=1200).cases())
    gen = int(st.get("generation", 0)) + 1
    res = red_queen.generation(attackers, _incumbent_validator(), sealed, seed=gen)
    real = _real_gauntlet_attack([e["attack"] for e in res["elite_attacks"]], gen)
    hist = list(st.get("success_history") or [])
    hist.append({"gen": gen, "at": NOW.isoformat(), "attack_success": res["attack_success"],
                 "real_attack_success": real.get("attack_success"),
                 "real_genuine_power": real.get("genuine_power")})
    _save_state("red_queen", {"generation": gen, "attackers": res["next_attackers"],
                              "success_history": hist[-500:],
                              "challenger": res["challenger"],
                              "real_leaks": (real.get("leaks") or [])[:20]})
    if res["challenger"]:
        _register_challenger("validator", f"red_queen_gen{gen}", res["challenger"],
                             res["best_defender"])
    return {"generation": gen, **{k: v for k, v in res.items() if k != "next_attackers"},
            "real_gauntlet": real,
            "metric": {"attack_success": res["attack_success"],
                       "defender_balanced": res["best_defender"]["balanced"],
                       "real_attack_success": real.get("attack_success"),
                       "real_genuine_power": real.get("genuine_power")}}


def organ_online_fdr() -> dict[str, Any]:
    tests: list[online_fdr.Test] = []
    surv = survivors()
    tests.extend(online_fdr.tests_from_survivors(surv))
    # a survivor is keyed "<hunt>.<cell>" but the gate ledger by the bare cell: both spellings
    # go into `seen`, or the same trial is charged twice
    seen = {t.test_id for t in tests} | {str(r.get("cell")) for r in surv.values()
                                         if isinstance(r, dict) and r.get("cell")}
    n_gate = n_graph = 0
    graph_ids: set[str] = set()
    for r in _jsonl(GATE_LEDGER):
        cell = str(r.get("cell") or "")
        if r.get("graph_id"):
            graph_ids.add(str(r["graph_id"]))
        if not cell or cell in seen or r.get("passed"):
            continue
        seen.add(cell)
        n_gate += 1
        tests.append(online_fdr.Test(test_id=cell, at=str(r.get("at") or ""), p=1.0,
                                     family=str(r.get("family") or "")))
    # hypotheses the graph records as FAILED upstream of the gauntlet (screens, dedup, cheap
    # falsifiers) were tests too: each spent a look at the data. Charged once, at p=1.
    for r in _jsonl(HGRAPH, 400_000):
        nid = str(r.get("id") or "")
        if r.get("fate") != "FAILED" or not nid or nid in graph_ids or nid in seen:
            continue
        seen.add(nid)
        n_graph += 1
        tests.append(online_fdr.Test(test_id=nid, at=str(r.get("at") or ""), p=1.0,
                                     family=str(r.get("family") or "")))
    res = online_fdr.replay(tests)
    rows = res.pop("rows")
    over = [r for r in rows if r["over_budget"]]
    _write(OUT_DIR / "ONLINE_FDR_ROWS.json", {"generated_utc": NOW.isoformat(),
                                              "over_budget": over[:500],
                                              "certified": [r for r in rows if r["certified"]]})
    return {**res, "failed_tests_charged": n_gate, "upstream_failures_charged": n_graph,
            "note": "failed trials enter at p=1: they spend lifetime budget without earning it",
            "metric": {"over_budget_share": res["over_budget_share"],
                       "lord_discoveries": res["lord_discoveries"]}}


def _sleeve_descriptors() -> tuple[list[str], list[dict[str, Any]]]:
    names, descs = [], []
    for k, v in registry().items():
        if not isinstance(v, dict) or v.get("status") not in ("LIVE", "STANDBY", "ACTIVE"):
            continue
        idn = v.get("identity") or {}
        fam = str(idn.get("family") or "")
        sym = str(idn.get("symbol") or "")
        names.append(str(k))
        descs.append({"family": fam, "mechanism": _mechanism(fam), "symbol": sym,
                      "asset_class": _asset_class(sym), "selector": idn.get("selector"),
                      "direction": idn.get("direction"), "timeframe": idn.get("timeframe"),
                      "code": idn.get("code_hash")})
    return names, descs


def organ_topology() -> dict[str, Any]:
    sleeve_names, descs = _sleeve_descriptors()
    # live daily R per sleeve where the ledger has fills
    daily: dict[str, dict[str, float]] = defaultdict(dict)
    for r in live_rows():
        s, t = r["_group"], str(r.get("time") or "")[:10]
        if s and t:
            daily[s][t] = daily[s].get(t, 0.0) + float(r.get("pl_quote") or 0.0)
    pnl = None
    # live P&L is kept per SYMBOL.window (the grain a fill can be traced to), one column each
    pnl_names = sorted({g for g in (names().group(n) for n in sleeve_names) if g in daily})
    if len(pnl_names) >= 2:
        days = sorted({d for n in pnl_names for d in daily[n]})
        pnl = np.array([[daily[n].get(d, 0.0) for n in pnl_names] for d in days])
    rank = topology.rank_report(None, sleeve_names, descs)
    if pnl is not None and pnl.shape[0] >= 10:
        rank["live_pnl"] = topology.rank_report(pnl, pnl_names, None)
    steer = topology.steering(descs, rank.get("uniqueness"), sleeve_names,
                              ("mechanism", "asset_class", "selector", "timeframe"))
    # ancestry novelty over the hypothesis graph (parent -> child)
    nodes: dict[str, dict[str, Any]] = {}
    for r in _jsonl(HGRAPH, 60_000):
        nid = str(r.get("id") or "")
        if not nid:
            continue
        par = r.get("parent")
        nodes[nid] = {"parents": [str(par)] if par and str(par) in nodes else [],
                      "descriptors": {"family": r.get("family"), "symbol": r.get("symbol"),
                                      "source": str(r.get("source") or "").split(":")[0]}}
    nov = topology.novelty(nodes) if nodes else {}
    eff = topology.effective_discoveries(nov)
    st = _state("topology")
    hist = list(st.get("rank_history") or [])
    hist.append({"at": NOW.isoformat(), "combined": rank.get("combined"),
                 "n": len(sleeve_names)})
    _save_state("topology", {"rank_history": hist[-2000:]})
    # orthogonal directions -> hypotheses: the least-occupied mechanisms on new symbols
    emitted = _emit_orthogonal(steer, descs)
    return {"rank": rank, "steering": steer, "ancestry": eff, "emitted": emitted,
            "metric": {"effective_rank": rank.get("combined"), "n_sleeves": len(sleeve_names),
                       "effective_discoveries": eff.get("effective")}}


def _emit_orthogonal(steer: Mapping[str, Mapping[str, float]],
                     descs: list[dict[str, Any]]) -> dict[str, Any]:
    vocab = _family_vocab()
    if not vocab:
        return {"kind": "orthogonal", "emitted": 0, "why": "family vocabulary unavailable"}
    held = {(d["family"], d["symbol"]) for d in descs}
    mech_w = steer.get("mechanism") or {}
    fam_w = {f: mech_w.get(_mechanism(f), 1.0) for f in vocab}
    syms = [p.name[: -len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet")] if \
        UNIVERSE.exists() else []
    syms = [s for s in syms if _may_hypothesise(s)]
    cls_w = steer.get("asset_class") or {}
    rows = []
    for f in sorted(vocab, key=lambda x: -fam_w[x]):
        for s in sorted(syms, key=lambda x: -cls_w.get(_asset_class(x), 1.0)):
            if (f, s) in held:
                continue
            rows.append({"kind": "hypothesis", "family": f, "symbols": [s],
                         "text": f"tier_s orthogonal direction: {f} on {s} -- mechanism weight "
                                 f"{fam_w[f]:.3f}, asset-class weight "
                                 f"{cls_w.get(_asset_class(s), 1.0):.3f} vs the effective basis",
                         "steering": {"mechanism": fam_w[f],
                                      "asset_class": cls_w.get(_asset_class(s), 1.0)}})
            if len(rows) >= MAX_EMIT_PER_KIND:
                break
        if len(rows) >= MAX_EMIT_PER_KIND:
            break
    return _emit("orthogonal", rows)


def organ_qd() -> dict[str, Any]:
    # THE BEHAVIOUR SPACE IS THE DESK'S OWN (axis_registry.axis_cell: asset class, instrument,
    # chart, session, horizon, mechanism, information source, economic actor, regime, execution
    # style) plus direction and complexity -- the niches an elite can occupy are the ones the
    # research programme already names, not a private five-axis grid
    try:
        import axis_registry
        axis_cell = axis_registry.axis_cell
    except Exception:
        axis_cell = None
    axes = ("mechanism", "asset_class", "session", "chart", "horizon", "information_source",
            "economic_actor", "regime", "execution_style", "direction", "complexity")
    arch = evolution.Archive(axes)
    shadow = shadow_rows()
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sym, fam = str(spec.get("symbol") or row.get("sym") or ""), str(spec.get("family") or "")
        params = spec.get("params") or row.get("params") or {}
        q = float(((row.get("gates") or {}).get("expected_value") or {}).get("ev") or 0.0)
        fw = shadow.get(f"{sym}.{spec.get('selector')}") or {}
        if fw.get("exp_r") is not None:
            q = 0.5 * q + 0.5 * float(fw["exp_r"])
        if axis_cell is not None:
            ax = dict(axis_cell(sym, fam, params if isinstance(params, dict) else {},
                                timeframe=spec.get("timeframe"),
                                session=spec.get("selector") or spec.get("session")))
        else:
            ax = {"mechanism": _mechanism(fam), "asset_class": _asset_class(sym),
                  "session": str(spec.get("selector") or "?")}
        n_par = len(params) if isinstance(params, dict) else 0
        ax.update({"direction": str(spec.get("side") or spec.get("direction") or "?"),
                   "complexity": "simple" if n_par <= 3 else "moderate" if n_par <= 8
                   else "complex", "family": fam, "symbol": sym})
        arch.add(str(key), {k: ax.get(k, "?") for k in (*axes, "family", "symbol")}, q)
    cov = arch.coverage()
    empty = arch.marginal_empty([("mechanism", "asset_class"), ("mechanism", "session"),
                                 ("mechanism", "horizon"), ("information_source", "asset_class"),
                                 ("economic_actor", "session")], top=400)
    # empty (mechanism, asset class) niches -> registered families of that mechanism on symbols
    # of that class that are eligible for hypotheses
    vocab = _family_vocab()
    by_mech: dict[str, list[str]] = defaultdict(list)
    for f in vocab:
        by_mech[_mechanism(f)].append(f)
    syms = [p.name[: -len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet")] if \
        UNIVERSE.exists() else []
    by_cls: dict[str, list[str]] = defaultdict(list)
    for s in syms:
        if _may_hypothesise(s):
            by_cls[_asset_class(s)].append(s)
    try:
        import axis_registry
        cls3 = {f: axis_registry.classify_family(f) for f in vocab}
        actor = dict(getattr(axis_registry, "MECHANISM_ACTOR", {}))
    except Exception:
        cls3, actor = {}, {}
    all_syms = [s for v in by_cls.values() for s in v]
    rows = []
    for e in empty:
        # families that can occupy the niche: by mechanism, information source or actor
        fams = [f for f in vocab
                if ("mechanism" not in e or _mechanism(f) == e["mechanism"])
                and ("information_source" not in e or (cls3.get(f) or ("", "", ""))[1]
                     == e["information_source"])
                and ("economic_actor" not in e or actor.get((cls3.get(f) or ("",))[0])
                     == e["economic_actor"])]
        pool = by_cls.get(str(e["asset_class"]), []) if "asset_class" in e else all_syms
        extra = {"session": e["session"]} if e.get("session") not in (None, "all", "?") \
            else {}
        label = ", ".join(f"{k}={v}" for k, v in e.items())
        for f in fams[:2]:
            for s in pool[:3]:
                r: dict[str, Any] = {"kind": "hypothesis", "family": f, "symbols": [s],
                                     "text": f"tier_s MAP-Elites: niche ({label}) holds no "
                                             f"elite; {f} on {s} is the probe", "niche": e}
                if extra:
                    r["params"] = extra
                rows.append(r)
    emitted = _emit("qd_niches", rows)
    return {"coverage": cov, "empty_projections": empty[:40], "weak": arch.weak(10),
            "emitted": emitted,
            "metric": {"niche_share": cov.get("share"), "qd_score": cov.get("qd_score"),
                       "filled": cov.get("filled")}}


def _gate_by_symfam() -> dict[str, list[tuple[str, bool]]]:
    """SYMBOL.family -> [(at, passed)] in ledger order: the grain a genome proposes at."""
    out: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for r in _jsonl(GATE_LEDGER):
        sym, fam = str(r.get("sym") or ""), str(r.get("family") or "")
        if sym and fam:
            out[f"{sym}.{fam}"].append((str(r.get("at") or ""), bool(r.get("passed"))))
    return out


def _gauntlet_s_per_verdict() -> float:
    """Measured CPU seconds the desk spends per gate verdict (compile + sweep + gauntlet legs)."""
    cpu = 0.0
    for row in _jsonl(COMPUTE, 200_000):
        if str(row.get("run") or "") in ("compile_candidates", "sweep", "external_gauntlet",
                                          "search", "deepen"):
            s = row.get("cpu_s") or row.get("wall_s")
            if isinstance(s, (int, float)):
                cpu += float(s)
    n = sum(1 for _ in _jsonl(GATE_LEDGER))
    return cpu / n if cpu > 0 and n else 30.0


def organ_genomes() -> dict[str, Any]:
    """Researcher genomes: each emits EXACT recipes; fitness is what the gauntlet made of them.

    Every gene reaches the row: operator_set and feature_language pick the families, horizon
    the chart, data_policy the asset classes, source where the (symbol, family) pair comes
    from, novelty which pairs are preferred, complexity_cap how many parameters leave their
    defaults, exploration how many rows, falsify_order the gate the row asks to be judged on
    first. Fitness uses the gate ledger AFTER the emission only, with measured compute per
    verdict, duplicates (pairs the ledger had already judged) and false discoveries (pairs that
    passed and later failed) as penalties."""
    st = _state("genomes")
    gen = int(st.get("generation", 0))
    rng = np.random.default_rng(gen + 17)
    pop = [evolution.complete(g, rng) for g in st.get("population") or []]
    emitted: dict[str, list[list[str]]] = {k: [list(x) if isinstance(x, list) else [x, ""]
                                              for x in v]
                                          for k, v in (st.get("emitted") or {}).items()}
    by_sf = _gate_by_symfam()
    s_per = _gauntlet_s_per_verdict()
    fwd = shadow_rows()
    scored: list[tuple[dict[str, Any], float]] = []
    fit_rows = []
    for g in pop:
        gid = evolution.genome_id(g)
        judged = passed = dup = false_d = 0
        degr = 0.0
        for cell, at in emitted.get(gid, []):
            hist = by_sf.get(cell, [])
            before = [p for t, p in hist if at and t < at]
            after = [p for t, p in hist if not at or t >= at]
            if not after:
                continue
            judged += 1
            dup += int(bool(before))
            if any(after):
                passed += 1
                first = after.index(True)
                false_d += int(not all(after[first:]))
                sym = cell.split(".")[0]
                fw = [v for k, v in fwd.items() if k.startswith(f"{sym}.")]
                if fw and all(float(v.get("exp_r") or 0) <= 0 for v in fw if v.get("n")):
                    degr += 1.0 / len(fw)
        stats = {"validated_independent": passed - false_d, "compute_s": max(1.0, s_per * judged),
                 "complexity": float(g.get("complexity_cap", 4.0)),
                 "false_discoveries": float(false_d), "duplicates": float(dup) / max(1, judged),
                 "live_degradation": degr, "mining_pressure": float(judged) / 100.0}
        f = evolution.fitness(stats) if judged else 0.0
        scored.append((g, f))
        fit_rows.append({"genome": gid, "fitness": f, **stats, "judged": judged})
    nxt = evolution.step(scored, rng, size=12)
    vocab = _family_vocab()
    op_family = {"momentum": ["momentum_volgate", "trend_ma_cross", "asia_momentum",
                              "london_close_momentum"],
                 "reversion": ["mean_reversion_rsi", "mean_reversion_bollinger",
                               "range_reversion"],
                 "carry": ["overnight_drift", "overnight_gap_decay"],
                 "seasonal": ["dow_effect", "turn_of_month", "calendar_month", "monday_gap"],
                 "breakout": ["session_range_breakout", "level_breakout", "failed_breakout",
                              "volatility_squeeze"],
                 "vol_regime": ["volatility_squeeze", "momentum_volgate"],
                 "lead_lag": ["london_close_momentum"], "mixed": vocab}
    policy_classes = {"bars_only": None, "bars+macro": {"FX", "FOREX", "INDEX", "BOND"},
                      "bars+cot": {"METAL", "METALS", "ENERGY", "SOFT", "COMMODITY", "FX",
                                   "FOREX"},
                      "bars+events": {"FX", "FOREX", "INDEX", "INDICES"},
                      "cross_asset": None}
    try:
        import axis_registry
        info_of = {f: str(axis_registry.classify_family(f)[1]) for f in vocab}
    except Exception:
        info_of = {}
    try:
        from mt5desk.families import FAMILY_REGISTRY  # type: ignore[import-not-found]
    except Exception:
        FAMILY_REGISTRY = {}
    syms = sorted(p.name[: -len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet")) if \
        UNIVERSE.exists() else []
    syms = [s for s in syms if _may_hypothesise(s)]
    cls = {s: _asset_class(s) for s in syms}
    held = {(str((v.get("identity") or {}).get("symbol")), str((v.get("identity") or {})
                                                            .get("family")))
            for v in registry().values() if isinstance(v, dict)}
    judged_pairs = set(by_sf)
    surv_pairs = [(str(_spec(r).get("symbol")), str(_spec(r).get("family")))
                  for r in survivors().values() if isinstance(r, dict)]
    graph_pairs = [(str(r.get("symbol")), str(r.get("family"))) for r in _jsonl(HGRAPH, 60_000)
                   if r.get("fate") == "BORN" and r.get("symbol") and r.get("family")]
    rows = []
    for g in nxt:
        gid = evolution.genome_id(g)
        fams = [f for f in op_family.get(str(g.get("operator_set")), []) if f in vocab]
        lang = str(g.get("feature_language") or "any")
        if lang != "any" and info_of:
            fams = [f for f in fams if info_of.get(f) == lang] or fams
        allowed = policy_classes.get(str(g.get("data_policy")))
        pool = [s for s in syms if allowed is None or cls[s].upper() in allowed] or syms
        if not fams or not pool:
            continue
        k = max(1, round(float(g.get("exploration", 0.3)) * 10))
        src = str(g.get("source") or "own")
        if src == "hypothesis_graph":
            cand = [(s, f) for s, f in graph_pairs if s in pool and f in vocab]
        elif src == "survivor_neighbourhood":
            cand = [(s2, f) for s, f in surv_pairs for s2 in pool
                    if f in vocab and cls.get(s2) == cls.get(s) and s2 != s]
        elif src == "failure_gap":
            cand = [(s, f) for s in pool for f in fams if f"{s}.{f}" not in judged_pairs]
        else:
            cand = [(s, f) for s in pool for f in fams]
        if str(g.get("novelty")) == "species":
            cand = [c for c in cand if c not in held] or cand
        elif str(g.get("novelty")) == "exposure":
            occ = Counter(cls.get(s, "?") for s, _f in held)
            cand.sort(key=lambda c: occ.get(cls.get(c[0], "?"), 0))
        if not cand:
            continue
        idx = rng.choice(len(cand), size=min(k, len(cand)), replace=False)
        for i in idx:
            s, f = cand[int(i)]
            spec = FAMILY_REGISTRY.get(f) or {}
            params = dict(spec.get("defaults") or {})
            grid = [(pk, pv) for pk, pv in (spec.get("param_grid") or {}).items() if pv]
            for pk, pv in grid[: max(0, int(float(g.get("complexity_cap", 4.0)) // 2))]:
                params[pk] = pv[int(rng.integers(len(pv)))]
            # the chart is an identity key the gauntlet reads; H1 is spelled by its absence, and
            # the desk holds no H4/D1 bars, so those horizons lengthen the hold instead
            hz = str(g.get("horizon") or "H1")
            if hz == "M15":
                params["timeframe"] = "M15"
            elif hz in ("H4", "D1") and "ttl_bars" in params:
                params["ttl_bars"] = int(params["ttl_bars"]) * (4 if hz == "H4" else 24)
            row: dict[str, Any] = {
                "kind": "hypothesis", "family": f, "symbols": [s], "genome": gid,
                "falsify_first": g.get("falsify_order"),
                "text": f"tier_s researcher genome {gid} ({g.get('operator_set')}, "
                        f"{g.get('data_policy')}, {lang}, {src}, {g.get('horizon')}) proposes "
                        f"{f} on {s}"}
            if spec:
                row["params"] = params     # an EXACT recipe: the compiler builds it as written
            rows.append(row)
            emitted.setdefault(gid, []).append([f"{s}.{f}", NOW.isoformat()])
    out = _emit("genomes", rows)
    _save_state("genomes", {"generation": gen + 1, "population": nxt,
                            "emitted": {k: v[-400:] for k, v in emitted.items()},
                            "fitness": fit_rows})
    best = max((f for _g, f in scored), default=0.0)
    return {"generation": gen + 1, "population": len(nxt),
            "diversity": evolution.diversity(nxt), "best_fitness": best,
            "fitness_rows": sorted(fit_rows, key=lambda r: -r["fitness"])[:12],
            "cpu_s_per_verdict": s_per, "emitted": out,
            "metric": {"best_fitness": best, "diversity": evolution.diversity(nxt),
                       "judged_emissions": sum(r["judged"] for r in fit_rows)}}


def _expr_str(expr: Any) -> str:
    try:
        from libs.research.alpha_grammar import to_str
        return to_str(expr) if isinstance(expr, (list, tuple)) else str(expr or "")
    except Exception:
        return str(expr or "")


def _cell_of(sym: Any, family: Any, params: Any) -> str:
    try:
        from research.frontier_identity import cell_id
        return str(cell_id({"sym": sym, "family": family, "params": dict(params or {})}))
    except Exception:
        return ""


def _gate_passed() -> dict[str, bool]:
    """cell -> passed (latest verdict wins), from the gauntlet's own ledger."""
    out: dict[str, bool] = {}
    for r in _jsonl(GATE_LEDGER):
        c = str(r.get("cell") or "")
        if c:
            out[c] = bool(r.get("passed"))
    return out


def _formula_programs() -> tuple[list[tuple[str, bool]], list[str], int]:
    """Every formula the generators proposed, labelled by what the gauntlet made of it.

    alpha_evolution writes `discoveries` with the formula as a prefix list in `params.expr`
    (daily files plus gzipped jsonl rollups). A program counts toward operator yield only once
    the gauntlet has judged its exact cell; survivors also come from the canon rows that carry
    an expression. Returns (judged programs, surviving expressions, proposed count)."""
    import gzip
    root = DESK / "data" / "intelligence" / "alpha_evolution"
    judged = _gate_passed()
    rows: list[dict[str, Any]] = []
    if root.exists():
        for p in sorted(root.glob("*.json"))[-400:]:
            d = _read(p)
            if isinstance(d, dict):
                rows.extend(r for r in d.get("discoveries") or [] if isinstance(r, dict))
        for p in sorted(root.glob("*.jsonl.gz"))[-60:]:
            try:
                with gzip.open(p, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(r, dict):
                            rows.extend(x for x in (r.get("discoveries") or [r])
                                        if isinstance(x, dict))
            except (OSError, EOFError):
                continue
    progs: list[tuple[str, bool]] = []
    surv: list[str] = []
    seen: set[str] = set()
    for r in rows:
        params = r.get("params") or {}
        expr = params.get("expr") if isinstance(params, dict) else None
        if expr is None:
            continue
        e = _expr_str(expr)
        cell = _cell_of(r.get("symbol") or r.get("sym"), r.get("family") or "formula", params)
        if not e or cell in seen:
            continue
        seen.add(cell)
        if cell in judged:
            progs.append((e, judged[cell]))
            if judged[cell]:
                surv.append(e)
    for row in survivors().values():
        if not isinstance(row, dict):
            continue
        for src in (row.get("params"), (row.get("shadow_spec") or {}).get("params")):
            if isinstance(src, dict) and src.get("expr") is not None:
                surv.append(_expr_str(src["expr"]))
    ef = _read(REPORTS / "EXPRESSION_FACTORY.json") or {}
    for r in ef.get("survivors") or [] if isinstance(ef, dict) else []:
        if isinstance(r, dict):
            e = r.get("expr") or r.get("expression") or (r.get("params") or {}).get("expr")
            if e is not None:
                surv.append(_expr_str(e))
    return progs, surv, len(seen)


def organ_grammar() -> dict[str, Any]:
    """Operator yield and learned abstractions (layers 22 and 44) from judged formulas.

    The primitives are written to data/tier_s/grammar.json, which expression_factory reads as
    extra terminals: the learned vocabulary is used, not only reported."""
    progs, survivors_expr, proposed = _formula_programs()
    oy = evolution.operator_yield(progs) if progs else {"operators": {}, "retired": []}
    ab = evolution.abstractions(survivors_expr) if survivors_expr else {"primitives": [],
                                                                        "n_primitives": 0}
    _save_state("grammar", {"operator_weights": {k: v["weight"] for k, v in
                                                 (oy.get("operators") or {}).items()},
                            "retired": oy.get("retired") or [],
                            "primitives": ab.get("primitives"),
                            "generated_utc": NOW.isoformat()})
    return {"n_proposed": proposed, "n_programs": len(progs),
            "n_survivor_exprs": len(survivors_expr), "operator_yield": oy, "abstractions": ab,
            "metric": {"n_primitives": ab.get("n_primitives"),
                       "judged_programs": len(progs),
                       "retired_operators": len(oy.get("retired") or [])}}


_MECH_CACHE: dict[str, theory.Mechanism] = {}


def mechanism_for(fam: str) -> theory.Mechanism:
    """A family's causal mechanism, compiled from what the desk already declares about it.

    axis_registry.FAMILY_TABLE gives the mechanism class, information source and execution
    style; MECHANISM_ACTOR names who is forced or informed; alpha_schema.EVENTS gives payer,
    transmission and a falsifier for the event mechanisms; the family's own defaults give the
    condition and horizon. Every slot is filled from a declaration, and a slot with no source
    stays empty, so `complete_share` measures what the desk has actually written down."""
    if fam in _MECH_CACHE:
        return _MECH_CACHE[fam]
    mech, info, style = "UNKNOWN", "", ""
    actor = ""
    try:
        import axis_registry
        mech, info, style = (str(x) for x in axis_registry.classify_family(fam))
        actor = str(getattr(axis_registry, "MECHANISM_ACTOR", {}).get(mech) or "")
    except Exception:
        pass
    ev: Mapping[str, Any] = {}
    try:
        from libs.research import alpha_schema
        ev = alpha_schema.EVENTS.get(mech) or {}
    except Exception:
        ev = {}
    defaults: Mapping[str, Any] = {}
    try:
        from mt5desk.families import FAMILY_REGISTRY  # type: ignore[import-not-found]
        defaults = (FAMILY_REGISTRY.get(fam) or {}).get("defaults") or {}
    except Exception:
        defaults = {}
    cond = ", ".join(f"{k}={v}" for k, v in defaults.items()
                     if ("filter" in k or k in ("session", "range_start", "signal_at"))
                     and v not in (None, "all", "none", "off", False))
    hold = defaults.get("ttl_bars") or defaults.get("max_hold") or defaults.get("hold")
    raw: dict[str, Any] = {
        "cause": " -- ".join(x for x in (actor.replace("_", " "), str(ev.get("payer") or ""))
                             if x),
        "observable": f"{info} ({', '.join(k for k in defaults if k.endswith('_n'))})"
                      if info else "",
        "transmission": str(ev.get("mechanism") or (mech.replace("_", " ") if mech != "UNKNOWN"
                                                     else "")),
        "condition": cond or "any session the gauntlet admits (session axis expanded)",
        "trade": f"{style} execution, rr {defaults.get('rr')}" if style and defaults.get("rr")
                 else style,
        "horizon": f"{hold} bars" if hold else "",
        "falsifier": str(ev.get("falsifier") or (
            f"mean R after the desk's own costs <= 0 on the lockbox, or the effect is equal in "
            f"a session where no {actor.replace('_', ' ') or mech} is active" if mech != "UNKNOWN"
            else "")),
        "family": fam, "mechanism_class": mech}
    m = theory.compile_mechanism(raw, family=fam)
    _MECH_CACHE[fam] = m
    return m


def organ_theory() -> dict[str, Any]:
    """Theory graph (layer 17): evidence per mechanism from backtest, forward and live, and
    COMPOSITION -- a supported or contested theory is composed with a condition mechanism
    (session window, volatility state, trend state) and the composite is emitted as an exact
    recipe, so the graph proposes the next experiment instead of only scoring the last one."""
    g = theory.TheoryGraph()
    shadow = shadow_rows()
    n_back = 0
    by_fam_sym: dict[str, Counter[str]] = defaultdict(Counter)
    for r in _jsonl(GATE_LEDGER):
        fam = str(r.get("family") or "")
        if not fam:
            continue
        g.theory(mechanism_for(fam)).add(experiment=str(r.get("cell")),
                                         supports=bool(r.get("passed")), source="backtest",
                                         context=str(r.get("sym") or ""))
        if r.get("passed"):
            by_fam_sym[fam][str(r.get("sym") or "")] += 1
        n_back += 1
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fam = str(spec.get("family") or "")
        if not fam:
            continue
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        if fw.get("n") and int(fw["n"]) >= 5 and fw.get("exp_r") is not None:
            g.theory(mechanism_for(fam)).add(experiment=f"forward:{key}",
                                             supports=float(fw["exp_r"]) > 0, source="forward",
                                             context=str(spec.get("symbol")))
        by_fam_sym[fam][str(spec.get("symbol") or "")] += 1
    rep_doc = _read(REPORTS / "REPLICATION.json") or {}
    for r in (rep_doc.get("verdicts") or []) if isinstance(rep_doc, dict) else []:
        if isinstance(r, dict) and r.get("family"):
            g.theory(mechanism_for(str(r["family"]))).add(
                experiment=f"replication:{r.get('key')}", source="replication",
                supports=str(r.get("verdict") or "").upper() in ("REPLICATED", "AGREE"),
                context=str(r.get("symbol") or ""))
    live_by: dict[str, float] = defaultdict(float)
    for r in live_rows():
        live_by[r["_group"]] += float(r.get("pl_quote") or 0.0)
    done: set[tuple[str, str]] = set()
    for k, v in registry().items():
        fam = str(((v or {}).get("identity") or {}).get("family") or "")
        grp = names().group(k)
        if fam and grp in live_by and (fam, grp) not in done:
            done.add((fam, grp))
            g.theory(mechanism_for(fam)).add(experiment=f"live:{grp}", supports=live_by[grp] > 0,
                                             source="live", context=grp)
    rep = g.report(top=80)
    # composition: theory x condition -> exact recipes
    try:
        from mt5desk.families import FAMILY_REGISTRY  # type: ignore[import-not-found]
    except Exception:
        FAMILY_REGISTRY = {}
    conditions: list[tuple[str, dict[str, Any]]] = [
        (f"session={x}", {"session": x}) for x in ("asia", "london", "ny")]
    conditions += [("vol_filter=high", {"vol_filter": "high"}),
                   ("vol_filter=low", {"vol_filter": "low"}),
                   ("trend_filter=aligned", {"trend_filter": "aligned"})]
    rows: list[dict[str, Any]] = []
    composed = 0
    for t in rep["theories"]:
        if t["status"] not in ("SUPPORTED", "CONTESTED") or not t.get("family"):
            continue
        fam = str(t["family"])
        spec = FAMILY_REGISTRY.get(fam) or {}
        base = dict(spec.get("defaults") or {})
        if not spec:
            continue
        syms = [s for s, _n in by_fam_sym[fam].most_common(4) if s and _may_hypothesise(s)]
        for label, extra in conditions:
            if any(k != "session" and k not in base for k in extra):
                continue
            cm = theory.compile_mechanism({"condition": label, "falsifier":
                                           f"the effect is no larger under {label} than without"},
                                          family=fam)
            comp = theory.compose(mechanism_for(fam), condition=cm)
            composed += 1
            for sym in syms:
                rows.append({"kind": "hypothesis", "family": fam, "symbols": [sym],
                             "params": {**base, **extra}, "theory": t["id"],
                             "composed": comp.mid, "falsifier": comp.falsifier,
                             "text": f"tier_s theory composition: {fam} ({t['status']}, "
                                     f"confidence {t['confidence']}) under {label} on {sym}"})
    emitted = _emit("theory_compositions", rows)
    return {**rep, "backtest_rows": n_back, "composed": composed, "emitted": emitted,
            "metric": {"n_theories": rep["n_theories"], "complete_share":
                       rep["complete_share"], "refuted": rep["by_status"].get("REFUTED", 0),
                       "supported": rep["by_status"].get("SUPPORTED", 0),
                       "composed": composed}}


def organ_review(topo: Mapping[str, Any] | None, fdr_rows: Mapping[str, Any] | None,
                 rq: Mapping[str, Any] | None) -> dict[str, Any]:
    shadow = shadow_rows()
    uniq = ((topo or {}).get("rank") or {}).get("uniqueness") or {}
    over = {r["test_id"]: r for r in (fdr_rows or {}).get("certified") or []}
    rep_doc = _read(REPORTS / "REPLICATION.json") or {}
    # REPLICATION.json (replication_civilization) keeps its rows under "verdicts", keyed "key"
    rep_rows = (rep_doc.get("verdicts") or rep_doc.get("rows") or []) if isinstance(rep_doc,
                                                                                 dict) else []
    rep_by = {}
    for r in rep_rows if isinstance(rep_rows, list) else []:
        if isinstance(r, dict):
            k = str(r.get("cell") or r.get("key") or "")
            v = r.get("verdict") or r.get("status")
            if k:
                rep_by[k] = "AGREE" if str(v).upper() in ("AGREE", "REPLICATED", "PASS",
                                                           "MATCH") else str(v)
    fills: Counter[str] = Counter(r["_group"] for r in live_rows())
    worlds_by = {str(r.get("key")): r for r in (_read(STATE / "worlds_by_certificate.json")
                                                or {}).get("rows") or []}
    cands: dict[str, dict[str, Any]] = {}
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sym, sel, fam = spec.get("symbol"), spec.get("selector"), spec.get("family")
        fw = shadow.get(f"{sym}.{sel}") or {}
        sleeve_keys = [k for k in uniq if str(k).startswith(f"{sym}.{fam}")]
        ev: dict[str, Any] = {"gates": row.get("gates") or {}, "days": row.get("days"),
                              "forward": {"n": fw.get("n"), "mean_r": fw.get("exp_r")},
                              "execution": {"matched_fills": fills.get(f"{sym}.{sel}", 0)},
                              "mechanism": {"falsifier": mechanism_for(str(fam or "")).falsifier}}
        if sleeve_keys:
            ev["topology"] = {"uniqueness": uniq[sleeve_keys[0]]}
        if str(key) in over:
            ev["online_fdr"] = {"over_budget": bool(over[str(key)]["over_budget"])}
        cell = str(row.get("cell") or key)
        if cell in rep_by:
            ev["replication"] = {"verdict": rep_by[cell]}
        # the real-gauntlet attack is program-level: a trap kind the certifier admitted this
        # generation means every certificate that gauntlet issued is open to that attack, and
        # the panel records it against each until the leak closes
        leaks = (((rq or {}).get("real_gauntlet") or {}).get("leaks") or [])
        n_fw = int(fw.get("n") or 0)
        if n_fw and fw.get("forward_t") not in (None, 0) and fw.get("exp_r") is not None:
            mu_f = float(fw["exp_r"])
            se_f = abs(mu_f / float(fw["forward_t"]))
            q = epistemic.Quantity(f"forward_edge:{key}", mu_f, mu_f - 1.96 * se_f,
                                   mu_f + 1.96 * se_f, n=n_fw, source="shadow")
        else:
            q = epistemic.Quantity(f"forward_edge:{key}", None, n=n_fw, source="shadow")
        ev["epistemic"] = {"decision": str(epistemic.decide(q, 0.0)),
                           "label": str(epistemic.classify(q, 0.0)), "n": n_fw}
        wf = worlds_by.get(str(key))
        if wf is not None:
            ev["stress"] = {"worlds_measured": wf.get("worlds_measured"),
                            "flags": wf.get("flags") or [], "exp_x5": wf.get("exp_x5")}
        ev["red_queen"] = None if rq is None else {
            "attacks": len((rq.get("real_gauntlet") or {}).get("rows") or []) or
            rq.get("generation"), "killed": bool(leaks),
            "killed_by": ", ".join(sorted({str(x["kind"]) for x in leaks})) or None}
        cands[str(key)] = ev
    rep = review_panel.panel_report(cands)
    rows = rep.pop("rows")
    _write(OUT_DIR / "REVIEW_PANEL_ROWS.json", {"generated_utc": NOW.isoformat(), "rows": rows})
    return {**rep, "metric": {"resolved_share": rep["resolved_share"],
                              "challenged": rep["verdicts"].get("CHALLENGED", 0),
                              "failed": rep["verdicts"].get("FAILED", 0)}}


#: epistemology of a producer, read off the tokens of its hypothesis-graph `source`. Cohorts are
#: epistemologies: two cohorts that reach one mechanism by different routes are independent.
EPISTEMOLOGY = (("fund_playbook", "institutional_playbook"), ("deep_forest", "practitioner_story"),
                ("youtube", "practitioner_story"), ("forexfactory", "practitioner_story"),
                ("video", "practitioner_story"), ("chatgpt", "llm_reasoning"),
                ("kimi", "llm_reasoning"), ("deepseek", "llm_reasoning"),
                ("world_lab", "structural_model"), ("cross_science", "structural_model"),
                ("macro_state", "structural_model"), ("factor_residual", "structural_model"),
                ("alpha_evolution", "evolutionary_search"), ("genomes", "evolutionary_search"),
                ("moat_factory", "evolutionary_search"), ("standing_questions",
                                                          "first_principles"),
                ("anomalies", "anomaly_detection"), ("search_paradigm", "anomaly_detection"),
                ("cot", "flow_positioning"), ("broker_swaps", "flow_positioning"),
                ("plumbing", "flow_positioning"), ("calendar", "event_study"),
                ("event_response", "event_study"), ("qd_niches", "quality_diversity"),
                ("orthogonal", "quality_diversity"), ("axis_registry", "quality_diversity"),
                ("external", "external_literature"), ("discovery_compiler",
                                                      "empirical_mining"))


def _producer(source: Any) -> str:
    parts = [p for p in str(source or "").split(":") if p]
    if not parts:
        return "unattributed"
    return ":".join(parts[:2]) if parts[0] in ("miner", "tier_s", "fund_playbook") else parts[0]


def _epistemology(producer: str) -> str:
    low = producer.lower()
    return next((e for tok, e in EPISTEMOLOGY if tok in low), "empirical_mining")


def _leg_of(producer: str, legs: Iterable[str]) -> str | None:
    toks = [t for t in producer.replace("-", "_").split(":") if t not in ("miner", "tier_s")]
    legs = set(legs)
    for t in reversed(toks):
        if t in legs:
            return t
        hit = sorted(lg for lg in legs if t and (t in lg or lg in t))
        if hit:
            return hit[0]
    return "tier_s" if producer.startswith("tier_s") and "tier_s" in legs else None


def _producer_of_cell() -> dict[str, str]:
    """gate-ledger cell -> the producer that bore it (through graph_id -> hypothesis graph)."""
    node: dict[str, str] = {}
    for r in _jsonl(HGRAPH, 400_000):
        if r.get("id"):
            node[str(r["id"])] = _producer(r.get("source"))
    out: dict[str, str] = {}
    for r in _jsonl(GATE_LEDGER):
        c = str(r.get("cell") or "")
        if c:
            out[c] = node.get(str(r.get("graph_id") or "")) or _producer(r.get("source"))
    return out


def organ_market() -> dict[str, Any]:
    """Researchers = the PRODUCERS that bore the hypotheses the gauntlet judged.

    A gate verdict's `graph_id` names the hypothesis-graph node, whose `source` names the
    producer that bore it; that is the researcher. Its record: candidates born (hypothesis
    graph), P(novel) (births on a (symbol, family) pair nobody had judged or certified), P(pass
    full) (gate verdicts), P(forward holds) (its certificates' forward clocks), historical false
    discovery rate (cells that passed and later failed), honesty (prediction accounting) and
    measured CPU (the compute ledger, through the leg that runs the producer; producers with no
    leg of their own split the unattributed pool by their share of births). The prices are
    written per researcher AND per leg: cycle_pricing reads the leg prices as a price source,
    so this market steers compute. It never touches capital."""
    rs: dict[str, researcher_market.Researcher] = {}

    def R(name: str) -> researcher_market.Researcher:
        if name not in rs:
            ep = _epistemology(name)
            rs[name] = researcher_market.Researcher(name=name, cohort=ep, epistemology=ep)
        return rs[name]

    births: Counter[str] = Counter()
    novel: Counter[str] = Counter()
    producer_of_node: dict[str, str] = {}
    first_seen: dict[str, datetime] = {}
    judged_pairs = set(_gate_by_symfam())
    held = {f"{_spec(r).get('symbol')}.{_spec(r).get('family')}" for r in survivors().values()
            if isinstance(r, dict)}
    for r in _jsonl(HGRAPH, 400_000):
        pr = _producer(r.get("source"))
        nid = str(r.get("id") or "")
        if nid:
            producer_of_node[nid] = pr
        births[pr] += 1
        pair = f"{r.get('symbol')}.{r.get('family')}"
        novel[pr] += int(pair not in judged_pairs and pair not in held)
        t = replay.parse_t(r.get("at"))
        if t:
            first_seen[pr] = min(first_seen.get(pr, t), t)
    for pr, n in births.items():
        rr = R(pr)
        rr.candidates = n
        rr.trials["novel"], rr.successes["novel"] = n, novel[pr]
    producer_of_cell: dict[str, str] = {}
    hist_by_cell: dict[str, list[bool]] = defaultdict(list)
    for row in _jsonl(GATE_LEDGER):
        pr = producer_of_node.get(str(row.get("graph_id") or "")) or _producer(
            row.get("source") or row.get("hunt"))
        cell = str(row.get("cell") or "")
        producer_of_cell[cell] = pr
        hist_by_cell[cell].append(bool(row.get("passed")))
        rr = R(pr)
        rr.trials["cheap"] = rr.trials.get("cheap", 0) + 1
        rr.trials["full"] = rr.trials.get("full", 0) + 1
        if row.get("passed"):
            rr.successes["full"] = rr.successes.get("full", 0) + 1
        if row.get("passed") or str(row.get("terminal_gate") or "") not in ("", "cost",
                                                                             "costs", "spread"):
            rr.successes["cheap"] = rr.successes.get("cheap", 0) + 1
    fdr: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for cell, h in hist_by_cell.items():
        if True in h:
            k = h.index(True)
            fdr[producer_of_cell[cell]][0] += 1
            fdr[producer_of_cell[cell]][1] += int(not all(h[k:]))
    shadow = shadow_rows()
    for _key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        pr = producer_of_cell.get(str(row.get("cell") or "")) or _producer(row.get("hunt"))
        spec = _spec(row)
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        if fw.get("n") and int(fw["n"]) >= 5:
            rr = R(pr)
            rr.trials["forward"] = rr.trials.get("forward", 0) + 1
            rr.successes["forward"] = rr.successes.get("forward", 0) + int(
                float(fw.get("exp_r") or 0) > 0)
    cpu: Counter[str] = Counter()
    for row in _jsonl(COMPUTE, 200_000):
        name = str(row.get("run") or "")
        sec = row.get("cpu_s") or row.get("wall_s") or row.get("seconds")
        if name and isinstance(sec, (int, float)):
            cpu[name] += float(sec)
    leg_of = {name: _leg_of(name, cpu) for name in rs}
    claimed = {lg for lg in leg_of.values() if lg}
    pool = sum(v for k, v in cpu.items() if k not in claimed and k in (
        "mine", "deepen", "compile_candidates", "search", "sweep", "world_crawler",
        "deep_forest", "market_intel"))
    unlegged = sum(rs[n].candidates for n, lg in leg_of.items() if not lg) or 1
    hon = _state("honesty").get("factories") or {}
    for name, rr in rs.items():
        lg = leg_of[name]
        share = [x for x, y in leg_of.items() if y == lg] if lg else []
        rr.cost["cpu_s"] = (cpu[lg] / max(1, len(share))) if lg else pool * rr.candidates / \
            unlegged
        rr.cost["cpu_s"] = rr.cost["cpu_s"] or 60.0
        rr.hours = max(1.0, (NOW - first_seen[name]).total_seconds() / 3600.0) \
            if name in first_seen else 24.0
        h = hon.get(name)
        if isinstance(h, dict) and h.get("honesty") is not None:
            rr.honesty = float(h["honesty"])
        p, f = fdr.get(name, [0, 0])
        rr.mean_novelty = max(0.05, 1.0 - (f / p if p else 0.0))
    res = researcher_market.allocate(list(rs.values()), headroom_s=1800.0, seed=NOW.hour)
    # independent discovery: a mechanism x asset-class species that PASSED for >= 2 cohorts
    sight = []
    for row in _jsonl(GATE_LEDGER):
        if row.get("passed"):
            pr = producer_of_cell.get(str(row.get("cell") or ""), "unattributed")
            sp = f"{_mechanism(str(row.get('family') or ''))}|{_asset_class(str(row.get('sym')))}"
            sight.append((pr, sp))
    ind = researcher_market.independent_discoveries(sight, {n: r.cohort for n, r in rs.items()})
    # THE FRONTIER PRICES THE GROUND (layer 36): a producer whose ground the species estimator
    # says still hides many unseen mechanisms is worth more compute than its record alone says.
    # Last hour's FRONTIER report (the organ runs after this one); absent -> factor 1.
    fr = (_read(OUT_DIR / "FRONTIER.json") or {}).get("grounds") or {}
    unseen = {str(g): float(v.get("unseen") or 0.0) for g, v in fr.items() if isinstance(v, dict)}
    tot_unseen = sum(unseen.values())
    leg_prices: dict[str, float] = {}
    for name, a in res["allocations"].items():
        lg = leg_of.get(name)
        f = 1.0 + (unseen.get(name, 0.0) / tot_unseen if tot_unseen > 0 else 0.0)
        a["frontier_factor"] = round(f, 4)
        if lg:
            leg_prices[lg] = max(leg_prices.get(lg, 0.0), float(a["price"]) * f)
    table = {n: {"epistemology": r.epistemology, "leg": leg_of.get(n), "births": r.candidates,
                 "p_novel": round(r.mean("novel"), 4), "p_pass_full": round(r.mean("full"), 4),
                 "p_forward": round(r.mean("forward"), 4),
                 "historical_fdr": round(fdr[n][1] / fdr[n][0], 4) if fdr.get(n, [0])[0]
                 else None, "cpu_s": round(r.cost.get("cpu_s", 0.0), 1),
                 "validated_per_cpu_h": round(3600.0 * r.successes.get("full", 0)
                                              / max(1.0, r.cost.get("cpu_s", 1.0)), 6),
                 "honesty": r.honesty} for n, r in rs.items()}
    _write(STATE / "researcher_prices.json", {
        "generated_utc": NOW.isoformat(),
        "prices": {k: v["price"] for k, v in res["allocations"].items()},
        "budgets": {k: v["budget_s"] for k, v in res["allocations"].items()},
        "leg_prices": leg_prices, "researchers": table,
        "consumer": "research/cycle_pricing.py (compute only; never capital)"})
    return {**{k: v for k, v in res.items() if k != "allocations"},
            "researchers": dict(sorted(table.items(), key=lambda kv: -kv[1]["births"])[:40]),
            "independent_discoveries": ind, "priced_legs": len(leg_prices),
            "metric": {"n_researchers": len(rs), "independently_discovered":
                       ind["independently_discovered"], "priced_legs": len(leg_prices)}}


def organ_frontier(topo_hist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sightings = []
    for r in _jsonl(HGRAPH, 200_000):
        ground = _producer(r.get("source"))
        species = f"{_mechanism(str(r.get('family') or ''))}|{r.get('family')}"
        sightings.append((ground, species))
    comp: dict[str, float] = defaultdict(float)
    for row in _jsonl(COMPUTE, 200_000):
        t = str(row.get("at") or "")[:13]
        s = row.get("cpu_s") or row.get("wall_s") or row.get("seconds")
        if t and isinstance(s, (int, float)):
            comp[t] += float(s)
    surv_by: dict[str, float] = defaultdict(float)
    for row in survivors().values():
        if isinstance(row, dict):
            surv_by[str(row.get("gated_at") or "")[:13]] += 1.0
    hours = sorted(set(comp) | set(surv_by))
    ranks = [float(h["combined"]) for h in (topo_hist or []) if h.get("combined") is not None]
    est = frontier.estimate(sightings, compute_series=[comp.get(h, 0.0) for h in hours],
                            survivor_series=[surv_by.get(h, 0.0) for h in hours],
                            rank_history=ranks)
    return {**est, "metric": {"unseen": est["overall"].get("unseen"),
                              "coverage": est["overall"].get("coverage"),
                              "new_per_100": est["overall"].get("new_per_100_recent"),
                              "yield_b": (est.get("yield") or {}).get("b")}}


def organ_failure_memory() -> dict[str, Any]:
    rows = []
    for r in _jsonl(GATE_LEDGER):
        sym = str(r.get("sym") or "")
        cell = str(r.get("cell") or "")
        parts = cell.split(".")
        rows.append({"family": r.get("family"), "mechanism": _mechanism(str(r.get("family"))),
                     "asset_class": _asset_class(sym) if sym else "?",
                     "selector": parts[2] if len(parts) > 2 else "?",
                     "passed": r.get("passed"), "terminal_gate": r.get("terminal_gate"),
                     "cell": cell})
    # FAILURES AFTER THE GAUNTLET (layer 13): a forward clock whose own record turned against
    # it, and a live window whose fills lost, are failures of the same kind the gates record --
    # usually the more expensive kind -- so they enter the memory beside the gate verdicts
    nm = names()
    n_fwd = n_live = 0
    for k, fw in shadow_rows().items():
        n = int(fw.get("n") or 0)
        if n < 20 or fw.get("exp_r") is None or float(fw["exp_r"]) > 0:
            continue
        t = nm.triple(k)
        if not t:
            continue
        rows.append({"family": t[1], "mechanism": _mechanism(t[1]),
                     "asset_class": _asset_class(t[0]), "selector": t[2], "passed": False,
                     "terminal_gate": "forward", "cell": f"forward:{k}"})
        n_fwd += 1
    live_r: dict[str, list[float]] = defaultdict(list)
    for r in live_rows():
        if r.get("r_multiple") is not None:
            live_r[r["_key"]].append(float(r["r_multiple"]))
    for k, rs in live_r.items():
        if len(rs) >= 10 and sum(rs) < 0:
            t = nm.triple(k)
            if t:
                rows.append({"family": t[1], "mechanism": _mechanism(t[1]),
                             "asset_class": _asset_class(t[0]), "selector": t[2],
                             "passed": False, "terminal_gate": "live", "cell": f"live:{k}"})
                n_live += 1
    mem = failure_memory.compress(rows)
    _write(STATE / "failure_memory.json", {"generated_utc": NOW.isoformat(),
                                            "theorems": mem["theorems"], "rules": mem["rules"]})
    return {**{k: v for k, v in mem.items() if k not in ("theorems", "rules")},
            "theorems": mem["theorems"][:40], "rules": mem["rules"][:20],
            "forward_failures": n_fwd, "live_failures": n_live,
            "metric": {"theorems": len(mem["theorems"]),
                       "rows_per_statement": mem["compression"]["rows_per_statement"],
                       "coverage_share": mem["compression"]["coverage_share"]}}


def organ_formal() -> dict[str, Any]:
    abl = formal.ablations()
    existing: dict[str, Any] = {}
    try:
        import formal_invariants as fi  # type: ignore[import-not-found]
        existing = fi.build()
        _write(REPORTS / "FORMAL_INVARIANTS.json", existing)
    except Exception as exc:
        existing = {"error": f"{type(exc).__name__}: {exc}"}
    conformance = _protocol_conformance()
    return {"protocol": {"desk_all_proven": abl["desk_all_proven"],
                         "states": abl["runs"]["desk"]["states"],
                         "invariants": abl["runs"]["desk"]["invariants"],
                         "depends_on": abl["depends_on"]},
            "desk_all_proven": abl["desk_all_proven"],
            "conformance": conformance, "structural_invariants": existing,
            "metric": {"protocol_proven": 1.0 if abl["desk_all_proven"] else 0.0,
                       "knobs_evidenced": conformance.get("evidenced_share")}}


#: protocol knob -> source patterns in the gateway that evidence the real code implements it.
#: Static evidence, not proof; a knob with no evidence is an OBLIGATION the report names.
KNOB_EVIDENCE: dict[str, tuple[str, ...]] = {
    "persist_before_send": ("order_intents", "intent_id", "_journal"),
    "reconcile_on_restart": ("positions_get", "orders_get", "reconcile"),
    "idempotent_client_id": ("magic", "comment", "client_id", "intent_id"),
    "recheck_alloc_at_send": ("allocator gave this sleeve no heat", "book_zeroed", "zeroed"),
    "check_cert_at_send": ("load_sleeves", "live_policy", "admit"),
    "clamp_data_to_clock": ("closed bar", "bar_closed", "iloc[-2]", "last closed"),
}


def _protocol_conformance() -> dict[str, Any]:
    src = ""
    for p in (DESK / "mt5desk" / "gateway.py", DESK / "mt5desk" / "decision_core.py"):
        with contextlib.suppress(OSError):
            src += p.read_text("utf-8", errors="replace")
    if not src:
        return {"status": "UNMEASURED"}
    rows = {k: [pat for pat in pats if pat in src] for k, pats in KNOB_EVIDENCE.items()}
    ev = sum(1 for v in rows.values() if v)
    return {"evidence": rows, "evidenced": ev, "of": len(rows),
            "evidenced_share": ev / len(rows),
            "obligations": [k for k, v in rows.items() if not v]}


def organ_chaos() -> dict[str, Any]:
    camp = chaos.campaign(runs=1500, depth=60, seed=NOW.hour)
    drills = []
    try:
        from mt5desk import decision_core as dc  # type: ignore[import-not-found]
        drills.append(chaos.drill("sleeves.json -> load_sleeves_verbose",
                                  DESK / "data" / "sleeves.json",
                                  lambda p: dc.load_sleeves_verbose(p)[0],
                                  lambda out: out == []))
    except Exception as exc:
        drills.append({"drill": "load_sleeves_verbose", "status": "UNMEASURED",
                       "why": f"{type(exc).__name__}: {exc}"})
    jp = STATE / "truth_journal.jsonl"
    drills.append(chaos.drill("truth journal -> verify", jp,
                              lambda p: truth_kernel.Journal(p).verify(),
                              lambda out: not bool(out.get("ok")) or int(out.get("n", 0)) == 0,
                              corruptions=("truncate", "garbage")))
    failing = [d for d in drills if d.get("status") == "FAIL"]
    return {"campaign": camp, "drills": drills,
            "metric": {"breaches": sum(camp["breaches"].values()),
                       "drills_failing": len(failing)}}


def organ_replay() -> dict[str, Any]:
    streams = [
        replay.Stream("fills", _jsonl(LIVE_LEDGER), "time",
                      key=lambda r: str(r.get("sleeve")), reducer=replay.position_reducer),
        replay.Stream("orders", _jsonl(ORDER_INTENTS), "time",
                      key=lambda r: str(r.get("sleeve")), reducer=replay.count_reducer),
        replay.Stream("decisions", _jsonl(DECISIONS), "decided_at",
                      key=lambda r: str(r.get("strategy_id"))),
        replay.Stream("certificates", [dict(v, _key=k) for k, v in survivors().items()
                                       if isinstance(v, dict)], "gated_at",
                      key=lambda r: str(r.get("_key"))),
        replay.Stream("sleeves", [dict(v, _key=k) for k, v in registry().items()
                                  if isinstance(v, dict)], ("frozen_at", "forward_start"),
                      key=lambda r: str(r.get("_key"))),
        replay.Stream("legs", _jsonl(EVENTS), "at", key=lambda r: str(r.get("leg"))),
        replay.Stream("allocations", _jsonl(FORECAST_LOG), "t", key=lambda r: "book"),
        replay.Stream("verdicts", _jsonl(GATE_LEDGER), "at", key=lambda r: str(r.get("cell"))),
        replay.Stream("hypotheses", _jsonl(HGRAPH, 400_000), "at",
                      key=lambda r: str(r.get("id"))),
        replay.Stream("compute", _jsonl(COMPUTE, 200_000), "at",
                      key=lambda r: str(r.get("run"))),
        replay.Stream("exchange", _jsonl(STATE / "exchange_book_log.jsonl", 50_000), "t",
                      key=lambda r: "book"),
    ]
    live = {"certificates": {str(k) for k in survivors()},
            "sleeves": {str(k) for k in registry()}}
    cons = replay.consistency(streams, live, NOW)
    sample_t = NOW - timedelta(days=7)
    past = replay.replay(streams, sample_t)
    return {**cons, "sample_past": {"at": past["at"],
                                    "sizes": {k: len(v) for k, v in past["state"].items()}},
            "metric": {"reconstructible_share": cons["reconstructible_share"]}}


def organ_data_os() -> dict[str, Any]:
    audits = {}
    for name, p in (("deep_forest_claims", DESK / "data" / "deep_forest_claims.jsonl"),
                    ("news_captures", DESK / "data" / "news_captures.jsonl"),
                    ("hypothesis_graph", HGRAPH)):
        audits[name] = bitemporal.pit_audit(_jsonl(p, 50_000))
    intel_rows: list[dict[str, Any]] = []
    for p in sorted((DESK / "data" / "intelligence").rglob("*.json"))[-400:]:
        d = _read(p)
        rows = d.get("rows") if isinstance(d, dict) else d
        if isinstance(rows, list):
            intel_rows.extend(r for r in rows[:200] if isinstance(r, dict))
    audits["intelligence"] = bitemporal.pit_audit(intel_rows)
    # the acquisition ledger: predictions from the four rankers, resolved on arrival
    st = _state("acquisition")
    preds = [bitemporal.Prediction(**p) for p in st.get("predictions") or []]
    known = {p.item for p in preds}
    metric_now = {"pit_share": float(audits["intelligence"].get("pit_share") or 0.0)}
    for ranker, fname in (("data_acquisition_scientist", "DATA_ACQUISITION.json"),
                          ("evig_acquisition", "EVIG_ACQUISITION.json"),
                          ("source_evig", "SOURCE_EVIG.json"),
                          ("value_of_data", "VALUE_OF_DATA.json")):
        d = _read(REPORTS / fname)
        rows = []
        if isinstance(d, dict):
            for k in ("ranking", "rows", "targets", "candidates", "top"):
                if isinstance(d.get(k), list):
                    rows = d[k]
                    break
        for r in rows[:20]:
            if not isinstance(r, dict):
                continue
            item = str(r.get("item") or r.get("dataset") or r.get("source") or r.get("name")
                       or r.get("id") or "")
            if not item or item in known:
                continue
            gain = r.get("evig") or r.get("value") or r.get("expected_gain") or r.get("score")
            try:
                g = float(gain)
            except (TypeError, ValueError):
                continue
            preds.append(bitemporal.Prediction(item=item, kind=str(r.get("kind") or "dataset"),
                                               ranker=ranker, predicted_gain=g,
                                               cost_eur=float(r.get("cost_eur") or 0.0),
                                               cost_cpu_h=float(r.get("cost_cpu_h") or 0.1),
                                               metric="pit_share",
                                               metric_before=metric_now["pit_share"],
                                               at=NOW.isoformat()))
            known.add(item)
    acquired: dict[str, datetime] = {}
    acq_dir = DESK / "data" / "acquired"
    if acq_dir.exists():
        for p in acq_dir.iterdir():
            acquired[p.stem] = datetime.fromtimestamp(p.stat().st_mtime, UTC)
    n_res = bitemporal.resolve(preds, acquired, metric_now, NOW.isoformat())
    cal = bitemporal.calibration(preds)
    ranking = bitemporal.rank(preds, cal)
    _save_state("acquisition", {"predictions": [p.to_dict() for p in preds][-3000:]})
    return {"pit_audits": audits, "acquisition": {"open": len(ranking),
                                                  "resolved_now": n_res,
                                                  "calibration": cal, "top": ranking[:25]},
            "metric": {"pit_share": audits["intelligence"].get("pit_share"),
                       "calibrated_rankers": len(cal)}}


def organ_world_and_science() -> dict[str, Any]:
    rets, closes, vols = _returns_panel()
    if len(rets) < 3:
        return {"status": "UNMEASURED", "why": f"{len(rets)} eligible H1 series on this host",
                "metric": {"stable_edges": None, "hypotheses": 0}}
    edges = world_edges.classify_all(rets, lags=(1,), max_pairs=300)
    resid = world_edges.residuals(rets, edges)
    labs = cross_science.run_all(rets, closes, vols)
    # map to registered families the compiler can build (the lab stays on the row)
    fam_map = {"control": {"lost": "trend_ma_cross", "over": "mean_reversion_bollinger"},
               "signal": "range_reversion", "queueing": "volatility_squeeze",
               "ecology": "momentum_volgate", "dynamical": "range_reversion",
               "information": "london_close_momentum", "network": "london_close_momentum",
               "bayesian": {"persistence": "trend_ma_cross", "reversion": "mean_reversion_rsi"}}
    rows: list[dict[str, Any]] = []
    for lab, hits in labs.items():
        for h in hits:
            m = fam_map.get(lab)
            if isinstance(m, dict):
                claim = str(h.get("claim"))
                fam = next((v for k, v in m.items() if k in claim), next(iter(m.values())))
            else:
                fam = str(m)
            rows.append({**h, "family": fam, "lab_family": h.get("family"),
                         "text": h.get("claim")})
    for r in resid:
        rows.append({**r, "family": "range_reversion", "text": r.get("claim")})
    emitted = _emit("cross_science", rows)
    census = world_edges.census(edges)
    return {"edges": census, "broken_relationships": resid[:20],
            "labs": {k: len(v) for k, v in labs.items()}, "emitted": emitted,
            "sample": {k: v[:3] for k, v in labs.items()},
            "metric": {"stable_edges": census.get("STABLE", 0), "hypotheses": len(rows)}}


def organ_worlds() -> dict[str, Any]:
    """Layer 16, joined per certificate: which stress worlds each certificate has been through
    (synthetic_regimes' sixteen worlds, the digital twin's replays) and which it has NOT. A
    certificate no world has touched is named -- an untested edge is not a robust one -- and the
    flags it earned are carried to the review panel as the evidence of a named failure mode."""
    sr = _read(REPORTS / "SYNTHETIC_REGIMES.json") or {}
    results = sr.get("results") or [] if isinstance(sr, dict) else []
    worlds = [w.get("name") for w in sr.get("scenarios") or []] if isinstance(sr, dict) else []
    by_sf: dict[str, dict[str, Any]] = {}
    for r in results:
        if isinstance(r, dict):
            by_sf[f"{r.get('symbol')}.{r.get('family')}"] = r
    twin_doc = _read(REPORTS / "DIGITAL_TWIN.json") or {}
    twin_keys = {str(k) for k in (twin_doc.get("sleeves") or twin_doc.get("results") or {})} \
        if isinstance(twin_doc, dict) else set()
    rows, untested = [], []
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sf = f"{spec.get('symbol')}.{spec.get('family')}"
        hit = by_sf.get(sf)
        measured = [k for k, v in ((hit or {}).get("scenarios") or {}).items()
                    if isinstance(v, dict) and v.get("status") == "MEASURED"]
        rec = {"key": str(key), "worlds_measured": len(measured), "of": len(worlds),
               "flags": (hit or {}).get("flags") or [], "verdict": (hit or {}).get("verdict"),
               "twin": str(key) in twin_keys,
               "exp_x5": (((hit or {}).get("scenarios") or {}).get("spread_x5") or {})
               .get("expectancy")}
        rows.append(rec)
        if not measured:
            untested.append(str(key))
    _write(STATE / "worlds_by_certificate.json", {"generated_utc": NOW.isoformat(),
                                                   "rows": rows})
    n = len(rows)
    flagged = sum(1 for r in rows if r["flags"])
    return {"worlds": worlds, "n_certificates": n, "untested": untested[:60],
            "flagged": flagged,
            "metric": {"stress_tested_share": (n - len(untested)) / n if n else None,
                       "flagged_share": flagged / n if n else None,
                       "worlds": len(worlds)}}


def _posterior_bids() -> tuple[list[opportunity_exchange.Bid], dict[str, float]]:
    shadow = shadow_rows()
    hon = _state("honesty").get("factories") or {}
    live_book: dict[str, float] = {}
    alloc = _first(PF_ALLOCATION)
    if isinstance(alloc, dict) and isinstance(alloc.get("book"), dict):
        live_book = {str(k): float(v) for k, v in alloc["book"].items()}
    if not live_book:
        last = _jsonl(FORECAST_LOG, 5_000)
        if last and isinstance(last[-1].get("book"), dict):
            live_book = {str(k): float(v) for k, v in last[-1]["book"].items()}
    # the allocator's book is spelled per book name; a certificate is spelled per survivor key.
    # Both resolve to SYMBOL.window, and a window's heat is shared by the certificates in it
    nm = names()
    by_group: dict[str, float] = defaultdict(float)
    for k, v in live_book.items():
        by_group[nm.group(k)] += v
    per_group = Counter(nm.group(k) for k, r in survivors().items() if isinstance(r, dict))
    # measured execution drag per (symbol, family), like-for-like variant (execution_science)
    drag_of: dict[tuple[str, str], float] = {}
    es = _read(REPORTS / "EXECUTION_SCIENCE.json") or {}
    for c in es.get("cells") or [] if isinstance(es, dict) else []:
        if isinstance(c, dict) and c.get("like_for_like") and c.get("execution_drag") is not None:
            k2 = (str(c.get("symbol")), str(c.get("family")))
            drag_of[k2] = min(drag_of.get(k2, 1e9), float(c["execution_drag"]))
    bids = []
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        k = f"{spec.get('symbol')}.{spec.get('selector')}"
        fw = shadow.get(k) or {}
        n = int(fw.get("n") or 0)
        ev = float(((row.get("gates") or {}).get("expected_value") or {}).get("ev") or 0.0)
        h = float(((hon.get(str(row.get("hunt"))) or {}).get("honesty")) or 1.0)
        prior_mu = ev * h
        mu = prior_mu if n == 0 else (prior_mu * 10 + float(fw.get("exp_r") or 0.0) * n) / (
            10 + n)
        sd = 1.0 / math.sqrt(10 + n)
        fam = str(spec.get("family") or "")
        drag = drag_of.get((str(spec.get("symbol")), fam))
        # sigma: the forward clock's own dispersion of R when it has one (cum_r and max drawdown
        # bound it from below), else 1R per trade, the unit the edge is quoted in
        sig_r = 1.0
        if n >= 5 and fw.get("max_dd_r") is not None:
            sig_r = max(0.5, abs(float(fw["max_dd_r"])) / math.sqrt(n))
        bids.append(opportunity_exchange.Bid(
            key=str(key), mu=mu * 0.01, mu_sd=sd * 0.01, sigma=sig_r * 0.01,
            friction=float(drag) if drag is not None else 0.0,
            capacity=0.05, current=by_group.get(nm.group(key), 0.0)
            / max(1, per_group.get(nm.group(key), 1)),
            mechanism=_mechanism(fam),
            evidence_arriving=str(fw.get("status") or "ACTIVE").upper() == "ACTIVE"))
    return bids, live_book


def organ_exchange() -> dict[str, Any]:
    bids, live = _posterior_bids()
    if not bids:
        return {"status": "UNMEASURED", "why": "no certificates on this host",
                "metric": {"defer_share": None}}
    res = opportunity_exchange.clear(bids)
    live_as_bids = {b.key: b.current for b in bids}
    cmp = opportunity_exchange.compare(res["book"], live_as_bids, {b.key: b.mu for b in bids})
    cmp["live_book_names"] = len(live)
    _write(STATE / "exchange_book.json", {"generated_utc": NOW.isoformat(), "book": res["book"],
                                          "actions": res["action_counts"]})
    # the book as it stood each hour: the twin scores the challenger on the book it HELD that
    # day, never on today's book replayed over the past
    with (STATE / "exchange_book_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": NOW.isoformat(), "book": res["book"]}) + "\n")
    _register_challenger("allocator", "opportunity_exchange", {"k": res["k"]}, None)
    n = sum(res["action_counts"].values())
    return {**{k: v for k, v in res.items() if k != "actions"},
            "actions_sample": dict(list(res["actions"].items())[:30]), "vs_live": cmp,
            "metric": {"expected_log_growth": res["expected_log_growth"],
                       "defer_share": res["action_counts"]["DEFER"] / n if n else None}}


def organ_predictions() -> dict[str, Any]:
    st = _state("forecasts")
    ledger = [prediction_accounting.Forecast(**f) for f in st.get("forecasts") or []]
    shadow = shadow_rows()
    # register this hour's forecast for every LIVE sleeve BEFORE its next outcome
    horizon = (NOW + timedelta(days=2)).isoformat()
    made = 0
    # forecasts are made at the grain outcomes can be traced to (SYMBOL.window): the live
    # ledger's fills resolve to that through the ticket that opened them
    groups: set[str] = set()
    for k, v in registry().items():
        if not isinstance(v, dict) or v.get("status") != "LIVE":
            continue
        idn = v.get("identity") or {}
        k = names().group(k)
        if k in groups:
            continue
        groups.add(k)
        fw = shadow.get(f"{idn.get('symbol')}.{idn.get('selector')}") or {}
        n = int(fw.get("n") or 0)
        mu = float(fw.get("exp_r") or 0.0)
        sd = max(0.5, 1.2 / math.sqrt(max(n, 1)) + 0.8)
        try:
            prediction_accounting.register(ledger, prediction_accounting.Forecast(
                key=str(k), made_at=NOW.isoformat(), horizon_end=horizon, mu=mu, sd=sd,
                p_positive=0.5 + 0.5 * math.erf(mu / (sd * math.sqrt(2))),
                source="tier_s.posterior"))
            made += 1
        except prediction_accounting.RegistrationError:
            continue
    outcomes: dict[str, list[tuple[str, float]]] = defaultdict(list)
    traded: list[tuple[str, str]] = []
    for r in live_rows():
        k = r["_group"]
        rm = r.get("r_multiple")
        if k and rm is not None and float(rm) != 0.0:
            outcomes[k].append((str(r.get("time")), float(rm)))
        if k:
            traded.append((k, str(r.get("time"))))
    sc = prediction_accounting.score(ledger, outcomes)
    cov = prediction_accounting.unaccounted(traded, ledger)
    # factory honesty: backtest claims vs forward/live
    claims = []
    live_by: dict[str, list[float]] = defaultdict(list)
    for k, v in outcomes.items():
        live_by[k].extend(x for _t, x in v)
    prod = _producer_of_cell()
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        ev = float(((row.get("gates") or {}).get("expected_value") or {}).get("ev") or 0.0)
        lk = list(live_by.get(f"{spec.get('symbol')}.{spec.get('selector')}") or [])
        claims.append(prediction_accounting.Claim(
            factory=prod.get(str(row.get("cell") or "")) or _producer(row.get("hunt")),
            key=str(key), claimed_edge=ev,
            forward_edge=float(fw["exp_r"]) if fw.get("exp_r") is not None else None,
            forward_n=int(fw.get("n") or 0),
            live_edge=(sum(lk) / len(lk)) if lk else None, live_n=len(lk)))
    hon = prediction_accounting.honesty(claims)
    _save_state("honesty", hon)
    cutoff = (NOW - timedelta(days=30)).isoformat()
    _save_state("forecasts", {"forecasts": [f.__dict__ for f in ledger
                                            if f.made_at >= cutoff][-20_000:]})
    return {"registered_now": made, "score": sc, "coverage": cov, "honesty": hon,
            "metric": {"crps": sc["crps"], "coverage90": sc["coverage90"],
                       "accounted_share": cov["accounted_share"],
                       "overconfidence": sc["overconfidence"]}}


def _register_challenger(component: str, name: str, genome: Any,
                         fitness: Any) -> None:
    st = _state("challengers")
    rows = {r["name"]: r for r in st.get("challengers") or []}
    if name not in rows:
        rows[name] = {"component": component, "name": name,
                      "registered_at": NOW.isoformat(),
                      "genome_hash": truth_kernel.sha256(truth_kernel.canon(genome))[:16],
                      "genome": genome, "fitness": fitness}
    _save_state("challengers", {"challengers": list(rows.values())[-200:]})


def organ_twin(sealed_now: Mapping[str, Any]) -> dict[str, Any]:
    st = _state("challengers")
    out = []
    ex = _read(STATE / "exchange_book.json") or {}
    nm = names()
    daily: dict[str, dict[str, float]] = defaultdict(dict)
    for r in live_rows():
        d = str(r.get("time"))[:10]
        daily[d][r["_group"]] = daily[d].get(r["_group"], 0.0) + float(r.get("r_multiple") or 0.0)
    live_hist = _jsonl(FORECAST_LOG, 50_000)
    live_book_by_day: dict[str, dict[str, float]] = {}
    for r in live_hist:
        grp: dict[str, float] = defaultdict(float)
        for k, v in (r.get("book") or {}).items():
            with contextlib.suppress(TypeError, ValueError):
                grp[nm.group(k)] += float(v)
        live_book_by_day[str(r.get("t"))[:10]] = dict(grp)
    ex_book_by_day: dict[str, dict[str, float]] = {}
    for r in _jsonl(STATE / "exchange_book_log.jsonl", 50_000):
        grp2: dict[str, float] = defaultdict(float)
        for k, v in (r.get("book") or {}).items():
            with contextlib.suppress(TypeError, ValueError):
                grp2[nm.group(k)] += float(v)
        ex_book_by_day[str(r.get("t"))[:10]] = dict(grp2)
    _ = ex
    for c in st.get("challengers") or []:
        ch = twin.Challenger(c["component"], c["name"], c["registered_at"], c["genome_hash"])
        pairs = []
        if c["component"] == "allocator":
            for day, pnl in sorted(daily.items()):
                book = ex_book_by_day.get(day)
                if book is None:
                    continue       # the challenger held no book that day: no pair, no verdict
                lb = live_book_by_day.get(day) or {}
                inc = sum(float(lb.get(k, 0.0)) * v for k, v in pnl.items())
                cha = sum(float(book.get(k, 0.0)) * v for k, v in pnl.items())
                pairs.append((f"{day}T23:59:59+00:00", inc, cha))
        res = twin.evaluate(ch, pairs)
        adoption = self_model.adoption(c, res["verdict"], res["money_path"],
                                       bool(sealed_now.get("blocked")))
        if adoption == "ADOPTED" and c["component"] == "validator" and isinstance(
                c.get("genome"), dict):
            ad = _state("adopted")
            ad["validator"] = c["genome"]
            ad["validator_adopted_at"] = NOW.isoformat()
            _save_state("adopted", ad)
        out.append({"name": c["name"], "component": c["component"], **res,
                    "adoption": adoption})
    # validator challengers are judged on the SEALED suite, not on pairs
    for row in out:
        if row["component"] != "validator":
            continue
        c = next(x for x in st.get("challengers") or [] if x["name"] == row["name"])
        fit = c.get("fitness") or {}
        imm = _state("immune").get("history") or [{}]
        inc_bal = ((imm[-1].get("immune_score") or 0) + (imm[-1].get("power") or 0)) / 2
        if isinstance(fit, dict) and fit.get("balanced") is not None:
            better = float(fit["balanced"]) > inc_bal + 0.01
            row["sealed_balanced"] = fit["balanced"]
            row["incumbent_balanced"] = inc_bal
            if better and not sealed_now.get("blocked"):
                row["adoption"] = "ADOPTED"
                ad = _state("adopted")
                ad["validator"] = c.get("genome")
                ad["validator_adopted_at"] = NOW.isoformat()
                ad["validator_from"] = c["name"]
                _save_state("adopted", ad)
    rb = twin.rollback_plan(_release_history())
    return {"challengers": out[-30:], "rollback": rb,
            "metric": {"challengers": len(out),
                       "adopted": sum(1 for r in out if r["adoption"] == "ADOPTED")}}


def _release_history() -> list[dict[str, Any]]:
    """Distinct sealed code SHAs, oldest first: the immutable manifest's `code`, then the
    current RELEASE.json `code_sha` if it is newer than the manifest's last."""
    rows: list[dict[str, Any]] = []
    for r in _jsonl(DESK / "data" / "LIVE_MANIFEST.jsonl", 20_000):
        sha = r.get("code") or r.get("sha") or r.get("code_sha")
        if sha and (not rows or rows[-1]["sha"] != str(sha)):
            rows.append({"sha": str(sha), "at": r.get("at"), "sealed": True})
    rel = _read(DESK / "data" / "RELEASE.json") or {}
    sha = rel.get("code_sha") or rel.get("live_sha")
    if sha and (not rows or rows[-1]["sha"] != str(sha)):
        rows.append({"sha": str(sha), "at": rel.get("generated_utc"), "sealed": True})
    return rows


# ------------------------------------------------------------------------------------------------
# contracts, epistemics, self-model
# ------------------------------------------------------------------------------------------------

def evaluate_contracts(reports: Mapping[str, Any]) -> dict[str, Any]:
    ledger = _read(LEDGER) or {}
    st = _state("contracts")
    hist: dict[str, list[float]] = {k: list(v) for k, v in (st.get("history") or {}).items()}
    out: dict[str, Any] = {}
    counts: Counter[str] = Counter()
    for layer in ledger.get("layers") or []:
        lid = str(layer.get("id"))
        raw = layer.get("contract") or {}
        try:
            c = contracts.Contract.parse(raw)
        except (KeyError, ValueError) as exc:
            out[lid] = {"verdict": "INVALID", "why": str(exc)}
            counts["INVALID"] += 1
            continue
        organ = str(raw.get("organ") or "")
        if organ.startswith("report:"):
            # a layer whose organ is an existing desk leg: read that leg's own artifact
            src = _read(DESK / "reports" / organ.split(":", 1)[1]) or {}
        else:
            src = reports.get(organ) or {}
        val = contracts.read_metric(src, c.metric)
        if val is not None:
            hist.setdefault(lid, []).append(val)
            hist[lid] = hist[lid][-500:]
        ev = contracts.evaluate(c, hist.get(lid, []))
        out[lid] = {**ev, "gain": str(c.gain), "metric": f"{organ}.{c.metric}",
                    "latest": val}
        counts[ev["verdict"]] += 1
    _save_state("contracts", {"history": hist})
    return {"layers": out, "counts": dict(counts)}


def epistemic_census(reports: Mapping[str, Any]) -> dict[str, Any]:
    qs: list[epistemic.Quantity] = []
    imm = (reports.get("immune") or {}).get("score") or {}
    if imm.get("n_cases"):
        n_traps = sum(v["n"] for k, v in (imm.get("per_kind") or {}).items()
                      if not k.startswith("true"))
        rej = round((imm.get("immune_score") or 0) * n_traps)
        qs.append(epistemic.beta_quantity("immune_score", int(rej), int(n_traps),
                                          source="immune"))
    pa = reports.get("predictions") or {}
    cov = (pa.get("coverage") or {})
    if cov.get("trades"):
        acc = int(cov["trades"]) - int(cov["unaccounted"])
        qs.append(epistemic.beta_quantity("accounted_share", acc, int(cov["trades"]),
                                          source="predictions"))
    for key, row in list(survivors().items())[:500]:
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fw = shadow_rows().get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        n = int(fw.get("n") or 0)
        t = fw.get("forward_t")
        if n and t is not None and fw.get("exp_r") is not None:
            mu = float(fw["exp_r"])
            se = abs(mu / float(t)) if float(t) != 0 else None
            qs.append(epistemic.Quantity(f"forward_edge:{key}", mu,
                                         None if se is None else mu - 1.96 * se,
                                         None if se is None else mu + 1.96 * se, n=n,
                                         source="shadow"))
        else:
            qs.append(epistemic.Quantity(f"forward_edge:{key}", None, n=0, source="shadow"))
    cen = epistemic.census(qs, {q.name: 0.0 for q in qs if q.name.startswith("forward_edge")})
    undecided = sum(1 for q in qs if q.name.startswith("forward_edge") and
                    epistemic.decide(q, 0.0) == epistemic.Decision.INSUFFICIENT_EVIDENCE)
    return {**cen, "forward_edges_undecided": undecided,
            "statement": f"{undecided} certificates' forward edge cannot yet be decided from "
                         "their evidence -- there is not enough evidence to decide them",
            "metric": {"decidable_share": cen["decidable_share"]}}


def organ_self_model(reports: dict[str, Any]) -> dict[str, Any]:
    card = self_model.sealed_scorecard(reports)
    st = _state("self_model")
    prev = st.get("scorecard") or {}
    reg = self_model.regression(prev, card)
    defs = self_model.rank(self_model.inventory(reports))
    best = st.get("best") or {}
    for k, better in self_model.SEALED_METRICS.items():
        v = card.get(k)
        if v is None:
            continue
        if k not in best or (better == "up" and v > best[k]) or (better == "down"
                                                                 and v < best[k]):
            best[k] = v
    _save_state("self_model", {"scorecard": card, "best": best, "at": NOW.isoformat()})
    docket = [{"task": f"Tier S deficiency: {d['area']}", "why": d["why"],
               "expected_improvement": d["expected_improvement"], "gain": d["gain"]}
              for d in defs[:10]]
    _write(STATE / "SELF_MODEL_DOCKET.json", {"generated_utc": NOW.isoformat(),
                                               "tasks": docket})
    return {"scorecard": card, "best_ever": best, "regression": reg,
            "largest_deficiency": defs[0] if defs else None, "deficiencies": defs[:25],
            "metric": {"top_expected_improvement": defs[0]["expected_improvement"] if defs
                       else None, "regressed": len(reg["regressed"])}}


# ------------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------------

def _run(name: str, fn: Callable[[], dict[str, Any]], timings: dict[str, float],
         errors: dict[str, str]) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        out = fn()
    except Exception as exc:
        errors[name] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1200:]}"
        out = {"status": "ERROR", "error": errors[name][:400]}
    timings[name] = round(time.perf_counter() - t0, 3)
    out.setdefault("generated_utc", NOW.isoformat())
    out["seconds"] = timings[name]
    _write(OUT_DIR / f"{name.upper()}.json", out)
    print(f"tier_s {name}: {timings[name]:.1f}s"
          + (f" ERROR {errors[name].splitlines()[0]}" if name in errors else ""), flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="comma-separated organ names")
    ap.add_argument("--dry-run", action="store_true", help="probation: run the fast organs only")
    ap.add_argument("--rollback-to", default=None,
                    help="print the one-commit rollback plan to this sealed release")
    ap.add_argument("--apply-rollback", action="store_true",
                    help="with --rollback-to: make that one commit (never pushes)")
    a = ap.parse_args(argv)
    if a.rollback_to:
        from libs.tiers import rollback
        rb_plan = rollback.plan(a.rollback_to)
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in rb_plan.items()},
                         indent=1))
        if not rb_plan.get("available"):
            return 1
        if a.apply_rollback:
            if not rb_plan.get("sealed"):
                print("refusing: the target is not a sealed release in LIVE_MANIFEST")
                return 1
            print(f"rolled back in one commit: {rollback.apply(rb_plan)}")
        return 0
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    if a.dry_run:
        only = only or {"formal", "firewall", "epistemic"}
    timings: dict[str, float] = {}
    errors: dict[str, str] = {}
    reports: dict[str, Any] = {}

    def want(n: str) -> bool:
        return not only or n in only

    plan: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("truth_kernel", organ_truth_kernel), ("firewall", organ_firewall),
        ("immune", organ_immune), ("red_queen", organ_red_queen),
        ("test_invention", organ_test_invention), ("online_fdr", organ_online_fdr),
        ("topology", organ_topology), ("qd", organ_qd), ("genomes", organ_genomes),
        ("grammar", organ_grammar), ("theory", organ_theory),
        ("predictions", organ_predictions), ("market", organ_market),
        ("failure_memory", organ_failure_memory), ("formal", organ_formal),
        ("chaos", organ_chaos), ("replay", organ_replay), ("data_os", organ_data_os),
        ("world_science", organ_world_and_science), ("exchange", organ_exchange),
        ("worlds", organ_worlds),
    ]
    for name, fn in plan:
        if want(name):
            reports[name] = _run(name, fn, timings, errors)
    if want("frontier"):
        th = _state("topology").get("rank_history") or []
        reports["frontier"] = _run("frontier", lambda: organ_frontier(th), timings, errors)
    if want("review"):
        fdr_rows = _read(OUT_DIR / "ONLINE_FDR_ROWS.json")
        reports["review"] = _run("review", lambda: organ_review(
            reports.get("topology"), fdr_rows, reports.get("red_queen")), timings, errors)
    if want("epistemic"):
        reports["epistemic"] = _run("epistemic", lambda: epistemic_census(reports), timings,
                                    errors)
    if want("contracts") or not only:
        reports["contracts"] = _run("contracts", lambda: evaluate_contracts(reports), timings,
                                    errors)
    if want("self_model"):
        reports["self_model"] = _run("self_model", lambda: organ_self_model(reports), timings,
                                     errors)
    if want("twin"):
        sm = reports.get("self_model") or {}
        reports["twin"] = _run("twin", lambda: organ_twin(sm.get("regression") or {}),
                               timings, errors)
    summary = {"generated_utc": NOW.isoformat(), "organs": sorted(reports),
               "seconds": timings, "total_seconds": round(sum(timings.values()), 2),
               "errors": {k: v.splitlines()[0] for k, v in errors.items()},
               "metrics": {k: (v or {}).get("metric") for k, v in reports.items()},
               "contracts": (reports.get("contracts") or {}).get("counts"),
               "largest_deficiency": ((reports.get("self_model") or {})
                                      .get("largest_deficiency")),
               "immune_verdict": ((reports.get("immune") or {}).get("verdict")),
               "emitted": {k: (v or {}).get("emitted") for k, v in reports.items()
                           if isinstance(v, dict) and v.get("emitted")}}
    if not only:
        _write(SUMMARY, summary)
    print(json.dumps({"total_seconds": summary["total_seconds"],
                      "errors": list(summary["errors"])}), flush=True)
    return 1 if errors and len(errors) == len(timings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
