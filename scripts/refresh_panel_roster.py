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
    # Fill labs with no representative. Target set = the labs THIS roster holds, plus the seed
    # list -- so a delisted seat's lineage is restored AND the board can still grow into a lab it
    # has never held, while the four evidence-retired labs (removed from the seed above) can
    # never come back. Roster-first ordering keeps existing lineages ahead of new ones.
    target_labs = tuple(dict.fromkeys([_family(m) for m in current] + list(_LABS)))
    for lab in target_labs:
        if lab not in covered:
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
