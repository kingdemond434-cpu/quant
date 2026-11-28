"""Weather data miner for commodities.

Scrapes weather data for agricultural/energy commodity impacts.
Extreme weather = supply shocks = price moves in wheat, coffee, natural gas.
"""

from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "weather"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "quant-desk-research/1.0 (NOAA public data)"}

# Weather events that move commodities
WEATHER_SOURCES = {
    # CurrentSummaries.json was RENAMED to CurrentStorms.json; the old path now serves a
    # 404 HTML page (22,982 bytes), which resp.json() rejects and the bare except swallowed,
    # so this source read as "no storms" rather than "endpoint moved" -- measured 2026-09-01
    # with 4 active storms live on the new path. The response SCHEMA is unchanged
    # (activeStorms[].name), so this is a route fix only.
    "noaa_hurricanes": "https://www.nhc.noaa.gov/CurrentStorms.json",
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
                        "symbols": ["XTIUSD", "XBRUSD", "XNGUSD"],
                        "confidence": 0.5,
                        "description": f"Active hurricane {name} - may impact energy prices",
                    })
    except Exception:
        pass

    # Open-Meteo was dropped (2026-11-13): its free API is licensed for non-commercial use only
    # (open-meteo.com/en/terms). Its one check -- an NYC max above 38C -- also never fired in the
    # box's history. The door in net_gate refuses the host if a later edit brings it back.

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_weather()
    out_file = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"weather: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
