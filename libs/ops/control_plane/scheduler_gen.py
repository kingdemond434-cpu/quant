"""GENERATE SCHEDULING FROM THE REGISTRY -- "built but never put on a clock" cannot happen.

The desk's oldest recurring defect has one shape: an organ is written, it is correct, it is
imported, it is documented, and nothing ever runs it. 293 unwired organs were counted in one
morning. The fix is not another audit; it is to stop MAINTAINING the schedule as a separate
artifact. The schedule is RENDERED from the component registry:

    desired_rows()      the box task manifest, from the specs that own a box task
    manifest_drift()    what the manifest says that the specs do not, and vice versa (a test)
    write_manifest()    --write: regenerates the TASK lines IN PLACE, keeping every comment
    task_xml()          one Windows task definition per component (UTF-16, SYSTEM, IgnoreNew,
                        ExecutionTimeLimit from the spec, keep-alive triggers for residents)
    validate()          --validate: the LIVE `schtasks /Query /FO CSV /V` table against desired
                        state -- missing, extra, disabled, wrong trigger
    apply()             --apply: box only, behind a flag; registers what is missing and retires
                        what desired state removed
    timer_validate()    the same for the VPS's systemd timers, where the spec says host=vps

WRITE IS IN-PLACE, NOT WHOLESALE. `box_tasks.manifest` carries the reasoning for why each task
exists -- five tasks `stall_watch` heals with no installer, the false-alarm note on
MT5-Gauntlet-Rotation, the measured 2026-09-16 census. Regenerating the file from scratch would
throw all of that away and call it automation. The generator replaces TASK lines where they
stand, appends new ones under a named block, and never touches a comment.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from libs.ops.control_plane.specs import UNMEASURED, ComponentSpec, Registry

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
MANIFEST = DESK / "ops" / "box_tasks.manifest"
GENERATED_BANNER = ("# --- GENERATED FROM desks/mt5/ops/components.py by "
                    "libs/ops/control_plane/scheduler_gen.py --write. Rows below this line are "
                    "owned by the component registry; edit the registry, never this block. ---")

_TASK_LINE = re.compile(r"^(\s*)TASK\s+(.*)$")
_KV = re.compile(r'(\w+)="([^"]*)"')


def _row_text(row: Mapping[str, str]) -> str:
    return (f'TASK name="{row["name"]}" trigger="{row["trigger"]}" runs="{row["runs"]}" '
            f'installer="{row["installer"]}" lane="{row["lane"]}"')


def _trigger_words(spec: ComponentSpec) -> str:
    """The manifest's plain-words trigger for one spec. Residents say keep-alive, because that is
    what the trigger IS: a no-op while the singleton lives."""
    note = re.search(r"trigger='([^']*)'", spec.notes or "")
    if note:
        return note.group(1)
    if spec.kind == "resident":
        return "at startup + every 10 minutes (keep-alive of a 24/7 resident)"
    if spec.cadence_s is None:
        return "UNDECLARED"
    if spec.cadence_s % 3600 == 0:
        hours = spec.cadence_s // 3600
        return "every 1 hour" if hours == 1 else f"every {hours} hours"
    return f"every {spec.cadence_s // 60} minutes"


def desired_rows(registry: Registry) -> dict[str, dict[str, str]]:
    """task name -> the manifest row the registry says must exist."""
    out: dict[str, dict[str, str]] = {}
    # THE TASK'S OWN SPEC OWNS ITS ROW. `task:` and `resident:` ids are derived from the manifest
    # and the resident families; an explicit component that merely RIDES a task (the control
    # plane rides MT5-ClockFixer) must not rewrite that task's `runs` to its own file.
    ordered = sorted(registry.all(),
                     key=lambda s: (not s.component_id.startswith(("task:", "resident:")),
                                    s.component_id))
    for s in ordered:
        if s.kind not in ("task", "resident") or not s.scheduled:
            continue
        name = s.schedule
        runs = s.code_paths[0] if s.code_paths else "UNKNOWN"
        installer = "NONE"
        m = re.search(r"installer=(\S+)", s.notes or "")
        if m:
            installer = m.group(1)
        lane = s.owner.split(":", 1)[1] if s.owner.startswith("lane:") else "research"
        row = {"name": name, "trigger": _trigger_words(s), "runs": runs,
               "installer": installer, "lane": lane, "component_id": s.component_id}
        out.setdefault(name, row)
    return out


def manifest_rows(path: Path | None = None) -> dict[str, list[dict[str, str]]]:
    p = path or MANIFEST
    out: dict[str, list[dict[str, str]]] = {}
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        m = _TASK_LINE.match(line)
        if not m:
            continue
        row = dict(_KV.findall(m.group(2)))
        if row.get("name"):
            out.setdefault(row["name"], []).append(row)
    return out


def manifest_drift(registry: Registry, path: Path | None = None) -> dict[str, Any]:
    """What the manifest and the registry disagree about. The drift test pins `missing` to [].

    `extra` is NOT a failure. The manifest is also the box's DR floor and holds tasks this
    repository can only observe (MT5-MoatFence, MT5-CacheWarm): they have a manifest line and no
    in-repo declaration, which is the honest state and the reason the file's own ratchet counts
    UNDECLARED triggers rather than deleting them.
    """
    desired = desired_rows(registry)
    have = manifest_rows(path)
    missing = sorted(set(desired) - set(have))
    extra = sorted(set(have) - set(desired))
    mismatched: list[dict[str, Any]] = []
    for name, row in sorted(desired.items()):
        rows = have.get(name) or []
        if not rows:
            continue
        triggers = {r.get("trigger") for r in rows}
        if row["trigger"] != "UNDECLARED" and row["trigger"] not in triggers:
            mismatched.append({"name": name, "desired_trigger": row["trigger"],
                               "manifest_trigger": sorted(triggers)})
    return {"missing": missing, "extra": extra, "mismatched": mismatched,
            "desired": len(desired), "in_manifest": len(have),
            "why": ("a task the registry declares and the manifest does not know is a DR floor "
                    "that cannot rebuild the desk; the reverse is a task this repo can only "
                    "observe on the box")}


def _merge_row(existing: Mapping[str, str], desired: Mapping[str, str]) -> dict[str, str]:
    """The registry's facts over the manifest's, field by field, and ONLY where the registry
    knows something: an UNDECLARED trigger, an UNKNOWN runs or a NONE installer in the desired
    row is an absence, and an absence must not overwrite a fact the manifest read off the box."""
    trigger = desired.get("trigger") or "UNDECLARED"
    runs = desired.get("runs") or "UNKNOWN"
    installer = desired.get("installer") or "NONE"
    return {
        "name": str(existing.get("name") or desired.get("name") or ""),
        "trigger": trigger if trigger != "UNDECLARED" else str(existing.get("trigger") or
                                                               "UNDECLARED"),
        "runs": runs if runs != "UNKNOWN" else str(existing.get("runs") or "UNKNOWN"),
        "installer": installer if installer != "NONE" else str(existing.get("installer") or
                                                                "NONE"),
        "lane": str(desired.get("lane") or existing.get("lane") or "research"),
    }


def write_manifest(registry: Registry, path: Path | None = None) -> dict[str, Any]:
    """Rewrite the manifest's TASK lines from the registry, in place, preserving every comment."""
    p = path or MANIFEST
    desired = desired_rows(registry)
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    seen: set[str] = set()
    out: list[str] = []
    changed = 0
    for line in lines:
        m = _TASK_LINE.match(line)
        if not m:
            out.append(line)
            continue
        row = dict(_KV.findall(m.group(2)))
        name = row.get("name") or ""
        if name in desired and name not in seen:
            seen.add(name)
            merged = _merge_row(row, desired[name])
            if merged == {k: row.get(k, "") for k in ("name", "trigger", "runs", "installer",
                                                        "lane")}:
                out.append(line)            # same facts: keep the line, its alignment, its place
            else:
                changed += 1
                out.append(m.group(1) + _row_text(merged))
        else:
            out.append(line)
    added = [n for n in sorted(desired) if n not in seen]
    if added:
        out += ["", GENERATED_BANNER]
        out += [_row_text(desired[n]) for n in added]
    text = "\n".join(out) + "\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)
    return {"path": str(p), "rows_rewritten": changed, "rows_added": added}


