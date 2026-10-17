"""ManganAI FastAPI app: serves the JSON API under /api and the static frontend at /."""
import logging

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .config import settings
from .ml import pipeline as P
from .schemas import FeaturesIn, RefreshIn, ReserveExplainIn, ReservePredictIn, ScenarioIn, ScenarioSaveIn
from .services import analytics as A
from .services import dataops as D

log = logging.getLogger("manganai")
app = FastAPI(title="ManganAI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["*"])


def ok(data, **extra):
    return {"status": "ok", "data": data, **extra}


@app.exception_handler(HTTPException)
async def _http(_, e):
    return JSONResponse({"status": "error", "message": e.detail}, status_code=e.status_code)


@app.exception_handler(RequestValidationError)
async def _val(_, e):
    return JSONResponse({"status": "error", "message": "Invalid input", "details": [x["msg"] for x in e.errors()]}, status_code=422)


@app.exception_handler(Exception)
async def _any(_, e):
    log.exception("Unhandled error")
    return JSONResponse({"status": "error", "message": "Internal server error"}, status_code=500)


@app.on_event("startup")
def _startup():
    database.init_db()
    P.get_model("reserve"); P.get_model("production")


def _row_features(feats):
    base = A.current_features()
    base.update({k: v for k, v in feats.items() if k in base})
    return base


@app.get("/api/health")
def health():
    return ok({"service": "ManganAI", "mode": database.mode, "demo_mode": settings.demo_mode, "xgboost": P.HAS_XGB})


@app.get("/api/dashboard/summary")
def dashboard():
    return ok(A.dashboard_summary())


@app.get("/api/reserves/summary")
def reserves_summary():
    return ok(A.reserve_summary(), metrics=P.get_model("reserve")["metrics"])


@app.get("/api/reserves/map")
def reserves_map():
    return ok(A.reserve_map())


@app.post("/api/reserves/predict")
def reserves_predict(body: ReservePredictIn):
    p = P.predict_reserve(body.features)
    return ok({"manganese_probability": p, "category": A.prob_category(p)})


@app.get("/api/production/history")
def prod_history(days: int = 365):
    return ok(A.production_history(max(7, min(days, 1500))))


@app.get("/api/production/forecast")
def prod_forecast(days: int = 30):
    return ok(A.production_forecast(max(1, min(days, 90))))


@app.post("/api/production/predict")
def prod_predict(body: FeaturesIn):
    f = _row_features(body.features)
    return ok({**A.outcome(f), "features": f})


@app.get("/api/risk/current")
def risk_current():
    f = A.current_features(); o = A.outcome(f)
    return ok({**A.risk(f, o), "outcome": o, "features": f})


@app.post("/api/risk/analyze")
def risk_analyze(body: FeaturesIn):
    f = _row_features(body.features); o = A.outcome(f)
    return ok({**A.risk(f, o), "outcome": o, "features": f})


@app.get("/api/recommendations")
def recs():
    return ok(A.recommendations(A.current_features()))


@app.post("/api/recommendations/generate")
def recs_generate(body: FeaturesIn):
    return ok(A.recommendations(_row_features(body.features)))


@app.post("/api/explain/reserve")
def explain_reserve(body: ReserveExplainIn):
    b = P.get_model("reserve"); df = P.reserve_frame()
    if body.sample_id:
        df = df[df.sample_id == body.sample_id]
        if df.empty:
            raise HTTPException(404, "Sample not found")
        X = P.reserve_X(df.head(1), b["features"])
    else:
        X = pd.DataFrame([{c: b["medians"][c] for c in b["features"]}])
        for k, v in body.features.items():
            if k in X: X[k] = v
    return ok(P.explain(b, X))


@app.post("/api/explain/production")
def explain_production(body: FeaturesIn):
    return ok(P.explain(P.get_model("production"), pd.DataFrame([_row_features(body.features)])))


@app.post("/api/scenario/simulate")
def simulate(body: ScenarioIn):
    return ok(A.scenario(body.model_dump(exclude_none=True)))


@app.post("/api/scenario/save")
def scenario_save(body: ScenarioSaveIn):
    return ok({"stored_in": database.save_scenario(body.name, body.inputs, body.results)})


@app.post("/api/data/upload")
async def upload(dataset: str = Form(...), file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    raw = await file.read(int(settings.max_upload_mb * 1024 * 1024) + 1)
    try:
        return ok(D.handle_upload(dataset, raw))
    except OverflowError as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/data/save/{dataset}")
def data_save(dataset: str):
    try:
        return ok(D.save_temp(dataset))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/data/quality")
def data_quality():
    return ok(D.quality_report())


@app.post("/api/data/refresh")
def data_refresh(body: RefreshIn):
    try:
        return ok(D.refresh(body.seed, body.retrain))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/models/summary")
def models_summary():
    out = {}
    for k in ("reserve", "production"):
        b = P.get_model(k)
        out[k] = {"name": b["name"], "n_train": b["n_train"], "n_test": b["n_test"], "features": b["features"], "metrics": b["metrics"],
                  "all_metrics": b["all_metrics"], "importance": b["importance"], "trained_at": b["trained_at"],
                  "validation": b.get("validation", "Stratified 75/25 split"), "shap": P.global_shap(k)}
    return ok(out, synthetic=True, disclaimer=P.DISCLAIMER, metadata=P.metadata())


@app.get("/api/models/metrics")
def models_metrics():
    return ok({k: {"model": P.get_model(k)["name"], "metrics": P.get_model(k)["metrics"], "all_models": P.get_model(k)["all_metrics"]}
               for k in ("reserve", "production")})


@app.post("/api/models/retrain")
def models_retrain():
    P.retrain_all()
    return ok({"retrained": True})


app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")
