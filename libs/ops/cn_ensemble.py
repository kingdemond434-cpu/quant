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
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    "minimax/minimax-m3:free",
    "z-ai/glm-4.5-air:free",
    "z-ai/glm-5.2:free",
)

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
)

#: The research questions, chosen for what feeds the judge: new hypotheses, repairs of near
#: misses, recombinations, and what the public literature and filings say. Public briefs only.
ROLES: tuple[tuple[str, str], ...] = (
    ("edge_inventor", "invent economically grounded trading hypotheses for liquid FX, gold, "
                      "metals, energy and equity-index CFDs from first principles: who is forced "
                      "to trade, when, and why they cannot avoid it"),
    ("paper_reader", "recall published academic papers and working papers (SSRN, arXiv q-fin, "
                     "central-bank and BIS research) with a tradable, still-plausible effect in "
                     "those markets, and state each as a testable rule"),
    ("filings_and_flows", "public filings, auctions, fixings, index rebalances, option expiries, "
                          "commodity reports and central-bank operations that create predictable "
                          "flows in those markets"),
    ("china_market_lens", "what Chinese-language market research, onshore CNH/CNY flows, SGE and "
                          "SHFE gold and metals dynamics and Asia-session behaviour imply for "
                          "trading those markets during Asian hours"),
    ("regime_conditioner", "conditions (volatility, trend, rates, risk-on/off, calendar) under "
                           "which a simple price rule in those markets flips from losing to "
                           "winning, stated as a regime-gated rule"),
    ("recombiner", "combine two weak, unrelated public effects in those markets into one rule "
                   "whose parts are independent, and say why the combination should hold"),
    ("contrarian", "popular retail trading beliefs in those markets that are probably wrong, and "
                   "the trade that profits from the crowd acting on them"),
    ("microstructure", "intraday patterns in those markets from session opens and closes, "
                       "liquidity gaps, spread changes and stop clustering, stated as rules"),
)

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


def seat_for(p: Provider, env: Mapping[str, str] | None = None,
             list_models: Callable[[str, str], list[str]] | None = None) -> Seat:
    """The provider's seat, or a DARK seat saying why. Never raises, never prints a key."""
    e = os.environ if env is None else env
    key = str(e.get(p.key_env, "") or "").strip()
    if not key and p.name == "openrouter":
        try:
            from libs.ops.deepseek_cycle import resolve_key
            key = resolve_key(dict(e))[0]
        except Exception:
            key = ""
    base = str(e.get(p.base_env, "") or p.default_base).rstrip("/")
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
    else:
        try:
            listed = (list_models or _list_models)(base, key)
        except Exception as exc:
            return Seat(p, base, "", why=f"DARK: /models unreachable ({type(exc).__name__})")
        models = [m for m in listed if CN_FAMILY.search(m)]
        if not models:
            return Seat(p, base, "", why="DARK: the relay lists no Chinese-lab model")
    if not p.relay:
        models = [m for m in models if m.endswith(":free")]     # no paid id, ever
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
    left = llm_seat.free_budget_left(now)
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


def plan(seats: list[Seat], quotas: Mapping[str, int], start: int) -> list[tuple[Seat, str, str]]:
    """(seat, model, role) calls for this run: round-robin over roles, and for each role the
    next model in a rotation across EVERY lit provider, so one hour spreads over as many
    different models as its quota allows (the diversity is the point)."""
    pool = [(s, m) for s in seats if s.lit for m in s.models]
    if not pool:
        return []
    left = dict(quotas)
    calls: list[tuple[Seat, str, str]] = []
    i = start
    tries = 0
    total = sum(max(0, v) for v in quotas.values())
    while len(calls) < total and tries < total * len(pool) + len(pool):
        s, m = pool[i % len(pool)]
        role = ROLES[(start + len(calls)) % len(ROLES)][0]
        if left.get(s.provider.name, 0) > 0:
            calls.append((s, m, role))
            left[s.provider.name] -= 1
        i += 1
        tries += 1
    return calls


