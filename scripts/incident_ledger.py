"""THE INCIDENT LEDGER: every incident the desk's own monitors saw, when it was detected, how
long detection could have lagged (MTTD), how long it took to resolve (MTTR), what cleared it and
whether a person had to act. Hourly pass ideas 626 (incidents) and 622 (the release-train
freeze ledger, which is the `merge_train` source here).

    python scripts/incident_ledger.py [--print]

WHY. On the night of 11-10/11-11 incidents ran from 30 min to 26 h (an expired box login, a
jammed gate clone, a ROOT pin, a hung docket, a starved gold runner) and the only record was
chat. Nobody could say how fast the desk notices, how fast it recovers, or how much of that
needed zuck -- the numbers the autonomy work exists to drive down.

SOURCES (each read from a report another organ already writes; an absent report is listed under
`unmeasured`, never read as healthy):
    merge_train        reports/MERGE_FLOW.json   verdict RED/GREEN, reasons, heal   (idea 622)
    slo:<service>      reports/SLO_STATUS.json   `breaching_now`
    desk:<finding>     reports/DESK_HEALTH.json  each PROBLEM finding, keyed by its section and
                                                 the first words of its message

THE LEDGER (desks/mt5/data/incident_ledger.jsonl) is append-only; open incidents are found by
replaying it, so a crash between runs loses nothing:
    {"event": "open",  "id", "source", "at", "causes", "last_ok"}    last_ok: the last time this
                                                                     source was seen healthy
    {"event": "cause", "id", "source", "at", "causes"}
    {"event": "heal",  "id", "source", "at", "action"}
    {"event": "close", "id", "source", "at", "minutes", "mttd_min", "mttr_min", "causes_seen",
     "cleared_by", "human_needed"}

MTTD is an UPPER BOUND: detected `at` minus `last_ok` (the incident began somewhere in between);
MTTR is resolved minus `last_ok` (also an upper bound), `minutes` is resolved minus detected.
With no healthy sighting on record both are null, never guessed. `human_needed` is true when a
cause seen is one only a person can clear by design (HUMAN_ONLY). `cleared_by` is "self_heal"
when a heal ran inside the incident within HEAL_CREDIT of its end, "human" when human_needed,
else "unattributed".

It reads reports and writes only its ledger, its small last-ok state and INCIDENTS.json. It
never touches GitHub, a task, a gate or a trade.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
LEDGER = DESK / "data" / "incident_ledger.jsonl"
STATE = DESK / "data" / "incident_state.json"
REPORT = DESK / "reports" / "INCIDENTS.json"
MERGE_FLOW = DESK / "reports" / "MERGE_FLOW.json"
SLO_STATUS = DESK / "reports" / "SLO_STATUS.json"
DESK_HEALTH = DESK / "reports" / "DESK_HEALTH.json"
SCHEMA = "incident_ledger/1"
MERGE_TRAIN = "merge_train"

#: Causes that, by design, only a person can clear (a GitHub login, a ROOT re-pin).
HUMAN_ONLY = frozenset({"BOX_LOGIN", "ROOT_PIN"})
#: A heal gets the credit for a resolution that lands within this long after it.
HEAL_CREDIT = timedelta(hours=2)
DAYS = 7
#: A report older than this is not read as current: its source is listed unmeasured.
STALE_H = 3.0


def _ts(s: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _min(a: datetime | None, b: datetime | None) -> float | None:
    return None if a is None or b is None else round((b - a).total_seconds() / 60.0, 1)


def read_rows(lines: Iterable[str]) -> list[dict[str, Any]]:
    out = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if (
            isinstance(r, dict)
            and r.get("event") in ("open", "cause", "heal", "close")
            and r.get("source")
        ):
            out.append(r)
    return out


def open_incidents(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """source -> its open incident {id, at, last_ok, causes, causes_seen, heals}."""
    cur: dict[str, dict[str, Any]] = {}
    for r in rows:
        src, ev = str(r["source"]), r["event"]
        if ev == "open":
            cur[src] = {"id": r.get("id"), "at": r.get("at"), "last_ok": r.get("last_ok"),
                        "causes": list(r.get("causes") or []),
                        "causes_seen": list(r.get("causes") or []), "heals": []}  # fmt: skip
            continue
        c = cur.get(src)
        if c is None or r.get("id") != c["id"]:
            continue
        if ev == "cause":
            c["causes"] = list(r.get("causes") or [])
            c["causes_seen"] += [x for x in c["causes"] if x not in c["causes_seen"]]
        elif ev == "heal":
            c["heals"].append({"at": r.get("at"), "action": r.get("action")})
        elif ev == "close":
            del cur[src]
    return cur


def step(
    rows: Sequence[Mapping[str, Any]],
    now: datetime,
    observed: Mapping[str, Sequence[str]],
    healthy: Iterable[str],
    last_ok: Mapping[str, str],
    heals: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Rows to append for one observation (pure). `observed`: source -> causes, for every source
    that is RED now. `healthy`: sources measured healthy now. A source in neither was not
    measured this run and is left exactly as it was."""
    heals = heals or {}
    at = now.isoformat()
    cur = open_incidents(rows)
    new: list[dict[str, Any]] = []
    for src in sorted(observed):
        causes = sorted(set(observed[src]))
        c = cur.get(src)
        if c is None:
            iid = f"I-{now.strftime('%Y%m%dT%H%M%SZ')}-{re.sub(r'[^A-Za-z0-9]+', '_', src)[:40]}"
            new.append({"event": "open", "id": iid, "source": src, "at": at, "causes": causes,
                        "last_ok": last_ok.get(src), "schema": SCHEMA})  # fmt: skip
        else:
            iid = c["id"]
            if sorted(c["causes"]) != causes:
                new.append({"event": "cause", "id": iid, "source": src, "at": at,
                            "causes": causes})  # fmt: skip
        done = [h.get("action") for h in (c or {}).get("heals", [])]
        if heals.get(src) and str(heals[src])[:200] not in done:  # one heal is recorded once
            new.append({"event": "heal", "id": iid, "source": src, "at": at,
                        "action": str(heals[src])[:200]})  # fmt: skip
    for src in sorted(set(healthy) - set(observed)):
        c = cur.get(src)
        if c is None:
            continue
        detected, ok = _ts(c["at"]), _ts(c.get("last_ok"))
        seen = sorted(set(c["causes_seen"]))
        human = bool(HUMAN_ONLY.intersection(seen))
        heal_ts = [t for h in c["heals"] if (t := _ts(h["at"])) is not None]
        if heal_ts and now - max(heal_ts) <= HEAL_CREDIT:
            cleared = "self_heal"
        elif human:
            cleared = "human"
        else:
            cleared = "unattributed"
        new.append({
            "event": "close", "id": c["id"], "source": src, "at": at,
            "minutes": _min(detected, now), "mttd_min": _min(ok, detected),
            "mttr_min": _min(ok, now), "causes_seen": seen, "cleared_by": cleared,
            "human_needed": human,
        })  # fmt: skip
    return new


