"""THE FREE CHAIN: every zero-cost model the desk can reach, cloud first and local last.

WHY THIS EXISTS (principal, 2026-10-12, the owned 24/7 multi-lab research civilization):

    "Free quota exhaustion must NEVER stop the laboratory.
     Fallback: free cloud -> another free provider -> another free provider -> local model.
     The local research workers remain available continuously."

`libs.research.free_panel` rotates OpenRouter's free roster and `libs.ops.llm_seat` is the paid
escalation with its monthly cap. Both stop at the same wall: one provider. When OpenRouter's free
tier is exhausted or down, every research organ on the desk goes dark together. This module is the
rung below them, and it is the ONLY transport for the providers it names -- `proposer_seat._ask`
calls it after the free panel and before the paid seat, so every organ that already asks the seat
inherits the extra rungs with no change of its own.

WHAT "FREE" MEANS HERE, AND THE RULE THAT KEEPS IT TRUE:

    local        an OpenAI-compatible server on this machine (Ollama, llama.cpp, vLLM, LM Studio).
                 No key, no bill, no quota. Discovered from QUANT_LOCAL_LLM_URLS.
    model_free   a provider whose catalogue marks individual models free (OpenRouter ":free" and
                 zero-priced rows; Z.ai's *-flash models). Only those model ids are ever sent.
    account_free a provider whose free tier is the account itself (Groq, Gemini, Cerebras). A key
                 is used only within that provider's own daily request cap, held here as config
                 and never as a scientific constant -- quotas move, so they live in
                 `desks/mt5/data/llm_lab/providers.json` and the env, not in code.

Nothing here can spend: there is no paid provider in this module. Paid escalation stays where it
already lives (`llm_seat`, under QUANT_FREE_TIER=0 and its monthly cap), so a paid call can never
be introduced by adding a row to this chain.

KEYS COME FROM THE ENVIRONMENT ONLY and never appear in a return value, a log line or an artifact.
Official endpoints only; every request is a plain chat completion with a sanitized prompt that the
caller (`proposer_seat.build_prompt`) has already scanned.

RATE LIMITS ARE STATE, NOT ERRORS (free_panel's rule, kept): a 429 cools that provider/model for a
while and the chain moves on; the cooldown expires on its own.
"""
from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "desks" / "mt5" / "data" / "llm_lab" / "providers.json"
STATE = ROOT / "desks" / "mt5" / "data" / "llm_lab" / "free_chain_state.json"
UNMEASURED = "UNMEASURED"

#: Default cooldown after a rate limit, seconds. A busy minute is a moment, not a property.
COOLDOWN_S = 600
#: Cooldown after a hard failure (5xx, connection refused): longer, still finite.
FAIL_COOLDOWN_S = 1800
TIMEOUT_S = 120.0


@dataclass(frozen=True)
class Provider:
    """One OpenAI-compatible endpoint. `key_env` empty means no key (a local server)."""

    name: str
    base_url: str
    key_env: str = ""
    tier: str = "local"                         #: local | model_free | account_free
    models: tuple[str, ...] = ()                #: pinned ids; empty -> discovered
    free_pattern: tuple[str, ...] = ()          #: substrings a model id must carry (model_free)
    daily_cap: int = 0                          #: requests/day for account_free; 0 = no cap

    def key(self) -> str:
        return os.environ.get(self.key_env, "").strip() if self.key_env else ""

    def usable(self) -> bool:
        return self.tier == "local" or bool(self.key())


#: The defaults. Endpoints are each provider's own documented OpenAI-compatible base URL. The
#: config file and QUANT_LOCAL_LLM_URLS extend or override this list; they never have to edit code.
DEFAULTS: tuple[Provider, ...] = (
    Provider("openrouter_free", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
             "model_free", free_pattern=(":free",)),
    Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "account_free",
             daily_cap=900),
    Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
             "GEMINI_API_KEY", "account_free", daily_cap=200),
    Provider("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "account_free",
             daily_cap=900),
    Provider("zai_flash", "https://api.z.ai/api/paas/v4", "ZAI_API_KEY", "model_free",
             models=("glm-4.5-flash",), free_pattern=("flash",)),
    Provider("mistral_free", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "account_free",
             daily_cap=500),
)

#: Local servers tried when QUANT_LOCAL_LLM_URLS is unset: Ollama, then llama.cpp's server.
LOCAL_DEFAULT_URLS = ("http://127.0.0.1:11434/v1", "http://127.0.0.1:8080/v1")


