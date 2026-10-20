"""The desk's PAGER -- push critical alerts to the principal's phone via ntfy.sh (free, keyless).

Silent failure is the one failure mode a self-healing system can't fix: if the kill switch fires,
the heartbeat dies, or a conservatism defect sits unresolved while nobody is looking, the dashboard
knows and the principal doesn't. This closes that gap. Runs each watchdog tick (cheap, feed-only);
only CRITICAL conditions page, each deduped to once per 6h so it never becomes noise (a pager that
cries wolf is worse than none).

Subscribe once: install the ntfy app (or open the URL in any browser) and subscribe to the topic
printed on first run (stored in data/secrets/ntfy.json -- random suffix, treat like a password;
messages carry NO account data, only alert names).

    python scripts/run_alerts.py [--test]
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from libs.ops.fresh import stamp_age_h

# alerts that a brain cycle can actually REMEDIATE (auto-heal event trigger). Deliberately
# EXCLUDES growth_defect/data_health (slow/justified -- would loop the brain forever) and
# deadman_latched/kill/principal_action (human-only -- the brain cannot resolve them).
_EVENT_TRIGGER = {"cadence_floor_violation", "root_cause_critical", "recorder_stale"}

_SECRETS = Path("data/secrets/ntfy.json")
_STATE = Path("data/.last_alerts.json")
_DEDUPE_S = 6 * 3600
# per-key dedupe overrides (2026-07-17 principal: pager spam is noise; a pager that cries
# wolf is worse than none). Slow-moving conditions remind daily, not 4x/day. deadman_latched
# stays at 6h deliberately -- a latched ruin rail SHOULD nag until the operator acts.
_DEDUPE_OVERRIDES_S = {"growth_defect": 24 * 3600, "data_health": 24 * 3600,
                       "brain_noop": 24 * 3600, "principal_action_needed": 24 * 3600,
                       "trade_class_bleeding": 24 * 3600, "auth_broken": 12 * 3600,
                       # the chain runs once a day; its failures can only change once a day
                       "research_chain_failed": 24 * 3600}

# PLUMBING + JUDGE STALL (2026-10-20). The plumbing watchdog escalated into three places a human
# meets only by LOOKING (desk state, the events log, docs/research/PLUMBING_ALERTS.md), and the
# judge's rate meter (JUDGING_RATE.json) recorded a judge with zero verdicts for days -- and
# this pager read neither, so a stalled judge paged no one. Both are read here now.
#: The watchdog's full report (box-local: gitignored, so absent on the VPS) and its published
#: escalation page (tracked, so it reaches the VPS). Whichever is newer and readable is used.
_PLUMBING_JSON = Path("desks/mt5/reports/PLUMBING_WATCHDOG.json")
_PLUMBING_MD = Path("docs/research/PLUMBING_ALERTS.md")
#: verdicts/hour from the judge's own ledger (desks/mt5/research/judging_throughput.py).
_JUDGING_RATE = Path("desks/mt5/reports/JUDGING_RATE.json")
#: No new verdict for this long is a STALLED judge. The judge runs on a minutes cadence, so six
#: hours of silence is a stop, not a slow hour.
JUDGE_STALL_H = 6.0
#: The watchdog runs every 15 min; a report older than this means the watchdog itself stopped
#: (or stopped being published), which is UNMEASURED plumbing -- never a quiet pass.
PLUMBING_MAX_AGE_H = 3.0
#: Re-page every REPAGE_H while still failing (box_heartbeat's convention): these are stops,
#: and a stop should nag until someone repairs it.
REPAGE_H = 2.0
#: A stamp up to this far in the future is clock skew between writer and reader, not a defect
#: (the same allowance the judge_throughput producer uses).
CLOCK_SKEW_H = 0.25
#: The severities the watchdog emits. Anything else -- a mangled cell, a new word -- is
#: UNMEASURED and pages as such; an unknown severity may never be read as "not CRITICAL".
KNOWN_SEVERITIES = frozenset({"CRITICAL", "MAJOR"})
_PLUMBING_KEYS = ("plumbing_critical", "plumbing_unmeasured", "judge_throughput_critical",
                  "judge_throughput_unmeasured", "judge_stalled", "judge_rate_unmeasured")
_DEDUPE_OVERRIDES_S.update(dict.fromkeys(_PLUMBING_KEYS, int(REPAGE_H * 3600)))
_HB = Path("data/cashcarry_exec_heartbeat")
_PAGER_BACKOFF = Path("data/.pager_backoff")
_KILL = Path("data/CASHCARRY_KILL")
_ERR = Path("data/cashcarry_error.log")


def _topic() -> str:
    if _SECRETS.exists():
        return str(json.loads(_SECRETS.read_text("utf-8"))["topic"])
    topic = f"quant-desk-{secrets.token_hex(6)}"
    _SECRETS.parent.mkdir(parents=True, exist_ok=True)
    _SECRETS.write_text(json.dumps({"topic": topic}), "utf-8")
    # The topic IS the credential: never echo it into a log. Read it from the file to subscribe.
    print(f"NEW pager topic created -> stored in {_SECRETS} (read it there to subscribe)")
    return topic


def _read_topic(paths: tuple[Path, ...]) -> str | None:
    """The EXISTING topic, or None. Never mints one and never prints one (box path)."""
    for p in paths:
        try:
            topic = json.loads(p.read_text("utf-8-sig")).get("topic")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
    return None


def _push(topic: str, title: str, body: str) -> None:
    # HTTP headers must be latin-1 (urllib/http.client encode them that way); a title with an
    # emoji or other non-latin-1 char raises UnicodeEncodeError BEFORE the request is ever sent,
    # silently killing this and every future push (2026-07-19: broke ALL paging for 29h+,
    # including a live dead-man fire, because the resolved title carried a raw "⚠️").
    # ntfy already renders an icon from Tags, so titles stay plain ASCII; this encode is a
    # defense-in-depth backstop against the same class recurring via a future non-ASCII edit.
    safe_title = title.encode("latin-1", "ignore").decode("latin-1")
    # 429 backoff (2026-07-20): ntfy rate-limits the topic; a due re-page retried on
    # every 3-min tick keeps the topic throttled forever (observed self-DoS loop,
    # journalctl 06:47Z). After any 429, cool down 1h before the next push attempt.
    import time as _t
    if _PAGER_BACKOFF.exists():
        try:
            _until = float(_PAGER_BACKOFF.read_text().strip())
        except ValueError:
            _until = 0.0
        if _t.time() < _until:
            raise RuntimeError(f"pager 429 backoff: {(_until - _t.time()) / 60:.0f}m remaining")
    # second-channel mirror (gap #38): fire the independent path FIRST so a failure in
    # the ntfy path (encoding, 429, outage) can never suppress the alert entirely.
    _second_channel(f"{safe_title}: {body}")
    # ...and every configured channel in the registry (telegram/webhook/email), each independently
    # wrapped so none can raise into this path. 2026-07-29: this is the half gap #38 was still
    # missing -- not another channel, but a DELIVERY LEDGER, so "nothing arrived anywhere" becomes
    # observable instead of being the thing nobody notices for five days.
    with contextlib.suppress(Exception):
        from libs.ops.alert_channels import send_all
        send_all(safe_title, body)
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                 headers={"Title": safe_title, "Priority": "high",
                                          "Tags": "rotating_light"})
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
        if _PAGER_BACKOFF.exists():
            _PAGER_BACKOFF.unlink()
        _ledger_ok("ntfy", "http 200", safe_title)
    except Exception as e:
        if getattr(e, "code", None) == 429:
            _PAGER_BACKOFF.write_text(str(_t.time() + 3600))
        _ledger_ok("ntfy", f"{type(e).__name__}: {e}", safe_title, ok=False)
        raise


def _ledger_ok(channel: str, detail: str, title: str, *, ok: bool = True) -> None:
    """Record the PRIMARY path's outcome in the same ledger as the registry channels, so the
    silence check sees one unified view. Never raises -- a logging failure must not kill a page."""
    with contextlib.suppress(Exception):
        from libs.ops.alert_channels import _log
        _log(channel, ok, detail, title)


# --- PRINCIPAL REPLY CHANNEL (2026-07-31) --------------------------------------------------
# Pages have asked for replies ("reply YES/NO", "reply KILL-DIGEST") since 07-18, but nothing
# ever READ the topic, and data/PAGE_ACK -- the derisk ladder's ack input -- had never been
# created by anything: the ladder could latch (it froze the book today) while the principal
# had no phone-usable way to ack or re-arm. The ntfy app can PUBLISH to the topic it
# subscribes to, so replies arrive as TITLELESS messages on the same channel; desk pushes
# always carry a Title (_push sets one), which is the discriminator. REARM here is transport
# for the human's own act, not an automated re-arm: it only ever runs off an explicit
# principal message. Trust boundary = knowledge of the secret topic, identical to the pager
# itself (ledgered limitation; falsifier: any suspected abuse moves this to authed ntfy).
_PAGE_ACK = Path("data/PAGE_ACK")
_REPLIES = Path("data/principal_replies.jsonl")
_REPLY_STATE = Path("data/.reply_poll_state.json")


def _poll_replies(topic: str) -> None:
    """Fail-quiet by design: paging must never break because reply-polling did."""
    try:
        st: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            st = json.loads(_REPLY_STATE.read_text("utf-8"))
        since = str(st.get("last_id") or "24h")
        url = f"https://ntfy.sh/{topic}/json?poll=1&since={since}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            lines = resp.read().decode("utf-8", "replace").splitlines()
        last_id = st.get("last_id")
        for ln in lines:
            try:
                m = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if m.get("event") != "message":
                continue
            last_id = m.get("id") or last_id
            if m.get("title"):                      # desk's own page, not a reply
                continue
            body = str(m.get("message") or "").strip()
            if not body or len(body) > 500:
                continue
            with contextlib.suppress(Exception):
                _REPLIES.parent.mkdir(parents=True, exist_ok=True)
                with _REPLIES.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                         "msg_ts": m.get("time"), "body": body}) + "\n")
            # ANY reply is operator contact: ack the pager (the derisk ladder's input).
            _PAGE_ACK.write_text(
                f"{datetime.now(tz=UTC).isoformat()} {body[:120]}\n", "utf-8")
            cmd = body.split()[0].upper() if body.split() else ""
            # The REARM command was removed 2026-09-05 (universe mandate). It re-armed
            # `scripts/run_live_guard.py` -- the size governor for the retired cash-carry
            # executor -- and lifted `data/CASHCARRY_KILL`. Both the guard and the executor are
            # deleted, so the command could only ever have unlinked a kill file guarding nothing
            # while reporting a successful re-arm to the principal's phone. An operator command
            # that lies about what it did is worse than one that does not exist.
            if cmd == "REARM":
                out = ("REARM is retired: the cash-carry size governor it re-armed was deleted "
                       "with the crypto-exchange universe (2026-09-05). Nothing was changed.")
                with contextlib.suppress(Exception):
                    _push(topic, "Quant desk: REARM received", out)
        if last_id:
            _REPLY_STATE.write_text(
                json.dumps({"last_id": last_id,
                            "polled": datetime.now(tz=UTC).isoformat()}), "utf-8")
    except Exception as exc:
        # LOUD, NOT SILENT (2026-09-23 swallowed-write audit). A reply cursor that fails to write
        # re-delivers every alert next poll, and nothing said why.
        print(f"alerts: reply cursor NOT written ({type(exc).__name__}: {exc})", flush=True)
        return


# --- SILENT-FAILURE DETECTION (2026-07-22) -------------------------------------------------
# All four digger timers fired into quota/auth walls for 2 days and NOTHING noticed: systemd
# reported "success" because the unit ran, while the log said "hit your session limit" and the
# dig produced zero research. systemd-success != work-done. Same window: the `quant` user's
# claude credentials were absent, so every claude organ was dead on arrival.
_DIGGER_LOGS = {"dataaxis": "dataaxis_*.log", "prospector": "prospector_*.log",
                "litminer": "litminer_*.log", "blindrediscovery": "blindrediscovery_*.log"}
_BLOCK_SIGS = ("hit your session limit", "hit your weekly limit", "not logged in",
               "please run /login", "invalid api key", "authentication_error")
_CRED = Path("/home/quant/.claude/.credentials.json")


def _auth_broken() -> bool:
    """Every claude organ (brain + all diggers) runs as `quant`. The legacy credentials file
    was RETIRED 2026-07-19 (auth moved to setup-token/session storage), so the old existence
    check paged false-positives for 12 days and fed the derisk ladder that froze the book on
    2026-07-31. Truthful free check: session storage mtime moves on every authenticated
    request, so 'broken' = no legacy file AND no session activity for >36h (organs run daily,
    so a 36h-quiet desk is genuinely dead-on-arrival, whether auth or otherwise)."""
    if _CRED.exists():
        return False
    for probe in (Path("/home/quant/.claude/history.jsonl"),
                  Path("/home/quant/.claude/projects")):
        try:
            if time.time() - probe.stat().st_mtime < 36 * 3600:
                return False
        except OSError:
            continue
    return True


def _digger_health() -> list[tuple[str, str]]:
    """A dig that FIRED but produced no research is a silent failure, not a success."""
    out: list[tuple[str, str]] = []
    logdir = Path("data/cro_ai_logs")
    for name, pat in _DIGGER_LOGS.items():
        try:
            logs = sorted(logdir.glob(pat), key=lambda p: p.stat().st_mtime)
            if not logs:
                continue
            last = logs[-1]
            age_h = (time.time() - last.stat().st_mtime) / 3600.0
            if age_h > 24 * 10:            # long-idle cadence (e.g. quarterly) -> not a defect
                continue
            txt = last.read_text("utf-8", errors="ignore")[:4000].lower()
            if any(sig in txt for sig in _BLOCK_SIGS):
                out.append((f"digger_blocked_{name}",
                            f"{name} dig FIRED but produced NOTHING (quota/auth block) -- "
                            f"{last.name}; the timer 'succeeded' while doing no research"))
            elif last.stat().st_size < 400:
                out.append((f"digger_noop_{name}",
                            f"{name} dig produced a near-empty log "
                            f"({last.stat().st_size}B) -- likely blocked"))
        except OSError:
            pass
    return out


def _second_channel(text: str) -> None:
    """INDEPENDENT alert path (gap #38). ntfy is a single point of failure -- a header-encoding
    bug killed it silently for 29h across a live dead-man fire. healthchecks.io is already
    configured for the heartbeat; POSTing to its /fail endpoint triggers whatever notification
    the operator set up there, through completely different infrastructure. Best-effort: this
    must NEVER raise into the primary alert path."""
    with contextlib.suppress(Exception):
        hb = json.loads(Path("data/secrets/heartbeat_url.json").read_text("utf-8")).get("url")
        if hb:
            req = urllib.request.Request(hb.rstrip("/") + "/fail",
                                         data=text.encode("utf-8", "ignore")[:900])
            with urllib.request.urlopen(req, timeout=10):
                pass


def _parse_at(raw: object) -> datetime | None:
    """A timezone-aware ISO stamp, or None. A naive stamp is not a time (it cannot be aged)."""
    try:
        t = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else None


def _age_h(now: datetime, at: datetime) -> float:
    """Hours since `at`. Within CLOCK_SKEW_H of the future reads as 0; beyond it, negative."""
    age = (now - at).total_seconds() / 3600
    return 0.0 if -CLOCK_SKEW_H <= age < 0 else age


_MD_GENERATED = re.compile(r"^Generated\s+(\S+)\s+from", re.MULTILINE)
_MD_CELL_SPLIT = re.compile(r"(?<!\\)\|")


def _parse_plumbing_md(text: str) -> dict[str, Any]:
    """PLUMBING_ALERTS.md -> {at, rows}. Only escalated rows are rendered there, so every row
    read is escalated. A page without a `severity` column (older producer) yields rows whose
    severity is UNMEASURED -- reported as such, never assumed MAJOR."""
    m = _MD_GENERATED.search(text)
    rows: list[dict[str, Any]] = []
    header: list[str] | None = None
    for ln in text.splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            header = None if not s else header
            continue
        cells = [c.strip().strip("`").replace("\\|", "|")
                 for c in _MD_CELL_SPLIT.split(s)[1:-1]]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        row = dict(zip(header, cells, strict=False))
        sev = (row.get("severity") or "UNMEASURED").upper()
        evidence = row.get("evidence", "")
        if len(cells) != len(header):
            # an unescaped `|` shifts every cell after it: nothing in the row can be trusted
            sev, evidence = "UNMEASURED", (f"malformed row ({len(cells)} cells, header "
                                           f"{len(header)}): {s[:80]}")
        rows.append({"check": row.get("check", ""), "organ": row.get("organ", ""),
                     "severity": sev, "escalated": True, "evidence": evidence})
    return {"at": _parse_at(m.group(1)) if m else None, "rows": rows}


def _read_plumbing(json_path: Path, md_path: Path) -> dict[str, Any]:
    """The newest READABLE plumbing source: {source, at, rows} or {source: None, why}."""
    cands: list[dict[str, Any]] = []
    whys: list[str] = []
    try:
        doc = json.loads(json_path.read_text("utf-8-sig"))
        if not isinstance(doc, dict) or not isinstance(doc.get("defects"), list):
            raise ValueError("no defects list")
        raw_facts = doc.get("facts")
        facts: dict[str, Any] = raw_facts if isinstance(raw_facts, dict) else {}
        skipped = doc.get("checks_skipped_for_budget")
        ran = doc.get("checks_run")
        cands.append({"source": json_path.name, "at": _parse_at(doc.get("at")),
                      "rows": [r for r in doc["defects"] if isinstance(r, dict)],
                      "has_facts": "judge_throughput" in facts,
                      "judge_facts": facts.get("judge_throughput"),
                      "checks_run": [str(x) for x in ran] if isinstance(ran, list) else [],
                      "skipped": skipped if isinstance(skipped, list) else []})
    except (OSError, ValueError) as exc:
        whys.append(f"{json_path.name} {type(exc).__name__}")
    try:
        md = _parse_plumbing_md(md_path.read_text("utf-8-sig"))
        cands.append({"source": md_path.name, **md})
    except (OSError, ValueError) as exc:
        whys.append(f"{md_path.name} {type(exc).__name__}")
    if not cands:
        return {"source": None, "why": "; ".join(whys)}
    floor = datetime.min.replace(tzinfo=UTC)
    best = max(cands, key=lambda c: c["at"] or floor)
    js = cands[0] if cands[0]["source"] == json_path.name else None
    if js is not None and best is not js:
        # the md carries rows only: the JSON's facts and budget skips must not vanish just
        # because the published page is newer (they are the last measured ones)
        best = {**best, **{k: js[k] for k in ("has_facts", "judge_facts", "checks_run",
                                              "skipped")}}
    return best


def _row_line(r: dict[str, Any]) -> str:
    return f"{str(r.get('organ'))[:40]} ({r.get('check')}): {str(r.get('evidence'))[:70]}"


def _plumbing_checks(now: datetime | None = None, *, json_path: Path = _PLUMBING_JSON,
                     md_path: Path = _PLUMBING_MD) -> list[tuple[str, str]]:
    """CRITICAL escalated plumbing rows, a CRITICAL judge_throughput row on its own key, and an
    UNMEASURED page when the watchdog's output is missing, unreadable, unstamped or stale."""
    t = now or datetime.now(tz=UTC)
    src = _read_plumbing(json_path, md_path)
    if src.get("source") is None:
        return [("plumbing_unmeasured",
                 f"plumbing watchdog output missing/unreadable ({src.get('why')}) -- the desk's "
                 "plumbing is UNMEASURED, not fine; run desks/mt5/research/plumbing_watchdog.py "
                 "--once on the box")]
    out: list[tuple[str, str]] = []
    at = src.get("at")
    age_h = _age_h(t, at) if at else None
    if age_h is None or age_h < 0 or age_h > PLUMBING_MAX_AGE_H:
        seen = "carries no parseable stamp" if age_h is None else (
            "carries a future stamp" if age_h < 0
            else f"is {age_h:.1f}h old (> {PLUMBING_MAX_AGE_H:g}h)")
        out.append(("plumbing_unmeasured",
                     f"plumbing watchdog report {src['source']} {seen} -- the watchdog "
                     "(MT5-PlumbingWatchdog) or its publication stopped; plumbing is UNMEASURED"))
    rows = [r for r in src.get("rows") or []
            if r.get("escalated", True) is not False]
    crit = [r for r in rows if str(r.get("severity")).upper() == "CRITICAL"]
    judge = [r for r in crit if r.get("check") == "judge_throughput"]
    other = [r for r in crit if r.get("check") != "judge_throughput"]
    asof = f" (as of {at.isoformat(timespec='minutes') if at else '?'}, {src['source']})"
    if judge:
        out.append(("judge_throughput_critical",
                    "CRITICAL judge_throughput defect: " + _row_line(judge[0]) + asof))
    if other:
        more = f" +{len(other) - 3} more" if len(other) > 3 else ""
        out.append(("plumbing_critical",
                    f"{len(other)} CRITICAL plumbing defect(s): "
                    + "; ".join(_row_line(r) for r in other[:3]) + more + asof))
    unsev = [r for r in rows if str(r.get("severity")).upper() not in KNOWN_SEVERITIES]
    if unsev:
        out.append(("plumbing_unmeasured",
                    f"{len(unsev)} escalated plumbing defect(s) in {src['source']} carry no "
                    "known severity -- whether any is CRITICAL is UNMEASURED: "
                    + "; ".join(_row_line(r) for r in unsev[:2])))
    skipped = [str(x) for x in src.get("skipped") or []]
    if skipped:
        out.append(("plumbing_unmeasured",
                    f"{len(skipped)} plumbing check(s) skipped for budget, so UNMEASURED this "
                    f"pass: {', '.join(skipped[:5])}"))
    jf = src.get("judge_facts")
    if src.get("has_facts") or "judge_throughput" in (src.get("checks_run") or []):
        # the producer ran the check (18ad03416+): anything but a measured status is a page.
        # A raising check leaves {"error": ...} with no status; a missing key is no reading.
        status = str(jf.get("status") or "").upper() if isinstance(jf, dict) else ""
        if status in ("", "UNMEASURED"):
            why = (str(jf.get("why") or jf.get("error") or "") if isinstance(jf, dict)
                   else "no facts.judge_throughput published")
            out.append(("judge_throughput_unmeasured",
                        f"the watchdog's judge_throughput check is UNMEASURED "
                        f"({status or 'no status'}): {why[:120]}{asof}"))
    # one key may only page once per tick: merge duplicate keys' messages
    merged: dict[str, str] = {}
    for k, msg in out:
        merged[k] = f"{merged[k]} | {msg}" if k in merged else msg
    return list(merged.items())


def _judge_checks(now: datetime | None = None, *,
                  rate_path: Path = _JUDGING_RATE) -> list[tuple[str, str]]:
    """A STALLED judge (no new verdict in JUDGE_STALL_H), read straight from JUDGING_RATE.json's
    own last_verdict_at and stamp. A rate meter that cannot be read is UNMEASURED, never 'fine'."""
    t = now or datetime.now(tz=UTC)
    try:
        doc = json.loads(rate_path.read_text("utf-8-sig"))
        if not isinstance(doc, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as exc:
        return [("judge_rate_unmeasured",
                 f"{rate_path.name} missing/unreadable ({type(exc).__name__}) -- whether the "
                 "judge is producing verdicts is UNMEASURED")]
    at = _parse_at(doc.get("at"))
    meter_age = _age_h(t, at) if at else None
    meter = (f"rate meter {meter_age:.1f}h old" if meter_age is not None
             else "rate meter unstamped")
    raw_ver = doc.get("verdicts")
    ver: dict[str, Any] = raw_ver if isinstance(raw_ver, dict) else {}
    if ver.get("status") != "MEASURED":
        return [("judge_rate_unmeasured",
                 f"{rate_path.name} verdicts {ver.get('status') or 'absent'}: "
                 f"{str(ver.get('why') or '')[:100]} -- judge liveness is UNMEASURED ({meter})")]
    last = _parse_at(ver.get("last_verdict_at"))
    if last is None:
        if ver.get("last_verdict_at") is None and not ver.get("rows_total"):
            return [("judge_stalled", f"the judge's ledger holds NO verdict at all ({meter})")]
        return [("judge_rate_unmeasured",
                 f"{rate_path.name} last_verdict_at unparseable -- judge liveness is "
                 f"UNMEASURED ({meter})")]
    age_h = _age_h(t, last)
    if age_h < 0:
        return [("judge_rate_unmeasured",
                 f"{rate_path.name} last_verdict_at is in the future -- UNMEASURED ({meter})")]
    if age_h > JUDGE_STALL_H:
        return [("judge_stalled",
                 f"judge STALLED: no new verdict in {age_h:.1f}h (> {JUDGE_STALL_H:g}h); last "
                 f"{last.isoformat(timespec='minutes')}, verdicts/h(24h)="
                 f"{doc.get('verdicts_per_hour')}; {meter}. Check MT5-Gauntlet on the box")]
    if meter_age is None:
        return [("judge_rate_unmeasured", f"{rate_path.name} carries no parseable stamp")]
    if meter_age < 0:
        return [("judge_rate_unmeasured",
                 f"{rate_path.name} is stamped {-meter_age:.1f}h in the future -- UNMEASURED")]
    return []


def _guarded(key: str, fn: Callable[[], list[tuple[str, str]]]) -> list[tuple[str, str]]:
    """A check that raises pages as UNMEASURED: it may never silence the pager or itself."""
    try:
        return fn()
    except Exception as exc:
        return [(key, f"{key} check raised {type(exc).__name__} -- UNMEASURED, not fine")]


def _checks() -> list[tuple[str, str]]:
    """CRITICAL conditions only -- each is (key, message). No account values in messages."""
    out: list[tuple[str, str]] = []
    now = time.time()
    if _HB.exists():
        age = now - _HB.stat().st_mtime
        if age > 1800:
            out.append(("heartbeat_dead", f"executor heartbeat stale {age/60:.0f}min "
                        "(watchdog should have respawned -- check the machine)"))
    else:
        out.append(("heartbeat_missing", "executor heartbeat file missing"))
    if _KILL.exists() and now - _KILL.stat().st_mtime > 3600:
        out.append(("kill_switch_stuck", "CASHCARRY_KILL present >1h -- book is DOWN deliberately; "
                    "remove the file if unintended"))
    if Path("data/DEADMAN_FIRED").exists():
        out.append(("deadman_latched", "DEADMAN_FIRED latch present -- the ruin rail fired and "
                    "the book stays flat until the operator investigates and resets "
                    "(rm data/deadman_state.json data/DEADMAN_FIRED data/CASHCARRY_KILL)"))
    # PRINCIPAL-ACTION channel (2026-07-18): the brain writes data/PRINCIPAL_ACTION.md
    # whenever a human-only door must be opened (live keys at the gate, sub-account
    # proposal, key rotation...). First line = the page text. Re-pages daily until the
    # brain clears the file on resolution. This is how "notify me if you need me" works.
    try:
        pa = Path("data/PRINCIPAL_ACTION.md").read_text("utf-8").strip().splitlines()
        if pa:
            out.append(("principal_action_needed", "the desk needs YOU: " + pa[0][:160]))
    except OSError:
        pass
    rec_hb = Path("data/recorder_heartbeat")
    if rec_hb.exists() and now - rec_hb.stat().st_mtime > 600:
        out.append(("recorder_stale", "data-moat recorder heartbeat stale >10min -- "
                    "unrecoverable microstructure data is being LOST; respawner runs next "
                    "cycle, or: .venv/bin/python scripts/ensure_recorder.py"))
    # LIVE-GUARD DEATH (L1.44, capability hunt 2026-07-31). run_live_guard is simultaneously the
    # size-fraction governor and the stage-demotion tripwire evaluator, and the executor's
    # documented stale-guard behavior is fail-OPEN (full size, takers allowed). Its freeze path
    # cannot save it: the KILL file is written BY the guard, so a dead guard can never write its
    # own freeze -- both degradations point toward MORE aggressive execution, and until this
    # check nothing paged on the file's age. Content stamp over mtime (deploys lie fresh).
    #
    # WELDED FOR AS LONG AS IT HAS EXISTED (R0399, proven 2026-08-13). This read was
    # `lg.get("generated", "1970-01-01T00:00:00+00:00")` and data/live_guard.json has never had a
    # `generated` key -- run_live_guard.py stamps `ts`. So the default fired every time and the
    # page read "live guard stale 29776345min" (56 years) three minutes after the guard wrote the
    # file. A pager that fires on 100% of runs carries zero information (L1.43) and gets acked
    # into silence, which is exactly how the one signal it exists to carry -- the size governor
    # being dead while the executor fail-opens to full size -- would have been lost. The absent
    # key resolved to a LOOSENING default in the sense that matters: not a missed page, but a
    # permanent one, which is the same thing to a reader. Now resolved through the shared
    # stamp-key zoo, so coining a sixth name upstream cannot silently re-weld it.
    lg_age: float | None = None
    lg_absent = ""
    try:
        lg = json.loads(Path("data/live_guard.json").read_text("utf-8"))
        lg_age_h, _lg_key = stamp_age_h(lg)
        if lg_age_h is None:
            # UNMEASURABLE is kept DISTINCT from missing (L1.28a): a guard that is running but
            # publishing no stamp needs its PRODUCER fixed, an absent one needs starting, and
            # collapsing them sends the operator to the wrong organ. Never fall back to mtime
            # here -- that is the direction the whole check exists to distrust.
            lg_absent = ("present but carries no parseable stamp key -- its age is "
                         "UNMEASURABLE, so liveness is unknown rather than fine")
        else:
            lg_age = lg_age_h * 3600.0
    except (OSError, ValueError, TypeError) as exc:
        lg_absent = f"missing/unreadable ({type(exc).__name__})"
    # THE TWO live_guard ALERTS WERE REMOVED 2026-09-05 (universe mandate). They paged when
    # `data/live_guard.json` was missing or stale, on the grounds that "the executor fail-opens to
    # full size". That executor is deleted; the artifact now has no writer at all, so both alerts
    # would fire on EVERY tick, for ever, about a size governor for a book that cannot trade.
    # A permanently-firing pager row is the cry-wolf shape this desk fences elsewhere -- it trains
    # the principal to ack the whole channel, which is how a real alert gets missed.
    _ = (lg_absent, lg_age)     # read above; retained so the parse stays a measured no-op
    try:
        v = json.loads(Path("data/cadence_violation.json").read_text("utf-8"))
        out.append(("cadence_floor_violation", "review/safety cadence FLOOR breached: "
                    + "; ".join(str(x)[:70] for x in v.get("violations", [])[:3])))
    except (OSError, json.JSONDecodeError):
        pass
    # BRAIN-DOWN (2026-07-16 incident: the AI CRO was unauthenticated for 3 days and the 07-13
    # dead-man fire sat untriaged -- rails page instantly, but nothing paged about the missing
    # brain). A real cycle writes a multi-KB log; a no-auth run writes a near-empty one.
    try:
        logs = sorted(Path("data/cro_ai_logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
        if not logs or now - logs[-1].stat().st_mtime > 26 * 3600:
            out.append(("brain_down", "AI CRO cycle has not run in >26h -- check "
                        "quant-cro-ai.timer and auth (ssh: claude -p 'say OK') on the VPS"))
        elif logs[-1].stat().st_size < 2048 and now - logs[-1].stat().st_mtime > 2 * 3600:
            out.append(("brain_noop", "last AI CRO run produced a near-empty log -- likely auth "
                        "failure; verify on the VPS with: claude -p 'say OK'"))
    except OSError:
        pass
    try:
        rc = json.loads(Path("web/root_cause.json").read_text("utf-8"))
        if rc.get("action") == "act_autonomously" and rc.get("top_confidence", 0) >= 0.7:
            out.append(("root_cause_critical",
                        f"root-cause engine: {rc.get('top_cause')} at "
                        f"{rc.get('top_confidence'):.0%} confidence"))
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    try:
        ga = json.loads(Path("web/growth_audit.json").read_text("utf-8"))
        if ga.get("conservatism_defects"):
            out.append(("growth_defect", "unresolved conservatism defect(s): "
                        + ", ".join(ga["conservatism_defects"])))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        h = json.loads(Path("web/health.json").read_text("utf-8"))
        alerts = h.get("alerts") or []
        if alerts:
            out.append(("data_health", f"{len(alerts)} data-health alert(s): "
                        + "; ".join(str(a)[:60] for a in alerts[:3])))
    except (OSError, json.JSONDecodeError):
        pass
    # RESEARCH-CHAIN STEP FAILURES (R0258). The daily research runners are best-effort BY DESIGN
    # (one step must never abort the chain) -- which made a dead step silent by design too:
    # run_cashcarry_shadow's SystemExit killed the flagship forward clock for a full day with
    # zero alarm. Both runners now drop data/research_chain_status.json (atomic write); a latest
    # status carrying failed steps pages here, naming them. ABSENT artifact = no page: it is a
    # new artifact, and the brain-down / cycle-age checks above already own "chain never ran".
    try:
        rcs = json.loads(Path("data/research_chain_status.json").read_text("utf-8"))
        failed = [f for f in (rcs.get("failed") or []) if isinstance(f, dict)]
        if failed:
            names = "; ".join(
                f"{str(f.get('step'))[:44]}(rc={f.get('rc')}) {str(f.get('tail', ''))[:60]}"
                for f in failed[:3])
            more = f" +{len(failed) - 3} more" if len(failed) > 3 else ""
            out.append(("research_chain_failed",
                        f"{len(failed)}/{rcs.get('steps_total', '?')} research step(s) FAILED "
                        f"({rcs.get('runner', '?')} @ {str(rcs.get('generated', '?'))[:16]}Z): "
                        f"{names}{more}"))
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        pass
    # silent-failure sweep (2026-07-22): systemd-success != work-done. A timer that fired
    # into a quota/auth wall reports success while producing zero research.
    try:
        tf = json.loads(Path("web/trade_forensics.json").read_text("utf-8"))
        for fl in (tf.get("flags") or [])[:3]:
            out.append(("trade_class_bleeding", str(fl)[:170]))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        # TWO-STAGE LAW: confirmation slots are the ONLY multiplicity that matters; the
        # bar stays fixed for life only while the concurrent count stays <= 12.
        # The cohort is DERIVED from the clock artifacts (libs.research.slot_registry), never
        # counted here. This block used to sum an empty registry + a hardcoded `_standing = 6`
        # + the axis count -- three files each holding a different m, none of them the truth.
        # Imported locally on purpose: this daemon is what pages the principal, so a bad import
        # must degrade one alert, never silence the pager.
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots

        _snap = derive_slots()
        _total = int(_snap["m_concurrent"])
        _by_kind = Counter(str(s["kind"]) for s in _snap["slots"])
        _mix = " + ".join(f"{n} {k}" for k, n in sorted(_by_kind.items()))
        if not _snap["complete"]:
            # Unreadable is reported, never read as 0: a missing clock shrinks m and LOOSENS
            # every bar, so silence here would be the phantom-edge direction.
            out.append(("slot_budget_unreadable",
                        f"forward-slot sources unreadable ({', '.join(_snap['unknown_sources'])})"
                        f" -- the concurrent count is a LOWER BOUND ({_total}), not the truth; "
                        "every clock's Holm bar may be too loose this run"))
        elif _total > MAX_FORWARD_SLOTS:
            out.append(("slot_budget_exceeded",
                        f"{_total} concurrent confirmation slots > {MAX_FORWARD_SLOTS} "
                        f"({_mix}) -- the fixed forward bar is only fixed while the cohort is "
                        "capped; recycle or EV-evict before enrolling more"))
        elif _total < MAX_FORWARD_SLOTS:
            # CLOCK-SATURATION DUTY: an idle slot is idle capital's research twin. The law
            # pins the cohort always-full-never-over, so under is a defect exactly like over.
            out.append(("clock_slots_idle",
                        f"only {_total}/{MAX_FORWARD_SLOTS} confirmation slots accruing "
                        f"({_mix}) -- {MAX_FORWARD_SLOTS - _total} idle. Every verified axis owes "
                        "a pre-registered hypothesis within 7 days; an empty clock discovers "
                        "nothing"))
    except (OSError, json.JSONDecodeError, ImportError, KeyError, TypeError):
        pass
    if _auth_broken():
        out.append(("auth_broken",
                    "NO claude credentials for the `quant` user -- the brain AND all 4 "
                    "diggers are dead on arrival. Fix on the VPS: "
                    "sudo -u quant -i ; claude setup-token"))
    out.extend(_digger_health())
    # The plumbing / judge checks are NOT run here: their inputs are written on the box and the
    # VPS (orphan desk-sync-clean) never receives them, so here they could only page UNMEASURED
    # forever. They run on the box, from the box's own files: `run_alerts.py --box`.
    return out


def _box_checks() -> list[tuple[str, str]]:
    return (_guarded("plumbing_unmeasured", _plumbing_checks)
            + _guarded("judge_rate_unmeasured", _judge_checks))


def _brain_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-f", "run_cro_ai.sh"],
                              capture_output=True).returncode == 0
    except Exception:
        return False


def _brain_should_trigger(state: dict[str, Any], active: set[str], *, healthy_today: bool, hour: int,
                          now: float) -> str | None:
    """PURE decision (drill-testable): should the brain be auto-triggered? Rate-limited to one
    trigger per 3h. AUTO-RETRY when today's cycle failed/near-empty and it is past ~11:00 UTC
    (session limit likely reset). EVENT when a brain-remediable alert is live and no healthy
    cycle ran since. Human-only + slow/justified conditions never trigger (see _EVENT_TRIGGER)."""
    if now - float(state.get("_brain_trigger", 0)) < 3 * 3600:
        return None
    if (not healthy_today) and hour >= 11:
        return "auto-retry"
    if bool(active & _EVENT_TRIGGER) and not healthy_today:
        return "event"
    return None


def _brain_watchdog(state: dict[str, Any], active: set[str]) -> str | None:
    """Self-heal the AI brain WITHOUT the operator (2026-07-18): auto-retry a failed daily cycle
    (e.g. the 07-18 session-limit lost-day) + event-trigger on a remediable alert. Never two
    brains; the brain's own CI + escalation keep it safe; risk/money still page the operator."""
    if _brain_running():
        return None
    now = time.time()
    healthy_today = False
    try:
        logs = sorted(Path("data/cro_ai_logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
        if logs:
            last = logs[-1]
            healthy_today = (last.stat().st_size >= 2048
                            and now - last.stat().st_mtime < 20 * 3600)
    except OSError:
        pass
    reason = _brain_should_trigger(state, active, healthy_today=healthy_today,
                                   hour=datetime.now(tz=UTC).hour, now=now)
    if not reason:
        return None
    try:
        subprocess.Popen(["setsid", "nohup", "bash", "ops/run_cro_ai.sh"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL, start_new_session=True)
        state["_brain_trigger"] = now
        return reason
    except Exception as e:
        print(f"brain-watchdog: trigger failed {e!r}"[:100])
        return None


_KEY_RE = re.compile(r"[a-z0-9_]{1,80}")


def _load_state(path: Path) -> dict[str, Any]:
    """The dedupe state, sanitised. A corrupt file (not JSON, not an object, non-UTF8, a
    non-numeric stamp, `_paged` not a list) may neither crash the tick nor storm: bad entries
    are dropped, so each live key pages once and is then stamped afresh."""
    try:
        raw = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {k: float(v) for k, v in raw.items()
                           if isinstance(v, int | float) and not isinstance(v, bool)
                           and k != "_paged"}
    paged = raw.get("_paged")
    # only well-formed key names: a junk entry ([1], {"a": 2}) would send a bogus RESOLVED page
    out["_paged"] = ([x for x in paged if isinstance(x, str) and _KEY_RE.fullmatch(x)]
                     if isinstance(paged, list) else [])
    return out


def _recent(now: float, stamp: object, window: float) -> bool:
    """True while `stamp` is inside `window` seconds. A FUTURE stamp (clock step-back, hand
    edit) is never recent: it may not be what keeps the pager quiet."""
    if not isinstance(stamp, int | float) or isinstance(stamp, bool):
        return False
    return 0 <= now - float(stamp) < window


def _dispatch(topic: str, checks: list[tuple[str, str]], state: dict[str, Any],
              now: float) -> tuple[int, set[str], int]:
    """Page each check (deduped, backed off) and RESOLVE what cleared. Mutates `state`.
    Returns (sent, active keys, due): `due` counts WARNING pages owed this tick (outside their
    dedupe window), whether or not the push went out or was held by the failure backoff."""
    sent = 0
    due = 0
    active = {k for k, _ in checks}
    paged = set(state.get("_paged") or [])
    for key, msg in checks:
        # a FUTURE stamp (clock step, hand edit) is overdue, never what keeps the pager quiet
        if _recent(now, state.get(key), _DEDUPE_OVERRIDES_S.get(key, _DEDUPE_S)):
            paged.add(key)                                 # still-alerting, still track for resolve
            continue
        due += 1
        # FAILURE BACKOFF (2026-07-16): a failed push used to retry every 3-min tick forever --
        # the sustained hammering kept the free ntfy.sh quota exhausted from 07-11 on, so EVERY
        # page (including the 07-13 dead-man fire) was silently dropped. One attempt per key per
        # 30min keeps total volume far under quota and lets it refill.
        if _recent(now, state.get(f"_try_{key}"), 1800):
            continue
        state[f"_try_{key}"] = now
        try:
            _push(topic, f"WARNING Quant desk: {key}", msg)
            state[key] = now
            paged.add(key)
            sent += 1
        except Exception as e:  # pager failing must never break the tick
            print(f"pager push failed: {e!r}"[:120])
    # RESOLUTION / "FIXED" PAGES (2026-07-18 principal idea): pair every alert with a "cleared"
    # notification, so the operator only has to LOOK when a warning arrives with NO fix behind
    # it. A previously-paged condition that is no longer active -> one "resolved" page.
    for key in list(paged):
        if key not in active:
            with contextlib.suppress(Exception):
                _push(topic, f"RESOLVED Quant desk: {key}",
                      "auto-fixed / cleared -- no action needed")
            paged.discard(key)
            state.pop(key, None)
    state["_paged"] = sorted(paged)
    return sent, active, due


def _write_state(path: Path, state: dict[str, Any]) -> None:
    """LOUD, never raising: a state file that cannot be written must not undo sent pages."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), "utf-8")
    except OSError as exc:
        print(f"alerts: dedupe state NOT written ({type(exc).__name__})", flush=True)


#: THE BOX PATH (audit HOLD 2026-10-20). The VPS runs orphan desk-sync-clean and never receives
#: the plumbing or judge inputs, so the box pages them itself, from its own files, as task
#: MT5-PlumbingPager (desks/mt5/scripts/install_plumbing_pager_task.ps1).
_ROOT = Path(__file__).resolve().parents[1]
_BOX_SECRETS = (Path("data/secrets/ntfy.json"), Path("desks/mt5/data/secrets/ntfy.json"))
_BOX_STATE = Path("desks/mt5/logs/plumbing_pager_state.json")


def box_main() -> int:
    """One box pass: plumbing + judge checks only, through the existing sender.

    A missing ntfy secret is a LOGGED FAILURE (exit 2) with no page: the box never mints a
    topic (a minted topic has no subscriber, so a page to it reaches no one) and never prints
    one. Exit 3 when a page was due and did not go out (push failed, or held by the failure
    backoff): a pager that cannot deliver must fail its task, so MT5-PlumbingWatchdog's
    last-result check sees it. Exit 0 otherwise."""
    os.chdir(_ROOT)
    topic = _read_topic(_BOX_SECRETS)
    if topic is None:
        print("alerts --box: NOT ARMED -- no readable ntfy topic in "
              + " or ".join(str(p) for p in _BOX_SECRETS)
              + "; no page sent and no topic created", flush=True)
        return 2
    state = _load_state(_BOX_STATE)
    checks = _box_checks()
    sent, active, due = _dispatch(topic, checks, state, time.time())
    _write_state(_BOX_STATE, state)
    print(f"alerts --box: {sent}/{due} due page(s) sent, {len(active)} active "
          f"({', '.join(sorted(active)) or 'none'}) ({datetime.now(tz=UTC).isoformat()[:16]}Z)",
          flush=True)
    if due > sent:
        print(f"alerts --box: FAILED -- {due - sent} due page(s) NOT delivered", flush=True)
        return 3
    return 0


def main() -> None:
    if "--box" in sys.argv:
        raise SystemExit(box_main())
    topic = _topic()
    if "--status" in sys.argv:
        # gap #38: which channels are ARMED, when each last DELIVERED, and whether everything has
        # been silent -- the three facts nobody could read before 2026-07-29.
        from libs.ops.alert_channels import status as _chan_status
        st = _chan_status()
        print(f"pager topic: configured in {_SECRETS} (not printed)")
        print(f"registry channels armed: {st['armed']} {st['armed_kinds']}")
        if st["arming_owed"]:
            print("  NOT-ARMED (human step): data/secrets/alert_channels.json -- ntfy alone is "
                  "the single point of failure gap #38 exists to remove")
        print(f"last success per channel: {st['last_success_per_channel'] or 'NONE RECORDED'}")
        print(f"all channels silent 24h: {st['all_silent_24h']}  "
              f"SILENT flag: {st['silent_flag_present']}")
        for row in st["ledger_tail"]:
            print(f"  {row.get('ts', '?')} {row.get('channel', '?'):9} "
                  f"ok={row.get('ok')} {row.get('detail', '')}")
        return
    if "--test" in sys.argv:
        _push(topic, "Quant desk pager: TEST", "pager wired -- you will only hear from me "
              "when something is genuinely wrong")
        print(f"test page sent (topic in {_SECRETS})")
        return
    _poll_replies(topic)          # read principal replies BEFORE computing pages: a fresh
    state = _load_state(_STATE)   # ACK/REARM must suppress this very tick's escalation
    sent, active, _due = _dispatch(topic, _checks(), state, time.time())
    # SELF-HEAL: auto-retry a failed daily brain cycle + event-trigger the brain on a remediable
    # alert -- so the desk fixes itself without waiting for the operator (2026-07-18).
    trig = _brain_watchdog(state, active)
    if trig:
        print(f"brain-watchdog: triggered brain cycle ({trig})")
    _write_state(_STATE, state)
    # EXTERNAL HEARTBEAT (2026-07-16, v8-blueprint triage 8.13): an off-box dead-man for the
    # box itself. Everything above -- deadman, pager, watchdog -- dies WITH the host; a 3-min
    # ping to an external healthchecks-class URL makes the outside world notice silence and
    # page the principal directly. Graceful skip until the operator creates the free check and
    # drops its URL into data/secrets/heartbeat_url.json ({"url": "https://hc-ping.com/..."}).
    try:
        hb = json.loads(Path("data/secrets/heartbeat_url.json").read_text("utf-8")).get("url")
        if hb:
            with urllib.request.urlopen(hb, timeout=10):
                pass
    except Exception:
        # THE PAGER'S JOB IS PAGES, NOT THE HEARTBEAT. This is a best-effort ping to an
        # external liveness service; failing it must never stop pages that have already been
        # computed from going out, which is what raising here would do.
        pass
    print(f"alerts: {sent} page(s) sent "
          f"({datetime.now(tz=UTC).isoformat()[:16]}Z)")


if __name__ == "__main__":
    main()
