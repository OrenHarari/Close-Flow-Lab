"""Post-mortem diagnostics after the Phase-2 KILL (IS only; holdout stays locked).
(1) Big-move subset |z|>=1 with the pre-registered costs -> where does residual net edge live?
    Logged in trials.csv as 'postmortem' (not eligible for selection; for deflated-Sharpe accounting).
(2) Correlation of daily PnL with the live OPEN-CLOSE-TRADE strategies (Apex Reserve, Barometer)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import backtest as B, trials as T, data as D

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]
rows, series = [], {}
for universe, inst, sizing in [("BASKET4", "L", "EQ"), ("BASKET4", "L", "LIN"), ("SOXX", "L", "EQ"), ("QQQ", "U", "EQ"), ("BASKET4", "U", "EQ")]:
    fams = FAMS if universe == "BASKET4" else [universe]
    R, G, tr = B.portfolio(fams, inst, sizing, z_min=1.0)
    m = B.metrics(R); mg = B.metrics(G)
    yr = R.groupby(R.index.year).apply(lambda r: r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan)
    T.log("2-postmortem", "H1-P3b+|z|>=1", f"{universe}-{inst}-{sizing}-z1", dict(universe=universe, instrument=inst, sizing=sizing,
          z_min=1.0, cost_mult=1.5, slip_bp=0.5), is_m=dict(n_trades=len(tr), **m), notes="diagnostic only; not eligible (Phase 2 failed, no pivots left)")
    rows.append(dict(variant=f"{universe}-{inst}-{sizing}-z1", n_trades=len(tr), **m, gross_sharpe=mg["sharpe"],
                     avg_net_bp=float((tr["net"] * tr["w"]).mean() * 1e4), years_positive=int((yr > 0).sum()), years=int(yr.notna().sum()),
                     **{f"sh_{y}": v for y, v in yr.round(2).items()}))
    series[f"{universe}-{inst}-{sizing}-z1"] = R
res = pd.DataFrame(rows); res.to_csv(OUT / "postmortem_bigmove.csv", index=False)
pd.set_option("display.width", 250); print(res.round(3).to_string())

# best Phase-2 gate variant (highest net Sharpe) + baskets
for universe, inst, sizing in [("SOXX", "L", "LIN"), ("BASKET4", "L", "LIN"), ("QQQ", "U", "LIN")]:
    fams = FAMS if universe == "BASKET4" else [universe]
    series[f"{universe}-{inst}-{sizing}"] = B.portfolio(fams, inst, sizing)[0]
S = pd.DataFrame(series)
S.to_parquet(OUT / "daily_series_postmortem.parquet")
oct_dir = Path("/home/user/open-close-trade/research/honest-backtest")
ext = {}
for name, f, col in [("ApexReserve", "reserve_daily.csv", "pnl_pct"), ("Barometer", "baro_daily.csv", "book5")]:
    d = pd.read_csv(oct_dir / f, parse_dates=["date"]).set_index("date")
    d = d[d.index < D.HOLDOUT_START]
    ext[name] = d[col].groupby(level=0).sum() / 100
E = pd.DataFrame(ext)
J = S.join(E, how="inner").fillna(0)
corr = J.corr().loc[S.columns, E.columns]
print("daily PnL correlation (IS, common days):\n", corr.round(3)); corr.to_csv(OUT / "corr_open_close_trade.csv")
# conditional: correlation on days both traded
for c in S.columns:
    for e in E.columns:
        both = J[(J[c] != 0) & (J[e] != 0)]
        print(c, e, "both-active days", len(both), "corr", round(both[c].corr(both[e]), 3))
