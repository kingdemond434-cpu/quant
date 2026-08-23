"""One GPT Hunter: transcripts, extreme returns, public strategies and elite intelligence.

This is a source acquisition and extraction organ, not a fourth miner architecture.  It shares one
source state, corpus ledger, mechanism dedupe and downstream artifact across all missions.  Kimi's
deep-forest protocol and Claude's miners remain untouched.

YouTube caption access is attempted and truthfully classified.  A description is never labelled a
transcript; datacenter blocking becomes ``UNAVAILABLE`` with the error retained.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.core.coerce import integer

_UA = "Mozilla/5.0 (compatible; QuantResearchPublicSourceMonitor/1.0)"
_CTX = ssl.create_default_context()
_EXTREME = re.compile(
    r"(?:\b(?:100|200|300|500|1000)%|triple[- ]digit|world cup|champion|record return|10x|100x)",
    re.I,
)
_ELITE = re.compile(
    r"(?:research|paper|working paper|quant|microstructure|market making|MEV|blockspace|"
    r"execution|systematic|arxiv|repository|dataset|laboratory)",
    re.I,
)

#: Transcript states that mean "the desk did not get to look", as opposed to UNAVAILABLE, which
#: means "we looked and this video has no captions". R0466: a reader that cannot tell these apart
#: reads a WALL as a THIN ground and retires the ground (WS-005/L1.28a). Exported so a consumer
#: can test membership instead of re-deriving the list from string literals and drifting.
TRANSCRIPT_BLOCKED = "BLOCKED"
TRANSCRIPT_UNREADABLE = "UNREADABLE"
TRANSCRIPT_UNKNOWN_STATES = frozenset({TRANSCRIPT_BLOCKED, TRANSCRIPT_UNREADABLE})

EVIDENCE_TIERS = {
    "MARKETING_CLAIM": 0,
    "SCREENSHOT_SELECTED_RESULT": 1,
    "BACKTEST": 2,
    "FORWARD_PAPER_TRADING": 3,
    "LIVE_BROKER_EXCHANGE": 4,
    "INDEPENDENTLY_VERIFIABLE": 5,
    "INSTITUTIONAL_AUDITED": 6,
}


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    kind: str
    language: str = "unknown"
    surface: str = "site"


def fetch(url: str, *, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as response:
        payload: object = response.read()
    if not isinstance(payload, bytes):
        raise TypeError("public-source response must be bytes")
    return payload


def youtube_channel_id(page: bytes) -> str | None:
    text = page.decode("utf-8", errors="ignore")
    for pattern in (r'"channelId":"(UC[^"]+)"', r"channel_id=(UC[A-Za-z0-9_-]+)"):
        hit = re.search(pattern, text)
        if hit:
            return hit.group(1)
    return None


def feed_items(payload: bytes, *, source: Source) -> list[dict[str, Any]]:
    """RSS/Atom discovery with namespaces ignored by local-name."""
    root = ET.fromstring(payload)
    rows = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] not in {"entry", "item"}:
            continue
        values: dict[str, str] = {}
        link = ""
        for child in node.iter():
            key = child.tag.rsplit("}", 1)[-1]
            if key == "link":
                link = child.attrib.get("href") or (child.text or link)
            elif key in {
                "title",
                "published",
                "updated",
                "pubDate",
                "description",
                "summary",
                "videoId",
            }:
                values.setdefault(key, child.text or "")
        if not link and values.get("videoId"):
            link = f"https://www.youtube.com/watch?v={values['videoId']}"
        if link:
            video_id = values.get("videoId") or _youtube_video_id(link)
            rows.append(
                {
                    "source": source.name,
                    "source_kind": source.kind,
                    "url": link,
                    "title": html.unescape(values.get("title", "")),
                    "published_at": values.get("published")
                    or values.get("pubDate")
                    or values.get("updated"),
                    "description": html.unescape(
                        values.get("description") or values.get("summary", "")
                    ),
                    "video_id": video_id,
                }
            )
    return rows


def discover(source: Source, getter: Callable[[str], bytes] = fetch) -> list[dict[str, Any]]:
    if source.kind == "youtube":
        channel = youtube_channel_id(getter(source.url))
        if not channel:
            raise ValueError("YouTube channel ID not discoverable from public handle page")
        rows = feed_items(
            getter(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel}"), source=source
        )
        for row in rows:
            row["channel_id"] = channel
        return rows
    if source.kind in {"atom", "rss"}:
        return feed_items(getter(source.url), source=source)
    # A site is kept in coverage and freshness state, but a generic page is not hallucinated into
    # item-level strategy claims. Specialized feeds discovered in its links can be added later.
    payload = getter(source.url)
    digest = hashlib.sha256(payload).hexdigest()
    text = re.sub(r"<[^>]+>", " ", payload.decode("utf-8", errors="ignore"))
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return [
        {
            "source": source.name,
            "source_kind": source.kind,
            "url": source.url,
            "title": source.name,
            "published_at": None,
            "description": text[:50000],
            "content_hash": digest,
        }
    ]


def _refused(exc: BaseException, what: str) -> dict[str, object]:
    """The transcript record for a fetch the network REFUSED, as distinct from one that was empty.

    ``http_status`` is carried when the venue named one, because 403 (a curated denylist -- run the
    OP-052 UA matrix) and 429 (a pace problem -- come back later) demand different next moves, and
    a reader that only sees "blocked" cannot pick between them.
    """
    status = getattr(exc, "code", None)
    return {
        "transcript_state": TRANSCRIPT_BLOCKED,
        "text": "",
        "http_status": status,
        "reason": (f"{what} refused: HTTP {status}" if status is not None
                   else f"{what} failed at the transport: {type(exc).__name__}: {exc}"),
    }


def youtube_transcript(
    watch_page: bytes, getter: Callable[[str], bytes] = fetch
) -> dict[str, object]:
    """Caption text, with REFUSAL kept distinct from ABSENCE (R0466 / OP-052).

    THE DEFECT THIS FIXES, measured. A caption endpoint answering 403 and a video that genuinely
    carries no captions both returned ``transcript_state: UNAVAILABLE``. ``extraction_prompt``
    reads that field and nothing else, so at the only place the state is consumed a ground the
    desk is BLOCKED FROM was byte-identical to a ground with nothing on it. That is WS-005 /
    L1.28a exactly: absence resolving to a clean verdict. It is also the trap OP-052 names -- a
    seat whose fetch path treats a non-200 as no-content records "this ground is thin" when the
    truth is "we are not allowed to look", and those retire a region in opposite directions.

    Three states, because there are three facts:

      UNAVAILABLE -- the watch page ITSELF says there are no caption tracks. A content fact, and
                     the only one of the three that is evidence about the video.
      BLOCKED     -- the transport refused (403/429/5xx/timeout/DNS). The ground is UNKNOWN.
      UNREADABLE  -- we were served something, and it was not captions: a shape change, or the
                     200-carrying-an-anti-bot-page class. Also UNKNOWN, but a parser problem
                     rather than an access one, so it is worth its own name.
    """
    text = watch_page.decode("utf-8", errors="ignore")
    match = re.search(r'"captionTracks":(\[.*?\])(?:,"audioTracks"|,"videoDetails")', text)
    if not match:
        return {
            "transcript_state": "UNAVAILABLE",
            "text": "",
            "reason": "captionTracks absent",
            "caption_language": None,
            "caption_provenance": "youtube_watch_page",
        }
    try:
        tracks = json.loads(match.group(1))
        track = next(
            (t for t in tracks if str(t.get("languageCode", "")).startswith("en")), tracks[0]
        )
        url = str(track["baseUrl"])
        language = str(track.get("languageCode") or "unknown")
        provenance = "youtube_public_caption_track"
    except (KeyError, IndexError, ValueError) as exc:
        return {"transcript_state": TRANSCRIPT_UNREADABLE, "text": "",
                "reason": f"caption track list unusable: {type(exc).__name__}: {exc}"}
    try:
        # HTTPError, URLError, TimeoutError and socket errors are all OSError, and every one of
        # them means "we did not get to look", never "there was nothing there".
        raw = getter(url)
    except OSError as exc:
        return _refused(exc, "caption track")
    try:
        xml = ET.fromstring(raw)
    except ET.ParseError as exc:
        return {"transcript_state": TRANSCRIPT_UNREADABLE, "text": "",
                "reason": (f"caption body is not XML ({len(raw)} bytes) -- a challenge page or a "
                           f"format change, not a video without captions: {exc}")}
    root_name = xml.tag.rsplit("}", 1)[-1].casefold()
    if root_name not in {"transcript", "timedtext"}:
        return {
            "transcript_state": TRANSCRIPT_UNREADABLE,
            "text": "",
            "reason": (
                f"caption endpoint returned XML root {root_name!r}, not a caption document "
                f"({len(raw)} bytes); likely a challenge page"
            ),
        }
    transcript = " ".join(
        html.unescape("".join(x.itertext()))
        for x in xml.iter()
        if x.tag.rsplit("}", 1)[-1] in {"text", "p"}
    )
    return {
        "transcript_state": "FULL" if len(transcript) >= 1000 else "PARTIAL",
        "text": transcript,
        "reason": "public caption track",
        "caption_language": language,
        "caption_provenance": provenance,
    }


def _youtube_video_id(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.casefold().removeprefix("www.")
    if host == "youtu.be":
        return parsed.path.strip("/").split("/", 1)[0] or None
    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            return urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith(("/shorts/", "/live/")):
            return parsed.path.strip("/").split("/", 1)[1]
    return None


def _item_identity(item: Mapping[str, object]) -> str:
    video_id = str(item.get("video_id") or _youtube_video_id(str(item.get("url", ""))) or "")
    if video_id:
        return f"youtube-video:{video_id}"
    url = str(item.get("url", ""))
    return f"{url}#{item['content_hash']}" if item.get("content_hash") else url


def _qualified_related_source(extracted: Mapping[str, object]) -> bool:
    """Admit related sources only when the retrieved item exposes testable research substance."""
    substantive = any(
        bool(extracted.get(key))
        for key in (
            "mechanism",
            "hypothesis",
            "validation",
            "execution",
            "data",
            "reproducible",
            "research_system",
            "testing_process",
        )
    )
    return substantive and evidence_tier(extracted.get("evidence_class")) >= 0


def missions(item: Mapping[str, object]) -> list[str]:
    text = f"{item.get('title', '')} {item.get('description', '')}"
    out = ["PUBLIC_STRATEGY"]
    if "youtube.com" in str(item.get("url", "")):
        out.insert(0, "VIDEO_TRANSCRIPT")
    if _EXTREME.search(text):
        out.append("EXTREME_RETURN")
    external_text = f"{text} {item.get('source', '')} {item.get('url', '')}"
    if item.get("source_kind") != "youtube" and _ELITE.search(external_text):
        out.append("ELITE_EXTERNAL_INTELLIGENCE")
    return out


def evidence_tier(value: object) -> int:
    """Normalize claim evidence without treating a return number as credibility."""
    label = re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")
    aliases = {
        "CLAIM_ONLY": "MARKETING_CLAIM",
        "UNVERIFIED": "MARKETING_CLAIM",
        "SCREENSHOT": "SCREENSHOT_SELECTED_RESULT",
        "PAPER": "FORWARD_PAPER_TRADING",
        "FORWARD": "FORWARD_PAPER_TRADING",
        "LIVE": "LIVE_BROKER_EXCHANGE",
        "AUDITED": "INSTITUTIONAL_AUDITED",
    }
    return EVIDENCE_TIERS.get(aliases.get(label, label), -1)


def source_coverage(sources: Sequence[Source]) -> dict[str, object]:
    languages = sorted({source.language for source in sources})
    surfaces = sorted({source.surface for source in sources})
    return {
        "sources": len(sources),
        "languages": languages,
        "surfaces": surfaces,
        "unknown_language_sources": sum(source.language == "unknown" for source in sources),
        "law": "coverage gaps are search targets; popularity is never evidence weight",
    }


def _update_reputation(
    previous: Mapping[str, object], items: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    reputation = {
        str(name): dict(row) for name, row in previous.items() if isinstance(row, Mapping)
    }
    for item in items:
        name = str(item.get("source", "UNKNOWN"))
        row = reputation.setdefault(
            name,
            {
                "items": 0,
                "extracted": 0,
                "reproducible": 0,
                "internal_replications": 0,
                "independent_survivors": 0,
                "failed_or_misleading": 0,
                "max_evidence_tier": -1,
            },
        )
        row["items"] = int(row.get("items", 0)) + 1
        row["extracted"] = int(row.get("extracted", 0)) + int(item.get("status") == "EXTRACTED")
        for field in ("reproducible", "internal_replications", "independent_survivors"):
            row[field] = int(row.get(field, 0)) + int(bool(item.get(field)))
        row["failed_or_misleading"] = int(row.get("failed_or_misleading", 0)) + int(
            item.get("status") == "EXTRACTION_FAILED"
            or bool(item.get("marketing"))
            or bool(item.get("data_leakage"))
        )
        row["max_evidence_tier"] = max(
            integer(row.get("max_evidence_tier"), -1),
            integer(item.get("evidence_tier"), -1),
        )
    return reputation


def _emergence_watch(
    previous: Mapping[str, object], items: Sequence[Mapping[str, object]]
) -> tuple[dict[str, list[str]], list[dict[str, object]]]:
    sources = {
        str(mechanism): {str(source) for source in raw if source}
        for mechanism, raw in previous.items()
        if isinstance(raw, list)
    }
    for item in items:
        mechanism = re.sub(r"\s+", " ", str(item.get("mechanism", "")).strip().casefold())
        source = str(item.get("source", "")).strip()
        if mechanism and source:
            sources.setdefault(mechanism, set()).add(source)
    serial = {mechanism: sorted(names) for mechanism, names in sources.items()}
    emergent = [
        {"mechanism": mechanism, "independent_sources": names, "source_count": len(names)}
        for mechanism, names in serial.items()
        if len(names) >= 2
    ]
    emergent.sort(key=lambda row: (-integer(row.get("source_count")), str(row["mechanism"])))
    return serial, emergent


def extraction_prompt(item: Mapping[str, object], content: str, mission_set: Sequence[str]) -> str:
    """Prompt only over retrieved evidence; the model may not invent unseen transcript content."""
    return f"""You are the existing GPT Hunter's unified extraction stage.
