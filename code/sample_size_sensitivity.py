"""Post-collection precision and sensitivity of the fixed LOCO predictions.

This is not an a priori calculation or a power estimate at the observed gain.
Resampling is paired, stratified by competition-season and clustered by match,
as in evaluate.py. Training and competition-selection uncertainty are excluded.
"""
from pathlib import Path
import hashlib
import json
import platform

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import brentq
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
B, SEED, ALPHA, TARGET_POWER = 10000, 20261103, 0.05, 0.80


def main():
    source = ROOT / "data/preds.parquet"
    p = pd.read_parquet(source)
    p = p[p.design == "loco"].copy()
    assert not p.id.duplicated().any()
    assert p.groupby("match_id").unit.nunique().max() == 1
    y = p.goal.to_numpy()
    for kind in ("GLM", "GBM"):
        losses = []
        for suffix in ("LOC", "GEO"):
            q = p[kind + "_" + suffix].to_numpy().clip(1e-6, 1 - 1e-6)
            losses.append(-y * np.log(q) - (1 - y) * np.log1p(-q))
        p[kind + "_gain"] = losses[0] - losses[1]
    matches = p.groupby(["unit", "match_id"]).agg(
        shots=("id", "size"), GLM=("GLM_gain", "sum"), GBM=("GBM_gain", "sum"))
    rng = np.random.default_rng(SEED)
    sums = np.zeros((B, 3))
    for _, frame in matches.groupby(level="unit"):
        values = frame[["shots", "GLM", "GBM"]].to_numpy()
        # Batch draws to avoid keeping B x all-match x 3 arrays in memory.
        for start in range(0, B, 250):
            ix = rng.integers(len(values), size=(min(250, B-start), len(values)))
            sums[start:start+len(ix)] += values[ix].sum(axis=1)
    z = norm.ppf(1 - ALPHA/2)
    # Solve the two-sided normal-test equation for the noncentral shift.
    shift = brentq(lambda d: norm.cdf(-z-d)+norm.sf(z-d)-TARGET_POWER, 0, 10)
    rows = []
    existing = pd.read_csv(ROOT / "results/gain.csv")
    for i, kind in enumerate(("GLM", "GBM"), 1):
        draws = sums[:, i] / sums[:, 0]
        gain = float(p[kind + "_gain"].mean())
        ref = existing.query("scope == 'all' and model == @kind and score == 'logloss'")
        assert len(ref) == 1 and abs(gain - float(ref.iloc[0].gain)) < 1e-12
        se = float(draws.std(ddof=1))
        rows.append({"model": kind, "gain": gain, "bootstrap_se": se,
                     "ci_lo": float(np.quantile(draws, .025)),
                     "ci_hi": float(np.quantile(draws, .975)),
                     "normal_sensitivity_minimum_gain": float(shift * se)})
    out = {"timing": "post-collection, during submission preparation; not preregistered",
           "estimand": "shot-weighted paired LOC minus GEO LOCO log loss",
           "shots": len(p), "matches_with_open_play_shots": len(matches),
           "competition_seasons": p.unit.nunique(), "replications": B, "seed": SEED,
           "alpha": ALPHA, "target_power": TARGET_POWER, "sidedness": "two-sided",
           "normal_noncentral_shift": float(shift), "probability_clip": 1e-6,
           "method": "Normal sensitivity approximation using a match-bootstrap SE, stratified by unit. Variance is assumed locally constant under a hypothetical mean shift. No power is calculated at the observed gain.",
           "limitations": "Conditional on fitted predictions and observed competition-seasons; excludes refitting and selection uncertainty. Does not justify subgroup, interaction, equivalence or player-level claims.",
           "versions": {"python": platform.python_version(), "numpy": np.__version__,
                        "pandas": pd.__version__, "scipy": scipy.__version__},
           "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "results": rows}
    dest = ROOT / "results/sample_size_sensitivity.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
