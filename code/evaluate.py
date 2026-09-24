"""Scores, calibration and match-clustered bootstrap intervals from data/preds.parquet.

Outputs (aggregate only, publishable):
  results/metrics_units.csv   every design x split/unit x model: log loss, Brier + CORP terms, AUC, calibration
  results/metrics_groups.csv  the same pooled over the four groups and over all units
  results/gain.csv            gain from geometry (LOC - GEO, positive = GEO better) with 95 % bootstrap CIs,
                              and the transfer penalty (loco - within) of each feature set
  results/recal.csv           LOCO forecasts recalibrated (logistic intercept + slope) on the first
                              10 matches of the held-out unit, scored on its remaining matches
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

import metrics as M

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)
MODELS = ["GLM_LOC", "GLM_GEO", "GBM_LOC", "GBM_GEO", "statsbomb_xg"]
B, SEED = 2000, 20260924


def table(p, keys):
    rows = []
    for k, g in p.groupby(keys):
        for m in MODELS:
            rows.append({**dict(zip(keys, k if isinstance(k, tuple) else (k,))), "model": m,
                         **M.all_metrics(g.goal.values, g[m].values)})
    return pd.DataFrame(rows)


def cluster_boot(g, stat, rng):
    """Match-clustered bootstrap of stat(frame) (matches resampled within units)."""
    idx = {mid: np.flatnonzero(g.match_id.values == mid) for mid in g.match_id.unique()}
    by_unit = g.groupby("unit").match_id.unique()
    out = []
    for _ in range(B):
        take = np.concatenate([idx[m] for ms in by_unit for m in rng.choice(ms, size=len(ms))])
        out.append(stat(g.iloc[take]))
    return np.percentile(out, [2.5, 97.5])


def ll(g, m):
    return M.logloss(g.goal.values, g[m].values)


def br(g, m):
    return M.brier(g.goal.values, g[m].values)


def gains(p):
    rng = np.random.default_rng(SEED)
    rows = []
    loco, within = p[p.design == "loco"], p[p.design == "within"].set_index("id")
    for scope, g in [("all", loco)] + list(loco.groupby("group")):
        for kind in ("GLM", "GBM"):
            lo, ge = f"{kind}_LOC", f"{kind}_GEO"
            for sname, f in (("logloss", ll), ("brier", br)):
                d = f(g, lo) - f(g, ge)
                ci = cluster_boot(g, lambda h: f(h, lo) - f(h, ge), rng)
                w = within.loc[g.id]
                w = w.assign(unit=g.unit.values, match_id=g.match_id.values)
                pen_lo, pen_ge = f(g, lo) - f(w, lo), f(g, ge) - f(w, ge)
                rows.append({"scope": scope, "model": kind, "score": sname, "n": len(g), "gain": d,
                             "gain_lo": ci[0], "gain_hi": ci[1], "rel_gain": d / f(g, lo),
                             "penalty_LOC": pen_lo, "penalty_GEO": pen_ge})
                print(rows[-1], flush=True)
    return pd.DataFrame(rows)


def recal(p, k=10):
    rows = []
    loco = p[p.design == "loco"]
    for u, g in loco.groupby("unit"):
        ms = np.sort(g.match_id.unique())
        cal, ev = g[g.match_id.isin(ms[:k])], g[~g.match_id.isin(ms[:k])]
        for m in MODELS[:4]:
            lr = LogisticRegression(C=1e6).fit(M.logit(cal[m].values).reshape(-1, 1), cal.goal)
            q = lr.predict_proba(M.logit(ev[m].values).reshape(-1, 1))[:, 1]
            for how, f in (("none", ev[m].values), ("recal", q)):
                rows.append({"unit": u, "group": g.group.iloc[0], "model": m, "how": how,
                             **M.all_metrics(ev.goal.values, f)})
    return pd.DataFrame(rows)


def main():
    p = pd.read_parquet(ROOT / "data" / "preds.parquet")
    table(p, ["design", "split"]).to_csv(RES / "metrics_units.csv", index=False)
    lp = p[p.design == "loco"]
    grp = pd.concat([table(lp, ["group"]).assign(design="loco"),
                     table(lp.assign(group="all"), ["group"]).assign(design="loco"),
                     table(p[p.design == "within"].assign(group="all"), ["group"]).assign(design="within"),
                     table(p[p.design == "within"], ["group"]).assign(design="within"),
                     table(p[p.design == "cross"], ["split", "group"]).assign(design="cross")])
    grp.to_csv(RES / "metrics_groups.csv", index=False)
    gains(p).to_csv(RES / "gain.csv", index=False)
    recal(p).to_csv(RES / "recal.csv", index=False)


if __name__ == "__main__":
    main()
