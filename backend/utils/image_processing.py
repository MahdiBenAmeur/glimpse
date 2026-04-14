from datetime import datetime
from pathlib import Path
from typing import Sequence

from PIL import Image


IMAGE_SUFFIXES = {suffix.lower() for suffix in Image.registered_extensions()}


def coerce_image_paths(image_paths: Sequence[str | Path]) -> list[Path]:
    return [Path(path) for path in image_paths]


def extract_image_created_at(image: Image.Image) -> str | None:
    exif_data = image.getexif()
    if not exif_data:
        return None

    value = exif_data.get(36867) or exif_data.get(36868) or exif_data.get(306)
    if not value:
        return None

    value = str(value)
    try:
        return value.replace(":", "-", 2).replace(" ", "T", 1)
    except Exception:
        return value


def prepare_images(image_paths: Sequence[str | Path]) -> tuple[list[Path], list[dict], dict[Path, str | None]]:
    valid_paths: list[Path] = []
    failed_items: list[dict] = []
    path_2_created_at: dict[Path, str | None] = {}

    for path in coerce_image_paths(image_paths):
        if not path.exists():
            failed_items.append({"path": str(path), "reason": "missing"})
            continue
        if not path.is_file():
            failed_items.append({"path": str(path), "reason": "not_a_file"})
            continue

        try:
            with Image.open(path) as image:
                created_at = extract_image_created_at(image)
                image.load()
        except Exception as exc:
            failed_items.append({"path": str(path), "reason": f"invalid_image: {exc}"})
            continue

        valid_paths.append(path)
        if created_at is None:
            try:
                created_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            except Exception:
                created_at = None
        path_2_created_at[path] = created_at

    return valid_paths, failed_items, path_2_created_at


def list_image_files(folder_path: str | Path, *, recursive: bool = True) -> list[Path]:
    folder = Path(folder_path)
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
