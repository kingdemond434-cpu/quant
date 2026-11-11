"""THE RELEASE TRAIN'S SLO: is Auditor-CLEARed work reaching LIVE, and if not, say why, page, and
fix what is mechanical.

    python scripts/merge_flow.py [--repo OWNER/NAME] [--no-heal] [--no-alert] [--print]

Writes desks/mt5/reports/MERGE_FLOW.json (box state, published by `publish_state`); rc 2 on RED.
Runs as the core hourly leg `merge_flow`, on its OWN clock, never inside the merge sweep.

WHY (Hourly pass idea 587, 2026-11-11). Nothing merged into LIVE from 23:21Z on 11-10 while about
forty PRs carried an Auditor CLEAR. The box's GitHub login had expired at 23:16Z (401), so the box
merge sweep (Quant-WorkflowGate) could read and write nothing. scripts/merge_pipeline_watch.py
runs INSIDE that sweep with that same login, so it went quiet with it, and no page went out.
This organ is built not to share those failure modes:

  * its own clock (the hourly cycle), not the sweep's;
  * it reads GitHub with the box login when that works, and ANONYMOUSLY when it does not (the
    repository is public), so a dead login is a finding here, never a blind spot;
  * the Auditor's rows come from the audit-registry ref over raw HTTPS.

RED (each named in `reasons`, in plain words in the page):
    MERGE_SLO     a PR whose newest Auditor registry row is CLEAR for its current head has
                  waited past its veto window (VETO_H) plus SLO_H since that row, and nothing
                  merged into LIVE in SLO_H. A CLEAR inside its 24 h window is counted
                  (`in_veto_window`), never alarmed on: the window is zuck's veto, by design
    GATE_SILENT   CLEARed PRs are open and the sweep has posted no `audit/clear` status on any
                  of their heads for GATE_SILENT_MIN (it is not running, or cannot write)
    BOX_LOGIN     the box's own `gh` cannot read GitHub (an expired login reads as 401)

SELF-HEAL, only what is mechanical and safe, at most once per HEAL_EVERY:
    GATE_SILENT with a working login  -> start the sweep task now (schtasks /Run), once
    BOX_LOGIN                         -> nothing: renewing a login is not a thing a script may
                                         do (no secrets are read or written here); the page says
                                         exactly that and what is waiting on it
It never merges, approves, comments, re-runs, cancels or edits anything on GitHub.

THE PAGE goes to every armed channel (libs/ops/alert_channels.send_all) when RED starts, when its
reasons change, every REPAGE_H while it lasts, and once when merges flow again.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = "kingdemond434-cpu/quant"
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPORT = ROOT / "desks" / "mt5" / "reports" / "MERGE_FLOW.json"
STATE = ROOT / "desks" / "mt5" / "data" / "merge_flow_state.json"
REGISTRY_REF = "audit-registry"
REGISTRY_FILE = "REGISTRY_ROWS.jsonl"
GATE_STATUS = "audit/clear"
GATE_TASK = "Quant-WorkflowGate"

SLO_H = 2.0
#: The registry path's veto window (.github/scripts/audit_gate.py REGISTRY_HOLD_H): a CLEAR merges
#: no earlier than this after the gate delivered its veto notice. Waiting inside it is the design,
#: never a breach, and nothing here shortens or works around it.
VETO_H = 24.0
GATE_SILENT_MIN = 40.0
HEAL_EVERY = timedelta(minutes=55)
REPAGE_H = 3.0
#: Heads whose gate status is read per run (oldest CLEAR first): bounded so an anonymous read
#: stays far inside GitHub's 60 requests an hour.
STATUS_SAMPLE = 12
UA = "merge-flow-slo"

Fetch = Callable[[str], Any]


def _ts(s: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _h(now: datetime, t: datetime | None) -> float | None:
    return None if t is None else round((now - t).total_seconds() / 3600.0, 2)


# ----------------------------------------------------------------------------- pure judgement


def newest_rows(lines: Iterable[str]) -> dict[int, dict[str, Any]]:
    """The Auditor's newest row per PR (the file is append-only, so the last one wins)."""
    out: dict[int, dict[str, Any]] = {}
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("pr"), int):
            out[r["pr"]] = r
    return out


def last_merge(commits: Iterable[Mapping[str, Any]]) -> tuple[str, datetime] | None:
    """(sha, time) of the newest PR merge on LIVE among `commits` (newest first)."""
    for c in commits:
        msg = str((c.get("commit") or {}).get("message") or "")
        if msg.startswith("Merge #") and len(c.get("parents") or []) == 2:
            at = _ts(((c.get("commit") or {}).get("committer") or {}).get("date"))
            if at is not None:
                return str(c.get("sha")), at
    return None


