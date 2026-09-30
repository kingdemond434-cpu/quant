"""ENFORCED BLINDING BETWEEN RESEARCH COHORTS (Tier S layer 4).

The researcher market counts a mechanism as INDEPENDENTLY DISCOVERED when two cohorts that cannot
read each other's output both reach it. "Cannot read" was a sentence until this module. Now it is
a firewall role per seat:

    seat:<name>   the organs whose own code writes data/intelligence/<name>/ (its HOME);
                  forbidden to read data/intelligence/<other>/ for every seat of another cohort

Seats are measured, never listed: a seat is a directory under either intelligence root, or one an
organ's code writes into. A seat's cohort is its epistemology (the caller's `cohort_of`, the same
function the market prices cohorts by). The roles are fed to the existing firewall:

  * STATIC: `firewall.audit` checks every home organ's resolved path strings for another cohort's
    seat (BLIND_READ); this module adds BLIND_TREE, a home organ that walks the WHOLE intelligence
    tree (it can read every cohort at once).
  * RUNTIME: `firewall.register` makes the roles visible to `firewall.may`, and `guard_read` is
    the one-line call a seat organ makes before it opens another seat's file.
  * CONSEQUENCE: `contaminated_pairs` turns the violations into the cohort pairs that are NOT
    blind to each other, and the market stops counting their joint discoveries as independent.

Nothing here reads a discovery file's contents; it reads code and directory names.
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

from libs.tiers import firewall

#: where seat organs live (tests excluded)
SCAN: tuple[str, ...] = ("desks/mt5/research/*.py", "desks/mt5/scripts/*.py", "scripts/*.py",
                         "desks/mt5/side_channels/*.py", "libs/**/*.py")
INTEL_ROOTS: tuple[str, ...] = ("data/intelligence", "desks/mt5/data/intelligence")
_WALKS = ("glob", "rglob", "iterdir", "walk", "listdir", "scandir")


def disk_seats(root: Path, roots: Iterable[str] = INTEL_ROOTS) -> set[str]:
    out: set[str] = set()
    for r in roots:
        d = root / r
        if d.is_dir():
            out |= {p.name for p in d.iterdir() if p.is_dir()}
    return out


def _tree_walker(tree: ast.AST) -> bool:
    """True when the module walks an intelligence ROOT (not one seat) with glob/rglob/iterdir/
    os.walk/listdir/scandir."""
    nodes, consts = firewall.index(tree)
    for n in nodes:
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        if name not in _WALKS:
            continue
        srcs: list[ast.AST] = list(n.args[:1])
        if isinstance(f, ast.Attribute):
            srcs.append(f.value)
        for s in srcs:
            for p in firewall._resolve(s, consts):
                if p.replace("\\", "/").rstrip("/").endswith("intelligence"):
                    return True
    return False


def seat_map(root: Path, globs: Iterable[str] = SCAN,
             roots: Iterable[str] = INTEL_ROOTS) -> dict[str, Any]:
    """organ -> the seats it writes (home), the seats it names (refs), whether it walks the tree;
    seat -> its home organs."""
    known = disk_seats(root, roots)
    organs: dict[str, dict[str, Any]] = {}
    for p in firewall._organs(root, globs):
        rel = p.relative_to(root).as_posix()
        if "/tests/" in f"/{rel}" or rel.startswith("tests/"):
            continue
        text = p.read_text("utf-8", errors="replace")
        if "intelligence" not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        home = {s for t in firewall.written_paths(tree) for s in firewall.seats_in(t)}
        refs = {s for t in firewall.path_strings(tree) for s in firewall.seats_in(t)}
        organs[rel] = {"home": home, "refs": refs, "tree": _tree_walker(tree)}
    seats: dict[str, dict[str, Any]] = {s: {"home_organs": [], "on_disk": True} for s in known}
    for rel, o in organs.items():
        for s in o["home"]:
            seats.setdefault(s, {"home_organs": [], "on_disk": s in known})
            seats[s]["home_organs"].append(rel)
    for o in organs.values():
        o["refs"] = sorted(s for s in o["refs"] if s in seats)
        o["home"] = sorted(o["home"])
    return {"seats": seats, "organs": organs}


def cohort_roles(smap: Mapping[str, Any], cohort_of: Callable[[str], str]
                 ) -> tuple[firewall.Role, ...]:
    """One firewall role per seat that has a home organ: forbidden every other cohort's seats."""
    seats = smap.get("seats") or {}
    cohort = {s: cohort_of(s) for s in seats}
    out: list[firewall.Role] = []
    for s, row in sorted(seats.items()):
        others = tuple(sorted(o for o in seats if cohort[o] != cohort[s]))
        out.append(firewall.Role(
            f"seat:{s}", tuple(sorted(set(row.get("home_organs") or []))),
            forbid_seats=others,
            sentence=f"Seat {s} (cohort {cohort[s]}) may not read another cohort's "
                     "data/intelligence output."))
    return tuple(out)


