"""CLAUDE'S FINANCE AND TRADING SKILLS AS A PROPOSER SEAT: institutional methods in, leads out.

WHAT THIS IS (principal 2026-10-29, wave 3: "plug in Claude's finance and trading skills as one
more proposer source"). Anthropic publishes the methods its financial-services skills follow --
the FX carry desk's carry-to-vol workflow, the rates monitor, the curve and relative-value
playbooks, the equity analyst's screens, catalyst calendar and thesis tracker -- as plain
`SKILL.md` text under Apache-2.0 (github.com/anthropics/financial-services). Twelve of them that
speak to the MT5 universe are vendored, unmodified, in `libs/research/fsi_skills/` with the
upstream commit and every file's sha256 in `MANIFEST.json`. Each pass hands a free model one
method at a time and asks it to apply that method to this desk's instruments as falsifiable price
rules in the desk's own registered families.

A PROPOSER AND NOTHING ELSE. The model's reply goes through `proposer_seat.propose` -- the one
composer, the hygiene scan, the verdict stripper, the free panel then the seat -- and each
accepted row is written as an ordinary LEAD under `data/intelligence/fsi_skills/`. From there the
analyst pipeline triages it, structures it, pre-screens it on the desk's own bars and donates
survivors through the one PIT door, and the sealed gauntlet judges what reaches it. Nothing here
scores, ranks, promotes or sizes; a conviction, a score or a target in a reply is stripped.

WHAT THE METHODS CANNOT HAVE HERE, SAID OUT LOUD. The partner skills assume a vendor's terminal
(forward curves, option surfaces, swap curves). This desk has none of those feeds, so the prompt
says so and asks for the price-path expression of the method only; a family that needs a feed the
desk lacks is refused downstream as `family_not_price_only`, on the record. Single-name equities
stay in the event lane: the equity-research methods are pointed at indices and the non-equity
universe, never at share CFDs (the two-lane order, CLAUDE.md).

TRIALS ARE NOT CHARGED HERE. A lead is not a test; the pipeline and the gauntlet charge the
cells they actually evaluate, so charging the proposal as well would count one trial twice.

    python fsi_skill_proposer.py [--skills 2] [--per-skill 6] [--dry-run] [--json]

Exit 0 when the seat is dark (UNMEASURED, a state) or at least one lead was written; exit 1 when
the seat answered and not one lead survived -- zero proposals from a lit seat is a failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SKILLS_DIR = REPO / "libs" / "research" / "fsi_skills"
MANIFEST = SKILLS_DIR / "MANIFEST.json"
INTEL = BASE / "data" / "intelligence" / "fsi_skills"
CURSOR = BASE / "data" / "fsi_skill_cursor.json"
REPORT = BASE / "reports" / "FSI_SKILL_PROPOSER.json"
ORGAN = "fsi_skills"
SOURCE = "fsi_skills"
UNMEASURED = "UNMEASURED"

#: Method text handed to the model, per skill. The longest vendored method is ~8.7k characters,
#: most of it report formatting; the workflow and principles sit in the first part of every file.
METHOD_CHARS = 4000
#: Symbols listed per prompt -- enough to span a class, few enough to keep the prompt short.
MAX_SYMBOLS = 40
MAX_SYMBOLS_PER_ROW = 4
SKILLS_PER_PASS = 2
PER_SKILL = 6

#: The manifest's class names -> the words the asset-class registry uses for them.
CLASS_WORDS: dict[str, tuple[str, ...]] = {
    "forex": ("forex", "fx"),
    "indices": ("indices", "index"),
    "bonds": ("bond",),
    "metals": ("metal",),
    "energy": ("energy",),
    "commodities": ("commodit", "soft"),
}

_URL = re.compile(r"https?://|www\.", re.I)


# ============================================================================== the methods
def manifest() -> list[dict[str, Any]]:
    """Every vendored skill whose file is present AND matches its recorded sha256."""
    try:
        doc = json.loads(MANIFEST.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    out: list[dict[str, Any]] = []
    for row in doc.get("skills") or []:
        if not isinstance(row, dict):
            continue
        try:
            body = (SKILLS_DIR / str(row.get("file") or "")).read_bytes()
        except OSError:
            continue
        if hashlib.sha256(body).hexdigest() != row.get("sha256"):
            continue                    # an edited method is not the method the manifest names
        out.append({**row, "commit": doc.get("commit", "")})
    return out


def method_text(entry: dict[str, Any]) -> str:
    """The skill's body without its frontmatter, capped at METHOD_CHARS."""
    text = (SKILLS_DIR / str(entry["file"])).read_text("utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    return text.strip()[:METHOD_CHARS]


# ============================================================================= the desk side
def _pipeline() -> Any:
    try:
        from research import analyst_pipeline
        return analyst_pipeline
    except Exception:
        return None


def families_menu() -> list[tuple[str, str]]:
    """(family, mechanism) for every registered, constructible, PRICE-ONLY family."""
    ap = _pipeline()
    if ap is None:
        return []
    table = ap._family_table()
    return sorted((fam, str(row[0])) for fam, row in table.items()
                  if ap.admissible_family(fam) is not None)


def symbols_for(classes: Sequence[str], *, turn: int = 0) -> list[str]:
    """Discovery-lane symbols with bars whose asset class is one of `classes`, at most
    MAX_SYMBOLS, SPREAD ACROSS THE CLASSES and rotated by `turn`.

    A sorted list cut at forty is forty AUD crosses: every pass would offer the same corner of
    the universe and the rest would never be asked about. Interleaving by class and starting each
    class at a different offset every pass walks the whole universe instead.
    """
    ap = _pipeline()
    try:
        from research import universe_policy as up
    except Exception:
        return []
    known = sorted(ap.known_symbols()) if ap is not None else []
    groups: dict[str, list[str]] = {c: [] for c in classes}
    for sym in known:
        if up.lane(sym) != up.HYPOTHESIS:
            continue
        klass = up.asset_class_of(sym)
        for c in classes:
            if any(w in klass for w in CLASS_WORDS.get(c, (c,))):
                groups[c].append(sym)
                break
    queues = [g[turn % len(g):] + g[:turn % len(g)] for g in groups.values() if g]
    out: list[str] = []
    while queues and len(out) < MAX_SYMBOLS:
        for q in list(queues):
            if q:
                out.append(q.pop(0))
            if not q:
                queues.remove(q)
            if len(out) >= MAX_SYMBOLS:
                break
    return out


def grammar(families: Sequence[tuple[str, str]], symbols: Sequence[str]) -> str:
    fams = ", ".join(f"{f} ({m})" for f, m in families)
    return "\n".join([
        "One JSON object per line with exactly these keys:",
        '  "family":    one registered family name from FAMILIES',
        f'  "symbols":   1 to {MAX_SYMBOLS_PER_ROW} symbols from SYMBOLS',
        '  "params":    optional object of numeric parameters for the family',
        '  "claim":     one sentence: the price rule the method implies, testable on H1 bars',
        '  "falsifier": one sentence naming the price behaviour that would kill the claim',
        "",
        f"FAMILIES: {fams}",
        f"SYMBOLS: {', '.join(symbols)}",
    ])


def task(entry: dict[str, Any]) -> str:
    return "\n".join([
        f"Below is an institutional research method ({entry['skill']}). Apply it to this desk's "
        f"MetaTrader universe as {entry.get('desk_reading', 'price rules')}.",
        "The method mentions data tools (forward curves, option surfaces, terminals) that this "
        "desk does NOT have. Use only what the desk's own hourly price bars can show; where the "
        "method needs data the desk lacks, propose its price-path expression or skip it.",
        "Each row must be a distinct, falsifiable rule. No single-company stocks.",
        "",
        "METHOD:",
        method_text(entry),
    ])


def make_validator(families: Sequence[tuple[str, str]], symbols: Sequence[str]):
    fams = {f for f, _ in families}
    syms = set(symbols)

    def validate(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return "not an object"
        if payload.get("family") not in fams:
            return "family not in the registered price-only menu"
        got = payload.get("symbols")
        if not isinstance(got, list) or not got or len(got) > MAX_SYMBOLS_PER_ROW:
            return "symbols missing or too many"
        if any(s not in syms for s in got):
            return "symbol outside the offered discovery-lane list"
        claim = payload.get("claim")
        if not isinstance(claim, str) or len(claim.strip()) < 20:
            return "no claim sentence"
        if any(_URL.search(str(payload.get(k) or "")) for k in ("claim", "falsifier")):
            return "a claim may not carry a URL"
        params = payload.get("params", {})
        if params is not None and not (isinstance(params, dict) and all(
                isinstance(v, int | float) and not isinstance(v, bool)
                for v in params.values())):
            return "params must be an object of numbers"
        return None
    return validate


def to_lead(payload: dict[str, Any], entry: dict[str, Any], prov: Any,
            now: datetime) -> dict[str, Any]:
    """An intelligence row the analyst pipeline reads: `family` makes it an executable lead."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    return {
        "source": f"{SOURCE}:{entry['skill']}",
        "seat": SOURCE,
        "kind": "hypothesis",
        "title": f"{entry['skill']}: {str(payload['claim']).strip()[:200]}",
        "claim": str(payload["claim"]).strip(),
        "falsifier": str(payload.get("falsifier") or "").strip()[:400],
        "family": payload["family"],
        "params": dict(payload.get("params") or {}),
        "symbols": list(payload["symbols"]),
        "skill": entry["skill"],
        "skill_sha256": entry["sha256"],
        "skill_commit": entry.get("commit", ""),
        "model": getattr(prov, "model", ""),
        "prompt_sha256": getattr(prov, "prompt_sha256", ""),
        "found_at": now.isoformat(timespec="seconds"),
        "url": f"fsi://{entry['skill']}/{digest}",
    }


# ================================================================================ state files
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def _next_skills(skills: list[dict[str, Any]], k: int, *, advance: bool) -> list[dict[str, Any]]:
    """Round-robin over the manifest so every method is asked in turn."""
    if not skills:
        return []
    at = int(_read_json(CURSOR, {}).get("next", 0)) % len(skills)
    picked = [skills[(at + i) % len(skills)] for i in range(min(k, len(skills)))]
    if advance:
        _atomic(CURSOR, {"next": (at + len(picked)) % len(skills),
                         "updated_utc": datetime.now(UTC).isoformat(timespec="seconds")})
    return picked


# ======================================================================================= run
def run(*, n_skills: int = SKILLS_PER_PASS, per_skill: int = PER_SKILL, dry_run: bool = False,
        now: datetime | None = None) -> dict[str, Any]:
    from libs.research import proposer_seat as ps

    now = now or datetime.now(UTC)
    report: dict[str, Any] = {"generated_utc": now.isoformat(timespec="seconds"),
                              "organ": ORGAN, "authority": "PROPOSER ONLY -- leads for the "
                              "analyst pipeline; the sealed gauntlet judges",
                              "trials_charged": 0, "skills": []}
    skills = manifest()
    report["skills_vendored"] = len(skills)
    if not skills:
        report["status"] = "NO_SKILLS"
        return report
    families = families_menu()
    report["families_offered"] = len(families)
    if not families:
        report["status"] = UNMEASURED
        report["why"] = "no registered price-only family resolved on this tree"
        return report
    if not ps.enabled():
        report["status"] = UNMEASURED
        report["why"] = "proposer seat dark: no free panel or LLM seat resolved"
        report["would_ask"] = [s["skill"] for s in _next_skills(skills, n_skills, advance=False)]
        return report

    leads: list[dict[str, Any]] = []
    turn = int(now.timestamp() // 3600)
    for entry in _next_skills(skills, n_skills, advance=not dry_run):
        symbols = symbols_for(entry.get("classes") or [], turn=turn)
        row: dict[str, Any] = {"skill": entry["skill"], "symbols_offered": len(symbols)}
        if not symbols:
            row.update(asked=0, accepted=0, why="no discovery-lane symbol of its classes")
            report["skills"].append(row)
            continue
        props = ps.propose(ORGAN, role=f"fsi:{entry['skill']}", task=task(entry),
                           grammar=grammar(families, symbols), n=per_skill,
                           kind="hypothesis", validate=make_validator(families, symbols))
        ok = [p for p in props if p.accepted]
        leads.extend(to_lead(p.payload, entry, p.provenance, now) for p in ok)
        row.update(asked=per_skill, replies=len(props), accepted=len(ok),
                   model=(props[0].provenance.model if props else ""),
                   discarded=dict(Counter(p.reason[:120] for p in props if not p.accepted)),
                   stripped=sorted({k for p in props for k in p.stripped}))
        report["skills"].append(row)

    report["leads"] = len(leads)
    if leads and not dry_run:
        from libs.data.pit import stamp_or_refuse
        stamped, refused = stamp_or_refuse(leads, SOURCE)
        report["pit_refused"] = len(refused)
        if stamped:
            path = INTEL / f"discoveries_{now.strftime('%Y%m%d_%H%M%S')}.json"
            _atomic(path, {"source": SOURCE, "generated_at": now.isoformat(),
                           "discoveries": stamped})
            report["written"] = str(path.relative_to(REPO))
        report["leads"] = len(stamped)
    report["status"] = "OK" if report["leads"] else "ZERO_PROPOSALS"
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--skills", type=int, default=SKILLS_PER_PASS)
    ap.add_argument("--per-skill", type=int, default=PER_SKILL)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = run(n_skills=args.skills, per_skill=args.per_skill, dry_run=args.dry_run)
    if not args.dry_run:
        _atomic(REPORT, report)
    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        print(f"FSI SKILLS {report['status']}: {report.get('leads', 0)} lead(s) from "
              f"{[s['skill'] for s in report['skills']]} -- {report.get('why', '')}")
    return 1 if report["status"] == "ZERO_PROPOSALS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
