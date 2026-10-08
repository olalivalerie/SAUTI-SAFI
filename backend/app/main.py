from contextlib import asynccontextmanager
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import User, PasswordResetToken, Post, Alert, MonitoringTopic
from .schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from .auth import hash_password, verify_password, create_access_token, get_current_user
from .ingestion import collect_topic


def initialize_database() -> None:
    """Create missing Phase 3 tables and upgrade an older Phase 2 users table.

    SQLAlchemy create_all() only creates missing tables. It does not add columns
    to an existing table, so we explicitly migrate the legacy users table.
    """
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name != "postgresql":
        return

    migrations = {
        "role": "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'analyst'",
        "plan": "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(50) NOT NULL DEFAULT 'Starter'",
        "is_active": "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "is_superuser": "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN NOT NULL DEFAULT FALSE",
        "created_at": "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE IF NOT EXISTS monitoring_topics (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), name VARCHAR(120) NOT NULL, query VARCHAR(512) NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"""))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_monitoring_topic_user_name ON monitoring_topics(user_id, name)"))
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS topic_id INTEGER REFERENCES monitoring_topics(id)"))
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS author_username VARCHAR(255)"))
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS author_id VARCHAR(255)"))
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS language VARCHAR(20)"))
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        connection.execute(text("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS post_id INTEGER REFERENCES posts(id)"))
        connection.execute(text("CREATE TABLE IF NOT EXISTS password_reset_tokens (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), token VARCHAR(255) UNIQUE NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used BOOLEAN NOT NULL DEFAULT FALSE)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens(user_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token ON password_reset_tokens(token)"))

        for statement in migrations.values():
            connection.execute(text(statement))

    # Refresh SQLAlchemy's schema view after the migration. This also makes the
    # startup behavior deterministic when an old database is reused.
    inspect(engine).get_columns("users")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="SAUTI SAFI API",
    description="Social Media Early Warning Intelligence System",
    version="0.3.1",
    lifespan=lifespan,
)

frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500").rstrip("/")
origins = list(dict.fromkeys([
    frontend_url,
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:43043",
    "http://localhost:43043",
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
def root():
    return {"message": "SAUTI SAFI API is running", "version": app.version, "status": "development"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(user_data: RegisterRequest, db: Session = Depends(get_db)):
    name = user_data.name.strip()
    email = user_data.email.lower().strip()

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must contain at least 2 characters.")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(user_data.password),
        role="analyst",
        plan="Starter",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Account created successfully",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "plan": user.plan,
        },
    }


@app.post("/auth/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    email = login_data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated.")

    return {
        "message": "Login successful",
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "plan": user.plan,
        },
    }


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    generic = {"message": "If an account exists for that email, a password reset link has been generated."}
    email = data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return generic

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update({"used": True})

    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
    db.add(PasswordResetToken(user_id=user.id, token=token, expires_at=expires, used=False))
    db.commit()

    reset_url = f"{frontend_url}/reset-password.html?token={token}"
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")

    if not all([smtp_host, smtp_user, smtp_password, smtp_from]):
        print(f"[LOCAL DEV] Password reset URL for {user.email}: {reset_url}")
        return generic

    msg = EmailMessage()
    msg["Subject"] = "SAUTI SAFI password reset"
    msg["From"] = smtp_from
    msg["To"] = user.email
    msg.set_content(
        "Use this link to reset your SAUTI SAFI password. It expires in 30 minutes.\n\n"
        + reset_url
    )

    try:
        with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as exc:
        print(f"[SMTP ERROR] Failed to send email: {exc}")

    return {"message": "If an account exists for that email, a password reset link has been sent."}


@app.post("/auth/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token,
        PasswordResetToken.used.is_(False),
    ).first()

    if not row:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired.")

    expires_at = row.expires_at
    if expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if expires_at < now:
        row.used = True
        db.commit()
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired.")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset request.")

    user.password_hash = hash_password(data.password)
    row.used = True
    db.commit()
    return {"message": "Password updated successfully. You can now sign in."}


@app.get("/monitoring/topics")
def list_topics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    topics = db.query(MonitoringTopic).filter(MonitoringTopic.user_id == current_user.id).order_by(MonitoringTopic.created_at.asc()).all()
    return [{"id": t.id, "name": t.name, "query": t.query, "enabled": t.enabled, "created_at": t.created_at} for t in topics]


@app.post("/monitoring/topics")
def create_topic(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = str(payload.get("name", "")).strip()
    query = str(payload.get("query", "")).strip()
    if not name or len(name) > 120:
        raise HTTPException(status_code=400, detail="Topic name is required and must be 120 characters or fewer.")
    if not query or len(query) > 512:
        raise HTTPException(status_code=400, detail="X search query is required and must be 512 characters or fewer.")
    if db.query(MonitoringTopic).filter(MonitoringTopic.user_id == current_user.id, MonitoringTopic.name == name).first():
        raise HTTPException(status_code=400, detail="A topic with this name already exists.")
    topic = MonitoringTopic(user_id=current_user.id, name=name, query=query, enabled=True)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "name": topic.name, "query": topic.query, "enabled": topic.enabled}


@app.delete("/monitoring/topics/{topic_id}")
def delete_topic(topic_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    topic = db.query(MonitoringTopic).filter(MonitoringTopic.id == topic_id, MonitoringTopic.user_id == current_user.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Monitoring topic not found.")
    db.delete(topic)
    db.commit()
    return {"message": "Monitoring topic deleted."}


@app.post("/monitoring/collect")
def collect_monitoring_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    topics = db.query(MonitoringTopic).filter(MonitoringTopic.user_id == current_user.id, MonitoringTopic.enabled.is_(True)).all()
    if not topics:
        raise HTTPException(status_code=400, detail="Create at least one monitoring topic first.")
    results = []
    for topic in topics:
        try:
            results.append(collect_topic(db, topic, current_user.id, max_results=10))
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"Collector failed for topic '{topic.name}': {exc}") from exc
    return {"message": "Collection completed.", "results": results}


@app.get("/dashboard")
def get_dashboard_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .filter(or_(Post.user_id == current_user.id, Post.user_id.is_(None)))
        .order_by(Post.created_at.desc())
        .limit(50)
        .all()
    )

    alerts = (
        db.query(Alert)
        .filter(or_(Alert.user_id == current_user.id, Alert.user_id.is_(None)))
        .order_by(Alert.created_at.desc())
        .limit(10)
        .all()
    )

    relevant = sum(
        1
        for post in posts
        if max(post.misinformation_risk or 0, post.hate_speech_risk or 0) >= 50
    )

    return {
        "posts_received": len(posts),
        "relevant_detections": relevant,
        "alerts": len(alerts),
        "posts": [
            {
                "id": post.id,
                "source_name": post.source_name,
                "platform": post.platform,
                "text": post.text,
                "misinformation_risk": post.misinformation_risk,
                "hate_speech_risk": post.hate_speech_risk,
                "early_warning_priority": post.early_warning_priority,
                "created_at": post.created_at,
            }
            for post in posts
        ],
        "alert_items": [
            {
                "id": alert.id,
                "title": alert.title,
                "detail": alert.detail,
                "priority": alert.priority,
                "created_at": alert.created_at,
            }
            for alert in alerts
        ],
    }
