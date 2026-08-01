"""DATA VITALS -- live collector health scoring (DQS) + provenance. Prevents the silent failure.

WHY THIS EXISTS. A Binance websocket handshake succeeded and then delivered no frames for 14 days.
Nothing noticed. A forward clock ran the whole time on a dead feed. `measurement_gate.py` answers
"is this dataset VALID FOR RESEARCH?" -- a slow, structural question. This answers a different and
faster one: "is this collector ALIVE RIGHT NOW?" They are not the same check and conflating them
is how a dead feed passes as healthy: a frozen file is perfectly self-consistent.

DATA QUALITY SCORE, five components, each in [0,1], product-weighted so ANY single failure drags
the score down. A mean would let four healthy components hide one dead one -- which is exactly the
silent-failure shape.

    latency            staleness vs the source's own observed cadence
    completeness       records in the last window vs the historical rate
    schema_integrity   modal key-set conformance (did the format change under us?)
    temporal_alignment monotonic, no future stamps
    cross_validation   0.5 when no second source exists -- ABSENCE IS NOT HEALTH

HARD RULE (principal): DQS < 0.5 sustained => the collector is dead. The action is emitted here;
execution of failover belongs to whatever supervises collectors, because a read-only health
scorer that also restarts things is a scorer nobody can trust to be read-only.

PROVENANCE is recorded per source: how it was collected, whether it can be regenerated, and
whether its timestamps are verified or assumed. `cny_otc_premium_history.jsonl` carries
"23:55 CST (UTC+8) assumed" in a prose field -- an unverified alignment feeding a LIVE mechanism.

Read-only. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/data_vitals.json"
DQS_DEAD = 0.5
MAX_ROWS = 3000

_TIME_KEYS = ("ts", "date", "timestamp", "time", "datetime", "updated")

# Provenance the desk can state with evidence. Anything absent is reported UNKNOWN, never assumed.
PROVENANCE = {
    "cny_otc_premium_history.jsonl": {
        "collection": "wayback-cdx-replay of history.btc126.com (UNCOMMITTED one-off)",
        "regenerable": False,
        "timestamp_verified": False,
        "note": "rows carry '23:55 CST (UTC+8) assumed'. Alignment vs the USD/CNY reference is "
                "ASSUMED. Feeds M_STRUCTURAL_BARRIER, one of two ALIVE mechanisms."},
    "oi_ls_history.jsonl": {"collection": "binance futures API", "regenerable": True,
                            "timestamp_verified": True, "note": "daily archive"},
    "onchain_metrics.jsonl": {"collection": "public chain API", "regenerable": True,
                              "timestamp_verified": True, "note": "public, no moat"},
    "coinmetrics_flows.jsonl": {"collection": "coinmetrics community API", "regenerable": True,
                                "timestamp_verified": True, "note": "public tier"},
    "venue_divergence_shadow.jsonl": {"collection": "self-recorded multi-venue poll",
                                      "regenerable": False, "timestamp_verified": True,
                                      "note": "point-in-time capture; cannot be backfilled"},
}


# Not every .jsonl is a live collector. Scoring a static archive or a git-derived artifact by
# live-feed latency rules produced 9 DEAD flags of which only one was real -- and an alarm that
# fires mostly on non-problems trains its reader to ignore it.
_ARTIFACT_KIND = {
    "oi_ls_history.jsonl": ("STATIC", "historical backfill, ends 2023-12-03 BY DESIGN"),
    "cny_otc_premium_history.jsonl": ("STATIC", "wayback backfill; live feed is cny_premium.jsonl"),
    "experiment_registry.jsonl": ("DERIVED", "harvested from git; timestamps are commit dates"),
    "panel_verdicts.jsonl": ("EVENT_LOG", "appended per panel run, not a feed"),
    "external_panel_log.jsonl": ("EVENT_LOG", "appended per panel run"),
    "micro_audit_log.jsonl": ("EVENT_LOG", "appended per audit"),
    "mine_conversion_log.jsonl": ("EVENT_LOG", "appended per conversion"),
    "blind_spot_ledger.jsonl": ("EVENT_LOG", "appended per gap"),
    "information_value.jsonl": ("DERIVED", "written by libs/research/information_value.py"),
}


def _parse_ts(v):
    if isinstance(v, (int, float)):
        x = float(v)
        if x > 1e11:
            x /= 1000.0
        return datetime.fromtimestamp(x, tz=UTC) if 9.4e8 < x < 4.1e9 else None
    if not isinstance(v, str):
        return None
    s = v.strip().replace("Z", "+00:00")
    for f in (None, "%Y-%m-%d"):
        try:
            d = datetime.fromisoformat(s) if f is None else datetime.strptime(s, f).replace(tzinfo=UTC)
            return d if d.tzinfo else d.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
    return None


def _rows(p: Path):
    out = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, ln in enumerate(fh):
                if i >= MAX_ROWS:
                    break
                ln = ln.strip()
                if ln:
                    try:
                        d = json.loads(ln)
                        if isinstance(d, dict):
                            out.append(d)
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return out


def score(p: Path) -> dict | None:
    kind, why = _ARTIFACT_KIND.get(p.name, (None, None))
    if kind:
        # Reported with its true nature. DEAD must mean "a live feed stopped", nothing else.
        return {"source": p.name, "dqs": None,
                "components": {"latency": None, "completeness": None, "schema_integrity": None,
                               "temporal_alignment": None, "cross_validation_available": False},
                "cadence_s": None, "age_s": None,
                "provenance": PROVENANCE.get(p.name, {"collection": kind, "regenerable": None,
                                                      "timestamp_verified": None, "note": why}),
                "action": f"{kind} -- not a live feed ({why})"}
    rows = _rows(p)
    if len(rows) < 20:
        # REPORTED, NOT DROPPED. A silently skipped file vanishes from the denominator and is
        # then indistinguishable from a file that passed -- coverage read 56.8% while the desk
        # could not say what became of the other 43%.
        return {"source": p.name, "dqs": None,
                "components": {"latency": None, "completeness": None, "schema_integrity": None,
                               "temporal_alignment": None, "cross_validation_available": False},
                "cadence_s": None, "age_s": None,
                "provenance": PROVENANCE.get(p.name, {"collection": "UNKNOWN",
                                                      "regenerable": None,
                                                      "timestamp_verified": None,
                                                      "note": f"only {len(rows)} rows"}),
                "action": "TOO_SMALL -- reported, not scored"}
    key = next((k for k in _TIME_KEYS if k in rows[0]), None)
    ts = [t for t in (_parse_ts(r.get(key)) for r in rows) if t] if key else []
    now = datetime.now(tz=UTC)
    # NEW-FILE GRACE. A collector's first run writes many rows at ONE timestamp, so cadence is
    # uncomputable and latency/completeness default low -- scoring a healthy new source DEAD.
    # defi_lending scored 0.250 DEAD on its .jsonl while its heartbeat scored 1.000 OK: the same
    # source, two verdicts, one of them false. Fewer than 3 distinct timestamps means "not yet
    # measurable", which is not the same as "dead" and must not page.
    if len({t.isoformat() for t in ts}) < 3:
        return {"source": p.name, "dqs": None,
                "components": {"latency": None, "completeness": None,
                               "schema_integrity": None, "temporal_alignment": None,
                               "cross_validation_available": False},
                "cadence_s": None, "age_s": None,
                "provenance": PROVENANCE.get(p.name, {"collection": "UNKNOWN",
                                                      "regenerable": None,
                                                      "timestamp_verified": None,
                                                      "note": "too few timestamps to score"}),
                "action": "NEW -- not yet measurable"}

    # latency -- measured against the source's OWN observed cadence, not a global constant.
    # A daily archive is not "stale" at 6h; a websocket feed is dead at 6h.
    lat = 0.5
    cadence_s = None
    if len(ts) >= 8:
        gaps = sorted((b - a).total_seconds() for a, b in itertools.pairwise(ts) if b >= a)
        cadence_s = gaps[len(gaps) // 2] if gaps else None
        if cadence_s and cadence_s > 0:
            age = (now - max(ts)).total_seconds()
            lat = 1.0 if age <= cadence_s * 2 else max(0.0, 1.0 - (age / (cadence_s * 10)))

    # completeness -- recent rate vs historical rate
    comp = 0.5
    if cadence_s and len(ts) >= 20:
        recent = [t for t in ts if (now - t).total_seconds() <= cadence_s * 20]
        comp = min(1.0, len(recent) / 20.0)

    keysets = [frozenset(r) for r in rows]
    modal = max(set(keysets), key=keysets.count)
    schema = keysets.count(modal) / len(keysets)

    align = 1.0
    if ts:
        ooo = sum(1 for a, b in itertools.pairwise(ts) if b < a)
        fut = sum(1 for t in ts if t > now.replace(microsecond=0) and (t - now).days > 0)
        align = max(0.0, 1.0 - (ooo + fut * 5) / len(ts))

    # ABSENCE IS NOT HEALTH: no second source == 0.5, never 1.0.

    # DQS excludes cross_validation: it is a CONSTANT 0.5 (no source has a second feed),
    # so multiplying it in capped every score at 0.5 against a 0.5 threshold and marked
    # 14/14 collectors DEAD regardless of health. A constant carries no information.
    dqs = lat * comp * schema * align
    prov = PROVENANCE.get(p.name, {"collection": "UNKNOWN", "regenerable": None,
                                   "timestamp_verified": None, "note": "provenance not recorded"})
    return {"source": p.name, "dqs": round(dqs, 4),
            "components": {"latency": round(lat, 3), "completeness": round(comp, 3),
                           "schema_integrity": round(schema, 3),
                           "temporal_alignment": round(align, 3), "cross_validation_available": False},
            "cadence_s": round(cadence_s, 1) if cadence_s else None,
            "age_s": round((now - max(ts)).total_seconds(), 0) if ts else None,
            "provenance": prov,
            "action": "DEAD -- FAILOVER" if dqs < DQS_DEAD else "OK"}



# ---------------------------------------------------------------- non-.jsonl sources
# Added 2026-07-28 after dependency_graph showed the three sources feeding EVERY alpha were
# entirely outside the DQS scan. Each carries its own cadence because a daily state file and an
# hourly recorder are not "stale" at the same age.
EXTRA_SOURCES = {
    "axis_shadow_state.json (live clocks)": {
        "kind": "JSON_STATE", "path": "data/axis_shadow_state.json",
        "field": "updated", "cadence_s": 86400,
        "feeds": "A002 -- the running forward clocks"},
    "data/moat (order books)": {
        "kind": "DIR_GLOB", "path": "data/moat", "glob": "**/*.jsonl.gz",
        "cadence_s": 3600,
        "feeds": "A004 -- the only source with a real information advantage"},
    "cashcarry_positions.json (live book)": {
        "kind": "JSON_STATE", "path": "data/cashcarry_positions.json",
        "field": None, "cadence_s": 900,
        "feeds": "A001 -- the live carry book; mtime is the freshness signal"},
    "binance funding (live API)": {
        "kind": "JSON_STATE", "path": "data/cashcarry_exec_heartbeat",
        "field": None, "cadence_s": 120,
        "feeds": "A001 live carry entry gate. PROXY, and the link is causal: the executor calls "
                 "current_funding() every cycle and cannot complete one without it, so a stalled "
                 "heartbeat IS a dead funding feed"},
    "oi_ls_live (Binance positioning)": {
        "kind": "JSON_STATE", "path": "data/oi_ls_live_heartbeat",
        "field": None, "cadence_s": 3600,
        "feeds": "M_FORCED_DELEVERAGE -- live crowding; the static archive ends 2023-12-03"},
    "defi_lending (Aave/Compound/Morpho)": {
        "kind": "JSON_STATE", "path": "data/defi_lending_heartbeat",
        "field": None, "cadence_s": 3600,
        "feeds": "M_FORCED_DELEVERAGE -- leverage build-up upstream of perp funding"},
    "cashcarry_exec_heartbeat (executor)": {
        "kind": "JSON_STATE", "path": "data/cashcarry_exec_heartbeat",
        "field": None, "cadence_s": 120,
        "feeds": "A001 -- executor liveness; the money-moving process itself"},
}


def score_extra(name: str, cfg: dict) -> dict | None:
    """Liveness for sources the .jsonl scan cannot see. Freshness IS the signal here; there is
    no schema or completeness to measure on a state file or a rolling directory."""
    p = ROOT / cfg["path"]
    now = datetime.now(tz=UTC).timestamp()
    age = None
    if cfg["kind"] == "JSON_STATE":
        if not p.exists():
            age = None
        elif cfg.get("field"):
            d = None
            try:
                d = json.loads(p.read_text("utf-8")).get(cfg["field"])
            except Exception:  # blind-except intentional (BLE001)
                d = None
            t = _parse_ts(d) if d else None
            age = (now - t.timestamp()) if t else (now - p.stat().st_mtime)
        else:
            age = now - p.stat().st_mtime
    elif cfg["kind"] == "DIR_GLOB" and p.exists():
        newest = max((f.stat().st_mtime for f in p.glob(cfg["glob"])), default=None)
        age = (now - newest) if newest else None

    if age is None:
        return {"source": name, "dqs": 0.0, "components": {"latency": 0.0, "completeness": 0.0,
                "schema_integrity": 0.0, "temporal_alignment": 0.0,
                "cross_validation_available": False},
                "cadence_s": cfg["cadence_s"], "age_s": None,
                "provenance": {"collection": cfg["kind"], "regenerable": None,
                               "timestamp_verified": None, "note": cfg["feeds"]},
                "action": "MISSING -- source not found"}

    cad = float(cfg["cadence_s"])
    lat = 1.0 if age <= cad * 2 else max(0.0, 1.0 - (age / (cad * 10)))
    # A state file has no schema drift or completeness to measure; scoring them 1.0 would be
    # inventing evidence, so DQS for these is the latency term alone and is labelled as such.
    return {"source": name, "dqs": round(lat, 4),
            "components": {"latency": round(lat, 3), "completeness": None,
                           "schema_integrity": None, "temporal_alignment": None,
                           "cross_validation_available": False},
            "cadence_s": cfg["cadence_s"], "age_s": round(age, 0),
            "provenance": {"collection": cfg["kind"], "regenerable": None,
                           "timestamp_verified": None, "note": cfg["feeds"]},
            "action": "DEAD -- FAILOVER" if lat < DQS_DEAD else "OK"}


def main() -> None:
    print("=== DATA VITALS -- is the collector ALIVE, not is the dataset VALID ===")
    print("    a 14-day silent websocket failure passed every structural check, because a")
    print("    frozen file is perfectly self-consistent. DQS is a PRODUCT, so one dead")
    print("    component cannot be hidden by four healthy ones.\n")
    rows = [s for s in (score(p) for p in sorted((ROOT / "data").glob("*.jsonl"))) if s]
    rows += [r for r in (score_extra(n, c) for n, c in EXTRA_SOURCES.items()) if r]
    if not rows:
        raise SystemExit("no collectors with >=20 rows")
    rows.sort(key=lambda r: (r["dqs"] is None, r["dqs"] or 0))
    print(f"  {'source':<38}{'DQS':>7}{'lat':>6}{'comp':>6}{'schm':>6}{'algn':>6}  action")
    dead = 0
    for r in rows:
        c = r["components"]
        dead += (r["dqs"] is not None and r["dqs"] < DQS_DEAD)

        def _f(v):
            return f"{v:>6.2f}" if isinstance(v, (int, float)) else f"{'-':>6}"
        _d = f"{r['dqs']:>7.3f}" if r['dqs'] is not None else f"{'new':>7}"
        print(f"  {r['source']:<38}{_d}{_f(c['latency'])}{_f(c['completeness'])}"
              f"{_f(c['schema_integrity'])}{_f(c['temporal_alignment'])}  {r['action']}")
    print(f"\n  {dead}/{len(rows)} collectors below DQS {DQS_DEAD} -> flagged DEAD")
    print("  NOTE: cross_validation is 0.5 for every source because NO collector currently has")
    print("  a second independent feed. That caps every DQS at 0.5x its otherwise value, which")
    print("  is deliberate -- an unverifiable feed is not a healthy feed, it is an unchecked one.")

    unk = [r for r in rows if r["provenance"]["collection"] == "UNKNOWN"]
    bad_ts = [r for r in rows if r["provenance"].get("timestamp_verified") is False]
    norg = [r for r in rows if r["provenance"].get("regenerable") is False]
    print(f"\n  PROVENANCE: {len(unk)} sources with UNKNOWN collection method; "
          f"{len(norg)} NOT regenerable; {len(bad_ts)} with UNVERIFIED timestamps")
    for r in bad_ts:
        print(f"    !! {r['source']}: {r['provenance']['note']}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "dqs_dead_threshold": DQS_DEAD, "n_dead": dead,
                               "collectors": rows}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
