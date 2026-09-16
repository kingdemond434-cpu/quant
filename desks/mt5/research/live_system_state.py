"""LIVE_SYSTEM_STATE -- one document that answers what is actually trading, right now.

THE DESK'S TRUTH WAS SPLIT ACROSS A DOZEN FILES, each true about a different thing.
`release_identity.json` knows which commit the gateway IMPORTED; `RELEASE.json` knows which was
SEALED; `sleeves.json` knows which rows the promoter BELIEVES are live; `pf_allocation.json` and
`ALLOCATOR_PROOF.json` know the heat the allocator SOLVED FOR and whether its certificate still
holds; `gateway_state.json` knows what the terminal is HOLDING; `live_ledger.jsonl` knows what
the account actually DID. Nothing joined them, so the question a session asks first -- "what code
is trading, on what sleeves, with what risk, under which allocator state and which promotion
state" -- had five answers to reconcile by hand, every hour, and a session that reconciled them
wrong shipped on a fact that was stale.

DISCOVERY IS NOT DEPLOYED CODE AND DEPLOYED CODE IS NOT LIVE STATE. A certificate is a discovery,
a sealed release is deployed code, a LIVE row the gateway placed against is live state. They
drift apart legitimately -- the box adopts on its own clock, the promoter re-judges on its own,
the certificate expires on its own -- so all three are reported SEPARATELY and never averaged.
The one cross-fact asserted here is the cheapest and most load-bearing: `running_matches_sealed`,
HEAD against the sealed SHA, which is None (not False) whenever either side is unknown.

ABSENCE IS UNMEASURED, NEVER A DEFAULT (L1.28a). Every input may be missing on some host. A
missing or unparsable one yields status UNMEASURED, is named in `unmeasured`, and appears in
`sources` with its path, presence and age -- it never becomes a zero, an empty list or a False,
because a zero that means "absent" is the lie this organ exists to stop telling.

THE PROVENANCE ENVELOPE makes the document self-describing: `config_hash` fingerprints WHICH
files were read and their (path, mtime, size), `input_hash` WHAT they held, `output_hash` the
document itself. Two documents with one `input_hash` were built from identical inputs.

WHAT THIS IS NOT: it reads and joins. It decides nothing, sizes nothing and gates nothing, so it
can never reduce the book's aggressiveness or be the reason a trade is not placed.

    python live_system_state.py            write the document, print a 12-line summary
    python live_system_state.py --dry-run  print the summary only, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent

#: The inputs, by the name each carries in `sources`. A tuple means "first one that exists wins":
#: the same fact is written to different paths on the VPS and on the trading box.
RELEASE_IDENTITY = DESK / "data" / "release_identity.json"
RELEASE_PATHS = (DESK / "data" / "RELEASE.json", ROOT / "RELEASE.json", DESK / "RELEASE.json")
GATEWAY_STATE = DESK / "data" / "gateway_state.json"
SLEEVES = DESK / "data" / "sleeves.json"
PF_ALLOCATION = DESK / "reports" / "pf_allocation.json"
ALLOCATOR_PROOF_PATHS = (ROOT / "reports" / "ALLOCATOR_PROOF.json",
                         DESK / "reports" / "ALLOCATOR_PROOF.json")
SYNC_MARKER = DESK / "data" / "sync_marker.json"
STALL_WATCH = DESK / "data" / "stall_watch.json"
BANNED_FAMILIES = DESK / "data" / "banned_families.json"
FORWARD_RECONCILE = DESK / "data" / "forward_reconcile.json"
SHADOW_STATE = DESK / "reports" / "shadow" / "shadow_state.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
GATE_ATTESTATION_PATHS = (DESK / "data" / "gate_attestation.json",
                          ROOT / "data" / "gate_attestation.json")
CLOSED_LOOP = DESK / "data" / "architecture" / "closed_loop_attestation.json"
E8_ARMED = DESK / "data" / "E8_GOLD_ARMED"
E8_GOLD = DESK / "reports" / "E8_GOLD.json"
OUT = DESK / "data" / "LIVE_SYSTEM_STATE.json"

UNMEASURED = "UNMEASURED"
GIT_TIMEOUT_S = 20.0
#: The certificate's own expiry when ALLOCATOR_PROOF.json does not publish `max_age_s`.
ALLOCATOR_MAX_AGE_S = 93600.0
LEDGER_WINDOW_H = 24.0
GENERATED_BY = "desks/mt5/research/live_system_state.py"
LIVE_FIELDS = ("name", "family", "symbol", "timeframe", "session", "risk_frac", "lot")
IDENT_FIELDS = ("running_sha", "release_id", "verdict", "ok", "allows_new_risk", "stale",
                "tested_sha")
MANIFEST_FIELDS = ("generated_utc", "live_sha", "code_sha", "tree_sha", "config_hash",
                   "money_path_hash", "survivor_registry_hash", "data_schema_version")
HEAT_FIELDS = ("target", "resolved", "total", "held", "free_optimum")
EXEC_FIELDS = ("armed", "equity", "lot", "last_bracket_date", "bracket_cancelled",
               "last_reconcile")
GATE_FIELDS = ("result", "tested_sha", "gates", "at", "tree_clean", "dirty_paths")
RULE = (
    "One canonical join, rebuilt on the hour from the files that own each fact. Discovery is not "
    "deployed code and deployed code is not live state: the three are reported separately and "
    "never averaged. An absent or unreadable input is UNMEASURED, is named in `unmeasured`, and "
    "never resolves to a default. This organ reads and joins -- it decides nothing, sizes "
    "nothing and gates nothing."
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _age_h(value: Any, now: datetime) -> float | str:
    parsed = _parse_dt(value)
    return UNMEASURED if parsed is None else round((now - parsed).total_seconds() / 3600.0, 2)


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick(doc: Any, *keys: str, default: Any = UNMEASURED) -> Any:
    """Nested read that answers UNMEASURED rather than raising or inventing a zero."""
    cur = doc
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return default if cur is None else cur


def _fields(doc: Any, *names: str) -> dict[str, Any]:
    """Lift a published block wholesale: every named field, UNMEASURED where it is absent."""
    return {name: _pick(doc, name) for name in names}


def _first(*values: Any) -> Any:
    """The first value that was actually measured -- how a fact with two homes is resolved."""
    return next((v for v in values if v is not None and v != UNMEASURED), UNMEASURED)


def _len(value: Any) -> Any:
    return len(value) if isinstance(value, (list, dict)) else UNMEASURED


def _status(*present: bool) -> str:
    return "MEASURED" if all(present) else ("PARTIAL" if any(present) else UNMEASURED)


def _clip(value: Any, limit: int = 300) -> Any:
    return value[:limit] if isinstance(value, str) and len(value) > limit else value


class Inputs:
    """Every file this pass opened, what it held, and whether it was there at all.

    The hashes cover exactly the inputs ATTEMPTED (present or not), so a file appearing moves
    `config_hash` just as surely as a file changing moves `input_hash`.
    """

    ABSENT = b"\x00ABSENT"

    def __init__(self, now: datetime) -> None:
        self.now = now
        self.sources: dict[str, dict[str, Any]] = {}
        self._stat: list[list[Any]] = []
        self._blob: list[tuple[str, bytes]] = []

    def blob(self, name: str, *paths: Path) -> bytes | None:
        chosen, raw = Path(paths[0]), None
        for candidate in paths:
            try:
                raw, chosen = Path(candidate).read_bytes(), Path(candidate)
                break
            except (OSError, ValueError):
                continue
        self._record(name, chosen, raw)
        return raw

    def json(self, name: str, *paths: Path) -> Any:
        raw = self.blob(name, *paths)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8-sig", errors="replace"))
        except (ValueError, UnicodeDecodeError) as exc:
            self.sources[name]["readable"] = False
            self.sources[name]["why"] = f"{type(exc).__name__}: {exc}"[:160]
            return None

    def _record(self, name: str, path: Path, raw: bytes | None) -> None:
        mtime_iso: Any = UNMEASURED
        age_h: Any = UNMEASURED
        mtime, size = -1, -1
        if raw is not None:
            try:
                stat = path.stat()
                mtime, size = int(stat.st_mtime), int(stat.st_size)
                stamp = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                mtime_iso = stamp.isoformat(timespec="seconds")
                age_h = round(max(0.0, self.now.timestamp() - stat.st_mtime) / 3600.0, 2)
            except (OSError, OverflowError, ValueError):
                pass
        self.sources[name] = {"path": str(path), "present": raw is not None,
                              "readable": raw is not None, "mtime": mtime_iso, "age_h": age_h,
                              "bytes": size if size >= 0 else UNMEASURED}
        self._stat.append([str(path), mtime, size])
        self._blob.append((str(path), self.ABSENT if raw is None else raw))

    def config_hash(self) -> str:
        payload = json.dumps(sorted(self._stat, key=str), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def input_hash(self) -> str:
        digest = hashlib.sha256()
        for path, raw in sorted(self._blob, key=lambda row: row[0]):
            digest.update(path.encode("utf-8") + b"\x00" + hashlib.sha256(raw).digest())
        return digest.hexdigest()


def _git(*args: str) -> str | None:
    """One git question, bounded. Any failure is None, which the caller reads as UNMEASURED."""
    try:
        proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                              timeout=GIT_TIMEOUT_S, check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None if proc.returncode != 0 else (proc.stdout or "").strip()


def git_facts() -> dict[str, Any]:
    porcelain = _git("status", "--porcelain")
    dirty: Any = UNMEASURED
    if porcelain is not None:
        dirty = len([line for line in porcelain.splitlines() if line.strip()])
    return {"commit_sha": _git("rev-parse", "HEAD") or UNMEASURED,
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or UNMEASURED,
            "dirty_paths": dirty,
            "tree_clean": (dirty == 0) if isinstance(dirty, int) else UNMEASURED}


def _release_section(identity: Any, manifest: Any, now: datetime) -> dict[str, Any]:
    ident = identity if isinstance(identity, dict) else {}
    man = manifest if isinstance(manifest, dict) else {}
    if not ident and not man:
        return {"status": UNMEASURED, "sealed_sha": UNMEASURED, "running_sha": UNMEASURED,
                "why": "neither release_identity.json nor RELEASE.json was readable"}
    drift = ident.get("drift")
    return {
        "status": _status(bool(ident), bool(man)), **_fields(ident, *IDENT_FIELDS),
        "sealed_sha": _first(_pick(ident, "release_sha"), _pick(man, "live_sha"),
                             _pick(man, "code_sha")),
        "identity_at": _pick(ident, "at"), "identity_age_h": _age_h(ident.get("at"), now),
        "allocator_certificate": _clip(_pick(ident, "allocator_certificate")),
        "changed_paths_n": _len(ident.get("changed_paths")),
        "money_path_drift": drift if isinstance(drift, list) else UNMEASURED,
        "why": _clip(_pick(ident, "reason")),
        "manifest": {**_fields(man, *MANIFEST_FIELDS),
                     "age_h": _age_h(man.get("generated_utc"), now),
                     "money_path_n": _len(man.get("money_path"))} if man else UNMEASURED,
    }


def _sleeves_section(doc: Any) -> dict[str, Any]:
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return {"status": UNMEASURED, "why": "sleeves.json absent or carries no `sleeves` list",
                "n_live": UNMEASURED, "n_standby": UNMEASURED, "n_retired": UNMEASURED,
                "live": UNMEASURED}
    rows = [row for row in rows if isinstance(row, dict)]
    counts = Counter(str(row.get("status") or UNMEASURED).upper() for row in rows)
    live = sorted((_fields(row, *LIVE_FIELDS) for row in rows
                   if str(row.get("status") or "").upper() == "LIVE"),
                  key=lambda row: str(row.get("name")))
    return {"status": "MEASURED", "n_total": len(rows), "n_live": counts.get("LIVE", 0),
            "n_standby": counts.get("STANDBY", 0),
            "n_retired": sum(n for name, n in counts.items() if "RETIRE" in name),
            "by_status": dict(sorted(counts.items())), "live": live}


def _fractions(book: Any) -> dict[str, Any]:
    if not isinstance(book, dict):
        return {"status": UNMEASURED, "why": "no allocator book published"}
    fracs = {str(k): float(v) for k, v in book.items() if _num(v) is not None}
    top = sorted(fracs.items(), key=lambda row: -row[1])[:5]
    return {"status": "MEASURED", "n": len(fracs),
            "n_funded": sum(1 for value in fracs.values() if value > 0.0),
            "total_heat": round(sum(fracs.values()), 6),
            "top": [{"sleeve": name, "frac": round(value, 6)} for name, value in top]}


def _allocator_section(proof: Any, allocation: Any, now: datetime) -> dict[str, Any]:
    body = proof if isinstance(proof, dict) else {}
    alloc = allocation if isinstance(allocation, dict) else {}
    if not body and not alloc:
        return {"status": UNMEASURED, "at": UNMEASURED, "passed": UNMEASURED, "stale": UNMEASURED,
                "why": "neither ALLOCATOR_PROOF.json nor pf_allocation.json was readable"}
    at = _first(_pick(body, "at"), _pick(alloc, "generated_utc"))
    max_age = _num(body.get("max_age_s")) or ALLOCATOR_MAX_AGE_S
    age = _age_h(at, now)
    book = body.get("book") if isinstance(body.get("book"), dict) else alloc.get("book")
    return {"status": _status(bool(body), bool(alloc)), "at": at, "age_h": age,
            "passed": _first(_pick(body, "passed"), _pick(alloc, "proof", "passed")),
            "stale": bool(age * 3600.0 > max_age) if isinstance(age, float) else UNMEASURED,
            "max_age_s": max_age, "why": _clip(_pick(body, "why")),
            **_fields(body, "best_baseline", "margin_frac", "hysteresis"),
            **_fields(alloc, "mode", "armed", "advisory"), "fractions": _fractions(book)}


def _daily_loss(gateway: Any, sleeves_doc: Any) -> dict[str, Any]:
    """Whatever daily-loss parameter the two registries publish -- named, never invented."""
    found = {f"{name}.{key}": value
             for name, doc in (("gateway_state", gateway), ("sleeves", sleeves_doc))
             if isinstance(doc, dict)
             for key, value in doc.items()
             if "daily" in str(key).lower() and isinstance(value, (int, float, str, bool))}
    if found:
        return {"status": "MEASURED", "params": found}
    return {"status": UNMEASURED,
            "why": "no daily-loss parameter is published in gateway_state.json or sleeves.json"}


def _risk_section(allocation: Any, proof: Any, gateway: Any, sleeves_doc: Any,
                  sleeves: dict[str, Any]) -> dict[str, Any]:
    alloc = allocation if isinstance(allocation, dict) else {}
    heat = alloc.get("heat") if isinstance(alloc.get("heat"), dict) else {}
    aggr = alloc.get("aggression") if isinstance(alloc.get("aggression"), dict) else {}
    live = sleeves.get("live")
    per_sleeve: Any = UNMEASURED
    total: Any = UNMEASURED
    if isinstance(live, list):
        per_sleeve = {str(row.get("name")): row.get("risk_frac") for row in live}
        values = [_num(row.get("risk_frac")) for row in live]
        total = round(sum(value for value in values if value is not None), 6)
    return {"status": _status(bool(alloc), isinstance(live, list)),
            "heat": {"floor": _first(_pick(aggr, "floor"), _pick(heat, "target")),
                     "ceiling": _first(_pick(aggr, "ceiling"), _pick(heat, "hard_ceiling"),
                                       _pick(heat.get("envelope"), "growth_ceiling")),
                     **_fields(heat, *HEAT_FIELDS),
                     "source": "pf_allocation.json" if heat else UNMEASURED},
            "proof_passed": _pick(proof, "passed") if isinstance(proof, dict) else UNMEASURED,
            "daily_loss": _daily_loss(gateway, sleeves_doc),
            "risk_frac_by_live_sleeve": per_sleeve, "risk_frac_live_total": total,
            "equity": _pick(gateway, "equity") if isinstance(gateway, dict) else UNMEASURED}


def _promotion_section(banned: Any, shadow: Any, reconcile: Any) -> dict[str, Any]:
    families: Any = UNMEASURED
    reasons: Any = UNMEASURED
    node = banned.get("banned") if isinstance(banned, dict) else None
    if isinstance(node, (dict, list)):
        families = sorted(str(key) for key in node)
        reasons = ({str(k): _clip(_pick(v, "why")) for k, v in node.items()}
                   if isinstance(node, dict) else {})
    clocks: Any = UNMEASURED
    rows = [row for row in shadow.values() if isinstance(row, dict)] if isinstance(
        shadow, dict) else None
    if rows is not None:
        clocks = dict(sorted(Counter(str(_pick(row, "status")) for row in rows).items()))
    rec = reconcile if isinstance(reconcile, dict) else {}
    unreachable = rec.get("unreachable_certified")
    if isinstance(unreachable, dict):
        unreachable = _pick(unreachable, "n")
    return {"status": _status(families is not UNMEASURED, rows is not None, bool(rec)),
            "banned_families": families, "banned_why": reasons,
            "forward_clocks_by_status": clocks,
            "n_forward_clocks": len(rows) if rows is not None else UNMEASURED,
            "unreachable_certified": UNMEASURED if unreachable is None else unreachable,
            **_fields(rec, "identity_unfrozen", "enrolled", "certified_clocks"),
            "reconciled_at": _pick(rec, "checked_at")}


def _ledger_24h(raw: bytes | None, now: datetime) -> dict[str, Any]:
    if raw is None:
        return {"status": UNMEASURED, "why": "live_ledger.jsonl absent or unreadable",
                "deals": UNMEASURED, "sum_r": UNMEASURED, "by_sleeve": UNMEASURED}
    cutoff = now - timedelta(hours=LEDGER_WINDOW_H)
    deals, total_r, unparsed = 0, 0.0, 0
    by_sleeve: dict[str, dict[str, float]] = {}
    for line in raw.decode("utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if not isinstance(row, dict):
            unparsed += 1
            continue
        stamp = _parse_dt(row.get("time"))
        if stamp is None or stamp < cutoff:
            continue
        deals += 1
        value = _num(row.get("r_multiple")) or 0.0
        total_r += value
        entry = by_sleeve.setdefault(str(row.get("sleeve") or UNMEASURED), {"n": 0, "r": 0.0})
        entry["n"], entry["r"] = entry["n"] + 1, round(entry["r"] + value, 6)
    return {"status": "MEASURED", "window_h": LEDGER_WINDOW_H, "deals": deals,
            "sum_r": round(total_r, 6), "unparsed_lines": unparsed,
            "by_sleeve": dict(sorted(by_sleeve.items()))}


def _execution_section(gateway: Any, ledger: bytes | None, now: datetime) -> dict[str, Any]:
    gw = gateway if isinstance(gateway, dict) else {}
    return {"status": _status(bool(gw), ledger is not None), **_fields(gw, *EXEC_FIELDS),
            "last_pass_at": _pick(gw, "placement_pass"),
            "last_pass_age_h": _age_h(gw.get("placement_pass"), now),
            "positions": _len(gw.get("position")), "pending_orders": _len(gw.get("pending")),
            "live_24h": _ledger_24h(ledger, now)}


def _attestation_section(gate: Any, closed: Any, now: datetime) -> dict[str, Any]:
    gate_doc = gate if isinstance(gate, dict) else {}
    loop = closed if isinstance(closed, dict) else {}
    node = loop.get("summary") if isinstance(loop.get("summary"), dict) else {}
    gate_out: Any = {"status": UNMEASURED, "why": "no gate_attestation.json on either path"}
    if gate_doc:
        gate_out = {**_fields(gate_doc, *GATE_FIELDS), "sha": _pick(gate_doc, "tested_sha"),
                    "age_h": _age_h(gate_doc.get("at"), now)}
    loop_out: Any = {"status": UNMEASURED, "why": "no closed_loop_attestation.json"}
    if loop:
        loop_out = {**_fields(loop, "at", "architecture_28_implemented"),
                    "age_h": _age_h(loop.get("at"), now),
                    **_fields(node, "true", "false", "unmeasured"),
                    "n_open": _len(node.get("open"))}
    return {"status": _status(bool(gate_doc), bool(loop)), "gate": gate_out,
            "closed_loop": loop_out}


def _e8_section(armed: bytes | None, doc: Any) -> dict[str, Any]:
    body = doc if isinstance(doc, dict) else {}
    return {"status": "MEASURED" if body else UNMEASURED, "armed": armed is not None,
            "armed_why": "the marker's absence IS the unarmed state (prop/e8_gold.py), not an "
                         "absent measurement; `status` speaks for the E8_GOLD.json report",
            "armed_marker": str(E8_ARMED), "report_status": _pick(body, "status"),
            "at": _pick(body, "at"), "report_armed": _pick(body, "armed"),
            "equity": _pick(body, "equity"), "placed": _len(body.get("placed"))}


def _box_section(stall: Any, sync: Any, now: datetime) -> dict[str, Any]:
    watch = stall if isinstance(stall, dict) else {}
    memory = watch.get("memory") if isinstance(watch.get("memory"), dict) else {}
    marker = sync if isinstance(sync, dict) else {}
    legs = [row for row in marker.values() if isinstance(row, dict) and "exit_code" in row]
    codes = Counter("ok" if row.get("exit_code") == 0
                    else ("unfinished" if row.get("exit_code") is None else "failed")
                    for row in legs)
    mem: Any = {"status": UNMEASURED, "why": "no stall_watch.json"}
    if watch:
        mem = {**_fields(memory, "total_phys_mb", "free_phys_mb", "free_commit_mb"),
               "checked_at": _pick(watch, "checked_at"),
               "age_h": _age_h(watch.get("checked_at"), now),
               "actions_n": _len(watch.get("actions"))}
    cycle: Any = {"status": UNMEASURED, "why": "no sync_marker.json"}
    if marker:
        cycle = {"last_cycle": _pick(marker, "last_cycle"),
                 "age_h": _age_h(marker.get("last_cycle"), now), "legs": len(legs),
                 "ok": codes.get("ok", 0), "failed": codes.get("failed", 0),
                 "unfinished": codes.get("unfinished", 0)}
    return {"status": _status(bool(watch), bool(marker)), "memory": mem, "cycle": cycle}


def _unmeasured(doc: dict[str, Any], inputs: Inputs) -> list[str]:
    names = {name for name, row in inputs.sources.items()
             if not row.get("present") or not row.get("readable")}
    envelope = doc["envelope"]
    names.update(f"envelope.{key}" for key in ("commit_sha", "branch", "sealed_sha", "tree_clean")
                 if envelope.get(key) == UNMEASURED)
    if envelope.get("running_matches_sealed") is None:
        names.add("envelope.running_matches_sealed")
    names.update(section for section, body in doc.items()
                 if isinstance(body, dict) and body.get("status") == UNMEASURED)
    return sorted(names)


def _document_hash(doc: dict[str, Any]) -> str:
    """sha256 of the whole document with `envelope.output_hash` removed -- self-verifiable."""
    envelope = {k: v for k, v in doc.get("envelope", {}).items() if k != "output_hash"}
    shadow = {k: (envelope if k == "envelope" else v) for k, v in doc.items()}
    payload = json.dumps(shadow, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _key_facts(doc: Any) -> dict[str, Any]:
    live = _pick(doc, "sleeves", "live", default=None) if isinstance(doc, dict) else None
    return {"commit_sha": _pick(doc, "envelope", "commit_sha"),
            "sealed_sha": _pick(doc, "envelope", "sealed_sha"),
            "live_sleeves": sorted(str(row.get("name")) for row in live if isinstance(row, dict))
            if isinstance(live, list) else None,
            "banned_families": _pick(doc, "promotion", "banned_families", default=None),
            "allocator_passed": _pick(doc, "allocator", "passed")}


def diff_since_previous(doc: dict[str, Any], previous: Any) -> list[str]:
    """What changed against the document this one replaces -- the facts a session acts on."""
    if not isinstance(previous, dict) or not previous:
        return [f"{UNMEASURED}: no previous LIVE_SYSTEM_STATE.json to compare against"]
    fresh, was = _key_facts(doc), _key_facts(previous)
    changes = [f"{key}: {was.get(key)} -> {fresh.get(key)}"
               for key in ("commit_sha", "sealed_sha", "allocator_passed")
               if fresh.get(key) != was.get(key)]
    for key, label in (("live_sleeves", "live sleeve"), ("banned_families", "banned family")):
        new_set, old_set = fresh.get(key), was.get(key)
        if not isinstance(new_set, list) or not isinstance(old_set, list):
            if new_set != old_set:
                changes.append(f"{label} set: {old_set} -> {new_set}")
            continue
        for verb, moved in (("added", sorted(set(new_set) - set(old_set))),
                            ("removed", sorted(set(old_set) - set(new_set)))):
            if moved:
                changes.append(f"{label} {verb} ({len(moved)}): {moved[:8]}")
    return changes or [f"no change in the key facts since {_pick(previous, 'envelope', 'at')}"]


def _previous() -> Any:
    """The document this pass replaces. Read OUTSIDE `Inputs` on purpose: it is the diff
    baseline, not an input, and hashing it would make every hour's input_hash unique."""
    try:
        return json.loads(OUT.read_bytes().decode("utf-8-sig", errors="replace"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def build(now: datetime | None = None) -> dict[str, Any]:
    """Join every source into one document. Never raises: absence is a verdict."""
    now = now or _now()
    inputs = Inputs(now)
    identity = inputs.json("release_identity", RELEASE_IDENTITY)
    manifest = inputs.json("release_manifest", *RELEASE_PATHS)
    gateway = inputs.json("gateway_state", GATEWAY_STATE)
    sleeves_doc = inputs.json("sleeves", SLEEVES)
    allocation = inputs.json("pf_allocation", PF_ALLOCATION)
    proof = inputs.json("allocator_proof", *ALLOCATOR_PROOF_PATHS)
    sync = inputs.json("sync_marker", SYNC_MARKER)
    stall = inputs.json("stall_watch", STALL_WATCH)
    banned = inputs.json("banned_families", BANNED_FAMILIES)
    reconcile = inputs.json("forward_reconcile", FORWARD_RECONCILE)
    shadow = inputs.json("shadow_state", SHADOW_STATE)
    ledger = inputs.blob("live_ledger", LIVE_LEDGER)
    gate = inputs.json("gate_attestation", *GATE_ATTESTATION_PATHS)
    closed = inputs.json("closed_loop_attestation", CLOSED_LOOP)
    armed = inputs.blob("e8_gold_armed", E8_ARMED)
    e8_doc = inputs.json("e8_gold", E8_GOLD)

    git = git_facts()
    release = _release_section(identity, manifest, now)
    sleeves = _sleeves_section(sleeves_doc)
    head, sealed = git["commit_sha"], release.get("sealed_sha", UNMEASURED)
    try:
        host = socket.gethostname() or UNMEASURED
    except OSError:
        host = UNMEASURED
    doc: dict[str, Any] = {
        "envelope": {"at": now.isoformat(timespec="seconds"), "host": host, **git,
                     "sealed_sha": sealed, "generated_by": GENERATED_BY,
                     "running_matches_sealed": (None if UNMEASURED in (head, sealed)
                                                else bool(head == sealed)),
                     "config_hash": inputs.config_hash(), "input_hash": inputs.input_hash()},
        "release": release,
        "risk": _risk_section(allocation, proof, gateway, sleeves_doc, sleeves),
        "sleeves": sleeves,
        "allocator": _allocator_section(proof, allocation, now),
        "promotion": _promotion_section(banned, shadow, reconcile),
        "execution": _execution_section(gateway, ledger, now),
        "attestation": _attestation_section(gate, closed, now),
        "e8": _e8_section(armed, e8_doc),
        "box": _box_section(stall, sync, now),
        "sources": inputs.sources,
        "unmeasured": [],
        "rule": RULE,
    }
    doc["unmeasured"] = _unmeasured(doc, inputs)
    doc["changes_since_previous"] = diff_since_previous(doc, _previous())
    doc["envelope"]["output_hash"] = _document_hash(doc)
    return doc


def write(doc: dict[str, Any]) -> Path | None:
    """Atomic: a reader never sees half a document, and a crashed pass never truncates one."""
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_name(OUT.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        return OUT
    except OSError as exc:
        print(f"LIVE_SYSTEM_STATE write failed: {type(exc).__name__}: {exc}")
        return None


def summary(doc: dict[str, Any]) -> list[str]:
    """Twelve lines: the whole desk at a glance, in the order a session needs it."""
    env, rel, sle = doc["envelope"], doc["release"], doc["sleeves"]
    risk, alc, pro = doc["risk"], doc["allocator"], doc["promotion"]
    exe, att, e8 = doc["execution"], doc["attestation"], doc["e8"]
    heat, live = risk.get("heat", {}), exe.get("live_24h", {})
    gate, loop = att.get("gate", {}), att.get("closed_loop", {})
    changes = doc.get("changes_since_previous") or ["none"]
    sources = doc.get("sources", {})
    present = sum(1 for row in sources.values() if row.get("present"))
    rows = [
        ("release", f"running={str(env['commit_sha'])[:12]} sealed={str(env['sealed_sha'])[:12]} "
                    f"match={env['running_matches_sealed']} verdict={rel.get('verdict')}"),
        ("tree", f"branch={env['branch']} clean={env['tree_clean']} dirty={env['dirty_paths']} "
                 f"allows_new_risk={rel.get('allows_new_risk')}"),
        ("sleeves", f"live={sle.get('n_live')} standby={sle.get('n_standby')} "
                    f"retired={sle.get('n_retired')} of {sle.get('n_total', UNMEASURED)}"),
        ("risk", f"heat floor={heat.get('floor')} ceiling={heat.get('ceiling')} "
                 f"resolved={heat.get('resolved')} live_frac={risk.get('risk_frac_live_total')}"),
        ("allocator", f"at={alc.get('at')} passed={alc.get('passed')} stale={alc.get('stale')} "
                      f"funded={_pick(alc, 'fractions', 'n_funded')}"),
        ("promotion", f"banned={pro.get('banned_families')} clocks={pro.get('n_forward_clocks')} "
                      f"unfrozen={pro.get('identity_unfrozen')} "
                      f"unreachable={pro.get('unreachable_certified')}"),
        ("execution", f"pass={exe.get('last_pass_at')} positions={exe.get('positions')} "
                      f"bracket={exe.get('last_bracket_date')} 24h deals={live.get('deals')} "
                      f"R={live.get('sum_r')}"),
        ("attest", f"gate={gate.get('result', UNMEASURED)}@{gate.get('age_h', UNMEASURED)}h "
                   f"closed_loop true={loop.get('true')} false={loop.get('false')} "
                   f"unmeasured={loop.get('unmeasured')}"),
        ("e8", f"armed={e8.get('armed')} status={e8.get('report_status')} at={e8.get('at')} | "
               f"box free_mb={_pick(doc['box'], 'memory', 'free_phys_mb')}"),
        ("sources", f"present={present}/{len(sources)} "
                    f"unmeasured={len(doc.get('unmeasured', []))} "
                    f"config={env['config_hash'][:12]} input={env['input_hash'][:12]}"),
        ("changed", changes[0] + (f" (+{len(changes) - 1} more)" if len(changes) > 1 else "")),
    ]
    return [f"LIVE_SYSTEM_STATE  at={env['at']}  host={env['host']}  -> {OUT}"] + [
        f"  {label:<9} {text}" for label, text in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Join the desk's split truth into one document.")
    parser.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = parser.parse_args(argv)
    doc = build()
    if not args.dry_run:
        write(doc)
    for line in summary(doc):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
