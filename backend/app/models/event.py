"""Detection event models: frame events, vehicles, sightings, plate reads."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class DetectionEvent(Base):
    """A single AI detection (vehicle or person) on a camera at a timestamp."""

    __tablename__ = "detection_events"
    __table_args__ = (
        Index("ix_events_camera_ts", "camera_id", "timestamp"),
        Index("ix_events_class_ts", "object_class", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    object_class: Mapped[str] = mapped_column(String(24), index=True)  # car/motorcycle/bus/truck/person
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bbox_x: Mapped[float] = mapped_column(Float, default=0)
    bbox_y: Mapped[float] = mapped_column(Float, default=0)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float] = mapped_column(Float, default=0)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_path: Mapped[str] = mapped_column(String(255), default="")
    frame_path: Mapped[str] = mapped_column(String(255), default="")
    plate_read_id: Mapped[int | None] = mapped_column(ForeignKey("plate_reads.id", ondelete="SET NULL"), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    camera = relationship("Camera")
    plate_read = relationship("PlateRead", foreign_keys=[plate_read_id])
    sighting = relationship(
        "VehicleSighting", back_populates="event", uselist=False, cascade="all, delete-orphan"
    )


class Vehicle(Base):
    """Aggregated vehicle identity by recognized registration number."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    vehicle_class: Mapped[str] = mapped_column(String(24), default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    total_sightings: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    sightings = relationship("VehicleSighting", back_populates="vehicle")


class VehicleSighting(Base):
    """A vehicle sighting tied to a DetectionEvent via a plate read."""

    __tablename__ = "vehicle_sightings"
    __table_args__ = (Index("ix_sightings_vehicle_ts", "vehicle_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("detection_events.id", ondelete="CASCADE"), unique=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    vehicle = relationship("Vehicle", back_populates="sightings")
    event = relationship("DetectionEvent", back_populates="sighting")
    camera = relationship("Camera")


class PlateRead(Base):
    """Result of one ANPR OCR pass. Confidence below threshold needs review."""

    __tablename__ = "plate_reads"
    __table_args__ = (Index("ix_plate_reads_ts", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate_text: Mapped[str] = mapped_column(String(20), default="", index=True)
    raw_text: Mapped[str] = mapped_column(String(40), default="")
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    corrected_text: Mapped[str | None] = mapped_column(String(20), nullable=True)
    crop_path: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    events = relationship("DetectionEvent", back_populates="plate_read")
