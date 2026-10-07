"""KEYS_NEEDED: the short list of keys the principal should fetch now, and nothing else.

The principal's ask (2026-10-06 20:12): "make an alert where everytime keys r needed in future i
get noti". This module derives that list; `research/credential_coverage.py` writes it hourly to
`desks/mt5/reports/KEYS_NEEDED.json` beside CREDENTIAL_COVERAGE.json, and a daily routine posts
it to the project only when its `digest` changes.

A key is NEEDED when any of these holds, and its catalog row is not in a group the principal
cannot or must not act on (unavailable, paid, banned, legacy, not built, infra):

  * MISSING     -- a free key in env_keys_catalog.json that this host cannot see (`read_key`);
                   a new keyed source landing in the catalog with no key set shows up here.
  * BLOCKED_AUTH -- credential_coverage or keyed_sources says a consumer is dark for want of it.
  * UNCONFIGURED -- asia_collector skipped a keyed row because its key is not set.
  * REJECTED    -- the key IS set and the publisher answered 401/403: expired or rotated.

Presence only. No value is read into the artifact, printed or compared; `--acquired` lets a
session with no box state (the cloud routine) treat a list of NAMES as present:

    python -m libs.ops.keys_needed --acquired /mnt/project-files/keys/ACQUIRED.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from libs.ops import env_keys

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "desks" / "mt5" / "reports"
OUT = REPORTS / "KEYS_NEEDED.json"

#: Days a requested key stays parked before the alert names it again.
REQUEST_STALE_DAYS = 14
#: Groups whose keys the principal should register when missing.
ASK_GROUPS = frozenset({"free_data", "free_llm", "free_infra"})
#: Groups never asked for, whatever a report says: the principal marked them unavailable, or the
#: policy refuses them, or nothing reads them.
NEVER_ASK = frozenset({"unavailable", "paid_blocked", "banned", "paid_llm", "legacy",
                       "not_built", "infra"})


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _catalog_by_name() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in env_keys.catalog():
        out[str(row["name"])] = dict(row)
        for alias in row.get("aliases") or ():
            out.setdefault(str(alias), dict(row))
    return out


def _reasons(reports: Path) -> dict[str, list[str]]:
    """{key name: [reason, ...]} from the hourly reports that exist on this host."""
    found: dict[str, list[str]] = {}

    def add(name: Any, why: str) -> None:
        if name:
            found.setdefault(str(name), []).append(why)

    cov = _read(reports / "CREDENTIAL_COVERAGE.json") or {}
    for v in cov.get("vars") or ():
        if v.get("status") == "BLOCKED_AUTH" and v.get("actionable"):
            dark = len(v.get("dark_consumers") or ())
            add(v.get("env"), f"BLOCKED_AUTH: {dark or 'a'} built consumer(s) dark without it")
    ks = _read(reports / "KEYED_SOURCES.json") or {}
    for sid, rec in (ks.get("sources") or {}).items():
        status = str(rec.get("status") or "")
        if status.startswith("BLOCKED_AUTH"):
            for var in rec.get("credential_vars") or ():
                add(var, f"BLOCKED_AUTH: keyed source {sid} cannot run")
    asia = _read(reports / "ASIA_COLLECTOR.json") or {}
    for row in asia.get("rows") or ():
        status, env = str(row.get("status") or ""), row.get("key_env")
        if status == "UNCONFIGURED":
            add(env, f"UNCONFIGURED: source {row.get('id')} skipped for want of it")
        elif (row.get("access") == "key" and status == "HTTP_ERROR"
              and row.get("http") in (401, 403)):
            add(row.get("key_env") or env,
                f"REJECTED: source {row.get('id')} answered HTTP {row.get('http')} with the key "
                f"set (expired or rotated)")
    return found


def build(*, reports: Path = REPORTS, acquired: Iterable[str] = (),
          requested: Iterable[str] = (), present: Callable[[str], bool] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    """`requested`: `NAME@YYYY-MM-DD` for a key the principal applied for on that day and is
    waiting on (a provider that answers by email). Parked out of the list and the digest so the
    alert does not nag about a key nobody can fetch yet -- for REQUEST_STALE_DAYS only; after
    that it comes back as REQUESTED_STALE. An undated name is never parked (audit of #252: an
    undated park dropped a never-set key off the list for good), nor one dated in the future
    (`@2099-...` would park it for decades), nor a REJECTED key."""
    cat = _catalog_by_name()
    have = {str(n).strip() for n in acquired if str(n).strip()}
    today = (now or datetime.now(tz=UTC)).date()
    waiting: dict[str, date] = {}
    for entry in requested:
        name, _, day = str(entry).strip().partition("@")
        try:
            waiting[name.strip()] = date.fromisoformat(day.strip())
        except ValueError:
            continue                     # undated: not parked

    def is_set(name: str) -> bool:
        if name in have:
            return True
        return bool(present(name) if present else env_keys.read_key(name))

    reasons = _reasons(reports)
    items: dict[str, dict[str, Any]] = {}
    for row in env_keys.catalog():
        name = str(row["name"])
        names = [name, *(row.get("aliases") or ())]
        if row.get("group") in ASK_GROUPS and not any(is_set(n) for n in names):
            items[name] = {"name": name, "reasons": ["MISSING: not set on this host"]}
    for name, why in reasons.items():
        hit = cat.get(name)
        if hit is None or hit.get("group") in NEVER_ASK:
            continue
        canon = str(hit["name"])
        rejected = [w for w in why if w.startswith("REJECTED")]
        if not rejected and any(is_set(n) for n in [canon, *(hit.get("aliases") or ())]):
            continue   # set since the report was written; the next pass will agree
        items.setdefault(canon, {"name": canon, "reasons": []})["reasons"] += why
    parked: list[str] = []
    for n in sorted(items):
        if n not in waiting or any(r.startswith("REJECTED") for r in items[n]["reasons"]):
            continue
        age = (today - waiting[n]).days
        if age < 0:   # a future date would park the key until then (re-audits of #252)
            items[n]["reasons"].append(f"REQUESTED_FUTURE_DATE: marked applied for "
                                       f"{waiting[n]}, after today, so it is not parked")
            continue
        if age < REQUEST_STALE_DAYS:
            parked.append(n)
            items.pop(n)
        else:
            items[n]["reasons"].append(f"REQUESTED_STALE: applied for {waiting[n]}, {age} days "
                                       f"ago, and still not set")
    out = []
    for name in sorted(items):
        row = cat[name]
        out.append({"name": name, "signup": row.get("signup"), "why": row.get("unlocks"),
                    "owner": row.get("owner"), "machine": row.get("machine"),
                    "reasons": sorted(set(items[name]["reasons"]))})
    digest = hashlib.sha256(json.dumps(
        [(i["name"], i["reasons"]) for i in out]).encode()).hexdigest()[:16]
    return {"generated_at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
            "writer": "libs/ops/keys_needed.py",
            "rule": "names, links and reasons only; no value is read into this file",
            "acquired_names_assumed": sorted(have), "requested_waiting": parked,
            "n": len(out), "digest": digest,
            "items": out}


def lines(doc: Mapping[str, Any]) -> list[str]:
    """One line per item: name, signup link, why. What the routine posts."""
    return [f"- `{i['name']}`: {i['signup']} ({i['why']}; {i['reasons'][0]})"
            for i in doc.get("items") or ()]


def write(doc: Mapping[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--acquired", default="",
                    help="file of key NAMES (one per line) to treat as set, for a host with no "
                         "box state; a line ~NAME@YYYY-MM-DD marks a key applied for that day")
    ap.add_argument("--write", action="store_true", help=f"write {OUT.name}")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    names: list[str] = []
    if a.acquired:
        names = [ln.split("#", 1)[0].strip() for ln in
                 Path(a.acquired).read_text("utf-8").splitlines()]
    # A line `~NAME@YYYY-MM-DD` means applied for that day and waiting on the provider.
    doc = build(acquired=[n for n in names if not n.startswith("~")],
                requested=[n[1:] for n in names if n.startswith("~")])
    if a.write:
        write(doc)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"{doc['n']} key(s) needed (digest {doc['digest']})")
        print("\n".join(lines(doc)) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
