"""FEDERATION OPERATIONS -- the persisted ExternalResearchSystemRegistry kept in step with the
federation organ and the sandbox runner, upstream delta scans by hash, spawn signals from
already-fetched material, the technique exchange across the forests, benchmark twins, and the
federation dashboard that names the exact first invariant preventing
FEDERATION_CLOSED_AND_HEALTHY = true.

THE LAW (docs/LAWS.md 5h, 5m and 5f rule 13). A system is fully exploited only when it is
REGISTERED and SANDBOXED and SCHEDULED and EXECUTED and PROGRESSED and PRODUCED and CONSUMED and
ATTRIBUTED; every system is delta-scanned and has a benchmark twin; the dashboard shows
scientific outputs, never uptime. Rule 13: this plugs into the existing architecture -- the
roster and `admit()` in `libs/research/external_federation.py`, the spawn-signal vocabulary and
delta cadence in `research/source_civilizations.py`, the `technique` rows `forest_runner`
records, the desk's one HTTP client behind `moat_collectors.fetch_text` -- and adds no new
top-level module, no new scraper and no new registry of the same machine.

WHAT ONE PASS DOES

  1. SYNC        one registry row per system (`libs/research/federation_registry.py`, every
                 field LAWS 5h/5m name), from the federation organ's state, the sandbox runner's
                 artifacts and the drained packets; UNMEASURED by name where nothing measured it;
                 every field change is one hash-chained, append-only history entry.
  2. DELTA       the due upstreams re-hashed surface by surface (repos, commits, releases, docs)
                 through the desk's EXISTING fetcher with its robots and terms checks, allowlisted
                 hosts only; an unchanged hash costs one fetch, a changed one REOPENS the
                 capability fingerprint and records a `delta_reopen` discovery.
  3. SPAWN       signals read off material other organs already fetched (registry sources,
                 intelligence donations, source ROI, competition claims, fork parents) -> one
                 ExternalSystem each -> `external_federation.admit` -> a new roster row donated
                 through the federation organ's own door, or a DUPLICATE with lineage.
  4. TECHNIQUES  every `technique` discovery a forest recorded is judged on DELAYED yield; a
                 survivor becomes a `technique_transfer` discovery for every other forest, naming
                 the local equivalent to hunt.
  5. TWINS       native workflow vs integrated variant at equal compute, recorded when both ran;
                 integration that makes a system worse leaves the native path standing.
  6. DASHBOARD   reports/FEDERATION.json: per system runs, compute, unique capabilities,
                 candidates, effective trials, duplicate rate, gauntlet pass rate, forward
                 enrolment/survival, live descendants, incremental Elog, information gain, data
                 fields and representations discovered, failures contributed, freshness, health
                 state, marginal ROI -- and the first broken invariant.

WHAT IT DOES NOT DO: install, run or validate third-party code (the sandbox runner is its own
component), crawl (only allowlisted upstream surfaces, through the existing client), or decide
capital. `--dry-run` computes everything and writes nothing.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import external_federation as fed  # noqa: E402
from libs.research import federation_registry as FR  # noqa: E402
from libs.research import forests as F  # noqa: E402
from research import external_federation as xfo  # noqa: E402

UNMEASURED = FR.UNMEASURED
GENERATOR = "federation_ops"
REGISTRY_PATH = DESK / "data" / "federation_registry.json"
REPORT = DESK / "reports" / "FEDERATION.json"
DONATIONS = DESK / "data" / "intelligence" / "federation_ops"
ROI_REPORT = DESK / "reports" / "RESEARCH_ROI.json"
# THE COMPILER'S OWN PATH, RE-POINTED (measured 2026-09-24). `miner_candidate_compiler` writes
# `data/hypotheses/miner_candidates.json` -- the path ten other readers use -- and this constant
# named `data/miner_candidates.json`, which NOTHING in the tree writes and which has never existed.
# So `seat_consumption()` opened an absent file every pass, took the `None` branch and reported the
# federation seats as UNMEASURED forever: the exact defect the plumbing watchdog's orphan check was
# built to find, sitting inside a function whose docstring promises the compiler's own measurement.
MINER_CANDIDATES = DESK / "data" / "hypotheses" / "miner_candidates.json"
SLEEVES = DESK / "data" / "sleeves.json"
FORWARD = DESK / "data" / "forward_reconcile.json"
CLAIMS_JSONL = DESK / "data" / "deep_forest_claims.jsonl"
#: Upstreams re-hashed per pass and surfaces per upstream: bounded so a thousand watched
#: sources cost a few fetches an hour each week, which is the whole economy of delta scanning.
MAX_SCAN_PER_PASS = 8
MAX_SIGNALS_PER_PASS = 40
MAX_TECHNIQUES_PER_PASS = 200
CANONICAL_CONSUMERS = ("miner_candidate_compiler", "external_gauntlet", "forward_lab",
                       "pf_allocator")
#: The hosts a delta scan may touch. The sandbox's clone allowlist plus the read-only surfaces
#: of the same forges; anything else is refused BY NAME and reported, never fetched.
_EXTRA_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com", "arxiv.org",
                          "export.arxiv.org"})

Fetcher = Callable[[str], tuple[str, int, str]]


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


def _norm_url(url: str) -> str:
    u = str(url or "").strip().lower().rstrip("/")
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u[:-4] if u.endswith(".git") else u


def _host(url: str) -> str:
    try:
        return (urlparse(url if "://" in url else "https://" + url).hostname or "").lower()
    except ValueError:
        return ""


def allowed_hosts() -> frozenset[str]:
    try:
        from libs.research import sandbox
        base: frozenset[str] = frozenset(sandbox.ALLOWED_HOSTS)
    except Exception:
        base = frozenset(xfo._CODE_HOSTS)
    return base | _EXTRA_HOSTS


def _code_host(url: str) -> bool:
    return any(h in str(url or "").lower() for h in xfo._CODE_HOSTS)


# --------------------------------------------------------------------------- the fetcher
_ROBOTS_CACHE: dict[str, bool] = {}


def desk_fetch(url: str) -> tuple[str, int, str]:
    """The desk's EXISTING client (`moat_collectors.fetch_text` -> `deep_forest_miner._http`)
    behind its measured robots hard stops and the live robots re-probe, on allowlisted hosts
    only. Refusals come back as (body "", status 0, why) -- a measurement, never a raise."""
    host = _host(url)
    if host not in allowed_hosts():
        return "", 0, f"host {host!r} is not allowlisted for delta scans"
    try:
        from research import moat_collectors as mc
    except Exception as exc:                                       # pragma: no cover
        return "", 0, f"moat_collectors unavailable: {type(exc).__name__}"
    barred = mc.robots_barred(url)
    if barred:
        return "", 0, barred
    if host not in _ROBOTS_CACHE:
        _ROBOTS_CACHE[host] = bool(mc.robots_still_disallows(host))
    if _ROBOTS_CACHE[host]:
        return "", 0, f"{host}/robots.txt disallows this agent (or could not be read: refused)"
    return mc.fetch_text(url)


def surfaces_for(upstream: str) -> dict[str, str]:
    """surface -> url for one upstream. GitHub gets the API record, the commit feed, the release
    feed and the README; another forge or a website gets its page as `websites`."""
    url = str(upstream or "")
    if not url or url == UNMEASURED or ("://" not in url and "." not in url):
        return {}
    full = url if "://" in url else "https://" + url
    host = _host(full)
    path = urlparse(full).path.strip("/")
    parts = path.split("/")
    if host in ("github.com", "www.github.com") and len(parts) >= 2:
        owner, repo = parts[0], parts[1].removesuffix(".git")
        return {"repos": f"https://api.github.com/repos/{owner}/{repo}",
                "commits": f"https://github.com/{owner}/{repo}/commits.atom",
                "releases": f"https://github.com/{owner}/{repo}/releases.atom",
                "docs": f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"}
    if host in ("arxiv.org", "export.arxiv.org"):
        return {"papers": full}
    if host.endswith(("gitlab.com", "gitee.com", "codeberg.org", "bitbucket.org")):
        return {"repos": full}
    if host == "huggingface.co":
        return {"datasets": full}
    return {"websites": full}


_STABLE_REPO_FIELDS = ("pushed_at", "default_branch", "stargazers_count", "forks_count",
                       "open_issues_count", "archived", "fork", "size")


def stable_body(surface: str, body: str) -> tuple[str, dict[str, Any]]:
    """What is hashed, and what is read off the surface. An API record carries volatile fields
    (`updated_at` moves on a star), so only the fields that mean "the upstream changed" are
    hashed; a feed is hashed whole after its request-time noise is stripped."""
    meta: dict[str, Any] = {}
    if surface == "repos" and body.lstrip().startswith("{"):
        try:
            doc = json.loads(body)
        except ValueError:
            return body, meta
        if isinstance(doc, dict):
            stable = {k: doc.get(k) for k in _STABLE_REPO_FIELDS}
            lic = doc.get("license") if isinstance(doc.get("license"), dict) else {}
            stable["license"] = (lic or {}).get("spdx_id")
            meta = {"stars": doc.get("stargazers_count"), "forks": doc.get("forks_count"),
                    "pushed_at": doc.get("pushed_at"), "fork": bool(doc.get("fork")),
                    "parent": ((doc.get("parent") or {}).get("html_url")
                               if isinstance(doc.get("parent"), dict) else None),
                    "licence_spdx": stable["license"]}
            return json.dumps(stable, sort_keys=True), meta
    if surface == "commits":
        m = re.search(r"Grit::Commit/([0-9a-f]{40})", body)
        if m:
            meta["upstream_head"] = m.group(1)
    return body, meta


# --------------------------------------------------------------------------- inputs
def sandbox_records() -> dict[str, dict[str, Any]]:
    """What the sandbox runner left per system: its record (commit, licence, dependencies) and
    the run documents in out/. Absent means UNMEASURED, never "not provisioned"."""
    out: dict[str, dict[str, Any]] = {}
    try:
        from libs.research import sandbox
        root = sandbox.SANDBOX_ROOT
    except Exception:
        return out
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        rec = _read(d / "sandbox.json", None)
        runs: list[dict[str, Any]] = []
        for p in sorted((d / "out").glob("*.json"))[-50:] if (d / "out").exists() else []:
            doc = _read(p, None)
            if isinstance(doc, dict) and (doc.get("run_id") or doc.get("candidates") is not None):
                doc.setdefault("_file", p.name)
                doc.setdefault("_mtime", datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
                               .isoformat(timespec="seconds"))
                runs.append(doc)
        out[d.name] = {"record": rec if isinstance(rec, dict) else None, "runs": runs}
    return out


def packet_docs() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for folder in (xfo.PROCESSED, xfo.PACKETS):
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.json"))[-400:]:
            doc = _read(p, None)
            if isinstance(doc, dict):
                doc.setdefault("_file", p.name)
                doc.setdefault("_mtime", datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
                               .isoformat(timespec="seconds"))
                docs.append(doc)
    return docs


def _cand_hash(row: Any) -> str:
    return FR.content_hash(row if isinstance(row, (dict, list)) else str(row))


def run_records(packets: Sequence[Mapping[str, Any]],
                sandboxes: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One record per run: scientific counts, compute, variant, revision, verdict leaks."""
    recs: dict[tuple[str, str], dict[str, Any]] = {}
    docs: list[Mapping[str, Any]] = list(packets)
    for sid, sb in sandboxes.items():
        for doc in sb.get("runs") or []:
            docs.append({**doc, "system_id": doc.get("system_id") or sid})
    for doc in docs:
        sid = str(doc.get("system_id") or "UNKNOWN")
        rid = str(doc.get("run_id") or doc.get("_file") or "UNMEASURED")
        key = (sid, rid)
        if key in recs:
            continue
        cands = list(doc.get("candidates") or [])
        leaks = 0
        for group in ("candidates", "datasets", "mechanisms", "representations",
                      "research_methods"):
            for row in doc.get(group) or []:
                if isinstance(row, Mapping):
                    leaks += sum(1 for k in row if str(k).lower() in fed.PACKET_FORBIDDEN)
        prov = doc.get("provenance") if isinstance(doc.get("provenance"), Mapping) else {}
        compute = doc.get("compute_s", doc.get("seconds", prov.get("compute_s")))
        failures = sum(1 for row in (doc.get("mechanisms") or []) + (doc.get("research_methods")
                                                                     or [])
                       if isinstance(row, Mapping) and (
                           str(row.get("kind") or "").lower() in ("failure", "negative")
                           or row.get("failure_knowledge") or row.get("known_failures")))
        recs[key] = {
            "system_id": sid, "run_id": rid, "commit": str(doc.get("commit") or UNMEASURED),
            "variant": str(doc.get("variant") or prov.get("variant") or UNMEASURED),
            "compute_s": float(compute) if isinstance(compute, (int, float)) else None,
            "candidates": len(cands), "unique_candidates": len({_cand_hash(c) for c in cands}),
            "datasets": len(doc.get("datasets") or []),
            "mechanisms": len(doc.get("mechanisms") or []),
            "representations": len(doc.get("representations") or []),
            "research_methods": len(doc.get("research_methods") or []),
            "effective_trials": int(doc.get("trials_charged") or 0),
            "failures": failures, "verdict_leaks": leaks,
            "at": str(doc.get("at") or prov.get("at") or doc.get("_mtime") or UNMEASURED),
            "scheduled_by": str(doc.get("scheduled_by") or prov.get("scheduled_by") or ""),
            "data_fields": sum(len(row.get("fields") or []) if isinstance(row, Mapping) else 0
                               for row in doc.get("datasets") or []),
        }
    return sorted(recs.values(), key=lambda r: str(r["at"]))


