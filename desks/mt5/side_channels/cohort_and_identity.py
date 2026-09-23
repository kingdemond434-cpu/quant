"""Forward Cohort tracker + Cross-Platform Identity Graph (principal Drop 3, 2026-08-25).

THE TWO MINERS THE PRINCIPAL NAMED MOST-MISSING, and the reason they outrank another site:

FORWARD COHORT -- leaderboards are backward-selected; the cure is OUR OWN point-in-time record.
Every strategy/track-record row any miner discovers gets an IMMUTABLE cohort ID and a frozen t0
snapshot the day we first see it -- entry criteria never change retroactively. Then this module
re-observes each cohort member on the mortality schedule (t+30/90/180/365/730d): alive, dead
(404/410), delisted, changed. In two years that registry is proprietary asymmetric data
generated free by TIME: what today's public "champions" looked like BEFORE anyone knew which
would survive. The liveness check needs only the URL, so it works even for sources whose stat
selectors are still raw-capture.

IDENTITY GRAPH -- one strategy on three unrelated platforms is worth more than three
leaderboard rows. Authors are resolved across platforms from miner rows (author fields, MQL5
/en/users/ links, page URL patterns) into author -> presences -> evidence scores
(independent platform count, record longevity via cohorts, blowup/deleted counts). Scores are
recomputed every run from ground truth, never accumulated by hand.

Both are pure Python, invoked hourly at the end of seed_miners.run_and_save(); Claude sees only
the ranked tail of what these join together.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
INTEL = BASE / "data" / "intelligence"
COHORTS = INTEL / "cohorts"
REGISTRY = COHORTS / "cohort_registry.json"
OBS = COHORTS / "observations.jsonl"
GRAPH = INTEL / "identity_graph.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TRACKED_KINDS = {"track_record", "strategy_source", "strategy_thread", "leaderboard", "repo"}
SCHEDULE_D = (30, 90, 180, 365, 730)
MAX_CHECKS_PER_RUN = 25
AUTHOR_PATTERNS = [
    re.compile(r"mql5\.com/en/users/([A-Za-z0-9_\-.]{3,40})", re.I),
    re.compile(r"myfxbook\.com/members/([A-Za-z0-9_\-.]{3,40})", re.I),
    re.compile(r"tradingview\.com/u/([A-Za-z0-9_\-.]{3,40})", re.I),
    re.compile(r"github\.com/([A-Za-z0-9_\-]{2,40})/", re.I),
    re.compile(r"fxblue\.com/users/([A-Za-z0-9_\-.]{3,40})", re.I),
]


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def cohort_id(r: dict) -> str:
    raw = json.dumps({"u": r.get("url"), "t": r.get("title"), "s": r.get("source")},
                     sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def enroll_new(reg: dict) -> int:
    """Freeze a t0 snapshot for every never-seen tracked row across today's discovery files."""
    added = 0
    now = datetime.now(tz=UTC)
    stamp = f"discoveries_{now:%Y%m%d}"
    for f in INTEL.rglob(f"{stamp}_*.json"):
        rows = _read(f, [])
        if isinstance(rows, dict):
            rows = rows.get("discoveries", [])
        for r in rows:
            if not isinstance(r, dict) or r.get("kind") not in TRACKED_KINDS \
                    or not r.get("url"):
                continue
            cid = cohort_id(r)
            if cid in reg:
                continue
            try:
                from lang_intel import detect_mechanisms  # noqa: PLC0415
                tags = detect_mechanisms(" ".join(str(r.get(k, "")) for k in
                                                  ("title", "text")))
            except Exception:                                            # noqa: BLE001
                tags = []
            reg[cid] = {"t0": now.isoformat(timespec="seconds"), "frozen": r,
                        "mechanism_tags": tags,
                        "status": "ALIVE", "observations": 0, "next_due_d": SCHEDULE_D[0]}
            added += 1
    return added


