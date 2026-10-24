# Upcoming civilizations: Vikings and Scots (Raiders of the North, Update 17.0)

Collected 2026-10-23, numbers filled 2026-10-24. Neither civilization is in the installed game (Steam build 24231237, 16.3.11308). Text sources: `data/upcoming-civs/vikings.json`, `scots.json`, `raw/`. **The numbers now live in `data/upcoming-civs/checklist.json` (full provenance), `stats.json` (compact base + tier values for the engine), `CHECKLIST.md` and `review.html`, and in the app's Library (Next view) via `data/catalog-preview-17.0.json`.** The sections below "Status 2026-10-24" are the 2026-10-23 text-only collection and are kept as history; their "unknowns" are answered by the status section.

## Status 2026-10-24: numbers from frames, datamined records and game files

344 objects, 2,953 fields: **2,169 confirmed** by two or more independent sources, 706 single-source, 70 n/a, 2 text-only, **6 unknown, 0 conflicts**. The 822 fields of the civs' unique objects (the 90 from the text sources) are 752 confirmed, 52 single-source, 17 n/a, 2 text-only, none unknown. The other 254 objects are the civs' standard roster (Villager, Archer, Barracks, Wheelbarrow …) as these civs see it, discovered in the datamined records and footage.

### Sources, and how each value is checked

