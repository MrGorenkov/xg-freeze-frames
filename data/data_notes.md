# Data notes (checked 2026-09-23)

## 1. StatsBomb open data: where it lives now

- `github.com/statsbomb/open-data` now **redirects to `github.com/hudl/open-data`** (GitHub API: `full_name = hudl/open-data`, default branch `master`, last push 2026-09-07, licence field `NOASSERTION`, meaning the licence is a custom PDF and not an SPDX licence).
- Layout (from README): `data/competitions.json`; `data/matches/{competition_id}/{season_id}.json`; `data/events/{match_id}.json`; `data/lineups/{match_id}.json`; `data/three-sixty/{match_id}.json`; specs in `doc/`.
- Saved locally: `data/competitions.json` (80 competition-seasons); `data/StatsBomb_open_data_LICENSE.pdf`; `data/spec/Open_Data_360_Frames_v1.0.0.pdf`; `data/spec/Open_Data_Events_v4.0.0.pdf`; `data/spec/open-data_README.md`.

### Size and partial download
- GitHub-reported packed repository size: 7,403,076 KB, about **7.1 GB**. A full `git clone` is therefore large.
- Uncompressed sizes from the git tree API: `events/` has 4,235 files, **12.2 GB**. `three-sixty/` has 426 files, **3.06 GB**. `lineups/` has 4,235 files, 79 MB. `matches/` totals about 7 MB.
- **Partial download works.** Every file is served individually at `https://raw.githubusercontent.com/hudl/open-data/master/data/...`. A per-competition download is: fetch `matches/{cid}/{sid}.json`, then fetch `events/{match_id}.json` (and `three-sixty/{match_id}.json`) for those matches. This is how `statsbombpy`/`socceraction` loaders work. Alternatives are `git clone --filter=blob:none --sparse` with `git sparse-checkout set data/matches data/events/...`.
- Typical file sizes: an event file is about 2.9 MB per match; a 360 file is about 7.2 MB per match.
- Estimated download for the whole 360 subset (426 matches): events about 1.44 GB plus 360 frames about 3.06 GB, **≈ 4.5 GB**. The full event data for all 3,961 listed matches is about 11.4 GB. Neither was downloaded now; only matches files and a 30-match sample (~97 MB, in the scratchpad, not in this folder).

## 2. Competitions with 360 data vs shot freeze frames only

Two distinct positional sources exist, and the paper must keep them apart:
1. **Shot freeze frame** (`event.shot.freeze_frame`, inside the event files). For each shot, it gives the location, player, position and teammate flag of the players visible on camera, *excluding the shooter*. It exists for essentially **all competitions** in the open data, including historic matches.
2. **StatsBomb 360 frame** (`three-sixty/{match_id}.json`). Every event gets `visible_area` (polygon of the camera view) plus `freeze_frame` entries with `location, teammate, actor, keeper`. **There is no player identity** ("these freeze frames will not contain player identification, beyond their team (except for the player performing the current event who will be marked as the actor)", 360 spec v1.0.0, 17 Nov 2021). 360 frames are available only for 426 matches.

Spec caveats (360 spec, quoted): "Not all 22 players will be visible in the frame." "The visible_area attribute will not be available for every frame." "Not all events in the match will receive a 360 frame." "Some events will lack a player marked with the 'actor' attribute." "The 'keeper' attribute will, in some rare cases, refer to the keeper on the same team as the 'actor', without being marked as a 'teammate'."

### 2a. Competition-seasons with 360 files (counted by matching three-sixty file names to match IDs)

