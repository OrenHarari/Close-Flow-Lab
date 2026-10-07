"""Phase 2 cost model: bar-based half-spread estimator calibrated on SIP NBBO quotes (IS rows only).
Estimator: Abdi-Ranaldo (2017) close/high/low spread on 1m (or 5m) bars, per day over 14:30-15:45 ET,
floored at the 1-cent tick. Calibration window: 15:50-15:59 where both quotes and bars exist."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
import data as D

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"; OUT.mkdir(parents=True, exist_ok=True)


def ar_spread(b):
    """Abdi-Ranaldo relative spread per day from bars (sorted)."""
    b = b.copy()
    eta = np.log((b["h"] + b["l"]) / 2); c = np.log(b["c"])
    b["eta"] = eta; b["lc"] = c
    b["eta_next"] = b.groupby("date")["eta"].shift(-1)
    prod = (b["lc"] - b["eta"]) * (b["lc"] - b["eta_next"])
    s2 = 4 * prod.groupby(b["date"]).mean()
    return np.sqrt(s2.clip(lower=0))


def quotes_spread(sym):
    fs = sorted(D.SRC.glob(f"{sym}/quotes/{sym}_quotes_1s_*.csv"))
    out = []
    for f in fs:
        q = pd.read_csv(f, usecols=["timestamp", "bid", "ask", "spread_bps"])
        ts = pd.to_datetime(q["timestamp"], utc=True).dt.tz_convert(D.ET)
        q["date"] = ts.dt.tz_localize(None).dt.normalize(); q["mins"] = ts.dt.hour * 60 + ts.dt.minute
        q = q[(q["date"] < D.HOLDOUT_START) & (q["mins"] >= 950) & (q["mins"] < 960) & (q["ask"] > q["bid"])]
        out.append(q.groupby("date")["spread_bps"].median())
    return pd.concat(out) if out else pd.Series(dtype=float)


if __name__ == "__main__":
    calib = []
    for sym, tf in [("SOXL", "1m"), ("SOXS", "1m"), ("TNA", "1m")]:
        qs = quotes_spread(sym)
        b = D.load_bars(sym, tf); b = b[(b["mins"] >= 950) & (b["mins"] < 960)]
        ar = ar_spread(b) * 1e4
        j = pd.DataFrame({"quoted_bps": qs, "ar_bps": ar}).dropna()
        calib.append(dict(sym=sym, days=len(j), quoted_med=j.quoted_bps.median(), ar_med=j.ar_bps.median(), ratio=j.quoted_bps.median() / max(j.ar_bps.median(), 1e-9)))
    calib = pd.DataFrame(calib); print(calib.round(2)); calib.to_csv(OUT / "spread_calibration.csv", index=False)
    syms = {"QQQ": "1m", "IWM": "1m", "XLK": "1m", "SOXX": "5m", "TQQQ": "1m", "SQQQ": "1m", "TNA": "1m", "TZA": "1m",
            "TECL": "1m", "TECS": "1m", "SOXL": "1m", "SOXS": "1m", "XBI": "5m", "LABU": "5m", "LABD": "5m", "DIA": "1m", "UDOW": "1m", "SDOW": "1m"}
    rows = []
    for sym, tf in syms.items():
        b = D.load_bars(sym, tf)
        w = b[(b["mins"] >= 870) & (b["mins"] < 945)]
        ar = ar_spread(w)
        px = w.groupby("date")["c"].median()
        tick = 0.01 / px
        hs = np.maximum(ar, tick) / 2  # half-spread, relative
        df = pd.DataFrame({"half_spread": hs, "tick_half": tick / 2, "px": px})
        df["sym"] = sym
        rows.append(df)
        print(sym, "median half-spread bp by year:", (df["half_spread"].groupby(df.index.year).median() * 1e4).round(2).to_dict(), flush=True)
    allc = pd.concat(rows)
    allc.to_parquet(D.CACHE / "half_spread_is.parquet")
