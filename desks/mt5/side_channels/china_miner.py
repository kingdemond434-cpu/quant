"""China market intelligence miner.

Scrapes Chinese financial platforms (Bilibili, Zhihu, East Money)
for trading ideas and market sentiment.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "china"
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "zhihu": "https://www.zhihu.com/search?type=content&q=外汇交易策略",
    "eastmoney": "https://so.eastmoney.com/web/s?keyword=外汇策略",
}

SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    # Chinese platform names may use different notation
    mappings = {"黄金": "XAUUSD", "欧元": "EURUSD", "英镑": "GBPUSD", "日元": "USDJPY",
                "澳元": "AUDUSD", "加元": "USDCAD", "瑞郎": "USDCHF", "纽元": "NZDUSD"}
    found = []
    for cn, en in mappings.items():
        if cn in text:
            found.append(en)
    return found

def mine_china() -> list[dict]:
    discoveries = []
    for source, url in SOURCES.items():
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "Accept-Language": "zh-CN,zh;q=0.9"},
                              timeout=15)
            resp.raise_for_status()
            content = re.sub(r'<[^>]+>', ' ', resp.text)[:2000]
            syms = _extract_symbols(content)

            if syms:
                discoveries.append({
                    "source": "china",
                    "platform": source,
                    "url": url,
                    "symbols": syms,
                    "confidence": 0.2,
                })
        except Exception:
            continue
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_china()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"china: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