MISSIONS: {", ".join(mission_set)}
SOURCE: {item.get("url")}
TITLE: {item.get("title")}
TRANSCRIPT_STATE: {item.get("transcript_state", "DESCRIPTION_ONLY")}

Return JSON only with keys mechanism, economic_rationale, hypothesis, actors, constraint, signal,
entry, exit, horizon, state, sizing, leverage, portfolio, execution, costs, capacity, data,
validation, failures, performance_claim, evidence_class, transferable, falsifier, entities,
relationships, capability_gaps, open_questions, descendant_hypotheses, reproducible, new_sources,
component_assets, failure_cause, emergence_class, regional_terms, combine_with_internal,
research_system, discovery_process, testing_process, data_pipeline, superior_capabilities,
internal_analogue, measurable_gap, replication_plan, source_license, mt5_experiment,
regime_hypothesis, activation_rule, reduced_rule, hibernation_rule and unconditional_control.
Use null when the source does not specify them. A regime is part of the
hypothesis, must be observable point-in-time and frozen before OOS, and creates an additional
counted trial. Always retain the unconditional strategy as a separately counted control; never
discover a winning regime on the holdout and relabel it as preregistered.
Evidence class must be one of MARKETING_CLAIM,
SCREENSHOT_SELECTED_RESULT, BACKTEST, FORWARD_PAPER_TRADING, LIVE_BROKER_EXCHANGE,
INDEPENDENTLY_VERIFIABLE, INSTITUTIONAL_AUDITED. Preserve hidden leverage, selection, capacity,
cost and drawdown concerns explicitly. A failed whole strategy may still yield components.
The source is an EXTERNAL PRIOR. Do not upgrade evidence, infer unseen text, or recommend promotion.
For a creator or research-system source, mine HOW the work is done as deeply as WHAT it claims:
discovery process, data acquisition, experiment design, negative-result memory, validation,
portfolio/execution use and self-improvement. Identify atomic capabilities that appear better than
the desk's current analogue and specify a measurable challenger. Convert useful material into a
falsifiable replication, component test, data acquisition or explicit rejection; a reading-list
summary is not completion and an external threshold never becomes an internal gate.

