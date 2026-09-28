"""Optional AI module tables (Re-ID, attributes, person detection, quality, anomaly).

These are NEW tables only. No existing model/table is modified. Tables are
auto-created by ``Base.metadata.create_all`` on startup (and by Alembic when
used), so dropping this file removes the modules entirely.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class VehicleAttribute(Base):
    """Appearance attributes of one detection (vehicle type/color/predicate)."""

    __tablename__ = "vehicle_attributes"
    __table_args__ = (Index("ix_vattr_event", "event_id"), Index("ix_vattr_color", "color"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("detection_events.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(24), default="")
    color: Mapped[str] = mapped_column(String(24), default="")
    color_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    body_style: Mapped[str] = mapped_column(String(24), default="")
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # full raw attribute dict
    model_name: Mapped[str] = mapped_column(String(64), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    camera = relationship("Camera")


class ReidMatch(Base):
    """Appearance-based candidate match between two detections on different cameras.

    ALWAYS unconfirmed: appearance similarity is a lead for investigators,
    never proof of identity (two similar cars can share a look).
    """

    __tablename__ = "reid_matches"
    __table_args__ = (Index("ix_reid_created", "created_at"), Index("ix_reid_event", "event_id"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("detection_events.id", ondelete="CASCADE"), index=True)  # the new sighting
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    matched_event_id: Mapped[int | None] = mapped_column(ForeignKey("detection_events.id", ondelete="SET NULL"), nullable=True)
    matched_camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    matched_plate: Mapped[str] = mapped_column(String(20), default="")  # plate of the matched fingerprint, if known
    status: Mapped[str] = mapped_column(String(16), default="unconfirmed", index=True)  # unconfirmed|confirmed|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class QualityMetric(Base):
    """Frame quality assessment for one ingested frame (blur/brightness/etc.)."""

    __tablename__ = "quality_metrics"
    __table_args__ = (Index("ix_quality_camera_ts", "camera_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    composite: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 overall usability
    blur_score: Mapped[float] = mapped_column(Float, default=0.0)
    brightness_score: Mapped[float] = mapped_column(Float, default=0.0)
    visibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(16), default="good")  # good|degraded|poor
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class PersonDetection(Base):
    """One person detection from the dedicated person model (presence only)."""

    __tablename__ = "person_detections"
    __table_args__ = (Index("ix_person_camera_ts", "camera_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bbox_x: Mapped[float] = mapped_column(Float, default=0.0)
    bbox_y: Mapped[float] = mapped_column(Float, default=0.0)
    bbox_w: Mapped[float] = mapped_column(Float, default=0.0)
    bbox_h: Mapped[float] = mapped_column(Float, default=0.0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    camera = relationship("Camera")


class AnomalyReview(Base):
    """Review event for unusual vehicle movement. Never a criminal label."""

    __tablename__ = "anomaly_reviews"
    __table_args__ = (Index("ix_anomaly_camera_ts", "camera_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("detection_events.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    anomaly_type: Mapped[str] = mapped_column(String(32), default="speed")  # speed|loitering|direction
    score: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[str] = mapped_column(String(255), default="")
    review_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|reviewed
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    camera = relationship("Camera")
