"""The manifest must describe the repo that exists, not the one someone meant to build.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

`desk_manifest.yaml` names one canonical implementation per job. A manifest nobody verifies is
just a sixth conflicting description of the desk -- and five conflicting descriptions is the
problem it was written to solve. So this checks three things a stale manifest gets wrong:

    EXISTS       every `canonical:` target resolves to a real module or file. A manifest entry
                 pointing at a module someone renamed is worse than no entry, because it reads
                 as a guarantee.
    IMPORTABLE   the module actually imports. `libs.research.lineage_dag` existing as a file
                 says nothing about whether it loads on this box -- the desk lost its entire
                 forward lane for hours to a module that was committed, hash-verified and
                 unimportable where it mattered.
    RETIRED IS UNREACHABLE   nothing listed under `retired:` may be invoked from a scheduled
                 path. A retired file that still runs is not retired, and the crypto chain sat
                 in exactly that state -- unscheduled by systemd, still Popen'd detached by a
                 sibling script.

WHAT IT DOES NOT DO. It does not import `validation:` or `promotion:` targets that touch the
money path. Importing a promoter to check that it imports is a side effect on the wrong side of
the firewall; those are checked for EXISTENCE only, and their behaviour is the gauntlet's job.
"""
from __future__ import annotations

import importlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "desk_manifest.yaml"
OUT = ROOT / "data" / "desk_manifest_health.json"

#: Sections whose modules are imported to prove they load. `validation` and `promotion` are
#: DELIBERATELY ABSENT: importing a promoter has side effects on the money path, and this check
#: must never be the thing that moves capital.
_IMPORT_SECTIONS = ("research", "shadow")

#: Sections checked for existence only.
_EXISTS_SECTIONS = ("validation", "promotion", "watchdogs")


