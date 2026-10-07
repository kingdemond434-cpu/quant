"""The OpenRouter FREE-model seat: every ":free" model, rotated, batched, rate-limited, 24/7.

    POST https://openrouter.ai/api/v1/chat/completions      (OpenAI-compatible)
    GET  https://openrouter.ai/api/v1/models                 (the free list: pricing prompt == "0")
    GET  https://openrouter.ai/api/v1/key                    (the account's REAL remaining quota)

WHY (principal 2026-09-30: "the deepening seat runs on OpenRouter's free models, 24/7"). The
deepening worker had one seat resolution -- `llm_seat.primary_seat()` -- and one model per call,
so a day's free allowance (about 50 requests without purchased credit, about 1,000 with >= $10 of
credit; ~20 requests a minute either way) decided at most that many ROWS a day. This module
multiplies rows per request by BATCHING (10-25 rows per call, one JSON array back, validated per
row against that row's own text) and keeps the seat alive by ROTATING across every free model:
a 429 or a 404 on one model moves to the next, a 5xx backs off exponentially with jitter.

NEVER ASSUME THE CAP. The daily ceiling is read from `GET /api/v1/key` (`limit_remaining`,
`is_free_tier`, `rate_limit`) where the account exposes it; the desk's own spend ledger
(`llm_seat.calls_today`) and the ceiling a 429 taught it (`llm_seat.observed_free_ceiling`) bound
it from below. An unreadable quota is UNMEASURED and the seat runs until the provider says no.

KEYS ARE NAMES HERE, NEVER VALUES. The key is resolved from `OPENROUTER_API_KEY` first, then from
`data/secrets/llm_panel.json` / `llm_panel_free.json` provider entries whose base URL is
openrouter.ai. It is handed to the HTTP header and nowhere else; every artifact records only the
SOURCE NAME (`env:OPENROUTER_API_KEY`, `file:llm_panel.json:<provider name>`).

THE CURSOR SURVIVES A CRASH. The model rotation index, today's request/row/429 counts and the
per-model success table are persisted after every request (`STATE`), so a killed pass resumes on
the model it was using with the day's counts intact.
"""
from __future__ import annotations

import contextlib
import json
import os
import random
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://openrouter.ai/api/v1"
ENV_VAR = "OPENROUTER_API_KEY"
PANELS: tuple[Path, ...] = (_ROOT / "data" / "secrets" / "llm_panel.json",
                            _ROOT / "data" / "secrets" / "llm_panel_free.json")
DESK = _ROOT / "desks" / "mt5"
#: The daily free-model list, cached so /models is asked once a day.
MODELS_CACHE = DESK / "logs" / "openrouter_free_models.json"
#: The persisted cursor: rotation index, today's counts, per-model success.
STATE = DESK / "data" / "hypotheses" / "openrouter_seat_state.json"
#: The published artifact (requests/day, rows/day, per-model success, 429s, quota remaining).
REPORT = DESK / "reports" / "OPENROUTER_FREE_SEAT.json"

#: Shipped so a failed /models read never leaves the seat with nothing to call. Rotation order;
#: the live /models list (when readable) replaces it for the day.
FALLBACK_FREE_MODELS: tuple[str, ...] = (
    "deepseek/deepseek-chat-v3.1:free",
    "deepseek/deepseek-r1:free",
    "moonshotai/kimi-k2:free",
    "qwen/qwen3-235b-a22b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "z-ai/glm-4.5-air:free",
    "openai/gpt-oss-20b:free",
    "nousresearch/deephermes-3-llama-3-8b-preview:free",
)

#: Free models allow roughly 20 requests a minute; the spacing keeps the seat under it.
REQUESTS_PER_MIN = float(os.environ.get("OPENROUTER_FREE_RPM", "20"))
#: Retries per request on 429/5xx before the request is given up for this pass.
MAX_RETRIES = int(os.environ.get("OPENROUTER_FREE_RETRIES", "4"))
BACKOFF_BASE_S = float(os.environ.get("OPENROUTER_FREE_BACKOFF_S", "2.0"))
BACKOFF_CAP_S = 60.0

