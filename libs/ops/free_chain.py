"""ONE free-model chain for every job, over EVERY LLM key this host holds.

The owner's order (2026-11-25): everything built for the free models -- alt-data cells, data
discovery, the translator, judge feedback, near-miss mutation, dedupe, the job registry -- runs on
every key the desk holds (OpenRouter, Groq, SiliconFlow, Cloudflare Workers AI, Cerebras, GitHub
Models, DeepSeek, the cn relays hcnsec / agentrouter / yjs, and any future key), and a new key
lights up when it appears on the box with no code change.

Before this file the desk had two chains that disagreed: `conversion_lanes.route_ask` walked
OpenRouter then the cn_ensemble providers, while `data_discovery.seat_chain` walked
`llm_seat.seats()` and the free roster file. Each job reached a different subset of the keys and
always started at the same door, so the first lit key served nearly all the traffic.

WHERE A ROUTE COMES FROM, in this order (deduplicated by base URL + key + pinned model):

  1. `openrouter_free`  -- OpenRouter's free rotation (`libs/ops/openrouter_free`).
  2. `seat`             -- `llm_seat.seats()`: OPENROUTER / OPENAI / DEEPSEEK / XAI env keys and
                           `data/secrets/llm_panel.json`.
  3. `panel_free`       -- `data/secrets/llm_panel_free.json`.
  4. `cn`               -- every `cn_ensemble` provider, built in (hcnsec, agentrouter, yjs, groq,
                           cloudflare, siliconflow) and plug-in (`data/secrets/cn_providers.json`).
                           These are RELAYS: public prompts only (`cn_ensemble.assert_public`),
                           their terms ruling, daily caps and weekly credit caps.
  5. `owner`            -- the principal's own free keys built in here: Cerebras and GitHub
                           Models. DARK until the key exists.
  6. `env`              -- THE NO-CODE DOOR. Any environment variable (process env, or the
                           machine/user registry on the Windows box)
                               FREE_LLM_<NAME>_KEY     the key
                               FREE_LLM_<NAME>_BASE    its OpenAI-compatible base, https only
                               FREE_LLM_<NAME>_MODELS  optional comma-separated model ids
                               FREE_LLM_<NAME>_DAILY   optional calls/day cap
                               FREE_LLM_<NAME>_WEEKLY  optional rolling 7-day credit cap
                               FREE_LLM_<NAME>_RELAY   optional "1": treat as a third-party
                                                       relay (public prompts only)
                           registers a route on the next call. Without _MODELS the base's
                           /models list is read and every id it serves is used.

`ask(organ, system, user)` walks the lit routes with failover and ROTATES the starting route per
call (by organ, hour and a per-organ counter), so every lit key serves traffic across the jobs.
Each call is appended to `data/free_chain_calls.jsonl` (provider, model, organ, ok, latency --
never a key), and `write_report()` publishes `desks/mt5/reports/FREE_MODEL_ROUTES.json`: every
known provider LIT / DARK (why) / CAPPED (until when), its calls and successes per job over 24h,
and its last success.

Nothing here ever prints, logs or reports a key value.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
import time
import urllib.request
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "data/free_chain_calls.jsonl"
REPORT = "desks/mt5/reports/FREE_MODEL_ROUTES.json"
FREE_ROSTER = "data/secrets/llm_panel_free.json"
ENV_PREFIX = "FREE_LLM_"
_ENV_KEY = re.compile(r"FREE_LLM_([A-Z][A-Z0-9_]{0,30}?)_KEY")
#: Seconds a discovered route list is reused inside one process (discovery reads /models lists).
CACHE_S = 1800.0
#: Models tried per route per call before failing over to the next route.
MODELS_PER_ROUTE = 2


@dataclass(frozen=True)
class OwnerProvider:
    """A free LLM key the principal holds himself (not a third-party relay)."""
    name: str
    key_env: str
    default_base: str
    base_env: str = ""
    key_aliases: tuple[str, ...] = ()
    models_env: str = ""
    default_models: tuple[str, ...] = ()
    lists_models: bool = True
    models_url: str = ""              # a catalog URL other than `<base>/models`
    daily_cap: int = 0
    daily_env: str = ""
    weekly_cap: int = 0
    weekly_env: str = ""
    relay: bool = False               # True: public prompts only (FREE_LLM_<NAME>_RELAY=1)


#: Cerebras (api.cerebras.ai, OpenAI-compatible, /models lists ids). Free tier: ~1M tokens/day,
#: 30 RPM; one call is ~6K tokens, so 150 calls/day stays inside it.
CEREBRAS_MODELS: tuple[str, ...] = (
    "gpt-oss-120b", "qwen-3-235b-a22b-instruct-2507", "llama-3.3-70b", "qwen-3-32b")
#: GitHub Models (models.github.ai, OpenAI-compatible; a fine-grained PAT with Models:read).
#: Free tier: 50-150 requests/day by model tier, so 50/day.
GITHUB_MODELS: tuple[str, ...] = (
    "openai/gpt-4.1", "openai/gpt-4.1-mini", "deepseek/DeepSeek-V3-0324",
    "meta/Llama-4-Maverick-17B-128E-Instruct-FP8")

OWNER_PROVIDERS: tuple[OwnerProvider, ...] = (
    OwnerProvider("cerebras", "CEREBRAS", "https://api.cerebras.ai/v1",
                  base_env="CEREBRAS_BASE_URL", key_aliases=("CEREBRAS_API_KEY",),
                  models_env="CEREBRAS_MODELS", default_models=CEREBRAS_MODELS,
                  daily_cap=150, daily_env="CEREBRAS_DAILY"),
    OwnerProvider("github_models", "GITHUB_MODELS_TOKEN", "https://models.github.ai/inference",
                  base_env="GITHUB_MODELS_BASE_URL", key_aliases=("GITHUB_TOKEN",),
                  models_env="GITHUB_MODELS_MODELS", default_models=GITHUB_MODELS,
                  models_url="https://models.github.ai/catalog/models",
                  daily_cap=50, daily_env="GITHUB_MODELS_DAILY"),
)


@dataclass
class Route:
    """One door: a provider + base + key, the models it may serve, and its caps."""
    name: str
    kind: str                         # openrouter_free | seat | panel_free | cn | owner | env
    base_url: str
    key: str = field(repr=False)
    models: tuple[str, ...] = ()
    relay: bool = False               # public prompts only
    lit: bool = False
    why: str = ""
    key_envs: tuple[str, ...] = ()    # NAMES only
    daily_cap: int = 0
    weekly_cap: int = 0
    weekly_name: str = ""             # the ledger name its weekly credits are counted under
    paid: bool = False                # a metered seat: failover tail only, never rotated onto
    handle: Any = field(default=None, repr=False)   # cn Seat / llm_seat Seat / provider object

    def __repr__(self) -> str:        # never a key, whatever is added later
        return (f"Route({self.name!r}, kind={self.kind!r}, lit={self.lit}, "
                f"models={len(self.models)})")

    @property
    def ident(self) -> tuple[str, str, str]:
        pinned = self.models[0] if self.kind in ("seat", "panel_free") and self.models else "*"
        return (self.base_url.rstrip("/"),
                hashlib.sha256(self.key.encode()).hexdigest()[:12] if self.key else "",
                pinned)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(str(env.get(name, "") or default))
    except ValueError:
        return default


def _read(name: str, env: Mapping[str, str] | None) -> str:
    """A key by NAME: the explicit mapping when given (tests), else env_keys.read_key (machine
    registry, user registry, process env; catalog refusals apply)."""
    if not name:
        return ""
    if env is not None:
        return str(env.get(name, "") or "").strip()
    try:
        from libs.ops.env_keys import read_key
        return str(read_key(name) or "").strip()
    except Exception:
        return str(os.environ.get(name, "") or "").strip()


def _refused_alias(names: Iterable[str]) -> str:
    """The first name the key catalog refuses to hand out, or ''."""
    with contextlib.suppress(Exception):
        from libs.ops.env_keys import refused
        for n in names:
            if refused(n):
                return n
    return ""


def env_names(env: Mapping[str, str] | None = None) -> list[str]:
    """Every variable NAME this host carries (process env, plus the machine and user registry on
    Windows). Values are never returned."""
    names = set((os.environ if env is None else env).keys())
    if env is None:
        with contextlib.suppress(Exception):
            from libs.ops.env_secret import _registry_all
            for hive in ("machine", "user"):
                names |= set(_registry_all(hive).keys())
    return sorted(names)


def _list_models(url: str, key: str) -> list[str]:
    from libs.ops import llm_seat
    req = urllib.request.Request(url, headers=llm_seat._headers(key))
    body, err = llm_seat._send(req, 20.0)
    if err:
        raise RuntimeError(err)
    rows = body if isinstance(body, list) else (body.get("data") or body.get("models") or [])
    return [str(m.get("id") or m.get("name") or "") for m in rows
            if isinstance(m, dict) and (m.get("id") or m.get("name"))]


def _owner_route(p: OwnerProvider, kind: str, env: Mapping[str, str] | None,
                 list_models: Callable[[str, str], list[str]] | None) -> Route:
    e = os.environ if env is None else env
    names = (p.key_env, *p.key_aliases)
    key = ""
    for n in names:
        key = key or _read(n, env)
    base = str(e.get(p.base_env, "") or p.default_base).rstrip("/") if p.base_env \
        else p.default_base.rstrip("/")
    daily = _env_int(e, p.daily_env, p.daily_cap) if p.daily_env else p.daily_cap
    weekly = _env_int(e, p.weekly_env, p.weekly_cap) if p.weekly_env else p.weekly_cap
    r = Route(p.name, kind, base, "", relay=p.relay, key_envs=names, daily_cap=daily,
              weekly_cap=weekly, weekly_name=p.name, handle=p)
    if not key:
        bad = _refused_alias(names) if env is None else ""
        r.why = (f"DARK: no key ({' / '.join(names)} not set)"
                 + (f"; {bad} is refused by env_keys_catalog" if bad else ""))
        return r
    if not base.startswith("https://"):
        r.why = f"DARK: base must be an https URL ({p.base_env or 'base'})"
        return r
    override = [m.strip() for m in str(e.get(p.models_env, "") or "").split(",") if m.strip()] \
        if p.models_env else []
    if override:
        models = override
    elif p.lists_models:
        try:
            listed = (list_models or _list_models)(p.models_url or f"{base}/models", key)
        except Exception as exc:
            r.why = f"DARK: refused (/models unreachable: {type(exc).__name__})"
            return r
        models = [m for m in p.default_models if m in set(listed)] or list(listed)
        if not models:
            r.why = "DARK: refused (/models lists no model)"
            return r
    else:
        models = list(p.default_models)
    if not models:
        r.why = "DARK: no model configured"
        return r
    r.key, r.models, r.lit = key, tuple(dict.fromkeys(models)), True
    return r


def env_providers(env: Mapping[str, str] | None = None) -> list[OwnerProvider]:
    """The FREE_LLM_<NAME>_KEY convention: one provider per name, no code change."""
    e = os.environ if env is None else env
    out: list[OwnerProvider] = []
    taken = {p.name for p in OWNER_PROVIDERS}
    for n in env_names(env):
        m = _ENV_KEY.fullmatch(n)
        if not m:
            continue
        tag = m.group(1)
        name = tag.lower()
        if name in taken:
            continue
        taken.add(name)
        relay = str(e.get(f"{ENV_PREFIX}{tag}_RELAY", "") or _read(
            f"{ENV_PREFIX}{tag}_RELAY", env)).strip().lower() in ("1", "true", "yes")
        base = str(e.get(f"{ENV_PREFIX}{tag}_BASE", "") or _read(f"{ENV_PREFIX}{tag}_BASE", env))
        out.append(OwnerProvider(
            name, f"{ENV_PREFIX}{tag}_KEY", base.strip(), models_env=f"{ENV_PREFIX}{tag}_MODELS",
            daily_env=f"{ENV_PREFIX}{tag}_DAILY", weekly_env=f"{ENV_PREFIX}{tag}_WEEKLY",
            relay=relay))
    return out


def _env_overlay(env: Mapping[str, str] | None, provs: list[OwnerProvider]) -> Mapping[str, str]:
    """For registry-held FREE_LLM_* settings: an env view carrying their MODELS/DAILY/WEEKLY
    (never keys) so _owner_route reads them like process env."""
    if env is not None:
        return env
    extra: dict[str, str] = {}
    for p in provs:
        for n in (p.models_env, p.daily_env, p.weekly_env):
            if n and n not in os.environ:
                v = _read(n, None)
                if v:
                    extra[n] = v
    return {**os.environ, **extra} if extra else os.environ


def discover(*, env: Mapping[str, str] | None = None, root: Path | None = None,
             list_models: Callable[[str, str], list[str]] | None = None) -> list[Route]:
    """EVERY known route, lit or dark (with why), deduplicated. Never raises, never prints."""
    base_root = root or _ROOT
    e = os.environ if env is None else env
    out: list[Route] = []
    # 1. OpenRouter's free rotation
    with contextlib.suppress(Exception):
        from libs.ops import openrouter_free as orf
        key, _src = orf.resolve_key(None if env is None else dict(env))
        out.append(Route("openrouter_free", "openrouter_free", orf.BASE_URL, key or "",
                         lit=bool(key), why="" if key else "DARK: no key (OPENROUTER_API_KEY "
                         "not set and no openrouter panel entry)",
                         key_envs=("OPENROUTER_API_KEY",), handle=orf))
    # 2. llm_seat's seats (env keys + llm_panel.json)
    if env is None:
        with contextlib.suppress(Exception):
            from libs.ops import llm_seat
            for st in llm_seat.seats():
                # A direct vendor seat (DEEPSEEK / OPENAI / XAI) is metered unless its pinned
                # model is a free id: it is the chain's failover TAIL, never rotated onto.
                paid = "openrouter.ai" not in str(st.base_url) and \
                    not llm_seat.is_free_model(str(st.model or ""))
                out.append(Route(str(st.name), "seat", str(st.base_url).rstrip("/"), st.key,
                                 (st.model,) if st.model else (), lit=bool(st.key),
                                 key_envs=(st.source.split(":", 1)[-1],), paid=paid,
                                 handle=st))
    # 3. the free roster file
    with contextlib.suppress(Exception):
        from libs.ops import llm_seat
        from libs.ops.llm_route import load_seats
        for p in load_seats(base_root / FREE_ROSTER):
            st = llm_seat.Seat(name=str(p.get("name") or "free"),
                               base_url=str(p.get("base_url")).rstrip("/"),
                               key=str(p.get("key")), model=str(p.get("model") or ""),
                               source="file:llm_panel_free.json")
            out.append(Route(st.name, "panel_free", st.base_url, st.key,
                             (st.model,) if st.model else (), lit=True,
                             key_envs=("llm_panel_free.json",), handle=st))
    # 4. every cn_ensemble provider, built in and plug-in
    with contextlib.suppress(Exception):
        from libs.ops import cn_ensemble as cn
        extra, overlay = cn.extra_providers(base_root, e)
        cn_env: Mapping[str, str] | None = ({**e, **overlay} if (overlay or env is not None)
                                            else None)
        for p in (*cn.PROVIDERS, *extra):
            if p.name == "openrouter":            # served by openrouter_free (same key)
                continue
            try:
                seat = cn.seat_for(p, cn_env, list_models) if list_models else \
                    cn.seat_for(p, cn_env)
            except Exception as exc:
                seat = cn.Seat(p, p.default_base, "", why=f"DARK: {type(exc).__name__}")
            names = (p.key_env, *p.key_aliases) + ((p.account_env,) if p.account_env else ())
            why = seat.why
            if not seat.lit and env is None and "is not set" in why:
                bad = _refused_alias((p.key_env, *p.key_aliases))
                if bad:
                    why += f"; {bad} is refused by env_keys_catalog"
            out.append(Route(p.name, "cn", str(seat.base_url).rstrip("/"), seat.key if seat.lit
                             else "", tuple(seat.models), relay=bool(p.relay), lit=seat.lit,
                             why=why, key_envs=names,
                             daily_cap=(cn.relay_daily_cap(p, e) if p.relay else 0),
                             weekly_cap=cn.weekly_cap_of(p, e), weekly_name=p.name,
                             handle=seat))
    # 5 + 6. the principal's own keys, built in and by the env convention
    envp = env_providers(env)
    oenv = _env_overlay(env, envp)
    for p in OWNER_PROVIDERS:
        out.append(_owner_route(p, "owner", oenv if env is None else env, list_models))
    for p in envp:
        r = _owner_route(p, "env", oenv if env is None else env, list_models)
        if r.lit is False and not p.default_base:
            r.why = f"DARK: {ENV_PREFIX}{p.name.upper()}_BASE is not set"
        out.append(r)
    # dedupe lit routes by (base, key, pinned model); names unique
    seen: set[tuple[str, str, str]] = set()
    names: set[str] = set()
    kept: list[Route] = []
    for r in out:
        if r.lit:
            if r.ident in seen:
                continue
            seen.add(r.ident)
        n, i = r.name, 2
        while n in names:
            n, i = f"{r.name}_{i}", i + 1
        r.name = n
        names.add(n)
        kept.append(r)
    return kept


_CACHE: dict[str, Any] = {}
_LOCK = threading.Lock()
_COUNTER: dict[str, int] = {}


def reset() -> None:
    """Forget cached routes and rotation counters (tests; a key added mid-process)."""
    with _LOCK:
        _CACHE.clear()
        _COUNTER.clear()


def _fingerprint(root: Path | None) -> tuple[Any, ...]:
    """What a cached route list depends on: the root, the env var NAMES that name a key, and
    the discovery functions themselves (a test that swaps one gets a fresh list)."""
    from libs.ops import cn_ensemble as cn
    from libs.ops import llm_seat
    from libs.ops import openrouter_free as orf
    names = tuple(n for n in os.environ if n.startswith(ENV_PREFIX) or n.endswith(
        ("_KEY", "_TOKEN")) or n in ("CEREBRAS", "GROQ", "HCNSEC", "YJS", "YJSS", "SILICONFLOW",
                                     "AGENTROUTER", "CLOUDFLARE_AI"))
    return (str(root), names, id(cn.seat_for), id(cn.extra_providers), id(orf.resolve_key),
            id(llm_seat.seats))


def _cached(root: Path | None) -> list[Route]:
    fp = _fingerprint(root)
    with _LOCK:
        hit = _CACHE.get("routes")
        if hit is not None and time.monotonic() - _CACHE.get("at", 0.0) < CACHE_S \
                and _CACHE.get("fp") == fp:
            return list(hit)
    got = discover(root=root)
    with _LOCK:
        _CACHE.update(routes=got, at=time.monotonic(), fp=fp)
    return list(got)


def is_public(*texts: str) -> bool:
    from libs.ops import cn_ensemble as cn
    try:
        cn.assert_public(*texts)
    except ValueError:
        return False
    return True


def routes(organ: str = "", *, public: bool, root: Path | None = None,
           env: Mapping[str, str] | None = None,
           list_models: Callable[[str, str], list[str]] | None = None) -> list[Route]:
    """Every LIT route this host has for a prompt of this publicity (relays need public)."""
    rs = discover(env=env, root=root, list_models=list_models) \
        if (env is not None or list_models is not None) else _cached(root)
    return [r for r in rs if r.lit and (public or not r.relay)]


# ------------------------------------------------------------------------------ caps --------
def _ledger_path(root: Path | None) -> Path:
    return (root or _ROOT) / LEDGER


def _calls_today(r: Route, root: Path | None, now: datetime) -> int:
    from libs.ops import cn_ensemble as cn
    if r.kind == "cn":
        return int(cn._relay_calls_today(root or _ROOT, r.weekly_name or r.name, now))
    used, _st = cn.ledger_credits(_ledger_path(root), r.name,
                                  now.replace(hour=0, minute=0, second=0, microsecond=0))
    return int(used)


def cap_state(r: Route, now: datetime, root: Path | None = None, organ: str = ""
              ) -> tuple[str, str | None]:
    """("" , None) when the route may be called now, else (why, reset ISO time)."""
    from libs.ops import cn_ensemble as cn
    if r.weekly_cap > 0:
        path = (root or _ROOT) / (cn.RELAY_LEDGER if r.kind == "cn" else LEDGER)
        used, stamps = cn.ledger_credits(path, r.weekly_name or r.name, now - timedelta(days=7))
        if used >= r.weekly_cap:
            reset = _iso(min(stamps) + timedelta(days=7)) if stamps else None
            return f"CAPPED: weekly {int(used)}/{r.weekly_cap} credits", reset
    if r.daily_cap > 0:
        n = _calls_today(r, root, now)
        if n >= r.daily_cap:
            nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return f"CAPPED: daily {n}/{r.daily_cap} calls", _iso(nxt)
    if r.kind == "openrouter_free":
        with contextlib.suppress(Exception):
            from libs.ops import llm_seat
            if llm_seat.lane_budget_left(organ or None) <= 0:
                return "CAPPED: OpenRouter free lane budget spent", None
    return "", None


def rotation(rs: list[Route], organ: str, now: datetime) -> list[Route]:
    """The routes in this call's order: a start that moves with organ, hour and a per-organ
    counter, so successive calls spread over every lit route."""
    free = [r for r in rs if not r.paid]
    tail = [r for r in rs if r.paid]
    if not free:
        return tail
    with _LOCK:
        k = _COUNTER.get(organ, 0)
        _COUNTER[organ] = k + 1
    start = (zlib.crc32(f"{organ}|{now:%Y%m%d%H}".encode()) + k) % len(free)
    return free[start:] + free[:start] + tail


def _record(root: Path | None, row: dict[str, Any]) -> None:
    from libs.ops import cn_ensemble as cn
    with contextlib.suppress(Exception):
        cn._append(_ledger_path(root), row)


def _call(r: Route, model: str, system: str, user: str, *, max_tokens: int,
          temperature: float) -> tuple[str, str, str | None]:
    """(text, model actually served, error). Never raises."""
    try:
        if r.kind == "openrouter_free":
            orf = r.handle
            models, _basis = orf.free_models(r.key)
            if model and model in models:
                models = [model] + [m for m in models if m != model]
            st = orf.load_state()
            text, served, err = orf.complete(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                key=r.key, models=models, state=st, max_tokens=max_tokens)
            return text, served or model, err
        if r.kind == "cn":
            from libs.ops import cn_ensemble as cn
            text, err = cn._chat(r.handle, model, system, user)
            return text, model, err
        from libs.ops import llm_seat
        if r.kind in ("seat", "panel_free"):
            st = r.handle
        else:
            st = llm_seat.Seat(name=f"free_{r.name}", base_url=r.base_url, key=r.key,
                               model=model, source=llm_seat.FREE_RELAY)
        text, err = llm_seat.chat(user, system=system, seat=st, max_tokens=max_tokens,
                                  temperature=temperature)
        return text, model or str(getattr(st, "model", "") or "discovered"), err
    except Exception as exc:
        return "", model, f"{type(exc).__name__}: {str(exc)[:120]}"


def ask(organ: str, system: str, user: str, *, max_tokens: int = 4000,
        temperature: float = 0.7, public: bool | None = None, root: Path | None = None,
        now: datetime | None = None, chain: list[Route] | None = None,
        budget_s: float | None = None, job: str | None = None
        ) -> tuple[str, str, str | None]:
    """(text, "provider/model", error) from the first lit route that answers, starting at this
    call's rotation point. A private prompt (or `public=False`) never reaches a relay. `organ`
    carries the lane budget; `job` (default: organ) is what the evidence counts calls under.
    Never raises."""
    if str(os.environ.get("FREE_CHAIN_OFF", "")).strip() in ("1", "true", "yes"):
        return "", "", "free chain switched off (FREE_CHAIN_OFF)"
    t0 = time.monotonic()
    pub = is_public(system, user) and (public is not False)
    try:
        rs = [r for r in (chain if chain is not None else routes(organ, public=pub, root=root))
              if r.lit and (pub or not r.relay)]
    except Exception as exc:
        return "", "", f"free chain: {type(exc).__name__}"
    stamp = now or _now()
    errors: list[str] = []
    with _LOCK:
        k = _COUNTER.get(f"{organ}#m", 0)
        _COUNTER[f"{organ}#m"] = k + 1
    from libs.ops import cn_ensemble as cn
    for r in rotation(rs, organ, stamp):
        if budget_s is not None and time.monotonic() - t0 > budget_s:
            errors.append("pass budget reached")
            break
        why, reset = cap_state(r, stamp, root, organ)
        if why:
            errors.append(f"{r.name}: {why}" + (f" until {reset}" if reset else ""))
            continue
        models = list(r.models) or [""]
        order = [models[(k + i) % len(models)] for i in range(min(MODELS_PER_ROUTE, len(models)))]
        for model in order:
            c0 = time.monotonic()
            text, served, err = _call(r, model, system, user, max_tokens=max_tokens,
                                      temperature=temperature)
            ok = bool(text and text.strip() and not err)
            credits = None
            if ok and r.weekly_cap > 0:
                with contextlib.suppress(Exception):
                    credits = cn.credits_of_last_call(r.weekly_cap)
            row: dict[str, Any] = {"at": _iso(_now()), "provider": r.name, "kind": r.kind,
                                   "model": served or model, "organ": organ,
                                   "job": job or organ, "ok": ok,
                                   "latency_s": round(time.monotonic() - c0, 2)}
            if credits:
                row["credits"] = credits
            if not ok:
                row["error"] = str(err or "empty response")[:120]
            _record(root, row)
            if r.kind == "cn" and r.relay:
                with contextlib.suppress(Exception):
                    cn._append((root or _ROOT) / cn.RELAY_LEDGER,
                               {"at": row["at"], "provider": r.weekly_name or r.name,
                                "model": row["model"], "organ": organ, "ok": ok,
                                **({"credits": credits} if credits else {})})
            if ok:
                return text, f"{r.name}/{served or model or 'discovered'}", None
            errors.append(f"{r.name}/{model or 'discovered'}: {err or 'empty'}"[:160])
            if err and r.kind == "openrouter_free":
                break                 # orf.complete already walked its own free rotation
    if not rs:
        return "", "", ("no free provider lit" + ("" if pub else
                                                   " for a private prompt (relays need public)"))
    return "", "", "; ".join(errors[-4:]) or "no free provider lit"


# ------------------------------------------------------------------------------ evidence ----
def _usage(root: Path | None, now: datetime) -> dict[str, dict[str, Any]]:
    since = now - timedelta(hours=24)
    out: dict[str, dict[str, Any]] = {}
    try:
        lines = _ledger_path(root).read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            row = json.loads(ln)
            t = datetime.fromisoformat(str(row.get("at")))
        except (ValueError, TypeError, AttributeError):
            continue
        if not isinstance(row, dict):
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        p = out.setdefault(str(row.get("provider") or "?"),
                           {"calls_24h": 0, "ok_24h": 0, "by_job": {}, "last_ok": None})
        if row.get("ok") and (p["last_ok"] is None or str(row.get("at")) > p["last_ok"]):
            p["last_ok"] = str(row.get("at"))
        if t < since:
            continue
        job = p["by_job"].setdefault(str(row.get("job") or row.get("organ") or "?"),
                                     {"calls": 0, "ok": 0})
        p["calls_24h"] += 1
        job["calls"] += 1
        if row.get("ok"):
            p["ok_24h"] += 1
            job["ok"] += 1
    return out


def build_report(*, now: datetime | None = None, root: Path | None = None,
                 env: Mapping[str, str] | None = None,
                 list_models: Callable[[str, str], list[str]] | None = None) -> dict[str, Any]:
    now = now or _now()
    rs = discover(env=env, root=root, list_models=list_models) \
        if (env is not None or list_models is not None) else _cached(root)
    use = _usage(root, now)
    rows: list[dict[str, Any]] = []
    for r in rs:
        status, why, reset = ("LIT", "", None) if r.lit else ("DARK", r.why, None)
        if r.lit:
            cw, reset = cap_state(r, now, root)
            if cw:
                status, why = "CAPPED", cw
        u = use.get(r.name, {})
        rows.append({
            "provider": r.name, "kind": r.kind, "key_envs": list(r.key_envs),
            "public_prompts_only": r.relay, "paid_tail": r.paid, "status": status,
            "why": why or None,
            "reset_at": reset, "models": list(r.models)[:12], "n_models": len(r.models),
            "daily_cap": r.daily_cap or None, "weekly_cap": r.weekly_cap or None,
            "calls_24h": int(u.get("calls_24h", 0)), "ok_24h": int(u.get("ok_24h", 0)),
            "by_job": u.get("by_job", {}), "last_ok": u.get("last_ok")})
    known = {r["provider"] for r in rows}
    for name, u in use.items():                # a route that served and has since gone
        if name not in known:
            rows.append({"provider": name, "kind": "?", "status": "DARK",
                         "why": "DARK: no longer configured on this host",
                         "calls_24h": u["calls_24h"], "ok_24h": u["ok_24h"],
                         "by_job": u["by_job"], "last_ok": u["last_ok"]})
    lit = [r for r in rows if r["status"] == "LIT"]
    return {
        "generated_at": _iso(now), "writer": "libs/ops/free_chain.py",
        "rule": ("every LLM key this host holds is one route of ONE shared free chain; ask() "
                 "rotates the starting route per call and fails over. A new key lights with no "
                 "code: FREE_LLM_<NAME>_KEY + FREE_LLM_<NAME>_BASE (https) [+ _MODELS, _DAILY, "
                 "_WEEKLY, _RELAY=1], or an entry in data/secrets/cn_providers.json. Relays get "
                 "public prompts only. No key value is ever written here."),
        "summary": {"providers": len(rows), "lit": len(lit),
                    "capped": sum(1 for r in rows if r["status"] == "CAPPED"),
                    "dark": sum(1 for r in rows if r["status"] == "DARK"),
                    "calls_24h": sum(int(r.get("calls_24h") or 0) for r in rows),
                    "ok_24h": sum(int(r.get("ok_24h") or 0) for r in rows),
                    "serving_24h": sum(1 for r in rows if int(r.get("ok_24h") or 0) > 0)},
        "providers": rows,
    }


def write_report(path: Path | None = None, **kw: Any) -> dict[str, Any]:
    doc = build_report(**kw)
    p = path or ((kw.get("root") or _ROOT) / REPORT)
    with contextlib.suppress(OSError):
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, p)
    return doc


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="publish FREE_MODEL_ROUTES.json")
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = write_report()
    s = doc["summary"]
    print(f"free chain: {s['lit']} lit / {s['capped']} capped / {s['dark']} dark of "
          f"{s['providers']}; {s['ok_24h']}/{s['calls_24h']} ok calls in 24h over "
          f"{s['serving_24h']} provider(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
