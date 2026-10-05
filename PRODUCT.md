# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Taskbar Hero players on Windows who clone the repository from GitHub, run `python server.py`, and want to tune the enchantments on their heroes' equipped gear without grinding for rolls. They are not assumed to be technical: they know the game's items and stats, not save formats, raw values, or encryption.

## Product Purpose

A local browser tool that edits Decoration, Engraving, and Inscription slots on equipped items in a `SaveFile_Live.es3` save. Success is a player choosing a hero and item, staging the enchant they want, reviewing before/after values, and writing the save with a backup, without producing a save the game's local checks would reject.

## Positioning

Edits are constrained to stat, tier, material, and value combinations that exist in the game's own extracted tables, and the `SystemInfo` HMAC is recomputed on save. The product is "as safe as a local tool can make it," not "unlimited cheats." Custom out-of-table values exist only as an explicit, warned advanced mode.

## Operating Context

- Runs on the same Windows PC as the game; the save path is auto-filled from the standard location.
- The game must be closed before saving, or it overwrites the edits on exit.
- Workflow: load save → choose hero → choose equipped item → add/edit/clear enchants → review staged changes → save with `.es3.bak` backup.
- Desktop is the primary environment; narrow/mobile layouts are a fallback, not a target use scene.

## Capabilities and Constraints

- Python 3 stdlib server plus vanilla HTML/CSS/JS. No build step, no npm, no runtime dependencies, and no network font or CDN requests; the tool works offline.
- Bundled tables target Taskbar Hero 1.2.4 (Steam build 25336766). Table version and save version are shown separately.
- Stat values are displayed in scaled units (raw ÷ 1, 10, or 100); validation is exact, with no truncation.
- UI language is English only; no i18n is planned.
- Terminology: Decoration, Engraving, Inscription (slot groups); material, stat, tier, value; "staged" changes before "save".

## Brand Commitments

- Name: TBH Save Editor; the UI calls itself the "Enchantment workbench."
- Honesty about risk is binding: never claim an edit is safe, undetectable, or accepted by the game. The game validates some items server-side and accounts can be flagged; DWYOR messaging and backups stay visible. Local table validation must never be labeled as in-game or server verification.

## Evidence on Hand

- Original game item, material, and hero icons extracted to `data/icons/` (530).
- Video tutorial: `docs/tutorial_tbh_save_editor.webm`.
- No user testimonials, usage numbers, or confirmed in-game reload for 1.2.4; do not fabricate them.

## Product Principles

1. Valid by default: the normal path only offers what the game's tables allow; anything else is an explicit opt-in.
2. Nothing is written without review: edits stage in memory, show before/after, and save with a backup.
3. Tell the truth about risk: state limits of local validation plainly, without fear-mongering or false reassurance.
4. Zero setup: a player with Python installed runs one command and everything else is local.
