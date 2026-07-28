"""AUTO-UPGRADE the Claude organ models (the brain chain) when a newer flagship ships.

WHAT WAS BROKEN: every organ's model was a hand-pinned literal. ops/brain_env.sh pins
ANTHROPIC_MODEL and _BRAIN_MODEL_CHAIN; ops/run_frontier_miner.sh and scripts/run_deep_sweep.py
each carry their OWN chain. The chain walks DOWN on starvation (that is what brain_auth_check
does) but nothing ever walked UP: when Anthropic shipped a newer flagship, the desk kept running
the old one forever, silently, until a human hand-edited three files. Three copies also meant
three chances to drift.

THE CHAIN ORDER IS LOAD-BEARING AND IS NOT RE-RANKED HERE. brain_env leads with opus-5 and puts
fable LAST on purpose: fable draws a METERED credit pool that one max-effort dig drained
(evidence 2026-07-24), while opus sits on the Max subscription seat. run_frontier_miner
deliberately INVERTS that -- fable first -- because the region rotation is resumable, so a
mid-dig credit death costs nothing and each miner run on fable preserves Max headroom for the
brain. Those orderings encode BILLING and RESUMABILITY constraints, not a capability ranking, so
this script must never reorder a chain. It upgrades each slot IN PLACE, within its own model
family, and leaves every file's own ordering exactly as its author intended.

THE UPGRADE RULE, per chain slot:
  1. Candidate must be the SAME FAMILY (opus -> opus, fable -> fable). A cross-family "upgrade"
     would silently move a slot onto a different billing pool and break the reason the slot
     was ordered where it is.
  2. Candidate version must be strictly NEWER (4.8 < 5 < 5.1).
  3. Candidate must appear in the live Models API listing -- i.e. it exists AND this account can
     actually reach it. A model we cannot call is not an upgrade.
  4. Candidate must PASS A LIVE PROBE through the real brain env (`claude -p` with
     ANTHROPIC_MODEL set). Same verify-then-flip discipline the principal used by hand on
     2026-07-25: FABLE-OK before any config change.

ROLLBACK IS FREE AND AUTOMATIC. The displaced incumbent is not deleted -- it is demoted to the
next position in the chain. So if a promoted model later starves, 429s, or is withdrawn,
brain_auth_check walks past it to the known-good incumbent on the very next cycle, with a page.
The worst case of a bad promotion is one fallback hop, never a dead organ.

Dry-run by default; `--apply` writes (each file backed up, and `bash -n` must pass before any
shell file is committed to disk).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/brain_model_upgrade.json"
LOG = ROOT / "data/model_upgrade_log.jsonl"
MODELS_URL = "https://api.anthropic.com/v1/models?limit=100"
CTX = ssl.create_default_context()

# Files that pin a brain model. Each keeps its OWN chain order (see module docstring).
_CHAIN_RE = re.compile(r'(_BRAIN_MODEL_CHAIN=)(["\'])(.*?)\2')
_DEFAULT_RE = re.compile(r'(export ANTHROPIC_MODEL="\$\{ANTHROPIC_MODEL:-)([a-z0-9.\-]+)(\}")')
_PROBE = "Reply with exactly: UPGRADE-OK"


# ---------------------------------------------------------------- pure id parsing (testable)

def parse_model(model_id: str) -> tuple[str, tuple[int, ...]] | None:
    """'claude-opus-4-8' -> ('opus', (4, 8)); 'claude-haiku-4-5-20251001' -> ('haiku', (4, 5)).

    Returns None for anything that is not a recognisable `claude-<family>-<version>` id, so an
    unparseable or oddly-named model can never be mistaken for an upgrade candidate.
    """
    if not model_id.startswith("claude-"):
        return None
    parts = model_id[len("claude-"):].split("-")
    if not parts or not parts[0] or parts[0].isdigit():
        return None
    family = parts[0]
    version: list[int] = []
    for tok in parts[1:]:
        if not tok.isdigit():
            return None if not version else (family, tuple(version))
        if len(tok) == 8:            # YYYYMMDD snapshot suffix -- not a version component
            break
        version.append(int(tok))
    if not version:
        return None
    return family, tuple(version)


def newer(candidate: str, incumbent: str) -> bool:
    """True iff candidate is the same family and a strictly higher version. Pure.

    Version tuples compare left-to-right, so (5,) > (4, 8) -- opus-5 beats opus-4-8, which is
    exactly the comparison a naive string sort gets wrong.
    """
    c, i = parse_model(candidate), parse_model(incumbent)
    if c is None or i is None or c[0] != i[0]:
        return False
    return c[1] > i[1]


def best_candidate(available: list[str], incumbent: str) -> str | None:
    """Highest-version same-family model strictly newer than the incumbent. Pure."""
    ups = [m for m in available if newer(m, incumbent)]
    if not ups:
        return None
    return max(ups, key=lambda m: (parse_model(m) or ("", ()))[1])


def upgrade_chain(chain: list[str], available: list[str],
                  approved: dict[str, str]) -> list[str]:
    """Apply approved per-slot promotions, DEMOTING each incumbent to the next slot. Pure.

    Order is preserved and the incumbent is retained -- that retention IS the rollback path:
    a promoted model that later starves falls through to the model it replaced.
    """
    out: list[str] = []
    for slot in chain:
        new = approved.get(slot)
        if new and new not in out:
            out.append(new)
        if slot not in out:
            out.append(slot)
    seen, dedup = set(), []
    for m in out:
        if m not in seen:
            seen.add(m)
            dedup.append(m)
    return dedup


def rewrite_text(text: str, approved: dict[str, str]) -> tuple[str, list[str]]:
    """Rewrite every _BRAIN_MODEL_CHAIN / ANTHROPIC_MODEL default in a file body. Pure.

    Returns (new_text, human-readable change lines). Regex-scoped to the exact assignment forms
    so prose and comments mentioning a model id are never touched.
    """
    changes: list[str] = []

    def _chain_sub(m: re.Match[str]) -> str:
        chain = m.group(3).split()
        new = upgrade_chain(chain, [], approved)
        if new != chain:
            changes.append(f"chain: {' '.join(chain)}  ->  {' '.join(new)}")
        return f"{m.group(1)}{m.group(2)}{' '.join(new)}{m.group(2)}"

    def _default_sub(m: re.Match[str]) -> str:
        cur = m.group(2)
        new = approved.get(cur, cur)
        if new != cur:
            changes.append(f"default ANTHROPIC_MODEL: {cur} -> {new}")
        return f"{m.group(1)}{new}{m.group(3)}"

    out = _CHAIN_RE.sub(_chain_sub, text)
    out = _DEFAULT_RE.sub(_default_sub, out)
    return out, changes


def chain_files() -> list[Path]:
    """Every tracked file that pins a brain model -- found, not hardcoded, so a NEW organ
    script that copies the chain idiom is upgraded too instead of silently aging."""
    out = []
    for d in ("ops", "scripts"):
        for p in sorted((ROOT / d).glob("*")):
            if p.suffix not in (".sh", ".py") or p.name == Path(__file__).name:
                continue
            try:
                body = p.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "_BRAIN_MODEL_CHAIN" in body or _DEFAULT_RE.search(body):
                out.append(p)
    return out


def pinned_models(paths: list[Path]) -> list[str]:
    """Distinct model ids pinned across all chain files, in first-seen order."""
    seen: list[str] = []
    for p in paths:
        body = p.read_text("utf-8")
        for m in _CHAIN_RE.finditer(body):
            for mid in m.group(3).split():
                if mid not in seen:
                    seen.append(mid)
        for m in _DEFAULT_RE.finditer(body):
            if m.group(2) not in seen:
                seen.append(m.group(2))
    return seen


# ---------------------------------------------------------------- live discovery + probe

def _auth_headers() -> dict[str, str] | None:
    """Match ops/brain_env.sh's own auth precedence: API key first, then the OAuth token.

    An API key authenticates with `x-api-key`; a `claude setup-token` OAuth token must go on
    `Authorization: Bearer` AND carry the oauth beta header -- sending an OAuth token as
    `x-api-key` is a 401, which would look like "no newer models" if we swallowed it.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}", "anthropic-version": "2023-06-01",
                "anthropic-beta": "oauth-2025-04-20"}
    return None


