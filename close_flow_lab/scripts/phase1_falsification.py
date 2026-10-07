"""Devil's-advocate test for Pivot 3 / P3b (pre-registered in STATE.md before running):
apply P3b unchanged to instruments never looked at in Phases 0-1.
Refutation of 'P3b is a snooped artefact' requires BOTH:
  (1) >= 70% of fresh instruments have a positive slope, and
  (2) median NW t across fresh instruments > 1.0.
Otherwise Phase 1 is treated as FAIL -> KILL (no pivots left)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import data as D, features as F
from phase1_effect import ols_nw

FRESH = {"AAPL": "5m", "MSFT": "1m", "AMZN": "1m", "GOOGL": "1m", "TSLA": "1m", "INTC": "1m", "AMD": "5m",
         "AVGO": "5m", "MU": "5m", "AMAT": "5m", "LRCX": "5m", "KLAC": "5m", "QCOM": "5m", "TXN": "5m",
         "ASML": "5m", "TSM": "5m", "SMH": "5m", "GLD": "5m", "SLV": "5m", "GDX": "5m", "IBIT": "1m"}
F.TF.update(FRESH)
rows = []
for sym, tf in FRESH.items():
    try:
        df = F.day_returns(sym)
    except Exception as e:
        print(sym, "skip", e); continue
    df = df.join(F.calendar_flags(df.index))
    sig = df["cc"].rolling(60, min_periods=40).std().shift(1)
    zx = df["pc1500"] / sig; zy = (df["p1530"] / df["p1500"] - 1) / sig
    m = ~df["month_end"] & zx.notna() & zy.notna()
    r = ols_nw(zx[m].values, zy[m].values)
    rows.append(dict(sym=sym, tf=tf, first=df.index.min().date(), **r))
res = pd.DataFrame(rows)
res.to_csv(Path(__file__).resolve().parents[1] / "reports" / "phase1" / "falsification_p3b.csv", index=False)
print(res.round(3).to_string())
pos = (res.b > 0).mean(); med_t = res.t.median()
print(f"positive slope: {pos:.2%}  median t: {med_t:.2f}  -> {'REFUTED (supports P3b)' if pos >= 0.7 and med_t > 1.0 else 'NOT REFUTED'}")
