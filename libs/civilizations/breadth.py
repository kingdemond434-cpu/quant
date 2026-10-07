"""ANTI-SATURATION FOR THE CIVILIZATIONS: release the rules that add independent bets first.

    zuck, 2026-10-05: "maximise ROBUST MARGINAL EFFECTIVE BREADTH, not nominal sleeve count,
    certificate count, symbol count or parameter variants ... Do not let a different symbol name
    create fake breadth." And: every producer consumes the live breadth map, runs cheap duplicate
    checks before full compute, retargets away from saturated ground (same payer, factor, clock),
    and reports its duplicate share and delta-k_eff per compute-hour.

THE DESK ALREADY MEASURES THE INGREDIENTS; THIS READS THEM, IT DOES NOT REBUILD THEM.

    certified family occupancy   libs.research.alpha_fitness.certified_family_shares (the canon)
    certified genome slots       libs.research.alpha_fitness.survivor_slots (instrument x family)
    per-cell marginal k_eff      desks/mt5/research/docket_keff.score (EFFECTIVE_BREADTH's book,
                                 the empty clusters and the vacant census classes)
    structural cell              the same axes as judge_coverage.structural_cell: family, symbol,
                                 horizon, chart, session, regime, direction, representation

WHERE IT ACTS: at RELEASE, the civilizations' own choke point between the parked queue and the
spine's compile/seal/donate. Compiling a parked rule is cheap and pure (`compiler.compile_rule`);
judging it is the full compute. So every candidate near the head of the queue is compiled in
memory, its specs are compared with the certified canon and with what this producer has already
released, and the queue is re-ordered:

    NEAR-DUPLICATE   every spec lands on a (family, instrument) slot the canon already holds, or
                     on a structural cell this producer already released, and NO exception holds.
                     It is sampled at the exploration floor (1 in 10), never banned: markets
                     change and a better variant may exist.
    EXCEPTIONS       (A) new payer: the family is absent from the canon; (C) new temporal stream:
                     a chart other than the canon's H1 default, or a session/regime condition;
                     (E) new market expression: the instrument's asset class holds no
                     certificate of this family. (B) new information, (D) new regime and
                     (F) measured orthogonality need data a parked rule does not carry, so they
                     are UNMEASURED here, never assumed true. The judge's own docket_keff and
                     variant_split re-check everything downstream.
    ORDER            near-duplicates last; then by breadth score = max spec priority (docket_keff,
                     units of effective bets) x (2 - certified share of the family), the same
                     one-sided certified-breadth factor judge_coverage.rank_by_value uses.

UNMEASURED IS NEVER A DEMOTION (L1.28a): an unreadable canon or breadth artifact leaves every
candidate at par and says so in the report. Nothing is dropped, no gate moves, no cell is
certified or refused here.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

#: How far down the parked queue the screen compiles each pass, as a multiple of the release
#: budget. The rest keeps its backpressure order; it is screened when it nears the head.
SCREEN_DEPTH = 20
SCREEN_MIN = 2_000
EXPLORATION_EVERY = 10          # 1 near-duplicate per 10 released (the exploration floor)
#: THE SCREEN IS NOT A TRIAL, AND THE CODE MAKES THAT TRUE RATHER THAN SAYING IT (coordinator's
#: ruling 2026-10-07 under charge-once: a screen that sees any returns or P&L is a trial and is
#: charged exactly once; one that only compiles and compares structure carries no charge). It
#: compiles rules and compares specs with the published canon and this producer's own released
#: keys, and it calls docket_keff with `no_returns` as its loader, so the instrument-correlation
#: term (the only part of docket_keff that reads a return series) sits at par here and is
#: measured by the judge downstream. No candidate's returns, P&L or backtest is ever computed or
#: read, so nothing is charged; the cells it releases are charged once, when judged.
H1 = "H1"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _desk_module(root: Path, name: str) -> Any:
    """desks/mt5/research/<name>.py, imported by path (it is not a package import)."""
    for p in (str(root / "desks" / "mt5"), str(root / "desks" / "mt5" / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    if name in sys.modules:
        return sys.modules[name]
    path = root / "desks" / "mt5" / "research" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def no_returns(sym: str) -> None:
    """The screen's return loader: none, for every symbol (see the charge rule above)."""
    return None


