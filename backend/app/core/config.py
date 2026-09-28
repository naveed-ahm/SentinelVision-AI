"""Application configuration via environment variables (pydantic-settings)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[2]  # .../backend


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "SentinelVision AI"
    ENVIRONMENT: str = "development"  # development | demo | production
    DEMO_MODE: bool = True  # synthetic data is clearly labeled as demonstration data
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # --- Security ---
    SECRET_KEY: str = "CHANGE_ME_dev_only_secret_key_set_via_env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./sentinelvision.db"  # dev default; prod uses Postgres

    # --- Paths ---
    MEDIA_DIR: str = str(BASE_DIR.parent / "data" / "media")  # crops / frames / plates
    DEMO_VIDEO_DIR: str = str(BASE_DIR.parent / "data" / "demo_videos")

    # --- Video ingestion / AI ---
    MAX_CONCURRENT_STREAMS: int = 8  # keep small; browsers and CPUs are finite
    INGEST_FPS_LIMIT: float = 12.0  # upper bound on frames decoded per camera
    DETECTION_SAMPLE_INTERVAL: float = 1.0  # seconds between AI passes per camera
    DETECT_PERSONS: bool = True
    ANPR_ENABLED: bool = True
    DETECTION_CONFIDENCE: float = 0.35
    OCR_MIN_CONFIDENCE: float = 0.55  # below this, plate text needs review
    YOLO_WEIGHTS: str = "yolov8n.pt"  # auto-downloaded by ultralytics on first run
    ENABLE_GPU: bool = False

    # --- Optional extended AI modules (all independent; see requirements-ai.txt) ---
    ENABLE_REID: bool = True  # vehicle Re-ID: appearance embedding + cross-camera matching
    ENABLE_ATTRIBUTES: bool = True  # vehicle attribute recognition (type/color heuristic + optional model)
    ENABLE_PERSON_MODEL: bool = True  # dedicated person detection model (independent of vehicle YOLO)
    ENABLE_QUALITY: bool = True  # frame quality assessment (blur/brightness/visibility scoring)
    ENABLE_ANOMALY: bool = True  # unusual vehicle movement pattern review events
    ENABLE_WATCHLIST: bool = True  # watchlist matching on confirmed ANPR plate reads
    WATCHLIST_MATCH_MIN_CONFIDENCE: float = 0.70  # min OCR confidence for a watchlist match
    REID_SIMILARITY_THRESHOLD: float = 0.72  # cosine sim above which a Re-ID candidate match is recorded
    REID_MATCH_TTL_MINUTES: int = 120  # max camera-to-camera gap for an appearance match
    REID_HISTORY_SIZE: int = 200  # recent appearance fingerprints kept per vehicle identity
    ANOMALY_SPEED_LIMIT_KMPH: float = 90.0  # estimated speed above which movement is flagged for review
    ANOMALY_MIN_TRACK_HISTORY: int = 8  # track history points required before speed estimation
    ANOMALY_COOLDOWN_SECONDS: int = 300  # minimum seconds between review events per camera
    QUALITY_SAMPLE_EVERY_N: int = 100  # assess one frame per N ingested frames per camera
    QUALITY_LOW_THRESHOLD: float = 0.35  # composite score below this marks a camera "poor quality"
    PERSON_MODEL_WEIGHTS: str = "yolov8n.pt"  # dedicated weights for the person model (independent load)

    # --- Alerts / health ---
    HEALTH_CHECK_INTERVAL: int = 60
    ALERT_OFFLINE_AFTER: int = 180  # seconds without frames before a camera is OFFLINE

    # --- Rate limiting (very small in-memory limiter for the PoC) ---
    RATE_LIMIT_REQUESTS: int = 300
    RATE_LIMIT_WINDOW: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

Path(settings.MEDIA_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.DEMO_VIDEO_DIR).mkdir(parents=True, exist_ok=True)
