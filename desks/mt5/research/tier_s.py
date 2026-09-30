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
  * data/tier_s/PROMOTION_FREEZE.json the immune system's verdict. CONSUMED by the promoter's
                                      Tier S door (libs/tiers/promotion_authority.py): a DROP judged
                                      by the production certifier withholds new live rows.

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
    agent_worlds,
    allocator_tilts,
    authority,
    bitemporal,
    chaos,
    closure_worlds,
    contracts,
    control_arm,
    cross_science,
    data_os,
    epistemic,
    evolution,
    failure_memory,
    firewall,
    formal,
    frontier,
    graph_edges,
    meta_benchmark,
    online_fdr,
    opportunity_exchange,
    prediction_accounting,
    red_queen,
    replay,
    researcher_market,
    review_panel,
    science_labs,
    self_model,
    swap_world,
    test_invention,
    theory,
    theory_context,
    topology,
    traps,
    truth_kernel,
    twin,
    world_edges,
    world_macro,
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
    if not authority.suspended("failure_memory"):
        rows = sorted(rows, key=_explored)
    rows = rows[:MAX_EMIT_PER_KIND]
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
    # the static roles, the developer role widened to every organ measured to write code, and
    # the lockbox rule (a lockbox is opened only on a candidate frozen in the same function)
    dev = firewall.developer_role(ROOT)
    firewall.register([dev])
    roles = (*[r for r in firewall.ROLES if r.name != "developer"], dev)
    audit = firewall.audit(ROOT, roles)
    lock = firewall.lockbox_audit(ROOT)
    audit["violations"] = [*audit["violations"], *lock["violations"]]
    audit["n_violations"] = len(audit["violations"])
    audit["organs_checked"]["lockbox"] = lock["openers"]
    audit["roles"]["lockbox"] = firewall.LOCKBOX_SENTENCE
    audit["developer_code_writers"] = [o for o in dev.organs
                                       if o not in firewall.DEVELOPER_ORGANS]
    st = _state("firewall")
    rule_set = (*roles, firewall.Role("lockbox", (), sentence=firewall.LOCKBOX_SENTENCE))
    base = firewall.seed_baseline(audit, st.get("baseline"), rule_set)
    rat = firewall.ratchet(audit, base)
    if len(audit["violations"]) < len(base.get("violations") or []):
        base["violations"] = audit["violations"]
    st["baseline"] = {**base, "at": NOW.isoformat()}
    _save_state("firewall", st)
    return {"audit": audit, "ratchet": rat, "seeded_rules": base.get("seeded"),
            "runtime_checks_remaining": "money-path call sites (universal_gate, "
            "external_gauntlet, the autodiscovery orchestrator's lockbox open) do not yet call "
            "firewall.may / firewall.lockbox_accepts: a desktop session's edit",
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


#: THE SEALED META-BENCHMARK, IN THOUSANDS. 17 kinds x 150 cases. The reference validator scores
#: all of them every hour (seconds); the PRODUCTION certifier judges a rotating blind slice of the
#: same-shaped suite (400 draws a case, the docket's length) and keeps each verdict until the
#: certifier's own code changes, so the whole suite is re-judged within a day of any gate edit.
IMMUNE_PER_KIND = 150
PROD_SUITE = meta_benchmark.Suite(per_kind=IMMUNE_PER_KIND, n=420, base_seed=20260930)
PROD_DOCKET = 64               # cells per run_gauntlet call: PBO/SPA are docket-level gates
PROD_BUDGET_S = 240.0          # production judging seconds per hour
#: the docket's round-trip cost as a fraction of its unit price (1-pip spread on a 1.0 price)
DOCKET_COST_FRAC = 1e-4


def _case_series(case: Any, n: int = 400) -> tuple[list[float], list[float]]:
    """(signal, forward return) per bar for one case, returns scaled so the case's own
    edge-to-cost ratio holds against the docket's fixed cost model."""
    px = np.asarray(case.prices, dtype=float)
    k = DOCKET_COST_FRAC / max(1e-9, float(case.cost_per_trade))
    sig, fwd = [], []
    for t in range(1, min(len(px) - 1, n + 1)):
        sig.append(float(case.signal_fn(px, t)))
        fwd.append(float(px[t + 1] / px[t] - 1.0) * k)
    return sig, fwd


def _gauntlet_code_hash(gate: Any) -> str:
    import inspect
    try:
        return truth_kernel.sha256(Path(inspect.getfile(gate._gauntlet)).read_text("utf-8"))[:16]
    except Exception:
        return "unknown"


def _suite_index(suite: meta_benchmark.Suite) -> list[tuple[str, int]]:
    """(kind, seed) for every case, WITHOUT generating one (the seed rule is Suite.cases')."""
    return [(kind, suite.base_seed + 1000 * k_i + j) for k_i, kind in enumerate(traps.ALL_KINDS)
            for j in range(suite.per_kind)]


def production_immune(budget_s: float = PROD_BUDGET_S) -> dict[str, Any]:
    """The sealed suite judged BLIND by the desk's real ten-gate certifier.

    Blind means: a cell's name is a hash of its case, dockets mix kinds in a hash order, and the
    certifier is handed nothing but the bars and the stamped signals -- the same route the poison
    canaries take (`adversary.docket_cell`, `run_gauntlet`). Late-information kinds are stamped at
    the honest bar of what they read (`traps.LATE_INFORMATION_KINDS`); kinds the certifier is
    never shown (`traps.INEXPRESSIBLE_TO_GAUNTLET`) are counted apart. Nothing here writes a
    certificate: the docket is named for the suite and its verdicts are read back."""
    try:
        import adversary
        gate, blocked = adversary.real_gate()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    if gate is None:
        return {"status": "UNMEASURED", "why": blocked}
    code = _gauntlet_code_hash(gate)
    st = _state("immune_prod")
    verdicts: dict[str, dict[str, Any]] = {k: v for k, v in (st.get("verdicts") or {}).items()
                                           if v.get("code") == code}
    idx = [(k, sd) for k, sd in _suite_index(PROD_SUITE)
           if k not in traps.INEXPRESSIBLE_TO_GAUNTLET]
    todo = sorted((truth_kernel.sha256(f"{k}|{sd}|{code}"), k, sd) for k, sd in idx
                  if f"{k}|{sd}" not in verdicts)
    t0 = time.perf_counter()
    judged_now = 0
    import io
    while todo and time.perf_counter() - t0 < budget_s:
        batch, todo = todo[:PROD_DOCKET], todo[PROD_DOCKET:]
        cells, truth = [], {}
        for h, kind, seed in batch:
            name = "im" + h[:12]
            try:
                case, _t = traps.generate(kind, seed, PROD_SUITE.n)
                sig, fwd = _case_series(case)
                cells.append(adversary.docket_cell(
                    name, sig, fwd,
                    stamp_offset=1 if kind in traps.LATE_INFORMATION_KINDS else 0))
                truth[name] = (kind, seed)
            except Exception:
                continue
        if len(cells) < 2:
            break
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                out = gate._gauntlet.run_gauntlet(cells, "immune-sealed-suite",
                                                  adversary.CANARY_META)
        except Exception as exc:
            return {"status": "UNMEASURED", "why": f"run_gauntlet: {type(exc).__name__}: {exc}"}
        for v in out.get("verdicts") or []:
            name = str(v.get("family", "")).removeprefix("canary_")
            if name in truth:
                kind, seed = truth[name]
                verdicts[f"{kind}|{seed}"] = {
                    "kind": kind, "passed": bool(v.get("passed")),
                    "unmeasured": bool(v.get("unmeasured")), "code": code,
                    "failed": [g for g, s in (v.get("stages") or {}).items()
                               if not s.get("passed")][:3]}
                judged_now += 1
    _save_state("immune_prod", {"verdicts": verdicts, "code": code, "at": NOW.isoformat()})
    per: dict[str, dict[str, int]] = {}
    for v in verdicts.values():
        if v["unmeasured"]:
            continue
        d = per.setdefault(v["kind"], {"n": 0, "accepted": 0})
        d["n"] += 1
        d["accepted"] += int(v["passed"])
    tr = [d for k, d in per.items() if k in traps.TRAP_KINDS]
    gen = [d for k, d in per.items() if k in traps.TRUE_KINDS]
    n_tr, n_gen = sum(d["n"] for d in tr), sum(d["n"] for d in gen)
    immune = 1.0 - sum(d["accepted"] for d in tr) / n_tr if n_tr else None
    power = sum(d["accepted"] for d in gen) / n_gen if n_gen else None
    return {"status": "MEASURED", "gauntlet_code": code, "judged_now": judged_now,
            "judged_total": len(verdicts), "expressible_cases": len(idx),
            "coverage": round(len(verdicts) / len(idx), 4) if idx else None,
            "inexpressible_kinds": sorted(traps.INEXPRESSIBLE_TO_GAUNTLET),
            "immune_score": immune, "power": power,
            "per_kind": {k: {**d, "accept_rate": round(d["accepted"] / d["n"], 4)}
                         for k, d in sorted(per.items())},
            "traps_let_through": {k: d["accepted"] for k, d in per.items()
                                  if k in traps.TRAP_KINDS and d["accepted"]}}


#: the production score replaces the reference validator's in the verdict once this many traps
#: have been judged by the real certifier on its current code
PROD_MIN_TRAPS = 200


#: the real-episode suite: every kind at this many seeds on the desk's own H1 bars
REAL_PER_KIND = 30


def real_episode_immune(cfg: meta_benchmark.ValidatorConfig,
                        synthetic: Mapping[str, Any]) -> dict[str, Any]:
    """Layer 34's second suite: the same kinds planted on direction-free REAL H1 episodes
    (`libs/tiers/real_episodes.py`), scored by the same incumbent validator, sealed by its own
    hash, with its history kept apart and its gap to the synthetic suite published per kind."""
    from libs.tiers import real_episodes
    rets, _c, _v = _returns_panel(max_symbols=20, bars=3000)
    if len(rets) < 2:
        return {"status": "UNMEASURED", "why": f"{len(rets)} eligible H1 series on this host"}
    suite = real_episodes.RealSuite(panel=rets, per_kind=REAL_PER_KIND)
    rows = list(suite.cases())
    seal = suite.seal(rows)
    res = meta_benchmark.score(meta_benchmark.reference_validator(cfg), cases=rows)
    st = _state("immune_real")
    hist = list(st.get("history") or [])
    verdict = meta_benchmark.immune_verdict(res, hist, floor=0.0, seal=seal)
    hist.append({"at": NOW.isoformat(), "seal": seal, "immune_score": res["immune_score"],
                 "power": res["power"]})
    _save_state("immune_real", {"history": hist[-500:]})
    return {"status": "MEASURED", "seal": seal, **res,
            "symbols": sorted(rets), "episodes": len(suite.episodes),
            "drift_verdict": verdict, "vs_synthetic": real_episodes.compare(res, synthetic),
            "note": "real H1 magnitudes, signs randomised: no-edge is true by construction; "
                    "the drift verdict is published, and the promotion freeze stays the "
                    "sealed synthetic/production suite's"}


def organ_immune() -> dict[str, Any]:
    suite = meta_benchmark.Suite(per_kind=IMMUNE_PER_KIND)
    cfg = _incumbent_validator()
    seal = suite.seal()
    res = meta_benchmark.score(meta_benchmark.reference_validator(cfg), suite)
    prod = production_immune()
    n_prod_traps = sum(d["n"] for k, d in (prod.get("per_kind") or {}).items()
                       if k in traps.TRAP_KINDS)
    use_prod = prod.get("status") == "MEASURED" and n_prod_traps >= PROD_MIN_TRAPS
    judged = ({"immune_score": prod["immune_score"], "power": prod["power"]} if use_prod
              else res)
    judge = f"production:{prod.get('gauntlet_code')}" if use_prod else "reference_validator"
    st = _state("immune")
    hist = list(st.get("history") or [])
    const = _read(CONSTITUTION) or truth_kernel.constitution_doc()
    floor = float(((const.get("rules") or {}).get("immune.min_trap_rejection") or {})
                  .get("value", 0.9))
    hseal = f"{seal}|{judge}"
    verdict = meta_benchmark.immune_verdict(judged, hist, floor=floor, seal=hseal)
    hist.append({"at": NOW.isoformat(), "seal": hseal, "immune_score": judged["immune_score"],
                 "power": judged["power"], "reference_immune": res["immune_score"],
                 "production_immune": prod.get("immune_score")})
    _save_state("immune", {"history": hist[-500:]})
    _write(STATE / "PROMOTION_FREEZE.json", {
        "verdict": verdict["verdict"], "why": verdict.get("why"), "at": NOW.isoformat(),
        "judge": judge,
        "consumer": "research/promoter.py tier_s_block (libs/tiers/promotion_authority.py): a "
                    "production-judged DROP withholds new live rows",
        "immune_score": judged["immune_score"], "seal": hseal})
    # A JUDGE THAT REJECTS EVERYTHING IS PERFECTLY IMMUNE. Its immunity is then uninformative,
    # and its zero power is lost discovery -- the missed-growth side of the same gate.
    n_gen = sum(d["n"] for k, d in (prod.get("per_kind") or {}).items() if k in traps.TRUE_KINDS)
    power_alarm = None
    if prod.get("power") is not None and n_gen >= 100 and float(prod["power"]) < 0.05:
        power_alarm = (f"the production certifier accepted {prod['power']:.1%} of {n_gen} genuine "
                       "positive controls (incl. an AR(0.25) edge): its immunity is uninformative "
                       "and it is rejecting real edges")
    real = real_episode_immune(cfg, res)
    return {"score": res, "production": prod, "judge": judge, "seal": seal, "verdict": verdict,
            "power_alarm": power_alarm, "real_episode": real,
            "floor": floor, "validator": cfg.genome(),
            "metric": {"immune_score": judged["immune_score"], "power": judged["power"],
                       "balanced": res["balanced"],
                       "real_immune": real.get("immune_score"), "real_power": real.get("power"),
                       "real_balanced": real.get("balanced"),
                       "production_immune": prod.get("immune_score"),
                       "production_power": prod.get("power"),
                       "production_coverage": prod.get("coverage")}}


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
    # WHAT FOOLED THE REAL GATES. The production certifier's own blind verdicts on the sealed
    # suite (`production_immune`): every trap it let through, beside the genuine controls, split
    # by seed parity into proposal and confirmation sets, so an invented check must stop a trap
    # the real gates missed on cases it never saw while costing no real edge.
    prod = _state("immune_prod").get("verdicts") or {}
    fooled = [(v["kind"], int(k.split("|")[1])) for k, v in prod.items()
              if v.get("passed") and v.get("kind") in traps.TRAP_KINDS]
    genuine = [(v["kind"], int(k.split("|")[1])) for k, v in prod.items()
               if v.get("kind") in traps.TRUE_KINDS][:300]
    real: dict[str, Any] = {"fooling_cases": len(fooled)}
    if fooled:
        cases = [traps.generate(kd, sd, PROD_SUITE.n) for kd, sd in fooled[:300] + genuine]
        prop = [c for i, c in enumerate(cases) if i % 2 == 0]
        conf = [c for i, c in enumerate(cases) if i % 2 == 1]
        real = {**real, **test_invention.invent_from(inc, prop, conf)}
        for g in real.get("candidate_gates") or []:
            k = json.dumps(g["check"])
            reg.setdefault(k, {**g, "first_seen": NOW.isoformat(), "confirmations": 0,
                               "source": "fooled_production_certifier"})
            reg[k]["confirmations"] = int(reg[k].get("confirmations", 0)) + 1
            reg[k]["last_seen"] = NOW.isoformat()
    # THE LABELLED REAL SUITE: every certificate x what its forward clock then did
    suite = test_invention.labelled_suite(
        survivors(), shadow_rows(),
        lambda c: f"{_spec(c).get('symbol')}.{_spec(c).get('selector')}")
    real_suite = test_invention.invent_real(suite)
    for g in real_suite.get("candidate_gates") or []:
        k = json.dumps(g["check"])
        reg.setdefault(k, {**g, "first_seen": NOW.isoformat(), "confirmations": 0})
        reg[k]["confirmations"] = int(reg[k].get("confirmations", 0)) + 1
        reg[k]["last_seen"] = NOW.isoformat()
    # THE GATE REDUNDANCY MATRIX over every real-certifier verdict the desk holds: the Red
    # Queen's full gate vectors and the sealed suite's production verdicts (first three kills)
    vectors = [dict(v) for v in _state("red_queen").get("gate_vectors") or []
               if isinstance(v, dict)]
    vectors += [{"kind": v.get("kind"), "genuine": v.get("kind") in traps.TRUE_KINDS,
                 "failed": v.get("failed") or [], "truncated": len(v.get("failed") or []) >= 3}
                for v in prod.values() if isinstance(v, dict) and not v.get("unmeasured")]
    matrix = test_invention.redundancy_matrix(vectors)
    _save_state("candidate_gates", {"gates": list(reg.values())})
    return {**out, "from_production": real, "registry_size": len(reg),
            "real_suite": {**{k: v for k, v in suite.items() if k != "rows"}, **real_suite},
            "redundancy": matrix,
            "metric": {"candidate_gates": len(out["candidate_gates"])
                       + len(real.get("candidate_gates") or [])
                       + len(real_suite.get("candidate_gates") or []),
                       "registry": len(reg),
                       "production_fooling_cases": len(fooled),
                       "real_suite_labelled": suite["n_labelled"],
                       "certificate_precision": suite["precision"],
                       "redundant_gates": len(matrix.get("subsumed") or [])
                       if matrix.get("status") == "MEASURED" else None}}


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
    plan = [(str(a.get("kind")), float(a.get("subtlety") or 0.0),
             str(a.get("researcher") or red_queen.UNATTRIBUTED)) for a in attackers[:6]]
    # the Red Queen's own expressible kinds reach the real certifier every generation
    plan += [(k, 0.5, red_queen.UNATTRIBUTED) for k in red_queen.NEW_KINDS
             if k not in red_queen.INEXPRESSIBLE_TO_GAUNTLET and k not in {p[0] for p in plan}]
    plan += [("true_signal", 0.0, ""), ("true_weak_signal", 0.0, "")]
    inexpressible = []
    by_cell: dict[str, str] = {}
    for k, (kind, sub, who) in enumerate(plan):
        if kind in red_queen.INEXPRESSIBLE_TO_GAUNTLET:
            inexpressible.append(kind)       # the certifier is never shown what this trap fakes
            continue
        # the cell name carries no hint of the kind: the certifier judges it blind
        name = f"rq{gen}_" + truth_kernel.sha256(f"{gen}:{k}:{kind}:{sub}")[:10]
        try:
            case, _t = red_queen.generate(kind, gen * 101 + k, 402, sub)
            sig, fwd = _case_series(case)
            # a late-information attack is stamped where its information exists; stamped a bar
            # early it would be a real predictor in the docket and no engine could reject it
            cells.append(adversary.docket_cell(
                name, sig, fwd, stamp_offset=1 if kind in traps.LATE_INFORMATION_KINDS else 0))
            truth[name] = kind
            by_cell[name] = who
        except Exception:
            continue
    if len(cells) < 2:
        return {"status": "UNMEASURED", "why": "fewer than two attack cells could be built"}
    try:
        import io
        with contextlib.redirect_stdout(io.StringIO()):
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
                     "failed_gates": failed, "researcher": by_cell.get(name) or None,
                     "gates": sorted(v.get("stages") or {})})
    traps_ = [r for r in rows if not r["genuine"] and not r["unmeasured"]]
    real = [r for r in rows if r["genuine"] and not r["unmeasured"]]
    leaks = [r for r in traps_ if r["passed"]]
    per: dict[str, dict[str, Any]] = {}
    for r in traps_:
        d = per.setdefault(str(r["researcher"]), {"attacks": 0, "leaks": 0, "kinds_leaked": []})
        d["attacks"] += 1
        if r["passed"]:
            d["leaks"] += 1
            d["kinds_leaked"] = sorted({*d["kinds_leaked"], r["kind"]})
    return {"status": "MEASURED", "rows": rows, "leaks": leaks, "inexpressible": inexpressible,
            "by_researcher": per,
            "attack_success": len(leaks) / len(traps_) if traps_ else None,
            "genuine_power": sum(r["passed"] for r in real) / len(real) if real else None}


