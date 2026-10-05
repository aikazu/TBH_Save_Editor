---
name: TBH Save Editor
description: Enchantment workbench for Taskbar Hero saves, a dark local tool lit by one amber accent.
colors:
  amber: "#f0ba58"
  amber-bright: "#ffd28a"
  amber-ink: "#171a13"
  amber-wash: "#2e2a1e"
  charcoal-canvas: "#151714"
  bench-surface: "#1d201b"
  bench-raised: "#252920"
  bench-pressed: "#353b2d"
  work-pane: "#191c17"
  hairline: "#3b4035"
  control-edge: "#777e6e"
  parchment-text: "#f2f3eb"
  sage-muted: "#b8bdb0"
  placeholder: "#a4ab9a"
  success-sage: "#b4dca0"
  danger-coral: "#ffb0a5"
  danger-wash: "#3a2522"
  grade-legendary: "#efc377"
  grade-immortal: "#d8b8ef"
  grade-arcana: "#efb7c9"
  grade-beyond: "#bdc9fb"
  grade-celestial: "#abd6e8"
  grade-divine: "#f0d797"
  grade-uncommon: "#b4dca0"
typography:
  display:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "clamp(1.8rem, 3vw, 2.7rem)"
    fontWeight: 600
    lineHeight: 1.15
  headline:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "clamp(1.4rem, 2vw, 1.9rem)"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
  value:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 600
    lineHeight: 1.2
    fontFeature: "tnum"
rounded:
  slot: "4px"
  control: "5px"
  editor: "6px"
  artwork: "8px"
  dialog: "10px"
spacing:
  xs: "0.5rem"
  sm: "0.75rem"
  md: "1rem"
  lg: "1.25rem"
  xl: "1.5rem"
  2xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1rem"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.amber-bright}"
    textColor: "{colors.amber-ink}"
  button-primary-disabled:
    backgroundColor: "transparent"
    textColor: "{colors.sage-muted}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1rem"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.bench-raised}"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.danger-coral}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1rem"
    height: "44px"
  button-danger-hover:
    backgroundColor: "{colors.danger-wash}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.sage-muted}"
    rounded: "{rounded.control}"
  input:
    backgroundColor: "{colors.charcoal-canvas}"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.control}"
    padding: "0.65rem 0.8rem"
    height: "44px"
  selection-tile:
    backgroundColor: "{colors.bench-surface}"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.control}"
    padding: "0.85rem"
  selection-tile-selected:
    backgroundColor: "{colors.amber-wash}"
    textColor: "{colors.parchment-text}"
  slot-editor:
    backgroundColor: "{colors.bench-surface}"
    rounded: "{rounded.editor}"
    padding: "1rem"
  dialog:
    backgroundColor: "{colors.bench-surface}"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.dialog}"
    padding: "1.75rem"
---

# Design System: TBH Save Editor

## Overview

**Creative North Star: "The Enchanter's Bench"**

A craftsperson's bench at night. The surfaces are warm charcoal, quiet and matte, and a single amber lamp falls on whatever the player is working on: the selected hero, the selected item, the next action. The game's own item art supplies the color; the interface around it stays low and steady so a long session of comparing rolls never tires the eye.

The layout reads left to right as the job itself: heroes, then equipment, then the enchant slots of one item. Density is compact but never cramped; every control keeps a 44px hit target. Motion is almost absent: one short color transition confirms a selection or press, and reduced-motion preferences remove it.

The bench is honest. Validation problems, custom values, and the save path are shown plainly in the working surface rather than hidden behind reassurance, and nothing is written to disk without a review step.

**Key Characteristics:**
- Warm charcoal tonal layers with 1px hairlines; no decorative depth.
- One amber accent marks selection and the next meaningful action.
- Original game icons are the only illustration.
- Rarity colors encode the game's actual grades, never decoration.
- Windows-native type (Bahnschrift headings, Segoe UI body) with no network font requests.

## Colors

A warm, low-chroma charcoal bench with one amber lamp and a set of pale grade tints borrowed from the game.

### Primary
- **Lamp Amber**: selection borders, the selected hero's name, staged values, the primary action, caret, and slider fill. Text on amber uses **Amber Ink**. Focus rings are Parchment Text, never amber, so focus and selection stay distinguishable.
- **Bright Amber**: hover state of the primary action only.
- **Amber Wash**: fill behind a selected hero or item tile, so selection reads even without the border.