def _now() -> float:
    return time.time()


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
        try:
            os.replace(tmp, path)
        except OSError:                                   # Windows read-only destination
            path.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
            tmp.unlink(missing_ok=True)
    except OSError:
        pass


def _local_providers() -> list[Provider]:
    raw = os.environ.get("QUANT_LOCAL_LLM_URLS")
    urls = [u.strip().rstrip("/") for u in raw.split(",")] if raw else list(LOCAL_DEFAULT_URLS)
    return [Provider(f"local{i}", u, "", "local") for i, u in enumerate(urls) if u]


def providers() -> list[Provider]:
    """Cloud free providers in chain order, then local servers. Config rows may add or replace.

    The config file is DATA a principal can edit: `{"providers": [{"name": ..., "base_url": ...,
    "key_env": ..., "tier": ..., "models": [...], "daily_cap": N, "disabled": false}]}`. A row with
    a tier outside {local, model_free, account_free} is ignored, so a paid endpoint cannot be
    slipped in through configuration.
    """
    by_name: dict[str, Provider] = {p.name: p for p in DEFAULTS}
    order = [p.name for p in DEFAULTS]
    cfg = _read_json(CONFIG) or {}
    for row in cfg.get("providers") or []:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        name = str(row["name"])
        if row.get("disabled"):
            by_name.pop(name, None)
            continue
        tier = str(row.get("tier") or "")
        if tier not in ("local", "model_free", "account_free") or not row.get("base_url"):
            continue
        by_name[name] = Provider(name, str(row["base_url"]).rstrip("/"),
                                 str(row.get("key_env") or ""), tier,
                                 tuple(str(m) for m in row.get("models") or ()),
                                 tuple(str(m) for m in row.get("free_pattern") or ()),
                                 int(row.get("daily_cap") or 0))
        if name not in order:
            order.append(name)
    cloud = [by_name[n] for n in order if n in by_name]
    return cloud + _local_providers()


# ------------------------------------------------------------------------------ state
@dataclass
class _State:
    doc: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> _State:
        d = _read_json(STATE)
        return cls(d if isinstance(d, dict) else {})

    def save(self) -> None:
        _write_json(STATE, self.doc)

    def cooled(self, key: str) -> bool:
        return float((self.doc.get("cooldown") or {}).get(key, 0)) > _now()

    def cool(self, key: str, seconds: float) -> None:
        self.doc.setdefault("cooldown", {})[key] = _now() + seconds

    def calls_today(self, provider: str) -> int:
        day = self.doc.get("calls") or {}
        return int((day.get(_today()) or {}).get(provider, 0))

    def count(self, provider: str, model: str, ok: bool) -> None:
        calls = self.doc.setdefault("calls", {})
        for stale in [d for d in calls if d != _today()]:
            calls.pop(stale, None)
        today = calls.setdefault(_today(), {})
        today[provider] = int(today.get(provider, 0)) + 1
        m = self.doc.setdefault("models", {}).setdefault(f"{provider}:{model}", {})
        m["calls"] = int(m.get("calls", 0)) + 1
        m["ok"] = int(m.get("ok", 0)) + int(ok)
        m["last"] = datetime.now(UTC).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------ transport
def _ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    bundle = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if bundle and Path(bundle).exists():
        ctx.load_verify_locations(bundle)
    return ctx


def _request(url: str, key: str, payload: dict[str, Any] | None, timeout: float
             ) -> tuple[dict[str, Any], str | None]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        ctx = _ctx() if url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read() or b"{}"), None
    except urllib.error.HTTPError as exc:
        return {}, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {}, f"{type(exc).__name__}"


def list_models(p: Provider, *, timeout: float = 10.0) -> tuple[list[str], str | None]:
    """The provider's own catalogue, filtered to what is FREE on it. Never raises.

    Pinned models win (a provider whose catalogue we must not trust to label price). A model_free
    provider keeps only ids carrying a free marker, or rows whose published price is zero.
    """
    if p.models:
        return list(p.models), None
    if not p.usable():
        return [], "no key in env"
    doc, err = _request(f"{p.base_url}/models", p.key(), None, timeout)
    if err:
        return [], err
    rows = doc.get("data") if isinstance(doc, dict) else None
    out: list[str] = []
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        mid = str(row["id"])
        if p.tier == "model_free":
            price = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
            zero = price and all(str(price.get(k, "1")) in ("0", "0.0") for k in
                                 ("prompt", "completion"))
            if not (any(f in mid for f in p.free_pattern) or zero):
                continue
        out.append(mid)
    return out, None


