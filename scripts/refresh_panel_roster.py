"""Refresh the advisory-panel roster from the live OpenRouter catalog (monthly).

Two jobs, both serving COGNITIVE DIVERSITY (the panel's entire value -- different labs =
different training = different blind spots; a stale or converging roster becomes a monoculture
that shares blind spots, the exact single-reviewer trap the panel exists to break):
  1. DROP dead model IDs (they 404 silently = one fewer reviewer).
  2. Keep ONE strong, recent model per distinct LAB, across the widest set of labs available,
     so the roster stays maximally diverse and current as new frontier models appear.

Conservative + reversible: backs up the old config, logs every change, preserves the API key,
and never trusts a new pick blindly -- the hit-rate scorer (score_panel.py) down-weights bad
additions over time. Advisory-only output, so a wrong pick just yields advice that gets rejected.
Run at monthly governance: `python scripts/refresh_panel_roster.py` (add --apply to write).
"""

from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import certifi

_KEYS = Path("data/secrets/llm_panel.json")
_LOG = Path("data/panel_roster_log.jsonl")
_CATALOG = "https://openrouter.ai/api/v1/models"
_CAPS_OUT = Path("data/roster_capabilities.json")
_CTX = ssl.create_default_context(cafile=certifi.where())

# BOOTSTRAP SEED ONLY -- used when there is no roster yet to learn the lab set from. The
# fill-empty-labs loop targets the labs the LIVE roster actually holds (see select_roster), never
# this literal.
#
# WHY: this list was the target set, and it went stale against deliberate decisions. It still
# names mistralai, meta-llama, cohere and microsoft -- all four RETIRED on evidence (ledger #116
# replaced cohere/command-a and microsoft/wizardlm; #118 dropped meta-llama after llama-4-maverick
# failed the capacity probe twice and muse-spark returned 403). Because the loop fills any lab
# "missing" from this tuple, an `--apply` run would have RE-ADDED those four -- taking the roster
# from 13 seats to ~17 and re-seating the exact models the desk measured as broken. A refresh that
# resurrects retired downgrades is the opposite of a refresh, so the target set is now DERIVED.
# anthropic stays excluded everywhere: the CRO is Claude, so an external Claude adds no
# cognitive diversity.
_LABS = ("x-ai", "openai", "google", "deepseek", "qwen", "z-ai", "moonshotai", "nvidia")

# MAX BREADTH (2026-07-29). The fill loop could only ever seat a lab named in `_LABS` or already
# on the roster, so a brand-new frontier lab appearing on OpenRouter could NEVER be seated -- the
# board's diversity was capped at labs someone had once typed into this file. Cognitive diversity
# is the panel's entire value, so the target set is now DISCOVERED from the live catalog and the
# exclusions are stated as an explicit deny-list instead of being implied by a short allow-list.
#
# Deny beats allow here because the reasons are specific and durable, and an allow-list silently
# excludes everything nobody thought of -- which is exactly the failure being fixed.
_DENY_LABS = {
    # Independence policy, permanent: the CRO is Claude. An external Claude shares its training,
    # its priors and its blind spots, so it adds a seat without adding an independent view.
    "anthropic": "the brain is Claude -- an external Claude adds no cognitive diversity",
    # Evidence-retired (ledger #116, #118). Re-adding these is a measured downgrade, not growth.
    "mistralai": "retired on evidence (ledger #116)",
    "meta-llama": "retired -- llama-4-maverick failed the capacity probe twice (ledger #118)",
    "cohere": "retired -- command-a replaced (ledger #116)",
    "microsoft": "retired -- wizardlm replaced (ledger #116)",
}

