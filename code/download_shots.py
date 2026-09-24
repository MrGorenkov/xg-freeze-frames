"""Download StatsBomb (Hudl) open data match by match and keep only the shots.

For every match of every competition-season in data/competitions.json the event file is fetched from
raw.githubusercontent.com at a pinned commit; the shots (with their freeze frames) are kept, and for
matches with 360 data the 360 frame of each shot event (visible area + anonymous player locations)
is attached. Raw files are not stored: the data licence does not allow redistribution, and the full
event set is about 12 GB. Output: data/shots/{match_id}.json.gz (local only, git-ignored) and
data/matches.csv. Resumable: matches already present are skipped.
"""
import concurrent.futures as cf
import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "shots"
REPO = "hudl/open-data"
UA = {"User-Agent": "xg-freeze-frames research script"}


def fetch(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** i)
        except Exception:
            time.sleep(2 ** i)
    raise RuntimeError(f"failed: {url}")


def commit_sha():
    return fetch(f"https://api.github.com/repos/{REPO}/commits/master")["sha"]


def shot_record(e):
    s = e["shot"]
    return {
        "id": e["id"], "period": e["period"], "minute": e["minute"], "second": e["second"],
        "team": e["team"]["name"], "player": e["player"]["name"], "player_id": e["player"]["id"],
        "position": e.get("position", {}).get("name"), "play_pattern": e["play_pattern"]["name"],
        "location": e["location"], "under_pressure": bool(e.get("under_pressure")),
        "type": s["type"]["name"], "body_part": s["body_part"]["name"], "technique": s["technique"]["name"],
        "outcome": s["outcome"]["name"], "statsbomb_xg": s.get("statsbomb_xg"), "end_location": s.get("end_location"),
        "first_time": bool(s.get("first_time")), "one_on_one": bool(s.get("one_on_one")),
        "open_goal": bool(s.get("open_goal")), "follows_dribble": bool(s.get("follows_dribble")),
        "aerial_won": bool(s.get("aerial_won")), "redirect": bool(s.get("redirect")),
        "deflected": bool(s.get("deflected")), "key_pass_id": s.get("key_pass_id"),
        "freeze_frame": [{"location": p["location"], "teammate": p["teammate"],
                          "position": p.get("position", {}).get("name")} for p in s.get("freeze_frame") or []],
    }


def one_match(base, m, has360):
    mid = m["match_id"]
    path = OUT / f"{mid}.json.gz"
    if path.exists():
        return mid, "skip"
    ev = fetch(f"{base}/events/{mid}.json")
    if ev is None:
        return mid, "no events"
    shots = [shot_record(e) for e in ev if e["type"]["name"] == "Shot"]
    frames = {}
    if has360:
        tf = fetch(f"{base}/three-sixty/{mid}.json") or []
        ids = {s["id"] for s in shots}
        frames = {f["event_uuid"]: {"visible_area": f.get("visible_area"), "freeze_frame": f.get("freeze_frame")}
                  for f in tf if f.get("event_uuid") in ids}
    for s in shots:
        s["frame360"] = frames.get(s["id"])
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(shots, f, ensure_ascii=False)
    tmp.replace(path)
    return mid, f"{len(shots)} shots, {len(frames)} 360"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pin = ROOT / "data" / "commit.txt"
    if not pin.exists():
        pin.write_text(commit_sha())
    sha = pin.read_text().strip()
    base = f"https://raw.githubusercontent.com/{REPO}/{sha}/data"
    comps = fetch(f"{base}/competitions.json")
    rows = []
    for c in comps:
        ms = fetch(f"{base}/matches/{c['competition_id']}/{c['season_id']}.json") or []
        for m in ms:
            rows.append((c, m))
    print(f"commit {sha[:10]}: {len(comps)} competition-seasons, {len(rows)} matches", flush=True)
    with open(ROOT / "data" / "matches.csv", "w", encoding="utf-8") as f:
        f.write("match_id,competition_id,season_id,competition,season,gender,international,match_date,"
                "home_team,away_team,home_score,away_score,data_version,available_360\n")
        for c, m in rows:
            f.write(",".join(str(v).replace(",", " ") for v in (
                m["match_id"], c["competition_id"], c["season_id"], c["competition_name"], c["season_name"],
                c["competition_gender"], c["competition_international"], m["match_date"],
                m["home_team"]["home_team_name"], m["away_team"]["away_team_name"], m["home_score"], m["away_score"],
                m.get("metadata", {}).get("data_version"), c.get("match_available_360") is not None)) + "\n")
    done = 0
    with cf.ThreadPoolExecutor(max_workers=int(sys.argv[1]) if len(sys.argv) > 1 else 8) as ex:
        futs = [ex.submit(one_match, base, m, c.get("match_available_360") is not None) for c, m in rows]
        for fu in cf.as_completed(futs):
            mid, msg = fu.result()
            done += 1
            if done % 100 == 0 or msg == "no events":
                print(f"{done}/{len(rows)} {mid}: {msg}", flush=True)
    print("finished", flush=True)


if __name__ == "__main__":
    main()
