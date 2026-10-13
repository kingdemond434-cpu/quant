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

import dataclasses
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import openrouter_guard

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
    """One OpenAI-compatible endpoint. `key_env` empty means no key (a local server).

    `base_url` may carry `{ENV_VAR}` placeholders (Cloudflare puts the account id in the path);
    an unset placeholder makes the provider unusable, never a request to a half-built URL.

    `terms` is the desk's terms gate for the provider, and it FAILS CLOSED: only "confirmed" is
    used. `terms_url` is the provider's own published free-tier terms, so whoever flips a row
    in `providers.json` can read what they are confirming.
    """

    name: str
    base_url: str
    key_env: str = ""
    tier: str = "local"                         #: local | model_free | account_free
    models: tuple[str, ...] = ()                #: pinned ids; empty -> discovered
    free_pattern: tuple[str, ...] = ()          #: substrings a model id must carry (model_free)
    daily_cap: int = 0                          #: requests/day for account_free; 0 = no cap
    terms: str = "confirmed"                    #: confirmed | to_confirm | refused
    terms_url: str = ""
    open_weights: bool = True                   #: serves open-weight models (Llama, Qwen, ...)
    #: ACCOUNT-TIER PROVIDERS ARE CLOSED UNTIL THE PRINCIPAL SAYS THE ACCOUNT IS FREE-ONLY (audit
    #: must-fix 6, 2026-10-13). Whether a Groq/Cerebras/Cloudflare/HF/Mistral/Gemini call is free
    #: depends on that account's billing, which no code here can see, and a daily cap counts
    #: requests, not money. Opened per provider by `"free_only_account": true` in providers.json
    #: or by naming it in QUANT_FREE_ONLY_ACCOUNTS (comma list, or "all").
    free_only_account: bool = False

    def key(self) -> str:
        return os.environ.get(self.key_env, "").strip() if self.key_env else ""

    def url(self) -> str:
        """The base URL with its `{ENV}` placeholders filled, or "" when one is unset."""
        out = self.base_url
        for var in re.findall(r"\{([A-Z0-9_]+)\}", self.base_url):
            val = os.environ.get(var, "").strip()
            if not val:
                return ""
            out = out.replace("{" + var + "}", val)
        return out.rstrip("/")

    def usable(self) -> bool:
        if self.terms != "confirmed" or not self.url():
            return False
        if self.tier == "account_free" and not self.account_opened():
            return False
        return self.tier == "local" or bool(self.key())

    def account_opened(self) -> bool:
        named = {x.strip().lower() for x in
                 os.environ.get("QUANT_FREE_ONLY_ACCOUNTS", "").split(",") if x.strip()}
        return self.free_only_account or "all" in named or self.name.lower() in named