_LOCK = threading.Lock()
_LAST_REQUEST = [0.0]


def _today(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=UTC)).strftime("%Y-%m-%d")


def resolve_key(env: dict[str, str] | None = None,
                panels: tuple[Path, ...] | None = None) -> tuple[str, str]:
    """(key, source NAME). Environment first, then an openrouter entry in either panel file.

    ("", "") when no seat is configured. The key is never logged; callers record the source."""
    e = os.environ if env is None else env
    key = str(e.get(ENV_VAR, "")).strip()
    if key:
        return key, f"env:{ENV_VAR}"
    for path in (panels or PANELS):
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for p in (doc.get("providers") if isinstance(doc, dict) else None) or []:
            if not isinstance(p, dict):
                continue
            base = str(p.get("base_url") or "")
            name = str(p.get("name") or "")
            if ("openrouter.ai" in base or "openrouter" in name.lower()) and p.get("key"):
                return str(p["key"]).strip(), f"file:{path.name}:{name or 'openrouter'}"
    return "", ""


def _get(url: str, key: str, timeout: float = 20.0) -> tuple[dict[str, Any], str | None]:
    from libs.ops import llm_seat
    return llm_seat._get(url, key, timeout=timeout)


def _post(url: str, key: str, req: dict[str, Any], timeout: float = 180.0
          ) -> tuple[dict[str, Any], str | None]:
    from libs.ops import llm_seat
    return llm_seat._post_with_degrade(url, key, req, timeout=timeout)


def free_models(key: str = "", *, now: datetime | None = None,
                get: Callable[..., tuple[dict[str, Any], str | None]] | None = None,
                cache: Path | None = None) -> tuple[list[str], str]:
    """(free model ids in rotation order, basis). Cached per UTC day; the shipped list is the
    floor when /models cannot be read, and the basis says which one this is."""
    path = cache or MODELS_CACHE
    day = _today(now)
    with contextlib.suppress(OSError, ValueError, AttributeError):
        doc = json.loads(path.read_text("utf-8"))
        if doc.get("date") == day and doc.get("models"):
            return list(doc["models"]), f"cache:{day}"
    body, err = (get or _get)(f"{BASE_URL}/models", key)
    models: list[str] = []
    if not err:
        for m in body.get("data") or []:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "")
            pr = m.get("pricing") or {}
            if mid and (str(pr.get("prompt")) in ("0", "0.0") or mid.endswith(":free")) \
                    and str(pr.get("completion", "0")) in ("0", "0.0"):
                models.append(mid)
    if not models:
        return list(FALLBACK_FREE_MODELS), f"fallback: /models unreadable ({err or 'no free ids'})"
    # Larger context first is a cheap proxy for the flagship end of the free list.
    ctx = {str(m.get("id")): int(m.get("context_length") or 0)
           for m in body.get("data") or [] if isinstance(m, dict)}
    models.sort(key=lambda mid: (-ctx.get(mid, 0), mid))
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"date": day, "models": models,
                                    "basis": "GET /api/v1/models, pricing prompt == 0"},
                                   indent=1), "utf-8")
    return models, f"live:{day}"


def quota(key: str, *, get: Callable[..., tuple[dict[str, Any], str | None]] | None = None
          ) -> dict[str, Any]:
    """The account's real remaining quota from GET /api/v1/key (then /auth/key). UNMEASURED when
    neither answers -- never an assumed number."""
    g = get or _get
    for path in ("/key", "/auth/key"):
        body, err = g(f"{BASE_URL}{path}", key)
        if err:
            continue
        raw = body.get("data")
        d: dict[str, Any] = raw if isinstance(raw, dict) else body
        return {"status": "MEASURED", "endpoint": path,
                "limit": d.get("limit"), "limit_remaining": d.get("limit_remaining"),
                "usage": d.get("usage"), "is_free_tier": d.get("is_free_tier"),
                "rate_limit": d.get("rate_limit")}
    return {"status": "UNMEASURED", "why": "GET /api/v1/key and /auth/key both failed"}


