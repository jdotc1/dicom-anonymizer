"""Run the bundled engine with its bundled, pinned pydicom dependency."""
from pathlib import Path
import runpy
import sys

resources = Path(__file__).resolve().parent
sys.path.insert(0, str(resources / "vendor"))
sys.path.insert(0, str(resources / "engine"))
runpy.run_path(str(resources / "engine" / "engine.py"), run_name="__main__")
