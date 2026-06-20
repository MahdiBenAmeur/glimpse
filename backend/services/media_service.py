from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import av
from PIL import Image

from backend.config import THUMBNAIL_CACHE_DIR
from backend.utils.path_utils import canonicalize_path
from backend.utils.video_processing import extract_thumbnail_frame


DEFAULT_THUMBNAIL_SIZE = 512


def get_image_dimensions(image_path: str | Path) -> tuple[int | None, int | None]:
    """
    Returns the width and height of an image.
    """
    try:
        with Image.open(image_path) as image:
            return image.width, image.height
    except Exception:
        return None, None


def get_image_taken_at(image_path: str | Path, preferred: str | None = None) -> str | None:
    """
    Extracts the creation date from EXIF data or file modification time.
    """
    if preferred is not None and str(preferred).strip():
        return str(preferred)

    source_path = Path(canonicalize_path(image_path))
    if not source_path.exists() or not source_path.is_file():
        return None

    try:
        with Image.open(source_path) as image:
            exif_data = image.getexif()
            if exif_data:
                value = exif_data.get(36867) or exif_data.get(36868) or exif_data.get(306)
                if value:
                    text = str(value)
                    return text.replace(":", "-", 2).replace(" ", "T", 1)
    except Exception:
        pass

    try:
        return datetime.fromtimestamp(source_path.stat().st_mtime).isoformat()
    except Exception:
        return None


def ensure_thumbnail(image_path: str | Path, *, size: int = DEFAULT_THUMBNAIL_SIZE) -> Path:
    """
    Generates or retrieves a cached thumbnail for an image.
    """
    source_path = Path(canonicalize_path(image_path))
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Image file is missing: {source_path}")

    THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stats = source_path.stat()
    cache_key = hashlib.sha1(f"{source_path}|{stats.st_mtime_ns}|{size}".encode("utf-8")).hexdigest()
    thumbnail_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.jpg"
    if thumbnail_path.exists():
        return thumbnail_path

    with Image.open(source_path) as image:
        image = image.convert("RGB")
        image.thumbnail((size, size))
        image.save(thumbnail_path, format="JPEG", quality=85, optimize=True)

    return thumbnail_path


def get_video_dimensions(video_path: str | Path) -> tuple[int | None, int | None]:
    """Returns the width and height of a video's first stream."""
    try:
        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            return int(stream.width), int(stream.height)
    except Exception:
        return None, None


def ensure_video_thumbnail(video_path: str | Path, *, size: int = DEFAULT_THUMBNAIL_SIZE) -> Path:
    """Generates or retrieves a cached thumbnail for a video (mid-point frame)."""
    source_path = Path(canonicalize_path(video_path))
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Video file is missing: {source_path}")

    THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stats = source_path.stat()
    cache_key = hashlib.sha1(f"{source_path}|{stats.st_mtime_ns}|{size}|video".encode("utf-8")).hexdigest()
    thumbnail_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.jpg"
    if thumbnail_path.exists():
        return thumbnail_path

    frame_bytes = extract_thumbnail_frame(source_path)
    if frame_bytes is None:
        raise ValueError(f"Could not extract thumbnail frame from video: {source_path}")

    import io
    from PIL import Image as PILImage
    image = PILImage.open(io.BytesIO(frame_bytes))
    image.thumbnail((size, size))
    image.save(thumbnail_path, format="JPEG", quality=85, optimize=True)
    return thumbnail_path


def clear_thumbnail_cache() -> None:
    """
    Deletes all cached thumbnail files.
    """
    if THUMBNAIL_CACHE_DIR.exists():
        shutil.rmtree(THUMBNAIL_CACHE_DIR)
    THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
