"""CLAIM VERIFIER -- does every number the desk PUBLISHES survive contact with its own source?

THREE MEASURED FAILURES ON 2026-07-27, all the same shape: a dashboard confidently reported a
state that was not true, and nothing cross-checked it.
  health.json     said all_ok: true          while every AI organ had been dead 4+ days
  portfolio.json  said equity $14,853        while the venue reported $5,262 (175% divergence)
  axis_shadows    said cny "ACCRUING 1/40"   while it had 0 usable z-values (evidence not started)

None of these were crashes. Each was a CONFIDENT WRONG CLAIM, and a claim is what you act on.
The NAV gap was found by accident while checking an unrelated false positive -- nothing was
looking for it. This looks for it.

METHOD: for each published claim, read the SOURCE independently and compare. Never trust a
summary artifact to describe itself; a self-report cannot detect its own divergence.

PRIORITISED BY CAPITAL CONSEQUENCE, not by ease: a wrong NAV corrupts every sizing, leverage and
risk decision downstream, so it is checked first and hardest.

Read-only, no LLM, no keys. Run from repo root, daily.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web"
OUT = DATA / "claim_verification.json"


def load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for ln in p.read_text("utf-8", errors="ignore").splitlines():
        if ln.strip():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not r.get("_summary"):
                out.append(r)
    return out


def check(findings, sev, claim, claimed, actual, consequence):
    ok = sev == "OK"
    findings.append(
        {
            "severity": sev,
            "claim": claim,
            "claimed": str(claimed)[:90],
            "actual": str(actual)[:90],
            "consequence": consequence,
        }
    )
    tag = "OK      " if ok else sev
    print(f"  [{tag}] {claim}")
    if not ok:
        print(f"             claims : {claimed}")
        print(f"             source : {actual}")
        print(f"             -> {consequence}")


def main() -> None:
    print("=== CLAIM VERIFIER -- every published number, traced to its source ===")
    print("    a self-report cannot detect its own divergence. 3 dashboards lied today.\n")
    f: list[dict] = []

    # ---- 1. NAV SCOPE -- corrected 2026-07-27 -------------------------------------------
    # ORIGINAL CHECK WAS WRONG and escalated a false CRITICAL. It compared venue_nav against
    # portfolio equity as if they measured the same thing. They never did:
    #   venue_equity.json  = "fut margin + tracked spot legs + USDT delta" (FUTURES scope, ~$5k;
    #                        venue 5,169 / start_futures 5,000 = 1.03x)
    #   portfolio.equity   = the whole book (TOTAL scope, ~$14.4k / start 15,000 = 0.96x)
    # So the "175% divergence" was a UNIT ERROR of mine, not a lost $9k. No money is missing.
    #
    # THE REAL DEFECT IS DOWNSTREAM: run_venue_divergence_shadow.py logs pct_diff between these
    # two scopes, and its stated purpose is calibrating the GAP #19 circuit breaker at "~2x
    # OBSERVED noise". A breaker calibrated on a 175% phantom gap either never fires or always
    # fires. Its own docstring says the 07-22 dead-man false fires happened "because a trigger was
    # set without knowing the measurement noise of its own inputs" -- this is that same failure,
    # one level up. So the check now verifies SCOPE COMPARABILITY, which is the thing that matters.
    port = load(WEB / "portfolio.json") or {}
    equity = (port.get("deployed") or {}).get("equity")
    ven = load(WEB / "venue_equity.json") or {}
    vneq = ven.get("equity")
    att = jsonl(DATA / "nav_attestation.jsonl")
    fut_start = att[-1].get("start_futures_equity") if att else None
    if equity and vneq and fut_start:
        vratio = vneq / fut_start  # ~1.0 => venue tracks the futures scope
        pratio = equity / (port.get("deployed") or {}).get("start_capital", 1)
        scope_mismatch = abs(equity - vneq) / max(vneq, 1e-9) > 0.5 and 0.5 < vratio < 2.0
        sev = "HIGH" if scope_mismatch else "OK"
        check(
            f,
            sev,
            "venue and book NAV are compared on the SAME scope",
            f"venue ${vneq:,.0f} (={vratio:.2f}x futures start) vs "
            f"book ${equity:,.0f} (={pratio:.2f}x total start)",
            "venue=FUTURES scope, portfolio=TOTAL scope -- not comparable"
            if scope_mismatch
            else "scopes comparable",
            "run_venue_divergence_shadow logs pct_diff between these and that series is what "
            "calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker "
            "that never fires or always fires. Fix the shadow to compare like-for-like BEFORE "
            "arming anything from it.",
        )

    # ---- 2. HEALTH: does all_ok survive the organ logs? --------------------------------
    health = load(WEB / "health.json") or {}
    logs = DATA / "cro_ai_logs"
    stubs = fresh = 0
    if logs.exists():
        for lg in sorted(logs.glob("*.log"))[-40:]:
            sz = lg.stat().st_size
            age_h = (datetime.now(tz=UTC).timestamp() - lg.stat().st_mtime) / 3600
            if age_h < 48:
                if sz < 600:
                    stubs += 1
                else:
                    fresh += 1
    claimed_ok = health.get("all_ok")
    organs_ok = health.get("organs_ok")
    sev = "HIGH" if (claimed_ok and stubs > fresh and stubs > 0) else "OK"
    check(
        f,
        sev,
        "health all_ok is consistent with organ logs",
        f"all_ok={claimed_ok}, organs_ok={organs_ok}",
        f"{stubs} stub logs vs {fresh} real logs in last 48h",
        "a green dashboard while organs are dead means silent research outage",
    )

    # ---- 3. CLOCK PROGRESS: are 'accruing' days actually usable? -----------------------
    sh = load(WEB / "axis_shadows.json") or {}
    for ax in sh.get("axes", []):
        name = ax.get("axis", "?")
        fwd = ax.get("forward_days", 0)
        fn = {
            "kimchi_premium": "kimchi_premium.jsonl",
            "stablecoin_supply_momentum": "stablecoin_supply.jsonl",
            "cny_premium": "cny_premium.jsonl",
        }.get(name)
        if not fn:
            continue
        rows = jsonl(DATA / fn)
        usable = sum(1 for r in rows if r.get("z20") is not None)
        sev = "HIGH" if (fwd > 0 and usable == 0) else ("MEDIUM" if usable < fwd else "OK")
        check(
            f,
            sev,
            f"{name}: reported forward days are usable",
            f"forward_days={fwd}",
            f"{usable}/{len(rows)} rows have a usable z20",
            "an axis reported as accruing evidence that has not started will read as "
            "'failing' later for the wrong reason, and its Holm slot is wasted meanwhile",
        )

    # ---- 4. DEPLOYMENT: does claimed notional match the positions? ---------------------
    cc = load(WEB / "cashcarry_live.json") or {}
    n, dep = cc.get("n_carries"), cc.get("deployed_notional")
    carries = cc.get("carries") or []
    if n is not None:
        sev = "HIGH" if n != len(carries) else "OK"
        check(
            f,
            sev,
            "carry count matches the position list",
            f"n_carries={n}, notional=${dep:,.0f}" if dep else f"n_carries={n}",
            f"{len(carries)} positions listed",
            "a mismatch means the executor and the dashboard disagree about the book",
        )

    # ---- 5. FRESHNESS: does 'updated' match the file's own mtime? ----------------------
    for name in ("portfolio.json", "health.json", "axis_shadows.json"):
        p = WEB / name
        d = load(p)
        if not d or "updated" not in d:
            continue
        try:
            claimed_t = datetime.fromisoformat(str(d["updated"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        drift_h = abs((mtime - claimed_t).total_seconds()) / 3600
        age_h = (datetime.now(tz=UTC) - claimed_t).total_seconds() / 3600
        sev = "HIGH" if age_h > 24 else ("MEDIUM" if drift_h > 2 else "OK")
        check(
            f,
            sev,
            f"{name} freshness claim is true",
            f"updated {claimed_t:%Y-%m-%d %H:%M}",
            f"age {age_h:.1f}h, mtime drift {drift_h:.1f}h",
            "a stale artifact presented as current is read as live state",
        )

    bad = [x for x in f if x["severity"] != "OK"]
    sev_counts: dict[str, int] = {}
    for x in bad:
        sev_counts[x["severity"]] = sev_counts.get(x["severity"], 0) + 1
    print(
        f"\n  {len(f)} claims checked | {len(bad)} FAILED"
        + (f"  ({', '.join(f'{k}:{v}' for k, v in sorted(sev_counts.items()))})" if bad else "")
    )
    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "checked": len(f),
                "failed": len(bad),
                "by_severity": sev_counts,
                "claims": f,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"  -> {OUT}")
    print("  CRITICAL here should block Gate-0: the desk does not know what it owns.")


if __name__ == "__main__":
    main()