| Competition | Season | comp_id / season_id | Gender | Type | Matches | Matches with 360 file | Est. shots* | Events MB | 360 MB | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| FIFA World Cup | 2022 | 43/106 | M | international | 64 | 64 | ~1,750 | 190 | 438 | full tournament |
| UEFA Euro | 2020 | 55/43 | M | international | 51 | 51 | ~1,400 | 156 | 360 | full |
| UEFA Euro | 2024 | 55/282 | M | international | 51 | 51 | ~1,400 | 153 | 381 | full |
| Women's World Cup | 2023 | 72/107 | F | international | 64 | 64 | ~1,750 | 188 | 403 | full |
| UEFA Women's Euro | 2022 | 53/106 | F | international | 31 | 31 | ~850 | 87 | 188 | full |
| UEFA Women's Euro | 2025 | 53/315 | F | international | 31 | 31 | ~850 | 88 | 190 | full |
| 1. Bundesliga | 2023/24 | 9/281 | M | club | 34 | 34 | ~900 | 114 | 276 | **Bayer Leverkusen matches only** |
| La Liga | 2020/21 | 11/90 | M | club | 35 | 35 | ~950 | 114 | 307 | **Barcelona matches only** |
| Ligue 1 | 2022/23 | 7/235 | M | club | 32 | 32 | ~850 | 107 | 274 | **PSG matches only** |
| Ligue 1 | 2021/22 | 7/108 | M | club | 26 | 26 | ~700 | 84 | 207 | **PSG matches only** |
| Major League Soccer | 2023 | 44/107 | M | club | 6 | 6 | ~150 | 18 | 39 | **Inter Miami only** |
| African Cup of Nations | 2023 | 1267/107 | M | international | 52 | 1 | ~1,400 | 133 | ≈0 | flagged `match_available_360` in competitions.json, but only one 360 file of **1,962 bytes** (effectively empty), so treat as **no 360** |
| **Total** | | | | | **477** | **426 (425 usable)** | **~11,500 (360 subset, excl. AFCON)** | | 3,063 | |

*Estimated shots = matches × 27. The factor comes from a sample of 22 matches with 360 data, which averaged 27.6 shots per match (range 12–41). See §3. These are **estimates**; exact counts need the full event download.

### 2b. Competition-seasons with shot freeze frames but no 360 (selection; full list in competitions.json)

| Competition | Season(s) | Gender | Matches | Est. shots | Note |
|---|---|---|---|---|---|
| Premier League | 2015/16 | M | 380 | ~10,250 | full season |
| La Liga | 2015/16 | M | 380 | ~10,250 | full season |
| Serie A | 2015/16 | M | 380 | ~10,250 | full season |
| Ligue 1 | 2015/16 | M | 377 | ~10,200 | full season |
| 1. Bundesliga | 2015/16 | M | 34 | ~900 | Leverkusen only |
| La Liga | 2004/05–2019/20 (16 seasons) | M | 7–38 each (≈ 500 total) | ~13,500 | **Barcelona (Messi) matches only** |
| Premier League | 2003/04 | M | 38 | ~1,050 | Arsenal only |
| FIFA World Cup | 2018 | M | 64 | ~1,750 | data_version 1.0.2 |
| Copa America | 2024 | M | 32 | ~850 | |
| Indian Super League | 2021/22 | M | 115 | ~3,100 | |
| FA Women's Super League | 2018/19, 19/20, 20/21, 23/24 | F | 107 / 87 / 131 / 132 | ~12,300 total | full seasons (18/19 partly data_version 1.0.3) |
| Frauen-Bundesliga | 2023/24 | F | 132 | ~3,550 | full season |
| Liga F | 2023/24 | F | 240 | ~6,500 | full season |
| Serie A Women | 2023/24 | F | 130 | ~3,500 | full season |
| NWSL | 2018 / 2023 | F | 36 / 137 | ~950 / ~3,700 | 2018 = data_version 1.0.2 |
| Women's World Cup | 2019 | F | 52 | ~1,400 | |
| Historic single matches | Champions League finals 1970–2019, World Cups 1958–1990, etc. | M | 1–6 each | small | historic, video-coded; exclude or use as a robustness case |

