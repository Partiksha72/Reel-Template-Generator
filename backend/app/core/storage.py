"""Storage abstraction.

MVP: local filesystem. The `Storage` interface is intentionally small so an
S3/Azure Blob implementation can be dropped in later without touching services.
"""
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .config import get_settings


class Storage(ABC):
    @abstractmethod
    def project_dir(self, project_id: str, create: bool = True) -> Path: ...

    @abstractmethod
    def save_upload(self, project_id: str, filename: str, tmp_path: Path) -> Path: ...

    @abstractmethod
    def abs_path(self, project_id: str, *relparts: str) -> Path: ...

    @abstractmethod
    def delete_project(self, project_id: str) -> None: ...


class LocalStorage(Storage):
    def __init__(self) -> None:
        self.root = get_settings().data_path

    def project_dir(self, project_id: str, create: bool = True) -> Path:
        d = self.root / "projects" / project_id
        if create:
            (d / "uploads").mkdir(parents=True, exist_ok=True)
            (d / "renders").mkdir(parents=True, exist_ok=True)
            (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    def save_upload(self, project_id: str, filename: str, tmp_path: Path) -> Path:
        dest = self.project_dir(project_id) / "uploads" / filename
        shutil.move(str(tmp_path), str(dest))
        return dest

    def abs_path(self, project_id: str, *relparts: str) -> Path:
        return self.project_dir(project_id) / Path(*relparts)

    def delete_project(self, project_id: str) -> None:
        d = self.root / "projects" / project_id
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


_storage: Optional[Storage] = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        backend = get_settings().storage_backend
        if backend == "local":
            _storage = LocalStorage()
        else:
            raise NotImplementedError(f"Storage backend '{backend}' not implemented yet")
    return _storage


def new_id() -> str:
    return uuid.uuid4().hex[:12]
