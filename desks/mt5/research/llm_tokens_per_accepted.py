"""TOKENS PER ACCEPTED ROW, PER BOX LLM JOB. One artifact, hourly, read by the hourly pass.

    py -3 desks/mt5/research/llm_tokens_per_accepted.py        # argless: one pass

WHAT IT ANSWERS. The hourly pass carries a standing row, "eliminate token waste in box jobs, no
quality reduction", and it could not be worked because nothing published what each job SPENT
against what it PRODUCED. `llm_budget_census` names who spent the seat; this names what the spend
bought, job by job, in one unit the pass can rank: model tokens per row a downstream judge
accepted.

ONE WRITER PER FILE (agreed with the LLM brain thread, 2026-11-11). The token side is read from
`libs/ops/llm_seat.SPEND_LEDGER`, whose only writer is `llm_seat._record_spend` (one row per
completed call, with organ, model and the provider's token split). Nothing here appends to it.
The accepted side is read from the two places a job's output is accepted today:

  * `data/hypotheses/miner_candidates.json["per_source"]` -- executable candidates the compiler
    built from each source's donated rows (the compiler's own window, WINDOW_DAYS);
  * `data/hypotheses/deepening_worked.jsonl` -- `n_candidates` per exact-rule extraction, the
    `deepening_worker` organ's acceptance.

A job is matched to its sources by name (the organ is the entry script's stem, the source is the
seat directory or donor name): equal, `organ:` prefixed, one a prefix of the other, or an alias in
ALIASES. A job with spend and no matching source is UNMAPPED and its ratio is UNMEASURED -- never
zero, never infinite (L1.28a). A mapped job with spend and nothing accepted is NO_ACCEPTED: every
token it spent in the window is waste by this measure, which is the line the pass should read
first.

WHAT THE REPORT CANNOT SEE, AND SAYS SO. A caller that posts to a chat-completions endpoint itself
writes no ledger row, so its spend is invisible here. `unledgered_callers` lists every such file
on this tree by a static scan, so a low total is never mistaken for a thrifty desk.

NO KEY IS READ OR PRINTED. NO NETWORK CALL IS MADE. Exit 0 always: a report, not a gate.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "LLM_TOKENS_PER_ACCEPTED.json"
CANDIDATES = BASE / "data" / "hypotheses" / "miner_candidates.json"
DEEPENED = BASE / "data" / "hypotheses" / "deepening_worked.jsonl"

#: The compiler counts a source's candidates over its own window; tokens are summed over the SAME
#: window so the ratio compares like with like.
WINDOW_DAYS = 7

#: A compiled docket older than this cannot speak for the current window: acceptance UNMEASURED.
STALE_DOCKET_DAYS = 2.0

#: Organ (entry script stem) -> source names it donates under, where the names differ.
ALIASES: dict[str, tuple[str, ...]] = {
    "kimi_hunter": ("kimi", "kimi_k3_deep_forest"),
    "deepseek_cycle": ("deepseek",),
    "run_deepseek_factory": ("deepseek",),
    "deep_forest_miner": ("deep_forest", "kimi_k3_deep_forest"),
}

#: A call whose spend bought no usable text: empty content, or cut off at the completion cap.
WASTE_FINISH = ("length",)

_POST = re.compile(r"urlopen|requests\.post|httpx\.|\.post\(")
_SEAT = re.compile(r"llm_seat|openrouter_free|free_chain|llm_route")
_SCAN_DIRS = ("scripts", "libs", "desks/mt5/research", "desks/mt5/scripts", "desks/mt5/mt5desk")


def _parse_utc(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _ledger_path() -> Path:
    try:
        from libs.ops import llm_seat
        return Path(llm_seat.SPEND_LEDGER)
    except Exception:
        return ROOT / "data" / "llm_spend.jsonl"


def _jsonl(path: Path, since: datetime, stamp: str) -> tuple[list[dict[str, Any]], int]:
    """Rows stamped at or after `since`, and the count of lines that could not be read."""
    rows: list[dict[str, Any]] = []
    bad = 0
    try:
        fh = path.open("r", encoding="utf-8", errors="ignore")
    except OSError:
        return rows, bad
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                bad += 1
                continue
            t = _parse_utc(row.get(stamp)) if isinstance(row, dict) else None
            if t is None:
                bad += 1
                continue
            if t >= since:
                rows.append(row)
    return rows, bad


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def spend_by_organ(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        organ = str(r.get("organ") or "unattributed")
        s = out.setdefault(organ, {"calls": 0, "tokens": 0, "prompt_tokens": 0,
                                   "completion_tokens": 0, "reasoning_tokens": 0,
                                   "wasted_calls": 0, "wasted_tokens": 0, "models": {}})
        tok = _int(r.get("tokens"))
        s["calls"] += 1
        s["tokens"] += tok
        for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens"):
            s[k] += _int(r.get(k))
        if r.get("empty_content") is True or str(r.get("finish_reason") or "") in WASTE_FINISH:
            s["wasted_calls"] += 1
            s["wasted_tokens"] += tok
        m = str(r.get("model") or "?")
        s["models"][m] = s["models"].get(m, 0) + 1
    return out


def _per_source(path: Path, now: datetime) -> tuple[dict[str, dict[str, Any]] | None, str]:
    """The compiler's per-source conversion, read without loading the 50k-row docket whole."""
    try:
        text = path.read_text("utf-8", errors="ignore")
    except OSError:
        return None, f"{path.name} is not on this host"
    dec = json.JSONDecoder()

    def _value_after(key: str, last: bool = False) -> Any:
        i = text.rfind(key) if last else text.find(key)
        if i < 0:
            raise ValueError(key)
        k = text.index(":", i) + 1
        while k < len(text) and text[k].isspace():
            k += 1
        return dec.raw_decode(text, k)[0]

    try:
        at = _parse_utc(_value_after('"compiled_at"'))
    except ValueError:
        at = None
    if at is None:
        return None, f"{path.name} carries no readable compiled_at"
    if (now - at).total_seconds() > STALE_DOCKET_DAYS * 86400:
        return None, f"{path.name} compiled {at.isoformat()} is stale for this window"
    try:
        doc = _value_after('"per_source"', last=True)
    except ValueError:
        return None, f"{path.name} per_source is absent or unreadable"
    if not isinstance(doc, dict):
        return None, f"{path.name} per_source is not a map"
    return {str(s): v for s, v in doc.items() if isinstance(v, dict)}, at.isoformat()


