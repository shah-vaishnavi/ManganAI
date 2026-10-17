"""Risk engine, recommendations, scenario simulation and summaries (all computed from data/models)."""
import numpy as np
import pandas as pd

from ..ml import pipeline as P
from ..ml.datagen import weather_risk

LEVELS = [(25, "LOW"), (50, "MEDIUM"), (75, "HIGH"), (100, "CRITICAL")]
OVERRIDABLE = ["equipment_downtime", "equipment_availability", "rainfall", "weather_factor", "blasting_delay", "working_days"]


def level(score):
    return next(n for t, n in LEVELS if score <= t)


def prob_category(p):
    return "Low" if p < .25 else "Moderate" if p < .5 else "High" if p < .75 else "Very High"


def current_features(window=30):
    last = P.load("production").sort_values("date").tail(window)
    f = {k: float(last[k].mean()) for k in P.PROD_FEATS}
    f["working_days"] = float(round(f["working_days"]))
    return f


def outcome(feats):
    pred = float(P.predict_prod_df(pd.DataFrame([feats]))[0])
    t = float(feats["production_target"])
    short = max(t - pred, 0.0)
    return {"production_target": t, "predicted_production": pred, "expected_shortfall": short,
            "shortfall_percentage": short / t * 100 if t > 0 else 0.0}


def risk(feats, out=None):
    out = out or outcome(feats)
    wr = weather_risk(feats["rainfall"], feats["soil_moisture"])
    spec = [("Production shortfall", "shortfall_percentage", out["shortfall_percentage"], 30, lambda v: v / 25, "%"),
            ("Equipment downtime", "equipment_downtime", feats["equipment_downtime"], 20, lambda v: v / 10, "h/day"),
            ("Equipment availability", "equipment_availability", feats["equipment_availability"], 15, lambda v: (1 - v) / .4, ""),
            ("Rainfall", "rainfall", feats["rainfall"], 15, lambda v: v / 50, "mm/day"),
            ("Weather risk", "weather_risk", wr, 10, lambda v: v / 100, "/100"),
            ("Blasting delay", "blasting_delay", feats["blasting_delay"], 10, lambda v: v / 6, "h")]
    factors = []
    for name, key, val, w, fn, unit in spec:
        norm = float(np.clip(fn(val), 0, 1))
        factors.append({"factor": name, "key": key, "value": float(val), "unit": unit, "weight": w, "contribution": round(norm * w, 2)})
    score = round(sum(f["contribution"] for f in factors), 1)
    factors.sort(key=lambda f: -f["contribution"])
    return {"score": score, "level": level(score), "factors": factors}


def recommendations(feats, out=None):
    out = out or outcome(feats)
    wr = weather_risk(feats["rainfall"], feats["soil_moisture"])
    rules = [
        ("equipment_downtime", feats["equipment_downtime"], 4.0, ">", "Schedule preventive maintenance",
         "Average daily downtime exceeds the acceptable level and directly reduces equipment availability.", 6.0),
        ("equipment_availability", feats["equipment_availability"], .82, "<", "Reallocate or add equipment capacity",
         "Fleet availability is below target; rebalance excavators/trucks or bring standby units online.", .75),
        ("blasting_delay", feats["blasting_delay"], 2.0, ">", "Re-plan blasting schedule",
         "Blast delays are cutting into face availability; pre-clear exclusion zones and fix blast windows.", 3.5),
        ("rainfall", feats["rainfall"], 20.0, ">", "Adopt wet-weather operating plan",
         "High rainfall lowers the weather factor; prioritise drainage, haul-road upkeep and flexible shifts.", 35.0),
        ("weather_risk", wr, 50.0, ">", "Re-sequence work around weather risk",
         "Combined rainfall/soil-moisture risk is elevated; shift exposed activities to dry windows.", 70.0),
        ("shortfall_percentage", out["shortfall_percentage"], 5.0, ">", "Intervene to close production gap",
         "Model-predicted production is below target; review bottlenecks listed above and raise shift output.", 12.0)]
    recs = []
    for key, val, thr, op, title, why, crit in rules:
        hit = val > thr if op == ">" else val < thr
        if hit:
            crit_hit = val > crit if op == ">" else val < crit
            recs.append({"priority": "High" if crit_hit else "Medium", "title": title, "reason": why, "affected_factor": key,
                         "current_value": round(float(val), 3), "threshold": thr})
    if not recs:
        recs.append({"priority": "Low", "title": "Operations within thresholds", "reason": "No monitored factor breaches its threshold.",
                     "affected_factor": "all", "current_value": None, "threshold": None})
    return sorted(recs, key=lambda r: {"High": 0, "Medium": 1, "Low": 2}[r["priority"]])


def scenario(overrides):
    cur = current_features()
    new = dict(cur)
    for k, v in (overrides or {}).items():
        if k in OVERRIDABLE and v is not None:
            new[k] = float(v)
    a, b = outcome(cur), outcome(new)
    ra, rb = risk(cur, a), risk(new, b)
    return {"current": {**a, "risk_score": ra["score"], "risk_level": ra["level"], "features": cur},
            "scenario": {**b, "risk_score": rb["score"], "risk_level": rb["level"], "features": new},
            "impact": {"production_difference": b["predicted_production"] - a["predicted_production"],
                       "shortfall_difference": b["expected_shortfall"] - a["expected_shortfall"],
                       "risk_difference": round(rb["score"] - ra["score"], 1)},
            "recommendations": recommendations(new, b)}


