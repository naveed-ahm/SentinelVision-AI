"""Camera and camera credential models.

RTSP credentials are stored in a separate table and are never serialized to
API responses; the frontend only ever sees a redacted RTSP URL.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (Index("ix_cameras_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    location_name: Mapped[str] = mapped_column(String(200), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    manufacturer: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    protocol: Mapped[str] = mapped_column(String(16), default="rtsp")  # rtsp | file | webcam
    rtsp_url: Mapped[str] = mapped_column(Text, default="")  # stored redacted; secrets in Credential
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    detection_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="offline")  # online | offline | error | disabled
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    stream_fps: Mapped[float] = mapped_column(Float, default=0.0)  # measured, informational
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    credential: Mapped["CameraCredential | None"] = relationship(
        back_populates="camera", uselist=False, cascade="all, delete-orphan"
    )


class CameraCredential(Base):
    """Sensitive per-camera credentials. Never exposed through the API."""

    __tablename__ = "camera_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), unique=True)
    username: Mapped[str] = mapped_column(String(120), default="")
    secret: Mapped[str] = mapped_column(String(255), default="")  # password / token
    channel: Mapped[str] = mapped_column(String(32), default="")

    camera: Mapped[Camera] = relationship(back_populates="credential")
