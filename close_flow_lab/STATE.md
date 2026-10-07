# Close-Flow Lab — STATE

_Last updated: 2026-10-07 — TERMINAL: **KILL** (Phase 2 failed after 3 pivots)_

## Run constants
- Source data (read-only): `OrenHarari/OPEN-CLOSE-TRADE` @ `8ca63a9`, folder `data/` (cloned to `/home/user/open-close-trade`). Never written to.
- **HOLDOUT LOCK: 2025-08-01 → end of data (≥ 2026-08-05 for every core symbol). Locked. Not loaded, plotted or evaluated before Phase FINAL.**
  - Today is 2026-10-07, but the newest local 1-min data ends 2026-08-05 (QQQ/TQQQ/SQQQ) … 2026-09-29 (SOXL/SOXS), and new downloads are blocked (see Phase 0). A uniform start of 2025-08-01 gives ≥ 12 months of holdout for every core symbol.
  - In-sample (IS) = 2016-01-04 → 2025-07-31.
  - Enforcement: `close_flow_lab/src/data.py` drops every bar / daily row with ET date ≥ 2025-08-01 at read time unless `CFL_UNLOCK_HOLDOUT=1`; caches are tagged `_is` vs `_full`.
- Branch: work committed on `CLOSE_FLOW_LAB` (as requested) and mirrored to the session branch `claude/trusting-hawking-wjw3bm`. Never main.

## Counters
- Trials used: **84 / 200** (30 Phase-2 pre-registered + 30 Phase-2 corrected-cost re-run + 24 post-mortem diagnostics, all in `trials.csv`)
- Pivots used: **3 / 3**
- Phase-1 effect specs tested (not strategy trials): 7 + 2 + 2 + 2 = 13, plus a 21-instrument falsification run

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

---

## Phase 1 — Effect validation → **FAIL → PIVOT #1**

Script: `scripts/phase1_effect.py` → `reports/phase1/effect_full.csv`, `effect_by_year.csv`, `effect_splits.csv`.
7 pre-registered specs × 7 underlyings + 14 LETFs, OLS + Newey-West(5).

### Gate numbers (underlyings; pass = t>2.5 & same-sign ≥70 % of years & max year share ≤ 40 %)
| spec | QQQ t | IWM t | XLK t | SOXX t | DIA t | XBI t | NVDA t | # pass |
|---|---|---|---|---|---|---|---|---|
| S1 on1000→last30 (Gao et al.) | 0.91 | 0.20 | 1.18 | −0.18 | −1.14 | 1.61 | 0.12 | 0 |
| S2 on1000→last60 | 1.27 | 0.67 | 1.52 | 1.21 | −0.68 | 2.05 | 0.34 | 0 |
| S3 oc1500→last60 | 1.89 | 0.94 | 1.26 | 2.09 | 0.70 | 2.76 (share 0.50) | 2.28 | 0 |
| S4 oc1530→last30 | 1.11 | −0.89 | 0.76 | 0.61 | 0.62 | 1.79 | 2.02 | 0 |
| S5 oc1500→last30 | 0.65 | −1.03 | 0.42 | 0.34 | 0.12 | 1.21 | 1.82 | 0 |
| S6 pc1530→last30 (LETF) | 1.50 | −0.34 | 1.77 | 0.41 | 0.11 | 2.75 (same-sign 0.50) | 1.21 | 0 |
| S7 pc1500→last60 (LETF) | 2.58 (same-sign 0.50, 2020 share 0.52) | 1.26 | 2.60 (0.50, 0.57) | **2.51 (0.90, 0.28) ✔** | 0.64 | 3.41 (0.67, 0.55) | 1.77 | **1** |

