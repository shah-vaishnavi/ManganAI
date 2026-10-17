"""Synthetic (demo) manganese-mining dataset generator with causal-style relationships."""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

GEOLOGY = ["Laterite", "Phyllite", "Quartzite", "Shale", "Dolomite", "Granite"]
EQUIPMENT = ["Excavator", "Dump Truck", "Drill Machine", "Loader", "Crusher"]


def _sig(x):
    return 1 / (1 + np.exp(-x))


def weather_risk(rain, soil_moisture):
    """0-100 weather risk from rainfall (mm/day) and soil moisture (0-1). Works on scalars and arrays."""
    r = np.clip(np.asarray(rain, float) + 0 * np.asarray(soil_moisture, float), 0, None) / 60 * 60 \
        + np.maximum(np.asarray(soil_moisture, float) - 0.25, 0) * 100
    r = np.clip(r, 0, 100)
    return float(r) if r.ndim == 0 else r


def generate(outdir, seed=42):
    rng = np.random.default_rng(seed)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    # ---------- Geological + environmental ----------
    n = 1500
    bodies = np.array([[21.30, 79.30], [21.12, 79.55], [21.22, 79.42]])
    lat, lon = rng.uniform(21.0, 21.4, n), rng.uniform(79.2, 79.6, n)
    dist = np.min(np.hypot(lat[:, None] - bodies[:, 0], lon[:, None] - bodies[:, 1]), axis=1)
    prox = np.exp(-dist / 0.06)
    geo = rng.choice(GEOLOGY, n, p=[.2, .2, .18, .18, .14, .1])
    fav = pd.Series(geo).map({"Laterite": .5, "Phyllite": .6, "Quartzite": .1, "Shale": .3, "Dolomite": .4, "Granite": -.4}).values
    z = 3.2 * prox + fav + rng.normal(0, .7, n) - 1.6          # latent mineralization signal
    pres = (rng.random(n) < _sig(2 * z)).astype(int)
    ids = [f"GS{i:04d}" for i in range(n)]
    elev = 320 + 120 * prox + rng.normal(0, 40, n)
    slope = np.clip(rng.gamma(2.5, 4, n), 0, 45)
    geol = pd.DataFrame({
        "sample_id": ids, "latitude": lat.round(5), "longitude": lon.round(5), "elevation": elev.round(1),
        "slope": slope.round(1), "aspect": rng.uniform(0, 360, n).round(0), "geology_type": geo,
        "rock_strength": np.clip(rng.normal(70, 25, n) - 10 * (geo == "Shale"), 15, 160).round(1),
        "soil_depth": np.clip(rng.gamma(2, 1.2, n) + 1.5 * (geo == "Laterite"), .1, 15).round(2),
        "geological_indicator": np.clip(_sig(z) * .8 + rng.normal(0, .15, n), 0, 1).round(3),
        "drilling_indicator": np.clip(_sig(z) * .75 + rng.normal(0, .2, n), 0, 1).round(3),
        "sample_grade": np.clip(8 + 22 * _sig(z) + rng.normal(0, 7, n), 0, 48).round(2),
        "manganese_presence": pres})
    env = pd.DataFrame({
        "sample_id": ids, "ndvi": np.clip(.5 - .2 * prox + rng.normal(0, .12, n), -.1, .9).round(3),
        "ndwi": np.clip(-.1 + rng.normal(0, .12, n) + .002 * (400 - elev) / 10, -.5, .6).round(3),
        "land_surface_temperature": (31 + 4 * prox + rng.normal(0, 2.5, n)).round(1),
        "rainfall": np.clip(rng.normal(1100, 150, n), 600, 1700).round(0),
        "soil_moisture": np.clip(.25 + rng.normal(0, .07, n), .05, .6).round(3),
        "elevation": elev.round(1), "slope": slope.round(1)})
    m = 400
    idx = rng.choice(n, m, replace=False)
    drill = pd.DataFrame({
        "drill_id": [f"DH{i:03d}" for i in range(m)],
        "latitude": (lat[idx] + rng.normal(0, .002, m)).round(5), "longitude": (lon[idx] + rng.normal(0, .002, m)).round(5),
        "depth": rng.uniform(20, 300, m).round(1), "rock_type": geo[idx],
        "geological_indicator": np.clip(geol.geological_indicator.values[idx] + rng.normal(0, .05, m), 0, 1).round(3),
        "ore_indicator": np.clip(geol.drilling_indicator.values[idx] + rng.normal(0, .08, m), 0, 1).round(3),
        "sample_grade": np.clip(geol.sample_grade.values[idx] + rng.normal(0, 2.5, m), 0, 50).round(2)})

    # ---------- Daily weather / blasting / production (3 years) ----------
    N = 1095
    dates = pd.date_range("2023-10-01", periods=N, freq="D")
    doy = dates.dayofyear.values
    season = np.exp(-((doy - 200) / 45) ** 2)                      # monsoon peak ~ mid-July
    rain = (rng.random(N) < (.08 + .7 * season)) * rng.gamma(2, 6 + 14 * season)
    sm = np.zeros(N); s = .15
    for i in range(N):
        s = np.clip(.85 * s + .004 * rain[i] + .012, .05, .6); sm[i] = s
    temp = 27 + 8 * np.sin((doy - 90) / 365 * 2 * np.pi) - 3 * season + rng.normal(0, 1.5, N)
    wf = np.clip(1 - .006 * rain - .35 * np.maximum(sm - .3, 0), .55, 1)
    weather = pd.DataFrame({"date": dates, "rainfall": rain.round(1), "temperature": temp.round(1),
                            "soil_moisture": sm.round(3), "weather_risk": np.round(weather_risk(rain, sm), 1)})

    down = np.clip(rng.gamma(2, 1.2, N) + 2.5 * season + 3 * ((np.arange(N) % 25) < 3), 0, 14)
    avail = np.clip(1 - down / 16, .3, 1)
    ef = avail ** .9
    planned = rng.random(N) < .55
    delay = np.where(rng.random(N) < .2 + .4 * (rain > 10), rng.gamma(2, 1.5, N), 0).clip(0, 10)
    dur = np.where(planned, np.clip(rng.normal(2.5, .6, N), 1, 5) + delay, 0)
    bf = np.clip(1 - .03 * delay, .7, 1)
    wd = np.repeat(rng.choice([5, 6, 7], size=N // 7 + 1, p=[.3, .5, .2]), 7)[:N]
    tgt = 1000 + .12 * np.arange(N)
    actual = tgt * 1.18 * wf * bf * ef * (wd / 6) ** .6 * np.exp(rng.normal(0, .035, N))
    prod = pd.DataFrame({
        "date": dates, "mine_id": "MN-01", "production_target": tgt.round(1), "actual_production": actual.round(1),
        "working_days": wd, "equipment_downtime": down.round(2), "equipment_availability": avail.round(3),
        "rainfall": rain.round(1), "soil_moisture": sm.round(3), "weather_factor": wf.round(3),
        "blasting_delay": delay.round(2), "blasting_duration": dur.round(2), "blasting_factor": bf.round(3),
        "equipment_factor": ef.round(3)})

    bi = np.sort(rng.choice(N, 400, replace=False))
    reason = np.where(rain[bi] > 15, "Weather", rng.choice(["Equipment", "Safety clearance", "Permit"], 400))
    blast = pd.DataFrame({"date": dates[bi], "blast_id": [f"BL{i:04d}" for i in range(400)], "planned_blast": 1,
                          "blast_duration": np.maximum(dur[bi], 1).round(2), "delay_hours": delay[bi].round(2),
                          "delay_reason": np.where(delay[bi] > 0, reason, "None"), "blasting_factor": bf[bi].round(3)})

    rows = []
    for et, mult in zip(EQUIPMENT, [1.0, 1.15, .9, .8, .7]):
        ei = np.sort(rng.choice(N, 150, replace=False))
        dt = np.clip(down[ei] * mult + rng.normal(0, .6, 150), 0, 16)
        av = np.clip(1 - dt / 16, .3, 1)
        rows.append(pd.DataFrame({"equipment_id": f"{et[:3].upper()}-{rng.integers(1, 4):02d}", "date": dates[ei],
                                  "equipment_type": et, "availability": av.round(3), "downtime_hours": dt.round(2),
                                  "maintenance_hours": rng.gamma(2, .8, 150).round(2),
                                  "utilization": np.clip(av * .85 + rng.normal(0, .04, 150), .2, 1).round(3)}))
    equip = pd.concat(rows, ignore_index=True)

    tables = dict(geological=geol, environmental=env, drilling=drill, production=prod, equipment=equip,
                  weather=weather, blasting=blast)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
    meta = {"synthetic": True, "seed": int(seed), "generated_at": datetime.now().isoformat(timespec="seconds"),
            "rows": {k: int(len(v)) for k, v in tables.items()}}
    (out / "dataset_metadata.json").write_text(json.dumps(meta, indent=2))
    return meta
