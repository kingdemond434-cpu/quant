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
import smtplib
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from hashlib import sha256
from pathlib import Path
from typing import Any

_CONFIG = Path("data/secrets/alert_channels.json")
_LEDGER = Path("data/alert_delivery.jsonl")
_SILENT_FLAG = Path("data/ALERT_CHANNELS_SILENT")

_TIMEOUT = 12.0
_KINDS = ("ntfy", "telegram", "webhook", "email")


def _log(channel: str, ok: bool, detail: str, title: str, ledger: Path = _LEDGER) -> None:
    """One row per attempt. The title is HASHED, never stored: alert bodies can name positions,
    and a delivery ledger is not a place to leak book state."""
    with contextlib.suppress(OSError):
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(tz=UTC).isoformat(), "channel": channel, "ok": ok,
               "detail": detail[:200],
               "title_sha": sha256(title.encode("utf-8", "ignore")).hexdigest()[:12]}
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


_SENDERS = {"ntfy": _send_ntfy, "telegram": _send_telegram,
            "webhook": _send_webhook, "email": _send_email}


def send_all(title: str, body: str, *, config: Path = _CONFIG,
             ledger: Path = _LEDGER) -> dict[str, Any]:
    """Fire EVERY armed channel; one channel's failure can never stop another's.

    Returns {"armed": n, "delivered": n, "results": [...]}. When nothing is armed the result says
    so and a row is written -- an unarmed pager is a recorded state, not silence.
    """
    channels = load_channels(config)
    if not channels:
        _log("none", False, "NOT-ARMED: data/secrets/alert_channels.json absent or empty",
             title, ledger)
        return {"armed": 0, "delivered": 0, "results": [],
                "note": "second-channel arming is a HUMAN step: drop credentials at "
                        "data/secrets/alert_channels.json on the box"}
    results = []
    for cfg in channels:
        kind = str(cfg.get("kind"))
        try:
            detail = _SENDERS[kind](cfg, title, body)
            ok = True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError,
                smtplib.SMTPException, ValueError) as e:
            ok, detail = False, f"{type(e).__name__}: {e}"[:200]
        _log(kind, ok, detail, title, ledger)
        results.append({"channel": kind, "ok": ok, "detail": detail})
    return {"armed": len(channels), "delivered": sum(1 for r in results if r["ok"]),
            "results": results}


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
            if row.get("ok"):
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
