"""Per-day return features built from data.build_day_table (IS-locked by data.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import data as D

UNDERLYINGS = {"QQQ": "1m", "IWM": "1m", "XLK": "1m", "SOXX": "5m", "DIA": "1m", "XBI": "5m", "NVDA": "1m"}
LETFS = {"TQQQ": "1m", "SQQQ": "1m", "TNA": "1m", "TZA": "1m", "TECL": "1m", "TECS": "1m", "SOXL": "1m",
         "SOXS": "1m", "UDOW": "1m", "SDOW": "1m", "LABU": "5m", "LABD": "5m", "NVDL": "1m", "NVDS": "1m"}
FAMILY = {  # underlying -> (bull, bear)
    "QQQ": ("TQQQ", "SQQQ"), "IWM": ("TNA", "TZA"), "XLK": ("TECL", "TECS"), "SOXX": ("SOXL", "SOXS"),
    "DIA": ("UDOW", "SDOW"), "XBI": ("LABU", "LABD"), "NVDA": ("NVDL", "NVDS"),
}
TF = {**UNDERLYINGS, **LETFS}


def day_returns(sym: str) -> pd.DataFrame:
    d = D.build_day_table(sym, TF[sym])
    d = d[d["usable"]].copy()
    pc = d["open"] / (1 + d["gap_ret"])  # split-corrected previous close in today's price units
    out = pd.DataFrame(index=d.index)
    out["gap"] = d["gap_ret"]
    out["on1000"] = d["p1000"] / pc - 1
    out["oc1500"] = d["p1500"] / d["open"] - 1
    out["oc1530"] = d["p1530"] / d["open"] - 1
    out["pc1500"] = d["p1500"] / pc - 1
    out["pc1530"] = d["p1530"] / pc - 1
    out["pc1545"] = d["p1545"] / pc - 1
    out["r1500_1530"] = d["p1530"] / d["p1500"] - 1
    out["last60"] = d["close"] / d["p1500"] - 1
    out["last30"] = d["close"] / d["p1530"] - 1
    out["last15"] = d["close"] / d["p1545"] - 1
    out["cc"] = d["close"] / pc - 1
    for c in ["p1500", "p1530", "p1545", "p1550", "p1555", "close", "open", "vol_rth", "vol_0930_1000",
              "vol_1530_1600", "rv_to1500", "close_src", "stale1500", "stale1530"]:
        out[c] = d[c]
    return out


def calendar_flags(idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar features known before the open of day t."""
    s = pd.Series(idx, index=idx)
    f = pd.DataFrame(index=idx)
    f["dow"] = idx.dayofweek
    # OPEX = third Friday (if a holiday, the Thursday before is not handled -> rare)
    f["opex"] = (idx.dayofweek == 4) & (idx.day >= 15) & (idx.day <= 21)
    ym = idx.to_period("M")
    last_in_month = s.groupby(ym).transform("max") == s
    f["month_end"] = last_in_month.values
    f["quarter_end"] = f["month_end"] & np.isin(idx.month, [3, 6, 9, 12])
    return f


def vol_regime(ref: str = "QQQ") -> pd.DataFrame:
    """Realized-vol proxies for VIX (level) and VIX/VIX3M (term structure). Uses data through t-1."""
    d = D.build_day_table(ref, TF[ref])
    d = d[~d["data_gap"]]
    cc = np.log(d["close"]).diff() - d["ca_logratio"]
    rv20 = cc.rolling(20).std() * np.sqrt(252)
    rv5 = cc.rolling(5).std() * np.sqrt(252)
    rv60 = cc.rolling(60).std() * np.sqrt(252)
    out = pd.DataFrame({"rv20": rv20.shift(1), "ts_ratio": (rv5 / rv60).shift(1)})
    return out
