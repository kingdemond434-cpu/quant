"""L1.54 routing, as one primitive every LLM organ can reach: a CHAIN, never a single name.

WHY THIS IS A LIBRARY AND NOT A PATTERN TO COPY. Twelve organs on this desk read
data/secrets/llm_panel.json -- the panel scorer, the code auditor, the collector author, the meta
architect, the breadth expander, deep review, the micro audit, the external panel, and the
hunters. Eleven of them resolve ONE model and stop. kimi_hunter proved what that costs: scheduled
56 times a week, one unavailable model string, and it had produced literally nothing since it was
built -- no artifact, no ledger row, no complaint. Copying the fix into eleven more files would
guarantee eleven slightly different fixes and eleven separate regressions.

THE RULE THIS ENCODES. A route failing ends that ATTEMPT and nothing else. Free and degraded tiers
sit at the END of the chain and are never omitted: a free-tier answer is worth immeasurably more
than no answer, and "the account is unfunded" is a reason to route cheaper, never a reason to stop.

WHAT IT DELIBERATELY DOES NOT DO. It does not lower any bar, retry a REFUSAL, or paper over an
empty answer. Degradation buys ATTEMPTS, never leniency (L1.54 clause 2), so callers are handed
the model that actually answered and are expected to record it -- a fallback result must stay
attributable and re-runnable on the preferred route later.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: Hosts that route by the request's `model` field rather than by which model the credential was
#: filed under. For these, ANY seat can serve ANY model in the chain -- which is exactly the fact
#: kimi_hunter was missing when a roster full of OpenRouter seats yielded "not in the seated
#: roster" and an immediate exit.
#:
#: THE TEST FOR MEMBERSHIP IS A PROPERTY, NOT A PREFERENCE: an OpenAI-compatible gateway that
#: dispatches on the request body's `model`. `opencode` (OpenCode Zen) qualifies and is listed so
#: that adding a Zen seat to the roster is a CREDENTIAL change with no code change -- the desk
#: should never have to ship a commit to gain a route. Listing a host here grants nothing on its
#: own: `build_chain` only ever considers seats that actually exist in `llm_panel.json`, so an
#: unused entry costs nothing and an added key works immediately.
#:
#: AND IT IS AN ADDITION, NEVER A SWAP. L1.54's whole claim is that depth beats picking a better
#: single name: the failure it was written for -- one unavailable model string, 56 scheduled runs
#: a week, zero artifacts and no complaint -- is a SINGLE-ROUTE failure, and replacing one gateway
#: with another reproduces its exact shape at a different address.
MODEL_ROUTING_HOSTS: Final[tuple[str, ...]] = ("openrouter", "opencode")


@dataclass(frozen=True)
class Route:
    """One (model, endpoint, credential) worth trying. Frozen: a caller cannot teach the chain."""

    model: str
    base_url: str
    key: str
    #: True when this route is a free/degraded tier. Carried so a caller can record HOW it got its
    #: answer -- never so it can be quietly skipped.
    free: bool = False

    @property
    def label(self) -> str:
        return f"{self.model}{' [free]' if self.free else ''}"


def load_seats(keys_path: Path) -> list[dict[str, Any]]:
    """Roster seats that carry BOTH a base_url and a key, or [] .

    Returns [] for an absent, unreadable or malformed roster rather than raising: this is called
    from scheduled organs, and a broken credentials file must produce a recorded blocker, not a
    traceback that kills the run before it can write one.
    """
    try:
        raw = json.loads(keys_path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    providers = raw.get("providers") if isinstance(raw, dict) else None
    if not isinstance(providers, list):
        return []
    return [p for p in providers
            if isinstance(p, dict) and p.get("base_url") and p.get("key")]


def build_chain(model_chain: Sequence[str], keys_path: Path) -> list[Route]:
    """Every route worth trying, in preference order, from a model chain and a roster.

    Ordering is the caller's chain, and within each model: the EXACT seat first (a credential
    filed under that model is the most likely to work), then any model-routing host that can serve
    it. Duplicates are dropped so one seat is not tried twice for the same model.

    An empty result is a real answer and the caller must record it as a blocker. This function
    never invents a route, and never reorders a free tier ahead of a paid one -- the chain's order
    IS the policy.
    """
    seats = load_seats(keys_path)
    routable = [p for p in seats
                if any(h in str(p.get("base_url", "")).lower() for h in MODEL_ROUTING_HOSTS)]
    out: list[Route] = []
    seen: set[tuple[str, str]] = set()
    for model in model_chain:
        exact = [p for p in seats if p.get("model") == model]
        for p in [*exact, *routable]:
            k = (model, str(p["base_url"]))
            if k in seen:
                continue
            seen.add(k)
            out.append(Route(model=model, base_url=str(p["base_url"]), key=str(p["key"]),
                             free=model.endswith(":free")))
    return out


def chain_is_sound(model_chain: Sequence[str]) -> tuple[bool, str]:
    """Is this chain actually a chain? (ok, reason).

    Checks the three properties that make a chain worth having, because a chain that fails any of
    them is a single point of failure wearing a list's clothing:

      * DEPTH -- more than a token second entry.
      * FAMILY DIVERSITY -- fallbacks from one vendor share a prior and, for exploration work,
        share a blind spot. Four versions of one model is one opinion, four times.
      * A FREE TAIL, LAST -- present, so an unfunded account degrades instead of stopping; last,
        so it is never preferred over a paid route that would answer.
    """
    if len(model_chain) < 3:
        return False, f"chain has {len(model_chain)} entr(ies) -- that is a preference, not a chain"
    families = {m.split("/")[0] for m in model_chain}
    if len(families) < 2:
        return False, (f"all routes are {families} -- a fallback must change the lens, "
                       "not the version")
    free = [i for i, m in enumerate(model_chain) if m.endswith(":free")]
    if not free:
        return False, "no free tier -- an unfunded account has nowhere to degrade to"
    paid = [i for i, m in enumerate(model_chain) if not m.endswith(":free")]
    # FREE-FIRST IS A DELIBERATE POLICY, NOT THE ACCIDENT THIS RULE WAS WRITTEN AGAINST.
    # "Free tiers go last" existed to stop a free route being preferred over a paid one that
    # WOULD HAVE ANSWERED -- an accident that silently costs quality. Under LLM_FREE_FIRST the
    # ordering is the principal's standing instruction (2026-08-26), taken on measured evidence:
    # paid seats produced 0 of 27 accepted findings while free/self organs produced all of them,
    # and the account is unfunded by choice. Intent, not oversight -- so the guard reports the
    # policy instead of failing it. Unset the flag and the original rule applies unchanged.
    if os.environ.get("LLM_FREE_FIRST") == "1":
        return True, (f"{len(model_chain)} routes across {len(families)} families, FREE-FIRST "
                      f"policy active ({len(free)} free tier(s) leading)")
    if paid and min(free) < max(paid):
        return False, "a free tier is ordered ahead of a paid route -- free tiers go last"
    return True, (f"{len(model_chain)} routes across {len(families)} families, "
                  f"{len(free)} free tier(s) at the tail")


def prefer_free(model_chain: Sequence[str]) -> list[str]:
    """Reorder a chain free-first when the free-first policy is active, else return it unchanged.

    THE CHAIN IS REORDERED, NOT THE BUILDER. `build_chain` documents that the caller's order IS
    the policy and deliberately never reorders -- so the honest place to express a routing
    preference is the chain handed to it. Relative order WITHIN each tier is preserved, so a
    caller's family-diversity intent survives the flip.
    """
    if os.environ.get("LLM_FREE_FIRST") != "1":
        return list(model_chain)
    free = [m for m in model_chain if m.endswith(":free")]
    paid = [m for m in model_chain if not m.endswith(":free")]
    # Paid routes are KEPT, not deleted: an organ explicitly allowed to spend (ALLOW_PAID=1)
    # still has somewhere to go, and a free tier that refuses or empties still degrades upward
    # rather than dead-ending. Free-first changes the ORDER, never the options.
    return [*free, *paid]
