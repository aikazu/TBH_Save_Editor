"""Paths and command-line options shared by the one-shot extractors."""
import argparse
import json
import os
from pathlib import Path

DEFAULT_GAME_DIR = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam/steamapps/common/TaskbarHero"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def game_data_dir(path):
    path = Path(path).expanduser().resolve()
    return path if path.name.lower() == "taskbarhero_data" else path / "TaskBarHero_Data"


def require_files(paths):
    missing = [str(path) for path in paths if not Path(path).is_file()]
    if missing:
        raise FileNotFoundError("Missing extraction input(s):\n  " + "\n  ".join(missing))


def parser(description, *, dump=False):
    result = argparse.ArgumentParser(description=description)
    if dump:
        result.add_argument("--dump-path", type=Path, required=True, help="Il2CppDumper dump.cs from the installed game build")
    else:
        result.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR, help="TaskbarHero install directory or TaskBarHero_Data directory")
    result.add_argument("--output", type=Path, default=DEFAULT_DATA_DIR, help="Generated data directory (default: repository data/)")
    return result


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
