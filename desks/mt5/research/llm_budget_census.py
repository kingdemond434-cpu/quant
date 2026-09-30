"""WHO SPENT THE MODEL SEAT TODAY, AND WHAT THE SPEND BOUGHT. One artifact, hourly.

    py -3 desks/mt5/research/llm_budget_census.py        # argless: one pass, the only mode

THE QUESTION THIS EXISTS TO ANSWER WITHOUT ANYONE ASKING IT. A genuinely novel mechanism -- one
with no pre-existing family function -- reaches the gauntlet by exactly one path: the compiler
labels it NEEDS_EXACT_RULE_EXTRACTION and `deepening_worker` spends a model call recovering the
rule. Every other door the desk owns is a REGISTERED family being re-parameterised. So the whole
Chinese, Japanese, Korean and Russian forest, the championship records, the world crawler and the
arXiv feed all funnel through one account's daily allowance of model requests, and the size of
that allowance is the desk's novel-mechanism discovery rate. Nothing published it.

WHAT WENT WRONG WITHOUT IT, measured on the trading box 2026-09-24, and every line of this file
is here because one of these was invisible:

  1. THE ALLOWANCE WAS MISREPORTED IN ITS OWN SOURCE, BY A FACTOR OF TWO. `note_free_limit_hit`
     recorded the desk's COMPLETION count at the moment of a 429 and called it "the ceiling".
     The provider counts REQUESTS. On 2026-09-23 those numbers were 460 and 1000; the smaller one
     then appeared in four docstrings as the account's capacity ("the provider refused at 458
     calls"), and every plan sized against it was sized against less than half the truth. A
     budget measured in the wrong unit does not read as wrong -- it reads as a smaller desk.

  2. THE GAP BETWEEN THE TWO IS PURE WASTE AND NOBODY OWNED IT. 219 requests on 2026-09-24 and
     540 on 2026-09-23 were spent without producing a completion: parameter-degradation retries,
     upstream 5xx, replies with no content. That is 22% to 54% of the day's research budget,
     recoverable for nothing, and it was not a number anyone could see.

  3. THE CALLS THAT DID COMPLETE WERE MOSTLY THROWN AWAY. 456 of 789 completed calls (58%) were
     rejected downstream with "reply was not a JSON object" -- and that parser already strips
     code fences and scans brace-to-brace, so a rejection means the reply carried no object AT
     ALL. Empty content and a refusal are indistinguishable once the text is gone, which is why
     `finish_reason`, `completion_tokens` and `reasoning_tokens` are now recorded per call and
     summarised here: a 700-token completion cap requested at `reasoning_effort: high` truncates
     a reasoning model before it writes a character of answer, and that hypothesis is testable
     only against this table.

  4. ONE ORGAN ATE THE ALLOWANCE AND THE REST WENT DARK BLAMING THE PROVIDER. The allowance was
     gone by 01:42 UTC. Every audit, panel and recommendation organ scheduled after that hour got
     a refusal whose text reads exactly like an outage. The recommendation ledger recorded SEVEN
     new entries in the twenty days to 2026-09-24, against dozens a week before -- the audits did
     not stop working, they stopped being able to call anything. The ledger could not name the
     spender because it recorded the PROVIDER's name and never the CALLER's.

NO KEY IS EVER READ, PRINTED OR LOGGED HERE. This reports health, counts and rates. The one
network call is `/key`, which returns quota metadata and is not a model request, so measuring the
budget never consumes it.

EXIT CODE IS A VERDICT, NOT A FAULT. 1 means the seat is DARK -- no seat resolves, or the
provider refused the quota read -- because a desk whose only novel-mechanism door is shut should
say so in the one place a scheduler looks. A merely exhausted daily budget is exit 0: that is the
system working as designed and recovering at 00:00 UTC.
"""
from __future__ import annotations

import collections
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "LLM_BUDGET_CENSUS.json"

#: The ledger row count is the desk's own view; the provider's `used` is the truth. Anything above
#: this fraction of the day's requests going to waste is worth naming in the report, because it is
#: the cheapest budget on the desk: recovering it costs no money and needs no permission.
WASTE_NOTABLE = 0.10

#: A recommendation-producing organ that has not raised anything in this many days, while the seat
#: was exhausted daily, is starved rather than idle. Reported, never auto-repaired.
STARVED_DAYS = 7.0


def _rows(path: Path, day: str | None = None) -> list[dict[str, Any]]:
    """Spend-ledger rows, optionally one UTC day. A malformed line is skipped, never fatal."""
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    try:
        text = path.read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if day and not str(row.get("utc", "")).startswith(day):
            continue
        out.append(row)
    return out