def generator_yields(conn: Any) -> dict[str, dict[str, Any]]:
    """`generator_yield` rows for `ext:<sid>` generators -- the canonical ledger's own count of
    what an external generator donated, had judged, and had survive."""
    out: dict[str, dict[str, Any]] = {}
    if conn is None:
        return out
    try:
        rows = conn.execute("SELECT * FROM generator_yield WHERE generator LIKE 'ext:%'").fetchall()
    except Exception:
        return out
    for r in rows:
        row = dict(r)
        out[str(row.get("generator") or "")[4:]] = row
    return out


def seat_consumption() -> dict[str, Any] | None:
    """The compiler's own measurement of the federation seats (miner_candidates.json["seats"]).
    None when the compiler has not published; that is UNMEASURED, not zero."""
    doc = _read(MINER_CANDIDATES, None)
    seats = (doc or {}).get("seats") if isinstance(doc, dict) else None
    if not isinstance(seats, dict):
        return None
    return {k: v for k, v in seats.items() if "federation" in str(k)}


def _scan_generators(doc: Any, hits: dict[str, int], depth: int = 0) -> None:
    if depth > 4:
        return
    if isinstance(doc, dict):
        gen = str(doc.get("generator") or doc.get("origin_generator") or "")
        if gen.startswith("ext:"):
            hits[gen[4:]] = hits.get(gen[4:], 0) + 1
        for v in doc.values():
            _scan_generators(v, hits, depth + 1)
    elif isinstance(doc, list):
        for v in doc[:5000]:
            _scan_generators(v, hits, depth + 1)


