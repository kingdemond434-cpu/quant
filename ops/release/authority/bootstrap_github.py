#!/usr/bin/env python3
"""The GitHub half of the one-time Level 2 bootstrap (ops/release/authority/LEVEL2.md; called by
bootstrap_level2.ps1, run by the owner with his own gh login, because each act here is his).

    python bootstrap_github.py --repo OWNER/NAME ready --pr N
    python bootstrap_github.py --repo OWNER/NAME rulesets --state-app-id N [--apply]

`ready`: exit 0 only when the PR's exact head has every gating and AUTO check passed with the
gate's own provenance rules AND the latest trusted audit verdict is a CLEAR naming that head --
the same bar the gate holds every ROOT PR to. It merges nothing; the caller does, pinned to the
head it prints.

`rulesets`: fill in the state App's id, prove both rulesets safe with check_ruleset.py, and with
--apply create
(or updates, matched by name) both rulesets through the REST API with the gh login of whoever
runs it -- the repository admin, because only an admin can set rules -- and then reads the
public rules endpoint for LIVE back, exactly as the authority does every pass
(authority.level2_enforced). It exits 0 only when GitHub itself reports the rule active.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"_boot_{name}", HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fill(rs: dict[str, Any], state_app_id: int) -> dict[str, Any]:
    """The ruleset with its one placeholder (Integration actor_id 0) set to the state App."""
    out = copy.deepcopy(rs)
    holes = [b for b in out.get("bypass_actors") or []
             if b.get("actor_type") == "Integration" and b.get("actor_id") == 0]  # fmt: skip
    if len(holes) != 1:
        raise ValueError(f"{rs.get('name')}: expected exactly one placeholder bypass actor")
    holes[0]["actor_id"] = int(state_app_id)
    return out


def gh(*args: str, data: Any = None) -> Any:
    cmd = ["gh", "api", *args] + (["--input", "-"] if data is not None else [])
    p = subprocess.run(cmd, input=json.dumps(data) if data is not None else None,
                       capture_output=True, text=True, check=False, timeout=60)  # fmt: skip
    if p.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout) if p.stdout.strip() else None


def apply(repo: str, rs: dict[str, Any]) -> str:
    have = gh(f"repos/{repo}/rulesets?includes_parents=false&per_page=100") or []
    same = [r for r in have if r.get("name") == rs["name"]]
    if same:
        gh(f"repos/{repo}/rulesets/{same[0]['id']}", "-X", "PUT", data=rs)
        return f"updated ruleset {same[0]['id']} {rs['name']}"
    got = gh(f"repos/{repo}/rulesets", "-X", "POST", data=rs)
    return f"created ruleset {got.get('id')} {rs['name']}"


def gate() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_boot_audit_gate", HERE.parents[2] / ".github" / "scripts" / "audit_gate.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ready(ag: Any, repo: str, pr: int) -> tuple[str | None, list[str]]:
    """(head to merge at, problems). Pure over `ag`'s reads, so it is tested with a fake."""
    p = ag._gh(f"repos/{repo}/pulls/{pr}")
    head = str(p["head"]["sha"])
    out: list[str] = []
    if p.get("state") != "open" or p.get("merged"):
        out.append(f"#{pr} is not open")
    if p["base"]["ref"] != LIVE or (p["head"].get("repo") or {}).get("full_name") != repo:
        out.append(f"#{pr} is not a same-repo PR into LIVE")
    runs = (ag._gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100") or {}).get(
        "check_runs") or []  # fmt: skip
    state, why = ag.checks(runs, tuple(ag.GATING_JOBS) + tuple(ag.AUTO_JOBS),
                           ag.provenance(repo, pr, head))  # fmt: skip
    if state != "pass":
        out.append(f"checks on {head[:9]}: {state} ({why})")
    comments = ag._flat(ag._gh(f"repos/{repo}/issues/{pr}/comments?per_page=100", "--paginate",
                               "--slurp"))  # fmt: skip
    found = ag.verdicts(comments)
    if not found or found[-1]["verdict"] != "CLEAR" or not head.startswith(found[-1]["sha"]):
        last = f"{found[-1]['verdict']} {found[-1]['sha'][:9]}" if found else "none"
        out.append(f"no standing audit CLEAR on {head[:9]} (latest: {last})")
    return (head if not out else None), out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ready")
    r.add_argument("--pr", type=int, required=True)
    rs = sub.add_parser("rulesets")
    rs.add_argument("--state-app-id", type=int, required=True)
    rs.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "ready":
        head, bad = ready(gate(), a.repo, a.pr)
        for b in bad:
            print(f"NOT READY: {b}")
        if head:
            print(head)
        return 0 if head else 1
    live = fill(json.loads((HERE / "ruleset_live.json").read_text(encoding="utf-8")),
                a.state_app_id)  # fmt: skip
    master = fill(json.loads((HERE / "ruleset_master.json").read_text(encoding="utf-8")),
                  a.state_app_id)  # fmt: skip
    with tempfile.TemporaryDirectory() as d:
        lp, mp = Path(d) / "live.json", Path(d) / "master.json"
        lp.write_text(json.dumps(live), encoding="utf-8")
        mp.write_text(json.dumps(master), encoding="utf-8")
        rc = _load("check_ruleset").main(["--repo", a.repo, str(lp), "--master", str(mp)])
    if rc != 0:
        print("NOTHING APPLIED: the checker refused.")
        return 1
    if not a.apply:
        print("checked; run with --apply to apply")
        return 0
    # master and production first: once LIVE is enforced, a promote must already be able to run
    print(apply(a.repo, master))
    print(apply(a.repo, live))

    class _Ag:
        @staticmethod
        def _gh(path: str) -> Any:
            return gh(path)

    auth = _load("authority")
    ok, why = auth.level2_enforced(_Ag, a.repo, LIVE)
    print(f"GitHub reports: {why}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
