#!/usr/bin/env python3
"""THE RUNTIME ATTESTATION: what actually ran on this host, in one small committed file.

    python desks/mt5/research/runtime_attestation.py --once --budget-s 180
    python scripts/check_runtime_attestation.py [--require-state]

THE PROBLEM THIS EXISTS FOR (a reviewer reading this repository from GitHub, 2026-09-23):

    "GitHub code is not current VPS reality. The runtime reports -- COEVOLUTION.json,
     EXPERIMENT_SPINE.json, SANDBOX_RUNNER.json and the rest -- are not committed, so I cannot
     verify from GitHub alone that each organ ran successfully this morning on the box. Comments
     in the code describe measured runs, but that is not the same as seeing runtime state."

That is correct and it is not fixable by committing the reports: `desks/mt5/reports/` is ~50 MB
of state the box owns and rewrites hourly, and a repository that carries it would be a repository
nobody can clone. A DOCSTRING IS NOT EVIDENCE, and neither is a green test that ran in CI on a
machine with no terminal, no MT5 and no artifacts. The gap between "the code that would do this
exists" and "it ran here, this morning, and left this" is exactly the gap LAWS 7 calls a defect,
and until now the only way across it was to be on the box.

THE MIDDLE PATH. One committed attestation, derived not written: for every organ the component
registry declares with an artifact of its own, this pass records the organ's name, the clock that
fires it, when it last ran and how that run ended, the artifact it owns, and that artifact's age,
size and SHA-256 -- plus a handful of scalar keys the organ itself publishes (rows, candidates,
survivors, defects), never a nested report body. Scalars and hashes only, so the file is ~200 KB
and stays that way by construction while the reports it describes stay where they belong.

A hash is not the body, and that is the point: a reader on GitHub sees WHICH build produced WHICH
artifact at WHAT time, and can ask for the body by name and check it against the hash published
before they asked. That is a weaker claim than holding the file and a far stronger one than a
comment, and it is the strongest claim a repository can carry about a machine it is not.

FOUR HONEST STATES AND NEVER A BLANK (L1.28a). An organ whose artifact is absent while something
recorded it running reads MISSING; one with neither artifact nor run record has NEVER run; one
whose artifact is older than its own derived max-silence reads STALE; only a present artifact
inside its cadence reads LIVE. An organ whose cadence this repo does not declare reads UNMEASURED
-- the registry cannot say when it should have run, so nothing here may say it is late. Absence
is never rendered as a pass, a zero or an empty cell.

IT ATTESTS TO ONE HOST AND REFUSES TO DESCRIBE ANOTHER. The document stamps the hostname,
platform and git SHA it was measured on, and every row carries that same host. A checkout on
another machine reads the file as a report ABOUT the box, never as a claim about itself, and
`scripts/check_runtime_attestation.py` fails on a document that mixes hosts or that goes stale on
the host it names. The role is measured too, not assumed: a host with no fresh gateway state says
so in its first line, so a build box attesting to itself can never read as the trading box.

Clock: `hourly_cycle:runtime_attestation` (department `meta`, layer `meta`).
Artifact: `docs/research/runtime_state.json` + `docs/research/RUNTIME_STATE.md` -- both COMMITTED,
because a fact nobody outside the box can read is not evidence.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import socket
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
# RUN AS A SCRIPT, `desks` IS NOT IMPORTABLE WITHOUT THIS (2026-09-29). The hourly leg runs this
# file by path with cwd desks/mt5, so sys.path[0] is desks/mt5/research and `organ_rows`'s
# `from desks.mt5.ops.components import registry` raised ModuleNotFoundError on every pass unless
# the host happened to export PYTHONPATH -- and the committed attestation sat at 2026-09-23.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: The one string for "this tree does not know" (L1.28a). Never a zero, never an empty cell.
UNMEASURED = "UNMEASURED"

#: The states an organ may be in. Every row carries exactly one and none of them is blank.
STATES: tuple[str, ...] = ("LIVE", "STALE", "MISSING", "NEVER", UNMEASURED)

#: THE DECLARED SUMMARY KEYS. A summary value is a SCALAR the organ already publishes at the top
#: level of its own artifact -- never a nested body, never a list, never a derived judgement of
#: ours. The set is declared here so the attestation's size is bounded by construction rather than
#: by whatever an organ happens to write next.
SUMMARY_KEYS: tuple[str, ...] = (
    "status", "verdict", "outcome", "ok", "state",
    "n", "rows", "count", "total", "examined", "written", "seeded",
    "candidates", "survivors", "promoted", "certified", "passed", "failed", "refused",
    "defects", "divergences", "n_divergences", "n_fatal", "stale", "gap", "coverage",
)

#: At most this many summary keys per organ, and this many characters per string value.
MAX_SUMMARY_KEYS = 6
MAX_SUMMARY_CHARS = 48

#: An artifact larger than this is hashed but NOT parsed: opening a 30 MB report for six scalars
#: would spend the whole budget on the two files least likely to hold them.
MAX_PARSE_BYTES = 8_000_000

#: The size the JSON is held under by construction. When rows would push past it, summaries are
#: dropped from the tail and the count of trimmed rows is published -- never a silent truncation.
#: 800 KB since 2026-09-29: the registry now reads each organ's own artifact declaration and the
#: law gate's record for its fences, so the attested set went from ~370 organs to ~800. Rows are
#: scalars and hashes only, so the bound still holds by construction; it scales with the roster.
MAX_JSON_BYTES = 800_000

#: How much of the event log one pass reads (its tail). The log is append-only and the last run of
#: each organ is near its end; reading it whole would grow without bound.
MAX_EVENT_BYTES = 4_000_000

#: This organ's own cadence, which is also what the fence judges its freshness against.
CADENCE_S = 3600
MAX_SILENCE_S = 2 * CADENCE_S

#: A gateway state older than this means this host is not running the live trading loop right now,
#: whatever else it is. Three hours is two gateway passes plus slack.
GATEWAY_FRESH_S = 3 * 3600


@dataclass(frozen=True)
class Paths:
    root: Path
    desk: Path
    events: Path
    ledger: Path
    release: Path
    gateway: Path
    out_json: Path
    out_md: Path
    ratchet: Path

    @classmethod
    def at(cls, root: Path | None = None) -> Paths:
        base = Path(root or ROOT)
        desk = base / "desks" / "mt5"
        return cls(
            ratchet=base / "docs" / "research" / "runtime_ratchet.json",
            root=base,
            desk=desk,
            events=desk / "data" / "events.jsonl",
            ledger=desk / "data" / "compute_ledger.jsonl",
            release=desk / "data" / "release_identity.json",
            gateway=desk / "data" / "gateway_state.json",
            out_json=base / "docs" / "research" / "runtime_state.json",
            out_md=base / "docs" / "research" / "RUNTIME_STATE.md",
        )


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _git_sha(root: Path) -> tuple[str, str]:
    """(sha, branch) read from `.git` directly -- no subprocess, so it costs nothing and cannot
    hang on a lock. UNMEASURED when the tree is not a checkout (an exported tarball, a container
    image), which is a fact about the reader's copy and not an error."""
    git = root / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return UNMEASURED, UNMEASURED
    if not head.startswith("ref:"):
        return (head or UNMEASURED), "DETACHED"
    ref = head.split(" ", 1)[1].strip()
    branch = ref.rsplit("/", 1)[-1]
    try:
        return (git / ref).read_text(encoding="utf-8").strip(), branch
    except OSError:
        pass
    try:
        for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0].strip(), branch
    except OSError:
        pass
    return UNMEASURED, branch


