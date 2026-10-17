# ManganAI — AI-Powered Manganese Mining Intelligence Platform
*From Geological Insight to Production Intelligence*

**Overview.** ManganAI combines geological, drilling, environmental and operational data with ML, GIS-style mapping and explainable AI to estimate manganese mineralization probability, predict production and shortfall, score operational risk, recommend actions and simulate what-if scenarios.
**Data is synthetic (demo)** and generated with realistic cause-and-effect relationships (downtime → availability → production → shortfall → risk; rainfall → weather factor → production). Nothing on screen is hard-coded: `CSV → Pandas → ML/rules → FastAPI → fetch() → UI`.

## Features
Dashboard · Reserve probability map (filters, SHAP per point) · Production history/forecast · Risk engine (transparent weighted score) · Rule-based recommendations · What-if simulator · CSV upload + data-quality checks · Model insights (metrics, importance, SHAP) · Refresh Demo Data / Retrain Models buttons.

## Stack
Frontend: HTML/CSS/JS, Bootstrap 5, Plotly, Leaflet (loaded from CDN → internet needed in the browser). Backend: Python 3.11+, FastAPI, Pydantic, SQLAlchemy. ML: pandas, scikit-learn, XGBoost, SHAP, joblib. If XGBoost/SHAP are not installed the app falls back to scikit-learn gradient boosting and an occlusion-based explanation (clearly labelled in the UI).

## Install & run (Windows PowerShell)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts/generate_demo_data.py      # optional (data/demo already included)
python scripts/train_all_models.py        # optional (models are also trained automatically on first start)
uvicorn backend.app.main:app --reload     # then open http://localhost:8000
```
The FastAPI server serves both the API (`/api/...`, docs at `/docs`) and the frontend. Linux/macOS: use `source venv/bin/activate`.

## Optional PostgreSQL/PostGIS
Copy `.env.example` to `.env`, set `DEMO_MODE=false` and `DATABASE_URL=postgresql+psycopg2://...`; load the variables into your shell, then start the server. Tables are created on startup; saved scenarios go to `scenario_runs`. If the database is unreachable the app falls back to demo mode (see `/api/health`).

## Tests
```powershell
pytest -q
```

## Layout
`backend/app/{main,config,database,models,schemas}.py`, `ml/` (data generator, training, SHAP), `services/` (analytics, data ops) · `frontend/` pages + `js/api.js` (all requests) + `js/app.js` · `data/demo`, `data/temp` · `models/` · `scripts/` · `tests/`.

## Demo workflow
Dashboard → Reserve Intelligence (filter, click a point → SHAP) → Production (actual vs target vs ML) → Risk & Actions (score, factors, recommendations) → Scenario Simulator (change inputs → Run) → Model Insights. Then **Refresh Demo Data** (new seed) → **Retrain Models** and watch every number change.

## Limitations & future scope
Synthetic data only; one mine; PostGIS geometry columns not yet used (lat/lon stored); SHAP is not causal; satellite features are supporting indicators only. Future: real data connectors, GeoPandas spatial joins/kriging, multi-mine support, scheduled retraining, auth.