def run(now: datetime | None = None, *, root: Path | None = None,
        env: Mapping[str, str] | None = None,
        chat: Callable[[Seat, str, str, str], tuple[str, str | None]] | None = None,
        list_models: Callable[[str, str], list[str]] | None = None,
        quotas: Mapping[str, int] | None = None, deadline_s: float = 1500.0) -> dict[str, Any]:
    """One hourly pass. Never raises; every outcome is in the report."""
    import time
    t0 = time.monotonic()
    now = now or _now()
    base = root or _ROOT
    e = os.environ if env is None else env
    seats = [seat_for(p, e, list_models) for p in PROVIDERS]
    if quotas is None:
        share = float(e.get("CN_ENSEMBLE_OPENROUTER_SHARE", "0.35") or 0.35)
        relay_daily = int(e.get("CN_ENSEMBLE_RELAY_DAILY", "240") or 240)
        q: dict[str, int] = {}
        for s in seats:
            if not s.lit:
                continue
            if s.provider.relay:
                left = relay_daily - _relay_calls_today(base, s.provider.name, now)
                q[s.provider.name] = max(0, -(-left // max(1, 24 - now.hour)))
            else:
                try:
                    q[s.provider.name] = openrouter_quota(now, share)
                except Exception:
                    q[s.provider.name] = 0
        quotas = q
    start = int(now.timestamp() // 3600)
    calls = plan(seats, quotas, start)
    briefs = dict(ROLES)
    ideas: dict[str, dict[str, Any]] = {}
    outcomes: list[dict[str, Any]] = []
    do = chat or _chat
    try:
        workers = max(1, min(8, int(e.get("CN_ENSEMBLE_WORKERS", "4") or 4)))
    except ValueError:
        workers = 4

    def one(call: tuple[Seat, str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        seat, model, role = call
        head = {"provider": seat.provider.name, "model": model, "role": role}
        if time.monotonic() - t0 > deadline_s:
            return {**head, "status": "DEADLINE"}, []
        user = f"RESEARCH QUESTION ({role}): {briefs[role]}."
        try:
            assert_public(SYSTEM, user)
        except ValueError as exc:
            return {**head, "status": "REFUSED_PRIVATE", "why": str(exc)}, []
        try:
            text, err = do(seat, model, SYSTEM, user)
        except Exception as exc:
            text, err = "", f"{type(exc).__name__}: {exc}"
        if seat.provider.relay:
            _append(base / RELAY_LEDGER, {"utc": _iso(_now()), "relay": seat.provider.name,
                                          "model": model, "ok": not err})
        if err:
            return {**head, "status": "CALL_FAILED", "why": str(err)[:300]}, []
        found = _parse(text)
        return {**head, "status": "OK", "n_findings": len(found)}, found

    # A few calls in flight at once: free reasoning models take a minute each, and the hourly
    # box task has a hard 45-minute ceiling shared with the DeepSeek cycle that runs first.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, calls))
    for (_seat, model, role), (outcome, found) in zip(calls, results, strict=True):
        outcomes.append(outcome)
        for f in found:
            k = _key(str(f["title"]))
            if not k:
                continue
            row = ideas.setdefault(k, {**f, "models": [], "roles": []})
            if model not in row["models"]:
                row["models"].append(model)
            if role not in row["roles"]:
                row["roles"].append(role)
    path = _donate(list(ideas.values()), now, base) if ideas else None
    by_model: dict[str, dict[str, int]] = {}
    for o in outcomes:
        b = by_model.setdefault(f"{o['provider']}:{o['model']}", {"calls": 0, "ok": 0, "ideas": 0})
        b["calls"] += 1
        b["ok"] += o["status"] == "OK"
        b["ideas"] += int(o.get("n_findings") or 0)
    report = {
        "generated_utc": _iso(now),
        "authority": "PROPOSE ONLY: no sizing, capital, promotion or live-trading authority",
        "prompt_policy": "public text only; assert_public refuses any desk-shaped content",
        "providers": {s.provider.name: {"lit": s.lit, "why": s.why, "models": list(s.models),
                                        "quota_this_run": int(quotas.get(s.provider.name, 0))}
                      for s in seats},
        "calls": len(outcomes),
        "ok_calls": sum(o["status"] == "OK" for o in outcomes),
        "distinct_ideas": len(ideas),
        "single_model_ideas": sum(len(r["models"]) == 1 for r in ideas.values()),
        "multi_model_ideas": sum(len(r["models"]) > 1 for r in ideas.values()),
        "by_model": by_model,
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
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def _donate(rows: list[dict[str, Any]], now: datetime, base: Path) -> Path:
    """The miner-discovery contract the compiler reads (`data/intelligence/**`)."""
    from libs.data.pit import stamp_or_refuse
    from libs.research.source_provenance import stamp_row
    out = base / DONATE_DIR
    out.mkdir(parents=True, exist_ok=True)
    gen = _iso(now)
    path = out / f"discoveries_{now.strftime('%Y%m%dT%H%M%S')}.json"
    stamped, refused = stamp_or_refuse([stamp_row({
        "source": "cn_ensemble", "title": str(r["title"])[:200],
        "symbols": [str(x).upper() for x in (r.get("symbols") or []) if str(x).strip()][:8],
        "type": "MECHANISM_HYPOTHESIS", "kind": "hypothesis", "family": None,
        "mechanism": str(r.get("mechanism") or "")[:1000],
        "testable_claim": str(r.get("testable_claim") or "")[:1000],
        "horizon": r.get("horizon"), "public_source": r.get("source"),
        "models": r["models"], "roles": r["roles"],
        "consensus": len(r["models"]),
        "url": f"cn_ensemble://{r['roles'][0]}/{_key(str(r['title']))[:40].replace(' ', '_')}",
    }, ground="cn_ensemble", retrieved_at=gen) for r in rows], "cn_ensemble")
    path.write_text(json.dumps({"source": "cn_ensemble", "generated_at": gen,
                                "refused": len(refused), "discoveries": stamped},
                               indent=1, default=str), "utf-8")
    return path
