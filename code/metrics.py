"""Proper scores, CORP decomposition and calibration measures for binary forecasts.

CORP (Dimitriadis, Gneiting & Jordan 2021): the PAV (isotonic) recalibration p* of the forecast p gives
  score(p) = MCB - DSC + UNC,  MCB = S(p) - S(p*),  DSC = S(c) - S(p*),  UNC = S(c),
with c the climatological (mean) forecast. Calibration intercept and slope (Van Calster et al. 2019)
come from a logistic regression of y on logit(p); the intercept is estimated with the slope fixed at 1.
ICI (Austin & Steyerberg 2019) is the mean |loess-smoothed observed rate - p|; here the smoother is
the PAV fit, so ICI equals the mean absolute distance to the CORP reliability curve.
"""
import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

EPS = 1e-6


def logloss(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def corp(y, p, score=brier):
    pav = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(p, y).predict(p)
    c = np.full_like(p, y.mean(), dtype=float)
    s, s_star, s_c = score(y, p), score(y, pav), score(y, c)
    return {"score": s, "MCB": s - s_star, "DSC": s_c - s_star, "UNC": s_c, "ICI": float(np.mean(np.abs(pav - p)))}


def calib_intercept(y, p):
    off = logit(p)
    f = lambda a: logloss(y, 1 / (1 + np.exp(-(a + off))))  # noqa: E731
    return float(minimize_scalar(f, bounds=(-3, 3), method="bounded").x)


def calib_slope(y, p):
    lr = LogisticRegression(C=1e6).fit(logit(p).reshape(-1, 1), y)
    return float(lr.coef_[0, 0])


def all_metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    c = corp(y, p)
    return {"n": len(y), "goals": int(y.sum()), "logloss": logloss(y, p), "brier": c["score"],
            "MCB": c["MCB"], "DSC": c["DSC"], "UNC": c["UNC"], "ICI": c["ICI"],
            "auc": float(roc_auc_score(y, p)), "cal_int": calib_intercept(y, p), "cal_slope": calib_slope(y, p),
            "obs_exp": float(y.sum() / p.sum())}