#: Seat cap. NOT a diversity opinion -- a budget one, and stated as such so it is revisited when
#: the budget is. Measured cost is ~$3-5/run against a $100-150/mo envelope at weekly cadence,
#: so ~24 seats is affordable with headroom. Growth beyond the cap is a spend decision for the
#: principal, never a silent one taken by a refresh script.
MAX_SEATS = 24
# variants that are NOT strong general adversarial reviewers -> never auto-pick as a fill.
# "newest created" != "most capable" (flash/medium/mini are often newer AND weaker), so weak
# tiers are excluded and, crucially, working models are NEVER auto-swapped (see select_roster).
_EXCLUDE = ("image", "vision", "-vl", "audio", "tts", "whisper", "embed", "rerank", "moderation",
            "guard", "safety", "coder", "-code", "-mini", "-nano", "-lite", "lyria", "-oss",
            # `:free` added 2026-07-28 -- ledger #116 records the free tier rate-limiting and
            # returning BLANKS, which inside a consensus panel is a silent seat loss. A dead-seat
            # replacement could previously pick one; reliability costs pennies, so never again.
            ":free",
            "distill", "content-safety", "-air", "flash", "medium", "small", "phi", "haiku",
            "turbo", "-8b", "-4b", "-3b", "-1b")


def _family(model_id: str) -> str:
    return model_id.split("/", 1)[0].lower()


def _newest_strong(models: list[dict[str, Any]], lab: str) -> str | None:
    """Newest non-weak model for a lab (used only to REPLACE a dead pick or FILL an empty lab)."""
    best, best_ts = None, -1.0
    for m in models:
        mid = str(m.get("id", ""))
        if _family(mid) != lab or any(x in mid.lower() for x in _EXCLUDE):
            continue
        ts = float(m.get("created") or 0)
        if ts > best_ts:
            best, best_ts = mid, ts
    return best


def discover_labs(models: list[dict[str, Any]]) -> list[str]:
    """Every lab in the live catalog offering at least one non-excluded model, best-first.

    This is what turns the roster from "the eight labs in a literal" into "every strong lab that
    exists". Ordered by the recency of each lab's best qualifying model so that, when the seat
    cap binds, the labs shipping current frontier work are seated ahead of dormant ones -- the
    cap should cost the desk its least interesting seats, not its arbitrary ones.

    `_DENY_LABS` is applied here AND at the fill site. Belt and braces on purpose: this list is
    the one place a retired lab could silently walk back onto the board, and the whole reason the
    old seed tuple carried a paragraph of warning was that it had already happened once.
    """
    best: dict[str, float] = {}
    for m in models:
        mid = str(m.get("id", ""))
        lab = _family(mid)
        if not lab or lab in _DENY_LABS or any(x in mid.lower() for x in _EXCLUDE):
            continue
        ts = float(m.get("created") or 0)
        if ts > best.get(lab, -1.0):
            best[lab] = ts
    return [lab for lab, _ in sorted(best.items(), key=lambda kv: -kv[1])]


def select_roster(models: list[dict[str, Any]], key: str, base_url: str,
                  current: list[str] | None = None) -> list[dict[str, str]]:
    """CONSERVATIVE refresh (pure -> testable): KEEP every current model that still exists, only
    REPLACE dead ones and FILL labs with no representative. Never auto-swaps a working flagship
    for a merely-newer variant (that risks a capability downgrade -- deliberate upgrades happen
    at monthly review from the 'upgrades available' log, not here)."""
    live = {str(m.get("id", "")) for m in models}
    current = current or []
    roster: list[dict[str, str]] = []
    covered: set[str] = set()
    for mid in current:                                  # keep-alive: preserve working picks
        lab = _family(mid)
        # A denied lab is never kept alive and never replaced in-lineage. Keep-alive is the one
        # path that could carry a retired lab -- or an anthropic seat, breaking the independence
        # policy outright -- forward forever without any decision being made, purely because it
        # was already there.
        if lab in _DENY_LABS:
            print(f"roster: DROPPING {mid} -- {_DENY_LABS[lab]}")
            continue
        if mid in live:
            roster.append({"name": lab.split("-")[-1], "base_url": base_url, "key": key,
                           "model": mid})
            covered.add(lab)
        else:                                            # dead -> replace within the same lab
            repl = _newest_strong(models, lab)
            if repl:
                roster.append({"name": lab.split("-")[-1], "base_url": base_url, "key": key,
                               "model": repl})
                covered.add(lab)
    # Fill labs with no representative. Target set = the labs THIS roster holds, then the seed,
    # then EVERY OTHER LAB THE LIVE CATALOG OFFERS A STRONG MODEL FROM. That last group is the
    # 2026-07-29 change: previously the loop could only seat a lab someone had already typed into
    # `_LABS`, so a new frontier lab appearing on OpenRouter was unreachable and the board's
    # diversity was capped by this file rather than by the market. Roster-first ordering keeps
    # existing lineages ahead of new ones, so growth never displaces a working seat.
    target_labs = tuple(dict.fromkeys(
        [_family(m) for m in current] + list(_LABS) + discover_labs(models)))
    for lab in target_labs:
        if len(roster) >= MAX_SEATS:
            break
        if lab in _DENY_LABS or lab in covered:
            continue
        pick = _newest_strong(models, lab)
        if pick:
            roster.append({"name": lab.split("-")[-1], "base_url": base_url, "key": key,
                           "model": pick})
    return roster


