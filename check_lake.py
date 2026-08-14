#!/usr/bin/env python3
from libs.data.lake import ParquetLake
from pathlib import Path

lake = ParquetLake("data/lake")
# Check what's in the crypto lake
crypto_path = Path("data/lake/bronze/crypto")
if crypto_path.exists():
    for p in crypto_path.rglob("*.parquet"):
        print(p)
else:
    print("No crypto path")

# Check the bronze/index
index_path = Path("data/lake/bronze/index")
if index_path.exists():
    for p in index_path.iterdir():
        if p.is_dir():
            print(f"Index: {p.name}")
            for q in p.iterdir():
                if q.is_dir():
                    print(f"  {q.name}")