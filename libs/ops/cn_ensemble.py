"""CHINESE-MODEL RESEARCH ENSEMBLE: every free Chinese model the desk can reach, 24/7, proposing.

WHY (principal, 2026-11-17: "make most use of all 24/7 Chinese models for max breadth ... edge
discoveries, idea building, research, everything"). The DeepSeek flywheel (`deepseek_cycle`) runs
ONE model, ONE call an hour. Breadth comes from DIFFERENT models disagreeing: DeepSeek, Qwen, GLM,
Kimi and MiniMax were trained on different corpora (much of it Chinese-language market writing
the English seats never read), so the same research question put to five of them yields ideas
that overlap less than five calls to one. This organ puts each hour's research questions to a
spread of those models and keeps every distinct idea, marking which ones only a single model
produced (the orthogonal tail) and which several converged on.

WHERE THE MODELS COME FROM. Three providers, each fail-closed:
  * OpenRouter, free ids only (the existing OPENROUTER key; `openrouter_guard` refuses any
    paid id). Its daily free allowance is SHARED with every other organ, so this organ takes at
    most `CN_ENSEMBLE_OPENROUTER_SHARE` of the day's budget, spread across the hours.
  * hcnsec (api.hcnsec.cn) and AgentRouter (agentrouter.org): free-credit relays the principal
    chose (2026-11-17). Each needs its key (`HCNSEC`, `AGENTROUTER`), which the principal adds to
    the box; with no key the provider is DARK and nothing is sent. Both are third-party relays
    that probably forward upstream vendors' keys and whose logging is opaque, so they receive
    the PUBLIC prompt below and nothing else.

WHAT IS SENT: PUBLIC TEXT ONLY, for every provider. A role, a public research brief and the
output contract. Never the desk's packet, survivors, certificates, edges, sleeves, strategy code,
keys, paths or box details. `assert_public` checks every outgoing prompt and refuses the call if
anything desk-shaped is in it, so a later edit that adds context fails closed instead of leaking.

AUTHORITY: NONE. Proposals land in `data/intelligence/cn_ensemble/` in the miner-discovery
contract and enter the same compiler, judge and gauntlet as every other seat. No model here
touches sizing, capital, promotion or live trading.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import cn_swarm

_ROOT = Path(__file__).resolve().parents[2]
DONATE_DIR = "data/intelligence/cn_ensemble"
REPORT = "desks/mt5/reports/CN_MODEL_ENSEMBLE.json"
RELAY_LEDGER = "data/cn_ensemble_relay_calls.jsonl"

#: Free Chinese-model ids on OpenRouter. Data, not a ranking: every id gets turns, and an id the
#: provider stops serving shows up as a CALL_FAILED row in the report, never a silent gap.
OPENROUTER_CN_MODELS: tuple[str, ...] = (
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-235b-a22b:free",
    "moonshotai/kimi-k2:free",
    "z-ai/glm-4.5-air:free",
    "z-ai/glm-5.2:free",
)

#: Families the principal took OFF the OpenRouter lane (2026-11-24: "on openrouter use alternative
#: fr minimax"). Their turns go to the other live free Chinese-lab ids; relays are unaffected.
OPENROUTER_EXCLUDED = re.compile(r"(?i)minimax|abab")

#: Model-family words that mark an id as Chinese-lab on a relay's /models list.
CN_FAMILY = re.compile(
    r"deepseek|qwen|qwq|glm|chatglm|zhipu|kimi|moonshot|minimax|abab|doubao|ernie|hunyuan"
    r"|baichuan|\byi-|step-|internlm|spark", re.IGNORECASE)


@dataclass(frozen=True)
class Provider:
    name: str
    key_env: str                 # the env var the principal sets; a missing key is DARK
    base_env: str
    default_base: str
    relay: bool                  # True: a free-credit relay (its own allowance, public prompt)
    models_env: str = ""         # optional comma-separated model override
    key_aliases: tuple[str, ...] = ()   # other names the same key may be saved under
    # A relay whose allowance is a fixed model list (not "every Chinese-lab id it serves"):
    # the seat uses these ids that /models also lists, with no CN_FAMILY filter.
    default_models: tuple[str, ...] = ()
    # The relay's own calls/day ceiling (0: the shared CN_ENSEMBLE_RELAY_DAILY); `daily_env`
    # overrides it on the box.
    daily_cap: int = 0
    daily_env: str = ""
    # A base URL carrying "{account}" takes it from this env var (DARK while it is unset).
    account_env: str = ""
    # False: the relay has no OpenAI-style /models list, so `default_models` are used as given.
    lists_models: bool = True
    # Other bases to try, in order, when the default base's /models cannot be read (a key is
    # tied to one region's site). Only used when `base_env` is not set.
    alt_bases: tuple[str, ...] = ()


#: Groq's free models for the swarm; the seat drops any id Groq's /models no longer lists.
GROQ_MODELS: tuple[str, ...] = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b")
#: Calls/day across Groq's models (token-bound: 3 models x ~30 calls x ~6K tokens < 200K each).
GROQ_DAILY = 90
#: Workers AI models for the swarm (override with CLOUDFLARE_AI_MODELS on the box).
CLOUDFLARE_MODELS: tuple[str, ...] = ("@cf/openai/gpt-oss-120b", "@cf/openai/gpt-oss-20b")
#: Calls/day inside 10,000 free Neurons: a gpt-oss-120b call (~2K in, 4K out) is ~340 Neurons,
#: so 20 calls is ~6,800, leaving headroom for prompt growth.
CLOUDFLARE_DAILY = 20
#: SiliconFlow's free (0-price) models. Free models are rate-limited, not metered, so the cap
#: is the shared relay pace; nothing paid is ever named here.
SILICONFLOW_FREE_MODELS: tuple[str, ...] = (
    "Qwen/Qwen3-8B", "Qwen/Qwen2.5-7B-Instruct", "THUDM/GLM-4-9B-0414", "THUDM/glm-4-9b-chat",
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "internlm/internlm2_5-7b-chat")
SILICONFLOW_DAILY = 240


PROVIDERS: tuple[Provider, ...] = (
    Provider("openrouter", "OPENROUTER_API_KEY", "CN_ENSEMBLE_OPENROUTER_BASE",
             "https://openrouter.ai/api/v1", relay=False,
             models_env="CN_ENSEMBLE_OPENROUTER_MODELS"),
    # Both relays run the "new-api" gateway: OpenAI chat/completions at /v1, Bearer auth. The
    # base is an env override because neither publishes it in a page this desk could verify.
    Provider("hcnsec", "HCNSEC", "HCNSEC_BASE_URL", "https://api.hcnsec.cn/v1", relay=True,
             models_env="HCNSEC_MODELS"),
    Provider("agentrouter", "AGENTROUTER", "AGENTROUTER_BASE_URL", "https://agentrouter.org/v1",
             relay=True, models_env="AGENTROUTER_MODELS"),
    # yjs (api.yjs.im), the principal's third relay (2026-11-17). Same contract: DARK until the
    # `YJS` key exists, https only, Chinese-lab models only, public prompts only.
    # The principal saved this key as YJSS on the box (2026-11-17); both names are read.
    Provider("yjs", "YJS", "YJS_BASE_URL", "https://api.yjs.im/v1", relay=True,
             models_env="YJS_MODELS", key_aliases=("YJSS",)),
    # Groq (api.groq.com, OpenAI-compatible), the principal's own free key (zuck 2026-11-25
    # 02:27Z "groq api use it" / "On me"). Free tier per model: 30 RPM, 1000 RPD, 200K tokens/day.
    # One call is ~6K tokens (4K max out + prompt), so tokens bind first: ~30 calls/model/day,
    # 90/day across three models, paced per hour (a handful per hour, far under 30 RPM).
    Provider("groq", "GROQ", "GROQ_BASE_URL", "https://api.groq.com/openai/v1", relay=True,
             models_env="GROQ_MODELS", key_aliases=("GROQ_API_KEY",),
             default_models=GROQ_MODELS, daily_cap=GROQ_DAILY, daily_env="GROQ_DAILY"),
    # Cloudflare Workers AI (OpenAI-compatible /ai/v1), the principal's own free token (zuck
    # 2026-11-25 02:30Z). Free allowance 10,000 Neurons/day; DARK until both the token and the
    # account id exist on the box. Workers AI serves no /models list at /ai/v1.
    Provider("cloudflare", "CLOUDFLARE_AI", "CLOUDFLARE_AI_BASE",
             "https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1", relay=True,
             models_env="CLOUDFLARE_AI_MODELS", default_models=CLOUDFLARE_MODELS,
             daily_cap=CLOUDFLARE_DAILY, daily_env="CLOUDFLARE_AI_DAILY",
             account_env="CLOUDFLARE_ACCOUNT_ID", lists_models=False),
    # SiliconFlow (OpenAI-compatible), the principal's own key (zuck 2026-11-25 02:35Z). The
    # key belongs to one site, so .com is tried first and .cn second. Only its permanently free
    # Chinese-lab models are used; any id the account's /models no longer lists drops out.
    Provider("siliconflow", "SILICONFLOW", "SILICONFLOW_BASE_URL",
             "https://api.siliconflow.com/v1", relay=True, models_env="SILICONFLOW_MODELS",
             default_models=SILICONFLOW_FREE_MODELS, daily_cap=SILICONFLOW_DAILY,
             daily_env="SILICONFLOW_DAILY", alt_bases=("https://api.siliconflow.cn/v1",)),
)

#: PLUG-IN PROVIDERS (principal 2026-11-20: "I even have 2 more things I'll login n give u api
#: of soon"). A new key is ONE box-local file entry, no code change and no release:
#:   data/secrets/cn_providers.json  ->  [{"name": "acme", "base_url": "https://api.acme.cn/v1",
#:                                        "key": "<secret>", "models": ["qwen-max"]}, ...]
#: `key` may be replaced by `key_env` (the name of a box environment variable). `models` is
#: optional: without it the provider's /models list is read and every Chinese-lab id is used.
#: Every entry is treated as a RELAY: its own allowance (`CN_ENSEMBLE_RELAY_DAILY`), the same
#: public-only prompt, and fail-closed DARK on any defect. The file lives with the other secrets
#: on the box and is never printed or reported; only the provider NAME appears in the report.
EXTRA_PROVIDERS_FILE = "data/secrets/cn_providers.json"
_PROVIDER_NAME = re.compile(r"[a-z][a-z0-9_]{1,31}")


def extra_providers(root: Path, env: Mapping[str, str]) -> tuple[list[Provider], dict[str, str]]:
    """The box file's providers and an env overlay carrying their keys/models. Bad entries are
    skipped; a missing or unreadable file means no extras. Never raises, never prints a key."""
    try:
        raw = json.loads((root / EXTRA_PROVIDERS_FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return [], {}
    entries = raw.get("providers", []) if isinstance(raw, dict) else raw
    taken = {p.name for p in PROVIDERS}
    out: list[Provider] = []
    overlay: dict[str, str] = {}
    for ent in entries if isinstance(entries, list) else []:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip().lower()
        base = str(ent.get("base_url") or "").strip()
        if not _PROVIDER_NAME.fullmatch(name) or name in taken or not base.startswith("https://"):
            continue
        tag = name.upper()
        p = Provider(name, f"CN_EXTRA_{tag}_KEY", f"CN_EXTRA_{tag}_BASE", base, relay=True,
                     models_env=f"CN_EXTRA_{tag}_MODELS")
        key_env = str(ent.get("key_env") or "").strip()
        key = str(ent.get("key") or (env.get(key_env, "") if key_env else "") or "").strip()
        if key:
            overlay[p.key_env] = key
        models = ent.get("models")
        if isinstance(models, list):
            overlay[p.models_env] = ",".join(str(m).strip() for m in models if str(m).strip())
        taken.add(name)
        out.append(p)
    return out, overlay


#: The swarm's lenses (one public source or region each) live in `cn_swarm.LENSES`.
ROLES: tuple[tuple[str, str], ...] = tuple((lid, brief) for lid, _lg, brief in cn_swarm.LENSES)

SYSTEM = (
    "You are an independent research idea generator. You propose testable trading hypotheses; "
    "you decide nothing. Every idea you give will be tested by an independent statistical judge "
    "on historical data with costs, and most will fail, which is expected. Prefer ideas that are "
    "unusual and specific over ones every trader already knows.\n\n"
    "Return ONLY valid JSON, no prose outside it:\n"
    '{"findings": [{"title": "short label", '
    '"mechanism": "the economic reason the effect exists: who pays, and why they cannot stop", '
    '"testable_claim": "one falsifiable rule with entry, exit and holding time", '
    '"symbols": ["instruments it trades, e.g. EURUSD, XAUUSD, USDCNH, US500, USOIL"], '
    '"horizon": "intraday | days | weeks", '
    '"source": "a named public paper, report or practitioner source, '
    'or null if first-principles"}]}\n'
    "Give up to 8 findings. An empty list is an honest answer."
)

#: What must never leave the desk. Checked on every outgoing prompt (fail closed).
_PRIVATE = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|Bearer\s|api[_-]?key|secret|password|token\b|C:\\|/home/|desks/mt5"
    r"|data/secrets|\.py\b|sleeve|certificate|cert_id|survivor|gauntlet|allocator|lot size"
    r"|account\s*(id|number)|login|vmi\d|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|E8|FTMO|Fusion)",
    re.IGNORECASE)


def assert_public(*texts: str) -> None:
    """Raise if any outgoing text carries something desk-shaped. Never trust a prompt edit."""
    for t in texts:
        m = _PRIVATE.search(t or "")
        if m:
            raise ValueError(
                f"refused: outgoing prompt carries private-looking text {m.group(0)!r}")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


@dataclass
class Seat:
    provider: Provider
    base_url: str
    key: str = field(repr=False)
    models: tuple[str, ...] = ()
    lit: bool = False
    why: str = ""


RULINGS = "ops/relay_terms_rulings.json"


def relay_ruling(name: str) -> str:
    """The terms ruling for a free-credit relay (Governance or the principal): ALLOWED, or why
    not. Fail closed."""
    try:
        doc = json.loads((_ROOT / RULINGS).read_text("utf-8"))
    except (OSError, ValueError):
        return "UNREADABLE"
    row = doc.get(name) if isinstance(doc, dict) else None
    return str(row.get("ruling") or "PENDING") if isinstance(row, dict) else "ABSENT"


def _read(name: str, env: Mapping[str, str] | None) -> str:
    """A key through `env_keys.read_key` (registry, then process env; catalog refusals apply).
    An explicit `env` mapping (tests, dry runs) is read as given."""
    if env is not None:
        return str(env.get(name, "") or "").strip()
    from libs.ops.env_keys import read_key
    return str(read_key(name) or "").strip()


def seat_for(p: Provider, env: Mapping[str, str] | None = None,
             list_models: Callable[[str, str], list[str]] | None = None) -> Seat:
    """The provider's seat, or a DARK seat saying why. Never raises, never prints a key."""
    e = os.environ if env is None else env
    if p.relay and relay_ruling(p.name) != "ALLOWED":
        return Seat(p, p.default_base, "",
                    why=f"DARK: no ALLOWED terms ruling ({RULINGS} says "
                        f"{relay_ruling(p.name)})")
    key = _read(p.key_env, env)
    for alias in p.key_aliases:
        key = key or _read(alias, env)
    if not key and p.name == "openrouter":
        try:
            from libs.ops.deepseek_cycle import resolve_key
            key = resolve_key(dict(e))[0]
        except Exception:
            key = ""
    base = str(e.get(p.base_env, "") or p.default_base).rstrip("/")
    if "{account}" in base:
        account = str(e.get(p.account_env, "") or "").strip() if p.account_env else ""
        if not account and p.account_env and env is None:
            account = _read(p.account_env, None)
        if not re.fullmatch(r"[0-9a-f]{32}", account):
            return Seat(p, base, "", why=f"DARK: {p.account_env or 'account id'} is not set")
        base = base.replace("{account}", account)
    if not key:
        return Seat(p, base, "", why=f"DARK: {p.key_env} is not set")
    if not base.startswith("https://"):
        return Seat(p, base, "", why=f"DARK: {p.base_env} must be an https URL")
    override = [m.strip() for m in str(e.get(p.models_env, "") or "").split(",") if m.strip()]
    if override:
        models = override
    elif not p.relay:
        # EVERY free Chinese-lab id OpenRouter serves today (new ones join with no edit, retired
        # ones drop out); the static list is only the fallback when /models cannot be read.
        try:
            listed = (list_models or _list_models)(base, key)
        except Exception:
            listed = []
        live = [m for m in listed if m.endswith(":free") and CN_FAMILY.search(m)]
        models = live or list(OPENROUTER_CN_MODELS)
    elif not p.lists_models:
        models = list(p.default_models)
    else:
        bases = [base] + ([] if e.get(p.base_env) else [b.rstrip("/") for b in p.alt_bases])
        listed, err = [], ""
        for cand in bases:
            try:
                listed = (list_models or _list_models)(cand, key)
            except Exception as exc:
                err = type(exc).__name__
                continue
            base = cand
            break
        else:
            return Seat(p, base, "", why=f"DARK: /models unreachable ({err})")
        if p.default_models:
            models = [m for m in p.default_models if m in set(listed)]
            if not models:
                return Seat(p, base, "", why="DARK: /models lists none of the configured models")
        else:
            models = [m for m in listed if CN_FAMILY.search(m)]
        if not models:
            return Seat(p, base, "", why="DARK: the relay lists no Chinese-lab model")
    if not p.relay:
        models = [m for m in models if m.endswith(":free")     # no paid id, ever
                  and not OPENROUTER_EXCLUDED.search(m)]
        if not models:
            return Seat(p, base, "", why="DARK: no :free model configured")
    return Seat(p, base, key, tuple(dict.fromkeys(models)), lit=True)


