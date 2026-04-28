"""Pre-build helper: download the Ludusavi manifest and build the search
index so they can be bundled into the PyInstaller exe.

Skips work that is already done. Run from the project root before pyinstaller.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from savesync import (
    MANIFEST_FILE,
    MANIFEST_INDEX,
    download_manifest,
    build_manifest_index,
)


def main() -> int:
    if not MANIFEST_FILE.exists():
        print("  Downloading Ludusavi manifest...")
        if not download_manifest(silent=False):
            print("  ERROR: manifest download failed.")
            return 1
    else:
        print(f"  Manifest already present: {MANIFEST_FILE.name}")

    if not MANIFEST_INDEX.exists():
        print("  Building search index...")
        if not build_manifest_index(silent=False):
            print("  ERROR: index build failed.")
            return 1
    else:
        print(f"  Index already present: {MANIFEST_INDEX.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