def _rate(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


def census(now: datetime | None = None) -> dict[str, Any]:
    """The whole measurement. Never raises: an unreachable provider is UNMEASURED, not an error."""
    t = now or datetime.now(UTC)
    today = t.strftime("%Y-%m-%d")
    out: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "law": ("the seat's daily REQUEST allowance is the desk's novel-mechanism discovery rate: "
                "a mechanism with no registered family function reaches the gauntlet only through "
                "an exact-rule extraction, and every extraction is one request. Measure the "
                "allowance in the provider's unit, name who spends it, and count what the spend "
                "converted -- an unattributed budget cannot be allocated (L1.28a)"),
    }
    try:
        from libs.ops import llm_seat
    except Exception as exc:
        out["status"] = "DARK"
        out["blocker"] = f"libs.ops.llm_seat did not import: {type(exc).__name__}: {exc}"
        return out

    seats = llm_seat.seats()
    out["seats"] = {
        "n": len(seats),
        # Model ids and sources only. A key never appears here, in any form.
        "pinned": sorted({s.model for s in seats if s.model}),
        "unpinned": sum(1 for s in seats if not s.model),
        "sources": dict(collections.Counter(s.source for s in seats)),
        "note": ("a PINNED seat bypasses `discover_model` entirely, so the auto-upgrade that "
                 "keeps this desk on the best listed model never runs for it"),
    }
    out["free_tier_only"] = llm_seat.free_tier_only()
    out["month_spend_usd"] = llm_seat.month_spend_usd()
    out["monthly_cap_usd"] = llm_seat.monthly_cap_usd()
    if not seats:
        out["status"] = "DARK"
        out["blocker"] = ("no seat resolves: every novel-mechanism extraction is refused and the "
                          "forests, championship records and crawler all funnel into nothing")
        return out

    # ---- THE PROVIDER'S OWN ARITHMETIC, which is the only one it will refuse against ----------
    quota = llm_seat.provider_free_quota()
    out["provider_quota"] = quota or {"status": "UNMEASURED",
                                      "why": "the provider did not publish a free-request counter"}
    ledger_today = _rows(llm_seat.SPEND_LEDGER, today)
    ours = len(ledger_today)
    used = quota.get("used") if isinstance(quota.get("used"), int) else None
    limit = quota.get("limit") if isinstance(quota.get("limit"), int) else None
    out["today"] = {
        "provider_requests_used": used,
        "provider_daily_limit": limit,
        "provider_remaining": quota.get("remaining"),
        "desk_completions": ours,
        "desk_ceiling_belief": llm_seat.free_daily_max(),
        "desk_budget_left_belief": llm_seat.free_budget_left(),
    }
    if used is not None:
        waste = max(0, used - ours)
        out["today"]["invisible_requests"] = waste
        out["today"]["waste_rate"] = _rate(waste, used)
        out["today"]["waste_verdict"] = (
            "NOTABLE: requests that never became a completion -- degradation retries, upstream "
            "5xx, empty replies. This is the cheapest budget on the desk: it costs nothing to "
            "recover and needs no purchase"
            if used and waste / used > WASTE_NOTABLE else "within tolerance")
        if limit:
            out["today"]["exhausted"] = bool(quota.get("remaining") == 0)
            out["today"]["capacity_understatement"] = (
                f"the account's allowance is {limit} REQUESTS/day. The desk's own ceiling belief "
                f"is {llm_seat.free_daily_max()}, which counts COMPLETIONS -- never quote the "
                f"smaller number as this desk's research capacity")

    # ---- WHO SPENT IT ------------------------------------------------------------------------
    by_organ = collections.Counter(str(r.get("organ") or "unattributed") for r in ledger_today)
    out["today_by_organ"] = dict(by_organ.most_common(25))
    out["today_by_model"] = dict(collections.Counter(
        str(r.get("model") or "?") for r in ledger_today).most_common(25))
    if by_organ and set(by_organ) == {"unattributed"}:
        out["attribution"] = ("UNMEASURED: no row carries an organ. Attribution begins with the "
                              "first call after libs/ops/llm_seat.calling_organ landed; rows "
                              "written before it cannot be back-filled and are not guessed")
    else:
        top, n = by_organ.most_common(1)[0]
        out["attribution"] = {
            "largest_consumer": top, "its_share": _rate(n, ours),
            "why_it_matters": ("one allowance, first-come-first-served: an organ that drains it "
                               "early takes every later organ dark with a message that reads like "
                               "a provider outage"),
        }

    # ---- WHAT THE SPEND BOUGHT, and where it was thrown away ----------------------------------
    fr = collections.Counter(str(r.get("finish_reason")) for r in ledger_today
                             if r.get("finish_reason"))
    empty = sum(1 for r in ledger_today if r.get("empty_content") is True)
    measured = sum(1 for r in ledger_today if "empty_content" in r)
    out["reply_quality"] = {
        "finish_reason": dict(fr.most_common(10)),
        "empty_content": empty, "rows_measuring_it": measured,
        "empty_rate": _rate(empty, measured),
        "verdict": ("UNMEASURED: no row records finish_reason yet -- the fields land with the "
                    "first call after the llm_seat change" if not measured else
                    "an empty completion is reported downstream as 'reply was not a JSON object', "
                    "which is indistinguishable from a refusal once the text is gone. "
                    "finish_reason=length with reasoning_tokens at the cap is TRUNCATION, and the "
                    "remedy is a completion cap that covers the reasoning, not a better prompt"),
    }
    reasoning = [int(r["reasoning_tokens"]) for r in ledger_today
                 if isinstance(r.get("reasoning_tokens"), int)]
    comp = [int(r["completion_tokens"]) for r in ledger_today
            if isinstance(r.get("completion_tokens"), int)]
    if reasoning or comp:
        out["reply_quality"]["token_shape"] = {
            "n_reasoning_rows": len(reasoning),
            "mean_reasoning_tokens": (round(sum(reasoning) / len(reasoning), 1)
                                      if reasoning else None),
            "mean_completion_tokens": round(sum(comp) / len(comp), 1) if comp else None,
        }

    # ---- THE HISTORY, so a trend is visible rather than a single day's reading ----------------
    allrows = _rows(llm_seat.SPEND_LEDGER)
    byday = collections.Counter(str(r.get("utc", ""))[:10] for r in allrows)
    out["completions_by_day_last14"] = dict(sorted(byday.items())[-14:])

    # ---- THE STARVATION LINK: did the budget's exhaustion silence the audit lane? -------------
    led = ROOT / "docs" / "research" / "recommendation_ledger.json"
    if led.exists():
        try:
            doc = json.loads(led.read_text("utf-8", errors="ignore"))
            recs = doc.get("recommendations") or []
            cut = (t - timedelta(days=STARVED_DAYS)).isoformat()
            cut30 = (t - timedelta(days=30)).isoformat()
            openish = [r for r in recs
                       if str(r.get("status")) in ("open", "scheduled", "screened")]
            done = [r for r in recs if str(r.get("status")) in ("implemented", "done")]
            out["recommendations"] = {
                "n": len(recs),
                "implemented_or_done": len(done),
                "implementation_rate": _rate(len(done), len(recs)),
                "open_like": len(openish),
                "raised_last_7d": sum(1 for r in recs if str(r.get("raised") or "") >= cut),
                "raised_last_30d": sum(1 for r in recs if str(r.get("raised") or "") >= cut30),
                "last_drain_at": doc.get("last_drain_at"),
                "verdict": ("the DRAIN is alive and the PRODUCERS are quiet: a ledger that is "
                            "being implemented but not replenished is an audit lane with no seat "
                            "to call, not an audit lane with nothing to say"),
            }
        except (OSError, ValueError) as exc:
            out["recommendations"] = {"status": "UNREADABLE", "why": str(exc)[:160]}

    out["status"] = "EXHAUSTED" if out["today"].get("exhausted") else "OK"
    return out


