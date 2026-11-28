"""Reviewed terms, one record per host: what the desk has READ of each host's terms.

WHY THIS EXISTS (LAWS 5e act 6, amended 2026-11-17; Governance ruling 2026-11-17 23:50Z). Act 6
refuses an automated fetch that a host's robots.txt or terms refuse, and Governance reads it
STRICTLY: a host whose terms the desk has not read is refused too ("unread terms are not 'no
ban'"). `refused_hosts` lists the settled refusals; this registry is the other half, the hosts
whose terms the desk HAS read, with what they said. A host with no record here is a host whose
terms are unread.

THE REFUSAL IS REACHED IN STEPS. This module is the record and its lookup (step 1). The gap it
leaves -- fetches that went to hosts with no record -- is measured every pass by
`desks/mt5/research/terms_record_gap.py` (steps 2 and 3). Nothing here changes a fetch path yet:
turning "no record" into a refusal at the fetch is step 4 and is NOT taken here. So the absence
of a record is not a permission either; it is the measured defect.

THE RECORD. Keyed by host (lowercased, a leading ``www.`` dropped). Fields:

* ``verdict``: ``permits`` (the terms read allow the desk's automated use), ``forbids`` (they
  refuse it), or ``unreadable`` (the desk tried and could not read them: walled, JS-only,
  robots-disallowed, error, or no terms page found). Under act 6 only ``permits`` lets a fetch
  through; ``unreadable`` refuses exactly as ``forbids`` does.
* ``terms_url``, ``date_read``, ``quote`` (the clause, or the not-readable note, VERBATIM from the
  evidence the repo holds), ``recorded_by`` (the organ, ruling or file that recorded it).
* ``evidence``: every held reading behind the record, each citing the repository object it was
  copied from. When readings disagree the record takes the most refusing one
  (forbids > unreadable > permits): fail closed.

LOOKUP. ``terms_record_for(url)`` matches the host or any parent domain that holds a record, the
same suffix rule ``refused_hosts`` uses (``api.e-stat.go.jp`` is covered by ``e-stat.go.jp``),
and the most specific record wins. There is no public-suffix list on this branch, so a record is
never inferred for a sibling host: ``a.example.org`` does not cover ``b.example.org``.

THE REGISTRY IS A DIRECTORY (Governance ruling 2026-11-18): ``libs/data/terms_records/`` holds
one group file per first character of the host (``a.json`` ... ``z.json``, ``0.json`` ...),
each ``{"records": {host: record}}`` in the record shape above, plus ``_meta.json`` (the
registry's own description, schema, counts, the ``not_seeded`` list, and ``files``: every group
file and how many records it holds). It is split so that no file is a diff hunk too large for
the independent review to read whole (``ops/release/independent_review.py`` PART_CHARS,
mirrored here as ``MAX_FILE_CHARS``); ``scripts/seed_terms_records.py`` refuses a write past it.

FAIL CLOSED. An absent, unparseable or invalid registry raises ``TermsRecordsUnreadable``; a
caller never reads a broken registry as "no records" (which would look like a clean gap) or as
"every host recorded". That is the module's one refusal state, and the split keeps it whole
rather than per file: an unreadable or invalid group file, a record with no host, a host filed in
the wrong group or in two files, a group file missing from or not named in ``_meta.json``, or a
count that disagrees with ``_meta.json`` makes the WHOLE registry unreadable. No file is ever
skipped, so the registry never silently shrinks: every host, including the ones the broken file
held, is then a host with no readable record -- under act 6, refused. The exception names the
hosts it can (``.hosts``); a file that does not parse names none, and that is why the rest are
refused with it.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from libs.data.refused_hosts import host_of

REGISTRY = Path(__file__).with_name("terms_records")
META = "_meta.json"
#: Mirrors ops/release/independent_review.py PART_CHARS (a test pins the two equal): a diff hunk
#: larger than this is never read whole by the independent review, so no group file may be.
MAX_FILE_CHARS = 24_000
VERDICTS: tuple[str, ...] = ("permits", "forbids", "unreadable")
#: Fail-closed precedence when readings of one host disagree: the most refusing wins.
SEVERITY: dict[str, int] = {"permits": 0, "unreadable": 1, "forbids": 2}
QUOTE_KINDS: tuple[str, ...] = ("verbatim_terms", "recorded_reading", "not_readable_note")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class TermsRecordsUnreadable(RuntimeError):
    """The registry could not be read or did not validate. Never read as "no records".
    ``hosts``: the hosts the failure could name (empty when a file did not even parse)."""

    def __init__(self, message: str, hosts: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.hosts = hosts


def group_file(host: str) -> str:
    """The group file a normalised host's record lives in: its first character."""
    return f"{host[:1]}.json"