def _load_manifest() -> dict[str, Any]:
    """Parse the manifest without a YAML dependency.

    Deliberately a small parser rather than a new import: this check must run in the barest
    possible environment, because the situation where it matters most -- a box where something
    did not install -- is exactly the situation where an extra dependency is unavailable.
    """
    try:
        text = MANIFEST.read_text("utf-8")
    except OSError:
        return {}
    data: dict[str, Any] = {}
    section: str | None = None
    list_key: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            data[section] = {}
            list_key = None
            continue
        if indent == 0:
            m0 = re.match(r"^([\w_]+):\s*(.+)$", line)
            if m0:
                data[m0.group(1)] = m0.group(2).strip().strip('"')
                section = None
            continue
        if section is None:
            continue
        if line.startswith("- "):
            body = line[2:].strip()
            bucket = data.setdefault(section, {})
            if not isinstance(bucket, dict):
                continue
            entries = bucket.setdefault("_list", [])
            m = re.match(r"^(\w+):\s*(.*)$", body)
            entries.append({m.group(1): m.group(2).strip().strip('"')} if m else {"path": body})
            continue
        m = re.match(r"^([\w_]+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip('"')
        if not value:
            list_key = key
            data[section][key] = []
            continue
        if isinstance(data.get(section), dict):
            if list_key and indent > 2 and isinstance(data[section].get(list_key), list):
                data[section][list_key].append(value)
            else:
                data[section][key] = value
                list_key = None
    return data


def _resolve(target: str) -> tuple[bool, str]:
    """Does this dotted module or path exist on disk?"""
    if "/" in target or target.endswith((".py", ".yaml", ".json")):
        p = ROOT / target
        if "*" in target:
            return (bool(list(ROOT.glob(target))), f"glob {target}")
        return (p.exists(), str(target))
    parts = target.split(".")
    p = ROOT / Path(*parts).with_suffix(".py")
    if p.exists():
        return True, str(p.relative_to(ROOT))
    # A manifest entry may name a SYMBOL inside a module (`...shadow_forward.sleeve_key`).
    # Resolve the module and confirm the symbol is DEFINED there -- reporting the whole entry
    # missing because the last component is a function is a false alarm, and a checker that
    # cries wolf gets skimmed past, which is worse than not having it.
    if len(parts) > 1:
        mod = ROOT / Path(*parts[:-1]).with_suffix(".py")
        if mod.exists():
            try:
                src = mod.read_text("utf-8")
            except OSError:
                return False, target
            sym = parts[-1]
            if f"def {sym}" in src or f"class {sym}" in src or f"\n{sym} = " in src:
                return True, f"{mod.relative_to(ROOT)}::{sym}"
            return False, f"{mod.relative_to(ROOT)} exists but defines no {sym!r}"
    return False, target


def _grep_callers(path: str) -> list[str]:
    """Files that invoke a retired path. A retired file that still runs is not retired."""
    name = Path(path).name
    try:
        r = subprocess.run(["grep", "-rl", "--include=*.py", "--include=*.sh", "--include=*.ps1",
                            "-F", name, "."], cwd=ROOT, capture_output=True, text=True,
                           timeout=90, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return []
    out = []
    for line in (r.stdout or "").splitlines():
        f = line.strip().lstrip("./")
        # `data/rollback/**` are timestamped ARCHIVES of previous trees. A retired file appearing
        # in a snapshot of the past is a record that it once existed, not evidence that anything
        # runs it now -- counting them made every retired entry permanently "reachable".
        if (f and f != path and not f.startswith(("tests/", "data/rollback/", "data/archive/",
                                  "claude/worktrees/", ".claude/"))
                and "check_desk_manifest" not in f and "check_universe_mandate" not in f and Path(f).name != Path(path).name):
            out.append(f)
    return out


def _halts_on_mandate(path: str) -> bool:
    """Does this retired entry refuse to run? Presence of a caller is fine if the target halts."""
    try:
        src = (ROOT / path).read_text("utf-8")
    except OSError:
        return False
    return "_mandate_halt" in src or "HALTED BY MANDATE" in src


def main() -> int:
    now = datetime.now(tz=UTC)
    man = _load_manifest()
    report: dict[str, Any] = {"checked_at": now.isoformat(timespec="seconds"),
                              "missing": [], "unimportable": [], "retired_reachable": [],
                              "checked": 0}

    if not man:
        print("MANIFEST: desk_manifest.yaml is missing or unparseable -- the desk has no "
              "canonical description. Failing closed.")
        return 1

    print(f"DESK MANIFEST {now.isoformat(timespec='seconds')}  (version "
          f"{man.get('version', {}) or '?'})")

    for sec in (*_IMPORT_SECTIONS, *_EXISTS_SECTIONS):
        entries = man.get(sec) or {}
        if not isinstance(entries, dict):
            continue
        for key, target in entries.items():
            targets = target if isinstance(target, list) else [target]
            for t in targets:
                if not isinstance(t, str) or key in ("type", "canonical", "law"):
                    continue
                report["checked"] += 1
                ok, _where = _resolve(t)
                if not ok:
                    report["missing"].append({"section": sec, "key": key, "target": t})
                    continue
                if sec in _IMPORT_SECTIONS and "/" not in t and not t.endswith(".py"):
                    # `_resolve` reports a symbol entry as `module.py::name`; import the MODULE.
                    # Passing the full dotted symbol to import_module raises ModuleNotFoundError
                    # and reads as a broken manifest entry when the entry is perfectly correct.
                    mod_name = t
                    if _where.endswith(f"::{t.rsplit('.', 1)[-1]}"):
                        mod_name = t.rsplit(".", 1)[0]
                    try:
                        importlib.import_module(mod_name)
                    except Exception as exc:
                        report["unimportable"].append(
                            {"section": sec, "key": key, "target": t,
                             "error": f"{type(exc).__name__}: {str(exc)[:120]}"})

    # RETIRED MUST BE UNREACHABLE.
    for row in (man.get("retired") or {}).get("_list", []):
        path = row.get("path")
        if not path:
            continue
        report["checked"] += 1
        if not (ROOT / path).exists():
            continue                      # deleted is a fine way to be retired
        callers = _grep_callers(path)
        if callers and not _halts_on_mandate(path):
            report["retired_reachable"].append(
                {"path": path, "callers": callers[:5],
                 "why": ("a retired path invoked from live code and not halting is not retired; "
                         "add a mandate halt or remove the caller")})

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"  checked {report['checked']} entries")
    for label, rows in (("MISSING", report["missing"]),
                        ("UNIMPORTABLE", report["unimportable"]),
                        ("RETIRED BUT REACHABLE", report["retired_reachable"])):
        if rows:
            print(f"\n  {label} ({len(rows)}):")
            for r in rows[:8]:
                print(f"    {r.get('target') or r.get('path')}"
                      f"{': ' + r['error'] if r.get('error') else ''}"
                      f"{' <- ' + ', '.join(r['callers']) if r.get('callers') else ''}")
    if not any((report["missing"], report["unimportable"], report["retired_reachable"])):
        print("  manifest describes the repo that exists")
    print(f"  -> {OUT}")
    return 1 if any((report["missing"], report["unimportable"],
                     report["retired_reachable"])) else 0


if __name__ == "__main__":
    raise SystemExit(main())