- **H2 (Gao-Han-Li-Zhou first-30 → last-30) is absent in 2016-2025** on every ETF (t between −1.1 and 1.6; sign flips year to year). Dead.
- **H1 (day's move → last hour) exists but is not stable**: S7 t≈2.5–3.4 on QQQ/XLK/SOXX/XBI; winsorized t 2.9–3.7. Per-year: carried by 2018, 2020, 2022, 2023; negative in 2016, 2019, 2024 for QQQ/XLK.
- Decay check (S7 t, 2023 / 2024 / 2025-H1): QQQ 4.11 / −0.89 / 0.61; XLK 3.83 / −0.74 / 0.61; SOXX 2.96 / 0.41 / 0.56; IWM 1.10 / −0.98 / 0.65 → no reliable recent effect except 2023.
- Splits (S7): strongest in high RV20 tercile (t 2.3–3.3) and top |move| quintile (t 2.2–2.7); ≈0 in low-vol tercile; **negative at month-end and quarter-end** (QQQ −2.2 bp, IWM quarter-end −7.6 bp), consistent with opposing pension rebalancing; weak on OPEX days.
- Gate: S7 passes on 1/7 underlyings (need ≥ 3). **FAIL.**

### Devil's advocate (Phase 1)
"Even the 'significant' S7 is just 2020 + 2022." → Confirmed by the year-share column (QQQ 2020 share 52 %, XLK 57 %). Excluding 2020, t drops to 2.17 (QQQ) / 2.02 (XLK) / 2.05 (SOXX). The gate rightly rejects it.

### PIVOT #1 (pre-registered before running) — H1′ big-move LETF flow
Structural reason: rebalancing $ = Σ AUM·L(L−1)·r_day. It moves the close only when it is large relative to closing liquidity (big |r| days). Month-end pension/balanced-fund rebalancing trades the other way. Specs: P1a pc1500→last60 and P1b pc1530→last30 on days with |x| ≥ 1.0·σ60(t−1), excluding month-end. Gate unchanged.

**Result: FAIL.** P1a passes only on SOXX (t 2.72, same-sign 0.90, max share 0.36). QQQ t 2.62 / XLK t 2.70 fail on year concentration (2020 share 0.61 / 0.63) and same-sign (0.60 / 0.67). IWM 1.33, DIA 0.31, XBI 2.21, NVDA 1.02. P1b passes nowhere. Pivots used: 1/3.

### Reading of the evidence so far
The effect is real in **risk units but crisis-weighted in return units**: raw-return covariances weight each day by σ², so 2020 dominates every pooled estimate. A trader sizing by risk (vol-targeting) does not earn the σ²-weighted effect; they earn the z-scored effect. That gives PIVOT #2.

### PIVOT #2 (pre-registered before running) — vol-scaled LETF flow
Structural reason: (i) rebalancing demand is proportional to the move, and market makers' required compensation for absorbing it scales with σ (inventory risk), so the continuation should be stable **per unit of risk**, not per dollar; (ii) month-end opposing flow, as in Pivot 1. Specs:
- P2a: x = pc1500/σ60(t−1), y = last60/σ60(t−1), all usable days except month-end.
- P2b: same as P2a, only days with |x| ≥ 1.
Gate unchanged (t>2.5 NW on ≥3 underlyings, same sign ≥70 % of years, no year > 40 % of total, computed on the scaled series).

**PIVOT #2 result: FAIL.** P2a passes on SOXX only (t 3.21, same-sign 0.90, max share 0.36 [2018]); XLK t 2.80 (same-sign 0.60 ✗), XBI t 2.85 (same-sign 0.67 ✗), QQQ t 2.35, IWM 1.83, NVDA 1.45, DIA −0.13. P2b: SOXX only. Vol-scaling removed the 2020 dominance (max year is now 2018 Q4) but year-to-year sign instability remains (2016, 2019, 2024 negative for QQQ/XLK). Pivots used: 2/3.

### Diagnostics before the last pivot (IS, not a trial)
Decomposing the vol-scaled S7 effect inside the last hour (x = pc1500/σ, NW t):
| window | QQQ | IWM | XLK | SOXX | XBI | NVDA | DIA |
|---|---|---|---|---|---|---|---|
| 15:00→15:30 | **3.42** | **2.53** | **2.92** | **3.15** | 2.29 | 1.67 | 1.33 |
| 15:30→15:45 | 1.20 | −0.22 | 1.01 | −0.08 | −1.02 | −1.44 | 0.13 |
| 15:45→15:55 | 0.77 | 0.29 | 1.30 | 2.48 | 4.05 | 2.61 | −0.89 |
| 15:55→close (auction) | 0.12 | 0.77 | 1.34 | 0.69 | 0.32 | 0.45 | −1.77 |

→ The closing auction itself carries **no** continuation; the drift happens in the continuous market before the 15:50 MOC-imbalance publication. LETF intensity proxy (LETF $vol·|L(L−1)| / underlying $vol, median by year): SOXX 3→40, QQQ 1–5.5, XBI 2–5, DIA 2–3, IWM 1–1.6, XLK 0.1–1.9, NVDA ≈ 0.

### PIVOT #3 (last; pre-registered before running) — pre-imbalance continuation window
Structural reason: LETF rebalancing size is (nearly) known from ~15:00 (Σ AUM·L(L−1)·r). Swap dealers / issuers and the liquidity providers who will absorb the MOC imbalance pre-hedge in the continuous market rather than in the auction; once NYSE/Nasdaq publish the imbalance at 15:50 the information is public and gets arbitraged, so the drift should be in 15:00→15:50, not in the auction. Exit before 15:50 also avoids month-end/index flows that print in the auction.
Specs (vol-scaled, month-end excluded, as Pivot 2):
- P3a (principled): y = (p1550/p1500 − 1)/σ60(t−1).
- P3b (data-suggested, flagged as highest snooping risk): y = (p1530/p1500 − 1)/σ60(t−1).
Gate unchanged. If both fail → KILL.

**PIVOT #3 result: GATE PASSED by P3b.**
| spec | QQQ | IWM | XLK | SOXX | DIA | XBI | NVDA | # pass |
|---|---|---|---|---|---|---|---|---|
| P3a 15:00→15:50 | **3.19 ✔** | 1.37 | **2.97 ✔** | 1.97 | 1.01 | 0.37 | 0.51 | 2 ✗ |
| P3b 15:00→15:30 | **3.42 ✔** (same-sign 0.70, max share 0.25) | **2.53 ✔** (0.70, 0.21) | **2.92 ✔** (0.80, 0.31) | **3.15 ✔** (0.80, 0.29) | 1.33 | 2.29 | 1.67 | **4 ✔** |
- Decay (P3b per-year t, 2023 / 2024 / 2025-H1): QQQ 6.42 / 0.06 / 1.20; XLK 6.95 / −0.46 / 1.14; SOXX 4.40 / 0.34 / 1.55; IWM 1.02 / −0.01 / 1.24. 2024 ≈ 0 everywhere: a warning sign.
- **Devil's advocate:** "P3b was picked after seeing the 15:00→15:30 decomposition on the same data, so its t-stats are circular." Test (pre-registered refutation rule: ≥ 70 % positive slopes and median t > 1 on instruments never looked at): 21 fresh instruments (AAPL, MSFT, AMZN, GOOGL, TSLA, INTC, AMD, AVGO, MU, AMAT, LRCX, KLAC, QCOM, TXN, ASML, TSM, SMH, GLD, SLV, GDX, IBIT) → **20/21 positive, median t 1.53 → refuted**. The pattern matches the mechanism: semis names (SOXL basket) t 2.2–3.1, gold/IBIT ≈ 0. `reports/phase1/falsification_p3b.csv`.
- Decision: **GO → Phase 2** with P3b (entry 15:00, exit 15:30, direction = sign of prev-close→15:00, month-end excluded).

---

## Phase 2 — Baseline strategy → **FAIL → KILL** (no pivots left)

Pre-registered grid (30 trials): instrument {LETF bull/bear, underlying long/short} × sizing {EQ, VOL, LIN} × universe {basket of the 4 gate-passing families, each alone}. Entry 15:01 (1-min latency), exit 15:31. Month-end excluded. Random baseline = same days/weights/costs, random direction, 2000 draws.

Costs (pre-registered): per side = 1.5 × Abdi-Ranaldo half-spread (tick-floored, from 14:30–15:45 bars) + 0.5 bp.

| variant | gross SR | net SR | PF | MaxDD | p vs random |
|---|---|---|---|---|---|
| Basket LETF EQ | 1.60 | −0.46 | 0.91 | −62 % | <0.001 |
| Basket LETF LIN | 1.57 | 0.04 | 1.01 | −31 % | <0.001 |
| Basket underlying LIN | 1.46 | −0.15 | 0.96 | −16 % | <0.001 |
| QQQ underlying LIN | 1.42 | 0.28 | 1.08 | −13 % | <0.001 |
| **SOXX LETF LIN (best)** | 1.69 | **0.28** | 1.07 | −34 % | <0.001 |
Gate (net SR > 1.0, PF > 1.3, p < 0.05): **0 / 30**.

**Calibration error found and corrected (disclosed):** the NBBO calibration file holds quoted/estimator = 0.85 (SOXL) and 0.70 (SOXS), i.e. the bar estimator **over**-states quoted spreads; the 1.5× multiplier came from reading it backwards. Re-ran all 30 variants with a quote-calibrated model (0.8 × estimator, floored at ½ tick, + 0.5 bp): best = SOXX LETF LIN **0.78** (PF 1.22), basket LETF LIN 0.56, QQQ underlying LIN 0.57 → still **0 / 30**. Even quoted half-spread alone with zero slippage gives a best of 0.99 (QQQ underlying LIN). The FAIL does not depend on the cost model.

Why: gross edge ≈ 1.5–2 bp/trade on the underlying and ≈ 5 bp on the LETF; LETF round-trip costs are 3–8 bp (SOXS/TECS/SQQQ spreads are wide). Net edge is positive only on |z| ≥ 1 days (+4.6 to +14 bp/trade).

### Devil's advocate (Phase 2)
"The KILL is fake: costs are overstated." → Tested above with three cost models (pre-registered, quote-calibrated, half-spread-only with zero slippage); no variant reaches 1.0. "The best filter (|z| ≥ 1) would pass." → It is a Phase-3 filter, selected post hoc; diagnostic only: quote-calibrated basket LETF EQ |z| ≥ 1 = SR 1.07, PF 1.43, MaxDD −7 %, 7/10 years positive, **deflated-Sharpe probability 0.08** (84 trials) → not significant. Recorded as the best lead, not as a result.

### Decision: **KILL.**
Pivot budget exhausted (3/3) and Phase 2 failed. Phase 3 and Phase FINAL were not run. **The holdout (2025-08-01 →) was never loaded, plotted or evaluated and remains clean** for one future pre-registered test.

### Terminal outputs
`FINAL_REPORT.md`, `trials.csv` (84 rows), `configs/close_flow_preclose_continuation.yaml` (catalog entries: rejected strategy + untested lead), `reports/` (all tables and figures).
