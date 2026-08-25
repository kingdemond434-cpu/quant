"""Central bank statement miner.

Scrapes central bank websites for policy statements, rate decisions,
and forward guidance that could impact FX markets.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "central_banks"
OUT.mkdir(parents=True, exist_ok=True)

BANKS = {
    "Fed": {"url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "currency": "USD"},
    "ECB": {"url": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html", "currency": "EUR"},
    "BoE": {"url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes", "currency": "GBP"},
    "BoJ": {"url": "https://www.boj.or.jp/en/mopo/mpmdeci/index.htm", "currency": "JPY"},
    "RBA": {"url": "https://www.rba.gov.au/monetary-policy/rba-board-minutes/", "currency": "AUD"},
    "RBNZ": {"url": "https://www.rbnz.govt.nz/monetary-policy/monetary-policy-decisions", "currency": "NZD"},
    "BoC": {"url": "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/", "currency": "CAD"},
    "SNB": {"url": "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions/decisions", "currency": "CHF"},
}

SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    return [s for s in SYMBOLS if s in text.upper()]

def _extract_policy_signals(text: str) -> list[str]:
    keywords = ["hawkish", "dovish", "rate hike", "rate cut", "tightening", "easing",
                "quantitative easing", "QE", "taper", "pause", "hold", "increase", "decrease",
                "inflation target", "full employment", "price stability", "forward guidance"]
    return [k for k in keywords if k.lower() in text.lower()]

def mine_central_banks() -> list[dict]:
    discoveries = []
    for bank, info in BANKS.items():
        try:
            resp = requests.get(info["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.raise_for_status()
            text = resp.text
            # Extract relevant content
            content = re.sub(r'<[^>]+>', ' ', text)[:2000]
            signals = _extract_policy_signals(content)
            syms = _extract_symbols(f"{bank} {info['currency']} {content}")

            if signals or syms:
                discoveries.append({
                    "source": "central_bank",
                    "bank": bank,
                    "currency": info["currency"],
                    "url": info["url"],
                    "policy_signals": signals,
                    "symbols": syms or [f"{info['currency']}USD"],
                    "confidence": min(1.0, len(signals) * 0.3),
                })
        except Exception:
            continue
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_central_banks()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"central_bank: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