def organ_red_queen() -> dict[str, Any]:
    st = _state("red_queen")
    attackers = red_queen.from_state(st)
    sealed = list(meta_benchmark.Suite(per_kind=4, base_seed=5150, n=1200).cases())
    gen = int(st.get("generation", 0)) + 1
    # ATTRIBUTION: the market's researchers (their gate verdicts and passes) shape the attacks
    prices = _read(STATE / "researcher_prices.json") or {}
    profiles = {str(k): v for k, v in ((prices.get("researchers") if isinstance(prices, dict)
                                        else None) or {}).items()
                if isinstance(v, dict) and v.get("judged")}
    res = red_queen.generation(attackers, _incumbent_validator(), sealed, seed=gen,
                               researchers=profiles or None)
    real = _real_gauntlet_attack([e["attack"] for e in res["elite_attacks"]], gen)
    hist = list(st.get("success_history") or [])
    hist.append({"gen": gen, "at": NOW.isoformat(), "attack_success": res["attack_success"],
                 "real_attack_success": real.get("attack_success"),
                 "real_genuine_power": real.get("genuine_power")})
    # every real-certifier verdict's full gate vector, for the gate redundancy matrix (layer 21)
    vectors = list(st.get("gate_vectors") or [])
    vectors += [{"kind": r["kind"], "genuine": r["genuine"], "failed": r["failed_gates"],
                 "gates": r.get("gates") or []} for r in real.get("rows") or []
                if not r.get("unmeasured")]
    # attribution accumulates across generations: one hour samples a few researchers
    tot = {str(k): dict(v) for k, v in (st.get("attribution_total") or {}).items()
           if isinstance(v, dict)}
    for who, row in (res.get("by_researcher") or {}).items():
        d = tot.setdefault(who, {"attacks": 0, "success_sum": 0.0, "real_attacks": 0,
                                 "real_leaks": 0, "kinds_through": []})
        d["attacks"] += int(row["attacks"])
        d["success_sum"] = float(d["success_sum"]) + float(row["success"]) * int(row["attacks"])
        d["kinds_through"] = sorted({*d["kinds_through"], *row["kinds_through"]})
    for who, row in (real.get("by_researcher") or {}).items():
        d = tot.setdefault(who, {"attacks": 0, "success_sum": 0.0, "real_attacks": 0,
                                 "real_leaks": 0, "kinds_through": []})
        d["real_attacks"] = int(d.get("real_attacks", 0)) + int(row["attacks"])
        d["real_leaks"] = int(d.get("real_leaks", 0)) + int(row["leaks"])
    _save_state("red_queen", {"generation": gen, "attackers": res["next_attackers"],
                              "success_history": hist[-500:],
                              "challenger": res["challenger"],
                              "real_leaks": (real.get("leaks") or [])[:20],
                              "gate_vectors": vectors[-3000:],
                              "attribution_total": tot})
    res["attribution_total"] = {
        k: {"attacks": v["attacks"], "success": round(v["success_sum"] / v["attacks"], 4)
            if v["attacks"] else None, "real_attacks": v.get("real_attacks", 0),
            "real_leaks": v.get("real_leaks", 0), "kinds_through": v["kinds_through"]}
        for k, v in sorted(tot.items())}
    if res["challenger"] and not authority.suspended("red_queen"):
        _register_challenger("validator", f"red_queen_gen{gen}", res["challenger"],
                             res["best_defender"])
    # S33: SCHEDULING and SEARCH-POLICY challengers beside the validator genomes. The search
    # policy population evolves here; the scheduler champion is the one S05 evolved (last hour's
    # state), re-examined on the held-out days. A challenger that beats the desk's incumbent
    # (the split it actually spent) on days evolution never saw is registered for the twin.
    from libs.tiers import program_evolution as pe
    arch: dict[str, Any] = {}
    try:
        data = _program_data(("scheduler", "search_policy"))
        sp_rep, sp_st = pe.run(("search_policy",), _state("architecture_challengers"), data, gen)
        _save_state("architecture_challengers", sp_st)
        arch["search_policy"] = sp_rep["search_policy"]
        champ = ((_state("program_evolution").get("scheduler") or {}).get("champion"))
        if champ and data.get("scheduler"):
            held = pe.score("scheduler", champ, data["scheduler"], pe.TRAIN_SHARE, 1.0)
            inc = pe.score("scheduler", pe.INCUMBENT["scheduler"], data["scheduler"],
                           pe.TRAIN_SHARE, 1.0)
            lift = (None if held.get("fitness") is None or inc.get("fitness") is None
                    else round(float(held["fitness"]) - float(inc["fitness"]), 6))
            arch["scheduler"] = {"status": held.get("status"), "why": held.get("why"),
                                 "champion": champ, "champion_heldout": held.get("fitness"),
                                 "incumbent_heldout": inc.get("fitness"), "heldout_lift": lift,
                                 "beats_incumbent_heldout": lift is not None and lift > 0}
        else:
            arch["scheduler"] = {"status": "UNMEASURED",
                                 "why": "no scheduler champion yet (S05 evolves it)"
                                 if not champ else "no judgement days by producer"}
        for comp in ("scheduler", "search_policy"):
            row = arch[comp]
            if row.get("beats_incumbent_heldout") and not authority.suspended("red_queen"):
                _register_challenger(comp, f"{comp}_gen{gen}", row["champion"],
                                     {"heldout": row.get("champion_heldout"),
                                      "incumbent_heldout": row.get("incumbent_heldout"),
                                      "lift": row.get("heldout_lift")})
    except Exception as exc:
        arch = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
    return {"generation": gen, **{k: v for k, v in res.items() if k != "next_attackers"},
            "real_gauntlet": real, "architecture_challengers": arch,
            "attribution": ("MEASURED" if profiles else
                            "UNMEASURED: no researcher_prices.json with judged counts yet; "
                            "attacks charged their trap's own trials and left unattributed"),
            "metric": {"attack_success": res["attack_success"],
                       "defender_balanced": res["best_defender"]["balanced"],
                       "attributed_researchers": len(profiles),
                       "real_attack_success": real.get("attack_success"),
                       "real_genuine_power": real.get("genuine_power"),
                       "scheduler_heldout_lift": (arch.get("scheduler") or {})
                       .get("heldout_lift"),
                       "search_policy_heldout_lift": (arch.get("search_policy") or {})
                       .get("heldout_lift")}}


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
    # ancestry novelty over the hypothesis graph: EVERY parent a row records (first parent,
    # co-parents, mutated_from edges), so a crossover child is discounted by both ancestors
    from libs.research.hypothesis_graph import parents_of
    nodes: dict[str, dict[str, Any]] = {}
    src_of: dict[str, str] = {}
    multi = 0
    for r in _jsonl(HGRAPH, 60_000):
        nid = str(r.get("id") or "")
        if not nid:
            continue
        pars = [p for p in parents_of(r) if p in nodes]
        multi += int(len(pars) > 1)
        src_of[nid] = _producer(r.get("source"))
        nodes[nid] = {"parents": pars,
                      "descriptors": {"family": r.get("family"), "symbol": r.get("symbol"),
                                      "source": str(r.get("source") or "").split(":")[0]}}
    nov = topology.novelty(nodes) if nodes else {}
    eff = topology.effective_discoveries(nov)
    eff["multi_parent_nodes"] = multi
    eff["parented_nodes"] = sum(1 for n in nodes.values() if n["parents"])
    st = _state("topology")
    hist = list(st.get("rank_history") or [])
    hist.append({"at": NOW.isoformat(), "combined": rank.get("combined"),
                 "n": len(sleeve_names)})
    # THE RANK STEERS COMPUTE: each producer's mean ancestry novelty is the "mean novelty
    # (ancestry-discounted)" term of its researcher-market value, read by organ_market this
    # same hour -- so a producer whose births are copies of their parents is priced as copies
    by_prod: dict[str, list[float]] = defaultdict(list)
    for nid, v in nov.items():
        by_prod[src_of.get(nid, "unattributed")].append(float(v))
    prod_nov = {k: round(float(np.mean(v)), 4) for k, v in by_prod.items() if len(v) >= 5}
    eff["producer_novelty"] = prod_nov
    _save_state("topology", {"rank_history": hist[-2000:], "producer_novelty": prod_nov,
                             "at": NOW.isoformat()})
    # orthogonal directions -> hypotheses: the least-occupied mechanisms on new symbols
    # a SUSPENDED topology organ still emits; its weights stop ordering what it emits
    emitted = _emit_orthogonal({} if authority.suspended("topology") else steer, descs)
    sims = _topology_simulations(sleeve_names, descs, rank)
    return {"rank": rank, "steering": steer, "ancestry": eff, "emitted": emitted,
            "simulations": sims,
            "metric": {"effective_rank": rank.get("combined"), "n_sleeves": len(sleeve_names),
                       "effective_discoveries": eff.get("effective"),
                       "effective_rank_simulated": sims["combined"].get("combined"),
                       "trade_overlap_rank": sims["trade_overlap"].get("trade_overlap"),
                       "exposure_sim_rank": sims["exposure_sim"].get("combined")}}


