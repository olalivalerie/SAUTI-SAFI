from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="analyst", nullable=False)
    plan = Column(String(50), default="Starter", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)


class MonitoringTopic(Base):
    __tablename__ = "monitoring_topics"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    query = Column(String(512), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_monitoring_topic_user_name"),)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("monitoring_topics.id"), nullable=True, index=True)
    source_name = Column(String(255), nullable=True)
    platform = Column(String(100), nullable=True)
    external_id = Column(String(255), nullable=True, index=True)
    text = Column(Text, nullable=False)
    author_username = Column(String(255), nullable=True)
    author_id = Column(String(255), nullable=True)
    language = Column(String(20), nullable=True)
    misinformation_risk = Column(Float, default=0, nullable=False)
    hate_speech_risk = Column(Float, default=0, nullable=False)
    spread_velocity = Column(Float, default=0, nullable=False)
    reach = Column(Float, default=0, nullable=False)
    early_warning_priority = Column(Float, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    detail = Column(Text, nullable=True)
    priority = Column(Float, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
