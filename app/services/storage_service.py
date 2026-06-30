import re
import uuid
from pathlib import Path

from app.core.config import Settings
from app.core.errors import ValidationAppError

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.ensure_data_directories()

    def safe_filename(self, filename: str) -> str:
        name = Path(filename).name
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        name = name.strip().rstrip(". ")
        if not name:
            name = "uploaded_video"

        stem = Path(name).stem.strip().rstrip(". ")
        suffix = Path(name).suffix.lower()
        if stem.upper() in WINDOWS_RESERVED_NAMES:
            stem = f"{stem}_file"
        return f"{stem}{suffix}" if suffix else stem

    def validate_video_extension(self, filename: str) -> str:
        extension = Path(filename).suffix.lower()
        if extension not in self.settings.allowed_video_extensions:
            raise ValidationAppError(
                message="Unsupported video extension.",
                detail={
                    "extension": extension,
                    "allowed": list(self.settings.allowed_video_extensions),
                },
                suggested_action="Upload mp4, mov, mkv, avi, or webm video.",
            )
        return extension

    def upload_path(self, original_filename: str) -> Path:
        safe_name = self.safe_filename(original_filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        return self.ensure_under_root(self.settings.upload_dir / unique_name)

    def relative_path(self, path: Path) -> str:
        resolved = self.ensure_under_root(path)
        return resolved.relative_to(self.settings.storage_root.resolve()).as_posix()

    def resolve_storage_path(self, relative_path: str) -> Path:
        if Path(relative_path).is_absolute():
            raise ValidationAppError(
                message="Storage path must be relative.",
                detail={"path": relative_path},
                suggested_action="Use a storage-root relative path.",
            )
        return self.ensure_under_root(self.settings.storage_root / relative_path)

    def ensure_under_root(self, path: Path) -> Path:
        root = self.settings.storage_root.resolve()
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValidationAppError(
                message="Resolved path is outside storage root.",
                detail={"path": str(path), "storage_root": str(root)},
                suggested_action="Use a file name without path traversal components.",
            )
        return resolved