#: The defaults. Endpoints are each provider's own documented OpenAI-compatible base URL. The
#: config file and QUANT_LOCAL_LLM_URLS extend or override this list; they never have to edit code.
#: Daily caps sit UNDER each provider's published free quota and are config, not science: quotas
#: move, and a row in providers.json overrides any of them.
#:
#: OPEN WEIGHTS FIRST (principal 2026-10-13: "will it also use llama or something open source
#: has good free tiers too to broaden it"). Every hosted rung but Gemini serves open-weight
#: families -- Llama, Qwen, DeepSeek, Mistral, Gemma, GLM, gpt-oss, Phi -- and the local rung runs
#: them on the box itself. Pinned ids are where a provider has no usable /models listing; a pin
#: that rots answers 404, cools for half an hour, and the rotation moves on.
DEFAULTS: tuple[Provider, ...] = (
    Provider("openrouter_free", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
             "model_free", free_pattern=(":free",),
             terms_url="https://openrouter.ai/terms"),
    Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "account_free",
             daily_cap=900, terms_url="https://groq.com/terms-of-use"),
    Provider("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "account_free",
             daily_cap=900, terms_url="https://www.cerebras.ai/terms-of-service"),
    Provider("cloudflare_ai",
             "https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
             "CLOUDFLARE_API_TOKEN", "account_free", daily_cap=300,
             models=("@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/qwen/qwq-32b",
                     "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
                     "@cf/mistralai/mistral-small-3.1-24b-instruct", "@cf/google/gemma-3-12b-it",
                     "@cf/openai/gpt-oss-120b"),
             terms_url="https://developers.cloudflare.com/workers-ai/platform/pricing/"),
    Provider("huggingface", "https://router.huggingface.co/v1", "HF_TOKEN", "account_free",
             daily_cap=300, terms_url="https://huggingface.co/docs/inference-providers/pricing"),
    Provider("mistral_free", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "account_free",
             daily_cap=500, terms_url="https://mistral.ai/terms"),
    Provider("zai_flash", "https://api.z.ai/api/paas/v4", "ZAI_API_KEY", "model_free",
             models=("glm-4.5-flash",), free_pattern=("flash",),
             terms_url="https://docs.z.ai/legal-agreement/terms-of-use"),
    # GITHUB MODELS' FREE TIER IS DOCUMENTED FOR PROTOTYPING AND EXPERIMENTATION. Whether a
    # scheduled hourly research loop fits that is a reading of their terms the desk has not
    # made, so the rung ships CLOSED: set "terms": "confirmed" for it in providers.json to open
    # it. GITHUB_TOKEN alone is not consent.
    Provider("github_models", "https://models.github.ai/inference", "GITHUB_TOKEN",
             "account_free", daily_cap=150, terms="to_confirm",
             models=("meta/Llama-3.3-70B-Instruct", "deepseek/DeepSeek-V3-0324",
                     "mistral-ai/mistral-small-2503", "microsoft/Phi-4"),
             terms_url="https://docs.github.com/en/github-models/use-github-models/"
                       "prototyping-with-ai-models"),
    Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
             "GEMINI_API_KEY", "account_free", daily_cap=200, open_weights=False,
             terms_url="https://ai.google.dev/gemini-api/terms"),
)

