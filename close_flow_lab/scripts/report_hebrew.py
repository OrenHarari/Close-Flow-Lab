"""Builds the Hebrew HTML report (reports/hebrew_report.html) from the run's result files. IS data only."""
import sys, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import backtest as B

ROOT = Path(__file__).resolve().parents[1]
R2 = ROOT / "reports" / "phase2"
FAMS = ["QQQ", "IWM", "XLK", "SOXX"]

# ---------- data ----------
yy = pd.read_csv(ROOT / "reports/phase1/pivot3_by_year.csv")
p3 = yy[(yy.spec == "P3b") & yy.sym.isin(FAMS)].pivot(index="year", columns="sym", values="t")[FAMS]
pre = pd.read_parquet(R2 / "daily_BASKET4_L_LIN.parquet")
cor = pd.read_parquet(R2 / "daily_BASKET4_L_LIN-corrected.parquet")
lead = B.portfolio(FAMS, "L", "EQ", z_min=1.0, cost_mult=0.8)[0]
curves = [("ברוטו, לפני עלויות", pre["gross"]), ("נטו, עלויות רשומות מראש", pre["net"]),
          ("נטו, עלויות מכוילות לציטוטים", cor["net"]), ("ליד: רק ימי תנועה גדולה, נטו מכויל", lead)]
heat = pd.read_csv(R2 / "heatmap_zmin_cost.csv", index_col=0)
reg = pd.read_csv(R2 / "regime_breakdown.csv")
fals = pd.read_csv(ROOT / "reports/phase1/falsification_p3b.csv")

def bdi(s): return f"<bdi>{html.escape(str(s))}</bdi>"

