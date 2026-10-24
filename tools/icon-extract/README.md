# Local game UI icons

`IconExtract` reads only requested archive paths from `requested.json` and writes them into the local game knowledge base. It does not edit the installation. `bin/` and `obj/` are ignored.

Extraction used the installed `cardinal/archives/UIArt.sga` (Steam build 24231237). The existing local AOEMods Essence CLI converts `.rrtex` files to PNG with `rrtex-decode --batch`. The raw extracted files remain under `projects/games/kb/aoe4/extract/UIArt`, outside this project.

Run `python scripts/package_game_icons.py` from the project root after extraction. It selects only comparison-relevant art, preferring installed icons and using the existing mcaoe artwork cache when needed. `data/game-icons-provenance.json` identifies each source and SHA-256. `data/game-icons.json` is a flat normalized-name-to-data-URL map embedded by `site/build.py` as `window.GAME_ICONS`. Missing art is listed explicitly; never use an unrelated icon as a substitute.

Artwork is used in Sam's local workspace. Image availability does not establish any unit statistic or patch equivalence.