### Neutral
- **Charcoal Canvas**: page background and input wells.
- **Bench Surface**: save strip, tiles, the slot editor, and dialogs.
- **Bench Raised**: hover fill for buttons and the backing plate behind item artwork.
- **Work Pane**: the enchantment pane, a half step lighter than the canvas to mark it as the working surface.
- **Hairline**: pane dividers, slot rules, and idle tile borders.
- **Control Edge**: borders of buttons and inputs, where the edge must meet non-text contrast.
- **Parchment Text**: primary text.
- **Sage Muted**: secondary text, counts, captions, and quiet buttons.

### Semantic
- **Success Sage**: success notices (save and discard results).
- **Danger Coral**: error notices, invalid fields, slot validation problems, and the outline of risky confirmations. **Danger Wash** is their hover fill.
- **Grade tints** (Legendary, Immortal, Arcana, Beyond, Celestial/Rare, Divine/Cosmic, Uncommon): the item's rarity label only. Common gear uses Sage Muted.

### Named Rules
**The One Lamp Rule.** Amber is the only accent. If two amber things compete on screen, one of them is not the current selection or the next action and should lose its amber.

**The Grade Truth Rule.** A grade tint appears only on a grade label and only for the grade the game assigns. Never reuse a grade tint for status, emphasis, or decoration.

## Typography

**Display Font:** Bahnschrift (with Segoe UI, sans-serif)
**Body Font:** Segoe UI (with sans-serif)

**Character:** Bahnschrift's condensed, engineered letterforms give headings a workshop-label feel; Segoe UI keeps controls, numbers, and long Windows paths familiar. Both ship with Windows, so the tool never requests a font from the network.

### Hierarchy
- **Display**: the empty-state welcome line only.
- **Headline**: the selected item's name and the review dialog title (dialog fixed at 1.8rem).
- **Title**: pane headings and the app title (app title scales from 1.1rem to 1.55rem).
- **Body**: default text, item names, and control text.
- **Label**: form labels, notices in the save strip, review values, and slot errors.
- **Caption**: counts, step numbers, slot details, grade and group metadata.
- **Value**: the enchant value at the right of each filled slot, set in tabular figures so columns of numbers align.

### Named Rules
**The Tabular Numbers Rule.** Any number a player compares (enchant values, counts) uses tabular figures.

## Layout

Three working panes on wide screens (heroes rail 190–220px, equipment list, then a wider enchantment pane), separated by 1px hairlines rather than gutters. Breakpoints:

- **Below 650px:** a single column. Heroes become a two-column grid; equipment becomes a two-column tile grid with the icon above the name; choosing an item scrolls to the enchantment pane.
- **650–1099px:** heroes span the top in three columns; equipment and enchantments sit side by side.
- **1100px and up:** the three-pane bench with the hero rail and its short rail note.
- **1600px and up:** the rail and list widen, and the enchantment pane gains generous side padding.

Below 1100px, once edits are staged, the save status and "Review & save" button pin to the bottom of the viewport so the action stays reachable on the stacked page.

Each enchant slot is a two-column grid: summary (icon, stat, detail, value) on the left and Edit/Clear on the right at every width, with errors, the staged marker, and the inline editor spanning below. Spacing steps are 0.5, 0.75, 1, 1.25, 1.5, and 2rem; groups sit tight inside and separate with the larger steps.

## Elevation & Depth

Flat by default, with depth from tonal layering: canvas, then surface, then raised, with 1px hairlines defining edges. Shadows appear only on things that float above the bench.

### Shadow Vocabulary
- **Dialog lift** (`box-shadow: 0 20px 80px #0008`, over a `#060805c9` backdrop): the review and confirmation dialog.
- **Pinned save bar** (`box-shadow: 0 -8px 24px #0006`): the bottom save bar on stacked layouts.

### Named Rules
**The Flat Bench Rule.** Tiles, panes, slots, and the editor never cast shadows. If something needs to feel separate, give it a surface step or a hairline.

## Shapes

