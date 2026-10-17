import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Settings:
    demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
    database_url = os.getenv("DATABASE_URL", "")
    max_upload_mb = float(os.getenv("MAX_UPLOAD_MB", "5"))
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")]
    demo_dir = ROOT / "data" / "demo"
    temp_dir = ROOT / "data" / "temp"
    models_dir = ROOT / "models"
    frontend_dir = ROOT / "frontend"


settings = Settings()
for _d in (settings.demo_dir, settings.temp_dir, settings.models_dir):
    _d.mkdir(parents=True, exist_ok=True)
