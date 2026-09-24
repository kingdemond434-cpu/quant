"""THE SEAT. One key resolution and one call path for every external-model organ on this desk.

WHY THIS EXISTS, and it is the highest-leverage thing in this area rather than another organ.
Eleven organs on this desk are dark right now -- run_external_panel, strategic_director,
llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, collector_author, deep_review,
run_micro_audit, refresh_panel_roster, llm_blind_researcher -- and every one of them is dark for
the SAME reason: they each open `data/secrets/llm_panel.json`, that file does not exist, and not
one of them reads an environment variable. `run_discretionary_max` names this as lever 2 of five,
CROSS-FAMILY, and records it as "blocked on the OpenRouter seat"; `strategic_director` describes
itself as "activation-ready by construction" waiting on the same thing.

So the binding constraint was never eleven integrations. It was one credential with no env-var
route into the box. This module is that route: resolve a key from the environment FIRST and the
secrets file second, and every dark organ can light from a single exported variable -- which is
the same mechanism that just unblocked GitHub search, and a mechanism the principal already
operates.

ONE CODE PATH, AND OPENROUTER IS THE RECOMMENDED KEY. `/chat/completions` is OpenAI-COMPATIBLE
across OpenRouter, xAI, DeepSeek, Qwen, Mistral and OpenAI itself, so any of them work. OpenRouter
is preferred for a reason that only shows up over time: a DIRECT vendor key bounds the
auto-upgrade below to that vendor's catalogue, so an OpenAI key would climb gpt-5 -> gpt-6 -> gpt-7
forever and never reach a better model from anyone else. OpenRouter lists the whole landscape, so
the same version parser upgrades across the MARKET. It is also the only single credential that
delivers cross-family (lever 2), and a second seat from the desk's OWN family would agree with it
for reasons that have nothing to do with the market.

THE FLAGSHIP IS DISCOVERED AND UPGRADES ITSELF. A pinned model string is a time bomb: it works
until the provider retires it, and then every organ fails with an error that reads like an outage.
A pinned PREFERENCE LIST is the same bomb with a longer fuse and it is the worse of the two --
the day `gpt-6` ships, a list containing `gpt-5` keeps choosing the older model forever while
every status line still reads healthy. So the version number is PARSED out of whatever the
provider lists and the highest wins, which makes the upgrade automatic and silent in the right
direction. Cheaper variants (mini, nano, turbo, :free) are refused outright rather than ranked
low, because they sort adjacent to the flagship and often carry the SAME version number.

EFFORT IS REQUESTED AT MAXIMUM. Four cycles a day against a $20/month cap means the binding
constraint is the quality of twelve recommendations, never the tokens spent producing them.
Providers that reject the parameter are retried without it, so asking for more thinking can never
cost a cycle.

SPEND IS CAPPED AND MEASURED, because this is wired to a daily cadence and a runaway loop against
a metered API is a real way to lose real money. Every call records its token usage; the month's
spend is checked BEFORE each call against a hard cap. The desk has already been burned by the
opposite design -- run_external_panel discovered credit exhaustion mid-run, after spending the
last of it on a verification panel that verified nothing (0/13 responded, all HTTP 402).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
SECRETS = _ROOT / "data" / "secrets" / "llm_panel.json"
SPEND_LEDGER = _ROOT / "data" / "llm_spend.jsonl"

#: Environment variables consulted, in order. OPENROUTER IS FIRST, and the reason is the auto-
#: upgrade requirement rather than convenience.
#:
#: Version parsing makes the flagship selection automatic, but a DIRECT vendor key bounds that
#: automation to one vendor's catalogue: an OpenAI key upgrades gpt-5 -> gpt-6 -> gpt-7 forever and
#: can never reach a better model from anyone else. OpenRouter lists the whole landscape, so the
#: same parser upgrades across the MARKET rather than within a supplier. Given a standing order to
#: always run the best available model, a single-vendor key quietly caps that at "best available
#: from this vendor" -- which is the "then never" failure with a wider blast radius.
#:
#: It is also the only key that satisfies cross-family (lever 2) from one credential, and the
#: eleven dark organs already point at OpenRouter base URLs -- kimi_hunter cannot run without it.
KEY_ENV_VARS: tuple[tuple[str, str, str], ...] = (
    ("OPENROUTER_API_KEY", "openrouter", "https://openrouter.ai/api/v1"),
    ("OPENAI_API_KEY", "openai", "https://api.openai.com/v1"),
    ("DEEPSEEK_API_KEY", "deepseek", "https://api.deepseek.com/v1"),
    ("XAI_API_KEY", "xai", "https://api.x.ai/v1"),
)

#: Flagship families, as VERSION-EXTRACTING patterns rather than a list of names.
#:
#: WHY NOT A LIST OF NAMES (principal 2026-08-01: "always maximum flagship models, max effort, and
#: upgrade in future automatic if better comes"). A hardcoded preference list is pinned to what was
#: known the day it was written: the day `gpt-6` ships, a list containing `gpt-5` keeps selecting
#: the older model forever, silently, and the desk reads a healthy green seat while running a
#: superseded brain. That is the same failure as a pinned model string, one level up.
#:
#: So the version is PARSED and the HIGHEST wins. `gpt-6` outranks `gpt-5` the moment the provider
#: lists it, with no code change and no release note to notice. Families are ordered only to break
#: ties between equal version numbers.
_FLAGSHIP_PATTERNS: tuple[tuple[str, str], ...] = (
    # A minor version is introduced by a DOT only (gpt-4.1, gpt-5.2). A HYPHEN followed by digits
    # is a dated snapshot -- `gpt-5-2026-04-01` -- and reading that as minor version 2026 made the
    # snapshot outrank its own stable alias. Snapshots get retired under you; the bare alias does
    # not, so it must win.
    ("gpt", r"(?:^|/)gpt-(\d+)(?:\.(\d+))?"),         # gpt-5, gpt-5.1, gpt-6, gpt-12 ...
    ("o", r"(?:^|/)o(\d+)(?:\.(\d+))?\b"),            # o3, o4, o5 ...
    ("grok", r"(?:^|/)grok-(\d+)(?:\.(\d+))?"),
    ("deepseek", r"(?:^|/)deepseek-r(\d+)(?:\.(\d+))?"),
    ("claude", r"(?:^|/)claude-[a-z]*-?(\d+)(?:\.(\d+))?"),
)

#: LAST-RESORT FAMILY MATCH: any `name-<version>` id at all.
#:
#: WHY (principal 2026-08-01: "it should always upgrade when new better released, not just to gpt6
#: then never"). Parsing the version number already makes gpt-7, gpt-12 and beyond automatic --
#: there is no ceiling. But the FAMILY list is still a list, and a genuinely new family under a new
#: name would match nothing and be invisible forever. That is the same "then never" failure one
#: level up, and it is the one that actually bites when the landscape moves.
#:
#: So when no KNOWN family is present, any versioned non-downgrade id becomes a candidate. Known
#: families still win outright when they exist, because an unrecognised name is weaker evidence
#: than a recognised one -- but "unrecognised" can no longer mean "unusable".
_GENERIC_PATTERN = r"(?:^|/)([a-z][a-z0-9]*)[-_]?v?(\d+)(?:\.(\d+))?"

#: Tie-break order between families at the same version number. GPT first because the principal
#: seated GPT specifically; the rest exist so a provider without it still yields a flagship.
_FAMILY_RANK = {name: i for i, (name, _) in enumerate(_FLAGSHIP_PATTERNS)}

#: Tokens that mark a CHEAPER, SMALLER or OLDER variant. A model id carrying any of these is not
#: the flagship, and picking one would quietly downgrade the seat while every status line still
#: read healthy. `mini` and `nano` are the dangerous ones: they sort adjacent to the flagship and
#: often carry the same version number.
_DOWNGRADE_TOKENS: tuple[str, ...] = (
    "mini", "nano", "small", "lite", "tiny", "turbo", "instruct", "preview", "legacy",
    ":free", "-free", "8b", "7b", "3b", "flash", "haiku", "distill", "base", "audio",
    "realtime", "transcribe", "tts", "image", "search", "embedding", "moderation", "codex",
)

#: Reasoning effort requested. MAX BY DEFAULT: this seat runs four times a day against a $20/month
#: cap, so the binding constraint is the quality of twelve recommendations rather than the token
#: cost of producing them. Providers that reject the parameter are retried without it -- see
#: `chat` -- so requesting it can never cost a cycle.
DEFAULT_EFFORT = "high"

#: Hard monthly ceiling in USD. Deliberately low: this is wired to a daily cadence, and the cost
#: of an over-cautious cap is a deferred run while the cost of no cap is unbounded. Raise it
#: through the environment when the spend is proven worth it, never by editing this line -- a cap
#: that gets edited upward whenever it binds is not a cap.
DEFAULT_MONTHLY_CAP_USD = 20.0

#: Rough blended $/1k tokens, used only to enforce the cap. Intentionally an OVER-estimate: the
#: two errors are not symmetric. Over-estimating defers a run by a cycle; under-estimating spends
#: money the principal did not agree to.
_USD_PER_1K_TOKENS = 0.02

#: FREE TIER IS THE DEFAULT, EVERYWHERE (2026-09-12, principal: "make everything free tier on
#: openrouter... all the paid run things js run on free tiers instead").
#:
#: WHY A DEFAULT AND NOT A FLAG ON EACH ORGAN. A flag has to be remembered at every call site, and
#: the organs that resolve a seat here are spread across six scripts and three libraries -- one
#: forgotten export is a paid run nobody authorised. Defaulting the policy ON and requiring
#: QUANT_FREE_TIER=0 to spend makes the safe state the automatic one.
#:
#: IT IS NOT A THROTTLE. Free models are weaker than flagships and every finding still faces the
#: identical ten gates, so this buys ATTEMPTS and never leniency -- and the cadence it pays for is
#: 24x: the six seats went from daily to hourly in the same change. kimi_hunter measured this
#: trade already and its conclusion holds: a free-tier hunt is worth immeasurably more than no
#: hunt, and the binding constraint was never model quality, it was the seat being dark.
def free_tier_only() -> bool:
    """True unless the principal explicitly re-enables spending with QUANT_FREE_TIER=0."""
    return os.environ.get("QUANT_FREE_TIER", "1") != "0"


_CTX: ssl.SSLContext | None = None


def _ctx() -> ssl.SSLContext:
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            _CTX = ssl.create_default_context()
    return _CTX


@dataclass(frozen=True)
class Seat:
    name: str
    base_url: str
    # `repr=False` IS THE WHOLE POINT OF THIS LINE (2026-09-24). `redacted` below has always
    # existed and says in as many words that a key reaching a log file is a leaked key -- but a
    # dataclass writes its own `__repr__` from every field, so the moment anything printed a Seat,
    # logged one, put one in an f-string, or let one surface in a traceback frame, the key went
    # out IN FULL and the careful helper beside it was simply bypassed. Found by a builder that
    # was not looking for it. Opting the field out of the generated repr is what makes the
    # redaction the ONLY way the key can be rendered, rather than the polite way.
    key: str = field(repr=False)
    model: str = ""
    source: str = ""

    @property
    def redacted(self) -> str:
        """For logs and reports. A key that reaches a log file is a leaked key."""
        return f"{self.name}:{self.model or '<undiscovered>'} (key {self.key[:6]}...)"

    def __repr__(self) -> str:
        """Redacted by construction, so a bare `print(seat)` cannot leak.

        Explicit rather than relying on `repr=False` alone: a later field added without the flag
        would silently re-open the hole, and `str()` falls through to this too.
        """
        return f"Seat({self.redacted}, base_url={self.base_url!r}, source={self.source!r})"


def seats() -> list[Seat]:
    """Every seat this box can reach, environment first, secrets file second.

    ENVIRONMENT FIRST IS THE WHOLE POINT. The secrets file has to be written onto a box that gets
    reclaimed; an exported variable is set once in the environment config and survives every
    container the desk is ever given.
    """
    out: list[Seat] = []
    for var, name, base in KEY_ENV_VARS:
        key = os.environ.get(var, "").strip()
        if key:
            out.append(Seat(name=name, base_url=os.environ.get(f"{name.upper()}_BASE_URL", base),
                            key=key, model=os.environ.get(f"{name.upper()}_MODEL", ""),
                            source=f"env:{var}"))
    if SECRETS.exists():
        try:
            cfg = json.loads(SECRETS.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
        for p in cfg.get("providers") or []:
            key = str(p.get("key") or "").strip()
            if not key:
                continue
            out.append(Seat(name=str(p.get("name") or "panel"),
                            base_url=str(p.get("base_url") or "https://openrouter.ai/api/v1"),
                            key=key, model=str(p.get("model") or ""), source="file:llm_panel.json"))
    return out


def primary_seat() -> Seat | None:
    """The seat organs should use when they want exactly one. None when the desk is dark."""
    got = seats()
    return got[0] if got else None


def flagship_rank(model_id: str) -> tuple[int, int, int, int] | None:
    """Rank a model id as a flagship candidate, or None if it is not one.

    Higher sorts better. The version number dominates, which is what makes the upgrade AUTOMATIC:
    when a provider lists `gpt-6`, it outranks every `gpt-5` immediately, with no code change.
    Downgrade-marked ids (mini, nano, turbo, :free ...) are rejected outright rather than ranked
    low -- they sort adjacent to the flagship and often carry the SAME version number, so ranking
    alone would let a `gpt-6-mini` beat a `gpt-5` and quietly shrink the brain.
    """
    low = model_id.lower()
    if any(tok in low for tok in _DOWNGRADE_TOKENS):
        return None
    for family, pat in _FLAGSHIP_PATTERNS:
        m = re.search(pat, low)
        if not m:
            continue
        major = int(m.group(1))
        minor = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0
        # Shorter id wins at equal version: the bare alias (`gpt-5`) is the provider's stable
        # pointer, while decorated ids are dated snapshots that get retired under you.
        return (major, minor, -_FAMILY_RANK[family], -len(low))
    return None


def discover_model(seat: Seat, *, timeout: float = 20.0) -> tuple[str, str | None]:
    """Ask the provider what it serves and pick the HIGHEST-VERSION FLAGSHIP. Returns (model, err).

    A PINNED MODEL STRING IS A TIME BOMB. It works until the provider retires it and then every
    organ fails with something that reads like an outage rather than like a rename. A pinned
    PREFERENCE LIST is the same bomb with a longer fuse: the day `gpt-6` ships, a list containing
    `gpt-5` keeps choosing the older model forever while every status line still reads healthy.
    Parsing the version and taking the maximum makes the upgrade automatic.

    An explicit `<NAME>_MODEL` environment variable still wins -- discovery is the default, never
    an override of the principal's choice.
    """
    if seat.model:
        return seat.model, None
    body, err = _get(f"{seat.base_url}/models", seat.key, timeout=timeout)
    if err:
        return "", err
    ids = [str(m.get("id") or "") for m in (body.get("data") or [])]
    ids = [i for i in ids if i]
    if not ids:
        return "", "provider listed no models"
    if free_tier_only():
        # FREE FIRST -- AND THE SUFFIX MUST COME OFF BEFORE RANKING, or this goes dark.
        #
        # `:free` and `-free` are in _DOWNGRADE_TOKENS, so flagship_rank REFUSES every free id by
        # design: a `gpt-6:free` must never outrank a paid `gpt-6` when both are available. Simply
        # narrowing `ids` to the free ones would therefore leave `ranked` empty, `generic` empty
        # too, and return "no flagship model found" -- every seat dark, with an error that reads
        # like a provider outage. Caught before this shipped; it is the exact shape of the
        # ship-the-caller-before-the-callee outage this desk already paid for once.
        #
        # Stripping the suffix and ranking the BASE name keeps the auto-upgrade property inside
        # the free tier: the day a better free model is listed, it wins on version, with no edit.
        free_ids = [i for i in ids if i.endswith((":free", "-free"))]
        if free_ids:
            base = {re.sub(r"[:\-]free$", "", i): i for i in free_ids}
            # VARIABLE-LENGTH RANK KEY, because the two rankers return different arities:
            # flagship_rank yields a 4-tuple and _generic_rank a 3-tuple. Both are only ever fed
            # to max(), which compares tuples element-wise, and the fallback list is used ONLY
            # when the flagship list is empty -- so the two arities are never compared against
            # each other and the common annotation is honest rather than a widening to silence
            # the checker.
            ranked_free: list[tuple[tuple[int, ...], str]] = [
                (r, orig) for stripped, orig in base.items()
                if (r := flagship_rank(stripped)) is not None]
            if not ranked_free:
                ranked_free = [(g, orig) for stripped, orig in base.items()
                               if (g := _generic_rank(stripped)) is not None]
            if ranked_free:
                return max(ranked_free)[1], None
            # Free models exist but none carries a parseable version. Take one rather than going
            # dark -- an unrankable free seat still answers, and a dark seat answers nothing.
            return sorted(free_ids)[0], None
    ranked = [(r, i) for i in ids if (r := flagship_rank(i)) is not None]
    if ranked:
        return max(ranked)[1], None
    # No KNOWN family present. Rather than going dark on a provider serving something new, fall
    # back to any versioned non-downgrade id -- an unrecognised name is weaker evidence than a
    # recognised one, but it must not mean unusable.
    generic = [(g, i) for i in ids if (g := _generic_rank(i)) is not None]
    if generic:
        return max(generic)[1], None
    return "", (f"no flagship model found among {len(ids)} listed "
                f"(e.g. {', '.join(sorted(ids)[:5])}) -- every candidate carried a downgrade "
                f"marker {_DOWNGRADE_TOKENS[:6]}... or carried no version at all. Set "
                "<PROVIDER>_MODEL explicitly.")


def _generic_rank(model_id: str) -> tuple[int, int, int] | None:
    low = model_id.lower()
    if any(tok in low for tok in _DOWNGRADE_TOKENS):
        return None
    m = re.search(_GENERIC_PATTERN, low)
    if not m:
        return None
    return (int(m.group(2)), int(m.group(3) or 0), -len(low))




def month_spend_usd(now: datetime | None = None) -> float:
    """This calendar month's estimated spend, read from the append-only ledger.

    FREE ROWS ARE SKIPPED BY MODEL ID, not by the `usd` they carry, and that is deliberate. The
    ledger is append-only, so the phantom dollars already booked against free calls before
    `_record_spend` learned the difference cannot be edited out -- $234.26 of them on the trading
    box the month this was found, against a $20 cap and a true bill of zero. The ROLLUP can be
    right even when the history cannot be rewritten: a `:free` model charged nothing on the day it
    ran and charges nothing retroactively. Without this the cap stays tripped by its own past for
    the rest of the month, and the cap is what gates the paid lane the principal would be buying.
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m")
    total = 0.0
    if not SPEND_LEDGER.exists():
        return 0.0
    for line in SPEND_LEDGER.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not str(row.get("utc", "")).startswith(stamp):
            continue
        if row.get("free") is True or is_free_model(str(row.get("model") or "")):
            continue
        total += float(row.get("usd") or 0.0)
    return round(total, 4)


