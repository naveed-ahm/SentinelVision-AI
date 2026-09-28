"""Pydantic schemas for API requests and responses."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------- Auth / Users ----------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    full_name: str = ""


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""
    role: str = Field(default="viewer", pattern="^(admin|operator|viewer)$")


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    full_name: str | None = None
    role: str | None = Field(default=None, pattern="^(admin|operator|viewer)$")
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


# ---------- Cameras ----------


class CameraCredentialIn(BaseModel):
    username: str = ""
    secret: str = ""
    channel: str = ""


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=32, pattern="^[A-Za-z0-9_-]+$")
    location_name: str = ""
    latitude: float | None = None
    longitude: float | None = None
    manufacturer: str = ""
    model: str = ""
    protocol: str = Field(default="rtsp", pattern="^(rtsp|file|webcam)$")
    rtsp_url: str = ""
    description: str = ""
    enabled: bool = True
    detection_enabled: bool = True
    credential: CameraCredentialIn | None = None


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    manufacturer: str | None = None
    model: str | None = None
    protocol: str | None = Field(default=None, pattern="^(rtsp|file|webcam)$")
    rtsp_url: str | None = None
    description: str | None = None
    enabled: bool | None = None
    detection_enabled: bool | None = None
    credential: CameraCredentialIn | None = None


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    location_name: str
    latitude: float | None
    longitude: float | None
    manufacturer: str
    model: str
    protocol: str
    rtsp_url: str  # redacted
    description: str
    enabled: bool
    detection_enabled: bool
    status: str
    last_connected_at: datetime | None
    last_health_check: datetime | None
    last_error: str
    stream_fps: float
    created_at: datetime
    is_demo: bool


class CameraTestResult(BaseModel):
    camera_id: int
    ok: bool
    message: str
    latency_ms: float | None = None


# ---------- Events / Detections ----------


class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class DetectionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    timestamp: datetime
    object_class: str
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float | None
    bbox_h: float
    track_id: int | None
    image_path: str
    frame_path: str
    is_demo: bool


class EventPage(BaseModel):
    items: list[DetectionEventOut]
    total: int
    page: int
    page_size: int


class PlateReadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate_text: str
    raw_text: str
    ocr_confidence: float
    needs_review: bool
    corrected_text: str | None
    crop_path: str
    created_at: datetime
    is_demo: bool


class PlateCorrection(BaseModel):
    corrected_text: str = Field(min_length=1, max_length=20)


# ---------- Vehicles ----------


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    registration_number: str
    vehicle_class: str
    first_seen_at: datetime
    last_seen_at: datetime
    total_sightings: int
    is_demo: bool


class VehicleSightingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    event_id: int
    camera_id: int
    timestamp: datetime
    camera_name: str | None = None
    registration_number: str | None = None
    object_class: str | None = None
    confidence: float | None = None
    image_path: str = ""
    frame_path: str = ""
    ocr_confidence: float | None = None


class VehicleDetail(BaseModel):
    vehicle: VehicleOut
    sightings: list[VehicleSightingOut]


class VehiclePage(BaseModel):
    items: list[VehicleOut]
    total: int
    page: int
    page_size: int


# ---------- Alerts ----------


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    severity: str
    camera_id: int | None
    event_id: int | None
    title: str
    description: str
    status: str
    acknowledged_by: int | None
    acknowledged_at: datetime | None
    assigned_to: int | None
    created_at: datetime
    is_demo: bool


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    page_size: int


class AlertAck(BaseModel):
    assigned_to: int | None = None


# ---------- Analytics / GIS / Reports ----------


class OverviewStats(BaseModel):
    cameras_total: int
    cameras_online: int
    cameras_offline: int
    streams_active: int
    detections_today: int
    anpr_today: int
    alerts_open: int
    events_total: int
    demo_mode: bool


class TimeSeriesPoint(BaseModel):
    bucket: str  # ISO timestamp of bucket start
    count: int


class ClassBreakdown(BaseModel):
    object_class: str
    count: int


class CameraAvailability(BaseModel):
    camera_id: int
    name: str
    status: str
    uptime_pct: float


class AlertTypeBreakdown(BaseModel):
    alert_type: str
    severity: str
    count: int


class GisCamera(BaseModel):
    id: int
    name: str
    code: str
    status: str
    location_name: str
    latitude: float | None
    longitude: float | None
    last_connected_at: datetime | None
    is_demo: bool


class GisSighting(BaseModel):
    event_id: int
    camera_id: int
    camera_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    registration_number: str | None
    object_class: str | None
    confidence: float | None
    image_path: str = ""


class GisPathPoint(BaseModel):
    registration_number: str
    points: list[GisSighting]


# ---------- Settings / Health ----------


class SettingItem(BaseModel):
    key: str
    value: str
    updated_at: datetime | None = None
    updated_by: str = ""


class SettingUpdate(BaseModel):
    value: str


class ComponentHealth(BaseModel):
    component: str
    status: str
    detail: str = ""
    cpu_percent: float = 0
    memory_percent: float = 0
    checked_at: datetime | None = None


class WorkerStatus(BaseModel):
    running: bool
    cameras: dict[str, str]  # camera code -> state
    detector_ready: bool
    detector_device: str
    ocr_ready: bool
    demo_mode: bool


# ---------- Optional AI modules (new, additive only) ----------


class VehicleAttributeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    camera_id: int
    timestamp: datetime
    vehicle_type: str
    color: str
    color_confidence: float
    body_style: str
    model_name: str
    is_demo: bool


class ReidMatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    camera_id: int
    matched_event_id: int | None
    matched_camera_id: int | None
    similarity: float
    matched_plate: str
    status: str
    created_at: datetime
    is_demo: bool


class QualityMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    timestamp: datetime
    composite: float
    blur_score: float
    brightness_score: float
    visibility_score: float
    verdict: str
    is_demo: bool


class PersonDetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    timestamp: datetime
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    is_demo: bool


class AnomalyReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    event_id: int | None
    timestamp: datetime
    anomaly_type: str
    score: float
    detail: str
    review_status: str
    is_demo: bool


class AiModulesStatus(BaseModel):
    reid: dict
    attributes: dict
    person: dict
    quality: dict
    anomaly: dict


# ---------- Watchlist (new, additive only) ----------


class WatchlistEntryCreate(BaseModel):
    category: str = Field(default="stolen_vehicle", pattern="^(stolen_vehicle|wanted_person|missing_person|blacklist|custom)$")
    identifier_type: str = Field(default="plate", pattern="^(plate|custom)$")
    identifier_value: str = Field(min_length=3, max_length=64)
    title: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=2000)
    severity: str = Field(default="warning", pattern="^(info|warning|critical)$")
    active: bool = True
    expires_at: datetime | None = None


class WatchlistEntryUpdate(BaseModel):
    category: str | None = Field(default=None, pattern="^(stolen_vehicle|wanted_person|missing_person|blacklist|custom)$")
    title: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    severity: str | None = Field(default=None, pattern="^(info|warning|critical)$")
    active: bool | None = None
    expires_at: datetime | None = None


class WatchlistEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    identifier_type: str
    identifier_value: str
    display_value: str
    title: str
    notes: str
    severity: str
    active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    is_demo: bool
    hit_count: int = 0


class WatchlistHitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_id: int
    plate_read_id: int | None
    event_id: int | None
    camera_id: int | None
    timestamp: datetime
    plate_text: str
    ocr_confidence: float
    match_type: str
    evidence_path: str
    alert_id: int | None
    acknowledged: bool
    is_demo: bool
