# Online stats check: Vikings and Scots (Update 17.0), 2026-10-27

**Bottom line:** No published source has newer or more complete numeric Vikings/Scots stats than what the project already has. Official full patch notes are not out yet. aoe4world has not added the civs. jeandogaming still lists both civs but shows no version or date, so there is no sign its dataset changed after 2026-10-24. The only thing that changed is the fandom wiki: its Vikings/Scots pages were edited 2026-10-26/27, after the project's 2026-10-23 wikitext grab. I did not read those edits.

Budget: 12 searches/fetches used, which was the cap.

## Per-source findings

### 1. aoe4world (data repo and explorer)
- https://github.com/aoe4world/data: the `units/` directory has 23 civ folders and no `vikings` or `scots` folder (read 2026-10-27 via `gh api repos/aoe4world/data/contents/units`). CONFIRMED.
- Commits since 2026-10-15 (`gh api repos/aoe4world/data/commits`, read 2026-10-27). Newest first: 2026-10-23 "Updated to patch 16.2.10604", 2026-10-23 "Updated to patch 16.1.10056 (And fix for Greatwall Bastion Bed Crossbows)", 2026-10-23 "Fixed mongol prayer tent being omitted", then commits on 2026-10-17/18/20 for locale extraction and weapon ids. None mention 17.0, Vikings or Scots. No GitHub releases are published. CONFIRMED.
- Note: the repo's newest patch label is 16.2.10604, which is behind the installed 16.3 catalog. CONFIRMED (commit message).
- https://aoe4world.com/explorer: lists the existing civs and has no Vikings or Scots. No version string on the page (read 2026-10-27). CONFIRMED.
- Final or preview: neither. No 17.0 data exists here yet.

### 2. jeandogaming.com explorer
- https://jeandogaming.com/fr/aoe4/explorer lists 25 civs, including "Vikings" and "Écossais" (`/scots`). The page shows no version, patch, build number, "updated" date or changelog (read 2026-10-27). CONFIRMED.
- A raw curl of https://jeandogaming.com/fr/aoe4/explorer/vikings (506 KB, served with no-cache headers, 2026-10-27) contains no "17.0", "16.3" or build-number strings. The only "patch" matches are UI strings like `"patch":"Patch {version}"`. I cannot tell from the page whether the dataset changed after 2026-10-24. To check, diff a fresh RSC payload against the 2026-10-24 capture. UNVERIFIED (whether it was updated).
- The homepage https://jeandogaming.com has a "Patch 17.0" video entry that refers to DLC patch notes dated 29/10/26. That is a video, not data. LIKELY.
- Final or preview: preview datamine. Nothing marks it as the release build.

### 3. Official sources (ageofempires.com, Steam)
- https://www.ageofempires.com/news/age-of-empires-iv-update-17-0/ is titled "Age of Empires IV – Update 17.0 Preview", byline "AoE Official October 22, 2026". It says Raiders of the North releases October 29. It names Longhouse, Knights, Militia Crossbowmen, Heroic Sagas, Sacred Groves, Highland Cattle, Tower Houses and Mustering Hall, but gives **no HP, attack, cost, armor or research-time numbers**. It does not promise a date for full notes; it mentions "a patch in the near future" and links a "17.1 - Bugfix QoL" page (read 2026-10-27). CONFIRMED.
- Steam news for app 1466860 (https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=1466860, read 2026-10-27):
  - 2026-10-26 "Raiders of the North Time Zone Map"
  - 2026-10-22 "Update 17.0 Preview"
  - 2026-10-16 "The Crucible Reforged"
  - 2026-10-12 "The Vikings in Raiders of the North"
  - 2026-10-09 "The Scots in Raiders of the North"

  None of these are full patch notes. CONFIRMED.
- Final or preview: official preview only. Full 17.0 patch notes are not published as of 2026-10-27. They are presumably due on release day, 2026-10-29. UNVERIFIED (timing).

### 4. Fandom wiki and stats sites
- The fandom recent-changes API (https://ageofempires.fandom.com/api.php?action=query&list=recentchanges, window 2026-10-20 to 2026-10-27, read 2026-10-27) shows these edits after the project's 2026-10-23 wikitext grab. CONFIRMED (edit timestamps):

  | Page | Last edit (UTC) | New size (bytes) | Project copy |
  |---|---|---|---|
  | Vikings (Age of Empires IV) | 2026-10-27T05:47 | 9026 | none |
  | Longhouse (Age of Empires IV) | 2026-10-27T07:15 | 2588 | none |
  | Longship (Age of Empires IV) | 2026-10-27T07:21 | 2358 | none |
  | Berserker | 2026-10-26T22:40 | 3754 | 2594 |
  | Age of Empires IV: Raiders of the North | 2026-10-26T12:23 | 6979 | 7126 |
  | Scots | 2026-10-26T10:41 | 8163 | none |

  I did not open these edits because of the budget, so whether they add numbers, and where those numbers came from, is UNVERIFIED. Wiki pages before release usually copy official blogs and preview videos.
- aoe4.net / aoestats: not checked separately (budget). They are match-statistics sites and would not hold unit stats before release. UNVERIFIED.

### 5. Other datamines (reddit, forums, GitHub mirrors)
- Search for "aoe4 vikings scots datamined unit stats 17.0 reddit" (2026-10-27) found no reddit or GitHub datamine. It found only forum discussion threads, for example https://forums.ageofempires.com/t/first-look-at-viking-berserkers-and-longboats/285739 and https://forums.ageofempires.com/t/age-of-empires-iv-raiders-of-the-north/286737, which have impressions and no numbers. LIKELY (search coverage is not exhaustive).

## Verdict

There is nothing worth aligning the preview catalog to right now. The official 17.0 post (2026-10-22) is a preview with no numbers. aoe4world/data has no Vikings or Scots and is still labeled patch 16.2. No reddit or GitHub datamine came up. jeandogaming is still the only numeric source, it shows no version or date, and there is no evidence it changed after the 2026-10-24 capture. Two cheap optional steps before release: (a) diff a fresh jeandogaming RSC payload against the 2026-10-24 capture, and (b) re-pull the fandom wikitext for the six pages edited 2026-10-26/27 to see whether they added numbers. The real alignment target is the release itself on 2026-10-29: the official full patch notes, the installed 17.0 game files, and the aoe4world/data commit that adds `vikings`/`scots`, which usually lands within days of a patch.
