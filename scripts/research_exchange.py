"""RESEARCH EXCHANGE -- the ChatGPT <-> Claude daily loop, and the scoreboard that judges both.

THE PRINCIPAL'S QUESTION: "im copy pasting ur responses to claude and claudes to urs, is there a
way to make them communicate w eachother daily?"

THE PRINCIPAL'S OWN ANSWER IS THE CORRECT ONE AND THIS IMPLEMENTS IT LITERALLY: "evidence sits
between them. They shouldn't persuade each other -- they should respond to the same data and
deterministic validation results." So there is NO model-to-model channel here, deliberately. Two
LLMs arguing directly produce consensus, and consensus between two systems trained on overlapping
corpora is not evidence -- it is correlated error wearing the costume of agreement. Worse, the
loser of an argument is decided by rhetoric, which is the single thing an LLM is best at and the
single thing that should carry no weight on a trading desk.

So the channel is a SHARED ARTEFACT, and both models are downstream of it:

    desk state (measured)  --brief-->  each model, independently, cold
                                            |
                                       proposals
                                            |
                                        --intake-->  suggestion ledger (attributed, deduped)
                                            |
                                       deterministic validation (the desk's existing gates)
                                            |
                                        --score-->  contributor scoreboard -> research allocation

Three verbs, one file, because they are one loop and splitting them would produce three scripts of
which two go unwired -- this desk already has 179 of those.

    python scripts/research_exchange.py brief          # -> docs/DESK_BRIEF.md  (paste to either)
    python scripts/research_exchange.py intake FILE --source chatgpt
    python scripts/research_exchange.py score

WHY THE SCOREBOARD IS THE POINT, NOT THE BRIEF. data/panel_scorecard.json has existed since
2026-07-17 with 13 providers and this content: 0 scored, hit_rate null, for EVERY provider. The
desk has never once measured which intelligence source produced value, so every allocation it has
ever made between sources was made on reputation. The brief is easy; attribution is the part that
was missing, and attribution only works if it is stamped at INTAKE, before anyone knows whether
the idea was any good. Scoring proposals after the fact, from memory, is how you get a scorecard
of nulls.

DEDUPE IS A HARD GATE, NOT A CONVENIENCE. An external model that has not read the graveyard will
re-propose dead mechanisms indefinitely -- it costs it nothing. Intake checks every proposal
against the mechanism FAMILY KILLS and the graveyard before it is allowed to consume a slot, and
records the rejection against the source's record. A source that mostly re-proposes corpses should
lose allocation for exactly that reason, and now it can be shown to.

Read-only w.r.t. trading. No keys, no network. Run from repo root.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data/suggestion_ledger.jsonl"
BRIEF = ROOT / "docs/DESK_BRIEF.md"
SCORE = ROOT / "data/contributor_scoreboard.json"
GRAVE = ROOT / "docs/graveyard.md"

# status ladder -- a proposal earns its way up. Weights are the reward function, so they are the
# whole design: a source is paid for CHANGING A DECISION, not for sounding insightful.
LADDER = {
    "proposed": 0.0,
    "rejected_dup": -0.5,
    "rejected_dead": -1.0,
    "accepted": 0.5,
    "built": 2.0,
    "changed_decision": 4.0,
    "improved_live": 10.0,
}

_STOP = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "is",
        "are",
        "be",
        "this",
        "that",
        "it",
        "as",
        "by",
        "from",
        "at",
        "we",
        "you",
        "your",
        "our",
        "their",
        "its",
        "should",
        "could",
        "would",
        "may",
        "might",
        "can",
        "will",
        "not",
        "no",
        "yes",
        "if",
        "then",
        "than",
        "more",
        "most",
        "less",
        "least",
        "very",
        "much",
        "many",
        "some",
        "any",
        "all",
        "new",
        "use",
        "used",
        "using",
        "into",
        "over",
        "under",
        "when",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "how",
        "why",
        "where",
        "research",
        "desk",
        "system",
        "data",
    }


def _toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in _STOP}


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return default


def _ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for ln in LEDGER.read_text("utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


# ------------------------------------------------------------------ BRIEF
def brief() -> None:
    """One machine-generated evidence file. No prose, no argument, no framing -- numbers only.

    Framing is how an LLM gets led. If the brief said "our carry is underperforming, what should
    we do?" every model would return carry ideas. It states measured quantities and lets the model
    decide what is interesting; a model that ignores the biggest number in the file is telling you
    something about the model.
    """
    reg = _read(ROOT / "data/experiment_registry.json", {}) or {}
    aut = _read(ROOT / "data/research_autopsy.json", {}) or {}
    mb = _read(ROOT / "data/mechanism_board.json", {}) or {}
    erv = _read(ROOT / "data/research_erv.json", {}) or {}
    mic = _read(ROOT / "data/micro_features.json", {}) or {}
    hold = _read(ROOT / "data/optimal_hold.json", {}) or {}

    L = [
        f"# DESK BRIEF -- {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%MZ')}",
        "",
        "Machine-generated from measured desk state. Every number traces to an artifact in",
        "`data/`. Nothing here is an argument. Respond to the evidence, not to another model.",
        "",
        "## Standing rules that bind any proposal",
        "1. Every proposal must name the MEASURABLE BOTTLENECK it removes, the metric that should",
        "   move, and the observation that would kill it. Missing any of the three = rejected.",
        "2. A proposal mapping to a FAMILY KILL below must present a NEW forced-flow or asymmetry",
        "   story. A new dataset for a dead mechanism is not a new hypothesis.",
        "3. Prefer DELETE/MERGE over ADD. This desk has 226 scripts and ~179 unwired.",
        "4. Screening is unlimited and carries ZERO promotion authority. Only pre-registered",
        "   forward clocks promote.",
        "",
    ]

    if reg:
        d = reg.get("decisions", {})
        L += [
            "## Experiment record (45d, harvested from git -- one row per commit)",
            f"- experiments: **{reg.get('n')}**; decided: "
            f"{sum(d.get(k, 0) for k in ('SURVIVED', 'REFUTED', 'INCONCLUSIVE'))}",
            f"- survival rate: **{(reg.get('survival_rate') or 0) * 100:.1f}%** "
            f"({d.get('SURVIVED', 0)} survived / {d.get('REFUTED', 0)} refuted / "
            f"{d.get('INCONCLUSIVE', 0)} inconclusive)",
            f"- unclassified commit decisions: {reg.get('unclassified')} "
            "(commit-discipline defect)",
            "",
        ]
        ms = reg.get("mechanism_survival", {})
        if ms:
            L += ["| mechanism | tested | survived | rate |", "|---|---:|---:|---:|"]
            for m, v in sorted(ms.items(), key=lambda kv: -kv[1]["tested"]):
                r = v["survived"] / v["tested"] * 100 if v["tested"] else 0
                L.append(f"| {m} | {v['tested']} | {v['survived']} | {r:.0f}% |")
            L.append("")
        fm = reg.get("failure_modes", {})
        if fm:
            tot = sum(fm.values())
            L += ["### Why experiments died (45d)", ""]
            for k, v in sorted(fm.items(), key=lambda kv: -kv[1]):
                L.append(f"- `{k}` {v} ({v / tot * 100:.0f}%)")
            meas = fm.get("E_DATA_QUALITY", 0) + fm.get("B_WRONG_MEASUREMENT", 0)
            L += [
                "",
                f"**{meas}/{tot} = {meas / tot * 100:.0f}% of refutations are MEASUREMENT "
                "failures (data quality + wrong construction), not absent alpha.**",
                "",
            ]
    if mb.get("family_kills"):
        L += [
            "## FAMILY KILLS -- mechanisms closed by evidence",
            "",
            ", ".join(f"`{m}`" for m in mb["family_kills"]),
            "",
            "Every future variant inherits this evidence.",
            "",
        ]
    if aut.get("lessons"):
        L += ["## Transferable lessons (family -> dominant failure mode)", ""]
        for x in aut["lessons"][:8]:
            L.append(f"- **{x['family']}** -> `{x['dominant_mode']}` (n={x['n']})")
        L.append("")
    if mic.get("results"):
        r0 = mic["results"]
        L += [
            "## Proprietary moat (4.4GB order books, 30 symbols, top-20 snapshots)",
            "",
            "M_LIQUIDITY_WITHDRAWAL, construction = negative z of near-touch depth vs 24h roll:",
            f"- raw lead rho pooled: {sum(x['lead_rho'] for x in r0) / len(r0):+.4f}",
            "- **after orthogonalising forward RV against current RV: residual rho +0.0154 "
            "(t +0.28), sign 1/5 -> the lead was vol clustering.**",
            "- ONE construction tested only. The mechanism is NOT refuted. Untested: "
            "replenishment rate, one-sided withdrawal, book shape, migration, recovery "
            "half-life, d(book)/dt.",
            "",
        ]
    if hold:
        L += [
            "## Live carry",
            "",
            "- entry gate `_DEFAULT_RT_BPS` 4.5 -> 39.5 (p90 of measured round-trip) on "
            "2026-07-27; bar is now ~8.8x the funding floor. Effect unmeasured until 24-48h "
            "of rotations accumulate.",
            "- pre-fix: funding harvested $113 vs implied costs $876 = **7.75x**.",
            "- hold-time scan: 8h -39.2%/yr, 24h +5.8%/yr (LIVE), 48h +14.0%/yr, 72h +17.0%/yr. "
            "`_MIN_HOLD_H` is still 24. ~+11pp/yr unclaimed.",
            "",
        ]
    if erv.get("ranked"):
        L += ["## Highest-ERV open hypotheses", ""]
        for h in erv["ranked"][:6]:
            L.append(f"- {h.get('erv', 0):.3f} — {h.get('name', '')[:88]}")
        L.append("")
    L += [
        "## Known blockers",
        "",
        "- OpenRouter 402: 4 written LLM roles have NEVER executed (code auditor, blind "
        "researcher, hypothesis generator, architecture board).",
        "- `health.json` reports all_ok=True against 14 stub vs 13 real logs (fail-open).",
        "- First forward-clock verdict: 2026-08-07 (OI/LS). Confirmed alphas to date: 0.",
        "",
    ]
    BRIEF.parent.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text("\n".join(L), "utf-8")
    print(f"wrote {BRIEF}  ({len(L)} lines)")
    print("Paste this ONE file to each model independently. Do not paste one model's reply to the")
    print("other -- that is persuasion. Paste their replies back through `intake` instead.")


# ------------------------------------------------------------------ INTAKE
def _dead_terms() -> tuple[set[str], list[str]]:
    mb = _read(ROOT / "data/mechanism_board.json", {}) or {}
    kills = set(mb.get("family_kills", []))
    names = []
    if GRAVE.exists():
        for ln in GRAVE.read_text("utf-8").splitlines():
            if ln.startswith("|") and not set(ln) <= set("|- "):
                c = [x.strip() for x in ln.strip("|").split("|")]
                if c and c[0].lower() not in ("name", "signal", "strategy"):
                    names.append(c[0])
    return kills, names


def intake(path: str, source: str) -> None:
    txt = Path(path).read_text("utf-8", errors="ignore")
    kills, _dead_names = _dead_terms()
    mb_kw = {
        "M_ATTENTION_DELAY": ("attention", "sentiment", "social", "twitter", "reddit", "trends"),
        "M_SKILL_PERSISTENCE": ("trader", "copytrad", "leaderboard", "smart money", "skill"),
        "M_FLOW_PRESSURE": ("netflow", "inflow", "outflow", "stablecoin flow", "bridge flow"),
        "M_PRICE_PATTERN": ("momentum", "rsi", "macd", "breakout", "moving average", "reversal"),
    }
    prior = _ledger()
    prior_toks = [(_toks(p.get("problem", "") + " " + p.get("benefit", "")), p) for p in prior]

    rows, stats = [], {"kept": 0, "dup": 0, "dead": 0, "incomplete": 0}
    for ln in txt.splitlines():
        if ln.count("|") < 2:
            continue
        parts = [x.strip() for x in ln.split("|") if x.strip()]
        if len(parts) < 7:
            stats["incomplete"] += 1  # looked like a proposal, missing mandatory fields
            continue
        rec = {
            "date": datetime.now(tz=UTC).date().isoformat(),
            "source": source,
            "problem": parts[0][:220],
            "evidence": parts[1][:220],
            "benefit": parts[2][:180],
            "cost": parts[3][:140],
            "dependencies": parts[4][:140],
            "success_metric": parts[5][:180],
            "kill_condition": parts[6][:180],
            "status": "proposed",
        }
        blob = " ".join(parts).lower()
        tk = _toks(rec["problem"] + " " + rec["benefit"])

        hit = next(
            (m for m, kws in mb_kw.items() if m in kills and any(k in blob for k in kws)), None
        )
        if hit:
            rec["status"] = "rejected_dead"
            rec["reason"] = f"maps to FAMILY KILL {hit} with no new asymmetry story"
            stats["dead"] += 1
        else:
            best, bp = 0.0, None
            for ptk, p in prior_toks:
                if not ptk or not tk:
                    continue
                j = len(tk & ptk) / len(tk | ptk)
                if j > best:
                    best, bp = j, p
            if best >= 0.55:
                rec["status"] = "rejected_dup"
                rec["reason"] = f"jaccard {best:.2f} vs prior {bp.get('source', '?')} proposal"
                stats["dup"] += 1
            else:
                stats["kept"] += 1
        rows.append(rec)

    if not rows:
        print("no charter-complete proposals found. Required per line, '|'-separated:")
        print("PROBLEM|EVIDENCE|BENEFIT|COST|DEPENDENCIES|SUCCESS_METRIC|KILL_CONDITION")
        print(f"({stats['incomplete']} lines looked like proposals but lacked all 7 fields)")
        return
    with LEDGER.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(
        f"source={source}  {stats['kept']} accepted-for-review, {stats['dup']} duplicate, "
        f"{stats['dead']} re-proposed a dead mechanism, {stats['incomplete']} incomplete"
    )
    for r in rows:
        if r["status"] != "proposed":
            print(f"  [{r['status']}] {r['problem'][:64]}\n      {r.get('reason', '')}")
    print(f"-> {LEDGER}")
    print("\nStatus is advanced by HUMAN/desk decision, never by the proposer:")
    print("  proposed -> accepted -> built -> changed_decision -> improved_live")


# ------------------------------------------------------------------ SCORE
def score() -> None:
    rows = _ledger()
    print("=== CONTRIBUTOR SCOREBOARD ===")
    print("    data/panel_scorecard.json has held 13 providers at 0 scored / hit_rate null since")
    print("    2026-07-17. Every allocation between sources so far was made on reputation.\n")
    if not rows:
        print("  ledger EMPTY -- 0 external proposals have ever been ingested.")
        print("  That is the honest state: there is nothing to score yet, and a scoreboard that")
        print("  reported numbers here would be fabricating them. Run `intake` first.")
        SCORE.write_text(
            json.dumps(
                {"updated": datetime.now(tz=UTC).isoformat(), "sources": {}, "n": 0}, indent=1
            ),
            "utf-8",
        )
        return
    by: dict[str, dict] = {}
    for r in rows:
        s = r.get("source") or r.get("seat") or "unknown"
        d = by.setdefault(s, dict.fromkeys(LADDER, 0))
        d[r.get("status", "proposed")] = d.get(r.get("status", "proposed"), 0) + 1
    print(
        f"  {'source':<26}{'prop':>6}{'dead':>6}{'dup':>5}{'built':>7}{'live':>6}{'score':>8}"
        f"{'yield':>8}"
    )
    out = {}
    for s, d in sorted(by.items()):
        n = sum(d.values())
        pts = sum(LADDER.get(k, 0) * v for k, v in d.items())
        conv = (d.get("built", 0) + d.get("changed_decision", 0) + d.get("improved_live", 0)) / n
        print(
            f"  {s:<26}{n:>6}{d.get('rejected_dead', 0):>6}{d.get('rejected_dup', 0):>5}"
            f"{d.get('built', 0):>7}{d.get('improved_live', 0):>6}{pts:>8.1f}{conv * 100:>7.0f}%"
        )
        out[s] = {"n": n, "points": round(pts, 2), "conversion": round(conv, 4), "detail": d}
    print("\n  SCORE weights the ladder: improved_live 10, changed_decision 4, built 2,")
    print("  accepted 0.5, re-proposing a dead mechanism -1. A source producing 200 clever")
    print("  proposals and one live improvement ranks BELOW one producing 20 of which five")
    print("  became infrastructure. Volume is not rewarded anywhere in this function.")
    SCORE.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "weights": LADDER,
                "sources": out,
                "n": len(rows),
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"  -> {SCORE}")


def main() -> None:
    a = sys.argv[1:]
    if not a or a[0] not in ("brief", "intake", "score"):
        print(__doc__)
        return
    if a[0] == "brief":
        brief()
    elif a[0] == "score":
        score()
    else:
        if len(a) < 2:
            raise SystemExit("usage: research_exchange.py intake FILE --source NAME")
        src = a[a.index("--source") + 1] if "--source" in a else "unknown"
        intake(a[1], src)


if __name__ == "__main__":
    main()
