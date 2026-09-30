"""Source provenance: where every candidate came from, from the producer's row to the docket.

    source_url    the external page the row was read from ("" when the source is not a URL)
    source_id     a stable id for the source when there is no URL: the producer's own id if it
                  names one, otherwise the ARTIFACT COORDINATE `<relative path>#<row index>`
    ground        the ground / host / seat the row belongs to
    retrieved_at  when the producer retrieved it (the producer's own stamp; the artifact's mtime
                  only when the row carries none, and `retrieved_at_basis` says which)
    content_hash  the source's own content hash when the producer recorded one, else the sha256
                  of the row exactly as the compiler read it

WHY (six-event trace, 2026-09-30). 0 of 53,174 compiled candidates carried a `source_url`. The
field existed on every candidate and was empty on every one: `_candidate` read `url`/`link` off
the row and nothing else, most producers never wrote either, and nothing recorded WHICH row in
WHICH artifact a candidate was minted from. A cell whose origin cannot be named cannot be traced
back to the mechanism that justified it, and event 1 of the trace ("source mined into a cell")
was stale for exactly that reason.

WHAT IS COUNTED AS PROVENANCE, and why an internal producer is not a failure. A candidate is
PROVENANCED when it carries a content hash, a retrieval time, and EITHER an external URL OR a
source id. The desk's own generators (discovery_compiler, video_anchor_exit, the standing
questions) read no web page; their honest provenance is the artifact coordinate, and demanding a
URL from them would push the measurement toward dropping internal producers, which is the
opposite of what the desk wants. The external-URL share is published beside it, never fenced.

This module never fetches, never reads a secret, and never drops a row: it only names things.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The provenance keys, in the order they are stamped. `retrieved_at_basis` rides along.
FIELDS: tuple[str, ...] = ("source_url", "source_id", "ground", "retrieved_at", "content_hash")

#: THE FOUR KEYS A ROW NAMES ITS SOURCE BY, in the ONE order every reader uses (audit
#: 2026-09-30). `url`/`link` first because that is what the compiler has always hashed into the
#: seed key and the deepening task id, so a row that carries them keeps every historical join;
#: then `source_url` (this branch's producers) and `source_uri` (the MT5 global mining pipeline,
#: `lead_schema`, `factory_federation`), which were silently read as "no source" before.
URL_FIELDS: tuple[str, ...] = ("url", "link", "source_url", "source_uri")

#: Keys a producer has used for the page a row was read from, most specific first. Only values
#: that are http(s) URLs count as a `source_url`; anything else (kimi://, deepseek://) is an id.
URL_KEYS: tuple[str, ...] = ("source_url", "source_uri", "url", "link", "href", "permalink",
                             "canonical_source", "page_url", "feed")


def source_url_of(row: Mapping[str, Any]) -> Any:
    """THE source-URL read: the first non-empty of `URL_FIELDS`, RAW (never stringified or
    filtered), else "".

    Raw because the seed key (`hypothesis_graph.seed_key_of`), `lead_schema.row_cell_key` and the
    deepening task id all hash exactly this value and `json.dumps` renders a non-string
    differently; every one of them now calls this, so the two ends of each join cannot drift. A
    value that is not http(s) is still the row's source identity (kimi://, a DOI); whether it is
    an EXTERNAL URL is `is_external_url`'s question, not this one's.
    """
    for k in URL_FIELDS:
        v = row.get(k)
        if v not in (None, "") and not (isinstance(v, str) and not v.strip()):
            return v
    return ""


def is_external_url(v: Any) -> bool:
    """An http(s) URL -- the only thing the external-URL floor counts."""
    return _is_url(v)

#: Keys a producer has used for when it retrieved or first saw a row, most specific first.
#: Measured over 220,465 committed intelligence rows 2026-09-30: `found_at` (156,836), `date`,
#: `captured_at`, `available_time`/`ingested_time`, `published_at`, `harvested_utc`, `mined_at`.
TIME_KEYS: tuple[str, ...] = ("retrieved_at", "fetched_utc", "fetched_at", "captured_at",
                              "found_at", "harvested_utc", "collected_at", "mined_at",
                              "available_time", "ingested_time", "first_seen_at", "observed_at",
                              "generated_at", "published_utc", "published_at", "published_time",
                              "timestamp", "at", "date")

#: Keys a producer has used for the hash of the document it read.
HASH_KEYS: tuple[str, ...] = ("content_hash", "source_hash", "payload_hash", "vault_sha",
                              "claim_hash")

#: Keys that name the ground a row belongs to.
GROUND_KEYS: tuple[str, ...] = ("ground", "host", "seat", "source")


def _is_url(v: Any) -> bool:
    return isinstance(v, str) and v.strip().lower().startswith(("http://", "https://"))


def row_hash(row: Mapping[str, Any]) -> str:
    """sha256 of the row exactly as the compiler dedupes it (sorted keys, compact separators)."""
    payload = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _first_provenance(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """The first telling of a row that carries a `provenance` list/dict (deep forest tasks)."""
    prov = row.get("provenance")
    if isinstance(prov, list) and prov and isinstance(prov[0], Mapping):
        return prov[0]
    if isinstance(prov, Mapping):
        return prov
    return {}


def extract(row: Mapping[str, Any], *, artifact: str | None = None,
            row_index: int | None = None, digest: str | None = None,
            artifact_mtime: float | None = None) -> dict[str, Any]:
    """The provenance a row supports. Never raises; an absent field is "" (never invented).

    `artifact`/`row_index` are the compiler's coordinate for the row; `digest` is the row hash the
    compiler already computed for dedupe (recomputed when absent); `artifact_mtime` is the last
    resort for `retrieved_at` and is labelled as such.
    """
    first = _first_provenance(row)
    url = ""
    named = source_url_of(row)
    if _is_url(named):
        url = str(named).strip()
    for k in () if url else URL_KEYS:
        v = row.get(k)
        if _is_url(v):
            url = str(v).strip()
            break
    if not url and _is_url(first.get("url")):
        url = str(first.get("url")).strip()
    if not url and _is_url(row.get("title")):          # link-only captures put the URL there
        url = str(row.get("title")).strip()

    sid = str(row.get("source_id") or "").strip()
    if not sid:
        for k in ("url", "link"):                      # a non-http scheme is still an identity
            v = row.get(k)
            if isinstance(v, str) and "://" in v and not _is_url(v):
                sid = v.strip()
                break
    if not sid and artifact:
        sid = f"{artifact}#{row_index if row_index is not None else '?'}"

    ground = ""
    for k in GROUND_KEYS:
        v = row.get(k) or (first.get(k) if k == "ground" else None)
        if isinstance(v, str) and v.strip():
            ground = v.strip()
            break

    when, basis = "", ""
    for k in TIME_KEYS:
        v = row.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            when, basis = str(v).strip(), f"row:{k}"
            break
    if not when:
        for k in ("available_time", "published_time"):
            v = first.get(k)
            if isinstance(v, str) and v.strip():
                when, basis = v.strip(), f"provenance:{k}"
                break
    if not when and artifact_mtime is not None:
        when = datetime.fromtimestamp(float(artifact_mtime), tz=UTC).isoformat(timespec="seconds")
        basis = "artifact_mtime"

    chash = ""
    for k in HASH_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            chash, hbasis = v.strip(), f"row:{k}"
            break
    else:
        hbasis = ""
    if not chash and isinstance(first.get("source_hash"), str) and first.get("source_hash"):
        chash, hbasis = str(first["source_hash"]), "provenance:source_hash"
    if not chash:
        chash, hbasis = (digest or row_hash(row)), "row_sha256"
    return {"source_url": url, "source_id": sid, "ground": ground, "retrieved_at": when,
            "retrieved_at_basis": basis, "content_hash": chash, "content_hash_basis": hbasis}


def stamp_row(row: dict[str, Any], *, ground: str | None = None,
              retrieved_at: str | None = None, source_url: str | None = None,
              source_id: str | None = None) -> dict[str, Any]:
    """Stamp a PRODUCER's donation row in place (and return it). Existing values win.

    For the producers that know their own provenance at write time: the page they fetched, the
    ground they were working, when. The content hash is taken over the row BEFORE the stamp, so
    two identical findings hash identically whatever time they were stamped at.
    """
    if not isinstance(row, dict):
        return row
    if "content_hash" not in row and not any(row.get(k) for k in HASH_KEYS):
        row["content_hash"] = row_hash({k: v for k, v in row.items() if k not in FIELDS})
    if source_url and _is_url(source_url):
        row.setdefault("source_url", source_url)
    elif not row.get("source_url"):
        got = extract(row)["source_url"]
        if got:
            row["source_url"] = got
    if source_id:
        row.setdefault("source_id", source_id)
    if ground:
        row.setdefault("ground", ground)
    if not any(row.get(k) for k in TIME_KEYS):
        row["retrieved_at"] = retrieved_at or datetime.now(tz=UTC).isoformat(timespec="seconds")
    elif retrieved_at:
        row.setdefault("retrieved_at", retrieved_at)
    return row


def stamp_rows(rows: Iterable[dict[str, Any]], **kw: Any) -> list[dict[str, Any]]:
    return [stamp_row(r, **kw) for r in rows]


def stamp_candidate(cand: dict[str, Any], prov: Mapping[str, Any]) -> dict[str, Any]:
    """Carry a row's provenance onto a compiled candidate. A value the candidate already holds
    (a deepened candidate carrying its original row's URL) is never overwritten by an empty one.

    When the stamp FILLS an empty `source_url` (a URL found under `href`, `permalink`, a
    link-only title), the value the seed key was computed from is kept as `seed_url`, so
    `hypothesis_graph.seed_key_of` and `lead_schema.row_cell_key` still agree on the row."""
    for k in (*FIELDS, "retrieved_at_basis", "content_hash_basis"):
        v = prov.get(k)
        if v in (None, ""):
            continue
        if not cand.get(k):
            if k == "source_url" and "source_url" in cand and "seed_url" not in cand:
                cand["seed_url"] = cand["source_url"]
            cand[k] = v
    return cand


def seed_url_of(cand: Mapping[str, Any]) -> Any:
    """The URL the candidate's seed key hashes: `seed_url` when a stamp filled `source_url`
    after the fact, else `source_url` -- which the compiler set from `source_url_of(row)`."""
    return cand["seed_url"] if "seed_url" in cand else cand.get("source_url")


#: The culture fields (principal 2026-09-30; schema module libs/research/cell_culture.py lands on
#: another branch). Copied from the row onto the candidate when the producer stated them.
CULTURE_FIELDS: tuple[str, ...] = ("source_culture", "participant_structure",
                                   "failure_mode_hypothesis", "crowding_prior")


def carry_culture(cand: dict[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    for k in CULTURE_FIELDS:
        v = row.get(k)
        if v not in (None, "") and not cand.get(k):
            cand[k] = v
    return cand


def has_provenance(c: Mapping[str, Any]) -> bool:
    """content hash + retrieval time + (external URL or source id)."""
    return bool(c.get("content_hash") and c.get("retrieved_at")
                and (c.get("source_url") or c.get("source_id")))


def coverage(cands: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    n = full = url = 0
    by_source: dict[str, list[int]] = {}
    for c in cands:
        n += 1
        ok = has_provenance(c)
        full += int(ok)
        has_url = _is_url(c.get("source_url"))
        url += int(has_url)
        slot = by_source.setdefault(str(c.get("source") or "?"), [0, 0, 0])
        slot[0] += 1
        slot[1] += int(ok)
        slot[2] += int(has_url)
    return {"n": n, "provenanced": full, "with_source_url": url,
            "share": round(full / n, 6) if n else None,
            "share_source_url": round(url / n, 6) if n else None,
            "by_source": {s: {"n": v[0], "provenanced": v[1], "with_source_url": v[2]}
                          for s, v in sorted(by_source.items(), key=lambda kv: -kv[1][0])[:40]}}


def ratchet_window(floor_path: Path, measured_share: float | None, *, window: int = 24,
                   now: datetime | None = None, what: str = "external-URL share") -> dict[str, Any]:
    """A floor that ONLY RISES, raised to the WORST of the last `window` measured passes.

    For a share that legitimately swings with which producers donated this hour (the external-
    URL share: an internal generator has no URL). `ratchet` would raise the floor to the best
    pass ever and then fail every ordinary hour; this raises it only when `window` consecutive
    passes all cleared the new level, so the floor still never falls and a pass worse than a
    whole window's worst is a regression. UNMEASURED (None) neither tests nor moves it.
    """
    prior: dict[str, Any] = {}
    try:
        loaded = json.loads(floor_path.read_text("utf-8"))
        if isinstance(loaded, dict):
            prior = loaded
    except (OSError, ValueError):
        prior = {}
    floor = float(prior.get("floor") or 0.0)
    hist = [float(x) for x in (prior.get("history") or []) if isinstance(x, (int, float))]
    stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    if measured_share is None:
        status, new_floor = "UNMEASURED", floor
    else:
        status = "BELOW_FLOOR" if measured_share < floor - TOLERANCE else "OK"
        if status == "OK":
            hist = [*hist, float(measured_share)][-window:]
        new_floor = max(floor, min(hist)) if len(hist) >= window else floor
    doc = {"floor": round(new_floor, 6), "measured": measured_share, "status": status,
           "at": stamp, "prior_floor": round(floor, 6), "window": window, "history": hist,
           "rule": (f"the {what} of NEW candidates only ratchets up, to the worst of the last "
                    f"{window} passes; a pass below the floor (less a rounding tolerance) is a "
                    "regression and scripts/check_provenance_floor.py fails on it")}
    if status != "BELOW_FLOOR":
        try:
            floor_path.parent.mkdir(parents=True, exist_ok=True)
            floor_path.write_text(json.dumps(doc, indent=1), "utf-8")
        except OSError:
            pass
    return doc


#: A pass may read up to this far below the recorded floor before the fence calls it a
#: regression -- rounding on a few-candidate pass, not a licence to drift.
TOLERANCE = 0.001


def ratchet(floor_path: Path, measured_share: float | None, *, now: datetime | None = None
            ) -> dict[str, Any]:
    """Record `measured_share` against the floor and raise the floor to it. Floors only rise.

    An UNMEASURED pass (no new candidates) neither raises nor tests the floor. Never raises.
    """
    prior: dict[str, Any] = {}
    try:
        loaded = json.loads(floor_path.read_text("utf-8"))
        if isinstance(loaded, dict):
            prior = loaded
    except (OSError, ValueError):
        prior = {}
    floor = float(prior.get("floor") or 0.0)
    stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    if measured_share is None:
        status = "UNMEASURED"
        new_floor = floor
    else:
        status = "BELOW_FLOOR" if measured_share < floor - TOLERANCE else "OK"
        new_floor = max(floor, float(measured_share))
    doc = {"floor": round(new_floor, 6), "measured": measured_share, "status": status,
           "at": stamp, "prior_floor": round(floor, 6),
           "rule": ("the provenance share of NEW candidates only ratchets up; a pass below the "
                    "floor (less a rounding tolerance) is a regression and "
                    "scripts/check_provenance_floor.py fails on it")}
    if status != "BELOW_FLOOR":
        try:
            floor_path.parent.mkdir(parents=True, exist_ok=True)
            floor_path.write_text(json.dumps(doc, indent=1), "utf-8")
        except OSError:
            pass
    return doc