def main() -> None:
    apply = "--apply" in sys.argv
    cfg = json.loads(_KEYS.read_text("utf-8"))
    key = cfg["providers"][0]["key"]
    base = cfg["providers"][0].get("base_url", "https://openrouter.ai/api/v1")
    try:
        with urllib.request.urlopen(urllib.request.Request(_CATALOG), timeout=30,
                                    context=_CTX) as r:
            models = json.loads(r.read())["data"]
    except Exception as e:
        print(f"roster: catalog unreachable ({e!r}) -- keeping current roster")
        return
    catalog_ids = {str(m.get("id", "")) for m in models}
    # RECORD WHAT EACH SEAT CAN ACTUALLY DO. Until 2026-08-02 every organ sent
    # a hardcoded middle-rung reasoning effort -- six copies, none derived from the seat.
    # "high" reads like a maximum and is the middle rung of a ladder whose top differs per model
    # and per month, so a flagship the desk pays for was being asked a shallower question than it
    # can answer, and the call succeeded either way so the cost never surfaced. This is the only
    # place with a live catalog, so it is the only place that can turn capability into DATA.
    _caps = {str(m.get("id", "")): sorted(str(x) for x in (m.get("supported_parameters") or []))
             for m in models if m.get("id")}
    _CAPS_OUT.parent.mkdir(parents=True, exist_ok=True)
    _CAPS_OUT.write_text(json.dumps({
        "ts": datetime.now(tz=UTC).isoformat(),
        "source": _CATALOG,
        "_": ("model id -> declared supported_parameters. libs/llm/effort.py reads this to ask "
              "each seat for the DEEPEST reasoning rung it advertises. A seat missing here falls "
              "back to the old 'high' literal and says so, because inventing a parameter name "
              "produces a request the provider rejects -- or silently ignores while the desk "
              "believes it bought deeper reasoning."),
        "models": _caps,
    }, indent=1), "utf-8")
    print(f"roster: recorded capabilities for {len(_caps)} catalog model(s) -> {_CAPS_OUT}")
    old = [p["model"] for p in cfg["providers"]]
    dead = [m for m in old if m not in catalog_ids]
    new_roster = select_roster(models, key, base, current=old)
    new = [p["model"] for p in new_roster]
    added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    # UPGRADES AVAILABLE (report only, never auto-applied): labs where a NEWER strong model
    # than the current pick exists -> surfaced for DELIBERATE monthly-review upgrade.
    upgrades = []
    for mid in new:
        newest = _newest_strong(models, _family(mid))
        if newest and newest != mid:
            upgrades.append(f"{mid} -> {newest}")
    print(f"roster: {len(new)} labs | dead (auto-replaced): {dead or 'none'}")
    print(f"  + {added or 'none'}")
    print(f"  - {removed or 'none'}")
    print(f"  upgrades available (review before adopting): {upgrades or 'none'}")
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), "applied": apply,
                            "dead": dead, "added": added, "removed": removed,
                            "upgrades_available": upgrades, "roster": new}) + "\n")
    if apply and new_roster:
        _KEYS.with_suffix(".json.bak").write_text(_KEYS.read_text("utf-8"), "utf-8")
        _KEYS.write_text(json.dumps({"providers": new_roster}, indent=1), "utf-8")
        print(f"roster APPLIED ({len(new_roster)} models); backup -> {_KEYS}.bak")
    elif not apply:
        print("roster: dry-run (add --apply to write). Monthly governance applies after review.")


if __name__ == "__main__":
    main()
