import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from .analyzer import analyze_post
from .models import Alert, MonitoringTopic, Post

X_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"


def x_bearer_token() -> str:
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("X_BEARER_TOKEN is not configured.")
    return token


def search_recent(query: str, max_results: int = 10) -> dict:
    params = {
        "query": query,
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,public_metrics,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username,name,verified",
    }
    response = requests.get(
        X_SEARCH_URL,
        headers={"Authorization": f"Bearer {x_bearer_token()}"},
        params=params,
        timeout=30,
    )
    if not response.ok:
        try:
            detail = response.json().get("detail") or response.json().get("title") or response.text
        except Exception:
            detail = response.text
        raise RuntimeError(f"X API request failed ({response.status_code}): {detail}")
    return response.json()


def collect_topic(db, topic: MonitoringTopic, user_id: int, max_results: int = 10) -> dict:
    payload = search_recent(topic.query, max_results)
    users = {u.get("id"): u for u in payload.get("includes", {}).get("users", [])}
    inserted = 0
    skipped = 0
    alerts_created = 0

    for item in payload.get("data", []):
        external_id = str(item.get("id"))
        existing = db.query(Post).filter(
            Post.user_id == user_id,
            Post.platform == "X",
            Post.external_id == external_id,
        ).first()
        if existing:
            skipped += 1
            continue

        author = users.get(item.get("author_id"), {})
        metrics = item.get("public_metrics") or {}
        scores = analyze_post(item.get("text", ""), metrics)
        created_at = item.get("created_at")
        if created_at:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created_at = datetime.now(timezone.utc)

        post = Post(
            user_id=user_id,
            topic_id=topic.id,
            source_name=author.get("name") or author.get("username") or "X user",
            platform="X",
            external_id=external_id,
            text=item.get("text", ""),
            author_username=author.get("username"),
            author_id=str(item.get("author_id")) if item.get("author_id") else None,
            language=item.get("lang"),
            created_at=created_at,
            **scores,
        )
        db.add(post)
        db.flush()
        inserted += 1

        if scores["early_warning_priority"] >= 70:
            alert = Alert(
                user_id=user_id,
                post_id=post.id,
                title="High priority early warning detected",
                detail=f"Topic: {topic.name}. Misinformation risk {scores['misinformation_risk']:.0f}%, hate speech risk {scores['hate_speech_risk']:.0f}%, priority {scores['early_warning_priority']:.0f}/100.",
                priority=scores["early_warning_priority"],
            )
            db.add(alert)
            alerts_created += 1

    db.commit()
    return {
        "topic": topic.name,
        "query": topic.query,
        "fetched": len(payload.get("data", [])),
        "inserted": inserted,
        "skipped": skipped,
        "alerts_created": alerts_created,
    }
