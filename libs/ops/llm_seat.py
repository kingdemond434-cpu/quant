"""THE SEAT. One key resolution and one call path for every external-model organ on this desk.

WHY THIS EXISTS, and it is the highest-leverage thing in this area rather than another organ.
Eleven organs on this desk are dark right now -- run_external_panel, strategic_director,
llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, collector_author, deep_review,
run_micro_audit, refresh_panel_roster, llm_blind_researcher -- and every one of them is dark for
the SAME reason: they each open `data/secrets/llm_panel.json`, that file does not exist, and not
one of them reads an environment variable. `run_discretionary_max` names this as lever 2 of five,
CROSS-FAMILY, and records it as "blocked on the OpenRouter seat"; `strategic_director` describes
itself as "activation-ready by construction" waiting on the same thing.

So the binding constraint was never eleven integrations. It was one credential with no env-var
route into the box. This module is that route: resolve a key from the environment FIRST and the
secrets file second, and every dark organ can light from a single exported variable -- which is
the same mechanism that just unblocked GitHub search, and a mechanism the principal already
operates.

WHY OPENAI IS A FIRST-CLASS PROVIDER HERE. The existing panel code is written against
OpenAI-COMPATIBLE `/chat/completions`, which is genuinely one code path for OpenRouter, xAI,
DeepSeek, Qwen, Mistral and OpenAI itself. But every default in the repo points at OpenRouter, so
an OpenAI key -- by far the easiest one for a principal to obtain -- had nowhere to go. It does
now, and it is the cross-family seat: an independent model FAMILY, which is the entire point of
lever 2. A second Anthropic seat would agree with the first for reasons that have nothing to do
with the market.

THE MODEL IS DISCOVERED, NOT HARDCODED. A pinned model string is a time bomb: it works until the
provider retires it, and then every organ fails with an error that reads like an outage. This asks
the provider what it serves and picks by preference order over what actually came back. Same
discipline as re-probing a source instead of trusting a recorded status.

SPEND IS CAPPED AND MEASURED, because this is wired to a daily cadence and a runaway loop against
a metered API is a real way to lose real money. Every call records its token usage; the month's
spend is checked BEFORE each call against a hard cap. The desk has already been burned by the
opposite design -- run_external_panel discovered credit exhaustion mid-run, after spending the
last of it on a verification panel that verified nothing (0/13 responded, all HTTP 402).
"""

from __future__ import annotations

import contextlib
import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
SECRETS = _ROOT / "data" / "secrets" / "llm_panel.json"
SPEND_LEDGER = _ROOT / "data" / "llm_spend.jsonl"

#: Environment variables consulted, in order. `OPENAI_API_KEY` is first because it is the one a
#: principal is most likely to already have, and because OpenAI is the cross-family seat the
#: discretionary ceiling-pusher has been asking for.
KEY_ENV_VARS: tuple[tuple[str, str, str], ...] = (
    ("OPENAI_API_KEY", "openai", "https://api.openai.com/v1"),
    ("OPENROUTER_API_KEY", "openrouter", "https://openrouter.ai/api/v1"),
    ("DEEPSEEK_API_KEY", "deepseek", "https://api.deepseek.com/v1"),
    ("XAI_API_KEY", "xai", "https://api.x.ai/v1"),
)

#: Preference order for model discovery, matched as SUBSTRINGS against whatever the provider
#: actually lists. Substrings rather than exact names because provider naming drifts constantly
#: and an exact match that misses would silently fall through to a weak model.
MODEL_PREFERENCE: tuple[str, ...] = (
    "gpt-5", "o4", "gpt-4.1", "o3", "gpt-4o", "deepseek-r", "grok-4", "grok-3",
)

#: Hard monthly ceiling in USD. Deliberately low: this is wired to a daily cadence, and the cost
#: of an over-cautious cap is a deferred run while the cost of no cap is unbounded. Raise it
#: through the environment when the spend is proven worth it, never by editing this line -- a cap
#: that gets edited upward whenever it binds is not a cap.
DEFAULT_MONTHLY_CAP_USD = 20.0

