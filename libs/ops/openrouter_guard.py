"""No OpenRouter request may name a paid model unless the principal switched paid on.

WHY A GUARD AT THE WIRE AND NOT A POLICY PER ORGAN (2026-10-13, principal: "will the 10 ever
burn"). Adding $10 of credit lifts OpenRouter's free-model allowance from 50 to 1,000 requests a
day, and it is also money every organ holding OPENROUTER_API_KEY could spend. The desk's free
tier was a default in `llm_seat` (QUANT_FREE_TIER), but it was not a wall:

- `llm_seat.discover_model` returned a pinned `<NAME>_MODEL` as-is, and `convert_swarm` pins one
  per lane;
- with no free id listed it fell through to the paid flagship;
- ten scripts post to `/chat/completions` themselves, with model ids from a secrets file.

None of those spends anything while the account holds no credit, and every one of them would
spend the day the credit lands. So the check sits on the request itself: every POST to an
openrouter.ai host goes through `refusal()` first, whatever built it.

THE RULE. Every model the body names (`model`, plus any `models` fallback list, which OpenRouter
also routes to) must end in `:free`. A router id such as `openrouter/auto` names no price and is
refused. The only way past is QUANT_LLM_LAB_PAID=1, set by the principal; nothing in the repo
sets it. Other providers' hosts are not this guard's business.

`tests/ops/test_openrouter_guard.py` fails if a file that posts to `/chat/completions` stops
calling it.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PAID_ENV = "QUANT_LLM_LAB_PAID"
FREE_SUFFIX = ":free"


class PaidModelRefused(RuntimeError):
    """Raised by `check` when a request would spend OpenRouter credit."""


def paid_allowed() -> bool:
    return os.environ.get(PAID_ENV, "0").strip() == "1"


def is_openrouter(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


def _models(body: Any) -> list[str]:
    if isinstance(body, (bytes, bytearray)):
        try:
            body = json.loads(bytes(body).decode("utf-8", errors="replace"))
        except (ValueError, TypeError):
            return [""]                    # unreadable body: cannot prove it free
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return [""]
    if not isinstance(body, dict):
        return [""]
    out = [str(body.get("model") or "")]
    extra = body.get("models")
    if isinstance(extra, list):
        out.extend(str(m or "") for m in extra)
    return out


def refusal(url: str, body: Any) -> str | None:
    """None when the request may go out; otherwise why it may not."""
    if not is_openrouter(url) or paid_allowed():
        return None
    if not (urlparse(url).path or "").rstrip("/").endswith(("/completions", "/responses",
                                                            "/embeddings")):
        return None                       # /models, /key, /credits read nothing billable
    bad = [m for m in _models(body) if not m.lower().endswith(FREE_SUFFIX)]
    if not bad:
        return None
    return (f"openrouter_guard: refused paid model {bad[0] or '<none>'!r}: only ids ending "
            f"{FREE_SUFFIX!r} may be called unless {PAID_ENV}=1")


def check(url: str, body: Any) -> None:
    """Raise PaidModelRefused if the request would spend credit."""
    why = refusal(url, body)
    if why:
        raise PaidModelRefused(why)


def check_request(req: Any) -> None:
    """`check` for a urllib.request.Request."""
    check(str(getattr(req, "full_url", "") or ""), getattr(req, "data", None))


#: THE ACCOUNT'S OWN DAILY FREE ALLOWANCE, ASKED FOR RATHER THAN ASSUMED. OpenRouter allows 50
#: free-model requests a day to an account that has never bought credit and 1,000 to one that has.
#: `GET /api/v1/key` says which this key is (`is_free_tier`) and, where published, the counter
#: itself (`free_model_daily_requests`). Read once an hour and cached, so the day $10 lands every
#: budget that reads this scales from 50 to 1,000 with no edit.
KEY_INFO = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "llm_lab" \
    / "openrouter_key.json"
KEY_URL = "https://openrouter.ai/api/v1/key"
FREE_TIER_DAILY = 50
CREDITED_DAILY = 1000
KEY_INFO_TTL_S = 3600
#: The suite's conftests set this False (and KEY_INFO to tmp), so no test reads the box's file or
#: spends a request.
NETWORK = True


def _parse_key_info(body: dict[str, Any]) -> dict[str, Any]:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    quota = data.get("free_model_daily_requests")
    if isinstance(quota, dict) and quota.get("limit") is not None:
        try:
            out["daily_limit"] = int(quota["limit"])
            out["limit_source"] = "free_model_daily_requests"
        except (TypeError, ValueError):
            pass
        for k in ("used", "remaining"):
            if quota.get(k) is not None:
                with contextlib.suppress(TypeError, ValueError):
                    out[k] = int(quota[k])
    if "daily_limit" not in out and isinstance(data.get("is_free_tier"), bool):
        out["daily_limit"] = FREE_TIER_DAILY if data["is_free_tier"] else CREDITED_DAILY
        out["limit_source"] = "is_free_tier"
    if isinstance(data.get("is_free_tier"), bool):
        out["is_free_tier"] = data["is_free_tier"]
    # The key's CREDIT limit (null = no limit). $0 is the principal's backstop: a key with a
    # zero credit limit cannot spend even if this guard were bypassed.
    out["credit_limit_usd"] = data.get("limit")
    if data.get("usage") is not None:
        out["usage_usd"] = data.get("usage")
    return out


def key_info(*, refresh: bool = False, timeout: float = 15.0, fetch: Any = None,
             now: float | None = None, cached_only: bool = False) -> dict[str, Any]:
    """The key's limits, cached for an hour. `{}` when unreachable: UNMEASURED, never a zero.

    `cached_only` reads the file and never touches the network: budget checks on every call use
    it, and the lab pass refreshes the file once an hour.
    """
    t = time.time() if now is None else now
    cached: dict[str, Any] = {}
    with contextlib.suppress(OSError, ValueError):
        cached = json.loads(KEY_INFO.read_text("utf-8"))
    if cached_only:
        # A day-old reading is still the right class of account; older than that, UNMEASURED.
        fresh = isinstance(cached, dict) and t - float(cached.get("fetched_at", 0) or 0) < 86400
        return cached if fresh else {}
    if (not refresh and isinstance(cached, dict) and cached.get("daily_limit")
            and t - float(cached.get("fetched_at", 0)) < KEY_INFO_TTL_S):
        return cached
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if fetch is None and (not key or not NETWORK):
        return cached if isinstance(cached, dict) else {}
    try:
        if fetch is not None:
            body = fetch(KEY_URL)
        else:
            req = urllib.request.Request(KEY_URL, headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read() or b"{}")
    except Exception:                                  # never raises
        return cached if isinstance(cached, dict) else {}
    out = _parse_key_info(body if isinstance(body, dict) else {})
    if not out.get("daily_limit"):
        return cached if isinstance(cached, dict) else {}
    out["fetched_at"] = t
    with contextlib.suppress(OSError):
        KEY_INFO.parent.mkdir(parents=True, exist_ok=True)
        KEY_INFO.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def daily_limit(**kw: Any) -> int | None:
    """OpenRouter's free requests per day for this key, or None when UNMEASURED."""
    raw = key_info(**kw).get("daily_limit")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None
