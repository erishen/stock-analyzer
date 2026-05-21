from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"


def get_stock_analysis_db_path() -> str:
    try:
        from investkit_utils.db import get_stock_analysis_db_path as _get_path

        return _get_path()
    except ImportError:
        return str(DATA_DIR / "stock_analysis.db")


def get_asset_lens_db_path() -> str:
    try:
        from investkit_utils.db import get_asset_lens_db_path as _get_path

        return _get_path()
    except ImportError:
        return str(DATA_DIR / "asset_lens.db")


def get_stock_klines_db_path() -> str:
    try:
        from investkit_utils.db import get_stock_klines_db_path as _get_path

        return _get_path()
    except ImportError:
        return str(DATA_DIR / "stock_klines.db")