EXCURSIONS = DESK / "data" / "excursions.jsonl"


def _epoch(t: Any) -> float:
    p = replay.parse_t(str(t or "").replace(" ", "T"))
    return p.timestamp() if p is not None else float("nan")


def _recorded_trades() -> dict[str, list[topology.Trade]]:
    """SYM.window -> recorded trades: shadow excursions (entry/exit/side) and live fills whose
    opening order the intents ledger holds (open = the intent's time, side = the intent's)."""
    nm = names()
    out: dict[str, list[topology.Trade]] = defaultdict(list)
    for r in _jsonl(EXCURSIONS, 200_000):
        g = nm.group(r.get("sleeve"))
        s, e = _epoch(r.get("entry_time")), _epoch(r.get("exit_time"))
        if g and r.get("symbol") and math.isfinite(s) and math.isfinite(e):
            out[g].append((s, e, float(r.get("side") or 0.0), str(r["symbol"])))
    opened: dict[str, tuple[float, float]] = {}
    for r in _jsonl(ORDER_INTENTS, 200_000):
        t = str(r.get("ticket") or "")
        side = str(r.get("side") or "").lower()
        if t and t != "0" and side:
            opened[t] = (_epoch(r.get("time")), -1.0 if side.startswith("sell") else 1.0)
    for r in live_rows():
        op = next((opened[str(r.get(k))] for k in ("entry_order", "position_id", "order")
                   if str(r.get(k) or "") in opened), None)
        e = _epoch(r.get("time"))
        if op is not None and r.get("symbol") and math.isfinite(op[0]) and e >= op[0]:
            out[r["_group"]].append((op[0], e, op[1], str(r["symbol"])))
    return out


def _h1_returns(symbols: Iterable[str], bars: int = 4000) -> dict[str, Any]:
    """symbol -> H1 log returns (pandas Series on the bars' UTC index), last `bars` bars."""
    out: dict[str, Any] = {}
    try:
        import pandas as pd
    except ImportError:
        return out
    for sym in sorted(set(symbols)):
        p = UNIVERSE / f"{sym}_H1.parquet"
        if not p.exists():
            continue
        try:
            c = pd.read_parquet(p, columns=["close"])["close"].astype(float).iloc[-bars - 1:]
        except Exception:
            continue
        c = c[np.isfinite(c) & (c > 0)]
        if len(c) > 50 and isinstance(c.index, pd.DatetimeIndex):
            out[sym] = np.log(c).diff().dropna()
    return out


def _topology_simulations(sleeve_names: list[str], descs: list[dict[str, Any]],
                          rank: Mapping[str, Any]) -> dict[str, Any]:
    """Layer 15's trade-overlap and exposure-simulation ranks, beside the descriptor and live-P&L
    ranks, and the conservative combination of all of them over the registry's sleeves."""
    from session_allocator import SESSION_HOURS
    extra: dict[str, tuple[list[str], np.ndarray]] = {}
    tr = topology.trade_overlap(_recorded_trades())
    if tr.get("status") == "MEASURED":
        # the trade grain is SYM.window; lift it onto every registry sleeve of that group
        nm = names()
        grp = [nm.group(n) for n in sleeve_names]
        sub = [n for n, g in zip(sleeve_names, grp, strict=True) if g in tr["names"]]
        gi = {g: i for i, g in enumerate(tr["names"])}
        sim_g = tr["similarity"]
        m = np.eye(len(sub))
        for a, na in enumerate(sub):
            for b, nb in enumerate(sub):
                if a != b:
                    ga, gb = nm.group(na), nm.group(nb)
                    m[a, b] = 1.0 if ga == gb else float(sim_g[gi[ga], gi[gb]])
        extra["trade_overlap"] = (sub, m)
    trade = {k: v for k, v in tr.items() if k not in ("names", "similarity")}
    sl = [{"name": n, "symbol": d.get("symbol"), "direction": d.get("direction"),
           "selector": d.get("selector")} for n, d in zip(sleeve_names, descs, strict=True)]
    rets = _h1_returns(str(d.get("symbol")) for d in descs if d.get("symbol"))
    sim_names, panel = topology.simulate_exposure(sl, rets, SESSION_HOURS)
    if len(sim_names) >= 2 and panel.shape[0] >= 10:
        expo = {"status": "MEASURED", **topology.rank_report(panel, sim_names, None),
                "symbols_with_bars": len(rets),
                "left_out": len(sleeve_names) - len(sim_names)}
        expo.pop("uniqueness", None)
        extra["exposure_sim"] = (sim_names, topology.pnl_similarity(panel))
    else:
        expo = {"status": "UNMEASURED", "combined": None,
                "why": f"{len(sim_names)} sleeve(s) simulable on {len(rets)} H1 series here"}
    comb = (topology.combined_with(rank, sleeve_names, descs, extra) if extra
            else {"combined": None, "why": "neither simulation measured"})
    return {"trade_overlap": trade, "exposure_sim": expo, "combined": comb}


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
            "economic_actor", "regime", "execution_style", "direction", "complexity",
            "capacity", "corr_cluster")
    arch = evolution.Archive(axes)
    shadow = shadow_rows()
    # CAPACITY and CORRELATION-CLUSTER axes (libs/tiers/qd_axes.py): measured per symbol from the
    # bar lake's aligned H1 returns and reports/CAPACITY.json; "?" where unmeasured
    from libs.tiers import panel, qd_axes
    surv_syms = {str(_spec(r).get("symbol") or r.get("sym") or "")
                 for r in survivors().values() if isinstance(r, dict)}
    frames = panel.load_frames(UNIVERSE, eligible=_may_hypothesise, bars=3000, max_symbols=80)
    frames.update(panel.load_frames(UNIVERSE, surv_syms - set(frames), bars=3000,
                                    eligible=_may_hypothesise, max_symbols=80))
    ccl = qd_axes.correlation_clusters(panel.log_returns(frames))
    cap = qd_axes.capacity_bands(_read(REPORTS / "CAPACITY.json"), frames)
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
                   else "complex", "family": fam, "symbol": sym,
                   "capacity": cap["labels"].get(sym, "?"),
                   "corr_cluster": ccl["labels"].get(sym, "?")})
        arch.add(str(key), {k: ax.get(k, "?") for k in (*axes, "family", "symbol")}, q)
    cov = arch.coverage()
    empty = arch.marginal_empty([("mechanism", "asset_class"), ("mechanism", "session"),
                                 ("mechanism", "horizon"), ("information_source", "asset_class"),
                                 ("economic_actor", "session"), ("corr_cluster", "mechanism"),
                                 ("capacity", "mechanism")], top=400)
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
        if "corr_cluster" in e:
            pool = [s for s in all_syms if ccl["labels"].get(s) == e["corr_cluster"]]
        if "capacity" in e:
            pool = [s for s in all_syms if cap["labels"].get(s) == e["capacity"]]
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
    filled_on = {a: sum(1 for c in arch.cells.values() if (c["desc"] or {}).get(a) != "?")
                 for a in ("capacity", "corr_cluster")}
    return {"coverage": cov, "empty_projections": empty[:40], "weak": arch.weak(10),
            "emitted": emitted, "axes": list(axes),
            "corr_clusters": {k: v for k, v in ccl.items() if k != "labels"},
            "capacity_axis": {k: v for k, v in cap.items() if k not in ("labels", "source")},
            "elites_measured_on": filled_on,
            "metric": {"niche_share": cov.get("share"), "qd_score": cov.get("qd_score"),
                       "filled": cov.get("filled"),
                       "corr_clusters": ccl.get("n_clusters"),
                       "capacity_measured_elites": filled_on["capacity"],
                       "cluster_measured_elites": filled_on["corr_cluster"]}}


def _gate_by_symfam() -> dict[str, list[tuple[str, bool]]]:
    """SYMBOL.family -> [(at, passed)] in ledger order: the grain a genome proposes at."""
    out: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for r in _jsonl(GATE_LEDGER):
        sym, fam = str(r.get("sym") or ""), str(r.get("family") or "")
        if sym and fam:
            out[f"{sym}.{fam}"].append((str(r.get("at") or ""), bool(r.get("passed"))))
    return out


#: THE falsify_order GENE'S PHENOTYPE. Each allele names the gates whose kills it tries to avoid
#: spending the genome's rows on: its candidates are ORDERED by the measured share of their
#: family's verdicts that died at those gates (lowest first), so two genomes identical but for this
#: gene emit different cells and selection sees the difference. Ordering, never a filter.
FALSIFY_GATES: dict[str, tuple[str, ...]] = {
    "cost_first": ("stress_costs", "swap_cost", "expected_value"),
    "lookahead_first": ("walk_forward", "lockbox", "cpcv"),
    "stability_first": ("pbo", "cpcv", "walk_forward"),
    "dsr_first": ("deflated_sharpe", "reality_check_spa", "in_sample_screen"),
}


def _family_gate_kills(rows: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Counter[str]]:
    """family -> Counter(terminal_gate) over every judged verdict (`_total` holds the count)."""
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows if rows is not None else _jsonl(GATE_LEDGER):
        fam = str(r.get("family") or "")
        if not fam:
            continue
        out[fam]["_total"] += 1
        if not r.get("passed"):
            out[fam][str(r.get("terminal_gate") or "")] += 1
    return out


def falsify_rank(family: str, allele: str, kills: Mapping[str, Counter[str]]) -> float:
    """Share of this family's verdicts that died at the allele's gates; 0.5 when unjudged."""
    c = kills.get(family)
    if not c or not c.get("_total"):
        return 0.5
    return sum(c.get(g, 0) for g in FALSIFY_GATES.get(allele, ())) / float(c["_total"])


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


def _program_data(kinds: Iterable[str]) -> dict[str, Any]:
    """The desk's own evidence for each evolved PROGRAM kind (libs/tiers/program_evolution.py):
    aligned H1 returns (portfolio), OHLC (execution, regime), and day x arm judgement counts
    from the gate ledger -- the hypothesis graph's fate events when the ledger splits into fewer
    than two arms -- by producer (scheduler) and by family (search_policy). None = UNMEASURED."""
    from libs.tiers import panel
    from libs.tiers import program_evolution as pe
    kinds = set(kinds)
    out: dict[str, Any] = {}
    if kinds & {"portfolio", "execution", "regime"}:
        frames = panel.load_frames(UNIVERSE, eligible=_may_hypothesise, bars=3000,
                                   max_symbols=24)
        rets = panel.log_returns(frames)
        out["portfolio"] = rets.dropna(how="all").to_numpy() if len(rets.columns) >= 2 \
            else None
        ohlc = pe.ohlc_arrays(dict(list(frames.items())[:12])) if frames else None
        out["execution"] = out["regime"] = ohlc or None
    if kinds & {"scheduler", "search_policy"}:
        gate = _jsonl(GATE_LEDGER)
        graph: list[dict[str, Any]] | None = None
        born: dict[str, str] = {}

        def _graph() -> list[dict[str, Any]]:
            nonlocal graph
            if graph is None:
                graph = _jsonl(HGRAPH, 400_000)
                for r in graph:
                    if r.get("fate") == "BORN" and r.get("id"):
                        born[str(r["id"])] = _producer(r.get("source"))
            return graph
        if "scheduler" in kinds:
            prod = _producer_of_cell() if gate else {}
            days = pe.arm_days(gate, lambda r: prod.get(str(r.get("cell") or ""))
                               or _producer(r.get("source")))
            if len({a for d in days.values() for a in d}) < 2:
                g = _graph()
                days = pe.arm_days(g, lambda r: born.get(str(r.get("id") or "")))
            out["scheduler"] = days or None
        if "search_policy" in kinds:
            days = pe.arm_days(gate, lambda r: str(r.get("family") or ""))
            if len({a for d in days.values() for a in d}) < 2:
                days = pe.arm_days(_graph(), lambda r: str(r.get("family") or ""))
            out["search_policy"] = days or None
    return out


