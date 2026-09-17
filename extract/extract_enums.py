"""
Parses the relevant enums from dump.cs (Il2CppDumper) -> data/enums.json.
Needed to translate the numeric codes in the save (StatType:24, ModType:0, RecipeType:3...)
into names, and to cross-reference with the CSV tables (which use the names).
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import DEFAULT_DATA_DIR, parser, require_files, write_json

WANTED = ["StatType", "MODTYPE", "ERecipeType", "EMaterialType", "EGradeType", "GearGroup", "GEARGROUP"]
REQUIRED = {"StatType", "MODTYPE", "ERecipeType", "EMaterialType", "EGradeType"}


def parse_enum(text, name):
    # find "public enum <name> ... {" and read the members up to the closing '}'
    m = re.search(r"public enum %s\b[^\n]*\n\{" % re.escape(name), text)
    if not m:
        return None
    start = m.end()
    end = text.find("}", start)
    body = text[start:end]
    members = {}
    for mm in re.finditer(r"public const %s (\w+) = (-?\d+);" % re.escape(name), body):
        member, val = mm.group(1), int(mm.group(2))
        if member == "value__":
            continue
        members[str(val)] = member
    return members


def read_enums(dump_path):
    require_files([dump_path])
    text = Path(dump_path).read_text(encoding="utf-8")
    out = {}
    for name in WANTED:
        e = parse_enum(text, name)
        if e:
            out[name] = e
            print(f"  {name}: {len(e)} members  (ex: {list(e.items())[:4]})")
    missing = REQUIRED - out.keys()
    if missing:
        raise ValueError("Required enums not found in dump: " + ", ".join(sorted(missing)))
    return out


def main(dump_path, output=DEFAULT_DATA_DIR):
    enums = read_enums(dump_path)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "enums.json", enums)
    print(f"\n-> {out / 'enums.json'}")
    return {name: len(members) for name, members in enums.items()}


if __name__ == "__main__":
    args = parser(__doc__, dump=True).parse_args()
    main(args.dump_path, args.output)