# ------------------------------------------------------------------------------- the XML
def _iso8601(seconds: int | None) -> str:
    if not seconds or seconds <= 0:
        return "PT0S"
    if seconds % 3600 == 0:
        return f"PT{seconds // 3600}H"
    if seconds % 60 == 0:
        return f"PT{seconds // 60}M"
    return f"PT{seconds}S"


def task_xml(spec: ComponentSpec, *, python: str = r"C:\Python313\python.exe",
             working_dir: str = r"C:\opt\quant", root: str = r"C:\opt\quant") -> str:
    """The Windows Task Scheduler definition for one component.

    SYSTEM (S-1-5-18) because the box runs its tasks as SYSTEM; IgnoreNew because a second
    instance of a singleton is a process that starts, fails to take the lock and exits -- which
    read as a successful restart for as long as the fixer trusted return codes; and
    ExecutionTimeLimit FROM THE SPEC, because PT20M terminated MT5-AdoptRelease before its seal
    and a limit that is not the component's own is a guess with the same shape.
    """
    exe = spec.code_paths[0] if spec.code_paths else ""
    args = " ".join(spec.production_args)
    cmd_args = f'"{root}\\{exe.replace("/", chr(92))}"' + (f" {args}" if args else "")
    keepalive = spec.kind == "resident"
    every = _iso8601(spec.cadence_s or 600)
    limit = _iso8601(spec.timeout_s) if spec.timeout_s else "PT0S"
    boot = ("  <BootTrigger>\n    <Enabled>true</Enabled>\n  </BootTrigger>\n"
            if keepalive else "")
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.4" '
        'xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo>\n"
        f"    <Description>{spec.component_id}: {spec.notes or 'desk component'}</Description>\n"
        "    <Author>libs/ops/control_plane/scheduler_gen.py</Author>\n"
        "  </RegistrationInfo>\n"
        "  <Triggers>\n"
        f"{boot}"
        "    <TimeTrigger>\n"
        "      <Repetition>\n"
        f"        <Interval>{every}</Interval>\n"
        "        <StopAtDurationEnd>false</StopAtDurationEnd>\n"
        "      </Repetition>\n"
        "      <StartBoundary>2026-01-01T00:00:00</StartBoundary>\n"
        "      <Enabled>true</Enabled>\n"
        "    </TimeTrigger>\n"
        "  </Triggers>\n"
        "  <Principals>\n"
        '    <Principal id="Author">\n'
        "      <UserId>S-1-5-18</UserId>\n"
        "      <RunLevel>HighestAvailable</RunLevel>\n"
        "    </Principal>\n"
        "  </Principals>\n"
        "  <Settings>\n"
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n"
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        "    <StartWhenAvailable>true</StartWhenAvailable>\n"
        f"    <ExecutionTimeLimit>{limit}</ExecutionTimeLimit>\n"
        "    <Enabled>true</Enabled>\n"
        "  </Settings>\n"
        '  <Actions Context="Author">\n'
        "    <Exec>\n"
        f"      <Command>{python}</Command>\n"
        f"      <Arguments>{cmd_args}</Arguments>\n"
        f"      <WorkingDirectory>{working_dir}</WorkingDirectory>\n"
        "    </Exec>\n"
        "  </Actions>\n"
        "</Task>\n")


