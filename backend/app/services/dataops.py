"""CSV upload, validation, data-quality and refresh."""
import io
import json
import shutil
from datetime import datetime

import pandas as pd

from ..config import settings
from ..ml import pipeline as P
from ..ml.datagen import generate

REQUIRED = {
    "geological": ["sample_id", "latitude", "longitude", "elevation", "slope", "aspect", "geology_type", "rock_strength", "soil_depth",
                   "geological_indicator", "drilling_indicator", "sample_grade", "manganese_presence"],
    "drilling": ["drill_id", "latitude", "longitude", "depth", "rock_type", "geological_indicator", "ore_indicator", "sample_grade"],
    "production": ["date", "mine_id", "production_target", "actual_production", "working_days", "equipment_downtime",
                   "equipment_availability", "rainfall", "soil_moisture", "weather_factor", "blasting_delay", "blasting_duration"],
    "equipment": ["equipment_id", "date", "equipment_type", "availability", "downtime_hours", "maintenance_hours", "utilization"],
    "weather": ["date", "rainfall", "temperature", "soil_moisture", "weather_risk"],
    "blasting": ["date", "blast_id", "planned_blast", "blast_duration", "delay_hours", "delay_reason", "blasting_factor"],
}
RANGES = {"latitude": (-90, 90), "longitude": (-180, 180), "rainfall": (0, 1000), "actual_production": (0, None),
          "production_target": (0, None), "equipment_availability": (0, 1), "availability": (0, 1), "soil_moisture": (0, 1),
          "equipment_downtime": (0, 24), "downtime_hours": (0, 24), "weather_factor": (0, 1.5), "manganese_presence": (0, 1),
          "sample_grade": (0, 100), "working_days": (0, 7), "geological_indicator": (0, 1), "drilling_indicator": (0, 1)}
TEXT = {"sample_id", "drill_id", "mine_id", "equipment_id", "blast_id", "geology_type", "rock_type", "equipment_type", "delay_reason", "date"}


def validate(df, dataset):
    req = REQUIRED[dataset]
    missing_cols = [c for c in req if c not in df.columns]
    q = {"dataset": dataset, "rows": int(len(df)), "columns": int(df.shape[1]), "missing_required_columns": missing_cols,
         "missing_values": {c: int(v) for c, v in df.isna().sum().items() if v}, "duplicates": int(df.duplicated().sum()),
         "invalid_values": {}, "date_range": None}
    for c in req:
        if c in df.columns and c not in TEXT:
            num = pd.to_numeric(df[c], errors="coerce")
            bad = int((num.isna() & df[c].notna()).sum())
            lo, hi = RANGES.get(c, (None, None))
            if lo is not None: bad += int((num < lo).sum())
            if hi is not None: bad += int((num > hi).sum())
            if bad: q["invalid_values"][c] = bad
    if "date" in df.columns:
        d = pd.to_datetime(df["date"], errors="coerce")
        bad = int(d.isna().sum())
        if bad: q["invalid_values"]["date"] = bad
        if d.notna().any(): q["date_range"] = [str(d.min().date()), str(d.max().date())]
    q["status"] = "invalid" if missing_cols or q["rows"] == 0 else ("warnings" if q["missing_values"] or q["duplicates"] or q["invalid_values"] else "valid")
    return q


def handle_upload(dataset, raw: bytes):
    if dataset not in REQUIRED:
        raise ValueError(f"Unknown dataset '{dataset}'. Allowed: {', '.join(REQUIRED)}")
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise OverflowError(f"File exceeds {settings.max_upload_mb:g} MB limit")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise ValueError("File is not a readable CSV")
    q = validate(df, dataset)
    q["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
    df.to_csv(settings.temp_dir / f"{dataset}.csv", index=False)           # temporary storage only
    (settings.temp_dir / f"{dataset}_quality.json").write_text(json.dumps(q))
    q["preview"] = json.loads(df.head(10).to_json(orient="records", date_format="iso"))
    q["columns_list"] = list(df.columns)
    return q


def save_temp(dataset):
    src = settings.temp_dir / f"{dataset}.csv"
    if dataset not in REQUIRED or not src.exists():
        raise ValueError("No uploaded temporary file for this dataset")
    if json.loads((settings.temp_dir / f"{dataset}_quality.json").read_text())["status"] == "invalid":
        raise ValueError("Cannot save an invalid dataset")
    shutil.copy(src, settings.demo_dir / f"{dataset}.csv")
    P.clear_cache()
    return {"saved": dataset, "note": "Saved permanently. Retrain models to use the new data."}


def quality_report():
    demo = {}
    for ds in REQUIRED:
        f = settings.demo_dir / f"{ds}.csv"
        if f.exists(): demo[ds] = validate(pd.read_csv(f), ds)
    up = {}
    for f in settings.temp_dir.glob("*_quality.json"):
        up[f.stem.replace("_quality", "")] = json.loads(f.read_text())
    return {"demo": demo, "uploaded": up, "metadata": P.metadata()}


def refresh(seed=None, retrain=False):
    seed = int(seed) if seed is not None else int(datetime.now().timestamp()) % 100000
    meta = generate(settings.demo_dir, seed)
    P.clear_cache()
    report = quality_report()["demo"]
    if any(v["status"] == "invalid" for v in report.values()):
        raise ValueError("Generated data failed validation")
    if retrain: P.retrain_all()
    return {"metadata": meta, "retrained": bool(retrain), "validation": {k: v["status"] for k, v in report.items()}}
