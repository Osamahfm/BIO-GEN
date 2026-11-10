import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'data' / 'matplotlib-cache'))
DATA = Path(os.environ.get('BIOGEN_DATA_DIR', ROOT / 'data' / 'cases'))
DATA.mkdir(parents=True, exist_ok=True)
MODELS = ROOT / 'models'
AYUR = ROOT / 'vendor' / 'ayur-ai'
IMPPAT = ROOT / 'vendor' / 'imppat2'