Small, consistent corners. Slot markers use 4px; buttons, inputs, and tiles 5px; the inline editor 6px; the selected item's artwork plate 8px; dialogs 10px. Borders are 1px throughout. An empty slot's marker is dashed, a locked slot's is solid hairline, and a filled slot shows its material icon instead.

## Components

### Buttons
Precise and quiet.
- **Shape:** gently squared (5px), 44px minimum height.
- **Primary:** Lamp Amber fill with Amber Ink bold text; one per context ("Review & save", "Apply enchant", "Save with backup").
- **Primary disabled:** transparent with a hairline border and muted text, never a dimmed amber.
- **Secondary:** transparent with a Control Edge border; hover fills with Bench Raised, active with Bench Pressed.
- **Quiet:** borderless, muted text that brightens on hover; used for Clear, Cancel, and Close.
- **Danger:** transparent with a Danger Coral border and text, for confirmations that discard staged work, clear an enchant, or enable custom values. The safe choice beside it is never outranked by an amber button.
- **Focus:** a 3px Parchment Text outline offset by 3px, on every focusable element.

### Selection tiles (heroes and equipment)
- **Idle:** Bench Surface fill with a hairline border.
- **Selected:** Amber Wash fill and an amber border, with `aria-pressed="true"`; the hero name turns amber.
- **Content:** item icon (48px), name, then a caption row of grade tint and gear group. An "Edited" marker in amber appears when the item has staged changes.
- **Keyboard:** each list is one Tab stop; arrow keys, Home, and End move between tiles.

### Inputs / Fields
- **Style:** Charcoal Canvas well, Control Edge border, 5px corners, 44px height, labels above in Sage Muted.
- **Invalid:** border turns Danger Coral after user interaction.
- **Disabled:** dimmed to half opacity with a not-allowed cursor.
- **Checkbox and range:** native controls tinted with `accent-color` amber.

### Enchant slot (signature)
The working row of the bench: a 36px material icon or slot marker, stat name and "material · tier" detail, the value in Bahnschrift tabular figures, and Revert/Edit/Clear on the right. A staged slot's value turns amber with a "Staged change" marker and gains Revert. Validation problems show in coral in display units with the tier's range, keep the raw check under a "Technical detail" disclosure, and offer a "Set to <max>" fix. The selected item's header offers "Max N rolls" when filled enchants sit below their tier maximum.

### Inline slot editor
Opens beneath its slot on a Bench Surface panel with a Control Edge border. Stat and tier selects, then value with slider (hidden until a stat is chosen, named after the stat), number field, and Max. A mode label states "Game-table values" or, in amber, "Custom values". The range hint lists min, max, and step in display units; invalid input is reported in the editor's alert line, not a browser tooltip. Escape or Cancel closes it and returns focus to the trigger.

### Review dialog
A native `<dialog>` on Bench Surface with a lifted shadow. It lists each staged slot with labeled Before and After values (After in amber), a hairline-bordered "Checked on your device only" note about server-side validation, then the exact path that will be written in a canvas-colored well. Actions: "Keep editing" (secondary, receives initial focus) and "Save with backup" (primary); Escape also cancels.

### Notices
Full-width bordered strips under the save strip, with role="status", used only for results that need to persist: save (with the backup path), discard, and errors. Routine feedback such as loading or staging lives in the status text beside "Review & save" instead. Success uses Success Sage text; errors use Danger Coral text and border; the version mismatch warning uses amber text.

## Do's and Don'ts

### Do:
- **Do** reserve Lamp Amber for the current selection, staged values, and the one primary action in view.
- **Do** keep every control at least 44px tall with a visible 3px parchment focus ring.
- **Do** use the game's extracted icons for items and materials, sized 36px in slots, 48px in tiles, and 88px for the selected item.
- **Do** show table version and save version separately, and keep the full save path visible in the footer and review dialog.
- **Do** use the native dialog for confirmations and keep custom values behind the Advanced editing disclosure with a confirmation.

### Don't:
- **Don't** use browser `confirm()` or `alert()`; confirmations go through the review dialog.
- **Don't** add shadows to tiles, panes, slots, or the editor.
- **Don't** load fonts, scripts, or images from the network; everything ships with the app.
- **Don't** label local table validation as in-game or server verification, or describe an edit as safe.
- **Don't** use grade tints, success, or danger colors as decoration.
