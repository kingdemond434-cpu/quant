#!/usr/bin/env python3
"""STRATEGIC DIRECTOR runner -- writes data/strategic_director.json (EXECUTION_QUEUE.md RANK 3).

A runtime ROLE, not a doctrine document: dossier assembled from artifacts that already exist ->
prompt -> ENFORCED output contract -> accepted recommendations written to the recommendation ledger,
where §41 forces every row to reach implemented / rejected / scheduled.

ACTIVATION-READY. Execution needs OpenRouter credit (the same 402 that blocks the panel and
llm_code_auditor.py). Everything except the network call is pure and tested, so --dry-run proves the
entire path today for free, and no redesign is needed when credit lands. --dry-run is the automatic
default when no key file exists.

    python scripts/run_strategic_director.py --dry-run     # dossier + prompt + contract, no spend
    python scripts/run_strategic_director.py               # live (needs data/secrets/llm_panel.json)
    python scripts/run_strategic_director.py --from-file r.json --ledger   # parse + ledger a response
"""
from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.strategic_director import (  # noqa: E402
    assemble_dossier,
    build_prompt,
    director_report,
    parse_recommendations,
    to_ledger_commands,
)

OUT = ROOT / "data/strategic_director.json"
KEYS = ROOT / "data/secrets/llm_panel.json"

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402
from libs.llm.effort import reasoning_payload  # noqa: E402

# overridable; any reasoning model satisfies the contract -- but the DEFAULT is deliberately a
# GPT model, not a Claude one (principal order 2026-07-31, and it was the design intent from the
# start: "GPT Strategic Director"). Every other reasoning organ on this desk is Claude, so a
# Claude strategist re-reads the desk with the same eyes that built it -- same priors, same blind
# spots, zero independence. The strategist exists precisely to be the OTHER model family: the
# same reason the v8 8.2 bar demands a second-model-family fuzz report rather than more of the
# first family's opinion. gpt-9 is the flagship seat the panel roster already vets.
MODEL = "openai/gpt-9"
_CTX = ssl.create_default_context()


def _ask(prompt: str, model: str, timeout: float = 360.0) -> tuple[str, str]:
    """(response, error). Never raises -- a dead provider must not crash the cycle.

    DOCTRINE INJECTED AS A SYSTEM MESSAGE (2026-08-01). scripts/doctrine.py's own three-surface
    audit reported this caller at 9/10: it posted a bare user message to chat/completions with no
    preamble, so the strategic director -- the organ that proposes what the desk should DO -- was
    the one intelligence here running unconstrained. It therefore also missed the adversarial
    review rubric that now rides along with the preamble, which is the specific reason this was
    worth fixing today rather than logging.

    Wrapped defensively because doctrine is an improvement to a working caller, never a
    precondition for one: an import failure degrades to the previous behaviour rather than taking
    down the cycle.
    """
    try:
        providers = json.loads(KEYS.read_text("utf-8"))["providers"]
    except (OSError, ValueError, KeyError) as e:
        return "", f"key file unreadable: {e}"
    for prov in providers:
        base, key = prov.get("base_url", ""), prov.get("key", "")
        if not base or not key:
            continue
        try:
            from scripts.doctrine import preamble as _doctrine
            system = _doctrine("strategic director")
        except Exception:
            system = ""
        system = OBJECTIVE_PREAMBLE + ("\n" + system if system else "")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": prompt}]
        body = json.dumps({
            "model": model, "max_tokens": 8000, "temperature": 0.4,
            # depth follows the roster's per-model caps, never a hardcoded literal -- the
            # effort ladder lives in ONE place (libs/llm/effort) for every organ.
            "reasoning": reasoning_payload(model),
            "messages": messages,
        }).encode()
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                doc = json.loads(r.read())
            msg = doc["choices"][0]["message"]
            return str(msg.get("content") or msg.get("reasoning") or ""), ""
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
            continue
    return "", last if providers else "no providers configured"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="assemble + build the prompt, spend nothing (default without a key)")
    ap.add_argument("--from-file", type=Path, default=None,
                    help="parse a response already captured (manual mode / replay)")
    ap.add_argument("--ledger", action="store_true",
                    help="write accepted recommendations to the recommendation ledger")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    dossier = assemble_dossier(ROOT)
    prompt = build_prompt(dossier)

    raw, err, mode = "", "", "dry-run"
    if a.from_file is not None:
        try:
            raw, mode = a.from_file.read_text("utf-8"), "replay"
        except OSError as e:
            print(f"strategic-director: cannot read {a.from_file}: {e}", file=sys.stderr)
            return 2
    elif not a.dry_run:
        if not KEYS.exists():
            # NOT an error: the designed state until credit lands. Prove the path, spend nothing.
            err, mode = "no data/secrets/llm_panel.json -- dry-run (activation-ready)", "dry-run"
        else:
            raw, err = _ask(prompt, a.model)
            mode = "live" if raw else "blocked"

    payload: dict[str, object] = {
        "generated": datetime.now(tz=UTC).isoformat(), "mode": mode, "model": a.model,
        "dossier_summary": dossier.summary(),
        "dossier_missing": dossier.missing,
        "dormant_count": dossier.dormant_count,
        "prompt_chars": len(prompt),
        "error": err,
    }

    if raw:
        res = parse_recommendations(raw, dossier)
        payload["report"] = director_report(res, dossier)
        payload["status"] = "ACTIVE"
        ledgered = 0
        if a.ledger:
            for argv_add in to_ledger_commands(res):
                r = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/recommendations.py"), *argv_add],
                    capture_output=True, text=True, check=False, cwd=str(ROOT))
                ledgered += int(r.returncode == 0)
        payload["ledgered"] = ledgered
    else:
        payload["status"] = "BLOCKED" if mode == "blocked" else "READY"
        # The contract and dossier are still emitted, so the artifact PROVES activation-readiness
        # rather than asserting it -- and a reviewer can check the prompt without paying for a run.
        payload["report"] = director_report(parse_recommendations("[]", dossier), dossier)
        payload["prompt"] = prompt

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
        return 0
    print(f"strategic-director | {payload['status']} ({mode})")
    print(f"  dossier: {dossier.summary()}")
    if dossier.missing:
        print(f"  MISSING: {', '.join(dossier.missing)}")
    if err:
        print(f"  {err}")
    rep = payload.get("report")
    if isinstance(rep, dict):
        acc, rej = rep.get("accepted", []), rep.get("rejected", [])
        if acc or rej:
            print(f"  {len(acc)} accepted, {len(rej)} rejected by the output contract")
            for r in acc:
                print(f"    [{r['kind']}] {r['title']}")
            for r in rej:
                print(f"    REJECTED {r['title']}: {r['reason'][:100]}")
    if payload.get("ledgered"):
        print(f"  {payload['ledgered']} recommendation(s) ledgered -- §41 now owes a disposition")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