def hunk_chars(text: str) -> int:
    """How large ``text`` is as one added-file diff hunk: every line gains a leading ``+``, plus
    a generous allowance for the file and hunk headers."""
    return len(text) + text.count("\n") + 400


def dump(doc: Any) -> str:
    """The one serialisation every registry file is written in."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def split(doc: Mapping[str, Any]) -> dict[str, str]:
    """A whole registry document (``records`` plus its description) as the directory's files,
    name -> text. Pure; the caller validates and enforces the size limit."""
    groups: dict[str, dict[str, Any]] = {}
    for host in sorted(doc["records"]):
        groups.setdefault(group_file(host), {})[host] = doc["records"][host]
    meta = {k: v for k, v in doc.items() if k != "records"}
    meta["files"] = {name: len(recs) for name, recs in sorted(groups.items())}
    out = {META: dump(meta)}
    out.update({name: dump({"records": recs}) for name, recs in sorted(groups.items())})
    return out


def record_key(host_or_url: str) -> str | None:
    """The registry key for a host or URL: lowercased hostname, trailing dot and a leading
    ``www.`` dropped. None when it does not parse to a host."""
    s = str(host_or_url or "").strip()
    host = host_of(s if "://" in s else f"https://{s}")
    if host is None:
        return None
    return host[4:] if host.startswith("www.") and host.count(".") >= 2 else host


def validate(doc: Any) -> list[str]:
    """Every problem with a registry document; empty when it is valid."""
    if not isinstance(doc, Mapping):
        return ["the registry is not a JSON object"]
    recs = doc.get("records")
    if not isinstance(recs, Mapping):
        return ["`records` is missing or not an object"]
    out: list[str] = []
    for key, rec in recs.items():
        where = f"records[{key!r}]"
        if not isinstance(rec, Mapping):
            out.append(f"{where} is not an object")
            continue
        if record_key(key) != key or not _HOST.match(key):
            out.append(f"{where}: key is not a normalised host")
        if rec.get("host") != key:
            out.append(f"{where}: host field does not equal its key")
        if rec.get("verdict") not in VERDICTS:
            out.append(f"{where}: verdict {rec.get('verdict')!r} not in {VERDICTS}")
        if not str(rec.get("quote") or "").strip():
            out.append(f"{where}: no quote")
        if not str(rec.get("recorded_by") or "").strip():
            out.append(f"{where}: no recorded_by")
        url = rec.get("terms_url")
        if url is not None and not str(url).startswith(("http://", "https://")):
            out.append(f"{where}: terms_url is neither null nor an http(s) URL")
        date = rec.get("date_read")
        if date is not None and not _DATE.match(str(date)):
            out.append(f"{where}: date_read is neither null nor YYYY-MM-DD")
        ev = rec.get("evidence")
        if not isinstance(ev, list) or not ev:
            out.append(f"{where}: no evidence")
            continue
        worst = None
        for i, e in enumerate(ev):
            w = f"{where}.evidence[{i}]"
            if not isinstance(e, Mapping):
                out.append(f"{w} is not an object")
                continue
            if e.get("verdict") not in VERDICTS:
                out.append(f"{w}: verdict not in {VERDICTS}")
            elif worst is None or SEVERITY[e["verdict"]] > SEVERITY[worst]:
                worst = e["verdict"]
            if not str(e.get("quote") or "").strip():
                out.append(f"{w}: no quote")
            if e.get("quote_kind") not in QUOTE_KINDS:
                out.append(f"{w}: quote_kind not in {QUOTE_KINDS}")
            src = e.get("source")
            if not isinstance(src, Mapping) or not src.get("file") or not src.get("object"):
                out.append(f"{w}: source must name the file and object it was copied from")
        if worst is not None and rec.get("verdict") != worst:
            out.append(f"{where}: verdict {rec.get('verdict')!r} is not the most refusing "
                       f"reading ({worst!r}); fail closed")
    return out


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TermsRecordsUnreadable(f"{p}: {type(exc).__name__}: {exc}") from exc


def load_document(path: Path | str | None = None) -> dict[str, Any]:
    """The whole registry document reassembled from the directory: ``_meta.json``'s fields with
    ``records`` the union of every group file, read in sorted order. FAIL CLOSED (see the module
    docstring): any problem raises ``TermsRecordsUnreadable``; nothing is skipped."""
    d = Path(path) if path is not None else REGISTRY
    if not d.is_dir():
        raise TermsRecordsUnreadable(f"{d}: the registry directory is absent")
    meta = _read(d / META)
    if not isinstance(meta, Mapping) or not isinstance(meta.get("files"), Mapping) \
            or "records" in meta:
        raise TermsRecordsUnreadable(f"{d / META}: not an object with a `files` map and no "
                                     "records")
    declared = {str(k): v for k, v in meta["files"].items()}
    present = sorted(p.name for p in d.iterdir() if p.name != META)
    problems: list[str] = []
    named: set[str] = set()
    for name in sorted(set(declared) - set(present)):
        problems.append(f"{name} is named in {META} but absent")
    for name in sorted(set(present) - set(declared)):
        problems.append(f"{name} is in the directory but not named in {META}")
    records: dict[str, Any] = {}
    home: dict[str, str] = {}
    for name in present:
        if name not in declared:
            continue
        try:
            doc = _read(d / name)
        except TermsRecordsUnreadable as exc:
            problems.append(str(exc))
            continue
        recs = doc.get("records") if isinstance(doc, Mapping) else None
        if not isinstance(recs, Mapping) or set(doc) != {"records"}:
            problems.append(f"{name}: not an object holding only `records`")
            continue
        if len(recs) != declared[name]:
            problems.append(f"{name}: holds {len(recs)} records, {META} says {declared[name]}")
        for key, rec in recs.items():
            key = str(key)
            named.add(key)
            if group_file(key) != name:
                problems.append(f"{name}: {key!r} belongs in {group_file(key)}")
            if key in home:
                problems.append(f"{key!r} is in both {home[key]} and {name}")
                continue
            home[key] = name
            records[key] = rec
    whole = {**{k: v for k, v in meta.items() if k != "files"}, "records": records}
    problems.extend(validate(whole))
    counts = meta.get("counts")
    if isinstance(counts, Mapping) and counts.get("records") != len(records):
        problems.append(f"{len(records)} records read, {META} counts {counts.get('records')}")
    if problems:
        bad = tuple(sorted(h for h in named if any(repr(h) in x for x in problems)))
        raise TermsRecordsUnreadable(f"{d}: {len(problems)} problem(s): {problems[:5]}",
                                     hosts=bad)
    return whole


def load(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """The records, keyed by host. FAIL CLOSED: raises ``TermsRecordsUnreadable`` on an absent,
    unparseable or invalid registry directory or any file in it."""
    doc = load_document(path)
    return {str(k): dict(v) for k, v in doc["records"].items()}


_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def _records(records: Mapping[str, Mapping[str, Any]] | None) -> Mapping[str, Mapping[str, Any]]:
    if records is not None:
        return records
    key = str(REGISTRY)
    if key not in _CACHE:
        _CACHE[key] = load(REGISTRY)
    return _CACHE[key]


def matching_key(url: str, keys: Any) -> str | None:
    """The most specific registry key covering ``url``'s host (the host itself or a parent
    domain), or None. Pure."""
    host = host_of(url if "://" in str(url) else f"https://{url}")
    if host is None:
        return None
    best: str | None = None
    for k in keys:
        if (host == k or host.endswith("." + k)) and (best is None or len(k) > len(best)):
            best = k
    return best


def terms_record_for(url: str,
                     records: Mapping[str, Mapping[str, Any]] | None = None
                     ) -> dict[str, Any] | None:
    """The reviewed-terms record governing ``url``, or None when the desk holds none (its terms
    are unread). ``records`` defaults to the committed registry, loaded fail-closed."""
    recs = _records(records)
    k = matching_key(url, recs.keys())
    return dict(recs[k]) if k is not None else None