def _q(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1)


def summary(rows: Sequence[Mapping[str, Any]], now: datetime) -> dict[str, Any]:
    since = now - timedelta(days=DAYS)
    opens = {str(r.get("id")): r for r in rows if r["event"] == "open"}
    closes = [r for r in rows if r["event"] == "close" and (_ts(r.get("at")) or now) >= since]
    cur = open_incidents(rows)
    mttd = [float(r["mttd_min"]) for r in closes if r.get("mttd_min") is not None]
    mttr = [float(r["mttr_min"]) for r in closes if r.get("mttr_min") is not None]
    # THE FREEZE VIEW (idea 622): release-train minutes frozen per UTC day, intervals split at
    # midnight, the open one counted to now.
    ivs = []
    for r in rows:
        if r["event"] == "close" and r["source"] == MERGE_TRAIN and str(r.get("id")) in opens:
            ivs.append((_ts(opens[str(r["id"])].get("at")), _ts(r.get("at"))))
    if MERGE_TRAIN in cur:
        ivs.append((_ts(cur[MERGE_TRAIN]["at"]), now))
    today = now.date()
    per_day: dict[str, float] = {}
    for k in range(DAYS - 1, -1, -1):
        d = today - timedelta(days=k)
        lo = datetime(d.year, d.month, d.day, tzinfo=UTC)
        hi = min(lo + timedelta(days=1), now)
        tot = sum(max(0.0, (min(b, hi) - max(a, lo)).total_seconds() / 60.0)
                  for a, b in ivs if a is not None and b is not None)  # fmt: skip
        per_day[d.isoformat()] = round(tot, 1)
    return {
        "schema": SCHEMA, "at": now.isoformat(), "days": DAYS,
        "open": [{"source": s, "id": c["id"], "since": c["at"], "causes": c["causes"],
                  "human_needed": bool(HUMAN_ONLY.intersection(c["causes_seen"]))}
                 for s, c in sorted(cur.items())],
        "closed_7d": len(closes),
        "mttd_min": {"median": round(statistics.median(mttd), 1) if mttd else None,
                     "p90": _q(mttd, 0.9), "n": len(mttd)},
        "mttr_min": {"median": round(statistics.median(mttr), 1) if mttr else None,
                     "p90": _q(mttr, 0.9), "n": len(mttr)},
        "human_needed_7d": sum(1 for r in closes if r.get("human_needed")),
        "self_healed_7d": sum(1 for r in closes if r.get("cleared_by") == "self_heal"),
        "merge_train_frozen_min_per_day": per_day,
        "human_only_causes": sorted(HUMAN_ONLY),
    }  # fmt: skip


