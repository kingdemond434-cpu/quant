#!/usr/bin/env python3
import os
os.chdir("/home/quant/quant-platform")
from scripts.agent_feed import write_entry
eid = write_entry(
    type_="capability",
    title="Auto ratchet runner deployed",
    payload={"mean": 8.03, "binding": "alpha_output.promotion_rung"},
    priority="critical"
)
print(f"Written: {eid}")