def contaminated_pairs(violations: Iterable[Mapping[str, Any]],
                       cohort_of: Callable[[str], str]) -> set[frozenset[str]]:
    """Cohort pairs that are not blind to each other, from BLIND_READ violations. A BLIND_TREE
    organ contaminates its cohort with every other cohort (`*`)."""
    out: set[frozenset[str]] = set()
    for v in violations:
        role = str(v.get("role") or "")
        if not role.startswith("seat:"):
            continue
        mine = cohort_of(role.removeprefix("seat:"))
        if v.get("kind") == "BLIND_READ":
            other = cohort_of(str(v.get("token") or ""))
            if other != mine:
                out.add(frozenset((mine, other)))
        elif v.get("kind") == "BLIND_TREE":
            out.add(frozenset((mine, "*")))
    return out


def audit(root: Path, cohort_of: Callable[[str], str], *, register: bool = True,
          globs: Iterable[str] = SCAN) -> dict[str, Any]:
    smap = seat_map(root, globs)
    roles = cohort_roles(smap, cohort_of)
    if register:
        firewall.register(roles)
    homed = [r for r in roles if r.organs]
    rep = firewall.audit(root, homed)
    viol = list(rep["violations"])
    for r in homed:
        for organ in r.organs:
            if (smap["organs"].get(organ) or {}).get("tree"):
                viol.append({"role": r.name, "organ": organ, "kind": "BLIND_TREE",
                             "token": "data/intelligence/**", "rule": r.sentence})
    cohorts: dict[str, list[str]] = {}
    for s in smap["seats"]:
        cohorts.setdefault(cohort_of(s), []).append(s)
    pairs = contaminated_pairs(viol, cohort_of)
    return {"n_seats": len(smap["seats"]), "n_homed_seats": len(homed),
            "n_cohorts": len(cohorts),
            "cohorts": {c: sorted(v) for c, v in sorted(cohorts.items())},
            "home_organs": {r.name: list(r.organs) for r in homed},
            "violations": viol, "n_violations": len(viol),
            "contaminated_pairs": sorted(sorted(p) for p in pairs),
            "roles": [r.name for r in roles], "registered": len(roles) if register else 0}


def guard_read(seat: str, target: str) -> None:
    """The runtime call: a seat organ asks before it reads another seat's file. Raises
    `firewall.FirewallError` when the target belongs to another cohort (roles must have been
    registered by `audit` or `firewall.register`)."""
    firewall.may(f"seat:{seat}", "read", target.replace("\\", "/"))


def is_blind(a: str, b: str, pairs: set[frozenset[str]]) -> bool:
    return a != b and frozenset((a, b)) not in pairs and frozenset((a, "*")) not in pairs \
        and frozenset((b, "*")) not in pairs


