"""
SQLAlchemy ORM models for persistent session memory.
"""

from __future__ import annotations

import datetime
import json

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    title = Column(String, default="New Research Session")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    queries = relationship("ResearchQuery", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utcnow)

    session = relationship("Session", back_populates="messages")


class ResearchQuery(Base):
    __tablename__ = "research_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    query = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utcnow)

    session = relationship("Session", back_populates="queries")
    sources = relationship("Source", back_populates="query", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(Integer, ForeignKey("research_queries.id"), nullable=False)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # "pubmed" or "document"
    identifier = Column(String, default="")
    url = Column(String, default="")
    extra_metadata = Column(Text, default="{}")  # JSON-encoded dict

    query = relationship("ResearchQuery", back_populates="sources")

    def set_metadata(self, data: dict) -> None:
        self.extra_metadata = json.dumps(data)

    def get_metadata(self) -> dict:
        try:
            return json.loads(self.extra_metadata or "{}")
        except json.JSONDecodeError:
            return {}
