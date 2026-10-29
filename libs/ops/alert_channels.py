"""ALERT CHANNEL REGISTRY + DELIVERY LEDGER -- gap #38, built 2026-07-29.

WHAT WAS ALREADY THERE, and this does not rebuild it: `scripts/run_alerts.py` pages ntfy.sh and
already mirrors to an INDEPENDENT path (`_second_channel` -> the healthchecks.io `/fail` endpoint,
different provider, different network route). The unanimous 12/13 panel finding was never only
"add a channel" -- it was that the desk had **no delivery confirmation, no canary, and no way to
observe BOTH channels being silent**. That is what this module adds:

  1. one place that knows which channels are ARMED (and records unarmed as a STATE, never silence),
  2. an append-only DELIVERY LEDGER -- one row per attempt per channel, success or failure,
  3. `all_silent_since()`, so "nothing has been delivered anywhere in N hours" becomes an
     observable condition instead of the thing nobody notices for five days.

FAILURE SEMANTICS, learned the hard way twice: no channel's exception may ever propagate into the
alert path (2026-07-19: a latin-1 header encode killed 39/39 pushes silently for 29h across a live
dead-man fire), and no channel's failure may suppress another's. Every send is best-effort,
independently wrapped, and always logged.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: it does not decide WHEN to page (that is
`run_alerts._checks`), it holds no thresholds, and it never reads book state.

AUDIENCE -- WHO A PAGE IS FOR (2026-10-29, the owner, verbatim: "only notify me on things which
need me or else it's confusing; handle rest n don't tell me"). Every `send_all` names one of two
audiences, and THE RULE IS: a page is `"principal"` only when the reader must take a HUMAN action
that the system and the agent threads cannot take for him. Everything the box, a watchdog or a
thread can handle itself is `"desk"`.

  * "principal" -- needs zuck personally. Examples: live positions that must be closed (only he
    may close a position); an account near or past a firm loss rail with no automatic protection
    having acted; the dead-man firing on a live account; a manual-follow trade he places by hand;
    a door only a person can open. The ONLY audience delivered to the personal push channels
    (`_PERSONAL_KINDS`: ntfy, telegram, email).
  * "desk" -- ops noise: box health (watchdog, gateway, disk, research staleness), state
    publication flowing/stale, fences UNMEASURED or REFUSED, judge stalls, restore drills, law
    police, the canary. Delivered to the ledger and the NON-personal channels (webhook, hc), which
    the reports, REDs and agent threads read and fix. Never pushed to the phone. For each personal
    channel a desk page writes a ledger row `{"channel": "ntfy", "ok": true, "detail": "routed:
    desk audience", "routed": "desk"}` so the routing is visible, never silent -- and routed rows
    are NOT counted as deliveries by `last_success_per_channel`/`all_silent_since`, so a desk-only
    week can never hide a dead phone channel.

  Box health is never "principal", not even the gateway or the disk: a RED a thread fixes.
  BORDERLINE? Read what the page asks the reader to DO. A human action -> principal; else desk.

  `page_principal(title, body)` is THE sanctioned "needs zuck" path for a thread that must ping him
  once: it is `send_all(..., audience="principal")`, plus the desk ntfy topic from
  data/secrets/ntfy.json when the registry arms no ntfy channel, and hc /fail from
  data/secrets/heartbeat_url.json when it arms no hc channel. Use it sparingly -- every
  principal page spends the credibility of the next one.

  WHERE A DESK PAGE GOES. Desk pages are not dropped, they are routed to something that acts: the
  ledger, hc /log (recorded, notifies nobody; /fail is principal only), and a row in
  desks/mt5/reports/DESK_ALERTS.json that check_desk_health turns into a PROBLEM while fresh.

  The default, for a caller that names no audience, is "principal" (the safe direction for money:
  a forgotten argument can over-page, never swallow a page). `tests/ops/test_alert_audience.py`
  fails on any `send_all` call site in the repo that omits `audience`, except the byte-pinned box
  watcher canon copies it lists by name.

Config (absent = gracefully unarmed, recorded): `data/secrets/alert_channels.json`
    {"channels": [{"kind": "telegram", "token": "...", "chat_id": "..."},
                  {"kind": "webhook",  "url": "https://..."},
                  {"kind": "email",    "host": "smtp...", "port": 587, "user": "...",
                   "password": "...", "to": "..."}]}
Stdlib only. import from libs.ops.alert_channels.
"""
from __future__ import annotations

