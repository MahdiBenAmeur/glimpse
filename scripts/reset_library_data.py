from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import (
    FACE_VS_PATH,
    IMAGE_VS_PATH,
    IMPORTED_LIBRARY_ROOT,
    LIBRARY_STATE_PATH,
    MODEL_STATE_PATH,
    PERSON_VS_PATH,
    SAVED_SEARCHES_PATH,
    SQLITE_DB_PATH,
    THUMBNAIL_CACHE_DIR,
)


TARGETS = [
    FACE_VS_PATH,
    PERSON_VS_PATH,
    IMAGE_VS_PATH,
    IMPORTED_LIBRARY_ROOT,
    LIBRARY_STATE_PATH,
    MODEL_STATE_PATH,
    THUMBNAIL_CACHE_DIR,
    SAVED_SEARCHES_PATH,
    SQLITE_DB_PATH,
]


def remove_path(path: Path) -> None:
    if not path.exists():
        print(f"skip  {path}")
        return

    if path.is_dir():
        shutil.rmtree(path)
        print(f"dir   {path}")
        return

    path.unlink()
    print(f"file  {path}")


def main() -> None:
    print("Deleting configured library, index, thumbnail, saved-search, and sqlite data. Model downloads are left untouched.")
    for target in TARGETS:
        remove_path(target)
    print("Done.")


if __name__ == "__main__":
    main()
