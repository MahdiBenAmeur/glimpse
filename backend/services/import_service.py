from __future__ import annotations

import shutil
import time
from pathlib import Path
from tkinter import Tk, filedialog

from backend.config import IMPORTED_LIBRARY_ROOT
from backend.utils.image_processing import IMAGE_SUFFIXES


def _open_dialog(callback):
    """
    Wraps a tkinter dialog to ensure it is focused and cleaned up.
    """
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return callback()
    finally:
        root.destroy()


def pick_folder_path() -> str | None:
    """
    Opens a folder picker dialog.
    """
    try:
        selected = _open_dialog(lambda: filedialog.askdirectory(mustexist=True))
    except Exception as exc:  # pragma: no cover - depends on desktop environment
        raise RuntimeError(f"Could not open folder picker: {exc}") from exc
    return selected or None


def pick_image_paths() -> list[str]:
    """
    Opens a file picker dialog for images.
    """
    file_types = [
        ("Image files", " ".join(f"*{suffix}" for suffix in sorted(IMAGE_SUFFIXES) if suffix)),
        ("All files", "*.*"),
    ]
    try:
        selected = _open_dialog(
            lambda: filedialog.askopenfilenames(
                title="Choose images",
                filetypes=file_types,
            )
        )
    except Exception as exc:  # pragma: no cover - depends on desktop environment
        raise RuntimeError(f"Could not open image picker: {exc}") from exc
    return [str(Path(path)) for path in selected if path]


def import_image_files(image_paths: list[str | Path]) -> dict[str, object]:
    """
    Copies selected images into the application's library.
    """
    normalized_paths = [Path(path).expanduser().resolve() for path in image_paths]
    existing_files = [path for path in normalized_paths if path.exists() and path.is_file()]
    if not existing_files:
        raise ValueError("No image files were selected")

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    target_dir = IMPORTED_LIBRARY_ROOT / f"import-{timestamp}"
    target_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for source_path in existing_files:
        target_path = target_dir / source_path.name
        duplicate_index = 1
        while target_path.exists():
            target_path = target_dir / f"{source_path.stem}-{duplicate_index}{source_path.suffix}"
            duplicate_index += 1
        shutil.copy2(source_path, target_path)
        copied_files.append(str(target_path))

    return {
        "folder_path": str(target_dir.resolve()),
        "imported_count": len(copied_files),
        "files": copied_files,
    }
