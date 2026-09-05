"""Zero-cost model panel: the desk keeps thinking when the card is empty and nobody is watching.

WHY THIS EXISTS (principal, 2026-08-29)

    "nothing should rely on claude limit or wait for it"
    "exploit all roi free openrouter models 24/7 for research generation, cold audits,
     feedbacks, reviews"

Measured the same day, and it is the single largest gap on the desk:

    data/hypothesis_queue.jsonl        HAS NEVER EXISTED
    scripts/hypothesis_generator.py    marked UNTESTED since written, on NO timer
    consumers of that queue             FOUR scripts read a file that was never created
    cause                               OpenRouter balance: 60 purchased, 60.59 used

The mechanism-generating role -- the only component that gives a candidate an economic reason to
exist -- has never run once, because a $60 balance ran out and a 402 killed the whole role instead
of degrading it. That is why 84% of the docket carries no declared mechanism, and it explains the
0.33% yield better than any research-architecture argument does.

THIRTEEN MODELS ANSWER ON AN OVERDRAWN KEY. Probed 2026-08-29: 13 of 19 zero-cost text models
returned normally, three were rate-limited (temporary), two are agentic-only. A free model
produces weaker hypotheses than a flagship. It produces INFINITELY more than a 402 does, and every
one still faces the identical gauntlet -- so the downside is trials spent on weaker ideas and the
upside is the role existing at all.

ROLES GET DIFFERENT TIERS, because the jobs are not equally hard. Generation needs reasoning and
gets the large models; a cold audit is mostly recall and comparison and runs fine on a small fast
one. Spending the largest free model on a formatting check wastes the rate limit that generation
needs.

RATE LIMITS ARE STATE, NOT ERRORS. A 429 means "this model, right now" -- not "this model is
broken". `mark_limited` records it with a cooldown so the next call rotates rather than retrying
into the same wall, and the cooldown expires on its own. Treating a 429 as a failure is how a
panel of thirteen degrades to a panel of one.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PANEL_KEY = ROOT / "data" / "secrets" / "llm_panel.json"
STATE = ROOT / "data" / "free_panel_state.json"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

#: Verified answering on an overdrawn key, 2026-08-29. Ordered by capability within each tier.
#: `openrouter/free` is a router alias that picks whatever free capacity exists, so it is the
#: last resort that is most likely to answer when everything specific is rate-limited.
HEAVY = (
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "minimax/minimax-m3:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "poolside/laguna-s-2.1:free",
    # Transiently 429'd on the first probe rather than refusing. A rate limit is a moment, not a
    # property, and excluding a model for one busy minute permanently shrinks the panel.
    "z-ai/glm-5.2:free",
    "google/gemma-4-31b-it:free",
)
LIGHT = (
    "nvidia/nemotron-3.5-lightning:free",
    "inclusionai/ling-3.0-flash-fin:free",
    "minimax/minimax-m2.7:free",
    "dots-studio/dots-3-note-preview:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "liquid/lfm-2.5-2.6b:free",
    "google/gemma-4-26b-a4b-it:free",
    "poolside/laguna-xs-2.1:free",
    "openrouter/free",
)

#: MILLION-TOKEN CONTEXT, FREE. The largest under-exploitation found on 2026-08-29: these models
#: accept ~1M tokens and the desk was sending them a few hundred. That is the difference between
#: asking "propose a mechanism" and asking "here is the ENTIRE research state -- every
#: certificate, the full graveyard, the measured funnel, the coverage map -- now tell me what
#: this desk is systematically failing to see".
#:
#: A model that can hold the whole desk at once can answer questions no paginated prompt can:
#: which mechanism is absent across every market, which failure repeats across unrelated
#: families, where the search has a blind spot rather than a gap. Those are exactly the questions
#: worth a free call.
DEEP = (
    "minimax/minimax-m3:free",                    # 1,048,576
    "nvidia/nemotron-3.5-lightning:free",         # 1,000,000
    "nvidia/nemotron-3-ultra-550b-a55b:free",     # 1,000,000
    "thinkingmachines/inkling:free",              # 1,048,576 (agentic-gated; tried last)
    "dots-studio/dots-3-note-preview:free",       # 512,000
)

#: Which tier each research role draws from. GENERATION and REVIEW are reasoning-heavy; an audit
#: that only has to compare a claim against a list does not need a 550B model, and taking one
#: starves generation of the shared rate limit.
ROLE_TIER: dict[str, tuple[str, ...]] = {
    # Roles that benefit from seeing the WHOLE desk at once get the million-token tier.
    "deep_audit": DEEP,
    "weakness": DEEP,
    "survivor_hunt": DEEP,
    "full_state": DEEP,
    "generation": HEAVY,
    "mechanism": HEAVY,
    "review": HEAVY,
    "falsify": HEAVY,
    "audit": LIGHT,
    "feedback": LIGHT,
    "classify": LIGHT,
    "hunt": HEAVY,
}

#: How long a rate-limited model sits out. Long enough that rotation is real, short enough that a
#: brief limit does not remove a model for the day.
COOLDOWN_S = 900

#: Free tiers are slow and sometimes queue. A generous timeout costs nothing on a free model and
#: a mean one turns capacity into failures.
TIMEOUT_S = 180


class PanelExhausted(RuntimeError):
    """Every model in the tier is cooling down or refusing.

    Raised so a caller can wait rather than guess -- capacity is not a defect.
    """


def _load_key() -> str:
    d = json.loads(PANEL_KEY.read_text("utf-8"))
    provs = d.get("providers")
    rows = provs if isinstance(provs, list) else [
        {"name": k, **(v or {})} for k, v in (provs or {}).items()]
    for c in rows:
        k = c.get("api_key") or c.get("key")
        if k:
            return str(k)
    raise PanelExhausted("no API key in the llm panel")


def _state() -> dict[str, Any]:
    try:
        loaded = json.loads(STATE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"limited": {}, "calls": {}, "failures": {}}
    return loaded if isinstance(loaded, dict) else {"limited": {}, "calls": {}, "failures": {}}


def _save(st: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1), "utf-8")


def mark_limited(model: str, seconds: int = COOLDOWN_S) -> None:
    st = _state()
    st.setdefault("limited", {})[model] = time.time() + seconds
    _save(st)


def available(tier: tuple[str, ...]) -> list[str]:
    """Models in this tier not currently cooling down, least-used first.

    Least-used-first rather than random: free tiers rate-limit per model, so spreading calls
    evenly is what keeps thirteen models usable instead of hammering the first one until it 429s
    and then discovering the second.
    """
    st = _state()
    now = time.time()
    limited = {m: t for m, t in (st.get("limited") or {}).items() if t > now}
    calls = st.get("calls") or {}
    live = [m for m in tier if m not in limited]
    return sorted(live, key=lambda m: calls.get(m, 0))


@dataclass
class Reply:
    text: str
    model: str
    attempts: list[str] = field(default_factory=list)


def ask(role: str, system: str, user: str, *, max_tokens: int = 2000,
        temperature: float = 0.9) -> Reply:
    """Ask the free panel, rotating on rate limits. Never charges the account.

    Rotation is the whole design. A single free model is a single point of failure with a rate
    limit attached; thirteen rotated by least-used is a research capacity that runs all day.
    """
    tier = ROLE_TIER.get(role, LIGHT)
    key = _load_key()
    tried: list[str] = []
    for model in available(tier) or list(tier):
        body = json.dumps({
            "model": model, "max_tokens": max_tokens, "temperature": temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        tried.append(model)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                out = json.loads(r.read())
            msg = out["choices"][0]["message"]
            text = str(msg.get("content") or msg.get("reasoning") or "").strip()
            if not text:
                # An empty completion is a failure that looks like success, and downstream code
                # would treat it as "the model had nothing to say" rather than "the call broke".
                continue
            st = _state()
            st.setdefault("calls", {})[model] = st.get("calls", {}).get(model, 0) + 1
            _save(st)
            return Reply(text=text, model=model, attempts=tried)
        except urllib.error.HTTPError as e:
            if e.code in (429, 402, 403):
                mark_limited(model, COOLDOWN_S if e.code == 429 else COOLDOWN_S * 4)
            st = _state()
            st.setdefault("failures", {})[model] = str(e.code)
            _save(st)
            continue
        except Exception:
            continue
    raise PanelExhausted(
        f"every model in the '{role}' tier is cooling down or refusing (tried {tried}). This is "
        f"a capacity state, not a defect -- the cooldown expires on its own; retry later rather "
        f"than falling back to a paid model on an overdrawn balance.")


def panel_health() -> dict[str, Any]:
    st = _state()
    now = time.time()
    limited = {m: round(t - now) for m, t in (st.get("limited") or {}).items() if t > now}
    return {
        "heavy_available": len(available(HEAVY)), "heavy_total": len(HEAVY),
        "light_available": len(available(LIGHT)), "light_total": len(LIGHT),
        "cooling_down": limited,
        "calls": st.get("calls", {}),
        "note": ("a cooling model is capacity state, not a defect; treating a 429 as failure is "
                 "how a panel of thirteen degrades to a panel of one"),
    }