def structural_key(spec: Mapping[str, Any]) -> str:
    """The judge's structural cell axes for one compiled spec (judge_coverage.structural_cell):
    a different chart, session, regime, direction or representation is distinct ground; a
    threshold-only change is not."""
    p = spec.get("params") or {}

    def axis(*vals: Any) -> str:
        v = next((x for x in vals if x is not None and str(x).strip()), "?")
        return str(v).strip().lower()
    return "|".join((
        str(spec.get("family") or "?"), str(spec.get("sym") or "?").upper(),
        axis(p.get("hold_bars"), p.get("horizon")),
        axis(spec.get("timeframe"), p.get("timeframe"), H1),
        axis(p.get("session"), p.get("selector")),
        axis(p.get("regime"), p.get("condition")),
        axis(p.get("direction"), p.get("side"), p.get("side_mode")),
        axis(p.get("representation"), p.get("feature"), p.get("norm"))))


class BreadthMap:
    """The live breadth map as the civilizations read it, loaded once per pass."""

    def __init__(self, root: Path, *, asset_class_of: Mapping[str, str] | None = None,
                 shares: tuple[dict[str, float], int] | None = None,
                 slots: Iterable[Mapping[str, str]] | None = None,
                 keff: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None) -> None:
        self.root = Path(root)
        self.unmeasured: list[str] = []
        if shares is None or slots is None:
            try:
                from libs.research import alpha_fitness as af
                shares = af.certified_family_shares() if shares is None else shares
                slots = af.survivor_slots() if slots is None else slots
            except Exception as exc:
                self.unmeasured.append(f"certified canon unreadable ({type(exc).__name__})")
                shares, slots = shares or ({}, 0), slots or ()
        self.shares, self.n_cert = shares
        if not self.n_cert:
            self.unmeasured.append("certified canon empty or absent: every family at par")
        self.asset_class_of = {str(k).upper(): str(v) for k, v in
                               (asset_class_of or self._universe()).items()}
        self.slots: set[tuple[str, str]] = set()
        self.fam_classes: dict[str, set[str]] = defaultdict(set)
        self.fam_cert: Counter[str] = Counter()
        for s in slots:
            fam, sym = str(s.get("mechanism") or ""), str(s.get("instrument") or "").upper()
            if not fam:
                continue
            self.fam_cert[fam] += 1
            self.slots.add((fam, sym))
            cls = str(s.get("asset_class") or self.asset_class_of.get(sym) or "")
            if cls:
                self.fam_classes[fam].add(cls)
        self._keff_fn = keff
        self._keff_cache: dict[tuple[str, str], float] = {}
        self.keff_status = "UNMEASURED"

    def _universe(self) -> dict[str, str]:
        p = self.root / "desks" / "mt5" / "data" / "universe" / "universe.json"
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            self.unmeasured.append("universe.json unreadable: asset classes UNMEASURED")
            return {}
        return {str(k): str(v.get("asset_class") or "") for k, v in doc.items()
                if isinstance(v, dict)} if isinstance(doc, dict) else {}

    def keff(self, pairs: Iterable[tuple[str, str]]) -> dict[tuple[str, str], float]:
        """docket_keff priority (effective bets) per (family, symbol); 0 at par when the
        book is unmeasured."""
        want = [p for p in dict.fromkeys(pairs) if p not in self._keff_cache]
        if want:
            rows = [{"family": f, "symbol": s} for f, s in want]
            try:
                if self._keff_fn is not None:
                    doc = self._keff_fn(rows)
                    self.keff_status = str((doc.get("instrument") or {}).get("status")
                                           or "MEASURED")
                else:
                    _desk_module(self.root, "docket_keff").score(rows, loader=no_returns)
                    # cluster and class terms measured; the instrument term is the judge's
                    self.keff_status = "STRUCTURE_ONLY"
                for r, (f, s) in zip(rows, want, strict=True):
                    self._keff_cache[(f, s)] = float(r.get("_keff") or 0.0)
            except Exception as exc:
                if "docket_keff" not in " ".join(self.unmeasured):
                    self.unmeasured.append(f"docket_keff unavailable ({type(exc).__name__}): "
                                           "delta-k_eff at par")
                for p in want:
                    self._keff_cache[p] = 0.0
        return {p: self._keff_cache[p] for p in pairs}

    def assess(self, specs: Sequence[Mapping[str, Any]], released: set[str]) -> dict[str, Any]:
        """One candidate's breadth verdict from its compiled specs (cheap, pre-judging)."""
        if not specs:
            return {"specs": 0, "near_duplicate": False, "breadth_score": 0.0,
                    "exceptions": [], "dup_canon": 0, "dup_own": 0, "keff": 0.0,
                    "structural_keys": []}
        keys = [structural_key(s) for s in specs]
        pairs = [(str(s.get("family") or ""), str(s.get("sym") or "").upper()) for s in specs]
        k = self.keff(pairs)
        dup_canon = sum(1 for p in pairs if p in self.slots)
        dup_own = sum(1 for key in keys if key in released)
        exc: set[str] = set()
        for s, (fam, sym) in zip(specs, pairs, strict=True):
            p = s.get("params") or {}
            if self.n_cert and fam not in self.fam_cert:
                exc.add("A_new_payer")
            if str(s.get("timeframe") or H1).upper() != H1 or p.get("session"):
                exc.add("C_new_temporal")
            if p.get("regime") or p.get("condition"):
                exc.add("D_new_regime")
            # an input beyond the instrument's own bars (and a regime label) is information the
            # certified book was not built on
            if any(not str(d).startswith(("bars:", "regime:"))
                   for d in s.get("required_data") or ()):
                exc.add("B_new_information")
            cls = self.asset_class_of.get(sym, "")
            if self.n_cert and cls and fam in self.fam_cert and cls not in self.fam_classes[fam]:
                exc.add("E_new_expression")
        near = (not exc) and all(p in self.slots or key in released
                                 for p, key in zip(pairs, keys, strict=True))
        best = max(k.values()) if k else 0.0
        fam0 = pairs[0][0]
        share = float(self.shares.get(fam0, 0.0)) if self.n_cert else None
        cert_factor = 2.0 - share if share is not None else 1.0
        return {"specs": len(specs), "near_duplicate": near, "exceptions": sorted(exc),
                "dup_canon": dup_canon, "dup_own": dup_own,
                "keff": round(sum(k.values()), 6), "keff_best": round(best, 6),
                "certified_share": None if share is None else round(share, 6),
                "breadth_score": round((1.0 + max(0.0, best)) * cert_factor, 6),
                "structural_keys": keys}


