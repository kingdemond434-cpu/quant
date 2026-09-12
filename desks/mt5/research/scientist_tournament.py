"""F7 -- TWELVE SCIENTISTS, GENUINELY INDEPENDENT, AND THE DISAGREEMENT IS THE PRODUCT.

THE PRINCIPAL, 2026-09-12, ranking this seventh of the remaining blueprint:

    Independent competing agents -- generator, causal critic, statistician, leakage hunter,
    data/PIT critic, execution critic, portfolio critic, novelty critic, alternative-explanation,
    red team, reviewer, meta-reviewer -- with genuinely independent context and priors, and
    DISAGREEMENT PRESERVED rather than averaged away.

THE GAP, AS THE LEDGER STATES IT: contract-level separation between Evidence, Mechanism,
Hypothesis and Falsifier agents exists and is genuinely useful; the TOURNAMENT does not. The
difference is not the number of roles. It is these three things, and each is easy to fake:

    INDEPENDENT CONTEXT. A panel where every role reads the same brief is one reader with twelve
    voices. Here each role is handed ONLY the evidence its question needs, and is DENIED the rest
    on purpose: the statistician never sees the mechanism story, so it cannot be talked into a
    number; the causal critic never sees the p-value, so it cannot rationalise backwards from
    significance; the leakage hunter sees the construction and not the performance, because
    knowing a strategy made money is the strongest possible prior against finding its leak.

    INDEPENDENT PRIORS. Roles are assigned to DIFFERENT model families, round-robin across what
    the free tier actually serves. Two seats agreeing because they are the same model is one
    opinion counted twice, and this desk has written that down before. The model that answered is
    recorded with every verdict, so a reader can see when an agreement is really a duplication.

    DISAGREEMENT PRESERVED. No score is averaged. The reviewer is FORBIDDEN to resolve a dissent
    and required to list it; the meta-reviewer's only job is to audit the reviewer for dissents
    that went missing between round two and round three. A panel that returns "7.2/10" has
    destroyed the only thing twelve independent readers produce that one reader cannot.

WHY DISAGREEMENT IS THE PRODUCT AND NOT A PROBLEM. Consensus among critics is nearly free to
manufacture and carries almost no information -- it is what a shared brief and a shared model
produce by construction. Two independent readers of different evidence reaching OPPOSITE verdicts
have located the exact place where this desk's belief is not supported, which is the only place a
new experiment is worth running. So every dissent becomes a falsifier node on the research tree.

THE STANDING ORDER IS ENFORCED AT THE DOOR, not argued with. Every recommendation the tournament
produces is classified by `audit_intake.classify` before it is recorded: anything touching the 20%
heat floor, and anything proposing a smaller book, is REFUSED on sight and the refusal is kept on
the record. A critic is free to be timid; the desk is not free to act on it.

FREE TIER ONLY, AND IT SKIPS RATHER THAN GOES DARK. The budget is checked before every call and a
reserve is held back for the rest of the desk, because an account rate-limited into darkness takes
every organ with it, not just the one that spent the last request.

    python desks/mt5/research/scientist_tournament.py [--apply] [--subjects N]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
TREE_REPORT = DESK / "reports" / "RESEARCH_TREE.json"
PIT = DESK / "reports" / "PIT_AUDIT.json"
ORTHO = DESK / "reports" / "ORTHOGONALITY.json"
FWD = DESK / "reports" / "FORWARD_CALIBRATION.json"
OUT = DESK / "reports" / "SCIENTIST_TOURNAMENT.json"
DISSENTS = DESK / "data" / "tournament_dissents.jsonl"

#: Requests held back for every other organ on this account. The audit lane, the deepseek cycle
#: and the hypothesis generator all draw on the same daily free budget, and a tournament that
#: spends the last request takes the whole desk dark until 00:00 UTC.
RESERVE = 60

#: Calls per subject: ten specialists, a reviewer, a meta-reviewer.
CALLS_PER_SUBJECT = 12

MAX_TOKENS = 1400
TEMPERATURE = 0.3


# ==============================================================================================
# THE ROLES, and -- more importantly -- WHAT EACH ONE IS NOT ALLOWED TO SEE.
#
# `sees` names the evidence blocks handed to that role. Everything else is withheld. The denial
# is the mechanism: a critic that has seen the performance cannot un-see it, and a panel whose
# members all read the same brief is one reader with twelve voices.
# ==============================================================================================
ROLES: tuple[dict[str, Any], ...] = (
    {"name": "causal_critic", "sees": ("mechanism",),
     "brief": ("You are a causal critic. You are shown a proposed market MECHANISM and nothing "
               "else -- no performance, no statistics, deliberately. State (1) who the payer is "
               "and why they must transact regardless of price, (2) what would have to be true "
               "of market structure for this to persist, (3) whether the stated mechanism could "
               "produce the claimed DIRECTION at all. If no payer can be named, say so plainly.")},
    {"name": "statistician", "sees": ("numbers",),
     "brief": ("You are a statistician. You are shown NUMBERS and no story, deliberately -- you "
               "cannot be talked into a verdict by a plausible mechanism. Given the sample size, "
               "the trial count and the effect, state whether the evidence survives the multiple "
               "testing that produced it, what the effect would have to be to matter after that, "
               "and what n would settle it.")},
    {"name": "leakage_hunter", "sees": ("construction",),
     "brief": ("You are a leakage hunter. You are shown how the signal is CONSTRUCTED and "
               "deliberately NOT whether it made money -- knowing a strategy was profitable is "
               "the strongest prior against finding its leak. Name every specific way future "
               "information could reach this construction: bar timestamp conventions, fills at "
               "prices unavailable at decision time, parameters chosen on the same data, "
               "survivorship in the symbol list, revised inputs. Be concrete or say none.")},
    {"name": "data_pit_critic", "sees": ("pit",),
     "brief": ("You are a point-in-time critic. You are shown this desk's own PIT audit. Name "
               "which missing time fact most endangers a live decision, and what a wrong answer "
               "would cost. Do not recommend broad rigour; name the field and the path.")},
    {"name": "execution_critic", "sees": ("construction", "costs"),
     "brief": ("You are an execution critic. Given the construction and the cost model, state "
               "whether the edge survives real fills: spread at the hour it trades, slippage on "
               "the order type implied, whether the entry is even reachable, and what fraction "
               "of the claimed edge the round trip consumes.")},
    {"name": "portfolio_critic", "sees": ("portfolio",),
     "brief": ("You are a portfolio critic. Given the book's measured effective breadth and its "
               "hidden tail dependence, state whether ADDING this raises independent bets or "
               "duplicates one the book already holds. The objective is E[log W] with more "
               "independent positive-expectancy bets inside the SAME heat -- never a smaller "
               "book. Do not propose reducing risk.")},
    {"name": "novelty_critic", "sees": ("mechanism", "known_families"),
     "brief": ("You are a novelty critic. Given the mechanism and the families this desk already "
               "trades, state whether this is genuinely a new mechanism or a re-parameterisation "
               "of one already funded. Name the family it collapses into if it does.")},
    {"name": "alternative_explanation", "sees": ("mechanism", "numbers"),
     "brief": ("You propose ALTERNATIVE EXPLANATIONS. For the observed result, give the three "
               "most plausible explanations that are NOT the claimed mechanism -- a cost model "
               "error, a clock or session artefact, a single regime, a symbol-specific quirk, "
               "selection. For each, state the single test that would distinguish it.")},
    {"name": "red_team", "sees": ("mechanism", "construction"),
     "brief": ("You are the red team. Your job is to make this fail. Describe the market "
               "condition under which this loses the most, how quickly it would be recognised, "
               "and what an informed counterparty would do if they knew this desk traded it. Do "
               "not hedge and do not recommend smaller size -- name the failure.")},
    {"name": "forward_critic", "sees": ("forward",),
     "brief": ("You are a forward-evidence critic. You are shown what fraction of PURE NOISE this "
               "desk's forward lane would promote at its own measured dispersion. State what the "
               "forward record can and cannot establish given that rate, and what would have to "
               "change for a forward pass to be informative.")},
)

REVIEWER = {
    "name": "reviewer", "sees": ("verdicts",),
    "brief": ("You are the reviewer. You are shown ten independent verdicts from critics who "
              "each saw DIFFERENT evidence. You are FORBIDDEN to resolve a disagreement and "
              "forbidden to average. Your output has exactly two parts: (1) AGREEMENTS -- what "
              "every critic that spoke to a point said about it; (2) DISSENTS -- every point on "
              "which two critics are inconsistent, stated as 'X says A, Y says B', with neither "
              "adjudicated. A dissent you resolve is a dissent you destroyed.")}

META = {
    "name": "meta_reviewer", "sees": ("verdicts", "review"),
    "brief": ("You are the meta-reviewer and you audit ONE thing: did the reviewer drop a "
              "disagreement? You are shown the ten original verdicts and the review. List every "
              "inconsistency present in the verdicts that the review does not carry forward, and "
              "every place the review reached a conclusion the verdicts do not jointly support. "
              "If the review preserved everything, say so in one line.")}


def _role_seats(seat: Any, n: int) -> list[Any]:
    """One seat per role, on as many DIFFERENT model VENDORS as the free tier actually serves.

    THE CODE HAS TO DO THIS OR THE DOCSTRING IS A LIE. "Independent priors" is the claim that
    makes a twelve-role panel worth more than one reader, and a panel that runs every role on the
    seat's single discovered model is one model answering twelve questions -- which the report
    would then present as twelve independent readings. So the free catalogue is read, grouped by
    VENDOR (the id's first path segment, `nvidia/...` vs `google/...`), and roles are dealt
    round-robin across vendors.

    WHEN ONLY ONE VENDOR IS FREE the rotation is a no-op and the report says so in
    `independence.priors_caveat`. That is the honest outcome, not a failure: the fix is more free
    vendors, never a claim of independence the catalogue does not support.
    """
    import dataclasses
    import re

    from libs.ops import llm_seat
    try:
        body, err = llm_seat._get(f"{seat.base_url}/models", seat.key, timeout=20.0)
    except Exception:
        body, err = {}, "model list unreachable"
    ids: list[str] = []
    if not err:
        ids = [str(m.get("id") or "") for m in (body.get("data") or [])]
        ids = [i for i in ids if i.endswith((":free", "-free"))]
    by_vendor: dict[str, list[str]] = {}
    for i in ids:
        by_vendor.setdefault(i.split("/", 1)[0], []).append(i)
    # One representative per vendor, chosen by DECLARED PARAMETER COUNT rather than by name
    # length. The first cut used the longest id and seated `nemotron-3-nano-omni-30b` over the
    # same vendor's 550b ultra, and `north-mini-code` -- a code model -- as the causal critic.
    # Most free ids state their size ("...-550b-a55b:free"); where one does not it sorts last,
    # because an undeclared size is not evidence of a large model.
    def _size(model_id: str) -> tuple[int, int]:
        hits = [int(m) for m in re.findall(r"(\d+)b(?:[-:]|$)", model_id.lower())]
        return (max(hits) if hits else 0, len(model_id))

    reps = [max(v, key=_size) for _k, v in sorted(by_vendor.items())]
    if not reps:
        return [seat] * n
    out = []
    for k in range(n):
        out.append(dataclasses.replace(seat, model=reps[k % len(reps)]))
    return out


# ------------------------------------------------------------------------- evidence assembly

def _load(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _subjects(limit: int) -> list[dict[str, Any]]:
    """What the tournament judges: the desk's own certificates, newest first."""
    doc = _load(SURVIVORS)
    rows: list[dict[str, Any]] = []
    for key, row in (doc.get("survivors") or {}).items():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        rows.append({
            "key": key, "symbol": spec.get("symbol") or row.get("sym"),
            "family": spec.get("family"), "params": spec.get("params"),
            "selector": spec.get("selector"),
            "gated_at": row.get("gated_at"), "days": row.get("days"),
            "gates": row.get("gates"), "hunt": row.get("hunt"),
        })
    rows.sort(key=lambda r: str(r.get("gated_at") or ""), reverse=True)
    return rows[:limit]


def _evidence(subject: dict[str, Any]) -> dict[str, str]:
    """The evidence BLOCKS. Each role receives only the ones its `sees` names."""
    pit, ortho, fwd = _load(PIT), _load(ORTHO), _load(FWD)
    fams = sorted({str(r.get("family")) for r in _subjects(200) if r.get("family")})
    gates = subject.get("gates")
    return {
        "mechanism": (
            f"Family: {subject.get('family')}\nInstrument: {subject.get('symbol')}\n"
            f"Hunt that produced it: {subject.get('hunt')}\n"
            f"Selector: {subject.get('selector')}\n"
            f"This is an MT5/Fusion instrument traded on hourly bars."),
        "numbers": (
            f"Forward days observed: {subject.get('days')}\n"
            f"Gate verdicts: {json.dumps(gates)[:900]}\n"
            f"This desk's docket has judged on the order of 21,000 cells and holds 61 "
            f"certificates, so the family-wise trial count behind any single pass is large."),
        "construction": (
            f"Family: {subject.get('family')}\nParameters: {json.dumps(subject.get('params'))}\n"
            f"Signals are generated from CLOSED hourly bars; entry fills at the next bar's open "
            f"unless a resting trigger is specified; exits are a stop and a target in ATR units "
            f"with a time-to-live in bars."),
        "costs": (
            "Costs are modelled per symbol from the broker's own contract terms. The desk's own "
            "cost audit reports that spread is treated as ONE scalar per symbol rather than a "
            "symbol x hour surface, and that overnight financing is not charged at all."),
        "pit": json.dumps({k: pit.get(k) for k in
                           ("n_paths", "n_certified", "coverage_pct",
                            "money_path_uncertified", "naive_timestamps")})[:1200],
        "portfolio": json.dumps({k: ortho.get(k) for k in
                                 ("n_symbols", "mean_abs_pearson", "n_eff_linear",
                                  "n_eff_tail", "hidden_dependence")})[:1200],
        "forward": json.dumps({k: fwd.get(k) for k in ("rule", "lane", "null", "verdict")})[:1200],
        "known_families": ", ".join(fams)[:900],
    }


def _prompt(role: dict[str, Any], subject: dict[str, Any], ev: dict[str, str],
            extra: dict[str, str] | None = None) -> str:
    blocks = []
    for k in role["sees"]:
        v = (extra or {}).get(k) or ev.get(k)
        if v:
            blocks.append(f"=== {k.upper()} ===\n{v}")
    withheld = sorted(set(ev) - set(role["sees"]))
    return (
        f"{role['brief']}\n\n"
        + "\n\n".join(blocks)
        + (f"\n\n=== WITHHELD FROM YOU ON PURPOSE ===\n{', '.join(withheld)}\n"
           f"Do not speculate about them and do not ask for them. Your verdict is worth exactly "
           f"what it is worth on the evidence above; say 'cannot judge from what I was given' "
           f"where that is the honest answer.\n" if withheld else "")
        + "\n=== OUTPUT ===\nAt most 200 words. End with a final line of exactly:\n"
          "VERDICT: SUPPORTS | UNDERMINES | CANNOT_JUDGE")


def _verdict_of(text: str) -> str:
    """The final verdict line, and a stated fallback when the model did not emit one.

    Two of ten roles came back UNPARSED on the first run -- the model wrote its verdict inside a
    sentence rather than on the required last line. Treating that as no-verdict throws away a
    reading the panel paid a request for, so the tail is scanned as a fallback. The fallback is
    NOT silent: it returns the token it found, and a verdict found nowhere at all stays UNPARSED
    rather than defaulting to anything.
    """
    keys = ("CANNOT_JUDGE", "UNDERMINES", "SUPPORTS")
    for ln in reversed(text.strip().splitlines()):
        u = ln.strip().upper()
        if u.startswith("VERDICT:"):
            v = u.split(":", 1)[1].strip()
            for k in keys:
                if k in v:
                    return k
    tail = text.strip().upper()[-400:]
    hits = [(tail.rfind(k), k) for k in keys if k in tail]
    if hits:
        return max(hits)[1]
    return "UNPARSED"


# --------------------------------------------------------------------------------- the run

def run(n_subjects: int) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        from libs.ops import llm_seat
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"llm_seat unavailable ({exc})"}
    try:
        from research.audit_intake import classify
    except ImportError:
        classify = None  # type: ignore[assignment]

    seat = llm_seat.primary_seat()
    if seat is None:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "no seat: this box holds no OpenRouter key, so no scientist can be seated"}

    budget = llm_seat.free_budget_left() - RESERVE
    affordable = max(0, budget // CALLS_PER_SUBJECT)
    n = min(n_subjects, affordable)
    if n <= 0:
        return {"at": now.isoformat(timespec="seconds"), "status": "SKIPPED",
                "free_budget_left": llm_seat.free_budget_left(), "reserve": RESERVE,
                "why": (f"{llm_seat.free_budget_left()} free request(s) left today against a "
                        f"{RESERVE}-request reserve for the rest of the desk and "
                        f"{CALLS_PER_SUBJECT} calls per subject. A SKIP, not a failure -- the "
                        f"budget resets at 00:00 UTC.")}

    role_seats = _role_seats(seat, len(ROLES))
    vendors = sorted({str(getattr(x, "model", "")).split("/", 1)[0] for x in role_seats
                      if getattr(x, "model", "")})

    subjects = _subjects(n)
    if not subjects:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "the survivor registry holds no certificate to put in front of a panel"}

    results: list[dict[str, Any]] = []
    dissent_rows: list[dict[str, Any]] = []
    calls = 0
    for subj in subjects:
        ev = _evidence(subj)
        verdicts: list[dict[str, Any]] = []
        for ri, role in enumerate(ROLES):
            # STOP AT THE CEILING, DO NOT GRIND AGAINST IT. The first run past the provider's
            # real daily limit reported ten identical "budget exhausted" rows, which reads like
            # ten failed critics rather than one exhausted account -- and a panel with ten errors
            # and no verdicts must never be summarised as "no critic contradicted another".
            if llm_seat.free_budget_left() <= 0:
                verdicts.append({"role": role["name"], "status": "SKIPPED",
                                 "why": ("the provider's daily free allowance was reached before "
                                         "this role was seated; the run stops rather than "
                                         "spending its cadence on refusals"),
                                 "saw": list(role["sees"])})
                continue
            rseat = role_seats[ri]
            text, err = llm_seat.chat(_prompt(role, subj, ev), seat=rseat,
                                      max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
            calls += 1
            model = getattr(rseat, "model", "") or "unknown"
            if err:
                verdicts.append({"role": role["name"], "status": "ERROR", "why": err[:300],
                                 "saw": list(role["sees"])})
                continue
            v = {"role": role["name"], "status": "OK", "model": model,
                 "saw": list(role["sees"]), "verdict": _verdict_of(text),
                 "text": text.strip()[:2400]}
            # THE STANDING ORDER AT THE DOOR. A critic may be timid; the desk may not act on it.
            if classify is not None:
                v["intake"] = classify(text)
            verdicts.append(v)

        spoke = [v for v in verdicts if v.get("status") == "OK"]
        if not spoke:
            results.append({
                "subject": subj, "verdicts": verdicts,
                "tally": {"supports": 0, "undermines": 0, "cannot_judge": 0,
                          "errors": len(verdicts)},
                "dissent_pairs": [], "n_dissent_pairs": 0,
                "review": {"status": "SKIPPED",
                           "why": "no critic answered, so there is nothing to review"},
                "meta_review": {"status": "SKIPPED", "why": "no review to audit"},
                "refused_by_standing_order": [],
                "status": "NO_PANEL",
            })
            continue
        review_txt, rerr = llm_seat.chat(
            _prompt(REVIEWER, subj, ev, extra={"verdicts": json.dumps(
                [{"role": v["role"], "saw": v["saw"], "verdict": v.get("verdict"),
                  "text": v.get("text")} for v in spoke], indent=1)[:9000]}),
            seat=seat, max_tokens=MAX_TOKENS * 2, temperature=TEMPERATURE)
        calls += 1
        meta_txt, merr = llm_seat.chat(
            _prompt(META, subj, ev, extra={
                "verdicts": json.dumps([{"role": v["role"], "verdict": v.get("verdict"),
                                         "text": v.get("text")} for v in spoke])[:7000],
                "review": review_txt[:4000]}),
            seat=seat, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
        calls += 1

        # DISAGREEMENT, COUNTED MECHANICALLY AS WELL AS READ. The reviewer's prose dissents are
        # its own; this is the arithmetic one, which cannot be talked out of existing: two roles
        # that saw DIFFERENT evidence and reached OPPOSITE verdicts.
        sup = [v["role"] for v in spoke if v.get("verdict") == "SUPPORTS"]
        und = [v["role"] for v in spoke if v.get("verdict") == "UNDERMINES"]
        pairs = [{"supports": a, "undermines": b} for a in sup for b in und]
        for p in pairs:
            dissent_rows.append({"at": now.isoformat(timespec="seconds"),
                                 "subject": subj["key"], **p})

        refused = [v for v in verdicts
                   if str((v.get("intake") or {}).get("verdict", "")).startswith("REFUSED")]
        results.append({
            "subject": subj,
            "verdicts": verdicts,
            "tally": {"supports": len(sup), "undermines": len(und),
                      "cannot_judge": len([v for v in spoke
                                           if v.get("verdict") == "CANNOT_JUDGE"]),
                      "errors": len(verdicts) - len(spoke)},
            "dissent_pairs": pairs,
            "n_dissent_pairs": len(pairs),
            "review": {"status": "ERROR" if rerr else "OK",
                       "text": (rerr or review_txt)[:4000]},
            "meta_review": {"status": "ERROR" if merr else "OK",
                            "text": (merr or meta_txt)[:3000]},
            "refused_by_standing_order": [
                {"role": v["role"], "verdict": v["intake"]["verdict"],
                 "matched": v["intake"].get("matched")} for v in refused],
        })

    total_dissent = sum(r["n_dissent_pairs"] for r in results)
    n_seated = sum(1 for r in results if r.get("status") != "NO_PANEL")
    n_spoke = sum(len([v for v in r["verdicts"] if v.get("status") == "OK"]) for r in results)
    return {
        "at": now.isoformat(timespec="seconds"),
        # A RUN WHERE NOBODY ANSWERED IS NOT AN OK RUN. Reporting OK with ten error rows is the
        # green-run lie this desk has a fence against.
        "status": "OK" if n_spoke else "SKIPPED",
        "n_critics_answered": n_spoke,
        "n_subjects_with_a_panel": n_seated,
        "n_subjects": len(results), "calls_made": calls,
        "free_budget_left_after": llm_seat.free_budget_left(),
        "roles": [r["name"] for r in ROLES] + [REVIEWER["name"], META["name"]],
        "independence": {
            "context": {r["name"]: list(r["sees"]) for r in ROLES},
            "why": ("each role is handed ONLY the evidence its question needs and is DENIED the "
                    "rest: the statistician never sees the mechanism story, the causal critic "
                    "never sees the p-value, and the leakage hunter never learns whether it made "
                    "money -- because knowing a strategy was profitable is the strongest prior "
                    "against finding its leak."),
            "vendors_seated": vendors,
            "n_vendors": len(vendors),
            "priors_caveat": (
                f"roles were dealt round-robin across {len(vendors)} free VENDOR(s): "
                f"{', '.join(vendors) or 'none -- the catalogue was unreadable'}. "
                + ("Agreement between roles here is NOT independent corroboration and must not "
                   "be read as such: it is ONE model answering twelve questions. The fix is more "
                   "free vendors, never a claim the catalogue does not support."
                   if len(vendors) <= 1 else
                   "Every verdict records the model that produced it, so a reader can check "
                   "whether an agreement is corroboration or duplication.")),
        },
        "results": results,
        "n_dissent_pairs": total_dissent,
        "headline": (
            f"NO PANEL SAT. {n_spoke} critic(s) answered across {len(results)} subject(s) -- the "
            f"provider's daily free allowance was already spent. This is a SKIP and says nothing "
            f"whatever about the subjects; the budget resets at 00:00 UTC."
            if not n_spoke else
            f"{total_dissent} dissent pair(s) across {n_seated} seated panel(s) -- each a place "
            f"where two critics reading DIFFERENT evidence reached opposite verdicts, which is "
            f"the only place a new experiment is worth running."
            if total_dissent else
            f"{n_spoke} critic(s) answered and none contradicted another. Read that carefully: "
            f"consensus among critics is nearly free to manufacture and carries little "
            f"information, especially where the free catalogue seats them on one vendor."),
        "boundary": (
            "NOTHING HERE CERTIFIES, SIZES OR PROMOTES. Verdicts are opinions with an audit "
            "trail. Every recommendation passes audit_intake first: anything touching the 20% "
            "heat floor and anything proposing a smaller book is REFUSED on sight and the "
            "refusal kept on the record. A critic may be timid; the desk may not act on it."),
        "why": (
            "consensus among critics is nearly free to manufacture -- a shared brief and a shared "
            "model produce it by construction -- and carries almost no information. Two "
            "independent readers of different evidence reaching OPPOSITE verdicts have located "
            "the exact place where the desk's belief is unsupported."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report and the dissent ledger")
    ap.add_argument("--subjects", type=int, default=1)
    a = ap.parse_args(argv)
    doc = run(max(1, a.subjects))
    st = doc.get("status")
    if st != "OK":
        print(f"scientist tournament: {st} -- {doc.get('why')}")
        if a.apply:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            print(f"-> {OUT}")
        return 0
    print(f"scientist tournament: OK   {doc['n_subjects']} subject(s), "
          f"{doc['calls_made']} call(s), "
          f"{doc['free_budget_left_after']} free request(s) left")
    for r in doc["results"]:
        s = r["subject"]
        t = r["tally"]
        print(f"  {s.get('symbol')!s:<10} {str(s.get('family'))[:26]:<26} "
              f"supports {t['supports']}  undermines {t['undermines']}  "
              f"cannot_judge {t['cannot_judge']}  errors {t['errors']}")
        for v in r["verdicts"]:
            if v.get("status") == "OK":
                print(f"     {v['role']:<24} {v['verdict']:<13} saw={','.join(v['saw'])}")
            else:
                print(f"     {v['role']:<24} {v.get('status')!s:<7} "
                      f"{str(v.get('why'))[:64]}")
        for d in r["refused_by_standing_order"]:
            print(f"     REFUSED  {d['role']} -- {d['verdict']} ({d.get('matched')})")
        print(f"     {r['n_dissent_pairs']} dissent pair(s)")
    print(f"  {doc['headline']}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    rows = [d for r in doc["results"] for d in
            [{"at": doc["at"], "subject": r["subject"]["key"], **p} for p in r["dissent_pairs"]]]
    if rows:
        DISSENTS.parent.mkdir(parents=True, exist_ok=True)
        with DISSENTS.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, default=str) + "\n")
    print(f"-> {OUT}  (+{len(rows)} dissent row(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
