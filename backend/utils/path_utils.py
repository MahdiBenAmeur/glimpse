from __future__ import annotations

import os
from pathlib import Path


def canonicalize_path(path: str | Path) -> str:
    candidate = Path(path).expanduser()
    try:
        candidate = candidate.resolve(strict=False)
    except Exception:
        candidate = candidate.absolute()
    return str(candidate)


def canonicalize_path_key(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(canonicalize_path(path)))