#: OpenRouter's free tier is capped in REQUESTS PER DAY, not dollars -- and that is the limit the
#: desk actually runs into once every organ is free. The published ceiling is 1,000/day for an
#: account that has ever purchased credit and 50/day for one that has not. The default below sits
#: under the higher number with room for retries; set QUANT_FREE_DAILY_MAX=40 on an account that
#: has never purchased, or the day's budget is gone before the first sweep finishes.
DEFAULT_FREE_DAILY_MAX = 900


#: What the PROVIDER actually refused at, learned from its own 429 rather than assumed. The
#: number above is a published figure for a class of account; this file is what THIS account did.
FREE_CEILING = _ROOT / "data" / "llm_free_ceiling.json"


#: THE PROVIDER'S OWN COUNTER, AND IT IS IN A DIFFERENT UNIT FROM OURS (measured 2026-09-24).
#:
#: `note_free_limit_hit` records `calls_today()` -- the number of calls that produced a PARSEABLE
#: COMPLETION and therefore a spend row -- as "the ceiling". OpenRouter counts REQUESTS: every
#: parameter-degradation retry in `_post_with_degrade`, every 5xx from an overloaded upstream and
#: every malformed reply is one of the day's thousand, and not one of them writes a ledger row.
#: The two numbers are therefore never equal and ours is always the smaller.
#:
#: MEASURED ON THE TRADING BOX, BOTH SIDES IN ONE SITTING:
#:     2026-09-23   desk ledger 460 calls   provider counted 1000   540 requests (54%) invisible
#:     2026-09-24   desk ledger 789 calls   provider counted 1008   219 requests (22%) invisible
#:
#: WHAT THE CONFUSION COST, and it is why this function exists rather than a comment. The desk's
#: own source files went on to quote the 09-23 reading as the account's CAPACITY -- "the provider
#: refused at 458 calls", in `deepening_worker`'s module docstring, four times over -- and every
#: plan sized against that number was sized against less than half the truth. A budget measured
#: in the wrong unit does not read as wrong; it reads as a smaller desk.
#:
#: So the authoritative figure is asked for by name. `/key` returns `free_model_daily_requests`
#: as {used, limit, remaining} and that is the provider's own arithmetic, not our inference from
#: a refusal. It is a network call, so it is OPTIONAL everywhere: every caller falls back to the
#: ledger-derived estimate, which is wrong in a known direction (low) rather than unavailable.
PROVIDER_QUOTA = _ROOT / "data" / "llm_provider_quota.json"