def daily_request_ceiling(q: dict[str, Any]) -> tuple[int | None, str]:
    """The day's free-request ceiling as far as it is KNOWN: the provider's published tier from
    /key (`is_free_tier` true = no purchased credit), bounded by what a 429 taught the desk
    today. None when nothing is known -- the seat then runs until the provider refuses."""
    ceiling: int | None = None
    basis = "UNMEASURED: /key unreadable and no refusal observed today"
    if q.get("status") == "MEASURED" and q.get("is_free_tier") is not None:
        ceiling = 50 if q.get("is_free_tier") else 1000
        basis = (f"/key is_free_tier={q.get('is_free_tier')}: OpenRouter's published free-model "
                 f"ceiling for this account class")
    with contextlib.suppress(Exception):
        from libs.ops.llm_seat import observed_free_ceiling
        seen = observed_free_ceiling()
        if seen is not None and (ceiling is None or seen < ceiling):
            ceiling, basis = seen, "a 429 today refused at this count (llm_seat.FREE_CEILING)"
    return ceiling, basis


# ------------------------------------------------------------------------------------ state
def load_state(path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    p = path or STATE
    try:
        st = json.loads(p.read_text("utf-8"))
        if not isinstance(st, dict):
            st = {}
    except (OSError, ValueError):
        st = {}
    day = _today(now)
    if st.get("date") != day:
        hist = list(st.get("history") or [])[-30:]
        if st.get("date"):
            hist.append({k: st.get(k) for k in ("date", "requests", "rows_sent", "rows_served",
                                                "rate_limited", "errors")})
        st = {"date": day, "requests": 0, "rows_sent": 0, "rows_served": 0, "rate_limited": 0,
              "errors": 0, "model_index": int(st.get("model_index") or 0),
              "per_model": {}, "history": hist}
    return st


def save_state(st: dict[str, Any], path: Path | None = None) -> None:
    p = path or STATE
    with contextlib.suppress(OSError):
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, indent=1), "utf-8")
        os.replace(tmp, p)


def _status(err: str) -> int:
    if err.startswith("HTTP "):
        with contextlib.suppress(ValueError):
            return int(err[5:8])
    return 0


def _backoff(tries: int) -> float:
    """Exponential backoff with full jitter (0.5x-1.5x), capped."""
    jitter = 0.5 + random.random()  # noqa: S311 -- scheduling jitter, not cryptography
    return float(min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** min(tries, 6)) * jitter))


def _pace(rpm: float) -> None:
    gap = 60.0 / max(1e-6, rpm)
    with _LOCK:
        wait = _LAST_REQUEST[0] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST[0] = time.monotonic()


