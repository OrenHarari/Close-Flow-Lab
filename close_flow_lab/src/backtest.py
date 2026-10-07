"""Close-Flow strategy backtester (daily granularity; one 15:0x->15:3x round trip per family per day).

Signal (P3b): dir = sign(prev close -> 15:00 return of the UNDERLYING), computed from the 14:59 bar close.
Fills: entry = close of the 15:00 bar (i.e. ~15:01:00, 1-minute latency); exit = close of the 15:30 bar
(~15:31:00). Configurable via entry/exit checkpoint names.
Costs per side = cost_mult * estimated half-spread (Abdi-Ranaldo, tick-floored) + slip_bp.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import data as D
import features as F

LEV = {"TQQQ": 3, "SQQQ": -3, "TNA": 3, "TZA": -3, "TECL": 3, "TECS": -3, "SOXL": 3, "SOXS": -3,
       "UDOW": 3, "SDOW": -3, "LABU": 3, "LABD": -3}


def _days(sym):
    return D.build_day_table(sym, F.TF[sym])


def half_spread_table():
    hs = pd.read_parquet(D.CACHE / "half_spread_is.parquet") if not D.UNLOCKED else pd.read_parquet(D.CACHE / "half_spread_full.parquet")
    return hs


def family_trades(fam: str, instrument: str = "L", entry: str = "p1501", exit_: str = "p1531",
                  cost_mult: float = 1.5, slip_bp: float = 0.5, sigma_win: int = 60,
                  exclude_month_end: bool = True, hs: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per eligible day for one family. Returns gross/net trade return of the chosen instrument."""
    u = _days(fam)
    pc = u["open"] / (1 + u["gap_ret"])
    cc = u["close"] / pc - 1
    sig = cc.where(u["usable"]).rolling(sigma_win, min_periods=40).std().shift(1)
    x = u["p1500"] / pc - 1
    df = pd.DataFrame({"x": x, "sigma": sig, "zx": x / sig, "u_usable": u["usable"]})
    cal = F.calendar_flags(u.index)
    df["month_end"] = cal["month_end"]
    df["dir"] = np.sign(df["x"])
    if hs is None:
        hs = half_spread_table()
    if instrument == "U":
        e, xo = u[entry], u[exit_]
        r = (xo / e - 1) * df["dir"]
        h = hs[hs.sym == fam]["half_spread"]
        hsd = h.reindex(df.index)
        df["inst"] = fam
        df["lev"] = 1.0
        df["gross"] = r
        df["inst_ok"] = u["usable"] & e.notna() & xo.notna()
    else:
        bull, bear = F.FAMILY[fam]
        b, s = _days(bull), _days(bear)
        rb = b[exit_] / b[entry] - 1
        rs = s[exit_] / s[entry] - 1
        df["inst"] = np.where(df["dir"] > 0, bull, bear)
        df["gross"] = np.where(df["dir"] > 0, rb.reindex(df.index), rs.reindex(df.index))
        okb = (b["usable"] & b[entry].notna() & b[exit_].notna()).reindex(df.index, fill_value=False)
        oks = (s["usable"] & s[entry].notna() & s[exit_].notna()).reindex(df.index, fill_value=False)
        df["inst_ok"] = np.where(df["dir"] > 0, okb, oks)
        hb = hs[hs.sym == bull]["half_spread"].reindex(df.index)
        hsb = hs[hs.sym == bear]["half_spread"].reindex(df.index)
        hsd = pd.Series(np.where(df["dir"] > 0, hb, hsb), index=df.index)
        df["lev"] = 3.0
    hsd = hsd.fillna(hsd.rolling(20, min_periods=1).median()).fillna(hsd.median())
    tick_half = _tick_half(df, fam, instrument, hs)
    df["cost"] = 2 * (np.maximum(cost_mult * hsd, tick_half) + slip_bp * 1e-4)
    df["net"] = df["gross"] - df["cost"]
    elig = df["u_usable"] & df["inst_ok"].astype(bool) & df["sigma"].notna() & (df["dir"] != 0)
    if exclude_month_end:
        elig &= ~df["month_end"]
    df["eligible"] = elig
    df["fam"] = fam
    return df


def _tick_half(df, fam, instrument, hs):
    if instrument == "U":
        t = hs[hs.sym == fam]["tick_half"].reindex(df.index)
    else:
        bull, bear = F.FAMILY[fam]
        tb = hs[hs.sym == bull]["tick_half"].reindex(df.index); ts = hs[hs.sym == bear]["tick_half"].reindex(df.index)
        t = pd.Series(np.where(df["dir"] > 0, tb, ts), index=df.index)
    return t.fillna(t.median()).fillna(0.0)


def weights(df: pd.DataFrame, sizing: str, sigma_ref: float | None = None, zcap: float = 2.0) -> pd.Series:
    """Notional weight per unit equity. EQ: 1/lev-free notional 1. VOL: risk-scaled. LIN: VOL * clip(|z|)."""
    if sizing == "EQ":
        w = pd.Series(1.0, index=df.index)
    else:
        ref = sigma_ref if sigma_ref is not None else 0.01
        w = ref / df["sigma"]  # LETF return already embeds its leverage
        if sizing == "LIN":
            w = w * df["zx"].abs().clip(upper=zcap)
    return w.where(df["eligible"], 0.0).fillna(0.0)


def portfolio(fams, instrument="L", sizing="EQ", z_min: float = 0.0, **kw):
    """Equal-weight basket of families; daily net return series (0 on no-trade days)."""
    rets, gross, trades = [], [], []
    for f in fams:
        df = family_trades(f, instrument, **kw)
        if z_min > 0:
            df["eligible"] &= df["zx"].abs() >= z_min
        w = weights(df, sizing)
        rets.append((w * df["net"]).rename(f).fillna(0.0))
        gross.append((w * df["gross"]).rename(f).fillna(0.0))
        t = df[df["eligible"]].assign(w=w[df["eligible"]])
        trades.append(t)
    R = pd.concat(rets, axis=1).fillna(0.0)
    G = pd.concat(gross, axis=1).fillna(0.0)
    return R.mean(axis=1), G.mean(axis=1), pd.concat(trades)


def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) == 0 or r.std() == 0:
        return dict(sharpe=np.nan, pf=np.nan, cagr=np.nan, maxdd=np.nan, ann_vol=np.nan, n_days=len(r))
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1
    yrs = len(r) / 252
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    return dict(sharpe=float(r.mean() / r.std() * np.sqrt(252)), pf=float(pos / neg) if neg > 0 else np.inf,
                cagr=float(eq.iloc[-1] ** (1 / yrs) - 1), maxdd=float(dd.min()), ann_vol=float(r.std() * np.sqrt(252)),
                n_days=int(len(r)))
