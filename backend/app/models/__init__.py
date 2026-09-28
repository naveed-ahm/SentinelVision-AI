"""All persistence models. Importing this package registers every table."""
from app.models.ai_modules import (
    AnomalyReview,
    PersonDetection,
    QualityMetric,
    ReidMatch,
    VehicleAttribute,
)
from app.models.alert import Alert
from app.models.camera import Camera, CameraCredential
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.system import AuditLog, PlatformSetting, SystemHealth
from app.models.user import User
from app.models.watchlist import WatchlistEntry, WatchlistHit

__all__ = [
    "Alert",
    "AnomalyReview",
    "WatchlistEntry",
    "WatchlistHit",
    "AuditLog",
    "Camera",
    "CameraCredential",
    "DetectionEvent",
    "PersonDetection",
    "PlateRead",
    "PlatformSetting",
    "QualityMetric",
    "ReidMatch",
    "SystemHealth",
    "User",
    "Vehicle",
    "VehicleAttribute",
    "VehicleSighting",
]
