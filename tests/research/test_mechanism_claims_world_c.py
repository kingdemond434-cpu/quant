"""The claim reader's last twelve gap languages: told apart, read, mapped, nothing else moved."""
# ruff: noqa: RUF001
from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from libs.research import mechanism_claims as mc
from libs.research import mechanism_claims_world_c as mcc

#: One London-session gold claim per language: a quantity, a direction and a horizon.
SENTENCES = {
    "bg": "Златото обикновено се покачва след отварянето на лондонската сесия и дневният тренд "
          "продължава, като това е често.",
    "sr": "Злато обично расте након отварања лондонске сесије, а дневни тренд се наставља.",
    "kk": "Алтын әдетте Лондон сессиясы ашылғаннан кейін өседі және күнделікті тренд жалғасады.",
    "mn": "Лондонгийн сесс нээгдсэний дараа алтны үнэ ихэвчлэн өснө, өдөр тутмын тренд "
          "үргэлжилнэ.",
    "az": "Qızıl adətən London sessiyasının açılışından sonra yüksəlir və gündəlik trend davam "
          "edir.",
    "uz": "Oltin odatda London sessiyasi ochilishidan keyin o'sadi va kunlik trend davom etadi.",
    "et": "Kuld tavaliselt tõuseb pärast Londoni sessiooni avamist ja päevane trend jätkub.",
    "lt": "Auksas paprastai kyla po Londono sesijos atidarymo, ir dienos tendencija tęsiasi, nes "
          "nuotaika gerėja.",
    "lv": "Zelts parasti kāpj pēc Londonas sesijas atvēršanas, un dienas trends turpinās.",
    "hr": "Zlato obično raste nakon otvaranja londonske sesije, a dnevni trend se nastavlja.",
    "sk": "Zlato zvyčajne rastie po otvorení londýnskej seansy a denný trend pokračuje, keď je trh "
          "pokojný.",
    "af": "Goud styg gewoonlik ná die opening van die Londense sessie en die daaglikse tendens "
          "hou aan.",
}


@pytest.mark.parametrize("lang", sorted(SENTENCES))
def test_each_language_is_told_apart_and_yields_one_gold_long_claim(lang: str) -> None:
    text = SENTENCES[lang]
    assert mc.language_of(text) == lang
    claims = mc.extract(text)["claims"]
    assert len(claims) == 1, lang
    assert claims[0]["lang"] == lang and claims[0]["instruments"]["analogues"] == ["XAUUSD"]
    assert mc._bucket(mc._DIR_BUCKET_TERMS, claims[0]["direction"]) == "long", lang


#: Neighbours the new detectors sit beside: each keeps its reading.
NEIGHBOURS = [
    ("Золото обычно растёт после открытия Лондона, и дневной тренд продолжается.", "ru"),
    ("Золото зазвичай зростає після відкриття Лондона, і денний тренд триває.", "uk"),
    ("Altın genellikle Londra açılışından sonra yükselir ve günlük trend devam eder.", "tr"),
    ("Złoto zwykle rośnie po otwarciu Londynu i trend dzienny jest kontynuowany.", "pl"),
    ("Zlato obvykle roste po otevření londýnské seance a denní trend pokračuje.", "cs"),
    ("Goud stijgt vaak na de opening van Londen en de trend zet door.", "nl"),
    ("Gold steigt meist nach der Londoner Eröffnung und der Trend setzt sich fort.", "de"),
    ("Die Kurse steigen meist nach der Eröffnung und der Trend setzt sich fort.", "de"),
    ("O ouro sobe após a abertura de Londres e as posições continuam no dia.", "pt"),
    ("Este año el oro sube después de la apertura de Londres y la tendencia continúa.", "es"),
    ("L'or monte souvent après l'ouverture de Londres et la tendance continue dans la séance.",
     "fr"),
    ("Guld brukar stiga efter öppningen i London och trenden fortsätter.", "sv"),
    ("Giá vàng thường tăng sau khi phiên London mở cửa.", "vi"),
    ("plain english sentence about gold", "en"),
]


@pytest.mark.parametrize(("text", "lang"), NEIGHBOURS)
def test_languages_already_read_keep_their_reading(text: str, lang: str) -> None:
    assert mc.language_of(text) == lang


@pytest.mark.parametrize("text", [
    "El precio de la nafta sube cada semana en Buenos Aires.",   # petrol at the pump
    "Cena nafty v Praze roste každý týden.",                     # Czech diesel
])
def test_homographs_never_name_oil(text: str) -> None:
    assert "XTIUSD" not in mc.resolve_instruments(text.lower())["analogues"], text


def test_vocabulary_floor_locale_buckets_and_no_invisible_source_characters() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"))
    import deep_forest_miner as dfm
    for lang, (q, d, h) in mcc.VOCAB.items():
        assert lang in mc.LANGUAGES and lang in dfm._LOCALE, lang
        assert len(q) >= 25 and len(d) >= 15 and len(h) >= 14, lang
    directions = {t for _, d, _ in mcc.VOCAB.values() for t in d}
    assert set(mcc.DIR_BUCKETS["long"] + mcc.DIR_BUCKETS["short"]) <= directions
    assert not set(mcc.DIR_BUCKETS["long"]) & set(mcc.DIR_BUCKETS["short"])
    src = Path(mcc.__file__).read_text(encoding="utf-8")
    assert not [c for c in src if unicodedata.category(c) == "Cf"]