def _read_json(path: Path, max_bytes: int = MAX_PARSE_BYTES) -> dict[str, Any] | None:
    """The document, or None when absent, oversized or unreadable -- never {} for any of them."""
    try:
        if path.stat().st_size > max_bytes:
            return None
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def host_identity(paths: Paths) -> dict[str, Any]:
    """WHICH MACHINE THIS DESCRIBES, measured here and now, never assumed from a config.

    The role is derived from one measurement -- the age of the gateway's own state file -- and
    published WITH that measurement, so a host that is not running the live trading loop says so
    in its own first line instead of being read as the box by a reader who assumes.
    """
    sha, branch = _git_sha(paths.root)
    now = _now()
    try:
        gw_age: float | None = now - paths.gateway.stat().st_mtime
    except OSError:
        gw_age = None
    # A CHECKOUT RESETS st_mtime, AND gateway_state.json IS TRACKED (2026-09-29). A fresh clone
    # therefore read as `trading_host` for three hours, on a machine with no terminal at all. The
    # file's own stamps are the gateway's, so the role is judged by the OLDER of the two ages when
    # the file carries any: a checkout can make the file look new, never its contents.
    gw_doc = _read_json(paths.gateway) or {}
    stamps: list[float] = []
    for key in ("last_reconcile", "placement_pass", "updated_at", "at", "ts"):
        with contextlib.suppress(KeyError, TypeError, ValueError):
            stamps.append(datetime.fromisoformat(str(gw_doc[key]).replace("Z", "+00:00"))
                          .timestamp())
    if gw_age is not None and stamps:
        gw_age = max(gw_age, now - max(stamps))
    rel = _read_json(paths.release) or {}
    if gw_age is None:
        role, why = "non_trading_host", "no gateway_state.json on this host"
    elif gw_age < GATEWAY_FRESH_S:
        role, why = "trading_host", f"gateway_state.json is {gw_age / 3600:.1f}h old (fresh)"
    else:
        role, why = ("non_trading_host",
                     f"gateway_state.json is {gw_age / 3600:.1f}h old -- no live trading loop "
                     f"is attested by this document")
    return {
        "hostname": socket.gethostname(),
        "platform": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "role": role,
        "role_evidence": why,
        "gateway_state_age_h": None if gw_age is None else round(gw_age / 3600, 2),
        "measured_at": _iso(now),
        "git_sha": sha,
        "git_branch": branch,
        "release_seal": {
            "ok": rel.get("ok", UNMEASURED),
            "running_sha": str(rel.get("running_sha") or UNMEASURED)[:40],
            "release_sha": str(rel.get("release_sha") or UNMEASURED)[:40],
            "verdict": str(rel.get("verdict") or UNMEASURED)[:64],
            "age_h": rel.get("age_h", UNMEASURED),
        } if rel else {"ok": UNMEASURED, "running_sha": UNMEASURED,
                       "release_sha": UNMEASURED, "verdict": UNMEASURED, "age_h": UNMEASURED},
    }


