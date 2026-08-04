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
import urllib.error
import urllib.request
from dataclasses import dataclass
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
    key: str
    model: str = ""
    source: str = ""

    @property
    def redacted(self) -> str:
        """For logs and reports. A key that reaches a log file is a leaked key."""
        return f"{self.name}:{self.model or '<undiscovered>'} (key {self.key[:6]}...)"


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
    """This calendar month's estimated spend, read from the append-only ledger."""
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
        if str(row.get("utc", "")).startswith(stamp):
            total += float(row.get("usd") or 0.0)
    return round(total, 4)


def monthly_cap_usd() -> float:
    raw = os.environ.get("LLM_MONTHLY_CAP_USD", "").strip()
    try:
        return float(raw) if raw else DEFAULT_MONTHLY_CAP_USD
    except ValueError:
        return DEFAULT_MONTHLY_CAP_USD


def chat(
    prompt: str, *, system: str = "", seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4, effort: str = DEFAULT_EFFORT,
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
    if spent >= cap:
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
    body, err = _post_with_degrade(f"{s.base_url}/chat/completions", s.key, req, timeout=timeout)
    if err:
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body.get("usage") or {})
    return text, None


def chat_messages(
    messages: list[dict[str, str]], *, seat: Seat | None = None, max_tokens: int = 8000,
    timeout: float = 240.0, temperature: float = 0.4, effort: str = DEFAULT_EFFORT,
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
    if spent >= cap:
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
    body, err = _post_with_degrade(f"{s.base_url}/chat/completions", s.key, req, timeout=timeout)
    if err:
        return "", err
    try:
        text = str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return "", f"unparseable response: {json.dumps(body)[:200]}"
    _record_spend(s, model, body.get("usage") or {})
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
_DEGRADABLE = ("temperature", "max_completion_tokens", "reasoning_effort")


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
        return {}, f"HTTP {exc.code}: {detail or exc.reason}"
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:160]}"


def _record_spend(seat: Seat, model: str, usage: dict[str, Any]) -> None:
    """Append-only, and it records what the PROVIDER reported rather than what we guessed."""
    tok = int(usage.get("total_tokens") or 0)
    row = {"utc": datetime.now(UTC).isoformat(timespec="seconds"), "seat": seat.name,
           "model": model, "tokens": tok,
           "usd": round(tok / 1000.0 * _USD_PER_1K_TOKENS, 5)}
    try:
        SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SPEND_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass                          # a ledger write must never take down the organ