**Overall:** 80 competition-seasons, **3,961 matches** (2,651 men's, 1,310 women's), roughly **100–110k shots** at about 27 per match. The per-match shot rate is unverified for every competition.

### Important data caveats for the design
- **Team-selection bias.** Several club "seasons" contain only one team's matches: Barcelona (La Liga), PSG (Ligue 1 21/22 and 22/23), Leverkusen (Bundesliga), Inter Miami (MLS), Arsenal (PL 03/04). In these, one team takes about half the shots, and that team is elite. Cross-competition transfer results on these subsets confound *competition* with *team quality* (cf. Davis & Robberechts 2024 on finishing-skill bias). Use full tournaments and full seasons as the main transfer units.
- **Data versions.** WC 2018 and NWSL 2018 are `data_version 1.0.2`, and part of FAWSL 18/19 is 1.0.3; everything else is 1.1.0. Check the freeze-frame schema per version.
- **Penalties have no freeze frame.** In the sample, every non-penalty shot had one. The only exception was one NWSL 2018 match, where 1 of 29 frames lacked the opposing goalkeeper. Exclude penalties and consider excluding direct free kicks, as is standard.
- **Visibility differs between 360 and shot freeze frames.** In the sample, the mean number of players per shot freeze frame was 9–16 (lowest in historic 1970 footage at 9.1). 360 frames give the visible-area polygon, so "defender absent" can be told apart from "defender off-camera". This is a real methodological advantage of 360 over shot freeze frames.
- **360 frame coverage of shots.** In WC 2022 match 3857266, 30 of 31 shots had a 360 frame, and 3,292 of 3,853 events had frames. 360 frame players have no identity; the shooter is marked `actor`.
- `statsbomb_xg` is present on every shot in the sample, including historic ones. It is itself a model **using freeze-frame features** (Hudl blog, Vatvani 2022), trained on proprietary data, so it is a strong external benchmark and not a "classical" baseline.

## 3. Sample check (30 matches, events downloaded to the scratchpad only)

Script: `scratchpad/sample_shots.py` (stdlib only). For each match it recorded shots, penalties, shots with freeze frames, shots with `statsbomb_xg`, mean players per frame, and opposing GK present:
- WC 2022: 31/31/28 shots per match, 100% with freeze frames, GK present in all, 13.5–15.0 players per frame.
- WWC 2023: 31/22/31. Euro 2024: 30/24. Euro 2020: 27/27. WEuro 2022: 28/30. WEuro 2025: 34/25. Bundesliga 23/24: 28/41. La Liga 20/21: 29/12. Ligue 1: 27/25/26. MLS 2023: 21.
- Non-360: PL 15/16: 20. La Liga 15/16: 27. WC 2018: 19. NWSL 2018: 29. FAWSL 20/21: 20. WWC 2019: 27. AFCON 2023: 23. WC 1970: 61 (mean 9.1 players per frame).

## 4. Licence: StatsBomb Public Data User Agreement

File: `data/StatsBomb_open_data_LICENSE.pdf`. Footer: "[StatsBomb Data: User Agreement Standard Terms - last updated 8 September 2023]". URL: https://github.com/hudl/open-data/blob/master/LICENSE.pdf (old path github.com/statsbomb/open-data redirects).

Key quotes:
- Purpose: "StatsBomb have made this data freely available and accessible to encourage and facilitate research and the shared analytical understanding of the game of Football. This is aimed to be a research tool, and is intended to be used as such. Any analysis or conclusions that are created as a result of using this data, may be shared publicly but are not necessarily the opinions or analytical insights of StatsBomb."
- Registration: "StatsBomb ask that all Users register their interest in our data via our website, www.statsbomb.com/resource-centre."
- 1.1: "StatsBomb will provide the User with access to the Service to be used for analysis, research and to facilitate the shared ideas & understanding of the data"
- 1.2: "The User may not: 1.2.1. edit, distort, distribute, reproduce, sell or in any way provide the data to any external or third party; 1.2.2. commercially exploit the data or any analysis derived from the use of the Service; …"
- **Attribution, 1.4: "The User is required to accredit any publication of analysis formed from StatsBomb Data with the StatsBomb brand logo."**
- README: "If you publish, share or distribute any research, analysis or insights based on this data, please state the data source as StatsBomb and use our logo, available in our Media Pack (https://statsbomb.com/media-pack/)."
- 7 (IP): "all data provided through the Service, is the property of StatsBomb … shall not modify, translate, transfer, distribute, license, sell or otherwise exploit … without the express prior written consent of StatsBomb".
- Governing law: England and Wales.