def provider_free_quota(seat: Seat | None = None, *, timeout: float = 20.0
                        ) -> dict[str, Any]:
    """The PROVIDER's free-request counter for today: {used, limit, remaining}. Never raises.

    This is the only honest answer to "how much budget is left", because it is the number the
    provider will actually refuse against. `free_budget_left()` derives its answer from the spend
    ledger, which counts completions rather than requests and therefore over-reports what is left
    by whatever fraction of the day went to retries and upstream errors -- 22% to 54% of it on the
    two days measured.

    Returns `{}` when the provider does not answer or does not publish the field, which is a
    verdict (UNMEASURED) rather than a zero: a caller that cannot reach the provider must not
    conclude the budget is gone.
    """
    s = seat or primary_seat()
    if s is None:
        return {}
    body, err = _get(f"{s.base_url}/key", s.key, timeout=timeout)
    if err:
        return {"error": err[:200]}
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    quota = data.get("free_model_daily_requests") if isinstance(data, dict) else None
    if not isinstance(quota, dict):
        return {}
    out: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "date": datetime.now(UTC).strftime("%Y-%m-%d")}
    for k in ("used", "limit", "remaining"):
        raw = quota.get(k)
        if raw is None:
            continue
        with contextlib.suppress(TypeError, ValueError):
            out[k] = int(raw)
    # The desk's own counter beside it, so the GAP is on the record rather than rediscovered.
    ours = calls_today()
    out["ledger_calls_today"] = ours
    if isinstance(out.get("used"), int):
        out["invisible_requests"] = max(0, int(out["used"]) - ours)
        out["why"] = ("`used` counts REQUESTS (degradation retries, upstream 5xx and unparseable "
                      "replies included); `ledger_calls_today` counts the subset that produced a "
                      "completion. The difference is the day's waste and is the number to drive "
                      "down -- it is free budget, recoverable without spending anything.")
    with contextlib.suppress(OSError, TypeError, ValueError):
        PROVIDER_QUOTA.parent.mkdir(parents=True, exist_ok=True)
        PROVIDER_QUOTA.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def observed_free_ceiling(now: datetime | None = None) -> int | None:
    """The request count at which the provider refused a free call TODAY, if it has.

    WHY THIS EXISTS. `DEFAULT_FREE_DAILY_MAX` is 900 because that is OpenRouter's published
    ceiling for an account that has purchased credit. Measured 2026-09-12: this account took
    `HTTP 429 ... free-models-per-day` with the desk's own counter reading 562 calls and 338
    budget "left". The desk therefore believed it had a third of a day's research left while
    every further call was already being refused -- and each refusal reads, at the organ, exactly
    like a provider outage.

    A GUESSED CEILING THAT IS TOO HIGH IS WORSE THAN ONE THAT IS TOO LOW. Too low costs a few
    unmade calls; too high means every organ after the limit spends its cadence on refusals,
    reports errors it cannot act on, and produces nothing -- which is how a lane goes quietly
    dark while its scheduler reports healthy. So the refusal is recorded and believed until the
    UTC day rolls, at which point it is stale by construction and ignored.
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    try:
        doc = json.loads(FREE_CEILING.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if str(doc.get("date")) != stamp:
        return None
    try:
        n = int(doc.get("ceiling"))
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


#: The provider states its own limit in the 429 body's headers. Reading it is strictly better than
#: inferring one, and it is the number that ends the "458/day" confusion for good.
_LIMIT_HEADER = re.compile(r'"X-RateLimit-Limit"\s*:\s*"?(\d+)')


def note_free_limit_hit(detail: str, now: datetime | None = None) -> None:
    """Record that the provider refused a FREE call, and at what count. Never raises.

    TWO NUMBERS, LABELLED, BECAUSE THEY ARE IN DIFFERENT UNITS. `ceiling` is what the DESK had
    counted when the refusal landed -- completions, from the spend ledger. `provider_limit` is
    what the provider says its own allowance is, lifted straight out of the 429 body's
    `X-RateLimit-Limit`. On 2026-09-23 those read 460 and 1000; the desk's own docstrings then
    quoted the smaller one as the account's capacity and every plan sized against it was sized
    against less than half the truth. Recording both, named, is what stops that happening again:
    `ceiling` still governs the rest of the day (the refusal is real and more calls will not
    work), but nobody reading the file can mistake it for the account's size.
    """
    t = now or datetime.now(UTC)
    mine = calls_today(t)
    row: dict[str, Any] = {
        "date": t.strftime("%Y-%m-%d"), "ceiling": mine,
        "ceiling_unit": "completions recorded by this desk (data/llm_spend.jsonl rows)",
        "observed_at": t.isoformat(timespec="seconds"), "detail": detail[:300],
        "why": ("the provider refused a free request at this count. Until the UTC day rolls, "
                "free_daily_max() believes this number rather than the configured default -- "
                "an organ that keeps calling past a real ceiling spends its cadence on "
                "refusals and goes dark while its scheduler still reports healthy.")}
    m = _LIMIT_HEADER.search(detail or "")
    if m:
        with contextlib.suppress(ValueError):
            lim = int(m.group(1))
            row["provider_limit"] = lim
            row["provider_limit_unit"] = ("REQUESTS the provider counted, retries and upstream "
                                          "errors included -- always >= `ceiling`")
            row["invisible_requests"] = max(0, lim - mine)
            row["read_this_one_for_capacity"] = (
                f"the account's allowance is {lim} REQUESTS/day, not {mine}. The gap is this "
                f"day's waste (degradation retries, 5xx, unparseable replies), which is free "
                f"budget recoverable without spending a penny. Do NOT quote `ceiling` as the "
                f"size of this desk's daily research allowance -- that error is what put "
                f"'458 calls/day' into four docstrings.")
    try:
        FREE_CEILING.parent.mkdir(parents=True, exist_ok=True)
        FREE_CEILING.write_text(json.dumps(row, indent=1), encoding="utf-8")
    except OSError:
        pass


def free_daily_max() -> int:
    try:
        configured = max(1, int(os.environ.get("QUANT_FREE_DAILY_MAX", DEFAULT_FREE_DAILY_MAX)))
    except ValueError:
        configured = DEFAULT_FREE_DAILY_MAX
    seen = observed_free_ceiling()
    # The MEASURED ceiling wins whenever it is lower, and only for the UTC day it was measured
    # on. It never raises the budget: a day that happened to stop early is not evidence the
    # provider will allow more tomorrow.
    return min(configured, seen) if seen is not None else configured


def calls_today(now: datetime | None = None) -> int:
    """Requests made today, from the same append-only ledger the spend rollup reads."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    if not SPEND_LEDGER.exists():
        return 0
    n = 0
    try:
        lines = SPEND_LEDGER.read_text("utf-8").splitlines()
    except OSError:
        return 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("utc", "")).startswith(stamp):
            n += 1
    return n


