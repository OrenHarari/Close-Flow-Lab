"""Phase 0: inventory of read-only source data (OPEN-CLOSE-TRADE/data). Never writes into source."""
import json, sys, glob, os
from collections import defaultdict
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "/home/user/open-close-trade/data"
OUT = sys.argv[2] if len(sys.argv) > 2 else "close_flow_lab/data_inventory/manifest_inventory.csv"
rows = []
for m in glob.glob(f"{SRC}/**/*MANIFEST.json", recursive=True):
    rel = os.path.relpath(m, SRC)
    parts = rel.split(os.sep)
    try:
        j = json.load(open(m))
    except Exception as e:
        rows.append(dict(path=rel, error=str(e)))
        continue
    rows.append(dict(sym=parts[0], folder=parts[1] if len(parts) > 2 else "", tf=j.get("timeframe"),
                     session=j.get("session"), window=j.get("session_window_et"), source=j.get("source"),
                     start=j.get("start_date"), end=j.get("end_date"), rows=j.get("total_rows"),
                     nfiles=len(j.get("files", [])), path=rel))
df = pd.DataFrame(rows).sort_values(["sym", "folder", "start"])
df.to_csv(OUT, index=False)
g = df.groupby(["sym", "folder"]).agg(start=("start", "min"), end=("end", "max"), rows=("rows", "sum"),
                                       sources=("source", lambda s: ",".join(sorted(set(map(str, s))))),
                                       nbundles=("path", "count"))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_colwidth", 60)
print(g)
