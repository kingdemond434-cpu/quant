"""Deterministic multilingual routing for public research text.

This is a conservative first reader, not a translator.  It recognizes scripts, named MT5
instruments and a small multilingual mechanism ontology; uncertain text is routed to a language
seat rather than silently treated as English.  Public-source miners use the native query tables
as seeds and extend them through their durable terminology ledger.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

RULE = ("preserve the original text; deterministic terms are hints, never evidence; route "
        "unknown language or meaning to a native understanding seat")
SOURCE_LAYERS = ("academic", "practitioner", "institutional", "regulatory", "code",
                 "retail_ecology", "archive", "media", "dataset", "source_graph")
GROUND_KIND_LAYER = {"paper": "academic", "journal": "academic", "interview": "practitioner",
                     "forum": "retail_ecology", "code": "code", "repository": "code",
                     "archive": "archive", "media": "media", "dataset": "dataset",
                     "institutional": "institutional", "regulatory": "regulatory"}

LANGUAGES = frozenset({"en", "zh", "ja", "ko", "ru", "es", "pt", "fr", "de", "it",
                       "ar", "fa", "tr", "pl", "uk", "hi", "bn", "ur", "vi", "th",
                       "id", "ms", "nl", "sv", "no", "da", "fi", "cs", "ro", "hu",
                       "el", "he", "sw", "am", "ka", "ug"})

@dataclass(frozen=True)
class Preservation:
    keep_fringe: bool = True
    keep_contradictory: bool = True
    keep_low_confidence: bool = True
    why: str = "credibility and predictive value are separate labels"

PRESERVE_FRINGE = Preservation()

@dataclass(frozen=True)
class Concept:
    concept_id: str
    mechanism_class: str = ""
    term: str = ""

@dataclass(frozen=True)
class Understanding:
    lang: str
    script: str
    confidence: float
    alternatives: tuple[tuple[str, float], ...]
    has_terminology: bool
    instruments: tuple[str, ...]
    concepts: tuple[Concept, ...]
    needs_seat: bool
    needs_seat_reason: str

_TERMS = {
    "en": {"breakout": ("breakout", "session_range_breakout"), "trend": ("trend", "trend_ma_cross"),
           "reversion": ("mean_reversion", "range_reversion"), "carry": ("carry", "carry"),
           "volatility": ("volatility", "volatility_transition"), "liquidity": ("liquidity", "liquidity_regime")},
    "zh": {"突破": ("breakout", "session_range_breakout"), "趋势": ("trend", "trend_ma_cross"),
           "均值回归": ("mean_reversion", "range_reversion"), "波动": ("volatility", "volatility_transition")},
    "ja": {"ブレイクアウト": ("breakout", "session_range_breakout"), "トレンド": ("trend", "trend_ma_cross"),
           "平均回帰": ("mean_reversion", "range_reversion"), "仲値": ("tokyo_fix", "fix_flow")},
    "ru": {"пробой": ("breakout", "session_range_breakout"), "тренд": ("trend", "trend_ma_cross"),
           "возврат к среднему": ("mean_reversion", "range_reversion")},
    "es": {"ruptura": ("breakout", "session_range_breakout"), "tendencia": ("trend", "trend_ma_cross"),
           "reversión": ("mean_reversion", "range_reversion")},
    "pt": {"rompimento": ("breakout", "session_range_breakout"), "tendência": ("trend", "trend_ma_cross")},
    "de": {"ausbruch": ("breakout", "session_range_breakout"), "trend": ("trend", "trend_ma_cross")},
    "fr": {"cassure": ("breakout", "session_range_breakout"), "tendance": ("trend", "trend_ma_cross")},
}
_NATIVE_BASE = {
    "en": "systematic trading strategy", "zh": "量化 交易 策略", "ja": "システムトレード 戦略",
    "ko": "퀀트 트레이딩 전략", "ru": "алгоритмическая торговая стратегия",
    "es": "estrategia cuantitativa", "pt": "estratégia quantitativa",
    "fr": "stratégie quantitative", "de": "quantitative handelsstrategie",
    "ar": "استراتيجية تداول كمية", "tr": "nicel alım satım stratejisi"}

def _script(text: str) -> tuple[str, str, float]:
    if re.search(r"[\u3040-\u30ff]", text): return "ja", "Japanese", .98
    if re.search(r"[\u4e00-\u9fff]", text): return "zh", "Han", .94
    if re.search(r"[\uac00-\ud7af]", text): return "ko", "Hangul", .98
    if re.search(r"[\u0400-\u04ff]", text): return "ru", "Cyrillic", .85
    if re.search(r"[\u0600-\u06ff]", text): return "ar", "Arabic", .72
    if re.search(r"[\u0370-\u03ff]", text): return "el", "Greek", .9
    return "en", "Latin", .6

def understand(text: str, *, universe: Iterable[str] | None = None) -> Understanding:
    raw = str(text or "")
    lang, script, conf = _script(raw)
    low = raw.lower()
    # Latin-language lexical overrides are intentionally conservative.
    scores = {k: sum(term in low for term in table) for k, table in _TERMS.items()
              if k not in {"zh", "ja", "ru"}}
    if script == "Latin" and scores and max(scores.values()) > 0:
        lang = max(scores, key=scores.get); conf = .78
    terms = _TERMS.get(lang, {})
    concepts = tuple(Concept(cid, fam, term) for term, (cid, fam) in terms.items()
                     if term.lower() in low)
    allowed = {str(x).upper() for x in (universe or ())}
    tokens = set(re.findall(r"\b[A-Z]{3,8}\b", raw.upper()))
    common = {"XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD",
              "USDCAD", "USDCHF", "US500", "NAS100", "US30", "XTIUSD", "XBRUSD", "UST10Y"}
    instruments = tuple(sorted(tokens & (allowed or common)))
    known = lang in _TERMS or lang in _NATIVE_BASE
    needs = (not known) or (not concepts and len(raw.split()) >= 8 and conf < .8)
    reason = ("no native terminology map" if not known else
              "meaning is not covered by deterministic terminology" if needs else "")
    alts = tuple((x, round(.15, 2)) for x in ("en", "es", "pt") if x != lang) if script == "Latin" else ()
    return Understanding(lang, script, conf, alts, known, instruments, concepts, needs, reason)

def native_queries(lang: str, layer: str = "practitioner", *, instrument: str = "",
                   limit: int = 6) -> list[str]:
    code = str(lang).split("-")[0].lower()
    base = _NATIVE_BASE.get(code)
    if not base or layer not in SOURCE_LAYERS:
        return []
    suffix = {"academic": "paper study", "practitioner": "rules backtest", "code": "source code",
              "archive": "archive historical", "dataset": "dataset", "media": "interview",
              "retail_ecology": "forum", "institutional": "research", "regulatory": "report",
              "source_graph": "authors citations"}[layer]
    seeds = [f"{base} {suffix}", f"{instrument} {base} {suffix}" if instrument else ""]
    return [x for x in seeds if x][:max(0, int(limit))]

def layers_unmeasured(lang: str) -> list[str]:
    return [] if str(lang).split("-")[0].lower() in _NATIVE_BASE else list(SOURCE_LAYERS)

def query_languages() -> tuple[str, ...]:
    return tuple(sorted(_NATIVE_BASE))

def query_coverage() -> dict[str, object]:
    return {"languages": len(_NATIVE_BASE), "layers": len(SOURCE_LAYERS),
            "cells": len(_NATIVE_BASE) * len(SOURCE_LAYERS)}

def languages_without_terminology(languages: Iterable[str]) -> list[str]:
    return sorted({str(x).split("-")[0].lower() for x in languages} - set(_TERMS))

COVERAGE = query_coverage()

