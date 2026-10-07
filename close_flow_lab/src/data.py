"""Close-Flow Lab data layer.

Reads the read-only OPEN-CLOSE-TRADE `data/` tree and produces one row per
(symbol, trading day) with the raw prices needed by every phase.

HOLDOUT LOCK: every bar / daily row with ET date >= HOLDOUT_START is dropped at
read time unless the environment variable CFL_UNLOCK_HOLDOUT=1 is set (Phase
FINAL only). Caches are written to separate files for locked / unlocked runs.

Conventions (verified in Phase 0, see STATE.md):
  * Bar timestamps are bar START times in UTC -> converted to America/New_York
    (handles DST).  CSV column `price` is the bar OPEN.
  * "Price at time T" = close of the last bar that ENDS at or before T
    (start <= T - tf).  A signal at T therefore only uses bars closed before T.
  * Official close (MOC fill) proxy = OPEN of the 16:00 bar (the closing-cross
    print is the first trade stamped 16:00:00).  Verified against the SIP daily
    close: median day-to-day factor drift 0.8-3.9 bp vs 1.4-11.8 bp for the
    16:00 close and 2-6 bp for the 15:59 close.  Fallback: 15:59 close.
  * Splits / reverse splits / dividends: intraday prices are RAW; the overnight
    gap is corrected with the ratio of raw-close / adjusted-close factors from the
    SIP `adjustment=all` daily file.
  * Half-days (no bars between 13:05 and 15:55) are flagged and excluded by
    downstream phases.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(os.environ.get("CFL_SRC", "/home/user/open-close-trade/data"))
CACHE = Path(os.environ.get("CFL_CACHE", Path(__file__).resolve().parents[1] / "cache"))
HOLDOUT_START = pd.Timestamp("2025-08-01")
UNLOCKED = os.environ.get("CFL_UNLOCK_HOLDOUT") == "1"
ET = "America/New_York"

# NYSE 13:00 early closes. Verified for the IS span against QQQ afternoon-volume share
# (all 19 IS dates < 0.2 of RTH volume vs >= 0.24 on every other day).
HALF_DAYS = pd.to_datetime([
    "2016-11-25", "2017-07-03", "2017-11-24", "2018-07-03", "2018-11-23", "2018-12-24",
    "2019-07-03", "2019-11-29", "2019-12-24", "2020-11-27", "2020-12-24", "2021-11-26",
    "2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24",
    "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27", "2026-12-24",
])

# checkpoints (ET, HH:MM) at which we record the price
MAX_STALE_MIN = 30  # thin LETFs (early TECL/TECS, NVDS) have minutes with no trades
CHECKPOINTS = ["10:00", "10:30", "12:00", "14:00", "15:00", "15:15", "15:30", "15:45", "15:50", "15:55"]


def _tag() -> str:
    return "full" if UNLOCKED else "is"


def _hm_to_min(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def load_bars(sym: str, tf: str = "1m") -> pd.DataFrame:
    """RTH bars 09:30-16:00 (16:00 bar kept for the closing print), ET, holdout dropped."""
    files = sorted(glob.glob(str(SRC / sym / tf / f"{sym}_{tf}_*_PART*.csv")))
    if not files:
        raise FileNotFoundError(f"no {tf} bundles for {sym}")
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df = df.drop_duplicates("timestamp", keep="first")
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(ET)
    out = pd.DataFrame({
        "date": ts.dt.tz_localize(None).dt.normalize(),
        "mins": ts.dt.hour * 60 + ts.dt.minute,
        "o": df["price"].astype(float).values,
        "h": df["high"].astype(float).values,
        "l": df["low"].astype(float).values,
        "c": df["close"].astype(float).values,
        "v": df["volume"].astype(float).values,
    })
    if not UNLOCKED:
        out = out[out["date"] < HOLDOUT_START]
    out = out[(out["mins"] >= 570) & (out["mins"] <= 960)]
    return out.sort_values(["date", "mins"]).reset_index(drop=True)


def load_daily(sym: str) -> pd.DataFrame:
    p = SRC / sym / "1d" / f"{sym.lower()}_1d_full.csv"
    d = pd.read_csv(p, parse_dates=["Date"]).rename(columns=str.lower).set_index("date").sort_index()
    d = d[~d.index.duplicated(keep="last")]
    if not UNLOCKED:
        d = d[d.index < HOLDOUT_START]
    return d


def build_day_table(sym: str, tf: str = "1m") -> pd.DataFrame:
    """One row per trading day with raw checkpoint prices and quality flags."""
    cache = CACHE / f"days_{sym}_{tf}_{_tag()}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    b = load_bars(sym, tf)
    step = int(tf.rstrip("m"))
    rth = b[b["mins"] < 960]
    g = rth.groupby("date")
    day = pd.DataFrame({
        "n_bars": g.size(),
        "first_min": g["mins"].min(),
        "last_min": g["mins"].max(),
        "vol_rth": g["v"].sum(),
    })
    first = rth[rth["mins"] == 570].set_index("date")
    day["open"] = first["o"]
    # bars closing at/before checkpoint; staleness <= 5 min
    for hm in CHECKPOINTS:
        t = _hm_to_min(hm)
        sub = rth[(rth["mins"] <= t - step) & (rth["mins"] >= t - step - MAX_STALE_MIN)]
        last = sub.groupby("date").tail(1).set_index("date")
        day[f"p{hm.replace(':', '')}"] = last["c"]
        day[f"stale{hm.replace(':', '')}"] = t - step - last["mins"]
    last_reg = rth[(rth["mins"] <= 959 - step + 1) & (rth["mins"] >= 959 - step + 1 - 5)].groupby("date").tail(1).set_index("date")
    day["c_last"] = last_reg["c"]
    b16 = b[b["mins"] == 960].set_index("date")
    day["c_auction"] = b16["o"]
    day["close"] = day["c_auction"].fillna(day["c_last"])
    day["close_src"] = np.where(day["c_auction"].notna(), "auction16", "last_bar")
    # windowed volume / realized vol
    for name, lo, hi in [("vol_0930_1000", 570, 600), ("vol_1500_1600", 900, 960), ("vol_1530_1600", 930, 960)]:
        day[name] = rth[(rth["mins"] >= lo) & (rth["mins"] < hi)].groupby("date")["v"].sum()
    pre15 = rth[rth["mins"] < 900].copy()
    pre15["lr"] = np.log(pre15["c"]).groupby(pre15["date"]).diff()
    day["rv_to1500"] = np.sqrt((pre15["lr"] ** 2).groupby(pre15["date"]).sum())
    day["hi_to1500"] = pre15.groupby("date")["h"].max()
    day["lo_to1500"] = pre15.groupby("date")["l"].min()
    day["half_day"] = day.index.isin(HALF_DAYS)
    day["expected_bars"] = np.where(day["half_day"], 210 // step, 390 // step)
    day["missing_bars"] = day["expected_bars"] - day["n_bars"]

    # split / dividend correction of the overnight gap from the adjusted daily file
    d = load_daily(sym)
    day = day.join(d[["open", "close"]].rename(columns={"open": "adj_open", "close": "adj_close"}), how="left")
    f = np.log(day["close"] / day["adj_close"])
    r = f.diff().fillna(0.0)  # log(f_t / f_{t-1})
    big = r.abs() > 0.0015
    # a factor jump that reverts the next day is a bad daily (or bad intraday) close,
    # not a corporate action -> ignore both legs and flag the day
    nxt = r.shift(-1).fillna(0.0)
    revert = big & big.shift(-1, fill_value=False) & ((r + nxt).abs() < 0.3 * r.abs())
    day["daily_mismatch"] = revert
    r_used = r.where(big & ~revert & ~revert.shift(1, fill_value=False), 0.0)
    day["ca_logratio"] = r_used
    day["ca_flag"] = r_used.abs() > 0.03  # split-size event
    day["prev_close"] = day["close"].shift(1)
    day["gap_ret"] = np.exp(np.log(day["open"] / day["prev_close"]) - r_used) - 1
    # sanity: intraday open->close vs adjusted daily open->close
    day["oc_raw"] = day["close"] / day["open"] - 1
    day["oc_adj"] = day["adj_close"] / day["adj_open"] - 1
    # data-gap days (e.g. QQQ/TQQQ/SQQQ 2018-05-02/03 hold a single bar)
    yr_med = day.groupby(day.index.year)["n_bars"].transform("median")
    day["data_gap"] = day["n_bars"] < 0.5 * yr_med
    need = ["open", "p1000", "p1500", "p1530", "close", "prev_close"]
    day["usable"] = ~day["half_day"] & ~day["data_gap"] & day[need].notna().all(axis=1)
    day["sym"] = sym
    day["tf"] = tf
    day.index.name = "date"
    CACHE.mkdir(parents=True, exist_ok=True)
    day.to_parquet(cache)
    return day


def bar_returns_last(sym: str, tf: str = "1m") -> pd.DataFrame:
    """Helper for Phase 2 cost estimation: raw bars (holdout-locked)."""
    return load_bars(sym, tf)
