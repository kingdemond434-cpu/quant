import sys
sys.path.insert(0, ".")
from mt5desk import data, families
import pandas as pd

cot = data.load_cot("USDJPY")
print("USDJPY COT:", len(cot), cot["report_date"].min().date(), "->",
      cot["report_date"].max().date())
h1 = pd.read_parquet("data/universe/USDJPY_H1.parquet")
for name, fn in [("cot_net_fade", families.family2_cot_net_fade),
                 ("cot_change_fade", families.family2_cot_change_fade),
                 ("cot_change_momentum", families.family2_cot_change_momentum)]:
    sigs = fn(h1, cot)
    print(f"{name}: {len(sigs)} signals")