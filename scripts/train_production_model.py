import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.ml import pipeline as p

if __name__ == "__main__":
    b = p.train_production()
    print(b["name"], {k: round(v, 3) for k, v in b["metrics"].items()}, b["validation"])