def descendants_in(path: Path) -> dict[str, int] | None:
    """Rows in a desk artifact whose generator is an external system, per system."""
    doc = _read(path, None)
    if doc is None:
        return None
    hits: dict[str, int] = {}
    _scan_generators(doc, hits)
    return hits


def system_stats(reg: FR.Registry, records: Sequence[Mapping[str, Any]],
                 yields: Mapping[str, Mapping[str, Any]], roi_doc: Mapping[str, Any] | None,
                 live: Mapping[str, int] | None, forward: Mapping[str, int] | None,
                 seats: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """The dashboard's per-system numbers, each from the artifact that owns it."""
    credit = ((roi_doc or {}).get("delayed_credit") or {}) if isinstance(roi_doc, Mapping) else {}
    by_gen = credit.get("by_generator") if isinstance(credit, Mapping) else {}
    by_gen = by_gen if isinstance(by_gen, Mapping) else {}
    stats: dict[str, dict[str, Any]] = {}
    for sid, row in reg.rows.items():
        mine = [r for r in records if r["system_id"] == sid]
        y = yields.get(sid) or {}
        cands = sum(int(r["candidates"]) for r in mine)
        uniq = sum(int(r["unique_candidates"]) for r in mine)
        compute = [float(r["compute_s"]) for r in mine if r.get("compute_s") is not None]
        judged = y.get("judged")
        survivors = y.get("survivors")
        # CONSUMED is the canonical ledger's count of what this generator donated; the compiler's
        # seat totals (miner_candidates.json["seats"]) are federation-wide and are published in
        # the report's inputs rather than attributed to a system they do not name.
        consumed = int(y.get("donated") or 0)
        gen_credit = by_gen.get(f"ext:{sid}") if isinstance(by_gen, Mapping) else None
        delta_elog = (y.get("delta_elogw") if y.get("delta_elogw") is not None else
                      (gen_credit or {}).get("delta_elogw") if isinstance(gen_credit, Mapping)
                      else None)
        data_fields = sum(int(r["data_fields"]) for r in mine)
        reps = sum(int(r["representations"]) for r in mine)
        info_gain = (data_fields + reps + sum(int(r["mechanisms"]) for r in mine)
                     + sum(int(r["datasets"]) for r in mine)) if mine else None
        st: dict[str, Any] = {
            "runs": len(mine), "compute_s": (round(sum(compute), 1) if compute else
                                             (float(row.get("compute_spent"))
                                              if isinstance(row.get("compute_spent"),
                                                            (int, float)) else None)),
            "unique_capabilities": len(set(row.get("capabilities") or [])),
            "candidates": cands, "unique_candidates": uniq,
            "effective_trials": sum(int(r["effective_trials"]) for r in mine),
            "duplicate_rate": (round(1.0 - uniq / cands, 4) if cands else None),
            "gauntlet_judged": judged, "gauntlet_survivors": survivors,
            "gauntlet_pass_rate": (round(float(survivors or 0) / float(judged), 4)
                                   if isinstance(judged, (int, float)) and judged > 0 else None),
            "forward_enrolled": (forward or {}).get(sid) if forward is not None else None,
            "forward_survivors": (row.get("forward_survivors")
                                  if FR.measured(row.get("forward_survivors")) else
                                  (y.get("independent_survivors") if y else None)),
            "live_descendants": (live or {}).get(sid, 0) if live is not None else None,
            "delta_elog": delta_elog, "information_gain": info_gain,
            "data_fields_discovered": data_fields if mine else None,
            "representations_discovered": reps if mine else None,
            "mechanisms": sum(int(r["mechanisms"]) for r in mine),
            "datasets": sum(int(r["datasets"]) for r in mine),
            "representations": reps,
            "research_methods": sum(int(r["research_methods"]) for r in mine),
            "failures_contributed": sum(int(r["failures"]) for r in mine) if mine else None,
            "consumed": consumed,
            "last_run_at": max((str(r["at"]) for r in mine), default=None),
            "last_delta_scan": (row.get("last_upstream_delta_scan")
                                if FR.measured(row.get("last_upstream_delta_scan")) else None),
            "twin": (reg.twins.get(sid) or {}).get("verdict", UNMEASURED),
        }
        st["freshness"] = {"last_run_at": st["last_run_at"] or UNMEASURED,
                           "last_delta_scan": st["last_delta_scan"] or UNMEASURED}
        st["health_state"] = FR.health_state(row, st)
        st["marginal_roi"] = FR.marginal_roi(row, st)
        stats[sid] = st
    return stats


# --------------------------------------------------------------------------- 1. sync
def _system_from_row(row: Mapping[str, Any]) -> fed.ExternalSystem | None:
    try:
        return fed.ExternalSystem(
            system_id=str(row["system_id"]), name=str(row.get("name") or row["system_id"]),
            upstream=str(row.get("upstream_repo") or UNMEASURED),
            role=str(row.get("why") or ""),
            integration=str(row.get("integration_mode") or "WRAPPED"),
            capabilities=tuple(row.get("capabilities") or ()) if isinstance(
                row.get("capabilities"), list) else (),
            axes=tuple(row.get("axes") or ()) if isinstance(row.get("axes"), list) else (),
            region=str(row.get("region") or "global"),
            languages=tuple(row.get("languages") or ("en",)) if isinstance(
                row.get("languages"), list) else ("en",),
            lineage_parent=(str(row["duplicate_family_id"])
                            if FR.measured(row.get("duplicate_family_id"))
                            and row.get("duplicate_family_id") != row["system_id"] else None),
            discovery_source=str(row.get("discovery_source") or "federation_registry"))
    except (KeyError, TypeError, ValueError):
        return None


def known_systems(reg: FR.Registry, fed_state: Mapping[str, Any]) -> list[fed.ExternalSystem]:
    """The roster the federation organ holds plus every system this registry spawned."""
    out = xfo.roster(dict(fed_state))
    have = {s.system_id for s in out}
    for sid, row in reg.rows.items():
        if sid in have:
            continue
        s = _system_from_row(row)
        if s is not None:
            out.append(s)
            have.add(sid)
    return out


def sync_registry(reg: FR.Registry, systems: Sequence[fed.ExternalSystem],
                  fed_state: Mapping[str, Any], sandboxes: Mapping[str, Mapping[str, Any]],
                  records: Sequence[Mapping[str, Any]], *, at: str) -> dict[str, int]:
    """Every system gets a row; every measured fact the federation organ, the sandbox runner or
    a packet holds lands in it. UNMEASURED never overwrites a measurement."""
    ledger = fed_state.get("systems") if isinstance(fed_state.get("systems"), Mapping) else {}
    changed = 0
    for s in systems:
        cand = FR.row_from_system(s, canonical_consumers=list(CANONICAL_CONSUMERS))
        led = ledger.get(s.system_id) if isinstance(ledger, Mapping) else None
        if isinstance(led, Mapping):
            for src, dst in (("commit_sha", "commit_version"), ("licence", "licence"),
                             ("integration_mode", "integration_mode"),
                             ("disposition", "disposition"), ("compute_spent", "compute_spent"),
                             ("descendants_generated", "descendants_created"),
                             ("trials_donated", "trials_donated"),
                             ("forward_survivors", "forward_survivors"),
                             ("live_delta_elog", "live_portfolio_contribution"),
                             ("failure_knowledge_extracted", "known_weaknesses"),
                             ("research_methods_extracted", "native_validation_methods"),
                             ("why", "why")):
                if FR.measured(led.get(src)):
                    cand[dst] = led[src]
            if FR.measured(led.get("capabilities")):
                cand["capabilities"] = list(led["capabilities"])
        sb = sandboxes.get(s.system_id) or {}
        rec = sb.get("record") if isinstance(sb, Mapping) else None
        if isinstance(rec, Mapping):
            if FR.measured(rec.get("commit")):
                cand["commit_version"] = rec["commit"]
            if FR.measured(rec.get("licence")) and rec.get("licence") != "UNVERIFIED":
                cand["licence"] = rec["licence"]
            if FR.measured(rec.get("dependencies")):
                cand["data_dependencies"] = list(rec["dependencies"])
            if rec.get("provisioned"):
                cand["sandbox_image_hash"] = FR.content_hash(
                    {"commit": rec.get("commit"), "dependencies": rec.get("dependencies"),
                     "policy": rec.get("policy")})
                cand["security_profile"] = rec.get("policy") or fed.POLICY.__dict__
        mine = [r for r in records if r["system_id"] == s.system_id]
        if mine:
            last = mine[-1]
            cand["progress_watermark"] = {"run_id": last["run_id"], "at": last["at"],
                                          "runs": len(mine)}
            cand["outputs"] = {k: sum(int(r[k]) for r in mine) for k in (
                "candidates", "datasets", "mechanisms", "representations", "research_methods")}
            cand["trials_donated"] = sum(int(r["effective_trials"]) for r in mine)
            commits = [r["commit"] for r in mine if FR.measured(r.get("commit"))]
            if commits:
                cand["commit_version"] = commits[-1]
            clocks = sorted({r["scheduled_by"] for r in mine if r.get("scheduled_by")})
            if clocks:
                cand["schedule"] = clocks
        if not FR.measured(cand.get("disposition")):
            # A SEED IS NOT AUTOMATICALLY DISPOSED (the federation organ's rule, kept): the
            # roster names an integration mode; it becomes the disposition only once the
            # licence is read at the pinned commit. Until then it is UNDISPOSED, by name.
            cand["disposition"] = ("UNDISPOSED" if str(cand.get("licence")) in
                                   (UNMEASURED, "UNVERIFIED", "") else s.integration)
        old = reg.rows.get(s.system_id) or {}
        row = {k: v for k, v in cand.items() if FR.measured(v) or k not in old}
        row["system_id"] = s.system_id
        if reg.upsert(row, at=at):
            changed += 1
    return {"systems": len(systems), "rows_changed": changed}


# --------------------------------------------------------------------------- 2. delta scans
def delta_scan_step(reg: FR.Registry, *, fetch: Fetcher, max_scan: int, deadline: float,
                    apply: bool, conn: Any, at: str, no_fetch: bool) -> dict[str, Any]:
    """Due upstreams re-hashed through the existing fetcher; a moved hash reopens the
    capability fingerprint and records a `delta_reopen` discovery for the compiler."""
    out: dict[str, Any] = {"scanned": [], "changed": {}, "unchanged": [], "refused": {},
                           "reopened": [], "meta": {}, "unmeasured": [],
                           "surfaces": list(FR.DELTA_SURFACES)}
    t = datetime.fromisoformat(at)
    due = [(sid, r) for sid, r in reg.rows.items()
           if FR.delta_due(r, now=t) and FR.measured(r.get("upstream_repo"))]
    due.sort(key=lambda p: (str(p[1].get("disposition")) not in fed.RUNNING_DISPOSITIONS,
                            str(p[1].get("next_upstream_delta_scan") or "")))
    out["due"] = len(due)
    if no_fetch:
        out["unmeasured"].append("--no-fetch: delta scans are UNMEASURED this pass")
        return out
    try:
        from research import source_civilizations as sc
        cadence, hasher = sc.delta_scan, sc.delta_hash
    except Exception:
        cadence, hasher = None, FR.content_hash
    previous = reg.delta.snapshot()
    for sid, row in due[:max(0, max_scan)]:
        if time.monotonic() > deadline:
            out["unmeasured"].append("budget exhausted; the remaining due upstreams are first in "
                                     "line next pass")
            break
        surfaces = surfaces_for(str(row.get("upstream_repo")))
        if not surfaces:
            out["refused"][sid] = "upstream is not a URL a delta scan can hash"
            continue
        hashed: dict[str, str] = {}
        refused: dict[str, str] = {}
        meta: dict[str, Any] = {}
        for surface, url in surfaces.items():
            body, status, err = fetch(url)
            if err or status != 200 or not body:
                refused[surface] = err or f"HTTP {status}"
                continue
            stable, m = stable_body(surface, body)
            reg.delta.observe(sid, surface, stable, at=at)
            hashed[surface] = reg.delta.hashes[sid][surface]
            meta.update(m)
        if not hashed:
            out["refused"][sid] = refused
            continue
        # COMPARED OVER THE SURFACES SEEN BEFORE. A README refused this pass and fetched last
        # pass is not a change of the upstream; a surface hashed for the first time is not one
        # either. Only a hash that MOVED reopens the fingerprint.
        prev_surfaces = previous.get(sid) or {}
        common = {s: h for s, h in hashed.items() if s in prev_surfaces}
        moved = sorted(s for s, h in common.items() if prev_surfaces[s] != h)
        first = not prev_surfaces
        if cadence is not None:
            prev_row = {"delta_hash": (hasher({s: prev_surfaces[s] for s in common})
                                       if common else ""),
                        "last_deep_scan": row.get("last_upstream_delta_scan")}
            scan = cadence(sid, common or hashed, prev_row, now=t)
            changed = bool(moved)
            nxt = str(scan["next_delta_scan"])
        else:                                                      # pragma: no cover
            changed = bool(moved)
            nxt = (t + timedelta(hours=24 if (changed or first) else 168)).isoformat(
                timespec="seconds")
        update: dict[str, Any] = {"system_id": sid, "last_upstream_delta_scan": at,
                                  "next_upstream_delta_scan": nxt}
        if changed:
            update["fingerprint_state"] = "REOPENED"
            out["changed"][sid] = moved
            out["reopened"].append(sid)
            if apply and conn is not None:
                try:
                    from libs.moat import registry as R
                    R.record_discovery(
                        kind="delta_reopen", origin="EXTERNAL", generator=GENERATOR,
                        source_id=f"ext:{sid}", source_type="delta_reopen",
                        mechanism=f"DELTA_REOPEN {sid}: upstream surfaces {moved} changed; the "
                                  f"capability fingerprint is reopened"[:400],
                        exact_rule_if_known=f"surfaces={moved} at={at}",
                        economic_rationale="a changed upstream may carry a new capability, "
                                           "data axis or failure the desk has not mined",
                        payload={"system_id": sid, "surfaces": moved, "meta": meta,
                                 "task": "re-mine the changed surfaces; re-fingerprint; route "
                                         "new capabilities to extraction"}, conn=conn)
                except Exception as exc:
                    out["unmeasured"].append(f"{sid}: delta_reopen not recorded: "
                                             f"{type(exc).__name__}")
        elif first:
            update["fingerprint_state"] = (row.get("fingerprint_state")
                                           if FR.measured(row.get("fingerprint_state"))
                                           else "MEASURED")
            out["unchanged"].append(sid)
        else:
            out["unchanged"].append(sid)
        reg.upsert(update, at=at)
        out["scanned"].append(sid)
        if refused:
            out["refused"][sid] = refused
        if meta:
            out["meta"][sid] = meta
    return out


# --------------------------------------------------------------------------- 3. spawn signals
_VIA_SIGNAL = (("citation", "citation_cluster"), ("paper", "citation_cluster"),
               ("contributor", "contributor_graph"), ("author", "contributor_graph"),
               ("fork", "stars_forks"), ("star", "stars_forks"),
               ("conference", "conference_co_occurrence"), ("dependency", "package_dependency"),
               ("requirements", "package_dependency"), ("competition", "competition_winner"),
               ("contest", "competition_winner"), ("benchmark", "benchmark_leader"),
               ("leaderboard", "benchmark_leader"), ("performance", "unusual_public_performance"),
               ("track_record", "unusual_public_performance"))


def _signal_for(via: str) -> str | None:
    low = str(via or "").lower()
    for token, sig in _VIA_SIGNAL:
        if token in low:
            return sig
    return None


def gather_signals(known_urls: set[str], *, conn: Any, roi_doc: Mapping[str, Any] | None,
                   delta_meta: Mapping[str, Mapping[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Spawn signals from material the desk ALREADY fetched. Nothing here crawls."""
    sigs: dict[str, dict[str, Any]] = {}

    def add(url: str, signal: str, name: str, evidence: str, **extra: Any) -> None:
        key = _norm_url(url)
        if not key or key in known_urls or key in sigs or not _code_host(url):
            return
        sigs[key] = {"signal": signal, "kind": "system", "name": name or key.split("/")[-1],
                     "url": url, "evidence": evidence[:300], **extra}

    if conn is not None:
        with contextlib.suppress(Exception):
            rows = conn.execute("SELECT url, kind, discovered_via, discovered_from, language, "
                                "country, meta_json FROM sources WHERE url IS NOT NULL "
                                "ORDER BY rowid DESC LIMIT 2000").fetchall()
            for r in rows:
                row = dict(r)
                url = str(row.get("url") or "")
                sig = _signal_for(str(row.get("discovered_via") or "") + " "
                                  + str(row.get("kind") or ""))
                if sig is None:
                    continue
                add(url, sig, url.rstrip("/").split("/")[-1],
                    f"registry source discovered via {row.get('discovered_via')} from "
                    f"{row.get('discovered_from')}; {str(row.get('meta_json') or '')[:200]}",
                    region=str(row.get("country") or "global"),
                    languages=[str(row.get("language") or "en")])
    intel = DESK / "data" / "intelligence"
    mentions: dict[str, list[tuple[str, str]]] = {}
    if intel.exists():
        files = [p for p in sorted(intel.rglob("*.json"), key=lambda p: p.stat().st_mtime)[-300:]
                 if DONATIONS.name not in p.parts]
        for p in files:
            doc = _read(p, None)
            rows2 = doc if isinstance(doc, list) else (doc or {}).get("discoveries") or []
            if not isinstance(rows2, list):
                continue
            for row in rows2[:300]:
                if not isinstance(row, dict):
                    continue
                url = str(row.get("url") or "")
                if _code_host(url):
                    text = " ".join(str(row.get(k) or "") for k in ("title", "text", "mechanism",
                                                                    "why"))[:400]
                    mentions.setdefault(_norm_url(url), []).append((p.parent.name, text))
    for key, seen in mentions.items():
        if len({d for d, _ in seen}) >= 2:
            add("https://" + key, "recurring_mention", key.split("/")[-1],
                f"mentioned by {len({d for d, _ in seen})} seats: {seen[0][1]}",
                text=" ".join(t for _, t in seen[:4]))
    src_roi = (roi_doc or {}).get("source_roi") if isinstance(roi_doc, Mapping) else None
    if isinstance(src_roi, Mapping):
        for sid, row in src_roi.items():
            if not isinstance(row, Mapping):
                continue
            roi = row.get("roi")
            if isinstance(roi, (int, float)) and roi > 0 and _code_host(str(sid)):
                add(str(sid), "high_source_roi_author", str(sid).rstrip("/").split("/")[-1],
                    f"source ROI {roi:.4f} with {row.get('credited_survivors')} credited "
                    f"survivors", region=str(row.get("region") or "global"))
    if CLAIMS_JSONL.exists():
        with contextlib.suppress(OSError):
            tail = CLAIMS_JSONL.read_bytes()[-2_000_000:].decode("utf-8", "replace").splitlines()
            for line in tail[-4000:]:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                sig = _signal_for(str(row.get("kind") or "") + " " + str(row.get("route") or ""))
                url = str(row.get("url") or row.get("code_url") or "")
                if sig and _code_host(url):
                    add(url, sig, url.rstrip("/").split("/")[-1],
                        str(row.get("text") or row.get("claim") or "")[:300],
                        region=str(row.get("region") or row.get("country") or "global"),
                        text=str(row.get("text") or "")[:400])
    for sid, meta in delta_meta.items():
        parent = meta.get("parent")
        if meta.get("fork") and parent:
            stars = meta.get("stars")
            add(str(parent), "contributor_graph", str(parent).rstrip("/").split("/")[-1],
                f"{sid} is a fork of this upstream ({stars} stars on the fork); the parent "
                f"lineage owns the mechanism")
    return list(sigs.values())[:limit]


def spawn_step(reg: FR.Registry, existing: Sequence[fed.ExternalSystem],
               signals: Sequence[Mapping[str, Any]], *, apply: bool, conn: Any, at: str,
               vocabulary: Iterable[str]) -> dict[str, Any]:
    """Each signal -> ExternalSystem -> `admit` -> a new roster row (donated through the
    federation organ's own door) or a DUPLICATE with lineage. Never breadth by renaming."""
    out: dict[str, Any] = {"signals": len(signals), "admitted": [], "duplicates": [],
                           "refused": [], "undisposed": [], "donated": 0}
    vocab = tuple(vocabulary)
    pool = list(existing)
    rows_out: list[dict[str, Any]] = []
    for sig in signals:
        url = str(sig.get("url") or "")
        sid = xfo._slug(url) if url else f"spawn_{FR.content_hash(sig)[:12]}"
        if sid in reg.rows:
            continue
        try:
            system = FR.system_from_signal(sig, system_id=sid, vocabulary=vocab)
        except ValueError as exc:
            out["refused"].append({"name": sig.get("name"), "why": str(exc)})
            continue
        decision = fed.admit(system, pool)
        row = FR.row_from_system(
            system, disposition=decision.disposition, why=decision.why,
            spawn_signal=str(sig.get("signal")),
            duplicate_family_id=decision.duplicate_of or system.system_id,
            authors_lineage=[decision.duplicate_of] if decision.duplicate_of else [],
            canonical_consumers=list(CANONICAL_CONSUMERS),
            historical_claims=[str(sig.get("evidence") or "")[:300]])
        reg.upsert(row, at=at)
        entry = {"system_id": sid, "url": url, "signal": sig.get("signal"),
                 "disposition": decision.disposition, "why": decision.why,
                 "duplicate_of": decision.duplicate_of, "novel_axes": list(decision.novel_axes)}
        if decision.disposition in fed.RUNNING_DISPOSITIONS:
            out["admitted"].append(entry)
            pool.append(system)
            rows_out.append({"kind": "spawn_signal", "url": url, "name": system.name,
                             "signal": sig.get("signal"), "system_id": sid,
                             "capabilities": list(system.capabilities),
                             "axes": list(system.axes), "region": system.region,
                             "languages": list(system.languages),
                             "disposition": decision.disposition, "why": decision.why,
                             "evidence": str(sig.get("evidence") or "")[:300],
                             "generator": GENERATOR, "origin": "EXTERNAL",
                             "provenance": {"authority": "a spawn signal is a hypothesis about "
                                                         "a source; the gauntlet judges its "
                                                         "descendants"}})
        elif decision.disposition == "DUPLICATE":
            out["duplicates"].append(entry)
        elif decision.disposition == "UNDISPOSED":
            out["undisposed"].append(entry)
        else:
            out["refused"].append(entry)
    if rows_out and apply:
        _write(DONATIONS / f"discoveries_{int(time.time())}.json", rows_out)
        out["donated"] = len(rows_out)
        if conn is not None:
            from libs.moat import registry as R
            for row in rows_out:
                with contextlib.suppress(Exception):
                    R.record_discovery(
                        kind="spawn_signal", origin="EXTERNAL", generator=GENERATOR,
                        source_id=f"ext:{row['system_id']}", source_type="spawn_signal",
                        mechanism=f"SPAWN {row['signal']}: {row['name']} brings "
                                  f"{row['axes']}"[:400],
                        exact_rule_if_known=row["url"][:400],
                        economic_rationale=row["evidence"],
                        payload={k: v for k, v in row.items() if k != "provenance"}, conn=conn)
    return out


# --------------------------------------------------------------------------- 4. techniques
def technique_exchange(conn: Any, roi_doc: Mapping[str, Any] | None, *, apply: bool, at: str,
                       deadline: float, limit: int = MAX_TECHNIQUES_PER_PASS) -> dict[str, Any]:
    """Every `technique` a forest recorded, judged on delayed yield; a survivor becomes a
    `technique_transfer` discovery for every other forest, naming the local equivalent."""
    out: dict[str, Any] = {"techniques": 0, "judged": [], "survivors": [], "transfers_created": 0,
                           "transfers_existing": 0, "unmeasured": []}
    if conn is None:
        out["unmeasured"].append("canonical registry unavailable: techniques UNMEASURED")
        return out
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM discoveries WHERE source_type='technique' ORDER BY created_at "
            "LIMIT ?", (limit,)).fetchall()]
    except Exception as exc:
        out["unmeasured"].append(f"discoveries unreadable: {type(exc).__name__}")
        return out
    out["techniques"] = len(rows)
    credit = ((roi_doc or {}).get("delayed_credit") or {}) if isinstance(roi_doc, Mapping) else {}
    by_disc = credit.get("by_discovery") if isinstance(credit, Mapping) else {}
    by_disc = by_disc if isinstance(by_disc, Mapping) else {}
    t = datetime.fromisoformat(at)
    from libs.moat import registry as R
    for row in rows:
        if time.monotonic() > deadline:
            out["unmeasured"].append("budget exhausted before every technique was judged")
            break
        did = str(row.get("discovery_id"))
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except ValueError:
            payload = {}
        method = payload.get("method") if isinstance(payload.get("method"), Mapping) else {}
        src_forest = str(payload.get("forest") or method.get("region") or "")
        name = str(method.get("technique") or row.get("mechanism") or did)[:120]
        yields: dict[str, Any] = {
            "descendants": 0, "later_discoveries_same_role": 0,
            "credited_survivors": int(by_disc.get(did, 0) or 0),
            "tested_cells": int(row.get("tested_cells") or 0),
            "generated_cells": int(row.get("generated_cells") or 0)}
        with contextlib.suppress(Exception):
            yields["descendants"] = len(R.descendants_of("discovery", did, conn=conn))
        with contextlib.suppress(Exception):
            got = conn.execute(
                "SELECT COUNT(*) AS n FROM discoveries WHERE generator=? AND created_at>? "
                "AND source_type<>'technique'", (row.get("generator"), row.get("created_at"))
            ).fetchone()
            yields["later_discoveries_same_role"] = int(dict(got)["n"] if got else 0)
        verdict, why = FR.technique_survival(row.get("created_at"), yields, now=t)
        judged = {"discovery_id": did, "technique": name, "forest": src_forest or UNMEASURED,
                  "survives": verdict, "why": why, "yield": yields}
        out["judged"].append(judged)
        if verdict is not True:
            continue
        out["survivors"].append(did)
        for fid, spec in F.FORESTS.items():
            if fid == src_forest:
                continue
            local = {"forest": fid, "name": spec.name, "languages": list(spec.languages),
                     "countries": list(spec.countries), "grounds": list(spec.grounds[:6]),
                     "source_class": method.get("source_class") or UNMEASURED}
            mech = (f"TECHNIQUE_TRANSFER {name} {src_forest or '?'} -> {fid}: hunt "
                    f"{local['source_class']} in {spec.name} "
                    f"({', '.join(spec.languages) or 'en'})")[:400]
            if not apply:
                out["transfers_created"] += 1
                continue
            try:
                new_id, created = R.record_discovery(
                    kind="technique_transfer", origin="EXTERNAL",
                    generator=f"{GENERATOR}:technique_exchange", source_id=f"forest:{fid}",
                    source_type="technique_transfer", mechanism=mech,
                    exact_rule_if_known=str(method.get("extraction_procedure") or "")[:400],
                    economic_rationale=f"a method that yielded in {src_forest} "
                                       f"({why}); the same source class exists here",
                    required_data=[str(local["source_class"])],
                    falsifier="no discovery from this technique in this forest after four passes",
                    parent_discovery_ids=[did],
                    payload={"kind": "technique_transfer", "technique": dict(method),
                             "from_forest": src_forest, "to_forest": fid,
                             "local_equivalent": local, "delayed_yield": yields,
                             "judged_at": at}, conn=conn)
            except Exception as exc:
                out["unmeasured"].append(f"{did}->{fid}: {type(exc).__name__}")
                continue
            if created:
                out["transfers_created"] += 1
                with contextlib.suppress(Exception):
                    R.link("discovery", did, "discovery", new_id, "transferred", conn=conn)
            else:
                out["transfers_existing"] += 1
    return out


# --------------------------------------------------------------------------- 5. twins
def twins_step(reg: FR.Registry, records: Sequence[Mapping[str, Any]], *, at: str
               ) -> dict[str, Any]:
    """The latest native and integrated run per system, compared at equal compute."""
    out: dict[str, Any] = {"measured": [], "unmeasured": []}
    by_sys: dict[str, dict[str, FR.TwinArm]] = {}
    for r in records:
        variant = str(r.get("variant") or "")
        if variant not in FR.TWIN_VARIANTS or r.get("compute_s") is None:
            continue
        by_sys.setdefault(str(r["system_id"]), {})[variant] = FR.TwinArm(
            variant=variant, run_id=str(r["run_id"]), compute_s=float(r["compute_s"]),
            candidates=int(r["candidates"]), unique_candidates=int(r["unique_candidates"]),
            mechanisms=int(r["mechanisms"]), representations=int(r["representations"]),
            datasets=int(r["datasets"]), effective_trials=int(r["effective_trials"]))
    for sid in reg.rows:
        arms = by_sys.get(sid) or {}
        rec = FR.twin_verdict(sid, arms.get("native"), arms.get("integrated"))
        rec["at"] = at
        if rec["verdict"] == UNMEASURED:
            if arms:
                reg.twins[sid] = rec
            out["unmeasured"].append(sid)
            continue
        reg.twins[sid] = rec
        out["measured"].append({"system_id": sid, "verdict": rec["verdict"],
                                "kept": rec["kept"]})
    return out


# --------------------------------------------------------------------------- 6. dashboard
def canonical_evidence(conn: Any, reg: FR.Registry, records: Sequence[Mapping[str, Any]],
                       yields: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """What the invariants beyond the eight terms need, from the canonical registry."""
    ev: dict[str, Any] = {"candidates_donated": None, "candidates_recorded": None,
                          "candidates_collapsed": 0, "stranded": None,
                          "verdict_fields_in_canonical": None}
    if records:
        ev["candidates_donated"] = sum(int(r["candidates"]) for r in records)
        ev["candidates_collapsed"] = sum(int(r["candidates"]) - int(r["unique_candidates"])
                                         for r in records)
        ev["candidates_recorded"] = sum(int(y.get("generated") or 0) for y in yields.values())
    if conn is None:
        return ev
    try:
        leaks = 0
        for r in conn.execute("SELECT payload_json FROM discoveries WHERE generator LIKE 'ext:%' "
                              "ORDER BY created_at DESC LIMIT 5000").fetchall():
            try:
                payload = json.loads(dict(r).get("payload_json") or "{}")
            except ValueError:
                continue
            if isinstance(payload, dict):
                leaks += sum(1 for k in payload if str(k).lower() in fed.PACKET_FORBIDDEN)
        ev["verdict_fields_in_canonical"] = leaks
        routed = {str(dict(r).get("source_id")) for r in conn.execute(
            "SELECT source_id FROM discoveries WHERE source_id LIKE 'ext:%'").fetchall()}
        stranded: list[str] = []
        for sid, row in reg.running().items():
            for cap in row.get("capabilities") or []:
                if f"ext:{sid}:{cap}" not in routed:
                    stranded.append(f"{sid}:{cap}")
        ev["stranded"] = stranded
    except Exception as exc:
        ev["unmeasured"] = f"canonical registry unreadable: {type(exc).__name__}"
    return ev


def control_plane_feed(first: Mapping[str, Any] | None, inv: Mapping[str, Mapping[str, Any]],
                       *, apply: bool, record: bool = True) -> dict[str, Any]:
    """The invariants in the control plane's own row shape, and the first broken one recorded
    as a fingerprint the reconciler carries into CONTROL_PLANE.json. The reconciler's twelve
    are a fixed tuple with no extension hook; a thirteenth bit is the named debt."""
    doc: dict[str, Any] = {"rows": dict(inv), "fed": False,
                           "invariant_test": "desks/mt5/tests/test_federation_ops.py::"
                                             "test_dashboard_names_the_first_broken_invariant"}
    try:
        from libs.ops.control_plane import fingerprints as fp
        from libs.ops.control_plane import reconciler as rc
    except Exception as exc:
        doc["debt"] = f"libs/ops/control_plane unavailable ({type(exc).__name__}): invariants " \
                      f"are published here only"
        return doc
    doc["table"] = f"libs.ops.control_plane.reconciler.INVARIANTS ({len(rc.INVARIANTS)} fixed)"
    doc["debt"] = ("reconciler.invariants() has no extension hook: FEDERATION_CLOSED_AND_HEALTHY "
                   "is published here and its first broken invariant is fed through the "
                   "fingerprint ledger the reconciler carries; a thirteenth row in "
                   "CONTROL_PLANE.json is owed to the control-plane owner")
    if first is not None and apply and record:
        with contextlib.suppress(Exception):
            row = fp.record(f"federation invariant broken: {first['invariant']}", GENERATOR,
                            invariant_test=doc["invariant_test"],
                            measured=first.get("measured"))
            doc["fed"] = bool(row.get("written"))
            doc["fingerprint"] = row.get("fingerprint")
    return doc


def dashboard(reg: FR.Registry, stats: Mapping[str, Mapping[str, Any]],
              inv: Mapping[str, Mapping[str, Any]], first: Mapping[str, Any] | None,
              steps: Mapping[str, Any], *, at: str, seconds: float, dry_run: bool
              ) -> dict[str, Any]:
    by_disp: dict[str, int] = {}
    by_health: dict[str, int] = {}
    for sid, row in reg.rows.items():
        d = str(row.get("disposition"))
        by_disp[d] = by_disp.get(d, 0) + 1
        h = str((stats.get(sid) or {}).get("health_state"))
        by_health[h] = by_health.get(h, 0) + 1
    rois = {sid: s.get("marginal_roi") for sid, s in stats.items()
            if isinstance(s.get("marginal_roi"), (int, float))}
    return {
        "at": at, "seconds": round(seconds, 1), "dry_run": dry_run,
        "law": ("LAWS 5h/5m: REGISTERED and SANDBOXED and SCHEDULED and EXECUTED and PROGRESSED "
                "and PRODUCED and CONSUMED and ATTRIBUTED for every DIRECT/WRAPPED/REBUILT row; "
                "every system delta-scanned and benchmark-twinned; scientific outputs, never "
                "uptime; the first broken invariant named"),
        "FEDERATION_CLOSED_AND_HEALTHY": first is None,
        "first_broken_invariant": first,
        "invariants": dict(inv),
        "systems": len(reg.rows), "running_rows": len(reg.running()),
        "by_disposition": by_disp, "by_health_state": by_health,
        "per_system": {sid: {**dict(stats.get(sid) or {}),
                             "disposition": reg.rows[sid].get("disposition"),
                             "duplicate_family_id": reg.rows[sid].get("duplicate_family_id"),
                             "commit_version": reg.rows[sid].get("commit_version"),
                             "next_upstream_delta_scan":
                                 reg.rows[sid].get("next_upstream_delta_scan")}
                       for sid in sorted(reg.rows)},
        "marginal_roi_ranking": sorted(rois.items(), key=lambda kv: -float(kv[1]))[:25],
        "twins": {sid: {"verdict": t.get("verdict"), "kept": t.get("kept"), "why": t.get("why")}
                  for sid, t in reg.twins.items()},
        "steps": dict(steps),
        "registry": {"path": str(REGISTRY_PATH), "content_hash": reg.content_hash(),
                     "history_entries": len(reg.history),
                     "history_valid": reg.history_valid()[0]},
        "consumers": {"registry": ["external_federation (roster via data/intelligence/"
                                   "federation_ops donations)", "check_external_federation"],
                      "technique_transfer": ["discovery_compiler (registry discoveries)",
                                             "forest_runner (DEBT: does not yet read "
                                             "technique_transfer rows for its scouts)"],
                      "delta_reopen": ["discovery_compiler", "source_civilizations"]},
    }


# --------------------------------------------------------------------------- the pass
def run_pass(*, budget_s: float = 600.0, dry_run: bool = False, no_fetch: bool = False,
             max_scan: int = MAX_SCAN_PER_PASS, fetch: Fetcher | None = None,
             registry_path: Path | None = None, report_path: Path | None = None
             ) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(5.0, budget_s * 0.9)
    at = now()
    apply = not dry_run
    reg_path = registry_path or REGISTRY_PATH
    steps: dict[str, Any] = {}
    try:
        reg = FR.Registry.load(reg_path)
        registry_ok = True
    except ValueError as exc:
        reg = FR.Registry()
        registry_ok = False
        steps["registry"] = {"unmeasured": f"registry unreadable, NOT overwritten: {exc}"}
    fed_state = xfo.load_state()
    sandboxes = sandbox_records()
    packets = packet_docs()
    records = run_records(packets, sandboxes)
    conn: Any = None
    try:                                # read in every mode; written only when `apply`
        from libs.moat import registry as R
        conn = R.connect()
    except Exception:
        conn = None
    try:
        systems = known_systems(reg, fed_state)
        steps["sync"] = sync_registry(reg, systems, fed_state, sandboxes, records, at=at)
        steps["delta"] = delta_scan_step(reg, fetch=fetch or desk_fetch, max_scan=max_scan,
                                         deadline=deadline, apply=apply, conn=conn, at=at,
                                         no_fetch=no_fetch)
        roi_doc = _read(ROI_REPORT, None)
        try:
            from research import source_civilizations as sc
            vocabulary: tuple[str, ...] = tuple(sc.SPAWN_SIGNALS)
        except Exception:
            vocabulary = ("citation_cluster", "contributor_graph", "stars_forks",
                          "conference_co_occurrence", "package_dependency",
                          "competition_winner", "benchmark_leader",
                          "unusual_public_performance", "high_source_roi_author",
                          "recurring_mention")
        known_urls = {_norm_url(str(s.upstream)) for s in systems} | {
            _norm_url(str(r.get("upstream_repo") or "")) for r in reg.rows.values()}
        signals = gather_signals(known_urls, conn=conn, roi_doc=roi_doc,
                                 delta_meta=steps["delta"].get("meta") or {},
                                 limit=MAX_SIGNALS_PER_PASS)
        steps["spawn"] = spawn_step(reg, systems, signals, apply=apply, conn=conn, at=at,
                                    vocabulary=vocabulary)
        steps["techniques"] = technique_exchange(conn, roi_doc, apply=apply, at=at,
                                                 deadline=deadline)
        steps["twins"] = twins_step(reg, records, at=at)
        yields = generator_yields(conn)
        stats = system_stats(reg, records, yields, roi_doc, descendants_in(SLEEVES),
                             descendants_in(FORWARD), seat_consumption())
        evidence = canonical_evidence(conn, reg, records, yields)
        inv = FR.invariants(reg.rows, stats, evidence, now=datetime.fromisoformat(at))
        first = FR.first_broken(inv)
        # The fingerprint ledger counts RECURRENCE, so the broken invariant is recorded when it
        # changes or once a day, never once an hour for the same unmoved fact.
        prev = _read(report_path or REPORT, None) or {}
        prev_first = ((prev.get("first_broken_invariant") or {}).get("invariant")
                      if isinstance(prev, dict) else None)
        prev_at = FR._parse(prev.get("at")) if isinstance(prev, dict) else None
        stale = prev_at is None or prev_at < datetime.fromisoformat(at) - timedelta(hours=24)
        steps["control_plane"] = control_plane_feed(
            first, inv, apply=apply,
            record=bool(first) and (stale or prev_first != (first or {}).get("invariant")))
        steps["evidence"] = evidence
        steps["inputs"] = {"federation_state": bool(fed_state.get("systems")),
                           "sandboxes": len(sandboxes), "packets": len(packets),
                           "run_records": len(records), "generator_yields": len(yields),
                           "roi_report": roi_doc is not None}
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
    doc = dashboard(reg, stats, inv, first, steps, at=at, seconds=time.monotonic() - t0,
                    dry_run=dry_run)
    if apply:
        if registry_ok:
            reg.save(reg_path, at=at)
        _write(report_path or REPORT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip upstream delta fetches (they read UNMEASURED this pass)")
    ap.add_argument("--max-scan", type=int, default=MAX_SCAN_PER_PASS)
    a = ap.parse_args(argv)
    doc = run_pass(budget_s=a.budget_s, dry_run=a.dry_run, no_fetch=a.no_fetch,
                   max_scan=a.max_scan)
    first = doc.get("first_broken_invariant") or {}
    steps = doc.get("steps") or {}
    print(f"federation ops: {doc['systems']} systems ({doc['running_rows']} running) "
          f"{doc['by_disposition']} | delta scanned "
          f"{len(steps.get('delta', {}).get('scanned', []))}"
          f" reopened {len(steps.get('delta', {}).get('reopened', []))} | spawn "
          f"{steps.get('spawn', {}).get('signals', 0)} signals, "
          f"{len(steps.get('spawn', {}).get('admitted', []))} admitted, "
          f"{len(steps.get('spawn', {}).get('duplicates', []))} duplicates | techniques "
          f"{steps.get('techniques', {}).get('techniques', 0)} judged, "
          f"{len(steps.get('techniques', {}).get('survivors', []))} survive, "
          f"{steps.get('techniques', {}).get('transfers_created', 0)} transfers | twins "
          f"{len(steps.get('twins', {}).get('measured', []))} | CLOSED_AND_HEALTHY="
          f"{doc['FEDERATION_CLOSED_AND_HEALTHY']} first broken: {first.get('invariant')} "
          f"({str(first.get('why'))[:80]}) in {doc['seconds']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
