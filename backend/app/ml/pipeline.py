"""Data loading, model training, prediction and explainability."""
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (GradientBoostingClassifier, GradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split

from ..config import settings
from .datagen import generate

try:
    from xgboost import XGBClassifier, XGBRegressor
    HAS_XGB = True
except Exception:  # optional dependency
    HAS_XGB = False

RES_NUM = ["elevation", "slope", "aspect", "rock_strength", "soil_depth", "geological_indicator", "drilling_indicator",
           "sample_grade", "ndvi", "ndwi", "land_surface_temperature", "rainfall", "soil_moisture"]
PROD_FEATS = ["production_target", "working_days", "equipment_downtime", "equipment_availability", "rainfall",
              "soil_moisture", "weather_factor", "blasting_delay", "blasting_duration"]
DISCLAIMER = "SHAP explains model behavior and feature contribution; it does not establish causal relationships."
_data, _models, _cache = {}, {}, {}


def clear_cache():
    _data.clear(); _models.clear(); _cache.clear()


def load(name):
    if name not in _data:
        f = settings.demo_dir / f"{name}.csv"
        if not f.exists():
            generate(settings.demo_dir)
        df = pd.read_csv(f)
        if "date" in df:
            df["date"] = pd.to_datetime(df["date"])
        _data[name] = df
    return _data[name]


def metadata():
    f = settings.demo_dir / "dataset_metadata.json"
    if not f.exists():
        load("geological")
    return json.loads(f.read_text()) if f.exists() else {"synthetic": True}


# ------------------------------------------------------------------ reserve
def reserve_frame():
    return load("geological").merge(load("environmental").drop(columns=["elevation", "slope"]), on="sample_id")


def reserve_X(df, cols=None):
    X = pd.get_dummies(df[RES_NUM + ["geology_type"]], columns=["geology_type"], dtype=float)
    return X if cols is None else X.reindex(columns=cols, fill_value=0.0)


def _importance(m, cols):
    imp = getattr(m, "feature_importances_", None)
    if imp is None:
        imp = np.abs(m.coef_)
    return {c: float(v) for c, v in sorted(zip(cols, np.asarray(imp) / (np.sum(imp) or 1)), key=lambda t: -t[1])}


def train_reserve():
    df = reserve_frame(); X = reserve_X(df); y = df["manganese_presence"]; cols = list(X.columns)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.25, stratify=y, random_state=42)
    cands = {"Random Forest": RandomForestClassifier(300, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1)}
    cands["XGBoost" if HAS_XGB else "Gradient Boosting (XGBoost not installed)"] = (
        XGBClassifier(n_estimators=200, max_depth=4, learning_rate=.08, subsample=.8, colsample_bytree=.8,
                      eval_metric="logloss", random_state=42) if HAS_XGB else GradientBoostingClassifier(random_state=42))
    res = {}
    for n, m in cands.items():
        m.fit(Xtr, ytr); p = m.predict_proba(Xte)[:, 1]; pr = (p >= .5).astype(int)
        res[n] = {"accuracy": accuracy_score(yte, pr), "precision": precision_score(yte, pr), "recall": recall_score(yte, pr),
                  "f1": f1_score(yte, pr), "roc_auc": roc_auc_score(yte, p), "confusion_matrix": confusion_matrix(yte, pr).tolist()}
    best = max(res, key=lambda k: res[k]["roc_auc"])
    b = {"kind": "classifier", "model": cands[best], "name": best, "features": cols, "metrics": res[best], "all_metrics": res,
         "importance": _importance(cands[best], cols), "medians": Xtr.median().to_dict(), "n_train": len(Xtr), "n_test": len(Xte),
         "trained_at": datetime.now().isoformat(timespec="seconds")}
    joblib.dump(b, settings.models_dir / "reserve_model.joblib")
    return b