def _blocker(status: Mapping[str, Any] | None) -> str:
    if not status:
        return "no gate status on this head"
    why = str(status.get("description") or "").strip() or str(status.get("state"))
    return why.split(";")[0].split(" -- ")[0][:80]


def assess(
    now: datetime,
    prs: list[Mapping[str, Any]],
    rows: Mapping[int, Mapping[str, Any]],
    merge: tuple[str, datetime] | None,
    statuses: Mapping[int, Mapping[str, Any] | None],
    login: tuple[bool, str],
) -> dict[str, Any]:
    """The verdict, from facts only. `statuses`: the gate's `audit/clear` status per sampled PR
    (None: it posted none on that head)."""
    cleared = []
    for p in prs:
        n, head = int(p["number"]), str((p.get("head") or {}).get("sha") or "")
        r = rows.get(n)
        if not r or r.get("verdict") != "CLEAR" or r.get("sha") != head:
            continue
        cleared.append({
            "pr": n, "head": head[:12], "draft": bool(p.get("draft")),
            "cleared_at": r.get("at"), "waiting_h": _h(now, _ts(r.get("at"))),
            "blocker": _blocker(statuses.get(n)) if n in statuses else "not sampled",
            "gate_seen": (statuses.get(n) or {}).get("updated_at"),
        })  # fmt: skip
    cleared.sort(key=lambda c: -(c["waiting_h"] or 0.0))
    merge_age = _h(now, merge[1]) if merge else None
    seen = [t for c in cleared if (t := _ts(c["gate_seen"])) is not None]
    gate_age_min = round((now - max(seen)).total_seconds() / 60.0, 1) if seen else None
    reasons = []
    oldest = cleared[0]["waiting_h"] if cleared else None
    due = VETO_H + SLO_H
    overdue = [c for c in cleared if c["waiting_h"] is not None and c["waiting_h"] >= due]
    if overdue and (merge_age is None or merge_age >= SLO_H):
        reasons.append("MERGE_SLO")
    if cleared and statuses and (gate_age_min is None or gate_age_min >= GATE_SILENT_MIN):
        reasons.append("GATE_SILENT")
    if not login[0]:
        reasons.append("BOX_LOGIN")
    tally = Counter(c["blocker"] for c in cleared if c["blocker"] != "not sampled")
    return {
        "schema": "merge_flow/1",
        "at": now.isoformat(),
        "verdict": "RED" if reasons else "GREEN",
        "reasons": reasons,
        "last_merge": {"sha": merge[0][:12], "at": merge[1].isoformat()} if merge else None,
        "merge_age_h": merge_age,
        "cleared_waiting": len(cleared),
        "overdue": len(overdue),
        "in_veto_window": len(cleared) - len(overdue),
        "oldest_clear_waiting_h": oldest,
        "gate_last_seen_min": gate_age_min,
        "box_login": {"ok": login[0], "detail": login[1][:200]},
        "blockers": dict(tally.most_common()),
        "prs": cleared,
        "thresholds": {"slo_h": SLO_H, "veto_h": VETO_H, "gate_silent_min": GATE_SILENT_MIN},
    }


def _or(v: Any, dflt: str) -> str:
    return dflt if v is None else str(v)


def heal_plan(doc: Mapping[str, Any], last_heal: datetime | None, now: datetime) -> str | None:
    """The one mechanical fix due now, or None."""
    if "GATE_SILENT" not in doc["reasons"] or "BOX_LOGIN" in doc["reasons"]:
        return None
    if last_heal is not None and now - last_heal < HEAL_EVERY:
        return None
    return "start_gate"


def page(doc: Mapping[str, Any], state: Mapping[str, Any], now: datetime) -> tuple[str, str] | None:
    """(title, body) when a page is due, else None."""
    was = list(state.get("reasons") or [])
    last = _ts(state.get("paged_at"))
    if doc["verdict"] == "GREEN":
        if was:
            return "Merges are flowing again", (
                f"LIVE's last merge {doc['last_merge']['sha'] if doc['last_merge'] else '?'}; "
                f"{doc['cleared_waiting']} CLEARed PR(s) still open."
            )
        return None
    due = was != doc["reasons"] or last is None or (now - last) >= timedelta(hours=REPAGE_H)
    if not due:
        return None
    words = {
        "MERGE_SLO": f"nothing has merged into LIVE for {doc['merge_age_h']} h while "
                     f"{doc['overdue']} Auditor-CLEARed PR(s) are past their 24 h veto window "
                     f"(oldest CLEAR {doc['oldest_clear_waiting_h']} h)",
        "GATE_SILENT": "the box merge sweep has not marked any CLEARed PR for "
                       f"{_or(doc['gate_last_seen_min'], 'ever')} min, so it is not running or "
                       "cannot write, and no veto window can start",
        "BOX_LOGIN": "the box's GitHub login does not work "
                     f"({doc['box_login']['detail'][:80]}), so nothing can merge until it is "
                     "renewed",
    }  # fmt: skip
    top = "; ".join(f"{k} x{v}" for k, v in list(doc["blockers"].items())[:3])
    body = ". ".join(words[r] for r in doc["reasons"]) + "."
    if top:
        body += f" What the sweep says holds them: {top}."
    return f"RED release train: {', '.join(doc['reasons'])}", body


