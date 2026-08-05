"""Hunt replacements for sources the health ledger has called DEAD.

THE PRINCIPLE THIS IMPLEMENTS, in the principal's words: "if something isn't working, a source at
all, then alternative sources must be explored and hunted." Until this script existed the desk did
the first half only. libs/data/cn_sources.probe_all() and scripts/mine_research_queue.probe_cn()
measure every source honestly and write down exactly why each one fails -- and then nothing
happens. A source could be blocked for six weeks, be re-probed daily, report the identical 403
daily, and no substitute was ever looked for. Noticing death without acting on it is a diary, not
a desk.

WHAT IT DOES. Reads data/source_health.jsonl (written by the miner through
libs/research/source_health.record_from_report), takes every DEAD source, probes the substitutes
libs/research/source_alternatives registers for it IN THE SAME INFORMATION CLASS, and writes
data/source_alternatives_report.json naming which ones actually answered and what parser work each
clean one now needs.

THREE THINGS IT REFUSES TO DO.

  * It never invents a working source. A candidate that has not been probed is UNVERIFIED and
    says so; a probe that fails records its reason exactly like every other probe on this desk.
  * It never calls a 200-OK anti-bot shell a working source. Baidu answers every request and
    serves 1.4KB of JavaScript; that is SHELL, its own status, because filing it as REACHABLE
    would hand the desk a "replacement" that returns nothing.
  * It never claims a candidate is unusable when it could not fairly test it. Candidates whose
    whole premise is the VPS's unproxied egress cannot be settled from inside this container, so
    they stay UNVERIFIED with that reason -- probing them through the proxy answers a different
    question.

EXIT: 2 when a DEAD source has NO registered alternatives at all (a real gap in the registry, and
the one condition a human must fix by hand); 0 otherwise, including the honest idle state where
nothing is dead and there is nothing to hunt.

    python3 scripts/hunt_source_alternatives.py [--all] [--source NAME] [--timeout SECS]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research import source_alternatives as alt
from libs.research import source_health as health

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "source_alternatives_report.json"

_UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
       "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.8",
       "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"}

#: Markers that mean "you were served a challenge, not the page you asked for". A large body is
#: not proof of content -- some challenge pages are fat -- so these are checked independently of
#: the byte threshold. Every one of these has actually been seen by this desk's own probes.
_CHALLENGE_MARKERS = ("antispider", "请输入验证码", "验证码", "captcha", "just a moment",
                      "security check", "访问验证", "滑动验证")


def _classify_body(raw: bytes, ctype: str) -> tuple[str, str]:
    """(status, detail) for a body that actually came back. Pure, so it is testable without a
    network -- the classification rules are where the judgement lives, not the socket.

    JSON AND HTML ARE JUDGED DIFFERENTLY, and that distinction is load-bearing. A byte threshold
    is the right test for a search-results PAGE (Baidu's shell is 1.4KB, real results are 100KB+)
    and completely wrong for an API, where five parsed results can be 3KB of perfectly good JSON.
    Applying the page rule to an endpoint would file every working API on this list as a shell.
    """
    body = raw.decode("utf8", errors="ignore")
    n = len(raw)
    low = body[:4000].lower()
    hit = next((m for m in _CHALLENGE_MARKERS if m in low), None)
    if hit is not None:
        return alt.STATUS_SHELL, f"{n} bytes but carries a challenge marker ({hit!r})"

    stripped = body.lstrip()
    if "json" in ctype.lower() or stripped[:1] in ("{", "["):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            return alt.STATUS_SHELL, f"{n} bytes, declared JSON but unparseable: {exc}"
        shape = (f"{len(parsed)} top-level keys" if isinstance(parsed, dict)
                 else f"{len(parsed)} elements" if isinstance(parsed, list) else "scalar")
        if isinstance(parsed, dict | list) and len(parsed) == 0:
            # An endpoint that answers `[]` is up and is not carrying anything. Filing it as
            # REACHABLE would emit a NEXT ACTION telling someone to write a parser against a
            # source that returned nothing -- measured live 2026-08-05 on Gitee's v5 search,
            # which answered 200 with a 2-byte empty array.
            return alt.STATUS_SHELL, (f"JSON, {n} bytes, {shape} -- the endpoint answered but "
                                      "returned an EMPTY result set for this query")
        return alt.STATUS_REACHABLE, f"JSON, {n} bytes, {shape}"

    if n < alt.CONTENT_BYTES:
        return alt.STATUS_SHELL, (f"{n} bytes -- under the {alt.CONTENT_BYTES}-byte content bar; "
                                  "a page this small is a shell/redirect, not results")
    return alt.STATUS_REACHABLE, f"HTML, {n} bytes"


def probe(url: str, *, timeout: float = 25.0) -> tuple[str, str]:
    """(status, detail) for one candidate URL. Never raises: a probe failure IS the measurement,
    recorded with its reason exactly like every other probe on this desk."""
    # All registry URLs are https literals declared in libs/research/source_alternatives.
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            raw = fh.read()
            ctype = str(fh.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        return alt.STATUS_FAILED, f"HTTP {exc.code} {exc.reason}"
    except Exception as exc:
        return alt.STATUS_FAILED, f"{type(exc).__name__}: {str(exc)[:140]}"
    return _classify_body(raw, ctype)


def hunt_one(entry: alt.Replacements, state: health.SourceState, *, timeout: float,
             vantage: str, states: dict[str, health.SourceState] | None = None,
             sleep: float = 0.4) -> dict[str, Any]:
    """Probe every candidate for one dead source and build its report block.

    ``states`` is the SAME ledger snapshot the caller read, threaded explicitly rather than
    re-loaded from the default path -- otherwise a test (or any caller pointing --ledger
    elsewhere) would silently mix a tmp ledger with the desk's real one.
    """
    known = {} if states is None else states
    rows: list[dict[str, Any]] = []
    actions: list[str] = []
    for cand in entry.candidates:
        if cand.in_tree is not None:
            # ALREADY BUILT AND ALREADY RUNNING HERE. Its health is measured by the miner every
            # day and lives in the ledger; re-probing it from this script would produce a second,
            # weaker reading of a source the desk already reads properly.
            key = health.canonical(cand.ledger_key
                                   if cand.ledger_key is not None else cand.name)
            built = known.get(key, health.SourceState(source=key))
            detail = (f"already implemented at {cand.in_tree}; ledger verdict for "
                      f"'{key}' is {built.verdict}")
            status = (alt.STATUS_REACHABLE if built.verdict == health.VERDICT_HEALTHY
                      else alt.STATUS_UNVERIFIED)
            if built.verdict == health.VERDICT_UNKNOWN:
                detail += " (never probed -- UNKNOWN, not a failure)"
            rows.append(alt.candidate_to_row(alt.probed(cand, status=status, detail=detail)))
            if status == alt.STATUS_REACHABLE:
                actions.append(f"[{entry.source} -> {cand.name}] {cand.next_action}")
            continue

        if cand.verify_from != "any" and cand.verify_from != vantage:
            detail = (f"cannot be settled from this vantage ({vantage}); this candidate is a "
                      f"claim about {cand.verify_from} and only that box can test it")
            rows.append(alt.candidate_to_row(
                alt.probed(cand, status=alt.STATUS_UNVERIFIED, detail=detail)))
            continue

        status, detail = probe(cand.url, timeout=timeout)
        rows.append(alt.candidate_to_row(alt.probed(cand, status=status, detail=detail)))
        if status == alt.STATUS_REACHABLE:
            actions.append(f"[{entry.source} -> {cand.name}] {cand.next_action}")
        time.sleep(sleep)

    return {
        "source": entry.source,
        "information_class": entry.information_class,
        "recorded_reason": entry.recorded_reason,
        "health": {
            "verdict": state.verdict,
            "scope": state.scope,
            "claim": state.claim(),
            "consecutive_failed_runs": state.consecutive_failed_runs,
            "last_ok_utc": state.last_ok_utc,
            "last_error": state.last_error,
        },
        "candidates": rows,
        "n_reachable": sum(1 for r in rows if r["status"] == alt.STATUS_REACHABLE),
        "n_unverified": sum(1 for r in rows if r["status"] == alt.STATUS_UNVERIFIED),
        "next_actions": actions,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true",
                    help="probe alternatives for EVERY registered source, not only DEAD ones "
                         "(how you seed the report before the ledger has any history)")
    ap.add_argument("--source", default="", metavar="NAME",
                    help="restrict to one registered source")
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--ledger", default="", help="health ledger path (tests point this at tmp)")
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    ledger = Path(args.ledger) if args.ledger else None
    states = health.load_states(ledger)
    vantage = health.current_vantage()

    dead = {s.source for s in health.dead_sources(ledger)}
    registered = {e.source for e in alt.registry()}
    # A DEAD source the registry has never heard of is the one thing this script cannot fix by
    # running: someone has to decide what carries the same information. Named, never swallowed.
    unregistered = sorted(dead - registered)

    if args.source:
        wanted = [args.source] if args.source in registered else []
        if not wanted:
            ap.error(f"{args.source!r} is not a registered source; "
                     f"known: {sorted(registered)}")
    elif args.all:
        wanted = sorted(registered)
    else:
        wanted = sorted(dead & registered)

    hunted: list[dict[str, Any]] = []
    for name in wanted:
        entry = alt.alternatives_for(name)
        if entry is None:
            continue
        state = states.get(health.canonical(name), health.SourceState(source=name))
        hunted.append(hunt_one(entry, state, timeout=args.timeout, vantage=vantage,
                               states=states))

    actions = [a for block in hunted for a in block["next_actions"]]
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "vantage": vantage,
        "vantage_note": ("this container reaches the internet through an egress proxy and the VPS "
                         "does not, so a probe result here is a fact about THIS BOX; a candidate "
                         "that fails here may be fine there and vice versa"),
        "dead_after_consecutive_failures": health.DEAD_AFTER_CONSECUTIVE_FAILURES,
        "mode": ("single-source" if args.source else
                 "all-registered" if args.all else "dead-only"),
        "dead_sources": sorted(dead),
        "dead_without_registered_alternatives": unregistered,
        "registry": alt.summary(),
        "hunted": hunted,
        "next_actions": actions,
    }
    if not dead and not (args.all or args.source):
        # The honest idle state, stated rather than implied by an empty file.
        doc["note"] = ("NO DEAD SOURCES in the health ledger -- nothing to hunt. This is a "
                       "result, not a failure; the ledger is at "
                       f"{(ledger or health.LEDGER_PATH)} and carries {len(states)} source(s).")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")

    print(f"source-alternatives hunt | vantage={vantage} | mode={doc['mode']} | "
          f"{len(dead)} dead, {len(hunted)} source(s) hunted")
    for block in hunted:
        h = block["health"]
        print(f"  {block['source']:<20} {h['verdict']:<9} class={block['information_class']}")
        for row in block["candidates"]:
            flags = "".join(c for c, on in (("A", row["needs_auth"]), ("J", row["needs_js"]),
                                            ("B", row["needs_browser"])) if on) or "-"
            print(f"      {row['status']:<11} {row['name']:<28} [{flags}] {row['probe_detail']}")
    for a in actions:
        print(f"  NEXT ACTION {a}")
    for u in unregistered:
        print(f"  REGISTRY GAP {u} is DEAD with no registered alternatives -- "
              f"name an in-class substitute in libs/research/source_alternatives.py")
    print(f"wrote {out}")
    return 2 if unregistered else 0


if __name__ == "__main__":
    raise SystemExit(main())