def organ_genomes() -> dict[str, Any]:
    """Researcher genomes: each emits EXACT recipes; fitness is what the gauntlet made of them.

    Every gene reaches the row: operator_set and feature_language pick the families, horizon
    the chart, data_policy the asset classes, source where the (symbol, family) pair comes
    from, novelty which pairs are preferred, complexity_cap how many parameters leave their
    defaults, exploration how many rows, falsify_order WHICH candidates it spends them on
    (ordered by the measured kill share of the gates it names, `FALSIFY_GATES`).
    Fitness uses the gate ledger AFTER the emission only, with measured compute per
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
    kills = _family_gate_kills()
    genomes_suspended = authority.suspended("genomes")
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
        occ: Counter[str] = Counter()
        if str(g.get("novelty")) == "exposure":
            occ = Counter(cls.get(s, "?") for s, _f in held)
        if not cand:
            continue
        allele = str(g.get("falsify_order") or "")
        jitter = rng.random(len(cand))
        # HELD-OUT CONTROL ARM: a fixed fifth of genomes draw at random, so the ordering is
        # judged against genomes that emitted under the same desk in the same hours
        if genomes_suspended or control_arm.in_control(gid, "genomes"):
            idx = sorted(range(len(cand)), key=lambda i: jitter[i])[:k]
        else:
            idx = sorted(range(len(cand)),
                         key=lambda i: (occ.get(cls.get(cand[i][0], "?"), 0),
                                        falsify_rank(cand[i][1], allele, kills), jitter[i]))[:k]
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
                "falsify_first_gates": list(FALSIFY_GATES.get(allele, ())),
                "falsify_first_kill_share": round(falsify_rank(f, allele, kills), 4),
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
    # S05: PORTFOLIO, EXECUTION, REGIME-DETECTOR and SCHEDULER programs evolved beside the
    # strategy genomes, scored offline on the desk's own artifacts; never deployed
    from libs.tiers import program_evolution as pe
    prog_kinds = ("portfolio", "execution", "regime", "scheduler")
    try:
        prog_rep, prog_st = pe.run(prog_kinds, _state("program_evolution"),
                                   _program_data(prog_kinds), gen + 1)
        _save_state("program_evolution", prog_st)
    except Exception as exc:
        prog_rep = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
    prog_measured = [k for k in prog_kinds
                     if (prog_rep.get(k) or {}).get("status") == "MEASURED"]
    judged_rows = [r for r in fit_rows if r["judged"]]
    arm = control_arm.compare(
        [r["fitness"] for r in judged_rows if not control_arm.in_control(r["genome"], "genomes")],
        [r["fitness"] for r in judged_rows if control_arm.in_control(r["genome"], "genomes")])
    return {"generation": gen + 1, "population": len(nxt), "control_arm": arm,
            "diversity": evolution.diversity(nxt), "best_fitness": best,
            "fitness_rows": sorted(fit_rows, key=lambda r: -r["fitness"])[:12],
            "cpu_s_per_verdict": s_per, "emitted": out, "programs": prog_rep,
            "metric": {"best_fitness": best, "diversity": evolution.diversity(nxt),
                       "judged_emissions": sum(r["judged"] for r in fit_rows),
                       "program_kinds_measured": len(prog_measured),
                       "program_diversity": ({k: prog_rep[k].get("diversity")
                                              for k in prog_measured} or None),
                       "program_heldout_lift": ({k: prog_rep[k].get("heldout_lift")
                                                 for k in prog_measured} or None)}}


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
    ctx = _TheoryContext()
    for r in _jsonl(GATE_LEDGER):
        fam = str(r.get("family") or "")
        if not fam:
            continue
        sym = str(r.get("sym") or "")
        theory_context.add(g.theory(mechanism_for(fam)), experiment=str(r.get("cell")),
                           supports=bool(r.get("passed")), source="backtest", context=sym,
                           jurisdiction=ctx.jurisdiction(sym),
                           regime=theory_context.declared_regime(str(r.get("cell")))
                           or "full_sample")
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
            sym = str(spec.get("symbol"))
            theory_context.add(g.theory(mechanism_for(fam)), experiment=f"forward:{key}",
                               supports=float(fw["exp_r"]) > 0, source="forward", context=sym,
                               jurisdiction=ctx.jurisdiction(sym),
                               regime=theory_context.declared_regime(str(spec.get("condition")
                                                                         or "")) or ctx.regime(sym))
        by_fam_sym[fam][str(spec.get("symbol") or "")] += 1
    rep_doc = _read(REPORTS / "REPLICATION.json") or {}
    for r in (rep_doc.get("verdicts") or []) if isinstance(rep_doc, dict) else []:
        if isinstance(r, dict) and r.get("family"):
            sym = str(r.get("symbol") or "")
            theory_context.add(
                g.theory(mechanism_for(str(r["family"]))),
                experiment=f"replication:{r.get('key')}", source="replication",
                supports=str(r.get("verdict") or "").upper() in ("REPLICATED", "AGREE"),
                context=sym, jurisdiction=ctx.jurisdiction(sym), regime="full_sample")
    live_by: dict[str, float] = defaultdict(float)
    for r in live_rows():
        live_by[r["_group"]] += float(r.get("pl_quote") or 0.0)
    done: set[tuple[str, str]] = set()
    for k, v in registry().items():
        ident = (v or {}).get("identity") or {}
        fam = str(ident.get("family") or "")
        grp = names().group(k)
        if fam and grp in live_by and (fam, grp) not in done:
            done.add((fam, grp))
            sym = str(ident.get("symbol") or grp.split(".")[0])
            theory_context.add(g.theory(mechanism_for(fam)), experiment=f"live:{grp}",
                               supports=live_by[grp] > 0, source="live", context=grp,
                               jurisdiction=ctx.jurisdiction(sym), regime=ctx.regime(sym))
    persisted = theory_context.merge_persisted(g, THEORY_GRAPH, NOW.isoformat())
    by_ctx = theory_context.context_report(g)
    rep = g.report(top=80)
    for t in rep["theories"]:
        t["context"] = by_ctx.get(t["id"])
    n_ctx = sum(1 for c in by_ctx.values() if c["context_dependent"])
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
            "persisted": persisted, "context_dependent": n_ctx,
            "metric": {"n_theories": rep["n_theories"], "complete_share":
                       rep["complete_share"], "refuted": rep["by_status"].get("REFUTED", 0),
                       "supported": rep["by_status"].get("SUPPORTED", 0),
                       "composed": composed, "context_dependent": n_ctx,
                       "carried_evidence": persisted["carried"]}}


THEORY_GRAPH = STATE / "theory_graph.json"


class _TheoryContext:
    """Jurisdiction and current volatility regime per symbol, each read once per pass."""

    def __init__(self) -> None:
        doc = _read(UNIVERSE / "universe.json")
        self.meta: dict[str, Any] = doc if isinstance(doc, dict) else {}
        self._reg: dict[str, str] = {}

    def jurisdiction(self, sym: str) -> str:
        return theory_context.jurisdiction_of(sym, self.meta.get(sym))

    def regime(self, sym: str) -> str:
        if sym not in self._reg:
            p = UNIVERSE / f"{sym}_H1.parquet"
            reg = theory_context.UNMEASURED
            if p.exists():
                try:
                    import pandas as pd
                    reg = theory_context.vol_regime(pd.read_parquet(p, columns=["close"])
                                                    ["close"].to_numpy()[-2500:])
                except Exception:
                    reg = theory_context.UNMEASURED
            self._reg[sym] = reg
        return self._reg[sym]


def _execution_evidence(n: int, rs: list[float] | None, fwd_exp: Any) -> dict[str, Any]:
    """Matched fills, the live mean R and CAPTURE = live mean R / forward expectancy (only when
    the forward clock's expectancy is positive; a ratio against <= 0 means nothing)."""
    out: dict[str, Any] = {"matched_fills": int(n)}
    if rs:
        live = float(np.mean(rs))
        out["live_mean_r"] = round(live, 5)
        try:
            f = float(fwd_exp)
        except (TypeError, ValueError):
            f = 0.0
        if f > 0:
            out["capture"] = round(live / f, 4)
    return out


#: evaluator -> the producer name its host process is paid under in the reward artifacts. The
#: panel and the Red Queen run inside tier_s, whose own emitters ("tier_s:<kind>") and whose leg
#: ("tier_s") the researcher market prices.
EVALUATOR_HOSTS: dict[str, str] = {"review_panel": "tier_s", "red_queen": "tier_s",
                                   "universal_gate": "universal_gate"}


def _shared_reward(keys: list[str]) -> dict[str, Any]:
    """Layer 32's firewall flag: which evaluator judged a candidate that the same reward
    artifact pays. Reward artifacts are the market's researcher prices and its leg prices (what
    cycle_pricing spends compute by). Absent prices are UNMEASURED, never 'no conflict'."""
    static = firewall.audit(ROOT, [firewall.EVALUATOR_REWARD])
    doc = _read(STATE / "researcher_prices.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("researchers"), dict):
        return {"status": "UNMEASURED", "why": "no researcher_prices.json (organ_market has "
                "not priced the producers yet)", "static": static, "by_candidate": {}}
    table = doc["researchers"]
    legs = {str(k) for k in (doc.get("leg_prices") or {})}
    rewarded = {"researcher_prices": set(map(str, table)),
                "leg_prices": legs | {str(n) for n, r in table.items()
                                      if isinstance(r, dict) and str(r.get("leg")) in legs}}
    rows = survivors()
    cell_prod = _producer_of_cell()
    producer_of: dict[str, str] = {}
    for k in keys:
        row = rows.get(k) or {}
        pr = cell_prod.get(str(row.get("cell") or "")) or (
            _producer(row.get("hunt")) if row.get("hunt") else "")
        if pr:
            producer_of[k] = pr
    judges = dict.fromkeys(EVALUATOR_HOSTS, keys)
    rep = firewall.shared_reward(judges, producer_of, rewarded, EVALUATOR_HOSTS)
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in rep["flags"]:
        by[f["candidate"]].append(f)
    return {"status": "MEASURED", **{k: v for k, v in rep.items() if k != "flags"},
            "flags": rep["flags"][:60], "static": static, "by_candidate": dict(by)}


def organ_review(topo: Mapping[str, Any] | None, fdr_rows: Mapping[str, Any] | None,
                 rq: Mapping[str, Any] | None) -> dict[str, Any]:
    shadow = shadow_rows()
    conflict = _shared_reward([str(k) for k, r in survivors().items() if isinstance(r, dict)])
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
    fills: Counter[str] = Counter()
    live_r: dict[str, list[float]] = defaultdict(list)
    for r in live_rows():
        fills[r["_group"]] += 1
        if r.get("r_multiple") is not None:
            with contextlib.suppress(TypeError, ValueError):
                live_r[r["_group"]].append(float(r["r_multiple"]))
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
                              "execution": _execution_evidence(
                                  fills.get(f"{sym}.{sel}", 0), live_r.get(f"{sym}.{sel}"),
                                  fw.get("exp_r")),
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
        if conflict.get("status") == "MEASURED":
            ev["firewall"] = {"shared_reward": conflict["by_candidate"].get(str(key)) or []}
        cands[str(key)] = ev
    rep = review_panel.panel_report(cands)
    rows = rep.pop("rows")
    _write(OUT_DIR / "REVIEW_PANEL_ROWS.json", {"generated_utc": NOW.isoformat(), "rows": rows})
    conflict.pop("by_candidate", None)
    return {**rep, "shared_reward": conflict,
            "metric": {"resolved_share": rep["resolved_share"],
                       "challenged": rep["verdicts"].get("CHALLENGED", 0),
                       "failed": rep["verdicts"].get("FAILED", 0),
                       "shared_reward_flags": conflict.get("n_flags"),
                       "self_judged": conflict.get("n_self"),
                       "evaluator_reward_reads": conflict["static"]["n_violations"]}}


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
    hon = {} if authority.suspended("predictions") else (
        _state("honesty").get("factories") or {})
    # ancestry novelty per producer from organ_topology (runs first); suspended -> no discount
    anc_nov: dict[str, float] = {} if authority.suspended("topology") else {
        str(k): float(v) for k, v in (_state("topology").get("producer_novelty") or {}).items()}
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
        anc = anc_nov.get(name)
        rr.mean_novelty = max(0.05, (1.0 - (f / p if p else 0.0)) *
                              (float(anc) if anc is not None else 1.0))
    res = researcher_market.allocate(list(rs.values()), headroom_s=1800.0, seed=NOW.hour)
    # independent discovery: a mechanism x asset-class species that PASSED for >= 2 cohorts
    sight = []
    for row in _jsonl(GATE_LEDGER):
        if row.get("passed"):
            pr = producer_of_cell.get(str(row.get("cell") or ""), "unattributed")
            sp = f"{_mechanism(str(row.get('family') or ''))}|{_asset_class(str(row.get('sym')))}"
            sight.append((pr, sp))
    # ENFORCED BLINDING: one firewall role per seat (registered for firewall.may), audited
    # statically with its own ratchet; cohort pairs that can read each other are not independent
    blind = _blinding_audit()
    ind = researcher_market.independent_discoveries(
        sight, {n: r.cohort for n, r in rs.items()}, blind.get("contaminated_pairs") or ())
    # THE FRONTIER PRICES THE GROUND (layer 36): a producer whose ground the species estimator
    # says still hides many unseen mechanisms is worth more compute than its record alone says.
    # Last hour's FRONTIER report (the organ runs after this one); absent -> factor 1.
    fr = {} if authority.suspended("frontier") else (
        _read(OUT_DIR / "FRONTIER.json") or {}).get("grounds") or {}
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
                 "honesty": r.honesty, "ancestry_novelty": anc_nov.get(n),
                 "judged": r.trials.get("full", 0), "passed": r.successes.get("full", 0),
                 "mean_novelty": round(r.mean_novelty, 4)} for n, r in rs.items()}
    # HELD-OUT CONTROL ARM: cycle_pricing never reprices a control leg by these prices, so the
    # market is judged by validated output per CPU hour on its treated legs against its held-out
    # ones in the same hours
    per_leg: dict[str, float] = {}
    for row in table.values():
        if row["leg"]:
            per_leg[str(row["leg"])] = per_leg.get(str(row["leg"]), 0.0) + float(
                row["validated_per_cpu_h"])
    arm = control_arm.compare(
        [v for lg, v in per_leg.items() if not control_arm.in_control(lg, "market")],
        [v for lg, v in per_leg.items() if control_arm.in_control(lg, "market")])
    arm["control_legs"] = sorted(lg for lg in per_leg if control_arm.in_control(lg, "market"))
    _write(STATE / "researcher_prices.json", {
        "generated_utc": NOW.isoformat(),
        "prices": {k: v["price"] for k, v in res["allocations"].items()},
        "budgets": {k: v["budget_s"] for k, v in res["allocations"].items()},
        "leg_prices": leg_prices, "researchers": table,
        "consumer": "research/cycle_pricing.py (compute only; never capital)"})
    return {**{k: v for k, v in res.items() if k != "allocations"},
            "researchers": dict(sorted(table.items(), key=lambda kv: -kv[1]["births"])[:40]),
            "independent_discoveries": ind, "priced_legs": len(leg_prices), "control_arm": arm,
            "blinding": blind,
            "metric": {"n_researchers": len(rs), "independently_discovered":
                       ind["independently_discovered"], "priced_legs": len(leg_prices),
                       "blinding_violations": blind.get("n_violations"),
                       "blinding_breach": blind.get("breach")}}


