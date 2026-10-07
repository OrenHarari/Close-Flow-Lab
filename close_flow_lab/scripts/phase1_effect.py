"""Phase 1: effect validation (no strategy). IS only (holdout locked in data.py)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import statsmodels.api as sm
import features as F

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase1"
OUT.mkdir(parents=True, exist_ok=True)
SPECS = {  # name: (x, y, hypothesis)
    "S1": ("on1000", "last30", "H2"), "S2": ("on1000", "last60", "H2"), "S3": ("oc1500", "last60", "H2"),
    "S4": ("oc1530", "last30", "H2"), "S5": ("oc1500", "last30", "H2"),
    "S6": ("pc1530", "last30", "H1"), "S7": ("pc1500", "last60", "H1"),
}
NW_LAGS = 5


def ols_nw(x, y):
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 30:
        return dict(n=len(x), b=np.nan, t=np.nan, r2=np.nan)
    X = sm.add_constant(x)
    r = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    return dict(n=int(len(x)), b=float(np.asarray(r.params)[1]), t=float(np.asarray(r.tvalues)[1]), r2=float(r.rsquared),
                hit=float(np.mean(np.sign(x) == np.sign(y))), signed_bp=float(np.mean(np.sign(x) * y) * 1e4))


def year_stats(df, x, y):
    d = df[[x, y]].dropna()
    xm, ym = d[x].mean(), d[y].mean()
    contrib = ((d[x] - xm) * (d[y] - ym)).groupby(d.index.year).sum()
    share = contrib / contrib.sum()
    per = {yr: ols_nw(g[x].values, g[y].values) for yr, g in d.groupby(d.index.year)}
    return share, per



def main():
    rv = F.vol_regime("QQQ")
    rows, yrows, srows = [], [], []
    syms = list(F.UNDERLYINGS) + list(F.LETFS)
    for sym in syms:
        df = F.day_returns(sym)
        df = df.join(rv).join(F.calendar_flags(df.index))
        for sp, (x, y, hyp) in SPECS.items():
            full = ols_nw(df[x].values, df[y].values)
            share, per = year_stats(df, x, y)
            signs = [np.sign(v["b"]) for v in per.values() if np.isfinite(v["b"])]
            same = float(np.mean([s == np.sign(full["b"]) for s in signs]))
            recent = {f"b_{yr}": per.get(yr, {}).get("b", np.nan) for yr in (2023, 2024, 2025)}
            recent.update({f"t_{yr}": per.get(yr, {}).get("t", np.nan) for yr in (2023, 2024, 2025)})
            # robustness: excluding 2020, and winsorized x/y at 1/99 pct
            ex20 = df[df.index.year != 2020]
            r_ex20 = ols_nw(ex20[x].values, ex20[y].values)
            w = df[[x, y]].dropna()
            w = w.clip(w.quantile(0.01), w.quantile(0.99), axis=1)
            r_w = ols_nw(w[x].values, w[y].values)
            rows.append(dict(sym=sym, kind="underlying" if sym in F.UNDERLYINGS else "letf", spec=sp, hyp=hyp, x=x, y=y,
                             **full, years=len(signs), same_sign_frac=same, max_year_share=float(share.max()),
                             max_year=int(share.idxmax()), t_ex2020=r_ex20["t"], b_ex2020=r_ex20["b"], t_winsor=r_w["t"],
                             b_winsor=r_w["b"], **recent))
            for yr, v in per.items():
                yrows.append(dict(sym=sym, spec=sp, year=yr, share=float(share.get(yr, np.nan)), **v))
            # regime splits (underlyings only, primary interest)
            if sym in F.UNDERLYINGS:
                q = pd.qcut(df["rv20"], 3, labels=["rv_lo", "rv_mid", "rv_hi"])
                groups = {"rv20": q, "ts_inverted": df["ts_ratio"] > 1, "dow": df["dow"], "opex": df["opex"],
                          "month_end": df["month_end"], "quarter_end": df["quarter_end"],
                          "absx_quintile": pd.qcut(df[x].abs(), 5, labels=[f"q{i}" for i in range(1, 6)]),
                          "vol_spike": (df["vol_0930_1000"] / df["vol_0930_1000"].rolling(20).median().shift(1)) > 1.5}
                for gname, gser in groups.items():
                    for lvl, g in df.groupby(gser, observed=True):
                        srows.append(dict(sym=sym, spec=sp, split=gname, level=str(lvl), **ols_nw(g[x].values, g[y].values)))
        print(sym, "done", flush=True)

    res = pd.DataFrame(rows); yr = pd.DataFrame(yrows); sp = pd.DataFrame(srows)
    res.to_csv(OUT / "effect_full.csv", index=False); yr.to_csv(OUT / "effect_by_year.csv", index=False); sp.to_csv(OUT / "effect_splits.csv", index=False)
    res["pass"] = (res.t > 2.5) & (res.same_sign_frac >= 0.7) & (res.max_year_share <= 0.4)
    res["pass_t_only"] = res.t > 2.5
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    cols = ["sym", "spec", "n", "b", "t", "r2", "hit", "signed_bp", "same_sign_frac", "max_year_share", "max_year", "t_ex2020", "t_winsor", "b_2023", "b_2024", "b_2025", "t_2023", "t_2024", "t_2025", "pass"]
    print(res[res.kind == "underlying"][cols].round(3).to_string())
    print(res[res.kind == "letf"][cols].round(3).to_string())
    gate = res[res.kind == "underlying"].groupby("spec")["pass"].sum()
    print("underlyings passing per spec:\n", gate)
    json.dump({k: int(v) for k, v in gate.items()}, open(OUT / "gate.json", "w"), indent=1)


if __name__ == "__main__":
    main()