def free_budget_left(now: datetime | None = None) -> int:
    """How many free requests today's budget still has. Negative is never returned."""
    return max(0, free_daily_max() - calls_today(now))


def monthly_cap_usd() -> float:
    raw = os.environ.get("LLM_MONTHLY_CAP_USD", "").strip()
    try:
        return float(raw) if raw else DEFAULT_MONTHLY_CAP_USD
    except ValueError:
        return DEFAULT_MONTHLY_CAP_USD


#: Phrases a provider uses when the refusal is the DAY's free allowance rather than a burst.
#: Matched on the error body, because the status code alone cannot tell "slow down for a minute"
#: from "come back tomorrow", and treating the second as the first burns the rest of the day.
_DAILY_FREE_MARKERS: tuple[str, ...] = (
    "free-models-per-day", "per-day", "daily limit", "requests per day", "quota exceeded",
)


def _is_daily_free_refusal(err: str) -> bool:
    low = err.lower()
    return any(m in low for m in _DAILY_FREE_MARKERS)


#: Ask the PROVIDER to guarantee a JSON object, rather than asking the model nicely in the prompt.
#:
#: WHY THIS IS WORTH A PARAMETER. Measured on the trading box 2026-09-24: of 789 completed seat
#: calls, 456 (58%) were thrown away by the caller with "reply was not a JSON object" -- and the
#: caller's parser is already lenient, stripping code fences and scanning from the first brace to
#: the last, so a rejection means the reply contained no object AT ALL. Each of those cost one of
#: the day's thousand requests and returned nothing. That is the single largest recoverable loss
#: in this lane and it costs no money to recover: the same allowance, spent on replies that parse.
#:
#: It is OPT-IN because not every caller wants JSON, and it degrades rather than fails because a
#: free model that has never implemented structured output must not go dark over it.
JSON_OBJECT: dict[str, str] = {"type": "json_object"}