def _blinding_audit() -> dict[str, Any]:
    """Layer 4's enforced blinding: seat roles from the repository, registered for
    `firewall.may`, audited, ratcheted (a rule enters at what it measured, then only falls)."""
    from libs.tiers import blinding
    try:
        rep = blinding.audit(ROOT, lambda s: _epistemology(f"miner:{s}"))
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    roles = [firewall.Role(n, ()) for n in rep["roles"]]  # signature per seat role name
    st = _state("blinding")
    base = firewall.seed_baseline(rep, st.get("baseline"), roles)
    rat = firewall.ratchet(rep, base)
    if len(rep["violations"]) < len(base["violations"]):
        base["violations"] = rep["violations"]
    _save_state("blinding", {"baseline": base, "at": NOW.isoformat()})
    return {"status": "MEASURED", **{k: v for k, v in rep.items() if k != "home_organs"},
            "violations": rep["violations"][:60], "ratchet": rat,
            "breach": 1.0 if rat["breach"] else 0.0}


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
    # S39: WORLD-SEARCH over architecture failure worlds (environment faults with every knob ON),
    # minimal failing fault sets with their shortest traces (libs/tiers/failure_worlds.py)
    from libs.tiers import core_drive, failure_worlds
    worlds = failure_worlds.search(max_size=3)
    # S31: every counterexample trace (knob ablations + failure worlds) DRIVEN through the real
    # decision_core in a temp dir (libs/tiers/core_drive.py)
    try:
        from mt5desk import decision_core as dc  # type: ignore[import-not-found]
        driven = core_drive.drive_all(core_drive.counterexamples(abl, worlds), dc)
    except Exception as exc:
        driven = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    return {"protocol": {"desk_all_proven": abl["desk_all_proven"],
                         "states": abl["runs"]["desk"]["states"],
                         "invariants": abl["runs"]["desk"]["invariants"],
                         "depends_on": abl["depends_on"]},
            "desk_all_proven": abl["desk_all_proven"],
            "conformance": conformance, "structural_invariants": existing,
            "failure_worlds": worlds, "decision_core_drive": driven,
            "metric": {"protocol_proven": 1.0 if abl["desk_all_proven"] else 0.0,
                       "knobs_evidenced": conformance.get("evidenced_share"),
                       "worlds_searched": worlds["worlds_searched"],
                       "failure_worlds": worlds["n_failing"],
                       "traces_driven": driven.get("traces_driven"),
                       "core_blocked_share": driven.get("blocked_share"),
                       "core_gaps": (len(driven["core_gaps"]) if "core_gaps" in driven
                                     else None)}}


def _protocol_conformance() -> dict[str, Any]:
    """The proved protocol's knobs judged on the REAL gateway's syntax tree, send site by send
    site (`libs/tiers/conformance.py`) -- never a keyword grep, which comments could satisfy."""
    from libs.tiers import conformance
    paths = [p for p in (DESK / "mt5desk" / "gateway.py", DESK / "mt5desk" / "scalp_exec.py")
             if p.exists()]
    if not paths:
        return {"status": "UNMEASURED", "why": "no gateway source on this host"}
    per = conformance.check_paths(paths)
    knobs: dict[str, bool] = {}
    for doc in per.values():
        for k, v in (doc.get("knobs") or {}).items():
            if v is not None:
                knobs[k] = knobs.get(k, True) and bool(v)
    ok = sum(1 for v in knobs.values() if v)
    return {"method": "ast", "files": per, "knobs": knobs, "evidenced": ok, "of": len(knobs),
            "evidenced_share": ok / len(knobs) if knobs else None,
            "obligations": sorted(k for k, v in knobs.items() if not v)}


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
    # A REAL PROCESS KILLED: a journal writer SIGKILLed mid-stream in a temp directory and
    # restarted, never the live terminal (`chaos.process_kill_drill`)
    try:
        kill = chaos.process_kill_drill(ROOT, seed=NOW.hour)
    except Exception as exc:                        # pragma: no cover - host dependent
        kill = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    drills.append({"drill": "SIGKILL journal writer -> restart", **kill})
    # THE REAL GATEWAY UNDER A FAULTY MT5 DOUBLE: gateway.py's own connect / place_bracket /
    # expiry sweep, one child process per fault, the double installed before import and
    # MT5_DESK_ROOT in a temp directory (`libs/tiers/gateway_drill`). Never the live terminal.
    try:
        from libs.tiers import gateway_drill
        gw = gateway_drill.campaign()
    except Exception as exc:                        # pragma: no cover - host dependent
        gw = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}", "breaches": []}
    failing = [d for d in drills if d.get("status") == "FAIL"]
    return {"campaign": camp, "drills": drills, "process_kill": kill, "gateway_drill": gw,
            "metric": {"breaches": sum(camp["breaches"].values()),
                       "drills_failing": len(failing),
                       "processes_killed": int(kill.get("kills") or 0),
                       "gateway_faults_measured": gw.get("n_measured", 0),
                       "gateway_breaches": len(gw.get("breaches") or [])}}


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
    # ONE RECORD PER SOURCE: data_registry x ingestion_ledger x vintage, and each source's gate
    # yield (`libs/tiers/data_os.py`).
    yields, sources = _data_os_sources()
    # THE ACQUISITION LEDGER, TWO HALVES. Each of the four rankers registers and resolves its
    # predictions on ITS OWN metric from its own report (`libs/tiers/acquisition_resolution.py`),
    # compared in normalised gain (S35). Every other open prediction -- the legacy pit_share rows
    # and anything registered against a dataset landing -- is scored on the GATE YIELD of the
    # item's information class (S02), never on pit_share.
    from libs.tiers import acquisition_resolution as acq
    st = _state("acquisition")
    preds = [bitemporal.Prediction(**p) for p in st.get("predictions") or []]
    own_metrics = {spec.metric for spec in acq.SPECS}
    own = [p for p in preds if p.metric in own_metrics]
    landed = [p for p in preds if p.metric not in own_metrics]
    metric_now = data_os.metric_now(yields)
    obs_by: dict[str, dict[str, dict[str, Any]]] = {}
    reports_seen: dict[str, bool] = {}
    for spec in acq.SPECS:
        d = _read(REPORTS / spec.report)
        reports_seen[spec.ranker] = d is not None
        obs_by[spec.ranker] = acq.observe(spec.ranker, d)
    n_res = acq.resolve(own, obs_by, NOW.isoformat())
    made = sum(acq.register(own, spec.ranker, obs_by[spec.ranker], NOW.isoformat())
               for spec in acq.SPECS)
    cal = acq.calibration(own)
    ranking = acq.rank(own, cal)
    for row in ranking:
        cls = data_os.info_class(row.get("item"), row.get("kind"))
        row["info_class"] = cls
        row["class_gate_yield"] = (yields.get(cls) or {}).get("yield")
    acquired: dict[str, datetime] = {}
    acq_dir = DESK / "data" / "acquired"
    if acq_dir.exists():
        for p in acq_dir.iterdir():
            acquired[p.stem] = datetime.fromtimestamp(p.stat().st_mtime, UTC)
    moved = data_os.retarget(landed, metric_now)
    n_landed = bitemporal.resolve(landed, acquired, metric_now, NOW.isoformat())
    _save_state("acquisition", {"predictions": [p.to_dict() for p in landed + own][-3000:]})
    return {"pit_audits": audits, "sources": sources, "gate_yield": yields,
            "acquisition": {"scored_on": {"rankers": "own_metric", "landed": "gate_yield"},
                            "open": len(ranking), "registered_now": made,
                            "resolved_now": n_res, "calibration": cal, "top": ranking[:25],
                            "reports_present": reports_seen,
                            "landed_on_gate_yield": {"n": len(landed), **moved,
                                                     "resolved_now": n_landed,
                                                     "calibration":
                                                         bitemporal.calibration(landed)}},
            "metric": {"pit_share": audits["intelligence"].get("pit_share"),
                       "calibrated_rankers": sum(1 for v in cal.values()
                                                 if v.get("status") == "MEASURED"),
                       "sources": sources.get("n_sources"),
                       "sources_fully_joined": sources.get("fully_joined"),
                       "gate_yield": (yields.get("all") or {}).get("yield")}}


INGESTION_LEDGER = DESK / "data" / "ingestion_ledger.jsonl"
DATA_REGISTRY = DESK / "data" / "data_registry.json"


def _yield_class(family: str) -> str:
    try:
        import axis_registry
    except Exception:                                 # pragma: no cover - import guard
        return data_os.UNKNOWN
    return str(axis_registry.classify_family(family)[1])


def _data_os_sources() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """(gate yield per information class, one record per source). Absent ledgers are UNMEASURED
    sides of each record, never an empty clean join."""
    yields = data_os.gate_yield(_jsonl(GATE_LEDGER), _yield_class, NOW)
    reg_doc = _read(DATA_REGISTRY)
    reg = reg_doc.get("datasets") if isinstance(reg_doc, dict) else None
    reg = reg if isinstance(reg, dict) else {}
    ing = data_os.ingestion_by_dataset(data_os.tail_jsonl(INGESTION_LEDGER))
    vint = data_os.vintage_series((ROOT, DESK))
    src = data_os.source_records(reg, ing, vint, yields)
    src["inputs"] = {"registry": len(reg) if reg_doc is not None else data_os.UNMEASURED,
                     "ingestion_datasets": len(ing) if INGESTION_LEDGER.exists()
                     else data_os.UNMEASURED, "vintage_series": len(vint)}
    return yields, src


#: THE CROSS-SCIENCE QUEUE. Hits whose mechanism no registered family states go to the expression
#: factory as grammar expressions, drained one per invention draw (`expression_factory.invent`)
#: under the generator `cross_science:<lab>`, so each lab is its own species with its own trial
#: charge -- never relabelled as range_reversion or momentum_volgate.
XSCI_QUEUE = STATE / "xsci_expressions.json"
XSCI_CAP = 400


def _nearest_window(x: float) -> int:
    from libs.research.alpha_grammar import WINDOWS
    return int(min(WINDOWS, key=lambda w: abs(w - x)))


