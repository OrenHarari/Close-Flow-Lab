"""PIVOT 2 (pre-registered, see STATE.md): vol-scaled LETF flow."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, statsmodels.api as sm
import features as F
from phase1_effect import ols_nw, year_stats

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase1"
rows, yrows = [], []
for sym in list(F.UNDERLYINGS) + list(F.LETFS):
    df = F.day_returns(sym)
    df = df.join(F.calendar_flags(df.index))
    sig = df["cc"].rolling(60, min_periods=40).std().shift(1)
    df["zx"] = df["pc1500"] / sig
    df["zy"] = df["last60"] / sig
    base = ~df["month_end"] & sig.notna()
    for sp, cond in {"P2a": base, "P2b": base & (df["zx"].abs() >= 1.0)}.items():
        d = df[cond]
        full = ols_nw(d["zx"].values, d["zy"].values)
        share, per = year_stats(d, "zx", "zy")
        signs = [np.sign(v["b"]) for v in per.values() if np.isfinite(v["b"])]
        same = float(np.mean([s == np.sign(full["b"]) for s in signs]))
        sy = np.sign(d["zx"]) * d["zy"]
        r = sm.OLS(sy.values, np.ones(len(sy))).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        ex20 = d[d.index.year != 2020]
        rows.append(dict(sym=sym, spec=sp, n=full["n"], b=full["b"], t=full["t"], same_sign_frac=same,
                         max_year_share=float(share.max()), max_year=int(share.idxmax()),
                         signed_z_mean=float(sy.mean()), signed_t=float(np.asarray(r.tvalues)[0]),
                         t_ex2020=ols_nw(ex20["zx"].values, ex20["zy"].values)["t"],
                         **{f"t_{k}": per.get(k, {}).get("t", np.nan) for k in (2023, 2024, 2025)}))
        for yr, v in per.items():
            yrows.append(dict(sym=sym, spec=sp, year=yr, share=float(share.get(yr, np.nan)), **v))
res = pd.DataFrame(rows)
res["pass"] = (res.t > 2.5) & (res.same_sign_frac >= 0.7) & (res.max_year_share <= 0.4)
res["underlying"] = res.sym.isin(list(F.UNDERLYINGS))
res.to_csv(OUT / "pivot2_effect.csv", index=False); pd.DataFrame(yrows).to_csv(OUT / "pivot2_by_year.csv", index=False)
pd.set_option("display.width", 250)
print(res.round(3).to_string())
print(res[res.underlying].groupby("spec")["pass"].sum())