def production_history(days=365):
    df = P.load("production").sort_values("date").tail(int(days)).copy()
    df["predicted"] = P.predict_prod_df(df)
    return {"dates": df.date.dt.strftime("%Y-%m-%d").tolist(), "target": df.production_target.round(1).tolist(),
            "actual": df.actual_production.round(1).tolist(), "predicted": df.predicted.round(1).tolist(),
            "rainfall": df.rainfall.tolist()}


def production_forecast(days=30):
    p = P.load("production").sort_values("date")
    prof = p.assign(doy=p.date.dt.dayofyear).groupby("doy")[P.PROD_FEATS].mean()
    last = p.date.max(); cur_t = float(p.tail(30).production_target.mean())
    dates = pd.date_range(last + pd.Timedelta(days=1), periods=int(days))
    rows = []
    for i, d in enumerate(dates):
        r = prof.loc[d.dayofyear].copy() if d.dayofyear in prof.index else prof.mean()
        r["production_target"] = cur_t + .12 * (i + 1)
        r["working_days"] = round(r["working_days"])
        rows.append(r)
    X = pd.DataFrame(rows)
    pred = P.predict_prod_df(X)
    return {"dates": dates.strftime("%Y-%m-%d").tolist(), "target": X.production_target.round(1).tolist(),
            "predicted": np.round(pred, 1).tolist(), "shortfall": np.round(np.maximum(X.production_target.values - pred, 0), 1).tolist()}


def reserve_map(zone=None):
    df, prob = P.reserve_probs(); df = df.assign(prob=prob)
    df["zone"] = np.where(df.latitude >= 21.2, "North", "South") + "-" + np.where(df.longitude >= 79.4, "East", "West")
    pts = [{"id": r.sample_id, "lat": r.latitude, "lon": r.longitude, "prob": round(float(r.prob), 3), "category": prob_category(r.prob),
            "geology": r.geology_type, "grade": r.sample_grade, "zone": r.zone, "geo_ind": r.geological_indicator,
            "drill_ind": r.drilling_indicator, "ndvi": r.ndvi, "ndwi": r.ndwi, "lst": r.land_surface_temperature,
            "rainfall": r.rainfall, "soil_moisture": r.soil_moisture, "elevation": r.elevation}
           for r in df.itertuples()]
    dr = P.load("drilling")
    nn = np.argmin((dr.latitude.values[:, None] - df.latitude.values) ** 2 + (dr.longitude.values[:, None] - df.longitude.values) ** 2, axis=1)
    drill = [{"id": r.drill_id, "lat": r.latitude, "lon": r.longitude, "depth": r.depth, "rock": r.rock_type, "grade": r.sample_grade,
              "ore_ind": r.ore_indicator, "geo_ind": r.geological_indicator, "prob": round(float(prob[j]), 3),
              "category": prob_category(prob[j])} for r, j in zip(dr.itertuples(), nn)]
    return {"samples": pts, "drilling": drill, "geologies": sorted(df.geology_type.unique().tolist()), "zones": sorted(df.zone.unique().tolist())}


def reserve_summary():
    df, prob = P.reserve_probs()
    cats = pd.Series([prob_category(p) for p in prob]).value_counts().reindex(["Low", "Moderate", "High", "Very High"], fill_value=0)
    g = df.assign(prob=prob, zone=np.where(df.latitude >= 21.2, "North", "South") + "-" + np.where(df.longitude >= 79.4, "East", "West"))
    return {"mapped_samples": int(len(df)), "drilling_points": int(len(P.load("drilling"))), "mean_probability": float(prob.mean()),
            "high_probability_samples": int((prob >= .5).sum()),
            "categories": {k: int(v) for k, v in cats.items()},
            "zones": [{"zone": z, "mean_probability": float(s.prob.mean()), "samples": int(len(s))} for z, s in g.groupby("zone")]}


def dashboard_summary():
    cur = current_features(); out = outcome(cur); r = risk(cur, out); rs = reserve_summary()
    rb, pb = P.get_model("reserve"), P.get_model("production")
    return {"kpis": {"mapped_samples": rs["mapped_samples"], "high_probability_zones": rs["high_probability_samples"],
                     "production_target": out["production_target"], "predicted_production": out["predicted_production"],
                     "expected_shortfall": out["expected_shortfall"], "shortfall_percentage": out["shortfall_percentage"],
                     "risk_score": r["score"], "risk_level": r["level"]},
            "models": {"reserve": {"name": rb["name"], "roc_auc": rb["metrics"]["roc_auc"], "trained_at": rb["trained_at"]},
                       "production": {"name": pb["name"], "r2": pb["metrics"]["r2"], "mape": pb["metrics"]["mape"], "trained_at": pb["trained_at"]}},
            "data": P.metadata(), "top_risk_factors": r["factors"][:4]}