def order(pending: list[dict[str, Any]], budget: int, *, assess: Callable[
        [dict[str, Any]], dict[str, Any]], base_key: Callable[[dict[str, Any]], Any],
          credit: float = 0.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Choose `budget` candidates: screen the head of the backpressure order, put independent
    ground first by breadth score, sample near-duplicates at the exploration floor. `credit` is
    the floor carried from earlier passes (returned as `exploration_credit` for the next)."""
    ranked = sorted(pending, key=base_key)
    depth = max(SCREEN_MIN, SCREEN_DEPTH * max(1, budget))
    head, tail = ranked[:depth], ranked[depth:]
    t0 = time.monotonic()
    for c in head:
        c["_breadth"] = assess(c)
    screen_s = time.monotonic() - t0
    fresh = [c for c in head if not c["_breadth"]["near_duplicate"]]
    dups = [c for c in head if c["_breadth"]["near_duplicate"]]
    fresh.sort(key=lambda c: -float(c["_breadth"]["breadth_score"]))
    out, credit = interleave(fresh, dups, budget, credit)
    for c in tail:                     # head exhausted: fall back to the backpressure order
        if len(out) >= budget:
            break
        out.append(c)
    # leftover budget is never left idle: the rest of the near-duplicates fill it, in the
    # backpressure order (released rows leave the queue, so successive passes rotate through)
    used = {id(c) for c in out}
    for c in dups:
        if len(out) >= budget:
            break
        if id(c) not in used:
            out.append(c)
            used.add(id(c))
            credit = 0.0               # saturated ground was sampled anyway: nothing owed
    dup_ids = {id(c) for c in dups}
    return out, {"screened": len(head), "screen_seconds": round(screen_s, 3),
                 "near_duplicates_in_head": len(dups),
                 "duplicate_share_head": round(len(dups) / len(head), 4) if head else None,
                 "unscreened_tail": len(tail),
                 "near_duplicates_released": sum(1 for c in out if id(c) in dup_ids),
                 "exploration_credit": round(credit, 6)}


def interleave(fresh: list[dict[str, Any]], dups: list[dict[str, Any]], budget: int,
               credit: float = 0.0) -> tuple[list[dict[str, Any]], float]:
    """Independent candidates first, with the exploration floor at EXACTLY one in
    EXPLORATION_EVERY released, never more (audit 2026-10-07: a floor of "at least one per pass"
    handed 25-100% of a 1-4 slot budget to near-duplicates). Each pass EARNS budget/10 of a
    near-duplicate slot while any is waiting; whole slots are spent, the fraction carries to the
    next pass (capped at one slot), so a budget of 3 samples saturated ground every fourth pass
    and the long-run share is one in ten whatever the budget. Returns (chosen, credit left)."""
    if budget <= 0:
        return [], credit
    if not dups:
        return fresh[:budget], credit
    earned = credit + budget / EXPLORATION_EVERY
    floor = min(len(dups), int(earned + 1e-9))
    take = fresh[:budget - floor]
    out: list[dict[str, Any]] = []
    di = 0
    for c in take:
        out.append(c)
        if len(out) % EXPLORATION_EVERY == EXPLORATION_EVERY - 1 and di < floor:
            out.append(dups[di])
            di += 1
    out.extend(dups[di:floor])
    return out[:budget], min(1.0, earned - floor)


class BreadthLedger:
    """What this producer released and what it bought in independent ground, per lane."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def released_keys(self) -> set[str]:
        keys: set[str] = set()
        for row in self._rows():
            keys.update(row.get("structural_keys") or [])
        return keys

    def _rows(self, since: datetime | None = None) -> Iterable[dict[str, Any]]:
        try:
            fh = self.path.open(encoding="utf-8")
        except OSError:
            return
        with fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if since is not None and str(r.get("at") or "") < _iso(since):
                    continue
                yield r

    def append(self, rows: Iterable[Mapping[str, Any]]) -> None:
        body = "".join(json.dumps(dict(r), default=str) + "\n" for r in rows)
        if body:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(body)

    def keff_by_source(self) -> dict[str, float]:
        out: defaultdict[str, float] = defaultdict(float)
        for r in self._rows():
            if not r.get("near_duplicate"):
                out[str(r.get("source_id"))] += float(r.get("keff") or 0.0)
        return dict(out)

    def report(self, compute_seconds: Mapping[str, float], meta: Mapping[str, Mapping[str, Any]],
               bmap: BreadthMap | None, last_screen: Mapping[str, Any] | None = None
               ) -> dict[str, Any]:
        """CIVILIZATION_BREADTH.json: duplicate share and delta-k_eff per compute-hour."""
        day = _now() - timedelta(hours=24)
        per: dict[str, Counter[str]] = defaultdict(Counter)
        per_day: dict[str, Counter[str]] = defaultdict(Counter)
        exc: Counter[str] = Counter()
        for r in self._rows():
            sid = str(r.get("source_id"))
            for tgt in ([per[sid], per_day[sid]] if str(r.get("at") or "") >= _iso(day)
                        else [per[sid]]):
                tgt["released"] += 1
                tgt["near_duplicate"] += int(bool(r.get("near_duplicate")))
                tgt["dup_canon_specs"] += int(r.get("dup_canon") or 0)
                tgt["dup_own_specs"] += int(r.get("dup_own") or 0)
                tgt["specs"] += int(r.get("specs") or 0)
                tgt["keff_milli"] += round(1000 * float(r.get("keff") or 0.0)
                                           * (0 if r.get("near_duplicate") else 1))
            exc.update(r.get("exceptions") or [])

        def row(sid: str, c: Counter[str]) -> dict[str, Any]:
            secs = float(compute_seconds.get(sid) or 0.0)
            keff = c["keff_milli"] / 1000.0
            return {"source_id": sid, "civilization": (meta.get(sid) or {}).get("civilization"),
                    "released": c["released"], "near_duplicates": c["near_duplicate"],
                    "duplicate_share": round(c["near_duplicate"] / c["released"], 4)
                    if c["released"] else None,
                    "specs": c["specs"], "specs_on_certified_slots": c["dup_canon_specs"],
                    "specs_already_released": c["dup_own_specs"],
                    "delta_keff": round(keff, 6), "compute_seconds": round(secs, 3),
                    "delta_keff_per_compute_hour": round(keff / (secs / 3600.0), 6)
                    if secs > 0 else "UNMEASURED"}
        lanes = {sid: row(sid, c) for sid, c in sorted(per.items())}
        civ: dict[str, Counter[str]] = defaultdict(Counter)
        for sid, c in per.items():
            civ[str((meta.get(sid) or {}).get("civilization") or "unknown")].update(c)
        tot: Counter[str] = Counter()
        for c in per.values():
            tot.update(c)
        secs_total = sum(float(v or 0.0) for k, v in compute_seconds.items() if k in per)
        totals = row("ALL", tot)
        totals["compute_seconds"] = round(secs_total, 3)
        keff_total = tot["keff_milli"] / 1000.0
        totals["delta_keff_per_compute_hour"] = (round(keff_total / (secs_total / 3600.0), 6)
                                                 if secs_total > 0 else "UNMEASURED")
        saturated = []
        if bmap is not None and bmap.n_cert:
            saturated = [{"family": f, "certificates": n,
                          "certified_share": round(bmap.shares.get(f, 0.0), 4)}
                         for f, n in bmap.fam_cert.most_common() if bmap.shares.get(f, 0) >= 0.1]
        return {"generated_at": _iso(_now()),
                "rule": ("released candidates screened against the certified canon (family x "
                         "instrument slots, family shares), docket_keff's per-cell marginal "
                         "k_eff and this producer's own released structural cells. A "
                         "near-duplicate has every spec on held ground and no exception; it is "
                         "released at the 1-in-10 exploration floor, never dropped. delta_keff "
                         "counts independent releases only, in docket_keff's units "
                         "(effective bets, PRE-judging: an expectation, not a measured gain)"),
                "totals": totals,
                "last_24h": {sid: row(sid, c) for sid, c in sorted(per_day.items())},
                "by_civilization": {k: row(k, c) for k, c in sorted(civ.items())},
                "lanes": lanes, "exceptions_claimed": dict(exc),
                "exceptions_post_evidence": {
                    "F_measured_orthogonality": "UNMEASURED at the producer: needs returns, "
                                                "measured by the judge and allocator",
                    "G_quality_replacement": "UNMEASURED at the producer: needs a verdict on "
                                             "both the incumbent and the candidate"},
                "saturated_families": saturated,
                "certificates_in_canon": bmap.n_cert if bmap is not None else "UNMEASURED",
                "keff_status": bmap.keff_status if bmap is not None else "UNMEASURED",
                "unmeasured": list(bmap.unmeasured) if bmap is not None else
                ["breadth map not loaded"],
                "last_screen": dict(last_screen or {})}
