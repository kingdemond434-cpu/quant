import zipfile, os
z = zipfile.ZipFile("/tmp/all_parquets.zip")
z.extractall("/home/quant/quant-platform/desks/mt5/data/universe")
n = len([f for f in os.listdir("/home/quant/quant-platform/desks/mt5/data/universe") if f.endswith(".parquet")])
print(f"Extracted. Total parquets: {n}")
