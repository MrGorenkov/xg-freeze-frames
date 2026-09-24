"""Figures for the article (PNG 600 dpi + PDF). Group colours follow a CVD-checked categorical palette;
each group also has its own marker, so identity never rests on colour alone.

Fig. 1  schematic of the freeze-frame geometry features (synthetic example, not StatsBomb data)
Fig. 2  relative log-loss gain of GEO over LOC for each held-out competition-season (LOCO), 95 % match-bootstrap CIs
Fig. 3  CORP reliability curves of LOC and GEO forecasts (LOCO), one panel per group
Fig. 4  calibration in the large (observed / expected goals) per competition-season, LOC vs GEO, LOCO and cross-group
Fig. 5  odds ratios of the five geometry terms by group
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Polygon, Wedge  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402

import metrics as M  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES, FIG = ROOT / "results", ROOT / "paper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
MM = 1 / 25.4
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
GROUPS = ["men_club", "women_club", "men_intl", "women_intl"]
GLAB = {"men_club": "Men's club", "women_club": "Women's club", "men_intl": "Men's international",
        "women_intl": "Women's international"}
GCOL = {"men_club": "#2a78d6", "women_club": "#eb6834", "men_intl": "#1baf7a", "women_intl": "#eda100"}
GMARK = {"men_club": "o", "women_club": "s", "men_intl": "^", "women_intl": "D"}
plt.rcParams.update({"font.family": "Arial", "font.size": 7.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
                     "legend.frameon": False, "lines.linewidth": 1.5})
SEED = 20260924


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=600, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_schematic():
    fig, ax = plt.subplots(figsize=(80 * MM, 62 * MM))
    ax.set_aspect("equal")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.plot([90, 120, 120, 90], [18, 18, 62, 62], color=MUTED, lw=0.8)       # box edge
    ax.plot([114, 120, 120, 114, 114], [30, 30, 50, 50, 30], color=MUTED, lw=0.6)
    ax.plot([120, 120], [36, 44], color=INK, lw=3)                          # goal mouth
    sx, sy = 101, 31
    ax.add_patch(Polygon([(sx, sy), (120, 36), (120, 44)], closed=True, color="#cde2fb", zorder=1))
    inside = [(108, 34.3), (112.5, 37.0)]            # outfield opponents inside the shot triangle
    others = [(103.5, 28.8), (112, 47), (96, 38)]      # outside it; the first is the nearest opponent
    gk = (117.2, 39.2)
    for x, y in inside:  # angular sector of the goal mouth hidden by each defender
        d, phi = np.hypot(x - sx, y - sy), np.arctan2(y - sy, x - sx)
        w = np.arcsin(0.5 / d)
        pts = [(sx, sy)] + [(120, sy + (120 - sx) * np.tan(a)) for a in (phi - w, phi + w)]
        ax.add_patch(Polygon(pts, closed=True, color="#eb6834", alpha=0.25, lw=0, zorder=2))
    for x, y in inside + others:
        ax.add_patch(plt.Circle((x, y), 0.55, color="#eb6834", zorder=3))
    ax.add_patch(plt.Circle(gk, 1.0, color=INK, zorder=3))
    ax.plot([sx, 120], [sy, 40], color=MUTED, lw=0.8, ls="--")
    ax.add_patch(plt.Circle((sx, sy), 0.7, color="#2a78d6", zorder=4))
    t = np.array([120 - sx, 40 - sy]); t = t / np.linalg.norm(t)
    foot = np.array([sx, sy]) + t * np.dot(np.array(gk) - [sx, sy], t)
    ax.plot([gk[0], foot[0]], [gk[1], foot[1]], color=INK, lw=0.9, zorder=4)
    arrow = dict(arrowstyle="-", color=MUTED, lw=0.5)
    ax.annotate("shooter", (sx, sy), xytext=(-30, -3), textcoords="offset points", fontsize=7, color=INK)
    ax.annotate("nearest opponent", (103.5, 28.8), xytext=(-58, -26), textcoords="offset points",
                fontsize=6.5, color=INK, arrowprops=arrow)
    ax.annotate("defenders in the\nshot triangle", (110, 35.5), xytext=(-62, 42), textcoords="offset points",
                fontsize=6.5, color=INK, arrowprops=arrow)
    ax.annotate("goalkeeper offset\nfrom the shot line", (117.0, 38.6), xytext=(-40, 62), textcoords="offset points",
                fontsize=6.5, color=INK, arrowprops=arrow)
    ax.annotate("hidden share of\nthe goal mouth", (120, 37.2), xytext=(-8, -46), textcoords="offset points",
                fontsize=6.5, color=INK, arrowprops=arrow)
    ax.set_xlim(88, 124); ax.set_ylim(17, 63)
    save(fig, "fig1_features")


def boot_gain(g, lo, ge, rng, b=1000):
    idx = {m: np.flatnonzero(g.match_id.values == m) for m in g.match_id.unique()}
    ms = np.array(list(idx))
    y, a, c = g.goal.values, g[lo].values, g[ge].values
    out = []
    for _ in range(b):
        t = np.concatenate([idx[m] for m in rng.choice(ms, size=len(ms))])
        la = M.logloss(y[t], a[t])
        out.append((la - M.logloss(y[t], c[t])) / la)
    return np.percentile(out, [2.5, 97.5])


def fig_gain(p):
    rng = np.random.default_rng(SEED)
    loco = p[p.design == "loco"]
    rows = []
    for u, g in loco.groupby("unit"):
        for kind in ("GLM", "GBM"):
            la = M.logloss(g.goal.values, g[f"{kind}_LOC"].values)
            ge = M.logloss(g.goal.values, g[f"{kind}_GEO"].values)
            lo, hi = boot_gain(g, f"{kind}_LOC", f"{kind}_GEO", rng) if kind == "GLM" else (np.nan, np.nan)
            rows.append({"unit": u, "group": g.group.iloc[0], "model": kind, "gain": (la - ge) / la, "lo": lo, "hi": hi,
                         "n": len(g)})
    r = pd.DataFrame(rows)
    r.to_csv(RES / "gain_units.csv", index=False)
    glm = r[r.model == "GLM"].copy()
    glm["order"] = glm.group.map({g: i for i, g in enumerate(GROUPS)})
    glm = glm.sort_values(["order", "gain"], ascending=[False, True]).reset_index(drop=True)
    gbm = r[r.model == "GBM"].set_index("unit").gain
    fig, ax = plt.subplots(figsize=(120 * MM, 118 * MM))
    for i, row in glm.iterrows():
        c = GCOL[row.group]
        ax.plot([100 * row.lo, 100 * row.hi], [i, i], color=c, lw=1.2)
        ax.plot(100 * row.gain, i, marker=GMARK[row.group], color=c, ms=5, ls="")
        ax.plot(100 * gbm[row.unit], i, marker="|", color=INK, ms=6, ls="")
    ax.set_yticks(range(len(glm)))
    ax.set_yticklabels([f"{u} (n = {n:,})".replace(",", " ") for u, n in zip(glm.unit, glm.n)], fontsize=6.5)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("Reduction in log loss from geometry features, %")
    ax.grid(axis="y", visible=False)
    h = [plt.Line2D([], [], color=GCOL[g], marker=GMARK[g], ls="-", lw=1.2, ms=5, label=GLAB[g]) for g in GROUPS]
    h.append(plt.Line2D([], [], color=INK, marker="|", ls="", ms=6, label="gradient boosting"))
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.3, -0.08), ncol=3, fontsize=6.5)
    save(fig, "fig2_gain_units")


def fig_reliability(p):
    loco = p[p.design == "loco"]
    fig, axes = plt.subplots(1, 4, figsize=(170 * MM, 48 * MM), sharex=True, sharey=True)
    for ax, g in zip(axes, GROUPS):
        d = loco[loco.group == g]
        for m, ls, lab in (("GLM_LOC", ":", "location and context"), ("GLM_GEO", "-", "+ geometry")):
            x = d[m].values
            o = np.argsort(x)
            fit = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(x, d.goal.values).predict(x[o])
            ax.plot(x[o], fit, color=GCOL[g], ls=ls, lw=1.5, label=lab)
        ax.plot([0, 1], [0, 1], color=MUTED, lw=0.6)
        ax.set_xlim(0, 0.8); ax.set_ylim(0, 0.8)
        ax.set_title(GLAB[g], fontsize=7.5, color=INK, loc="left")
        ax.set_xlabel("Forecast probability")
    axes[0].set_ylabel("Observed goal rate (CORP)")
    axes[0].legend(loc="upper left", fontsize=6.5)
    fig.subplots_adjust(wspace=0.12)
    save(fig, "fig3_reliability")


def fig_oe():
    u = pd.read_csv(RES / "metrics_units.csv")
    l = u[u.design == "loco"].pivot(index="split", columns="model", values="obs_exp")
    grp = pd.read_parquet(ROOT / "data" / "preds.parquet", columns=["unit", "group"]).drop_duplicates().set_index("unit").group
    l["group"] = grp.reindex(l.index).values
    l["order"] = l.group.map({g: i for i, g in enumerate(GROUPS)})
    l = l.sort_values(["order", "GLM_GEO"], ascending=[False, True])
    c = pd.read_csv(RES / "metrics_groups.csv")
    c = c[c.design == "cross"].pivot_table(index=["split", "group"], columns="model", values="obs_exp").reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(170 * MM, 100 * MM), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    for i, (unit, r) in enumerate(l.iterrows()):
        ax.plot([r.GLM_LOC, r.GLM_GEO], [i, i], color=GRID, lw=1.5, zorder=1)
        ax.plot(r.GLM_LOC, i, marker=GMARK[r.group], color="white", mec=GCOL[r.group], ms=5, ls="", zorder=2)
        ax.plot(r.GLM_GEO, i, marker=GMARK[r.group], color=GCOL[r.group], ms=5, ls="", zorder=3)
    ax.set_yticks(range(len(l)))
    ax.set_yticklabels(l.index, fontsize=6.5)
    ax.axvline(1, color=MUTED, lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks([0.8, 0.9, 1, 1.1, 1.2]); ax.set_xticklabels(["0.8", "0.9", "1", "1.1", "1.2"])
    ax.set_xlabel("Observed / expected goals")
    ax.set_title("(a) held-out competition-season", fontsize=7.5, color=INK, loc="left")
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    c["lab"] = [f"{GLAB[a]} → {GLAB[b].lower()}" for a, b in zip(c.split, c.group)]
    c["order"] = c.split.map({g: i for i, g in enumerate(GROUPS)})
    c = c.sort_values(["order", "group"], ascending=False).reset_index(drop=True)
    for i, r in c.iterrows():
        ax.plot([r.GLM_LOC, r.GLM_GEO], [i, i], color=GRID, lw=1.5, zorder=1)
        ax.plot(r.GLM_LOC, i, marker=GMARK[r.group], color="white", mec=GCOL[r.group], ms=5, ls="", zorder=2)
        ax.plot(r.GLM_GEO, i, marker=GMARK[r.group], color=GCOL[r.group], ms=5, ls="", zorder=3)
    ax.set_yticks(range(len(c)))
    ax.set_yticklabels(c.lab, fontsize=6.5)
    ax.axvline(1, color=MUTED, lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks([0.8, 0.9, 1, 1.1, 1.2]); ax.set_xticklabels(["0.8", "0.9", "1", "1.1", "1.2"])
    ax.set_xlabel("Observed / expected goals")
    ax.set_title("(b) trained on one group only", fontsize=7.5, color=INK, loc="left")
    ax.grid(axis="y", visible=False)
    h = [plt.Line2D([], [], marker="o", color="white", mec=MUTED, ls="", ms=5, label="location and context"),
         plt.Line2D([], [], marker="o", color=MUTED, ls="", ms=5, label="+ geometry")]
    h += [plt.Line2D([], [], marker=GMARK[g], color=GCOL[g], ls="", ms=5, label=f"test: {GLAB[g].lower()}") for g in GROUPS]
    fig.legend(handles=h, loc="lower center", ncol=3, bbox_to_anchor=(0.55, -0.06), fontsize=6.5)
    fig.subplots_adjust(wspace=0.75, bottom=0.14)
    save(fig, "fig4_obs_exp")


def fig_effects():
    e = pd.read_csv(RES / "effects.csv")
    terms = {"occ10": "Goal-mouth occlusion\n(+10 %)", "n_opp_tri_c": "Defenders in the\nshot triangle (+1)",
             "gk_line_off": "Goalkeeper offset from\nthe shot line (+1 yd)", "gk_dist_goal": "Goalkeeper distance\nfrom goal (+1 yd)",
             "near_opp": "Distance to nearest\nopponent (+1 yd)"}
    fig, axes = plt.subplots(1, 5, figsize=(170 * MM, 45 * MM), sharey=True)
    for ax, (t, lab) in zip(axes, terms.items()):
        d = e[e.term == t].set_index("group")
        for i, g in enumerate(GROUPS[::-1] + ["all"]):
            r = d.loc[g]
            c = INK if g == "all" else GCOL[g]
            ax.plot([r.OR_lo, r.OR_hi], [i, i], color=c, lw=1.2)
            ax.plot(r.OR, i, marker="o" if g == "all" else GMARK[g], color=c, ms=4.5, ls="")
        ax.axvline(1, color=MUTED, lw=0.8)
        ax.set_title(lab, fontsize=6.5, color=INK, loc="left")
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Odds ratio")
    axes[0].set_yticks(range(5))
    axes[0].set_yticklabels([GLAB[g] for g in GROUPS[::-1]] + ["All (pooled)"], fontsize=6.5)
    fig.subplots_adjust(wspace=0.25)
    save(fig, "fig5_effects")


def main():
    p = pd.read_parquet(ROOT / "data" / "preds.parquet")
    fig_schematic()
    fig_gain(p)
    fig_reliability(p)
    fig_oe()
    fig_effects()


if __name__ == "__main__":
    main()
