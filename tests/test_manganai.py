import io, sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.ml import pipeline as P
from backend.app.services import analytics as A
from backend.app.services import dataops as D


def test_reserve_prediction_probability_range():
    p = P.predict_reserve({"sample_grade": 35, "geological_indicator": .9, "drilling_indicator": .9, "geology_type": "Phyllite"})
    low = P.predict_reserve({"sample_grade": 3, "geological_indicator": .05, "drilling_indicator": .05, "geology_type": "Granite"})
    assert 0 <= low < p <= 1


def test_production_prediction_and_shortfall():
    o = A.outcome(A.current_features())
    assert o["predicted_production"] > 0 and o["expected_shortfall"] >= 0
    assert A.outcome({**A.current_features(), "production_target": 0})["shortfall_percentage"] == 0


def test_risk_levels_and_monotonic():
    f = A.current_features(); bad = {**f, "equipment_downtime": 12, "equipment_availability": .5, "rainfall": 60, "blasting_delay": 6}
    assert A.risk(bad)["score"] > A.risk(f)["score"] and A.level(10) == "LOW" and A.level(80) == "CRITICAL"


def test_recommendations_change_with_data():
    f = A.current_features()
    titles_bad = {r["title"] for r in A.recommendations({**f, "equipment_downtime": 9})}
    titles_ok = {r["title"] for r in A.recommendations({**f, "equipment_downtime": 1, "equipment_availability": .95, "blasting_delay": 0, "rainfall": 0})}
    assert "Schedule preventive maintenance" in titles_bad and "Schedule preventive maintenance" not in titles_ok


def test_scenario_uses_model():
    r = A.scenario({"equipment_downtime": 10, "rainfall": 50, "weather_factor": .65})
    assert r["impact"]["production_difference"] < 0 and r["impact"]["risk_difference"] > 0
    assert A.scenario({})["impact"]["production_difference"] == 0


def test_csv_validation():
    ok = D.handle_upload("weather", pd.read_csv(D.settings.demo_dir / "weather.csv").to_csv(index=False).encode())
    assert ok["status"] in ("valid", "warnings")
    bad = D.handle_upload("weather", b"date,rainfall\n2024-01-01,5\n")
    assert bad["status"] == "invalid" and "temperature" in bad["missing_required_columns"]
    with pytest.raises(ValueError): D.handle_upload("nonsense", b"a\n1")


def test_api_endpoints():
    pytest.importorskip("fastapi"); pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.get("/api/dashboard/summary").json()["data"]["kpis"]["mapped_samples"] > 0
        assert c.post("/api/production/predict", json={"features": {}}).status_code == 200
        assert c.post("/api/scenario/simulate", json={"rainfall": 400}).status_code == 200
        assert c.post("/api/scenario/simulate", json={"rainfall": -1}).status_code == 422
        assert c.post("/api/data/upload", data={"dataset": "weather"}, files={"file": ("x.txt", b"a")}).status_code == 400
