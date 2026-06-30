from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Scene Detector"
    app_version: str = "0.1.0"
    environment: str = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    storage_root: Path = Field(default=Path("data"))
    database_url: str = "sqlite:///data/app.db"

    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    max_upload_size_bytes: int = 50 * 1024 * 1024 * 1024
    allowed_video_extensions: tuple[str, ...] = (
        ".mp4",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
    )

    cuda_enabled: bool = True
    cpu_diagnostic_enabled: bool = False
    default_training_batch_size: int = 64
    default_detection_batch_size: int = 64
    auto_batch_reduction: bool = True
    default_frame_interval_sec: float = 1.0
    openclip_model_name: str = "ViT-B-32"
    openclip_pretrained: str = "laion2b_s34b_b79k"
    openclip_feature_dtype: str = "float16"

    request_log_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AISD_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def upload_dir(self) -> Path:
        return self.storage_root / "uploads"

    @property
    def training_dir(self) -> Path:
        return self.storage_root / "training"

    @property
    def features_dir(self) -> Path:
        return self.storage_root / "features"

    @property
    def models_dir(self) -> Path:
        return self.storage_root / "models"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_root / "outputs"

    @property
    def previews_dir(self) -> Path:
        return self.storage_root / "previews"

    @property
    def thumbnails_dir(self) -> Path:
        return self.storage_root / "thumbnails"

    @property
    def logs_dir(self) -> Path:
        return self.storage_root / "logs"

    @property
    def temp_dir(self) -> Path:
        return self.storage_root / "temp"

    def ensure_data_directories(self) -> None:
        for directory in (
            self.storage_root,
            self.upload_dir,
            self.training_dir,
            self.features_dir,
            self.models_dir,
            self.outputs_dir,
            self.previews_dir,
            self.thumbnails_dir,
            self.logs_dir,
            self.temp_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