#: Rough blended $/1k tokens, used only to enforce the cap. Intentionally an OVER-estimate: the
#: two errors are not symmetric. Over-estimating defers a run by a cycle; under-estimating spends
#: money the principal did not agree to.
_USD_PER_1K_TOKENS = 0.02

_CTX: ssl.SSLContext | None = None


def _ctx() -> ssl.SSLContext:
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            _CTX = ssl.create_default_context()
    return _CTX


@dataclass(frozen=True)
class Seat:
    name: str
    base_url: str
    key: str
    model: str = ""
    source: str = ""

    @property
    def redacted(self) -> str:
        """For logs and reports. A key that reaches a log file is a leaked key."""
        return f"{self.name}:{self.model or '<undiscovered>'} (key {self.key[:6]}...)"


def seats() -> list[Seat]:
    """Every seat this box can reach, environment first, secrets file second.

    ENVIRONMENT FIRST IS THE WHOLE POINT. The secrets file has to be written onto a box that gets
    reclaimed; an exported variable is set once in the environment config and survives every
    container the desk is ever given.
    """
    out: list[Seat] = []
    for var, name, base in KEY_ENV_VARS:
        key = os.environ.get(var, "").strip()
        if key:
            out.append(Seat(name=name, base_url=os.environ.get(f"{name.upper()}_BASE_URL", base),
                            key=key, model=os.environ.get(f"{name.upper()}_MODEL", ""),
                            source=f"env:{var}"))
    if SECRETS.exists():
        try:
            cfg = json.loads(SECRETS.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
        for p in cfg.get("providers") or []:
            key = str(p.get("key") or "").strip()
            if not key:
                continue
            out.append(Seat(name=str(p.get("name") or "panel"),
                            base_url=str(p.get("base_url") or "https://openrouter.ai/api/v1"),
                            key=key, model=str(p.get("model") or ""), source="file:llm_panel.json"))
    return out


def primary_seat() -> Seat | None:
    """The seat organs should use when they want exactly one. None when the desk is dark."""
    got = seats()
    return got[0] if got else None


def discover_model(seat: Seat, *, timeout: float = 20.0) -> tuple[str, str | None]:
    """Ask the provider what it serves and pick by preference. Returns (model, error).

    A PINNED MODEL STRING IS A TIME BOMB. It works until the provider retires it and then every
    organ fails with something that reads like an outage rather than like a rename. An explicit
    `<NAME>_MODEL` environment variable still wins -- discovery is the default, not a override of
    the principal's choice.
    """
    if seat.model:
        return seat.model, None
    body, err = _get(f"{seat.base_url}/models", seat.key, timeout=timeout)
    if err:
        return "", err
    ids = [str(m.get("id") or "") for m in (body.get("data") or [])]
    ids = [i for i in ids if i]
    if not ids:
        return "", "provider listed no models"
    for want in MODEL_PREFERENCE:
        hits = sorted(i for i in ids if want in i)
        if hits:
            # Shortest match wins: "gpt-5" over "gpt-5-chat-latest-preview-0613". The bare name is
            # the provider's stable alias; the decorated ones are snapshots that get retired.
            return min(hits, key=len), None
    return "", (f"none of {MODEL_PREFERENCE} found among {len(ids)} listed models "
                f"(e.g. {', '.join(ids[:5])}) -- set <PROVIDER>_MODEL explicitly")


def month_spend_usd(now: datetime | None = None) -> float:
    """This calendar month's estimated spend, read from the append-only ledger."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m")
    total = 0.0
    if not SPEND_LEDGER.exists():
        return 0.0
    for line in SPEND_LEDGER.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("utc", "")).startswith(stamp):
            total += float(row.get("usd") or 0.0)
    return round(total, 4)


def monthly_cap_usd() -> float:
    raw = os.environ.get("LLM_MONTHLY_CAP_USD", "").strip()
    try:
        return float(raw) if raw else DEFAULT_MONTHLY_CAP_USD
    except ValueError:
        return DEFAULT_MONTHLY_CAP_USD


def chat(
    prompt: str, *, system: str = "", seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4,
) -> tuple[str, str | None]:
    """One completion. Returns (text, error) -- NEVER raises, so a cadenced organ survives it.

    The cap is checked BEFORE the call, not after. Checking after is how run_external_panel
    discovered exhaustion mid-run with nothing to show for the spend.
    """
    s = seat or primary_seat()
    if s is None:
        return "", ("no seat: export OPENAI_API_KEY (or OPENROUTER_API_KEY / DEEPSEEK_API_KEY / "
                    "XAI_API_KEY) in the environment, or write data/secrets/llm_panel.json")
    spent, cap = month_spend_usd(), monthly_cap_usd()
    if spent >= cap:
        return "", (f"monthly cap reached: ${spent:.2f} of ${cap:.2f}. Raise it with "
                    "$LLM_MONTHLY_CAP_USD if the spend is proven worth it.")
    model, err = discover_model(s)
    if err:
        return "", f"model discovery failed: {err}"

    msgs: list[dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    payload = json.dumps({"model": model, "messages": msgs,
                          "max_completion_tokens": int(max_tokens),
                          "temperature": float(temperature)}).encode()
    body, err = _post(f"{s.base_url}/chat/completions", s.key, payload, timeout=timeout)
    if err:
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body.get("usage") or {})
    return text, None


def status() -> dict[str, Any]:
    """What this box can actually reach, re-measured rather than assumed. For the doctor."""
    got = seats()
    out: dict[str, Any] = {
        "n_seats": len(got),
        "seats": [{"name": s.name, "source": s.source, "model": s.model or "<discover>"}
                  for s in got],
        "month_spend_usd": month_spend_usd(),
        "monthly_cap_usd": monthly_cap_usd(),
        "secrets_file_present": SECRETS.exists(),
    }
    if not got:
        out["blocker"] = (
            "DARK: no external-model seat. Eleven organs depend on this -- run_external_panel, "
            "strategic_director, llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, "
            "collector_author, deep_review, run_micro_audit, refresh_panel_roster, "
            "llm_blind_researcher -- and one exported OPENAI_API_KEY lights all of them.")
        return out
    model, err = discover_model(got[0])
    out["primary"] = got[0].name
    out["primary_model"] = model or None
    out["primary_error"] = err
    return out


# ------------------------------------------------------------------------------------ transport

def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost", "X-Title": "quant-desk"}


def _get(url: str, key: str, *, timeout: float) -> tuple[dict[str, Any], str | None]:
    req = urllib.request.Request(url, headers=_headers(key))
    return _send(req, timeout)


def _post(url: str, key: str, payload: bytes, *, timeout: float
          ) -> tuple[dict[str, Any], str | None]:
    req = urllib.request.Request(url, data=payload, headers=_headers(key), method="POST")
    return _send(req, timeout)


def _send(req: urllib.request.Request, timeout: float) -> tuple[dict[str, Any], str | None]:
    """HTTP errors carry their BODY into the message. A bare '400 Bad Request' from a model API
    is unactionable; the body says which parameter the provider rejected."""
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as fh:
            parsed: dict[str, Any] = json.loads(fh.read().decode("utf8", errors="ignore"))
            return parsed, None
    except urllib.error.HTTPError as exc:
        detail = ""
        # A failed body read must not mask the HTTP error itself -- the status code is the part
        # that is always actionable.
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf8", errors="ignore")[:300]
        return {}, f"HTTP {exc.code}: {detail or exc.reason}"
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:160]}"


def _record_spend(seat: Seat, model: str, usage: dict[str, Any]) -> None:
    """Append-only, and it records what the PROVIDER reported rather than what we guessed."""
    tok = int(usage.get("total_tokens") or 0)
    row = {"utc": datetime.now(UTC).isoformat(timespec="seconds"), "seat": seat.name,
           "model": model, "tokens": tok,
           "usd": round(tok / 1000.0 * _USD_PER_1K_TOKENS, 5)}
    try:
        SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SPEND_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass                          # a ledger write must never take down the organ