def _tail_lines(path: Path, max_bytes: int) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()                       # drop the partial first line
            raw = fh.read()
    except OSError:
        return []
    return raw.decode("utf-8", errors="replace").splitlines()


def run_index(paths: Paths) -> dict[str, dict[str, Any]]:
    """leg -> {at, outcome, source}: the LAST recorded run of each organ, from the two logs the
    desk already keeps. `events.jsonl` carries LEG_DONE/LEG_FAILED with the organ's own scalars;
    `compute_ledger.jsonl` carries the cycle's own accounting. An organ in neither has no run
    record on this host, which is what makes NEVER distinguishable from MISSING."""
    out: dict[str, dict[str, Any]] = {}

    def put(name: str, at: str, outcome: str, source: str, extra: dict[str, Any]) -> None:
        if not name or not at:
            return
        prev = out.get(name)
        if prev is None or str(at) >= str(prev["at"]):
            out[name] = {"at": str(at)[:25], "outcome": str(outcome or UNMEASURED)[:24],
                         "source": source, "published": extra}

    for line in _tail_lines(paths.events, MAX_EVENT_BYTES):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        name = str(d.get("leg") or d.get("organ") or "")
        kind = str(d.get("kind") or "")
        outcome = d.get("outcome") or ("failed" if kind == "LEG_FAILED" else kind or UNMEASURED)
        scalars = {k: v for k, v in d.items()
                   if k in SUMMARY_KEYS and isinstance(v, (int, float, bool, str))}
        put(name, str(d.get("at") or ""), str(outcome), "events.jsonl", scalars)

    for line in _tail_lines(paths.ledger, MAX_EVENT_BYTES):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        put(str(d.get("run") or ""), str(d.get("at") or ""), str(d.get("outcome") or ""),
            "compute_ledger.jsonl", {})
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return UNMEASURED
    return h.hexdigest()


def _summary(path: Path, size: int) -> dict[str, Any]:
    """The declared scalar keys this artifact publishes at its top level, truncated.

    Never the body. An artifact too large to parse, or one that is not a JSON object, carries the
    reason as its single entry -- a named absence, which is a measurement.
    """
    if size > MAX_PARSE_BYTES:
        return {"_": f"{UNMEASURED} (artifact {size / 1e6:.1f} MB, not parsed within budget)"}
    doc = _read_json(path)
    if doc is None:
        return {"_": f"{UNMEASURED} (not a readable JSON object)"}
    out: dict[str, Any] = {}
    for k in SUMMARY_KEYS:
        if k not in doc:
            continue
        v = doc[k]
        if isinstance(v, (bool, int, float)):
            out[k] = v
        elif isinstance(v, str):
            out[k] = v[:MAX_SUMMARY_CHARS]
        if len(out) >= MAX_SUMMARY_KEYS:
            break
    return out