# ---------- SVG helpers ----------
def bars_by_year(df):
    W, H, l, r, t, b = 760, 300, 44, 12, 16, 34
    vmin, vmax = -1.0, 7.0
    years = list(df.index); n = len(years); gw = (W - l - r) / n; bw = gw * 0.8 / 4
    y = lambda v: t + (vmax - v) / (vmax - vmin) * (H - t - b)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="מובהקות האפקט לפי שנה">']
    for v in range(-1, 8):
        out.append(f'<line x1="{l}" x2="{W-r}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                   f'<text x="{l-6}" y="{y(v)+4:.1f}" class="tick" text-anchor="end">{v}</text>')
    out.append(f'<line x1="{l}" x2="{W-r}" y1="{y(2.5):.1f}" y2="{y(2.5):.1f}" class="ref"/>'
               f'<text x="{W-r}" y="{y(2.5)-5:.1f}" class="tick" text-anchor="end">סף t = 2.5</text>')
    out.append(f'<line x1="{l}" x2="{W-r}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="axis"/>')
    for i, yr in enumerate(years):
        x0 = l + i * gw + gw * 0.1
        for j, s in enumerate(FAMS):
            v = df.loc[yr, s]; x = x0 + j * bw; y0, y1 = sorted([y(0), y(v)])
            out.append(f'<rect x="{x+1:.1f}" y="{y0:.1f}" width="{bw-2:.1f}" height="{max(y1-y0,0.5):.1f}" rx="2" class="s{j+1}"><title>{s} {yr}: t = {v:.2f}</title></rect>')
        out.append(f'<text x="{l+i*gw+gw/2:.1f}" y="{H-12}" class="tick" text-anchor="middle">{yr}</text>')
    out.append("</svg>")
    return "".join(out)

def equity(curves):
    W, H, l, r, t, b = 760, 320, 44, 16, 16, 30
    ser = []
    for name, s in curves:
        e = (1 + s.fillna(0)).cumprod(); e = e.resample("W").last().dropna(); ser.append((name, e))
    lo = np.log(min(e.min() for _, e in ser)) - 0.03; hi = np.log(max(e.max() for _, e in ser)) + 0.03
    x0, x1 = ser[0][1].index.min(), ser[0][1].index.max()
    X = lambda d: l + (d - x0) / (x1 - x0) * (W - l - r)
    Y = lambda v: t + (hi - np.log(v)) / (hi - lo) * (H - t - b)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="עקומות הון בתוך המדגם">']
    for v in [0.7, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
        if lo < np.log(v) < hi:
            out.append(f'<line x1="{l}" x2="{W-r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="{"axis" if v==1 else "grid"}"/>'
                       f'<text x="{l-6}" y="{Y(v)+4:.1f}" class="tick" text-anchor="end">{v:g}</text>')
    for yr in range(2016, 2026):
        d = pd.Timestamp(f"{yr}-01-01")
        if d >= x0: out.append(f'<text x="{X(d):.1f}" y="{H-10}" class="tick" text-anchor="middle">{yr}</text>')
    for j, (name, e) in enumerate(ser):
        pts = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in e.items())
        out.append(f'<polyline points="{pts}" class="ln s{j+1}"/>')
        d, v = e.index[-1], e.iloc[-1]
        out.append(f'<circle cx="{X(d):.1f}" cy="{Y(v):.1f}" r="4" class="dot s{j+1}"><title>{name}: {v:.2f}</title></circle>')
    out.append("</svg>")
    return "".join(out)

def heatmap(h):
    cs = [float(c) for c in h.columns]; zs = list(h.index)
    vmax = float(np.abs(h.values).max())
    rows = ["<table class='heat'><thead><tr><th>סינון תנועה \\ עלות לצד (bp)</th>" + "".join(f"<th>{c:g}</th>" for c in cs) + "</tr></thead><tbody>"]
    for z in zs:
        cells = []
        for c in h.columns:
            v = float(h.loc[z, c]); a = min(abs(v) / vmax, 1) * 0.85 + 0.08
            cls = "pos" if v >= 0 else "neg"; strong = " strong" if v > 1.0 else ""
            cells.append(f"<td class='{cls}{strong}' style='--a:{a:.2f}' title='|z| ≥ {z:g}, עלות {float(c):g} bp: שארפ {v:.2f}'>{v:.2f}</td>")
        rows.append(f"<tr><th><bdi>|z| ≥ {z:g}</bdi></th>{''.join(cells)}</tr>")
    rows.append("</tbody></table>")
    return "".join(rows)

def regime(reg):
    names = {"gross LIN": "ברוטו", "net LIN": "נטו (עלויות רשומות)", "net |z|≥1 EQ": "נטו, ימי תנועה גדולה"}
    lv = {"low RV": "תנודתיות נמוכה", "mid RV": "תנודתיות בינונית", "high RV": "תנודתיות גבוהה"}
    W, H, l, r, t, b = 560, 260, 40, 10, 14, 34
    vmin, vmax = -1.5, 2.5
    y = lambda v: t + (vmax - v) / (vmax - vmin) * (H - t - b)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="שארפ לפי משטר תנודתיות">']
    for v in [-1, 0, 1, 2]:
        out.append(f'<line x1="{l}" x2="{W-r}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="{"axis" if v==0 else "grid"}"/><text x="{l-6}" y="{y(v)+4:.1f}" class="tick" text-anchor="end">{v}</text>')
    gw = (W - l - r) / 3; bw = gw * 0.78 / 3
    for i, (k, lab) in enumerate(lv.items()):
        for j, s in enumerate(names):
            v = float(reg[(reg.regime == k) & (reg.series == s)].sharpe.iloc[0])
            x = l + i * gw + gw * 0.11 + j * bw; y0, y1 = sorted([y(0), y(v)])
            out.append(f'<rect x="{x+1:.1f}" y="{y0:.1f}" width="{bw-2:.1f}" height="{max(y1-y0,0.5):.1f}" rx="2" class="s{j+1}"><title>{names[s]}, {lab}: {v:.2f}</title></rect>')
            out.append(f'<text x="{x+bw/2:.1f}" y="{(y0-5) if v>=0 else (y1+13):.1f}" class="val" text-anchor="middle">{v:.2f}</text>')
        out.append(f'<text x="{l+i*gw+gw/2:.1f}" y="{H-10}" class="tick" text-anchor="middle">{lab}</text>')
    out.append("</svg>")
    return "".join(out), names

def legend(labels):
    return "<ul class='legend'>" + "".join(f"<li><span class='sw s{j+1}'></span>{l}</li>" for j, l in enumerate(labels)) + "</ul>"

reg_svg, reg_names = regime(reg)
fals_rows = "".join(f"<tr><td>{bdi(r.sym)}</td><td class='num'>{int(r.n)}</td><td class='num {'hi' if r.t>2 else ''}'>{r.t:.2f}</td></tr>"
                    for r in fals.sort_values("t", ascending=False).itertuples())

TEMPLATE = (ROOT / "scripts" / "report_hebrew_template.html").read_text()
out = (TEMPLATE.replace("{{BARS}}", bars_by_year(p3)).replace("{{BARS_LEGEND}}", legend(FAMS))
       .replace("{{EQUITY}}", equity(curves)).replace("{{EQUITY_LEGEND}}", legend([c[0] for c in curves]))
       .replace("{{HEAT}}", heatmap(heat)).replace("{{REGIME}}", reg_svg).replace("{{REGIME_LEGEND}}", legend(list(reg_names.values())))
       .replace("{{FALS}}", fals_rows))
(ROOT / "reports" / "hebrew_report.html").write_text(out)
print("ok", len(out))
