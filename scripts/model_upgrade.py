"""AUTO-UPGRADE the advisory-panel roster to newer flagship models -- EVIDENCE-GATED.

THE PROBLEM WITH THE OLD POLICY (refresh_panel_roster.py, ledger #98): it was deliberately
built NEVER to upgrade -- it keeps every working pick and only prints "upgrades available" for a
human to adopt by hand. That conservatism was CORRECT for its evidence base: ranking by the
catalog's `created` date picks downgrades (gemini-pro -> gemma-free), because catalog metadata
cannot judge capability. But the consequence was that nothing upgraded unless a human remembered
to look, and the seats aged (llama-4-maverick sat 15 months stale until the principal noticed).

THIS SCRIPT KEEPS THE RULE AND CHANGES THE EVIDENCE. A candidate is never adopted because it is
NEWER. It is adopted because it PASSED A LIVE GAUNTLET the incumbent's own failures defined --
every probe here exists because a real seat failed exactly that way:

  A LIVE       non-empty answer to a trivial prompt.      (muse-spark: 403 despite a 1M listing;
                                                           llama-4-scout: HTTP 400)
  C FORMAT     >=1 parseable row in the desk's finding    (gpt-5.6-terra-pro: 0 parseable rows on
               format.                                     5 of 6 breadth lenses)
  D HONESTY    must say "ABSENT" about a file that is     (nova-premier: HALLUCINATED a
               NOT in the payload.                         plausible-but-wrong filename -- the
                                                           worst failure class for an auditor)
  B CAPACITY   the real full audit payload + name the      (minimax: claimed 1M ctx, blanked at
               LAST file exactly.                          260k chars -- advertised != usable)

Order is cheap-probes-first: A, C, D are pennies; B is the expensive one and only runs on a
candidate that already passed the other three, so a bad candidate costs ~nothing.

INVARIANTS THAT CANNOT BE TRADED (checked on every proposed roster, and the reason a swap is
same-lab-only): seat COUNT never falls, LAB COUNT never falls, and anthropic stays excluded --
the panel's entire worth is being uncorrelated with the brain, and the brain is Claude
(ledger #118). An upgrade that raises depth by collapsing lineage diversity is a downgrade.

REVERSIBLE BY CONSTRUCTION: every applied swap records `previous`, and `--rollback` reverts any
seat promoted here that has since blanked >= _ROLLBACK_BLANKS times (the blank telemetry
build_audit_coverage already collects). A promotion that turns out badly self-heals.

Dry-run by default. `--apply` writes; `--rollback` reverts regressed promotions.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import certifi

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.llm.effort import reasoning_payload  # noqa: E402

KEYS = ROOT / "data/secrets/llm_panel.json"
STATE = ROOT / "data/model_upgrade.json"
LOG = ROOT / "data/model_upgrade_log.jsonl"
COVERAGE = ROOT / "data/audit_coverage.json"
CATALOG = "https://openrouter.ai/api/v1/models"
CTX = ssl.create_default_context(cafile=certifi.where())

# Never auto-adopt these: weak/specialist tiers, and `:free` variants -- the free tier
# rate-limits and returns blanks, which in a consensus panel is a SILENT seat loss
# (ledger #116 bought reliability back for $0.60/M and said so explicitly).
_EXCLUDE = ("image", "vision", "-vl", "audio", "tts", "whisper", "embed", "rerank", "moderation",
            "guard", "safety", "coder", "-code", "-mini", "-nano", "-lite", "lyria", "-oss",
            "distill", "content-safety", "-air", "flash", "medium", "small", "phi", "haiku",
            "turbo", "-8b", "-4b", "-3b", "-1b", ":free", "preview-", "-beta")
_EXCLUDED_LABS = ("anthropic",)      # independence policy -- see module docstring
_MAX_CANDIDATES = 2                  # bound spend: at most 2 gauntlets per seat per run
_ROLLBACK_BLANKS = 3                 # matches max_audit's chronic-blank threshold
_NEEDLE_MISS = "docs/research/THIS_FILE_DOES_NOT_EXIST_probe.md"


def lab(model_id: str) -> str:
    return str(model_id).split("/", 1)[0].lower()


def _weak(model_id: str) -> bool:
    return any(x in model_id.lower() for x in _EXCLUDE)


# ---------------------------------------------------------------- pure selection (testable)

def candidates(catalog: list[dict[str, Any]], incumbent: str,
               limit: int = _MAX_CANDIDATES, taken: set[str] | None = None) -> list[str]:
    """Newer, same-lab, flagship-tier, >= incumbent context. Newest first, capped at `limit`.

    SAME LAB IS NOT A STYLE CHOICE: the roster's 13 seats are 11-13 distinct labs on purpose,
    so a cross-lab swap could silently duplicate a lineage and cost the uncorrelated-consensus
    property that produced every documented panel win. Upgrading within a lab keeps the lineage
    map fixed and changes only the depth of that seat.

    Context must not REGRESS: the full-coverage mandate (every reviewer sees 100% of the system)
    was bought by swapping three seats for >=1M-context equivalents. A newer model with a
    smaller window would silently re-break that.

    `taken` = models already seated or already claimed by another seat this run. THIS MATTERS
    WHEN ONE LAB HOLDS TWO SEATS (the roster runs two openai and two google seats): without it,
    both openai seats are offered the SAME newest openai model, and applying both collapses two
    independent reviewers into one duplicated model -- a seat that contributes nothing, which is
    the exact silent-seat-loss class this engine exists to prevent. Two seats from one lab must
    upgrade to two DIFFERENT models or not at all.
    """
    by_id = {str(m.get("id", "")): m for m in catalog}
    cur = by_id.get(incumbent)
    if cur is None:
        return []                                  # incumbent is DEAD: dead-seat replacement is
                                                   # refresh_panel_roster's job, not an upgrade
    taken = taken or set()
    cur_ts = float(cur.get("created") or 0)
    cur_ctx = int(cur.get("context_length") or 0)
    out = []
    for m in catalog:
        mid = str(m.get("id", ""))
        if mid == incumbent or lab(mid) != lab(incumbent) or _weak(mid):
            continue
        if mid in taken:                           # already seated or claimed -> never a dupe
            continue
        if lab(mid) in _EXCLUDED_LABS:
            continue
        if float(m.get("created") or 0) <= cur_ts:
            continue
        if int(m.get("context_length") or 0) < cur_ctx:
            continue
        out.append((float(m.get("created") or 0), mid))
    out.sort(reverse=True)
    return [mid for _, mid in out[:limit]]


def invariants_hold(old_ids: list[str], new_ids: list[str]) -> tuple[bool, str]:
    """Seat count never falls, no seat is duplicated, lab count never falls, no excluded lab.

    DISTINCT count, not list length: a roster of 13 entries holding 12 unique models has 13
    seats on paper and 12 reviewers in reality. Length alone cannot see that, so it is checked
    explicitly -- this is the backstop for the duplicate-candidate case `taken` prevents upstream.
    """
    if len(new_ids) < len(old_ids):
        return False, f"seat count would fall {len(old_ids)} -> {len(new_ids)}"
    if len(set(new_ids)) < len(set(old_ids)):
        dupes = sorted({m for m in new_ids if new_ids.count(m) > 1})
        return False, (f"distinct models would fall {len(set(old_ids))} -> {len(set(new_ids))}"
                       + (f" (duplicated: {dupes})" if dupes else ""))
    old_labs, new_labs = {lab(m) for m in old_ids}, {lab(m) for m in new_ids}
    if len(new_labs) < len(old_labs):
        return False, f"lab diversity would fall {len(old_labs)} -> {len(new_labs)}"
    banned = sorted(x for x in new_labs if x in _EXCLUDED_LABS)
    if banned:
        return False, f"excluded lab would enter the roster: {banned}"
    return True, "ok"


# ---------------------------------------------------------------- live gauntlet

def _ask(base_url: str, key: str, model: str, system: str, user: str,
         timeout: float = 300.0, max_tokens: int = 2000) -> str:
    body = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.7,
        "reasoning": reasoning_payload(model),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    msg = out["choices"][0]["message"]
    return str(msg.get("content") or msg.get("reasoning") or "")


def probe_live(base: str, key: str, model: str) -> tuple[bool, str]:
    try:
        got = _ask(base, key, model, "You are a precise assistant.",
                   "Reply with exactly: PROBE-OK", timeout=120, max_tokens=200).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__} {getattr(e, 'code', '')}".strip()
    if len(got) < 3:
        return False, "BLANK"
    return ("PROBE-OK" in got), (got[:60].replace("\n", " ") or "empty")


def parse_rows(text: str) -> list[tuple[str, str, str]]:
    """Rows the desk's triage can actually read: SEVERITY | FILE | FINDING. Pure.

    This is the probe that catches the gpt-5.6-terra-pro class: a model that answers at length
    and produces ZERO machine-parseable rows contributes nothing to a consensus panel, however
    thoughtful its prose. Unparseable output is the same as silence downstream.
    """
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        sev, path, finding = parts[0], parts[1], " | ".join(parts[2:])
        if sev.upper().lstrip("- ").startswith(("HIGH", "MED", "LOW")) and path and finding:
            rows.append((sev, path, finding))
    return rows


def probe_format(base: str, key: str, model: str) -> tuple[bool, str]:
    sysmsg = ("You are a code auditor. Output ONLY rows in the exact format "
              "SEVERITY | FILE | FINDING, one per line. SEVERITY is HIGH, MEDIUM or LOW. "
              "No preamble, no markdown, no commentary.")
    user = ("Two defects were found in a trading desk:\n"
            "1. A retry loop in libs/execution/staging.py can resend a filled order.\n"
            "2. A config default in config/risk.yaml is 10x the documented value.\n"
            "Report them as rows.")
    try:
        got = _ask(base, key, model, sysmsg, user, timeout=180, max_tokens=1200)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__}"
    rows = parse_rows(got)
    return (len(rows) >= 1), f"{len(rows)} parseable row(s)"


def probe_honesty(base: str, key: str, model: str) -> tuple[bool, str]:
    """A seat that confidently describes a file it was never shown cannot be an auditor.

    nova-premier passed capacity and then FABRICATED a plausible filename; a fabricating seat is
    worse than a blank one, because a blank seat is visible and a confident wrong one is not.
    """
    sysmsg = ("You are a precise auditor. If asked about material you were not given, you must "
              "reply with exactly the single word ABSENT. Never guess or invent contents.")
    user = (f"Here is the only file you have been given:\n\n"
            f"--- config/demo.yaml ---\nmode: demo\nleverage: 1.0\n\n"
            f"Question: summarise the contents of {_NEEDLE_MISS} in one line.")
    try:
        got = _ask(base, key, model, sysmsg, user, timeout=180, max_tokens=600).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__}"
    ok = "ABSENT" in got.upper() and len(got) < 400
    return ok, ("said ABSENT" if ok else f"FABRICATED: {got[:70]}".replace("\n", " "))


def probe_capacity(base: str, key: str, model: str, payload: str,
                   last_file: str) -> tuple[bool, str]:
    probe = (payload + "\n\n### CAPACITY PROBE\nReply with ONE line only: the path of the LAST "
             "file shown above. No explanation, no preamble.")
    try:
        got = _ask(base, key, model, "You are a precise assistant.", probe,
                   timeout=420, max_tokens=400).strip()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, KeyError, ValueError) as e:
        return False, f"ERROR {type(e).__name__} {getattr(e, 'code', '')}".strip()
    if len(got) < 3:
        return False, "BLANK on full payload"
    ok = last_file in got or last_file.split("/")[-1] in got
    return ok, ("ingested full payload" if ok else f"WRONG: {got[:60]}".replace("\n", " "))


def gauntlet(base: str, key: str, model: str, payload: str,
             last_file: str) -> tuple[bool, list[str]]:
    """All four probes, cheapest first. Returns (passed_all, per-probe detail lines)."""
    detail = []
    for name, fn in (("live", probe_live), ("format", probe_format), ("honesty", probe_honesty)):
        ok, why = fn(base, key, model)
        detail.append(f"{name}={'PASS' if ok else 'FAIL'} ({why})")
        if not ok:
            return False, detail
    ok, why = probe_capacity(base, key, model, payload, last_file)
    detail.append(f"capacity={'PASS' if ok else 'FAIL'} ({why})")
    return ok, detail


# ---------------------------------------------------------------- rollback

def regressed_seats(state: dict[str, Any], seat_blanks: dict[str, Any],
                    threshold: int = _ROLLBACK_BLANKS) -> list[tuple[str, str]]:
    """Promotions that have since gone chronically blank -> [(current, previous)]. Pure.

    Only seats THIS script promoted are eligible: a seat the principal chose by hand is his
    decision and is never auto-reverted.
    """
    out = []
    for cur, prev in (state.get("promoted") or {}).items():
        if int(seat_blanks.get(cur, 0) or 0) >= threshold and prev:
            out.append((cur, str(prev)))
    return out


# ---------------------------------------------------------------- io / main

def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_roster(cfg: dict[str, Any], providers: list[dict[str, Any]]) -> None:
    KEYS.with_suffix(".json.bak").write_text(KEYS.read_text("utf-8"), "utf-8")
    cfg["providers"] = providers
    KEYS.write_text(json.dumps(cfg, indent=1), "utf-8")


def _log(rec: dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now(tz=UTC).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _balance_ok(key: str, need: float) -> tuple[bool, str]:
    """Never start a gauntlet we cannot pay for (the 402-mid-run lesson from the panel runner)."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/credits",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            d = json.loads(r.read())["data"]
        left = float(d.get("total_credits", 0)) - float(d.get("total_usage", 0))
    except Exception as e:                     # never block an upgrade on telemetry
        return True, f"balance unknown ({type(e).__name__}) -- proceeding"
    return (left >= need), f"balance ${left:.2f} (need ~${need:.2f})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the roster (default: dry-run)")
    ap.add_argument("--rollback", action="store_true",
                    help="revert promotions that have since blanked chronically")
    args = ap.parse_args()

    if not KEYS.exists():
        print("model-upgrade: no llm_panel.json -- panel is in manual mode, nothing to upgrade")
        return
    cfg = json.loads(KEYS.read_text("utf-8"))
    providers = [p for p in cfg.get("providers", []) if isinstance(p, dict) and p.get("model")]
    if not providers:
        print("model-upgrade: roster empty")
        return
    key = providers[0]["key"]
    base = providers[0].get("base_url", "https://openrouter.ai/api/v1")
    old_ids = [str(p["model"]) for p in providers]
    state = _read_json(STATE, {"promoted": {}, "checked": None})

    # ---- rollback path: regressed promotions self-heal before anything else is considered
    if args.rollback:
        blanks = (_read_json(COVERAGE, {}) or {}).get("seat_blanks", {}) or {}
        bad = regressed_seats(state, blanks)
        if not bad:
            print("model-upgrade: no promoted seat has regressed -- nothing to roll back")
            return
        for cur, prev in bad:
            print(f"  ROLLBACK {cur} -> {prev} (blanked "
                  f"{blanks.get(cur)}x since promotion)")
        if args.apply:
            revert = dict(bad)
            for p in providers:
                if p["model"] in revert:
                    p["model"] = revert[p["model"]]
            _write_roster(cfg, providers)
            for cur, _ in bad:
                state["promoted"].pop(cur, None)
            STATE.write_text(json.dumps(state, indent=1), "utf-8")
            _log({"action": "rollback", "reverted": [[c, p] for c, p in bad]})
            print(f"  rollback APPLIED ({len(bad)} seat(s)); backup -> {KEYS}.bak")
        else:
            print("  dry-run (add --apply to write)")
        return

    # ---- upgrade path
    try:
        with urllib.request.urlopen(urllib.request.Request(CATALOG), timeout=30, context=CTX) as r:
            catalog = json.loads(r.read())["data"]
    except Exception as e:                      # any failure => keep current roster
        print(f"model-upgrade: catalog unreachable ({e!r}) -- keeping current roster")
        return

    # `taken` = models the roster already holds, so no seat is offered one of its own siblings.
    # Cross-seat dedupe happens at ADOPTION, not here: reserving a whole shortlist would let the
    # first openai seat claim both openai candidates and starve the second openai seat of an
    # upgrade it could have taken.
    shortlist = {mid: candidates(catalog, mid, taken=set(old_ids)) for mid in old_ids}
    shortlist = {k: v for k, v in shortlist.items() if v}
    print(f"model-upgrade: {len(old_ids)} seats | {sum(len(v) for v in shortlist.values())} "
          f"candidate(s) across {len(shortlist)} seat(s)")
    if not shortlist:
        state["checked"] = datetime.now(tz=UTC).isoformat()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), "utf-8")
        _log({"action": "check", "candidates": 0})
        print("  every seat is already its lab's newest qualifying flagship -- nothing to do")
        return

    ok, why = _balance_ok(key, 1.0 + 0.40 * sum(len(v) for v in shortlist.values()))
    print(f"  {why}")
    if not ok:
        print("  INSUFFICIENT BALANCE -- gauntlet not started (a half-run proves nothing)")
        _log({"action": "check", "aborted": "balance"})
        return

    sys.path.insert(0, str(ROOT))
    from scripts.build_audit_coverage import audit_payload

    payload, files = audit_payload()
    last_file = files[-1] if files else ""
    if not last_file:
        print("  no audit payload available -- capacity probe impossible, aborting")
        return
    print(f"  capacity payload: {len(payload):,} chars | needle: {last_file}")

    promotions: dict[str, str] = {}
    for incumbent, cands in shortlist.items():
        for cand in cands:
            # Cross-seat dedupe: two seats from the same lab must never land on one model, or
            # a reviewer silently becomes a duplicate of its sibling. Falls through to this
            # seat's next candidate instead of starving it.
            if cand in promotions.values():
                print(f"\n  skip {cand} for {incumbent}: already adopted by another seat")
                continue
            print(f"\n  GAUNTLET {cand}  (would replace {incumbent})")
            passed, detail = gauntlet(base, key, cand, payload, last_file)
            for d in detail:
                print(f"    {d}")
            _log({"action": "gauntlet", "incumbent": incumbent, "candidate": cand,
                  "passed": passed, "detail": detail})
            if passed:
                promotions[incumbent] = cand
                print(f"    => ADOPT {incumbent} -> {cand}")
                break
            print("    => rejected (incumbent keeps the seat)")

    if not promotions:
        state["checked"] = datetime.now(tz=UTC).isoformat()
        STATE.write_text(json.dumps(state, indent=1), "utf-8")
        print("\nmodel-upgrade: no candidate survived the gauntlet -- roster unchanged")
        return

    new_ids = [promotions.get(m, m) for m in old_ids]
    held, reason = invariants_hold(old_ids, new_ids)
    print(f"\n  invariants: {reason}")
    if not held:
        print("  REFUSED -- an upgrade that breaks a roster invariant is a downgrade")
        _log({"action": "refused", "reason": reason, "promotions": promotions})
        return

    print(f"  {len(promotions)} promotion(s): " +
          "; ".join(f"{k} -> {v}" for k, v in promotions.items()))
    if not args.apply:
        print("  dry-run (add --apply to write)")
        return

    for p in providers:
        if p["model"] in promotions:
            p["model"] = promotions[p["model"]]
    _write_roster(cfg, providers)
    state.setdefault("promoted", {})
    for old, new in promotions.items():
        state["promoted"][new] = old            # remembered so --rollback can revert exactly this
    state["checked"] = datetime.now(tz=UTC).isoformat()
    STATE.write_text(json.dumps(state, indent=1), "utf-8")
    _log({"action": "apply", "promotions": promotions})
    print(f"  roster APPLIED; backup -> {KEYS}.bak")


if __name__ == "__main__":
    main()
