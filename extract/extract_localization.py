"""
Extracts English text from Unity Localization bundles -> data/.
Only the keys the app actually consumes are written (saves ~110KB of dead weight).

  - ItemTable  -> data/names.json     (ItemKey -> item/material display name)
  - StringTable-> data/strings.json   (only HeroName_<key> -> hero display name)
Chain: SharedTableData (m_Id -> m_Key) + <Table>_en (m_Id -> m_Localized).
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import DEFAULT_DATA_DIR, DEFAULT_GAME_DIR, game_data_dir, parser, require_files, write_json

SHARED = "localization-assets-shared_assets_all.bundle"
BUNDLE = "localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle"
ITEMNAME_RE = re.compile(r"^ItemName_(\d+)$")
HERONAME_RE = re.compile(r"^HeroName_(\d+)$")


def shared_id_map(collection, aa):
    """m_Id -> m_Key of the collection (ItemTable / StringTable)."""
    import UnityPy

    env = UnityPy.load(str(aa / SHARED))
    out = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if tree.get("m_TableCollectionName") != collection:
            continue
        for e in tree.get("m_Entries", []):
            out[e["m_Id"]] = e.get("m_Key", "")
    return out


def locale_table(table_prefix, id_to_key, key_filter, aa):
    import UnityPy

    env = UnityPy.load(str(aa / BUNDLE))
    out = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if not str(tree.get("m_Name", "")).startswith(table_prefix):
            continue
        for e in tree.get("m_TableData", []):
            key = id_to_key.get(e.get("m_Id"))
            loc = e.get("m_Localized")
            if not (key and loc):
                continue
            value = key_filter(key)
            if value is not None:
                out[value] = loc
    return out


def _to_itemkey(key):
    m = ITEMNAME_RE.match(key)
    return str(int(m.group(1))) if m else None


def _to_herokey(key):
    m = HERONAME_RE.match(key)
    return key if m else None  # keep full "HeroName_<n>" key


def main(game_dir=DEFAULT_GAME_DIR, output=DEFAULT_DATA_DIR):
    aa = game_data_dir(game_dir) / "StreamingAssets/aa/StandaloneWindows64"
    require_files([aa / SHARED, aa / BUNDLE])
    items_ids = shared_id_map("ItemTable", aa)
    strings_ids = shared_id_map("StringTable", aa)
    print(f"SharedTableData: ItemTable={len(items_ids)} StringTable={len(strings_ids)}")

    names = locale_table("ItemTable_", items_ids, _to_itemkey, aa)
    hero_names = locale_table("StringTable_", strings_ids, _to_herokey, aa)
    if not names or not hero_names:
        raise ValueError("English item or hero localization is empty")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "names.json", names)
    print(f"  names.json: {len(names)} item names")

    write_json(out / "strings.json", hero_names)
    print(f"  strings.json: {len(hero_names)} hero names  (ex: {hero_names.get('HeroName_101')!r})")
    return {"itemNames": len(names), "heroNames": len(hero_names)}


if __name__ == "__main__":
    args = parser(__doc__).parse_args()
    main(args.game_dir, args.output)