**Implications for the paper:**
- Academic, non-commercial research is explicitly allowed.
- Put the StatsBomb logo in the paper, e.g. on a figure or in the acknowledgements, and name "StatsBomb (Hudl) open data" as the source.
- **Do not deposit raw or derived shot-level tables** containing StatsBomb data in Zenodo or supplementary material (1.2.1, 7). Publish the code, which downloads directly from the official repository, pinned to a commit hash. Publish aggregate results and trained-model coefficients.
- For JQAS's data availability statement, use wording like "Data are publicly available from StatsBomb/Hudl at github.com/hudl/open-data (commit …) under the StatsBomb Public Data User Agreement; redistribution is not permitted. Code: Zenodo DOI …".
- If you want to share the feature table, ask Hudl StatsBomb for written permission.

## 5. Secondary source: Wyscout public dataset (Pappalardo et al., 2019)

- Paper: Pappalardo, L., Cintia, P., Rossi, A., Massucco, E., Ferragina, P., Pedreschi, D., Giannotti, F. (2019). *A public data set of spatio-temporal match events in soccer competitions.* Scientific Data 6: 236. https://doi.org/10.1038/s41597-019-0247-7 (Crossref-verified).
- Data: figshare collection "Soccer match event dataset", https://doi.org/10.6084/m9.figshare.c.4415000.v5 (v5, 2020-01-28). Articles include Events (events.zip, **73.7 MB**), Matches (0.6 MB), Players, Teams, Competitions, Coaches, Referees, PlayeRank, and tag/event ID mappings.
- **Licence: CC BY 4.0** (figshare API for the Events, Matches and Competitions articles; also Crossref licence metadata of the paper). Required: "If you use these data cite the following paper: Pappalardo et al., (2019) … Nature Scientific Data 6:236".
- Coverage (figshare "Competitions" description): "seven major soccer competitions (Italian, Spanish, German, French, English first divisions, World cup 2018, European cup 2016)", one season each (2017/18 leagues). The abstract says "all the spatio-temporal events … for an entire season of seven prominent soccer competitions."
- **No freeze frames and no defender or goalkeeper positions.** The only positional information is the event's start/end location. Mead et al. (2023) used these data for xG and noted that "positional data" were unavailable.
- Possible use: an external *location-only* transfer test (train on StatsBomb, test on Wyscout, e.g. WC 2018, which both providers cover). Because provider definitions differ (Robberechts & Davis 2020 advise against mixing providers), treat this only as a robustness appendix.

## 7. Download at the pinned commit (2026-09-24)

- `code/download_shots.py` at commit `4b73468fc5` fetched all 3,961 matches. Only the shots are kept, with their freeze frames and, where present, the 360 frame of the shot event, in `data/shots/{match_id}.json.gz` (local only).
- **One corrupted 360 file:** `three-sixty/3845506.json` (UEFA Women's Euro 2022 semi-final, England–Sweden, 2022-07-26) is not valid JSON at this commit. The parser fails at the same character, 2,637,824, on every download. The match is kept, but its 28 shots have no 360 frame.
- Every 360 frame carries an `actor` whose location equals the shot location (2,265 of 2,265 checked). The 360 coordinates therefore share the orientation of the event data.
