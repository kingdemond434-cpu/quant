"""A SECOND FREE ALLOWANCE FOR THE BRAIN: GitHub Models, used only after OpenRouter's is gone.

WHY (2026-10-29, hourly pass 21). MT5-Deepening stood down every pass at "0 free request(s) left
today of a 519 ceiling" with 146 rows waiting. OpenRouter's free allowance is per ACCOUNT, so
adding more `:free` models buys nothing. The box already holds a GitHub token, and GitHub Models
serves chat models on a free allowance that is counted per MODEL per day, so each listed model
is a separate budget.

WHAT IT IS NOT.
  * Not a paid route. The free allowance is the only thing used; a refused call is recorded and
    the model is left alone until the UTC day rolls. Paid usage on GitHub Models has to be
    switched on by the account owner, and nothing here asks for it.
  * Not a second registry or scheduler. It is a seat, attributed in the same spend ledger under
    seat `github_models`, and `llm_seat.calls_today()` leaves its rows out of OpenRouter's count.
  * Not a key store. The token is read from the environment or the existing `~/.gh_token`
    fallback, never written, logged or put in a prompt. Prompts carry public source text only.

UNMEASURED UNTIL THE BOX CALLS IT. Whether the token carries the models scope is learned from
the first answer: a 401 or 403 marks the seat refused for the day, which reads as 0 budget left.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import llm_seat, openrouter_guard

NAME = "github_models"
BASE = "https://models.github.ai/inference"
CATALOG = "https://models.github.ai/catalog/models"
TOKEN_ENVS = ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN")
TOKEN_FILE = "~/.gh_token"  # noqa: S105 -- dotfile PATH, not a credential
STATE = llm_seat._ROOT / "data" / "llm_overflow_state.json"

#: Requests per model per day on the free allowance, by the catalog's `rate_limit_tier`. These
#: are the published free-account figures and only size the estimate: a 429 is the truth and
#: closes the model for the day whatever this table says.
TIER_DAILY = {"low": 150, "high": 50}

#: A 429 whose body names the day closes the model until UTC midnight; any other 429 is a burst
#: and only moves to the next model.
_DAILY = re.compile(r"per\s*day|perday|daily|UserByModelByDay", re.I)


def _today(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def token() -> str:
    for var in TOKEN_ENVS:
        got = os.environ.get(var, "").strip()
        if got:
            return got
    path = Path(TOKEN_FILE).expanduser()
    with contextlib.suppress(OSError):
        return path.read_text("utf-8").strip()
    return ""


def seat() -> llm_seat.Seat | None:
    key = token()
    return llm_seat.Seat(name=NAME, base_url=BASE, key=key, source="env:github") if key else None


def _state(now: datetime | None = None) -> dict[str, Any]:
    """Today's state. A file from another day is stale by construction and starts fresh,
    except the catalog, which is kept so a new day does not have to re-list."""
    try:
        doc = json.loads(STATE.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    if doc.get("date") != _today(now):
        doc = {"date": _today(now), "catalog": doc.get("catalog") or [],
               "exhausted": {}, "calls": {}, "refused": None}
    return doc


def _save(doc: dict[str, Any]) -> None:
    with contextlib.suppress(OSError):
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, STATE)


def catalog(s: llm_seat.Seat, doc: dict[str, Any], *, timeout: float = 20.0
            ) -> list[dict[str, Any]]:
    """[{id, tier}] of free-allowance chat models, low tier first (it has the larger budget)."""
    if doc.get("catalog"):
        return list(doc["catalog"])
    body, err = llm_seat._get(CATALOG, s.key, timeout=timeout)
    if err:
        return []
    rows = body if isinstance(body, list) else body.get("data") or []
    out = []
    for m in rows if isinstance(rows, list) else []:
        if not isinstance(m, dict):
            continue
        tier = str(m.get("rate_limit_tier") or "")
        mods = m.get("supported_output_modalities") or ["text"]
        if tier in TIER_DAILY and "text" in mods and m.get("id"):
            out.append({"id": str(m["id"]), "tier": tier})
    out.sort(key=lambda r: (-TIER_DAILY[r["tier"]], r["id"]))
    doc["catalog"] = out
    _save(doc)
    return out


def budget_left(now: datetime | None = None) -> int:
    """Requests the free overflow still has today. 0 when there is no token or it was refused;
    -1 when UNMEASURED (no catalog read yet), which callers treat as worth one try."""
    if seat() is None:
        return 0
    doc = _state(now)
    if doc.get("refused"):
        return 0
    cat = doc.get("catalog") or []
    if not cat:
        return -1
    calls = doc.get("calls") or {}
    return sum(max(0, TIER_DAILY[m["tier"]] - int(calls.get(m["id"]) or 0))
               for m in cat if m["id"] not in (doc.get("exhausted") or {}))


def chat(prompt: str, *, system: str = "", max_tokens: int = 3000, temperature: float = 0.0,
         timeout: float = 240.0) -> tuple[str, str | None]:
    """One completion from the first GitHub model with allowance left. Never raises."""
    s = seat()
    if s is None:
        return "", "no overflow seat: no GitHub token on this host"
    doc = _state()
    if doc.get("refused"):
        return "", f"free overflow refused for today (per-day): {doc['refused']}"
    url = f"{BASE}/chat/completions"
    # Not an OpenRouter host, so the paid-id guard has nothing to refuse; asserted so a base URL
    # change that points this at OpenRouter cannot skip it.
    if why := openrouter_guard.refusal(url, {"model": "github-models"}):
        return "", why
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}]
    for m in catalog(s, doc):
        mid = m["id"]
        if mid in doc["exhausted"]:
            continue
        req = {"model": mid, "messages": msgs, "max_tokens": int(max_tokens),
               "temperature": float(temperature)}
        body, err = llm_seat._post_with_degrade(url, s.key, req, timeout=timeout)
        doc["calls"][mid] = int(doc["calls"].get(mid) or 0) + 1
        if err:
            if err.startswith(("HTTP 401", "HTTP 403")):
                doc["refused"] = err[:160]
                _save(doc)
                return "", f"free overflow refused for today (per-day): {err[:160]}"
            if err.startswith("HTTP 429") and _DAILY.search(err):
                doc["exhausted"][mid] = datetime.now(UTC).isoformat(timespec="seconds")
            _save(doc)
            continue
        _save(doc)
        try:
            text = str(body["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError):
            continue
        llm_seat._record_spend(s, mid, body, free=True)
        return text, None
    _save(doc)
    return "", "free overflow exhausted for today (per-day): every GitHub model refused or spent"


def chat_with_overflow(prompt: str, **kw: Any) -> tuple[str, str | None]:
    """`llm_seat.chat`, and the GitHub overflow only when OpenRouter's DAY is gone."""
    text, err = llm_seat.chat(prompt, **kw)
    day_gone = "budget exhausted" in (err or "") or (
        "429" in (err or "") and llm_seat._is_daily_free_refusal(err or ""))
    if day_gone:
        return chat(prompt, system=str(kw.get("system") or ""),
                    max_tokens=int(kw.get("max_tokens") or 3000),
                    temperature=float(kw.get("temperature") or 0.0))
    return text, err
