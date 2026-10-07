"""Correlation of Close-Flow daily PnL with OPEN-CLOSE-TRADE live strategies (IS days only)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import backtest as B, data as D

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]
series = {}
for universe, inst, sizing, z in [("SOXX", "L", "LIN", 0), ("BASKET4", "L", "LIN", 0), ("QQQ", "U", "LIN", 0), ("BASKET4", "L", "EQ", 1.0)]:
    fams = FAMS if universe == "BASKET4" else [universe]
    series[f"{universe}-{inst}-{sizing}" + ("-z1" if z else "")] = B.portfolio(fams, inst, sizing, z_min=z)[0]
S = pd.DataFrame(series); S.to_parquet(OUT / "daily_series_postmortem.parquet")
oct_dir = Path("/home/user/open-close-trade/research/honest-backtest")
ext = {}
for name, f, col in [("ApexReserve", "reserve_daily.csv", "pnl_pct"), ("Barometer", "baro_daily.csv", "book5")]:
    d = pd.read_csv(oct_dir / f, parse_dates=["date"]).set_index("date")
    d = d[d.index < D.HOLDOUT_START]
    ext[name] = d[col].groupby(level=0).sum() / 100
E = pd.DataFrame(ext)
rows = []
for c in S.columns:
    for e in E.columns:
        j = pd.concat([S[c], E[e]], axis=1, join="inner").dropna()
        both = j[(j.iloc[:, 0] != 0) & (j.iloc[:, 1] != 0)]
        rows.append(dict(closeflow=c, oct=e, common_days=len(j), corr_all=j.corr().iloc[0, 1],
                         both_active=len(both), corr_both_active=both.corr().iloc[0, 1] if len(both) > 10 else np.nan,
                         span=f"{j.index.min().date()}..{j.index.max().date()}"))
r = pd.DataFrame(rows); r.to_csv(OUT / "corr_open_close_trade.csv", index=False)
pd.set_option("display.width", 250); print(r.round(3).to_string())
