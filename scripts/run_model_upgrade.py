"""MODEL AUTO-UPGRADE -- the desk adopts a newer flagship with NO HUMAN IN THE LOOP.

PRINCIPAL ORDER (2026-07-30): *"auto-upgrade to newer flagship models, no human needed."*

WHY THIS IS WORTH A SCRIPT. The brain, every miner, every audit and every dig runs a Claude model.
Model capability is the single input the desk cannot improve by its own work -- it improves when
the vendor ships. Historically that improvement reached this desk only when a human noticed and
hand-edited three files. Between ship date and notice date, every cycle ran on strictly worse
reasoning than was available: not a crash, just a quiet tax on every hypothesis screened, every
audit run, every mechanism proposed. Compounded over a research programme, that is the most
expensive kind of gap -- one with no error message.

WHAT IT DOES, in order:
  1. DISCOVER  candidate model ids: the Anthropic /v1/models listing when a key is present, plus
     a probe list synthesised by walking the version of the current head forward.
  2. RANK      via libs/ops/model_chain -- flagship tier only, strictly greater version.
  3. VERIFY    the candidate actually answers, through the same PING the organs use. An id that
     lists but does not answer (unreleased, entitlement-gated, wrong plan) is NOT an upgrade.
  4. PROMOTE   by PREPEND, keeping yesterday's head directly beneath it, and write the single
     source ops/model_chain.env.
  5. RECORD    every decision -- adopted, rejected, unverified -- to data/model_upgrade_log.jsonl,
     and page the principal on any change to the head.

THE SAFETY LINE. Auto-adoption is bounded to models whose FAMILY the desk already declares
(libs/ops/model_chain.FAMILY_TIER). A genuinely new family -- a name this code has never seen --
is PROPOSED and paged, never adopted, because promoting an unrecognised model into the path that
sizes real positions is precisely the convenience that ends compounding. Adding one line to
FAMILY_TIER is the human's entire job, and it is the only part that needs a human.

THE UPGRADE IS ALWAYS REVERSIBLE without anyone awake: the outgoing head stays in the chain, so a
promoted model that throttles or errors degrades to exactly what ran yesterday.

    python scripts/run_model_upgrade.py              # discover + report (default: SAFE)
    python scripts/run_model_upgrade.py --apply      # verify + promote + write the chain
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.model_chain import (  # noqa: E402
    CHAIN_FILE,
    FAMILY_TIER,
    is_upgrade,
    parse_model,
    promote,
    promote_into,
    read_chain,
    render_chain,
)

_LOG = _ROOT / "data/model_upgrade_log.jsonl"
_API = "https://api.anthropic.com/v1/models?limit=100"
_PING = "Reply with exactly: PING-OK"


def _list_models_api() -> list[str]:
    """Vendor listing. Returns [] on any failure -- discovery is best-effort by design; the probe
    path below is what makes the upgrader work on a box with only an OAuth token."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return []
    req = urllib.request.Request(_API, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []
    return [str(m.get("id", "")) for m in body.get("data", []) if m.get("id")]


def _probe_candidates(head: str) -> list[str]:
    """Synthesise plausible next ids from the current head.

    This exists because the box normally authenticates with an OAuth token, not an API key, so the
    /v1/models listing is unavailable exactly where the upgrader has to run. Walking the version
    forward and PINGing is crude, costs one cheap call per candidate, and is the difference
    between an upgrader that works on the VPS and one that only works in a demo.
    """
    out: list[str] = []
    for family in sorted(f for f, t in FAMILY_TIER.items() if t >= 3):
        _, ver = parse_model(head)
        base = int(ver) if ver > 0 else 5
        for nxt in (base + 1, base + 2):
            out.append(f"claude-{family}-{nxt}")
    return out


def _ping(model: str, timeout: int = 120) -> tuple[bool, str]:
    """Does this model actually ANSWER for this account? Listing is not entitlement."""
    env = dict(os.environ, ANTHROPIC_MODEL=model)
    try:
        p = subprocess.run(["claude", "-p", _PING, "--model", model,
                            "--dangerously-skip-permissions"],
                           check=False, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"[:200]
    out = (p.stdout or "") + (p.stderr or "")
    return ("PING-OK" in out), out.strip().splitlines()[-1][:200] if out.strip() else "no output"


def _page(msg: str) -> None:
    """Best-effort principal page; never fails the caller (same contract as brain_env.sh)."""
    try:
        cfg = json.loads((_ROOT / "data/secrets/ntfy.json").read_text("utf-8"))
        topic = cfg.get("topic") or cfg.get("ntfy_topic")
        if not topic:
            return
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"),
                                     headers={"Title": "MODEL UPGRADE", "Priority": "high"})
        urllib.request.urlopen(req, timeout=10).close()
    except (OSError, ValueError, KeyError):
        return


def discover(chain: list[str]) -> dict[str, Any]:
    """Everything decidable WITHOUT spending a call: what is new, what is unknown, what is old."""
    head = chain[0]
    listed = _list_models_api()
    candidates = sorted(set(listed) | set(_probe_candidates(head)))
    upgrades = [c for c in candidates if is_upgrade(c, head)]
    # A family this code has never declared: reported and paged, never adopted.
    unknown = sorted({c for c in listed if parse_model(c)[0] == -1})
    return {"head": head, "chain": chain, "n_listed": len(listed),
            "listing_available": bool(listed),
            "candidates": candidates, "upgrades": upgrades, "unknown_families": unknown}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="verify + promote (default: report only)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    chain = read_chain()
    rep = discover(chain)
    rep["generated"] = datetime.now(tz=UTC).isoformat()
    rep["verified"] = []
    rep["rejected"] = []
    rep["adopted"] = None

    if args.apply and rep["upgrades"]:
        # Newest first, so the desk adopts the best answering model and stops -- not the first one
        # it happens to enumerate.
        for cand in sorted(rep["upgrades"], key=lambda m: parse_model(m), reverse=True):
            ok, detail = _ping(cand)
            (rep["verified"] if ok else rep["rejected"]).append({"model": cand, "detail": detail})
            if ok:
                new_chain = promote(cand, chain)
                # BOTH SEATS GAIN THE MODEL, BUT ONLY ONE CHANGES ITS HEAD. The miner chain's
                # head is fable by PRINCIPAL POLICY (2026-08-12), not by capability ranking, so
                # prepending here would silently move every miner onto the Max seat at 03:00 with
                # nobody awake to review it -- an unattended reversal of a routing decision.
                # pin_head inserts the new flagship directly beneath fable instead: the miners
                # still get it on walk-down, and the pool split survives the upgrade.
                new_miner = promote_into(read_chain("_MINER_MODEL_CHAIN"), cand, pin_head=True)
                CHAIN_FILE.write_text(render_chain(
                    new_chain, reason=f"auto-upgrade: {cand} verified answering, prepended above "
                                      f"{chain[0]} (which is retained as the fallback); miner "
                                      "seat keeps its pinned fable head and takes it on walk-down",
                    sealed=rep["generated"], miner_chain=new_miner), "utf-8")
                rep["adopted"] = cand
                rep["chain"] = new_chain
                rep["miner_chain"] = new_miner
                _page(f"MODEL AUTO-UPGRADE: adopted {cand} (was {chain[0]}). "
                      f"Chain now: {' '.join(new_chain)}. Old head retained as fallback.")
                break

    if rep["unknown_families"]:
        _page("MODEL UPGRADE: unrecognised model family listed "
              f"({', '.join(rep['unknown_families'][:4])}) -- NOT adopted. Declare it in "
              "libs/ops/model_chain.FAMILY_TIER to make it eligible.")

    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rep) + "\n")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        mode = "APPLY" if args.apply else "report-only"
        print(f"model upgrade [{mode}] | head={rep['head']} | listing="
              f"{'api' if rep['listing_available'] else 'probe-only'} | "
              f"candidates={len(rep['candidates'])} upgrades={len(rep['upgrades'])}")
        for u in rep["upgrades"]:
            print(f"  UPGRADE-CANDIDATE {u}")
        for r in rep["rejected"]:
            print(f"  REJECTED          {r['model']}: {r['detail'][:90]}")
        for u in rep["unknown_families"]:
            print(f"  UNKNOWN-FAMILY    {u} (declare in FAMILY_TIER to make eligible)")
        print(f"  chain: {' '.join(rep['chain'])}"
              + (f"  <- ADOPTED {rep['adopted']}" if rep["adopted"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