#: OPEN-WEIGHT MODELS FOR THE LOCAL RUNG, by the RAM they need quantised (Q4). `status()` reads
#: this box's memory with psutil and names the ones that FIT; nothing is pulled automatically --
#: installing software on the trading box is the principal's act. Ollama tags.
LOCAL_RECOMMENDED: tuple[tuple[str, float], ...] = (
    ("qwen3:8b", 6.0), ("llama3.1:8b", 6.0), ("gemma3:12b", 9.0), ("mistral-nemo:12b", 9.0),
    ("deepseek-r1:14b", 11.0), ("phi4:14b", 11.0), ("qwen3:30b-a3b", 20.0),
    ("gemma3:27b", 19.0), ("qwen2.5:32b", 22.0), ("deepseek-r1:32b", 22.0),
    ("llama3.3:70b", 45.0), ("gpt-oss:120b", 66.0),
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
    return [Provider(f"local{i}", u, "", "local", terms_url="local server, no third party")
            for i, u in enumerate(urls) if u]


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
        tier = str(row.get("tier") or (by_name[name].tier if name in by_name else ""))
        if tier not in ("local", "model_free", "account_free"):
            continue
        if not row.get("base_url") and name not in by_name:
            continue
        prior = by_name.get(name)
        if not row.get("base_url") and prior is not None:
            # A row naming a known provider without a URL EDITS it: the usual case is
            # {"name": "github_models", "terms": "confirmed"} or a new daily cap.
            by_name[name] = Provider(
                name, prior.base_url, prior.key_env, prior.tier,
                tuple(str(m) for m in row.get("models") or prior.models), prior.free_pattern,
                int(row.get("daily_cap") or prior.daily_cap),
                str(row.get("terms") or prior.terms), prior.terms_url, prior.open_weights)
            continue
        by_name[name] = Provider(name, str(row["base_url"]).rstrip("/"),
                                 str(row.get("key_env") or ""), tier,
                                 tuple(str(m) for m in row.get("models") or ()),
                                 tuple(str(m) for m in row.get("free_pattern") or ()),
                                 int(row.get("daily_cap") or 0),
                                 str(row.get("terms") or
                                     ("confirmed" if tier == "local" else "to_confirm")),
                                 str(row.get("terms_url") or ""),
                                 bool(row.get("open_weights", True)))
        if name not in order:
            order.append(name)
    for row in cfg.get("providers") or []:
        if (isinstance(row, dict) and row.get("free_only_account") is True
                and str(row.get("name")) in by_name):
            by_name[str(row["name"])] = dataclasses.replace(by_name[str(row["name"])],
                                                            free_only_account=True)
    # OpenRouter's free allowance is the ACCOUNT's (50/day without credit, 1,000 with), read from
    # its own /key endpoint rather than assumed; no cap is set while that is UNMEASURED.
    orf = by_name.get("openrouter_free")
    if orf is not None and not orf.daily_cap:
        lim = openrouter_guard.daily_limit(cached_only=True)
        if lim:
            by_name["openrouter_free"] = dataclasses.replace(orf, daily_cap=lim)
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

    def count(self, provider: str, model: str, ok: bool,
              latency_s: float | None = None) -> None:
        calls = self.doc.setdefault("calls", {})
        for stale in [d for d in calls if d != _today()]:
            calls.pop(stale, None)
        today = calls.setdefault(_today(), {})
        today[provider] = int(today.get(provider, 0)) + 1
        m = self.doc.setdefault("models", {}).setdefault(f"{provider}:{model}", {})
        m["calls"] = int(m.get("calls", 0)) + 1
        m["ok"] = int(m.get("ok", 0)) + int(ok)
        m["last"] = datetime.now(UTC).isoformat(timespec="seconds")
        if latency_s is not None and ok:
            prev = m.get("latency_s")
            m["latency_s"] = round(latency_s if prev is None else 0.8 * float(prev)
                                   + 0.2 * latency_s, 2)

    def success(self, key: str) -> float:
        """Posterior mean answer rate, Beta(1,1) prior: an untried model reads 0.5, not 0."""
        m = (self.doc.get("models") or {}).get(key) or {}
        return (1.0 + float(m.get("ok", 0))) / (2.0 + float(m.get("calls", 0)))

    def provider_success(self, provider: str) -> float:
        rows = [v for k, v in (self.doc.get("models") or {}).items()
                if k.startswith(provider + ":")]
        ok = sum(float(r.get("ok", 0)) for r in rows)
        calls = sum(float(r.get("calls", 0)) for r in rows)
        return (1.0 + ok) / (2.0 + calls)


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
    if data is not None and (why := openrouter_guard.refusal(url, data)):
        return {}, why
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
    doc, err = _request(f"{p.url()}/models", p.key(), None, timeout)
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


#: How long a provider's model catalogue is trusted before it is listed again, seconds.
MODEL_LIST_TTL_S = 6 * 3600


def _cached_models(st: _State, p: Provider) -> tuple[list[str], str | None]:
    cache = st.doc.setdefault("model_lists", {}).get(p.name) or {}
    if cache.get("models") and _now() - float(cache.get("at", 0)) < MODEL_LIST_TTL_S:
        return list(cache["models"]), None
    models, err = list_models(p)
    if models:
        st.doc["model_lists"][p.name] = {"models": models[:200], "at": _now()}
    return models, err


def rank(st: _State, provs: list[Provider]) -> list[Provider]:
    """THE ROTATION. Cloud rungs ordered by measured answer rate times remaining daily quota, so
    load spreads across every free tier instead of draining the first one; local rungs last,
    always, because they are the floor that never runs out -- not the first resort."""
    def score(p: Provider) -> float:
        used = st.calls_today(p.name) / p.daily_cap if p.daily_cap else 0.0
        return st.provider_success(p.name) * max(0.0, 1.0 - used)
    cloud = sorted((p for p in provs if p.tier != "local"), key=score, reverse=True)
    return cloud + [p for p in provs if p.tier == "local"]


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
    provs = rank(st, [p for p in providers() if p.name not in skip and p.usable()])
    hint_p, _, hint_m = model_hint.partition(":")
    for p in provs:
        if (p.name == hint_p and hint_m and not st.cooled(p.name)
                and not (p.daily_cap and st.calls_today(p.name) >= p.daily_cap)
                and not (p.tier == "local" and local_blocked())):
            # A HINT IS ONLY A PREFERENCE AMONG FREE MODELS (audit must-fix 3, 2026-10-13): it is
            # tried only when the provider's own free-filtered catalogue lists it, so a caller can
            # never name its way past the free filter to a paid id.
            listed, _ = _cached_models(st, p)
            if hint_m in listed:
                plan.append((p, hint_m))
            else:
                tried.append(f"{p.name}:{hint_m}: hint not in the free catalogue")
    for p in provs:
        if p.tier == "local":
            why = local_blocked()
            if why:
                tried.append(f"{p.name}: {why}")
                continue
        if p.daily_cap and st.calls_today(p.name) >= p.daily_cap:
            tried.append(f"{p.name}: daily cap {p.daily_cap}")
            continue
        if st.cooled(p.name):
            tried.append(f"{p.name}: cooling")
            continue
        models, err = _cached_models(st, p)
        if err and not models:
            st.cool(p.name, FAIL_COOLDOWN_S if p.tier != "local" else 120)
            tried.append(f"{p.name}: {err}")
            continue
        capable = _cheapest_capable(models)
        capable.sort(key=lambda m: -st.success(f"{p.name}:{m}"))
        for m in capable[:4]:
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
        t0 = time.time()
        doc, err = _request(f"{p.url()}/chat/completions", p.key(), body, left)
        took = time.time() - t0
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
        st.count(p.name, m, bool(text), took)
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
                     "terms": p.terms, "terms_url": p.terms_url,
                     "open_weights": p.open_weights,
                     "answer_rate": round(st.provider_success(p.name), 3),
                     "calls_today": st.calls_today(p.name), "daily_cap": p.daily_cap,
                     "cooling": st.cooled(p.name)})
    usable = [r for r in rows if r["usable"] and r["tier"] != "local"]
    return {"providers": rows, "cloud_usable": len(usable),
            "terms_closed": [r["name"] for r in rows if r["terms"] != "confirmed"],
            # OPTIONAL BY DESIGN (principal 2026-10-13: no more keys are coming). A rung with no
            # key is skipped and listed here; it is a state of the box, never a failure, and the
            # lab runs on OpenRouter's :free models plus the local rung without any of them.
            "skipped_no_key": [r["name"] for r in rows
                               if r["key_present"] is False and r["terms"] == "confirmed"],
            "account_closed": [p.name for p in providers()
                               if p.tier == "account_free" and not p.account_opened()],
            "local_models_that_fit": local_fit(),
            "verdict": "RAN" if usable else UNMEASURED,
            "why": ("" if usable else "no free cloud key in env; local servers are probed on call")}


