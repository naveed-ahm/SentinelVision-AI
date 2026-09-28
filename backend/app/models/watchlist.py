"""Watchlist module models (NEW tables only; no existing table is modified).

WatchlistEntry: an entity of interest (stolen vehicle, wanted/missing person,
blacklisted vehicle, custom category) identified primarily by registration
plate. Representative/demo data is labeled ``is_demo`` like everywhere else.

WatchlistHit: one recorded match between a watchlist entry and a real ANPR
plate read / detection event, with the evidence crop path. Hits drive the
``watchlist_hit`` alert type and WS push.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"
    __table_args__ = (
        Index("ix_watchlist_identifier", "identifier_type", "identifier_value"),
        Index("ix_watchlist_active", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), default="stolen_vehicle", index=True)
    # identifier_type: plate | name | custom  (plate is the one matched automatically)
    identifier_type: Mapped[str] = mapped_column(String(16), default="plate")
    identifier_value: Mapped[str] = mapped_column(String(64), index=True)  # normalized plate text
    display_value: Mapped[str] = mapped_column(String(64), default="")  # as entered by the operator
    title: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # info|warning|critical
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    hits = relationship("WatchlistHit", back_populates="entry", cascade="all, delete-orphan")


class WatchlistHit(Base):
    __tablename__ = "watchlist_hits"
    __table_args__ = (Index("ix_whits_ts", "timestamp"), Index("ix_whits_entry_ts", "entry_id", "timestamp"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("watchlist_entries.id", ondelete="CASCADE"), index=True)
    plate_read_id: Mapped[int | None] = mapped_column(ForeignKey("plate_reads.id", ondelete="SET NULL"), nullable=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("detection_events.id", ondelete="SET NULL"), nullable=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    plate_text: Mapped[str] = mapped_column(String(20), default="")
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    match_type: Mapped[str] = mapped_column(String(16), default="exact")  # exact | normalized
    evidence_path: Mapped[str] = mapped_column(String(255), default="")
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    entry = relationship("WatchlistEntry", back_populates="hits")
    camera = relationship("Camera")
