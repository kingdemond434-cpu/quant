"""Korea market intelligence miner.

Scrapes Korean financial platforms for trading ideas and market sentiment.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "korea"
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "naver_finance": "https://finance.naver.com/search/search.naver?query=외환+전략",
    " investing_kr": "https://kr.investing.com/search/?q=외환+전략",
}

SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    mappings = {"금": "XAUUSD", "유로": "EURUSD", "파운드": "GBPUSD", "엔화": "USDJPY",
                "호주달러": "AUDUSD", "캐나다달러": "USDCAD", "스위스프랑": "USDCHF", "뉴질랜드달러": "NZDUSD"}
    found = []
    for kr, en in mappings.items():
        if kr in text:
            found.append(en)
    return found

def mine_korea() -> list[dict]:
    discoveries = []
    for source, url in SOURCES.items():
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"},
                              timeout=15)
            resp.raise_for_status()
            content = re.sub(r'<[^>]+>', ' ', resp.text)[:2000]
            syms = _extract_symbols(content)

            if syms:
                discoveries.append({
                    "source": "korea",
                    "platform": source,
                    "url": url,
                    "symbols": syms,
                    "confidence": 0.2,
                })
        except Exception:
            continue
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_korea()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"korea: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