def xsci_expression(hit: Mapping[str, Any]) -> str | None:
    """The lab's own mechanism as an alpha-grammar expression on the hit's symbol, or None when
    the mechanism is cross-instrument (those go to the compiler as lead_lag instead)."""
    lab = str(hit.get("lab") or "")
    if lab in ("operations", "motif"):
        return science_labs.expression(hit)          # libs/tiers/science_labs.py
    if lab == "signal":
        half = _nearest_window(max(2.0, float(hit.get("period") or 16.0) / 2.0))
        return f"neg(delta(close, {half}))"          # half a cycle up -> the next half is down
    if lab == "control":
        dev = "zscore(sub(close, decay(close, 24)), 120)"
        return dev if float(hit.get("ac") or 0.0) > 0 else f"neg({dev})"   # lost vs overshoot
    if lab == "queueing":
        return "mul(zscore(activity, 120), sign(mean(ret, 3)))"            # congestion release
    if lab == "ecology":
        mom = "mul(sign(sum(ret, 24)), ts_rank(abs(sum(ret, 24)), 120))"
        return mom if float(hit.get("coupling") or 0.0) > 0 else f"neg({mom})"
    if lab == "dynamical":
        return "mul(sign(mean(ret, 3)), ts_rank(abs(mean(ret, 3)), 120))"  # deterministic path
    if lab == "bayesian":
        phi = float((hit.get("posterior") or {}).get("mean") or 0.0)
        return "mean(ret, 2)" if phi > 0 else "neg(mean(ret, 2))"
    if lab == "constraint" and hit.get("atoms"):          # the satisfying clause, as a gate
        return cross_science.constraint_expression(list(hit["atoms"]),
                                                   float(hit.get("direction") or 1.0))
    if lab == "gaussian_process":                         # the feature the GP leans on
        return cross_science.gp_expression(str(hit.get("feature") or ""),
                                           float(hit.get("direction") or 1.0))
    return None