def available_models() -> tuple[list[str], str]:
    """Model ids this account can actually reach, via GET /v1/models. ([], reason) on failure."""
    headers = _auth_headers()
    if headers is None:
        return [], ("no ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in env -- "
                    "source ops/brain_env.sh first")
    try:
        req = urllib.request.Request(MODELS_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            data = json.loads(r.read()).get("data", [])
    except urllib.error.HTTPError as e:
        return [], f"models API HTTP {e.code}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return [], f"models API {type(e).__name__}"
    return [str(m.get("id", "")) for m in data if m.get("id")], "ok"


def probe(model: str, timeout: int = 180) -> tuple[bool, str]:
    """Live-call the candidate through the real CLI the organs use. Verify, then flip."""
    env = {**os.environ, "ANTHROPIC_MODEL": model}
    try:
        r = subprocess.run(["claude", "-p", _PROBE, "--dangerously-skip-permissions"],
                           capture_output=True, text=True, timeout=timeout, env=env, check=False)
    except FileNotFoundError:
        return False, "claude CLI not on PATH"
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"
    out = (r.stdout or "") + (r.stderr or "")
    if "UPGRADE-OK" in out:
        return True, "UPGRADE-OK"
    return False, (out.strip().splitlines() or ["no output"])[-1][:110]


def _log(rec: dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now(tz=UTC).isoformat()
    rec["surface"] = "brain"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the files (default: dry-run)")
    args = ap.parse_args()

    paths = chain_files()
    if not paths:
        print("brain-upgrade: no file pins a brain model -- nothing to do")
        return
    incumbents = pinned_models(paths)
    print(f"brain-upgrade: {len(paths)} file(s) pin {len(incumbents)} model(s): "
          f"{', '.join(incumbents)}")

    avail, why = available_models()
    if not avail:
        print(f"  models API unavailable ({why}) -- keeping current pins")
        _log({"action": "check", "aborted": why})
        return
    print(f"  catalog: {len(avail)} model(s) reachable by this account")

    approved: dict[str, str] = {}
    for inc in incumbents:
        cand = best_candidate(avail, inc)
        if not cand:
            print(f"  {inc:<22} already newest in its family")
            continue
        ok, detail = probe(cand)
        print(f"  {inc:<22} -> {cand:<22} probe={'PASS' if ok else 'FAIL'} ({detail})")
        _log({"action": "probe", "incumbent": inc, "candidate": cand,
              "passed": ok, "detail": detail})
        if ok:
            approved[inc] = cand

    STATE.parent.mkdir(parents=True, exist_ok=True)
    if not approved:
        STATE.write_text(json.dumps({"checked": datetime.now(tz=UTC).isoformat(),
                                     "pinned": incumbents}, indent=1), "utf-8")
        print("  no verified upgrade available -- pins unchanged")
        return

    planned: list[tuple[Path, str, list[str]]] = []
    for p in paths:
        body = p.read_text("utf-8")
        new_body, changes = rewrite_text(body, approved)
        if changes:
            planned.append((p, new_body, changes))
    for p, _, changes in planned:
        print(f"\n  {p.relative_to(ROOT)}")
        for c in changes:
            print(f"    {c}")

    if not args.apply:
        print("\n  dry-run (add --apply to write)")
        return

    for p, new_body, _changes in planned:
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
        p.write_text(new_body, "utf-8")
        if p.suffix == ".sh":
            # NEVER ship a shell file this script broke: the organs source brain_env at spawn,
            # so a syntax error there kills every organ at once. Validate, revert on failure.
            r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True, check=False)
            if r.returncode != 0:
                shutil.copy2(p.with_suffix(p.suffix + ".bak"), p)
                print(f"  REVERTED {p.name}: bash -n failed ({r.stderr.strip()[:90]})")
                _log({"action": "revert", "file": p.name, "reason": "bash -n"})
                continue
        print(f"  wrote {p.relative_to(ROOT)} (backup -> {p.name}{p.suffix}.bak)")

    STATE.write_text(json.dumps({"checked": datetime.now(tz=UTC).isoformat(),
                                 "promoted": approved, "pinned": incumbents}, indent=1), "utf-8")
    _log({"action": "apply", "promotions": approved,
          "files": [p.name for p, _, _ in planned]})
    print(f"\n  APPLIED {len(approved)} promotion(s) across {len(planned)} file(s). "
          "Each displaced model stays in-chain as the fallback.")


if __name__ == "__main__":
    main()