def _state(exists: bool, age_s: float | None, max_silence_s: int | None,
           ran: bool) -> tuple[str, str]:
    """The four honest states and the fifth that refuses to guess. Order matters: MISSING and
    NEVER are about the artifact's ABSENCE and must be decided before any freshness arithmetic
    that would otherwise divide by a cadence nobody declared."""
    if not exists:
        return ("MISSING", "artifact absent, but this host recorded a run") if ran else \
               ("NEVER", "no artifact and no run record on this host")
    if max_silence_s is None or age_s is None:
        return UNMEASURED, "artifact present; this repo declares no cadence to judge it against"
    if age_s > max_silence_s:
        return "STALE", (f"artifact {age_s / 3600:.1f}h old, past its "
                         f"{max_silence_s / 3600:.1f}h max silence")
    return "LIVE", f"artifact {age_s / 3600:.1f}h old, inside its cadence"


#: Where a state artifact lives on this desk. Used ONLY to find a declared basename that the
#: declaration put in the wrong directory -- never to invent an artifact nobody declared.
STATE_DIRS: tuple[str, ...] = (
    "desks/mt5/reports", "desks/mt5/reports/shadow", "desks/mt5/data", "desks/mt5/data/hypotheses",
    "docs/research", "data", "web", "reports/shadow",
)


def resolve_artifact(root: Path, outputs: tuple[str, ...]) -> tuple[str, str, float | None, int]:
    """(path, how, age_s, bytes) for the artifact that PROVES this organ ran.

    A component may declare several outputs; an organ is live if the FRESHEST of them is fresh,
    because writing any one of its declared artifacts is the organ running. When none of the
    declared paths exists, the same basename is looked for in the desk's state directories: a
    declaration that says `reports/X.json` while the organ writes `data/X.json` is a defect in the
    DECLARATION, and reading it as a dead organ hides a live one behind a typo. The relocation is
    published as `how` so the defect stays visible instead of being silently absorbed (L1.28a).
    """
    best: tuple[str, str, float, int] | None = None
    for rel in outputs:
        try:
            st = (root / rel).stat()
        except OSError:
            continue
        age = _now() - st.st_mtime
        if best is None or age < best[2]:
            best = (rel, "declared", age, int(st.st_size))
    if best is not None:
        return best
    for rel in outputs:
        name = rel.rsplit("/", 1)[-1]
        for d in STATE_DIRS:
            cand = f"{d}/{name}"
            if cand == rel:
                continue
            try:
                st = (root / cand).stat()
            except OSError:
                continue
            age = _now() - st.st_mtime
            if best is None or age < best[2]:
                best = (cand, f"relocated (declared {rel})", age, int(st.st_size))
        if best is not None:
            return best
    return (outputs[0] if outputs else UNMEASURED), "absent", None, 0