def write_xml(spec: ComponentSpec, out_dir: Path, **kw: Any) -> Path:
    """UTF-16, which `schtasks /Create /XML` requires and silently fails on without."""
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{spec.schedule}.xml"
    p.write_text(task_xml(spec, **kw), encoding="utf-16")
    return p


# --------------------------------------------------------------------------- live validation
def live_tasks(runner: Any = None) -> dict[str, dict[str, str]] | None:
    """The box's own table, `schtasks /Query /FO CSV /V`. None off-box -- UNMEASURED, not empty.

    An empty dict would read as "the box has no tasks", which is a very different claim from
    "this machine is not the box", and the difference decides whether `--apply` would register
    ninety tasks on a laptop.
    """
    if runner is None and sys.platform != "win32":
        return None
    run = runner or (lambda: subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V"],
                                            capture_output=True, text=True, check=False).stdout)
    try:
        text = run()
    except OSError:
        return None
    if not text:
        return None
    out: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("TaskName") or "").strip().lstrip("\\")
        if not name or name.lower() == "taskname":
            continue
        out[name] = {k: (v or "").strip() for k, v in row.items() if k}
    return out


def validate(registry: Registry, *, runner: Any = None,
             live: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    """Desired vs the LIVE scheduler table: missing, extra, disabled, wrong trigger."""
    desired = desired_rows(registry)
    table = dict(live) if live is not None else live_tasks(runner)
    if table is None:
        return {"measured": False, "why": "not the box: schtasks is unavailable, so the live "
                                          "schedule is UNMEASURED",
                "desired": len(desired)}
    missing = sorted(n for n in desired if n not in table)
    extra = sorted(n for n in table if n.startswith(("MT5-", "E8-")) and n not in desired)
    disabled = sorted(n for n, row in table.items()
                      if n in desired and str(row.get("Scheduled Task State", "")).lower()
                      == "disabled")
    wrong: list[dict[str, Any]] = []
    for name, row in sorted(desired.items()):
        live_row = table.get(name)
        if not live_row:
            continue
        spec = registry.get(str(row.get("component_id") or ""))
        want = spec.cadence_s if spec else None
        got = _repeat_seconds(str(live_row.get("Repeat: Every", "")))
        if want and got and abs(got - want) > max(60, want * 0.2):
            wrong.append({"name": name, "desired_cadence_s": want, "live_cadence_s": got})
    return {"measured": True, "desired": len(desired), "live": len(table),
            "missing": missing, "extra": extra, "disabled": disabled, "wrong_trigger": wrong,
            "ok": not (missing or disabled or wrong)}


_REPEAT = re.compile(r"(\d+):(\d+):(\d+)")


def _repeat_seconds(text: str) -> int | None:
    m = _REPEAT.search(text or "")
    if not m:
        return None
    h, mi, s = (int(g) for g in m.groups())
    total = h * 3600 + mi * 60 + s
    return total or None


def apply(registry: Registry, *, out_dir: Path | None = None, runner: Any = None,
          confirm: bool = False, retire: bool = False) -> dict[str, Any]:
    """Register missing tasks and (with --retire) remove ones desired state dropped. BOX ONLY.

    Guarded twice on purpose: `confirm` must be passed AND the machine must be Windows. A
    scheduler generator that can register ninety SYSTEM tasks is exactly the tool that must not
    run by accident on a developer's checkout.
    """
    if not confirm:
        return {"applied": False, "why": "--apply requires --confirm; nothing was registered"}
    if sys.platform != "win32" and runner is None:
        return {"applied": False, "why": "not the box: task registration is Windows-only"}
    v = validate(registry, runner=None)
    if not v.get("measured"):
        return {"applied": False, "why": v.get("why")}
    d = out_dir or (DESK / "data" / "generated_tasks")
    desired = desired_rows(registry)
    created: list[str] = []
    retired: list[str] = []
    run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True,
                                                 check=False).returncode)
    for name in v["missing"]:
        spec = registry.get(str(desired[name].get("component_id") or ""))
        if spec is None:
            continue
        xml = write_xml(spec, d)
        rc = run(["schtasks", "/Create", "/TN", name, "/XML", str(xml), "/F"])
        if rc == 0:
            created.append(name)
    if retire:
        for name in v["extra"]:
            rc = run(["schtasks", "/Delete", "/TN", name, "/F"])
            if rc == 0:
                retired.append(name)
    return {"applied": True, "created": created, "retired": retired, "validate": v}


