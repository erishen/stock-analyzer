from pathlib import Path

from investkit_utils.db.paths import (
    get_asset_lens_db_path,
    get_stock_analysis_db_path,
    get_stock_klines_db_path,
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
