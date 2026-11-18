"""Seed libs/data/terms_records/ from terms evidence the repository ALREADY holds.

Nothing is fetched and nothing is invented. Every record is copied from a named object in the
repository, and every evidence row cites that object (`source`: file, object, key, field) so
`resolve()` can read the quote back and a test can prove it is the same text. A host with no held
evidence gets no record. A reading that cannot be mapped honestly onto permits / forbids /
unreadable is NOT seeded and is listed in `not_seeded` with the reason, so a later session sees
it rather than a guess.

Held evidence read (LIVE branch, 2026-11-17):

* `libs/data/refused_hosts.py` REFUSED_HOSTS -- settled terms refusals (forbids).
* `libs/research/public_strategy_hunter.py` TERMS_REFUSED_HOSTS -- forbids.
* `desks/mt5/research/deep_forest_miner.py` TERMS_REFUSED -- forbids (read 2026-11-13).
* `desks/mt5/research/alt_proxies.py` TERMS_EVIDENCE with its TERMS verdicts.
* `libs/ops/token_refresh.py` TERMS_EVIDENCE with its TERMS verdicts.
* `libs/research/equivalence_ontology.py` TERMS_EVIDENCE (per fetch prefix).
* `desks/mt5/data/free_stack_sources.json` rows carrying `terms_evidence`.
* `desks/mt5/data/credential_registry.json` rows with machine_use_allowed=false and a terms text.

The registry is a directory (`libs/data/terms_records.py` says why): each record is written to
its group file (`tr.group_file`, the host's first character) and the description to `_meta.json`.
A write that would make any file a diff hunk past `tr.MAX_FILE_CHARS` (the independent review's
PART_CHARS) is REFUSED, exit 2, and nothing is written: split the group finer first.

Usage:  python scripts/seed_terms_records.py [--check]   (--check: exit 1 if any file differs)
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_records as tr  # noqa: E402

SEEDER = "scripts/seed_terms_records.py"

#: Terms URLs whose host is NOT the publisher whose terms they are, so keying a record on that
#: host would claim the desk read that host's own terms. Never seeded; listed in not_seeded.
THIRD_PARTY_TERMS_HOSTS: dict[str, str] = {
    "github.com": ("a repository README licenses that repository's data; it is not github.com's "
                   "own terms for automated access"),
    "catalog.data.gov": ("a dataset licence shown on a catalogue page; not the terms of the "
                         "host the data is fetched from"),
    "nationalgovernment.co.za": ("a third-party MIRROR of the publisher's notice; a mirror "
                                 "cannot confirm the publisher's own terms"),
}

#: module path (importable) -> repository file, for the citation.
_MODULES: dict[str, str] = {
    "libs.data.refused_hosts": "libs/data/refused_hosts.py",
    "libs.research.public_strategy_hunter": "libs/research/public_strategy_hunter.py",
    "research.deep_forest_miner": "desks/mt5/research/deep_forest_miner.py",
    "research.alt_proxies": "desks/mt5/research/alt_proxies.py",
    "libs.ops.token_refresh": "libs/ops/token_refresh.py",
    "libs.research.equivalence_ontology": "libs/research/equivalence_ontology.py",
}
_FILE_TO_MODULE = {v: k for k, v in _MODULES.items()}
_DATE_IN_TEXT = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _host(url: str) -> str | None:
    try:
        return (urlsplit(url).hostname or "").lower() or None
    except ValueError:
        return None


def resolve(source: dict[str, Any]) -> Any:
    """Read the cited object back out of the repository. Raises if it is not there."""
    f = source["file"]
    if f.endswith(".json"):
        obj: Any = json.loads((ROOT / f).read_text(encoding="utf-8"))
        for part in source["object"].split("."):
            obj = obj[part]
        if "index" in source:
            obj = obj[source["index"]]
    else:
        obj = getattr(importlib.import_module(_FILE_TO_MODULE[f]), source["object"])
    if "key" in source:
        obj = obj[source["key"]]
    for part in (source.get("field") or "").split("."):
        if part:
            obj = obj[part]
    return obj


def _unreadable_note(quote: str) -> bool:
    q = quote.strip().lower()
    return q.startswith(("(not readable", "(not found", "(none found")) or \
        "(no terms page found)" in q


def _ev(verdict: str, quote: str, kind: str, source: dict[str, Any], *, terms_url: str | None,
        date_read: str | None, label: str) -> dict[str, Any]:
    return {"verdict": verdict, "terms_url": terms_url, "date_read": date_read, "quote": quote,
            "quote_kind": kind, "source_label": label, "source": source}


def _refusal_dicts() -> Iterator[tuple[str, dict[str, Any]]]:
    """The three settled refusal lists: host -> recorded reading (forbids)."""
    lists = (("libs.data.refused_hosts", "REFUSED_HOSTS"),
             ("libs.research.public_strategy_hunter", "TERMS_REFUSED_HOSTS"),
             ("research.deep_forest_miner", "TERMS_REFUSED"))
    for mod, name in lists:
        for host, why in getattr(importlib.import_module(mod), name).items():
            src = {"file": _MODULES[mod], "object": name, "key": host}
            m = _DATE_IN_TEXT.search(str(why))
            date = m.group(1) if m else ("2026-11-13" if name == "TERMS_REFUSED" else None)
            yield host, _ev("forbids", str(why), "recorded_reading", src, terms_url=None,
                            date_read=date, label="refused")


def _alt_proxies(not_seeded: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, Any]]]:
    mod = importlib.import_module("research.alt_proxies")
    for sid, ev in mod.TERMS_EVIDENCE.items():
        label = mod.TERMS.get(sid, ("", ""))[0]
        yield from _from_evidence("research.alt_proxies", "TERMS_EVIDENCE", sid, ev, label,
                                  not_seeded)


def _token_refresh(not_seeded: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, Any]]]:
    mod = importlib.import_module("libs.ops.token_refresh")
    for sid, ev in mod.TERMS_EVIDENCE.items():
        label = mod.TERMS.get(sid, ("", ""))[0]
        yield from _from_evidence("libs.ops.token_refresh", "TERMS_EVIDENCE", sid, ev, label,
                                  not_seeded)


_LABEL_VERDICT = {"confirmed": "permits", "confirmed_private_use": "permits",
                  "refused": "forbids", "PERMITTED": "permits"}


def _verdict(label: str, quote: str) -> str | None:
    if _unreadable_note(quote):
        return "unreadable"
    return _LABEL_VERDICT.get(label)


def _from_evidence(mod: str, obj: str, sid: str, ev: dict[str, Any], label: str,
                   not_seeded: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, Any]]]:
    url = str(ev.get("terms_url") or "")
    quote = str(ev.get("terms_quote") or "")
    src = {"file": _MODULES[mod], "object": obj, "key": sid, "field": "terms_quote"}
    host = _host(url)
    if not host or not quote:
        not_seeded.append({"source": src, "why": "no terms URL or no quote held"})
        return
    if host in THIRD_PARTY_TERMS_HOSTS:
        not_seeded.append({"source": src, "host": host, "why": THIRD_PARTY_TERMS_HOSTS[host]})
        return
    verdict = _verdict(label, quote)
    if verdict is None:
        not_seeded.append({"source": src, "host": host, "source_label": label,
                           "why": ("terms were read but the desk's own reading is "
                                   f"{label!r} (not settled): neither permits, forbids nor "
                                   "unreadable, so no verdict is invented")})
        return
    yield host, _ev(verdict, quote, "not_readable_note" if verdict == "unreadable"
                    else "verbatim_terms", src, terms_url=url,
                    date_read=str(ev.get("checked_at") or "") or None, label=label)


def _equivalence() -> Iterator[tuple[str, dict[str, Any]]]:
    mod = importlib.import_module("libs.research.equivalence_ontology")
    for i, ev in enumerate(mod.TERMS_EVIDENCE):
        host = _host(ev["prefix"])
        quote = str(ev["terms_quote"])
        verdict = "unreadable" if _unreadable_note(quote) else _LABEL_VERDICT.get(ev["verdict"])
        if not host or verdict is None:
            continue
        src = {"file": _MODULES["libs.research.equivalence_ontology"],
               "object": "TERMS_EVIDENCE", "key": i, "field": "terms_quote"}
        yield host, _ev(verdict, quote, "not_readable_note" if verdict == "unreadable"
                        else "verbatim_terms", src, terms_url=ev["terms_url"],
                        date_read=ev.get("checked_at"), label=ev["verdict"])


def _free_stack(not_seeded: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, Any]]]:
    f = "desks/mt5/data/free_stack_sources.json"
    doc = json.loads((ROOT / f).read_text(encoding="utf-8"))
    for i, row in enumerate(doc.get("sources", [])):
        ev = row.get("terms_evidence")
        if not isinstance(ev, dict):
            continue
        url, quote = str(ev.get("terms_url") or ""), str(ev.get("terms_quote") or "")
        host = _host(url)
        src = {"file": f, "object": "sources", "index": i, "field": "terms_evidence.terms_quote",
               "row_id": row.get("id")}
        if not host or not quote:
            continue
        label = str(row.get("terms") or "")
        verdict = _verdict(label, quote)
        if verdict is None:
            not_seeded.append({"source": src, "host": host, "source_label": label,
                               "why": f"reading {label!r} is not a settled verdict"})
            continue
        yield host, _ev(verdict, quote, "not_readable_note" if verdict == "unreadable"
                        else "verbatim_terms", src, terms_url=url,
                        date_read=ev.get("checked_at"), label=label)


def _credentials() -> Iterator[tuple[str, dict[str, Any]]]:
    f = "desks/mt5/data/credential_registry.json"
    doc = json.loads((ROOT / f).read_text(encoding="utf-8"))
    for obj in ("vars", "keyless"):
        for i, row in enumerate(doc.get(obj, [])):
            if not isinstance(row, dict) or row.get("machine_use_allowed") is not False \
                    or not row.get("terms"):
                continue
            host = _host(str(row.get("signup_url") or ""))
            if not host:
                continue
            src = {"file": f, "object": obj, "index": i, "field": "terms",
                   "row_id": row.get("env")}
            yield host, _ev("forbids", str(row["terms"]), "recorded_reading", src,
                            terms_url=None, date_read=None, label="machine_use_allowed=false")


def build() -> dict[str, Any]:
    not_seeded: list[dict[str, Any]] = []
    pairs: list[tuple[str, dict[str, Any]]] = [
        *_refusal_dicts(), *_alt_proxies(not_seeded), *_token_refresh(not_seeded),
        *_equivalence(), *_free_stack(not_seeded), *_credentials()]
    records: dict[str, dict[str, Any]] = {}
    for raw_host, ev in pairs:
        key = tr.record_key(raw_host)
        if key is None:
            continue
        rec = records.setdefault(key, {"host": key, "evidence": []})
        if ev not in rec["evidence"]:
            rec["evidence"].append(ev)
    for key, rec in records.items():
        evs = rec["evidence"]
        # fail closed: the most refusing reading decides; ties keep the first (deterministic)
        lead = max(evs, key=lambda e: tr.SEVERITY[e["verdict"]])
        rec.update({"verdict": lead["verdict"], "terms_url": lead["terms_url"],
                    "date_read": lead["date_read"], "quote": lead["quote"],
                    "recorded_by": f"{lead['source']['file']} {lead['source']['object']} "
                                   f"(copied by {SEEDER}; no fetch)"})
        records[key] = {k: rec[k] for k in ("host", "verdict", "terms_url", "date_read",
                                            "quote", "recorded_by", "evidence")}
    counts: dict[str, int] = dict.fromkeys(tr.VERDICTS, 0)
    for rec in records.values():
        counts[rec["verdict"]] += 1
    return {
        "_doc": ("Reviewed terms per host (LAWS 5e act 6). A host with no record has terms the "
                 "desk has not read: under the Governance ruling of 2026-11-17 that host is "
                 "refused, and the gap is measured each pass in reports/TERMS_RECORD_GAP.json. "
                 "Seeded ONLY from evidence the repository held; each evidence row cites the "
                 "object it was copied from. Add a record when a session reads a host's terms "
                 "(URL, date, verbatim clause); never infer one."),
        "schema": {"verdicts": list(tr.VERDICTS), "quote_kinds": list(tr.QUOTE_KINDS),
                   "precedence": "forbids > unreadable > permits (fail closed)"},
        "seeded_by": SEEDER,
        "counts": {"records": len(records), **counts},
        "records": dict(sorted(records.items())),
        "not_seeded": not_seeded,
    }


def oversize(files: dict[str, str]) -> list[str]:
    """Every file that would be a diff hunk past the review's limit, with its size."""
    return [f"{name}: {tr.hunk_chars(text)} > {tr.MAX_FILE_CHARS}"
            for name, text in sorted(files.items()) if tr.hunk_chars(text) > tr.MAX_FILE_CHARS]


def write(files: dict[str, str], directory: Path) -> None:
    """Write the registry's files and remove any group file the new set does not hold."""
    directory.mkdir(parents=True, exist_ok=True)
    for stale in sorted({p.name for p in directory.iterdir()} - set(files)):
        (directory / stale).unlink()
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    problems = tr.validate(doc)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    files = tr.split(doc)
    big = oversize(files)
    if big:
        print("REFUSED: a registry file would be too large for the independent review to read "
              "whole; split its group finer (tr.group_file) before seeding:\n  "
              + "\n  ".join(big), file=sys.stderr)
        return 2
    d = tr.REGISTRY
    if args.check:
        held = {p.name: p.read_text(encoding="utf-8") for p in d.iterdir()} if d.is_dir() else {}
        same = held == files
        print("terms_records/ is current" if same else "terms_records/ is STALE")
        return 0 if same else 1
    write(files, d)
    print(f"wrote {d.relative_to(ROOT)}/ ({len(files)} files): {doc['counts']}; "
          f"not seeded: {len(doc['not_seeded'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
