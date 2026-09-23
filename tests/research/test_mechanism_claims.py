"""The world claim grammar: one shallow grammar, twenty-six languages, one instrument map.

What is pinned:

  * a sentence naming a quantity, a direction and a horizon is a claim in EVERY language the
    desk mines, and the instrument it names maps to the Fusion symbol -- never a guess;
  * the language detector separates the scripts and the Latin-script languages on function
    words, so each forest is read with its own vocabulary;
  * every alias' first candidate is a symbol Fusion quotes (universe.json); anything else is a
    mechanism-class transfer note, and a claim that maps to nothing is dropped AND counted;
  * crypto-exchange venues are dropped and counted in every script;
  * indirect channels (a central bank, a harvest, a customs table) land on the pair they move
    and the claim says `channel="indirect"`; the mechanism key folds the same story told twice;
  * the bandit resolves every region-cluster source to the external arm.
"""
# ruff: noqa: RUF001, E501  -- fixtures are real prose in many scripts
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import mechanism_claims as mc
from libs.research.bandit import ARMS, SOURCE_ARM, arm_of

_ROOT = Path(__file__).resolve().parents[2]
_UNIVERSE = {str(k).upper() for k in
             json.loads((_ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json").read_text("utf-8"))}

#: (language, sentence, expected analogue or indirect target)
_FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("zh", "夜盘开盘后前30分钟如果放量突破日内高点，顺势做多沪金持有到收盘前平仓，胜率62%。", "XAUUSD"),
    ("zh-Hant", "黃金在美盤開盤後一小時內常見反彈，逢低做多，隔日回檔再出場。", "XAUUSD"),
    ("ja", "ドル円は五十日の仲値にかけて日中ドル高になりやすく、仲値後に反落する。", "USDJPY"),
    ("ko", "원달러 환율은 월말 수출업체 네고 물량으로 하락 압력을 받는다.", "USDKRW"),
    ("ru", "Нефть растет после публикации запасов EIA внутри дня, если запасы падают, покупаю лонг.", "XTIUSD"),
    ("uk", "Золото після лондонського фіксингу часто дає відкат протягом години, купую лонг.", "XAUUSD"),
    ("vi", "Giá vàng thường tăng mạnh sau khi phá vỡ đỉnh tuần, tôi mua vào và chốt lời trong phiên.", "XAUUSD"),
    ("th", "ทองคำมักจะเด้งกลับตัวหลังจากหลุดแนวรับในช่วงเช้า ผมซื้อและปิดสถานะภายในวัน", "XAUUSD"),
    ("id", "Rupiah melemah saat Bank Indonesia tidak intervensi pada sesi pagi dan asing jual.", "USDIDR"),
    ("hi", "रुपया आरबीआई के हस्तक्षेप के बाद इंट्राडे मजबूत होता है, मैं डॉलर बेचता हूं।", "USDINR"),
    ("de", "Der DAX steigt nach dem Ausbruch über das Vortageshoch meist bis zum Handelsschluss weiter.", "GER40"),
    ("fr", "L'or rebondit souvent après le fixing de Londres dans l'heure qui suit, et le CAC 40 continue la tendance jusqu'à la clôture de la séance.", "XAUUSD"),
    ("it", "L'oro rimbalza spesso dopo la rottura del minimo giornaliero e il DAX prosegue il trend fino alla chiusura della seduta.", "XAUUSD"),
    ("es", "El oro suele rebotar después de la ruptura del mínimo diario y el Ibex continúa la tendencia hasta el cierre de la sesión.", "E35"),
    ("pt", "O ouro costuma subir após o rompimento da máxima do dia e o dólar cai quando o Copom sobe a Selic no fechamento do pregão.", "XAUUSD"),
    ("ar", "الذهب يرتفع بعد اختراق المقاومة اليومية وأبيع عند الإغلاق، والنفط يهبط خلال اليوم بعد قرار أوبك.", "XAUUSD"),
    ("tr", "Altın ons fiyatı günlük direnç kırılımı sonrasında yükseliyor ve dolar/TL merkez bankası faiz kararı sonrası gün içi düşüyor.", "USDTRY"),
    ("he", "הזהב עולה אחרי פריצה של ההתנגדות היומית ואני מוכר בסגירה, והדולר שקל יורד תוך יומי אחרי החלטת ריבית של בנק ישראל.", "USDILS"),
    ("pl", "Złoto rośnie po wybiciu dziennego oporu i sprzedaję na zamknięciu sesji, a złoty umacnia się w tygodniu po decyzji RPP o stopach.", "USDPLN"),
    ("nl", "Goud stijgt meestal na een uitbraak boven de dagelijkse weerstand en ik verkoop bij het slot van de handelsdag, terwijl de AEX vaak een week lang de trend vervolgt.", "NETH25"),
    ("sv", "Guld brukar stiga efter ett utbrott över dagens motstånd och jag säljer vid stängning, och kronan stärks ofta i en vecka efter Riksbankens räntebesked.", "USDSEK"),
    ("da", "Guld plejer at stige efter et udbrud over dagens modstand og jeg sælger ved lukning, og kronen styrkes ofte i en uge efter Nationalbankens rentebeslutning.", "XAUUSD"),
    ("no", "Gull pleier å stige etter et utbrudd over dagens motstand og jeg selger ved stenging, og kronen styrkes ofte i en uke etter Norges Banks rentebeslutning.", "XAUUSD"),
    ("fi", "Kulta nousee yleensä läpimurron jälkeen päivän vastuksen yli ja myyn päätöksessä, ja euro heikkenee usein viikon ajan EKP:n korkopäätöksen jälkeen.", "XAUUSD"),
    ("sw", "Bei ya dhahabu huwa inapanda baada ya kuvunja upinzani wa kila siku na ninauza wakati wa kufunga soko, na shilingi hudhoofika kwa wiki baada ya benki kuu kuingilia.", "XAUUSD"),
    ("en", "Gold tends to mean revert after the London fix within two hours when the daily range is already wide.", "XAUUSD"),
)


@pytest.mark.parametrize(("lang", "text", "target"), _FIXTURES, ids=[f[0] for f in _FIXTURES])
def test_a_claim_is_extracted_in_every_language_with_the_right_instrument(lang, text, target) -> None:
    assert mc.language_of(text) == lang
    claims = mc.extract_claims(text, universe=_UNIVERSE)
    assert claims, f"{lang}: no claim extracted"
    c = claims[0]
    assert c["lang"] == lang and c["quantities"] and c["direction"] and c["horizon"]
    inst = c["instruments"]
    assert target in inst["analogues"] or target in inst["indirect"], (lang, inst)
    assert c["channel"] in ("direct", "indirect") and c["mechanism_class"] in (*mc.MECHANISM_CLASSES, "other")
    assert len(c["mechanism_key"]) == 16 and len(c["claim_hash"]) == 12


def test_every_language_in_the_vocabulary_is_detectable_or_a_declared_fallback() -> None:
    assert len(mc.LANGUAGES) >= 26
    assert {"zh", "zh-Hant", "ja", "ko", "ru", "uk", "vi", "th", "id", "hi", "de", "fr", "it", "es",
            "pt", "ar", "tr", "he", "pl", "nl", "sv", "da", "no", "fi", "sw", "en"} <= set(mc.LANGUAGES)
    for lang, (q, d, h) in mc._VOCAB.items():
        assert len(q) >= 25 and len(d) >= 15 and len(h) >= 14, lang


def test_the_script_detector_separates_traditional_from_simplified_and_ukrainian_from_russian() -> None:
    assert mc.language_of("台指期在結算日前一週波動率上升，外資空單增加。") == "zh-Hant"
    assert mc.language_of("沪金夜盘开盘后放量突破。") == "zh"
    assert mc.language_of("Гривня зміцнюється, коли НБУ проводить інтервенції.") == "uk"
    assert mc.language_of("Золото после фиксинга дает откат.") == "ru"
    assert mc.language_of("plain english sentence about gold") == "en"
    assert mc.language_of("Tỷ giá tăng khi Ngân hàng Nhà nước can thiệp.") == "vi"


def test_forbidden_venues_are_dropped_and_counted_in_every_script() -> None:
    text = ("币安永续合约资金费率为正时做空黄金，日内套利。 "
            "업비트에서 금 선물 무기한 롱으로 매수하고 당일 청산한다. "
            "На бессрочных контрактах золото растет после фандинга внутри дня, лонг. "
            "Gold on the bitmex perpetual usually rallies after funding resets within the hour. "
            "Gold tends to mean revert after the London fix within two hours daily.")
    r = mc.extract(text, universe={"XAUUSD"})
    assert r["dropped_venue"] == 4
    assert len(r["claims"]) == 1 and r["claims"][0]["claim"].startswith("Gold tends")


def test_every_alias_first_candidate_is_a_symbol_fusion_quotes_and_transfers_say_which_class() -> None:
    """MAP ONLY TO SYMBOLS THAT EXIST (principal): the first candidate of every non-empty alias
    tuple is a name in universe.json; an empty tuple names the mechanism class it transfers to."""
    for aliases, cands, cls in mc.INSTRUMENT_ALIASES:
        assert aliases and cls
        if cands:
            assert cands[0].upper() in _UNIVERSE, (aliases[0], cands[0])
    for aliases, cands, note in mc.INDIRECT_CHANNELS:
        assert cands and all(c.upper() in _UNIVERSE for c in cands), (aliases[0], cands)
        assert "->" in note
    r = mc.resolve_instruments("코스피 선물 만기 주에 변동성이 상승한다", universe=_UNIVERSE)
    assert r["analogues"] == [] and r["transfer_only"] == ["코스피->indices (KRX)"]
    r2 = mc.resolve_instruments("nifty expiry day, bank nifty premium decays", universe=_UNIVERSE)
    assert r2["transfer_only"] and r2["transfer_only"][0].endswith("(NSE/BSE)")


def test_latin_aliases_are_word_bounded_so_gold_is_not_golden_and_dow_is_not_download() -> None:
    assert mc.resolve_instruments("the golden cross on the download page", universe=_UNIVERSE)["analogues"] == []
    assert mc.resolve_instruments("gold and the dow both rose", universe=_UNIVERSE)["analogues"] == ["XAUUSD", "US30"]
    assert mc.resolve_instruments("沪金期货夜盘", universe=_UNIVERSE)["analogues"] == ["XAUUSD"]


def test_indirect_channels_land_on_the_pair_they_move_and_mark_the_claim_indirect() -> None:
    r = mc.extract("The CBRT hike usually strengthens the lira for a week when positioning is short.",
                   universe=_UNIVERSE)
    c = r["claims"][0]
    assert c["instruments"]["analogues"] == ["USDTRY"] and c["channel"] == "direct"   # 'lira' names it
    r2 = mc.extract("Brazilian soy exports usually weaken the real over the month after the data.",
                    universe=_UNIVERSE)
    c2 = r2["claims"][0]
    assert c2["instruments"]["analogues"] == [] and c2["instruments"]["indirect"] == ["USDBRL"]
    assert c2["channel"] == "indirect" and c2["mechanism_class"] == "flow"
    assert any("soy" in ch for ch in c2["instruments"]["channels"])
    r3 = mc.extract("The Shanghai gold premium usually widens for a week after the PBoC fixing weakens.",
                    universe=_UNIVERSE)
    assert r3["claims"][0]["instruments"]["analogues"] == ["XAUUSD"]


def test_a_claim_that_maps_to_nothing_is_dropped_and_counted_not_summarised() -> None:
    r = mc.extract("The index usually rallies for a week after a breakout when volume expands.")
    assert r["claims"] == [] and r["dropped_unmappable"] == 1


def test_the_mechanism_key_folds_the_same_story_in_two_languages_and_separates_different_ones() -> None:
    en = mc.extract("Gold usually bounces within an hour after the London fix.", universe=_UNIVERSE)["claims"][0]
    ja = mc.extract("ゴールドはロンドン仲値の後、1時間で逆張りの反発が出やすい。", universe=_UNIVERSE)["claims"][0]
    assert en["mechanism_key"] == ja["mechanism_key"]
    other = mc.extract("Gold usually falls for a week after the London fix.", universe=_UNIVERSE)["claims"][0]
    assert other["mechanism_key"] != en["mechanism_key"]
    r = mc.extract("Gold usually bounces within an hour after the London fix. "
                   "Gold typically rebounds in the hour following the London fix.", universe=_UNIVERSE)
    assert len(r["claims"]) == 1 and r["duplicate_mechanisms"] == 1


def test_mechanism_classes_prefer_structure_over_the_generic_price_pattern() -> None:
    assert mc.mechanism_class("gold momentum breakout after the fomc rate decision") == "policy"
    assert mc.mechanism_class("copper falls when lme stocks rise, trend continues") == "inventory"
    assert mc.mechanism_class("breakout momentum continues") == "momentum"
    assert mc.mechanism_class("nothing here") == "other"
    c = mc.extract("Gold breakout momentum usually continues for a week after the daily high.",
                   universe=_UNIVERSE)["claims"][0]
    assert mc.claim_score(c) < mc.claim_score({**c, "mechanism_class": "policy"})


def test_stated_numbers_and_dates_are_read_in_other_languages_as_evidence_about_the_story() -> None:
    assert mc.performance("勝率62%、年率リターン85%、最大ドローダウン18%") == {"return_pct": 85.0, "drawdown_pct": 18.0,
                                                               "win_rate_pct": 62.0}
    assert mc.performance("Rendite 12,5 % pro Jahr, Drawdown 9 %")["drawdown_pct"] == 9.0
    assert mc.performance("승률 70% 손익비 1.8")["profit_factor"] == 1.8
    assert mc.stated_date("2026年9月3日の日銀会合後にドル円が反落した") == "2026-09-03"
    assert mc.stated_date("Am 15.08.2026 fiel Gold") == "2026-08-15"
    assert mc.stated_date("no date here") is None
    assert mc.extract("On 2026-08-15 gold fell for a week after the fix.", universe=_UNIVERSE)["claims"][0]["event_time"] == "2026-08-15"


def test_the_older_two_value_shape_still_works_for_its_callers() -> None:
    claims, dropped = mc.extract_claims_with_drops("币安永续合约资金费率为正时做空黄金，日内套利。 "
                                                   "Gold tends to mean revert after the London fix within two hours daily.")
    assert dropped == 1 and len(claims) == 1


def test_bandit_resolves_every_region_cluster_source_to_the_external_arm() -> None:
    clusters = ("jp", "kr", "tw_hk", "sea", "in", "south_asia", "anz", "mena", "africa", "west", "eu",
                "nordics", "east_eu", "ru", "latam", "institutional")
    for c in clusters:
        src = f"deep_forest_{c}"
        assert src in SOURCE_ARM and arm_of(src) == "external_screen" and arm_of(src) in ARMS
    assert arm_of("deep_forest") == "external_screen"
    assert arm_of("deep_forest_jp:note.com") == "external_screen"