| Source | What it gives | Check |
|---|---|---|
| Early-access video frames: 10 YouTube videos (Beastyqt, Aussie_Drongo, Corvinus1, LaSh, GiveUAnxiety, FitzBro, RTS_Papercut) and 16 bilibili parts (loueMT, DarkCarrot, 润州镜, and CaramelSG's re-uploads of the 2026-10-21..23 test-server streams of Beasty, Anotand, Corvinus, MarineLorD and LucifroN) | Tooltips and stat panels: costs, times, HP, armor, damage, bonus damage, attack speed, effects, tier stats | Frames extracted with ffmpeg, OCR-indexed on the GPU, tooltip moments clustered by title, read by an agent, then every number re-read **blind** (value hidden) by a second agent from the same frame; disagreements go to a third reader. 3,324 numbers passed (3,244 agreed outright, 80 settled by the third reader), 12 rejected (0.4%). Cited frames are copied to `frames/<video>/` (gitignored, ~340 MB). |
| jeandogaming.com explorer ("figures taken from the game files") | Datamined 17.0 records for every unit tier, building and technology of both civs (`raw/jeando/*_dataset.json`) | Counts as one source. Its standard objects equal the installed 16.3 game files in 1,268 of 1,275 values; the 7 differences (4 distinct changes) are below. Building `age` from this site is not used (it contradicts footage). |
| Installed 16.3 game files (`data/game-catalog.json`) | Same base objects for the standard roster; standard producers | Equal value = second source; different value kept as variant "installed 16.3 value". Producers and standard building ages are labelled `standard-roster` (not observed for these civs). |
| Web sweep (bilibili subtitles and articles, NGA/Tieba/Zhihu, other-language sites, English sites) | Spoken or written numbers | Each claim re-fetched by a separate verifier: 529 confirmed, 43 refuted. Claims that cite a video or jeandogaming map back to that source and do not count twice. |

Status rules (merge script): one source = `single-source`; two or more independent sources agree = `confirmed` (a disagreeing minority is kept as `dissent`); no majority = `conflict`; the object has no such stat = `n/a`. Tier and context readings (Hardened/Veteran/Elite, blacksmith upgrades, auras, discounts) are `variants` and never compete with the base value. Reviewed reclassifications, name aliases and exclusions are in `resolutions.json`, each with its evidence.

### Calculated values

- **Attack speed** = windup + cooldown + winddown + aim + reload + max(0.125 s tick, burst duration) of the primary weapon. It reproduces every tooltip read from footage (Bondi 1.88, Spearwall 1.12, torch 2.12, Berserker 1.25, Hirdman 1.38, Shield Maiden 2.12, Ghillie 2.00, Jylland Knight 1.50, Drakkar 4.88).
- Datamined values carry full precision; the tooltip rounds them (speed 1.375 shows as 1.38, train time 19.5 as 20 s). The merge treats those as the same reading and keeps the precise value.

### Where the 17.0 records differ from the same object in the installed 16.3 files

Only the Town Center row is known to be a global 17.0 change (the official notes say so). The others could be global 17.0 changes or specific to these civs; the records alone cannot tell.

| Object (civ) | 16.3 standard | 17.0 record |
|---|---|---|
| Town Center, additional (both) build time | 150 s | 165 s |
| Battering Ram (both) HP | 370 | 410 |
| Villager (Vikings) train time | 20 s | 22 s (Scots stay at 20 s) |
| Transport Ship (Scots) speed | 1.5 tiles/s | 1.625 tiles/s |

Corrected 2026-10-24: an earlier version also listed Bloomery, Decarbonization and Damascus Steel. Those rows were wrong: the comparison stripped `_iii` as if it were a civilization code and voted across civ-specific variants (Japanese, Delhi). Against the standard records, all three are unchanged (50/125, 100/250, 150/350 food/gold).

### Mechanics worth knowing for build orders

- Vikings start with **0 food**, 200 wood, 100 gold, 0 stone, 6 villagers and a scout; Scots start with 200 food, 200 wood, 100 gold, 6 villagers, a Ghillie and 1 Highland Cattle (not counted in population).
- Vikings villagers are recruited automatically **at no cost every 22 s** up to the villager capacity (10 at start, +10 per Longhouse). Food stays 0 on screen while they appear. The unit record's 50 food is kept as a labelled variant. Falkr's Village saga cuts the interval by 2 s.
- The six Vikings armor/damage techs are auto-researched by the Longhouse Smithy (damage) and Pasture and Loom (armor) attachments: no cost, 270 s each, one tier per age (Feudal/Castle/Imperial). The attachments cost 100 wood / 100 gold (80/80 with the saga discount).
- Bondi train in 17 s at the Barracks and slower at the Longhouse (23 s read on screen). Baugr Fort makes Barracks technologies 15% cheaper (frames showing 85/213 and 255/595 are those discounted tooltips).
- Scots Highland Cattle cost 75 food / 25 gold, 25 s at the Tower House, and produce 30 food per minute while grazing at berries (capacity starts at 9).
- Full per-tier stats (Hardened/Veteran/Elite) for every unit are in `stats.json` under `tiers`.

### Still open

- Unknown (no frame and no record shows them): Code of Jylland and Sledges, age and building (their records give cost and time only: 100 food / 50 gold / 45 s and 50 wood / 100 gold / 40 s); Upgrade to Veteran Berserker, building; Culverin bonus damage.
- Text-only: the "'Seven Sisters' cannons" entry is a landmark property of Dhùn Èideann, not a researched tech, so its cost and research time are n/a. Its weapons are listed under the landmark (seven cannons, 70/70/40/40/30/30/20 ranged damage with an equal bonus vs ships).
- Single-source values: 706, mostly datamined-only fields of standard objects (class lines, tier ages, calculated attack speeds). Unique objects have 52.
- Not read: 6 bilibili parts whose signed URLs expired (LucifroN part 2, VortiX parts 1-2, Beasty 2026-10-21 DLC stream, a 5-minute ships clip, a second DarkCarrot upload) and two reader batches stopped after running for hours (Beastyqt Vikings 0:13-6:20 lobby and sagas; GiveUAnxiety Scots batch 1). Their content is covered by other sources.
- The Vikings villager capacity reached 200 in three games; nothing on screen says whether that is a hard cap.
- Bee Skeps pay about 8 gold every 10 s (~48/min) on screen against the tooltip's 50 per minute.

### Reproduce

```
python -X utf8 scripts/download_upcoming_videos.py            # YouTube 1080p video + audio to .cache/upcoming-videos
bash scripts/run_upcoming_ocr.sh                                # frames + GPU OCR (.cache/ocr-venv, onnxruntime-directml)
python -X utf8 scripts/bili_pipeline.py                         # bilibili parts (needs .cache/bili/parts.json from a logged-in browser tab)
python -X utf8 scripts/plan_frame_batches.py <video ids>        # tooltip clusters -> .cache/frame-batches (agents read these)
python -X utf8 scripts/extract_jeando_dataset.py && python -X utf8 scripts/jeando_to_fills.py
python -X utf8 scripts/catalog_crosscheck_fills.py && python -X utf8 scripts/standard_roster_fills.py
python -X utf8 scripts/merge_checklist_fills.py && python -X utf8 scripts/export_upcoming_stats.py && python -X utf8 scripts/build_review_page.py
python -X utf8 scripts/build_preview_catalog.py && python -X utf8 site/build.py   # Library Next view (data/catalog-preview-17.0.json)
python -X utf8 scripts/search_frames.py "<regex>"               # search every OCR'd frame
```
Agent results are collected with `scripts/replay_workflow_journal.py` + `scripts/collect_workflow_fills.py`. After 17.0 ships, the installed-game extraction (`data/INSTALLED_DATA.md`) replaces all of this as the primary source.

## Release date evidence

| Source | Statement | Date of source |
|---|---|---|
| [Update 17.0 notes](https://www.ageofempires.com/news/age-of-empires-iv-update-17-0/) | "Raiders of the North is Available October 29!"; page is a preview, no separate date for the update itself | 2026-10-22 |
| [Official civ pages](https://www.ageofempires.com/games/age-of-empires-iv/civilizations/vikings/) | "Vikings Coming October 29th" / "Scots Coming October 29th" | live |
| [Steam DLC 4336170](https://store.steampowered.com/app/4336170/Age_of_Empires_IV_Raiders_of_the_North/) | Pre-purchase, "29 Oct, 2026", A$29.95, requires Anniversary Edition | live |
| [Pre-order post](https://www.ageofempires.com/news/pre-order-raiders-of-the-north-for-age-of-empires-iv/) | No date; "more in-depth details closer to release" | 2026-09-29 |

Release date 2026-10-29 is consistent across official sources. The 17.0 notes contain no Vikings/Scots numbers at all: only two marketing paragraphs per civ and the generic change **Town Center build time 150 -> 165 s**.

## What the sources actually give

| Category | Vikings | Scots |
|---|---|---|
| Civ bonuses (text) | Official: free auto-recruited Villagers (Northern Migration), Living off the Land heal, 7 Sagas with named effects, Sacred Grove/Hamingja, pop 210/220. Wiki adds: +10 villager cap per Longhouse, "slower rate", Dock influence -4%/Longhouse ship cost (max 16%) | Official: start with 1 Highland Cattle, cattle graze berries without depleting them, Tower House = Outpost + pop + cattle production, Mustering Hall (food -> muster charges; regional tech discount), Fishponds + gather aura, see through Stealth Forests. Wiki adds: Highland Ambush speed in forests |
| Landmarks | 6 named with text effects (official confirms 3: Konungr Hall, Valdemar Castle, Kongens Dør; other 3 wiki only) | 6 named with text effects (official confirms 3: Stone of Destiny, Tower of Skye, Dhùn Èideann; Abbey of the Isles, Snowdoun Gate, Three Loch Lookout wiki only). Region known for 3 of 6 |
| Unique units | 10 named, roles known, **zero** costs/HP/damage | 9 named (+ MAA with Lochaber Axes), roles known, **zero** costs/HP/damage |
| Unique buildings | Longhouse **has numbers** (wiki): 150 wood, 30 s, 1000 HP, 4x4, +10 vil cap, +25 pop, Bondi 25% slower; attachment table (Bee Skeps 200w -> 50 gold/min, Farmstead 200w -> 2 improved farms + drop-off, Pasture&Loom / Smithy 100w+100g Feudal auto-research). Sacred Grove: text only | Tower House, Mustering Hall, Fishpond: text only, no costs |
| Unique techs | 15 named with text effects; building known for 3 (Ulfberht Swords Barracks, Leikr Training University, Danevirke via Valdemar); no costs/ages | 14 named with text effects; no costs, ages or regions |
| Eco-timing changers | Free villagers (rate unknown), Longhouse attachments, Saga eco bonuses, Konungr Hall food trickle | Cattle food trickle (rate unknown), Stone of Destiny gold rebate (% unknown), muster-for-food, Snowdoun free infantry |
| Openings (commentary) | Official "Through the Ages" narrative only (early Longhouse, Farmstead/Bee Skeps, early Bondi/Berserker raids, buy Pasture&Loom + Smithy early in Feudal) | Official narrative only (cattle to berries by a Tower House, Stone of Destiny with buildings in its reach, Kirkman + Fishpond, Mustering Hall; Tower of Skye Castle; Dhùn Èideann Imperial) |

Confidence labels in the JSON: `official` (ageofempires.com / Steam text), `wiki` (fandom; the landmark/tech/Longhouse detail was added 2026-10-16..22 by one editor with no cited source), `community`, `inferred`.

## Sources checked and found empty

- aoe4world/data GitHub: no `vikings`/`scots` JSON, last commit 2026-05-04, no preview branch. aoe4world.com explorer has nothing.
- Fandom sub-pages for every landmark, 40+ technologies, Bondi/Hirdman (AoE IV), Shield Maiden, Jylland Knight, Tower House, Mustering Hall, Fishpond, Kirkman: do not exist yet.
- Official forum threads 286737 and 207081: reactions and speculation only.
- aoeinfo.net Vikings guide: explicitly says stats and build order pending.
- Liquipedia Scots: HTTP 403.
- ~~No content-creator early-access gameplay with stats found via search.~~ Superseded 2026-10-23: early-access footage exists from 2026-10-22; see "Stats from videos" below.

## Biggest unknowns (block any numeric build order)

1. **Vikings villager recruit interval** and starting villager capacity. The entire Viking eco curve is this one number plus Longhouse timing.
2. **Scots cattle trickle rate**, cattle cost/time/cap, Tower House cost and pop. The Malian cattle values in the installed catalog are not evidence.
3. Every unit cost/stat for both civs (nothing published anywhere).
4. Saga completion thresholds; muster charge cost and yield; Stone of Destiny rebate %.
5. Age-up and landmark costs (assumed standard, unverified); starting resources.
6. Whether the fandom Longhouse numbers come from a live build.

## Can two builds per civ be drafted responsibly now?

**No for numeric builds, yes for structural sketches.** A build order in this project is a timed sequence the engine simulates (CONTEXT.md: "New civilizations require actual plan and mechanic implementations"). With no villager rate (Vikings) or food trickle (Scots), any timeline would be invented. What can be drafted now, clearly labelled "structure only, numbers pending 17.0 extraction":

- Vikings A: Dark Age Longhouse + Farmstead eco into early Bondi/Berserker raid (Baugr Fort Feudal). Vikings B: Longhouse + Bee Skeps gold into Konungr Hall Feudal, Völur + Sacred Grove, Valdemar Castle.
- Scots A (Lowlands): Stone of Destiny Feudal, buildings in its reach, Kirkman/Fishpond, Mustering Hall defence into Snowdoun Gate. Scots B (Highlands): Abbey of the Isles Feudal, Tower House cattle eco, Cateran raids into Tower of Skye.

Assumptions each sketch would carry: standard age-up costs, standard starting resources, Longhouse 150w/30s (wiki), unknown recruit/trickle rates left as parameters, no unit costs. Recommendation: hold the numeric drafts until the 29th.

## After 17.0 lands

Re-run the extraction from `data/INSTALLED_DATA.md` (Reproduce section): `GameExtract.dll` on `Attrib.sga` with the new Steam build id and exe version, then `populate_game_catalog.py`, `test_game_catalog.py`, `build_patch_audit.py`. Then diff `game-catalog.json` against both `upcoming-civs/*.json` to confirm or replace every `wiki`/`inferred` field, and re-fetch the fandom pages (pattern: `api.php?action=parse&page=<title>&prop=wikitext&format=json`, see `raw/fandom_vikings_api.json`).

## Stats from videos

Swept 2026-10-23/24 (details and method in `videoSources` / `conventions.videoMining` of each JSON). Early-access footage exists: World's Edge gave creators test-server access around 2026-10-22, and Beastyqt, Aussie_Drongo, FitzBro, Anotand, Corvinus and loueMT all published that day. **No remote channel exposes what is on screen**: YouTube transcripts do not load through any endpoint tried (jina render, youtubetranscript.com, Invidious), Reddit is blocked, and descriptions/chapters carry no numbers. Every number below is a chapter title or a named commenter, labelled `video-transcribed`, and must be confirmed on screen.

### Vikings

| Item | Stat | Value | Who read it | Where |
|---|---|---|---|---|
| Longship | transport capacity | 16 units | @jsr3299 (comment, 16 likes) | [Beasty 44:11 SHIPS](https://www.youtube.com/watch?v=nd74LibluQ0&t=2651s) |
| Longship | bonus per non-villager passenger | +30 HP, +1 arrow (full ship +480 HP / +16 arrows) | @jsr3299 | same |
| Imperial landmark (which one unverified) | max pop bonus | +20 (fandom said +10) | Beasty chapter title "20 MAX POP LANDMARK??" | [Beasty 40:38](https://www.youtube.com/watch?v=nd74LibluQ0&t=2438s) |
| Springald ships / warships | behaviour | fire while moving, limited attack angles | @KochiyaOcean (comment) | Beasty 44:11-52:37 |

Still zero: every unit cost/HP/damage, villager recruit interval, Longhouse cost confirmation, Saga thresholds, tech costs.

### Scots

No numbers readable remotely. Zero rows. Chapter titles confirm the Ghillie scout ("Unique Scouts?"), Fishponds, gunpowder cavalry (Border Reiver), Seven Sisters, Tower of Skye stealth-forest spawn and Three Loch Lookout, nothing more.

### Videos that show stat panels (verify on screen)

Vikings:
1. **BeastyqtSC2 — Everything You Need to Know About Vikings** (2026-10-22, 53:47, 22K views) https://www.youtube.com/watch?v=nd74LibluQ0 — chapters: 1:39 Villager Auto-Queue · 2:37 Sagas · 5:11 Longhouse · 8:38 Dark Age Military · 10:55 Military eating food · 12:54 Dark Age Buildings · 14:09 Konungr Hall & Shield Maidens · 17:24 Feudal upgrades · 19:10 Unique upgrades · 21:59 Feudal units · 24:19 Blacksmith · 26:55 Völur & Sacred Grove · 30:22 Castle age-ups · 31:31 Castle units & upgrades · 34:42 Groves on Sacred Sites · 39:12 Imperial age-ups · 40:09 Hagl Brodda · 40:38 +20 pop landmark · 42:28 University · 43:50 Baugr Fort · 44:11 Ships · 46:47 Valdemar Castle · 49:50 Ríkets Nyckel · 50:52 more ships. **Best single source**: 5:11 (Longhouse cost/attachments), 8:38 (Bondi/Berserker cards), 21:59 and 31:31 (Hirdman, Shield Maiden, Jylland Knight, Skâne Crossbow cards).
2. **Aussie_Drongo — Civilization Overview - The Vikings** (2026-10-22, 31:18, 41K) https://www.youtube.com/watch?v=uNw-K34ZDPs — no chapters captured.
3. **FitzBro — Vikings vs Rus FIRST LOOK (Early Access)** (2026-10-22, 36:09) https://www.youtube.com/watch?v=qARfRxyhRhA — cast game, player @SAS_y; good for the villager auto-recruit rate in real time.
4. **loueMT — 超详细文明介绍 - 维京** (bilibili, 2026-10-22, 13:34) https://www.bilibili.com/video/BV1dSny6uE4j/ — Chinese, pro player; Scots video promised.
5. Test-server stream VODs reuploaded by CaramelSG (bilibili): Beasty 2026-10-22 https://www.bilibili.com/video/BV182n46EEDi/ · Anotand 2026-10-22 (2 parts, 2h20) https://www.bilibili.com/video/BV1Bmnx6ZEBh/ (Twitch source https://www.twitch.tv/videos/2907670868) · Corvinus 2026-10-22 https://www.bilibili.com/video/BV1Lvn46dEbY/ · Beasty 2026-10-09 preview https://www.bilibili.com/video/BV1H1WA6kE4x/ (Twitch https://www.twitch.tv/videos/2896104764).

Scots:
1. **BeastyqtSC2 — Everything You Need to Know About Scots** (2026-10-23, 39:43) https://www.youtube.com/watch?v=c_oaynL66jY — chapters: 0:00 civ bonuses · 1:22 Ghillie · 2:45 Cattle · 3:47 Tower Houses · 6:20 Stone of Destiny · 7:35 Fishponds · 9:53 Feudal units & upgrades · 14:57 Mustering Hall · 19:36 Snowdoun Gate · 20:56 Castle units · 22:16 Gallowglass & unique upgrades · 25:06 Border Reiver · 27:03 Seven Sisters · **28:35 Imperial Upgrades & Final Stats** · 34:19 Abbey of the Isles · 36:03 Stealth-forest spawn · 37:45 Three Loch Lookout. **Best single source**: 2:45-3:47 (cattle rate, Tower House cost), 14:57 (muster charge cost), 28:35 (final unit cards).
2. **Aussie_Drongo — Civilization Overview - The Scots** (2026-10-23, 41:08, 12K) https://www.youtube.com/watch?v=qlogYcWhKEU
3. The same test-server VODs as above (both civs were tested).

Text-only explainers with no gameplay (checked, nothing numeric): Valdy 2026-09-30 https://www.youtube.com/watch?v=cDG2lTq10DA · Day One Gaming 2026-10-02 https://www.youtube.com/watch?v=y43dWkM5UUA · LaSh (DE) 2026-09-29 https://www.youtube.com/watch?v=3NeeOb9wHkI · Jeando Tutos (FR) Vikings https://www.youtube.com/watch?v=RFHr4W5UHyo and Scots https://www.youtube.com/watch?v=KJqVr8NupKs (both 2026-10-09). Official channel (youtube.com/@ageofempires) has only trailers and the pre-order spot (YR4jW92ssVo); no civ overview.

Next step that actually yields numbers: open Beasty's two videos at the timestamps above and read the cards, or wait for the 17.0 extraction on 2026-10-29.

## Checklist and transcript fills (2026-10-24)

`data/upcoming-civs/checklist.json` / `CHECKLIST.md` list every Vikings and Scots object with the stat fields a build needs (90 objects, 682 fields). `scripts/build_upcoming_checklist.py` rebuilds it from the civ JSON; `scripts/merge_checklist_fills.py` merges agent fill files from `fills/`. Transcripts live in `transcripts/` (`videos.json` lists the candidate videos; `scripts/fetch_video_transcripts.py` uses yt-dlp, which YouTube rate-limited with HTTP 429 after two videos, so the Beastyqt Scots transcript was captured from the YouTube transcript panel instead).

| | Vikings | Scots |
|---|---|---|
| Transcripts read | Corvinus1 (ehO1BOe7wG8); Beastyqt (nd74LibluQ0) capture is broken, timestamps only | Beastyqt (c_oaynL66jY), Corvinus1 (wzT5WTqIIU4) |
| Fields from video (one source) | 51 | 61 |
| Fields confirmed by two sources | 3 | 56 |
| Conflicts | 0 | 5 (Gallowglass damage 19 vs 21 with blacksmith upgrades; Tower of Skye 15 vs 50 percent, likely a caption mishearing; Snowdoun batch 52 vs 58 s; two building attributions) |
| Still unknown | 260 | 202 |

Gaps that still block a numeric build: per-unit HP, armor, train times and most costs for Vikings (the Beastyqt Vikings video reads the unit cards; its transcript needs recapturing); unit train times, Mustering Hall and Fishpond costs, and undiscounted tech costs for Scots. Status labels: `video` = one transcript, `confirmed` = two independent sources, `conflict` = sources disagree, `known-text` = official/wiki text only.