import contextlib
import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

_CONFIG = Path("data/secrets/alert_channels.json")
_LEDGER = Path("data/alert_delivery.jsonl")
_SILENT_FLAG = Path("data/ALERT_CHANNELS_SILENT")

_HEARTBEAT = Path("data/secrets/heartbeat_url.json")
_NTFY_SECRET = Path("data/secrets/ntfy.json")

_TIMEOUT = 12.0
_KINDS = ("ntfy", "telegram", "webhook", "email", "hc")


#: The two audiences (see the module docstring). Anything else is treated as PRINCIPAL.
PRINCIPAL = "principal"
DESK = "desk"
AUDIENCES = (PRINCIPAL, DESK)
#: Channels that reach the owner personally. Only a PRINCIPAL page is sent to these.
_PERSONAL_KINDS = frozenset({"ntfy", "telegram", "email"})
ROUTED_DETAIL = "routed: desk audience"

#: THE DESK ALERT ARTIFACT. A desk page that only reaches a ledger reaches nobody who acts, so
#: every desk send_all also upserts one row per alert key here -- {key, source, title_sha,
#: first_seen, last_seen}, plus `title` (<=160) ONLY when the caller declares it value-free
#: (`public_title=True`) -- and desks/mt5/scripts/check_desk_health.py turns any row seen inside
#: DESK_ALERT_FRESH_H into a PROBLEM (a RED the threads read and fix). THIS FILE IS PUBLISHED, so
#: it never holds a page body and never a title that could carry book state: the key alone (a
#: check name, or the calling file:function) is what a thread follows back to the source.
#: Repo-relative like the ledger; a caller with its own ledger gets it beside the ledger.
_DESK_ALERTS = Path("desks/mt5/reports/DESK_ALERTS.json")
#: One day of re-pages (the slowest run_alerts dedupe is 24h) plus an hour of slack: a condition
#: still alerting keeps its row fresh; one that stopped ages out a day later.
DESK_ALERT_FRESH_H = 25.0
#: Rows not seen for this long are pruned so the artifact cannot grow without bound.
_DESK_ALERT_KEEP_D = 7.0
_REPO = Path(__file__).resolve().parents[2]


#: Every ledger/result detail is cut to this many characters -- AFTER redaction (`_redact`).
_DETAIL_MAX = 200
_REDACTED = "<redacted>"


def _redact(text: str, *secrets: object, limit: int = _DETAIL_MAX,
            mask: str = _REDACTED) -> str:
    """`text` with every secret removed, cut to `limit` -- in THAT order (audit MF, a072c7d7b).

    Cutting first and replacing second leaks: a secret straddling the cut survives as a prefix
    the replace cannot match (probe: the ntfy topic at offsets 170/175/180 of a 200-char detail
    leaked its first 30/25/20 characters into the ledger). So: replace every whole occurrence,
    cut, then strip any trailing PREFIX of a secret left at the cut edge -- which also covers a
    text that some upstream already cut mid-secret. The prefix strip may eat a few innocent tail
    characters that happen to spell a secret's first letters; a shorter detail is the cheap side.
    """
    keys = sorted({str(x) for x in secrets if x and len(str(x)) >= 4}, key=len, reverse=True)
    for k in keys:
        text = text.replace(k, mask)
    text = text[:limit]
    for k in keys:
        for n in range(min(len(k) - 1, len(text)), 0, -1):
            if text.endswith(k[:n]):
                text = text[:-n] + mask
                break
    return text


