"""Local persistent storage behind an abstraction (S3/MinIO can replace LocalStorage later).

Security: files are always written under server-generated names (uuid) with a whitelisted extension; callers never
control a filesystem path. `resolve` rejects any relative path escaping the storage root (path traversal)."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings

CATEGORIES = ("original", "processed", "segmented", "model_answers", "exports", "debug")
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".pdf"}


class StorageError(Exception):
    pass


class Storage(ABC):
    @abstractmethod
    def save_bytes(self, category: str, data: bytes, ext: str) -> str: ...
    @abstractmethod
    def resolve(self, rel_path: str) -> Path: ...
    @abstractmethod
    def delete(self, rel_path: str | None) -> None: ...


class LocalStorage(Storage):
    def __init__(self, root: Path | None = None):
        self.root = (root or get_settings().storage_root).resolve()
        for c in CATEGORIES:
            (self.root / c).mkdir(parents=True, exist_ok=True)

    def resolve(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if self.root != p and self.root not in p.parents:
            raise StorageError("Path escapes storage root")
        return p

    def category_dir(self, category: str) -> Path:
        if category not in CATEGORIES:
            raise StorageError(f"Unknown storage category {category}")
        d = self.root / category
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_bytes(self, category: str, data: bytes, ext: str) -> str:
        ext = ext.lower()
        if ext not in ALLOWED_EXT:
            raise StorageError("Extension not allowed")
        name = f"{uuid.uuid4().hex}{ext}"
        (self.category_dir(category) / name).write_bytes(data)
        return f"{category}/{name}"

    def save_array(self, category: str, name_hint: str, img) -> str:
        """Save an OpenCV image as PNG with a deterministic, sanitised name (derived data only, never originals)."""
        import cv2
        safe = "".join(c for c in name_hint if c.isalnum() or c in "-_.")[:120] or uuid.uuid4().hex
        if not safe.lower().endswith(".png"):
            safe += ".png"
        path = self.category_dir(category) / safe
        if not cv2.imwrite(str(path), img):
            raise StorageError(f"Could not write {safe}")
        return f"{category}/{safe}"

    def delete(self, rel_path: str | None) -> None:
        if not rel_path:
            return
        try:
            p = self.resolve(rel_path)
            if p.is_file():
                p.unlink()
        except StorageError:
            pass


_storage: LocalStorage | None = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None or _storage.root != get_settings().storage_root:
        _storage = LocalStorage()
    return _storage
