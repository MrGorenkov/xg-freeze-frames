"""Stability of geometry effects across groups of competitions, and the 360 visibility check.

1. A parametric logistic model: natural-spline terms for distance and angle, the shot context, and five
   pre-specified geometry terms (occ_all per 10 %, n_opp_tri, gk_line_off, gk_dist_goal, near_opp), with a
   control for a missing goalkeeper. It is fitted per group and pooled; odds ratios come with standard
   errors clustered by match. Heterogeneity: a cluster-robust Wald test of the group x geometry
   interactions in the pooled model with group-specific intercepts.
2. 360 subset: the share of shots whose shot triangle (shooter to both posts) lies partly outside the
   camera's visible area, and the goal rate of shots with no defender in the triangle by visibility.
Writes results/effects.csv, results/heterogeneity.json, results/visibility.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import models as M

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
GEO = ["occ10", "n_opp_tri_c", "gk_line_off", "gk_dist_goal", "near_opp"]
BASE = ("goal ~ cr(dist, df=4) + cr(angle, df=4) + abs_dy + " + " + ".join(M.CTX) + " + gk_present")


def fit(df, formula):
    return smf.logit(formula, df).fit(disp=0, maxiter=200, cov_type="cluster",
                                      cov_kwds={"groups": pd.factorize(df.match_id)[0]})


def main():
    df = M.load()
    df["occ10"] = df.occ_all * 10
    rows = []
    for name, g in [("all", df)] + list(df.groupby("group")):
        r = fit(g, BASE + " + " + " + ".join(GEO) + (" + C(group)" if name == "all" else ""))
        ci = r.conf_int()
        for v in GEO:
            rows.append({"group": name, "term": v, "n": len(g), "coef": r.params[v], "se": r.bse[v],
                         "OR": np.exp(r.params[v]), "OR_lo": np.exp(ci.loc[v, 0]), "OR_hi": np.exp(ci.loc[v, 1])})
    pd.DataFrame(rows).to_csv(RES / "effects.csv", index=False)

    inter = " + ".join(f"{v}:C(group)" for v in GEO)
    r = fit(df, BASE + " + C(group) + " + " + ".join(GEO) + " + " + inter)
    names = [n for n in r.params.index if ":C(group)" in n]
    w = r.wald_test(", ".join(f"{n} = 0" for n in names), scalar=True)
    het = {"wald_chi2": float(w.statistic), "df": len(names), "p": float(w.pvalue)}
    per_term = {}
    for v in GEO:
        nm = [n for n in names if n.startswith(v + ":")]
        t = r.wald_test(", ".join(f"{n} = 0" for n in nm), scalar=True)
        per_term[v] = {"chi2": float(t.statistic), "df": len(nm), "p": float(t.pvalue)}
    het["per_term"] = per_term
    (RES / "heterogeneity.json").write_text(json.dumps(het, indent=1))

    s = pd.read_parquet(ROOT / "data" / "shots.parquet")
    s = s[(s.type == "Open Play") & (s.has_ff == 1) & (s.has360 == 1) & s.tri_visible.notna()]
    part = s.tri_visible < 0.999
    empty = s.n_opp_tri == 0
    vis = {"shots_360": int(len(s)), "triangle_partly_hidden": int(part.sum()), "share_partly_hidden": float(part.mean()),
           "mean_visible_share_when_hidden": float(s.tri_visible[part].mean()),
           "empty_triangle_goal_rate_visible": float(s.goal[empty & ~part].mean()), "n_empty_visible": int((empty & ~part).sum()),
           "empty_triangle_goal_rate_hidden": float(s.goal[empty & part].mean()), "n_empty_hidden": int((empty & part).sum()),
           "empty_share_visible": float(empty[~part].mean()), "empty_share_hidden": float(empty[part].mean()),
           "dist_mean_visible": float(s.dist[~part].mean()), "dist_mean_hidden": float(s.dist[part].mean())}
    # model-based check within the 23 units: observed / expected goals of LOCO forecasts for partly hidden and fully
    # visible triangles, and for fully visible shots at a similar distance (>= 20 yd), where the hidden ones concentrate
    p = pd.read_parquet(ROOT / "data" / "preds.parquet")
    p = p[p.design == "loco"].merge(s[["id", "tri_visible", "dist"]], on="id")
    p["hidden"] = p.tri_visible < 0.999
    sets = {"hidden": p[p.hidden], "visible": p[~p.hidden], "visible_20yd_plus": p[~p.hidden & (p.dist >= 20)],
            "hidden_20yd_plus": p[p.hidden & (p.dist >= 20)]}
    vis["units_360_shots"] = int(len(p))
    vis["units_share_hidden"] = float(p.hidden.mean())
    for name, g in sets.items():
        for m in ("GLM_GEO", "GBM_GEO", "statsbomb_xg"):
            e, o = float(g[m].sum()), int(g.goal.sum())
            sd = float(np.sqrt((g[m] * (1 - g[m])).sum()))
            vis[f"{name}_{m}"] = {"n": int(len(g)), "goals": o, "expected": e, "O_E": o / e, "z": (o - e) / sd}
    (RES / "visibility.json").write_text(json.dumps(vis, indent=1))
    print(pd.DataFrame(rows).round(3).to_string())
    print(json.dumps(het, indent=1))
    print(json.dumps(vis, indent=1))


if __name__ == "__main__":
    main()
