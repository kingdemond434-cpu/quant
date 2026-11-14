"""The claim reader's eight one-script languages: detected, read, mapped, nothing else moved."""
# ruff: noqa: RUF001
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from libs.research import mechanism_claims as mc
from libs.research import mechanism_claims_world_b as mcb

#: One London-session gold claim per language: a quantity, a direction and a horizon.
SENTENCES = {
    "am": "የወርቅ ዋጋ ከለንደን ሴሽን በኋላ ብዙ ጊዜ ይጨምራል፣ ዕለታዊ ትሬንድ ይቀጥላል።",
    "hy": "Ոսկին սովորաբար աճում է Լոնդոնի սեսիայի բացումից հետո, և օրական թրենդը շարունակվում է։",
    "ka": "ოქრო ჩვეულებრივ იზრდება ლონდონის სესიის გახსნის შემდეგ და დღიური ტრენდი გრძელდება.",
    "si": "ලන්ඩන් සැසිය විවෘත කිරීමෙන් පසු රත්තරන් මිල ඉහළ යයි, දෛනික ප්\u200dරවණතාව දිගටම පවතී.",
    "ne": "लन्डन सत्र खुलेपछि सुनको भाउ प्रायः बढ्छ र दैनिक ट्रेन्ड पनि जारी रहन्छ।",
    "km": "តម្លៃមាសជាធម្មតាកើនឡើងបន្ទាប់ពីវគ្គទីក្រុងឡុងដ៍បើក ហើយនិន្នាការប្រចាំថ្ងៃបន្ត។",
    "lo": "ລາຄາຄຳມັກຈະເພີ່ມຂຶ້ນຫຼັງຈາກຊ່ວງເວລາລອນດອນເປີດ ແລະແນວໂນ້ມລາຍວັນສືບຕໍ່.",
    "my": "လန်ဒန်ဖွင့်ချိန်ပြီးနောက် ရွှေဈေး များသောအားဖြင့် မြင့်တက်ပြီး နေ့စဉ်လမ်းကြောင်း "
          "ဆက်လက်ရှိသည်။",
}


@pytest.mark.parametrize("lang", sorted(SENTENCES))
def test_each_language_is_detected_and_yields_one_gold_long_claim(lang: str) -> None:
    text = SENTENCES[lang]
    assert mc.language_of(text) == lang
    claims = mc.extract(text)["claims"]
    assert len(claims) == 1, lang
    assert claims[0]["lang"] == lang and claims[0]["instruments"]["analogues"] == ["XAUUSD"]
    assert mc._bucket(mc._DIR_BUCKET_TERMS, claims[0]["direction"]) == "long", lang


def test_hindi_and_marathi_keep_their_reading_next_to_nepali() -> None:
    assert mc.language_of("लंदन सेशन के बाद सोना अक्सर तेजी में रहता है और ट्रेंड जारी है।") == "hi"
    assert mc.language_of("कुछ लोग कहते हैं सोना ऊपर जाएगा और ट्रेंड जारी है।") == "hi"
    assert mc.language_of("लंडन सत्रानंतर सोन्याचा भाव वाढतो आणि दैनिक ट्रेंड सुरू राहतो असे "
                          "दिसते आहे.") == "mr"


@pytest.mark.parametrize(("text", "sym"), [
    ("भाई ध्यान से सुनना और फिर ट्रेड करना", "XAUUSD"),   # Hindi "listen", not gold
    ("ຄຳເວົ້າຂອງລາວແມ່ນຖືກຕ້ອງ", "XAUUSD"),            # Lao "word", not gold
    ("ငါတို့ အိမ်ရွှေ့မယ်", "XAUUSD"),                  # Myanmar "to move", not gold
    ("ዋጋው 500 ብር ነው", "XAGUSD"),                      # the birr, not silver
])
def test_homographs_of_instrument_words_stay_negative(text: str, sym: str) -> None:
    assert sym not in mc.resolve_instruments(text)["analogues"], text


def test_khmer_london_is_not_a_long_direction() -> None:
    claim = mc.extract(SENTENCES["km"])["claims"][0]
    assert all("ឡុង" not in d for d in claim["direction"])


def test_each_script_ends_its_own_sentences() -> None:
    # Ethiopic, Armenian, Myanmar and Khmer full stops: two claims are two sentences
    for lang in ("am", "hy", "my", "km"):
        assert len(mc._SPLIT.split(SENTENCES[lang] + " " + SENTENCES[lang])) >= 2, lang


def test_vocabulary_floor_locale_and_no_invisible_source_characters() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"))
    import deep_forest_miner as dfm
    for lang, (q, d, h) in mcb.VOCAB.items():
        assert lang in mc.LANGUAGES and lang in dfm._LOCALE, lang
        assert len(q) >= 25 and len(d) >= 15 and len(h) >= 14, lang
    directions = {t for _, d, _ in mcb.VOCAB.values() for t in d}
    assert set(mcb.DIR_BUCKETS["long"] + mcb.DIR_BUCKETS["short"]) <= directions
    # the independent-review screen routes any format character to the manual path
    src = Path(mcb.__file__).read_text(encoding="utf-8")
    assert not [c for c in src if unicodedata.category(c) == "Cf"]


#: The thirteen-language and base readings the additions must not move (re-run here).
BASE = [
    ("Este año el oro sube después de la apertura de Londres y la tendencia continúa.", "es"),
    ("Покупаем золото на пробое, когда доходность выше 2σ, держим неделю.", "ru"),
    ("黄金在伦敦开盘后上涨，当波动率超过2σ时做多，持有一周。", "zh"),
    ("ราคาทองมักขึ้นหลังตลาดลอนดอนเปิด และแนวโน้มรายวันยังคงดำเนินต่อ", "th"),
    ("قیمت طلا بعد از باز شدن سشن لندن معمولا صعود می\u200cکند و روند روزانه ادامه دارد.", "fa"),
    ("Ο χρυσός συνήθως ανεβαίνει μετά το άνοιγμα της συνεδρίασης του Λονδίνου και η "
     "ημερήσια τάση συνεχίζεται.", "el"),
]


@pytest.mark.parametrize(("text", "lang"), BASE)
def test_languages_already_read_keep_their_reading(text: str, lang: str) -> None:
    assert mc.language_of(text) == lang
    assert len(mc.extract(text)["claims"]) == 1