def observe_due(reg: dict) -> int:
    """Mortality checks for members whose schedule is due; oldest-due first, politely capped."""
    now = datetime.now(tz=UTC)
    due = []
    for cid, m in reg.items():
        if m.get("status") in ("DEAD", "EXHAUSTED"):
            continue
        t0 = datetime.fromisoformat(m["t0"])
        age_d = (now - t0).days
        if age_d >= m.get("next_due_d", SCHEDULE_D[0]):
            due.append((age_d - m["next_due_d"], cid))
    due.sort(reverse=True)
    checked = 0
    # ORPHAN-SAFE. This loop sleeps a second and waits up to twenty per member, so the handle
    # used to be held open across MINUTES while `desks/mt5/data/` -- a git-TRACKED tree this
    # box checks out every ten minutes (auto_push) and hourly (the cycle) -- was rewritten under
    # it. That is the 2026-08-28 FX Blue defect exactly: the file gets unlinked, the process
    # keeps appending to a nameless inode, nothing errors, and a reader sees a clean short file.
    # ~500 harvested records were lost to it once already. Stage outside the tracked tree and
    # publish in one append at the end, so the window a checkout can eat is a single write and
    # an interrupted run leaves its rows recoverable in the staging file.
    stage = Path("/tmp") / f"{OBS.name}.staging"          # noqa: S108 -- outside the repo IS the point
    with stage.open("w", encoding="utf-8") as obs:
        for _, cid in due[:MAX_CHECKS_PER_RUN]:
            m = reg[cid]
            url = m["frozen"].get("url", "")
            verdict, code = "ALIVE", None
            try:
                time.sleep(1.0)
                resp = requests.get(url, headers=HEADERS, timeout=20,
                                    allow_redirects=True)
                code = resp.status_code
                if code in (404, 410):
                    verdict = "DEAD"
                elif code >= 400:
                    verdict = "BLOCKED"
                else:
                    low = resp.text[:4000].lower()
                    if any(t in low for t in ("signal was blocked", "no longer available",
                                              "has been removed", "deleted")):
                        verdict = "DELISTED"
            except Exception:                                            # noqa: BLE001
                verdict = "UNREACHABLE"
            m["observations"] += 1
            m["last_observed"] = now.isoformat(timespec="seconds")
            m["last_verdict"] = verdict
            if verdict == "DEAD":
                m["status"] = "DEAD"
                m["died_at"] = now.isoformat(timespec="seconds")
            nxt = [d for d in SCHEDULE_D if d > m.get("next_due_d", 0)]
            m["next_due_d"] = nxt[0] if nxt else 10**6
            if not nxt:
                m.setdefault("status", "ALIVE")
                if m["status"] == "ALIVE":
                    m["status"] = "EXHAUSTED"     # full schedule observed and survived
            obs.write(json.dumps({"cid": cid, "ts": now.isoformat(timespec="seconds"),
                                  "verdict": verdict, "http": code,
                                  "source": m["frozen"].get("source")}) + "\n")
            checked += 1
            obs.flush()
    if checked:
        OBS.parent.mkdir(parents=True, exist_ok=True)
        with OBS.open("a", encoding="utf-8") as fh:
            fh.write(stage.read_text(encoding="utf-8"))
        stage.unlink(missing_ok=True)
    return checked


