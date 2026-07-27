"""INFORMATION CLASS MAP (L5 modality-blind mandate, principal 2026-07-27).

The branch registry tracks MECHANISMS. This tracks the orthogonal axis: MODALITY x ACCESS -- the
KINDS of information carrier the desk can mine. "Raw information is information no matter how it
was mined": text, audio, video, transcript, image, code, tabular, graph, stream, filing, archive.
Format never determines value; only testable-signal-per-source does.

Purpose: make "expand classes not yet searched" MEASURABLE. Every class carries a status; the
never-visited ones are the concrete target list that the NEW_BRANCHES budget slice funds. A class
is retired only to `low-yield-archived` (never deleted -- L1 monotonic), and archived classes are
re-surfaced by the quarterly blind re-derivation.

LEGITIMACY GATE (DIGGING_CHARTER s13, unchanged and non-negotiable): public + legitimately
accessible only. Public forums/groups/videos/transcripts/filings = YES. Paywalled, pirated,
cracked, private-group, or paid-DB-mirrored content = NO, regardless of expected value.

Read-only report. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

OUT = Path("data/information_class_map.json")

# class -> (modality, status, note)
#   covered      = actively mined today
#   partial      = touched but not systematically mined
#   never-visited= concrete expansion target (funded by NEW_BRANCHES)
#   blocked      = legitimacy gate or hard access wall (kept visible, never silently dropped)
CLASSES = {
    # --- structured / numeric (the desk's comfort zone) -----------------------------------
    "exchange_api_ohlcv":        ("tabular", "covered", "recorders + klines, multi-venue"),
    "derivatives_metrics":       ("tabular", "covered", "funding/OI/liquidations/vol surface"),
    "onchain_rpc":               ("tabular", "covered", "stablecoin flows, reserves, throughput"),
    "macro_series":              ("tabular", "covered", "FRED/SOMA/RRP/TGA net liquidity"),
    "orderbook_l2":              ("stream", "covered", "recorded L2 -> measured cost model"),
    # --- code / developer ------------------------------------------------------------------
    "source_repositories":       ("code", "covered", "prospector; commit/contributor tested 07-27"),
    "package_registries":        ("tabular", "never-visited", "npm/PyPI/crates download curves = adoption proxy"),
    "smart_contract_bytecode":   ("code", "never-visited", "deployment/verification rate, upgrade cadence"),
    # --- text ------------------------------------------------------------------------------
    "academic_papers":           ("text", "covered", "arXiv/SSRN feed -> litminer"),
    "regional_forums":           ("text", "partial", "CN/KR/JP/RU charter-mandated; not systematically parsed"),
    "protocol_governance":       ("text", "never-visited", "Snapshot/Tally proposals, delegate behaviour"),
    "regulatory_filings":        ("filing", "never-visited", "SEC/CFTC/FCA/MAS/FSA actions + licences"),
    "public_company_reports":    ("filing", "never-visited", "Virtu/Flow Traders 10-Ks = real execution economics"),
    "protocol_documentation":    ("text", "never-visited", "docs/roadmap diffs via archive snapshots"),
    # --- audio / video / transcript (explicitly named by the principal) ---------------------
    "video_transcripts":         ("transcript", "never-visited", "public conference/earnings/AMA talks; auto-caption"),
    "podcast_transcripts":       ("transcript", "never-visited", "public feeds; entity + commitment extraction"),
    "livestream_chat":           ("stream", "never-visited", "public stream chat = retail attention proxy"),
    "conference_talks":          ("video", "never-visited", "devcon/ETHGlobal schedules = roadmap leading indicator"),
    # --- social / group --------------------------------------------------------------------
    "public_group_messages":     ("text", "never-visited", "PUBLIC Telegram/Discord only (s13 gate)"),
    "social_graph_structure":    ("graph", "never-visited", "who-follows-whom topology, not sentiment"),
    "search_interest":           ("tabular", "covered", "Wikipedia pageviews tested; multilingual attention DEAD at all horizons"),
    # --- network / graph -------------------------------------------------------------------
    "wallet_transaction_graph":  ("graph", "partial", "addresses read; clustering/identity not built"),
    "bridge_flow_graph":         ("graph", "blocked", "DefiLlama bridges API now 402 paid"),
    "validator_topology":        ("graph", "never-visited", "stake concentration, client diversity, geography"),
    # --- infrastructure telemetry ----------------------------------------------------------
    "mempool_state":             ("stream", "partial", "size/fees tested SCREEN-WEAK; pending-tx stream unbuilt"),
    "rpc_node_health":           ("stream", "never-visited", "latency/failure as stress proxy"),
    "oracle_update_timing":      ("stream", "never-visited", "update cadence deviation = stress signal"),
    # --- archives --------------------------------------------------------------------------
    "web_archive_diffs":         ("archive", "never-visited", "Wayback diffs on docs/terms/roadmaps"),
    "historical_dumps":          ("archive", "partial", "binance.vision used for OI/LS backfill"),
    "prediction_markets":        ("tabular", "partial", "libs/data/prediction_markets.py exists, unmined"),
}

MODALITY_NOTE = ("format never determines value -- a transcript and a candle are both raw "
                 "information; only testable-signal-per-source ranks them")


def main() -> None:
    by_status, by_mod = {}, {}
    for name, (mod, status, note) in CLASSES.items():
        by_status.setdefault(status, []).append((name, mod, note))
        by_mod.setdefault(mod, []).append(status)

    print("=== INFORMATION CLASS MAP (modality x access) ===")
    print(f"    {MODALITY_NOTE}\n")
    order = ["covered", "partial", "never-visited", "blocked"]
    for st in order:
        items = by_status.get(st, [])
        print(f"--- {st.upper()} ({len(items)})")
        for name, mod, note in sorted(items):
            print(f"    {name:<28} [{mod:<10}] {note}")
        print()

    nv = by_status.get("never-visited", [])
    print(f"=> EXPANSION TARGET LIST: {len(nv)} classes never visited "
          f"({100*len(nv)/len(CLASSES):.0f}% of the mapped universe)")
    print("   These are what the NEW_BRANCHES budget slice funds. Modality coverage:")
    for mod in sorted(by_mod):
        sts = by_mod[mod]
        cov = sum(1 for s in sts if s == "covered")
        print(f"     {mod:<12} {cov}/{len(sts)} covered")
    print("\n   LEGITIMACY GATE (s13, non-negotiable): public + legitimately accessible ONLY.")
    print("   Public forums/groups/videos/transcripts/filings YES. Paywalled/pirated/private NO,")
    print("   regardless of expected value.")

    OUT.write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "n_classes": len(CLASSES),
         "never_visited": len(nv), "modality_note": MODALITY_NOTE,
         "classes": {k: {"modality": v[0], "status": v[1], "note": v[2]}
                     for k, v in CLASSES.items()}}, indent=1), "utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
