import os
from pathlib import Path

_INVESTKIT_ROOT = Path(__file__).parent.parent
DATA_DIR = _INVESTKIT_ROOT / "data"


def _load_env():
    for env_path in [_INVESTKIT_ROOT / ".env", Path.cwd() / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        if key and key not in os.environ:
                            os.environ[key] = value


_load_env()


def _resolve_path(env_value: str) -> Path:
    p = Path(env_value)
    if not p.is_absolute():
        p = _INVESTKIT_ROOT / p
    return p.resolve()


def get_db_path(db_name: str = "asset_lens.db") -> Path:
    env_key = f"{db_name.replace('.', '_').upper()}_PATH"
    env_path = os.environ.get(env_key)
    if env_path:
        return _resolve_path(env_path)
    env_path = os.environ.get("INVESTKIT_DB_PATH")
    if env_path:
        return _resolve_path(env_path) / db_name
    return DATA_DIR / db_name


def get_asset_lens_db_path() -> Path:
    env_path = os.environ.get("ASSET_LENS_DB_PATH")
    if env_path:
        return _resolve_path(env_path)
    return get_db_path("asset_lens.db")


def get_stock_analysis_db_path() -> Path:
    env_path = os.environ.get("STOCK_ANALYSIS_DB_PATH")
    if env_path:
        return _resolve_path(env_path)
    return get_db_path("stock_analysis.db")


def get_stock_klines_db_path() -> Path:
    env_path = os.environ.get("STOCK_KLINES_DB_PATH")
    if env_path:
        return _resolve_path(env_path)
    return get_db_path("stock_klines.db")


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