def organ_rows(paths: Paths, budget_s: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One row per organ the component registry declares WITH AN ARTIFACT OF ITS OWN.

    SCOPE IS STATED, NOT IMPLIED. A component that declares no output has nothing to attest to --
    there is no file whose hash would prove it ran -- so it is counted in `scope.excluded` with
    its reason rather than rendered as an empty row. `scripts/check_component_registry.py` is the
    fence for the registry's completeness; this one attests to what the registry declares.
    """
    from desks.mt5.ops.components import registry  # local: heavy import, one pass only

    reg = registry(paths.root)
    runs = run_index(paths)
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    excluded = 0
    hash_skipped = 0
    relocated = 0

    for spec in reg:
        if not spec.outputs:
            excluded += 1
            continue
        leg = spec.schedule.split(":", 1)[1].split()[0] if spec.schedule.startswith(
            "hourly_cycle:") else spec.component_id.split(":", 1)[-1]
        run = runs.get(leg) or runs.get(spec.component_id)
        art_rel, how, age, size = resolve_artifact(paths.root, tuple(spec.outputs))
        art = paths.root / art_rel
        exists = age is not None
        if how.startswith("relocated"):
            relocated += 1
        state, why = _state(exists, age, spec.max_silence_s, run is not None)
        if how.startswith("relocated"):
            why = f"{why}; DECLARATION DEFECT: {how}"
        over_budget = (time.monotonic() - started) > budget_s
        if exists and not over_budget:
            sha = _sha256(art)
            summary = _summary(art, size)
        elif exists:
            hash_skipped += 1
            sha = f"{UNMEASURED} (budget exhausted)"
            summary = {"_": f"{UNMEASURED} (budget exhausted)"}
        else:
            sha, summary = UNMEASURED, dict(run["published"]) if run else {}
        rows.append({
            "organ": spec.component_id,
            "kind": spec.kind,
            # The file(s) that ARE the organ, so a reader -- and the birth fence -- can find the
            # row for `run_desk_self_heal.py` when its clock names it `leg:desk_self_heal`.
            "code": [p for p in spec.code_paths if p != "desks/mt5/research/hourly_cycle.py"],
            "clock": spec.schedule if spec.scheduled else UNMEASURED,
            "cadence_s": spec.cadence_s,
            "max_silence_s": spec.max_silence_s,
            "state": state,
            "why": why,
            "last_run_at": run["at"] if run else UNMEASURED,
            "last_run_outcome": run["outcome"] if run else UNMEASURED,
            "last_run_source": run["source"] if run else UNMEASURED,
            "artifact": art_rel,
            "artifact_declared": spec.outputs[0] if spec.outputs else UNMEASURED,
            "artifact_resolved_by": how,
            "artifact_declared_n": len(spec.outputs),
            "artifact_age_s": None if age is None else int(age),
            "artifact_bytes": size,
            "artifact_sha256": sha,
            "summary": summary,
            "progress_metric": spec.progress_metric,
            "consumer": (spec.consumers[0][:80] if spec.consumers else UNMEASURED),
        })

    rows.sort(key=lambda r: (STATES.index(r["state"]) if r["state"] in STATES else 9,
                             str(r["organ"])))
    scope = {
        "attested": len(rows),
        "excluded": excluded,
        "excluded_reason": "component declares no output artifact -- nothing to hash; the "
                           "registry's own completeness is check_component_registry.py",
        "registry_components": len(reg),
        "declaration_defects": relocated,
        "declaration_defects_reason": "the component declares an artifact path the organ does "
                                      "not write, while the same basename is present elsewhere "
                                      "in the desk's state -- repair the declaration",
        "hash_skipped_over_budget": hash_skipped,
        "wall_s": round(time.monotonic() - started, 2),
    }
    return rows, scope


def _trim(doc: dict[str, Any], only: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Hold the file under MAX_JSON_BYTES BY CONSTRUCTION, and say so when it bites.

    Summaries are the only variable-width field here, so they are what goes -- from the LIVE tail
    first, because a live organ's scalars are the least load-bearing thing in the document and a
    defect row's are the most. The count is published; a silent truncation would make the file
    exactly the kind of evidence this organ exists to replace.
    """
    trimmed = 0
    mark = {"_": f"{UNMEASURED} (trimmed to hold the file under {MAX_JSON_BYTES // 1000} KB)"}
    # A TRIMMED ROW IS NOT A VICTIM AGAIN (2026-09-29). The replacement summary is itself a
    # non-empty dict, so `r.get("summary")` kept selecting the row it had just trimmed: whenever
    # the document could not be brought under the cap, this loop never ended. It surfaced the day
    # the registry began declaring each organ's own artifact and the attested set doubled.
    # `only` (--only-missing): the rows this pass appended are the ONLY ones it may touch, so the
    # victims are drawn from them -- LIVE first, as in a full pass, then any other appended row --
    # and the published count is ADDED to the committed one rather than replacing it.
    pool = doc["organs"] if only is None else only
    ids = {id(r) for r in pool}
    order = [r for r in reversed(doc["organs"]) if id(r) in ids]
    if only is not None:
        order = ([r for r in order if r["state"] == "LIVE"]
                 + [r for r in order if r["state"] != "LIVE"])
    while len(json.dumps(doc, default=str)) > MAX_JSON_BYTES:
        victim = next((r for r in order
                       if (only is not None or r["state"] == "LIVE") and r.get("summary")
                       and r["summary"] != mark), None)
        if victim is None:
            break
        victim["summary"] = dict(mark)
        trimmed += 1
    if only is None:
        doc["scope"]["summaries_trimmed"] = trimmed
    else:
        doc["scope"]["summaries_trimmed"] = int(doc["scope"].get("summaries_trimmed", 0)) + trimmed
    return doc


def attest(paths: Paths | None = None, budget_s: float = 180.0) -> dict[str, Any]:
    p = paths or Paths.at()
    rows, scope = organ_rows(p, budget_s)
    census = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
    host = host_identity(p)
    doc: dict[str, Any] = {
        "schema": "runtime_attestation/1",
        "generated_at": host["measured_at"],
        "cadence_s": CADENCE_S,
        "max_silence_s": MAX_SILENCE_S,
        "attests_to_host": host["hostname"],
        "host": host,
        "census": census,
        "scope": scope,
        "states": {
            "LIVE": "artifact present and newer than the organ's derived max silence",
            "STALE": "artifact present but older than the organ's derived max silence",
            "MISSING": "artifact absent while this host recorded the organ running",
            "NEVER": "no artifact and no run record on this host",
            UNMEASURED: "artifact present, cadence undeclared -- nothing here may call it late",
        },
        "organs": rows,
    }
    return _trim(doc)


#: The three counts that may only ever fall on a given host. LIVE is deliberately NOT ratcheted:
#: it moves with the registry's size, and a ratchet on it would fail the day an organ is retired.
RATCHET_KEYS: tuple[str, ...] = ("STALE", "MISSING", "NEVER")


def ratchet_update(paths: Paths, host: str, census: dict[str, int],
                   git_sha: str = UNMEASURED) -> dict[str, Any]:
    """Lower this host's floor for STALE/MISSING/NEVER, and never raise it.

    ALL LIVE IS A RATCHET, NOT A PHOTOGRAPH (the principal's order, 2026-09-23). A census is a
    number that drifts back the week after someone reads it; a floor that only falls is what
    makes the reading stick. The organ records the best this host has ever achieved and
    `scripts/check_runtime_attestation.py` fails when today's census is above it -- so a leg that
    stops, an artifact that disappears or a clock that is removed is a fence failure on the box
    that owns it, rather than a worse number nobody diffed.
    """
    doc = _read_json(paths.ratchet) or {"schema": "runtime_ratchet/1", "hosts": {}}
    hosts = doc.get("hosts")
    if not isinstance(hosts, dict):
        hosts = {}
    _prev = hosts.get(host)
    prev: dict[str, Any] = _prev if isinstance(_prev, dict) else {}
    floor: dict[str, Any] = {}
    lowered: list[str] = []
    for k in RATCHET_KEYS:
        cur = int(census.get(k, 0))
        was = prev.get(k)
        if isinstance(was, int) and was < cur:
            floor[k] = was
        else:
            floor[k] = cur
            if isinstance(was, int) and cur < was:
                lowered.append(f"{k} {was}->{cur}")
    floor["at"] = _iso(_now())
    floor["git_sha"] = str(git_sha)[:40]
    floor["attested"] = int(sum(census.get(k, 0) for k in STATES))
    hosts[host] = floor
    doc["hosts"] = hosts
    doc["note"] = ("Per-host floors for the runtime attestation. These numbers may only FALL. "
                   "scripts/check_runtime_attestation.py fails when a host's current census is "
                   "above its floor here -- that is what makes 'all organs live' a ratchet "
                   "instead of a number that drifts back next week.")
    with contextlib.suppress(OSError):                       # pragma: no cover - disk only
        _atomic(paths.ratchet, json.dumps(doc, indent=1, sort_keys=False))
    return {"floor": floor, "lowered": lowered}


def attest_only_missing(paths: Paths, budget_s: float = 180.0) -> dict[str, Any]:
    """APPEND rows for organs the committed attestation has no row for, and touch nothing else.

    WHY THIS EXISTS (2026-09-30). A PR that adds organs must also add their attestation rows, or
    `scripts/check_birth_obligations.py` fails the merge. Resolving `runtime_state.json` by taking
    one side wholesale either drops the PR's new rows (take LIVE) or rewrites every shared row
    with the PR author's machine state (take the PR, or re-run a full pass on a sparse tree --
    which flipped 89 shared rows on #140). Splicing rows in by hand is audit tampering. This is
    the third way: LIVE's committed file is the base, and the only thing added to it is a row
    WRITTEN BY THIS ORGAN for each organ the registry declares that the file does not yet name.

    Guarantees, pinned by tests: every existing row is left byte-identical (never rewritten,
    re-attested or flipped); rows are only appended; census and `scope.attested` move by the
    added rows alone; the host stamp, `generated_at` and the ratchet are left as the attesting
    host wrote them; a second run adds nothing; appended rows carry `measured_on`/`measured_at`
    and, off the attesting host, read NEVER or UNMEASURED rather than this machine's mtimes; the
    size trim runs over the appended rows only. Run it on a FULL tree -- on a sparse one the
    registry cannot see every organ's source, and absence there would be read as NEVER.
    """
    _doc = _read_json(paths.out_json, max_bytes=MAX_JSON_BYTES * 8)
    if _doc is None or not isinstance(_doc.get("organs"), list):
        raise FileNotFoundError(f"{paths.out_json}: no committed attestation to append to -- "
                                f"run a full --once pass on the attesting host first")
    doc: dict[str, Any] = _doc
    have = {str(r.get("organ")) for r in doc["organs"] if isinstance(r, dict)}
    rows, _scope = organ_rows(paths, budget_s)
    added = [r for r in rows if str(r["organ"]) not in have]
    if not added:
        return {"doc": doc, "added": []}
    # A ROW'S STATE IS A FACT ABOUT THE HOST THAT MEASURED IT. LIVE/STALE/MISSING are read off
    # file mtimes and run records on whatever machine runs this pass, so the same organ could
    # read LIVE here and STALE on the box. Every appended row is stamped with where and when it
    # was measured, and OFF the attesting host (the one the document's `host` stamp names) its
    # state is not taken from this machine at all: NEVER when nothing of it exists here either,
    # UNMEASURED otherwise -- this host cannot say whether the box ran it or how fresh it is.
    here = socket.gethostname()
    _h = doc.get("host")
    attesting = str((_h if isinstance(_h, dict) else {}).get("hostname")
                    or doc.get("attests_to_host") or UNMEASURED)
    on_host = attesting == here
    at = _iso(_now())
    for r in added:
        r["measured_on"] = here
        r["measured_at"] = at
        if not on_host:
            local = r["state"]
            r["state"] = "NEVER" if local == "NEVER" else UNMEASURED
            r["why"] = (f"appended by --only-missing on {here}, not the attesting host "
                        f"{attesting}: its state there is unmeasured (read {local} here)"
                        if r["state"] == UNMEASURED else
                        f"appended by --only-missing on {here}: no artifact and no run record "
                        f"here, and the attesting host {attesting} has never attested it")
    doc["organs"].extend(added)
    _c = doc.get("census")
    census: dict[str, Any] = _c if isinstance(_c, dict) else {}
    for r in added:
        census[r["state"]] = int(census.get(r["state"], 0)) + 1
    doc["census"] = census
    _s = doc.get("scope")
    scope: dict[str, Any] = _s if isinstance(_s, dict) else {}
    scope["attested"] = int(scope.get("attested", 0)) + len(added)
    log = scope.get("only_missing_appended")
    log = list(log) if isinstance(log, list) else []
    log.append({"at": at, "host": here, "on_attesting_host": on_host,
                "organs": [str(r["organ"]) for r in added]})
    scope["only_missing_appended"] = log
    doc["scope"] = scope
    _trim(doc, only=added)
    return {"doc": doc, "added": added}


def _age(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return UNMEASURED
    h = seconds / 3600.0
    return f"{h:.1f}h" if h < 72 else f"{h / 24:.1f}d"


def _size(n: Any) -> str:
    if not isinstance(n, (int, float)) or n <= 0:
        return "-"
    return f"{n / 1e6:.1f}M" if n >= 1e6 else (f"{n / 1e3:.0f}K" if n >= 1000 else f"{int(n)}B")


def _summary_line(row: dict[str, Any]) -> str:
    s = row.get("summary") or {}
    if not s:
        return UNMEASURED
    return "; ".join(f"{k}={v}" for k, v in s.items() if k != "_") or str(s.get("_", UNMEASURED))


def render(doc: dict[str, Any]) -> str:
    """The same facts as a page a reviewer can open on GitHub without running anything."""
    h = doc["host"]
    c = doc["census"]
    sc = doc["scope"]
    out: list[str] = []
    out.append("# RUNTIME STATE -- what actually ran on the box")
    out.append("")
    out.append("<!-- DERIVED. Written by desks/mt5/research/runtime_attestation.py on the clock "
               "`hourly_cycle:runtime_attestation`. Edit the organ, never this file. -->")
    out.append("")
    out.append(f"**This document attests to ONE host: `{h['hostname']}` "
               f"({h['platform']}), and describes no other machine.** Role measured as "
               f"`{h['role']}`: {h['role_evidence']}.")
    out.append("")
    out.append(f"- Measured at **{h['measured_at']}** (cadence {doc['cadence_s'] // 60} min; "
               f"stale past {doc['max_silence_s'] // 60} min)")
    out.append(f"- Tree: `{h['git_sha'][:12]}` on `{h['git_branch']}`; release seal "
               f"ok=`{h['release_seal']['ok']}` running=`{h['release_seal']['running_sha'][:12]}` "
               f"sealed=`{h['release_seal']['release_sha'][:12]}`")
    out.append(f"- Organs attested **{sc['attested']}** of {sc['registry_components']} registry "
               f"components ({sc['excluded']} declare no artifact, so there is nothing to hash: "
               f"{sc['excluded_reason']})")
    out.append(f"- Pass cost {sc['wall_s']}s; {sc['hash_skipped_over_budget']} hash(es) skipped "
               f"over budget; {sc.get('summaries_trimmed', 0)} summary/-ies trimmed for size")
    out.append("")
    out.append("| state | organs | meaning |")
    out.append("|---|---:|---|")
    for s in STATES:
        out.append(f"| **{s}** | {c.get(s, 0)} | {doc['states'][s]} |")
    out.append("")
    out.append("The hash is not the body. `desks/mt5/reports/**` is ~50 MB the box rewrites "
               "hourly and this repository deliberately does not carry it; the SHA-256 below "
               "lets a reader ask for any one artifact by name and check that what arrives is "
               "what this host published at the time stamped here.")
    out.append("")
    for s in STATES:
        rows = [r for r in doc["organs"] if r["state"] == s]
        if not rows:
            continue
        out.append(f"## {s} ({len(rows)})")
        out.append("")
        out.append("| organ | clock | last run | artifact | age | size | sha256 | published |")
        out.append("|---|---|---|---|---:|---:|---|---|")
        for r in rows:
            sha = str(r["artifact_sha256"])
            sha = sha[:16] if sha != UNMEASURED and not sha.startswith(UNMEASURED) else sha
            out.append(
                f"| `{r['organ']}` | `{r['clock']}` | {r['last_run_at']} "
                f"{r['last_run_outcome']} | `{r['artifact']}` | {_age(r['artifact_age_s'])} | "
                f"{_size(r['artifact_bytes'])} | `{sha}` | {_summary_line(r)} |")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one attestation pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=180.0)
    ap.add_argument("--root", type=Path, default=ROOT, help="repo root (tests)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only-missing", action="store_true",
                    help="append rows ONLY for organs the committed attestation lacks; every "
                         "existing row, the host stamp and the ratchet are left untouched "
                         "(merge resolution -- run on a FULL tree)")
    a = ap.parse_args(argv)
    paths = Paths.at(Path(a.root))
    if a.only_missing:
        try:
            res = attest_only_missing(paths, budget_s=float(a.budget_s))
        except FileNotFoundError as exc:
            print(f"runtime_attestation --only-missing: NOT written ({exc})")
            return 1
        if res["added"]:
            try:
                _atomic(paths.out_json,
                        json.dumps(res["doc"], indent=1, default=str, sort_keys=False))
                _atomic(paths.out_md, render(res["doc"]))
            except OSError as exc:
                print(f"runtime_attestation --only-missing: NOT written "
                      f"({type(exc).__name__}: {exc})")
                return 1
        names = ", ".join(f"{r['organ']} ({r['state']})" for r in res["added"])
        print(f"runtime_attestation --only-missing: appended {len(res['added'])} row(s)"
              + (f": {names}" if names else " -- every registry organ already has a row"))
        return 0
    doc = attest(paths, budget_s=float(a.budget_s))
    rat = ratchet_update(paths, doc["attests_to_host"], doc["census"],
                         str(doc["host"].get("git_sha") or UNMEASURED))
    doc["ratchet"] = rat["floor"]
    try:
        _atomic(paths.out_json, json.dumps(doc, indent=1, default=str, sort_keys=False))
        _atomic(paths.out_md, render(doc))
    except OSError as exc:
        print(f"runtime_attestation: NOT written ({type(exc).__name__}: {exc})")
        return 1
    try:
        from libs.ops import events
        events.emit("STATE_PUBLISHED", path=paths.events, leg="runtime_attestation",
                    host=doc["attests_to_host"], organs=doc["scope"]["attested"],
                    live=doc["census"]["LIVE"], stale=doc["census"]["STALE"],
                    missing=doc["census"]["MISSING"], never=doc["census"]["NEVER"])
    except Exception:                                       # pragma: no cover - event log only
        pass
    if a.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "organs"}, indent=1, default=str))
    else:
        c = doc["census"]
        print(f"runtime_attestation: host {doc['attests_to_host']} ({doc['host']['role']}) "
              f"{doc['scope']['attested']} organ(s): LIVE {c['LIVE']}, STALE {c['STALE']}, "
              f"MISSING {c['MISSING']}, NEVER {c['NEVER']}, {UNMEASURED} {c[UNMEASURED]}; "
              f"{doc['scope']['wall_s']}s -> {paths.out_json.name} + {paths.out_md.name}")
        f = rat["floor"]
        print(f"   ratchet floor for {doc['attests_to_host']}: STALE {f['STALE']}, "
              f"MISSING {f['MISSING']}, NEVER {f['NEVER']}"
              + (f" (lowered: {', '.join(rat['lowered'])})" if rat["lowered"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
