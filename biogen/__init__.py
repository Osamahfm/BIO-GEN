"""BIO-GEN's connected, evidence-tracked research workflow."""
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'data/matplotlib-cache'))