def _list_models(base: str, key: str) -> list[str]:
    from libs.ops import llm_seat
    body, err = llm_seat._get(f"{base}/models", key, timeout=20.0)
    if err:
        raise RuntimeError(err)
    return [str(m.get("id") or "") for m in (body.get("data") or []) if m.get("id")]


def _chat(seat: Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
    """One call through `llm_seat` so the token ledger has one writer and every row."""
    from libs.ops import llm_seat
    s = llm_seat.Seat(name=f"cn_{seat.provider.name}", base_url=seat.base_url, key=seat.key,
                      model=model, source=llm_seat.FREE_RELAY if seat.provider.relay else "")
    return llm_seat.chat(user, system=system, seat=s, max_tokens=4000, temperature=0.9)


def openrouter_quota(now: datetime, share: float) -> int:
    """This run's slice of OpenRouter's free day: `share` of the daily ceiling, spread over the
    hours left today, and never more than what is actually left after the other organs."""
    from libs.ops import llm_seat
    left = llm_seat.lane_budget_left(now=now)        # never the other lanes' reservations
    if not llm_seat.free_tier_only():
        left = max(left, 0)
    daily = llm_seat.free_daily_max()
    hours_left = max(1, 24 - now.hour)
    mine = int(daily * share)
    spent_by_me = _openrouter_calls_today(now)
    return max(0, min(left, -(-(mine - spent_by_me) // hours_left)))


def _openrouter_calls_today(now: datetime) -> int:
    from libs.ops import llm_seat
    stamp = now.strftime("%Y-%m-%d")
    n = 0
    try:
        for line in llm_seat.SPEND_LEDGER.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if (str(row.get("utc", "")).startswith(stamp) and row.get("seat") == "cn_openrouter"):
                n += 1
    except OSError:
        return 0
    return n


def _relay_calls_today(root: Path, name: str, now: datetime) -> int:
    path = root / RELAY_LEDGER
    stamp = now.strftime("%Y-%m-%d")
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return 0
    return sum(1 for ln in lines if f'"{name}"' in ln and stamp in ln)


def _parse(text: str) -> list[dict[str, Any]]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").split("\n", 1)[-1]
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        doc = json.loads(t[start:end + 1])
    except ValueError:
        return []
    rows = doc.get("findings") if isinstance(doc, dict) else None
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and str(r.get("title") or "").strip() and str(
                r.get("testable_claim") or "").strip():
            out.append(r)
    return out


def _key(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))[:80]


Call = tuple[Seat, str, str, str]        # (seat, model, lens, task)


def plan(seats: list[Seat], quotas: Mapping[str, int], start: int,
         lenses: list[str] | None = None, models: list[str] | None = None) -> list[Call]:
    """Proposal calls for this run: each call is one agent, a model through a lens. Models are
    taken in `models` order (the scoreboard's weighted order; default: as listed) across EVERY
    lit provider, lenses in `lenses` order, so one hour spreads over as many models and sources
    as its quota allows."""
    pool = [(s, m) for s in seats if s.lit for m in s.models]
    if models:
        rank = {k: i for i, k in enumerate(models)}
        pool.sort(key=lambda sm: rank.get(f"{sm[0].provider.name}:{sm[1]}", len(rank)))
    if not pool:
        return []
    order = lenses or [lid for lid, _lg, _b in cn_swarm.LENSES]
    left = dict(quotas)
    calls: list[Call] = []
    i = start
    tries = 0
    total = sum(max(0, v) for v in quotas.values())
    while len(calls) < total and tries < total * len(pool) + len(pool):
        s, m = pool[i % len(pool)]
        if left.get(s.provider.name, 0) > 0:
            calls.append((s, m, order[len(calls) % len(order)], "propose"))
            left[s.provider.name] -= 1
        i += 1
        tries += 1
    return calls


def _env_int(e: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(e.get(name, "") or default)
    except ValueError:
        return default


def run(now: datetime | None = None, *, root: Path | None = None,
        env: Mapping[str, str] | None = None,
        chat: Callable[[Seat, str, str, str], tuple[str, str | None]] | None = None,
        list_models: Callable[[str, str], list[str]] | None = None,
        quotas: Mapping[str, int] | None = None, deadline_s: float = 1500.0,
        rng: random.Random | None = None) -> dict[str, Any]:
    """One hourly swarm pass: propose (lenses), mutate (near misses), critique, donate, score.
    Never raises; every outcome is in the report."""
    import time
    t0 = time.monotonic()
    now = now or _now()
    base = root or _ROOT
    e = os.environ if env is None else env
    extras, overlay = extra_providers(base, e)
    e_all: Mapping[str, str] = {**e, **overlay} if overlay else e
    rng = rng or random.Random(int(now.timestamp()))  # noqa: S311 -- steering draws, not crypto
    seats = [seat_for(p, e_all, list_models) for p in (*PROVIDERS, *extras)]
    if quotas is None:
        share = float(e.get("CN_ENSEMBLE_OPENROUTER_SHARE", "0.5") or 0.5)
        relay_daily = _env_int(e, "CN_ENSEMBLE_RELAY_DAILY", 240)
        q: dict[str, int] = {}
        for s in seats:
            if not s.lit:
                continue
            if s.provider.relay:
                cap = relay_daily
                if s.provider.daily_cap:
                    cap = _env_int(e, s.provider.daily_env, s.provider.daily_cap)
                left = cap - _relay_calls_today(base, s.provider.name, now)
                q[s.provider.name] = max(0, -(-left // max(1, 24 - now.hour)))
            else:
                try:
                    q[s.provider.name] = openrouter_quota(now, share)
                except Exception:
                    q[s.provider.name] = 0
        quotas = q
    quotas = dict(quotas)
    # STEER BY WHAT PASSES: dead families (judged often, never passing) leave the prompt and
    # their recipes are not donated; the rest are listed best realised yield first.
    yld = cn_swarm.family_yield(base)
    cat, dead = cn_swarm.steer_catalog(cn_swarm.catalog(), yld)
    dead_set = set(dead)
    pruned_dead = 0

    # STEER: the scoreboard's Thompson order over models and lenses (floored exploration).
    board = cn_swarm.scoreboard(base)
    lens_ids = [lid for lid, _lg, _b in cn_swarm.LENSES]
    model_ids = [f"{s.provider.name}:{m}" for s in seats if s.lit for m in s.models]
    # The scouts' earlier finds become a lens of their own (names only; nothing is fetched).
    extra: dict[str, str] = {}
    found_brief = cn_swarm.discovered_brief(base, rng)
    if found_brief:
        extra[cn_swarm.DISCOVERED_LENS] = found_brief
        lens_ids.append(cn_swarm.DISCOVERED_LENS)
    lens_order = cn_swarm.ordered(
        lens_ids, cn_swarm.weights(lens_ids, board.get("by_lens") or {}, rng), rng)
    model_order = cn_swarm.ordered(
        model_ids, cn_swarm.weights(model_ids, board.get("by_model") or {}, rng), rng)

    # RESERVE: critic calls (any lit seat) and mutation calls (OpenRouter only: they carry the
    # desk's own near-miss rules, which never go to a free-credit relay).
    critic_cap = _env_int(e, "CN_SWARM_CRITIC_CALLS", 3)
    critic_seat = next((s for s in seats if s.lit and s.provider.relay
                        and quotas.get(s.provider.name, 0) > critic_cap), None) or next(
        (s for s in seats if s.lit and quotas.get(s.provider.name, 0) > critic_cap), None)
    critic_calls = critic_cap if critic_seat else 0
    if critic_seat:
        quotas[critic_seat.provider.name] -= critic_calls
    orseat = next((s for s in seats if s.lit and not s.provider.relay), None)
    near = cn_swarm.near_misses(base) if (orseat and cat) else []
    n_mut = 0
    if orseat and near:
        n_mut = min(_env_int(e, "CN_SWARM_MUTATIONS", 3), max(0, quotas.get("openrouter", 0) // 3))
        quotas["openrouter"] = quotas.get("openrouter", 0) - n_mut
    # One OpenRouter critic call for the mutation-derived recipes: they descend from the desk's
    # own near misses, so they are never scored by a relay (Auditor MF1, 2026-11-17).
    mut_critic = 1 if (n_mut and critic_cap and quotas.get("openrouter", 0) > 1) else 0
    quotas["openrouter"] = quotas.get("openrouter", 0) - mut_critic

    calls = plan(seats, quotas, int(now.timestamp() // 3600), lens_order, model_order)
    if orseat and n_mut:
        for k in range(n_mut):
            m = orseat.models[(k + int(now.timestamp() // 3600)) % len(orseat.models)]
            calls.append((orseat, m, "near_miss_mutation", "mutate"))
    psys = cn_swarm.propose_system(cat)
    do = chat or _chat
    workers = max(1, min(8, _env_int(e, "CN_ENSEMBLE_WORKERS", 6)))

    def one(call: Call) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        seat, model, lens, task = call
        head = {"provider": seat.provider.name, "model": model, "lens": lens, "task": task}
        if time.monotonic() - t0 > deadline_s:
            return {**head, "status": "DEADLINE"}, []
        if task == "mutate":
            k = calls.index(call) if call in calls else 0
            batch = near[(k * 3) % max(1, len(near)):][:3] or near[:3]
            system, user = cn_swarm.MUTATE_SYSTEM, cn_swarm.mutate_user(batch, cat)
        else:
            system = (cn_swarm.formula_system() if lens.startswith(cn_swarm.SCIENCE_PREFIX)
                      else cn_swarm.SCOUT_SYSTEM if lens == cn_swarm.SCOUT_LENS else psys)
            user = cn_swarm.lens_prompt(lens, extra)
        try:
            assert_public(system, user)
        except ValueError as exc:
            return {**head, "status": "REFUSED_PRIVATE", "why": str(exc)}, []
        try:
            text, err = do(seat, model, system, user)
        except Exception as exc:
            text, err = "", f"{type(exc).__name__}: {exc}"
        if seat.provider.relay:
            _append(base / RELAY_LEDGER, {"utc": _iso(_now()), "relay": seat.provider.name,
                                          "model": model, "ok": not err})
        if err:
            return {**head, "status": "CALL_FAILED", "why": str(err)[:300]}, []
        if lens == cn_swarm.SCOUT_LENS:
            srcs = cn_swarm.parse_sources(text)
            return {**head, "status": "OK", "n_sources": len(srcs)}, [{"_source": x}
                                                                       for x in srcs]
        found = _parse(text)
        return {**head, "status": "OK", "n_findings": len(found)}, found

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, calls))

    # SOURCE DISCOVERY: new scout finds into the ledger and the moat registry as candidates.
    known = cn_swarm.known_sources(base)
    new_sources: list[dict[str, Any]] = []
    for (_s, model, _l, _t), (_o, found) in zip(calls, results, strict=True):
        for f in found:
            src = f.get("_source") if isinstance(f, dict) else None
            if not src:
                continue
            hp = cn_swarm._host_path(src["url"])
            if hp in known:
                continue
            known.add(hp)
            new_sources.append({**src, "at": _iso(now), "model": model})
    for src in new_sources:
        _append(base / cn_swarm.SOURCES_LEDGER, src)
    registered = (cn_swarm.register_sources([x["url"] for x in new_sources])
                  if new_sources and root is None else
                  {"status": "SKIPPED", "why": "no new sources" if not new_sources
                   else "test root: registry not touched"})
    results = [(o, [f for f in fs if not (isinstance(f, dict) and "_source" in f)])
               for o, fs in results]

    seen_before = cn_swarm.recent_ids(base, 30, now)
    ideas: dict[str, dict[str, Any]] = {}
    recipes: dict[str, dict[str, Any]] = {}       # genome id -> recipe row
    outcomes: list[dict[str, Any]] = []
    dup_old = 0
    for (seat, model, lens, task), (outcome, found) in zip(calls, results, strict=True):
        outcomes.append(outcome)
        n_rec = 0
        science = lens.startswith(cn_swarm.SCIENCE_PREFIX)
        for f in found:
            # a cross-science analog is a NEW never-judged family (its own expr); the dead-family
            # prune is about catalogue families, so it never drops one
            if not science and str(f.get("family") or "") in dead_set:
                pruned_dead += 1
                continue
            r = (cn_swarm.validate_formula(f, lens) if science
                 else cn_swarm.validate_recipe(f, cat) if cat else None)
            if r is None:
                ik = _key(str(f["title"]))
                if not ik:
                    continue
                row = ideas.setdefault(ik, {**f, "models": [], "roles": []})
                if model not in row["models"]:
                    row["models"].append(model)
                if lens not in row["roles"]:
                    row["roles"].append(lens)
                continue
            for sym in r["symbols"]:
                gid = cn_swarm.genome_id(sym, r["family"], r["params"])
                if gid in seen_before:
                    dup_old += 1
                    continue
                rec = recipes.get(gid)
                if rec is None:
                    rec = recipes[gid] = {
                        "gid": gid, "symbol": sym, "family": r["family"], "params": r["params"],
                        "title": str(f.get("title") or "")[:200],
                        "mechanism": str(f.get("mechanism") or "")[:1000],
                        "testable_claim": str(f.get("testable_claim") or "")[:1000],
                        "horizon": f.get("horizon"), "public_source": f.get("source"),
                        "models": [], "lenses": [], "agents": [], "task": task}
                    n_rec += 1
                if model not in rec["models"]:
                    rec["models"].append(model)
                if lens not in rec["lenses"]:
                    rec["lenses"].append(lens)
                rec["agents"].append({"provider": seat.provider.name, "model": model,
                                      "lens": lens, "task": task})
        outcome["n_recipes"] = n_rec

    # CRITIC: a different model scores the recipes; below the floor they are not donated.
    floor = float(e.get("CN_SWARM_CRITIC_FLOOR", "4") or 4)
    crit: dict[str, Any] = {"seat": None, "scored": 0, "killed": 0, "failed_calls": 0}
    ranked = sorted(recipes.values(), key=lambda r: (-len(r["models"]), r["gid"]))
    private = [r for r in ranked if any(ag["task"] == "mutate" for ag in r["agents"])]
    public = [r for r in ranked if r not in private]
    jobs: list[tuple[Seat, int, list[dict[str, Any]]]] = []
    if critic_seat and public:
        jobs.append((critic_seat, critic_calls, public))
    if orseat and mut_critic and private:
        jobs.append((orseat, mut_critic, private))       # never a relay
    crit["private_unscored"] = len(private) if not (orseat and mut_critic) else 0
    for cseat, ncalls, pending in jobs:
        used = {m for r in pending for m in r["models"]}
        cmodel = next((m for m in cseat.models if m not in used), cseat.models[0])
        crit.setdefault("seats", []).append(f"{cseat.provider.name}:{cmodel}")
        crit["seat"] = crit["seat"] or f"{cseat.provider.name}:{cmodel}"
        size = min(25, max(1, -(-len(pending) // max(1, ncalls))))
        for b in range(min(ncalls, -(-len(pending) // size))):
            batch = pending[b * size:(b + 1) * size]
            user = cn_swarm.critic_user(batch)
            try:
                assert_public(cn_swarm.CRITIC_SYSTEM, user)
                text, err = do(cseat, cmodel, cn_swarm.CRITIC_SYSTEM, user)
            except Exception as exc:
                text, err = "", str(exc)
            if cseat.provider.relay:
                _append(base / RELAY_LEDGER, {"utc": _iso(_now()), "relay": cseat.provider.name,
                                              "model": cmodel, "ok": not err})
            if err:
                crit["failed_calls"] += 1
                continue
            for i, (score, why) in cn_swarm.parse_scores(text, len(batch)).items():
                batch[i]["prior_score"] = score
                batch[i]["critic_why"] = why
                crit["scored"] += 1
    keep = [r for r in recipes.values()
            if r.get("prior_score") is None or float(r["prior_score"]) >= floor]
    crit["killed"] = len(recipes) - len(keep)
    keep.sort(key=lambda r: (-(float(r["prior_score"]) if r.get("prior_score") is not None
                               else floor), -len(r["models"])))

    path = _donate(list(ideas.values()), keep, now, base) if (ideas or keep) else None
    for r in keep:
        for a in r["agents"]:
            _append(base / cn_swarm.LINEAGE, {
                "at": _iso(now), "gid": r["gid"], "symbol": r["symbol"], "family": r["family"],
                "params": r["params"], "provider": a["provider"], "model": a["model"],
                "lens": a["lens"], "task": a["task"], "prior_score": r.get("prior_score")})

    by_model: dict[str, dict[str, int]] = {}
    by_lens: dict[str, dict[str, int]] = {}
    for o in outcomes:
        for d, dk in ((by_model, f"{o['provider']}:{o['model']}"), (by_lens, o["lens"])):
            bk = d.setdefault(dk, {"calls": 0, "ok": 0, "ideas": 0, "recipes": 0})
            bk["calls"] += 1
            bk["ok"] += o["status"] == "OK"
            bk["ideas"] += int(o.get("n_findings") or 0)
            bk["recipes"] += int(o.get("n_recipes") or 0)
    report = {
        "generated_utc": _iso(now),
        "authority": "PROPOSE ONLY: no sizing, capital, promotion or live-trading authority",
        "prompt_policy": ("public text only to every provider; assert_public refuses any "
                          "desk-shaped content; near-miss mutation goes to OpenRouter only"),
        "providers": {s.provider.name: {"lit": s.lit, "why": s.why, "models": list(s.models),
                                        "quota_this_run": int(quotas.get(s.provider.name, 0))}
                      for s in seats},
        "catalog_families": len(cat),
        "steering_by_yield": {"source": "JUDGE_COVERAGE" if yld else "fallback list",
                              "pruned_families": dead,
                              "findings_dropped_dead_family": pruned_dead,
                              "top_families": list(cat)[:8]},
        "calls": len(outcomes),
        "ok_calls": sum(o["status"] == "OK" for o in outcomes),
        "mutation_calls": sum(o["task"] == "mutate" for o in outcomes),
        "near_misses_seen": len(near),
        "runnable_recipes": len(recipes),
        "recipes_donated": len(keep),
        "recipes_skipped_already_sent": dup_old,
        "critic": crit,
        "sources_discovered": len(new_sources),
        "sources_registration": registered,
        "lenses": len(lens_ids),
        "prose_ideas": len(ideas),
        "distinct_ideas": len(ideas) + len(keep),
        "single_model_ideas": sum(len(r["models"]) == 1 for r in ideas.values()),
        "multi_model_ideas": (sum(len(r["models"]) > 1 for r in ideas.values())
                              + sum(len(r["models"]) > 1 for r in keep)),
        "by_model": by_model,
        "by_lens": by_lens,
        "scoreboard": board,
        "steering": {"lens_order": lens_order[:8], "model_order": model_order[:8]},
        "outcomes": outcomes,
        "donated": str(path.relative_to(base)) if path else None,
    }
    out = base / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    tmp.replace(out)
    return report


_APPEND_LOCK = threading.Lock()


def _append(path: Path, row: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _APPEND_LOCK, path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass


_LENS_LANG = {lid: lg for lid, lg, _b in cn_swarm.LENSES}
_CULTURE = {"zh": "CN/zh", "ja": "JP/ja", "ko": "KR/ko", "es": "LATAM/es", "pt": "BR/pt",
            "ar": "MENA/ar", "ru": "RU/ru", "pl": "CEE/pl", "tr": "TR/tr", "hi": "IN/hi",
            "id": "ID/id", "th": "TH/th", "fr": "AFR/fr", "de": "DE/de"}


def _donate(rows: list[dict[str, Any]], recipes: list[dict[str, Any]], now: datetime,
            base: Path) -> Path:
    """The miner-discovery contract the compiler reads (`data/intelligence/**`). Recipes carry
    `family` + `params` + `symbols`, which the compiler's EXACT_RECIPE path turns straight into
    cells; prose rows (no runnable recipe) take the deepening route as before."""
    from libs.data.pit import stamp_or_refuse
    from libs.research.source_provenance import stamp_row
    out = base / DONATE_DIR
    out.mkdir(parents=True, exist_ok=True)
    gen = _iso(now)
    path = out / f"discoveries_{now.strftime('%Y%m%dT%H%M%S')}.json"
    docs = [{
        "source": "cn_ensemble", "title": str(r["title"])[:200],
        "symbols": [str(x).upper() for x in (r.get("symbols") or []) if str(x).strip()][:8],
        "type": "MECHANISM_HYPOTHESIS", "kind": "hypothesis", "family": None,
        "mechanism": str(r.get("mechanism") or "")[:1000],
        "testable_claim": str(r.get("testable_claim") or "")[:1000],
        "horizon": r.get("horizon"), "public_source": r.get("source"),
        "models": r["models"], "roles": r["roles"], "consensus": len(r["models"]),
        "url": f"cn_ensemble://{r['roles'][0]}/{_key(str(r['title']))[:40].replace(' ', '_')}",
    } for r in rows]
    docs += [{
        "source": "cn_ensemble", "title": r["title"] or f"{r['family']} on {r['symbol']}",
        "symbols": [r["symbol"]], "type": "MECHANISM_HYPOTHESIS", "kind": "hypothesis",
        "family": r["family"], "params": r["params"], "genome_id": r["gid"],
        "mechanism": r["mechanism"] or f"{r['family']} proposed through lens {r['lenses'][0]}",
        "testable_claim": r["testable_claim"], "horizon": r.get("horizon"),
        "public_source": r.get("public_source"), "models": r["models"],
        "roles": r["lenses"], "consensus": len(r["models"]), "task": r["task"],
        "prior_score": r.get("prior_score"), "critic_why": r.get("critic_why"),
        # Declared culture (cell_culture.py): the lens's own jurisdiction and language.
        "source_culture": _CULTURE.get(_LENS_LANG.get(r["lenses"][0], ""), "GLOBAL"),
        "url": f"cn_ensemble://{r['lenses'][0]}/{r['gid']}",
    } for r in recipes]
    stamped, refused = stamp_or_refuse(
        [stamp_row(d, ground="cn_ensemble", retrieved_at=gen) for d in docs], "cn_ensemble")
    path.write_text(json.dumps({"source": "cn_ensemble", "generated_at": gen,
                                "refused": len(refused), "discoveries": stamped},
                               indent=1, default=str), "utf-8")
    return path