def model_stats() -> dict[str, dict[str, Any]]:
    """Per provider:model call/ok counts the chain has recorded, for the lab's model registry."""
    return dict(_State.load().doc.get("models") or {})


# ------------------------------------------------------------------------------ the local rung
#: LOCAL INFERENCE RUNS ON SPARE CPU ONLY, AT THE LOWEST PRIORITY (principal's direction relayed
#: 2026-10-13: "it must never take cores from the judge or the miners"). KEYED ON LOAD, NOT ON
#: WHICH PROCESSES EXIST: the judge runs back to back 24/7 (#333), so "no judge running" would
#: mean the local rung never runs at all. Two rules, both live on every call: the machine's
#: measured CPU use must be under this share, and the inference server is dropped to the OS's
#: idle class, so the moment the judge or a miner wants the cores the scheduler hands them over
#: mid-generation. A blocked rung is a skipped rung, never a queue competing with the gauntlet.
LOCAL_MAX_CPU_PCT = float(os.environ.get("QUANT_LOCAL_LLM_MAX_CPU", "35"))
#: Command-line fragments of the desk's heavy processes, NAMED in the busy reason (not a gate).
YIELD_TO = ("external_gauntlet", "run_external_backtest", "miner_candidate_compiler",
            "conversion_maximiser", "sealed_suite", "judge_shard")