def enqueue_xsci(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    path = path or XSCI_QUEUE
    try:
        have = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        have = []
    have = have if isinstance(have, list) else []
    def key(r: Mapping[str, Any]) -> tuple[Any, Any, str]:
        return r.get("symbol"), r.get("expr"), json.dumps(r.get("bind") or {}, sort_keys=True)

    seen = {key(r) for r in have if isinstance(r, dict)}
    landed = 0
    for r in rows:
        if key(r) in seen:
            continue
        have.append(r)
        seen.add(key(r))
        landed += 1
    _write(path, have[-XSCI_CAP:])
    return landed


def science_rows(labs: Mapping[str, list[dict[str, Any]]],
                 resid: list[dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                       list[dict[str, Any]]]:
    """(compiler rows, expression-queue rows). Every hit is tested AS ITS OWN MECHANISM:
      * a broken relationship is a RESIDUAL: `cross_asset_residual` on the target with the
        driver as its factor (causal betas, `mt5desk.causal_residual`), faded as the claim says;
      * information / network hits are LEADS: `lead_lag` with the measured driver and lag 1;
      * every other lab becomes a grammar expression the expression factory judges under the
        generator `cross_science:<lab>`."""
    rows: list[dict[str, Any]] = []
    exprs: list[dict[str, Any]] = []
    for r in resid:
        tgt, drv = str(r.get("target")), str(r.get("driver"))
        if not _may_hypothesise(tgt):
            continue
        rows.append({**r, "family": "cross_asset_residual", "symbols": [tgt],
                     "params": {"factor_symbols": [drv], "side_mode": "revert"},
                     "text": r.get("claim")})
    for lab, hits in labs.items():
        for h in hits:
            if lab in ("information", "network"):
                drv = str(h.get("driver") or h.get("hub") or "")
                syms = [s for s in h.get("symbols") or [] if s != drv]
                if not drv or not syms or not _may_hypothesise(syms[0]):
                    continue
                c = h.get("corr")
                dirs = (["opposite" if float(c) < 0 else "same"] if isinstance(c, (int, float))
                        else ["same", "opposite"])     # TE has no sign: both are the claim
                for d in dirs:
                    rows.append({**h, "family": "lead_lag", "lab_family": h.get("family"),
                                 "symbols": [syms[0]],
                                 "params": {"driver_symbol": drv, "lag": 1, "direction": d},
                                 "text": h.get("claim")})
                continue
            expr = xsci_expression(h)
            for s in h.get("symbols") or []:
                if expr and _may_hypothesise(str(s)):
                    exprs.append({"symbol": str(s), "expr": expr, "lab": lab,
                                  "generator": f"cross_science:{lab}",
                                  "claim": h.get("claim"), "falsifier": h.get("falsifier"),
                                  "at": NOW.isoformat()})
    return rows, exprs


CAUSAL_GRAPH = DESK / "data" / "world_causal_graph.json"
CROSS_ASSET_GRAPH = REPORTS / "CROSS_ASSET_GRAPH.json"


def _listed_graph() -> dict[str, Any]:
    """The world model's OWN edge list (world_causal_graph + cross_asset_graph), classified
    (`libs/tiers/graph_edges.py`); broken STABLE listed edges come back as residual rows."""
    causal, cross = _read(CAUSAL_GRAPH), _read(CROSS_ASSET_GRAPH)
    if causal is None and cross is None:
        return {"status": "UNMEASURED", "why": "neither world_causal_graph.json nor "
                "CROSS_ASSET_GRAPH.json is on this host", "broken": [], "edges": []}
    listed = graph_edges.listed_edges(causal, cross)
    syms = {e[k] for e in listed for k in ("driver", "target")}
    out = graph_edges.classify_listed(listed, graph_edges.h1_returns(UNIVERSE, syms),
                                      may=_may_hypothesise)
    out["sources"] = {"world_causal_graph": causal is not None,
                      "cross_asset_graph": cross is not None}
    return out


def organ_world_and_science() -> dict[str, Any]:
    listed = _listed_graph()
    listed_broken = listed.pop("broken", [])
    rets, closes, vols = _returns_panel()
    if len(rets) < 3:
        rows0, _ = science_rows({}, listed_broken)
        return {"status": "UNMEASURED", "why": f"{len(rets)} eligible H1 series on this host",
                "listed_graph": listed, "emitted": _emit("cross_science", rows0),
                "metric": {"stable_edges": None, "hypotheses": len(rows0),
                           "listed_edges_measured": listed.get("n_measured")}}
    edges = world_edges.classify_all(rets, lags=(1,), max_pairs=300)
    resid = world_edges.residuals(rets, edges) + listed_broken
    labs = cross_science.run_all(rets, closes, vols)
    labs.update(science_labs.run_all(rets, vols))     # operations + motif labs (layer 43)
    rows, exprs = science_rows(labs, resid)
    emitted = _emit("cross_science", rows)
    queued = enqueue_xsci(exprs)
    census = world_edges.census(edges)
    macro = _macro_world(sorted(rets))
    macro_emitted = _emit("macro_world", macro.pop("rows"))
    macro_exprs = macro.pop("exprs")
    queued += enqueue_xsci(macro_exprs)
    macro.pop("edges", None)
    return {"edges": census, "broken_relationships": resid[:20], "listed_graph": listed,
            "macro_world": {**macro, "emitted": macro_emitted},
            "labs": {k: len(v) for k, v in labs.items()}, "emitted": emitted,
            # a SAT clause or GP feature the grammar cannot hold is counted, never re-shaped
            "inexpressible": {lab: sum(1 for h in labs.get(lab) or [] if xsci_expression(h)
                                       is None) for lab in ("constraint", "gaussian_process")},
            "expressions_queued": queued, "expressions_offered": len(exprs),
            "sample": {k: v[:3] for k, v in labs.items()},
            "metric": {"stable_edges": census.get("STABLE", 0),
                       "hypotheses": len(rows) + len(exprs) + int(macro_emitted.get(
                           "emitted") or 0) + len(macro_exprs),
                       "macro_kinds_measured": macro.get("kinds_measured"),
                       "listed_edges_measured": listed.get("n_measured"),
                       "listed_edges_contradicted": listed.get("contradicted"),
                       "or_motif_hits": len(labs.get("operations") or [])
                       + len(labs.get("motif") or []),
                       "macro_live_edges": len(macro.get("live_edges") or [])}}


def _macro_world(symbols: list[str]) -> dict[str, Any]:
    """The world model's non-price nodes (`libs/tiers/world_macro.py`) over the same targets."""
    try:
        from libs.research.alpha_dsl import FieldCatalogue
        cat = FieldCatalogue(DESK / "data" / "axes", DESK / "data" / "representations")
    except Exception as exc:                          # pragma: no cover - import guard
        return {"status": "UNMEASURED", "why": f"catalogue: {type(exc).__name__}", "rows": [],
                "exprs": [], "census": {}}
    return world_macro.run(cat, world_macro.bars_closes(UNIVERSE, symbols), NOW.isoformat(),
                           may=_may_hypothesise, vocab=set(_family_vocab() or ()))


def organ_worlds() -> dict[str, Any]:
    """Layer 16, joined per certificate: which stress worlds each certificate has been through
    (synthetic_regimes' worlds -- the closure and agent-based families included -- and the
    shadow desk's replays) and which it has NOT. A
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
    shadow_doc = _read(TWIN_REPORT) or {}          # the shadow desk's replayed sleeves
    if isinstance(shadow_doc, dict):
        twin_keys |= {str(k) for k in shadow_doc.get("sleeves_replayed") or []}
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
               .get("expectancy"),
               "swap_world": _swap_world_of(hit, worlds),
               "closure_worlds": {w: _named_world_of(hit, worlds, w)
                                  for w in closure_worlds.NAMES},
               "agent_worlds": {w: _named_world_of(hit, worlds, w)
                                for w in agent_worlds.NAMES}}
        rows.append(rec)
        if not measured:
            untested.append(str(key))
    _write(STATE / "worlds_by_certificate.json", {"generated_utc": NOW.isoformat(),
                                                   "rows": rows})
    n = len(rows)
    flagged = sum(1 for r in rows if r["flags"])
    swap_states = Counter(str(r["swap_world"]["status"]) for r in rows)
    swap_dead = sum(1 for r in rows if "dies_on_swap_rollover" in (r["flags"] or []))
    closure = _world_family_summary(rows, worlds, "closure_worlds", closure_worlds.NAMES,
                                    CLOSURE_FLAGS)
    agents = _world_family_summary(rows, worlds, "agent_worlds", agent_worlds.NAMES,
                                   AGENT_FLAGS)
    return {"worlds": worlds, "n_certificates": n, "untested": untested[:60],
            "flagged": flagged,
            "swap_world": {"name": swap_world.NAME, "what": swap_world.WHAT,
                           "in_synthetic_regimes": swap_world.NAME in worlds,
                           "by_status": dict(swap_states), "dies_on_swap_rollover": swap_dead},
            "closure_worlds": closure, "agent_worlds": agents,
            "metric": {"stress_tested_share": (n - len(untested)) / n if n else None,
                       "flagged_share": flagged / n if n else None,
                       "worlds": len(worlds),
                       "swap_world_measured_share": swap_states.get("MEASURED", 0) / n
                       if n else None,
                       "closure_world_measured_share": closure["measured_share"],
                       "agent_world_measured_share": agents["measured_share"]}}


#: the named failure modes each world family can earn (synthetic_regimes.FLAG_RULES)
CLOSURE_FLAGS: tuple[str, ...] = ("dies_on_market_closure", "needs_the_closed_session",
                                  "halt_fragile")
AGENT_FLAGS: tuple[str, ...] = ("dies_in_herding_market", "dies_in_value_market",
                                "dies_when_liquidity_withdraws")


def _named_world_of(hit: Mapping[str, Any] | None, worlds: list[Any],
                    name: str) -> dict[str, Any]:
    """This certificate's reading in one named synthetic world, or why there is none."""
    if name not in worlds:
        return {"status": "UNMEASURED", "why": f"SYNTHETIC_REGIMES.json predates {name} "
                "(its next pass on the box carries it)"}
    if not hit:
        return {"status": "UNMEASURED", "why": "no synthetic-regime row for this certificate"}
    row = (hit.get("scenarios") or {}).get(name) or {}
    if row.get("status") != "MEASURED":
        return {"status": "UNMEASURED", "why": row.get("why") or "scenario absent from the row"}
    return {"status": "MEASURED", "expectancy": row.get("expectancy"),
            "delta_expectancy": row.get("delta_expectancy"), "applied": row.get("applied")}


def _world_family_summary(rows: list[dict[str, Any]], worlds: list[Any], key: str,
                          names: Iterable[str], flags: Iterable[str]) -> dict[str, Any]:
    """Per world family: which of its worlds the synthetic organ carries, each world's status
    counts across certificates, the certificates measured in at least one of them, and how many
    earned each of the family's named failure modes."""
    names, flags = list(names), list(flags)
    n = len(rows)
    by_world = {w: dict(Counter(str(r[key][w]["status"]) for r in rows)) for w in names}
    touched = sum(1 for r in rows if any(v.get("status") == "MEASURED"
                                         for v in r[key].values()))
    return {"names": names, "in_synthetic_regimes": [w for w in names if w in worlds],
            "by_world": by_world, "certificates_measured": touched,
            "flags": {f: sum(1 for r in rows if f in (r["flags"] or [])) for f in flags},
            "measured_share": touched / n if n else None}


def _swap_world_of(hit: Mapping[str, Any] | None, worlds: list[Any]) -> dict[str, Any]:
    """This certificate's reading in the per-bar swap/rollover world, or why there is none."""
    if swap_world.NAME not in worlds:
        return {"status": "UNMEASURED", "why": "SYNTHETIC_REGIMES.json predates the swap world "
                "(its next pass on the box carries it)"}
    if not hit:
        return {"status": "UNMEASURED", "why": "no synthetic-regime row for this certificate"}
    row = (hit.get("scenarios") or {}).get(swap_world.NAME) or {}
    if row.get("status") != "MEASURED":
        return {"status": "UNMEASURED", "why": row.get("why") or "scenario absent from the row"}
    return {"status": "MEASURED", "expectancy": row.get("expectancy"),
            "delta_expectancy": row.get("delta_expectancy"), "trades_touched": row.get("applied")}


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


ALLOCATOR_TILTS = STATE / "allocator_tilts.json"


def _allocator_tilts(ex_book: Mapping[str, float], live_book: Mapping[str, float]
                     ) -> dict[str, Any]:
    """The exchange's book and each sleeve's measured execution capture, as heat-neutral tilts
    of the allocator's posterior means (`libs/tiers/allocator_tilts.py`), read by pf_allocator
    through `allocator_evidence.tier_s_factors`. Suspended exchange -> nothing written."""
    if not live_book:
        return {"status": "UNMEASURED", "why": "no live allocator book on this host"}
    if authority.suspended("exchange"):
        with contextlib.suppress(OSError):
            ALLOCATOR_TILTS.unlink()
        return {"status": "SUSPENDED", "why": "the exchange's contracts are all REJECTED"}
    nm = names()
    ex_by: dict[str, float] = defaultdict(float)
    for k, w in ex_book.items():
        ex_by[nm.group(k)] += float(w)
    shadow = shadow_rows()
    rs: dict[str, list[float]] = defaultdict(list)
    for r in live_rows():
        if r.get("r_multiple") is not None:
            with contextlib.suppress(TypeError, ValueError):
                rs[r["_group"]].append(float(r["r_multiple"]))
    cap: dict[str, dict[str, Any]] = {}
    for g, xs in rs.items():
        ev = _execution_evidence(len(xs), xs, (shadow.get(g) or {}).get("exp_r"))
        cap[g] = {"capture": ev.get("capture"), "n": len(xs)}
    rows = allocator_tilts.build(live_book, {k: nm.group(k) for k in live_book}, ex_by, cap,
                                 held_out=lambda k: control_arm.in_control(k, "exchange"))
    _write(ALLOCATOR_TILTS, {"kind": "tier_s_tilts", "generated_utc": NOW.isoformat(),
                             "sleeves": rows,
                             "consumer": "research/pf_allocator.py via "
                                         "libs/portfolio/allocator_evidence.tier_s_factors"})
    moved = [k for k, v in rows.items() if abs(float(v["tilt"]) - 1.0) > 1e-6]
    return {"status": "WRITTEN", "sleeves": len(rows), "tilted": len(moved),
            "captured_groups": sum(1 for v in cap.values() if v["capture"] is not None)}


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
    tilts = _allocator_tilts(res["book"], live)
    n = sum(res["action_counts"].values())
    return {**{k: v for k, v in res.items() if k != "actions"},
            "actions_sample": dict(list(res["actions"].items())[:30]), "vs_live": cmp,
            "allocator_tilts": tilts,
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
    qty = _quantity_accounting(groups, horizon, cutoff)
    return {"registered_now": made, "score": sc, "coverage": cov, "honesty": hon,
            "quantities": qty,
            "metric": {"crps": sc["crps"], "coverage90": sc["coverage90"],
                       "accounted_share": cov["accounted_share"],
                       "overconfidence": sc["overconfidence"],
                       "quantities_scored": sum(
                           1 for v in qty["prequential"].values() if v.get("n_scored")),
                       **{f"{q}_crps": qty["prequential"][q].get("crps")
                          for q in prediction_accounting.QUANTITIES}}}


def _quantity_history() -> dict[str, dict[str, list[tuple[str, float]]]]:
    """quantity -> SYM.window -> [(outcome time, value)] from the desk's own ledgers."""
    nm = names()
    hist: dict[str, dict[str, list[tuple[str, float]]]] = {
        q: defaultdict(list) for q in prediction_accounting.QUANTITIES}
    for r in _jsonl(EXCURSIONS, 200_000):
        g, t = nm.group(r.get("sleeve")), str(r.get("exit_time") or "").replace(" ", "T")
        if not g or not t:
            continue
        for q in ("mae_r", "mfe_r"):
            v = r.get(q)
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                hist[q][g].append((t, float(v)))
        s, e = _epoch(r.get("entry_time")), _epoch(r.get("exit_time"))
        if math.isfinite(s) and math.isfinite(e) and e >= s:
            hist["hold_h"][g].append((t, (e - s) / 3600.0))
    intents: dict[str, dict[str, Any]] = {}
    for r in _jsonl(ORDER_INTENTS, 200_000):
        tk = str(r.get("ticket") or "")
        if tk and tk != "0":
            intents[tk] = r
    for r in live_rows():
        it = next((intents[str(r.get(k))] for k in ("entry_order", "position_id", "order")
                   if str(r.get(k) or "") in intents), None)
        if it is None:
            continue
        side = str(it.get("side") or "").lower()
        sgn = -1.0 if side.startswith("sell") else 1.0
        t = str(r.get("time") or "")
        try:
            want, fill, stop = (float(it["intended"]), float(r["entry_price"]),
                                float(it["sl"]))
        except (KeyError, TypeError, ValueError):
            want = fill = stop = float("nan")
        if all(math.isfinite(x) for x in (want, fill, stop)) and abs(want - stop) > 0:
            hist["slip_r"][r["_group"]].append((t, (fill - want) * sgn / abs(want - stop)))
        # a pending order's intent time is its PLACEMENT, not its fill: only market orders
        # give a hold time
        s, e = _epoch(it.get("time")), _epoch(t)
        if "_" not in side and math.isfinite(s) and math.isfinite(e) and e >= s:
            hist["hold_h"][r["_group"]].append((t, (e - s) / 3600.0))
    return {q: dict(v) for q, v in hist.items()}


def _quantity_accounting(groups: set[str], horizon: str, cutoff: str) -> dict[str, Any]:
    """Layer 26: MAE/MFE, hold and slippage forecasts registered before their outcomes and
    scored beside R, plus the same forecaster's prequential score on the recorded history."""
    hist = _quantity_history()
    st = _state("quantity_forecasts")
    ledger = [prediction_accounting.Forecast(**f) for f in st.get("forecasts") or []]
    # the live windows, plus any key that recorded an outcome in the last week
    recent = (NOW - timedelta(days=7)).isoformat()
    keys = set(groups) | {k for v in hist.values() for k, xs in v.items()
                          if any(str(t) >= recent for t, _x in xs)}
    made = prediction_accounting.register_quantities(ledger, hist, sorted(keys),
                                                     NOW.isoformat(), horizon)
    reg = prediction_accounting.score_quantities(ledger, hist)
    preq = prediction_accounting.prequential(hist)
    _save_state("quantity_forecasts", {"forecasts": [f.__dict__ for f in ledger
                                                     if f.made_at >= cutoff][-40_000:]})
    return {"registered_now": made, "registered": reg, "prequential": preq,
            "outcomes": {q: sum(len(v) for v in hist[q].values()) for q in hist},
            "scale": {q: ("log1p" if q in prediction_accounting.LOG_QUANTITIES else "raw")
                      for q in prediction_accounting.QUANTITIES}}


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


#: the shadow desk's hourly load: the code candidate plus this many config challengers
SHADOW_MAX_CONFIG = 2
TWIN_REPORT = REPORTS / "TWIN.json"


def _git_out(*args: str) -> str | None:
    import subprocess
    try:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                              text=True, timeout=60).stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


def _shadow_sleeves() -> list[dict[str, Any]]:
    """The LIVE sleeves the shadow desk replays, as `synthetic_regimes.load_sleeves` resolves
    them (parameters from the certificate when the sleeve row carries none)."""
    import dataclasses
    try:
        import synthetic_regimes as sr
        sl, _gaps = sr.load_sleeves()
    except Exception:
        return []
    return sorted((dataclasses.asdict(s) for s in sl if s.lane == "live"),
                  key=lambda r: str(r["name"]))


def _shadow_candidate_ref() -> str | None:
    """The code MT5-AdoptRelease would land next: the tracked branch's origin head when the
    clone has one, else HEAD."""
    branch = _git_out("rev-parse", "--abbrev-ref", "HEAD")
    for ref in ((f"origin/{branch}",) if branch and branch != "HEAD" else ()) + ("HEAD",):
        sha = _git_out("rev-parse", "--verify", f"{ref}^{{commit}}")
        if sha:
            return sha
    return None


def organ_shadow_desk() -> dict[str, Any]:
    """Layer 28's shadow desk: the candidate code (and up to `SHADOW_MAX_CONFIG` config
    challengers) replayed beside the sealed live release on one snapshot of the live inputs, in
    a sandbox (`libs/tiers/shadow_desk.py`). Paired output -> reports/TWIN.json."""
    hist = _release_history()
    inc_ref = hist[-1]["sha"] if hist else None
    inc = _git_out("rev-parse", "--verify", f"{inc_ref}^{{commit}}") if inc_ref else None
    doc: dict[str, Any] = {"generated_utc": NOW.isoformat(), "incumbent": inc_ref, "runs": [],
                           "rule": "only days after a challenger's registration count; the "
                                   "sandbox never reaches the live terminal"}
    if inc is None:
        doc.update(status="UNMEASURED", why=("no sealed release in LIVE_MANIFEST/RELEASE.json"
                                             if not inc_ref else
                                             f"sealed release {inc_ref} is not in this clone"))
        _write(TWIN_REPORT, doc)
        return doc
    sleeves = _shadow_sleeves()
    cand = _shadow_candidate_ref() or inc
    todo: list[tuple[str, str, str, dict[str, Any]]] = []
    if cand != inc and not authority.suspended("twin"):
        _register_challenger("code", f"code_{cand[:12]}", {"sha": cand}, None)
    rows = {r["name"]: r for r in _state("challengers").get("challengers") or []}
    code_name = f"code_{cand[:12]}"
    todo.append(("code", code_name if code_name in rows else "self_consistency", cand, {}))
    cfgs = [r for r in rows.values() if r.get("component") == "config"][-SHADOW_MAX_CONFIG:]
    for r in cfgs:
        g = r.get("genome") if isinstance(r.get("genome"), dict) else {}
        todo.append(("config", str(r["name"]), str(g.get("sha") or inc),
                     dict(g.get("config") or {})))
    verdicts: dict[str, Any] = {}
    for component, name, ref, config in todo:
        row = rows.get(name)
        ch = twin.Challenger(component, name, str(row["registered_at"]) if row else
                             NOW.isoformat(), str(row["genome_hash"]) if row else "self")
        rep = twin.shadow(ch, ref, inc, sleeves, config=config)
        rep["name"], rep["component"] = name, component
        doc["runs"].append(rep)
        if row:
            verdicts[name] = rep["verdict"]
    doc["status"] = ("MEASURED" if any(r.get("status") == "MEASURED" for r in doc["runs"])
                     else "UNMEASURED")
    doc["sleeves_replayed"] = sorted({s["name"] for r in doc["runs"]
                                      for s in r.get("sleeves") or []
                                      if s.get("status") == "MEASURED"})
    _write(TWIN_REPORT, doc)
    return {"status": doc["status"], "incumbent": inc, "candidate": cand,
            "verdicts": verdicts, "runs": [
                {"name": r["name"], "status": r.get("status"), "why": r.get("why"),
                 "n_measured": r.get("n_measured"), "pairs": len(r.get("pairs") or []),
                 "decision_agreement": r.get("decision_agreement"),
                 "terminal_touches": len((r.get("sandbox") or {}).get("terminal_touches")
                                         or []),
                 "verdict": (r.get("verdict") or {}).get("verdict")} for r in doc["runs"]]}


def organ_twin(sealed_now: Mapping[str, Any]) -> dict[str, Any]:
    try:
        shadow = organ_shadow_desk()
    except Exception as exc:                       # the shadow desk never costs the twin
        shadow = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}",
                  "verdicts": {}}
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
        shadow_res = (shadow.get("verdicts") or {}).get(c["name"])
        res = shadow_res if c["component"] in ("code", "config") and shadow_res \
            else twin.evaluate(ch, pairs)
        adoption = self_model.adoption(c, res["verdict"], res["money_path"],
                                       bool(sealed_now.get("blocked")))
        if c["component"] == "validator":
            adoption = "PENDING"       # decided below, on the sealed suite and nowhere else
        out.append({"name": c["name"], "component": c["component"], **res,
                    "adoption": adoption})
    # VALIDATOR CHALLENGERS ARE RE-SCORED ON THE SEALED SUITE. Until 2026-09-30 the challenger's
    # score was the one it earned on its own TRAINING suite (the Red Queen's, seed 5150), compared
    # with the incumbent's sealed score -- a challenger graded on the exam it studied. Now both
    # are scored by the same reference validator on the same sealed suite, and the score is
    # cached per genome hash and suite seal so each genome is examined once.
    sealed = meta_benchmark.Suite(per_kind=IMMUNE_PER_KIND)
    seal = sealed.seal()
    cache = _state("sealed_scores")
    scores = {k: v for k, v in (cache.get("scores") or {}).items() if v.get("seal") == seal}

    def _sealed_balanced(genome: Any, gh: str) -> float | None:
        if gh in scores:
            return scores[gh]["balanced"]
        try:
            g = dict(genome or {})
            g["extra"] = tuple(tuple(x) for x in g.get("extra") or [])
            r = meta_benchmark.score(meta_benchmark.reference_validator(
                meta_benchmark.ValidatorConfig(**g)), sealed)
        except Exception:
            return None
        scores[gh] = {"seal": seal, "balanced": r["balanced"], "immune": r["immune_score"],
                      "power": r["power"]}
        return r["balanced"]

    inc = _incumbent_validator()
    inc_bal = _sealed_balanced(inc.genome(), "incumbent:" + truth_kernel.sha256(
        truth_kernel.canon(inc.genome()))[:16])
    fresh = 0
    for row in out:
        if row["component"] != "validator":
            continue
        c = next(x for x in st.get("challengers") or [] if x["name"] == row["name"])
        gh = str(c.get("genome_hash"))
        if gh not in scores and fresh >= 4:
            row["adoption"] = "PENDING_SEALED_SCORE"     # examined on a later hour
            continue
        fresh += int(gh not in scores)
        bal = _sealed_balanced(c.get("genome"), gh)
        row["sealed_balanced"] = bal
        row["incumbent_balanced"] = inc_bal
        row["judged_on"] = f"sealed:{seal[:12]}"
        if bal is None or inc_bal is None:
            continue
        if float(bal) > float(inc_bal) + 0.01 and authority.suspended("twin"):
            row["adoption"] = "PENDING_AUTHORITY"   # the twin's contract is REJECTED
        elif float(bal) > float(inc_bal) + 0.01 and not sealed_now.get("blocked"):
            row["adoption"] = "ADOPTED"
            ad = _state("adopted")
            ad["validator"] = c.get("genome")
            ad["validator_adopted_at"] = NOW.isoformat()
            ad["validator_from"] = c["name"]
            ad["validator_sealed_balanced"] = bal
            _save_state("adopted", ad)
            inc_bal = float(bal)
        else:
            row["adoption"] = "REJECTED_ON_SEALED"
    _save_state("sealed_scores", {"scores": scores})
    rb = twin.rollback_plan(_release_history())
    runs = shadow.get("runs") or []
    return {"challengers": out[-30:], "rollback": rb, "shadow_desk": shadow,
            "metric": {"challengers": len(out),
                       "adopted": sum(1 for r in out if r["adoption"] == "ADOPTED"),
                       "shadow_runs_measured": sum(1 for r in runs
                                                   if r.get("status") == "MEASURED"),
                       "shadow_terminal_touches": sum(int(r.get("terminal_touches") or 0)
                                                      for r in runs)}}


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
        # a significant CONTROL-ARM reading outranks the organ's comparison with its own past
        arm = src.get("control_arm") if isinstance(src, dict) else None
        if isinstance(arm, dict) and arm.get("verdict"):
            ev = {**ev, "vs_control": arm}
            if arm["verdict"] in ("ADMITTED", "REJECTED"):
                ev = {**ev, "verdict": arm["verdict"], "judged_by": "control_arm"}
        counts[ev["verdict"]] += 1
    # THE NEW HOURLY LEGS carry contracts too (`leg_contracts`), read from their own reports.
    # They are verdicts only: none of these legs is a steering organ, so none can be suspended.
    legs_out: dict[str, Any] = {}
    for lc in ledger.get("leg_contracts") or []:
        lid = f"leg:{lc.get('leg')}"
        raw = lc.get("contract") or {}
        try:
            c = contracts.Contract.parse(raw)
        except (KeyError, ValueError) as exc:
            legs_out[lid] = {"verdict": "INVALID", "why": str(exc)}
            continue
        organ = str(raw.get("organ") or "")
        if organ == "report:TIER_S.json":
            src: Any = {"contracts": dict(counts)}      # this hour's own verdicts, not last hour's
        else:
            src = _read(DESK / "reports" / organ.split(":", 1)[1]) or {}
        val = contracts.read_metric(src, c.metric)
        if val is not None:
            hist.setdefault(lid, []).append(val)
            hist[lid] = hist[lid][-500:]
        legs_out[lid] = {**contracts.evaluate(c, hist.get(lid, [])), "gain": str(c.gain),
                         "metric": f"{organ}.{c.metric}", "latest": val}
    _save_state("contracts", {"history": hist})
    auth = authority.compute(ledger, out)
    _write(authority.AUTHORITY, auth)
    return {"layers": out, "legs": legs_out, "counts": dict(counts),
            "leg_counts": dict(Counter(v["verdict"] for v in legs_out.values())),
            "suspended": auth["suspended"],
            "authority_rule": auth["rule"]}


