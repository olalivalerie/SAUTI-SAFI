"""Optional local-only helper for testing the authenticated dashboard.

Run from the project root after creating a user:
    python -m backend.app.dev_seed user@example.com

This inserts clearly labelled test records. It is not part of the Phase 4 collector.
"""
import sys
from .database import SessionLocal
from .models import User, Post, Alert


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m backend.app.dev_seed USER_EMAIL")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == sys.argv[1].lower().strip()).first()
        if not user:
            raise SystemExit("User not found. Register the account first.")
        db.add(Post(
            user_id=user.id,
            source_name="Phase 3 test source",
            platform="Test",
            external_id="phase3-test-post-1",
            text="This is a local dashboard test record. It is not live social media data.",
            misinformation_risk=35,
            hate_speech_risk=5,
            spread_velocity=1,
            reach=10,
            early_warning_priority=20,
        ))
        db.add(Alert(
            user_id=user.id,
            title="Phase 3 test alert",
            detail="This is a local dashboard test alert.",
            priority=20,
        ))
        db.commit()
        print("Inserted Phase 3 dashboard test records.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