# --------------------------------------------------------------- production
def train_production():
    df = load("production").sort_values("date").reset_index(drop=True)
    cut = int(len(df) * .8)                                   # chronological split
    Xtr, Xte = df.loc[:cut - 1, PROD_FEATS], df.loc[cut:, PROD_FEATS]
    ytr, yte = df.loc[:cut - 1, "actual_production"], df.loc[cut:, "actual_production"]
    cands = {"Linear Regression": LinearRegression(),
             "Random Forest": RandomForestRegressor(300, max_depth=10, min_samples_leaf=3, random_state=42, n_jobs=-1)}
    cands["XGBoost" if HAS_XGB else "Gradient Boosting (XGBoost not installed)"] = (
        XGBRegressor(n_estimators=300, max_depth=4, learning_rate=.05, subsample=.8, random_state=42) if HAS_XGB
        else GradientBoostingRegressor(random_state=42))
    res = {}
    for n, m in cands.items():
        m.fit(Xtr, ytr); p = m.predict(Xte); ok = yte.values > 0
        res[n] = {"mae": mean_absolute_error(yte, p), "rmse": float(np.sqrt(mean_squared_error(yte, p))), "r2": r2_score(yte, p),
                  "mape": float(np.mean(np.abs((yte.values[ok] - p[ok]) / yte.values[ok])) * 100)}
    best = min(res, key=lambda k: res[k]["rmse"])
    m = cands[best]
    if best == "Linear Regression":                          # standardized coefficients as importance
        m.coef_ = m.coef_  # keep
        imp = {c: abs(co) * Xtr[c].std() for c, co in zip(PROD_FEATS, m.coef_)}
        tot = sum(imp.values()) or 1
        importance = {k: v / tot for k, v in sorted(imp.items(), key=lambda t: -t[1])}
    else:
        importance = _importance(m, PROD_FEATS)
    b = {"kind": "regressor", "model": m, "name": best, "features": PROD_FEATS, "metrics": res[best], "all_metrics": res,
         "importance": importance, "medians": Xtr.median().to_dict(), "n_train": len(Xtr), "n_test": len(Xte),
         "validation": f"Chronological split: train to {df.loc[cut - 1, 'date'].date()}, test {df.loc[cut, 'date'].date()} onward",
         "trained_at": datetime.now().isoformat(timespec="seconds")}
    joblib.dump(b, settings.models_dir / "production_model.joblib")
    return b


def get_model(kind):
    if kind not in _models:
        f = settings.models_dir / f"{kind}_model.joblib"
        _models[kind] = joblib.load(f) if f.exists() else (train_reserve() if kind == "reserve" else train_production())
    return _models[kind]


def retrain_all():
    _models.clear(); _cache.clear()
    _models["reserve"], _models["production"] = train_reserve(), train_production()


def _pred(b, X):
    X = X[b["features"]]
    return b["model"].predict_proba(X)[:, 1] if b["kind"] == "classifier" else b["model"].predict(X)


def reserve_probs():
    if "probs" not in _cache:
        b = get_model("reserve"); df = reserve_frame()
        _cache["probs"] = (df, _pred(b, reserve_X(df, b["features"])))
    return _cache["probs"]


def predict_reserve(features):
    b = get_model("reserve")
    base = {c: float(b["medians"][c]) for c in b["features"]}
    for k, v in features.items():
        if k == "geology_type":
            col = f"geology_type_{v}"
            if col in base:
                for c in b["features"]:
                    if c.startswith("geology_type_"): base[c] = 0.0
                base[col] = 1.0
        elif k in base:
            base[k] = float(v)
    return float(_pred(b, pd.DataFrame([base]))[0])


def predict_prod_df(X):
    return _pred(get_model("production"), X)


# ----------------------------------------------------------------- explain
def contributions(b, X):
    """Matrix of per-feature contributions (SHAP if available for tree models, else median-occlusion)."""
    X = X[b["features"]].reset_index(drop=True)
    try:
        if b["name"].startswith("Linear"):
            raise ValueError
        import shap
        sv = shap.TreeExplainer(b["model"]).shap_values(X)
        sv = sv[-1] if isinstance(sv, list) else np.asarray(sv)
        return (sv[:, :, -1] if sv.ndim == 3 else sv), "SHAP (TreeExplainer)"
    except Exception:
        base, out = _pred(b, X), np.zeros(X.shape)
        for j, c in enumerate(b["features"]):
            X2 = X.copy(); X2[c] = b["medians"][c]
            out[:, j] = base - _pred(b, X2)
        return out, "Occlusion vs. training medians (SHAP library not installed)"


def explain(b, row, top=8):
    C, method = contributions(b, row)
    items = sorted(({"feature": f, "value": float(row[f].iloc[0]), "contribution": float(c)}
                    for f, c in zip(b["features"], C[0])), key=lambda d: -abs(d["contribution"]))[:top]
    return {"method": method, "prediction": float(_pred(b, row)[0]), "contributions": items,
            "positive": [i for i in items if i["contribution"] > 0], "negative": [i for i in items if i["contribution"] < 0],
            "disclaimer": DISCLAIMER}


def global_shap(kind, n=100):
    key = f"gshap_{kind}"
    if key not in _cache:
        b = get_model(kind)
        X = reserve_X(reserve_frame(), b["features"]) if kind == "reserve" else load("production")[PROD_FEATS]
        C, method = contributions(b, X.sample(min(n, len(X)), random_state=1))
        imp = np.abs(C).mean(axis=0)
        _cache[key] = {"method": method, "importance": {f: float(v) for f, v in sorted(zip(b["features"], imp), key=lambda t: -t[1])}}
    return _cache[key]
