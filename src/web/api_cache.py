"""Web 接口结果缓存

慢接口 (扫描/回测/组合/行业/择时) 计算耗时长, 每次点开都重算体验差。
数据每日更新, 这里按「接口 + 请求参数哈希 + 数据最新日期」落盘缓存:
  - 首次请求: 真计算, 结果写入 data/cache/{key}.json
  - 之后同参数请求: 直接读缓存瞬显
  - 数据更新 (分析库 MAX(date) 变化): key 自动变化, 重新计算
  - 提供 refresh 参数强制重算
"""

import hashlib
import json
import logging
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 分析库最新日期 -> 缓存 key 的一部分 (数据更新后自动失效)
_DB_PATH = None
_latest_date_cache: tuple[str, str] | None = None  # (db_path, date)

# 缓存文件保留天数(按最后修改时间), 旧于该天数的启动时清理避免无限膨胀
CACHE_KEEP_DAYS = 14


def init_cache(db_path: Path):
    global _DB_PATH
    _DB_PATH = db_path
    clean_old_caches(CACHE_KEEP_DAYS)


def clean_old_caches(keep_days: int = CACHE_KEEP_DAYS) -> int:
    """清理 data/cache 下超过 keep_days 未修改的旧缓存文件, 返回删除数。

    缓存文件名含数据日期, 数据更新后 key 自动变化, 旧日期的文件会残留;
    这里按文件 mtime 兜底清理, 避免目录随每日更新无限膨胀。
    """
    d = cache_dir()
    if not d.exists():
        return 0
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for p in d.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("清理 %d 个过期接口缓存 (%s)", removed, d)
    return removed


def _get_latest_date() -> str:
    global _latest_date_cache
    if _latest_date_cache and _latest_date_cache[0] == str(_DB_PATH):
        return _latest_date_cache[1]
    date = ""
    try:
        with sqlite3.connect(str(_DB_PATH)) as conn:
            row = conn.execute("SELECT MAX(date) FROM stock_analysis").fetchone()
            date = row[0] or ""
    except Exception:
        date = ""
    _latest_date_cache = (str(_DB_PATH), date)
    return date


def cache_dir() -> Path:
    d = Path(_DB_PATH).parent.parent / "data" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_key(endpoint: str, params: dict[str, Any]) -> str:
    """生成缓存文件名: {endpoint}_{datelatest}_{params_hash}.json"""
    params_hash = hashlib.md5(
        json.dumps(params, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()[:12]
    return f"{endpoint}_{_get_latest_date()}_{params_hash}"


def run_cached(
    endpoint: str,
    params: dict[str, Any],
    compute: Callable[[], Any],
    *,
    force_refresh: bool = False,
) -> dict:
    """带缓存地执行 compute(), 返回 JSON 可序列化 dict"""
    key = make_key(endpoint, params)
    path = cache_dir() / f"{key}.json"

    if not force_refresh and path.exists():
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"  [cache hit] {endpoint} <- {path.name}")
            return data
        except Exception:
            pass  # 缓存损坏则重算

    logger.info(f"  [cache miss] {endpoint} 计算中...")
    result = compute()
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"  缓存写入失败: {e}")
    return result
