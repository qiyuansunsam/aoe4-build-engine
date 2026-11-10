# Installed tier-list identities

The ranking collector reads the committed `data/tier-catalog.json`. It has no web or AoE4 World dependency. Regenerate it offline from the installed-game catalog in the same checkout:

```powershell
python -X utf8 scripts/build_tier_catalog.py
```

The source `data/game-catalog.json` was extracted from installed patch **17.0.12260**, Steam build **26400362**. Output provenance records the source-file hash, original archive hash, extraction time and patch. Numeric blueprint IDs, military classes, names and civilization references all come from that source. The collector independently checks match build metadata against downloaded replay headers.

Records are keyed by `(commandKind, pbgid)`. Training commands identify squad blueprints. Field construction identifies entity blueprints, so unit `entitySource` IDs create build-command aliases to the matching family. Field-built and workshop-produced siege join the same family. Shared entity IDs with conflicting family names remain unmapped.

Unit families normalize leading age-tier prefixes. Ghillie and Scout remain separate. Jeanne's Elite Champion/Rider join their non-Elite families. Technology names use the installed upgrade description to distinguish generic labels such as "Upgrade to Elite". Landmark buildings and House of Wisdom wing orders are included; ordinary buildings and victory wonders are excluded.

Current installed records resolve earlier gaps:

| Command | Blueprint ID | Identity | Classification |
| --- | --- | --- | --- |
| Build | 9007403 | Scots Fishpond | Ordinary building |
| Build | 9005988 | Vikings Sacred Grove | Ordinary building |
| Research | 9006034 | Upgrade to Hirdman | Technology |

Missing unit classifications and conflicting identities appear in `omittedIdentities`. The collector must exclude affected player-games from the relevant choice category rather than treating missing data as zero usage. Rank filters describe association with outcomes, not causal unit strength.

Focused checks:

```powershell
python -X utf8 -m unittest discover -s scripts -p test_tier_catalog.py
```
