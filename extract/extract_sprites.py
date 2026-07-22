"""
Extracts item/material icons from sharedassets0.assets -> data/icons/<ItemKey>.png.
Sprite naming convention: 'Item_<ItemKey>' (materials) or '<TYPE>_<GearKey>' (equipment).
Confirmed coverage: 1 sprite per ItemKey, no ambiguity.
"""
import json
import os
import re
import UnityPy

GAME_DATA = r"C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero\TaskBarHero_Data"
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ICONS = os.path.join(DATA, "icons")
SPRITE_RE = re.compile(r"^(?:Item|[A-Z]+)_(\d+)$")


def main():
    os.makedirs(ICONS, exist_ok=True)
    wanted = set(json.load(open(os.path.join(DATA, "names_en.json"), encoding="utf-8")).keys())
    env = UnityPy.load(os.path.join(GAME_DATA, "sharedassets0.assets"))
    icon_map = {}
    done = 0
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        try:
            sp = obj.read()
        except Exception:
            continue
        m = SPRITE_RE.match(sp.m_Name)
        if not m:
            continue
        key = m.group(1)
        if key not in wanted or key in icon_map:
            continue
        try:
            img = sp.image  # PIL image cropped from the atlas
            out = os.path.join(ICONS, key + ".png")
            img.save(out)
            icon_map[key] = key + ".png"
            done += 1
            if done % 100 == 0:
                print(f"  ...{done} icons")
        except Exception as e:
            print(f"  failed {key}: {e}")
    with open(os.path.join(DATA, "icon_map.json"), "w", encoding="utf-8") as fh:
        json.dump(icon_map, fh, ensure_ascii=False, indent=2)
    print(f"\nExtracted {done} icons -> {ICONS}")


if __name__ == "__main__":
    main()
