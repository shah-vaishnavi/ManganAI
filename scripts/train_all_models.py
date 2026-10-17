import subprocess, sys
from pathlib import Path
here = Path(__file__).parent
for s in ("generate_demo_data.py", "train_reserve_model.py", "train_production_model.py"):
    subprocess.run([sys.executable, str(here / s)], check=True)
