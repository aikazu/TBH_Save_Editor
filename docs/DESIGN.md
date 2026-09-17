# Enchantment workbench

Direction approved by the user: dark workbench, amber accent, original game icons, compact controls. This is a local Windows utility for choosing a hero's equipped item and adjusting its enchantments.

Energy 2 / Rhythm 2 / Motion 1. The selected item is the focal point. Persistent hero and equipment selection gives context; enchant rows are the working surface. Amber identifies the selection and the next meaningful action. Rarity colors encode the game's actual grades rather than decorative categories.

| Role | Choice | Purpose |
|---|---|---|
| Canvas | Warm charcoal `#151714` | Keeps luminous game item art readable during long sessions |
| Surface | `#1d201b`, `#252920` | Separates equipment from active editing without floating cards |
| Primary text | `#f2f3eb` | Clear reading against the dark workbench |
| Secondary text | `#b8bdb0` | Explanatory labels with sufficient contrast |
| Action | Amber `#f0ba58` on `#171a13` | Selection, focus, and the primary action |
| Heading | Bahnschrift, fallback Segoe UI | Compact workshop lettering available on Windows, no network font request |
| Body | Segoe UI, sans-serif | Familiar, readable Windows controls and numbers |
| Item artwork | Generated `data/icons` from the installed game | Recognizable equipment and material identity |

Mobile uses a wrapping hero selector and a stacked equipment/editor flow; medium widths use two columns; wide screens add the hero rail. Controls have at least 44px hit targets, associated labels, and visible keyboard focus. One short transition indicates selection or feedback; reduced-motion preferences remove it.

Keep the complete save path accessible. Show table and save versions separately. Stage edits in memory, review the before/after values, then write with a backup. Confirmation uses an accessible HTML dialog; avoid browser JavaScript confirmations. Custom values remain an explicit advanced mode with visible validation feedback. Do not label local table validation as in-game or server verification.
