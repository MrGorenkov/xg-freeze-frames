"""Nested expected-goals models evaluated within and across competitions.

Sample: open-play shots with a freeze frame from 23 complete competition-seasons (units), grouped as
men's club, women's club, men's international, women's international. One-team samples (Barcelona,
PSG, Leverkusen, Inter Miami, Arsenal 2003/04), NWSL 2018 (partial season) and historic matches are left out.

Feature sets:  LOC = location + context;  GEO = LOC + freeze-frame geometry.
Model classes: GLM = logistic regression with natural-spline terms; GBM = LightGBM.
Designs:
  within  5-fold cross-validation grouped by match over all units (in-distribution reference)
  loco    leave-one-competition-season-out: train on the other 22 units, predict the held-out unit
  cross   train on one group only (e.g. men's club) and predict every unit of the other groups
Writes data/preds.parquet (local only: shot-level, derived from StatsBomb data) and results/*.csv.
"""
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
ROOT = Path(__file__).resolve().parents[1]
SEED = 20260924

UNITS = {
    "men_club": [("Premier League", "2015/2016"), ("La Liga", "2015/2016"), ("Serie A", "2015/2016"),
                 ("Ligue 1", "2015/2016"), ("Indian Super league", "2021/2022")],
    "women_club": [("FA Women's Super League", s) for s in ("2018/2019", "2019/2020", "2020/2021", "2023/2024")]
                  + [("Frauen Bundesliga", "2023/2024"), ("Liga F", "2023/2024"), ("Serie A Women", "2023/2024"),
                     ("NWSL", "2023")],
    "men_intl": [("FIFA World Cup", "2018"), ("FIFA World Cup", "2022"), ("UEFA Euro", "2020"), ("UEFA Euro", "2024"),
                 ("Copa America", "2024"), ("African Cup of Nations", "2023")],
    "women_intl": [("Women's World Cup", "2019"), ("Women's World Cup", "2023"), ("UEFA Women's Euro", "2022"),
                   ("UEFA Women's Euro", "2025")],
}
CTX = ["header", "other_body", "volley", "tech_other", "first_time", "under_pressure", "follows_dribble",
       "pp_corner", "pp_free_kick", "pp_throw_in", "pp_counter", "pp_other"]
LOC_SPLINE, LOC_LIN = ["dist", "angle", "abs_dy"], CTX
GEO_SPLINE = ["gk_dist_goal", "gk_line_off", "occ_all", "near_opp"]
GEO_LIN = ["gk_present", "gk_in_tri", "n_opp_tri_c", "n_team_tri_c", "n_opp_3_c", "occ_def"]
FEATURES = {"LOC": LOC_SPLINE + LOC_LIN, "GEO": LOC_SPLINE + LOC_LIN + GEO_SPLINE + GEO_LIN}


def load():
    df = pd.read_parquet(ROOT / "data" / "shots.parquet")
    df["season"] = df["season"].astype(str)
    unit = {u: g for g, us in UNITS.items() for u in us}
    df["group"] = [unit.get((c, s)) for c, s in zip(df.competition, df.season)]
    df = df[df.group.notna() & (df.type == "Open Play") & (df.has_ff == 1)].copy()
    df["unit"] = df.competition + " " + df.season
    df["header"] = (df.body_part == "Head").astype(int)
    df["other_body"] = (df.body_part == "Other").astype(int)
    df["volley"] = df.technique.isin(["Volley", "Half Volley"]).astype(int)
    df["tech_other"] = (~df.technique.isin(["Normal", "Volley", "Half Volley"])).astype(int)
    pp = {"From Corner": "pp_corner", "From Free Kick": "pp_free_kick", "From Throw In": "pp_throw_in",
          "From Counter": "pp_counter"}
    for c in pp.values():
        df[c] = 0
    df["pp_other"] = 0
    for i, v in zip(df.index, df.play_pattern):
        if v in pp:
            df.at[i, pp[v]] = 1
        elif v != "Regular Play":
            df.at[i, "pp_other"] = 1
    for c in ("n_opp_tri", "n_team_tri", "n_opp_3"):
        df[f"{c}_c"] = df[c].clip(upper=4)
    # fixed, data-independent treatment (no information from test units): a missing goalkeeper (0.1 % of shots)
    # is flagged by gk_present and its distances set to 0; distances are capped at 15 yd (a goalkeeper farther out is\n    # out of the play, and uncapped values would be extrapolated by the splines)
    for c in ("gk_dist_goal", "gk_line_off", "gk_shot_dist"):
        df[c] = df[c].fillna(0.0).clip(upper=15.0)
    return df.reset_index(drop=True)


