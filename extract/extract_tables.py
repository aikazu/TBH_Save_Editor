"""
Extracts the data tables (CSV TextAssets) from sharedassets0.assets into data/tables/.
Runs once on a machine with the game installed + UnityPy (pip install UnityPy).
The result (data/tables/*.csv) is portable and ships with the app.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import DEFAULT_DATA_DIR, DEFAULT_GAME_DIR, game_data_dir, parser, require_files

# Tables required for items + enchantments (plus a few useful extras).
WANTED = {
    "GearInfoData", "GearTypeInfoData", "GearTypeScaleInfoData", "ItemTypeScaleInfoData",
    "MaterialInfoData", "StatModInfoData", "StatModGroupInfoData", "GradeInfoData",
    "AttributeGroupInfoData", "InventoryInfoData", "SynthesisRecipeInfoData",
    "RuneInfoData", "RuneLevelInfoData", "CurrencyInfoData", "HeroInfoData",
}


def main(game_dir=DEFAULT_GAME_DIR, output=DEFAULT_DATA_DIR):
    import UnityPy

    asset = game_data_dir(game_dir) / "sharedassets0.assets"
    require_files([asset])
    env = UnityPy.load(str(asset))
    tables = {}
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        d = obj.read()
        name = d.m_Name
        if name not in WANTED:
            continue
        raw = d.m_Script
        if isinstance(raw, str):
            raw = raw.encode("utf-8", "surrogateescape")
        tables[name] = bytes(raw)
    missing = WANTED - tables.keys()
    if missing:
        raise ValueError("Required game tables not found: " + ", ".join(sorted(missing)))
    out = Path(output) / "tables"
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in sorted(tables.items()):
        (out / (name + ".csv")).write_bytes(raw)
        print(f"  {name}.csv  ({len(raw)} bytes)")
    print(f"\nExtracted {len(tables)}/{len(WANTED)} tables into {out}")
    return len(tables)


if __name__ == "__main__":
    args = parser(__doc__).parse_args()
    main(args.game_dir, args.output)
