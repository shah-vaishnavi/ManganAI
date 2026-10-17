"""Optional database layer. Falls back to DEMO_MODE (CSV/JSON) when PostgreSQL is unavailable."""
import json
from datetime import datetime

from .config import settings
from .models import Base, TABLES

engine = None
mode = "demo"


def init_db():
    global engine, mode
    if settings.demo_mode or not settings.database_url:
        return mode
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(settings.database_url, pool_pre_ping=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
            try: c.execute(text("CREATE EXTENSION IF NOT EXISTS postgis")); c.commit()
            except Exception: pass
        Base.metadata.create_all(eng)
        engine, mode = eng, "database"
    except Exception:
        engine, mode = None, "demo"     # graceful fallback
    return mode


def save_scenario(name, inputs, results):
    """Explicit user save. Database in DB mode, JSON file in demo mode."""
    if engine is not None:
        from sqlalchemy.orm import Session
        with Session(engine) as s:
            s.add(TABLES["scenario_runs"](name=name, inputs=json.dumps(inputs), results=json.dumps(results))); s.commit()
        return "database"
    f = settings.demo_dir / "saved_scenarios.json"
    items = json.loads(f.read_text()) if f.exists() else []
    items.append({"name": name, "saved_at": datetime.now().isoformat(timespec="seconds"), "inputs": inputs, "results": results})
    f.write_text(json.dumps(items, indent=1))
    return "json"