# ------------------------------------------------------------------------------------------------
# RUNTIME BLINDING: what a proposer READS carries no held-out, lockbox or forward outcome
# ------------------------------------------------------------------------------------------------
#
# The audit above proves which organs can open which seat's files. It cannot stop an organ from
# being HANDED an outcome: a cold context carrying a certificate's held-out Sharpe, a donated row
# carrying the forward clock's exp_r, a crawler row echoing a gate verdict. A proposer that saw
# the held-out answer is not proposing blind, and its "discovery" of a cell that then passes the
# same held-out test is a copy of the answer, not evidence.
#
# So every door a proposer reads or writes through strips the desk's OUTCOME fields and counts
# them:
#
#   * libs/ops/deepseek_cycle.cold_context      the LLM seat's prompt context   (stage "context")
#   * research/proposer_common.donate           every proposer's write door     (stage "output")
#   * research/miner_candidate_compiler         the hypothesis compiler's read of
#                                               data/intelligence/**            ("compiler_read")
#
# Each door appends one line per pass to RUNTIME_LEDGER. `organ_market` (tier_s.py) publishes the
# counter in MARKET.json, and the CONSEQUENCE: a seat whose own OUTPUT carried outcome fields had
# the answer when it proposed, so its passes are withheld from the market's independent-discovery
# count exactly like a cohort pair that can read each other's output.
#
# What is an OUTCOME: a field whose value is the desk's verdict on data the proposer must not
# have seen -- lockbox and held-out results, out-of-sample scores, forward-clock and live
# results, gate/gauntlet verdicts and certificates. What is NOT: a source's own claimed
# statistics (a signal page's win rate, a paper's Sharpe), in-sample screens the proposer ran
# itself, survivor SPECS, schemas and portfolio state. Those are facts a proposer may use
# (deepseek_cycle's cold phase keeps them on purpose: starved is not independent).

#: a key is an OUTCOME when any of its separator-split tokens is one of these
OUTCOME_TOKENS: frozenset[str] = frozenset({
    "lockbox", "holdout", "heldout", "oos", "outofsample", "gauntlet", "certificate",
    "certificates", "certified", "verdict", "verdicts"})
#: adjacent token pairs (joined) that are outcomes
OUTCOME_PAIRS: frozenset[str] = frozenset({
    "heldout", "holdout", "outof", "terminalgate", "gatevote", "gatevotes", "gateresult",
    "gateresults", "gatepassed", "passedgates", "failedgates", "livepnl", "liver", "liveexp",
    "realizedr", "realisedr"})
#: forward-clock outcomes: `forward_`/`fwd_` followed by one of these
FORWARD_OUTCOMES: frozenset[str] = frozenset({
    "exp", "expr", "r", "n", "sharpe", "sr", "pnl", "verdict", "holds", "passed", "win",
    "winrate", "clock", "result", "results", "ledger", "state"})
#: keys that are outcomes by their exact spelling
OUTCOME_KEYS: frozenset[str] = frozenset({
    "passed_gauntlet", "universal_survivor", "shadow_state", "live_ledger", "pbo"})