def glm(fs):
    spl = LOC_SPLINE + (GEO_SPLINE if fs == "GEO" else [])
    lin = LOC_LIN + (GEO_LIN if fs == "GEO" else [])
    ct = ColumnTransformer([("s", SplineTransformer(n_knots=5, degree=3, extrapolation="linear"), spl),
                            ("l", "passthrough", lin)])
    return make_pipeline(ct, StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))


def fit_predict(kind, fs, tr, te):
    X = FEATURES[fs]
    if kind == "GLM":
        m = glm(fs).fit(tr[X], tr.goal)
        return m.predict_proba(te[X])[:, 1]
    # GBM: early stopping on 10 % of the training matches
    rng = np.random.default_rng(SEED)
    mids = tr.match_id.unique()
    val = set(rng.choice(mids, size=max(1, len(mids) // 10), replace=False))
    iv = tr.match_id.isin(val)
    m = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.02, num_leaves=15, min_child_samples=100,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                           random_state=SEED, verbose=-1)
    m.fit(tr.loc[~iv, X], tr.goal[~iv], eval_X=(tr.loc[iv, X],), eval_y=(tr.goal[iv],), eval_metric="binary_logloss",
          callbacks=[lgb.early_stopping(100, verbose=False)])
    return m.predict_proba(te[X])[:, 1]


def run(df, design):
    out = []
    if design == "within":
        folds = GroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(df, groups=df.match_id)
        splits = [(f"fold{i}", tr, te) for i, (tr, te) in enumerate(folds)]
    elif design == "loco":
        splits = [(u, np.flatnonzero(df.unit != u), np.flatnonzero(df.unit == u)) for u in sorted(df.unit.unique())]
    elif design == "loco_sub":
        # LOCO with the training set cut to the size of a within-pool fold (80 % of all matches), so that the
        # transfer penalty is not flattered by the larger LOCO training sets
        rng = np.random.default_rng(SEED)
        k = int(round(0.8 * df.match_id.nunique()))
        splits = []
        for u in sorted(df.unit.unique()):
            keep = rng.choice(df.match_id[df.unit != u].unique(), size=k, replace=False)
            splits.append((u, np.flatnonzero(df.match_id.isin(keep).values), np.flatnonzero(df.unit == u)))
    else:  # cross: train on one group, test on the units of the other groups
        splits = [(g, np.flatnonzero(df.group == g), np.flatnonzero(df.group != g)) for g in UNITS]
    for name, tr, te in splits:
        trd, ted = df.iloc[tr], df.iloc[te]
        res = pd.DataFrame({"id": ted.id.values, "split": name, "design": design})
        for kind in ("GLM", "GBM"):
            for fs in ("LOC", "GEO"):
                res[f"{kind}_{fs}"] = fit_predict(kind, fs, trd, ted)
        out.append(res)
        print(design, name, len(tr), len(te), flush=True)
    return pd.concat(out, ignore_index=True)


def main():
    df = load()
    print(len(df), "open-play shots with freeze frames;", df.groupby("group").size().to_dict(), flush=True)
    designs = sys.argv[1:] or ["within", "loco", "loco_sub", "cross"]
    preds = [run(df, d) for d in designs]
    p = pd.concat(preds, ignore_index=True).merge(
        df[["id", "match_id", "unit", "group", "goal", "statsbomb_xg"]], on="id")
    p.to_parquet(ROOT / "data" / "preds.parquet", index=False)


if __name__ == "__main__":
    main()