def _log(channel: str, ok: bool, detail: str, title: str, ledger: Path = _LEDGER, *,
         routed: str | None = None) -> None:
    """One row per attempt. The title is HASHED, never stored: alert bodies can name positions,
    and a delivery ledger is not a place to leak book state. `routed` marks a row that records a
    deliberate non-send (a desk page kept off a personal channel)."""
    with contextlib.suppress(OSError):
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {
            "ts": datetime.now(tz=UTC).isoformat(), "channel": channel, "ok": ok,
            "detail": detail[:_DETAIL_MAX],
            "title_sha": sha256(title.encode("utf-8", "ignore")).hexdigest()[:12]}
        if routed:
            row["routed"] = routed
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_channels(config: Path = _CONFIG) -> list[dict[str, Any]]:
    """Armed channels from config. A missing/unreadable file is NOT an error -- it means the
    second-channel work is owed a human step (credentials on the box) and callers report that."""
    try:
        raw = json.loads(config.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    chans = raw.get("channels") if isinstance(raw, dict) else raw
    if not isinstance(chans, list):
        return []
    return [c for c in chans if isinstance(c, dict) and c.get("kind") in _KINDS]


def _send_telegram(cfg: dict[str, Any], title: str, body: str) -> str:
    url = f"https://api.telegram.org/bot{cfg['token']}/sendMessage"
    data = json.dumps({"chat_id": str(cfg["chat_id"]),
                       "text": f"{title}\n{body}"[:3900]}).encode()
    req = urllib.request.Request(url, data=data,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"http {r.status}"


def _send_webhook(cfg: dict[str, Any], title: str, body: str) -> str:
    data = json.dumps({"title": title, "body": body}).encode()
    req = urllib.request.Request(str(cfg["url"]), data=data,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"http {r.status}"


def _send_email(cfg: dict[str, Any], title: str, body: str) -> str:
    msg = EmailMessage()
    # Non-ASCII in a header is exactly what killed ntfy for 29h; email headers are MIME-encoded
    # by EmailMessage so this is safe, but keep the same discipline for consistency.
    msg["Subject"] = title.encode("ascii", "ignore").decode("ascii") or "quant alert"
    msg["From"] = str(cfg.get("user", "quant@localhost"))
    msg["To"] = str(cfg["to"])
    msg.set_content(body)
    port = int(cfg.get("port", 587))
    with smtplib.SMTP(str(cfg["host"]), port, timeout=_TIMEOUT) as s:
        with contextlib.suppress(smtplib.SMTPException):
            s.starttls()
        if cfg.get("user") and cfg.get("password"):
            s.login(str(cfg["user"]), str(cfg["password"]))
        s.send_message(msg)
    return "smtp ok"


def _send_ntfy(cfg: dict[str, Any], title: str, body: str) -> str:
    safe = title.encode("latin-1", "ignore").decode("latin-1")
    req = urllib.request.Request(f"https://ntfy.sh/{cfg['topic']}", data=body.encode(),
                                 headers={"Title": safe, "Priority": "high"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return f"http {r.status}"


def _send_hc(cfg: dict[str, Any], title: str, body: str, *, canary: bool = False) -> str:
    """healthchecks.io -- the one independent provider this box can arm with NO new credential.

    Arming has sat "owed to a human step" since 2026-07-29 while a perfectly good second provider
    was already configured on the box for the box-liveness heartbeat: different company, different
    network path, and its ping URL is the only credential needed. `run_alerts._second_channel`
    has quietly relied on it for real pages since gap #38; this makes the SAME route visible to
    the registry, so its deliveries land in the ledger and `all_silent_since` can finally see two
    channels instead of one.

    /fail marks the check down and fires whatever notification is configured there; the next
    3-minute heartbeat ping clears it automatically. THE CANARY MUST NOT USE IT: a synthetic probe
    every 6h that cries "box is dead" would train the principal to ignore the one signal that says
    the machine is gone. /log records the event and notifies nobody, which is exactly what proving
    reachability calls for -- so the canary tests the route without spending its credibility.

    `url` is optional and normally absent: defaulting to the heartbeat file keeps ONE copy of the
    secret, so a rotated URL cannot leave this channel silently pointing at a dead check. Set it
    explicitly once a dedicated alert check exists -- see the semantics note in status().
    """
    url = str(cfg.get("url") or "").strip()
    if not url:
        url = str(json.loads(_HEARTBEAT.read_text("utf-8")).get("url", "")).strip()
    if not url:
        raise ValueError("hc channel: no url in config and no data/secrets/heartbeat_url.json")
    endpoint = url.rstrip("/") + ("/log" if canary else "/fail")
    data = f"{title}\n{body}".encode("utf-8", "ignore")[:9000]
    with urllib.request.urlopen(urllib.request.Request(endpoint, data=data),
                                timeout=_TIMEOUT) as r:
        return f"http {r.status} {'log' if canary else 'fail'}"


#: TWO MAPS, NOT ONE MAP AND A SET OF NAMES. Every sender answers the plain three-argument call;
#: only some also accept `canary=`. Keeping both in one dict makes the type the LOOSEST signature
#: in it, so a sender that silently stopped accepting `canary` would type-check fine and fail at
#: send time -- on the pager, which is the one path with no second chance to notice. Membership in
#: `_CANARY_SENDERS` is now a typed fact rather than a name in a frozenset that nothing checks.
_SENDERS: dict[str, Callable[[dict[str, Any], str, str], str]] = {
    "ntfy": _send_ntfy, "telegram": _send_telegram,
    "webhook": _send_webhook, "email": _send_email, "hc": _send_hc}


class _CanarySender(Protocol):
    def __call__(self, cfg: dict[str, Any], title: str, body: str, *,
                 canary: bool = False) -> str: ...


#: kinds with a non-notifying probe endpoint
_CANARY_SENDERS: dict[str, _CanarySender] = {"hc": _send_hc}
_CANARY_AWARE = frozenset(_CANARY_SENDERS)


def send_all(title: str, body: str, *, config: Path = _CONFIG,
             ledger: Path = _LEDGER, canary: bool = False,
             audience: str = PRINCIPAL, key: str | None = None, source: str = "",
             resolved: bool = False, public_title: bool = False,
             desk_row: bool = True) -> dict[str, Any]:
    """Fire EVERY armed channel the audience allows; one channel's failure can never stop another's.

    Returns {"armed": n, "delivered": n, "routed": n, "audience": a, "results": [...]}. When
    nothing is armed the result says so and a row is written -- an unarmed pager is a recorded
    state, not silence.

    `audience` (module docstring): "principal" reaches every armed channel; "desk" skips the
    personal ones (ntfy, telegram, email), writing an ok `routed: desk audience` ledger row for
    each instead. A routed channel counts in `delivered` -- the page reached the destination its
    audience names, so a caller's dedupe records it rather than re-sending every pass -- and is
    counted separately in `routed`. An unknown audience is treated as "principal".

    `canary=True` marks the send as a synthetic reachability probe. Channels that can distinguish
    the two use the non-notifying variant, so proving the route works never costs the principal an
    alert they have to read and dismiss -- a canary that pages is a canary that gets muted.

    A DESK send (not a canary) also upserts its row in the desk alert artifact under `key`
    (default: the calling file:function), tagged with `source` (default: the calling file);
    `resolved=True` removes that row instead, so a cleared condition stops holding the desk RED.
    `desk_row=False` is for a desk send that is INFORMATION, not a problem (the daily digest, a
    model auto-upgrade, "fell back and carried on"): it is ledgered and mirrored as usual but
    writes no artifact row, so it never holds the desk RED for a day over nothing to fix.
    A failed artifact write is never silent: it is ledgered (channel "desk_alerts", ok false) and
    returned as `desk_alert_error`.
    The body is never written there, and the title only with `public_title=True`. The hc
    channel takes a desk send on its /log endpoint (recorded, notifies nobody) and only a
    principal send on /fail.
    """
    aud = audience if audience in AUDIENCES else PRINCIPAL
    desk_err: str | None = None
    if aud == DESK and not canary and (desk_row or resolved):
        where = _caller()
        k = key or where
        if resolved:
            desk_err = clear_desk_alert(k, path=desk_alerts_path(ledger))
        else:
            desk_err = record_desk_alert(k, title, source=source or where.split(":", 1)[0],
                                         public_title=public_title,
                                         path=desk_alerts_path(ledger))
        if desk_err:                            # surfaced: ledgered and in the result
            _log("desk_alerts", False, desk_err, title, ledger)
    extra: dict[str, Any] = {"desk_alert_error": desk_err} if desk_err else {}
    channels = load_channels(config)
    if not channels:
        _log("none", False, "NOT-ARMED: data/secrets/alert_channels.json absent or empty",
             title, ledger)
        return {"armed": 0, "delivered": 0, "routed": 0, "audience": aud, "results": [],
                "note": "second-channel arming is a HUMAN step: drop credentials at "
                        "data/secrets/alert_channels.json on the box", **extra}
    results = []
    for cfg in channels:
        kind = str(cfg.get("kind"))
        if aud == DESK and kind in _PERSONAL_KINDS:
            _log(kind, True, ROUTED_DETAIL, title, ledger, routed=DESK)
            results.append({"channel": kind, "ok": True, "detail": ROUTED_DETAIL,
                            "routed": True})
            continue
        try:
            # a desk page rides the non-notifying endpoint, exactly like the canary (hc /log)
            detail = (_CANARY_SENDERS[kind](cfg, title, body, canary=canary or aud == DESK)
                      if kind in _CANARY_SENDERS else _SENDERS[kind](cfg, title, body))
            ok = True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError,
                json.JSONDecodeError, smtplib.SMTPException, ValueError) as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        # the channel's own credentials never reach a detail (redact BEFORE the cut)
        detail = _redact(detail, *(cfg.get(f) for f in ("topic", "token", "password", "url")))
        _log(kind, ok, detail, title, ledger)
        results.append({"channel": kind, "ok": ok, "detail": detail})
    return {"armed": len(channels), "delivered": sum(1 for r in results if r["ok"]),
            "routed": sum(1 for r in results if r.get("routed")), "audience": aud,
            "results": results, **extra}


def page_principal(title: str, body: str, *, config: Path = _CONFIG,
                   ledger: Path = _LEDGER, ntfy_secret: Path = _NTFY_SECRET,
                   heartbeat: Path = _HEARTBEAT) -> dict[str, Any]:
    """THE sanctioned "needs zuck" page: a thread that must have the owner's personal action pings
    him through this, and only for that (module docstring: a human action only he can take).
    Same failure semantics as `send_all` -- never raises, every attempt is ledgered.

    THE PHONE IS NOT OPTIONAL HERE, AND NEITHER IS THE SECOND PROVIDER. The desk's ntfy topic
    lives in data/secrets/ntfy.json and the healthchecks.io ping URL in
    data/secrets/heartbeat_url.json; the registry reads neither. So on a box whose
    alert_channels.json arms no ntfy (or no hc) channel, a principal page would miss the one
    channel he carries (or have no independent mirror if ntfy.sh itself is down). For each such
    channel the registry lacks, and whose secret exists, it is sent there too (ledgered): ntfy
    from ntfy.json, and hc /fail from heartbeat_url.json -- /fail because this IS a principal page
    (the next 3-minute heartbeat ping clears the check)."""
    res = dict(send_all(title, body, config=config, ledger=ledger, audience="principal"))
    armed = {str(c.get("kind")) for c in load_channels(config)}
    extra: list[dict[str, Any]] = []
    if "ntfy" not in armed:
        try:
            topic = str(json.loads(ntfy_secret.read_text("utf-8")).get("topic") or "").strip()
        except (OSError, ValueError, AttributeError):
            topic = ""
        if topic:
            try:
                detail, ok = _SENDERS["ntfy"]({"kind": "ntfy", "topic": topic}, title, body), True
            except Exception as e:              # never raises into the alert path
                ok, detail = False, f"{type(e).__name__}: {e}"
            # the topic is the secret: redact FIRST, then cut, then strip a prefix left at the edge
            detail = _redact(detail, topic, mask="<topic>")
            _log("ntfy", ok, detail, title, ledger)
            extra.append({"channel": "ntfy", "ok": ok, "detail": detail, "via": "ntfy.json"})
    if "hc" not in armed:
        try:
            url = str(json.loads(heartbeat.read_text("utf-8")).get("url") or "").strip()
        except (OSError, ValueError, AttributeError):
            url = ""
        if url:
            try:
                detail, ok = _SENDERS["hc"]({"kind": "hc", "url": url}, title, body), True
            except Exception as e:              # never raises into the alert path
                ok, detail = False, f"{type(e).__name__}: {e}"
            detail = _redact(detail, url, url.rstrip("/").rsplit("/", 1)[-1])
            _log("hc", ok, detail, title, ledger)
            extra.append({"channel": "hc", "ok": ok, "detail": detail,
                          "via": "heartbeat_url.json"})
    if extra:
        res["results"] = [*res.get("results", []), *extra]
        res["delivered"] = int(res.get("delivered", 0)) + sum(1 for r in extra if r["ok"])
    return res


def _caller() -> str:
    """`repo/relative/file.py:function` of send_all's caller -- a desk row's default key, so a
    thread can find the code that paged without the row repeating anything the page said."""
    try:
        f = sys._getframe(2)
        name = Path(f.f_code.co_filename).resolve()
        try:
            rel = name.relative_to(_REPO).as_posix()
        except ValueError:
            rel = name.name
        return f"{rel}:{f.f_code.co_name}"
    except Exception:
        return "unknown:unknown"


def desk_alerts_path(ledger: Path = _LEDGER) -> Path:
    """Where the desk alert artifact lives for a given ledger: the repo artifact for the repo's
    own `data/alert_delivery.jsonl` (relative or rooted), else beside the ledger (tests, tools)."""
    if ledger == _LEDGER:
        return _DESK_ALERTS
    if ledger.name == _LEDGER.name and ledger.parent.name == "data":
        return ledger.parent.parent / _DESK_ALERTS
    return ledger.parent / _DESK_ALERTS.name


def load_desk_alerts(path: Path = _DESK_ALERTS) -> dict[str, dict[str, Any]]:
    """The artifact's rows by key; absent or unreadable is empty (never raises)."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("alerts") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return {}
    return {str(r["key"]): r for r in rows if isinstance(r, dict) and "key" in r}


#: os.replace attempts on PermissionError (Windows: the target is open in a reader) and the pause
#: between them; the lock wait. A desk row is worth a short wait, never an unbounded one.
_REPLACE_TRIES = 20
_REPLACE_PAUSE_S = 0.05
_DESK_LOCK_WAIT_S = 10.0


def _desk_lock(path: Path) -> Path:
    """The sidecar the desk-alert read-modify-write is serialized on (never deleted; gitignored
    like everything under reports/)."""
    return path.with_name(f".{path.name}.lock")


def _write_desk_alerts(rows: dict[str, dict[str, Any]], path: Path) -> None:
    """Prune, then write through a UNIQUE temp name and a retried os.replace. Caller holds the
    lock. Raises on failure -- `_upsert_desk` turns that into a surfaced error, not silence."""
    floor = datetime.now(tz=UTC) - timedelta(days=_DESK_ALERT_KEEP_D)
    kept = []
    for r in rows.values():
        try:
            if datetime.fromisoformat(str(r.get("last_seen"))) < floor:
                continue
        except (ValueError, TypeError):
            continue
        kept.append(r)
    kept.sort(key=lambda r: str(r.get("last_seen")), reverse=True)
    doc = {"schema": "desk_alerts/1", "fresh_h": DESK_ALERT_FRESH_H, "alerts": kept}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        for attempt in range(_REPLACE_TRIES):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == _REPLACE_TRIES - 1:
                    raise
                time.sleep(_REPLACE_PAUSE_S)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _upsert_desk(path: Path, edit: Callable[[dict[str, dict[str, Any]]], bool]) -> str | None:
    """THE ONLY read-modify-write of the artifact: under a cross-process OS lock
    (libs.ops.alert_ledger.os_lock -- msvcrt/flock on a sidecar), so concurrent pagers cannot
    lose each other's rows or revive a row another process just cleared from a stale read
    (audit SF1: 8 procs x 25 keys had kept 60/200). `edit` mutates the rows and says whether
    anything changed. Never raises; returns the error text (None on success) so the caller can
    surface it -- a desk row that silently failed to land is a RED nobody sees."""
    try:
        from libs.ops.alert_ledger import os_lock
        with os_lock(_desk_lock(path), timeout_s=_DESK_LOCK_WAIT_S):
            rows = load_desk_alerts(path)
            if edit(rows):
                _write_desk_alerts(rows, path)
        return None
    except Exception as e:                      # never raises into the alert path
        err = f"desk alert write failed ({path.name}): {type(e).__name__}: {e}"[:_DETAIL_MAX]
        with contextlib.suppress(Exception):
            print(f"[alert_channels] {err}", file=sys.stderr)
        return err


def record_desk_alert(key: str, title: str, *, source: str = "", public_title: bool = False,
                      path: Path = _DESK_ALERTS) -> str | None:
    """Upsert one desk alert row (first_seen kept, last_seen refreshed). Never raises: a failed
    write must not kill the page that called it -- it RETURNS the error (None = written), which
    send_all ledgers and puts in its result. The artifact is PUBLISHED: no body is stored,
    the title is stored as its sha (exactly as the ledger does) and in clear only when the caller
    passes `public_title=True` for a title made of check names, never of values."""
    def edit(rows: dict[str, dict[str, Any]]) -> bool:
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        prev = rows.get(key, {})
        row: dict[str, Any] = {
            "key": key, "source": source or prev.get("source", ""),
            "title_sha": sha256(title.encode("utf-8", "ignore")).hexdigest()[:12],
            "first_seen": prev.get("first_seen", now), "last_seen": now}
        if public_title:
            row["title"] = title[:160]
        rows[key] = row
        return True
    return _upsert_desk(path, edit)


def clear_desk_alert(key: str, *, path: Path = _DESK_ALERTS) -> str | None:
    """Drop a resolved alert's row. Never raises; returns the error text, None on success."""
    return _upsert_desk(path, lambda rows: rows.pop(key, None) is not None)


def fresh_desk_alerts(*, path: Path = _DESK_ALERTS, hours: float = DESK_ALERT_FRESH_H,
                      now: datetime | None = None) -> list[dict[str, Any]]:
    """Rows seen inside the freshness window, newest first -- the ones that hold the desk RED."""
    floor = (now or datetime.now(tz=UTC)) - timedelta(hours=hours)
    out = []
    for r in load_desk_alerts(path).values():
        with contextlib.suppress(ValueError, TypeError):
            if datetime.fromisoformat(str(r.get("last_seen"))) >= floor:
                out.append(r)
    return sorted(out, key=lambda r: str(r.get("last_seen")), reverse=True)


def personal_channel_health(kind: str = "ntfy", *, ledger: Path = _LEDGER) -> dict[str, Any]:
    """Is a personal channel FAILING? Reads only real rows (routed ones prove nothing).

    stale = a real (non-routed) attempt FAILED after the channel's last real success (or with no
    success ever). Silence is NOT staleness: principal pages are rare by design, a quiet week is
    the normal state, and a RED the threads cannot clear without buzzing the owner is noise.
    `last_success` None means the ledger has never recorded one."""
    last_ok: str | None = None
    failed_after = False
    try:
        lines = ledger.read_text("utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        with contextlib.suppress(json.JSONDecodeError, AttributeError):
            row = json.loads(line)
            if row.get("channel") != kind or row.get("routed"):
                continue
            if row.get("ok"):
                last_ok, failed_after = str(row.get("ts")), False
            else:
                failed_after = True
    return {"channel": kind, "last_success": last_ok, "failed_since": failed_after,
            "stale": failed_after}


def ledger_tail(n: int = 20, *, ledger: Path = _LEDGER) -> list[dict[str, Any]]:
    try:
        lines = ledger.read_text("utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for line in lines:
        with contextlib.suppress(json.JSONDecodeError):
            out.append(json.loads(line))
    return out


def last_success_per_channel(*, ledger: Path = _LEDGER) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = ledger.read_text("utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        with contextlib.suppress(json.JSONDecodeError, KeyError):
            row = json.loads(line)
            # a routed row is a deliberate NON-send: it proves nothing about the channel's reach
            if row.get("ok") and not row.get("routed"):
                out[str(row["channel"])] = str(row["ts"])
    return out


def all_silent_since(hours: float = 24.0, *, ledger: Path = _LEDGER) -> bool:
    """True when NO channel has recorded a success inside the window.

    This is the condition the desk could not observe: the pager was dead 2026-07-11 -> 07-16 (five
    days) and again for 29h on 07-19, and in both cases the absence of delivery was invisible.
    Note what it is NOT: proof anyone READ the alert. Only an off-box watcher noticing the canary
    stopped arriving can prove that -- that is the healthchecks.io check of gap #17, deliberately
    not rebuilt here.
    """
    floor = datetime.now(tz=UTC) - timedelta(hours=hours)
    for ts in last_success_per_channel(ledger=ledger).values():
        with contextlib.suppress(ValueError):
            if datetime.fromisoformat(ts) >= floor:
                return False
    return True


def status(*, config: Path = _CONFIG, ledger: Path = _LEDGER) -> dict[str, Any]:
    channels = load_channels(config)
    return {"armed_kinds": [str(c.get("kind")) for c in channels],
            "armed": len(channels),
            "arming_owed": not channels,
            "last_success_per_channel": last_success_per_channel(ledger=ledger),
            "all_silent_24h": all_silent_since(24.0, ledger=ledger),
            "silent_flag_present": _SILENT_FLAG.exists(),
            "ledger_tail": ledger_tail(5, ledger=ledger)}