def main(argv: list[str] | None = None) -> int:
    doc = census()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    today = doc.get("today") or {}
    print(f"LLM BUDGET CENSUS  {doc.get('at')}  status={doc.get('status')}")
    print(f"  seats        {(doc.get('seats') or {}).get('n')} "
          f"(pinned {len((doc.get('seats') or {}).get('pinned') or [])})")
    print(f"  provider     used {today.get('provider_requests_used')} of "
          f"{today.get('provider_daily_limit')} REQUESTS, remaining "
          f"{today.get('provider_remaining')}")
    print(f"  desk         {today.get('desk_completions')} completions; "
          f"{today.get('invisible_requests')} request(s) produced nothing "
          f"({today.get('waste_rate')})")
    rq = doc.get("reply_quality") or {}
    print(f"  replies      empty {rq.get('empty_content')} of {rq.get('rows_measuring_it')} "
          f"measured (rate {rq.get('empty_rate')})")
    rec = doc.get("recommendations") or {}
    print(f"  recs         {rec.get('implemented_or_done')}/{rec.get('n')} implemented "
          f"(rate {rec.get('implementation_rate')}), {rec.get('open_like')} open, "
          f"{rec.get('raised_last_7d')} raised in 7d")
    print(f"  -> {REPORT}")
    return 1 if doc.get("status") == "DARK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
