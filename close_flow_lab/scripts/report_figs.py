"""Figures + deflated Sharpe for the final report (IS only; holdout locked)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.ticker
import backtest as B, features as F, trials as T, data as D

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
                     "lines.linewidth": 2, "legend.frameon": False})
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]

# 1. effect by year (P3b, NW t per year)
yy = pd.read_csv(ROOT / "reports/phase1/pivot3_by_year.csv")
p = yy[(yy.spec == "P3b") & yy.sym.isin(FAMS)].pivot(index="year", columns="sym", values="t")[FAMS]
fig, ax = plt.subplots(figsize=(9, 3.8)); w = 0.2; xs = np.arange(len(p))
for i, s in enumerate(FAMS):
    ax.bar(xs + (i - 1.5) * w, p[s], w * 0.9, color=C[i], label=s)
ax.axhline(0, color=INK2, lw=0.8); ax.axhline(2.5, color=INK2, lw=0.8, ls="--"); ax.text(len(p) - 0.5, 2.6, "t = 2.5", color=INK2, ha="right", fontsize=8)
ax.set_xticks(xs, p.index); ax.set_ylabel("Newey-West t (per year)")
ax.set_title("P3b effect by year: prev-close→15:00 move predicts 15:00→15:30 (vol-scaled)", loc="left", fontsize=11)
ax.legend(ncol=4, loc="upper left"); fig.tight_layout(); fig.savefig(FIG / "effect_by_year_p3b.png", dpi=130); plt.close(fig)

# series
S = pd.read_parquet(ROOT / "reports/phase2/daily_series_postmortem.parquet")
_, G, _ = B.portfolio(FAMS, "L", "LIN")
curves = {"Basket LETF, LIN sizing: gross (before costs)": G, "Basket LETF, LIN sizing: net (pre-registered costs)": S["BASKET4-L-LIN"],
          "Best Phase-2 variant SOXX LETF LIN: net": S["SOXX-L-LIN"], "Post-mortem |z|≥1 basket LETF EQ: net (not eligible)": S["BASKET4-L-EQ-z1"]}
fig, ax = plt.subplots(figsize=(9, 4.2))
for i, (k, r) in enumerate(curves.items()):
    eq = (1 + r.fillna(0)).cumprod(); ax.plot(eq.index, eq.values, color=C[i], label=k, lw=1.8)
ax.axvspan(D.HOLDOUT_START, pd.Timestamp("2026-09-30"), color=GRID, alpha=0.9)
ax.text(D.HOLDOUT_START + pd.Timedelta(days=20), ax.get_ylim()[1] * 0.97, "HOLDOUT\nlocked,\nnever\nevaluated", va="top", fontsize=8, color=INK2)
ax.set_yscale("log"); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.1f}")); ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax.set_ylabel("growth of $1 (log)"); ax.set_title("In-sample equity curves (2016 → 2025-07). No WF-OOS: run killed at Phase 2", loc="left", fontsize=11)
ax.legend(fontsize=8, loc="upper left"); fig.tight_layout(); fig.savefig(FIG / "equity_is.png", dpi=130); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 3.2))
for i, (k, r) in list(enumerate(curves.items()))[1:]:
    eq = (1 + r.fillna(0)).cumprod(); ax.plot(eq.index, (eq / eq.cummax() - 1).values * 100, color=C[i], label=k, lw=1.4)
ax.set_ylabel("drawdown %"); ax.set_title("In-sample drawdowns (net)", loc="left", fontsize=11); ax.legend(fontsize=8, loc="lower left")
fig.tight_layout(); fig.savefig(FIG / "drawdowns_is.png", dpi=130); plt.close(fig)

# 4. heatmap z_min x flat cost per side -> net Sharpe (basket, LETF, EQ). new z_min values logged as trials.
hs = B.half_spread_table()
dfs = {f: B.family_trades(f, "L", hs=hs) for f in FAMS}
zs, cs = [0.0, 0.5, 1.0, 1.5, 2.0], [0.0, 0.5, 1.0, 2.0, 3.0, 4.0]
H = pd.DataFrame(index=zs, columns=cs, dtype=float); Hpre = {}
for z in zs:
    cols_g, cols_w, cols_n = [], [], []
    for f, df in dfs.items():
        d = df.copy(); d["eligible"] &= d["zx"].abs() >= z
        w = B.weights(d, "EQ"); cols_g.append(w * d["gross"].fillna(0)); cols_w.append(w); cols_n.append(w * d["net"].fillna(0))
    Gz = pd.concat(cols_g, axis=1).fillna(0).mean(axis=1); Wz = pd.concat(cols_w, axis=1).fillna(0).mean(axis=1)
    Nz = pd.concat(cols_n, axis=1).fillna(0).mean(axis=1)
    for c in cs:
        H.loc[z, c] = B.metrics(Gz - Wz * 2 * c * 1e-4)["sharpe"]
    Hpre[z] = B.metrics(Nz)
    if z in (0.5, 1.5, 2.0):
        T.log("2-postmortem", "H1-P3b+|z|", f"BASKET4-L-EQ-z{z}", dict(universe="BASKET4", instrument="L", sizing="EQ", z_min=z, cost_mult=1.5, slip_bp=0.5),
              is_m=dict(n_trades=int(sum((d['eligible'] & (d['zx'].abs() >= z)).sum() for d in dfs.values())), **Hpre[z]), notes="heatmap cell; diagnostic only")
H.to_csv(ROOT / "reports/phase2/heatmap_zmin_cost.csv")
pd.Series({z: m["sharpe"] for z, m in Hpre.items()}).to_csv(ROOT / "reports/phase2/zmin_precosts_sharpe.csv")
fig, ax = plt.subplots(figsize=(7, 3.6))
vmax = float(np.nanmax(np.abs(H.values)))
im = ax.imshow(H.values.astype(float), cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto")
for i in range(len(zs)):
    for j in range(len(cs)):
        v = H.values[i, j]; ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color=INK if abs(v) < vmax * 0.6 else "white")
ax.set_xticks(range(len(cs)), [f"{c:g}" for c in cs]); ax.set_yticks(range(len(zs)), [f"|z|≥{z:g}" for z in zs]); ax.grid(False)
ax.set_xlabel("flat cost per side (bp)"); ax.set_title("Net Sharpe, basket LETF EQ: move-size filter × cost (IS)", loc="left", fontsize=11)
fig.colorbar(im, ax=ax, shrink=0.8, label="net Sharpe"); fig.tight_layout(); fig.savefig(FIG / "heatmap_zmin_cost.png", dpi=130); plt.close(fig)

# 5. regime breakdown (RV20 tercile of QQQ, causal) for basket LIN net and gross
rv = F.vol_regime("QQQ")["rv20"]
reg = pd.qcut(rv, 3, labels=["low RV", "mid RV", "high RV"])
rows = []
for name, r in [("gross LIN", G), ("net LIN", S["BASKET4-L-LIN"]), ("net |z|≥1 EQ", S["BASKET4-L-EQ-z1"])]:
    for lv, g in r.groupby(reg.reindex(r.index), observed=True):
        rows.append(dict(series=name, regime=str(lv), sharpe=g.mean() / g.std() * np.sqrt(252), days=len(g)))
rg = pd.DataFrame(rows); rg.to_csv(ROOT / "reports/phase2/regime_breakdown.csv", index=False)
pv = rg.pivot(index="regime", columns="series", values="sharpe").loc[["low RV", "mid RV", "high RV"]]
fig, ax = plt.subplots(figsize=(7, 3.4)); xs = np.arange(3)
for i, c in enumerate(pv.columns):
    ax.bar(xs + (i - 1) * 0.27, pv[c], 0.25, color=C[i], label=c)
ax.axhline(0, color=INK2, lw=0.8); ax.set_xticks(xs, pv.index); ax.set_ylabel("Sharpe (IS)")
ax.set_title("Regime breakdown (QQQ 20d realized-vol tercile; VIX proxy)", loc="left", fontsize=11); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "regime_breakdown.png", dpi=130); plt.close(fig)
print(pv.round(2))

# deflated Sharpe (Bailey & Lopez de Prado 2014) for the best Phase-2 gate variant
tr = pd.read_csv(ROOT / "trials.csv")
srs = tr["is_sharpe"].astype(float).dropna() / np.sqrt(252)
N = len(tr)
best = S["SOXX-L-LIN"].dropna(); sr = best.mean() / best.std(); Tn = len(best)
g = 0.5772156649
sr0 = np.sqrt(srs.var()) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * np.e)))
den = np.sqrt(1 - skew(best) * sr + (kurtosis(best, fisher=False) - 1) / 4 * sr ** 2)
dsr = norm.cdf((sr - sr0) * np.sqrt(Tn - 1) / den)
psr0 = norm.cdf(sr * np.sqrt(Tn - 1) / den)
out = dict(n_trials=N, best_variant="SOXX-L-LIN", best_ann_sharpe=sr * np.sqrt(252), sr0_ann=sr0 * np.sqrt(252),
           psr_vs_0=psr0, deflated_sharpe_prob=dsr, skew=float(skew(best)), kurt=float(kurtosis(best, fisher=False)), days=Tn)
json.dump(out, open(ROOT / "reports/phase2/deflated_sharpe.json", "w"), indent=1, default=float); print(out)
