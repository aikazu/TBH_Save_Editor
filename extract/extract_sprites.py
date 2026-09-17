"""
Extracts item/material icons from sharedassets0.assets -> data/icons/<ItemKey>.png.
Sprite naming convention: 'Item_<ItemKey>' (materials) or '<TYPE>_<GearKey>' (equipment).
ItemInfoData.IconPath resolves items that share a sprite with another item.
"""
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import DEFAULT_DATA_DIR, DEFAULT_GAME_DIR, game_data_dir, parser, require_files, write_json
SPRITE_RE = re.compile(r"^(?:Item|[A-Z]+)_(\d+)$")


def main(game_dir=DEFAULT_GAME_DIR, output=DEFAULT_DATA_DIR):
    import UnityPy

    asset = game_data_dir(game_dir) / "sharedassets0.assets"
    data = Path(output)
    require_files([asset, asset.with_suffix(".assets.resS"), data / "names.json"])
    wanted = set(json.loads((data / "names.json").read_text(encoding="utf-8")))
    env = UnityPy.load(str(asset))
    item_keys = set()
    aliases = {}
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        table = obj.read()
        if table.m_Name != "ItemInfoData":
            continue
        raw = table.m_Script
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        for row in csv.DictReader(io.StringIO(raw.lstrip("\ufeff"))):
            item_keys.add(row["ItemKey"])
            if row["ItemKey"] in wanted and row.get("IconPath"):
                sprite_name = row["IconPath"].rsplit("/", 1)[-1]
                aliases.setdefault(sprite_name, set()).add(row["ItemKey"])
    if not item_keys:
        raise ValueError("ItemInfoData is required to resolve shared item icons")
    icons = data / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    icon_map = {}
    done = 0
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        sp = obj.read()
        m = SPRITE_RE.match(sp.m_Name)
        keys = set(aliases.get(sp.m_Name, ()))
        if m and m.group(1) in wanted:
            keys.add(m.group(1))
        keys -= icon_map.keys()
        if not keys:
            continue
        img = sp.image  # PIL image cropped from the atlas
        for key in sorted(keys):
            img.save(icons / (key + ".png"))
            icon_map[key] = key + ".png"
            done += 1
            if done % 100 == 0:
                print(f"  ...{done} icons")
    if not icon_map:
        raise ValueError("No item icons found in game assets")
    write_json(data / "icon_map.json", icon_map)
    missing = sorted(wanted - icon_map.keys())
    missing_defined = sorted(set(missing) & item_keys)
    if missing_defined:
        raise ValueError("Missing icons for defined items: " + ", ".join(missing_defined))
    print(f"\nExtracted {done} icons -> {icons}; missing named item icons: {len(missing)}")
    return {"icons": done, "missingIconKeys": missing,
            "localizedKeysWithoutItemDefinitionOrIcon": missing}


if __name__ == "__main__":
    args = parser(__doc__).parse_args()
    main(args.game_dir, args.output)