def rebuild_identity_graph(reg: dict) -> dict:
    """Author -> platform presences -> evidence scores, recomputed from ground truth."""
    authors: dict[str, dict] = {}
    for cid, m in reg.items():
        r = m["frozen"]
        blob = " ".join(str(r.get(k, "")) for k in ("url", "text", "title"))
        for pat in AUTHOR_PATTERNS:
            for name in pat.findall(blob):
                key = name.lower()
                a = authors.setdefault(key, {"presences": {}, "cohorts": []})
                platform = pat.pattern.split("\\.")[0].strip("(?i").split("(")[-1] or "web"
                a["presences"].setdefault(r.get("source", platform), 0)
                a["presences"][r.get("source", platform)] += 1
                a["cohorts"].append(cid)
    now = datetime.now(tz=UTC)
    for key, a in authors.items():
        cids = a["cohorts"]
        dead = sum(1 for c in cids if reg.get(c, {}).get("status") == "DEAD")
        ages = [(now - datetime.fromisoformat(reg[c]["t0"])).days
                for c in cids if c in reg]
        a["scores"] = {
            "independent_evidence": len(a["presences"]),
            "record_count": len(cids),
            "longevity_max_d": max(ages) if ages else 0,
            "deleted_or_dead": dead,
            "mortality": round(dead / len(cids), 3) if cids else 0.0,
        }
        a["cohorts"] = cids[:50]
    return {"rebuilt_at": now.isoformat(timespec="seconds"),
            "authors": dict(sorted(authors.items(),
                                   key=lambda kv: -kv[1]["scores"]["independent_evidence"])[:500])}


def write_funnel(reg: dict) -> None:
    """The subsystem's supreme-metric diagnostics (principal 2026-08-26): validated
    incremental E[log W] per unit of hunting capacity, decomposed into its funnel. Counted
    from artifacts on disk, never from reports."""
    shortlist = _read(INTEL / "survivor_shortlist.json", {}).get("shortlist", [])
    # STREAMED, NOT PARSED WHOLE. This read cost 191MB of peak RSS to answer a question about
    # a prefix -- measured 2026-09-06 at 47,150 rows -- and it is one of eight sites that did the
    # same thing on an 8GB box. `iter_rows` yields one row at a time and falls back to the legacy
    # JSON when the JSONL is absent, so this is correct on a half-migrated tree.
    from research.queue_store import iter_rows
    ext_cards = [c for c in iter_rows() if str(c.get("id", "")).startswith("ext-")]
    surv = _read(BASE / "data" / "hypotheses" / "external_survivors.json", [])
    surv_n = len(surv if isinstance(surv, list) else surv.get("survivors", []))
    certs = _read(BASE / "reports" / "UNIVERSAL_SURVIVORS.json", {})
    funnel = {
        "updated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "supreme_metric": "validated incremental E[log W] per unit of survivor-hunting "
                          "capacity -- everything below is diagnostic, never the objective",
        "cohort_registry": len(reg),
        "cohort_alive": sum(1 for m in reg.values() if m.get("status") == "ALIVE"),
        "cohort_dead": sum(1 for m in reg.values() if m.get("status") == "DEAD"),
        "credible_shortlist": len(shortlist),
        "external_stageA_survivors": surv_n,
        "promoted_to_gauntlet_queue": len(ext_cards),
        "exact_certificates": len(certs.get("survivors", {})),
        "frozen_clones": 0,          # clone-spec stage not built yet -- honest zero
        "forward_clone_match_rate": None,
        "fusion_forward_survivors": None,
    }
    (INTEL / "survivor_funnel.json").write_text(json.dumps(funnel, indent=1), "utf-8")


def run_and_save() -> dict:
    COHORTS.mkdir(parents=True, exist_ok=True)
    reg = _read(REGISTRY, {})
    added = enroll_new(reg)
    checked = observe_due(reg)
    write_funnel(reg)
    REGISTRY.write_text(json.dumps(reg, indent=0, default=str), "utf-8")
    graph = rebuild_identity_graph(reg)
    GRAPH.write_text(json.dumps(graph, indent=1), "utf-8")
    alive = sum(1 for m in reg.values() if m.get("status") == "ALIVE")
    dead = sum(1 for m in reg.values() if m.get("status") == "DEAD")
    print(f"cohorts: +{added} enrolled, {checked} observed | registry {len(reg)} "
          f"(alive={alive} dead={dead}) | identity graph {len(graph['authors'])} authors")
    return {"enrolled": added, "observed": checked, "registry": len(reg),
            "authors": len(graph["authors"])}


if __name__ == "__main__":
    run_and_save()
