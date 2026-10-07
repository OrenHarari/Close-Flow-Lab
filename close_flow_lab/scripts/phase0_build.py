"""Phase 0: build in-sample day tables for the universe and write a quality report."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import data as D

UNIVERSE = [("SOXL","1m"),("SOXS","1m"),("SOXX","5m"),("SOXX","1m"),("TQQQ","1m"),("SQQQ","1m"),("QQQ","1m"),
            ("TNA","1m"),("TZA","1m"),("IWM","1m"),("TECL","1m"),("TECS","1m"),("XLK","1m"),
            ("UDOW","1m"),("SDOW","1m"),("DIA","1m"),("LABU","5m"),("LABD","5m"),("XBI","5m"),
            ("NVDL","1m"),("NVDS","1m"),("NVDA","1m")]
rows = []; splits = []
for sym, tf in UNIVERSE:
    t0 = time.time()
    d = D.build_day_table(sym, tf)
    full = d[~d.half_day]
    oc_err = (np.log1p(full.oc_raw) - np.log1p(full.oc_adj)).abs() * 1e4
    rows.append(dict(sym=sym, tf=tf, first=d.index.min().date(), last=d.index.max().date(), days=len(d),
                     half_days=int(d.half_day.sum()), days_missing_gt5pct=int((full.missing_bars > 0.05*full.expected_bars).sum()),
                     median_missing=float(full.missing_bars.median()), auction_close_pct=round(100*(d.close_src=="auction16").mean(),1),
                     no_open_0930=int(d.open.isna().sum()), no_p1500=int(full.p1500.isna().sum()), no_p1530=int(full.p1530.isna().sum()),
                     oc_vs_daily_med_bp=round(float(oc_err.median()),2), oc_vs_daily_gt50bp=int((oc_err>50).sum()),
                     daily_rows_missing_intraday=None, splits=int(d.ca_flag.sum()), secs=round(time.time()-t0,1)))
    for dt, r in d[d.ca_flag].iterrows():
        splits.append(dict(sym=sym, tf=tf, date=dt.date(), raw_gap=round(r.open/r.prev_close-1,4), ratio=round(float(np.exp(r.ca_logratio)),4), corrected_gap=round(r.gap_ret,4)))
    dd = D.load_daily(sym); dd = dd[dd.index >= d.index.min()]
    rows[-1]["daily_rows_missing_intraday"] = int((~dd.index.isin(d.index)).sum())
    print(rows[-1], flush=True)
out = Path("close_flow_lab/data_inventory")
pd.DataFrame(rows).to_csv(out/"quality_is.csv", index=False)
pd.DataFrame(splits).to_csv(out/"corporate_actions_is.csv", index=False)
print(pd.DataFrame(splits).to_string())