VENUE LAW: convert only into hypotheses for instruments executable through the dynamically
discovered Fusion Markets MT5 catalogue. Crypto/on-chain material is admissible only as a stamped
explanatory feature for a named Fusion-executable instrument; never create a Binance, Bybit, OKX,
Hyperliquid or other crypto-exchange strategy. Cost tests must use the target MT5 symbol's actual
point-in-time spread, commission, swap/financing, slippage, latency, capacity and session rules.
Preserve source-code and dataset links in source_code_links and new_sources. Generic news, price
predictions, lifestyle, affiliate reviews and motivation do not qualify as research sources unless
this retrieved item contains a deterministic falsifiable mechanism.

If and only if the mechanism has an exact executable analogue in the existing MT5 research
factory, mt5_experiment must be an object with family, side (LONG or SHORT) and param_overrides.
The only family names currently accepted are d1_trend_pullback, d1_swing_break, h4_momentum,
h4_vol_break, d1_inside, macro_gold_yield, gold_dxy_shock, asia_meanrev and
london_ny_breakout. Do not force a novel mechanism into a vaguely similar family: use null and
name the missing implementation or data in measurable_gap. Code under AGPL or another reciprocal
licence may be studied as public evidence, but must not be copied into this repository; specify an
independent clean-room replication instead.