def _cheapest_capable(models: list[str]) -> list[str]:
    """Order a catalogue so instruction models come before embedders, guards and tiny models."""
    skip = ("embed", "whisper", "tts", "guard", "rerank", "moderation", "vision-only", "audio")
    keep = [m for m in models if not any(s in m.lower() for s in skip)]
    return keep or models


@dataclass(frozen=True)
class Reply:
    text: str
    provider: str
    model: str
    tier: str


class ChainExhausted(RuntimeError):
    pass


def chat(system: str, user: str, *, max_tokens: int = 1600, temperature: float = 0.9,
         timeout: float = TIMEOUT_S, model_hint: str = "",
         skip: tuple[str, ...] = ()) -> Reply:
    """One completion from the first free rung that answers. Raises ChainExhausted otherwise.

    `model_hint` ("provider:model") is tried FIRST when that provider is usable, which is how a
    caller pins independent labs to different models; it is a preference, never a requirement --
    an exhausted hint falls through to the rest of the chain rather than stopping the lab.
    """
    st = _State.load()
    deadline = _now() + max(1.0, float(timeout))
    tried: list[str] = []
    plan: list[tuple[Provider, str]] = []
    provs = [p for p in providers() if p.name not in skip and p.usable()]
    hint_p, _, hint_m = model_hint.partition(":")
    for p in provs:
        if (p.name == hint_p and hint_m and not st.cooled(p.name)
                and not (p.daily_cap and st.calls_today(p.name) >= p.daily_cap)):
            plan.append((p, hint_m))
    for p in provs:
        if p.daily_cap and st.calls_today(p.name) >= p.daily_cap:
            tried.append(f"{p.name}: daily cap {p.daily_cap}")
            continue
        if st.cooled(p.name):
            tried.append(f"{p.name}: cooling")
            continue
        models, err = list_models(p)
        if err and not models:
            st.cool(p.name, FAIL_COOLDOWN_S if p.tier != "local" else 120)
            tried.append(f"{p.name}: {err}")
            continue
        for m in _cheapest_capable(models)[:4]:
            plan.append((p, m))
    for p, m in plan:
        key = f"{p.name}:{m}"
        left = deadline - _now()
        if left < 2.0:
            tried.append("deadline reached")
            break
        if st.cooled(key):
            continue
        body = {"model": m, "max_tokens": max_tokens, "temperature": temperature,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}
        doc, err = _request(f"{p.base_url}/chat/completions", p.key(), body, left)
        if err:
            st.count(p.name, m, False)
            st.cool(key, COOLDOWN_S if err == "HTTP 429" else FAIL_COOLDOWN_S)
            if err in ("HTTP 401", "HTTP 403", "HTTP 402"):
                st.cool(p.name, FAIL_COOLDOWN_S * 4)     # a key problem is provider-wide
            tried.append(f"{key}: {err}")
            continue
        try:
            msg = doc["choices"][0]["message"]
            text = str(msg.get("content") or "").strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            text = ""
        st.count(p.name, m, bool(text))
        if not text:
            tried.append(f"{key}: empty completion")
            continue
        st.save()
        return Reply(text, p.name, m, p.tier)
    st.save()
    raise ChainExhausted("; ".join(tried[-8:]) or "no free provider is usable on this host")


def status() -> dict[str, Any]:
    """What the chain can reach, without a network call and without printing a key."""
    st = _State.load()
    rows = []
    for p in providers():
        rows.append({"name": p.name, "tier": p.tier, "usable": p.usable(),
                     "key_present": bool(p.key()) if p.key_env else None,
                     "calls_today": st.calls_today(p.name), "daily_cap": p.daily_cap,
                     "cooling": st.cooled(p.name)})
    usable = [r for r in rows if r["usable"] and r["tier"] != "local"]
    return {"providers": rows, "cloud_usable": len(usable),
            "verdict": "RAN" if usable else UNMEASURED,
            "why": ("" if usable else "no free cloud key in env; local servers are probed on call")}


def model_stats() -> dict[str, dict[str, Any]]:
    """Per provider:model call/ok counts the chain has recorded, for the lab's model registry."""
    return dict(_State.load().doc.get("models") or {})
