"""Append-only trial log (feeds the deflated Sharpe)."""
import csv, json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "trials.csv"
COLS = ["trial_id", "phase", "hypothesis", "variant", "params_json", "is_start", "is_end", "is_n_trades", "is_sharpe",
        "is_pf", "is_cagr", "is_maxdd", "oos_n_trades", "oos_sharpe", "oos_pf", "notes"]


def next_id():
    with open(PATH) as f:
        return sum(1 for _ in f)  # header counts as row 0 -> ids start at 1


def log(phase, hypothesis, variant, params, is_m=None, oos_m=None, is_start="", is_end="", notes=""):
    is_m, oos_m = is_m or {}, oos_m or {}
    with open(PATH) as f:  # idempotent: re-running a script never double-counts a trial
        for r in csv.DictReader(f):
            if r["phase"] == str(phase) and r["variant"] == variant and r["hypothesis"] == hypothesis:
                return int(r["trial_id"])
    tid = next_id()
    row = dict(trial_id=tid, phase=phase, hypothesis=hypothesis, variant=variant, params_json=json.dumps(params, sort_keys=True),
               is_start=is_start, is_end=is_end, is_n_trades=is_m.get("n_trades", ""), is_sharpe=_r(is_m.get("sharpe")),
               is_pf=_r(is_m.get("pf")), is_cagr=_r(is_m.get("cagr")), is_maxdd=_r(is_m.get("maxdd")),
               oos_n_trades=oos_m.get("n_trades", ""), oos_sharpe=_r(oos_m.get("sharpe")), oos_pf=_r(oos_m.get("pf")), notes=notes)
    with open(PATH, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=COLS).writerow(row)
    return tid


def _r(v):
    return "" if v is None else round(float(v), 4)