# ----------------------------------------------------------------------------- the box side


def gh_fetch(path: str) -> Any:
    gh = os.environ.get("GH_BIN") or "gh"
    p = subprocess.run([gh, "api", path], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60, check=False)  # fmt: skip
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200] or f"gh exit {p.returncode}")
    return json.loads(p.stdout or "null")


def anon_fetch(path: str) -> Any:
    hdr = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=hdr)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def raw_registry(repo: str) -> list[str]:
    url = f"https://raw.githubusercontent.com/{repo}/{REGISTRY_REF}/{REGISTRY_FILE}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8").splitlines()


def collect(repo: str, now: datetime, gh: Fetch = gh_fetch, anon: Fetch = anon_fetch,
            registry: Callable[[str], list[str]] = raw_registry) -> dict[str, Any]:  # fmt: skip
    try:
        gh("user")
        login, fetch = (True, "gh api user: ok"), gh
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        login, fetch = (False, f"gh api user: {exc}"), anon
    commits = fetch(f"repos/{repo}/commits?sha={LIVE}&per_page=100") or []
    prs = fetch(f"repos/{repo}/pulls?state=open&base={LIVE}&per_page=100") or []
    rows = newest_rows(registry(repo))
    statuses: dict[int, Mapping[str, Any] | None] = {}
    want = [p for p in prs if (r := rows.get(int(p["number"]))) and r.get("verdict") == "CLEAR"
            and r.get("sha") == (p.get("head") or {}).get("sha")]  # fmt: skip
    want.sort(key=lambda p: str(rows[int(p["number"])].get("at")))
    for p in want[:STATUS_SAMPLE]:
        got = fetch(f"repos/{repo}/commits/{p['head']['sha']}/status") or {}
        mine = [s for s in got.get("statuses") or [] if s.get("context") == GATE_STATUS]
        statuses[int(p["number"])] = mine[0] if mine else None
    return assess(now, prs, rows, last_merge(commits), statuses, login)


def start_gate() -> str:
    if os.name != "nt":
        return "not on the box: nothing started"
    p = subprocess.run(["schtasks", "/Run", "/TN", GATE_TASK], capture_output=True, text=True,
                       timeout=60, check=False)  # fmt: skip
    return f"schtasks /Run {GATE_TASK}: rc {p.returncode} {(p.stdout or p.stderr).strip()[:120]}"


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--no-heal", action="store_true")
    ap.add_argument("--no-alert", action="store_true")
    ap.add_argument("--print", action="store_true", help="stdout only: no report, heal or page")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    try:
        doc = collect(a.repo, now)
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, KeyError) as exc:
        doc = {"schema": "merge_flow/1", "at": now.isoformat(), "verdict": "UNMEASURED",
               "reasons": [], "error": f"{type(exc).__name__}: {str(exc)[:200]}"}  # fmt: skip
    if a.print:
        print(json.dumps(doc, indent=1))
        return 2 if doc["verdict"] == "RED" else 0
    state = _load(STATE)
    if doc["verdict"] in ("RED", "GREEN"):
        if not a.no_heal and heal_plan(doc, _ts(state.get("healed_at")), now) == "start_gate":
            doc["heal"] = start_gate()
            state["healed_at"] = now.isoformat()
        due = None if a.no_alert else page(doc, state, now)
        if due is not None:
            try:
                sys.path.insert(0, str(ROOT))
                from libs.ops.alert_channels import send_all

                got = send_all(*due)
                doc["paged"] = f"armed {got.get('armed', 0)}, delivered {got.get('delivered', 0)}"
            except Exception as exc:  # a page that fails is recorded, never fatal
                doc["paged"] = f"not sent ({type(exc).__name__})"
            state["paged_at"] = now.isoformat()
        state["reasons"] = doc["reasons"]
        _write(STATE, state)
    _write(REPORT, doc)
    print(f"merge_flow: {doc['verdict']} {' '.join(doc.get('reasons') or [])}".rstrip())
    return 2 if doc["verdict"] == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
