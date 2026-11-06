"""
Run with: uv run python -m app.seed

Seeds reference data (muscles, equipment, set types) and a handful of
example exercises into whatever database DATABASE_URL points at. Safe to
run more than once — see app/infrastructure/seed_data.py.
"""

from app.infrastructure.database import SessionLocal
from app.infrastructure.seed_data import seed

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
        print("Seed complete.")
    finally:
        db.close()