RETRIEVED CONTENT:
{content[:50000]}
"""


def parse_extraction(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if "```" in candidate:
        blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.S)
        candidate = blocks[0] if blocks else candidate
    try:
        value = json.loads(candidate)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def run(
    sources: Sequence[Source],
    state: dict[str, Any],
    ask: Callable[[str], str],
    *,
    getter: Callable[[str], bytes] = fetch,
    max_new_per_source: int = 10,
    max_transcript_retries_per_run: int = 2,
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    watch_timestamp = now.isoformat()
    seen = set(state.get("seen", []))
    retry_state = dict(state.get("transcript_retry", {}))
    retries_attempted = 0
    processed, failures, discovered_sources = [], [], set(state.get("discovered_sources", []))
    for source in sources:
        try:
            items = discover(source, getter)
        except Exception as exc:  # each source is an independent acquisition path
            failures.append({"source": source.name, "stage": "DISCOVER", "error": str(exc)})
            continue
        for item in items[:max_new_per_source]:
            url = str(item["url"])
            dedupe_key = _item_identity(item)
            if dedupe_key in seen:
                continue
            mission_set = missions(item)
            content = str(item.get("description", ""))
            if "VIDEO_TRANSCRIPT" in mission_set:
                prior = retry_state.get(dedupe_key, {})
                due_raw = prior.get("next_retry_at") if isinstance(prior, Mapping) else None
                try:
                    due = datetime.fromisoformat(str(due_raw)) if due_raw else None
                except ValueError:
                    due = None
                if due and due > now:
                    continue
                if prior and retries_attempted >= max_transcript_retries_per_run:
                    continue
                if prior:
                    retries_attempted += 1
                # THE CALLER HALF OF R0466. This handler used to flatten every failure of the
                # WATCH-PAGE fetch to UNAVAILABLE, so hardening youtube_transcript alone would
                # have fixed nothing: a 403 on the watch page never reached it and still read as
                # "this video has no captions" (the L1.60 invisible-attrition shape -- a helper
                # that starts distinguishing into a caller that does not).
                try:
                    transcript = youtube_transcript(getter(url), getter)
                except OSError as exc:
                    transcript = _refused(exc, "watch page")
                except Exception as exc:
                    transcript = {"transcript_state": TRANSCRIPT_UNREADABLE, "text": "",
                                  "reason": f"watch page unusable: {type(exc).__name__}: {exc}"}
                item.update(transcript)
                content = str(transcript.get("text") or content)
                if item.get("transcript_state") in TRANSCRIPT_UNKNOWN_STATES:
                    attempts = integer(prior.get("attempts"), default=0) + 1
                    delay_hours = min(24 * 7, 6 * (2 ** min(attempts - 1, 5)))
                    retry_state[dedupe_key] = {
                        "attempts": attempts,
                        "next_retry_at": (now + timedelta(hours=delay_hours)).isoformat(),
                        "last_state": item.get("transcript_state"),
                        "http_status": item.get("http_status"),
                    }
                    processed.append(
                        {
                            **item,
                            "first_seen_at": watch_timestamp,
                            "missions": mission_set,
                            "mission": mission_set[0],
                            "status": "TRANSCRIPT_RETRY_PENDING",
                            "mechanism": "",
                            "evidence_tier": -1,
                            "canonical_item_id": dedupe_key,
                        }
                    )
                    continue
                retry_state.pop(dedupe_key, None)
            seen.add(dedupe_key)
            prompt = extraction_prompt(item, content, mission_set)
            try:
                extracted = parse_extraction(ask(prompt))
            except Exception as exc:
                extracted = None
                failures.append(
                    {"source": source.name, "url": url, "stage": "EXTRACT", "error": str(exc)}
                )
            if extracted is None:
                # Keep the source item and transcript state. An extraction failure must remain
                # retryable and cannot become a false clean result.
                processed.append(
                    {
                        **item,
                        "first_seen_at": watch_timestamp,
                        "missions": mission_set,
                        "mission": mission_set[0],
                        "status": "EXTRACTION_FAILED",
                        "mechanism": "",
                        "evidence_tier": -1,
                    }
                )
                continue
            processed.append(
                {
                    **item,
                    **extracted,
                    "first_seen_at": watch_timestamp,
                    "missions": mission_set,
                    "mission": mission_set[0],
                    "status": "EXTRACTED",
                    "authority": "EXTERNAL_PRIOR_ONLY",
                    "evidence_tier": evidence_tier(extracted.get("evidence_class")),
                    "canonical_item_id": dedupe_key,
                }
            )
            for found in (
                extracted.get("new_sources", [])
                if isinstance(extracted.get("new_sources"), list)
                else []
            ):
                if _qualified_related_source(extracted):
                    discovered_sources.add(str(found))
    previous_reputation = state.get("source_reputation", {})
    if not isinstance(previous_reputation, Mapping):
        previous_reputation = {}
    reputation = _update_reputation(previous_reputation, processed)
    previous_mechanisms = state.get("mechanism_sources", {})
    if not isinstance(previous_mechanisms, Mapping):
        previous_mechanisms = {}
    mechanism_sources, emergent = _emergence_watch(previous_mechanisms, processed)
    return {
        "watch_timestamp": watch_timestamp,
        "items": processed,
        "failures": failures,
        "state": {
            "seen": sorted(seen),
            "discovered_sources": sorted(discovered_sources),
            "source_reputation": reputation,
            "mechanism_sources": mechanism_sources,
            "transcript_retry": retry_state,
        },
        "source_reputation": reputation,
        "emergence_watch": emergent,
        "source_coverage": source_coverage(sources),
        "missions": [
            "VIDEO_TRANSCRIPT",
            "EXTREME_RETURN",
            "PUBLIC_STRATEGY",
            "ELITE_EXTERNAL_INTELLIGENCE",
        ],
        "conversion_law": (
            "discover -> canonical ID dedupe -> extract -> MT5/Fusion hypothesis -> preregister -> "
            "cost-aware validate -> untouched forward shadow -> survivor or negative knowledge -> "
            "portfolio marginal contribution -> reputation update"
        ),
        "venue_scope": "MT5_FUSION_ONLY",
        "k_miner_replaced": False,
    }


def load_sources(path: Path, discovered_sources: Sequence[object] = ()) -> list[Source]:
    doc = json.loads(path.read_text("utf-8"))
    sources = [
        Source(
            str(r["name"]),
            str(r["url"]),
            str(r["kind"]),
            str(r.get("language", "unknown")),
            str(r.get("surface", r["kind"])),
        )
        for r in doc.get("sources", [])
        if isinstance(r, dict)
    ]
    def identity(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.casefold().removeprefix("www.")
        if host in {"youtube.com", "m.youtube.com"}:
            return f"youtube:{parsed.path.rstrip('/').casefold()}"
        return urllib.parse.urlunparse(
            (parsed.scheme.casefold(), host, parsed.path.rstrip("/"), "", parsed.query, "")
        )

    known = {identity(source.url) for source in sources}
    for raw in discovered_sources:
        url = str(raw).strip()
        parsed = urllib.parse.urlparse(url)
        source_id = identity(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or source_id in known:
            continue
        is_youtube = parsed.netloc.casefold().removeprefix("www.") in {
            "youtube.com",
            "m.youtube.com",
        } and parsed.path.startswith(("/@", "/channel/"))
        sources.append(
            Source(
                name=f"discovered:{parsed.netloc}",
                url=url,
                kind="youtube" if is_youtube else "site",
                language="unknown",
                surface="discovered",
            )
        )
        known.add(source_id)
    return sources
