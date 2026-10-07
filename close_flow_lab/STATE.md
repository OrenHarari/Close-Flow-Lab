# Close-Flow Lab — STATE

_Last updated: 2026-10-07 — end of Phase 0_

## Run constants
- Source data (read-only): `OrenHarari/OPEN-CLOSE-TRADE` @ `8ca63a9`, folder `data/` (cloned to `/home/user/open-close-trade`). Never written to.
- **HOLDOUT LOCK: 2025-08-01 → end of data (≥ 2026-08-05 for every core symbol). Locked. Not loaded, plotted or evaluated before Phase FINAL.**
  - Today is 2026-10-07, but the newest local 1-min data ends 2026-08-05 (QQQ/TQQQ/SQQQ) … 2026-09-29 (SOXL/SOXS), and new downloads are blocked (see Phase 0). A uniform start of 2025-08-01 gives ≥ 12 months of holdout for every core symbol.
  - In-sample (IS) = 2016-01-04 → 2025-07-31.
  - Enforcement: `close_flow_lab/src/data.py` drops every bar / daily row with ET date ≥ 2025-08-01 at read time unless `CFL_UNLOCK_HOLDOUT=1`; caches are tagged `_is` vs `_full`.
- Branch: work committed on `CLOSE_FLOW_LAB` (as requested) and mirrored to the session branch `claude/trusting-hawking-wjw3bm`. Never main.

## Counters
- Trials used: **0 / 200**
- Pivots used: **0 / 3**

---

## Phase 0 — Data inventory & fill → **GO** (with documented deviations)

### Findings
- The Close-Flow-Lab repo was empty. The data referred to as "my local data" lives in `OPEN-CLOSE-TRADE/data/{SYMBOL}/{tf}/` as PART+MANIFEST CSV bundles (`timestamp,price(=open),high,low,close,volume,vwap,trades,change_pct`), timestamps = **bar start, UTC**, session window 09:25–16:05 ET (RTH + a few auction-adjacent minutes). Manifests record feed = `alpaca-sip` for every 1m/5m bundle used here (DIA/UDOW/SDOW 5m are IEX → not used; their 1m is SIP).
- Daily: `{sym}/1d/{sym}_1d_full.csv`, Alpaca SIP `adjustment=all` (split + dividend adjusted). Intraday is **raw**.
- Full inventory: `data_inventory/manifest_inventory.csv`; IS quality table: `data_inventory/quality_is.csv`; corporate actions: `data_inventory/corporate_actions_is.csv`.
- Junk check: no `XYZNOTREAL`, no `APPL` folder in this snapshot (only `AAPL`); no download logs; the only zip is an unrelated research export. Nothing to ignore.

### Coverage that matters (IS span; all SIP)
| Pair (bull / bear / underlying) | 1m LETFs | Underlying | Usable IS days |
|---|---|---|---|
| SOXL / SOXS / SOXX | 2016-01-04 → | SOXX **5m** 2016→, 1m 2023→ | 2304 / 2328 / 2349 |
| TQQQ / SQQQ / QQQ | 2016-01-04 → | QQQ 1m 2016→ | 2333 / 2306 / 2372 |
| TNA / TZA / IWM | 2016-01-04 → | IWM 1m 2016→ | 2341 / 2357 / 2376 |
| TECL / TECS / XLK | 2016-01-04 → (thin pre-2019) | XLK 1m 2016→ | 2334 / 2234 / 2373 |
| UDOW / SDOW / DIA | 2022-01-03 → | DIA 1m 2022→ | 802 / 807 / 882 |
| LABU / LABD / XBI | 5m 2020-01-02 → | XBI 5m 2020→ | 1350 / 1348 / 1377 |
| NVDL / NVDS / NVDA | 2022-12 → | NVDA 1m 2020→ | 541 / 627 / 1367 |

