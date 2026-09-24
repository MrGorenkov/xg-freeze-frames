"""Shot table with location, context and freeze-frame geometry features -> data/shots.parquet (local only).

Coordinates are StatsBomb yards (pitch 120 x 80), the attacking goal is at x = 120 between the posts
y = 36 and y = 44. Features:
  location   dist, angle (angle subtended by the goal mouth), abs_dy
  context    body part, technique, play pattern, first_time, under_pressure, follows_dribble
  geometry   (shot freeze frame, shooter excluded by StatsBomb)
             gk_present, gk_dist_goal, gk_shot_dist, gk_line_off (distance of the goalkeeper from the
             shooter-goal-centre line), gk_in_tri; n_opp_tri, n_team_tri (players inside the triangle
             shooter-posts); near_opp (nearest opponent, capped at 10), n_opp_3 (opponents within 3 yd);
             occ_def / occ_all (share of the goal-mouth angle hidden by outfield opponents, and by all
             opponents incl. the goalkeeper; players are discs of radius 0.5 yd, the goalkeeper 1 yd);
             n_frame (players visible in the freeze frame)
  visibility (360 frame, where present) tri_visible (share of the shot triangle inside the camera's visible area)
The StatsBomb qualifiers one_on_one and open_goal are kept as columns but not used as model features,
because they are coded by annotators from the same positional situation.
"""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
GX, P1, P2 = 120.0, 36.0, 44.0
R_PLAYER, R_GK = 0.5, 1.0


def in_triangle(p, a, b, c):
    def s(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def occlusion(x, y, players):
    """Share of the goal-mouth angle (seen from the shot location) covered by discs (px, py, r)."""
    a1, a2 = np.arctan2(P1 - y, GX - x), np.arctan2(P2 - y, GX - x)
    lo, hi = min(a1, a2), max(a1, a2)
    if hi - lo <= 0:
        return 0.0
    iv = []
    for px, py, r in players:
        d = np.hypot(px - x, py - y)
        if px <= x or d <= r:
            if d <= r:
                iv.append((lo, hi))
            continue
        phi, w = np.arctan2(py - y, px - x), np.arcsin(r / d)
        a, b = max(phi - w, lo), min(phi + w, hi)
        if b > a:
            iv.append((a, b))
    iv.sort()
    cov, cur = 0.0, None
    for a, b in iv:
        if cur is None or a > cur[1]:
            if cur:
                cov += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        cov += cur[1] - cur[0]
    return cov / (hi - lo)


def geometry(s):
    x, y = s["location"][:2]
    shooter, post1, post2 = (x, y), (GX, P1), (GX, P2)
    ff = s["freeze_frame"]
    opp = [p for p in ff if not p["teammate"]]
    gk = [p for p in opp if p["position"] == "Goalkeeper"]
    out = [p for p in opp if p["position"] != "Goalkeeper"]
    team = [p for p in ff if p["teammate"]]
    f = {"n_frame": len(ff), "gk_present": int(bool(gk))}
    if gk:
        gx, gy = gk[0]["location"]
        f["gk_dist_goal"] = np.hypot(GX - gx, 40 - gy)
        f["gk_shot_dist"] = np.hypot(gx - x, gy - y)
        vx, vy = GX - x, 40 - y
        f["gk_line_off"] = abs(vx * (gy - y) - vy * (gx - x)) / max(np.hypot(vx, vy), 1e-9)
        f["gk_in_tri"] = int(in_triangle((gx, gy), shooter, post1, post2))
    else:
        f.update(gk_dist_goal=np.nan, gk_shot_dist=np.nan, gk_line_off=np.nan, gk_in_tri=0)
    f["n_opp_tri"] = sum(in_triangle(tuple(p["location"]), shooter, post1, post2) for p in out)
    f["n_team_tri"] = sum(in_triangle(tuple(p["location"]), shooter, post1, post2) for p in team)
    d = [np.hypot(p["location"][0] - x, p["location"][1] - y) for p in opp]
    f["near_opp"] = min(min(d), 10.0) if d else 10.0
    f["n_opp_3"] = sum(v <= 3 for v in d)
    f["occ_def"] = occlusion(x, y, [(*p["location"], R_PLAYER) for p in out])
    f["occ_all"] = occlusion(x, y, [(*p["location"], R_PLAYER) for p in out] + [(*p["location"], R_GK) for p in gk])
    return f


def visibility(s):
    fr = s.get("frame360")
    if not fr or not fr.get("visible_area"):
        return {"has360": 0, "tri_visible": np.nan, "n_visible": np.nan}
    va = fr["visible_area"]
    poly = Polygon(list(zip(va[0::2], va[1::2])))
    if not poly.is_valid:
        poly = poly.buffer(0)
    x, y = s["location"][:2]
    tri = Polygon([(x, y), (GX, P1), (GX, P2)])
    share = poly.intersection(tri).area / tri.area if tri.area > 0 else np.nan
    return {"has360": 1, "tri_visible": share, "n_visible": len(fr.get("freeze_frame") or [])}


def main():
    matches = pd.read_csv(ROOT / "data" / "matches.csv")
    rows = []
    for _, m in matches.iterrows():
        p = ROOT / "data" / "shots" / f"{m.match_id}.json.gz"
        if not p.exists():
            continue
        for s in json.load(gzip.open(p, "rt", encoding="utf-8")):
            x, y = s["location"][:2]
            r = {"match_id": m.match_id, "competition": m.competition, "season": m.season, "gender": m.gender,
                 "international": m.international, "data_version": m.data_version,
                 "id": s["id"], "team": s["team"], "player_id": s["player_id"], "type": s["type"],
                 "goal": int(s["outcome"] == "Goal"), "statsbomb_xg": s["statsbomb_xg"],
                 "x": x, "y": y, "dist": np.hypot(GX - x, 40 - y), "abs_dy": abs(40 - y),
                 "angle": abs(np.arctan2(P2 - y, GX - x) - np.arctan2(P1 - y, GX - x)),
                 "body_part": s["body_part"], "technique": s["technique"], "play_pattern": s["play_pattern"],
                 "first_time": int(s["first_time"]), "under_pressure": int(s["under_pressure"]),
                 "follows_dribble": int(s["follows_dribble"]), "one_on_one": int(s["one_on_one"]),
                 "open_goal": int(s["open_goal"]), "has_ff": int(bool(s["freeze_frame"]))}
            if s["freeze_frame"]:
                r.update(geometry(s))
            r.update(visibility(s))
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_parquet(ROOT / "data" / "shots.parquet", index=False)
    print(len(df), "shots;", df.type.value_counts().to_dict())
    print(df.groupby(["gender", "international"]).agg(n=("goal", "size"), goal=("goal", "mean"),
                                                      ff=("has_ff", "mean"), s360=("has360", "sum")))


if __name__ == "__main__":
    main()
