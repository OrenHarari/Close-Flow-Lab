"""PIVOT 1 (pre-registered before running): H1' = LETF rebalancing pressure is detectable when
expected flow is large relative to closing liquidity, i.e. on big-move days, and is masked at
month-end by opposing pension/balanced-fund rebalancing.
Specs (no other variants):
  P1a: x = pc1500 (prev close -> 15:00), y = last60, days with |x| >= 1.0 * sigma60_{t-1}, not month-end
  P1b: x = pc1530 (prev close -> 15:30), y = last30, same conditioning on |x|
sigma60_{t-1} = std of the symbol's own close-to-close returns over the 60 prior days (causal).
Gate unchanged: t>2.5 NW on >=3 underlyings, same sign >=70% of years, no year >40% of total.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import features as F
from phase1_effect import ols_nw, year_stats  # noqa (re-runs nothing heavy: guarded below)

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase1"
SPECS = {"P1a": ("pc1500", "last60"), "P1b": ("pc1530", "last30")}
rows, yrows = [], []
for sym in list(F.UNDERLYINGS) + list(F.LETFS):
    df = F.day_returns(sym).join(F.calendar_flags(F.day_returns(sym).index))
    sig = df["cc"].rolling(60, min_periods=40).std().shift(1)
    for sp, (x, y) in SPECS.items():
        cond = (df[x].abs() >= 1.0 * sig) & ~df["month_end"]
        d = df[cond]
        full = ols_nw(d[x].values, d[y].values)
        share, per = year_stats(d, x, y)
        signs = [np.sign(v["b"]) for v in per.values() if np.isfinite(v["b"])]
        same = float(np.mean([s == np.sign(full["b"]) for s in signs]))
        # signed-return t (NW) : mean of sign(x)*y
        sy = np.sign(d[x]) * d[y]
        import statsmodels.api as sm
        r = sm.OLS(sy.values, np.ones(len(sy))).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        rows.append(dict(sym=sym, spec=sp, frac_days=float(cond.mean()), **full, years=len(signs), same_sign_frac=same,
                         max_year_share=float(share.max()), max_year=int(share.idxmax()),
                         signed_mean_bp=float(sy.mean() * 1e4), signed_t=float(np.asarray(r.tvalues)[0]),
                         **{f"t_{k}": per.get(k, {}).get("t", np.nan) for k in (2023, 2024, 2025)},
                         **{f"b_{k}": per.get(k, {}).get("b", np.nan) for k in (2023, 2024, 2025)}))
        for yr, v in per.items():
            yrows.append(dict(sym=sym, spec=sp, year=yr, share=float(share.get(yr, np.nan)), **v))
res = pd.DataFrame(rows)
res["pass"] = (res.t > 2.5) & (res.same_sign_frac >= 0.7) & (res.max_year_share <= 0.4)
res["underlying"] = res.sym.isin(list(F.UNDERLYINGS))
res.to_csv(OUT / "pivot1_effect.csv", index=False); pd.DataFrame(yrows).to_csv(OUT / "pivot1_by_year.csv", index=False)
pd.set_option("display.width", 250)
print(res.round(3).to_string())
print(res[res.underlying].groupby("spec")["pass"].sum())