### Conventions verified
- **Close price** = OPEN of the 16:00 bar (closing-cross print). Day-to-day drift of raw/adjusted factor: 0.8–3.9 bp median vs 1.4–11.8 bp for the 16:00 close and 2–6 bp for the 15:59 close. Available on 95–99.5 % of days for liquid names (TECL/TECS/NVDL/NVDS 76–85 % → fallback to the 15:59 close).
- **Checkpoint price at T** = close of the last bar ending ≤ T (stale ≤ 30 min allowed for thin LETFs; median staleness 0 min at 15:00). No lookahead by construction.
- **DST**: handled by tz conversion UTC→America/New_York (bars at 09:30 ET exist on both sides of every DST switch).
- **Half-days**: hard-coded NYSE 13:00 early-close calendar, verified against QQQ afternoon-volume share (all 19 IS dates < 0.20 vs ≥ 0.24 on every other day). Excluded.
- **Missing bars / data gaps**: QQQ/TQQQ/SQQQ 2018-05-02/03 contain a single bar → `data_gap`, excluded. Thin LETFs (TECL/TECS pre-2019, NVDS) have many no-trade minutes — that is real illiquidity, not missing data.
- **Splits / reverse splits**: detected from jumps in raw/adjusted factor. All 39 IS events have clean ratios (2:1, 3:1, 1:4, 1:5, 1:10, 1:12, 1:20, 1:8) or are year-end distributions (NVDL/NVDS/SDOW/SOXL Dec). Corrected gaps on split days are normal (|gap| ≤ 4 %). Factor jumps that revert the next day (e.g. SOXL 2020-03-16, where the daily file's close equals its open) are **bad daily rows**, not corporate actions: flagged `daily_mismatch` and not used for corrections. The intraday close matches the daily close to < 1 bp on normal days, so the intraday auction proxy is the price of record.
- **SOXX 5m ≡ 1m at checkpoints**: on 635 overlapping IS days, open / 10:00 / 15:00 / 15:30 / 15:45 / close are identical to 0.0 bp (max). Every signal in this study is on a 5-min boundary, so the 5m SOXX history is equivalent.

### Gate check
- Gate: ≥ 8 underlying/LETF pairs with clean 1-min data 2016→today + verified split handling.
- Result: **8 LETF↔underlying pairs** with clean SIP data from 2016-01-04 (SOXL–SOXX, SOXS–SOXX, TQQQ–QQQ, SQQQ–QQQ, TNA–IWM, TZA–IWM, TECL–XLK, TECS–XLK); split handling verified (39/39 events). Plus 3 short-history families (DIA, XBI, NVDA).
- **Deviations (documented, not hidden):**
  1. "→today": data ends 2026-08-05…2026-09-29, not 2026-10-07. The fill download was **impossible**: the environment's network policy denies `data.alpaca.markets` (and every other market-data host); no Alpaca keys exist in this environment either. The holdout still has ≥ 12 months.
  2. **SPY / UPRO / SPXU not available** (not in the local data, can't download). The S&P 500 family is therefore absent; DIA/UDOW/SDOW (2022→) is the large-cap-index stand-in.
  3. **VIX / VIX3M not available** (not in data; VIX is a CBOE index, not on Alpaca). Phase 1 uses pre-registered *realized-vol* proxies computed from QQQ with data through t−1 only: level = 20-day close-to-close realized vol; "term structure" = RV(5d)/RV(60d) (> 1 = short-term stress ≈ VIX/VIX3M > 1).
  4. SOXX underlying is 5m before 2023 (proven equivalent above).
- Decision: **GO.**

### Devil's advocate
"The data is fine for the signal but the close price you'll trade at is fake: the 16:00 bar open is a single print that may not be the official cross, so backtests will assume fills you can't get." → Tested: the 16:00-bar open matches the SIP daily close to < 1 bp median on normal days (better than any other candidate). On the 0.3–3 % of days where it disagrees with the daily file, it also disagrees with the 15:59 close by the same amount, i.e. the daily row is the outlier. Residual risk: MOC fill = official close, so the proxy is the right price; slippage vs that price is modelled separately in Phase 2.

### Phase 1 plan (self-generated)
1. Build per-day returns from the day tables: `gap` (split-corrected), `on1000` = prev close→10:00, `oc1500` = 09:30→15:00, `oc1530` = 09:30→15:30, `pc1500` / `pc1530` = prev close→15:00 / 15:30, targets `last60` = 15:00→close, `last30` = 15:30→close.
2. Pre-registered specs (predictor ends before target starts):
   - H2 (intraday momentum): S1 on1000→last30, S2 on1000→last60, S3 oc1500→last60, S4 oc1530→last30, S5 oc1500→last30.
   - H1 (LETF rebalancing, flow ∝ day's close-to-close move): S6 pc1530→last30, S7 pc1500→last60.
3. OLS with Newey-West HAC (5 lags) per symbol (7 underlyings + LETFs) and per year; year contribution share = Σ_year (x−x̄)(y−ȳ) / Σ_all.
4. Splits: realized-vol regime (tercile of RV20), RV5/RV60 > 1, |x| quintile, day of week, OPEX (3rd Friday), month-end (last trading day), quarter-end.
5. Decay: slope and t for 2023, 2024, 2025-H1 separately.
6. Gate: a spec passes on an underlying if t > 2.5, same sign in ≥ 70 % of years, no year > 40 % of the total; hypothesis passes if one of its specs passes on ≥ 3 underlyings.
