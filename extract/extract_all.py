"""Refresh portable game data using UnityPy and a matching Il2CppDumper dump.

python -B extract/extract_all.py --dump-path C:\\path\\dump.cs \
    --game-version 1.2.8 --steam-build 25454993

Use --game-dir for another Steam library. UnityPy is an extraction dependency
only; the editor keeps its zero-dependency runtime.
"""
import csv
import hashlib
import importlib.metadata
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.dont_write_bytecode = True
from common import game_data_dir, parser, require_files, write_json
import extract_enums
import extract_localization
import extract_sprites
import extract_tables

GENERATED_ENTRIES = {"tables", "icons", "names.json", "strings.json", "enums.json", "icon_map.json", "version.json"}


def source_files(game_dir, dump_path):
    game_data = game_data_dir(game_dir)
    aa = game_data / "StreamingAssets/aa/StandaloneWindows64"
    return {
        "sharedassets0.assets": game_data / "sharedassets0.assets",
        "sharedassets0.assets.resS": game_data / "sharedassets0.assets.resS",
        extract_localization.SHARED: aa / extract_localization.SHARED,
        extract_localization.BUNDLE: aa / extract_localization.BUNDLE,
        "dump.cs": Path(dump_path).expanduser().resolve(),
    }


def preflight(game_dir, dump_path, output):
    sources = source_files(game_dir, dump_path)
    require_files(sources.values())
    try:
        import UnityPy
    except ImportError as error:
        raise RuntimeError("UnityPy is required for extraction. Install it with: python -m pip install UnityPy") from error
    extract_enums.read_enums(sources["dump.cs"])
    if output.exists():
        if not output.is_dir():
            raise ValueError("Output must be a generated data directory")
        unexpected = {entry.name for entry in output.iterdir()} - GENERATED_ENTRIES
        if unexpected:
            raise ValueError("Output contains non-generated entries: " + ", ".join(sorted(unexpected)))
    if any(path.is_relative_to(output) for path in sources.values()):
        raise ValueError("Output must not contain game assets or the input dump")
    return sources


def check_catalog(data):
    names = json.loads((data / "names.json").read_text(encoding="utf-8"))
    heroes = json.loads((data / "strings.json").read_text(encoding="utf-8"))
    icons = json.loads((data / "icon_map.json").read_text(encoding="utf-8"))
    tables = {}
    for path in sorted((data / "tables").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as file:
            tables[path.stem] = list(csv.DictReader(file))
    for row in tables["HeroInfoData"]:
        if "HeroName_" + row["HeroKey"] not in heroes:
            raise ValueError(f"Missing hero name for {row['HeroKey']}")
    for row in tables["MaterialInfoData"]:
        if row["MATERIALTYPE"] in {"DECORATION", "ENGRAVING", "INSCRIPTION"}:
            if row["ItemKey"] not in names or row["ItemKey"] not in icons:
                raise ValueError(f"Missing name or icon for enchant material {row['ItemKey']}")
    from PIL import Image
    for key, filename in icons.items():
        if filename != key + ".png":
            raise ValueError(f"Invalid generated icon filename: {filename}")
        with Image.open(data / "icons" / filename) as image:
            image.verify()
    return {name: len(rows) for name, rows in tables.items()}


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def run(args):
    output = args.output.expanduser().resolve()
    sources = preflight(args.game_dir, args.dump_path, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the previous data intact until every extractor and catalog check passes.
    with tempfile.TemporaryDirectory(prefix=".tbh-extract-", dir=output.parent) as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir()
        print("== 1/4 CSV tables ==")
        extract_tables.main(args.game_dir, staged)
        print("\n== 2/4 enums from dump ==")
        enum_counts = extract_enums.main(args.dump_path, staged)
        print("\n== 3/4 names (English only) ==")
        localization = extract_localization.main(args.game_dir, staged)
        print("\n== 4/4 icons ==")
        icon_counts = extract_sprites.main(args.game_dir, staged)
        table_rows = check_catalog(staged)
        metadata = {
            "gameVersion": args.game_version,
            "steamBuild": args.steam_build,
            "extractedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": {
                "kind": "installed-game-assets-and-il2cpp-dump",
                "versionEvidence": "Game version and Steam build supplied to extraction command",
                "unityPyVersion": importlib.metadata.version("UnityPy"),
                "sha256": {name: sha256(path) for name, path in sources.items()},
            },
            "counts": {"tableRows": table_rows, "enumMembers": enum_counts, **localization, **icon_counts},
            "verification": {"dataExtraction": True, "catalogChecks": True, "inGameVerified": False},
        }
        write_json(staged / "version.json", metadata)
        # The rollback copy is outside the staging context so cleanup cannot erase
        # it if an OS error prevents both publication and restoration.
        backup = output.with_name(f".tbh-data-backup-{uuid4().hex}")
        if output.exists():
            output.rename(backup)
        try:
            staged.rename(output)
        except OSError:
            if backup.exists():
                try:
                    backup.rename(output)
                except OSError as error:
                    raise RuntimeError(f"Previous data retained for recovery at {backup}") from error
            raise
        if backup.exists():
            if backup.resolve().parent != output.parent:
                raise RuntimeError(f"Unexpected backup path retained at {backup}")
            shutil.rmtree(backup)
    print(f"\nDone. Data extracted for {args.game_version}, Steam build {args.steam_build}, into {output}.")
    print("This verifies extracted assets and catalog coverage, not an in-game save reload.")


def main():
    arguments = parser(__doc__)
    arguments.add_argument("--dump-path", type=Path, required=True, help="Il2CppDumper dump.cs from the same installed build")
    arguments.add_argument("--game-version", required=True, help="Client version reported by the installed game")
    arguments.add_argument("--steam-build", required=True, help="Build ID from the installed Steam app manifest")
    args = arguments.parse_args()
    try:
        run(args)
    except Exception as error:
        arguments.exit(1, f"Extraction failed: {error}\n")


if __name__ == "__main__":
    main()
