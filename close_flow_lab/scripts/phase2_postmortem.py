"""Phase 2 post-mortem (NOT a gate re-test): how sensitive is the FAIL to the cost model?
(a) break-even cost per side, (b) 'quoted half-spread only' costs (cost_mult=1, slip=0) logged as trials,
(c) per-year gross/net for the best variants, (d) edge vs |z| bucket (gross bp per trade)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import backtest as B, trials as T

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]
hs = B.half_spread_table()
rows = []
for universe in ["BASKET4", "QQQ", "SOXX"]:
    fams = FAMS if universe == "BASKET4" else [universe]
    for inst in ["U", "L"]:
        for sizing in ["EQ", "LIN"]:
            dfs = {f: B.family_trades(f, inst, hs=hs) for f in fams}
            W = {f: B.weights(df, sizing) for f, df in dfs.items()}
            G = pd.concat([(W[f] * dfs[f]["gross"]).fillna(0) for f in fams], axis=1).fillna(0).mean(axis=1)
            Wsum = pd.concat([W[f] for f in fams], axis=1).fillna(0).mean(axis=1)
            # flat cost per side c (bp) applied to traded notional
            be = None
            for c in np.arange(0, 8.01, 0.1):
                r = G - Wsum * 2 * c * 1e-4
                if r.mean() <= 0:
                    be = c; break
            # Sharpe at flat cost levels
            sh = {f"sharpe_c{c}": B.metrics(G - Wsum * 2 * c * 1e-4)["sharpe"] for c in (0, 0.25, 0.5, 1.0, 2.0)}
            # quoted half-spread only
            dq = {f: B.family_trades(f, inst, hs=hs, cost_mult=1.0, slip_bp=0.0) for f in fams}
            Rq = pd.concat([(B.weights(dq[f], sizing) * dq[f]["net"]).fillna(0) for f in fams], axis=1).fillna(0).mean(axis=1)
            mq = B.metrics(Rq)
            ntr = int(sum(d["eligible"].sum() for d in dq.values()))
            T.log("2-postmortem", "H1-P3b", f"{universe}-{inst}-{sizing}-halfspread", dict(universe=universe, instrument=inst, sizing=sizing,
                  cost_mult=1.0, slip_bp=0.0, entry="15:01", exit="15:31"), is_m=dict(n_trades=ntr, **mq),
                  notes="cost sensitivity only; not eligible for selection")
            rows.append(dict(universe=universe, inst=inst, sizing=sizing, breakeven_cost_side_bp=be, **sh,
                             sharpe_halfspread_only=mq["sharpe"], pf_halfspread_only=mq["pf"]))
res = pd.DataFrame(rows); res.to_csv(OUT / "cost_sensitivity.csv", index=False)
pd.set_option("display.width", 250); print(res.round(3).to_string())

# per-year gross vs net (pre-registered costs) for BASKET4-L-LIN and QQQ-U-LIN
for universe, inst in [("BASKET4", "L"), ("QQQ", "U"), ("SOXX", "L")]:
    fams = FAMS if universe == "BASKET4" else [universe]
    R, G, tr = B.portfolio(fams, inst, "LIN")
    yy = pd.DataFrame({"gross_bp_sum": G.groupby(G.index.year).sum() * 1e4, "net_bp_sum": R.groupby(R.index.year).sum() * 1e4,
                       "net_sharpe": R.groupby(R.index.year).apply(lambda r: r.mean() / r.std() * np.sqrt(252))})
    print(universe, inst, "LIN by year\n", yy.round(2).to_string())
    yy.to_csv(OUT / f"by_year_{universe}_{inst}_LIN.csv")

# edge by |z| bucket (gross & cost, bp per trade, EQ notional, LETF)
allt = pd.concat([B.family_trades(f, "L", hs=hs) for f in FAMS])
allt = allt[allt["eligible"]]
allt["zb"] = pd.cut(allt["zx"].abs(), [0, 0.25, 0.5, 1, 1.5, 2, 99])
zt = allt.groupby("zb", observed=True).agg(n=("gross", "size"), gross_bp=("gross", lambda s: s.mean() * 1e4), cost_bp=("cost", lambda s: s.mean() * 1e4))
zt["net_bp"] = zt.gross_bp - zt.cost_bp
print(zt.round(2)); zt.to_csv(OUT / "edge_by_z_letf.csv")
