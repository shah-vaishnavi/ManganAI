"""SQLAlchemy tables for PostgreSQL/PostGIS persistence mode (lat/lon columns; PostGIS geometry can be added with geoalchemy2)."""
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()
SPEC = {
    "geological_samples": ["sample_id:s", "latitude:f", "longitude:f", "geology_type:s", "sample_grade:f", "manganese_presence:i"],
    "drilling_samples": ["drill_id:s", "latitude:f", "longitude:f", "depth:f", "sample_grade:f"],
    "satellite_observations": ["sample_id:s", "ndvi:f", "ndwi:f", "land_surface_temperature:f", "rainfall:f", "soil_moisture:f"],
    "production_records": ["date:s", "mine_id:s", "production_target:f", "actual_production:f", "equipment_downtime:f", "rainfall:f"],
    "equipment_records": ["equipment_id:s", "date:s", "equipment_type:s", "availability:f", "downtime_hours:f"],
    "weather_records": ["date:s", "rainfall:f", "temperature:f", "soil_moisture:f", "weather_risk:f"],
    "blasting_records": ["date:s", "blast_id:s", "delay_hours:f", "delay_reason:s"],
    "reserve_predictions": ["sample_id:s", "manganese_probability:f", "model_name:s"],
    "production_predictions": ["date:s", "predicted_production:f", "expected_shortfall:f", "model_name:s"],
    "risk_assessments": ["risk_score:f", "risk_level:s", "details:t"],
    "recommendations": ["priority:s", "title:s", "reason:t", "affected_factor:s"],
    "scenario_runs": ["name:s", "inputs:t", "results:t"],
    "dataset_metadata": ["name:s", "details:t"],
}
_T = {"s": lambda: String(120), "f": lambda: Float, "i": lambda: Integer, "t": lambda: Text}
TABLES = {}
for _name, _cols in SPEC.items():
    attrs = {"__tablename__": _name, "id": Column(Integer, primary_key=True),
             "created_at": Column(DateTime, server_default=func.now())}
    for _c in _cols:
        n, t = _c.split(":"); attrs[n] = Column(_T[t]())
    TABLES[_name] = type("".join(w.title() for w in _name.split("_")), (Base,), attrs)
