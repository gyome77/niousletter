from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    name = Column(String(255))
    enabled = Column(Boolean, default=True, nullable=False)
    unsubscribed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    group_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    source_id = Column(String(128), unique=True, nullable=False, index=True)
    type = Column(String(64), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    last_polled_at = Column(DateTime)
    params = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    source_id = Column(String(128), nullable=False, index=True)
    title = Column(String(512))
    content_text = Column(Text, nullable=False)
    url = Column(String(2048))
    published_at = Column(DateTime)
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    links = Column(JSON)
    fingerprint = Column(String(64), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("source_id", "fingerprint", name="uq_item_source_fingerprint"),)


class WebsiteSnapshot(Base):
    __tablename__ = "website_snapshots"

    id = Column(Integer, primary_key=True)
    source_id = Column(String(128), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    content_hash = Column(String(64), nullable=False)
    content_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NewsletterRun(Base):
    __tablename__ = "newsletter_runs"

    id = Column(Integer, primary_key=True)
    newsletter_id = Column(String(128), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(String(32), nullable=False, default="created")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    items = relationship("NewsletterRunItem", back_populates="run", cascade="all, delete-orphan")


class NewsletterRunItem(Base):
    __tablename__ = "newsletter_run_items"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("newsletter_runs.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    summary = Column(Text)
    links_json = Column(JSON)

    run = relationship("NewsletterRun", back_populates="items")

    __table_args__ = (UniqueConstraint("run_id", "item_id", name="uq_run_item"),)


class EmailSent(Base):
    __tablename__ = "emails_sent"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("newsletter_runs.id"), nullable=False)
    recipient_email = Column(String(320), nullable=False)
    gmail_message_id = Column(String(256))
    status = Column(String(32), nullable=False, default="pending")
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("run_id", "recipient_email", name="uq_run_recipient"),)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails_sent.id"), nullable=False)
    type = Column(String(32), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    link_url = Column(String(2048))
