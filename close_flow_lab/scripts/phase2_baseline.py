"""Phase 2: baseline strategy for the Phase-1 survivor P3b (15:00 -> 15:30 continuation).
Pre-registered grid (30 trials): instrument {L=LETF bull/bear, U=underlying long/short}
x sizing {EQ, VOL, LIN} x universe {basket of the 4 gate-passing families, each family alone}.
Random baseline: same days/weights/costs, random direction, 2000 draws."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import os
import backtest as B, trials as T
CM = float(os.environ.get("CFL_COST_MULT", "1.5")); TAG = os.environ.get("CFL_TAG", "")

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"; OUT.mkdir(parents=True, exist_ok=True)
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]
rng = np.random.default_rng(20261007)
hs = B.half_spread_table()
res = []
for universe in ["BASKET4"] + FAMS:
    fams = FAMS if universe == "BASKET4" else [universe]
    for inst in ["L", "U"]:
        dfs = {f: B.family_trades(f, inst, hs=hs, cost_mult=CM) for f in fams}
        for sizing in ["EQ", "VOL", "LIN"]:
            net_cols, gross_cols, rand_inputs = [], [], []
            ntr = 0
            for f, df in dfs.items():
                w = B.weights(df, sizing)
                net_cols.append((w * df["net"]).fillna(0).rename(f)); gross_cols.append((w * df["gross"]).fillna(0).rename(f))
                e = df["eligible"]; ntr += int(e.sum())
                rand_inputs.append((w[e], df.loc[e, "gross"], df.loc[e, "cost"], e))
            idx = pd.concat(net_cols, axis=1).index
            R = pd.concat(net_cols, axis=1).fillna(0).mean(axis=1)
            G = pd.concat(gross_cols, axis=1).fillna(0).mean(axis=1)
            m = B.metrics(R); mg = B.metrics(G)
            # random-direction baseline (same days, weights, costs)
            sims = []
            for _ in range(2000):
                cols = []
                for (w, g, c, e) in rand_inputs:
                    s = rng.choice([-1.0, 1.0], size=len(g))
                    # flipping direction: LETF -> other leg's return is ~ -3x underlying; approximate with -gross
                    cols.append(pd.Series(w.values * (s * g.values - c.values), index=g.index))
                rr = pd.concat(cols, axis=1).reindex(idx).fillna(0).mean(axis=1)
                sims.append(rr.mean() / rr.std() * np.sqrt(252))
            sims = np.array(sims); p = float((sims >= m["sharpe"]).mean())
            tr = R[R != 0]
            row = dict(universe=universe, inst=inst, sizing=sizing, n_trades=ntr, **m, gross_sharpe=mg["sharpe"],
                       avg_net_bp=float(tr.mean() * 1e4), hit=float((tr > 0).mean()), rand_sharpe_mean=float(sims.mean()),
                       rand_sharpe_p95=float(np.quantile(sims, 0.95)), p_vs_random=p)
            row["gate"] = (row["sharpe"] > 1.0) and (row["pf"] > 1.3) and (p < 0.05)
            res.append(row)
            T.log("2" + TAG, "H1-P3b", f"{universe}-{inst}-{sizing}", dict(universe=universe, instrument=inst, sizing=sizing,
                  entry="15:01", exit="15:31", cost_mult=CM, slip_bp=0.5, month_end_excluded=True),
                  is_m=dict(n_trades=ntr, **m), is_start=str(idx.min().date()), is_end=str(idx.max().date()),
                  notes=f"gross_sharpe={mg['sharpe']:.3f}; p_vs_random={p:.4f}")
            print(row, flush=True)
            if universe == "BASKET4":
                pd.DataFrame({"net": R, "gross": G}).to_parquet(OUT / f"daily_{universe}_{inst}_{sizing}{TAG}.parquet")
res = pd.DataFrame(res); res.to_csv(OUT / f"phase2_results{TAG}.csv", index=False)
pd.set_option("display.width", 250)
print(res.drop(columns=["n_days"]).round(3).to_string())
