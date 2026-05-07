import sys
from pathlib import Path

src_dir = str(Path(__file__).parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
