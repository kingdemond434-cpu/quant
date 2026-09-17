"""THE OPEN-SOURCE RESEARCH FEDERATION, as an organ -- every public research system disposed,
ledgered, delta-watched, budgeted, and (when a sandbox has run) drained of its donations.

THE LAW (docs/LAWS.md 5h, principal 2026-09-17). It replaced "NO THIRD-PARTY TOOLING -- mine it
as TEXT": a capability whose measured expected research value is positive may not rest at
TEXT_ONLY, every discovered system carries exactly one disposition, and an external engine is a
researcher -- never a validator, never a capital authority. The rules live in
`libs/research/external_federation.py`; this organ is the hour's work over desk state.

WHAT ONE PASS DOES

  1. ROSTER      the bootstrap seeds plus every system the desk has discovered since, each with
                 a ledger row carrying the fields the law names (LEDGER_FIELDS).
  2. DISCOVER    new systems from what the desk already fetched -- registry `sources` rows and
                 the intelligence donations -- fingerprinted and passed through `admit()`, which
                 refuses fake breadth (a fork storm is one lineage) before any compute is spent.
  3. DISPOSE     a system with no disposition is the one defect this organ exists to remove; each
                 undisposed system also becomes a registry discovery so the compiler, the scouts
                 and the gauntlet see the work rather than this report alone.
  4. CAPABILITY  every capability of every running system becomes a discovery with its extraction
                 task, so "mine it" and "use it" are both scheduled work, not prose.
  5. PACKETS     anything a sandboxed worker left in data/external_packets/ is validated against
                 the packet contract (a verdict-shaped field raises), deduplicated, and donated
                 in the seat shape the miner candidate compiler already reads.
  6. BUDGET      ROI_s per system, two-sided, with a floor so no frontier is ever switched off --
                 written to data/external_allocation.json for the sandbox runner to read.

WHAT IT DOES NOT DO: fetch, install, or execute third-party code. Provisioning a sandbox is a
separate, explicit act (`libs/research/sandbox.py` holds the policy; the runner is registered as
its own component) because installing a stranger's dependencies is not something an hourly leg
should do behind a budget flag.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import external_federation as fed  # noqa: E402

STATE = DESK / "data" / "external_federation.json"
ALLOCATION = DESK / "data" / "external_allocation.json"
REPORT = DESK / "reports" / "EXTERNAL_FEDERATION.json"
PACKETS = DESK / "data" / "external_packets"
PROCESSED = PACKETS / "processed"
DONATIONS = DESK / "data" / "intelligence" / "external_federation"
#: A delta scan older than this is stale (LAWS 5h: unchanged sources cost near nothing, but a
#: source nobody has looked at for a fortnight is not "unchanged", it is unwatched).
DELTA_STALE_DAYS = 14
#: Total sandbox seconds per hour the federation may spend, shared out by ROI with a floor.
FEDERATION_BUDGET_S = 3600


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def load_state() -> dict[str, Any]:
    doc = _read(STATE, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("systems"), dict):
        return {"at": None, "systems": {}, "discovered": {}, "packets_seen": []}
    doc.setdefault("discovered", {})
    doc.setdefault("packets_seen", [])
    return doc


def roster(state: dict[str, Any]) -> list[fed.ExternalSystem]:
    """The seeds plus every system discovery has added. The seeds never disappear from the
    roster: a bootstrap entry that stops being interesting becomes REJECTED_WITH_EVIDENCE with a
    reopening condition, which is a decision, where deletion would be forgetting."""
    out = list(fed.SEEDS)
    known = {s.system_id for s in out}
    for sid, row in (state.get("discovered") or {}).items():
        if sid in known or not isinstance(row, dict):
            continue
        with contextlib.suppress(TypeError, ValueError):
            out.append(fed.ExternalSystem(
                system_id=sid, name=str(row.get("name") or sid),
                upstream=str(row.get("upstream") or "UNMEASURED"),
                role=str(row.get("role") or "discovered by the desk"),
                integration=str(row.get("integration") or "WRAPPED"),
                capabilities=tuple(row.get("capabilities") or ()),
                axes=tuple(row.get("axes") or ()),
                region=str(row.get("region") or "global"),
                languages=tuple(row.get("languages") or ("en",)),
                lineage_parent=row.get("lineage_parent"),
                discovery_source=str(row.get("discovery_source") or "desk_discovery")))
    return out


# ------------------------------------------------------------------------------- discovery

_CODE_HOSTS = ("github.com", "gitlab.com", "gitee.com", "huggingface.co", "bitbucket.org",
               "sourceforge.net", "codeberg.org")


def _candidate_systems_from_desk(limit: int) -> list[dict[str, Any]]:
    """Repository-shaped sources the desk already holds. Reads ONLY what other organs fetched --
    this organ never crawls (the frontier supervisor's rule, kept)."""
    found: dict[str, dict[str, Any]] = {}
    try:
        from libs.moat import registry as R
        conn = R.connect()
        try:
            rows = conn.execute(
                "SELECT url, title, language, country FROM sources "
                "WHERE url IS NOT NULL ORDER BY rowid DESC LIMIT ?", (limit * 20,)).fetchall()
        except Exception:                                   # table shape differs on a fresh file
            rows = []
        finally:
            conn.close()
        for row in rows:
            url = str(row["url"] if hasattr(row, "keys") else row[0] or "")
            if not any(h in url for h in _CODE_HOSTS):
                continue
            sid = _slug(url)
            found.setdefault(sid, {
                "name": url.rstrip("/").split("/")[-1] or sid, "upstream": url,
                "discovery_source": "registry.sources",
                "region": str((row["country"] if hasattr(row, "keys") else "") or "global"),
                "languages": [str((row["language"] if hasattr(row, "keys") else "en") or "en")]})
            if len(found) >= limit:
                break
    except Exception:                                       # the registry is optional here
        pass
    intel = DESK / "data" / "intelligence"
    if len(found) < limit and intel.exists():
        for p in sorted(intel.rglob("*.json"))[-200:]:
            doc = _read(p, None)
            rows2 = doc if isinstance(doc, list) else (doc or {}).get("discoveries") or []
            if not isinstance(rows2, list):
                continue
            for row in rows2[:200]:
                url = str((row or {}).get("url") or "") if isinstance(row, dict) else ""
                if not any(h in url for h in _CODE_HOSTS):
                    continue
                sid = _slug(url)
                found.setdefault(sid, {"name": url.rstrip("/").split("/")[-1] or sid,
                                       "upstream": url, "discovery_source": p.name})
                if len(found) >= limit:
                    break
            if len(found) >= limit:
                break
    return [{"system_id": k, **v} for k, v in found.items()]


def _slug(url: str) -> str:
    tail = url.rstrip("/").split("//")[-1].replace("/", "_").replace(".", "_").lower()
    return f"disc_{tail[:40]}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:8]}"


def discover(state: dict[str, Any], known: list[fed.ExternalSystem], limit: int) -> list[dict]:
    """New systems, each with the admission decision that let it in or collapsed it."""
    out: list[dict[str, Any]] = []
    have = {s.system_id for s in known}
    for row in _candidate_systems_from_desk(limit):
        sid = row["system_id"]
        if sid in have or sid in (state.get("discovered") or {}):
            continue
        cand = fed.ExternalSystem(
            system_id=sid, name=str(row.get("name") or sid),
            upstream=str(row.get("upstream") or "UNMEASURED"),
            role="discovered by the desk; capabilities UNMEASURED until it is mined",
            integration="WRAPPED", capabilities=(), axes=(),
            region=str(row.get("region") or "global"),
            languages=tuple(row.get("languages") or ("en",)),
            discovery_source=str(row.get("discovery_source") or "desk"))
        decision = fed.admit(cand, known)
        state.setdefault("discovered", {})[sid] = {
            "name": cand.name, "upstream": cand.upstream, "region": cand.region,
            "languages": list(cand.languages), "capabilities": [], "axes": [],
            "discovery_source": cand.discovery_source, "first_seen": now(),
            "disposition": decision.disposition, "why": decision.why,
            "integration": cand.integration}
        out.append({"system_id": sid, "upstream": cand.upstream,
                    "disposition": decision.disposition, "why": decision.why})
    return out


# ------------------------------------------------------------------------------- the ledger

def ledger(systems: Iterable[fed.ExternalSystem], state: dict[str, Any]) -> dict[str, dict]:
    """One row per system, carrying forward what previous passes measured."""
    prev = state.get("systems") or {}
    rows: dict[str, dict[str, Any]] = {}
    for s in systems:
        row = fed.ledger_row(s)
        old = prev.get(s.system_id)
        if isinstance(old, dict):
            for k, v in old.items():
                if v not in (None, "", "UNMEASURED"):
                    row[k] = v
        disc = (state.get("discovered") or {}).get(s.system_id)
        if isinstance(disc, dict) and disc.get("disposition"):
            row["disposition"] = disc["disposition"]
            row["why"] = disc.get("why") or row.get("why") or ""
        elif row.get("disposition") in (None, "", "UNMEASURED", "UNDISPOSED"):
            # A SEED IS NOT AUTOMATICALLY DISPOSED. The roster says what integration mode the
            # principal named; the disposition becomes that only when the sandbox status and the
            # licence make it real. Until then it is UNDISPOSED and this organ reports it as the
            # work it is -- which is the whole defect the law names.
            row["disposition"] = ("UNDISPOSED" if row.get("licence") in (None, "", "UNVERIFIED",
                                                                        "UNMEASURED")
                                  else s.integration)
            row["why"] = ("licence unverified: a provisioning run must read LICENSE at the pinned "
                          "commit before DIRECT execution is allowed")
        row["fingerprint"] = fed.fingerprint(s)
        row["lineage_parent"] = s.lineage_parent or ""
        rows[s.system_id] = row
    return rows


def roi_from_registry(rows: dict[str, dict]) -> dict[str, float | None]:
    """Per-system ROI from what the registry actually recorded for its generator."""
    out: dict[str, float | None] = dict.fromkeys(rows)
    try:
        from libs.moat import registry as R
        conn = R.connect()
        try:
            for sid, row in rows.items():
                gen = f"ext:{sid}"
                try:
                    got = conn.execute(
                        "SELECT SUM(candidates) AS c, SUM(survivors) AS s "
                        "FROM generator_yield WHERE generator=?", (gen,)).fetchone()
                except Exception:
                    break
                cands = float((got["c"] if got and got["c"] is not None else 0) or 0)
                survs = float((got["s"] if got and got["s"] is not None else 0) or 0)
                row["descendants_generated"] = cands or row.get("descendants_generated")
                row["forward_survivors"] = survs or row.get("forward_survivors")
                spend = float(row.get("compute_spent") or 0) or 0.0
                out[sid] = (survs / spend) if spend > 0 else None
        finally:
            conn.close()
    except Exception:
        return out
    return out


# ------------------------------------------------------------------------------- packets

def drain_packets(state: dict[str, Any], apply: bool) -> dict[str, Any]:
    """Validate, deduplicate and donate whatever the sandboxed workers left behind.

    A packet is UNTRUSTED input (LAWS 5h). It is parsed through the packet contract -- which
    raises on a verdict-shaped field rather than quietly accepting a "survivor" -- and its
    candidates are written in the seat-donation shape `miner_candidate_compiler` already reads,
    so an external worker reaches the gauntlet through the same door as every internal miner.
    """
    seen = set(state.get("packets_seen") or [])
    out = {"files": 0, "donated": 0, "rejected": [], "duplicates": 0, "unmeasured": []}
    if not PACKETS.exists():
        out["unmeasured"].append(f"{PACKETS} does not exist: no sandbox has produced a packet yet")
        return out
    rows: list[dict[str, Any]] = []
    for p in sorted(PACKETS.glob("*.json")):
        doc = _read(p, None)
        if not isinstance(doc, dict):
            out["rejected"].append({"file": p.name, "why": "unreadable or not an object"})
            continue
        key = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        if key in seen:
            out["duplicates"] += 1
            continue
        try:
            packet = fed.ExternalResearchPacket(
                system_id=str(doc.get("system_id") or "UNKNOWN"),
                run_id=str(doc.get("run_id") or key),
                commit=str(doc.get("commit") or "UNMEASURED"),
                candidates=tuple(doc.get("candidates") or ()),
                datasets=tuple(doc.get("datasets") or ()),
                mechanisms=tuple(doc.get("mechanisms") or ()),
                representations=tuple(doc.get("representations") or ()),
                research_methods=tuple(doc.get("research_methods") or ()),
                trials_charged=int(doc.get("trials_charged") or 0))
        except (TypeError, ValueError) as exc:
            out["rejected"].append({"file": p.name, "why": str(exc)[:300]})
            continue
        out["files"] += 1
        seen.add(key)
        for cand in packet.candidates:
            row = dict(cand)
            row.setdefault("kind", "hypothesis")
            row["origin"] = "EXTERNAL"
            row["generator"] = f"ext:{packet.system_id}"
            row["provenance"] = {"system": packet.system_id, "run": packet.run_id,
                                 "commit": packet.commit,
                                 "trials_charged": packet.trials_charged,
                                 "authority": "researcher only; the gauntlet judges"}
            rows.append(row)
        if apply:
            PROCESSED.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(OSError):
                os.replace(p, PROCESSED / p.name)
    if rows and apply:
        DONATIONS.mkdir(parents=True, exist_ok=True)
        _write(DONATIONS / f"discoveries_{int(time.time())}.json", rows)
    out["donated"] = len(rows)
    state["packets_seen"] = sorted(seen)[-500:]
    return out


# ------------------------------------------------------------------------------- discoveries

def record_work(rows: dict[str, dict], apply: bool, budget_left: float) -> dict[str, int]:
    """Undisposed systems and undisposed capabilities become registry work items.

    A report nobody reads changes nothing; a discovery in the canonical registry is claimed by a
    department, compiled, and counted in conversion debt until it resolves.
    """
    made = {"systems": 0, "capabilities": 0}
    if not apply:
        return made
    try:
        from libs.moat import registry as R
    except Exception:
        return made
    conn = R.connect()
    try:
        for sid, row in rows.items():
            if budget_left <= 0:
                break
            if str(row.get("disposition")) == "UNDISPOSED":
                with contextlib.suppress(Exception):
                    R.record_discovery(
                        kind="external_system", origin="EXTERNAL",
                        generator="external_federation",
                        source_id=f"ext:{sid}",
                        payload={"system_id": sid, "upstream": row.get("upstream_repo"),
                                 "why": row.get("why"),
                                 "task": ("read LICENSE at the pinned commit, fingerprint the "
                                          "capabilities, then set DIRECT / WRAPPED / REBUILT / "
                                          "REJECTED_WITH_EVIDENCE"),
                                 "law": "LAWS 5h: TEXT_ONLY is not a resting state"},
                        conn=conn)
                    made["systems"] += 1
            for cap in (row.get("capabilities") or []):
                if budget_left <= 0:
                    break
                with contextlib.suppress(Exception):
                    R.record_discovery(
                        kind="external_capability", origin="EXTERNAL",
                        generator=f"ext:{sid}", source_id=f"ext:{sid}:{cap}",
                        payload={"system_id": sid, "capability": cap,
                                 "task": ("extract the mechanism, name its data requirements and "
                                          "generate orthogonal descendants for the gauntlet"),
                                 "integration": row.get("integration_mode")},
                        conn=conn)
                    made["capabilities"] += 1
    finally:
        conn.close()
    return made


# ------------------------------------------------------------------------------- the pass

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--discover-limit", type=int, default=40)
    a = ap.parse_args(argv)
    apply = not a.dry_run
    t0 = time.monotonic()

    state = load_state()
    known = roster(state)
    new = discover(state, known, a.discover_limit)
    known = roster(state)
    rows = ledger(known, state)
    roi_from_registry(rows)

    for sid, row in rows.items():
        last = str(row.get("last_delta_scan") or "")
        stale = True
        if last and last != "UNMEASURED":
            with contextlib.suppress(ValueError):
                stale = datetime.fromisoformat(last) < datetime.now(tz=UTC) - timedelta(
                    days=DELTA_STALE_DAYS)
        row["delta_stale"] = bool(stale)
        row["system_id"] = sid

    alloc = fed.allocation(list(rows.values()), FEDERATION_BUDGET_S)
    packets = drain_packets(state, apply)
    made = record_work(rows, apply, a.budget_s - (time.monotonic() - t0))

    by_disp: dict[str, int] = {}
    for row in rows.values():
        by_disp[str(row.get("disposition"))] = by_disp.get(str(row.get("disposition")), 0) + 1
    lineages = fed.collapse_lineage(known)
    operational_rows = {sid: fed.operational(row)[1] for sid, row in rows.items()}
    doc = {
        "at": now(), "seconds": round(time.monotonic() - t0, 1), "dry_run": a.dry_run,
        "law": ("LAWS 5h: every lawfully usable, security-qualified, positive-ROI public research "
                "system gets exactly one disposition; TEXT_ONLY is not a resting state; an "
                "external engine is a researcher, never a validator and never a capital "
                "authority"),
        "systems": len(rows), "by_disposition": by_disp,
        "newly_discovered": new,
        "undisposed": sorted(sid for sid, r in rows.items()
                             if str(r.get("disposition")) == "UNDISPOSED"),
        "delta_stale": sorted(sid for sid, r in rows.items() if r.get("delta_stale")),
        "not_operational": {sid: missing for sid, missing in operational_rows.items() if missing},
        "lineages": {k: v for k, v in lineages.items() if v},
        "packets": packets, "work_recorded": made,
        "allocation_s": alloc,
        "sandbox_policy": fed.POLICY.__dict__,
        "unmeasured": ([] if packets.get("files") else
                       ["no sandbox has produced an ExternalResearchPacket yet: provisioning is "
                        "an explicit act, and until it happens every DIRECT row is a plan"]),
    }
    if apply:
        state["at"] = doc["at"]
        state["systems"] = rows
        _write(STATE, state)
        _write(ALLOCATION, {"at": doc["at"], "rule": "ROI_s with a floor; no frontier is ever "
                                                     "switched off", "budget_s": alloc})
        _write(REPORT, doc)
    print(f"external federation: {len(rows)} systems {by_disp} | new {len(new)} | "
          f"undisposed {len(doc['undisposed'])} | delta-stale {len(doc['delta_stale'])} | "
          f"packets {packets.get('files', 0)} donated {packets.get('donated', 0)} | "
          f"work {made} in {doc['seconds']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
