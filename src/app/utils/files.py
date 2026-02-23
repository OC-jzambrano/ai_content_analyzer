from __future__ import annotations

import uuid
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_work_dir(root: str | Path, prefix: str = "job") -> Path:
    rid = uuid.uuid4().hex[:12]
    return ensure_dir(Path(root) / f"{prefix}_{rid}")


def safe_ext_from_url(url: str, default: str = ".mp4") -> str:
    # minimal extension detection
    lowered = url.split("?")[0].lower()
    for ext in (".mp4", ".mov", ".mkv", ".webm", ".m4v"):
        if lowered.endswith(ext):
            return ext
    return default