def chat(
    prompt: str, *, system: str = "", seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4, effort: str = DEFAULT_EFFORT,
    response_format: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    """One completion at MAXIMUM reasoning effort. Returns (text, error) -- NEVER raises, so a
    cadenced organ survives it.

    EFFORT IS REQUESTED HIGH AND DEGRADED ONLY IF REFUSED. The seat runs four times a day against
    a $20/month cap, so the binding constraint is the quality of twelve recommendations rather
    than the tokens spent producing them -- there is no version of this where thinking less is the
    right trade. Providers differ on which parameters they accept, so a 400 naming a parameter is
    retried with the offending one dropped rather than surfaced as a failure: a seat that goes
    dark because it asked for too much thinking would be a self-inflicted outage.

    The cap is checked BEFORE the call, not after. Checking after is how run_external_panel
    discovered exhaustion mid-run with nothing to show for the spend.
    """
    s = seat or primary_seat()
    if s is None:
        return "", ("no seat: export OPENROUTER_API_KEY (recommended -- one key reaches every "
                    "model family and auto-upgrades across the market, not just within one "
                    "vendor), "
                    "or OPENAI_API_KEY / DEEPSEEK_API_KEY / XAI_API_KEY, or write "
                    "data/secrets/llm_panel.json")
    spent, cap = month_spend_usd(), monthly_cap_usd()
    # THE CAP CANNOT BIND A FREE RUN, and letting it would be the worst failure mode available:
    # the ledger accrues an ESTIMATED cost (_USD_PER_1K_TOKENS is a deliberate over-estimate), so
    # a month of free-tier calls would book phantom spend and then refuse free calls for the rest
    # of the month -- the desk going dark over money it never spent.
    # THE FREE TIER'S LIMIT IS REQUESTS PER DAY, so that is what gets checked when the run is
    # free. Stopping one call short of the ceiling is the difference between an organ that skips
    # a cycle and an account rate-limited into darkness for the rest of the day -- and a dark
    # account takes EVERY organ with it, not just the one that spent the last request.
    if free_tier_only():
        left = free_budget_left()
        if left <= 0:
            return "", (f"free-tier daily request budget exhausted: {calls_today()} call(s) "
                        f"today against a {free_daily_max()} ceiling. This is a SKIP, not a "
                        f"failure -- the budget resets at 00:00 UTC and the next cadence picks "
                        f"it up. Raise QUANT_FREE_DAILY_MAX only if the provider's real limit "
                        f"is higher than the one assumed here.")
    if spent >= cap and not free_tier_only():
        return "", (f"monthly cap reached: ${spent:.2f} of ${cap:.2f}. Raise it with "
                    "$LLM_MONTHLY_CAP_USD if the spend is proven worth it.")
    model, err = discover_model(s)
    if err:
        return "", f"model discovery failed: {err}"

    msgs: list[dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    req: dict[str, Any] = {"model": model, "messages": msgs,
                           "max_completion_tokens": int(max_tokens),
                           "temperature": float(temperature)}
    if effort:
        req["reasoning_effort"] = effort
    if response_format:
        req["response_format"] = dict(response_format)
    body, err = _post_with_degrade(f"{s.base_url}/chat/completions", s.key, req, timeout=timeout)
    if err:
        # A DAILY FREE-TIER REFUSAL IS EVIDENCE, NOT NOISE. Recording it teaches every later
        # caller today's real ceiling instead of letting each one rediscover it one wasted
        # request at a time.
        if "429" in err and _is_daily_free_refusal(err):
            note_free_limit_hit(err)
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body)
    return text, None


def chat_messages(
    messages: list[dict[str, str]], *, seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4, effort: str = DEFAULT_EFFORT,
    response_format: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    """chat(), at the MESSAGES level -- the seam the push ladder needs.

    Added 2026-08-04 for `libs.llm.push.push_rounds`: a push round re-sends the whole
    conversation (system + prior rounds + the rung), which a single-prompt entrypoint cannot
    express. Same cap-before-call, same discovery, same degradation ladder, same spend record --
    a second transport here would drift from the first on the exact policies that must not.
    """
    s = seat or primary_seat()
    if s is None:
        return "", "no seat: export OPENROUTER_API_KEY (see chat())"
    spent, cap = month_spend_usd(), monthly_cap_usd()
    # THE CAP CANNOT BIND A FREE RUN, and letting it would be the worst failure mode available:
    # the ledger accrues an ESTIMATED cost (_USD_PER_1K_TOKENS is a deliberate over-estimate), so
    # a month of free-tier calls would book phantom spend and then refuse free calls for the rest
    # of the month -- the desk going dark over money it never spent.
    # THE FREE TIER'S LIMIT IS REQUESTS PER DAY, so that is what gets checked when the run is
    # free. Stopping one call short of the ceiling is the difference between an organ that skips
    # a cycle and an account rate-limited into darkness for the rest of the day -- and a dark
    # account takes EVERY organ with it, not just the one that spent the last request.
    if free_tier_only():
        left = free_budget_left()
        if left <= 0:
            return "", (f"free-tier daily request budget exhausted: {calls_today()} call(s) "
                        f"today against a {free_daily_max()} ceiling. This is a SKIP, not a "
                        f"failure -- the budget resets at 00:00 UTC and the next cadence picks "
                        f"it up. Raise QUANT_FREE_DAILY_MAX only if the provider's real limit "
                        f"is higher than the one assumed here.")
    if spent >= cap and not free_tier_only():
        return "", (f"monthly LLM spend cap reached (${spent:.2f} of ${cap:.2f}) -- raise "
                    "$LLM_MONTHLY_CAP_USD if the spend is proven worth it.")
    model, err = discover_model(s)
    if err:
        return "", f"model discovery failed: {err}"
    req: dict[str, Any] = {"model": model, "messages": list(messages),
                           "max_completion_tokens": int(max_tokens),
                           "temperature": float(temperature)}
    if effort:
        req["reasoning_effort"] = effort
    if response_format:
        req["response_format"] = dict(response_format)
    body, err = _post_with_degrade(f"{s.base_url}/chat/completions", s.key, req, timeout=timeout)
    if err:
        # Same refusal, same lesson: chat_messages is the push ladder's seam and
        # hits the identical daily ceiling.
        if "429" in err and _is_daily_free_refusal(err):
            note_free_limit_hit(err)
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body)
    return text, None


def stale_pins(*, timeout: float = 20.0) -> list[dict[str, Any]]:
    """Every seat PINNED to a model below the provider's current flagship.

    WHY THIS EXISTS AND WHY IT COVERS MORE THAN THIS MODULE (principal 2026-08-01: "this goes for
    every single llm related to our quant, all panels etc, kimi, you all"). Discovery keeps THIS
    seat current automatically, but the desk's other eleven model organs read
    `data/secrets/llm_panel.json`, and every provider entry there carries a hardcoded `model`
    string. A pin is invisible by construction: the organ runs, returns text, and reports success
    while quietly executing a superseded model -- for years, if nobody looks.

    So the pins are CHECKED against what the provider currently serves, and a pin below the
    flagship is reported as a defect with the replacement named. Reported rather than rewritten:
    silently editing a credentials file out from under eleven organs is a worse failure than a
    stale pin, and a pin may be deliberate (a cost decision, a capability the flagship lost).
    `status()` surfaces this, so it reaches the CRO and the doctor without anyone remembering to
    ask.
    """
    out: list[dict[str, Any]] = []
    for s in seats():
        if not s.model:
            continue                      # unpinned: discovery already keeps it current
        probe = Seat(name=s.name, base_url=s.base_url, key=s.key, model="", source=s.source)
        best, err = discover_model(probe, timeout=timeout)
        if err or not best:
            out.append({"seat": s.name, "source": s.source, "pinned": s.model,
                        "flagship": None, "stale": None, "error": err})
            continue
        # Either ranker may answer; only the leading (major, minor) pair is compared, so the
        # differing tuple widths never meet.
        pinned_rank: tuple[int, ...] | None = flagship_rank(s.model) or _generic_rank(s.model)
        best_rank: tuple[int, ...] | None = flagship_rank(best) or _generic_rank(best)
        stale = bool(best_rank and (pinned_rank is None or best_rank[:2] > pinned_rank[:2]))
        out.append({"seat": s.name, "source": s.source, "pinned": s.model, "flagship": best,
                    "stale": stale,
                    "note": (f"PINNED BELOW FLAGSHIP: {s.model} -> {best}. Either update the pin "
                             "or clear the `model` field so discovery keeps it current."
                             if stale else "")})
    return out


def status() -> dict[str, Any]:
    """What this box can actually reach, re-measured rather than assumed. For the doctor."""
    got = seats()
    out: dict[str, Any] = {
        "n_seats": len(got),
        "seats": [{"name": s.name, "source": s.source, "model": s.model or "<discover>"}
                  for s in got],
        "month_spend_usd": month_spend_usd(),
        "monthly_cap_usd": monthly_cap_usd(),
        "secrets_file_present": SECRETS.exists(),
    }
    if not got:
        out["blocker"] = (
            "DARK: no external-model seat. Export OPENROUTER_API_KEY (one key reaches every "
            "family and auto-upgrades across the market). Eleven organs depend on this -- "
            "run_external_panel, "
            "strategic_director, llm_code_auditor, meta_architect, breadth_expander, kimi_hunter, "
            "collector_author, deep_review, run_micro_audit, refresh_panel_roster, "
            "llm_blind_researcher -- and one exported OPENAI_API_KEY lights all of them.")
        return out
    model, err = discover_model(got[0])
    out["primary"] = got[0].name
    out["primary_model"] = model or None
    out["primary_error"] = err
    out["effort"] = DEFAULT_EFFORT
    # Stale pins reach the CRO and the doctor without anyone remembering to ask. A pinned model is
    # invisible by construction: the organ runs, returns text, and reports success while quietly
    # executing something superseded.
    pins = [p for p in stale_pins() if p.get("stale")]
    if pins:
        out["stale_pins"] = pins
    return out


# ------------------------------------------------------------------------------------ transport

def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost", "X-Title": "quant-desk"}


def _get(url: str, key: str, *, timeout: float) -> tuple[dict[str, Any], str | None]:
    req = urllib.request.Request(url, headers=_headers(key))
    return _send(req, timeout)


#: Parameters that a provider may reject, in the order they are given up. Effort goes LAST because
#: it is the one the principal asked for; temperature and the token-cap spelling go first because
#: their defaults are harmless.
#:
#: `response_format` sits ahead of effort and behind the harmless two: a free model that does not
#: implement structured output must not cost the caller its request, and a caller that asked for
#: JSON still gets a reply it can attempt to parse. EVERY RETRY HERE IS ONE OF THE DAY'S THOUSAND
#: REQUESTS -- see `provider_free_quota` -- so the ladder is ordered to be short in the common
#: case, not to be thorough.
_DEGRADABLE = ("temperature", "max_completion_tokens", "response_format", "reasoning_effort")


def _post_with_degrade(url: str, key: str, req: dict[str, Any], *, timeout: float
                       ) -> tuple[dict[str, Any], str | None]:
    """POST, and if the provider rejects a parameter by name, drop that one and retry.

    WHY THIS EXISTS RATHER THAN A PER-PROVIDER PARAMETER TABLE. Providers differ on which
    parameters they accept and change it without notice; a table encodes today's answer and rots.
    Reading the rejection is self-correcting -- the provider names the parameter it refused in the
    400 body, which is exactly why `_send` carries the body into the error string.

    `max_completion_tokens` is retried as `max_tokens`, because that rename is the single most
    common 400 across OpenAI-compatible endpoints and losing the cap entirely would let one call
    run away against a metered API.
    """
    attempt = dict(req)
    for _ in range(len(_DEGRADABLE) + 1):
        body, err = _post(url, key, json.dumps(attempt).encode(), timeout=timeout)
        if err is None or not err.startswith("HTTP 400"):
            return body, err
        low = err.lower()
        if "max_completion_tokens" in low and "max_tokens" not in attempt:
            attempt["max_tokens"] = attempt.pop("max_completion_tokens", max(1, 8000))
            continue
        dropped = next((p for p in _DEGRADABLE if p in attempt and p.lower() in low), None)
        if dropped is None:
            return body, err            # a 400 about something we cannot fix by dropping
        attempt.pop(dropped)
    return {}, "exhausted parameter degradation without a successful call"


def _post(url: str, key: str, payload: bytes, *, timeout: float
          ) -> tuple[dict[str, Any], str | None]:
    req = urllib.request.Request(url, data=payload, headers=_headers(key), method="POST")
    return _send(req, timeout)


def _send(req: urllib.request.Request, timeout: float) -> tuple[dict[str, Any], str | None]:
    """HTTP errors carry their BODY into the message. A bare '400 Bad Request' from a model API
    is unactionable; the body says which parameter the provider rejected."""
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as fh:
            parsed: dict[str, Any] = json.loads(fh.read().decode("utf8", errors="ignore"))
            return parsed, None
    except urllib.error.HTTPError as exc:
        detail = ""
        # A failed body read must not mask the HTTP error itself -- the status code is the part
        # that is always actionable.
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf8", errors="ignore")[:300]
        # AND IT MUST BE CLOSED. `HTTPError` is itself a response object holding a spooled
        # temporary file; left to the collector it emits `ResourceWarning: Implicitly cleaning up
        # <HTTPError ...>` from `tempfile.__del__` at an arbitrary later moment. The suite runs
        # `filterwarnings = error`, so that stray warning fails whichever test happens to be
        # executing when the collector gets to it -- which is how a genuine assertion
        # (`test_a_key_never_appears_in_full_in_a_report`, and its assertions PASS) reported red
        # for a leak that had nothing to do with keys. Every 4xx and 429 this desk takes goes
        # through here, so on a day of rate-limit refusals it leaks one per refusal.
        with contextlib.suppress(Exception):
            exc.close()
        return {}, f"HTTP {exc.code}: {detail or exc.reason}"
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:160]}"


