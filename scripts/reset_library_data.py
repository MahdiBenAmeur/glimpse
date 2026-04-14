from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ROOT / "backend" / "data" / "face_vector_store",
    ROOT / "backend" / "data" / "person_vector_store",
    ROOT / "backend" / "data" / "image_vector_store",
    ROOT / "backend" / "data" / "imported_library",
    ROOT / "backend" / "data" / "library_state.json",
    ROOT / "backend" / "data" / "model_state.json",
    ROOT / "saved_searches.json",
    ROOT / "glimpse.db",
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
    print("Deleting index/vector/sqlite data. Model downloads in backend/data/cache_dir are left untouched.")
    for target in TARGETS:
        remove_path(target)
    print("Done.")


if __name__ == "__main__":
    main()