def _matches(organ: str, source: str) -> bool:
    o, s = organ.lower(), source.lower()
    if s in ALIASES.get(o, ()):
        return True
    return (s == o or s.startswith(o + ":") or o.startswith(s) or s.startswith(o))


def unledgered_callers(root: Path = ROOT) -> list[str]:
    """Files that post to a chat-completions endpoint themselves, so their spend has no row."""
    out: list[str] = []
    for d in _SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.py")):
            rel = f.relative_to(root).as_posix()
            if "/tests/" in rel or "/_retired/" in rel or rel.endswith("llm_seat.py"):
                continue
            try:
                src = f.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            if "chat/completions" in src and _POST.search(src) and not _SEAT.search(src):
                out.append(rel)
    return out


def measure(now: datetime | None = None, *, ledger: Path | None = None,
            candidates: Path | None = None, deepened: Path | None = None,
            root: Path = ROOT) -> dict[str, Any]:
    t = now or datetime.now(UTC)
    since = t - timedelta(days=WINDOW_DAYS)
    lp = ledger or _ledger_path()
    spend_rows, bad_spend = _jsonl(lp, since, "utc")
    spend = spend_by_organ(spend_rows)
    per_source, docket_note = _per_source(candidates or CANDIDATES, t)
    deep_rows, _ = _jsonl(deepened or DEEPENED, since, "at")
    deep_accepted = sum(_int(r.get("n_candidates")) for r in deep_rows)

    jobs: dict[str, dict[str, Any]] = {}
    for organ, s in sorted(spend.items(), key=lambda kv: -kv[1]["tokens"]):
        row: dict[str, Any] = {**s}
        if organ == "deepening_worker":
            row["accepted_from"] = [DEEPENED.name]
            accepted: int | None = deep_accepted
        elif per_source is None:
            row["accepted_from"] = []
            accepted = None
        else:
            srcs = [src for src in per_source if _matches(organ, src)]
            row["accepted_from"] = srcs
            accepted = (sum(_int(per_source[x].get("candidates")) for x in srcs)
                        if srcs else None)
        row["accepted"] = accepted
        if accepted is None:
            row["status"] = "UNMAPPED" if per_source is not None else "UNMEASURED"
            row["tokens_per_accepted"] = None
        elif accepted == 0:
            row["status"] = "NO_ACCEPTED" if s["tokens"] else "IDLE"
            row["tokens_per_accepted"] = None
        else:
            row["status"] = "MEASURED"
            row["tokens_per_accepted"] = round(s["tokens"] / accepted, 1)
        row["waste_share"] = (round(s["wasted_tokens"] / s["tokens"], 4) if s["tokens"]
                              else None)
        jobs[organ] = row

    total = sum(s["tokens"] for s in spend.values())
    acc = sum(j["accepted"] for j in jobs.values() if isinstance(j["accepted"], int))
    no_acc = sorted((o for o, j in jobs.items() if j["status"] == "NO_ACCEPTED"),
                    key=lambda o: -jobs[o]["tokens"])
    return {
        "generated_utc": t.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "status": "MEASURED" if spend_rows else "UNMEASURED",
        "why": (None if spend_rows else
                f"no spend rows in the last {WINDOW_DAYS} days at {lp.name} on this host"),
        "definition": ("tokens = provider-reported total_tokens of every completed seat call by "
                       "the organ in the window; accepted = executable candidates the compiler "
                       "built from the organ's sources (deepening_worker: n_candidates of its "
                       "extractions); waste = tokens on calls with empty content or "
                       "finish_reason=length"),
        "sources": {"spend_ledger": lp.name, "unreadable_spend_lines": bad_spend,
                    "docket": docket_note, "deepened_rows": len(deep_rows)},
        "totals": {"calls": sum(s["calls"] for s in spend.values()), "tokens": total,
                   "wasted_tokens": sum(s["wasted_tokens"] for s in spend.values()),
                   "accepted_mapped": acc,
                   "tokens_on_no_accepted_jobs": sum(jobs[o]["tokens"] for o in no_acc)},
        "no_accepted_jobs": no_acc,
        "jobs": jobs,
        "unledgered_callers": unledgered_callers(root),
        "unledgered_note": ("these files post to a chat-completions endpoint without the seat, "
                            "so their tokens are absent from every number above"),
    }


def main(argv: list[str] | None = None) -> int:
    doc = measure()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_name(f"{REPORT.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, REPORT)
    tot = doc["totals"]
    print(f"llm_tokens_per_accepted: {doc['status']} {tot['tokens']} tokens / {tot['calls']} "
          f"calls in {WINDOW_DAYS}d; {len(doc['no_accepted_jobs'])} job(s) accepted nothing; "
          f"{len(doc['unledgered_callers'])} unledgered caller(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
