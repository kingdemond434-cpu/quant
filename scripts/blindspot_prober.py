"""BLIND-SPOT PROBER (L6, principal 2026-07-27) -- structured creativity against self-blindness.

THE PROBLEM THIS EXISTS FOR: data/information_class_map.json is itself a blind spot. A hand-written
map can only contain classes someone already imagined; listing 30 classes never proves the universe
holds 30. Any "we've covered everything" is a statement about the MAP, never the TERRITORY.

So this is deliberately NOT another list of sources. It is a set of orthogonal LENSES that
MECHANICALLY GENERATE the question "what did we never mine, and why not?" from angles that do not
share a failure mode. A single lens has blind spots; six lenses that fail differently are much
harder to fool. Each lens emits concrete probes; probes become never-visited classes; those get
funded by the NEW_BRANCHES slice.

Run every cycle. The output is questions, not answers -- answering them is the dig.
Read-only. Run from repo root.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

MAP = Path("data/information_class_map.json")
OUT = Path("data/blindspot_probes.json")

LENSES = {
    "L6a_MODALITY_GAP": {
        "question": "Which information CARRIERS are structurally under-mined vs our comfort zone?",
        "why_orthogonal": ("catches format bias -- we mine numbers because numbers are easy, "
                           "not because they are informative"),
        "probes": [
            "For every modality at <50% coverage, name ONE concrete free source and screen it.",
            "What information exists ONLY as audio/video and has no text equivalent?",
            "What is published as an image/chart but never as a series (and could be OCR'd)?",
            "What arrives as a STREAM we only sample as snapshots (and thus destroy)?",
        ],
    },
    "L6b_NEGATIVE_SPACE": {
        "question": "What important information leaves NO public footprint -- and what proxies it?",
        "why_orthogonal": ("the class map can only list what EXISTS; this lens starts from "
                           "what MATTERS and works backwards"),
        "probes": [
            "OTC block flow: invisible directly -- proxy via exchange reserve steps, stablecoin "
            "mints, settlement windows?",
            "Market-maker inventory: invisible -- proxy via quote asymmetry, depth decay, funding "
            "response?",
            "Institutional execution algos: invisible -- proxy via intraday volume fingerprints, "
            "child-order spacing?",
            "Private treasury/board decisions: invisible -- proxy via hiring, filings, domain "
            "registrations, doc diffs?",
            "For each: is the PROXY testable free, and does it lead or coincide?",
        ],
    },
    "L6c_CROSS_DOMAIN_IMPORT": {
        "question": ("What information classes do OTHER disciplines mine that crypto quant "
                     "does not?"),
        "why_orthogonal": "imports modalities the whole FIELD is blind to, not just this desk",
        "probes": [
            "Epidemiology: contact-network diffusion models -- applied to holder/wallet graphs?",
            "Ad-tech: attribution + incrementality testing -- applied to flow attribution?",
            "Insurance: catastrophe/tail modelling -- applied to liquidation cascades?",
            "Supply chain: lead-time and bullwhip -- applied to mining/hardware/energy?",
            "Sports betting: closing-line value as a skill metric -- applied to trader/prediction "
            "markets?",
            "Seismology: foreshock/aftershock clustering (Hawkes) -- applied to liquidation "
            "clustering?",
        ],
    },
    "L6d_ADVERSARIAL": {
        "question": "If a competitor had an edge we lack, what information would it be built on?",
        "why_orthogonal": "inverts from OPPONENT capability rather than our own inventory",
        "probes": [
            "What does a market maker see that we never will -- and what shadow does it cast in "
            "public data?",
            "What does a large exchange see internally, and which of it leaks into public "
            "endpoints?",
            "What does a VC see pre-announcement, and what public artifact appears first (repos, "
            "domains, hiring)?",
            "What would a regulator see, and which of it becomes public on a lag we could exploit?",
        ],
    },
    "L6e_INVERSION": {
        "question": "Start from the TARGET, derive the information required, THEN hunt it.",
        "why_orthogonal": ("everything else starts from available data; this starts from the "
                           "question and refuses to be limited by inventory"),
        "probes": [
            "To predict a funding regime change, what would you IDEALLY observe? Does any public "
            "proxy exist?",
            "To predict a liquidation cascade 1h ahead, what is the minimal sufficient "
            "observation?",
            "To predict venue migration, what would you need? (fee changes, listing races, "
            "incentive programmes)",
            "For each ideal observable: rank by (importance x free-obtainability), not by "
            "convenience.",
        ],
    },
    "L6f_SELF_AUDIT": {
        "question": "What did we DECLINE to test, and is the reason still valid?",
        "why_orthogonal": ("audits our own past judgement rather than the world -- catches "
                           "stale refusals"),
        "probes": [
            "List every source parked as 'blocked/paid/too hard'. Re-check access -- did it "
            "change?",
            "List every class killed on ONE test. Was the test powered? (power now mandatory)",
            "What did we skip because it was UNCOMFORTABLE (NLP, video, non-English) rather than "
            "because it was refuted?",
            "Which refusals were about cost, and has the cost or our budget moved?",
        ],
    },
}


def main() -> None:
    cov = {}
    if MAP.exists():
        d = json.loads(MAP.read_text("utf-8"))
        for _k, v in d.get("classes", {}).items():
            cov.setdefault(v["modality"], {"covered": 0, "n": 0})
            cov[v["modality"]]["n"] += 1
            if v["status"] == "covered":
                cov[v["modality"]]["covered"] += 1

    print("=== BLIND-SPOT PROBER (L6) -- structured creativity, not another source list ===")
    print("    The class map is ITSELF a blind spot: it holds only what someone imagined.")
    print("    Six lenses that FAIL DIFFERENTLY are much harder to fool than one list.\n")

    if cov:
        weak = sorted(cov.items(), key=lambda kv: kv[1]["covered"] / max(1, kv[1]["n"]))
        print("  measured format bias (feeds L6a):")
        for m, c in weak:
            print(
                f"    {m:<12} {c['covered']}/{c['n']} covered"
                f"{'   <-- STRUCTURAL BLIND SPOT' if c['covered'] == 0 else ''}"
            )
        print()

    for lid, L in LENSES.items():
        print(f"--- {lid}")
        print(f"    Q: {L['question']}")
        print(f"    why orthogonal: {L['why_orthogonal']}")
        for pr in L["probes"]:
            print(f"      . {pr}")
        print()

    n = sum(len(L["probes"]) for L in LENSES.values())
    print(f"=> {n} standing probes across {len(LENSES)} orthogonal lenses.")
    print("   RULE: every cycle answers at least one probe per lens with EVIDENCE (a screened")
    print("   source, or a documented reason it is not free-obtainable). An unanswered lens is")
    print("   a live blind spot, not a completed audit.")
    print("   CEILING CLAUSE: 'no probes remain' is never a valid report -- it means the lenses")
    print("   went stale. Blind re-derivation regenerates them from scratch, ignoring this file.")

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "n_probes": n,
                "modality_bias": cov,
                "lenses": LENSES,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
