"""Post-mortem: big-move subset under the quote-calibrated cost model (cost_mult=0.8). Diagnostic only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import backtest as B, trials as T

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]
rows = []
for universe, inst, sizing, z in [("BASKET4", "L", "EQ", 1.0), ("BASKET4", "L", "LIN", 1.0), ("SOXX", "L", "EQ", 1.0), ("BASKET4", "L", "EQ", 0.5)]:
    fams = FAMS if universe == "BASKET4" else [universe]
    R, G, tr = B.portfolio(fams, inst, sizing, z_min=z, cost_mult=0.8)
    m = B.metrics(R)
    yr = R.groupby(R.index.year).apply(lambda r: r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan)
    T.log("2-postmortem", "H1-P3b+|z|", f"{universe}-{inst}-{sizing}-z{z}-corrcost", dict(universe=universe, instrument=inst, sizing=sizing, z_min=z, cost_mult=0.8, slip_bp=0.5),
          is_m=dict(n_trades=len(tr), **m), notes="diagnostic only; not eligible")
    rows.append(dict(variant=f"{universe}-{inst}-{sizing}-z{z}", n_trades=len(tr), **{k: m[k] for k in ("sharpe", "pf", "cagr", "maxdd")},
                     years_pos=int((yr > 0).sum()), **{f"sh_{y}": round(v, 2) for y, v in yr.items()}))
r = pd.DataFrame(rows); r.to_csv(OUT / "postmortem_bigmove_corrcost.csv", index=False)
pd.set_option("display.width", 250); print(r.round(3).to_string())
