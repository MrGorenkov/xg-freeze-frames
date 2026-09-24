"""Scores, calibration and match-clustered bootstrap intervals from data/preds.parquet.

Outputs (aggregate only, publishable):
  results/metrics_units.csv   every design x split/unit x model: log loss, Brier + CORP terms, AUC, calibration
  results/metrics_groups.csv  the same pooled over the four groups and over all units
  results/corp_logloss.csv    CORP decomposition of the log score (pooled) and the mean unit-level MCB, LOCO
  results/gain.csv            gain from geometry (LOC - GEO, positive = GEO better), absolute and relative, with 95 %
                              match-bootstrap CIs; transfer penalties (loco - within, loco_sub - within)
  results/oe_spread.json      between-unit spread of log(observed/expected goals): mean |log O/E|, and the
                              between-unit SD tau with binomial sampling noise removed (method of moments), for LOCO
                              and cross-group transfer, with bootstrap CIs of the LOC - GEO differences
  results/recal.csv           LOCO forecasts recalibrated on the first 10 matches (by date) of each held-out unit and
                              scored on its remaining matches: logistic intercept + slope, intercept only, and
                              intercept + slope shrunk towards (0, 1)
The bootstrap resamples matches within units and holds the fitted models fixed (training variability is not included).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

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


class Boot:
    """Match-clustered bootstrap indices (matches resampled within units)."""

    def __init__(self, g, rng, b=B):
        idx = {mid: np.flatnonzero(g.match_id.values == mid) for mid in g.match_id.unique()}
        by_unit = g.groupby("unit").match_id.unique()
        self.samples = [np.concatenate([idx[m] for ms in by_unit for m in rng.choice(ms, size=len(ms))])
                        for _ in range(b)]


def ci(vals):
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def gains(p, rng):
    rows = []
    loco = p[p.design == "loco"]
    within = p[p.design == "within"].set_index("id")
    sub = p[p.design == "loco_sub"].set_index("id")
    for scope, g in [("all", loco)] + list(loco.groupby("group")):
        bt = Boot(g, rng)
        y = g.goal.values
        w, s = within.loc[g.id], sub.loc[g.id]
        for kind in ("GLM", "GBM"):
            lo, ge = f"{kind}_LOC", f"{kind}_GEO"
            for sname, f in (("logloss", M.logloss), ("brier", M.brier)):
                a, c = g[lo].values, g[ge].values
                d = f(y, a) - f(y, c)
                bd = [f(y[t], a[t]) - f(y[t], c[t]) for t in bt.samples]
                br = [(f(y[t], a[t]) - f(y[t], c[t])) / f(y[t], a[t]) for t in bt.samples]
                rows.append({"scope": scope, "model": kind, "score": sname, "n": len(g), "gain": d,
                             "gain_lo": ci(bd)[0], "gain_hi": ci(bd)[1], "rel_gain": d / f(y, a),
                             "rel_lo": ci(br)[0], "rel_hi": ci(br)[1],
                             "penalty_LOC": f(y, a) - f(y, w[lo].values), "penalty_GEO": f(y, c) - f(y, w[ge].values),
                             "penalty_sub_LOC": f(y, s[lo].values) - f(y, w[lo].values),
                             "penalty_sub_GEO": f(y, s[ge].values) - f(y, w[ge].values)})
        print(scope, "done", flush=True)
    return pd.DataFrame(rows)


def corp_log(p):
    loco = p[p.design == "loco"]
    rows = []
    for m in MODELS:
        c = M.corp(loco.goal.values, loco[m].values, score=M.logloss)
        unit_mcb = [M.corp(g.goal.values, g[m].values, score=M.logloss)["MCB"] for _, g in loco.groupby("unit")]
        unit_mcb_b = [M.corp(g.goal.values, g[m].values)["MCB"] for _, g in loco.groupby("unit")]
        rows.append({"model": m, **{k: c[k] for k in ("score", "MCB", "DSC", "UNC")},
                     "unit_mean_MCB_log": float(np.mean(unit_mcb)), "unit_mean_MCB_brier": float(np.mean(unit_mcb_b))})
    return pd.DataFrame(rows)


def log_oe_stats(frames, m):
    """mean |log O/E| and method-of-moments between-frame SD of log O/E (binomial noise removed)."""
    lo, var = [], []
    for g in frames:
        e, o = g[m].sum(), g.goal.sum()
        lo.append(np.log(o / e))
        var.append((g[m] * (1 - g[m])).sum() / e ** 2)
    lo, var = np.array(lo), np.array(var)
    tau2 = max(0.0, lo.var(ddof=1) - var.mean())
    return float(np.abs(lo).mean()), float(np.sqrt(tau2))


def oe_spread(p, rng):
    out = {}
    for design in ("loco", "cross"):
        d = p[p.design == design]
        if design == "loco":
            keyed = [g for _, g in d.groupby("unit")]
        else:
            keyed = [g for _, g in d.groupby(["split", "group"])]
        res = {m: dict(zip(("mean_abs_log_oe", "tau"), log_oe_stats(keyed, m))) for m in MODELS}
        # bootstrap: resample matches within units of each frame
        diffs = {k: {"mean_abs": [], "tau": []} for k in ("GLM", "GBM")}
        pre = [(g, {mid: np.flatnonzero(g.match_id.values == mid) for mid in g.match_id.unique()},
                g.groupby("unit").match_id.unique()) for g in keyed]
        for _ in range(500):
            fr = []
            for g, idx, by_unit in pre:
                t = np.concatenate([idx[mm] for ms in by_unit for mm in rng.choice(ms, size=len(ms))])
                fr.append(g.iloc[t])
            for k in ("GLM", "GBM"):
                a, b = log_oe_stats(fr, f"{k}_LOC"), log_oe_stats(fr, f"{k}_GEO")
                diffs[k]["mean_abs"].append(a[0] - b[0])
                diffs[k]["tau"].append(a[1] - b[1])
        for k in ("GLM", "GBM"):
            res[f"{k}_LOC_minus_GEO_mean_abs_CI"] = ci(diffs[k]["mean_abs"])
            res[f"{k}_LOC_minus_GEO_tau_CI"] = ci(diffs[k]["tau"])
        out[design] = res
        print(design, "oe done", flush=True)
    return out


def fit_recal(y, x, how, lam=20.0):
    """Recalibration on the logit scale: q = sigmoid(a + b * logit(p))."""
    def nll(theta):
        a, b = (theta[0], 1.0) if how == "intercept" else theta
        z = a + b * x
        pen = lam * (a ** 2 + (b - 1) ** 2) if how == "shrunk" else 0.0
        return np.sum(np.logaddexp(0, z) - y * z) + pen
    th = minimize(nll, [0.0] if how == "intercept" else [0.0, 1.0], method="BFGS").x
    return (th[0], 1.0) if how == "intercept" else tuple(th)


def recal(p, k=10):
    dates = pd.read_csv(ROOT / "data" / "matches.csv", usecols=["match_id", "match_date"]).set_index("match_id").match_date
    rows = []
    loco = p[p.design == "loco"]
    for u, g in loco.groupby("unit"):
        order = dates.reindex(g.match_id.unique()).sort_values(kind="stable").index.values
        cal, ev = g[g.match_id.isin(order[:k])], g[~g.match_id.isin(order[:k])]
        for m in MODELS[:4]:
            xc, xe = M.logit(cal[m].values), M.logit(ev[m].values)
            fc = {"none": ev[m].values}
            for how in ("two_param", "intercept", "shrunk"):
                a, b = fit_recal(cal.goal.values, xc, how)
                fc[how] = 1 / (1 + np.exp(-(a + b * xe)))
            for how, f in fc.items():
                rows.append({"unit": u, "group": g.group.iloc[0], "model": m, "how": how, "n_eval": len(ev),
                             "cal_shots": len(cal), "cal_goals": int(cal.goal.sum()),
                             **M.all_metrics(ev.goal.values, f)})
    return pd.DataFrame(rows)


def main():
    rng = np.random.default_rng(SEED)
    p = pd.read_parquet(ROOT / "data" / "preds.parquet")
    table(p, ["design", "split"]).to_csv(RES / "metrics_units.csv", index=False)
    lp = p[p.design == "loco"]
    grp = pd.concat([table(lp, ["group"]).assign(design="loco"),
                     table(lp.assign(group="all"), ["group"]).assign(design="loco"),
                     table(p[p.design == "within"].assign(group="all"), ["group"]).assign(design="within"),
                     table(p[p.design == "within"], ["group"]).assign(design="within"),
                     table(p[p.design == "loco_sub"].assign(group="all"), ["group"]).assign(design="loco_sub"),
                     table(p[p.design == "cross"], ["split", "group"]).assign(design="cross")])
    grp.to_csv(RES / "metrics_groups.csv", index=False)
    corp_log(p).to_csv(RES / "corp_logloss.csv", index=False)
    gains(p, rng).to_csv(RES / "gain.csv", index=False)
    (RES / "oe_spread.json").write_text(json.dumps(oe_spread(p, rng), indent=1))
    recal(p).to_csv(RES / "recal.csv", index=False)


if __name__ == "__main__":
    main()