#: Process names of local inference servers whose priority is dropped to idle.
LOCAL_SERVERS = ("ollama", "llama-server", "llama_server", "llama.cpp", "lms", "vllm")
_DEMOTED: set[int] = set()


def _psutil() -> Any:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except Exception:
        return None
    return psutil


def demote_local_servers() -> list[int]:
    """Drop every local inference server to the OS's idle priority. Best effort, once per pid.

    Idle class on Windows, nice 19 elsewhere: the scheduler then gives the model only the cycles
    nothing else wants, which is what makes a local rung safe on the box that trades.
    """
    ps = _psutil()
    if ps is None:
        return []
    out = []
    for proc in ps.process_iter(["pid", "name"]):
        try:
            name = str(proc.info.get("name") or "").lower()
            if proc.pid in _DEMOTED or not any(n in name for n in LOCAL_SERVERS):
                continue
            idle = getattr(ps, "IDLE_PRIORITY_CLASS", None)
            proc.nice(idle if idle is not None else 19)
            _DEMOTED.add(proc.pid)
            out.append(proc.pid)
        except Exception:
            continue
    return out


def local_blocked() -> str:
    """Why the local rung must not run right now, or "" when the machine is idle enough."""
    if os.environ.get("QUANT_LOCAL_LLM_GUARD", "1") == "0":
        return ""
    ps = _psutil()
    if ps is None:
        return "psutil unavailable: cannot prove the box is idle, so the local rung stays off"
    try:
        busy = float(ps.cpu_percent(interval=0.5))
    except Exception:
        return "cpu reading failed"
    if busy > LOCAL_MAX_CPU_PCT:
        heavy = ""
        for proc in ps.process_iter(["cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
            except Exception:
                continue
            heavy = next((f for f in YIELD_TO if f in cmd), "")
            if heavy:
                break
        return (f"box busy ({busy:.0f}% CPU > {LOCAL_MAX_CPU_PCT:.0f}%)"
                + (f", {heavy} needs the cores" if heavy else ""))
    demote_local_servers()
    return ""


def seat_compatible_chat(prompt: str, *, system: str = "", max_tokens: int = 1600,
                         temperature: float = 0.0, timeout: float = TIMEOUT_S,
                         local_only: bool = False) -> tuple[str, str | None]:
    """`llm_seat.chat`'s shape -- (text, error) -- over this chain, for organs written to it.

    `local_only` skips every cloud rung: the deepening worker uses it after OpenRouter's daily
    allowance is spent, when asking the same account again would only collect the same refusal.
    """
    skip = tuple(p.name for p in providers() if p.tier != "local") if local_only else ()
    try:
        r = chat(system or "Answer exactly as instructed.", prompt, max_tokens=max_tokens,
                 temperature=temperature, timeout=timeout, skip=skip)
    except ChainExhausted as exc:
        return "", f"free_chain: {str(exc)[:200]}"
    return r.text, None


def local_declared() -> bool:
    return bool(os.environ.get("QUANT_LOCAL_LLM_URLS", "").strip())


def local_fit() -> dict[str, Any]:
    """Which recommended open-weight models fit THIS machine's free RAM, measured, never assumed."""
    try:
        vm = _psutil().virtual_memory()
        total, free = vm.total / 1024**3, vm.available / 1024**3
    except Exception:
        return {"verdict": UNMEASURED, "why": "psutil unavailable"}
    budget = free * 0.6                      # leave the terminal and the gateway their headroom
    return {"total_gb": round(total, 1), "available_gb": round(free, 1),
            "budget_gb": round(budget, 1),
            "fit": [m for m, gb in LOCAL_RECOMMENDED if gb <= budget],
            "pull_hint": "ollama pull <tag>, then QUANT_LOCAL_LLM_URLS=http://127.0.0.1:11434/v1"}

