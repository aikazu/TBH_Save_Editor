"""
Orchestrates all game data extraction (runs once on a machine with Taskbar Hero
installed + UnityPy). Generates data/ with tables, names, enums and icons -- after
that the app (server.py + web/ + data/) is portable and runs without the game or
dependencies.

Usage:  python extract/extract_all.py
Requires:  pip install UnityPy   (only for extraction; the app itself does not)
"""
import extract_tables
import extract_enums
import extract_localization
import extract_sprites

if __name__ == "__main__":
    print("== 1/4 CSV tables ==");                extract_tables.main()
    print("\n== 2/4 enums from dump ==");          extract_enums.main()
    print("\n== 3/4 names (English only) ==");      extract_localization.main()
    print("\n== 4/4 icons ==");                    extract_sprites.main()
    print("\nDone. Data in saveEditor/data/. Run 'python server.py'.")