def complete(messages: list[dict[str, str]], *, key: str, models: list[str],
             state: dict[str, Any], max_tokens: int = 6000, temperature: float = 0.0,
             post: Callable[..., tuple[dict[str, Any], str | None]] | None = None,
             sleep: Callable[[float], None] = time.sleep, rpm: float | None = None,
             state_path: Path | None = None) -> tuple[str, str, str | None]:
    """One chat completion on the free rotation: (text, model, error).

    429 or 404 -> the next free model (a 429 on the DAY's allowance ends the attempt: every free
    model shares the account's daily cap); 5xx / transport error -> exponential backoff with
    jitter on the same model. The cursor and the day's counts are saved after every request.
    """
    if not models:
        return "", "", "no free model to call"
    p = post or _post
    tries = 0
    last = ""
    while tries <= MAX_RETRIES + len(models):
        idx = int(state.get("model_index") or 0) % len(models)
        model = models[idx]
        if post is None:
            _pace(rpm or REQUESTS_PER_MIN)
        body, err = p(f"{BASE_URL}/chat/completions", key,
                      {"model": model, "messages": messages, "max_tokens": int(max_tokens),
                       "temperature": float(temperature)})
        state["requests"] = int(state.get("requests") or 0) + 1
        pm = state.setdefault("per_model", {}).setdefault(model, {"ok": 0, "fail": 0,
                                                                  "rate_limited": 0})
        if not err:
            try:
                text = str(body["choices"][0]["message"]["content"] or "")
            except (KeyError, IndexError, TypeError):
                text, err = "", f"unparseable response: {json.dumps(body)[:160]}"
            if not err:
                pm["ok"] += 1
                save_state(state, state_path)
                with contextlib.suppress(Exception):
                    from libs.ops import llm_seat
                    llm_seat._record_spend(llm_seat.Seat(name="openrouter_free",
                                                         base_url=BASE_URL, key="", model=model),
                                           model, body.get("usage") or {})
                return text, model, None
        pm["fail"] += 1
        last = str(err)
        code = _status(last)
        tries += 1
        if code == 429:
            state["rate_limited"] = int(state.get("rate_limited") or 0) + 1
            pm["rate_limited"] += 1
            daily = False
            with contextlib.suppress(Exception):
                from libs.ops.llm_seat import _is_daily_free_refusal, note_free_limit_hit
                daily = _is_daily_free_refusal(last)
                if daily:
                    note_free_limit_hit(last)
            state["model_index"] = idx + 1
            save_state(state, state_path)
            if daily:
                return "", model, f"daily free allowance refused: {last}"
            sleep(_backoff(tries))
            continue
        if code == 404 or code == 400:
            state["model_index"] = idx + 1              # the model is gone or refuses the shape
            save_state(state, state_path)
            continue
        state["errors"] = int(state.get("errors") or 0) + 1
        save_state(state, state_path)
        if code in (401, 402, 403):
            return "", model, last                      # the credential, not the model
        sleep(_backoff(tries))
    return "", "", f"retries exhausted: {last}"


def publish(state: dict[str, Any], *, q: dict[str, Any], models_basis: str, n_models: int,
            batch_size: int, key_source: str, ceiling: int | None, ceiling_basis: str,
            blocked_backlog: int | None = None, path: Path | None = None) -> dict[str, Any]:
    """The artifact: today's requests, rows, per-model success, 429s, quota, and the projection
    of rows/day at 50 and 1,000 requests at the measured batch size."""
    req = int(state.get("requests") or 0)
    sent = int(state.get("rows_sent") or 0)
    ok_calls = sum(int(v.get("ok") or 0) for v in (state.get("per_model") or {}).values())
    measured_batch = round(sent / ok_calls, 2) if ok_calls else None
    b = measured_batch or float(batch_size)
    proj = {str(n): {"rows_per_day": int(n * b),
                     "days_to_clear_backlog": (round(blocked_backlog / (n * b), 2)
                                               if blocked_backlog else None)}
            for n in (50, 1000)}
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "date": state.get("date"),
           "key_source": key_source or "NONE", "requests_today": req, "rows_sent_today": sent,
           "rows_served_today": int(state.get("rows_served") or 0),
           "rate_limited_429_today": int(state.get("rate_limited") or 0),
           "errors_today": int(state.get("errors") or 0),
           "per_model": state.get("per_model") or {}, "model_index": state.get("model_index"),
           "free_models": n_models, "free_models_basis": models_basis,
           "quota": q, "daily_request_ceiling": ceiling, "ceiling_basis": ceiling_basis,
           "batch_size_configured": batch_size, "batch_size_measured": measured_batch,
           "projection": proj, "projection_basis": (
               f"rows/day = requests/day x {b} rows per request "
               + ("(measured today)" if measured_batch else "(configured; none measured yet)")),
           "blocked_backlog": blocked_backlog, "history": state.get("history") or []}
    p = path or REPORT
    with contextlib.suppress(OSError):
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        os.replace(tmp, p)
    return doc
