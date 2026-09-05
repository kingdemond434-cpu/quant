"""The world crawler's own frontier walks every region's forest, in every script.

The deep-forest miner reaches ground by ROUTE; the crawler reaches it by LINK. These tests pin
that the crawler's seeds start in every region and that its mechanism vocabulary annotates a
page in Vietnamese, Thai, Polish, Turkish, Arabic ... with what it is ABOUT -- and that no seed
names a crypto-exchange venue.
"""
# ruff: noqa: RUF001, E501  -- fixtures are real prose in many scripts
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import world_crawler as wc  # noqa: E402

from libs.research import mechanism_claims as mc  # noqa: E402

_REGION_HOSTS = {
    "jp": "kabutan.jp", "kr": "paxnet.co.kr", "tw": "ptt.cc", "hk": "etnet.com.hk", "sg": "hardwarezone.com.sg",
    "vn": "f319.com", "th": "pantip.com", "id": "kontan.co.id", "my": "i3investor.com", "ph": "pinoyinvestor.com",
    "in": "tradingqna.com", "au": "hotcopper.com.au", "nz": "sharetrader.co.nz", "sa": "arabictrader.com",
    "tr": "bloomberght.com", "il": "globes.co.il", "za": "moneyweb.co.za", "ng": "nairametrics.com",
    "ke": "businessdailyafrica.com", "eg": "cbe.org.eg", "ma": "bkam.ma", "us": "elitetrader.com",
    "gb": "trade2win.com", "ca": "bankofcanada.ca", "de": "wallstreet-online.de", "fr": "boursorama.com",
    "it": "finanzaonline.com", "es": "x-trader.net", "nl": "iex.nl", "se": "riksbank.se", "no": "norges-bank.no",
    "dk": "nationalbanken.dk", "fi": "suomenpankki.fi", "pl": "stockwatch.pl", "cz": "cnb.cz", "hu": "mnb.hu",
    "ua": "bank.gov.ua", "ru": "mfd.ru", "br": "infomoney.com.br", "mx": "eleconomista.com.mx", "cl": "cochilco.cl",
    "ar": "rava.com", "institutional": "bis.org",
}


def test_seeds_start_in_every_region_and_never_name_a_forbidden_venue() -> None:
    hosts = {urlparse(u).netloc.lower() for u in wc.SEEDS}
    missing = [r for r, h in _REGION_HOSTS.items() if not any(x == h or x.endswith("." + h) for x in hosts)]
    assert not missing, f"no seed for {missing}"
    for url in wc.SEEDS:
        assert mc.forbidden_venue(url) is None, url
        assert url.startswith("https://") or url.startswith("http://")
    assert len(set(wc.SEEDS)) >= 150


def test_mechanism_vocabulary_annotates_pages_in_every_script() -> None:
    cases = (
        ("vi", "Giá vàng phá vỡ đỉnh tuần, tính mùa vụ và tương quan với dòng tiền khối ngoại.", {"breakout", "seasonality", "correlation", "positioning"}),
        ("th", "ทองคำทะลุแนวต้าน ความผันผวนสูง ต่างชาติซื้อ ดอกเบี้ย ธปท", {"breakout", "volatility", "positioning", "policy"}),
        ("pl", "Złoto po wybiciu, zmienność rośnie, decyzja RPP o stopach procentowych, sezonowość.", {"breakout", "volatility", "policy", "seasonality"}),
        ("tr", "Altın kırılım sonrası oynaklık arttı, TCMB faiz kararı, ihracat verisi.", {"breakout", "volatility", "policy", "flow"}),
        ("ar", "الذهب اختراق المقاومة، تذبذب مرتفع، البنك المركزي فائدة، مخزون النفط", {"breakout", "volatility", "policy", "inventory"}),
        ("he", "פריצה של הזהב, תנודתיות גבוהה, ריבית בנק ישראל, מתאם", {"breakout", "volatility", "policy", "correlation"}),
        ("pt", "Ouro rompimento, volatilidade, decisão do Copom sobre a Selic, safra de soja e exportações.", {"breakout", "volatility", "policy", "inventory", "flow"}),
        ("sv", "Guld utbrott, volatilitet, Riksbanken räntebesked, säsong", {"breakout", "volatility", "policy", "seasonality"}),
        ("id", "Emas penembusan resistance, volatilitas naik, suku bunga Bank Indonesia, ekspor", {"breakout", "volatility", "policy", "flow"}),
        ("hi", "सोना ब्रेकआउट, वोलैटिलिटी, आरबीआई ब्याज दर, निर्यात", {"breakout", "volatility", "policy", "flow"}),
        ("zh-Hant", "黃金突破，波動率上升，央行升息，庫存下降，外資籌碼", {"breakout", "volatility", "policy", "inventory", "positioning"}),
        ("uk", "Золото пробій, волатильність, НБУ ставка, експорт зерна", {"breakout", "volatility", "policy", "flow"}),
    )
    for lang, text, expected in cases:
        page = wc.read_page(f"<html><body><p>{text}</p></body></html>".encode(), "https://x.test/")
        assert expected <= set(page["patterns"]), (lang, page["patterns"])


def test_timeframe_tokens_are_read_in_other_scripts() -> None:
    page = wc.read_page("<html><body>日線 と 週足、분봉、intradía、nến ngày、รายวัน</body></html>".encode(),
                        "https://x.test/")
    assert {"日線", "週足", "분봉", "INTRADÍA", "NẾN NGÀY", "รายวัน"} <= set(page["timeframes"])


def test_a_world_forest_page_is_a_story_row_with_the_pair_it_moves() -> None:
    raw = ("<html lang='tr'><title>TCMB</title><body><p>Altın ons fiyatı günlük direnç kırılımı sonrasında "
           "yükseliyor ve dolar/TL merkez bankası faiz kararı sonrası gün içi düşüyor.</p></body></html>").encode()
    page = wc.read_page(raw, "https://www.bloomberght.com/x")
    assert page["claims"] and "USDTRY" in page["symbols"] and "XAUUSD" in page["symbols"]
    row = wc.to_discovery("https://www.bloomberght.com/x", page, "deadbeef")
    assert row and row["kind"] == "story" and row["claims"][0]["lang"] == "tr"