RUNTIME_LEDGER = "desks/mt5/data/tier_s/blinding_runtime.jsonl"
#: a proposer's output carrying outcomes is evidence it read them; these stages count against it
OUTPUT_STAGES: frozenset[str] = frozenset({"output", "compiler_read"})
_SPLIT = re.compile(r"[^a-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_MAX_DEPTH = 8


def is_outcome_key(key: Any) -> bool:
    raw = _CAMEL.sub("_", str(key).strip())
    low = raw.lower()
    if not low:
        return False
    if low in OUTCOME_KEYS:
        return True
    toks = [t for t in _SPLIT.split(low) if t]
    if any(t in OUTCOME_TOKENS for t in toks):
        return True
    if any(a + b in OUTCOME_PAIRS for a, b in pairwise(toks)):
        return True
    if len(toks) >= 2 and toks[0] in ("forward", "fwd"):
        return toks[1] in FORWARD_OUTCOMES or "".join(toks[1:3]) in FORWARD_OUTCOMES
    return False


def strip_outcomes(obj: Any, _path: str = "", _depth: int = 0) -> tuple[Any, list[str]]:
    """A copy of `obj` with every outcome-keyed field removed at any depth, and the dotted paths
    removed. Lists are walked; scalars pass through. Never mutates the input."""
    if _depth > _MAX_DEPTH:
        return obj, []
    if isinstance(obj, Mapping):
        out: dict[Any, Any] = {}
        gone: list[str] = []
        for k, v in obj.items():
            p = f"{_path}.{k}" if _path else str(k)
            if is_outcome_key(k):
                gone.append(p)
                continue
            out[k], sub = strip_outcomes(v, p, _depth + 1)
            gone.extend(sub)
        return out, gone
    if isinstance(obj, list):
        items: list[Any] = []
        gone = []
        for i, v in enumerate(obj):
            nv, sub = strip_outcomes(v, f"{_path}[{i}]", _depth + 1)
            items.append(nv)
            gone.extend(sub)
        return items, gone
    return obj, []


class RuntimeCounter:
    """One door's pass: per seat, rows seen, rows that carried outcomes (the VIOLATIONS), fields
    stripped and the commonest outcome keys. `filter` is the enforcement; `publish` the
    measurement."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.seats: dict[str, dict[str, Any]] = {}

    def filter(self, seat: str, row: Any) -> Any:
        clean, gone = strip_outcomes(row)
        d = self.seats.setdefault(str(seat), {"rows": 0, "rows_with_outcomes": 0,
                                              "fields_stripped": 0, "keys": Counter()})
        d["rows"] += 1
        if gone:
            d["rows_with_outcomes"] += 1
            d["fields_stripped"] += len(gone)
            for g in gone:
                d["keys"][re.sub(r"\[\d+\]", "", g).rsplit(".", 1)[-1]] += 1
        return clean

    def report(self) -> dict[str, Any]:
        seats = {s: {"rows": d["rows"], "rows_with_outcomes": d["rows_with_outcomes"],
                     "fields_stripped": d["fields_stripped"],
                     "keys": dict(d["keys"].most_common(8))}
                 for s, d in sorted(self.seats.items())}
        return {"stage": self.stage, "seats": seats,
                "rows": sum(d["rows"] for d in seats.values()),
                "violations": sum(d["rows_with_outcomes"] for d in seats.values()),
                "fields_stripped": sum(d["fields_stripped"] for d in seats.values())}

    def publish(self, root: Path, ledger: str = RUNTIME_LEDGER) -> dict[str, Any]:
        """Append this pass to the runtime ledger (one line; history is never rewritten)."""
        rep = {"at": datetime.now(UTC).isoformat(timespec="seconds"), **self.report()}
        record(root, rep, ledger)
        return rep


def record(root: Path, rep: Mapping[str, Any], ledger: str = RUNTIME_LEDGER) -> None:
    """Best-effort append. A door that cannot write its counter still strips: the filter is the
    enforcement, the ledger only its measurement."""
    try:
        p = root / ledger
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(rep), default=str, sort_keys=True) + "\n")
    except OSError:
        pass


def runtime_summary(rows: Iterable[Mapping[str, Any]], since: datetime | None = None
                    ) -> dict[str, Any]:
    """The runtime ledger (rows at or after `since`) per stage and per seat.
    `output_violators`: seats whose OWN OUTPUT carried outcome fields."""
    stages: dict[str, dict[str, int]] = {}
    per_seat: dict[str, dict[str, int]] = {}
    passes = 0
    for r in rows:
        if since is not None:
            try:
                t = datetime.fromisoformat(str(r.get("at")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if (t if t.tzinfo else t.replace(tzinfo=UTC)) < since:
                continue
        passes += 1
        st = str(r.get("stage") or "?")
        s = stages.setdefault(st, {"passes": 0, "rows": 0, "violations": 0,
                                   "fields_stripped": 0})
        s["passes"] += 1
        for k in ("rows", "violations", "fields_stripped"):
            s[k] += int(r.get(k) or 0)
        for seat, d in (r.get("seats") or {}).items():
            if not isinstance(d, Mapping):
                continue
            ps = per_seat.setdefault(str(seat), {"rows": 0, "violations": 0,
                                                 "output_violations": 0})
            ps["rows"] += int(d.get("rows") or 0)
            v = int(d.get("rows_with_outcomes") or 0)
            ps["violations"] += v
            if st in OUTPUT_STAGES:
                ps["output_violations"] += v
    return {"passes": passes, "stages": stages,
            "violations": sum(s["violations"] for s in stages.values()),
            "per_seat": {k: v for k, v in sorted(per_seat.items()) if v["violations"]},
            "output_violators": sorted(k for k, v in per_seat.items()
                                       if v["output_violations"])}


def runtime_contaminated(output_violators: Iterable[str], cohort_of: Callable[[str], str]
                         ) -> set[frozenset[str]]:
    """A seat whose output carried the desk's outcomes saw the answer: its cohort is blind to
    nothing (`*`), so none of its passes count toward an independent rediscovery."""
    return {frozenset((cohort_of(str(s)), "*")) for s in output_violators}