DOOR_VERDICTS = STATE / "door_verdicts.json"


def organ_door() -> dict[str, Any]:
    """The panel's and the theory graph's verdicts per certificate, for the promotion door
    (`libs/tiers/door_evidence`): the panel's candidate-specific HIGH failures, and the
    mechanism's status on OUT-OF-SAMPLE evidence only (forward, live, replication)."""
    from libs.tiers import door_evidence
    panel = _read(OUT_DIR / "REVIEW_PANEL_ROWS.json") or {}
    shadow = shadow_rows()
    oos: dict[str, list[tuple[bool, str]]] = defaultdict(list)
    family_of: dict[str, str] = {}
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fam = str(spec.get("family") or "")
        if not fam:
            continue
        family_of[str(key)] = fam
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        if fw.get("n") and int(fw["n"]) >= 5 and fw.get("exp_r") is not None:
            oos[fam].append((float(fw["exp_r"]) > 0, "forward"))
    rep_doc = _read(REPORTS / "REPLICATION.json") or {}
    for r in (rep_doc.get("verdicts") or []) if isinstance(rep_doc, dict) else []:
        if isinstance(r, dict) and r.get("family"):
            oos[str(r["family"])].append(
                (str(r.get("verdict") or "").upper() in ("REPLICATED", "AGREE"), "replication"))
    live_by: dict[str, float] = defaultdict(float)
    for r in live_rows():
        live_by[r["_group"]] += float(r.get("pl_quote") or 0.0)
    done: set[tuple[str, str]] = set()
    for k, v in registry().items():
        fam = str(((v or {}).get("identity") or {}).get("family") or "")
        grp = names().group(k)
        if fam and grp in live_by and (fam, grp) not in done:
            done.add((fam, grp))
            oos[fam].append((live_by[grp] > 0, "live"))
    rows = door_evidence.build(panel.get("rows") or [], family_of, oos)
    blocking = {k: door_evidence.door_reason(v) for k, v in rows.items()}
    blocking = {k: v for k, v in blocking.items() if v}
    _write(DOOR_VERDICTS, {"generated_utc": NOW.isoformat(), "rows": rows,
                           "consumer": "libs/tiers/promotion_authority.py block()"})
    fam_status = Counter(str((v.get("theory") or {}).get("status")) for v in rows.values())
    return {"n_rows": len(rows), "n_withheld": len(blocking), "withheld": dict(
        sorted(blocking.items())[:40]), "theory_status": dict(fam_status),
            "metric": {"door_rows": len(rows), "door_withheld": len(blocking)}}


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
    # the contract's metric keeps its definition (the quantities it has always counted), so
    # adding the certifier's quantities cannot read as a calibration regression
    cen_contract = epistemic.census(
        qs, {q.name: 0.0 for q in qs if q.name.startswith("forward_edge")})
    gate_qs, thr = _certifier_quantities()
    qs.extend(gate_qs)
    thr.update({q.name: 0.0 for q in qs if q.name.startswith("forward_edge")})
    cen = epistemic.census(qs, thr)
    undecided = sum(1 for q in qs if q.name.startswith("forward_edge") and
                    epistemic.decide(q, 0.0) == epistemic.Decision.INSUFFICIENT_EVIDENCE)
    fams: dict[str, list[epistemic.Quantity]] = defaultdict(list)
    for q in qs:
        fams[q.name.split(":")[0]].append(q)
    by_family = {f: epistemic.census(v, thr) for f, v in sorted(fams.items())}
    undecided_by = {f: sum(1 for q in v if epistemic.decide(
        q, thr.get(q.name, 0.0), greater=not f.startswith("pbo"))
        == epistemic.Decision.INSUFFICIENT_EVIDENCE) for f, v in fams.items()
        if f in ("dsr_excess", "pbo", "cost_x3", "cost_model")}
    return {**cen, "forward_edges_undecided": undecided, "by_family": by_family,
            "certifier_undecided": undecided_by,
            "statement": f"{undecided} certificates' forward edge cannot yet be decided from "
                         "their evidence -- there is not enough evidence to decide them",
            "metric": {"decidable_share": cen_contract["decidable_share"],
                       "decidable_share_all": cen["decidable_share"],
                       **{f"decidable_{f}": by_family[f]["decidable_share"]
                          for f in ("dsr_excess", "pbo", "cost_x3", "cost_model")
                          if f in by_family}}}


COST_SURFACE = DESK / "data" / "cost_surface.json"


def _certifier_quantities() -> tuple[list[epistemic.Quantity], dict[str, float]]:
    """Layer 37: every certificate's DSR excess, PBO and 3x-cost EV as labelled quantities,
    plus the cost model's error per live symbol against the measured spread surface."""
    qs: list[epistemic.Quantity] = []
    thr: dict[str, float] = {}
    for key, row in list(survivors().items())[:500]:
        if not isinstance(row, dict):
            continue
        g = row.get("gates") or {}
        days = row.get("days")
        sr = (g.get("in_sample_screen") or {}).get("sharpe")
        ds = g.get("deflated_sharpe") or {}
        qs.append(epistemic.dsr_quantity(f"dsr_excess:{key}", sr, ds.get("sr0"), days))
        thr[f"dsr_excess:{key}"] = 0.0
        pb = g.get("pbo") or {}
        qs.append(epistemic.pbo_quantity(f"pbo:{key}", pb.get("pbo"),
                                         (g.get("cpcv") or {}).get("folds") or pb.get("splits")))
        thr[f"pbo:{key}"] = 0.5
        qs.append(epistemic.cost_stress_quantity(
            f"cost_x3:{key}", (g.get("stress_costs") or {}).get("exp_x3"),
            (g.get("expected_value") or {}).get("ev"), sr, days))
        thr[f"cost_x3:{key}"] = 0.0
    surf = ((_read(COST_SURFACE) or {}).get("symbols") or {})
    seen: set[str] = set()
    for v in registry().values():
        if not isinstance(v, dict) or v.get("status") != "LIVE":
            continue
        sym = str((v.get("identity") or {}).get("symbol") or "")
        cf = v.get("cost_fields") or {}
        if not sym or sym in seen:
            continue
        seen.add(sym)
        s = surf.get(sym) if isinstance(surf, dict) else None
        name = f"cost_model:{sym}"
        thr[name] = 0.0
        if not isinstance(s, dict) or not s.get("tick_size") or not cf.get("contract_oz"):
            qs.append(epistemic.Quantity(name, None, n=0, source="cost_surface"))
            continue
        modelled = float(cf.get("spread_per_lot") or 0.0) / float(cf["contract_oz"]) / float(
            s["tick_size"])
        measured = [float(h["p50"]) for h in (s.get("hours") or {}).values()
                    if isinstance(h, dict) and h.get("status") == "MEASURED" and h.get("p50")]
        qs.append(epistemic.cost_model_quantity(name, measured, modelled))
    return qs, thr


RESEARCH_QUEUE = DESK / "data" / "research_queue.json"
#: the window the gate's verdict rate and the compute ledger's timeouts are read over
SELF_FACT_WINDOW = timedelta(days=7)


def _operational_self_facts() -> dict[str, Any]:
    """Layer 29's three missing inventory inputs, read from the artifacts that own them."""
    since = NOW - SELF_FACT_WINDOW
    q = _read(RESEARCH_QUEUE)
    status: dict[str, int] | None = None
    oldest: float | None = None
    if isinstance(q, list):
        status = dict(Counter(str(r.get("status") or "?") for r in q if isinstance(r, dict)))
        ages = [replay.parse_t(r.get("created_at")) for r in q if isinstance(r, dict)
                and str(r.get("status")) in self_model.GATE_WAITING]
        ages = [a for a in ages if a is not None]
        oldest = round((NOW - min(ages)).total_seconds() / 3600.0, 1) if ages else None
    # the gate's measured rate: verdicts it recorded over the window (none recorded while a
    # ledger exists is a rate of zero; no ledger at all is UNMEASURED)
    rate: float | None = None
    if GATE_LEDGER.exists():
        ts_ = [replay.parse_t(r.get("at") or r.get("judged_at") or r.get("time"))
               for r in _jsonl(GATE_LEDGER, 400_000)]
        n_recent = sum(1 for t in ts_ if t is not None and t >= since)
        rate = round(n_recent / (SELF_FACT_WINDOW.total_seconds() / 3600.0), 3)
    comp = [r for r in _jsonl(COMPUTE, 200_000)
            if (replay.parse_t(r.get("at")) or NOW) >= since] if COMPUTE.exists() else None
    return {"queue_status": status, "oldest_waiting_h": oldest, "verdicts_per_h": rate,
            "compute": comp, "allocation": _first(PF_ALLOCATION)}


def organ_self_model(reports: dict[str, Any]) -> dict[str, Any]:
    card = self_model.sealed_scorecard(reports)
    st = _state("self_model")
    prev = st.get("scorecard") or {}
    reg = self_model.regression(prev, card)
    ops_rows, ops_facts = self_model.operational_inventory(**_operational_self_facts())
    defs = self_model.rank(self_model.inventory(reports) + ops_rows)
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
            "operations": ops_facts,
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
    if want("door"):
        reports["door"] = _run("door", organ_door, timings, errors)
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
        # A layer is DONE only on the trading box's own evidence (libs/tiers/box_evidence).
        try:
            from libs.tiers import box_evidence
            box_evidence.attest()
        except Exception as exc:                    # pragma: no cover - host dependent
            errors["box_evidence"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps({"total_seconds": summary["total_seconds"],
                      "errors": list(summary["errors"])}), flush=True)
    return 1 if errors and len(errors) == len(timings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
