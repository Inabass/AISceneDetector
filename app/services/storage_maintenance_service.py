import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.services.storage_service import StorageService


@dataclass(frozen=True)
class StorageArea:
    name: str
    path: Path
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class CleanupTarget:
    name: str
    paths: list[Path]
    total_bytes: int


class StorageMaintenanceService:
    CLEANUP_TARGETS = {"temp", "previews", "thumbnails"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = StorageService(settings)

    def usage(self) -> dict[str, object]:
        areas = [
            self._area("uploads", self.settings.upload_dir),
            self._area("features", self.settings.features_dir),
            self._area("models", self.settings.models_dir),
            self._area("outputs", self.settings.outputs_dir),
            self._area("previews", self.settings.previews_dir),
            self._area("thumbnails", self.settings.thumbnails_dir),
            self._area("temp", self.settings.temp_dir),
            self._area("logs", self.settings.logs_dir),
        ]
        return {
            "storage_root": str(self.settings.storage_root),
            "total_bytes": sum(area.total_bytes for area in areas),
            "areas": [
                {
                    "name": area.name,
                    "path": self.storage.relative_path(area.path),
                    "file_count": area.file_count,
                    "total_bytes": area.total_bytes,
                }
                for area in areas
            ],
        }

    def cleanup(
        self,
        dry_run: bool = True,
        targets: list[str] | None = None,
        older_than_hours: int = 24,
    ) -> dict[str, object]:
        target_names = set(targets or ["temp", "previews", "thumbnails"])
        unknown = sorted(target_names - self.CLEANUP_TARGETS)
        if unknown:
            raise ValidationAppError(
                message="Unknown cleanup target.",
                detail={"targets": unknown, "allowed": sorted(self.CLEANUP_TARGETS)},
            )
        if older_than_hours < 0:
            raise ValidationAppError(
                message="older_than_hours must not be negative.",
                detail={"older_than_hours": older_than_hours},
            )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        cleanup_targets = [
            self._cleanup_target(name, cutoff) for name in sorted(target_names)
        ]
        deleted_file_count = 0
        deleted_bytes = 0
        skipped_file_count = 0
        errors: list[str] = []
        if not dry_run:
            for target in cleanup_targets:
                for path in target.paths:
                    try:
                        if path.is_file():
                            size = path.stat().st_size
                            path.unlink()
                            deleted_file_count += 1
                            deleted_bytes += size
                        elif path.is_dir():
                            size, count = self._dir_size(path)
                            shutil.rmtree(path)
                            deleted_file_count += count
                            deleted_bytes += size
                        else:
                            skipped_file_count += 1
                    except Exception as exc:
                        errors.append(f"{path}: {exc}")
            self._remove_empty_dirs()
        return {
            "dry_run": dry_run,
            "targets": [
                {
                    "name": target.name,
                    "file_count": len(target.paths),
                    "total_bytes": target.total_bytes,
                }
                for target in cleanup_targets
            ],
            "deleted_file_count": deleted_file_count,
            "deleted_bytes": deleted_bytes,
            "skipped_file_count": skipped_file_count,
            "errors": errors,
        }

    def _area(self, name: str, path: Path) -> StorageArea:
        safe_path = self.storage.ensure_under_root(path)
        total_bytes, file_count = self._dir_size(safe_path)
        return StorageArea(
            name=name,
            path=safe_path,
            file_count=file_count,
            total_bytes=total_bytes,
        )

    def _cleanup_target(self, name: str, cutoff: datetime) -> CleanupTarget:
        root = {
            "temp": self.settings.temp_dir,
            "previews": self.settings.previews_dir,
            "thumbnails": self.settings.thumbnails_dir,
        }[name]
        safe_root = self.storage.ensure_under_root(root)
        paths = [
            path
            for path in self._iter_files(safe_root)
            if self._modified_at(path) <= cutoff
        ]
        total_bytes = sum(path.stat().st_size for path in paths if path.exists())
        return CleanupTarget(name=name, paths=paths, total_bytes=total_bytes)

    def _dir_size(self, path: Path) -> tuple[int, int]:
        if not path.exists():
            return 0, 0
        total = 0
        count = 0
        for item in self._iter_files(path):
            try:
                total += item.stat().st_size
                count += 1
            except OSError:
                continue
        return total, count

    def _iter_files(self, path: Path) -> list[Path]:
        if not path.exists():
            return []
        if path.is_file():
            return [self.storage.ensure_under_root(path)]
        return [
            self.storage.ensure_under_root(item)
            for item in path.rglob("*")
            if item.is_file()
        ]

    def _modified_at(self, path: Path) -> datetime:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    def _remove_empty_dirs(self) -> None:
        for root in (
            self.settings.temp_dir,
            self.settings.previews_dir,
            self.settings.thumbnails_dir,
        ):
            safe_root = self.storage.ensure_under_root(root)
            for path in sorted(
                [item for item in safe_root.rglob("*") if item.is_dir()],
                key=lambda item: len(item.parts),
                reverse=True,
            ):
                try:
                    path.rmdir()
                except OSError:
                    pass
