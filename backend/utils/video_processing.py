from pathlib import Path
from typing import Sequence

import av

from backend.services.app_settings_service import load_app_settings


VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg"}


def coerce_video_paths(video_paths: Sequence[str | Path]) -> list[Path]:
    return [Path(path) for path in video_paths]


def get_video_duration(path: Path) -> float | None:
    try:
        with av.open(str(path)) as container:
            if container.streams.video:
                stream = container.streams.video[0]
                duration = float(stream.duration * stream.time_base) if stream.duration else None
                if duration is None:
                    duration = float(container.duration) / 1_000_000 if container.duration else None
                return duration
    except Exception:
        return None


def prepare_videos(video_paths: Sequence[str | Path]) -> tuple[list[Path], list[dict], dict[Path, float | None], dict[Path, str | None]]:
    valid_paths: list[Path] = []
    failed_items: list[dict] = []
    path_2_duration: dict[Path, float | None] = {}
    path_2_created_at: dict[Path, str | None] = {}

    for path in coerce_video_paths(video_paths):
        if not path.exists():
            failed_items.append({"path": str(path), "reason": "missing"})
            continue
        if not path.is_file():
            failed_items.append({"path": str(path), "reason": "not_a_file"})
            continue
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            failed_items.append({"path": str(path), "reason": "unsupported_format"})
            continue

        duration = get_video_duration(path)
        if duration is None:
            failed_items.append({"path": str(path), "reason": "unreadable"})
            continue

        valid_paths.append(path)
        path_2_duration[path] = duration
        try:
            path_2_created_at[path] = path.stat().st_mtime.isoformat() if hasattr(path.stat().st_mtime, "isoformat") else str(path.stat().st_mtime)
        except Exception:
            path_2_created_at[path] = None

    return valid_paths, failed_items, path_2_duration, path_2_created_at


def list_video_files(folder_path: str | Path, *, recursive: bool = True) -> list[Path]:
    folder = Path(folder_path)
    skip_hidden_folders = bool(load_app_settings().get("skip_hidden_folders", True))
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in VIDEO_SUFFIXES
        and not (
            skip_hidden_folders
            and any(part.startswith(".") for part in path.relative_to(folder).parts)
        )
    )


def extract_thumbnail_frame(path: str | Path, timestamp_sec: float | None = None) -> bytes | None:
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            if timestamp_sec is not None:
                seek_ts = int(timestamp_sec / float(stream.time_base)) if stream.time_base else 0
                container.seek(seek_ts, stream=stream)
            else:
                mid_duration = (float(stream.duration * stream.time_base) / 2) if stream.duration else 0
                seek_ts = int(mid_duration / float(stream.time_base))
                container.seek(seek_ts, stream=stream)

            for frame in container.decode(video=0):
                img = frame.to_image()
                img_rgb = img.convert("RGB")
                import io
                buf = io.BytesIO()
                img_rgb.save(buf, format="JPEG", quality=85)
                return buf.getvalue()
    except Exception:
        return None