def is_free_model(model: str) -> bool:
    """True when the provider serves this model id at no charge."""
    return model.lower().endswith((":free", "-free"))


def calling_organ() -> str:
    """Which organ is spending the seat. Env first, else the entry-point script's name.

    WHY THE BUDGET NEEDS A NAME ON IT. One account holds ONE allowance of a thousand requests a
    day, and every model organ on this desk draws from it first-come-first-served. Measured
    2026-09-24: the allowance was gone by 01:42 UTC, so every audit, panel and recommendation
    organ scheduled after that hour got a refusal that reads exactly like a provider outage --
    and the recommendation ledger duly recorded seven new entries in twenty days, down from
    dozens a week. Nothing in the ledger said WHO had spent it, because the ledger recorded the
    provider's name (`openrouter`) and never the caller's, so the question could not even be
    asked. A budget that cannot be attributed cannot be allocated.
    """
    named = os.environ.get("QUANT_LLM_ORGAN", "").strip()
    if named:
        return named[:64]
    with contextlib.suppress(Exception):
        stem = Path(sys.argv[0]).stem
        if stem and stem not in ("-c", "", "python", "python3"):
            return stem[:64]
    return "unattributed"


def _record_spend(seat: Seat, model: str, body: dict[str, Any]) -> None:
    """Append-only, and it records what the PROVIDER reported rather than what we guessed.

    A FREE CALL COSTS ZERO, AND BOOKING IT AS SPEND BRICKS THE PAID LANE (fixed 2026-09-24).
    `_USD_PER_1K_TOKENS` is a deliberate over-estimate, which is the right error for a metered
    call and a catastrophic one for a free model: the desk runs free-tier by default, so every
    call was accruing phantom dollars against a $20 monthly cap. Measured on the trading box the
    month this was found: $234.26 booked, $0.00 actually owed. Nothing had failed yet only
    because `free_tier_only()` skips the cap check -- but that is precisely the switch the
    principal flips to BUY more capacity, and flipping it would have taken every organ dark
    inside one call with "monthly cap reached: $234.26 of $20.00". The landmine sat directly on
    the upgrade path, armed by the safety feature.

    WHAT ELSE IS RECORDED, and why each field is a number the desk was arguing about without it:
    the ORGAN (so the one allowance can be attributed and therefore allocated), the COMPLETION and
    REASONING token split, and `finish_reason`. That last pair is the live question: seat calls go
    out at `reasoning_effort: high` under a 700-token completion cap, and a reasoning model that
    spends the cap thinking returns empty content -- which every caller reports as "reply was not
    a JSON object", 456 times on the day this was written, 58% of the day's completed calls.
    Truncation and refusal are indistinguishable downstream; `finish_reason` distinguishes them at
    the source, so the next pass measures the cause instead of inferring it.
    """
    raw_usage = body.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    tok = int(usage.get("total_tokens") or 0)
    free = is_free_model(model)
    row: dict[str, Any] = {
        "utc": datetime.now(UTC).isoformat(timespec="seconds"), "seat": seat.name,
        "organ": calling_organ(), "model": model, "tokens": tok, "free": free,
        # ZERO for a free model, and it is zero because it IS zero -- not a discount, not an
        # assumption. The estimate is kept for metered models only, where erring high is right.
        "usd": 0.0 if free else round(tok / 1000.0 * _USD_PER_1K_TOKENS, 5)}
    for key in ("prompt_tokens", "completion_tokens"):
        raw = usage.get(key)
        if raw is not None:
            with contextlib.suppress(TypeError, ValueError):
                row[key] = int(raw)
    det = usage.get("completion_tokens_details")
    if isinstance(det, dict) and det.get("reasoning_tokens") is not None:
        with contextlib.suppress(TypeError, ValueError):
            row["reasoning_tokens"] = int(det["reasoning_tokens"])
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        ch: dict[str, Any] = choices[0]
        if ch.get("finish_reason"):
            row["finish_reason"] = str(ch["finish_reason"])[:32]
        msg = ch.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        row["empty_content"] = not str(content or "").strip()
    try:
        SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SPEND_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass                          # a ledger write must never take down the organ
