# What freeze frames add to expected goals

Code, aggregate results and figures for the article "What freeze frames add to expected goals: discrimination,
calibration and transfer across competitions" (A. A. Gorenkov, Plekhanov Russian University of Economics, 2026).

Data: StatsBomb (Hudl) open data, https://github.com/hudl/open-data, commit `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.
The StatsBomb Public Data User Agreement does not allow redistribution, so this repository contains no shot-level data;
`code/download_shots.py` fetches it from the official repository.

## What is done
- 77,770 open-play shots with freeze frames from 23 complete competition-seasons (men's and women's leagues and
  tournaments, 2015–2025); one-club seasons and historic single matches are excluded.
- Nested models: location + context (LOC) vs. the same + freeze-frame geometry (GEO: ten inputs; the main five are goal-mouth occlusion,
  defenders in the shot triangle, goalkeeper offset from the shot line, goalkeeper distance from goal, nearest opponent), each as a
  spline logistic regression and as LightGBM.
- Designs: 5-fold cross-validation by match, leave-one-competition-season-out, and training on one group of
  competitions (men's/women's × club/international) with evaluation on the others.
- Scores: log loss, Brier score with the CORP decomposition (miscalibration, discrimination, uncertainty), AUC,
  calibration slope, observed/expected goals; match-clustered bootstrap intervals.
- Stability of geometry effects across groups (cluster-robust Wald test) and a camera-visibility check on the 360 subset.

## Layout
```
code/
  download_shots.py  fetch every match at the pinned commit, keep only shots (+ 360 frames) -> data/shots/
  features.py        location, context, geometry and visibility features -> data/shots.parquet
  models.py          GLM/GBM × LOC/GEO under the three designs -> data/preds.parquet
  metrics.py         proper scores, CORP decomposition, calibration measures
  evaluate.py        results/metrics_units.csv, metrics_groups.csv, gain.csv, recal.csv
  effects.py         results/effects.csv, heterogeneity.json, visibility.json
  figures.py         paper/figures/
data/data_notes.md   description of the source data, its licence and caveats
results/             aggregate results only
```

## Reproduce
```
pip install numpy pandas pyarrow scipy scikit-learn lightgbm statsmodels shapely matplotlib
python code/download_shots.py      # ~12 GB streamed, ~100 MB kept
python code/features.py
python code/models.py
python code/evaluate.py
python code/effects.py
python code/figures.py
```
One 360 file at this commit (`three-sixty/3845506.json`) is not valid JSON; the match is kept without 360 frames.

## Licence
Code: MIT. Data: © StatsBomb (Hudl), used under the StatsBomb Public Data User Agreement.
