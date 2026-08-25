"""Weather data miner for commodities.

Scrapes weather data for agricultural/energy commodity impacts.
Extreme weather = supply shocks = price moves in wheat, coffee, natural gas.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "weather"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Weather events that move commodities
WEATHER_SOURCES = {
    "noaa_hurricanes": "https://www.nhc.noaa.gov/CurrentSummaries.json",
    "drought_monitor": "https://droughtmonitor.unl.edu/Data/DmDataTokenDownload.aspx",
}


def mine_weather() -> list[dict]:
    """Check for extreme weather events affecting commodities."""
    discoveries = []

    # Check NOAA for active hurricanes (affect natural gas, oil)
    try:
        resp = requests.get(WEATHER_SOURCES["noaa_hurricanes"], headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            active = data.get("activeStorms", [])
            if active:
                for storm in active:
                    name = storm.get("name", "Unknown")
                    discoveries.append({
                        "source": "weather",
                        "type": "hurricane",
                        "name": name,
                        "symbols": ["USOIL", "NATGAS"],
                        "confidence": 0.5,
                        "description": f"Active hurricane {name} - may impact energy prices",
                    })
    except Exception:
        pass

    # Check for heat waves / cold snaps (affect natural gas, agriculture)
    try:
        resp = requests.get("https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.01&daily=temperature_2m_max&timezone=America/New_York", headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            daily = data.get("daily", {})
            temps = daily.get("temperature_2m_max", [])
            if temps:
                max_temp = max(temps[:7]) if temps else 0
                if max_temp > 38:  # > 100F heat wave
                    discoveries.append({
                        "source": "weather",
                        "type": "heat_wave",
                        "location": "NYC area",
                        "max_temp_c": max_temp,
                        "symbols": ["NATGAS", "CORN", "WHEAT"],
                        "confidence": 0.4,
                        "description": f"Heat wave in NYC area ({max_temp:.0f}C) - may impact energy/agriculture",
                    })
    except Exception:
        pass

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_weather()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"weather: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