# ----------------------------------------------------------------------------- the box side


def _load(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _fresh(doc: Mapping[str, Any] | None, key: str, now: datetime) -> bool:
    t = _ts((doc or {}).get(key))
    return t is not None and (now - t).total_seconds() / 3600.0 <= STALE_H


def _finding_key(f: Mapping[str, Any]) -> str:
    section = str(f.get("section") or "").split("(")[0].strip().lower()
    # timestamps, counts and AM/PM change between runs; the names around them do not
    words = [w.strip(".,;:()") for w in str(f.get("message") or "").split()]
    words = [w for w in words if w and not re.fullmatch(r"[\d/:.,%-]+|AM|PM|-?\d+\w{0,2}", w)][:4]
    return f"desk:{section}:{' '.join(words)}".strip()


def observe_reports(now: datetime) -> tuple[dict[str, list[str]], set[str], dict[str, str],
                                             list[str]]:  # fmt: skip
    """(red source -> causes, healthy sources, heals, unmeasured report names)."""
    red: dict[str, list[str]] = {}
    ok: set[str] = set()
    heals: dict[str, str] = {}
    unmeasured: list[str] = []
    mf = _load(MERGE_FLOW)
    if _fresh(mf, "at", now) and (mf or {}).get("verdict") in ("RED", "GREEN"):
        if mf["verdict"] == "RED":
            red[MERGE_TRAIN] = [str(x) for x in mf.get("reasons") or []] or ["RED"]
            if mf.get("heal"):
                heals[MERGE_TRAIN] = f"{mf.get('at')}: {mf['heal']}"  # the report's time keys it
        else:
            ok.add(MERGE_TRAIN)
    else:
        unmeasured.append("MERGE_FLOW.json")
    slo = _load(SLO_STATUS)
    if _fresh(slo, "at", now) and isinstance((slo or {}).get("services"), dict):
        bad = {str(x) for x in slo.get("breaching_now") or []}
        for name in slo["services"]:
            (red.setdefault(f"slo:{name}", ["BREACHING"]) if name in bad else ok.add(f"slo:{name}"))
    else:
        unmeasured.append("SLO_STATUS.json")
    dh = _load(DESK_HEALTH)
    if _fresh(dh, "checked_at", now) and isinstance((dh or {}).get("findings"), list):
        for f in dh["findings"]:
            if not isinstance(f, dict):
                continue
            key = _finding_key(f)
            if f.get("level") == "PROBLEM":
                red[key] = ["PROBLEM"]
            elif f.get("level") == "OK":
                ok.add(key)
        # a finding that stopped being reported at all is healthy again: close what it opened
        ok |= {s for s in open_incidents(read_rows(_lines(LEDGER))) if s.startswith("desk:")}
    else:
        unmeasured.append("DESK_HEALTH.json")
    return red, ok, heals, unmeasured


def _lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _write_json(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def run(now: datetime) -> dict[str, Any]:
    rows = read_rows(_lines(LEDGER))
    red, ok, heals, unmeasured = observe_reports(now)
    state = _load(STATE) or {}
    last_ok = {str(k): str(v) for k, v in (state.get("last_ok") or {}).items()}
    new = step(rows, now, red, ok, last_ok, heals)
    if new:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8", newline="\n") as f:
            f.write("".join(json.dumps(r, sort_keys=True) + "\n" for r in new))
    for s in ok - set(red):
        last_ok[s] = now.isoformat()
    _write_json(STATE, {"last_ok": last_ok})
    doc = summary(rows + new, now)
    doc["unmeasured"] = unmeasured
    doc["appended"] = len(new)
    _write_json(REPORT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--print", action="store_true", help="summary of the ledger only; write nothing"
    )
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    if a.print:
        print(json.dumps(summary(read_rows(_lines(LEDGER)), now), indent=1))
        return 0
    doc = run(now)
    print(f"incident_ledger: {len(doc['open'])} open, {doc['closed_7d']} closed in 7 d, "
          f"MTTD median {doc['mttd_min']['median']} min, MTTR median "
          f"{doc['mttr_min']['median']} min; unmeasured {doc['unmeasured']}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