# ----------------------------------------------------------------------------- VPS timers
def timer_validate(registry: Registry, root: Path | None = None) -> dict[str, Any]:
    """Every host=vps component must have a .timer AND a .service in ops/. Repo-only, so it means
    the same in CI, a fresh clone and on the box -- the VPS's live table is not reachable here."""
    base = root or ROOT
    rows: list[dict[str, Any]] = []
    for s in registry.all():
        if s.host != "vps":
            continue
        unit = s.schedule
        timer = base / "ops" / f"{unit}.timer"
        service = base / "ops" / f"{unit}.service"
        rows.append({"component_id": s.component_id, "unit": unit,
                     "timer": timer.exists(), "service": service.exists(),
                     "cadence_s": s.cadence_s})
    broken = [r for r in rows if not (r["timer"] and r["service"])]
    return {"timers": len(rows), "incomplete": broken,
            "ok": not broken,
            "why": "" if not broken else
                   f"{len(broken)} vps component(s) lack a .timer/.service pair"}


def _registry(root: Path | None = None) -> Registry:
    import importlib.util
    path = (root or ROOT) / "desks" / "mt5" / "ops" / "components.py"
    spec_ = importlib.util.spec_from_file_location("_cp_components_sched", path)
    if spec_ is None or spec_.loader is None:
        raise RuntimeError(f"cannot load the component registry from {path}")
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    reg = mod.registry(root)
    if not isinstance(reg, Registry):
        raise RuntimeError(f"{path} did not return a Registry")
    return reg


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="regenerate the manifest's TASK lines")
    ap.add_argument("--validate", action="store_true", help="live schtasks table vs desired")
    ap.add_argument("--apply", action="store_true", help="register missing tasks (box only)")
    ap.add_argument("--confirm", action="store_true", help="required by --apply")
    ap.add_argument("--retire", action="store_true", help="with --apply, delete dropped tasks")
    ap.add_argument("--xml", metavar="DIR", help="write one task XML per component into DIR")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(list(argv) if argv is not None else None)
    reg = _registry()
    out: dict[str, Any] = {"drift": manifest_drift(reg), "timers": timer_validate(reg)}
    if a.write:
        out["write"] = write_manifest(reg)
    if a.xml:
        d = Path(a.xml)
        out["xml"] = [str(write_xml(reg.get(str(r["component_id"])) or ComponentSpec(r["name"]),
                                    d))
                      for r in desired_rows(reg).values()]
    if a.validate or a.apply:
        out["validate"] = validate(reg)
    if a.apply:
        out["apply"] = apply(reg, confirm=a.confirm, retire=a.retire)
    if a.json:
        print(json.dumps(out, indent=1, default=str))
    else:
        d = out["drift"]
        print(f"scheduler: {d['desired']} desired task(s), {d['in_manifest']} in the manifest; "
              f"missing={len(d['missing'])} mismatched={len(d['mismatched'])} "
              f"extra={len(d['extra'])}")
        for n in d["missing"][:10]:
            print("   missing from manifest:", n)
        for m in d["mismatched"][:10]:
            print("   trigger drift:", m)
        v = out.get("validate")
        if v:
            print(f"   live: {v.get('why') or v}")
    return 0 if not out["drift"]["missing"] and not out["drift"]["mismatched"] else 1


UNMEASURED_TRIGGER = UNMEASURED


def all_desired(registry: Registry) -> Iterable[str]:
    return sorted(desired_rows(registry))


if __name__ == "__main__":
    raise SystemExit(main())
